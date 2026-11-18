#!/usr/bin/env python3
"""Check the packaged Bitwarden window without changing its native security."""
import argparse
import configparser
import ctypes as C
import ctypes.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import chromium_delivery_test as shared
from chromium_delivery_test import asar_source
from chromium_flatpak import binary,sha

ROOT=Path(__file__).resolve().parents[1]
APPLICATION='com.bitwarden.desktop'


def run(command):
    return subprocess.check_output(list(map(str,command)),text=True).strip()


def original_state():
    data=Path.home()/'.var/app'/APPLICATION/'config/Bitwarden/data.json'
    settings=json.loads(data.read_text())
    preference=settings.get('global_desktopSettings_openAtLogin',True)
    assert isinstance(preference,bool)
    autostart=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart'/(APPLICATION+'.desktop')
    assert not autostart.is_symlink()
    rows=[row for row in run(['/usr/bin/flatpak','permission-show',APPLICATION]).splitlines()
          if row.split('\t')[:3]==['background','background',APPLICATION]]
    assert len(rows)==1, 'Reconcile native background permission before the private fixture'
    permission=rows[0]
    assert permission.split()==['background','background',APPLICATION,'yes','0x00'], 'Reconcile native background permission before the private fixture'
    return dict(openAtLogin=preference,autostart_sha256=sha(autostart) if autostart.is_file() else None,
                backgroundPermission=permission)


def instances():
    return {line for line in run(['/usr/bin/flatpak','ps','--columns=application,instance']).splitlines()
            if line.startswith(APPLICATION+'\t')}


def working_instances():
    # Flatpak also lists short-lived command probes and nested renderer sandboxes.
    processes={}
    for path in Path('/proc').glob('[0-9]*/status'):
        try:fields=dict(line.split(':',1) for line in path.read_text().splitlines() if ':' in line)
        except (OSError,ValueError):continue
        if fields.get('Name','').strip()=='bitwarden-app' and fields.get('NSpid','').split()==[path.parent.name,'2']:
            processes.setdefault(int(fields['PPid']),[]).append(int(path.parent.name))
    result={}
    for line in run(['/usr/bin/flatpak','ps','--columns=application,instance']).splitlines():
        application,instance=line.split('\t')
        if application!=APPLICATION:continue
        try:
            payload=(Path(os.environ['XDG_RUNTIME_DIR'])/'.flatpak'/instance/'bwrapinfo.json').read_text()
            if not payload.strip():continue
            child=json.loads(payload)['child-pid']
        except FileNotFoundError:continue
        matches=processes.get(child,[]);assert len(matches)<=1
        if matches:result[instance]=matches[0]
    return result


def active_state(unit):
    result=subprocess.run(['systemctl','--user','show',unit,'--property=ActiveState','--value'],text=True,capture_output=True)
    assert result.returncode in (0,4)
    return result.stdout.strip()


