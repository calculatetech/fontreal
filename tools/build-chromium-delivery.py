#!/usr/bin/env python3
"""Assemble exact Teams application views without copying application data."""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import chromium_flatpak as target

ROOT=Path(__file__).resolve().parents[1]
WORK=(ROOT/'build/chromium-delivery').resolve()
APPLICATION='com.github.IsmaelMartinez.teams_for_linux'
ZYPAK='693a71c5ffa80ec9c9ce2ae03b1ccc493c698e53'
PATCH=ROOT/'patches/zypak-693a71c5-app-fd.patch'


def run(command,**kwargs):
    return subprocess.check_output(list(map(str,command)),text=True,**kwargs).strip()


def invoke(command,label,env=None):
    path=WORK/(label+'.log');print(label+': '+str(path),flush=True)
    with path.open('w') as log:subprocess.run(list(map(str,command)),env=env,stdout=log,stderr=log,check=True)


def tree(path):
    result={}
    for p in sorted(path.rglob('*')):
        name=str(p.relative_to(path))
        if p.is_symlink():result[name]=dict(link=os.readlink(p))
        elif p.is_file():result[name]=dict(sha256=target.sha(p),mode=p.stat().st_mode&0o777)
    return result


def verify(view):
    if tree(Path(view['directory']))!=view['files']:raise ValueError('An assembled application view changed.')


def sdk_environment():
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for name,folder in (('FLATPAK_USER_DIR','sdk/installation'),('XDG_CONFIG_HOME','sdk/config'),
                        ('XDG_DATA_HOME','sdk/data'),('XDG_STATE_HOME','sdk/state'),('XDG_CACHE_HOME','cache/flatpak'),
                        ('FLATPAK_SYSTEM_CACHE_DIR','cache/flatpak-system'),('TMPDIR','tmp')):
        path=WORK/folder;path.mkdir(parents=True,exist_ok=True);env[name]=str(path)
    return env


def zypak(env,runtime,sdk_commit):
    source=WORK/'sources/zypak'
    if not (source/'.git').is_dir():
        source.mkdir(parents=True,exist_ok=True)
        invoke(['git','-C',source,'init'],'zypak-init')
        invoke(['git','-C',source,'fetch','--depth=1','https://github.com/refi64/zypak.git',ZYPAK],'zypak-fetch')
        invoke(['git','-C',source,'checkout','--detach','FETCH_HEAD'],'zypak-checkout')
    assert run(['git','-C',source,'rev-parse','HEAD'])==ZYPAK
    assert not run(['git','-C',source,'diff','--name-only'])
    invoke(['git','-C',source,'submodule','update','--init','nickle'],'zypak-nickle')
    sdk='org.freedesktop.Sdk/x86_64/25.08'
    installed=subprocess.run(['flatpak','--user','info','--show-commit',sdk],env=env,text=True,capture_output=True)
    if installed.returncode:
        invoke(['flatpak','--user','remote-add','--if-not-exists','flathub','https://dl.flathub.org/repo/flathub.flatpakrepo'],'sdk-remote',env)
        invoke(['flatpak','--user','install','--noninteractive','--assumeyes','--no-related','flathub',sdk],'sdk-install',env)
    if run(['flatpak','--user','info','--show-commit',sdk],env=env)!=sdk_commit:
        invoke(['flatpak','--user','update','--noninteractive','--assumeyes','--commit='+sdk_commit,sdk],'sdk-pin',env)
    identity=dict(zypak=ZYPAK,nickle=run(['git','-C',source/'nickle','rev-parse','HEAD']),
                  sdk=sdk,sdk_commit=run(['flatpak','--user','info','--show-commit',sdk],env=env),
                  runtime=runtime,runtime_commit=run(['/usr/bin/flatpak','info','--show-commit',runtime]),
                  patch_sha256=target.sha(PATCH),recipe_sha256=target.sha(Path(__file__)))
    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
    folder=WORK/'zypak'/key;receipt=folder/'build.json'
    if receipt.exists():
        record=json.loads(receipt.read_text());assert record['spec']==identity
        for name,digest in record['files'].items():assert target.sha(folder/name)==digest
        return folder,record
    folder.mkdir(parents=True,exist_ok=True)
    if not (folder/'build/metadata').exists():
        invoke(['flatpak','build-init','--arch=x86_64',folder/'build','org.fontreal.ZypakBuild',
                'org.freedesktop.Sdk','org.freedesktop.Platform','25.08'],'zypak-build-init',env)
    private=folder/'build/files/zypak-source'
    if private.exists():shutil.rmtree(private)
    shutil.copytree(source,private,symlinks=True)
    invoke(['git','-C',private,'tag','fontreal-693a71c5'],'zypak-build-tag')
    invoke(['patch','--batch','--fuzz=0','-d',private,'-p1','-i',PATCH],'zypak-patch')
    assert set(run(['git','-C',private,'diff','--name-only']).splitlines())=={
        'src/dbus/flatpak_portal_proxy.h','src/dbus/flatpak_portal_proxy.cc','src/preload/host/spawn_strategy/spawn_launcher_delegate.cc'}
    (folder/'build/files/tmp').mkdir()
    command=['flatpak','build','--env=TMPDIR=/app/tmp','--env=XDG_CACHE_HOME=/app/.cache',folder/'build',
             'make','-C','/app/zypak-source','-j8','all','install','FLATPAK_DEST=/app']
    invoke(command,'zypak-compile',env)
    for name in ('bin','lib'):shutil.copytree(folder/'build/files'/name,folder/name,symlinks=True)
    files={str(p.relative_to(folder)):target.sha(p) for name in ('bin','lib') for p in (folder/name).rglob('*') if p.is_file() and not p.is_symlink()}
    compiler=run(['flatpak','build',folder/'build','g++','--version'],env=env)
    tools=run(['flatpak','build',folder/'build','sha256sum','/usr/bin/g++','/usr/bin/ld'],env=env)
    record=dict(spec=identity,command=list(map(str,command)),compiler=compiler,tools_sha256=tools,files=files)
    receipt.write_text(json.dumps(record,indent=2)+'\n')
    return folder,record


