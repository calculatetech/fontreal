#!/usr/bin/env python3
"""Build private selected normal/trace engines and a pristine Fontations oracle."""
import argparse
import fcntl
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
module=importlib.util.spec_from_file_location('electron_builder',ROOT/'tools/build-electron.py')
c1=importlib.util.module_from_spec(module);module.loader.exec_module(c1)
WORK=c1.WORK
UPSTREAM=dict(electron='44.9.1',commit='e02265be96c5e13ae43644ef482b718e1e800499',
              node_base='f2bc3c738a0873ecb23e8a09e5c074e412c4c42f')
RENDER_INPUTS=('patches/skia-747cf654-fontreal-selected.patch','patches/chromium-152-fontreal-selected-gn.patch',
               'integrations/chromium/fontreal_selected.h','integrations/chromium/fontreal_bridge.cpp',
               'src/fontreal_coverage.cpp','src/fontreal_coverage.h','tests/chromium_selected_probe.cpp')
INPUTS=('tools/build-electron-selected.py',*RENDER_INPUTS)
PRODUCER=ROOT/'tools/build-electron.py'
SKIA_PATCH=ROOT/RENDER_INPUTS[0]
GN_PATCH=ROOT/RENDER_INPUTS[1]


def configure(target):
    global c1,WORK,UPSTREAM,RENDER_INPUTS,INPUTS,PRODUCER,SKIA_PATCH,GN_PATCH
    if target=='teams':return
    assert target=='bitwarden'
    PRODUCER=ROOT/'tools/build-electron-bitwarden.py'
    module=importlib.util.spec_from_file_location('bitwarden_builder',PRODUCER)
    c1=importlib.util.module_from_spec(module);module.loader.exec_module(c1)
    WORK=c1.WORK
    UPSTREAM=dict(electron=c1.PINS['electron'],commit=c1.PINS['electron_commit'],node_base=c1.PINS['node_base'])
    SKIA_PATCH=ROOT/'patches/skia-f4ed99d2-fontreal-selected.patch'
    GN_PATCH=ROOT/'patches/chromium-142-fontreal-selected-gn.patch'
    RENDER_INPUTS=(str(SKIA_PATCH.relative_to(ROOT)),str(GN_PATCH.relative_to(ROOT)),*RENDER_INPUTS[2:])
    INPUTS=('tools/build-electron-selected.py',*RENDER_INPUTS)