def check_instance_selection(destination):
    before=working_instances();raw=instances()
    child=subprocess.Popen(['/usr/bin/flatpak','run','--command=/usr/bin/sleep',APPLICATION,'4'],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+5
        while True:
            during=instances()
            if during-raw:break
            assert time.monotonic()<deadline and child.poll() is None
            time.sleep(.05)
        assert working_instances()==before
        assert child.wait(timeout=10)==0 and working_instances()==before
    finally:
        if child.poll() is None:child.wait(timeout=10)
    (destination/'instance-selection.json').write_text(json.dumps(dict(passed=True,original=before,
        rawBefore=sorted(raw),rawDuring=sorted(during),nativeHelperExcluded=True),indent=2)+'\n')


def unit_instance(unit,view):
    pid=int(run(['systemctl','--user','show',unit,'--property=MainPID','--value']))
    matches=[]
    for line in run(['/usr/bin/flatpak','ps','--columns=application,instance,pid']).splitlines():
        application,instance,launcher=line.split('\t')
        if application!=APPLICATION or int(launcher)!=pid:continue
        info=configparser.ConfigParser(interpolation=None)
        info.read(Path(os.environ['XDG_RUNTIME_DIR'])/'.flatpak'/instance/'info')
        assert info['Application']['name']==APPLICATION and info['Instance']['app-path']==str(view)
        matches.append(dict(instance=instance,launcherPid=pid,appPath=info['Instance']['app-path']))
    assert len(matches)==1, 'No unique native instance for this private unit and application view'
    return matches[0]


def request(endpoint,method,params,destination):
    command=destination/('cdp-'+secrets.token_hex(6)+'.json')
    command.write_text(json.dumps(dict(method=method,params=params))+'\n')
    return json.loads(run(['node',ROOT/'tests/bitwarden_cdp.mjs',endpoint,command]))


def http(port,path):
    with urllib.request.urlopen('http://127.0.0.1:'+str(port)+path,timeout=2) as response:
        return json.load(response)


def native_stock(destination,view=None,observe=None,display=None,trace_address=None,passive=False,hook=None,environment=None,private_data=None):
    before=original_state();original_instances=working_instances()
    (destination/'original-instances.json').write_text(json.dumps(original_instances,indent=2)+'\n')
    location=Path(run(['/usr/bin/flatpak','info','--show-location',APPLICATION]))
    native=(location/'files').resolve();files=native if view is None else view.resolve()
    engine=files/'Bitwarden/bitwarden-app'
    identity=binary(engine);assert identity['electron_fuses']['states']=='01000101'
    archive=files/'Bitwarden/resources/app.asar'
    package=json.loads(asar_source(archive,'package.json'))
    source=asar_source(archive,package['main'])
    for marker in ('BITWARDEN_APPDATA_DIR','appDataPath','openAtLogin','desktopSettings','CURRENT_VERSION = 78'):
        assert marker in source,marker
    wrapper=(files/'bin/bitwarden').read_text()
    assert 'ZYPAK_LD_PRELOAD' in wrapper and 'PROCESS_ISOLATION_LD_PRELOAD' in wrapper
    assert '/app/bin/libprocess_isolation.so' in wrapper
    for path in ('bin/bitwarden','Bitwarden/resources/app.asar','Bitwarden/libprocess_isolation.so'):
        assert sha(files/path)==sha(native/path), 'Native application resources or isolation files changed'
    data=destination/'data' if private_data is None else private_data;data.mkdir(exist_ok=True)
    if private_data is not None:(data/'DevToolsActivePort').unlink(missing_ok=True)
    if private_data is None:(data/'data.json').write_text(json.dumps({'global_desktopSettings_openAtLogin':before['openAtLogin']})+'\n')
    unit='fontreal-bitwarden-proof-'+secrets.token_hex(6)+'.service'
    arguments=['run','--filesystem='+str(data)+':rw',
               '--env=BITWARDEN_APPDATA_DIR='+str(data),APPLICATION,'--remote-debugging-port=0']
    if passive:arguments.insert(1,'--env=FONTREAL_SKIA_TRACE=1')
    if hook is not None:arguments=['run','--user',APPLICATION,'--remote-debugging-port=0']
    launch=['/usr/bin/flatpak',*arguments]
    if view is not None or trace_address is not None:
        argv_file=destination/'native-arguments.json';argv_file.write_text(json.dumps(arguments)+'\n')
        launch=[sys.executable,'-B',str(Path(__file__).resolve()),'--case','exec-view','--native-arguments',str(argv_file)]
        if hook is not None:launch+=['--launch-hook',str(hook)]
        elif view is not None:launch+=['--view',str(files)]
        if trace_address is not None:launch+=['--trace-address',trace_address]
    command=['systemd-run','--user','--collect','--unit='+unit,'--property=Type=exec',
             '--property=StandardOutput=null','--property=StandardError=null',
             *launch]
    if display is not None:command.insert(3,'--setenv=DISPLAY='+display)
    if environment is not None:
        for key in ('HOME','FLATPAK_USER_DIR','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'):
            if key in environment:command.insert(3,'--setenv='+key+'='+environment[key])
    (destination/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    browser=None;port=None;quit_completed=False
    try:
        subprocess.run(command,check=True)
        if hook is not None:
            from types import SimpleNamespace
            pid=int(run(['systemctl','--user','show',unit,'--property=MainPID','--value']))
            observer=SimpleNamespace(pid=pid,poll=lambda:None if active_state(unit) in ('active','activating') else 0)
            entry=shared.native_entry(observer,arguments,files,destination/'native-entry.json')
            assert '--env=FONTREAL_PROFILE='+environment['EXPECTED_FONTREAL_PROFILE'] in entry['selectedOptions']
        deadline=time.monotonic()+60
        active=data/'DevToolsActivePort'
        while not active.is_file():
            assert active_state(unit) in ('active','activating'), 'Native fixture exited before its debugging endpoint'
            assert time.monotonic()<deadline, 'No private Chromium debugging endpoint'
            time.sleep(.2)
        lines=active.read_text().splitlines();assert len(lines)==2
        port=int(lines[0]);assert 0<port<65536 and lines[1].startswith('/devtools/browser/')
        browser='ws://127.0.0.1:'+str(port)+lines[1]
        version=request(browser,'Browser.getVersion',{},destination)
        while True:
            pages=[p for p in http(port,'/json/list') if p['type']=='page' and 'app.asar' in p.get('url','')]
            if len(pages)==1:
                page=pages[0];break
            assert time.monotonic()<deadline, 'No unique packaged Bitwarden page'
            time.sleep(.2)
        endpoint=page['webSocketDebuggerUrl']
        assert endpoint.startswith('ws://127.0.0.1:'+str(port)+'/devtools/page/')
        expression="({ready:document.readyState,appRoot:!!document.querySelector('app-root'),emailInput:!!document.querySelector('input[type=email]'),loginText:!!document.body&&document.body.innerText.includes('Log in'),nodeExposed:typeof require!=='undefined'})"
        while True:
            observed=request(endpoint,'Runtime.evaluate',dict(expression=expression,returnByValue=True),destination)['result']['value']
            if observed['ready']=='complete' and observed['appRoot'] and observed['emailInput'] and observed['loginText']:break
            assert time.monotonic()<deadline, 'Packaged login UI did not become ready'
            time.sleep(.3)
        assert observed['nodeExposed'] is False
        instance=unit_instance(unit,files)
        extra=observe(endpoint,browser,instance,files,destination) if observe is not None else None
        assert original_state()==before, 'Private bootstrap changed native startup configuration'
        result=dict(passed=True,case='native-stock' if view is None else 'view-readiness',application=APPLICATION,packageVersion=package['version'],
                    pixelEvidence=extra,engine=identity,asar_sha256=sha(archive),isolation_sha256=sha(files/'Bitwarden/libprocess_isolation.so'),
                    nativeState=before,version=version,observed=observed,instance=instance,
                    nodeInspectUsed=False,originalInstancesPreserved=original_instances.items()<=working_instances().items())
        assert result['originalInstancesPreserved']
    finally:
        if browser is not None:
            request(browser,'Browser.close',{},destination)
            deadline=time.monotonic()+30
            while active_state(unit) not in ('inactive','failed'):
                assert time.monotonic()<deadline, 'Private application did not quit normally; no force close attempted'
                time.sleep(.2)
            try:http(port,'/json/version')
            except (OSError,urllib.error.URLError):pass
            else:raise AssertionError('Private Chromium listener remained open')
            quit_completed=True
        if quit_completed:
            assert original_state()==before, 'Private teardown changed native startup configuration'
            assert original_instances.items()<=working_instances().items(), 'An original Bitwarden instance disappeared'
            if private_data is None:shutil.rmtree(data)
        else:
            (destination/'pending-cleanup.json').write_text(json.dumps(dict(unit=unit,privateData=str(data),forceCloseAttempted=False))+'\n')
    result['normalQuit']=True;result['privateDataRemoved']=private_data is None
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')


def readiness(build_record,destination):
    record=json.loads(build_record.read_text());assert record['spec']['application']==APPLICATION
    check_instance_selection(destination)
    roles={}
    for role in ('source-stock','source-passive','normal','trace'):
        view=record['views'][role];shared.delivery.builder.verify(view)
        folder=destination/role;folder.mkdir()
        native_stock(folder,Path(view['directory']))
        roles[role]=json.loads((folder/'result.json').read_text())
        assert roles[role]['engine']['sha256']==view['engine_sha256']
    (destination/'result.json').write_text(json.dumps(dict(passed=True,case='readiness',
        build=str(build_record),build_sha256=sha(build_record),roles=roles),indent=2)+'\n')


def main_pid(instance):
    child=json.loads((Path(os.environ['XDG_RUNTIME_DIR'])/'.flatpak'/instance['instance']/'bwrapinfo.json').read_text())['child-pid']
    rows=[]
    for path in Path('/proc').glob('[0-9]*/status'):
        try:fields=dict(line.split(':',1) for line in path.read_text().splitlines() if ':' in line)
        except (OSError,ValueError):continue
        if fields.get('PPid','').strip()==str(child) and fields.get('NSpid','').split()==[path.parent.name,'2']:rows.append(int(path.parent.name))
    assert len(rows)<=1,rows
    return rows[0] if rows else None

def control_q():
    x=C.CDLL(C.util.find_library('X11'));xt=C.CDLL(C.util.find_library('Xtst'))
    x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
    x.XStringToKeysym.argtypes=[C.c_char_p];x.XStringToKeysym.restype=C.c_ulong
    x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x.XKeysymToKeycode.restype=C.c_ubyte
    x.XSync.argtypes=[C.c_void_p,C.c_int];x.XCloseDisplay.argtypes=[C.c_void_p]
    xt.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x.XOpenDisplay(os.fsencode(os.environ['DISPLAY']));assert display
    try:
        control=x.XKeysymToKeycode(display,x.XStringToKeysym(b'Control_L'));q=x.XKeysymToKeycode(display,x.XStringToKeysym(b'q'));assert control and q
        for key,down in ((control,1),(q,1),(q,0),(control,0)):assert xt.XTestFakeKeyEvent(display,key,down,0)
        x.XSync(display,0)
    finally:x.XCloseDisplay(display)


OWNER_KEYS=('XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME','BITWARDEN_APPDATA_DIR')


def outer_instances(env):
    result=[]
    rows=subprocess.check_output(['/usr/bin/flatpak','ps','--columns=application,instance,pid'],env=env,text=True)
    runtime=Path(env['XDG_RUNTIME_DIR'])/'.flatpak'
    for line in rows.splitlines():
        application,instance,launcher=line.split('\t')
        if application!=APPLICATION:continue
        try:
            payload=(runtime/instance/'bwrapinfo.json').read_text()
            if not payload.strip():continue
            child=json.loads(payload)['child-pid']
            fields=dict(line.split(':',1) for line in (Path('/proc')/str(child)/'status').read_text().splitlines() if ':' in line)
            if fields['NSpid'].split()!=[str(child),'1']:continue
            info=configparser.ConfigParser(interpolation=None);info.optionxform=str;info.read(runtime/instance/'info')
            assert info['Application']['name']==APPLICATION
            environment=dict(info['Environment']) if info.has_section('Environment') else {}
            main=main_pid(dict(instance=instance))
            if main is None:continue
            result.append(dict(instance=instance,launcherPid=int(launcher),mainPid=main,
                               appPath=info['Instance']['app-path'],renderingProfile=environment.get('FONTREAL_PROFILE'),
                               ownerEnvironment={key:environment.get(key) for key in OWNER_KEYS}))
        except FileNotFoundError:continue
    return result


def lifecycle(engine_record,destination,env):
    destination.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-B',str(ROOT/'tools/build-chromium-delivery.py'),'--target','bitwarden','--build-record',str(engine_record)]
    built=subprocess.check_output(command,env=env,text=True);application_record=Path(built.splitlines()[-1]).resolve(strict=True)
    record=json.loads(application_record.read_text());assert record['spec']['application']==APPLICATION
    assert record['spec']['build_record']==str(engine_record.resolve()) and record['spec']['build_sha256']==sha(engine_record)
    v2='src/fontreal_v2_coverage.cpp' in json.loads(engine_record.read_text())['spec'].get('inputs',{})
    proof=json.loads((application_record.parent/('activation-check.json' if v2 else 'qualification.json')).read_text())
    assert proof['passed'] is True and proof['build_sha256']==sha(application_record),'Actual packaged pixel qualification must precede working-profile actions'
    # Activation receipts bind production inputs; unrelated lifecycle test edits do not invalidate the child proof.
    inputs={name:digest for name,digest in proof.get('test_inputs',{}).items() if not v2 or not name.startswith('tests/')}
    assert proof['engine_sha256']==sha(engine_record) and all(sha(ROOT/name)==digest for name,digest in inputs.items())
    if v2:assert proof['childWitness'] and proof['profiles']==['o','k3']
    state,_=shared.delivery.read_state();assert 'bitwarden' not in state['apps'],'Begin with Bitwarden delivery disabled'
    if state['apps']:shared.delivery.require_owned(state)
    teams=state['apps'].get('teams');before=original_state()
    native=(Path(subprocess.check_output(['/usr/bin/flatpak','info','--show-location',APPLICATION],env=env,text=True).strip())/'files').resolve()
    selected=shared.delivery.builder.current_view(record)
    data=(Path.home()/'.var/app'/APPLICATION/'config/Bitwarden').resolve(strict=True);identity=(data.stat().st_dev,data.stat().st_ino)
    original=outer_instances(env);assert len(original)==1 and original[0]['appPath']==str(native)
    owner=original[0]['ownerEnvironment'];assert owner['BITWARDEN_APPDATA_DIR'] is None
    # Flatpak's built-in XDG defaults are implicit in its context metadata.
    config=owner['XDG_CONFIG_HOME'] if owner['XDG_CONFIG_HOME'] is not None else str(data.parent)
    assert (Path(config)/'Bitwarden').resolve()==data
    _,hooks=shared.delivery.paths('bitwarden');autostart=Path(env.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart'/(APPLICATION+'.desktop')
    options=configparser.ConfigParser(interpolation=None);options.read(autostart)
    eligible=autostart.is_file() and not options['Desktop Entry'].getboolean('Hidden',fallback=False) and options['Desktop Entry'].getboolean('X-GNOME-Autostart-enabled',fallback=True)
    marker=data/('.fontreal-lifecycle-'+secrets.token_hex(12));value=secrets.token_hex(32)+'\n'
    with marker.open('x') as stream:stream.write(value)
    digest=sha(marker);observations=[];changed=False;finished=False;drivers=[]

    def same_data():
        assert (data.stat().st_dev,data.stat().st_ino)==identity and sha(marker)==digest
        assert original_state()==before

    def ownership():
        current,_=shared.delivery.read_state()
        if current['apps']:shared.delivery.require_owned(current)
        current_teams=current['apps'].get('teams')
        assert (None if current_teams is None else {k:v for k,v in current_teams.items() if k!='tool_sha256'})==(None if teams is None else {k:v for k,v in teams.items() if k!='tool_sha256'}),'Existing Teams engine identity changed'
        state_path=shared.delivery.paths()[0]
        if not state_path.exists():state_path=state_path.with_name('teams.json')
        return (state_path.read_bytes() if state_path.exists() else None,{row['path']:sha(Path(row['path'])) for row in current['hooks']})

    def ready(expected,driver=None):
        deadline=time.monotonic()+45
        while True:
            if driver is not None:assert driver.poll() in (None,0),'Ordinary launcher failed'
            instances=outer_instances(env)
            if instances:
                assert len(instances)==1;instance=instances[0]
                assert instance['appPath']==str(expected) and instance['ownerEnvironment']==owner,'View or original data owner changed'
                try:shared.dialog_geometry(instance['mainPid'],None,destination,env,activate=True)
                except AssertionError:
                    assert time.monotonic()<deadline;time.sleep(.2);continue
                same_data();return instance
            assert time.monotonic()<deadline,'Ordinary Bitwarden window did not become ready';time.sleep(.2)

    def quit_current():
        current=outer_instances(env);assert len(current)==1
        shared.dialog_geometry(current[0]['mainPid'],None,destination,env,activate=True);control_q()
        deadline=time.monotonic()+30
        while instances():
            assert time.monotonic()<deadline,'Normal Ctrl+Q did not close Bitwarden; no force attempted';time.sleep(.2)
        for child in drivers:
            child.wait(timeout=10);assert child.returncode==0
        drivers.clear();same_data()

    def launch(label,argv,expected):
        frozen=ownership();child=subprocess.Popen(list(map(str,argv)),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);drivers.append(child)
        observed=ready(expected,child);assert ownership()==frozen,'Ordinary launch changed hook ownership'
        if v2 and expected==selected:
            assert observed['renderingProfile']==shared.delivery.rendering_profile(),'Ordinary launch did not use the current saved choice'
        observations.append(dict(route=label,arguments=list(map(str,argv)),instance=observed,profileSame=True))

    tool=[sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py')]
    try:
        ready(native);quit_current();changed=True
        subprocess.run([*tool,'enable','bitwarden','--record',str(application_record)],env=env,check=True)
        ownership()
        for path in hooks.values():
            text=path.read_text()
            assert not any(flag in text for flag in ('--inspect','--remote-debugging','--user-data-dir','BITWARDEN_APPDATA_DIR'))
        routes=[('command',[hooks['command']]),('application-ID',[hooks['application']]),
                ('user-desktop',['/usr/bin/gio','launch',hooks['desktop']]),('shared-flatpak',[hooks['flatpak'],'run',APPLICATION])]
        if eligible:
            unit='app-'+APPLICATION+'@autostart.service'
            source=subprocess.check_output(['systemctl','--user','show',unit,'--property=SourcePath','--value'],env=env,text=True).strip()
            assert source==str(autostart),'No existing native startup unit for the original eligible entry'
            routes.append(('native-autostart',['systemctl','--user','start',unit]))
        for label,argv in routes:launch(label,argv,selected);quit_current()
        if v2:
            subprocess.run(['sh',str(ROOT/'packaging/session/fontreal-session'),'profile','k3'],env=env,check=True)
            launch('profile-k3',[hooks['command']],selected);quit_current()
            subprocess.run(['sh',str(ROOT/'packaging/session/fontreal-session'),'profile','o'],env=env,check=True)
        launch('absolute-stock-escape',['/usr/bin/flatpak','run',APPLICATION],native);quit_current()
        subprocess.run([*tool,'disable','bitwarden'],env=env,check=True);ownership()
        desktop=native.parent/'export/share/applications'/(APPLICATION+'.desktop')
        launch('restored-stock-desktop',['/usr/bin/gio','launch',desktop],native)
        final,_=shared.delivery.read_state();assert 'bitwarden' not in final['apps'];same_data();finished=True
        result=dict(passed=True,applicationBuild=str(application_record),build_sha256=sha(application_record),routes=observations,
                    originalDataDevice=identity[0],originalDataInode=identity[1],originalStartupUnchanged=True,
                    teamsEntryPreserved=True,normalQuitOnly=True,protectedProcessReads=False,leftRunningStock=True,deliveryDisabled=True)
        (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
    finally:
        try:
            if changed and not finished:
                if outer_instances(env):quit_current()
                current,_=shared.delivery.read_state()
                if 'bitwarden' in current['apps']:subprocess.run([*tool,'disable','bitwarden'],env=env,check=True)
                if not outer_instances(env):launch('failure-stock-return',['/usr/bin/flatpak','run',APPLICATION],native)
        finally:
            assert sha(marker)==digest;marker.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=['native-stock','readiness','exec-view'],required=True)
    parser.add_argument('--build-record',type=Path);parser.add_argument('--view',type=Path)
    parser.add_argument('--native-arguments',type=Path);parser.add_argument('--trace-address');parser.add_argument('--launch-hook',type=Path);args=parser.parse_args()
    if args.case=='exec-view':
        assert args.native_arguments is not None
        arguments=json.loads(args.native_arguments.read_text())
        assert arguments[0]=='run' and APPLICATION in arguments and all(isinstance(s,str) for s in arguments)
        if args.trace_address is not None:
            sender=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);sender.connect('\0'+args.trace_address)
            os.dup2(sender.fileno(),1);os.dup2(sender.fileno(),2);sender.close()
        fd=None
        if args.view is not None:
            options,fd=shared.delivery.view_options(args.view.resolve());os.set_inheritable(fd,True)
            arguments=['run',*options,*arguments[1:]]
        program=str(args.launch_hook) if args.launch_hook is not None else '/usr/bin/flatpak'
        try:os.execv(program,[program,*arguments])
        finally:
            if fd is not None:os.close(fd)
    if args.case=='readiness':assert args.build_record is not None
    output=(ROOT/'results/bitwarden-delivery').resolve();output.mkdir(parents=True,exist_ok=True)
    destination=Path(tempfile.mkdtemp(prefix=args.case+'-',dir=output));print(destination,flush=True)
    if args.case=='native-stock':native_stock(destination)
    else:readiness(args.build_record.resolve(),destination)


if __name__=='__main__':main()
