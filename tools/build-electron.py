#!/usr/bin/env python3
"""Build the exact Teams Electron engine privately from its upstream sources."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

from chromium_flatpak import owners, sha

ROOT=Path(__file__).resolve().parents[1]
WORK=(ROOT/'build/chromium-flatpak').resolve()
PINS=dict(electron='44.9.0',electron_commit='fd148b9908b83c8dc09924e45e6df44b83b6bfe7',
          chromium='152.0.7977.167',skia='747cf654ed6f864f4402e7d6eb54a6ede60141e5',
          depot_tools='ec77017fb3e090ff02bffb9c6980ebcdd3006ddc')
TEAMS_COMMIT='2ebbb9bbdf90b5fabf35fb35cfa274884cb5069325f3666b5beb55e53a2aecda'
TEAMS_BINARY='6be064aac9e7a36541f8fece09ce3845016dd9e2700c69eedba68339791a0b91'
PATCH=ROOT/'patches/skia-747cf654-fontreal-trace.patch'
HEADER=ROOT/'tests/skia_owner_trace.h'
BASE_FILES={'src/core/SkScalerContext.cpp':'6a7020ea88c37eaea9817d743c4ed6b022061f96fc81b876b43965e58bfbc27e',
            'src/ports/SkTypeface_fontations.cpp':'3291a320dbfee6f772837cc1b625782c90bc37a09fc94311db2284cce74fedca'}
GN_ARGS='''import("//electron/build/args/release.gn")
override_electron_version="44.9.0"
is_debug=false
is_official_build=false
is_component_build=false
symbol_level=0
blink_symbol_level=0
v8_symbol_level=0
use_thin_lto=false
use_remoteexec=false
use_siso=false
'''
CACHE_DIRECTORIES=dict(GIT_CACHE_PATH='git',VPYTHON_VIRTUALENV_ROOT='vpython',CIPD_CACHE_DIR='cipd',
                       XDG_CACHE_HOME='xdg',CARGO_HOME='cargo',RUSTUP_HOME='rustup',TMPDIR='tmp',
                       PIP_CACHE_DIR='pip',NPM_CONFIG_CACHE='npm',npm_config_cache='npm',
                       YARN_GLOBAL_FOLDER='yarn-global-parent/berry',COREPACK_HOME='corepack',
                       CLANG_MODULE_CACHE_PATH='clang-modules')


def environment():
    env={k:v for k,v in os.environ.items() if not k.startswith('FONTREAL_') and
         k not in ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES')}
    for key,name in CACHE_DIRECTORIES.items():
        path=WORK/'cache'/name;path.mkdir(parents=True,exist_ok=True);env[key]=str(path)
    env.update(DEPOT_TOOLS_UPDATE='0',DEPOT_TOOLS_METRICS='0',PYTHONDONTWRITEBYTECODE='1',
               PATH=str(WORK/'depot_tools')+os.pathsep+os.environ['PATH'])
    return env


def invoke(command,cwd,env,label):
    logpath=WORK/(label+'.log');print(label+': '+str(logpath),flush=True)
    with logpath.open('w') as log:
        result=subprocess.run(list(map(str,command)),cwd=cwd,env=env,stdout=log,stderr=log)
    if result.returncode:raise SystemExit(f'{label} failed with status {result.returncode}; see {logpath}')


def key(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:20]


def package(archive,destination):
    destination.mkdir(parents=True,exist_ok=True); saved=destination/'dist.zip'
    shutil.copyfile(archive,saved); payload=destination/'payload';payload.mkdir(exist_ok=True)
    with zipfile.ZipFile(saved) as bundle:
        for item in bundle.infolist():
            path=payload/item.filename
            if not path.resolve().is_relative_to(payload.resolve()):raise SystemExit('Unsafe path in the generated Electron archive.')
            bundle.extract(item,payload)
            if not item.is_dir():path.chmod((item.external_attr>>16)&0o777)
    files={str(p.relative_to(payload)):sha(p) for p in payload.rglob('*') if p.is_file()}
    if not (payload/'electron').is_file() or not (payload/'electron').stat().st_mode&0o111:
        raise SystemExit('The generated Electron archive has no executable.')
    return dict(archive=str(saved),archive_sha256=sha(saved),directory=str(payload),files=files)


def verify(package):
    payload=Path(package['directory'])
    if sha(Path(package['archive']))!=package['archive_sha256']:raise SystemExit('A retained Electron archive changed.')
    files={str(p.relative_to(payload)):sha(p) for p in payload.rglob('*') if p.is_file()}
    if files!=package['files']:raise SystemExit('A retained Electron distribution changed.')


def source_identity(checkout):
    heads={name:subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout/name,text=True).strip()
           for name in ('src','src/electron','src/third_party/skia')}
    return dict(pins=PINS,heads=heads,configuration=sha(checkout/'.gclient'),entries=sha(checkout/'.gclient_entries'))


def main():
    WORK.mkdir(parents=True,exist_ok=True);env=environment();depot=WORK/'depot_tools'
    base_spec=dict(pins=PINS,gn_args=GN_ARGS,source_files=BASE_FILES)
    spec=dict(base_spec,recipe=sha(Path(__file__)),patch=sha(PATCH),header=sha(HEADER),
              target_commit=TEAMS_COMMIT,target_binary=TEAMS_BINARY)
    artifact=WORK/'artifacts'/key(spec);record=artifact/'build.json'
    if record.exists():
        saved=json.loads(record.read_text())
        if saved['spec']!=spec:raise SystemExit('The Electron artifact identity changed.')
        for value in saved['packages'].values():verify(value)
        print(record);return
    if not depot.exists():
        invoke(['git','clone','--no-checkout','https://chromium.googlesource.com/chromium/tools/depot_tools.git',depot],WORK,env,'depot-clone')
        invoke(['git','checkout',PINS['depot_tools']],depot,env,'depot-pin')
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=depot,text=True).strip()
    if actual!=PINS['depot_tools']:raise SystemExit('The private depot_tools checkout differs from its pinned revision.')
    invoke([depot/'ensure_bootstrap'],WORK,env,'depot-bootstrap')
    checkout=WORK/('electron-'+PINS['electron']);checkout.mkdir(exist_ok=True)
    text='solutions = [\n  {"name": "src/electron", "url": "https://github.com/electron/electron.git@'+PINS['electron_commit']+'", "deps_file": "DEPS", "managed": False, "custom_deps": {}, "custom_vars": {}},\n]\ntarget_os = ["linux"]\n'
    config=checkout/'.gclient'
    if config.exists() and config.read_text()!=text:raise SystemExit('The private gclient configuration changed outside Fontreal.')
    config.write_text(text)
    receipt=checkout/'.fontreal-source.json'
    if receipt.exists():
        if json.loads(receipt.read_text())!=source_identity(checkout):raise SystemExit('The prepared source identity changed.')
    else:
        invoke([depot/'gclient','sync','--no-history','--nohooks','--jobs=8'],checkout,env,'fetch')
        invoke([depot/'gclient','runhooks'],checkout,env,'hooks')
        receipt.write_text(json.dumps(source_identity(checkout),indent=2)+'\n')
    source=checkout/'src';skia=source/'third_party/skia'
    for name,digest in BASE_FILES.items():
        if sha(skia/name)!=digest:raise SystemExit(f'The exact Skia source does not match: {name}')
    out=source/'out/Fontreal'
    if (out/'args.gn').exists() and (out/'args.gn').read_text()!=GN_ARGS:
        out=source/'out'/('Fontreal-'+key(base_spec))
    if (out/'args.gn').exists() and (out/'args.gn').read_text()!=GN_ARGS:
        raise SystemExit('The private output tree has a different GN configuration.')
    out.mkdir(parents=True,exist_ok=True)
    (out/'args.gn').write_text(GN_ARGS)
    invoke([source/'buildtools/linux64/gn','gen',out],source,env,'gn')
    ninja=[source/'third_party/ninja/ninja','-C',out,'-j'+str(min(24,os.cpu_count() or 1)),'electron:electron_dist_zip']
    stock_dir=WORK/'stock'/key(base_spec);stock_record=stock_dir/'package.json'
    marker=out/'fontreal-instrumented.json'
    if stock_record.exists():
        stock=json.loads(stock_record.read_text());verify(stock)
    else:
        if marker.exists():raise SystemExit('The retained stock artifact is missing; this output tree contains instrumentation.')
        invoke(ninja,source,env,'stock-build')
        stock=package(out/'dist.zip',stock_dir)
        stock_record.write_text(json.dumps(stock,indent=2)+'\n')
    artifact.mkdir(parents=True,exist_ok=True)
    views=artifact/'source-view';views.mkdir(exist_ok=True)
    for folder in ('src/core','src/ports'):
        destination=views/folder
        if destination.exists():shutil.rmtree(destination)
        shutil.copytree(skia/folder,destination,symlinks=True)
    invoke(['patch','--batch','--fuzz=0','-p1','-i',PATCH],views,env,'trace-patch')
    shutil.copyfile(HEADER,views/'src/core/fontreal_owner_trace.h')
    marker.write_text(json.dumps(dict(spec=spec,stock_archive=stock['archive_sha256']),indent=2)+'\n')
    # A plain root bind makes device nodes unusable; Ninja opens /dev/null.
    command=['bwrap','--ro-bind','/','/','--dev','/dev','--bind',out,out,'--bind',WORK/'cache',WORK/'cache']
    for folder in ('src/core','src/ports'):command+=['--ro-bind',views/folder,skia/folder]
    invoke([*command,'--',*ninja],source,env,'instrumented-build')
    instrumented=package(out/'dist.zip',artifact/'instrumented')
    shutil.copyfile(ROOT/'LICENSE',artifact/'FONTREAL-LICENSE.txt')
    shutil.copyfile(skia/'LICENSE',artifact/'SKIA-LICENSE.txt')
    for name,digest in BASE_FILES.items():
        if sha(skia/name)!=digest:raise SystemExit('The upstream Skia checkout changed during the private build.')
    record.write_text(json.dumps(dict(spec=spec,source=str(source),source_view=str(views),
                                     source_identity=source_identity(checkout),
                                     cache_environment={name:env[name] for name in CACHE_DIRECTORIES},
                                     packages=dict(stock=stock,instrumented=instrumented)),indent=2)+'\n')
    print(record)


if __name__=='__main__':main()
