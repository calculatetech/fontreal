#!/usr/bin/env python3
"""Prove qualified native Qt text and the approved-layout O prototype end to end."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import noto_kde_comparison as study
from browser_stroke_axis_test import Oracle
from pixel_references_test import assert_record,registered,oracle_mask
from selected_profile_test import expected_mask
BASE='9229921266f95c0c29c58a7ee7031abcf192bd24'
METHODS=(('stock','Stock KDE / Qt'),('approved','Last approved profile'),('O','O NORMAL / Qt-layout prototype'))
BODY=['The quick brown fox jumps over the lazy dog.']+[''.join(chr(c) for c in range(a,min(a+32,127))) for a in (32,64,96)]+['Repeated spaces: A  B   C','AV To office fi fl']
FOCUS='() O O i8! W'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def color_count(image):
    data=image.tobytes();return sum(data[i]!=data[i+1] or data[i+1]!=data[i+2] for i in range(0,len(data),3))
def tree(root):return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
def load(output,meta,files):
    files.add(meta['file']);assert sha(output/meta['file'])==meta['sha256'];return json.loads((output/meta['file']).read_text())
def image(output,meta,files):
    files.add(meta['file']);assert sha(output/meta['file'])==meta['sha256'];result=Image.open(output/meta['file']).convert('RGB')
    if 'size' in meta:assert list(result.size)==meta['size']
    return result


def paint(section,glyphs,method,polarity):
    """Independent scalar native placement and source-over, including actual overlaps."""
    w,h=section['width'],section['height'];bg=255 if polarity=='light' else 0;out=bytearray([bg])*(w*h);depth=[0]*(w*h)
    for line in section['lines']:
        for run in line['runs']:
            for placement in run['glyphs']:
                g=glyphs[placement['id']];frame,values=g[method];x0=math.floor(placement['x'])+frame['left'];y0=math.floor(placement['y']+.5)+frame['top']
                for i,a in enumerate(values):
                    x=x0+i%frame['width'];y=y0+i//frame['width']
                    if not (0<=x<w and 0<=y<h):assert a==0;continue
                    j=y*w+x;depth[j]+=a>0;out[j]=((255-bg)*a+out[j]*(255-a)+127)//255
    return Image.frombytes('L',(w,h),bytes(out)).convert('RGB'),depth


def reject(arguments,message):
    root=ROOT/'results/noto-kde-comparison';before=set(root.iterdir())
    entry=r'''
import pathlib,runpy,sys
root=pathlib.Path(sys.argv[1]);message=sys.argv[2];calls=[]
def audit(event,args):
    if event=='subprocess.Popen':calls.append(str(args[0]))
sys.addaudithook(audit);sys.path[:0]=[str(root/'tools'),str(root/'tests')]
sys.argv=[str(root/'tools/noto_kde_comparison.py'),*sys.argv[3:]]
try:runpy.run_path(sys.argv[0],run_name='__main__')
except ValueError as error:
    assert str(error)==message,(str(error),message)
    assert all(pathlib.Path(call).name in ('pkg-config','fc-match') for call in calls),calls
else:raise AssertionError('invalid qualified input admitted')
print('REJECTED before compile/capture/output: '+message)
'''
    r=subprocess.run([sys.executable,'-B','-c',entry,str(ROOT),message,*arguments],cwd=ROOT,text=True,capture_output=True,check=True)
    assert r.stdout.strip()=='REJECTED before compile/capture/output: '+message and set(root.iterdir())==before
    print(r.stdout.strip(),flush=True)


def main():
    p=argparse.ArgumentParser()
    for name in ('record','stock-qt','approved-qt','baseline-manifest'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();paths={name:getattr(a,name.replace('-','_')).resolve() for name in ('record','stock-qt','approved-qt','baseline-manifest')};argv=[part for name,path in paths.items() for part in ('--'+name,str(path))]
    baseline_path=paths['baseline-manifest'];baseline=json.loads(baseline_path.read_text());record=json.loads(paths['record'].read_text());protected=tree(baseline_path.parent)
    old={s:sha(ROOT/s) for s in study.SOURCES if s not in study.NEW_SOURCES}
    for name,value in old.items():assert value==hashlib.sha256(subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)).hexdigest(),name
    _,_,libraries,font,meta=study.admit(paths['record'],paths['stock-qt'],paths['approved-qt'],baseline_path)
    input_paths={Path(v['library']).resolve() for v in record['libraries'].values()}
    for role in ('stock','approved'):
        input_paths.update(libraries[role].values())
    input_paths.add(font);inputs={str(x):sha(x) for x in input_paths};role_trees={role:tree(paths[role+'-qt']) for role in ('stock','approved')}
    result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/noto_kde_comparison.py'),*argv],cwd=ROOT,text=True,capture_output=True,check=True)
    output=Path(result.stdout.strip().splitlines()[-1]);print('retained export:',output,flush=True);m=json.loads((output/'manifest.json').read_text())
    assert m['study']=='noto-kde-comparison' and m['base_git']==BASE and m['methods']==[list(x) for x in METHODS] and m['body']==BODY and m['focus']==FOCUS
    assert m['scope']=='Native Qt GUI text. O is a Qt-layout prototype, not a deployed Qt renderer. No KWin coverage or installed selector.'
    assert m['font']==meta and meta['style']=='Regular' and meta['sha256']==next(f['sha256'] for f in baseline['fonts'] if f['file']=='NotoSans-Regular.ttf')
    assert m['baseline_manifest']==os.path.relpath(baseline_path,output.resolve()) and not Path(m['baseline_manifest']).is_absolute() and (output/m['baseline_manifest']).resolve()==baseline_path
    assert m['baseline_sha256']==sha(baseline_path) and m['record_sha256']==sha(paths['record']) and m['sources']=={s:sha(ROOT/s) for s in study.SOURCES}
    assert m['fontconfig']==dict(antialias='True',autohint='False',hintstyle=3,rgba=1)
    assert [(c['points'],c['polarity']) for c in m['cases']]==[(pt,pol) for pt in (8,10,11,12) for pol in ('light','dark')]
    qualified={role:next(c['libraries'] for c in baseline['captures'] if c['mode']==mode) for role,mode in (('stock','stock'),('approved','selected'))}
    for role in qualified:assert m['inputs'][role]==qualified[role]
    fontbytes=font.read_bytes();tables={}
    for i in range(struct.unpack_from('>H',fontbytes,4)[0]):
        tag,checksum,start,length=struct.unpack_from('>4sIII',fontbytes,12+16*i)
        if tag in (b'head',b'cmap',b'name'):tables[tag.decode()]=hashlib.sha256(fontbytes[start:start+length]).hexdigest()
    provider=Path(record['libraries']['stock']['library']).resolve();oracle=Oracle(provider);files={'manifest.json'};glyph_count=0;colored={};max_error=0;different=0
    try:
        for case in m['cases']:
            pt,pol=case['points'],case['polarity'];pixel_size={8:11,10:13,11:15,12:16}[pt];step=math.ceil(pt*96/72)+12;caps={};native={}
            for role in ('stock','approved'):
                capture=case['captures'][role];cap=load(output,capture['metadata'],files);caps[role]=cap;files.add(capture['maps']['file']);maps=output/capture['maps']['file'];assert sha(maps)==capture['maps']['sha256'];mapped=maps.read_text()
                assert cap['family']=='Noto Sans' and cap['style']=='Regular' and cap['point_size']==pt and cap['pixel_size']==pixel_size and cap['image_format']=='RGB32' and cap['font_tables']==tables
                source=cap['source'];assert source==dict(family='Noto Sans',style='Regular',x_ppem=pixel_size,space_glyph_id=cap['space_glyph_id'],dpi=72,char_size_26_6=pixel_size*64,load_flags=32776,target=0,render=0,interpreter=40,darkening_properties={k:dict(no_stem_darkening=True) for k in ('cff','autofitter')},selected_reference=False,reference_library=str(provider))
                if pt==10:assert source['char_size_26_6']==832 and source['char_size_26_6']!=round(pt*96/72*64)
                for stem in ('libQt6Core.so.','libQt6Gui.so.','libQt6Widgets.so.'):
                    actual={Path(line.split()[-1]).resolve() for line in mapped.splitlines() if stem in line};declared=libraries[role][stem];assert actual=={declared} and sha(declared)==qualified[role][stem]['sha256'] and capture['actual_libraries'][stem]==qualified[role][stem]
                qt_provider=Path(record['libraries']['stock' if role=='stock' else 'candidate']['library']).resolve();actual={Path(line.split()[-1]).resolve() for line in mapped.splitlines() if 'libfreetype.so.' in line};assert actual=={provider,qt_provider}
                assert capture['actual_libraries']['freetype_roles']==dict(qt=qualified[role]['libfreetype.so.'],reference=qualified['stock']['libfreetype.so.'])
                assert [s['kind'] for s in cap['sections']]==['body','focus'];placed_ids=set()
                for section in cap['sections']:
                    kind=section['kind'];texts=BODY if kind=='body' else [FOCUS];assert [line['text'] for line in section['lines']]==texts and (section['width'],section['height'])==(500,16+step*len(texts)) and section['dpi']==96 and section['device_pixel_ratio']==1
                    for li,line in enumerate(section['lines']):
                        assert line['origin']==[12,8+li*step];placed=[g for run in line['runs'] for g in run['glyphs']];assert sum(g['id']==cap['space_glyph_id'] for g in placed)==line['text'].count(' ')
                        if line['text']==BODY[-1]:assert len(placed)==14<len(BODY[-1])
                        for run in line['runs']:
                            assert run['pixel_size']==pixel_size
                            for g in run['glyphs']:
                                assert g['id']>0 and g['x']==line['origin'][0]+g['local_x'] and g['y']==line['origin'][1]+g['local_y'] and g['local_y']==line['ascent'];placed_ids.add(g['id'])
                    native[role,kind]=image(output,capture['images'][kind],files)
                assert [g['id'] for g in cap['glyphs']]==sorted(placed_ids) and len(placed_ids)==98
                for g in cap['glyphs']:
                    raw=g['raw'];assert len(raw['pixels'])==raw['width']*raw['height'] and raw==oracle_mask(oracle,g)
                color=sum(color_count(native[role,kind]) for kind in ('body','focus'));assert (color>0)==(role=='stock');colored[pt,pol,role]=color
                different+=native['stock','body'].tobytes()!=native[role,'body'].tobytes() if role=='approved' else 0
            rows=load(output,case['masks'],files);approved=caps['approved'];assert [r['id'] for r in rows]==[g['id'] for g in approved['glyphs']];glyphs={}
            for row,g in zip(rows,approved['glyphs']):
                raw=g['raw'];assert row['raw']==raw;selected=list(expected_mask(bytes(raw['pixels']),raw['width'])) if raw['pixels'] else [];assert row['selected']==selected==g['qt_alpha']['pixels'] and (g['qt_alpha']['width'],g['qt_alpha']['height'])==(raw['width'],raw['height'])
                normal=row['normal'];frame=dict(left=raw['left']-2,top=raw['top']-2,width=raw['width']+4,height=raw['height']+4);assert normal['frame']==frame and normal['masks']['A']==registered(raw,frame)
                d=study.base.native_stems.treatments(bytes(raw['pixels']),raw['width'])[0]['D'];assert normal['masks']['D']==registered({**raw,'pixels':list(d)},frame)
                highframe=dict(left=(raw['left']-3)*4,top=(raw['top']-3)*4,width=(raw['width']+6)*4,height=(raw['height']+6)*4);assert {k:v for k,v in normal['high'].items() if k!='pixels'}==highframe and normal['high']['pixels']==registered(oracle_mask(oracle,g,4),highframe);assert_record(normal)
                glyphs[g['id']]={'selected':(raw,selected),'O':(frame,normal['masks']['O'])};glyph_count+=1
            proof_by_kind={q['kind']:q for q in case['approved_reconstruction']};assert set(proof_by_kind)=={'body','focus'} and len(case['approved_reconstruction'])==2
            for section in approved['sections']:
                kind=section['kind'];expected,depth=paint(section,glyphs,'selected',pol);saved=image(output,proof_by_kind[kind],files);assert saved.size==expected.size and saved.tobytes()==expected.tobytes()
                actual=native['approved',kind];reference_bytes=expected.tobytes();native_bytes=actual.tobytes();errors=[max(abs(reference_bytes[i+j]-native_bytes[i+j]) for j in range(3)) for i in range(0,len(native_bytes),3)];assert all(error<=max(1,n) for error,n in zip(errors,depth))
                assert proof_by_kind[kind]['max_error']==max(errors,default=0) and proof_by_kind[kind]['max_nonzero_layers']==max(depth,default=0);max_error=max(max_error,*errors)
                expected_o,_=paint(section,glyphs,'O',pol);o=image(output,case['prototype'][kind],files);assert o.size==expected_o.size and o.tobytes()==expected_o.tobytes();assert color_count(o)==0;native['O',kind]=o
            # Reconstruct complete scientific sheets, including exact headings and native crop boxes.
            bg='white' if pol=='light' else 'black';fg='black' if pol=='light' else 'white';focus_h=native['approved','focus'].height;body_h=native['approved','body'].height;expected=Image.new('RGB',(1584,104+focus_h+28+body_h+12),bg);draw=ImageDraw.Draw(expected);label=ImageFont.truetype(str(font),14)
            draw.text((12,10),f'Noto Sans Regular | {pt}pt | native 96 DPI / 1x',font=label,fill=fg);draw.text((12,32),'Stock RGB is preserved. O uses approved Qt layout and NORMAL source; prototype only. View at 100%.',font=label,fill=fg)
            headings=[];boxes=[]
            for col,(method,caption) in enumerate(METHODS):
                x=12+col*524;draw.text((x,64),caption,font=label,fill=fg);headings.append(dict(text=caption,position=[x,64]));box=dict(method=method)
                for kind,y in (('focus',96),('body',104+focus_h+28)):
                    patch=native[method,kind];expected.paste(patch,(x,y));meta=case['prototype'][kind] if method=='O' else case['captures'][method]['images'][kind];box[kind]=dict(file=meta['file'],box=[x,y,x+patch.width,y+patch.height])
                boxes.append(box)
            sheet=image(output,case['sheet'],files);assert case['sheet']['headings']==headings and case['sheet']['crops']==boxes and sheet.size==expected.size and sheet.tobytes()==expected.tobytes()
            for box in boxes:
                for kind in ('body','focus'):assert sheet.crop(box[kind]['box']).tobytes()==native[box['method'],kind].tobytes()
            print('checked Noto Sans Regular',pt,pol,'native roles, source/alpha/layout, complete reconstruction/O/sheet',flush=True)
    finally:oracle.close()
    assert glyph_count==784 and different==8 and len(files)==113 and len(list((output/'gallery').glob('*.png')))==8
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==files
    with tempfile.TemporaryDirectory(prefix='admission-',dir=output) as temporary:
        temp=Path(temporary)
        def replaced(key,path):return [part for name,value in paths.items() for part in ('--'+name,str(path if name==key else value))]
        for role in ('stock','approved'):reject(replaced(role+'-qt',paths[('approved' if role=='stock' else 'stock')+'-qt']),'Qt role differs from qualified baseline: '+role+' libQt6Core.so.')
        for role,key,alternate_key in (('stock','stock','candidate'),('approved','candidate','stock')):
            alternate=record['libraries'][alternate_key];genuine=Oracle(Path(alternate['library']));genuine.close();fixture=json.loads(json.dumps(record));fixture['libraries'][key]=alternate;fixture['test_input']='Synthetic role mismatch using a genuine alternate from the paired record';path=temp/('provider-'+role+'.json');path.write_text(json.dumps(fixture)+'\n');reject(replaced('record',path),'FreeType role differs from qualified baseline: '+role)
        fixture=json.loads(json.dumps(baseline));noto=next(f for f in fixture['fonts'] if f['file']=='NotoSans-Regular.ttf');noto['sha256']=next(f['sha256'] for f in baseline['fonts'] if f['file']!='NotoSans-Regular.ttf');fixture['test_input']='Synthetic qualification mismatch using another genuine baseline font hash';path=temp/'font.json';path.write_text(json.dumps(fixture)+'\n');reject(replaced('baseline-manifest',path),'Noto Sans differs from qualified baseline')
    assert protected==tree(baseline_path.parent) and inputs=={str(x):sha(x) for x in input_paths} and old=={s:sha(ROOT/s) for s in old} and role_trees=={role:tree(paths[role+'-qt']) for role in role_trees}
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==files
    print('PASS 8 conditions, 784 approved glyphs/1568 independent native source rasters, exact O/4x/scalar evidence, 113 artifacts, five early rejections; max approved error',max_error,flush=True)
    print('stock RGB pixels:',{str((pt,pol)):colored[pt,pol,'stock'] for pt in (8,10,11,12) for pol in ('light','dark')},flush=True);print('gallery:',output/'gallery',flush=True)


if __name__=='__main__':main()