def release_sources(source,view,env):
    if c1.PINS['electron']==UPSTREAM['electron']:
        archive=subprocess.check_output(['git','-C',source/'electron','archive',UPSTREAM['commit']])
        return [],dict(electron_archive_sha256=hashlib.sha256(archive).hexdigest(),node_base=UPSTREAM['node_base'],
                       node_head=subprocess.check_output(['git','-C',source/'third_party/electron_node','rev-parse','HEAD'],text=True).strip(),
                       node_patch_series_sha256=c1.sha(source/'electron/patches/node/.patches'))
    original=source/'electron';electron=view/'upstream-electron';node=view/'upstream-node'
    for folder in (electron,node,view/'upstream-chromium'):
        if folder.exists():shutil.rmtree(folder)
    tag='v'+UPSTREAM['electron']
    found=subprocess.run(['git','-C',original,'rev-parse','--verify',tag+'^{commit}'],text=True,capture_output=True)
    if found.returncode:
        c1.invoke(['git','fetch','--depth=1','https://github.com/electron/electron.git','tag',tag],original,env,'selected-release-fetch')
    assert subprocess.check_output(['git','-C',original,'rev-parse',tag+'^{commit}'],text=True).strip()==UPSTREAM['commit']
    archive=subprocess.check_output(['git','-C',original,'archive',UPSTREAM['commit']])
    electron.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:stream.extractall(electron,filter='data')
    for name in ('DEPS','package.json','yarn.lock','patches/config.json'):
        assert (electron/name).read_bytes()==(original/name).read_bytes(),name
    for directory in (electron/'patches').iterdir():
        if directory.is_dir() and directory.name not in ('node','chromium'):
            assert {str(p.relative_to(directory)):c1.sha(p) for p in directory.rglob('*') if p.is_file()}=={
                str(p.relative_to(original/'patches'/directory.name)):c1.sha(p)
                for p in (original/'patches'/directory.name).rglob('*') if p.is_file()}
    shutil.copytree(original/'node_modules',electron/'node_modules',symlinks=True)
    c1.invoke([sys.executable,electron/'script/pgo/download-profiles.py','--targets','v8-builtins'],
              WORK,env,'selected-release-v8-profile')
    profile=electron/'build/pgo_profiles/electron-v8-builtins.profile'
    profile_state=(electron/'build/pgo_profiles/v8-builtins.pgo.txt').read_text().split()
    assert len(profile_state)==2 and c1.sha(profile)==profile_state[1]
    c1.invoke(['git','clone','--local','--no-checkout',source/'third_party/electron_node',node],WORK,env,'selected-node-clone')
    c1.invoke(['git','checkout','--detach',UPSTREAM['node_base']],node,env,'selected-node-base')
    config=view/'node-patches.json'
    config.write_text(json.dumps([dict(patch_dir=str(electron/'patches/node'),repo=str(node))])+'\n')
    c1.invoke([sys.executable,electron/'script/apply_all_patches.py',config],WORK,env,'selected-node-release-patches')
    assert not subprocess.check_output(['git','-C',node,'status','--porcelain'],text=True)
    chromium=view/'upstream-chromium';name='net/cert/cert_verify_proc_blocklist.inc'
    destination=chromium/name;destination.parent.mkdir(parents=True)
    shutil.copyfile(source/name,destination)
    assert (electron/'patches/chromium/.patches').read_text()==(original/'patches/chromium/.patches').read_text()+'add_entries_to_the_spki_blocklist.patch\n'
    c1.invoke(['patch','--batch','--fuzz=0','-p1','-i',electron/'patches/chromium/add_entries_to_the_spki_blocklist.patch'],
              chromium,env,'selected-release-chromium')
    identity=dict(electron_archive_sha256=hashlib.sha256(archive).hexdigest(),
                  v8_profile_sha256=c1.sha(profile),
                  node_head=subprocess.check_output(['git','-C',node,'rev-parse','HEAD'],text=True).strip(),
                  node_base=UPSTREAM['node_base'],node_patch_series_sha256=c1.sha(electron/'patches/node/.patches'),
                  chromium_sha256=c1.sha(destination))
    return [(source/'electron',electron),(source/'third_party/electron_node',node),(source/name,destination)],identity


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
    c1.invoke(['patch','--batch','--fuzz=0','-p1','-i',GN_PATCH],gn_view,env,'selected-gn-patch')
    upstream_views,upstream_identity=release_sources(source,view,env)
    def invoke(command,label):
        wrapped=['bwrap','--ro-bind','/','/','--dev','/dev','--bind',out,out,'--bind',WORK/'cache',WORK/'cache']
        for folder in ('src/core','src/ports'):wrapped+=['--ro-bind',view/folder,skia/folder]
        for original,replacement in upstream_views:wrapped+=['--ro-bind',replacement,original]
        wrapped+=['--ro-bind',gn_view,source/'skia','--',*command]
        c1.invoke(wrapped,source,env,'selected-'+label)
    (out/'args.gn').write_text(spec['gn_args'])
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
    # The already exact source producer supplies matching application controls.
    if c1.PINS['electron']==UPSTREAM['electron']:
        stock=previous['packages']['stock'];passive=previous['packages']['instrumented']
    else:
        invoke([*ninja,'electron:electron_dist_zip'],'release-stock-build')
        stock=c1.package(out/'dist.zip',artifact/'source-stock')
        c1.invoke(['patch','--batch','--fuzz=0','-p1','-i',c1.PATCH],view,env,'release-passive-patch')
        shutil.copyfile(c1.HEADER,view/'src/core/fontreal_owner_trace.h')
        invoke([*ninja,'electron:electron_dist_zip'],'release-passive-build')
        passive=c1.package(out/'dist.zip',artifact/'source-passive')
    for folder in ('src/core','src/ports'):
        shutil.rmtree(view/folder);shutil.copytree(skia/folder,view/folder,symlinks=True)
    for name in spec['original_files']:os.utime(view/name,None)
    c1.invoke(['patch','--batch','--fuzz=0','-p1','-i',SKIA_PATCH],view,env,'selected-source-patch')
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
               baseline_packages=dict(stock=stock,instrumented=passive),
               upstream_identity=upstream_identity,upstream_views=[list(map(str,pair)) for pair in upstream_views],
               cache_environment={name:env[name] for name in c1.CACHE_DIRECTORIES},
               commands={role:c1.sha(artifact/(role+'-commands.txt')) for role in ('normal','trace')})
    record.write_text(json.dumps(saved,indent=2)+'\n');return record,saved


