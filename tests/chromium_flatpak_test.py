#!/usr/bin/env python3
"""Inspect exact target identities before claiming renderer coverage."""
import argparse
import configparser
import ctypes
import math
import mmap
import os
import json
from pathlib import Path
import sys
import shutil
import select
import socket
import struct
import subprocess
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import chromium_flatpak as target

WORK=(ROOT/'build/chromium-flatpak').resolve()
OUT=(ROOT/'results/chromium-flatpak').resolve()
PINS=dict(electron='44.9.0',electron_commit='fd148b9908b83c8dc09924e45e6df44b83b6bfe7',
          chromium='152.0.7977.167',skia='747cf654ed6f864f4402e7d6eb54a6ede60141e5',
          depot_tools='ec77017fb3e090ff02bffb9c6980ebcdd3006ddc')
FONTS={'Noto Sans':Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'),
       'Hack':Path('/usr/share/fonts/truetype/hack/Hack-Regular.ttf'),
       'Nimbus Sans':Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf')}


def owners():
    rows=target.owners()
    assert len(rows)==4 and {r['target'] for r in rows}=={'edge','teams','bitwarden','telegram'}
    assert all(r['status']=='installed' and r['backend']=='unknown' and not r['backend_observed'] for r in rows)
    by_name={r['target']:r for r in rows}
    assert by_name['edge']['version']=='157.0.4341.46-1'
    assert by_name['teams']['runtime']==by_name['bitwarden']['runtime']
    assert by_name['teams']['commit']!=by_name['bitwarden']['commit']
    assert by_name['teams']['binary']['electron_fuses']['run_as_node'] is True
    assert by_name['bitwarden']['binary']['electron_fuses']['run_as_node'] is False
    assert 'zypak-wrapper' in by_name['teams']['launch_script']
    assert 'PROCESS_ISOLATION_LD_PRELOAD' in by_name['bitwarden']['launch_script']
    assert by_name['telegram']['qt']['shared'] is False
    assert 'libfreetype.so.6' in by_name['telegram']['binary']['dependencies']
    assert not any('libQt6' in d for d in by_name['telegram']['binary']['dependencies'])
    for name in target.TARGETS:
        row=by_name[name]; application=row['application']
        location=Path(target.run(['flatpak','info','--show-location',application]))
        assert target.sha(location/'files/manifest.json')==row['manifest_sha256']
        assert target.run(['flatpak','info','--show-commit',application])==row['commit']
        metadata=configparser.ConfigParser(interpolation=None);metadata.read(location/'metadata')
        assert metadata['Application']['runtime']==row['runtime']
        assert metadata['Application']['command']==row['command']
    return rows


def build_record(path=None):
    candidates=[Path(path)] if path else list((WORK/'artifacts').glob('*/build.json'))
    matching=[]
    for candidate in candidates:
        record=json.loads(candidate.read_text()); spec=record['spec']
        if all(spec['pins'].get(k)==v for k,v in PINS.items()) and all(
                spec.get(k)==target.sha(ROOT/name) for k,name in (
                    ('recipe','tools/build-electron.py'),('patch','patches/skia-747cf654-fontreal-trace.patch'),
                    ('header','tests/skia_owner_trace.h'))):
            matching.append((candidate,record))
    assert len(matching)==1, 'Need one completed matching build.json; use --build-record with the builder final path'
    path,record=matching[0]
    assert path.resolve().is_relative_to(WORK), 'Build record must stay below the configured build root'
    assert all(Path(record[key]).resolve().is_relative_to(WORK) for key in ('source','source_view'))
    checkout=Path(record['source']).resolve().parent
    identity=record['source_identity']
    assert identity==json.loads((checkout/'.fontreal-source.json').read_text()), 'Build source identity differs from the prepared receipt'
    assert identity['pins']==record['spec']['pins']==PINS, 'Build source pins differ from the exact engine specification'
    heads={name:subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout/name,text=True).strip()
           for name in ('src','src/electron','src/third_party/skia')}
    observed=dict(pins=PINS,heads=heads,configuration=target.sha(checkout/'.gclient'),entries=target.sha(checkout/'.gclient_entries'))
    assert observed==identity, 'Live source HEADs or gclient configuration differ from the build source identity'
    assert heads['src/electron']==PINS['electron_commit']
    subprocess.run(['git','merge-base','--is-ancestor',PINS['skia'],heads['src/third_party/skia']],
                   cwd=checkout/'src/third_party/skia',check=True)
    depot_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=WORK/'depot_tools',text=True).strip()
    assert depot_head==PINS['depot_tools'], 'Live depot_tools HEAD differs from its exact pin'
    required_cache=set('''GIT_CACHE_PATH VPYTHON_VIRTUALENV_ROOT CIPD_CACHE_DIR XDG_CACHE_HOME CARGO_HOME
                          RUSTUP_HOME TMPDIR PIP_CACHE_DIR NPM_CONFIG_CACHE npm_config_cache
                          YARN_GLOBAL_FOLDER COREPACK_HOME CLANG_MODULE_CACHE_PATH'''.split())
    cache_environment=record['cache_environment']; cache_root=(WORK/'cache').resolve()
    assert set(cache_environment)==required_cache, 'Build cache environment is incomplete or changed'
    assert cache_root.is_relative_to(WORK)
    assert all(Path(value).resolve().is_relative_to(cache_root) and Path(value).is_dir()
               for value in cache_environment.values()), 'A recorded build cache is absent or outside WORK/cache'
    for role in ('stock','instrumented'):
        package=record['packages'][role]; payload=Path(package['directory']).resolve()
        archive=Path(package['archive']).resolve()
        assert payload.is_relative_to(WORK) and archive.is_relative_to(WORK)
        assert target.sha(archive)==package['archive_sha256'], f'{role} archive changed'
        files={str(p.relative_to(payload)):target.sha(p) for p in payload.rglob('*') if p.is_file()}
        assert files==package['files'], f'{role} distribution changed'
        binary=payload/'electron'
        assert binary.is_file() and os.access(binary,os.X_OK)
        with binary.open('rb') as stream, mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
            assert (data.find(b'FONTREAL_SKIA {')>=0)==(role=='instrumented'), f'{role} trace discriminator failed'
    return path.resolve(),record


