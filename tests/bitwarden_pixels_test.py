"""Qualify independent glyph pixels in the secured packaged Bitwarden input."""
import base64
import ctypes as C
import ctypes.util
import hashlib
import io
import json
import math
import re
import secrets
import socket
import struct
import subprocess
import sys
from unittest.mock import patch
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
import browser_masks_test as masks
import chromium_delivery_test as shared
import chromium_flatpak_test as trace
import bitwarden_delivery_test as app


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def blob(archive,name):
    with archive.open('rb') as stream:
        header=struct.unpack('<4I',stream.read(16));assert 0<header[3]<=16*1024*1024
        entry=json.loads(stream.read(header[3]))
        for part in name.split('/'):entry=entry['files'][part]
        assert not entry.get('unpacked') and not entry.get('link')
        offset=8+header[1]+int(entry['offset']);assert offset+entry['size']<=archive.stat().st_size
        stream.seek(offset);return stream.read(entry['size'])


def font_input(files,destination):
    packed=blob(files/'Bitwarden/resources/app.asar','fonts/inter.c504db5c06caaf7cdfba.woff2')
    digest=hashlib.sha256(packed).hexdigest();assert digest=='693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3'
    ft=C.CDLL(C.util.find_library('freetype'));library=C.c_void_p();face=C.c_void_p();hold=C.create_string_buffer(packed)
    assert ft.FT_Init_FreeType(C.byref(library))==0
    ft.FT_New_Memory_Face.argtypes=[C.c_void_p,C.c_void_p,C.c_long,C.c_long,C.POINTER(C.c_void_p)]
    ft.FT_Load_Sfnt_Table.argtypes=[C.c_void_p,C.c_ulong,C.c_long,C.c_void_p,C.POINTER(C.c_ulong)]
    try:
        assert ft.FT_New_Memory_Face(library,hold,len(packed),0,C.byref(face))==0
        size=C.c_ulong();assert ft.FT_Load_Sfnt_Table(face,0,0,None,C.byref(size))==0 and 0<size.value<16*1024*1024
        memory=(C.c_ubyte*size.value)();assert ft.FT_Load_Sfnt_Table(face,0,0,memory,C.byref(size))==0
        sfnt=bytes(memory);assert sfnt[:4]==b'\0\1\0\0' and len(sfnt)==struct.unpack_from('>I',packed,16)[0]
    finally:
        if face.value:ft.FT_Done_Face(face)
        ft.FT_Done_FreeType(library)
    path=destination/'Inter.ttf';path.write_bytes(sfnt)
    result=dict(woff2_sha256=digest,sfnt_sha256=hashlib.sha256(sfnt).hexdigest(),font=str(path),conversion='FT_Load_Sfnt_Table tag0; no glyph rendering')
    write(destination/'font.json',result);return result


def collector(destination):
    result=trace.StderrCollector(destination,trace_only=True);result.receiver.close()
    result.receiver=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
    address='fontreal-c6-'+secrets.token_hex(8);result.receiver.bind('\0'+address)
    result.receiver.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1);result.receiver.settimeout(.1)
    return result,address


def colors(measure):
    def rgb(value):
        match=re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)',value);assert match,value
        return tuple(map(int,match.groups()))
    return rgb(measure['style']['color']),rgb(measure['style']['backgroundColor'])