def credits(source,env,views,folder):
    folder=folder/c1.sha(Path(__file__))[:20];folder.mkdir(parents=True,exist_ok=True)
    output=folder/'LICENSES.chromium.html';depfile=folder/'credits.d';out=source/'out/Fontreal'
    receipt=folder/'identity.json'
    if receipt.exists():
        identity=json.loads(receipt.read_text())
        assert c1.sha(output)==identity['output_sha256'] and c1.sha(depfile)==identity['depfile_sha256']
        for name,digest in identity['inputs'].items():assert c1.sha(Path(name))==digest
        return identity,output,depfile
    command=[sys.executable,str(source/'tools/licenses/licenses.py'),'credits','--target-os=linux',
             '--depfile',os.path.relpath(depfile,out),os.path.relpath(output,out)]
    wrapped=['bwrap','--ro-bind','/','/','--dev','/dev','--bind',folder,folder,'--bind',WORK/'cache',WORK/'cache']
    for original,replacement in views:wrapped+=['--ro-bind',replacement,original]
    command=list(map(str,[*wrapped,'--',*command]))
    c1.invoke(command,out,env,'selected-credits')
    data=output.read_bytes()
    assert b'Generated by licenses.py' in data and b'This is sample credits page.' not in data
    assert all(name in data for name in (b'libc++',b'LLVM',b'Skia',b'zlib')),'Official credits omit an actual selected dependency'
    names=shlex.split(depfile.read_text().split(':',1)[1].replace('\\\n',''))
    paths={(out/name).resolve() for name in names}
    paths.update(source/name for name in ('components/resources/BUILD.gn','tools/licenses/licenses.py','tools/licenses/spdx_writer.py',
                                        'build/action_helpers.py','build/find_depot_tools.py','third_party/libc++/src/LICENSE.TXT'))
    paths.add(WORK/'depot_tools/metadata/fields/custom/license_allowlist.py')
    effective=set()
    for path in paths:
        for original,replacement in views:
            if path==original or path.is_relative_to(original):
                path=replacement/path.relative_to(original);break
        effective.add(path)
    paths=effective
    assert paths and all(path.is_relative_to(WORK) and path.is_file() for path in paths)
    inputs={str(path):c1.sha(path) for path in sorted(paths)}
    identity=dict(command=command,cwd=str(out),inputs=inputs,output_sha256=c1.sha(output),depfile_sha256=c1.sha(depfile),
                  python=sys.version,python_executable_sha256=c1.sha(Path(sys.executable)))
    receipt.write_text(json.dumps(identity,indent=2)+'\n')
    return identity,output,depfile


