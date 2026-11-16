#!/usr/bin/env python3
"""Synthetic launch contracts through actual written hooks; no rendering claim."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import chromium_delivery as delivery


def put(path,text):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)


# The provider observes real hashing/copying and replaces only external Flatpak/reload.
PROVIDER=r'''
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
root=Path(os.environ['LAUNCH_FIXTURE'])
logfd=os.open(root/'events.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
def note(value):os.write(logfd,(json.dumps(value)+'\n').encode())
original_digest=hashlib.file_digest
def digest(stream,*args,**kwargs):
    note(dict(kind='hash',path=str(stream.name)))
    return original_digest(stream,*args,**kwargs)
hashlib.file_digest=digest
original_copy=shutil.copytree
def copy(*args,**kwargs):
    note(dict(kind='copy',source=str(args[0])))
    return original_copy(*args,**kwargs)
shutil.copytree=copy
original_output=subprocess.check_output
def output(command,*args,**kwargs):
    if str(command[0])=='/usr/bin/flatpak':command=[str(root/'native-flatpak'),*map(str,command[1:])]
    return original_output(command,*args,**kwargs)
subprocess.check_output=output
original_run=subprocess.run
def run(command,*args,**kwargs):
    if list(command)==['systemctl','--user','daemon-reload']:
        note(dict(kind='reload'));return subprocess.CompletedProcess(command,0)
    return original_run(command,*args,**kwargs)
subprocess.run=run
original_exec=os.execv
def execute(file,args):
    if file=='/usr/bin/flatpak':return original_exec(str(root/'native-flatpak'),[str(root/'native-flatpak'),*args[1:]])
    return original_exec(file,args)
os.execv=execute
def audit(event,args):
    if event=='open' and str(args[0]).endswith('qualification.json'):
        note(dict(kind='qualification',path=str(args[0])))
sys.addaudithook(audit)
'''

NATIVE=r'''#!/usr/bin/env python3
import json,os,stat,sys
from pathlib import Path
root=Path(os.environ['LAUNCH_FIXTURE']);args=sys.argv[1:]
config=json.loads((root/'native.json').read_text())
def note(value):
    with (root/'events.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
if args[:1]==['info']:
    assert args[-2]=='--show-location',args
    selectors=args[1:-2]
    assert all(x in ('--user','--system','--installation=test') for x in selectors),args
    variant='user' if '--user' in selectors else ('installation' if '--installation=test' in selectors else config['current'])
    note(dict(kind='info',argv=['/usr/bin/flatpak',*args],variant=variant))
    print(config['deployments'][args[-1]][variant]);raise SystemExit
directories=[]
for value in os.listdir('/proc/self/fd'):
    try:
        descriptor=int(value)
        if descriptor>2 and stat.S_ISDIR(os.fstat(descriptor).st_mode):directories.append(descriptor)
    except OSError:pass
observed=dict(kind='exec',argv=['/usr/bin/flatpak',*args],selected=False)
paths=[x.split('=',1)[1] for x in args if x.startswith('--app-path=')]
if paths:
    assert len(paths)==1
    view=Path(paths[0]);fd=int(next(x.split('=',1)[1] for x in args if x.startswith('--ro-bind-fd=')))
    assert directories==[fd],directories
    assert os.get_inheritable(fd)
    assert (os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(view.stat().st_dev,view.stat().st_ino)
    assert '--env=FONTREAL_ZYPAK_APP_PATH='+str(view) in args
    observed.update(selected=True,view=str(view),fd_valid=True)
else:assert directories==[],directories
note(observed)
if os.environ.get('LAUNCH_STDIO_PROBE')=='1':
    os.write(1,b'probe-stdout\n');os.write(2,b'probe-stderr\n')
'''


def main():
    (ROOT/'results/chromium-launch').mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='launch-',dir=ROOT/'build') as temporary:
        root=Path(temporary).resolve();home=root/'home';home.mkdir();provider=root/'provider'
        put(provider/'sitecustomize.py',PROVIDER);put(root/'native-flatpak',NATIVE);(root/'native-flatpak').chmod(0o755)
        # Saved artifacts deliberately live outside this controller's WORK, in distinct roots.
        signature=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'+bytes([1,9])
        selected=signature+b'101100011'+b'selected engine'
        fuses={'A':b'111100011','B':b'011100011','user':b'111000011','installation':b'011000011'}
        deployments={};builds={};sources={}
        for name,application in delivery.APPS.items():
            folder,executable,command=delivery.builder.LAYOUTS[application]
            source=root/('saved-'+name)/'artifacts/exact/normal';sources[name]=source
            put(source/folder/'resources/app.asar','obsolete '+name)
            put(source/folder/executable,'');(source/folder/executable).write_bytes(selected+name.encode())
            for sidecar in ('icudtl.dat','resources.pak','LICENSE.fontreal.txt'):put(source/folder/sidecar,'selected '+name+' '+sidecar)
            for relative in ('bin/zypak-helper','lib/libzypak-preload-host.so'):put(source/relative,'selected '+relative)
            (source/'bin/zypak-wrapper').symlink_to('/app/bin/zypak-helper')
            put(source/'share/licenses/fontreal-zypak/LICENSE','BSD notice')
            deployments[application]={}
            for variant in fuses:
                location=root/'deployments'/name/variant;deployments[application][variant]=str(location)
                put(location/'files'/folder/'resources/app.asar','current '+name+' '+variant)
                put(location/'files'/folder/executable,'');(location/'files'/folder/executable).write_bytes(signature+fuses[variant]+b'native engine')
                put(location/'files/bin'/command,'native wrapper '+name+' '+variant)
                put(location/'files/lib/new-native-module.so','native module '+variant)
                put(location/'export/share/applications'/(application+'.desktop'),
                    '[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/flatpak run --branch=stable --arch=x86_64 --command='+command+' --file-forwarding '+application+' @@u %U @@\n')
            record=dict(spec=dict(application=application,location='obsolete deployment'),views=dict(normal=dict(
                directory=str(source),files=delivery.builder.tree(source),engine_sha256=delivery.target.sha(source/folder/executable))))
            build=source.parent/'build.json';builds[name]=build;put(build,json.dumps(record))
            put(build.parent/'qualification.json',json.dumps(dict(passed=True,build_sha256=delivery.target.sha(build))))
        native=dict(current='A',deployments=deployments);put(root/'native.json',json.dumps(native))
        originals={str(p):p.read_bytes() for p in (root/'deployments').rglob('*') if p.is_file()}
        marker=home/'original-profile/marker';put(marker,'keep working data');marker_bytes=marker.read_bytes()
        env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/'config'),XDG_DATA_HOME=str(home/'data'),
                 LAUNCH_FIXTURE=str(root),PYTHONPATH=os.pathsep.join((str(provider),str(ROOT/'tools'))),PYTHONDONTWRITEBYTECODE='1')
        # Run byte-identical owners in fixture storage, including their generated views.
        isolated=root/'controller'
        for name in ('chromium_delivery.py','build-chromium-delivery.py','chromium_flatpak.py','browser.py','freetype_provider.py'):
            destination=isolated/'tools'/name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/'tools'/name,destination)
            assert destination.read_bytes()==(ROOT/'tools'/name).read_bytes()
        legacy=root/'legacy/tools/chromium_delivery.py'
        for name in ('chromium_delivery.py','build-chromium-delivery.py'):
            destination=legacy.parent/name;destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(subprocess.check_output(['git','show','46b1bf0:tools/'+name],cwd=ROOT))
        controller=isolated/'tools/chromium_delivery.py'
        env['PYTHONPATH']=os.pathsep.join((str(provider),str(isolated/'tools')))
        registry=home/'config/fontreal/chromium/apps.json';oldstate=registry.with_name('teams.json')
        shared=home/'.local/bin/flatpak';events=root/'events.jsonl';observations=[]

        def hooks(name):
            app=delivery.APPS[name];command=delivery.builder.LAYOUTS[app][2]
            return dict(flatpak=shared,command=home/'.local/bin'/command,application=home/'.local/bin'/app,
                        desktop=home/'data/applications'/(app+'.desktop'),
                        autostart=home/'config/systemd/user'/('app-'+app+'@autostart.service.d')/'50-fontreal.conf')

        def logs():return [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []

        def call(*args,tool=controller,ok=True):
            result=subprocess.run([sys.executable,'-B',str(tool),*map(str,args)],env=env,text=True,capture_output=True)
            assert (result.returncode==0)==ok,(args,result.stdout,result.stderr)
            return result

        def status(name,enabled):
            before=snapshot();result=json.loads(call('status',name).stdout)
            assert result['enabled']==enabled and result['application']==delivery.APPS[name],result
            if enabled:assert result['build']==str(builds[name]) and result['compatibility'] is None,result
            assert snapshot()==before

        def snapshot():
            return {str(p):(p.read_bytes(),p.stat().st_mode&0o777) for p in home.rglob('*') if p.is_file()}

        def refused(*args):
            before=snapshot();reloads=sum(x['kind']=='reload' for x in logs())
            result=call(*args,ok=False)
            assert snapshot()==before and sum(x['kind']=='reload' for x in logs())==reloads
            return result

        def launch(command,argv,chosen,variant='A',name=None):
            before=logs();state=snapshot()
            result=subprocess.run(list(map(str,command)),env=env,text=True,capture_output=True)
            assert result.returncode==0,(command,result.stdout,result.stderr)
            deadline=time.monotonic()+5
            while True:
                new=logs()[len(before):];actual=[e for e in new if e['kind']=='exec']
                if actual:break
                assert time.monotonic()<deadline,new
                time.sleep(.01)
            assert len(actual)==1,new
            observed=actual[0];observations.append(observed)
            assert observed['selected']==chosen,(command,observed,result.stderr)
            stripped=[a for a in observed['argv'][1:] if not a.startswith(('--app-path=','--ro-bind-fd=','--env=FONTREAL_ZYPAK_APP_PATH='))]
            assert stripped==argv,(stripped,argv)
            if chosen:
                index=next(i for i,a in enumerate(argv) if a in (delivery.APPS[name],delivery.APPS[name]+'/x86_64',
                    delivery.APPS[name]+'/x86_64/stable','app/'+delivery.APPS[name]+'/x86_64/stable'))
                options=observed['argv'][1+index:1+index+3]
                assert [a.split('=',1)[0] for a in options]==['--app-path','--ro-bind-fd','--env']
                assert observed['argv']==['/usr/bin/flatpak',*argv[:index],*options,*argv[index:]]
            assert snapshot()==state
            assert not any(e['kind']=='qualification' for e in new),new
            if chosen:
                app=delivery.APPS[name];folder,executable,native_command=delivery.builder.LAYOUTS[app]
                view=Path(observed['view'])
                assert (view/folder/'resources/app.asar').read_text()=='current '+name+' '+variant
                assert (view/folder/executable).read_bytes()==signature+fuses[variant]+b'selected engine'+name.encode()
                assert (view/'bin'/native_command).read_text()=='native wrapper '+name+' '+variant
                assert (view/'lib/new-native-module.so').read_text()=='native module '+variant
                assert (view/folder/'icudtl.dat').read_text()=='selected '+name+' icudtl.dat'
                assert (view/folder/'LICENSE.fontreal.txt').read_text()=='selected '+name+' LICENSE.fontreal.txt'
                assert (view/'share/licenses/fontreal-zypak/LICENSE').read_text()=='BSD notice'
                assert (view/'bin/zypak-wrapper').is_symlink()
                info=[e for e in new if e['kind']=='info'];assert len(info)==1 and info[0]['variant']==variant
            else:
                assert observed['argv']==['/usr/bin/flatpak',*argv]
                assert not any(e['kind']=='info' for e in new)
            return observed,new

        def adapter(argv,chosen=True,**kwargs):return launch([shared,*argv],argv,chosen,**kwargs)

        def enable(name):call('enable',name,'--record',builds[name])

        def seed_legacy():
            # Independent C4 forms: do not call the new owner or its text/path helpers.
            application='com.github.IsmaelMartinez.teams_for_linux';config=home/'config';data=home/'data';bindir=home/'.local/bin'
            destinations=[bindir/'flatpak',bindir/'teams-for-linux',bindir/application,
                          data/'applications'/(application+'.desktop'),
                          config/'systemd/user'/('app-'+application+'@autostart.service.d')/'50-fontreal.conf']
            launch_args=[sys.executable,'-B',str(legacy)]
            for index,p in enumerate(destinations[:3]):
                args=[*launch_args,'flatpak','--'] if index==0 else [*launch_args,'run','teams','--']
                put(p,'#!/bin/sh\nexec '+' '.join(map(shlex.quote,args))+' "$@"\n');p.chmod(0o755)
            desktop=Path(deployments[application]['A'])/'export/share/applications'/(application+'.desktop')
            # C4 desktop_arg quotes the path when needed; this synthetic HOME has no spaces.
            from browser import desktop_arg
            put(destinations[3],desktop.read_text().replace('Exec=/usr/bin/flatpak ','Exec='+desktop_arg(destinations[0])+' '))
            portal=config/'autostart'/(application+'.desktop')
            argument=json.dumps(str(portal),ensure_ascii=False).replace('%','%%')
            put(destinations[4],'[Service]\nExecStart=\nExecStart=:/usr/bin/gio launch '+argument+'\n')
            proof=builds['teams'].parent/'qualification.json'
            state=dict(application=application,build=str(builds['teams']),build_sha256=delivery.target.sha(builds['teams']),
                       qualification=str(proof),qualification_sha256=delivery.target.sha(proof),tool_sha256=delivery.target.sha(legacy),
                       hooks=[dict(path=str(p),sha256=delivery.target.sha(p)) for p in destinations])
            put(oldstate,json.dumps(state,indent=2)+'\n');oldstate.chmod(0o600)
            return state

        # Neither and each fresh single-app state; target-specific missing engine refusal.
        status('teams',False);status('bitwarden',False)
        for name in delivery.APPS:
            folder,exe,_=delivery.builder.LAYOUTS[delivery.APPS[name]];binary=sources[name]/folder/exe;data=binary.read_bytes();binary.unlink()
            assert 'engine unavailable' in refused('enable',name,'--record',builds[name]).stderr
            binary.write_bytes(data)
            enable(name);status(name,True);status('bitwarden' if name=='teams' else 'teams',False)
            app=delivery.APPS[name]
            adapter(['run',app],name=name)
            call('disable',name);assert not shared.exists() and not registry.exists()

        foreign=hooks('bitwarden')['autostart'];put(foreign,'foreign fresh destination')
        refused('enable','bitwarden','--record',builds['bitwarden']);foreign.unlink()

        # Read-only legacy status and absent Bitwarden disable never migrate or reload.
        legacy_state=seed_legacy();before=snapshot();reloads=sum(x['kind']=='reload' for x in logs())
        status('teams',True);status('bitwarden',False);call('disable','bitwarden')
        assert snapshot()==before and sum(x['kind']=='reload' for x in logs())==reloads
        # Later old hook foreign: complete validation before migration writes anything.
        foreign=hooks('teams')['autostart'];saved=foreign.read_bytes();foreign.write_text('foreign later legacy hook')
        refused('enable','bitwarden','--record',builds['bitwarden']);foreign.write_bytes(saved)
        # A newly claimed later destination also blocks migration atomically.
        foreign=hooks('bitwarden')['autostart'];put(foreign,'foreign new destination')
        refused('enable','bitwarden','--record',builds['bitwarden']);foreign.unlink()
        enable('bitwarden');assert not oldstate.exists()
        state=json.loads(registry.read_text());assert len(state['hooks'])==9
        assert state['apps']['teams']=={k:v for k,v in legacy_state.items() if k!='hooks'}
        for name in delivery.APPS:
            for key in ('flatpak','command','application'):
                text=hooks(name)[key].read_text();assert str(controller) in text and str(legacy) not in text
        before=snapshot();call('disable','teams',tool=legacy);assert snapshot()==before
        status('teams',True);status('bitwarden',True)

        # Real commands and shared adapter: current A, cached A, then current B for both layouts.
        payload=['https://example.invalid/a b?x=1&y=2','--option-looking-app-argument']
        first_views={}
        for name,app in delivery.APPS.items():
            for key in ('command','application'):
                launch([hooks(name)[key],*payload],['run',app,*payload],True,name=name)
            first,_=adapter(['run',app,*payload],name=name);first_views[name]=first['view']
            cached,new=adapter(['run',app,*payload],name=name)
            assert cached['view']==first['view'] and not any(e['kind']=='copy' for e in new)
            allowed={str(p) for p in [registry,builds[name],*[Path(h['path']) for h in json.loads(registry.read_text())['hooks']]]}
            assert all(e['path'] in allowed for e in new if e['kind']=='hash'),new
            uri='https://example.invalid/a%20b?x=1&y=2';command=delivery.builder.LAYOUTS[app][2]
            launch(['/usr/bin/gio','launch',hooks(name)['desktop'],uri],
                   ['run','--branch=stable','--arch=x86_64','--command='+command,'--file-forwarding',app,'@@u',uri,'@@'],True,name=name)
        # Exercise the secured fixture's real exec-view case, including both trace streams.
        arguments=root/'exec-view-arguments.json';put(arguments,json.dumps(['run',delivery.APPS['bitwarden']]))
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as receiver:
            address='fontreal-launch-'+root.name;receiver.bind('\0'+address);receiver.settimeout(3)
            probe_env=dict(env,LAUNCH_STDIO_PROBE='1')
            result=subprocess.run([sys.executable,'-B',str(ROOT/'tests/bitwarden_delivery_test.py'),
                '--case','exec-view','--view',first_views['bitwarden'],'--native-arguments',str(arguments),
                '--trace-address',address],env=probe_env,text=True,capture_output=True)
            assert result.returncode==0,(result.stdout,result.stderr)
            assert {receiver.recv(100),receiver.recv(100)}=={b'probe-stdout\n',b'probe-stderr\n'}
        assert logs()[-1]['kind']=='exec' and logs()[-1]['selected'] and logs()[-1]['fd_valid']
        native['current']='B';put(root/'native.json',json.dumps(native))
        for name,app in delivery.APPS.items():
            observed,_=adapter(['run',app,*payload],name=name,variant='B');assert observed['view']!=first_views[name]
            command=delivery.builder.LAYOUTS[app][2]
            # Four accepted references spread across selectors, not a Cartesian matrix.
            for ref,selector,variant in [(app+'/x86_64','--user','user'),(app+'/x86_64/stable','--system','B'),
                                         ('app/'+app+'/x86_64/stable','--installation=test','installation')]:
                argv=[selector,'run','--file-forwarding','--command='+command,'--arch=x86_64','--branch=stable',ref,*payload]
                _,new=adapter(argv,name=name,variant=variant)
                assert [e for e in new if e['kind']=='info'][0]['argv'][2:-2]==[selector]
            other_command='bitwarden' if name=='teams' else 'teams-for-linux'
            for argv in (['run','other.app',*payload],['run','--file-forwarding','--command=other',app,*payload],
                         ['run','--command='+command,'--command='+other_command,app,*payload],
                         ['run','--user','--unknown',app,*payload],['run','--arch','x86_64',app,*payload]):
                adapter(argv,False)

        # Full ownership validation before re-enable or either disable.
        foreign=hooks('bitwarden')['autostart'];saved=foreign.read_bytes();foreign.write_text('foreign last shared-registry hook')
        refused('enable','teams','--record',builds['teams']);refused('disable','teams');refused('disable','bitwarden');foreign.write_bytes(saved)
        # Missing saved engine gives exact ordinary native fallback for either target.
        for name,app in delivery.APPS.items():
            folder,exe,_=delivery.builder.LAYOUTS[app];binary=sources[name]/folder/exe;data=binary.read_bytes();binary.unlink()
            adapter(['run',app,*payload],False)
            assert 'engine unavailable' in refused('enable',name,'--record',builds[name]).stderr
            binary.write_bytes(data)
        # Both complete disable orders, executing the remaining route after the first disable.
        for first,last in (('teams','bitwarden'),('bitwarden','teams')):
            call('disable',first);status(first,False);status(last,True);assert shared.exists()
            adapter(['run',delivery.APPS[first],*payload],False)
            launch([hooks(last)['command'],*payload],['run',delivery.APPS[last],*payload],True,name=last,variant='B')
            adapter(['run',delivery.APPS[last],*payload],name=last,variant='B')
            call('disable',last);assert not shared.exists() and not registry.exists()
            status(first,False);status(last,False)
            if first=='teams':enable('teams');enable('bitwarden')
        assert marker.read_bytes()==marker_bytes
        assert all(Path(p).read_bytes()==data for p,data in originals.items())
        result=dict(passed=True,securedExecViewBothStreams=True,scenarios=['S-ACT-'+str(i) for i in range(2,10)],observations=observations,
                    scope='Synthetic local launch contracts only. Actual rendering and original-profile lifecycle remain separate.',
                    external_seams=['Native Flatpak info/exec only; actual inherited FD checked in fake native executable.',
                                    'systemctl --user daemon-reload is recorded instead of invoking a user service.',
                                    'Hash/copy/qualification instrumentation observes calls; in-scope implementations execute unchanged.'])
    (ROOT/'results/chromium-launch/result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS Teams and Bitwarden shared activation launch contracts (S-ACT-2 through S-ACT-9)')


if __name__=='__main__':main()
