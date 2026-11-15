#!/usr/bin/env python3
"""Build private selected normal/trace engines and a pristine Fontations oracle."""
import fcntl
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
module=importlib.util.spec_from_file_location('electron_builder',ROOT/'tools/build-electron.py')
c1=importlib.util.module_from_spec(module);module.loader.exec_module(c1)
WORK=c1.WORK
RENDER_INPUTS=('patches/skia-747cf654-fontreal-selected.patch','patches/chromium-152-fontreal-selected-gn.patch',
               'integrations/chromium/fontreal_selected.h','integrations/chromium/fontreal_bridge.cpp',
               'src/fontreal_coverage.cpp','src/fontreal_coverage.h','tests/chromium_selected_probe.cpp')
INPUTS=('tools/build-electron-selected.py',*RENDER_INPUTS)


def render(spec,previous,env):
    source=Path(previous['source']);skia=source/'third_party/skia';out=source/'out/Fontreal'
    artifact=WORK/'selected-runtime'/c1.key(spec);record=artifact/'build.json'
    if record.exists():
        saved=json.loads(record.read_text());assert saved['spec']==spec
        for package in saved['packages'].values():c1.verify(package)
        assert c1.sha(Path(saved['probe']['executable']))==saved['probe']['sha256']
        return record,saved
    artifact.mkdir(parents=True,exist_ok=True)
    view=artifact/'source-view';view.mkdir(exist_ok=True)
    for folder in ('src/core','src/ports'):
        destination=view/folder
        if destination.exists():shutil.rmtree(destination)
        shutil.copytree(skia/folder,destination,symlinks=True)
    gn_view=view/'chromium-skia'
    if gn_view.exists():shutil.rmtree(gn_view)
    shutil.copytree(source/'skia',gn_view,symlinks=True)
    shutil.copyfile(ROOT/'tests/chromium_selected_probe.cpp',gn_view/'fontreal_native_probe.cpp')
    c1.invoke(['patch','--batch','--fuzz=0','-p1','-i',ROOT/'patches/chromium-152-fontreal-selected-gn.patch'],gn_view,env,'selected-gn-patch')
    def invoke(command,label):
        wrapped=['bwrap','--ro-bind','/','/','--dev','/dev','--bind',out,out,'--bind',WORK/'cache',WORK/'cache']
        for folder in ('src/core','src/ports'):wrapped+=['--ro-bind',view/folder,skia/folder]
        wrapped+=['--ro-bind',gn_view,source/'skia','--',*command]
        c1.invoke(wrapped,source,env,'selected-'+label)
    gn=[source/'buildtools/linux64/gn','gen',out]
    ninja=[source/'third_party/ninja/ninja','-C',out,'-j'+str(min(24,os.cpu_count() or 1))]
    (gn_view/'fontreal_build.gni').write_text('fontreal_selected_enabled = false\n')
    # Force actual pristine inputs, never C1 passive or earlier selected objects.
    for name in spec['original_files']:os.utime(view/name,None)
    invoke(gn,'probe-gn');invoke([*ninja,'skia:fontreal_native_probe'],'probe-build')
    pristine={name:c1.sha(view/name) for name in spec['original_files']}
    assert pristine==spec['original_files']
    (view/'pristine-inputs.json').write_text(json.dumps(pristine,indent=2)+'\n')
    probe=artifact/'fontreal-native-probe';shutil.copyfile(out/'fontreal_native_probe',probe);probe.chmod(0o755)
    probe_identity=dict(executable=str(probe),sha256=c1.sha(probe),source_sha256=c1.sha(ROOT/'tests/chromium_selected_probe.cpp'),
                        pristine_files=pristine,bridge=spec['source_identity']['heads']['src/third_party/skia'])
    commands=subprocess.check_output([*ninja,'-t','commands','skia:fontreal_native_probe'],cwd=source,env=env)
    (artifact/'probe-commands.txt').write_bytes(commands);probe_identity['commands_sha256']=c1.sha(artifact/'probe-commands.txt')
    c1.invoke(['patch','--batch','--fuzz=0','-p1','-i',ROOT/'patches/skia-747cf654-fontreal-selected.patch'],view,env,'selected-source-patch')
    for name in ('fontreal_coverage.cpp','fontreal_coverage.h'):shutil.copyfile(ROOT/'src'/name,view/'src/core'/name)
    for name in ('fontreal_selected.h','fontreal_bridge.cpp'):shutil.copyfile(ROOT/'integrations/chromium'/name,view/'src/core'/name)
    (gn_view/'fontreal_build.gni').write_text('fontreal_selected_enabled = true\n')
    packages={}
    for role,trace in (('normal',0),('trace',1)):
        (view/'src/core/fontreal_build.h').write_text(f'#define FONTREAL_SELECTED_TRACE {trace}\n')
        invoke(gn,role+'-gn');invoke([*ninja,'electron:electron_dist_zip'],role+'-build')
        packages[role]=c1.package(out/'dist.zip',artifact/role)
        commands=subprocess.check_output([*ninja,'-t','commands','electron:electron_dist_zip'],cwd=source,env=env)
        (artifact/(role+'-commands.txt')).write_bytes(commands)
    saved=dict(spec=spec,source=str(source),source_view=str(view),probe=probe_identity,packages=packages,
               cache_environment={name:env[name] for name in c1.CACHE_DIRECTORIES},
               commands={role:c1.sha(artifact/(role+'-commands.txt')) for role in ('normal','trace')})
    record.write_text(json.dumps(saved,indent=2)+'\n');return record,saved


