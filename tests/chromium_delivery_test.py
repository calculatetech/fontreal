#!/usr/bin/env python3
"""Qualify actual packaged Teams rendering and its ordinary delivery lifecycle."""
import argparse
import base64
import configparser
import errno
import fcntl
from contextlib import contextmanager
import importlib.util
import hashlib
import io
import json
import math
import mmap
import os
from pathlib import Path
import re
import select
import shlex
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from unittest.mock import patch
from PIL import Image

import browser_masks_test as masks
import chromium_flatpak_test as c1
import chromium_delivery as delivery
from selected_profile_test import expected_mask

ROOT=c1.ROOT
WORK=(ROOT/'build/chromium-delivery').resolve()
OUT=(ROOT/'results/chromium-delivery').resolve()
APPLICATION='com.github.IsmaelMartinez.teams_for_linux'
AUTOSTART_UNIT='app-'+APPLICATION+'@autostart.service'
CAPTURE_INVOCATIONS=[]


def capture_audit(event,arguments):
    if event=='subprocess.Popen' and arguments[0]=='/usr/bin/spectacle' and '-a' in arguments[1]:CAPTURE_INVOCATIONS.append(True)


sys.addaudithook(capture_audit)


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


class Inspector:
    def __init__(self,port,directory):
        self.port=port;self.directory=directory;self.sequence=0

    def evaluate(self,expression):
        self.sequence+=1;source=self.directory/(f'inspect-{self.sequence}.js');source.write_text(expression)
        result=subprocess.run(['node',str(ROOT/'tests/chromium_app_inspect.mjs'),str(self.port),str(source)],
                              text=True,capture_output=True,timeout=30,check=True)
        return json.loads(result.stdout)

    def quit(self):
        try:self.evaluate("setTimeout(()=>process.mainModule.require('electron').app.quit(),50);true")
        except (subprocess.SubprocessError,json.JSONDecodeError):pass


def comparison_tree(main_pid):
    pending=[main_pid];seen=set()
    while pending:
        pid=pending.pop()
        if pid in seen:continue
        seen.add(pid);process=Path('/proc')/str(pid)
        try:
            for task in (process/'task').iterdir():
                pending.extend(map(int,(task/'children').read_text().split()))
        except OSError:continue
    return seen


def comparison_processes(main_pid,engine):
    identity=engine.stat();result=[]
    for pid in comparison_tree(main_pid):
        try:
            executable=(Path('/proc')/str(pid)/'exe').stat()
            if (executable.st_dev,executable.st_ino)==(identity.st_dev,identity.st_ino):result.append(pid)
        except OSError:continue
    return result


@contextmanager
def comparison(view,destination,env,arguments=(),collector=None,native_options=(),expected_failure=None,signal_inspector=False):
    destination.mkdir(parents=True);state=Path(tempfile.mkdtemp(prefix='comparison-',dir=WORK));data=state/'data';data.mkdir()
    with socket.socket() as listener:
        if signal_inspector:listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        listener.bind(('127.0.0.1',9229 if signal_inspector else 0));port=listener.getsockname()[1]
    command=['/usr/bin/flatpak','run'];fd=None
    try:
        if view is not None:
            options,fd=delivery.view_options(view);command+=options
            stat=os.fstat(fd);chosen=Path(view).stat()
            assert (stat.st_dev,stat.st_ino)==(chosen.st_dev,chosen.st_ino)
            assert fcntl.fcntl(fd,fcntl.F_GETFL)&(os.O_PATH|os.O_NOFOLLOW|os.O_DIRECTORY)==(os.O_PATH|os.O_NOFOLLOW|os.O_DIRECTORY) and fcntl.fcntl(fd,fcntl.F_GETFD)&fcntl.FD_CLOEXEC
            write_json(destination/'host-alias-fd.json',dict(view=str(view),fd=fd,device=stat.st_dev,inode=stat.st_ino,
                       flags=fcntl.fcntl(fd,fcntl.F_GETFL),closeOnExec=True,options=options))
        command+=[*native_options,'--filesystem='+str(data),'--env=E2E_USER_DATA_DIR='+str(data),APPLICATION,
                  *([] if signal_inspector else ['--inspect=127.0.0.1:'+str(port)]),*arguments]
        write_json(destination/'command.json',command)
        # Application stderr can contain account data. Diagnostics retain only explicit bounded observations.
        env={key:value for key,value in env.items() if not key.startswith('FONTREAL_') and key not in
             ('LD_PRELOAD','LD_LIBRARY_PATH','FREETYPE_PROPERTIES','ELECTRON_RUN_AS_NODE','ELECTRON_NO_SANDBOX')}
        child=subprocess.Popen(command,env=env,stdout=subprocess.DEVNULL if collector is None else collector.sender,
                               stderr=subprocess.PIPE if collector is None else collector.sender,
                               pass_fds=(() if fd is None else (fd,)))
    finally:
        if fd is not None:
            os.close(fd)
            try:os.fstat(fd)
            except OSError as error:assert error.errno==errno.EBADF
            else:raise AssertionError('Host alias FD remained open after native handoff')
            write_json(destination/'host-alias-closed.json',dict(fd=fd,closedAfterNativePopen=True))
    diagnostics={};stop=threading.Event()
    def drain():
        markers={'node-inspector-listening':b'Debugger listening on',
                 'x-display-unavailable':b'Missing X server or $DISPLAY',
                 'wayland-display-unavailable':b'Failed to connect to Wayland display',
                 'native-library-unavailable':b'error while loading shared libraries:',
                 'portal-invocation-error':b'org.freedesktop.DBus.Error.',
                 'native-permission-denied':b'Permission denied',
                 'zypak-fork-preparing':b'Prepare for fork',
                 'zypak-fork-parent-resumed':b'Resume bus in parent',
                 'zypak-no-bus-at-fork':b'bus thread is not running, skipping fork override',
                 'zypak-spawn-request-ready':b'Ready to read spawn request',
                 'zypak-spawn-request-read':b'] Read spawn request',
                 'zypak-spawn-bus-reply':b'Got bus reply for ',
                 'zypak-spawn-bus-failed':b'Failed to call Spawn:',
                 'zypak-spawn-fulfilled':b'Initially spawned ',
                 'zypak-spawn-started':b'Marking as started:',
                 'zypak-spawn-exited':b'Marking as dead:',
                 'zypak-bus-failed':b'Failed to connect to session bus:',
                 'zypak-app-view-failed':b'Failed to retain the current application view',
                 'zypak-app-view-identity-failed':b'Failed to identify the application view',
                 'zypak-app-view-missing-or-relative':b'Missing or non-absolute application view',
                 'zypak-app-view-mismatched':b'Application view alias does not match /app',
                 'zypak-spawn-reply-failed':b'Failed to read u32 pid from Spawn reply',
                 'zypak-assertion-failed':b'Assertion failed:'}
        pending=b''
        while not stop.is_set():
            if not select.select([child.stderr.fileno()],[],[],.1)[0]:continue
            data=os.read(child.stderr.fileno(),65536)
            if not data:break
            pending+=data
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1)
                if line.startswith((b'bwrap: ',b'flatpak: ',b'/app/bin/zypak-helper: error while loading shared libraries: ')):
                    startup=diagnostics.setdefault('native-startup',[])
                    if len(startup)<32:startup.append(line[:512].decode('utf-8','replace'))
                    write_json(destination/'startup-stage-counts.json',diagnostics)
                match=re.fullmatch(rb'\[(\d+) preload-host-spawn-strategy\] (Initially spawned (\d+) as (\d+)|Marking as started: (\d+) (\d+)|Marking as dead: (\d+))',line)
                if match:
                    observations=diagnostics.setdefault('zypak-spawn-pids',[])
                    if len(observations)<32:observations.append([int(x) for x in match.groups()[2:] if x is not None])
                for key,marker in markers.items():
                    if marker in line:
                        diagnostics[key]=diagnostics.get(key,0)+1
                        write_json(destination/'startup-stage-counts.json',diagnostics)
            if len(pending)>65536:pending=b''
    reader=None
    if collector is None:reader=threading.Thread(target=drain,daemon=True);reader.start()
    inspector=Inspector(port,destination);inspector.launch_pid=child.pid;owned={}
    engine=(Path(view)/'teams-for-linux/teams-for-linux' if view is not None else
            Path(subprocess.check_output(['/usr/bin/flatpak','info','--show-location',APPLICATION],env=env,text=True).strip())/'files/teams-for-linux/teams-for-linux')
    def observe():
        for pid in comparison_processes(child.pid,engine):
            if pid not in owned:
                try:owned[pid]=os.pidfd_open(pid)
                except ProcessLookupError:pass
    failed=False;activation=None
    try:
        deadline=time.monotonic()+60
        while True:
            if collector is not None:collector.check()
            observe()
            if signal_inspector and activation is None:
                depth=len(process_status(child.pid)['namespacePids'])+1
                mains=[process_status(pid) for pid in comparison_processes(child.pid,engine)
                       if len(process_status(pid)['namespacePids'])==depth and process_status(pid)['namespacePids'][-1]==2]
                if mains and mains[0]['caughtSignals']&(1<<(signal.SIGUSR1-1)):
                    assert len(mains)==1,'Native inspector signal main mapping is ambiguous'
                    activation=activate_inspector(mains[0],engine,owned[mains[0]['hostPid']],destination)
                    write_json(destination/'native-inspector-activation.json',activation)
            if expected_failure and diagnostics.get(expected_failure):failed=True;break
            assert child.poll() is None,'Comparison application exited before its native inspector was ready'
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=1) as response:
                    if json.load(response):
                        ready=inspector.evaluate("(()=>{try{const a=process.mainModule.require('electron').app;return a.isReady()&&a.getPath('userData')==="+json.dumps(str(data))+";}catch{return false;}})()")
                        if ready:break
            except (OSError,urllib.error.URLError):pass
            assert time.monotonic()<deadline,'Native application inspector did not start'
            time.sleep(.1)
        if expected_failure:
            assert failed and not any(diagnostics.get(key) for key in ('node-inspector-listening','zypak-spawn-bus-reply','zypak-spawn-started')),'An invalid view reached native execution or the portal'
        if not failed:
            main=application_main(child.pid,engine.parent.parent,inspector.evaluate('({pid:process.pid})'))
            inspector.main_pid=main['hostPid']
        yield None if failed else inspector,child,data
    finally:
        try:
            observe()
            if not failed:
                inspector.quit()
                try:child.wait(timeout=20)
                except subprocess.TimeoutExpired:pass
            live={pid:fd for pid,fd in owned.items() if not select.select([fd],[],[],0)[0]}
            for fd in live.values():signal.pidfd_send_signal(fd,signal.SIGTERM)
            if live:diagnostics['terminated-private-comparison-pids']=list(live)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=10)
            deadline=time.monotonic()+5
            while any(not select.select([fd],[],[],0)[0] for fd in owned.values()) and time.monotonic()<deadline:time.sleep(.1)
            assert all(select.select([fd],[],[],0)[0] for fd in owned.values()),'Private comparison process did not stop after SIGTERM'
        finally:
            for fd in owned.values():os.close(fd)
            stop.set()
            if reader is not None:
                reader.join(timeout=5);assert not reader.is_alive();child.stderr.close()
            write_json(destination/'startup-diagnostics.json',dict(markers=diagnostics,exit_code=child.returncode))


IDENTITY="""(()=>{const e=process.mainModule.require('electron');return {pid:process.pid,execPath:process.execPath,
versions:{electron:process.versions.electron,chrome:process.versions.chrome,modules:process.versions.modules},
name:e.app.getName(),data:e.app.getPath('userData'),appPath:e.app.getAppPath(),
windows:e.BrowserWindow.getAllWindows().map(w=>({id:w.id,bounds:w.getBounds(),contentBounds:w.getContentBounds(),
rendererPid:w.webContents.getOSProcessId()})),contents:e.webContents.getAllWebContents().map(c=>({id:c.id,type:c.getType(),rendererPid:c.getOSProcessId(),preferences:(()=>{const p=c.getLastWebPreferences();return {sandbox:p.sandbox,contextIsolation:p.contextIsolation,nodeIntegration:p.nodeIntegration};})()}))};})()"""


def process_status(pid,identify_executable=True):
    root=Path('/proc')/str(pid)
    fields=dict(line.split(':',1) for line in (root/'status').read_text().splitlines() if ':' in line)
    executable=(root/'exe').stat() if identify_executable else None
    namespace_pids=list(map(int,fields['NSpid'].split()));assert namespace_pids[0]==pid and all(value>0 for value in namespace_pids)
    return dict(hostPid=pid,name=fields['Name'].strip(),parentPid=int(fields['PPid']),
                namespacePids=namespace_pids,pidNamespace=os.readlink(root/'ns/pid'),
                startTicks=int((root/'stat').read_text().rsplit(')',1)[1].split()[19]),
                executable=[executable.st_dev,executable.st_ino] if executable else None,
                seccomp=int(fields['Seccomp']),noNewPrivs=int(fields['NoNewPrivs']),caughtSignals=int(fields['SigCgt'],16),
                capabilities={name:int(fields[name],16) for name in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')})


def inspector_port_available(port=9229):
    with socket.socket() as available:
        # Match pinned Node/libuv: SO_REUSEADDR permits TIME_WAIT, never a live listener.
        available.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        available.bind(('127.0.0.1',port));available.listen(511)


def inspector_port_selfcheck(destination):
    destination.mkdir();listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0));port=listener.getsockname()[1];listener.listen(1)
    try:
        try:inspector_port_available(port)
        except OSError as error:assert error.errno==98
        else:raise AssertionError('Native-option probe accepted a live listener')
        with socket.create_connection(('127.0.0.1',port)) as client:
            accepted,_=listener.accept();accepted.shutdown(socket.SHUT_WR);assert client.recv(1)==b''
        assert accepted.recv(1)==b'';accepted.close()
    finally:listener.close()
    with socket.socket() as old:
        try:old.bind(('127.0.0.1',port))
        except OSError as error:assert error.errno==98
        else:raise AssertionError('Synthetic TCP connection did not establish the old-probe TIME_WAIT contrast')
    inspector_port_available(port)
    source=ROOT/'build/chromium-flatpak/electron-44.9.0/src/third_party/electron_node'
    result=dict(passed=True,synthetic=True,port=port,liveListenerRefused=True,oldProbeRejectedTimeWait=True,
                nativeProbeAcceptedTimeWait=True,reusePort=False,
                native_sources={str(p):c1.target.sha(p) for p in (source/'src/inspector_socket_server.cc',source/'deps/uv/src/unix/tcp.c')})
    write_json(destination/'result.json',result);return result