def glyph_ids(font,characters="m8Wg"):
    # Opaque FreeType handles provide only the independent cmap, never a mask oracle.
    ft=ctypes.CDLL('libfreetype.so.6'); handle=ctypes.c_void_p(); face=ctypes.c_void_p()
    ft.FT_Init_FreeType.argtypes=[ctypes.POINTER(ctypes.c_void_p)]
    ft.FT_New_Face.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_long,ctypes.POINTER(ctypes.c_void_p)]
    ft.FT_Get_Char_Index.argtypes=[ctypes.c_void_p,ctypes.c_ulong];ft.FT_Get_Char_Index.restype=ctypes.c_uint
    ft.FT_Done_Face.argtypes=[ctypes.c_void_p];ft.FT_Done_FreeType.argtypes=[ctypes.c_void_p]
    assert ft.FT_Init_FreeType(ctypes.byref(handle))==0
    try:
        assert ft.FT_New_Face(handle,os.fsencode(font),0,ctypes.byref(face))==0
        try:
            result={char:ft.FT_Get_Char_Index(face,ord(char)) for char in characters}
            assert all(result.values()) and len(set(result.values()))==len(set(characters))
            return result
        finally:ft.FT_Done_Face(face)
    finally:ft.FT_Done_FreeType(handle)