def credits(source,env):
    folder=WORK/'credits';folder.mkdir(exist_ok=True)
    output=folder/'LICENSES.chromium.html';depfile=folder/'credits.d';out=source/'out/Fontreal'
    command=[sys.executable,str(source/'tools/licenses/licenses.py'),'credits','--target-os=linux','--depfile',str(depfile),str(output)]
    c1.invoke(command,out,env,'selected-credits')
    data=output.read_bytes()
    assert b'Generated by licenses.py' in data and b'This is sample credits page.' not in data
    assert all(name in data for name in (b'libc++',b'LLVM',b'Skia',b'zlib')),'Official credits omit an actual selected dependency'
    names=shlex.split(depfile.read_text().split(':',1)[1].replace('\\\n',''))
    paths={(out/name).resolve() for name in names}
    paths.update(source/name for name in ('components/resources/BUILD.gn','tools/licenses/licenses.py','tools/licenses/spdx_writer.py',
                                        'build/action_helpers.py','build/find_depot_tools.py','third_party/libc++/src/LICENSE.TXT'))
    paths.add(WORK/'depot_tools/metadata/fields/custom/license_allowlist.py')
    assert paths and all(path.is_relative_to(WORK) and path.is_file() for path in paths)
    inputs={str(path):c1.sha(path) for path in sorted(paths)}
    identity=dict(command=command,cwd=str(out),inputs=inputs,output_sha256=c1.sha(output),depfile_sha256=c1.sha(depfile),
                  python=sys.version,python_executable_sha256=c1.sha(Path(sys.executable)))
    return identity,output,depfile


def package_with_notices(original,destination,html,llvm,fontreal):
    # Only notice entries change; retained engine files must remain byte-identical.
    temporary=destination.parent/(destination.name+'-notices.zip')
    with zipfile.ZipFile(original['archive']) as source,zipfile.ZipFile(temporary,'w') as target:
        for entry in source.infolist():
            target.writestr(entry,html.read_bytes() if entry.filename=='LICENSES.chromium.html' else source.read(entry.filename))
        for name,path in (('LICENSE.libcxx.txt',llvm),('LICENSE.fontreal.txt',fontreal)):
            entry=zipfile.ZipInfo(name);entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED
            target.writestr(entry,path.read_bytes())
    result=c1.package(temporary,destination);temporary.unlink()
    untouched={name:digest for name,digest in result['files'].items() if name not in ('LICENSES.chromium.html','LICENSE.libcxx.txt','LICENSE.fontreal.txt')}
    assert untouched=={name:digest for name,digest in original['files'].items() if name!='LICENSES.chromium.html'}
    return result