def activate_inspector(main,engine,pidfd,destination):
    assert main['caughtSignals']&(1<<(signal.SIGUSR1-1)),'Native main has no registered debug-signal handler'
    stat=engine.stat();assert main['executable']==[stat.st_dev,stat.st_ino]
    with engine.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as binary:
        signature=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX';at=binary.find(signature)+len(signature)
        assert at>=len(signature) and binary[at]==1 and binary[at+1]>=4 and binary[at+5]==ord('1'),'Original inspector fuse is disabled'
        wire=bytes(binary[at+2:at+2+binary[at+1]]).decode()
    current=process_status(main['hostPid'])
    write_json(destination/'signal-main-snapshots.json',dict(before=main,current=current))
    assert not select.select([pidfd],[],[],0)[0]
    assert {key:value for key,value in current.items() if key!='caughtSignals'}=={key:value for key,value in main.items() if key!='caughtSignals'},'Native main identity changed before inspector activation'
    assert current['caughtSignals']&(1<<(signal.SIGUSR1-1)),'Native debug-signal handler disappeared'
    inspector_port_available()
    signal.pidfd_send_signal(pidfd,signal.SIGUSR1)
    return dict(main=main,engine=str(engine),engine_sha256=c1.target.sha(engine),originalFuseWire=wire,
                signal='SIGUSR1',port=9229,registeredHandler=True)


def fd_info(pid,fd):
    lines=(Path('/proc')/str(pid)/'fdinfo'/str(fd)).read_text().splitlines();values={}
    for line in lines:
        key,separator,value=line.partition(':')
        if key not in ('mnt_id','ino','flags'):continue
        assert separator and key not in values,'Ambiguous native descriptor metadata'
        values[key]=value.strip()
    assert set(values)=={'mnt_id','ino','flags'},'Missing native descriptor identity'
    assert re.fullmatch(r'[0-7]+',values['flags']) and all(re.fullmatch(r'[0-9]+',values[key]) for key in ('mnt_id','ino'))
    flags=int(values['flags'],8);identity=[int(values['mnt_id']),int(values['ino'])]
    assert all(value>0 for value in identity)
    return dict(object=identity,access=flags&os.O_ACCMODE,flags=flags)


def stdio_links(pid):
    result={}
    for fd in (0,1,2):
        root=Path('/proc')/str(pid);link=os.readlink(root/'fd'/str(fd))
        # Retain only the pipe/socket identities needed by this observer.
        if not link.startswith(('pipe:[','socket:[')):link='other'
        info=fd_info(pid,fd)
        if link!='other':assert int(link.split('[',1)[1][:-1])==info['object'][1],'Descriptor object changed during observation'
        result[str(fd)]=dict(link=link,**info)
    return result


def application_main(launch_pid,view,identity):
    engine=Path(view)/'teams-for-linux/teams-for-linux'
    main_depth=len(process_status(launch_pid)['namespacePids'])+1
    mains=[process_status(pid) for pid in comparison_processes(launch_pid,engine)]
    # Portal children can also report inner PID2, at a deeper namespace level.
    mains=[row for row in mains if len(row['namespacePids'])==main_depth and row['namespacePids'][-1]==identity['pid']]
    assert len(mains)==1,'Actual application main-process mapping is ambiguous'
    return mains[0]


def trace_graph(collector,launch_pid,view,identity,renderer_pid):
    engine=Path(view)/'teams-for-linux/teams-for-linux';stat=engine.stat();engine_id=[stat.st_dev,stat.st_ino]
    main=application_main(launch_pid,view,identity);parent_index=len(main['namespacePids'])-1
    owned=comparison_tree(launch_pid);cats={};mapping=[]
    for pid in owned:
        try:
            fields=dict(line.split(':',1) for line in (Path('/proc')/str(pid)/'status').read_text().splitlines() if ':' in line)
        except FileNotFoundError:continue
        pids=list(map(int,fields['NSpid'].split()));assert pids and pids[0]==pid and all(n>0 for n in pids)
        mapping.append(dict(hostPid=pid,parentPid=int(fields['PPid']),name=fields['Name'].strip(),namespacePids=pids))
    target=[row for row in mapping if len(row['namespacePids'])>parent_index and row['namespacePids'][parent_index]==renderer_pid]
    assert len(target)==1,'Observed main-relative content PID has no unique owned kernel mapping'
    trace_pid=target[0]['namespacePids'][-1]
    for row in mapping:row['traceCandidate']=row['namespacePids'][-1]==trace_pid
    native_cat=(Path('/proc')/str(main['hostPid'])/'root/usr/bin/cat').stat()
    for pid in owned:
        try:
            if not re.search(r'^Name:\s*cat$',(Path('/proc')/str(pid)/'status').read_text(),re.M):continue
            row=process_status(pid)
            assert row['pidNamespace']==main['pidNamespace'] and row['executable']==[native_cat.st_dev,native_cat.st_ino]
            cats[pid]=dict(process=row,stdio=stdio_links(pid))
        except FileNotFoundError:continue
    socket_link=os.readlink(Path('/proc/self/fd')/str(collector.sender.fileno()))
    socket_object=fd_info(os.getpid(),collector.sender.fileno())['object']
    candidates=[]
    for candidate in mapping:
        if not candidate['traceCandidate']:
            candidate['exclusion']='kernel getpid differs from frozen trace payload identity';continue
        row=process_status(candidate['hostPid']);row['stderr']=fd_info(row['hostPid'],2);candidates.append(row)
    matches=[]
    for stdout_pid,stdout_cat in cats.items():
        first=stdout_cat['stdio']
        if first['1']['link']!=socket_link or first['1']['object']!=socket_object or not first['0']['link'].startswith('pipe:['):continue
        for stderr_pid,stderr_cat in cats.items():
            second=stderr_cat['stdio']
            if second['1']['link']!=first['0']['link'] or second['1']['object']!=first['0']['object'] or not second['0']['link'].startswith('pipe:['):continue
            assert first['0']['access']==second['0']['access']==os.O_RDONLY and second['1']['access']==os.O_WRONLY
            writers=[row for row in candidates if row['stderr']['object']==second['0']['object']]
            if not writers:continue
            renderers=[row for row in writers if len(row['namespacePids'])>parent_index and row['namespacePids'][parent_index]==renderer_pid]
            if not renderers:continue
            assert len(renderers)==1 and len({row['pidNamespace'] for row in writers})==1,'Native trace pipe spans ambiguous renderer namespaces'
            renderer=renderers[0];actual=process_status(renderer['hostPid'])
            assert actual['executable']==engine_id,'Actual content renderer uses a different engine'
            renderer.update(executable=actual['executable']);trace_pid=renderer['namespacePids'][-1]
            assert sum(row['namespacePids'][-1]==trace_pid for row in writers)==1,'Native trace PID is ambiguous within its owned pipe'
            assert renderer['stderr']['access']==os.O_WRONLY
            assert renderer['seccomp']==2 and renderer['noNewPrivs']==1
            assert all(renderer['capabilities'][name]==0 for name in ('CapInh','CapPrm','CapEff','CapAmb'))
            matches.append(dict(main=main,renderer=renderer,observedRendererPid=renderer_pid,
                                tracePid=trace_pid,credentialSenderPid=stdout_pid,stdoutCat=stdout_cat,
                                stderrCat=stderr_cat,matchingTraceWriters=writers,possibleTraceSenders=candidates,ownedPidMapping=mapping,collectorSocket=socket_link))
    assert len(matches)==1,'No unique live renderer-to-cat-to-cat-to-collector graph'
    return matches[0]


def graph_rows(collector,graph):
    collector.check()
    return [row['payload'] for row in list(collector.rows)
            if row['hostPid']==graph['credentialSenderPid'] and row['payload']['pid']==graph['tracePid']]


def privacy_selfcheck(destination):
    destination.mkdir();sentinel='SYNTHETIC_PRIVATE_NONTRACE_'+os.urandom(16).hex()
    payload=dict(pid=1,synthetic=True,source='C3 trace-only retention primitive')
    line=('FONTREAL_SKIA '+json.dumps(payload)+'\n').encode();ready_read,ready_write=os.pipe2(os.O_CLOEXEC)
    script="""import os,sys
sentinel,payload,ready=sys.argv[1].encode(),sys.argv[2].encode(),int(sys.argv[3])
os.write(1,sentinel+b'\\n');split=len(payload)//2;os.write(2,payload[:split])
os.write(ready,b'ready');os.close(ready)
assert sys.stdin.buffer.readline()==b'go\\n'
os.write(2,payload[split:])
"""
    with c1.StderrCollector(destination,trace_only=True) as collector:
        child=subprocess.Popen([sys.executable,'-c',script,sentinel,line.decode(),str(ready_write)],
                               stdin=subprocess.PIPE,stdout=collector.sender,stderr=collector.sender,
                               pass_fds=(ready_write,),env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(WORK)))
        os.close(ready_write)
        try:
            assert select.select([ready_read],[],[],5)[0] and os.read(ready_read,5)==b'ready','Privacy primitive did not fragment its trace'
            child.stdin.write(b'go\n');child.stdin.flush();assert child.wait(timeout=10)==0
        finally:
            os.close(ready_read);child.stdin.close()
            if child.poll() is None:child.terminate();child.wait(timeout=5)
    raw=(destination/'stderr.log').read_bytes();index=(destination/'stderr-credentials.jsonl').read_bytes()
    assert raw==line and sentinel.encode() not in raw+index,'Nontrace application output was retained'
    assert collector.rows==[dict(hostPid=child.pid,payload=payload)],'Fragmented synthetic trace lost its kernel sender'
    saved=[json.loads(row) for row in index.splitlines()]
    assert len(saved)==1 and saved[0]['hostPid']==child.pid and saved[0]['length']==len(line) and saved[0]['retainedTraceLine']
    result=dict(passed=True,synthetic=True,knownChildPid=child.pid,fragmentedTrace=True,nontraceExcluded=True)
    write_json(destination/'selfcheck.json',result);return result


MAIN_WINDOW="""(()=>{const m=Object.values(process.mainModule.require('module')._cache)
.find(m=>m.filename.endsWith('/app/mainAppWindow/index.js'))?.exports;return !!m?.getWindow()&&!!m.getTray();})()"""


def dbus(*arguments):
    result=subprocess.run(['busctl','--user','--json=short','--',*arguments],text=True,capture_output=True,check=True,timeout=10)
    return json.loads(result.stdout)['data'] if result.stdout.strip() else None


def instance_identity(pid):
    info=configparser.ConfigParser(interpolation=None);info.read_string((Path('/proc')/str(pid)/'root/.flatpak-info').read_text())
    return dict(application=info['Application']['name'],instance=info['Instance']['instance-id'],appPath=info['Instance']['app-path'])


def native_menu_action(main_pid,label,destination):
    assert label in ('Join Meeting','Quit');deadline=time.monotonic()+15
    proxy=Path('/usr/bin/xdg-dbus-proxy').stat();expected=[proxy.st_dev,proxy.st_ino]
    main=process_status(main_pid);instance=instance_identity(main_pid);assert instance['application']==APPLICATION
    while True:
        matches=[]
        items=dbus('get-property','org.kde.StatusNotifierWatcher','/StatusNotifierWatcher','org.kde.StatusNotifierWatcher','RegisteredStatusNotifierItems')
        for item in items:
            service,path=item.split('/',1)
            pid=dbus('call','org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s',service)[0]
            executable=(Path('/proc')/str(pid)/'exe').stat()
            if [executable.st_dev,executable.st_ino]!=expected:continue
            if instance_identity(pid)!=instance:continue
            principal=process_status(pid)
            menu=dbus('get-property',service,'/'+path,'org.kde.StatusNotifierItem','Menu')
            layout=dbus('call',service,menu,'com.canonical.dbusmenu','GetLayout','iias','0','1','2','label','enabled')
            def walk(value):
                if isinstance(value,list):
                    if len(value)==3 and isinstance(value[0],int) and isinstance(value[1],dict):
                        properties=value[1]
                        if properties.get('label',{}).get('data')==label and properties.get('enabled',{'data':True})['data']:
                            matches.append(dict(service=service,menu=menu,item=value[0],label=label,credential=principal,instance=instance,main=main))
                    for child in value:walk(child)
                elif isinstance(value,dict):
                    for child in value.values():walk(child)
            walk(layout)
        if matches:break
        assert time.monotonic()<deadline,'The owned original native menu action is not registered'
        time.sleep(.1)
    assert len(matches)==1,'The original native menu action is ambiguous'
    chosen=matches[0];pid=chosen['credential']['hostPid'];pidfd=os.pidfd_open(pid)
    try:
        assert not select.select([pidfd],[],[],0)[0] and process_status(pid)==chosen['credential']
        assert instance_identity(pid)==instance_identity(main_pid)==instance
        assert dbus('call','org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s',chosen['service'])[0]==pid
        dbus('call',chosen['service'],chosen['menu'],'com.canonical.dbusmenu','Event','isvu',str(chosen['item']),'clicked','s','','0')
        if label!='Quit':
            assert not select.select([pidfd],[],[],0)[0] and process_status(pid)==chosen['credential']
            assert instance_identity(pid)==instance_identity(main_pid)==instance
    finally:os.close(pidfd)
    write_json(destination/('native-'+label.replace(' ','-').lower()+'.json'),chosen);return chosen


def open_dialog(inspector,compositor_env=None):
    deadline=time.monotonic()+30
    while not inspector.evaluate(MAIN_WINDOW):
        assert time.monotonic()<deadline,'Actual main window did not initialize'
        time.sleep(.1)
    inspector.evaluate("(()=>{const m=Object.values(process.mainModule.require('module')._cache).find(m=>m.filename.endsWith('/app/mainAppWindow/index.js')).exports;const w=m.getWindow();w.show();w.focus();return true;})()")
    if compositor_env is not None:
        activated=dialog_geometry(inspector.main_pid,None,inspector.directory,compositor_env,activate=True)
        write_json(inspector.directory/'native-main-activation.json',activated)
    while not inspector.evaluate("Object.values(process.mainModule.require('module')._cache).find(m=>m.filename.endsWith('/app/mainAppWindow/index.js')).exports.getWindow().isFocused()"):
        assert time.monotonic()<deadline,'The ordinary main window did not receive focus'
        time.sleep(.1)
    native_menu_action(inspector.main_pid,'Join Meeting',inspector.directory)
    deadline=time.monotonic()+30
    while True:
        result=inspector.evaluate("""(async()=>{const e=process.mainModule.require('electron');
        const c=e.webContents.getAllWebContents().find(c=>c.getURL().split(/[?#]/)[0]==='file://'+e.app.getAppPath()+'/app/joinMeetingDialog/joinMeeting.html');
        if(!c)return {waiting:'native-action'};if(c.isLoadingMainFrame())return {waiting:'local-resource'};
        const w=e.BrowserWindow.fromWebContents(c);w.show();w.focus();
        const ready=await c.executeJavaScript("({input:!!document.getElementById('url-input'),disabled:document.getElementById('join-btn')?.disabled,regexType:typeof compiledRegex,regexReady:typeof compiledRegex!=='undefined'&&compiledRegex instanceof RegExp})");
        if(!ready.input||!(ready.disabled||ready.regexReady))return {waiting:'native-init',...ready,visible:w.isVisible(),readyHandlers:w.listenerCount('ready-to-show')};
        await c.executeJavaScript("(()=>{const t=document.getElementById('url-input');t.value='';t.dispatchEvent(new Event('input',{bubbles:true}));t.blur();return true;})()");
        return {contentsId:c.id,windowId:w.id,rendererPid:c.getOSProcessId()};})()""")
        if result.get('contentsId'):return result
        write_json(inspector.directory/'native-dialog-readiness.json',result)
        assert time.monotonic()<deadline,'The original native Join Meeting action did not initialize the local dialog'
        time.sleep(.1)