class StderrCollector:
    def __init__(self,destination):
        self.destination=destination
        self.receiver,self.sender=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM)
        self.receiver.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
        self.receiver.settimeout(.1)
        self.stop=threading.Event();self.error=None;self.rows=[]
        self.thread=threading.Thread(target=self.collect,name='fixture-stderr',daemon=True)

    def __enter__(self):
        self.thread.start();return self

    def check(self):
        if self.error:raise RuntimeError(f'Stderr collector failed: {self.error}') from self.error

    def collect(self):
        try:
            pending={};offset=0
            with (self.destination/'stderr.log').open('wb') as raw, (self.destination/'stderr-credentials.jsonl').open('w') as index:
                while True:
                    try:data,ancillary,flags,_=self.receiver.recvmsg(1<<20,socket.CMSG_SPACE(struct.calcsize('3i')))
                    except socket.timeout:
                        if self.stop.is_set():break
                        continue
                    assert not flags & (socket.MSG_TRUNC|socket.MSG_CTRUNC), 'Truncated stderr payload or credentials'
                    credentials=[value for level,kind,value in ancillary if level==socket.SOL_SOCKET and kind==socket.SCM_CREDENTIALS]
                    assert len(credentials)==1 and len(credentials[0])==struct.calcsize('3i'), 'Missing or malformed stderr sender credentials'
                    pid,uid,gid=struct.unpack('3i',credentials[0]);assert pid>0, 'Invalid kernel stderr sender PID'
                    raw.write(data)
                    index.write(json.dumps(dict(offset=offset,length=len(data),hostPid=pid,uid=uid,gid=gid))+'\n')
                    offset+=len(data)
                    fragments=(pending.get(pid,b'')+data).split(b'\n');pending[pid]=fragments.pop()
                    assert len(pending[pid])<=1<<20, 'Unbounded incomplete stderr line'
                    for line in fragments:
                        if b'FONTREAL_SKIA ' in line:
                            payload=json.loads(line.split(b'FONTREAL_SKIA ',1)[1])
                            assert isinstance(payload,dict) and isinstance(payload.get('pid'),int), 'Malformed trace record'
                            self.rows.append(dict(hostPid=pid,payload=payload))
                assert not any(b'FONTREAL_' in tail for tail in pending.values()), 'Incomplete trace record at end of stderr'
        except Exception as error:self.error=error

    def __exit__(self,*exception):
        self.sender.close();self.stop.set();self.thread.join(timeout=5)
        self.receiver.close()
        if self.thread.is_alive():self.thread.join(timeout=1)
        assert not self.thread.is_alive(), 'Stderr collector thread did not stop'
        self.check()


def renderer_rows(rows,host_pid,trace_pid):
    return [entry['payload'] for entry in rows if entry['hostPid']==host_pid and entry['payload']['pid']==trace_pid]


def collector_selfcheck(destination):
    destination.mkdir();children=[]
    payload=dict(pid=1,synthetic=True,source='S2a SYNTHETIC identical payload')
    line='FONTREAL_SKIA '+json.dumps(payload)+'\n'
    script="""import os,sys
payload=sys.argv[1].encode();split=len(payload)//2
os.write(2,payload[:split]);print('ready',flush=True)
assert sys.stdin.buffer.readline()==b'go\\n'
os.write(2,payload[split:])
"""
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(WORK/'cache/tmp'))
    with StderrCollector(destination) as collector:
        try:
            for _ in range(2):
                child=subprocess.Popen([sys.executable,'-c',script,line],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                       stderr=collector.sender,env=env,cwd=WORK)
                children.append(child)
                assert select.select([child.stdout],[],[],5)[0], 'Synthetic child ready barrier timed out'
                assert child.stdout.readline()==b'ready\n', 'Synthetic child did not send its first fragment'
                collector.check()
            collector.sender.close()
            for child in children:child.stdin.write(b'go\n');child.stdin.flush()
            for child in children:assert child.wait(timeout=10)==0
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                    try:child.wait(timeout=5)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
                child.stdin.close();child.stdout.close()
    pids=[child.pid for child in children]
    assert sorted(entry['hostPid'] for entry in collector.rows)==sorted(pids)
    assert all(entry['payload']==payload for entry in collector.rows)
    messages=[json.loads(line) for line in (destination/'stderr-credentials.jsonl').read_text().splitlines()]
    assert len(messages)==4 and [entry['hostPid'] for entry in messages[:2]]==pids, 'Synthetic fragments did not interleave'
    assert renderer_rows(collector.rows,pids[0],1)==[payload]
    foreign=[entry for entry in collector.rows if entry['hostPid']==pids[1]]
    assert not renderer_rows(foreign,pids[0],1), 'Foreign identical-payload evidence passed renderer selection'
    assert not renderer_rows(collector.rows,pids[0],2), 'Wrong namespace payload PID passed renderer selection'
    result=dict(synthetic=True,knownChildPids=pids,rows=collector.rows,interleavedFragments=messages)
    (destination/'selfcheck.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS S2a kernel sender credentials and interleaved synthetic trace isolation',flush=True)
    return result


