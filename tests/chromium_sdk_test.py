#!/usr/bin/env python3
"""Check SDK selection through the real assembler CLI with offline SDK responses."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SDK='org.freedesktop.Sdk/x86_64/25.08'
RUNTIME='org.freedesktop.Platform/x86_64/25.08'
CURRENT='3912bfb67e8fbda84403f805028df718c7f12216fe5cafb8b54b8bb0d57ad955'
HISTORICAL='d1eb1c10d166e7a611e0f26d2332aa9265ce2d048b054dca07f7919258ee1a0b'
RUNTIME_COMMIT='08713ee4ce58fee0b8ff2f5bb58e511ff2009c4d72209270d2ddd01fb0336a04'
TEAMS='com.github.IsmaelMartinez.teams_for_linux'
BITWARDEN='com.bitwarden.desktop'
SCOPED=('FLATPAK_USER_DIR','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','FLATPAK_SYSTEM_CACHE_DIR','TMPDIR')
FUSE=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')


def external_flatpak(config_path,command):
    config=json.loads(config_path.read_text());state_path=Path(config['state']);state=json.loads(state_path.read_text())
    args=command[1:];private='--user' in args or args[0] in ('build-init','build')
    environment={name:os.environ.get(name) for name in SCOPED}
    if private:
        assert all(value and Path(value).is_relative_to(config['work']) for value in environment.values())
    with Path(config['commands']).open('a') as stream:stream.write(json.dumps(dict(command=command,environment=environment,private=private))+'\n')
    if args[:2]==['run','--command=/usr/bin/true']:
        assert args[2] in config['apps'];return 0
    if args[:2]==['info','--show-location']:
        print(config['apps'][args[2]]['location']);return 0
    if args[:2]==['info','--show-commit']:
        print(RUNTIME_COMMIT if args[2]==RUNTIME else config['apps'][args[2]]['commit']);return 0
    if args==['--user','info','--show-commit',SDK]:
        if state['sdk'] is None:return 1
        print(state['sdk']);return 0
    if args[:2]==['--user','remote-add']:
        assert args==['--user','remote-add','--if-not-exists','flathub','https://dl.flathub.org/repo/flathub.flatpakrepo'];return 0
    if args[:2]==['--user','install']:
        assert args==['--user','install','--noninteractive','--assumeyes','--no-related','flathub',SDK]
        assert state['sdk'] is None;state['sdk']=CURRENT;write(state_path,state);return 0
    if args[:2]==['--user','update']:
        assert args==['--user','update','--noninteractive','--assumeyes','--commit='+CURRENT,SDK]
        state['sdk']=CURRENT;write(state_path,state);return 0
    if args[0]=='build-init':
        assert args[1]=='--arch=x86_64' and args[3:]==['org.fontreal.ZypakBuild','org.freedesktop.Sdk','org.freedesktop.Platform','25.08']
        folder=Path(args[2]);(folder/'files').mkdir(parents=True)
        (folder/'metadata').write_text('[Application]\nname=org.fontreal.ZypakBuild\nruntime='+RUNTIME+'\nsdk='+SDK+'\n')
        return 0
    if args[0]=='build':
        assert state['sdk'] in (CURRENT,HISTORICAL)
        if 'make' in args:
            assert args[1:3]==['--env=TMPDIR=/app/tmp','--env=XDG_CACHE_HOME=/app/.cache']
            folder=Path(args[3]);assert args[4:]==['make','-C','/app/zypak-source','-j8','all','install','FLATPAK_DEST=/app']
            for name in ('bin/zypak-helper','bin/zypak-wrapper.sh','lib/libzypak-preload-host.so'):
                path=folder/'files'/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('SDK compiler fixture '+state['sdk']+' '+name+'\n');path.chmod(0o755)
            (folder/'files/bin/zypak-wrapper').symlink_to('zypak-wrapper.sh')
            state['compiles']+=1;write(state_path,state);return 0
        assert Path(args[1]).is_relative_to(config['work'])
        if args[2:]==['g++','--version']:
            print('Freedesktop SDK compiler fixture '+state['sdk']);return 0
        assert args[2:]==['sha256sum','/usr/bin/g++','/usr/bin/ld']
        for tool in ('g++','ld'):print(hashlib.sha256((state['sdk']+tool).encode()).hexdigest(),' /usr/bin/'+tool)
        return 0
    raise AssertionError('Unexpected external Flatpak command: '+repr(command))


def fixture_cli(config_path,arguments):
    config=json.loads(config_path.read_text());checkout=Path(config['checkout']);real_run=subprocess.run
    def boundary(command,**kwargs):
        command=list(map(str,command))
        if Path(command[0]).name=='flatpak':
            return real_run([sys.executable,str(Path(__file__).resolve()),'--flatpak',str(config_path),*command],**kwargs)
        assert command[0] in ('git','patch'),command
        directory=Path(command[command.index('-C')+1]) if command[0]=='git' else Path(command[command.index('-d')+1])
        assert directory.resolve().is_relative_to(config['work']),command
        return real_run(command,**kwargs)
    sys.path.insert(0,str(checkout/'tools'))
    sys.argv=[str(checkout/'tools/build-chromium-delivery.py'),*arguments]
    with patch('subprocess.run',boundary):runpy.run_path(sys.argv[0],run_name='__main__')


def snapshot(folder):
    return {str(p.relative_to(folder)):(os.readlink(p) if p.is_symlink() else sha(p),p.lstat().st_mtime_ns)
            for p in folder.rglob('*') if p.is_symlink() or p.is_file()}


def package(folder,role,count):
    payload=folder/role/'payload';payload.mkdir(parents=True)
    (payload/'electron').write_bytes(b'\x7fELF'+FUSE+bytes((1,count))+b'1'*count+role.encode());(payload/'electron').chmod(0o755)
    (payload/'icudtl.dat').write_text('coherent '+role)
    (payload/'resources').mkdir();(payload/'resources/default_app.asar').write_text('engine resource excluded by app composition')
    files={str(p.relative_to(payload)):sha(p) for p in payload.rglob('*') if p.is_file()}
    archive=payload.parent/'dist.zip'
    with zipfile.ZipFile(archive,'w') as bundle:
        for name in files:bundle.write(payload/name,name)
    return dict(directory=str(payload),archive=str(archive),archive_sha256=sha(archive),files=files)


def setup(checkout):
    for name in ('tools/build-chromium-delivery.py','tools/chromium_flatpak.py','tools/chromium_delivery.py','patches/zypak-693a71c5-app-fd.patch'):
        path=checkout/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
        assert path.read_bytes()==(ROOT/name).read_bytes()
    work=checkout/'build/chromium-delivery';source=work/'sources/zypak'
    original=(ROOT/'build/chromium-delivery/sources/zypak').resolve();assert (original/'.git').is_dir(),'Prepare the pinned transport source before this offline check'
    shutil.copytree(original,source,symlinks=True)
    # Keep copied submodule operations confined even if the native checkout used an absolute path.
    config=source/'.git/modules/nickle/config'
    import configparser
    parser=configparser.ConfigParser();parser.read(config);parser['core']['worktree']='../../../nickle'
    with config.open('w') as stream:parser.write(stream)
    apps={};records={}
    for name,application,folder,executable,command,fuses,vendor,commit in (
        ('teams',TEAMS,'teams-for-linux','teams-for-linux','teams-for-linux','111100011',CURRENT,'be209a501c1b457a11fbde3f175010b0fb371fb8ad8c80c9705a6ff2410f8f57'),
        ('bitwarden',BITWARDEN,'Bitwarden','bitwarden-app','bitwarden','01000101',HISTORICAL,'c27bfa5ba9fa5c24e5f2c1b906f7653fc7074305f8f93dbbfc35790292b73698')):
        location=checkout/'native'/name;files=location/'files';app=files/folder;app.mkdir(parents=True)
        (location/'metadata').write_text('[Application]\nname='+application+'\nruntime='+RUNTIME+'\ncommand='+command+'\n')
        write(files/'manifest.json',{'id':application,'sdk-commit':vendor})
        (app/executable).write_bytes(b'\x7fELF'+FUSE+bytes((1,len(fuses)))+fuses.encode()+b'native');(app/executable).chmod(0o755)
        (app/'resources').mkdir();(app/'resources/app.asar').write_text('native application resource '+name)
        wrapper=files/'bin'/command;wrapper.parent.mkdir()
        if name=='bitwarden':
            wrapper.write_text('#!/bin/sh\nexport TMPDIR="$XDG_RUNTIME_DIR/app/$FLATPAK_ID"\nulimit -c 0\nexport ZYPAK_LD_PRELOAD="/app/bin/libprocess_isolation.so"\nexport PROCESS_ISOLATION_LD_PRELOAD="/app/bin/libprocess_isolation.so"\nif [ "$USE_X11" != "false" ]; then\nPARAMS="--ozone-platform=x11"\nfi\nexec zypak-wrapper /app/Bitwarden/bitwarden-app "$@" "$PARAMS"\n')
            (app/'libprocess_isolation.so').write_text('native isolation fixture')
        else:wrapper.write_text('#!/bin/sh\nexec zypak-wrapper /app/teams-for-linux/teams-for-linux "$@"\n')
        desktop=location/'export/share/applications'/(application+'.desktop');desktop.parent.mkdir(parents=True)
        desktop.write_text('[Desktop Entry]\nName='+name+'\nExec=/usr/bin/flatpak run --branch=stable --arch=x86_64 --command='+command+' '+application+' %U\n')
        packages={role:package(checkout/'packages'/name,role,len(fuses)) for role in ('stock','instrumented','normal','trace')}
        c1=checkout/'packages'/name/'c1.json';write(c1,dict(packages={k:packages[k] for k in ('stock','instrumented')}))
        record=checkout/'packages'/name/'selected.json';write(record,dict(spec=dict(c1_record=str(c1)),packages={k:packages[k] for k in ('normal','trace')},baseline_packages={k:packages[k] for k in ('stock','instrumented')}))
        apps[application]=dict(location=str(location),commit=commit,fuses=fuses,folder=folder,executable=executable,command=command,vendor=vendor)
        records[name]=record
    state=checkout/'external-state.json';write(state,dict(sdk=None,compiles=0))
    config=checkout/'fixture.json';write(config,dict(checkout=str(checkout),work=str(work),state=str(state),commands=str(checkout/'external-commands.jsonl'),apps=apps))
    return config,records


def main():
    output=(ROOT/'results/chromium-sdk').resolve();output.mkdir(parents=True,exist_ok=True)
    scratch=(ROOT/'build/chromium-sdk-test').resolve();scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cli-',dir=scratch) as temporary:
        checkout=Path(temporary);config_path,records=setup(checkout);config=json.loads(config_path.read_text())
        state_path=Path(config['state']);commands=Path(config['commands']);work=Path(config['work'])
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',
                 GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='protocol.allow',GIT_CONFIG_VALUE_0='never')
        native_before=snapshot(checkout/'native')
        def invoke(target):
            start=len(commands.read_text().splitlines()) if commands.exists() else 0
            args=['--build-record',str(records[target or 'teams'])]+(['--target',target] if target else [])
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--fixture',str(config_path),*args],env=env,text=True,capture_output=True,check=True)
            receipt=Path(result.stdout.splitlines()[-1]);record=json.loads(receipt.read_text())
            application=BITWARDEN if target=='bitwarden' else TEAMS;native=config['apps'][application]
            assert record['spec']['application']==application and record['spec']['recipe_sha256']==sha(ROOT/'tools/build-chromium-delivery.py')
            assert set(record['views'])=={'source-stock','source-passive','normal','trace'}
            for view in record['views'].values():
                directory=Path(view['directory']);assert view['fuses']['after']==native['fuses']
                assert (directory/'bin'/native['command']).read_bytes()==(Path(native['location'])/'files/bin'/native['command']).read_bytes()
                assert (directory/native['folder']/'resources/app.asar').read_text()=='native application resource '+('bitwarden' if application==BITWARDEN else 'teams')
            observed=[json.loads(line) for line in commands.read_text().splitlines()[start:]]
            assert snapshot(checkout/'native')==native_before
            return receipt,record,observed
        def actual(record,sdk):
            zypak=record['spec']['zypak'];assert zypak['spec']['sdk_commit']==sdk and zypak['spec']['runtime_commit']==RUNTIME_COMMIT
            assert zypak['compiler']=='Freedesktop SDK compiler fixture '+sdk
            for tool in ('g++','ld'):assert hashlib.sha256((sdk+tool).encode()).hexdigest()+'  /usr/bin/'+tool in zypak['tools_sha256']
            folder=work/'zypak'/hashlib.sha256(json.dumps(zypak['spec'],sort_keys=True).encode()).hexdigest()[:20]
            for name,digest in zypak['files'].items():assert sha(folder/name)==digest and sdk in (folder/name).read_text()
            return folder
        cold,record,cold_commands=invoke('bitwarden');first=actual(record,CURRENT)
        assert json.loads(state_path.read_text())==dict(sdk=CURRENT,compiles=1)
        assert any(row['command'][1:3]==['--user','install'] for row in cold_commands)
        assert not any(any(arg.startswith('--commit=') for arg in row['command']) for row in cold_commands)
        assert config['apps'][BITWARDEN]['vendor']==HISTORICAL!=CURRENT
        unchanged=(snapshot(cold.parent),snapshot(first))
        warm,warm_record,warm_commands=invoke('bitwarden');assert warm==cold and warm_record==record
        assert unchanged==(snapshot(warm.parent),snapshot(first)) and json.loads(state_path.read_text())['compiles']==1
        assert not any(row['command'][1] in ('build','build-init') for row in warm_commands)
        write(state_path,dict(sdk=HISTORICAL,compiles=1))
        changed,changed_record,changed_commands=invoke('bitwarden');second=actual(changed_record,HISTORICAL)
        assert changed!=cold and second!=first and json.loads(state_path.read_text())['compiles']==2
        assert not any(any(arg.startswith('--commit=') for arg in row['command']) for row in changed_commands)
        assert unchanged==(snapshot(cold.parent),snapshot(first))
        teams=[]
        for target in ('teams',None):
            write(state_path,dict(sdk=HISTORICAL,compiles=2))
            receipt,result,rows=invoke(target);actual(result,CURRENT)
            assert any('--commit='+CURRENT in row['command'] for row in rows)
            assert json.loads(state_path.read_text())==dict(sdk=CURRENT,compiles=2)
            teams.append(receipt)
        assert teams[0]==teams[1]
        result=dict(passed=True,realCli=True,realSourceAndPatch=True,fourRoles=True,coldBitwardenActualSdk=CURRENT,
                    vendorBitwardenSdk=HISTORICAL,warmArtifactsUnchanged=True,changedActualSdk=HISTORICAL,
                    differentActualSdkChangesArtifact=True,explicitAndDefaultTeamsPinPreserved=True,
                    nativeFixturesUnchanged=True,externalBoundaryOnly=True,commands=[json.loads(line) for line in commands.read_text().splitlines()])
        write(output/'result.json',result)
    print('PASS real assembler CLI SDK selection, provenance, cache reuse and Teams pin')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--flatpak':raise SystemExit(external_flatpak(Path(sys.argv[2]),sys.argv[3:]))
    if len(sys.argv)>1 and sys.argv[1]=='--fixture':fixture_cli(Path(sys.argv[2]),sys.argv[3:])
    else:main()