def dialog_stage(inspector,dialog,text,repaint=False):
    assert text in ('','W','WW','WWg')
    return inspector.evaluate("""(async()=>{const e=process.mainModule.require('electron');
    const c=e.webContents.fromId("""+str(dialog['contentsId'])+"""),w=e.BrowserWindow.fromWebContents(c);
    if(c.getURL().split(/[?#]/)[0]!=='file://'+e.app.getAppPath()+'/app/joinMeetingDialog/joinMeeting.html')throw Error('Unexpected local resource');
    const requested="""+json.dumps(text)+""";
    await c.executeJavaScript(`(()=>{const t=document.getElementById('url-input');t.focus();t.select();return true;})()`);
    if(requested)await c.insertText(requested);
    else await c.executeJavaScript("(()=>{const t=document.getElementById('url-input');t.value='';t.dispatchEvent(new Event('input',{bubbles:true}));return true;})()");
    await c.executeJavaScript("document.getElementById('url-input').blur();true");
    await c.executeJavaScript(`(async()=>{const t=document.getElementById('url-input');t.blur();
    if(t.classList.contains('invalid')!==Boolean(${JSON.stringify(requested)})||!document.getElementById('join-btn').disabled)
      throw Error('Original local validation is not ready');
    await Promise.race([Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{}))),
      new Promise((_,reject)=>setTimeout(()=>reject(Error('Native animation did not finish')),5000))]);
    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
    if(document.getAnimations().some(a=>a.playState==='running'))throw Error('Native animation is still running');return true;})()`);
    if("""+json.dumps(repaint)+"""){c.invalidate();await c.executeJavaScript("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))");}
    const measure=await c.executeJavaScript(`(()=>{const t=document.getElementById('url-input'),s=getComputedStyle(t),r=t.getBoundingClientRect();
    if(t.value!==${JSON.stringify(requested)})throw Error('Unexpected local test text');
    return {font:s.font,fontFamily:s.fontFamily,fontSize:s.fontSize,fontWeight:s.fontWeight,color:s.color,
    background:s.backgroundColor,borderColor:s.borderTopColor,lineHeight:s.lineHeight,padding:s.padding,border:s.borderWidth,
    bodyBackground:getComputedStyle(document.body).backgroundColor,bodyOpacity:getComputedStyle(document.body).opacity,
    borderRadius:s.borderRadius,borderStyle:s.borderStyle,boxShadow:s.boxShadow,opacity:s.opacity,filter:s.filter,
    backdropFilter:s.backdropFilter,transform:s.transform,appearance:s.appearance,backgroundClip:s.backgroundClip,
    documentFocused:document.hasFocus(),inputFocused:t.matches(':focus'),inputHovered:t.matches(':hover'),
    direction:s.direction,textAlign:s.textAlign,textIndent:s.textIndent,letterSpacing:s.letterSpacing,wordSpacing:s.wordSpacing,
    fontKerning:s.fontKerning,fontStretch:s.fontStretch,fontVariantCaps:s.fontVariantCaps,textRendering:s.textRendering,language:document.documentElement.lang,
    inputBlurred:document.activeElement!==t,invalid:t.classList.contains('invalid'),joinDisabled:document.getElementById('join-btn').disabled,
    animationsRunning:document.getAnimations().some(a=>a.playState==='running'),
    rectangle:{x:r.x,y:r.y,width:r.width,height:r.height},viewport:[innerWidth,innerHeight],devicePixelRatio};})()`);
    c.debugger.attach('1.3');let fonts;
    try{await c.debugger.sendCommand('DOM.enable');await c.debugger.sendCommand('CSS.enable');
    const doc=await c.debugger.sendCommand('DOM.getDocument');
    const node=await c.debugger.sendCommand('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#url-input'});
    fonts=await c.debugger.sendCommand('CSS.getPlatformFontsForNode',{nodeId:node.nodeId});}
    finally{c.debugger.detach();}
    const p=c.getLastWebPreferences();return {text:requested,measure,fonts:fonts.fonts,contentBounds:w.getContentBounds(),title:w.getTitle(),
    focused:w.isFocused(),visible:w.isVisible(),rendererPid:c.getOSProcessId(),
    preferences:{sandbox:p.sandbox,contextIsolation:p.contextIsolation,nodeIntegration:p.nodeIntegration}};})()""")


def provider_oracle(record,destination,env):
    destination.mkdir()
    assert c1.target.sha(Path(record['probe']['executable']))==record['probe']['sha256']
    assert c1.target.sha(ROOT/'tests/chromium_selected_probe.cpp')==record['probe']['source_sha256']
    command=['/usr/bin/flatpak','run','--command=fc-match',APPLICATION,'-f','%{family}\n%{postscriptname}\n%{file}\n','Arial:style=Regular']
    matched=subprocess.run(command,env=env,text=True,capture_output=True,check=True)
    family,postscript,path=matched.stdout.strip().splitlines()
    assert family=='Arial' and postscript=='ArialMT' and path.startswith('/run/host/fonts/'),'Actual native font selection is not the identified Arial input'
    font=Path('/usr/share/fonts')/path.removeprefix('/run/host/fonts/')
    command=[record['probe']['executable'],str(font),'14','32','126','2','0','1','0','0','1','-1']
    write_json(destination/'command.json',command)
    with (destination/'provider.json').open('w') as stdout,(destination/'stderr.log').open('w') as stderr:
        subprocess.run(command,stdout=stdout,stderr=stderr,env=env,check=True)
    rows=json.loads((destination/'provider.json').read_text());assert len(rows)==95
    ids=c1.glyph_ids(font,'Wg');oracles={chr(row['char']):row for row in rows}
    for char in 'Wg':
        row=oracles[char];assert row['glyph']==ids[char] and row['size']==14 and row['width'] and row['height']
        raw=bytes.fromhex(row['mask']);assert len(raw)==row['width']*row['height'] and any(raw)
        assert expected_mask(raw,row['width'])!=raw,'The actual glyph does not distinguish selected processing'
    identity=dict(font=str(font),font_sha256=c1.target.sha(font),family=family,postscript=postscript,
                  nativeFontPath=path,probe=record['probe'],cmap=ids)
    write_json(destination/'identity.json',identity);return oracles,identity


def dialog_geometry(main_pid,title,destination,env,activate=False):
    name='fontreal-dialog-'+str(time.monotonic_ns());source=destination/(name+'.js')
    if activate:
        assert title is None
        source.write_text('const owned=workspace.windowList().filter(w=>w.pid=='+str(main_pid)+'&&w.normalWindow);const rows=[];'
                          'if(owned.length===1){const w=owned[0];w.minimized=false;workspace.activeWindow=w;'
                          'rows.push({id:String(w.internalId),pid:w.pid,active:w.active});}'
                          'console.warn('+json.dumps(name+' ')+ '+JSON.stringify(rows));')
    else:
        source.write_text('const rows=[];for(const w of workspace.windowList())if(w.pid=='+str(main_pid)+'&&w.caption=='+json.dumps(title)+')'
                          '{const a=w.clientGeometry,b=w.frameGeometry;rows.push({id:String(w.internalId),pid:w.pid,caption:w.caption,active:w.active,'
                          'client:[a.x,a.y,a.width,a.height],frame:[b.x,b.y,b.width,b.height]});}console.warn('+json.dumps(name+' ')+ '+JSON.stringify(rows));')
    kwin_pid=subprocess.check_output(['qdbus6','org.freedesktop.DBus','/org/freedesktop/DBus',
                                    'org.freedesktop.DBus.GetConnectionUnixProcessID','org.kde.KWin'],env=env,text=True).strip()
    assert kwin_pid.isdecimal()
    loaded=subprocess.check_output(['qdbus6','org.kde.KWin','/Scripting','org.kde.kwin.Scripting.loadScript',str(source),name],env=env,text=True).strip()
    assert loaded.isdecimal()
    try:
        since='@'+str(time.time()-2)
        subprocess.run(['qdbus6','org.kde.KWin','/Scripting/Script'+loaded,'org.kde.kwin.Script.run'],env=env,check=True,capture_output=True)
        for _ in range(50):
            result=subprocess.run(['journalctl','--user','_PID='+kwin_pid,'--since',since,'--no-pager','-o','json'],env=env,text=True,capture_output=True,check=True)
            messages=[json.loads(line).get('MESSAGE','') for line in result.stdout.splitlines()]
            matches=[message.split(name+' ',1)[1] for message in messages if name+' ' in message]
            if matches:break
            time.sleep(.05)
        assert len(matches)==1,'No unique native compositor geometry observation'
        rows=json.loads(matches[0]);assert len(rows)==1 and rows[0]['active'],'The actual generic dialog is not the owned active window'
        return rows[0]
    finally:
        subprocess.run(['qdbus6','org.kde.KWin','/Scripting','org.kde.kwin.Scripting.unloadScript',name],env=env,check=True,capture_output=True)


def spectacle_capture(main_pid,title,expected,destination,env):
    before=dialog_geometry(main_pid,title,destination,env)
    if before!=expected:raise ValueError('Expected generic compositor window does not match the active owned dialog')
    original=dict(env)
    assert original.get('XDG_SESSION_TYPE')=='wayland' and original.get('WAYLAND_DISPLAY')
    assert original.get('QT_QPA_PLATFORM','wayland').split(';')[0].startswith('wayland'),'Capture environment contains a probe backend override'
    actor=Path('/usr/bin/spectacle');desktop=Path('/usr/share/applications/org.kde.spectacle.desktop')
    permissions=configparser.ConfigParser(interpolation=None);permissions.optionxform=str;permissions.read(desktop)
    assert permissions['Desktop Entry']['Exec'].split()[0]==str(actor)
    assert 'org.kde.KWin.ScreenShot2' in permissions['Desktop Entry']['X-KDE-DBUS-Restricted-Interfaces'].split(';')
    private_root=None
    try:
        with tempfile.TemporaryDirectory(prefix='spectacle-',dir=WORK) as temporary:
            private_root=Path(temporary);capture_env={key:value for key,value in original.items()
                if not key.startswith('FONTREAL_') and key not in ('LD_PRELOAD','LD_LIBRARY_PATH','FREETYPE_PROPERTIES')}
            private={}
            for name,folder in (('XDG_CONFIG_HOME','config'),('XDG_CONFIG_DIRS','config-dirs'),('XDG_DATA_HOME','data'),
                                ('XDG_STATE_HOME','state'),('XDG_CACHE_HOME','cache'),('TMPDIR','tmp')):
                path=private_root/folder;path.mkdir(mode=0o700);capture_env[name]=str(path);private[name]=str(path)
            assert capture_env.get('HOME')==original.get('HOME')
            config=private_root/'config/spectaclerc';config.write_text('[General]\nclipboardGroup=PostScreenshotDoNothing\n')
            effective=subprocess.check_output(['kreadconfig6','--file','spectaclerc','--group','General','--key','clipboardGroup'],env=capture_env,text=True).strip()
            assert effective=='PostScreenshotDoNothing','Effective Spectacle configuration can copy to the clipboard'
            output=private_root/'tmp/dialog.png'
            command=[str(actor),'-a','-e','-S','-b','-n','-i','-o',str(output)]
            version=subprocess.run([str(actor),'--version'],env=capture_env,text=True,capture_output=True,check=True,timeout=15).stdout.strip()
            child=subprocess.Popen(command,env=capture_env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,umask=0o077)
            try:stdout,stderr=child.communicate(timeout=25)
            except subprocess.TimeoutExpired:
                child.terminate();child.communicate(timeout=5);raise
            assert child.returncode==0,'Native Spectacle actor failed'
            after=dialog_geometry(main_pid,title,destination,env)
            assert after==before,'The owned active window changed during the undisturbed capture interval'
            with Image.open(output) as frame:
                assert frame.size==(before['client'][2],before['client'][3]),'Native compositor capture geometry differs from the owned dialog'
                image=frame.copy()
            result=dict(command=command,actor=str(actor),actor_sha256=c1.target.sha(actor),version=version,
                        permission_desktop=str(desktop),permission_sha256=c1.target.sha(desktop),before=before,after=after,
                        private_environment=private,effectiveClipboardGroup=effective,exit_code=child.returncode,
                        native_environment={name:original.get(name) for name in ('DISPLAY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','QT_QPA_PLATFORM')})
        assert not private_root.exists(),'Spectacle private state was not removed'
        result['privateStateRemoved']=True
        return image,result
    finally:
        if private_root is not None:assert not private_root.exists(),'Spectacle private state survived capture cleanup'


def native_controls_equal(first,second):
    assert first.size==second.size==(460,38)
    return all(first.crop(box).tobytes()==second.crop(box).tobytes()
               for box in ((0,0,460,5),(0,33,460,38),(0,5,5,33),(455,5,460,33)))