def trace_evidence(rows,host_pid,pid,family,ids):
    rows=renderer_rows(rows,host_pid,pid)
    evidence={}
    for char,glyph in ids.items():
        matches=[(i,row) for i,row in enumerate(rows) if row['pid']==pid and row['glyph']==glyph
                 and row['size']==15 and bytes.fromhex(row['family']).decode('utf-8')==family]
        for _,raster in matches:
            if raster['owner'] not in ('path-raster','direct-path-raster') or not raster['width'] or not raster['height']:
                continue
            same=[row for _,row in matches if row['font']==raster['font']]
            required={'fontations-metrics','fontations-image'} if raster['owner']=='path-raster' else {'fontations-metrics'}
            if not required <= {row['owner'] for row in same}:continue
            assert all(k in raster for k in ('flags','hinting','format','left','top','preblend','mask'))
            if raster['mask']:
                assert len(bytes.fromhex(raster['mask']))==raster['width']*raster['height']
            evidence[char]=dict(hostPid=host_pid,glyph=glyph,font=raster['font'],raster=raster,
                                owners=sorted({row['owner'] for row in same}))
            break
        assert char in evidence, f'Unknown owner: no positive matching metrics/image/base raster for {family} {char}'
    prefix_positions=[i for i,r in enumerate(rows) if r['pid']==pid and r['font'] in {evidence[c]['font'] for c in 'm8W'}
                      and r['glyph'] in {ids[c] for c in 'm8W'} and r['owner'] in ('path-raster','direct-path-raster')]
    later_positions=[i for i,r in enumerate(rows) if r['pid']==pid and r['font']==evidence['g']['font']
                     and r['glyph']==ids['g'] and r['owner'] in ('path-raster','direct-path-raster')]
    assert min(prefix_positions)<min(later_positions), 'Distinct later glyph did not follow the prefix raster'
    return evidence