def overlay(source,destination):
    for p in source.rglob('*'):
        q=destination/p.relative_to(source)
        if p.is_dir() and not p.is_symlink():q.mkdir(parents=True,exist_ok=True);continue
        if q.exists() or q.is_symlink():q.unlink()
        q.parent.mkdir(parents=True,exist_ok=True)
        if p.is_symlink():q.symlink_to(os.readlink(p))
        else:shutil.copy2(p,q)


def preserve_fuses(engine,original):
    signature=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'
    data=bytearray(engine.read_bytes());native=original.read_bytes()
    at=data.find(signature)+len(signature);other=native.find(signature)+len(signature)
    assert at>=len(signature) and other>=len(signature)
    assert data[at]==native[other]==1 and data[at+1]==native[other+1]
    count=data[at+1];before=bytes(data[at+2:at+2+count]);after=native[other+2:other+2+count]
    data[at+2:at+2+count]=after;engine.write_bytes(data)
    return dict(offset=at+2,before=before.decode(),after=after.decode())


def current_view(record,selectors=()):
    location=Path(run(['/usr/bin/flatpak','info',*selectors,'--show-location',APPLICATION])).resolve(strict=True)
    saved=record['views']['normal'];source=Path(saved['directory'])
    identity=dict(location=str(location),distribution=str(source),engine=saved['engine_sha256'])
    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20]
    cache=WORK/'current';cache.mkdir(parents=True,exist_ok=True)
    view=cache/key
    if (view/'.fontreal-view.json').is_file():return view
    with (WORK/'builder.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (view/'.fontreal-view.json').is_file():return view
        with tempfile.TemporaryDirectory(prefix='assemble-',dir=cache) as temporary:
            staging=Path(temporary)/'app'
            shutil.copytree(location/'files',staging,symlinks=True)
            for p in [staging,*[p for p in staging.rglob('*') if p.is_dir() and not p.is_symlink()]]:
                p.chmod(p.stat().st_mode|0o700)
            engine=staging/'teams-for-linux'
            # Keep current application resources and modules; replace the coherent engine only.
            for p in (source/'teams-for-linux').iterdir():
                if p.name=='resources':continue
                q=engine/p.name
                if q.is_dir() and not q.is_symlink():shutil.rmtree(q)
                elif q.exists() or q.is_symlink():q.unlink()
                if p.is_dir():shutil.copytree(p,q,symlinks=True)
                else:shutil.copy2(p,q)
            identity['fuses']=preserve_fuses(engine/'teams-for-linux',location/'files/teams-for-linux/teams-for-linux')
            for folder in ('bin','lib'):
                for p in (source/folder).glob('*zypak*'):
                    q=staging/folder/p.name
                    if q.exists() or q.is_symlink():q.unlink()
                    if p.is_symlink():q.symlink_to(os.readlink(p))
                    else:shutil.copy2(p,q)
            shutil.copytree(source/'share/licenses/fontreal-zypak',staging/'share/licenses/fontreal-zypak',dirs_exist_ok=True)
            (staging/'.fontreal-view.json').write_text(json.dumps(identity,indent=2)+'\n')
            staging.rename(view)
    return view


def build(build_record):
    WORK.mkdir(parents=True,exist_ok=True)
    with (WORK/'builder.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        invoke(['/usr/bin/flatpak','run','--command=/usr/bin/true',APPLICATION],'native-startup')
        location=Path(run(['/usr/bin/flatpak','info','--show-location',APPLICATION]))
        metadata=configparser.ConfigParser(interpolation=None);metadata.read(location/'metadata')
        assert metadata['Application']['runtime']=='org.freedesktop.Platform/x86_64/25.08'
        assert metadata['Application']['command']=='teams-for-linux'
        manifest=json.loads((location/'files/manifest.json').read_text())
        record=json.loads(build_record.read_text());c1_path=Path(record['spec']['c1_record']);c1=json.loads(c1_path.read_text())
        assert manifest['id']==APPLICATION
        env=sdk_environment();zypak_folder,zypak_record=zypak(env,metadata['Application']['runtime'],manifest['sdk-commit'])
        spec=dict(application=APPLICATION,location=str(location),commit=run(['/usr/bin/flatpak','info','--show-commit',APPLICATION]),
                  runtime=metadata['Application']['runtime'],runtime_commit=zypak_record['spec']['runtime_commit'],
                  metadata_sha256=target.sha(location/'metadata'),manifest_sha256=target.sha(location/'files/manifest.json'),
                  original_files=tree(location/'files'),build_record=str(build_record),build_sha256=target.sha(build_record),
                  c1_record_sha256=target.sha(c1_path),zypak=zypak_record,recipe_sha256=target.sha(Path(__file__)),
                  launch_sha256=target.sha(ROOT/'tools/chromium_delivery.py'),
                  native_desktop=str(location/'export/share/applications'/(APPLICATION+'.desktop')),
                  native_desktop_sha256=target.sha(location/'export/share/applications'/(APPLICATION+'.desktop')))
        key=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()[:20]
        artifact=WORK/'artifacts'/key;receipt=artifact/'build.json'
        if receipt.exists():
            saved=json.loads(receipt.read_text());assert saved['spec']==spec
            for view in saved['views'].values():verify(view)
            print(receipt);return
        artifact.mkdir(parents=True,exist_ok=True);views={}
        baseline=record.get('baseline_packages',c1['packages'])
        for role,package in [('source-stock',baseline['stock']),('source-passive',baseline['instrumented']),*record['packages'].items()]:
            view=artifact/role;shutil.copytree(location/'files',view,symlinks=True)
            for p in [view,*[p for p in view.rglob('*') if p.is_dir() and not p.is_symlink()]]:p.chmod(p.stat().st_mode|0o700)
            engine=Path(package['directory'])
            assert target.sha(Path(package['archive']))==package['archive_sha256']
            for name,digest in package['files'].items():assert target.sha(engine/name)==digest
            appdir=view/'teams-for-linux'
            for p in engine.iterdir():
                if p.name=='resources':continue
                q=appdir/('teams-for-linux' if p.name=='electron' else p.name)
                if p.is_dir():
                    if q.exists():shutil.rmtree(q)
                    shutil.copytree(p,q,symlinks=True)
                else:
                    if q.exists() or q.is_symlink():q.unlink()
                    shutil.copy2(p,q)
            fuses=preserve_fuses(appdir/'teams-for-linux',location/'files/teams-for-linux/teams-for-linux')
            for name in ('bin','lib'):overlay(zypak_folder/name,view/name)
            licenses=view/'share/licenses/fontreal-zypak';licenses.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(WORK/'sources/zypak/LICENSE',licenses/'LICENSE')
            shutil.copyfile(WORK/'sources/zypak/nickle/LICENSE',licenses/'Nickle-LICENSE')
            assert tree(appdir/'resources')==tree(location/'files/teams-for-linux/resources')
            views[role]=dict(directory=str(view),fuses=fuses,files=tree(view),engine_sha256=target.sha(appdir/'teams-for-linux'))
        saved=dict(spec=spec,views=views)
        receipt.write_text(json.dumps(saved,indent=2)+'\n');print(receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build-record',type=Path,required=True)
    try:build(parser.parse_args().build_record.resolve())
    except (ValueError,AssertionError,subprocess.CalledProcessError) as error:raise SystemExit(str(error))