def capture_dialog(inspector,dialog,state,main_pid,destination,stage,env,expected_window,control_reference=None):
    measure=state['measure'];rect=measure['rectangle']
    assert measure['devicePixelRatio']==1 and measure['viewport']==[500,250]
    assert rect==dict(x=20,y=87,width=460,height=38),'The packaged generic control geometry changed'
    assert state['visible'] and state['focused'] and measure['fontSize']=='14px' and measure['fontWeight']=='400'
    assert all(row['postScriptName']=='ArialMT' for row in state['fonts']) and state['fonts']
    assert state['preferences']==dict(sandbox=True,contextIsolation=True,nodeIntegration=False)
    before=dialog_geometry(main_pid,state['title'],destination,env)
    if before!=expected_window:raise ValueError('Expected generic compositor window does not match the active owned dialog')
    reference=None
    if control_reference is not None:
        with Image.open(control_reference/(stage+'-native.png')) as image:reference=image.convert('RGB')
    deadline=time.monotonic()+15;attempts=0
    while True:
        attempts+=1
        png=inspector.evaluate("""(async()=>{const c=process.mainModule.require('electron').webContents.fromId("""+str(dialog['contentsId'])+");return (await c.capturePage("+json.dumps(rect)+")).toPNG().toString('base64');})()")
        native=base64.b64decode(png,validate=True)
        with Image.open(io.BytesIO(native)) as image:
            assert image.size==(460,38);native_rgb=image.convert('RGB')
        (destination/(stage+'-native.png')).write_bytes(native)
        if reference is None or native_controls_equal(native_rgb,reference):break
        assert time.monotonic()<deadline,'Native source controls did not reach the exact source-stock painted state'
        time.sleep(.05)
    geometry=before;x,y,width,height=geometry['client']
    write_json(destination/(stage+'-geometry.json'),geometry)
    assert [width,height]==measure['viewport'],'Native client geometry does not match the actual local document'
    background=tuple(map(int,re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)',measure['background']).groups()))
    controls=[(8,4,452,8),(8,30,452,34),(430,9,450,29)]
    frame,capture=spectacle_capture(main_pid,state['title'],expected_window,destination,env)
    image=frame.crop((rect['x'],rect['y'],rect['x']+rect['width'],rect['y']+rect['height']))
    if image.mode=='RGBA':assert image.getchannel('A').getextrema()==(255,255),'Actual input control is not opaque'
    image=image.convert('RGB');assert image.size==(460,38)
    image.save(destination/(stage+'-window.png'))
    if control_reference is not None:
        with Image.open(control_reference/(stage+'-window.png')) as stock:
            assert native_controls_equal(image,stock),'Actual OS border controls differ from the source-stock stage'
    assert all(image.crop(box).tobytes()==bytes(background)*((box[2]-box[0])*(box[3]-box[1])) for box in controls),'Native compositor capture did not contain the actual generic input controls'
    if state['text']:assert image.crop((10,9,85,29)).tobytes()!=bytes(background)*(75*20),'Actual compositor text did not paint'
    image.save(destination/(stage+'-window.png'));write_json(destination/(stage+'-actor.json'),capture)
    return dict(geometry=geometry,rectangle=rect,background=background,controls=controls,
                os_sha256=c1.target.sha(destination/(stage+'-window.png')),native_sha256=c1.target.sha(destination/(stage+'-native.png')),
                controlReadiness=dict(attempts=attempts,reference=str(control_reference) if control_reference else None,exact=True))


def view_transport(record,destination,env):
    destination.mkdir();view=Path(record['views']['normal']['directory']);debug=dict(env,ZYPAK_DEBUG='1');results={}
    with comparison(view,destination/'valid',debug,native_options=['--cwd=/']) as (inspector,child,data):
        identity=inspector.evaluate(IDENTITY);assert identity['data']==str(data)
        results['valid']=identity
    for name,options,marker in (
        ('absent',['--unset-env=FONTREAL_ZYPAK_APP_PATH'],'zypak-app-view-missing-or-relative'),
        ('mismatched',['--env=FONTREAL_ZYPAK_APP_PATH=/usr'],'zypak-app-view-mismatched'),
        ('relative',['--env=FONTREAL_ZYPAK_APP_PATH='+str(view)[1:]],'zypak-app-view-missing-or-relative')):
        with comparison(view,destination/name,debug,native_options=['--cwd=/',*options],expected_failure=marker):pass
        observation=json.loads((destination/name/'startup-diagnostics.json').read_text())
        assert observation['markers'].get(marker) and not observation['markers'].get('zypak-spawn-started')
        results[name]=observation
    sibling=Path(record['views']['trace']['directory']);assert sibling.is_dir()
    options,fd=delivery.view_options(view);assert not os.get_inheritable(fd)
    command=['/usr/bin/flatpak','run',*options,'--command=/bin/sh',APPLICATION,'-c',
             'test -d "$1" && test ! -w "$1" && test ! -e "$2"','fontreal-alias-check',str(view),str(sibling)]
    try:
        result=subprocess.run(command,env=env,pass_fds=(fd,),text=True,capture_output=True,timeout=20)
    finally:os.close(fd)
    assert result.returncode==0,'The native alias is writable or exposes sibling code'
    write_json(destination/'containment.json',dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
    for role in record['views'].values():delivery.builder.verify(role)
    write_json(destination/'transport.json',results);return results


def package_identity(inspector,view,record=None):
    view=Path(view);deadline=time.monotonic()+20
    while True:
        identity=inspector.evaluate(IDENTITY)
        if all(row['rendererPid']>0 for row in identity['contents']):break
        assert time.monotonic()<deadline,'Native application content renderer did not initialize for package proof'
        time.sleep(.05)
    main=process_status(inspector.main_pid)
    expected=None;binding='current native deployment'
    if record is not None:
        if view==Path(record['spec']['location'])/'files' or (view.name=='files' and view.parent.name==record['spec']['commit']):expected=record['spec']['original_files'];binding='qualified original package'
        for role,entry in record['views'].items():
            if view==Path(entry['directory']):expected=entry['files'];binding='qualified '+role
    file_identities={}
    def file_identity(relative):
        if relative in file_identities:return file_identities[relative]
        path=view/relative;stat=path.stat();digest=c1.target.sha(path)
        if expected is not None:assert digest==expected[relative]['sha256'],'Live package file differs from qualified assembly'
        item=dict(path=relative,device=stat.st_dev,inode=stat.st_ino,sha256=digest);file_identities[relative]=item
        return item
    engine=view/'teams-for-linux/teams-for-linux'
    with engine.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as binary:
        marker=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX';offset=binary.find(marker)+len(marker)
        assert offset>=len(marker) and binary[offset]==1
        fuses=bytes(binary[offset+2:offset+2+binary[offset+1]]).decode()
    if expected is not None:assert fuses==record['views']['normal']['fuses']['after']
    root_id=view.stat();processes=[('main',main)]
    main_root=Path('/proc')/str(main['hostPid'])
    mount_fields=[line.split() for line in (main_root/'mountinfo').read_text().splitlines()]
    observed=[]
    for label,process in processes:
        pid=process['hostPid'];pin=os.pidfd_open(pid);root=Path('/proc')/str(pid)
        try:
            if label=='main':
                mounted=(root/'root/app').stat();assert (mounted.st_dev,mounted.st_ino)==(root_id.st_dev,root_id.st_ino),'Actual main /app differs from chosen view'
            maps=[];seen=set();hashed=set()
            for line in (root/'maps').read_text().splitlines():
                fields=line.split(None,5)
                if len(fields)!=6:continue
                path=fields[5]
                assert not path.startswith('/run/parent/app/'),'Process mapped original parent code outside its chosen /app'
                if not path.startswith('/app/'):continue
                relative=path[len('/app/'):];assert not relative.endswith(' (deleted)')
                key=(relative,fields[1],fields[3],fields[4])
                if key in seen:continue
                seen.add(key);item=file_identity(relative)
                major,minor=(int(n,16) for n in fields[3].split(':'))
                containing=[entry for entry in mount_fields if path==entry[4] or path.startswith(entry[4].rstrip('/')+'/')]
                length=max(len(entry[4]) for entry in containing);containing=[entry for entry in containing if len(entry[4])==length]
                assert len(containing)==1,'Package mapping has no unique containing mount'
                mount=containing[0];mount_major,mount_minor=map(int,mount[2].split(':'))
                assert os.makedev(major,minor)==os.makedev(mount_major,mount_minor) and int(fields[4])==item['inode'],'Mapped package inode/filesystem differs from chosen assembly'
                if label=='main':
                    live_path=root/'root/app'/relative;live=live_path.stat()
                    assert (live.st_dev,live.st_ino)==(item['device'],item['inode'])
                    if relative not in hashed:
                        assert c1.target.sha(live_path)==item['sha256'];hashed.add(relative)
                maps.append(dict(item,permissions=fields[1],mapFilesystemDevice=fields[3],mountFilesystemDevice=mount[2],kernelMappedPath=path))
            names={row['path'] for row in maps}
            assert {'teams-for-linux/teams-for-linux','teams-for-linux/icudtl.dat','teams-for-linux/resources.pak'}<=names
            mounts=[]
            for fields in mount_fields:
                point=fields[4]
                if point not in ('/app',str(view)):continue
                assert 'ro' in fields[5].split(','),'Chosen application mapping is writable'
                mounts.append(dict(path=point,options=fields[5],device=fields[2]))
            assert any(row['path']=='/app' for row in mounts)
            if label=='main' and binding.startswith('qualified ') and binding!='qualified original package':
                alias=(root/'root'/str(view).lstrip('/')).stat()
                assert (alias.st_dev,alias.st_ino)==(root_id.st_dev,root_id.st_ino)
                assert any(row['path']==str(view) for row in mounts),'Canonical alias lacks its readonly native mount'
            assert not select.select([pin],[],[],0)[0] and process_status(pid)['startTicks']==process['startTicks'],'Actual '+label+' stopped during its package mapping snapshot'
            observed.append(dict(role=label,hostPid=pid,startTicks=process['startTicks'],mappedAppView=[root_id.st_dev,root_id.st_ino],mainAppDirectoryObserved=label=='main',maps=maps,qualifiedMainMounts=mounts))
            if label=='main':
                while True:
                    identity=inspector.evaluate(IDENTITY)
                    if all(row['rendererPid']>0 for row in identity['contents']):break
                    assert time.monotonic()<deadline,'Actual content renderer did not publish its native PID'
                    time.sleep(.05)
                for contents in identity['contents']:
                    processes.append(('content-'+str(contents['id']),renderer_identity(inspector,contents['id'],engine)))
        finally:os.close(pin)
    main_root=Path('/proc')/str(main['hostPid']);resources=[];owned_directory_fds=[]
    for fd in (main_root/'fd').iterdir():
        try:stat=fd.stat();link=os.readlink(fd)
        except FileNotFoundError:continue
        if (stat.st_dev,stat.st_ino)==(root_id.st_dev,root_id.st_ino):
            info=dict(line.split(':',1) for line in (main_root/'fdinfo'/fd.name).read_text().splitlines() if ':' in line)
            flags=int(info['flags'].strip(),8);required=os.O_PATH|os.O_NOFOLLOW|os.O_DIRECTORY|os.O_CLOEXEC
            assert flags&required==required,'Raw inherited host alias FD reached app main'
            owned_directory_fds.append(dict(fd=int(fd.name),flags=flags,closeOnExec=True))
        if link=='/app/teams-for-linux/resources/app.asar':
            item=file_identity('teams-for-linux/resources/app.asar');assert (stat.st_dev,stat.st_ino)==(item['device'],item['inode']);resources.append(item)
    assert resources,'Actual application has no open original ASAR resource'
    loaded=inspector.evaluate("Object.keys(process.mainModule.require('module')._cache).filter(p=>p.startsWith('/app/')&&p.endsWith('.node'))")
    assert loaded,'Original native application module was not loaded'
    mapped={row['path'] for row in observed[0]['maps']}
    with (view/'teams-for-linux/resources/app.asar').open('rb') as stream:
        header=struct.unpack('<4I',stream.read(16));archive=json.loads(stream.read(header[3]))
    native=[]
    for path in loaded:
        relative=path[len('/app/'):]
        if '.asar/' in relative:
            entry=archive
            for part in relative.split('.asar/',1)[1].split('/'):entry=entry['files'][part]
            assert entry.get('unpacked') is True,'Native module ASAR entry is not explicitly unpacked'
            relative=relative.replace('.asar/','.asar.unpacked/',1)
        assert relative in mapped,'Loaded native module has no matching package mapping'
        native.append(dict(virtualPath=path,mapped=file_identity(relative)))
    bootstrap=inspector.evaluate('process.mainModule.filename')
    package=json.loads(asar_source(view/'teams-for-linux/resources/app.asar','package.json'))
    entry=package['main'];assert not entry.startswith('/') and '..' not in Path(entry).parts
    script='/app/teams-for-linux/resources/app.asar/'+entry
    assert identity['appPath']=='/app/teams-for-linux/resources/app.asar'
    assert inspector.evaluate('(()=>{const m=process.mainModule.require(\"module\")._cache['+json.dumps(script)+'];return !!m&&m.loaded;})()'),'Original package entry is not loaded in the native module cache'
    return dict(binding=binding,view=str(view),processes=observed,resources=resources,mainScript=script,bootstrapModule=bootstrap,
                ownedViewDirectoryFds=owned_directory_fds,loadedNativeModules=native,nativeModuleABI=identity['versions']['modules'],versions=identity['versions'],originalFuses=fuses)


def reconcile_trace(collector,graph,observations,silent=False):
    collector.check();assert not collector.thread.is_alive(),'Final trace inspected before collector drain'
    final=graph_rows(collector,graph)
    for observation in observations.values():
        before=observation['rows'];assert final[:len(before)]==before,'Final attributed trace does not extend its live stage snapshot'
    if silent:assert not collector.rows,'Forbidden instrumentation arrived before final stream drain'
    counts={stage:len(row['rows']) for stage,row in observations.items()}
    observations[next(reversed(observations))]['rows']=final
    return dict(completeRows=len(collector.rows),attributedRows=len(final),collectorStopped=True,
                liveSnapshotRows=counts,finalAttributedRows=final)


def selected_glyphs(rows,font,descriptor,glyphs,expected):
    chosen=[r for r in rows if r.get('owner')=='selected' and r.get('font')==font and r.get('descriptor')==descriptor
            and r.get('size')==14 and r.get('glyph') in glyphs]
    assert len(chosen)==len(expected) and {r['glyph'] for r in chosen}==set(expected),'A cached prefix was processed again or new work is missing'
    return chosen


def late_trace_selfcheck(destination):
    destination.mkdir();payload=dict(pid=1,synthetic=True,owner='selected',font=1,descriptor='SYNTHETIC',size=14,glyph=87)
    script="""import os,sys
line=sys.argv[1].encode()
print('empty',flush=True);assert sys.stdin.readline()=='first\\n';os.write(2,line)
print('first',flush=True);assert sys.stdin.readline()=='late\\n';os.write(2,line)
"""
    with c1.StderrCollector(destination,trace_only=True) as collector:
        child=subprocess.Popen([sys.executable,'-B','-c',script,'FONTREAL_SKIA '+json.dumps(payload)+'\n'],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=collector.sender,text=True)
        graph=dict(credentialSenderPid=child.pid,tracePid=1);stages={'empty':dict(rows=[])}
        try:
            assert select.select([child.stdout],[],[],5)[0] and child.stdout.readline()=='empty\n'
            assert not graph_rows(collector,graph);child.stdin.write('first\n');child.stdin.flush()
            assert select.select([child.stdout],[],[],5)[0] and child.stdout.readline()=='first\n'
            deadline=time.monotonic()+5
            while not graph_rows(collector,graph):
                assert time.monotonic()<deadline;time.sleep(.01)
            stages['first']=dict(rows=graph_rows(collector,graph));selected_glyphs(stages['first']['rows'],1,'SYNTHETIC',{87},[87])
            child.stdin.write('late\n');child.stdin.flush();assert child.wait(timeout=5)==0
        finally:
            child.stdin.close();child.stdout.close()
            if child.poll() is None:child.terminate();child.wait(timeout=5)
    result=reconcile_trace(collector,graph,stages)
    for label,action in [('lateDuplicate',lambda:selected_glyphs(stages['first']['rows'],1,'SYNTHETIC',{87},[87])),
                         ('lateInstrumentation',lambda:reconcile_trace(collector,graph,{'empty':dict(rows=[])},True))]:
        try:action()
        except AssertionError:result[label+'Rejected']=True
        else:raise AssertionError('Late trace discriminator accepted '+label)
    write_json(destination/'result.json',dict(result,passed=True,synthetic=True,knownChildPid=child.pid))


def application_session(record,role,destination,env,trace_value=None,control_reference=None):
    destination.mkdir();view=None if role=='official-stock' else Path(record['views'][role]['directory'])
    observations={};stages=(('empty','',False),('first','W',False),('prefix','WW',False),
                           ('prefix-repaint','WW',True),('later','WWg',False),('later-repaint','WWg',True))
    with c1.StderrCollector(destination,trace_only=True) as collector:
        options=[] if trace_value is None else ['--env=FONTREAL_SKIA_TRACE='+trace_value]
        with comparison(view,destination/'app',env,collector=collector,native_options=options) as (inspector,child,data):
            identity=inspector.evaluate(IDENTITY);write_json(destination/'identity.json',identity)
            main_view=view or Path(subprocess.check_output(['/usr/bin/flatpak','info','--show-location',APPLICATION],env=env,text=True).strip())/'files'
            main=application_main(child.pid,main_view,identity);write_json(destination/'main.json',main)
            write_json(destination/'initial-package.json',package_identity(inspector,main_view,record))
            dialog=open_dialog(inspector);previous=None
            for stage,text,repaint in stages:
                state=dialog_stage(inspector,dialog,text,repaint)
                write_json(destination/(stage+'-measurement.json'),state)
                graph=trace_graph(collector,child.pid,main_view,identity,state['rendererPid'])
                if previous is not None:
                    assert graph['renderer']==previous['renderer'],'The existing text renderer changed during its cache sequence'
                    assert graph['credentialSenderPid']==previous['credentialSenderPid']
                pins={}
                try:
                    for pid in {main['hostPid'],graph['renderer']['hostPid'],graph['stdoutCat']['process']['hostPid'],graph['stderrCat']['process']['hostPid']}:
                        pins[pid]=os.pidfd_open(pid)
                    expected=dialog_geometry(main['hostPid'],state['title'],destination,env)
                    if role=='official-stock' and stage=='first':
                        wrong=dict(expected,id='{00000000-0000-0000-0000-000000000000}');count=len(CAPTURE_INVOCATIONS)
                        try:capture_dialog(inspector,dialog,state,main['hostPid'],destination,'wrong',env,wrong)
                        except ValueError:pass
                        else:raise AssertionError('Wrong expected window identity was accepted')
                        assert len(CAPTURE_INVOCATIONS)==count and not list(destination.glob('wrong-*.png'))
                        write_json(destination/'capture-refusal.json',dict(passed=True,actorNotInvoked=True,noImage=True))
                    capture=capture_dialog(inspector,dialog,state,main['hostPid'],destination,stage,env,expected,control_reference)
                    after=trace_graph(collector,child.pid,main_view,identity,state['rendererPid'])
                    write_json(destination/(stage+'-graph-after.json'),after)
                    assert all(after[k]==graph[k] for k in graph if k not in ('matchingTraceWriters','possibleTraceSenders','ownedPidMapping')),'The live trace ownership chain changed during capture'
                    assert all(not select.select([fd],[],[],0)[0] for fd in pins.values()),'The native trace chain stopped during capture'
                finally:
                    for fd in pins.values():os.close(fd)
                rows=graph_rows(collector,after)
                observations[stage]=dict(state=state,capture=capture,graph=graph,rows=rows)
                write_json(destination/(stage+'.json'),observations[stage]);previous=after
            final=inspector.evaluate(IDENTITY);write_json(destination/'final-identity.json',final)
            write_json(destination/'final-package.json',package_identity(inspector,main_view,record))
            assert {c['id'] for c in final['contents']}>{c['id'] for c in identity['contents']},'No genuine later application child was created'
            assert inspector.evaluate("process.mainModule.require('electron').app.getPath('userData')")==str(data)
    drained=reconcile_trace(collector,after,observations,role not in ('trace','source-passive'))
    write_json(destination/'trace-drain.json',drained)
    write_json(destination/'session.json',dict(role=role,stages=list(observations),passed=True))
    return observations


def selected_evidence(observations,oracles,identity):
    first=observations['first']['rows'];glyph=identity['cmap']['W']
    work=[r for r in first if r['owner']=='selected' and r.get('glyph')==glyph and r.get('size')==14 and r.get('family')=='417269616c']
    assert len(work)==1,'No unique actual input W selected raster'
    font=work[0]['font'];descriptor=work[0]['descriptor']
    def selected(stage):
        return [r for r in observations[stage]['rows'] if r['owner']=='selected' and r.get('font')==font
                and r.get('descriptor')==descriptor and r.get('size')==14 and r.get('glyph') in identity['cmap'].values()]
    assert not selected('empty'),'The input strike was rasterized before its first actual glyph'
    for stage,chars in [('first','W'),('prefix','W'),('prefix-repaint','W'),('later','Wg'),('later-repaint','Wg')]:
        rows=selected_glyphs(observations[stage]['rows'],font,descriptor,identity['cmap'].values(),[identity['cmap'][c] for c in chars])
        assert {r['glyph'] for r in rows}=={identity['cmap'][c] for c in chars}
        for char in chars:
            row=next(r for r in rows if r['glyph']==identity['cmap'][char]);oracle=oracles[char]
            assert row['status']==0 and row['matrix']==[1,0,0,1] and row['hinting']==2 and row['format']==1
            assert not row['preblend'] and row['path']==oracle['path'] and row['raw']==oracle['mask']
            assert all(row[key]==oracle[key] for key in ('width','height','left','top','advance'))
            assert bytes.fromhex(row['mask'])==expected_mask(bytes.fromhex(oracle['mask']),oracle['width'])
    targets=[r for r in observations['later']['rows'] if r['owner']=='selected-target' and r.get('font')==font and r.get('size')==14]
    assert targets and all(r['eligible'] and r['control']==2 and not any(r[k] for k in ('mono','light','lcd','vertical','linear','subpixel')) for r in targets)
    return dict(font=font,descriptor=descriptor,glyphs=identity['cmap'],newGlyph='g',independentRaw=True,immutableSelected=True,processedOnce=True)


def colors(state):
    return tuple(tuple(map(int,re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)',state['measure'][field]).groups()))
                 for field in ('color','background'))


def paint_mask(image,row,mask,origin,foreground):
    left=origin[0]+row['left'];top=origin[1]+row['top']
    assert all(isinstance(n,int) for n in (left,top))
    assert 0<=left and 0<=top and left+row['width']<=image.width and top+row['height']<=image.height
    for y in range(row['height']):
        for x in range(row['width']):
            alpha=mask[y*row['width']+x];background=image.getpixel((left+x,top+y))
            image.putpixel((left+x,top+y),tuple(f*(alpha+1)//256+b*(256-alpha)//256 for f,b in zip(foreground,background)))


def same_domains(first,second,stage):
    with Image.open(first/(stage+'-window.png')) as a,Image.open(second/(stage+'-window.png')) as b:
        assert a.mode==b.mode=='RGB' and a.size==b.size==(460,38)
        assert a.tobytes()==b.tobytes(),f'{stage}: actual OS RGB bytes differ between controls'
    assert (first/(stage+'-native.png')).read_bytes()==(second/(stage+'-native.png')).read_bytes(),f'{stage}: native PNG bytes differ between controls'


def stock_origin(stock,passive,destination):
    for stage in stock:same_domains(destination/'source-stock',destination/'source-passive',stage)
    rows=passive['first']['rows']
    work=[r for r in rows if r['owner'] in ('path-raster','direct-path-raster') and r.get('family')=='417269616c'
          and r.get('glyph')==58 and r.get('size')==14 and r.get('width',0)>0 and r.get('height',0)>0]
    assert len(work)==1,'No unique actual native input W raster for stock localization'
    row=work[0];assert row['format']==1 and row['hinting']==1,'Natural input request is not the observed A8/slight request'
    assert any(r['owner']=='fontations-metrics' and all(r.get(k)==row[k] for k in ('pid','font','family','glyph','size','flags')) for r in rows)
    if row['owner']=='path-raster':
        assert any(r['owner']=='fontations-image' and all(r.get(k)==row[k] for k in ('pid','font','family','glyph','size','flags')) for r in rows)
    mask=bytes.fromhex(row['mask']);assert len(mask)==row['width']*row['height'] and any(mask)
    foreground,background=colors(stock['first']['state']);pattern=Image.new('RGB',(row['width'],row['height']),background)
    pattern_row=dict(row,left=0,top=0);paint_mask(pattern,pattern_row,mask,(0,0),foreground)
    with Image.open(destination/'source-stock/first-window.png') as image:
        positions=[(x,y) for y in range(8,30-row['height']+1) for x in range(8,85-row['width']+1)
                   if image.crop((x,y,x+row['width'],y+row['height'])).tobytes()==pattern.tobytes()]
    assert len(positions)==1,'Natural stock mask does not have exactly one unmodified match in the bounded input'
    origin=[positions[0][0]-row['left'],positions[0][1]-row['top']]
    result=dict(origin=origin,stockMaskPosition=positions[0],stockRequest=row,uniqueExactStockMatch=True,
                control=stock['first']['state']['measure'],selectedObservationUsed=False)
    write_json(destination/'stock-origin.json',result);return origin


def observation_gate(record,destination,env):
    destination.mkdir();results={}
    for role,value in [('source-passive',None),('source-passive','0'),('normal','1')]:
        name=role+'-'+str(value);folder=destination/name;folder.mkdir();view=Path(record['views'][role]['directory'])
        with c1.StderrCollector(folder,trace_only=True) as collector:
            options=[] if value is None else ['--env=FONTREAL_SKIA_TRACE='+value]
            with comparison(view,folder/'app',env,collector=collector,native_options=options) as (inspector,child,data):
                identity=inspector.evaluate(IDENTITY);dialog=open_dialog(inspector);state=dialog_stage(inspector,dialog,'W')
                graph=trace_graph(collector,child.pid,view,identity,state['rendererPid']);assert not graph_rows(collector,graph)
                write_json(folder/'graph.json',graph)
        assert not collector.rows,'Forbidden instrumentation arrived after live observation'
        results[name]=dict(passed=True,rows=0,collectorDrained=True)
    write_json(destination/'result.json',results);return results


def simple_kerning(font,ids):
    data=font.read_bytes();count=struct.unpack_from('>H',data,4)[0];tables={}
    for index in range(count):
        tag,_,offset,length=struct.unpack_from('>4sIII',data,12+16*index);assert offset+length<=len(data)
        tables[tag]=(offset,length)
    assert b'GPOS' not in tables,'The simple native input needs an independent GPOS positioning oracle'
    offset,length=tables[b'kern'];version,subtables=struct.unpack_from('>HH',data,offset)
    assert version==0 and subtables==1
    version,extent,coverage,pairs=struct.unpack_from('>4H',data,offset+4)
    assert version==0 and coverage==1 and extent+4==length and 14+6*pairs<=extent
    values={(a,b):value for a,b,value in struct.iter_unpack('>HHh',data[offset+18:offset+18+6*pairs])}
    relevant={(a,b):values.get((ids[a],ids[b]),0) for a,b in (('W','W'),('W','g'))}
    assert all(value==0 for value in relevant.values()),'Native input has nonzero pair positioning'
    return dict(noGpos=True,kernFormat=0,pairs={a+b:value for (a,b),value in relevant.items()})


def require_native_modules(versions,baseline):
    assert versions['modules']==baseline['modules'],'Native module ABI differs from the installed application'


def actual_app(build_record,destination,env):
    destination.mkdir(parents=True,exist_ok=True);command=[sys.executable,'-B',str(ROOT/'tools/build-chromium-delivery.py'),'--build-record',str(build_record)]
    write_json(destination/'producer-command.json',command)
    with (destination/'producer.stdout').open('w') as stdout,(destination/'producer.stderr').open('w') as stderr:
        subprocess.run(command,env=env,stdout=stdout,stderr=stderr,check=True)
    emitted=Path((destination/'producer.stdout').read_text().splitlines()[-1]).resolve();record=delivery.load_build(emitted)
    assert record['spec']['build_record']==str(build_record.resolve()) and record['spec']['build_sha256']==c1.target.sha(build_record)
    assert delivery.compatibility(record) is None
    write_json(destination/'build.json',dict(path=str(emitted),sha256=c1.target.sha(emitted)))
    privacy_selfcheck(destination/'privacy-selfcheck');late_trace_selfcheck(destination/'late-trace-selfcheck');view_transport(record,destination/'view-transport',env)
    observation_gate(record,destination/'observation-gate',env)
    oracles,font=provider_oracle(json.loads(build_record.read_text()),destination/'provider',env)
    kerning=simple_kerning(Path(font['font']),font['cmap']);write_json(destination/'provider/positioning.json',kerning)
    sessions={}
    for role in ('official-stock','source-stock','source-passive'):
        sessions[role]=application_session(record,role,destination/role,env,'1' if role=='source-passive' else None,
                                           destination/'source-stock' if role=='source-passive' else None)
        print(role+': six actual native captures passed',flush=True)
    origin=stock_origin(sessions['source-stock'],sessions['source-passive'],destination)
    for role in ('normal','trace'):
        sessions[role]=application_session(record,role,destination/role,env,control_reference=destination/'source-stock')
        print(role+': six actual native captures passed',flush=True)
    evidence=selected_evidence(sessions['trace'],oracles,font);write_json(destination/'selected-evidence.json',evidence)
    base=sessions['source-stock']['first']['state']['measure'];checks=[]
    versions=json.loads((destination/'official-stock/identity.json').read_text())['versions']
    for role in sessions:require_native_modules(json.loads((destination/role/'identity.json').read_text())['versions'],versions)
    for role,observations in sessions.items():
        for stage,observation in observations.items():
            state=observation['state'];assert state['measure']==sessions['source-stock'][stage]['state']['measure'],'Actual local control/font/style geometry differs across roles'
            if role not in ('trace','source-passive'):assert not observation['rows'],'An uninstrumented engine emitted renderer trace records'
    foreground,background=colors(sessions['source-stock']['first']['state'])
    for stage in sessions['normal']:
        same_domains(destination/'normal',destination/'trace',stage)
        text=sessions['normal'][stage]['state']['text']
        if not text:
            continue
        with Image.open(destination/'source-stock'/(stage+'-window.png')) as stock:
            expected=stock.copy()
        # Only the source-defined text interior changes; the border and native nontext controls stay exact.
        expected.paste(background,(8,8,85,30));advance=0
        for char in text:
            row=oracles[char];assert row['advance'][1]==0 and row['advance'][0]==int(row['advance'][0])
            paint_mask(expected,row,expected_mask(bytes.fromhex(row['mask']),row['width']),
                       (origin[0]+advance,origin[1]),foreground)
            advance+=int(row['advance'][0])
        expected.save(destination/(stage+'-expected.png'))
        with Image.open(destination/'normal'/(stage+'-window.png')) as normal:
            assert expected.tobytes()==normal.tobytes(),f'{stage}: actual selected OS pixels differ from the independent placed-mask expectation'
        checks.append(dict(stage=stage,origin=origin,advance=advance,expected_sha256=c1.target.sha(destination/(stage+'-expected.png'))))
    result=dict(passed=True,build_record=str(emitted),build_sha256=c1.target.sha(emitted),font=font,
                stockOrigin=origin,engineVersions=versions,selected=evidence,kerning=kerning,checks=checks,report=str(destination),
                test_inputs={name:c1.target.sha(ROOT/name) for name in ('tests/chromium_delivery_test.py','tests/chromium_app_inspect.mjs','tests/chromium_flatpak_test.py')})
    write_json(destination/'report.json',result);write_json(emitted.parent/'qualification.json',result)
    return result


def native_instances(env):
    output=subprocess.check_output(['/usr/bin/flatpak','ps','--columns=instance,pid,application'],env=env,text=True)
    matches=[]
    for line in output.splitlines():
        instance,launcher,application=line.split('\t')
        if application!=APPLICATION:continue
        folder=Path(env['XDG_RUNTIME_DIR'])/'.flatpak'/instance
        try:
            payload=(folder/'bwrapinfo.json').read_text()
            if not payload.strip():continue
            main_pid=json.loads(payload)['child-pid']
            fields=dict(line.split(':',1) for line in (Path('/proc')/str(main_pid)/'status').read_text().splitlines() if ':' in line)
        except FileNotFoundError:continue
        pids=list(map(int,fields['NSpid'].split()));assert pids[0]==main_pid and all(n>0 for n in pids)
        if len(pids)!=2:continue
        try:info=instance_identity(main_pid)
        except FileNotFoundError:continue
        assert info['application']==APPLICATION and info['instance']==instance
        matches.append(dict(instance=instance,launcherPid=int(launcher),initPid=main_pid,initNamespacePids=pids,info=info))
    return matches


def native_entry(process,arguments,view,destination):
    native=Path('/usr/bin/flatpak').stat();root=Path('/proc')/str(process.pid);deadline=time.monotonic()+15
    while True:
        try:
            before=process_status(process.pid);executable=(root/'exe').stat()
            if (executable.st_dev,executable.st_ino)==(native.st_dev,native.st_ino):
                argv=[part.decode() for part in (root/'cmdline').read_bytes().split(b'\0') if part]
                after=(root/'exe').stat()
                if (after.st_dev,after.st_ino)==(native.st_dev,native.st_ino):break
        except FileNotFoundError:pass
        assert process.poll() is None and time.monotonic()<deadline,'Owned launch did not expose its native Flatpak exec phase'
        time.sleep(.001)
    options=[arg for arg in argv[1:] if arg.startswith(('--app-path=','--ro-bind-fd=','--env=FONTREAL_ZYPAK_APP_PATH='))]
    assert [arg for arg in argv[1:] if arg not in options]==arguments,'Real native Flatpak entry changed the original argv'
    view_fd=None
    if view is None:assert not options
    else:
        assert '--app-path='+str(view) in options and '--env=FONTREAL_ZYPAK_APP_PATH='+str(view) in options
        descriptors=[int(arg.split('=',1)[1]) for arg in options if arg.startswith('--ro-bind-fd=')];assert len(descriptors)==1
        stat=(root/'fd'/str(descriptors[0])).stat();chosen=Path(view).stat()
        assert (stat.st_dev,stat.st_ino)==(chosen.st_dev,chosen.st_ino),'Native Flatpak did not receive the chosen alias FD'
        view_fd=dict(fd=descriptors[0],device=stat.st_dev,inode=stat.st_ino)
    assert process_status(process.pid)['startTicks']==before['startTicks']
    result=dict(hostPid=process.pid,startTicks=before['startTicks'],nativeExecutable=[native.st_dev,native.st_ino],
                argv=argv,selectedOptions=options,view=str(view) if view is not None else None,viewFd=view_fd)
    write_json(destination,result);return result


@contextmanager
def ordinary_observer(command,destination,env,engine,view,user_data=None,existing=False):
    destination.mkdir(parents=True);process=None;pidfd=None;initfd=None;inspector=None
    inspector_port_available()
    if not existing:
        assert not any(row['info']['appPath']==str(view) for row in native_instances(env)),'An existing instance of this code view must quit normally before this route'
        write_json(destination/'command.json',command)
        process=subprocess.Popen(command,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if 'msteams://fontreal.invalid/unsent?value=%2F&space=a%20b' in command:
            native_entry(process,command[1:],view,destination/'native-entry.json')
    deadline=time.monotonic()+45;main=None
    try:
        while True:
            instances=[row for row in native_instances(env) if row['info']['appPath']==str(view)]
            if instances:
                assert len(instances)==1,'Ordinary Teams main instance is ambiguous'
                instance=instances[0];depth=len(instance['initNamespacePids']);mains=[]
                for pid in comparison_processes(instance['launcherPid'],engine):
                    row=process_status(pid)
                    if len(row['namespacePids'])==depth and row['namespacePids'][-1]==2:mains.append(row)
                assert len(mains)<=1,'Ordinary main-engine mapping is ambiguous'
                if mains:
                    main=mains[0];stat=engine.stat()
                    assert main['executable']==[stat.st_dev,stat.st_ino] and instance['info']['appPath']==str(view),'Ordinary route chose a different code view'
                    if main['caughtSignals']&(1<<(signal.SIGUSR1-1)):break
            if process is not None:assert process.poll() in (None,0),'Ordinary launch dispatcher failed'
            assert time.monotonic()<deadline,'Ordinary Teams launch did not initialize its native main'
            time.sleep(.1)
        init=process_status(instance['initPid']);initfd=os.pidfd_open(init['hostPid'])
        pidfd=os.pidfd_open(main['hostPid']);activation=activate_inspector(main,engine,pidfd,destination)
        assert not select.select([initfd],[],[],0)[0] and process_status(init['hostPid'])==init
        write_json(destination/'activation.json',dict(instance=instance,init=init,activation=activation))
        inspector=Inspector(9229,destination);inspector.main_pid=main['hostPid'];inspector.launch_pid=instance['launcherPid']
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:9229/json/list',timeout=1) as response:ready=bool(json.load(response))
                if ready and inspector.evaluate("process.mainModule.require('electron').app.isReady()"):break
            except (OSError,urllib.error.URLError):pass
            assert time.monotonic()<deadline,'Native ordinary-launch inspector did not become ready'
            time.sleep(.1)
        identity=inspector.evaluate(IDENTITY)
        assert identity['pid']==main['namespacePids'][-1] and identity['appPath']=='/app/teams-for-linux/resources/app.asar'
        if user_data is not None:assert identity['data']==str(user_data),'Ordinary route changed the original application data path'
        mounted=inspector.evaluate("(()=>{const s=process.mainModule.require('fs').statSync('/app');return [s.dev,s.ino]})()")
        stat=view.stat();assert mounted==[stat.st_dev,stat.st_ino]
        write_json(destination/'identity.json',identity)
        uri='msteams://fontreal.invalid/unsent?value=%2F&space=a%20b'
        if command is not None and uri in command:
            entry=json.loads((destination/'native-entry.json').read_text());native=entry['argv']
            at=native.index(APPLICATION);assert native[at:]==[APPLICATION,'@@u',uri,'@@'],'Production dispatch changed original URI suffix'
            assert uri in inspector.evaluate('process.argv'),'Native application did not receive the unsent invalid URI'
            write_json(destination/'native-dispatch.json',dict(nativeEntry='native-entry.json',knownUri=uri,uriSuffixPreserved=True,applicationArgvContainsUri=True))
        yield inspector,identity,instance
        assert not select.select([initfd],[],[],0)[0] and process_status(init['hostPid'])==init
    finally:
        if inspector is not None:inspector.quit()
        if pidfd is not None:
            try:assert select.select([pidfd],[],[],25)[0],'Normal Teams app.quit did not complete; working data was not force-closed'
            finally:os.close(pidfd)
        if initfd is not None:os.close(initfd)
        if process is not None:
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:raise AssertionError('Ordinary launch dispatcher did not exit after normal application quit')


def renderer_identity(inspector,contents_id,engine):
    visible=inspector.evaluate('process.mainModule.require("electron").webContents.fromId('+str(contents_id)+').getOSProcessId()')
    main=process_status(inspector.main_pid);index=len(main['namespacePids'])-1;matches=[]
    for pid in comparison_tree(inspector.launch_pid):
        try:fields=dict(line.split(':',1) for line in (Path('/proc')/str(pid)/'status').read_text().splitlines() if ':' in line)
        except FileNotFoundError:continue
        pids=list(map(int,fields['NSpid'].split()));assert pids[0]==pid and all(n>0 for n in pids)
        if len(pids)>index and pids[index]==visible:matches.append(pid)
    assert len(matches)==1,'Ordinary content renderer has no unique native namespace mapping'
    row=process_status(matches[0]);stat=engine.stat();assert row['executable']==[stat.st_dev,stat.st_ino]
    assert row['seccomp']==2 and row['noNewPrivs']==1 and all(row['capabilities'][k]==0 for k in ('CapInh','CapPrm','CapEff','CapAmb'))
    return row


def working_text(inspector,destination,env,engine,proof,selected,baseline=None):
    destination.mkdir();dialog=open_dialog(inspector,compositor_env=env);observations={}
    record=delivery.load_build(Path(proof['build_record']))
    initial_package=package_identity(inspector,engine.parent.parent,record)
    if initial_package['binding'].startswith('qualified '):assert initial_package['versions']==proof['engineVersions']
    write_json(destination/'initial-package.json',initial_package)
    provider=json.loads((Path(proof['report'])/'provider/provider.json').read_text());oracles={chr(r['char']):r for r in provider}
    for stage,text in [('first','W'),('later','WWg')]:
        state=dialog_stage(inspector,dialog,text);write_json(destination/(stage+'-measurement.json'),state)
        row=renderer_identity(inspector,dialog['contentsId'],engine);pidfd=os.pidfd_open(row['hostPid'])
        try:
            expected=dialog_geometry(inspector.main_pid,state['title'],destination,env)
            capture=capture_dialog(inspector,dialog,state,inspector.main_pid,destination,stage,env,expected,baseline)
            assert not select.select([pidfd],[],[],0)[0] and renderer_identity(inspector,dialog['contentsId'],engine)==row
        finally:os.close(pidfd)
        if baseline is not None:
            stock_state=json.loads((baseline/(stage+'-measurement.json')).read_text())
            assert state['measure']==stock_state['measure'],'Working-data control style/layout differs from native baseline'
        if selected:
            assert baseline is not None
            with Image.open(baseline/(stage+'-window.png')) as stock:image=stock.copy()
            foreground,background=colors(state);image.paste(background,(8,8,85,30));advance=0
            for char in text:
                oracle=oracles[char]
                paint_mask(image,oracle,expected_mask(bytes.fromhex(oracle['mask']),oracle['width']),
                           (proof['stockOrigin'][0]+advance,proof['stockOrigin'][1]),foreground)
                advance+=int(oracle['advance'][0])
            image.save(destination/(stage+'-expected.png'))
            with Image.open(destination/(stage+'-window.png')) as actual:assert actual.tobytes()==image.tobytes(),'Original-data selected pixels differ from independent expectation'
        elif baseline is not None:same_domains(baseline,destination,stage)
        observations[stage]=dict(state=state,capture=capture,renderer=row)
    final=inspector.evaluate(IDENTITY)
    active=[]
    for contents in final['contents']:
        assert contents['rendererPid']>0,'An application content renderer is not initialized'
        active.append(dict(contentsId=contents['id'],type=contents['type'],kernel=renderer_identity(inspector,contents['id'],engine)))
    write_json(destination/'content-renderers.json',active)
    write_json(destination/'final-package.json',package_identity(inspector,engine.parent.parent,record))
    security=sorted({(row['type'],row['preferences']['sandbox'],row['preferences']['contextIsolation'],row['preferences']['nodeIntegration']) for row in final['contents']})
    if baseline is not None:assert [list(row) for row in security]==json.loads((baseline/'text.json').read_text())['security'],'Application security preferences changed from stock'
    write_json(destination/'text.json',dict(passed=True,selected=selected,observations=observations,security=security));return observations


def lifecycle_build(build_record,destination,env):
    command=[sys.executable,'-B',str(ROOT/'tools/build-chromium-delivery.py'),'--build-record',str(build_record)]
    write_json(destination/'producer-command.json',command)
    with (destination/'producer.stdout').open('w') as out,(destination/'producer.stderr').open('w') as err:
        subprocess.run(command,env=env,stdout=out,stderr=err,check=True)
    emitted=Path((destination/'producer.stdout').read_text().splitlines()[-1]).resolve();record=delivery.load_build(emitted)
    proof=json.loads((emitted.parent/'qualification.json').read_text())
    assert proof['passed'] and proof['build_sha256']==c1.target.sha(emitted) and record['spec']['build_sha256']==c1.target.sha(build_record)
    assert delivery.compatibility(record) is None
    return emitted,record,proof


def portal_autostart():
    path=Path.home()/'.config/autostart'/(APPLICATION+'.desktop');config=configparser.ConfigParser(interpolation=None);config.read(path)
    entry=config['Desktop Entry'];assert entry.get('X-XDP-Autostart')==APPLICATION and entry.get('X-Flatpak')==APPLICATION
    enabled=not entry.getboolean('Hidden',fallback=False) and entry.getboolean('X-GNOME-Autostart-enabled',fallback=True)
    stat=path.stat()
    return dict(path=str(path),sha256=c1.target.sha(path),device=stat.st_dev,inode=stat.st_ino,
                mtime_ns=stat.st_mtime_ns,enabled=enabled,command=entry['Exec'])


def generated_autostart(destination,expected,env,dropin=None):
    unit='app-'+APPLICATION+'@autostart.service'
    subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
    output=subprocess.check_output(['systemctl','--user','show',unit,'-p','ExecStart','-p','FragmentPath','-p','SourcePath','-p','DropInPaths'],env=env,text=True)
    fragment=next(line.split('=',1)[1] for line in output.splitlines() if line.startswith('FragmentPath='))
    write_json(destination,dict(unit=unit,expected=str(expected),observation=output,baseFragment=Path(fragment).read_text()))
    if dropin is not None:assert str(dropin) in next(line for line in output.splitlines() if line.startswith('DropInPaths='))
    assert 'path='+str(expected)+' ;' in output,'Native autostart generator did not resolve the expected launcher'
    return unit


def hook_checks(record,state_path,hooks,destination,env):
    destination.mkdir();state=json.loads(state_path.read_text());observations=[]
    for arguments in [['--version'],['run','--command=/usr/bin/true',APPLICATION],['run','--arch','x86_64',APPLICATION]]:
        first=subprocess.run([str(hooks['flatpak']),*arguments],env=env,text=True,capture_output=True)
        second=subprocess.run(['/usr/bin/flatpak',*arguments],env=env,text=True,capture_output=True)
        assert (first.returncode,first.stdout,first.stderr)==(second.returncode,second.stdout,second.stderr),'Unknown route changed native argv/outcome'
        observations.append(dict(arguments=arguments,exit_code=first.returncode,stdout=first.stdout,stderr=first.stderr))
    command=[str(hooks['flatpak']),'run','--command=/usr/bin/sleep',APPLICATION,'2']
    child=subprocess.Popen(command,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        entry=native_entry(child,command[1:],None,destination/'unknown-native-entry.json');native=entry['argv']
        chosen=Path(record['views']['normal']['directory']).stat()
        for fd in (Path('/proc')/str(child.pid)/'fd').iterdir():
            try:stat=fd.stat()
            except FileNotFoundError:continue
            assert (stat.st_dev,stat.st_ino)!=(chosen.st_dev,chosen.st_ino),'Unknown native route holds a selected alias FD'
        write_json(destination/'unknown-native-dispatch.json',dict(command=command,nativeArgv=native,aliasOptionsAbsent=True,aliasFdAbsent=True))
        assert child.wait(timeout=10)==0
    finally:
        if child.poll() is None:child.wait(timeout=10)
    uri='msteams://fontreal.invalid/unsent?value=%2F&space=a%20b'
    arguments=['run','--file-forwarding',APPLICATION,'@@u',uri,'@@']
    chosen=delivery.selected(arguments,state);assert chosen is not None
    command,fd=chosen
    try:
        index=command.index(APPLICATION);assert command[index:]==arguments[2:],'Opaque URI/file-forwarding arguments changed'
    finally:os.close(fd)
    original={name:p.read_bytes() for name,p in hooks.items()};before=state_path.read_bytes()
    for victim in ('flatpak','autostart'):
        changed=original[victim]+b'# SYNTHETIC foreign ownership discriminator\n';hooks[victim].write_bytes(changed)
        try:
            result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'enable','teams','--record',state['apps']['teams']['build']],env=env,text=True,capture_output=True)
            assert result.returncode!=0 and 'changed outside Fontreal' in result.stderr
            assert state_path.read_bytes()==before and all(p.read_bytes()==(changed if name==victim else original[name]) for name,p in hooks.items()),'Ownership refusal changed hook files'
        finally:
            assert hooks[victim].read_bytes()==changed;hooks[victim].write_bytes(original[victim])
    delivery.require_owned(state)
    write_json(destination/'checks.json',dict(passed=True,nativeForwarding=observations,opaqueUriComposition=True,uriInvoked=False,foreignOwnershipRefused=True))


def provider_contrasts(record_path,destination,env):
    destination.mkdir();private=dict(env);config=destination/'config'
    for key,name in (('XDG_CONFIG_HOME','config'),('XDG_CONFIG_DIRS','config-dirs'),('XDG_DATA_HOME','data'),
                     ('XDG_DATA_DIRS','data-dirs'),('XDG_CACHE_HOME','cache')):
        path=destination/name;path.mkdir();private[key]=str(path)
    private['SYSTEMD_SCOPE']='user';provider=config/'autostart'/(APPLICATION+'.desktop');provider.parent.mkdir()
    state=config/'fontreal/chromium/apps.json';unit=AUTOSTART_UNIT;observations=[];enabled=False
    try:
        command=[sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'enable','teams','--record',str(record_path)]
        with (destination/'enable.stdout').open('w') as out,(destination/'enable.stderr').open('w') as err:subprocess.run(command,env=private,stdout=out,stderr=err,check=True)
        enabled=True;owned=json.loads(state.read_text());dropin=next(Path(e['path']) for e in owned['hooks'] if e['path'].endswith('/50-fontreal.conf'))
        (destination/'actual-product-dropin.conf').write_bytes(dropin.read_bytes())
        for name,hidden in [('enabled',False),('disabled',True),('absent',None)]:
            if hidden is None:provider.unlink()
            else:provider.write_text('[Desktop Entry]\nType=Application\nName=SYNTHETIC native provider\nExec=/usr/bin/true\nHidden='+str(hidden).lower()+'\n')
            folder=destination/name;folder.mkdir();dirs=[folder/p for p in ('normal','early','late')]
            for path in dirs:path.mkdir()
            generator=['/usr/lib/systemd/user-generators/systemd-xdg-autostart-generator',*map(str,dirs)]
            with (folder/'generator.stdout').open('w') as out,(folder/'generator.stderr').open('w') as err:subprocess.run(generator,env=private,stdout=out,stderr=err,check=True)
            fragment=dirs[2]/unit;wants=dirs[2]/'xdg-desktop-autostart.target.wants'/unit
            verify_env=dict(private,SYSTEMD_UNIT_PATH=':'.join([str(config/'systemd/user'),str(dirs[2]),'/usr/lib/systemd/user']))
            command=['systemd-analyze','--user','--generators=no','--man=no','verify',unit]
            result=subprocess.run(command,env=verify_env,text=True,capture_output=True)
            (folder/'verify.stdout').write_text(result.stdout);(folder/'verify.stderr').write_text(result.stderr)
            if name=='enabled':assert fragment.is_file() and wants.is_symlink() and result.returncode==0
            else:assert not fragment.exists() and not wants.exists() and result.returncode!=0 and 'not found' in result.stderr
            observations.append(dict(case=name,generator=generator,verify=command,verify_exit=result.returncode,
                                     baseFragment=fragment.exists(),wanted=wants.exists(),productDropin=str(dropin)))
        write_json(destination/'report.json',dict(passed=True,syntheticProvider=True,nativeGeneratorAndUnitLoader=True,userPreferenceChanged=False,cases=observations))
    finally:
        if enabled:subprocess.run([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'disable','teams'],env=private,check=True,capture_output=True)
        assert not state.exists()


def lifecycle(build_record,destination,env):
    destination.mkdir(parents=True,exist_ok=True);emitted,record,proof=lifecycle_build(build_record,destination,env)
    inspector_port_selfcheck(destination/'port-selfcheck');provider_contrasts(emitted,destination/'provider-contrasts',env)
    state_path,hooks=delivery.paths();assert not state_path.exists() and not any(p.exists() or p.is_symlink() for p in hooks.values())
    stock=Path(record['spec']['location'])/'files';stock_engine=stock/'teams-for-linux/teams-for-linux'
    user_data=None;marker=None;enabled=False;results={};autostart_before=portal_autostart()
    assert autostart_before['enabled'],'Preserve the existing disabled autostart intent; this enabled-autostart scenario is unavailable'
    write_json(destination/'autostart-before.json',autostart_before)
    try:
        with ordinary_observer(None,destination/'baseline',env,stock_engine,stock,existing=True) as (inspector,identity,instance):
            user_data=Path(identity['data']);stat=user_data.stat();assert stat.st_uid==os.getuid()
            marker=user_data/('.fontreal-delivery-proof-'+os.urandom(12).hex());marker.write_text(os.urandom(32).hex()+'\n')
            data_identity=dict(path=str(user_data),device=stat.st_dev,inode=stat.st_ino,marker=str(marker),marker_sha256=c1.target.sha(marker))
            write_json(destination/'original-data.json',data_identity)
            baseline=destination/'baseline/text';working_text(inspector,baseline,env,stock_engine,proof,False)
            uri='msteams://fontreal.invalid/unsent?value=%2F&space=a%20b'
            rejection=inspector.evaluate('(async()=>{const f=process.mainModule.require(\"electron\").ipcMain._invokeHandlers.get(\"get-config\");const c=await f();return [c.meetupJoinRegEx,c.msTeamsProtocols.v1,c.msTeamsProtocols.v2].map(p=>new RegExp(p).test('+json.dumps(uri)+'));})()')
            assert rejection==[False,False,False],'Original effective URI predicates accept the supposedly harmless unsent test URI'
            source=asar_source(stock/'teams-for-linux/resources/app.asar','app/mainAppWindow/index.js')
            write_json(destination/'unsent-uri-safety.json',dict(uri=uri,effectivePredicatesAccepted=rejection,originalHandlerOnly=True,sourceSha256=hashlib.sha256(source.encode()).hexdigest()))
        command=[sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'enable','teams','--record',str(emitted)]
        with (destination/'enable.stdout').open('w') as out,(destination/'enable.stderr').open('w') as err:subprocess.run(command,env=env,stdout=out,stderr=err,check=True)
        enabled=True;normal=delivery.builder.current_view(record);engine=normal/'teams-for-linux/teams-for-linux'
        hook_checks(record,state_path,hooks,destination/'hook-checks',env)
        unit=generated_autostart(destination/'selected-autostart-generator.json',Path('/usr/bin/gio'),env,hooks['autostart'])
        desktop=configparser.ConfigParser(interpolation=None);desktop.read(hooks['desktop']);actions=[name for name in desktop.sections() if name.startswith('Desktop Action ')]
        assert not actions and 'Actions' not in desktop['Desktop Entry'];results['desktopActions']=[]
        routes=[('desktop',['gio','launch',str(hooks['desktop'])]),('command',[str(hooks['command'])]),
                ('application-command',[str(hooks['application'])]),('path-flatpak',['flatpak','run',APPLICATION]),
                ('autostart',['systemctl','--user','start',unit]),
                ('file-forwarding',[str(hooks['flatpak']),'run','--file-forwarding',APPLICATION,'@@u',
                                    'msteams://fontreal.invalid/unsent?value=%2F&space=a%20b','@@'])]
        for name,command in routes:
            with ordinary_observer(command,destination/name,env,engine,normal,user_data) as (inspector,identity,instance):
                assert c1.target.sha(marker)==data_identity['marker_sha256'] and [user_data.stat().st_dev,user_data.stat().st_ino]==[data_identity['device'],data_identity['inode']]
                working_text(inspector,destination/name/'text',env,engine,proof,True,baseline);results[name]=dict(passed=True)
            print(name+': original data and selected pixels passed',flush=True)
        deadline=time.monotonic()+35
        while portal_autostart()['mtime_ns']==autostart_before['mtime_ns']:
            assert time.monotonic()<deadline,'Original application did not regenerate its native portal autostart entry'
            time.sleep(.1)
        regenerated=portal_autostart();assert regenerated['enabled']==autostart_before['enabled'] and regenerated['command']==autostart_before['command']
        write_json(destination/'autostart-regenerated.json',regenerated)
        generated_autostart(destination/'rewritten-selected-autostart-generator.json',Path('/usr/bin/gio'),env,hooks['autostart'])
        with ordinary_observer(['systemctl','--user','start',unit],destination/'autostart-after-rewrite',env,engine,normal,user_data) as (inspector,identity,instance):
            working_text(inspector,destination/'autostart-after-rewrite/text',env,engine,proof,True,baseline)
        with ordinary_observer(['/usr/bin/flatpak','run',APPLICATION],destination/'native-escape',env,stock_engine,stock,user_data) as (inspector,identity,instance):
            working_text(inspector,destination/'native-escape/text',env,stock_engine,proof,False,baseline)
        subprocess.run([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'disable','teams'],env=env,check=True)
        enabled=False
        generated_autostart(destination/'stock-autostart-generator.json',Path('/usr/bin/flatpak'),env)
        with ordinary_observer(['/usr/bin/flatpak','run',APPLICATION],destination/'stock-reversal',env,stock_engine,stock,user_data) as (inspector,identity,instance):
            working_text(inspector,destination/'stock-reversal/text',env,stock_engine,proof,False,baseline)
        with ordinary_observer(['systemctl','--user','start',unit],destination/'stock-autostart',env,stock_engine,stock,user_data) as (inspector,identity,instance):
            working_text(inspector,destination/'stock-autostart/text',env,stock_engine,proof,False,baseline)
        inventory=c1.target.owners();assert {row['target'] for row in inventory}=={'edge','teams','bitwarden','telegram'}
        assert all(row['backend']=='unknown' and not row['backend_observed'] for row in inventory)
        results.update(passed=True,build=str(emitted),originalData=data_identity,workingActivation=False,inventory=inventory,
                       applicationProofs={'teams':['actual-app','lifecycle'],'edge':[],'bitwarden':[],'telegram':[]},
                       portalAutostartRegenerated=True,selectedAndStockAutostart=True,finalReviewActivationPending=True)
        write_json(destination/'report.json',results);return results
    finally:
        if enabled:subprocess.run([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'disable','teams'],env=env,check=True)
        if marker is not None:
            assert c1.target.sha(marker)==data_identity['marker_sha256'];marker.unlink()


def service_gio_capability(record_path,destination,env):
    destination.mkdir(parents=True,exist_ok=True);record=delivery.load_build(record_path)
    proof=json.loads((record_path.parent/'qualification.json').read_text());assert proof['passed'] and proof['build_sha256']==c1.target.sha(record_path)
    state,hooks=delivery.paths();assert not state.exists() and not any(p.exists() for p in hooks.values())
    original=Path(record['spec']['location'])/'files';stock=original/'teams-for-linux/teams-for-linux'
    enabled=False;marker=None;result={};phase_view=None
    try:
        with ordinary_observer(None,destination/'original',env,stock,original,existing=True) as (inspector,identity,instance):
            data=Path(identity['data']);marker=data/('.fontreal-gio-proof-'+os.urandom(12).hex());marker.write_text(os.urandom(32).hex())
            marker_sha=c1.target.sha(marker);data_stat=data.stat()
            write_json(destination/'data.json',dict(path=str(data),device=data_stat.st_dev,inode=data_stat.st_ino,marker=str(marker),marker_sha256=marker_sha))
        portal=portal_autostart();assert portal['enabled']
        for selected in (False,True):
            label='selected' if selected else 'stock';folder=destination/label;normal=Path(record['views']['normal']['directory']) if selected else original
            engine=normal/'teams-for-linux/teams-for-linux';phase_view=normal
            if selected:
                command=[sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'enable','teams','--record',str(record_path)]
                with (destination/'enable.stdout').open('w') as out,(destination/'enable.stderr').open('w') as err:subprocess.run(command,env=env,stdout=out,stderr=err,check=True)
                enabled=True
            unit='fontreal-teams-gio-capability-'+label+'-'+os.urandom(6).hex()+'.service'
            command=['systemd-run','--user','--collect','--wait','--unit='+unit,'--property=Type=exec',
                     '--property=ExitType=cgroup','--property=StandardOutput=null','--property=StandardError=null',
                     '/usr/bin/gio','launch',portal['path']]
            with ordinary_observer(command,folder,env,engine,normal,data) as (inspector,identity,instance):
                path=next(line for line in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines() if line.startswith('PATH='))
                shown=subprocess.check_output(['systemctl','--user','show',unit,'-p','ExecStart','-p','Transient','-p','ExitType','-p','Type'],env=env,text=True)
                write_json(folder/'service.json',dict(unit=unit,command=command,properties=shown,managerEffectivePath=path,noTestPath=True))
                assert c1.target.sha(marker)==marker_sha and [data.stat().st_dev,data.stat().st_ino]==[data_stat.st_dev,data_stat.st_ino]
                working_text(inspector,folder/'text',env,engine,proof,selected,destination/'stock/text' if selected else None)
            loaded=subprocess.run(['systemctl','--user','show',unit,'-p','LoadState','--value'],env=env,text=True,capture_output=True)
            assert loaded.stdout.strip()=='not-found','Collected native diagnostic unit remains installed'
            result[label]=dict(passed=True,unit=unit,collected=True,actualView=str(normal),originalData=str(data))
        write_json(destination/'result.json',dict(passed=True,stock=result['stock'],selected=result['selected'],gio=str(Path('/usr/bin/gio').resolve()),gio_sha256=c1.target.sha(Path('/usr/bin/gio'))))
    finally:
        if phase_view is not None and any(row['info']['appPath']==str(phase_view) for row in native_instances(env)):
            with ordinary_observer(None,destination/'normal-recovery-quit',env,phase_view/'teams-for-linux/teams-for-linux',phase_view,data,existing=True):pass
        if enabled:subprocess.run([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'disable','teams'],env=env,check=True)
        if marker is not None:
            assert c1.target.sha(marker)==marker_sha;marker.unlink()
        unit='app-'+APPLICATION+'@autostart.service'
        subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
        subprocess.run(['systemctl','--user','start',unit],env=env,check=True)


def asar_source(path,name):
    with path.open('rb') as stream:
        header=struct.unpack('<4I',stream.read(16));assert 0<header[3]<=16*1024*1024
        entry=json.loads(stream.read(header[3]))
        for part in name.split('/'):entry=entry['files'][part]
        assert not entry.get('unpacked') and not entry.get('link')
        offset=8+header[1]+int(entry['offset']);assert offset+entry['size']<=path.stat().st_size
        stream.seek(offset);return stream.read(entry['size']).decode('utf8')


def private_launch_source(location,destination,env):
    asar=location/'files/teams-for-linux/resources/app.asar'
    index=asar_source(asar,'app/index.js');background=asar_source(asar,'app/backgroundPortal/index.js')
    pin=re.search(r"const (\w+) = app\.getPath\(['\"]userData['\"]\)",index)
    assert pin and re.search(r"app\.setPath\(['\"]userData['\"],\s*"+re.escape(pin[1])+r"\)",index),'Updated application changed the early native user-data path owner'
    e2e=re.search(r'if\s*\(process\.env\.E2E_USER_DATA_DIR\)\s*\{\s*app\.setPath\([\"\']userData[\"\'],\s*process\.env\.E2E_USER_DATA_DIR\);?\s*\}',index)
    assert e2e and e2e.end()<index.index('new AppConfiguration('),'Private E2E path must precede configuration creation'
    start=background.index('function isAutostartEnabled()');end=background.index('let contents',start);reader=background[start:end]
    assert re.search(r'os\.homedir\(\)\s*,\s*["\']\.config["\']\s*,\s*["\']autostart["\']',reader),'Updated native autostart intent reader changed'
    portal=portal_autostart();command=['/usr/bin/flatpak','run','--command=/usr/bin/stat',APPLICATION,'-Lc','%d %i',portal['path']]
    observed=subprocess.check_output(command,env=env,text=True).strip();assert observed==str(portal['device'])+' '+str(portal['inode'])
    result=dict(asar=str(asar),asar_sha256=c1.target.sha(asar),index_sha256=hashlib.sha256(index.encode()).hexdigest(),
                background_sha256=hashlib.sha256(background.encode()).hexdigest(),nativeDataPathPreserved=True,earlyPrivateE2E=e2e[0],
                autostartReader=reader,autostart=portal,visibilityCommand=command,visibility=observed)
    write_json(destination,result);return result


def update_cycle(build_record,destination,env):
    destination.mkdir(parents=True,exist_ok=True);private=dict(env)
    preparation=json.loads((WORK/'update/install-command.json').read_text())['environment']
    for key in ('FLATPAK_USER_DIR','XDG_CACHE_HOME','FLATPAK_SYSTEM_CACHE_DIR','TMPDIR'):private[key]=preparation[key]
    state,hooks=delivery.paths();assert not state.exists() and not any(p.exists() or p.is_symlink() for p in hooks.values())
    unit=AUTOSTART_UNIT
    runtime=Path(env['XDG_RUNTIME_DIR'])/'systemd/user'/(unit+'.d')/('70-fontreal-update-'+destination.name+'.conf')
    assert not runtime.exists() and not runtime.is_symlink()
    runtime_bytes=('[Service]\nEnvironment='+json.dumps('FLATPAK_USER_DIR='+private['FLATPAK_USER_DIR'])+'\n').encode()
    data=WORK/'update'/('ordinary-data-'+destination.name);data.mkdir(mode=0o700)
    marker=data/'synthetic-durable-marker';marker.write_text(os.urandom(32).hex()+'\n');marker_sha=c1.target.sha(marker)
    override=Path(private['FLATPAK_USER_DIR'])/'overrides'/APPLICATION;assert not override.exists() and not override.is_symlink()
    working_overrides=[Path.home()/'.local/share/flatpak/overrides'/APPLICATION,Path('/var/lib/flatpak/overrides')/APPLICATION]
    original_overrides={str(p):c1.target.sha(p) if p.is_file() else None for p in working_overrides}
    portal_before=portal_autostart();assert portal_before['enabled']
    commands=[];enabled=False;created_override=None;runtime_created=False;phase_view=None;host=None;host_marker=None;result=None
    def invoke(command,label,context=private):
        with (destination/(label+'.stdout')).open('w') as out,(destination/(label+'.stderr')).open('w') as err:
            result=subprocess.run(command,env=context,stdout=out,stderr=err)
        observation=dict(command=command,exit_code=result.returncode,stdout=label+'.stdout',stderr=label+'.stderr')
        commands.append(observation);write_json(destination/'commands.json',commands);assert result.returncode==0
        return (destination/(label+'.stdout')).read_text()
    def native_info(option):return subprocess.check_output(['/usr/bin/flatpak','info',option,APPLICATION],env=private,text=True).strip()
    def prestart(label):
        assert runtime.read_bytes()==runtime_bytes and c1.target.sha(override)==created_override
        output=subprocess.check_output(['systemctl','--user','show',unit,'-p','Environment','--value'],env=env,text=True)
        values=[item.split('=',1)[1] for item in shlex.split(output) if item.startswith('FLATPAK_USER_DIR=')]
        assert values==[private['FLATPAK_USER_DIR']],'Native unit did not select the exact private installation'
        command=['/usr/bin/flatpak','run','--command=/usr/bin/printenv',APPLICATION,'E2E_USER_DATA_DIR']
        observed=subprocess.check_output(command,env=private,text=True).strip()
        assert observed==str(data),'Private native application environment lacks the proven early E2E data path'
        write_json(destination/(label+'-prestart.json'),dict(unit=unit,privateInstallation=values[0],
                   runtimeFile=str(runtime),runtimeSha256=c1.target.sha(runtime),command=command,E2E_USER_DATA_DIR=observed))
    try:
        expected=json.loads(Path(json.loads(build_record.read_text())['spec']['c1_record']).read_text())['spec']['target_commit']
        before=dict(commit=native_info('--show-commit'),location=native_info('--show-location'),origin=native_info('--show-origin'),ref=native_info('--show-ref'))
        assert before['commit']==expected,'Private fixture must start from the genuine qualified official deployment'
        write_json(destination/'before.json',before)
        private_launch_source(Path(before['location']),destination/'old-source.json',private)
        invoke(['/usr/bin/flatpak','override','--user','--filesystem='+str(data)+':rw','--env=E2E_USER_DATA_DIR='+str(data),APPLICATION],'private-data-override')
        created_override=c1.target.sha(override)
        runtime.parent.mkdir(parents=True,exist_ok=True)
        with runtime.open('xb') as stream:stream.write(runtime_bytes)
        runtime_created=True
        subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
        prestart('qualification')
        output=invoke([sys.executable,'-B',str(ROOT/'tests/chromium_delivery_test.py'),'--target','teams','--case','actual-app','--build-record',str(build_record)],'private-actual-app')
        qualification=Path(output.splitlines()[0]);proof=json.loads((qualification/'report.json').read_text());assert proof['passed']
        emitted=Path(proof['build_record']);record=delivery.load_build(emitted);assert record['spec']['location']==before['location']
        host_stock=Path(subprocess.check_output(['/usr/bin/flatpak','info','--show-location',APPLICATION],env=env,text=True).strip())/'files'
        with ordinary_observer(None,destination/'host-normal-quit',env,host_stock/'teams-for-linux/teams-for-linux',host_stock,existing=True) as (inspector,identity,instance):
            host_data=Path(identity['data']);host_stat=host_data.stat()
            host_marker=host_data/('.fontreal-update-proof-'+os.urandom(12).hex());host_marker.write_text(os.urandom(32).hex())
            host=dict(data=str(host_data),device=host_stat.st_dev,inode=host_stat.st_ino,view=str(host_stock),instance=instance,
                      marker=str(host_marker),markerSha256=c1.target.sha(host_marker))
            assert host_data!=data
            working_text(inspector,destination/'host-baseline-text',env,host_stock/'teams-for-linux/teams-for-linux',proof,False)
            write_json(destination/'original-working-data.json',host)
        stock=Path(before['location'])/'files';stock_engine=stock/'teams-for-linux/teams-for-linux';phase_view=stock
        prestart('old-native')
        with ordinary_observer(['/usr/bin/flatpak','run',APPLICATION],destination/'old-native',private,stock_engine,stock,data) as (inspector,identity,instance):
            baseline=destination/'old-native/text';working_text(inspector,baseline,private,stock_engine,proof,False)
        invoke([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'enable','teams','--record',str(emitted)],'enable-private')
        enabled=True
        with patch.dict(os.environ,private):normal=delivery.builder.current_view(record)
        engine=normal/'teams-for-linux/teams-for-linux';phase_view=normal
        generated_autostart(destination/'old-selected-effective.json',Path('/usr/bin/gio'),env,hooks['autostart'])
        prestart('old-selected-autostart')
        with ordinary_observer(['systemctl','--user','start',unit],destination/'old-selected-autostart',private,engine,normal,data) as (inspector,identity,instance):
            assert c1.target.sha(marker)==marker_sha
            working_text(inspector,destination/'old-selected-autostart/text',private,engine,proof,True,baseline)
        print('private qualified old deployment: native autostart selected pixels/data passed',flush=True)
        invoke(['/usr/bin/flatpak','--user','update','--noninteractive','--assumeyes','--no-related',APPLICATION],'official-update')
        after=dict(commit=native_info('--show-commit'),location=native_info('--show-location'),origin=native_info('--show-origin'),ref=native_info('--show-ref'))
        assert after['commit']!=before['commit'] and after['location']!=before['location'] and after['origin']==before['origin'] and after['ref']==before['ref']
        write_json(destination/'after.json',after)
        private_launch_source(Path(after['location']),destination/'updated-source.json',private)
        status=json.loads(invoke([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'status','teams'],'updated-status'))
        assert status['enabled'] and status['compatibility'] is None,'Application update disabled the saved Fontreal engine'
        current=Path(after['location'])/'files';current_engine=current/'teams-for-linux/teams-for-linux';phase_view=current
        prestart('updated-native')
        with ordinary_observer(['/usr/bin/flatpak','run',APPLICATION],destination/'updated-native',private,current_engine,current,data) as (inspector,identity,instance):
            updated_baseline=destination/'updated-native/text';working_text(inspector,updated_baseline,private,current_engine,proof,False)
        with patch.dict(os.environ,private):updated_view=delivery.builder.current_view(record)
        updated_engine=updated_view/'teams-for-linux/teams-for-linux';phase_view=updated_view
        generated_autostart(destination/'updated-selected-effective.json',Path('/usr/bin/gio'),env,hooks['autostart'])
        prestart('updated-selected-autostart')
        with ordinary_observer(['systemctl','--user','start',unit],destination/'updated-selected-autostart',private,updated_engine,updated_view,data) as (inspector,identity,instance):
            assert c1.target.sha(marker)==marker_sha
            working_text(inspector,destination/'updated-selected-autostart/text',private,updated_engine,proof,True,updated_baseline)
        invoke([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'disable','teams'],'disable-private');enabled=False
        generated_autostart(destination/'updated-stock-effective.json',Path('/usr/bin/flatpak'),env)
        prestart('updated-stock-autostart')
        with ordinary_observer(['systemctl','--user','start',unit],destination/'updated-stock-autostart',private,current_engine,current,data) as (inspector,identity,instance):
            working_text(inspector,destination/'updated-stock-autostart/text',private,current_engine,proof,False,updated_baseline)
        assert c1.target.sha(marker)==marker_sha
        result=dict(passed=True,before=before,after=after,engineQualification=proof['report'],compatibility=status['compatibility'],
                    data=str(data),durableMarkerSha256=marker_sha,actualUpdatedSelected=True,stockReversal=True,
                    originalWorkingData=host,autostartClaim=True,commands=commands)
    finally:
        try:
            if phase_view is not None and any(row['info']['appPath']==str(phase_view) for row in native_instances(private)):
                with ordinary_observer(None,destination/'private-normal-recovery-quit',private,phase_view/'teams-for-linux/teams-for-linux',phase_view,data,existing=True):pass
        finally:
            if enabled:invoke([sys.executable,'-B',str(ROOT/'tools/chromium_delivery.py'),'disable','teams'],'failure-disable-private')
            if runtime_created:
                assert runtime.read_bytes()==runtime_bytes;runtime.unlink()
            if override.exists():
                assert created_override is not None and c1.target.sha(override)==created_override
                invoke(['/usr/bin/flatpak','override','--user','--reset',APPLICATION],'remove-private-data-override')
            assert not state.exists() and not any(p.exists() for p in hooks.values())
            assert {str(p):c1.target.sha(p) if p.is_file() else None for p in working_overrides}==original_overrides
            assert portal_autostart()['enabled']==portal_before['enabled']
            subprocess.run(['systemctl','--user','daemon-reload'],env=env,check=True)
            subprocess.run(['systemctl','--user','start',unit],env=env,check=True)
            if host is not None:
                deadline=time.monotonic()+30
                while not any(row['info']['appPath']==host['view'] for row in native_instances(env)):
                    assert time.monotonic()<deadline,'Original host stock did not restore normally'
                    time.sleep(.1)
                host_view=Path(host['view']);host_engine=host_view/'teams-for-linux/teams-for-linux'
                with ordinary_observer(None,destination/'host-stock-return',env,host_engine,host_view,Path(host['data']),existing=True) as (inspector,identity,instance):
                    stat=Path(identity['data']).stat()
                    assert (stat.st_dev,stat.st_ino)==(host['device'],host['inode']) and c1.target.sha(host_marker)==host['markerSha256']
                    working_text(inspector,destination/'host-stock-return/text',env,host_engine,proof,False,destination/'host-baseline-text')
                assert c1.target.sha(host_marker)==host['markerSha256'];host_marker.unlink();host_marker=None
                subprocess.run(['systemctl','--user','start',unit],env=env,check=True)
                deadline=time.monotonic()+30
                while not any(row['info']['appPath']==host['view'] for row in native_instances(env)):
                    assert time.monotonic()<deadline;time.sleep(.1)
            write_json(destination/'cleanup.json',dict(ownedRuntimeRemoved=not runtime.exists(),privateOverrideRemoved=not override.exists(),
                       hooksRemoved=not state.exists(),workingOverridesPreserved=True,hostStockRestored=True,
                       hostOriginalDataAndPixelsReobserved=host is not None,hostMarkerRemoved=host_marker is None))
    if result is not None:write_json(destination/'report.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--target',choices=['teams','bitwarden'],required=True)
    parser.add_argument('--case',choices=['actual-app','lifecycle','update-cycle'],required=True);parser.add_argument('--build-record',type=Path,required=True)
    args=parser.parse_args()
    if args.target=='bitwarden' and args.case=='update-cycle':parser.error('Bitwarden update-cycle is not supported.')
    OUT.mkdir(parents=True,exist_ok=True)
    destination=Path(tempfile.mkdtemp(prefix=args.case+'-',dir=OUT));print(destination,flush=True)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str((ROOT/'build').resolve()))
    try:
        if args.target=='bitwarden':
            from bitwarden_pixels_test import actual_app as bitwarden_actual_app
            from bitwarden_delivery_test import lifecycle as bitwarden_lifecycle
            {'actual-app':bitwarden_actual_app,'lifecycle':bitwarden_lifecycle}[args.case](args.build_record.resolve(),destination,env)
        else:{'actual-app':actual_app,'lifecycle':lifecycle,'update-cycle':update_cycle}[args.case](args.build_record.resolve(),destination,env)
    except BaseException as error:
        write_json(destination/'failure.json',dict(passed=False,errorClass=type(error).__name__,message=str(error)))
        raise


if __name__=='__main__':main()