def capture(endpoint,text,destination,env):
    output=subprocess.check_output(['node',ROOT/'tests/bitwarden_font_stage.mjs',endpoint,text],text=True)
    evidence=json.loads(output);native=Image.open(io.BytesIO(base64.b64decode(evidence.pop('screenshot'),validate=True))).convert('RGB')
    write(destination/'measurement-before-capture.json',evidence)
    measure=evidence['measure'];assert measure['text']==text and measure['dpr']==1 and measure['blurred'] and measure['scrollLeft']==0
    style=measure['style'];assert style['fontSize']=='14px' and style['fontWeight']=='400' and style['fontStyle']=='normal'
    assert style['fontOpticalSizing']=='auto' and style['fontVariationSettings']=='normal' and style['transform']=='none' and style['opacity']=='1' and style['filter']=='none'
    if text:assert evidence['fonts']['fonts'] and all(f['isCustomFont'] and f['familyName']=='Inter Variable' and f['postScriptName']=='InterVariable' for f in evidence['fonts']['fonts'])
    width,height=measure['viewport'];assert native.size==(width,height)
    tree=subprocess.check_output(['xwininfo','-root','-tree'],env=env,text=True)
    identifiers=[match.group(1) for match in re.finditer(r'^\s*(0x[0-9a-fA-F]+)\s+"([^"]*)":',tree,re.M) if match.group(2)==measure['title']]
    matches=[];candidates=[]
    root_path=destination/'root-temporary.png';root=masks.screenshot(env,root_path);assert root.size==(1600,1400)
    for identifier in identifiers:
        info=subprocess.check_output(['xwininfo','-id',identifier],env=env,text=True)
        if 'Map State: IsViewable' not in info:continue
        values={key:int(re.search(pattern,info).group(1)) for key,pattern in (
            ('x',r'Absolute upper-left X:\s*(-?\d+)'),('y',r'Absolute upper-left Y:\s*(-?\d+)'),
            ('width',r'Width:\s*(\d+)'),('height',r'Height:\s*(\d+)'))}
        dx=values['width']-width;dy=values['height']-height
        candidates.append(dict(window=identifier,**values,widthDifference=dx,heightDifference=dy))
        if not (0<=dx<=32 and 0<=dy<=120):continue
        for oy in range(dy+1):
            for ox in range(dx+1):
                x=values['x']+ox;y=values['y']+oy
                if x<0 or y<0 or x+width>root.width or y+height>root.height:continue
                if root.crop((x,y,x+width,y+height)).tobytes()==native.tobytes():matches.append(dict(window=identifier,viewportOrigin=[x,y],client=values))
    if len(matches)!=1:
        write(destination/'capture-gap.json',dict(candidates=candidates,matches=matches))
        native.save(destination/'page-diagnostic.png')
        raise AssertionError('No unique exact native X11 viewport matching the real packaged page')
    binding=matches[0];rect=measure['rect'];box=(math.floor(rect['x']),math.floor(rect['y']),math.ceil(rect['x']+rect['width']),math.ceil(rect['y']+rect['height']))
    x,y=binding['viewportOrigin'];cropped=root.crop((x+box[0],y+box[1],x+box[2],y+box[3]));cropped.save(destination/'input.png')
    assert cropped.tobytes()==native.crop(box).tobytes()
    root_path.unlink();evidence['capture']=dict(**binding,inputBox=list(box),size=list(cropped.size),os_sha256=app.sha(destination/'input.png'),pageAndNativePixelsEqual=True)
    write(destination/'measurement.json',evidence);return evidence


def session(destination,view,env,passive=False):
    destination.mkdir();receiver,address=collector(destination);observations={}
    def observe(endpoint,browser,instance,files,folder):
        for stage,text in (('empty',''),('W','W'),('g','g')):
            location=folder/stage;location.mkdir();observations[stage]=capture(endpoint,text,location,env)
            observations[stage]['rows']=list(receiver.rows)
        return dict(stages=list(observations),privatePageAndNativeX11=True)
    with receiver:
        app.native_stock(destination,view,observe,env['DISPLAY'],address,passive)
    observations['traceRows']=receiver.rows
    write(destination/'observations.json',observations);return observations