def sandbox_evidence(identity,user_data,main_pid):
    measurement=identity['measurement']; preferences=identity['preferences']
    assert measurement['sandboxed'] is True and measurement['contextIsolated'] is True
    assert preferences['sandbox'] is True and preferences['contextIsolation'] is True and preferences['nodeIntegration'] is False
    assert identity['page']==dict(require='undefined',process='undefined')
    assert Path(identity['userData']).resolve()==user_data.resolve()
    assert identity['mainPid']==main_pid, 'Reported main PID differs from the launched Electron process'
    pid=identity['rendererPid']; assert pid!=main_pid and pid>0
    status=dict(line.split(':',1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
    namespace_pids=[int(value) for value in status['NSpid'].split()]
    assert namespace_pids and namespace_pids[0]==pid and all(value>0 for value in namespace_pids), namespace_pids
    processes={}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():continue
        try:
            metadata={key:value.strip() for line in (entry/'status').read_text().splitlines()
                      if ':' in line for key,value in [line.split(':',1)] if key in ('PPid','NSpid','Name')}
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
        processes[int(entry.name)]=dict(pid=int(entry.name),parentPid=int(metadata['PPid']),
                                       namespacePids=[int(value) for value in metadata.get('NSpid','').split()],name=metadata['Name'])
    assert main_pid in processes, 'Launched Electron main process disappeared during owner observation'
    owned={main_pid}
    while True:
        descendants={key for key,row in processes.items() if row['parentPid'] in owned}
        if descendants <= owned:break
        owned.update(descendants)
    assert pid in owned, 'Observed renderer is not a descendant of the launched Electron main process'
    mapping=[processes[key] for key in sorted(owned)]
    assert all(row['namespacePids'] and row['namespacePids'][0]==row['pid'] and
               all(value>0 for value in row['namespacePids']) for row in mapping), 'Incomplete owned-process NSpid mapping'
    assert processes[pid]['namespacePids']==namespace_pids, 'Renderer NSpid mapping changed during observation'
    assert status['Seccomp'].strip()=='2' and status['NoNewPrivs'].strip()=='1'
    caps={k:v.strip() for k,v in status.items() if k.startswith('Cap')}
    required_caps={'CapInh','CapPrm','CapEff','CapBnd','CapAmb'}
    assert required_caps <= set(caps) and all(len(caps[key])==16 and all(c in '0123456789abcdefABCDEF' for c in caps[key]) for key in required_caps), caps
    assert all(int(caps[key],16)==0 for key in required_caps-{'CapBnd'}), caps
    command=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    assert any(b'--type=renderer' in argument.split() for argument in command), command
    assert not any(b'no-sandbox' in arg or b'disable-seccomp' in arg or b'disable-setuid-sandbox' in arg for arg in command)
    return dict(hostPid=pid,tracePid=namespace_pids[-1],namespacePids=namespace_pids,ownedPidMapping=mapping,
                Seccomp=2,NoNewPrivs=1,capabilities=caps,command=[os.fsdecode(a) for a in command if a])



def painted_text(image,measurement,background):
    result={}
    prefix=measurement['prefix'];later=measurement['later']
    assert prefix['x']+prefix['width']==later['x'] and later['width']>0
    for key in ('prefix','later'):
        rect=measurement[key]
        box=(math.floor(rect['x']),math.floor(rect['y']),math.ceil(rect['x']+rect['width']),math.ceil(rect['y']+rect['height']))
        if key=='later':
            # Require ink inside the later glyph, beyond possible prefix overhang.
            box=(max(math.ceil(prefix['x']+prefix['width'])+2,math.ceil(rect['x']+rect['width']/3)),box[1],box[2],box[3])
        assert 0<=box[0]<box[2]<=image.width and 0<=box[1]<box[3]<=image.height
        ink=[(x,y) for y in range(box[1],box[3]) for x in range(box[0],box[2]) if image.getpixel((x,y))[:3]!=background]
        assert len({x for x,y in ink})>=2 and len({y for x,y in ink})>=3, f'{key} glyph region is empty or contains only prefix overhang'
        result[key]=dict(box=box,paintedPixels=len(ink))
    return result


def window_pixels(masks,env,identity,capture,destination,palette,collector):
    from PIL import Image
    native=Image.open(capture);measurement=identity['measurement']
    assert native.mode in ('RGB','RGBA')
    assert measurement['dpr']==1 and measurement['fontLoaded'] and measurement['text']=='m8Wm8Wg'
    assert native.size==(measurement['width'],measurement['height'])==(480,220)
    assert measurement['marker']==dict(x=16,y=16,width=8,height=8)
    assert measurement['control']==dict(x=40,y=16,width=18,height=18)
    background_box=(240,110,248,118)
    native_bg=native.getpixel(background_box[:2])[:3]
    assert {pixel[:3] for pixel in native.crop(background_box).getdata()}=={native_bg}, 'Native interior background is not solid'
    marker_rgb=native.getpixel((16,16))[:3];control_rgb=native.getpixel((40,16))[:3]
    assert len({marker_rgb,control_rgb,native_bg})==3
    assert {pixel[:3] for pixel in native.crop((16,16,24,24)).getdata()}=={marker_rgb}, 'Native marker is incomplete'
    assert sum(pixel[:3]==marker_rgb for pixel in native.getdata())==64, 'Native marker is not unique'
    assert {pixel[:3] for pixel in native.crop((40,16,58,34)).getdata()}=={control_rgb}, 'Native control is incomplete'
    native_text=painted_text(native,measurement,native_bg)
    source_bg=(32,33,36) if palette=='dark' else (255,255,255)
    deadline=time.monotonic()+10
    while True:
        collector.check()
        root=masks.screenshot(env,destination/'root.png')
        try:
            points=[(i%root.width,i//root.width) for i,pixel in enumerate(root.getdata()) if pixel==(17,91,143)]
            assert len(points)==64, 'OS marker is absent, incomplete or not unique'
            x=min(point[0] for point in points)-16;y=min(point[1] for point in points)-16
            assert 0<=x and 0<=y and x+480<=root.width and y+220<=root.height, 'OS content crop is out of bounds'
            crop=root.crop((x,y,x+480,y+220))
            assert set(crop.crop((16,16,24,24)).getdata())=={(17,91,143)}, 'OS marker geometry is incomplete'
            assert set(crop.crop((40,16,58,34)).getdata())=={(53,89,131)}, 'OS control geometry is incomplete'
            assert set(crop.crop(background_box).getdata())=={source_bg}, 'OS interior background does not match the palette'
            window_text=painted_text(crop,measurement,source_bg)
            break
        except AssertionError as error:
            if time.monotonic()>=deadline:raise AssertionError(f'Actual OS fixture did not finish painting: {error}') from error
            time.sleep(.1)
    crop.save(destination/'window.png')
    return dict(contentOrigin=[x,y],size=list(native.size),
                native=dict(markerRGB=marker_rgb,controlRGB=control_rgb,backgroundRGB=native_bg,text=native_text,
                            mode=native.mode,iccProfileBytes=len(native.info.get('icc_profile',b'')),sha256=target.sha(capture)),
                window=dict(markerRGB=[17,91,143],controlRGB=[53,89,131],backgroundRGB=source_bg,text=window_text,
                            sha256=target.sha(destination/'window.png')))


def fixture_run(masks,env,package,role,family,font,palette,destination,state):
    destination.mkdir();state.mkdir(); user_data=state/'user-data';user_data.mkdir()
    copied=state/font.name;shutil.copyfile(font,copied)
    assert target.sha(copied)==target.sha(font)
    config=dict(userData=str(user_data),font=str(copied),palette=palette,
                capture=str(destination/'native.png'),ready=str(destination/'ready.json'),quit=str(state/'quit'))
    config_path=state/'config.json';config_path.write_text(json.dumps(config))
    launch_env={k:v for k,v in env.items() if not k.startswith('FONTREAL_') and k not in
                ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','ELECTRON_RUN_AS_NODE','ELECTRON_NO_SANDBOX')}
    for key in ('CONFIG','CACHE','DATA','STATE'):
        path=state/key.lower();path.mkdir();launch_env[f'XDG_{key}_HOME']=str(path)
    temporary=state/'tmp';temporary.mkdir()
    launch_env.update(FONTREAL_FIXTURE_CONFIG=str(config_path),FONTREAL_SKIA_TRACE='1',TMPDIR=str(temporary),
                      NPM_CONFIG_CACHE=str(state/'npm'),PYTHONDONTWRITEBYTECODE='1')
    helper=Path('/opt/microsoft/msedge/msedge-sandbox')
    if helper.is_file() and helper.stat().st_uid==0 and helper.stat().st_mode&0o4777==0o4755:
        launch_env['CHROME_DEVEL_SANDBOX']=str(helper)
    else:launch_env.pop('CHROME_DEVEL_SANDBOX',None)
    command=[str(Path(package['directory'])/'electron'),str(ROOT/'tests/electron_owner_fixture'),'--ozone-platform=wayland']
    with StderrCollector(destination) as collector, (destination/'stdout.log').open('w') as stdout:
        child=subprocess.Popen(command,env=launch_env,stdout=stdout,stderr=collector.sender)
        collector.sender.close()
        try:
            deadline=time.monotonic()+60
            while not Path(config['ready']).is_file():
                collector.check()
                assert child.poll() is None, f'{role} fixture exited; see {destination}/stderr.log'
                assert time.monotonic()<deadline, f'{role} fixture timed out; see {destination}/stderr.log'
                time.sleep(.1)
            identity=json.loads(Path(config['ready']).read_text())
            assert identity['versions']['electron']==PINS['electron'] and identity['versions']['chrome']==PINS['chromium'], identity['versions']
            sandbox=sandbox_evidence(identity,user_data,child.pid)
            pixels=window_pixels(masks,launch_env,identity,Path(config['capture']),destination,palette,collector)
            Path(config['quit']).touch();assert child.wait(timeout=20)==0
        finally:
            if child.poll() is None:
                Path(config['quit']).touch()
                try:child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try:child.wait(timeout=5)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    rows=collector.rows
    ids=glyph_ids(copied)
    evidence=trace_evidence(rows,sandbox['hostPid'],sandbox['tracePid'],family,ids) if role=='instrumented' else {}
    if role=='stock':assert not rows, 'Stock fixture emitted instrumentation'
    result=dict(role=role,family=family,palette=palette,font=str(font),font_sha256=target.sha(copied),glyphs=ids,
                identity=identity,sandbox=sandbox,pixels=pixels,backend='fontations/base-path' if evidence else 'unknown',trace=evidence)
    (destination/'evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def stock_fixture(record_path=None):
    from PIL import Image
    import browser_masks_test as masks
    WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    destination=Path(tempfile.mkdtemp(prefix='stock-fixture-',dir=OUT))
    command=[sys.executable,str(ROOT/'tools/build-electron.py')]
    builder_env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(WORK/'cache/tmp'))
    builder=dict(command=command,cwd=str(ROOT),environment={key:builder_env[key] for key in ('PYTHONDONTWRITEBYTECODE','TMPDIR')})
    (destination/'builder-command.json').write_text(json.dumps(builder,indent=2)+'\n')
    with (destination/'builder-stdout.log').open('w') as stdout, (destination/'builder-stderr.log').open('w') as stderr:
        subprocess.run(command,cwd=ROOT,env=builder_env,stdout=stdout,stderr=stderr,check=True)
    lines=(destination/'builder-stdout.log').read_text().splitlines()
    assert lines, f'Builder emitted no build record; see {destination}/builder-stdout.log'
    emitted=Path(lines[-1])
    assert emitted.is_absolute() and emitted.name=='build.json', f'Builder did not finish with a build.json path: {lines[-1]}'
    if record_path is not None:
        assert emitted.resolve()==Path(record_path).resolve(), f'Builder emitted {emitted}, which differs from requested --build-record {record_path}'
    record_path,record=build_record(emitted)
    masks.WORK=WORK;masks.OUT=destination
    sender_check=collector_selfcheck(destination/'sender-selfcheck')
    results=[]
    with tempfile.TemporaryDirectory(prefix='fixture-state-',dir=WORK) as temporary:
        with masks.nested_display() as env:
            for family,font in FONTS.items():
                for palette in ('light','dark'):
                    condition=destination/(font.stem+'-'+palette);condition.mkdir()
                    pair=[]
                    for role in ('stock','instrumented'):
                        pair.append(fixture_run(masks,env,record['packages'][role],role,family,font,palette,
                                                condition/role,Path(temporary)/(font.stem+'-'+palette+'-'+role)))
                    with Image.open(condition/'stock/window.png') as stock, Image.open(condition/'instrumented/window.png') as instrumented:
                        assert stock.mode==instrumented.mode=='RGB' and stock.size==instrumented.size==(480,220)
                        assert stock.tobytes()==instrumented.tobytes(), f'{family} {palette}: passive instrumentation changed actual OS-window pixels'
                    assert (condition/'stock/native.png').read_bytes()==(condition/'instrumented/native.png').read_bytes(), f'{family} {palette}: passive instrumentation changed native PNG bytes'
                    assert pair[0]['identity']['measurement']==pair[1]['identity']['measurement']
                    assert pair[0]['font_sha256']==pair[1]['font_sha256']
                    results.extend(pair)
                    print(f'PASS exact Teams engine stock/instrumented {family} 15px {palette}; real window identity and sandbox',flush=True)
    report=dict(builder=builder,build_record=str(record_path),build_record_sha256=target.sha(record_path),spec=record['spec'],
                source_identity=record['source_identity'],cache_environment=record['cache_environment'],
                scope='exact-engine fixture only; installed application backend coverage remains unknown',sender_selfcheck=sender_check,conditions=results)
    (destination/'stock-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
    print(destination/'stock-fixture.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('owners','stock-fixture'),required=True)
    parser.add_argument('--target',choices=('teams',))
    parser.add_argument('--build-record',type=Path,help='Completed build-electron.py build.json (auto-detected if unique)')
    args=parser.parse_args()
    if args.case=='stock-fixture':
        if args.target!='teams':parser.error('--target teams is required for stock-fixture')
        stock_fixture(args.build_record)
    else:
        OUT.mkdir(parents=True,exist_ok=True)
        rows=owners();(OUT/'owners.json').write_text(json.dumps(rows,indent=2)+'\n')
        print('PASS exact four-target owner inventory; backend coverage remains unknown')


if __name__=='__main__':main()