def main():
    WORK.mkdir(parents=True,exist_ok=True)
    with (WORK/'selected-builder.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        build()


def build():
    env=c1.environment()
    result=subprocess.check_output([sys.executable,ROOT/'tools/build-electron.py'],env=env,text=True)
    c1_record=Path(result.splitlines()[-1]);previous=json.loads(c1_record.read_text())
    for package in previous['packages'].values():c1.verify(package)
    source=Path(previous['source']);checkout=source.parent;skia=source/'third_party/skia';out=source/'out/Fontreal'
    assert (out/'args.gn').read_text()==c1.GN_ARGS
    identity=c1.source_identity(checkout)
    assert identity==previous['source_identity']==json.loads((checkout/'.fontreal-source.json').read_text())
    tools={name:c1.sha(source/path) for name,path in (
        ('clang','third_party/llvm-build/Release+Asserts/bin/clang++'),('lld','third_party/llvm-build/Release+Asserts/bin/ld.lld'),
        ('mold','buildtools/third_party/mold/cipd/mold'),('rustc','third_party/rust-toolchain/bin/rustc'),
        ('gn','buildtools/linux64/gn'),('ninja','third_party/ninja/ninja'))}
    runtime_spec=dict(c1_record=str(c1_record),c1_record_sha256=c1.sha(c1_record),source_identity=identity,
              inputs={name:c1.sha(ROOT/name) for name in RENDER_INPUTS},tools=tools,gn_args=c1.GN_ARGS,
              runtime_recipe=hashlib.sha256(inspect.getsource(render).encode()).hexdigest(),
              original_files={name:c1.sha(skia/name) for name in (*c1.BASE_FILES,'src/core/SkScalerContext.h')},
              original_gn=c1.sha(source/'skia/BUILD.gn'),
              runtime_sources={name:c1.sha(source/name) for name in ('third_party/libc++/src/src/memory_resource.cpp','buildtools/third_party/libc++/BUILD.gn')})
    runtime_record,runtime=render(runtime_spec,previous,env)
    notice,html,depfile=credits(source,env)
    spec=dict(runtime_spec,inputs={name:c1.sha(ROOT/name) for name in INPUTS},notices=notice,
              runtime_record=str(runtime_record),runtime_record_sha256=c1.sha(runtime_record),fontreal_license_sha256=c1.sha(ROOT/'LICENSE'))
    artifact=WORK/'selected'/c1.key(spec);record=artifact/'build.json'
    if record.exists():
        saved=json.loads(record.read_text());assert saved['spec']==spec
        for package in saved['packages'].values():c1.verify(package)
        assert c1.sha(Path(saved['probe']['executable']))==saved['probe']['sha256']
        print(record);return
    artifact.mkdir(parents=True,exist_ok=True)
    llvm=source/'third_party/libc++/src/LICENSE.TXT'
    packages={role:package_with_notices(package,artifact/role,html,llvm,ROOT/'LICENSE') for role,package in runtime['packages'].items()}
    for name in ('probe-commands.txt','normal-commands.txt','trace-commands.txt'):
        shutil.copyfile(runtime_record.parent/name,artifact/name)
    probe=dict(runtime['probe']);probe_path=artifact/'fontreal-native-probe'
    shutil.copyfile(Path(probe['executable']),probe_path);probe_path.chmod(0o755);probe['executable']=str(probe_path)
    for label,path in (('FONTREAL',ROOT/'LICENSE'),('SKIA',skia/'LICENSE'),('CHROMIUM',source/'LICENSE'),('LLVM',llvm)):
        shutil.copyfile(path,artifact/(label+'-LICENSE.txt'))
    shutil.copyfile(html,artifact/'LICENSES.chromium.html');shutil.copyfile(depfile,artifact/'credits.d')
    for name,digest in runtime_spec['original_files'].items():assert c1.sha(skia/name)==digest
    assert c1.sha(source/'skia/BUILD.gn')==runtime_spec['original_gn']
    for package in previous['packages'].values():c1.verify(package)
    saved=dict(runtime,spec=spec,probe=probe,packages=packages)
    record.write_text(json.dumps(saved,indent=2)+'\n');print(record)


if __name__=='__main__':main()