def provider(record,font,destination):
    assert app.sha(Path(record['probe']['executable']))==record['probe']['sha256']
    oracles={}
    for char in 'Wg':
        command=[record['probe']['executable'],font['font'],'14',str(ord(char)),str(ord(char)),'2','0','1','0','0','1','-1','opsz','14','wght','400']
        write(destination/(char+'-command.json'),command)
        rows=json.loads(subprocess.check_output(command,text=True));assert len(rows)==1
        row=rows[0];assert row['char']==ord(char) and row['matrix']==[1,0,0,1] and row['scale']==14
        oracles[char]=row
    write(destination/'provider.json',oracles);return oracles


def stock_origin(stock,passive,char,glyph,destination):
    base=destination/'source-stock'/char/'input.png';traced=destination/'source-passive'/char/'input.png'
    with Image.open(base) as image:stock_image=image.convert('RGB')
    with Image.open(traced) as image:assert image.convert('RGB').tobytes()==stock_image.tobytes()
    foreground,background=colors(stock[char]['measure']);family=stock[char]['fonts']['fonts'][0]['familyName'].encode().hex();candidates={}
    for item in passive['traceRows']:
        row=item['payload']
        if row['owner'] not in ('path-raster','direct-path-raster') or row.get('family')!=family or row.get('size')!=14 or row.get('format')!=1 or row.get('glyph')!=glyph:continue
        key=json.dumps({k:row[k] for k in ('glyph','width','height','left','top','mask')},sort_keys=True);candidates[key]=row
    matches=[]
    for row in candidates.values():
        if not row['width'] or not row['height']:continue
        pattern=Image.new('RGB',(row['width'],row['height']),background)
        shared.paint_mask(pattern,dict(row,left=0,top=0),bytes.fromhex(row['mask']),(0,0),foreground)
        for y in range(stock_image.height-row['height']+1):
            for x in range(stock_image.width-row['width']+1):
                if stock_image.crop((x,y,x+row['width'],y+row['height'])).tobytes()==pattern.tobytes():
                    matches.append(dict(origin=[x-row['left'],y-row['top']],row=row,sender='opaque native relay; not renderer credential claim'))
    assert len(matches)==1,'No unique stock-only passive mask localization'
    return matches[0]


def verify(destination,observations,oracles):
    from selected_profile_test import expected_mask
    result={}
    for stage in ('empty','W','g'):
        for first,second in (('source-stock','source-passive'),('normal','trace')):
            assert observations[first][stage]['measure']==observations[second][stage]['measure']
            with Image.open(destination/first/stage/'input.png') as a,Image.open(destination/second/stage/'input.png') as b:assert a.convert('RGB').tobytes()==b.convert('RGB').tobytes()
    for char in 'Wg':
        anchor=stock_origin(observations['source-stock'],observations['source-passive'],char,oracles[char]['glyph'],destination)
        row=oracles[char];foreground,background=colors(observations['source-stock'][char]['measure']);origin=anchor['origin']
        with Image.open(destination/'source-stock'/char/'input.png') as image:expected=image.convert('RGB')
        native=anchor['row'];left=min(native['left'],row['left'])+origin[0];top=min(native['top'],row['top'])+origin[1]
        right=max(native['left']+native['width'],row['left']+row['width'])+origin[0];bottom=max(native['top']+native['height'],row['top']+row['height'])+origin[1]
        assert 0<=left<right<=expected.width and 0<=top<bottom<=expected.height
        expected.paste(background,(left,top,right,bottom));wanted=expected_mask(bytes.fromhex(row['mask']),row['width'])
        shared.paint_mask(expected,row,wanted,tuple(origin),foreground)
        domain=(max(0,left-1),max(0,top-1),min(expected.width,right+1),min(expected.height,bottom+1))
        for role in ('normal','trace'):
            assert observations[role][char]['measure']==observations['source-stock'][char]['measure']
            with Image.open(destination/role/char/'input.png') as image:assert image.convert('RGB').crop(domain).tobytes()==expected.crop(domain).tobytes(),char+': independent selected OS glyph pixels differ'
        traced=[item for item in observations['trace']['traceRows'] if item['payload'].get('owner')=='selected']
        matches=[item for item in traced if all(item['payload'].get(key)==row[key] for key in ('glyph','size','scale','matrix','path','width','height','left','top','advance')) and item['payload'].get('raw')==row['mask']]
        assert matches,'No independent native raw/path/metrics match in selected diagnostics'
        assert all(item['payload']['status']==0 and bytes.fromhex(item['payload']['mask'])==wanted for item in matches)
        expected.crop(domain).save(destination/(char+'-expected.png'));result[char]=dict(origin=origin,comparisonDomain=list(domain),independentPixels=True,stockAnchor=anchor,selectedDiagnosticMatches=len(matches),credentialMeaning='opaque native stderr sender; no renderer identity claim')
    assert any(expected_mask(bytes.fromhex(r['mask']),r['width'])!=bytes.fromhex(r['mask']) for r in oracles.values())
    write(destination/'pixel-proof.json',result);return result


