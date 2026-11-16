#!/usr/bin/env python3
"""Check complete release sources, packages and current-app startup, not font tuning."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import shutil

import chromium_delivery_test as app
import chromium_selected_test as selected


def source_retry(source,destination,env):
    spec=importlib.util.spec_from_file_location('retry_builder',app.ROOT/'tools/build-electron-selected.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    view=destination/'retry-source-view';view.mkdir()
    try:
        first,identity=builder.release_sources(source,view,env)
        trees={str(original):subprocess.check_output(['git','-C',replacement,'rev-parse','HEAD^{tree}'],text=True).strip()
               for original,replacement in first if replacement.name=='upstream-node'}
        # These owned folders also exist after a failed compile or partial preparation.
        (view/'upstream-electron/retry-sentinel').write_text('incomplete')
        second,retried=builder.release_sources(source,view,env)
        assert not (view/'upstream-electron/retry-sentinel').exists()
        assert {k:v for k,v in identity.items() if k!='node_head'}=={k:v for k,v in retried.items() if k!='node_head'}
        assert trees=={str(original):subprocess.check_output(['git','-C',replacement,'rev-parse','HEAD^{tree}'],text=True).strip()
                       for original,replacement in second if replacement.name=='upstream-node'}
    finally:shutil.rmtree(view)


def main():
    # Synthetic release labels exercise the existing native-module compatibility gate.
    older=dict(electron='44.9.0',chrome='152.0.7977.167',modules='149')
    newer=dict(older,electron='44.9.1',chrome='152.0.7977.168')
    app.require_native_modules(newer,older)
    try:app.require_native_modules(dict(newer,modules='148'),older)
    except AssertionError:pass
    else:raise AssertionError('Incompatible native-module ABI accepted')
    root=app.ROOT;builder=app.delivery.builder
    output=(root/'results/chromium-launch').resolve();output.mkdir(parents=True,exist_ok=True)
    destination=Path(tempfile.mkdtemp(prefix='engine-update-',dir=output));print(destination,flush=True)
    checkout=(root/'build/chromium-flatpak/electron-44.9.0').resolve();source=checkout/'src'

    def originals():
        expected=json.loads((checkout/'.fontreal-source.json').read_text())
        result=dict(receipt=expected,heads={},dirty={})
        for name in ('','electron','third_party/skia','third_party/electron_node'):
            path=source/name
            result['heads'][name]=subprocess.check_output(['git','-C',path,'rev-parse','HEAD'],text=True).strip()
            result['dirty'][name]=subprocess.check_output(['git','-C',path,'diff','--raw'],text=True)
            # Electron's prepared dependencies have patched Gitlink commits.
            assert not subprocess.check_output(['git','-C',path,'diff','--ignore-submodules','--name-only'],text=True),name
        assert result['heads']['']==expected['heads']['src']
        assert result['heads']['electron']==expected['heads']['src/electron']
        assert result['heads']['third_party/skia']==expected['heads']['src/third_party/skia']
        for name in ('src/fontreal_coverage.cpp','src/fontreal_coverage.h','integrations/chromium/fontreal_selected.h',
                     'integrations/chromium/fontreal_bridge.cpp','patches/skia-747cf654-fontreal-selected.patch'):
            accepted=subprocess.check_output(['git','show','e8c541f:'+name],cwd=root)
            assert (root/name).read_bytes()==accepted,name
        return result

    before=originals()
    source_retry(source,destination,dict(os.environ))
    script_key=app.c1.target.sha(root/'tools/build-electron-selected.py')[:20]
    existing_credits=set((root/'build/chromium-flatpak/selected-runtime').resolve().glob('*/credits/'+script_key+'/identity.json'))
    selected.selected_build(None,destination)
    record_path=Path(json.loads((destination/'builder-identity-contrast.json').read_text())['baseline'])
    record=json.loads(record_path.read_text());runtime=json.loads(Path(record['spec']['runtime_record']).read_text())
    credits_identity=Path(record['spec']['runtime_record']).parent/'credits'/script_key/'identity.json'
    assert credits_identity.is_file() and json.loads(credits_identity.read_text())==record['spec']['notices']
    generated=credits_identity not in existing_credits
    if generated:assert 'selected-credits:' in (destination/'builder-stdout.log').read_text()
    assert record['spec']['upstream']==dict(electron='44.9.1',commit='e02265be96c5e13ae43644ef482b718e1e800499',
                                           node_base='f2bc3c738a0873ecb23e8a09e5c074e412c4c42f')
    views=[(Path(a),Path(b)) for a,b in runtime['upstream_views']]
    electron=next(b for a,b in views if a==source/'electron')
    node=next(b for a,b in views if a==source/'third_party/electron_node')
    archive=subprocess.check_output(['git','-C',source/'electron','archive',record['spec']['upstream']['commit']])
    assert hashlib.sha256(archive).hexdigest()==runtime['upstream_identity']['electron_archive_sha256']
    members=[]
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream:
            path=electron/member.name
            if member.isfile():assert path.read_bytes()==stream.extractfile(member).read(),member.name
            elif member.issym():assert path.is_symlink() and os.readlink(path)==member.linkname,member.name
            members.append(member.name)
    assert members
    commits=subprocess.check_output(['git','-C',node,'rev-list','--reverse',record['spec']['upstream']['node_base']+'..HEAD'],text=True).splitlines()
    patches=(electron/'patches/node/.patches').read_text().splitlines()
    assert len(commits)==len(patches)>0
    for commit,name in zip(commits,patches):
        expected=subprocess.check_output(['git','patch-id','--stable'],input=(electron/'patches/node'/name).read_bytes()).split()[0]
        actual=subprocess.check_output(['git','-C',node,'show','--format=','--no-ext-diff',commit])
        assert subprocess.check_output(['git','patch-id','--stable'],input=actual).split()[0]==expected,name
    assert not subprocess.check_output(['git','-C',node,'status','--porcelain'],text=True)
    assert subprocess.check_output(['git','-C',node,'rev-parse','HEAD'],text=True).strip()==runtime['upstream_identity']['node_head']
    profile=electron/'build/pgo_profiles/electron-v8-builtins.profile'
    assert app.c1.target.sha(profile)==(electron/'build/pgo_profiles/v8-builtins.pgo.txt').read_text().split()[1]
    assert app.c1.target.sha(profile)==runtime['upstream_identity']['v8_profile_sha256']
    bindings=['bwrap','--ro-bind','/','/','--dev','/dev']
    for original,replacement in views:bindings+=['--ro-bind',str(replacement),str(original)]
    effective={}
    for name in ('node_use_node_snapshot','node_v8_path','node_use_v8_platform'):
        command=[*bindings,'--',str(source/'buildtools/linux64/gn'),'args',str(source/'out/Fontreal'),'--list='+name,'--short']
        effective[name]=subprocess.check_output(command,cwd=source,text=True).strip()
    assert effective['node_use_node_snapshot']=='node_use_node_snapshot = true'
    assert effective['node_use_v8_platform']=='node_use_v8_platform = false'
    assert effective['node_v8_path']=='node_v8_path = "//v8"'
    assert (source/'out/Fontreal/args.gn').read_text()==record['spec']['gn_args']
    for package in runtime['baseline_packages'].values():
        assert selected.c1.target.sha(Path(package['archive']))==package['archive_sha256']
        supplied=Path(package['directory'])
        assert {str(p.relative_to(supplied)):app.c1.target.sha(p) for p in supplied.rglob('*') if p.is_file()}==package['files']
    command=[sys.executable,'-B',str(root/'tools/build-chromium-delivery.py'),'--build-record',str(record_path)]
    assembled=subprocess.check_output(command,cwd=root,text=True)
    application_path=Path(assembled.splitlines()[-1]);application=json.loads(application_path.read_text())
    assert application['spec']['build_record']==str(record_path)
    native=Path(subprocess.check_output(['/usr/bin/flatpak','info','--show-location',app.APPLICATION],text=True).strip())
    assert application['spec']['location']==str(native)
    startup={}
    for role in ('normal','trace'):
        view=Path(application['views'][role]['directory'])
        assert builder.tree(view/'teams-for-linux/resources')==builder.tree(native/'files/teams-for-linux/resources')
        supplied=bytearray((Path(record['packages'][role]['directory'])/'electron').read_bytes())
        signature=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX';offset=supplied.index(signature)+len(signature)
        original=(native/'files/teams-for-linux/teams-for-linux').read_bytes();at=original.index(signature)+len(signature)
        assert supplied[offset:offset+2]==original[at:at+2]
        supplied[offset+2:offset+2+supplied[offset+1]]=original[at+2:at+2+original[at+1]]
        assert bytes(supplied)==(view/'teams-for-linux/teams-for-linux').read_bytes()
        with app.comparison(view,destination/role,dict(os.environ,PYTHONDONTWRITEBYTECODE='1')) as (inspector,child,data):
            observed=inspector.evaluate("(()=>{const e=process.mainModule.require('electron');return {versions:process.versions,ready:e.app.isReady(),data:e.app.getPath('userData')};})()")
            assert observed['ready'] and observed['data']==str(data)
            assert observed['versions']['electron']=='44.9.1' and observed['versions']['chrome']=='152.0.7977.167'
            startup[role]=dict(versions=observed['versions'],privateData=True,engine_sha256=app.c1.target.sha(view/'teams-for-linux/teams-for-linux'))
    assert originals()==before
    result=dict(passed=True,boundaries=['B-ENGINE-1','B-ENGINE-2','B-ENGINE-3'],selected_record=str(record_path),
                application_record=str(application_path),effectiveGN=effective,sourcePreserved=True,patches=len(patches),startup=startup,
                creditsGeneratedThisRun=generated,creditsIdentity=str(credits_identity))
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS matching engine source, package and current-application startup',flush=True)


if __name__=='__main__':main()