def package_with_notices(original,destination,html,llvm,fontreal,node):
    # Only notice entries change; retained engine files must remain byte-identical.
    temporary=destination.parent/(destination.name+'-notices.zip')
    with zipfile.ZipFile(original['archive']) as source,zipfile.ZipFile(temporary,'w') as target:
        for entry in source.infolist():
            target.writestr(entry,html.read_bytes() if entry.filename=='LICENSES.chromium.html' else source.read(entry.filename))
        for name,path in (('LICENSE.libcxx.txt',llvm),('LICENSE.fontreal.txt',fontreal),('LICENSE.node.txt',node)):
            entry=zipfile.ZipInfo(name);entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED
            target.writestr(entry,path.read_bytes())
    result=c1.package(temporary,destination);temporary.unlink()
    untouched={name:digest for name,digest in result['files'].items() if name not in ('LICENSES.chromium.html','LICENSE.libcxx.txt','LICENSE.fontreal.txt','LICENSE.node.txt')}
    assert untouched=={name:digest for name,digest in original['files'].items() if name!='LICENSES.chromium.html'}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',choices=['teams','bitwarden'],default='teams')
    configure(parser.parse_args().target)
    WORK.mkdir(parents=True,exist_ok=True)
    with (WORK/'selected-builder.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        build()


def build():
    env=c1.environment()
    result=subprocess.check_output([sys.executable,PRODUCER],env=env,text=True)
    c1_record=Path(result.splitlines()[-1]);previous=json.loads(c1_record.read_text())
    for package in previous['packages'].values():c1.verify(package)
    source=Path(previous['source']);checkout=source.parent;skia=source/'third_party/skia';out=source/'out/Fontreal'
    gn_args=c1.GN_ARGS.replace('override_electron_version="'+c1.PINS['electron']+'"','override_electron_version="'+UPSTREAM['electron']+'"')
    assert (out/'args.gn').read_text() in (c1.GN_ARGS,gn_args)
    identity=c1.source_identity(checkout)
    assert identity==previous['source_identity']==json.loads((checkout/'.fontreal-source.json').read_text())
    tool_paths=[
        ('clang','third_party/llvm-build/Release+Asserts/bin/clang++'),('lld','third_party/llvm-build/Release+Asserts/bin/ld.lld'),
        ('rustc','third_party/rust-toolchain/bin/rustc'),('gn','buildtools/linux64/gn'),('ninja','third_party/ninja/ninja')]
    if PRODUCER.name=='build-electron.py':tool_paths.append(('mold','buildtools/third_party/mold/cipd/mold'))
    tools={name:c1.sha(source/path) for name,path in tool_paths}
    runtime_spec=dict(c1_record=str(c1_record),c1_record_sha256=c1.sha(c1_record),source_identity=identity,
              inputs={name:c1.sha(ROOT/name) for name in RENDER_INPUTS},tools=tools,gn_args=gn_args,upstream=UPSTREAM,
              runtime_recipe=hashlib.sha256((inspect.getsource(render)+inspect.getsource(release_sources)).encode()).hexdigest(),
              original_files={name:c1.sha(skia/name) for name in (*c1.BASE_FILES,'src/core/SkScalerContext.h')},
              original_gn=c1.sha(source/'skia/BUILD.gn'),
              runtime_sources={name:c1.sha(source/name) for name in ('third_party/libc++/src/src/memory_resource.cpp','buildtools/third_party/libc++/BUILD.gn')})
    runtime_record,runtime=render(runtime_spec,previous,env)
    notice,html,depfile=credits(source,env,[(Path(a),Path(b)) for a,b in runtime['upstream_views']],runtime_record.parent/'credits')
    node_license=ROOT/'LICENSES/Node.txt' if PRODUCER.name=='build-electron.py' else source/'third_party/electron_node/LICENSE'
    spec=dict(runtime_spec,inputs={name:c1.sha(ROOT/name) for name in INPUTS},notices=notice,
              runtime_record=str(runtime_record),runtime_record_sha256=c1.sha(runtime_record),fontreal_license_sha256=c1.sha(ROOT/'LICENSE'),
              node_license_sha256=c1.sha(node_license))
    artifact=WORK/'selected'/c1.key(spec);record=artifact/'build.json'
    if record.exists():
        saved=json.loads(record.read_text());assert saved['spec']==spec
        for package in saved['packages'].values():c1.verify(package)
        assert c1.sha(Path(saved['probe']['executable']))==saved['probe']['sha256']
        print(record);return
    artifact.mkdir(parents=True,exist_ok=True)
    llvm=source/'third_party/libc++/src/LICENSE.TXT'
    packages={role:package_with_notices(package,artifact/role,html,llvm,ROOT/'LICENSE',node_license) for role,package in runtime['packages'].items()}
    for name in ('probe-commands.txt','normal-commands.txt','trace-commands.txt'):
        shutil.copyfile(runtime_record.parent/name,artifact/name)
    probe=dict(runtime['probe']);probe_path=artifact/'fontreal-native-probe'
    shutil.copyfile(Path(probe['executable']),probe_path);probe_path.chmod(0o755);probe['executable']=str(probe_path)
    for label,path in (('FONTREAL',ROOT/'LICENSE'),('SKIA',skia/'LICENSE'),('CHROMIUM',source/'LICENSE'),('LLVM',llvm)):
        shutil.copyfile(path,artifact/(label+'-LICENSE.txt'))
    shutil.copyfile(html,artifact/'LICENSES.chromium.html');shutil.copyfile(depfile,artifact/'credits.d')
    if PRODUCER.name=='build-electron-bitwarden.py':shutil.copyfile(node_license,artifact/'NODE-LICENSE.txt')
    for name,digest in runtime_spec['original_files'].items():assert c1.sha(skia/name)==digest
    assert c1.sha(source/'skia/BUILD.gn')==runtime_spec['original_gn']
    for package in previous['packages'].values():c1.verify(package)
    saved=dict(runtime,spec=spec,probe=probe,packages=packages)
    record.write_text(json.dumps(saved,indent=2)+'\n');print(record)


if __name__=='__main__':main()
