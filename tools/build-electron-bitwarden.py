#!/usr/bin/env python3
"""Build Bitwarden's exact Electron 39 engine without changing its app or data."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
module=importlib.util.spec_from_file_location('electron_shared_builder',ROOT/'tools/build-electron.py')
shared=importlib.util.module_from_spec(module);module.loader.exec_module(shared)
WORK=(ROOT/'build/chromium-flatpak/bitwarden').resolve()
shared.WORK=WORK
sha=shared.sha
key=shared.key
package=shared.package
verify=shared.verify
invoke=shared.invoke
CACHE_DIRECTORIES=shared.CACHE_DIRECTORIES
PINS=dict(electron='39.8.5',electron_commit='9d2f8cb4da0d35e2daf7e7f60e35313b508cb224',
          chromium='142.0.7444.265',skia='f4ed99d2443962782cf5f8b4dd27179f131e7cbe',
          node='22.22.1',node_base='b4acf0c9393e4b31c4937564f059c672967161d8',
          depot_tools='ec77017fb3e090ff02bffb9c6980ebcdd3006ddc')
PATCH=ROOT/'patches/skia-f4ed99d2-fontreal-trace.patch'
HEADER=ROOT/'tests/skia_owner_trace.h'
BASE_FILES={'src/core/SkScalerContext.cpp':'d853296cac33e83bef60b31dbdec7a94780ca3f26c03723f93a83f0e6fe809d8',
            'src/ports/SkTypeface_fontations.cpp':'db6cff4e3675a6dcf5d1f268368fdc3cf5498d3da4a6cfc73249c02838490f25'}
GN_ARGS=shared.GN_ARGS.replace('override_electron_version="44.9.0"','override_electron_version="39.8.5"')


def environment():
    env=shared.environment()
    env['PATH']=str(WORK/'host-tools/usr/bin')+os.pathsep+env['PATH']
    return env


def source_identity(checkout):
    heads={name:subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout/name,text=True).strip()
           for name in ('src','src/electron','src/third_party/skia','src/third_party/electron_node')}
    assert heads['src/electron']==PINS['electron_commit']
    patches=checkout/'src/electron/patches'
    return dict(pins=PINS,heads=heads,configuration=sha(checkout/'.gclient'),entries=sha(checkout/'.gclient_entries'),
                patch_series={str(p.relative_to(patches)):sha(p) for p in sorted(patches.rglob('*')) if p.is_file()},
                profiles={str(p.relative_to(checkout/'src')):sha(p)
                          for folder in ('electron/build/pgo_profiles','v8/tools/builtins-pgo/profiles','chrome/build/pgo_profiles')
                          for p in sorted((checkout/'src'/folder).glob('*')) if p.is_file()})


def prepare(env):
    WORK.mkdir(parents=True,exist_ok=True);depot=WORK/'depot_tools'
    if not depot.exists():
        invoke(['git','clone','--no-checkout','https://chromium.googlesource.com/chromium/tools/depot_tools.git',depot],WORK,env,'depot-clone')
        invoke(['git','checkout',PINS['depot_tools']],depot,env,'depot-pin')
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=depot,text=True).strip()==PINS['depot_tools']
    invoke([depot/'ensure_bootstrap'],WORK,env,'depot-bootstrap')
    checkout=WORK/('electron-'+PINS['electron']);checkout.mkdir(exist_ok=True)
    text='solutions = [\n  {"name": "src/electron", "url": "https://github.com/electron/electron.git@'+PINS['electron_commit']+'", "deps_file": "DEPS", "managed": False, "custom_deps": {}, "custom_vars": {}},\n]\ntarget_os = ["linux"]\n'
    config=checkout/'.gclient'
    if config.exists():assert config.read_text()==text,'The private gclient configuration changed'
    config.write_text(text)
    receipt=checkout/'.fontreal-source.json'
    if receipt.exists():
        assert json.loads(receipt.read_text())==source_identity(checkout),'The prepared source identity changed'
    else:
        invoke([depot/'gclient','sync','--no-history','--nohooks','--jobs=8'],checkout,env,'fetch')
        invoke([depot/'gclient','runhooks'],checkout,env,'hooks')
        receipt.write_text(json.dumps(source_identity(checkout),indent=2)+'\n')
    source=checkout/'src';skia=source/'third_party/skia'
    for name,digest in BASE_FILES.items():assert sha(skia/name)==digest,name
    assert subprocess.run(['git','merge-base','--is-ancestor',PINS['node_base'],'HEAD'],cwd=source/'third_party/electron_node').returncode==0
    return source,source_identity(checkout)


def main():
    env=environment();gperf=shutil.which('gperf',path=env['PATH'])
    if gperf is None:raise SystemExit('Install gperf before building Electron 39.')
    source,identity=prepare(env);skia=source/'third_party/skia'
    spec=dict(pins=PINS,gn_args=GN_ARGS,source_files=BASE_FILES,recipe=sha(Path(__file__)),
              shared_recipe=sha(ROOT/'tools/build-electron.py'),patch=sha(PATCH),header=sha(HEADER),
              host_tools=dict(gperf=sha(Path(gperf))))
    artifact=WORK/'artifacts'/key(spec);record=artifact/'build.json'
    if record.exists():
        saved=json.loads(record.read_text());assert saved['spec']==spec and saved['source_identity']==identity
        for value in saved['packages'].values():verify(value)
        print(record);return
    out=source/'out/Fontreal';out.mkdir(parents=True,exist_ok=True)
    if (out/'args.gn').exists():assert (out/'args.gn').read_text()==GN_ARGS
    (out/'args.gn').write_text(GN_ARGS)
    invoke([source/'buildtools/linux64/gn','gen',out],source,env,'gn')
    ninja=[source/'third_party/ninja/ninja','-C',out,'-j'+str(min(24,os.cpu_count() or 1)),'electron:electron_dist_zip']
    stock_dir=WORK/'stock'/key(dict(pins=PINS,gn_args=GN_ARGS,source_files=BASE_FILES));stock_record=stock_dir/'package.json'
    marker=out/'fontreal-instrumented.json'
    if stock_record.exists():stock=json.loads(stock_record.read_text());verify(stock)
    else:
        assert not marker.exists(),'The stock archive is missing from an instrumented output tree'
        invoke(ninja,source,env,'stock-build');stock=package(out/'dist.zip',stock_dir)
        stock_record.write_text(json.dumps(stock,indent=2)+'\n')
    artifact.mkdir(parents=True,exist_ok=True);view=artifact/'source-view';view.mkdir(exist_ok=True)
    for folder in ('src/core','src/ports'):
        destination=view/folder
        if destination.exists():shutil.rmtree(destination)
        shutil.copytree(skia/folder,destination,symlinks=True)
    invoke(['patch','--batch','--fuzz=0','-p1','-i',PATCH],view,env,'trace-patch')
    shutil.copyfile(HEADER,view/'src/core/fontreal_owner_trace.h')
    marker.write_text(json.dumps(dict(spec=spec,stock_archive=stock['archive_sha256']),indent=2)+'\n')
    command=['bwrap','--ro-bind','/','/','--dev','/dev','--bind',out,out,'--bind',WORK/'cache',WORK/'cache']
    for folder in ('src/core','src/ports'):command+=['--ro-bind',view/folder,skia/folder]
    invoke([*command,'--',*ninja],source,env,'instrumented-build')
    instrumented=package(out/'dist.zip',artifact/'instrumented')
    for name,digest in BASE_FILES.items():assert sha(skia/name)==digest
    assert source_identity(source.parent)==identity
    record.write_text(json.dumps(dict(spec=spec,source=str(source),source_view=str(view),source_identity=identity,
                                     cache_environment={name:env[name] for name in CACHE_DIRECTORIES},
                                     packages=dict(stock=stock,instrumented=instrumented)),indent=2)+'\n')
    print(record)


if __name__=='__main__':main()