def actual_app(engine_record,destination,env):
    destination.mkdir(parents=True,exist_ok=True)
    engine_record=engine_record.resolve(strict=True);engine_sha=app.sha(engine_record)
    inputs={name:app.sha(ROOT/name) for name in (
        'tests/bitwarden_pixels_test.py','tests/bitwarden_delivery_test.py','tests/bitwarden_font_stage.mjs',
        'tests/chromium_delivery_test.py','tests/chromium_flatpak_test.py','tests/browser_masks_test.py',
        'tests/selected_profile_test.py','tools/build-chromium-delivery.py','tools/chromium_delivery.py')}
    command=[sys.executable,'-B',str(ROOT/'tools/build-chromium-delivery.py'),
             '--target','bitwarden','--build-record',str(engine_record)]
    write(destination/'producer-command.json',command)
    with (destination/'producer.stdout').open('w') as stdout,(destination/'producer.stderr').open('w') as stderr:
        subprocess.run(command,env=env,stdout=stdout,stderr=stderr,check=True)
    application_record=Path((destination/'producer.stdout').read_text().splitlines()[-1]).resolve(strict=True)
    record=shared.delivery.load_build(application_record,'bitwarden');application_sha=app.sha(application_record)
    assert record['spec']['build_record']==str(engine_record) and record['spec']['build_sha256']==engine_sha
    assert record['spec']['recipe_sha256']==inputs['tools/build-chromium-delivery.py']
    assert record['spec']['launch_sha256']==inputs['tools/chromium_delivery.py']
    assert shared.delivery.compatibility(record) is None
    font=font_input(Path(record['views']['source-stock']['directory']),destination)
    engine=json.loads(engine_record.read_text());oracles=provider(engine,font,destination);observations={};roles={}
    display=destination/'display';display.mkdir()
    with patch.object(masks,'WORK',(ROOT/'build/bitwarden-pixels').resolve()),patch.object(masks,'OUT',display):
        with masks.nested_display() as display_env:
            for role in ('source-stock','source-passive','normal','trace'):
                view=record['views'][role];shared.delivery.builder.verify(view)
                observations[role]=session(destination/role,Path(view['directory']),display_env,role=='source-passive')
                roles[role]=json.loads((destination/role/'result.json').read_text())
                assert roles[role]['engine']['sha256']==view['engine_sha256']
                assert roles[role]['privateDataRemoved'] and roles[role]['normalQuit']
    pixels=verify(destination,observations,oracles)
    assert app.sha(engine_record)==engine_sha and app.sha(application_record)==application_sha
    assert all(app.sha(ROOT/name)==digest for name,digest in inputs.items())
    result=dict(passed=True,build_record=str(application_record),build_sha256=application_sha,
                engine_record=str(engine_record),engine_sha256=engine_sha,font=font,checks=pixels,roles=roles,
                report=str(destination),test_inputs=inputs,credentialMeaning='opaque native stderr relay; no renderer credential claim')
    write(destination/'report.json',result);write(application_record.parent/'qualification.json',result)
    return result
