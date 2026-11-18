#!/usr/bin/env python3
"""Check retained-input fractional edge trials through the guarded real CLI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import pixel_reference_smoothing as trial
import supersampling as shared
from supersampling_test import composed_bytes
from pixel_references_test import specimen_layout
BASE='8caba95bc396957394b63e5040963d822ccde008'
METHODS=[['A','Native raw'],['D','Accepted baseline'],['O','Coherent weak cores'],['L','Local weak cores'],['T','L + quarter edge'],['U','L + half edge']]
GUARDED_ENTRY=r'''
import json,pathlib,runpy,subprocess,sys
root=pathlib.Path(sys.argv[1]);source=sys.argv[2]
sys.path[:0]=[str(root/'tools'),str(root/'tests')]
import pixel_references as base
import supersampling as shared
from browser_stroke_axis_test import Oracle
def forbidden(*args,**kwargs):raise AssertionError('prohibited opaque native work reached')
shared.compile_tools=forbidden
base.condition=forbidden
Oracle.__init__=forbidden
Oracle.raster=forbidden
original=subprocess.Popen
calls=[]
def guarded(command,*args,**kwargs):
    if isinstance(command,str) or pathlib.Path(command[0]).name!='fc-match':
        raise AssertionError('external non-Fontconfig process reached: '+str(command))
    calls.append(list(command));return original(command,*args,**kwargs)
subprocess.Popen=guarded
sys.argv=[str(root/'tools/pixel_reference_smoothing.py'),'--source-manifest',source]
runpy.run_path(sys.argv[0],run_name='__main__')
print('NO_NATIVE_WORK '+json.dumps(dict(fontconfig_calls=len(calls),commands=calls)),file=sys.stderr)
'''


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scalar(l,s,denominator):
    result=[]
    for a,b in zip(l,s):
        q,r=divmod(b-a,denominator);result.append(a+q+(2*r>=denominator))
    return result


def load(root,meta):
    path=root/meta['file'];assert digest(path)==meta['sha256'];return json.loads(path.read_text())


def check_grid(output,grid,record,font,family,points):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9);w,h=record['frame']['width'],record['frame']['height'];column=max(280,w*20+40);cell=20
    title=f'{family} Regular / {points}pt / {chr(record["code"])} / fractional S edges';subtitle='Coverage: 0 = no ink, 255 = full ink. Orange marks T/U fringe additions to L. Native previews are not resized.'
    assert grid['title']==title and grid['subtitle']==subtitle and grid['code']==record['code'] and grid['cell_size']==20
    size=(column*4+20,h*20+146);assert grid['size']==list(size)
    image=Image.new('RGB',size,(24,24,24));draw=ImageDraw.Draw(image);draw.text((12,10),title,font=label,fill='white');draw.text((12,32),subtitle,font=small,fill='white');cells=[];previews=[];headings=[]
    for col,key in enumerate(('O','L','T','U')):
        x=12+col*column;values=record['masks'][key];draw.text((x,58),key,font=label,fill='white');headings.append(dict(text=key,position=[x,58]));image.paste(Image.frombytes('L',(w,h),bytes(values)).convert('RGB'),(x+38,58));previews.append(dict(method=key,box=[x+38,58,x+38+w,58+h]))
        for xx in range(w):draw.text((x+30+xx*20,90),str(xx+1),font=small,fill='white')
        for yy in range(h):
            draw.text((x,110+yy*20),str(yy+1),font=small,fill='white')
            for xx in range(w):
                i=yy*w+xx;v=values[i];l=record['masks']['L'][i];left=x+26+xx*20;top=108+yy*20;border=[240,150,70] if key in ('T','U') and v>l else [75,75,75]
                cells.append(dict(method=key,index=i,row=yy+1,column=xx+1,value=v,source_L=l,source_S=l+record['edge_increments'][i],box=[left,top,left+20,top+20],border=border,text_position=[left+1,top+4]));draw.rectangle((left,top,left+19,top+19),fill=(v,)*3,outline=tuple(border));draw.text((left+1,top+4),str(v),font=small,fill='black' if v>=145 else 'white')
    assert grid['cells']==cells and grid['previews']==previews and grid['headings']==headings
    saved=Image.open(output/grid['file']);assert saved.size==size and saved.tobytes()==image.tobytes() and digest(output/grid['file'])==grid['sha256']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-manifest',required=True,type=Path);args=parser.parse_args();source_path=args.source_manifest.resolve(strict=True);source_root=source_path.parent;source=json.loads(source_path.read_text())
    original_files={str(p.relative_to(source_root)):digest(p) for p in source_root.rglob('*') if p.is_file()}
    run=subprocess.run([sys.executable,'-B','-c',GUARDED_ENTRY,str(ROOT),str(source_path)],cwd=ROOT,text=True,capture_output=True,check=True)
    output=Path(run.stdout.strip().splitlines()[-1]);print('retained export:',output,flush=True)
    evidence=json.loads(next(line.removeprefix('NO_NATIVE_WORK ') for line in run.stderr.splitlines() if line.startswith('NO_NATIVE_WORK ')));assert evidence['fontconfig_calls']==5 and all(Path(c[0]).name=='fc-match' for c in evidence['commands'])
    print('PASS no-native-work guards: five genuine Fontconfig label lookups; no compile/capture/Oracle/external native work',flush=True)
    manifest=json.loads((output/'manifest.json').read_text());assert manifest['base_git']==BASE and manifest['study']=='pixel-reference-smoothing'
    assert (output/manifest['source_manifest']).resolve()==source_path and manifest['source_manifest_sha256']==digest(source_path)
    assert manifest['source_manifest']==str(Path('..')/'..'/'pixel-references'/source_root.name/'manifest.json')
    assert manifest['source_contributors']==source['sources'] and manifest['methods']==METHODS and manifest['fonts']==source['fonts'] and manifest['focus']=='() () i8! W'
    assert manifest['specimen']==source['specimen']==list(shared.SPECIMEN) and manifest['target_dpi']==96 and manifest['blend']=='encoded' and manifest['placement']==source['placement']
    assert set(manifest['sources'])==set(trial.SOURCES)
    for path,sha in manifest['sources'].items():
        assert sha==digest(ROOT/path)
        if path not in ('tools/pixel_reference_smoothing.py','tests/pixel_reference_smoothing_test.py'):
            assert sha==hashlib.sha256(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)).hexdigest(),path
    for path,sha in source['sources'].items():assert sha==digest(ROOT/path)
    assert [(c['font'],c['points']) for c in manifest['cases']]==[(f,p) for f in range(5) for p in (8,10,11,12)]
    expected_files={'manifest.json'};count=0;inc_values=set();core_count=0;grid_count=0;fonts={};ordered_calls=[]
    for fi,meta in enumerate(source['fonts']):
        result=subprocess.check_output(['fc-match','-f','%{file}\n',meta['family']+':style=Regular'],text=True).strip();font=Path(result);assert digest(font)==meta['sha256'];fonts[fi]=font
    for ci,(case,oldcase) in enumerate(zip(manifest['cases'],source['cases'])):
        fi,pt=case['font'],case['points'];family=source['fonts'][fi]['family'];font=fonts[fi];label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9)
        assert case['source_case']==ci and case['font']==oldcase['font'] and case['points']==oldcase['points']
        for name in ('capture','inputs','masks'):assert case['source_'+name]==oldcase[name];load(source_root,case['source_'+name])
        oldrecords=load(source_root,oldcase['masks']);inputs=load(source_root,oldcase['inputs']);records=load(output,case['masks']);assert case['masks']['file'] not in expected_files;expected_files.add(case['masks']['file'])
        assert [r['code'] for r in records]==[r['code'] for r in oldrecords]==list(range(32,127))
        for r,old in zip(records,oldrecords):
            assert r['frame']==old['frame'] and r['advance_pixels']==old['advance_pixels'] and r['source_record_sha256']==hashlib.sha256(json.dumps(old,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            l,s=old['masks']['L'],old['masks']['S'];t,u=scalar(l,s,4),scalar(l,s,2)
            assert r['masks']=={**{k:old['masks'][k] for k in 'ADOL'},'T':t,'U':u}
            ordered_calls.append((l,s,dict(T=t,U=u)))
            assert r['edge_increments']==[b-a for a,b in zip(l,s)];inc_values.update(r['edge_increments'])
            assert all(a<=b<=c<=d<=255 for a,b,c,d in zip(l,t,u,s))
            for i in old['overlay']['primary']:assert t[i]==u[i]==l[i]==s[i];core_count+=1
            for i,(a,b) in enumerate(zip(l,s)):
                if a==b or a==0:assert t[i]==u[i]==a
                assert s[i]<=max(old['masks']['D'][i],old['masks']['E'][i])
            count+=1
        assert records[0]['advance_pixels']>0 and not any(records[0]['masks']['T']) and not any(records[0]['masks']['U'])
        if fi==3 and pt==11:
            parent=next(r for r in records if r['code']==40);w=parent['frame']['width'];i=12*w+2
            assert [parent['masks'][k][i] for k in ('L','T','U')]==[125,150,175] and parent['edge_increments'][i]==100
            assert [parent['masks'][k][i+1] for k in ('D','O','L','T','U')]==[132,132,238,238,238]
        places,lines=specimen_layout(inputs);assert case['placements']==oldcase['placements']==places and case['lines']==oldcase['lines']==lines
        focus=[];x=0;advances={r['code']:r['advance_pixels'] for r in records}
        for code in map(ord,'() () i8! W'):focus.append(dict(code=code,x=x,line=0));x+=advances[code]
        assert case['focus_placements']==focus
        assert len(case['crops'])==len(case['focus_crops'])==12
        for kind,metadata,placements,nlines in (('body',case['crops'],places,lines),('focus',case['focus_crops'],focus,1)):
            assert [(m['method'],m['polarity']) for m in metadata]==([(k,p) for k,title in METHODS for p in ('light','dark')] if kind=='body' else [(k,p) for p in ('light','dark') for k,title in METHODS])
            for meta in metadata:
                key,polarity=meta['method'],meta['polarity'];size=(252,nlines*((pt*4+2)//3+6)+14);glyphs={r['code']:{'final':{**r['frame'],'pixels':r['masks'][key]}} for r in records};pixels=composed_bytes(glyphs,placements,pt,size)
                if polarity=='light':pixels=bytes(255-v for v in pixels)
                image=Image.open(output/meta['file']);assert image.size==size==tuple(meta['size']) and image.tobytes()==pixels and digest(output/meta['file'])==meta['sha256']
                assert meta['file'] not in expected_files;expected_files.add(meta['file'])
                if kind=='body' and key in 'ADOL':
                    oldmeta=next(c for c in oldcase['crops'] if c['method']==key and c['polarity']==polarity);assert meta['sha256']==oldmeta['sha256']==digest(source_root/oldmeta['file'])
        assert len(case['sheets'])==2
        for sheet in case['sheets']:
            polarity=sheet['polarity'];bg,fg=(255,0) if polarity=='light' else (0,255);fh=(pt*4+2)//3+20;body_y=138+fh;body_height=lines*((pt*4+2)//3+6)+14;size=(1628,body_y+body_height+12)
            title=f'{family} Regular | {pt}pt | 96 DPI | retained L cores and fractional S edges';subtitle='O preferred general control. T/U add quarter/half of S-L to L. Extra edge ink can still add weight. View at 100%.'
            assert sheet['title']==title and sheet['subtitle']==subtitle and sheet['body_y']==body_y and sheet['divider_y']==110+fh and sheet['size']==list(size)
            image=Image.new('L',size,bg);draw=ImageDraw.Draw(image);draw.text((12,10),title,font=label,fill=fg);draw.text((12,32),subtitle,font=label,fill=fg);draw.text((12,86),'Native focus: () () i8! W',font=small,fill=fg);draw.text((12,body_y-16),'Full source specimen',font=small,fill=fg)
            assert len(sheet['headings'])==len(sheet['crops'])==6
            for col,((key,caption),heading,boxes) in enumerate(zip(METHODS,sheet['headings'],sheet['crops'])):
                x=12+col*268;assert heading==dict(text=f'{key}: {caption}',position=[x,64]);draw.text((x,64),heading['text'],font=label,fill=fg);assert boxes['method']==key
                for kind,metadata,y in [('focus',case['focus_crops'],104),('body',case['crops'],body_y)]:
                    meta=next(m for m in metadata if m['method']==key and m['polarity']==polarity);patch=Image.open(output/meta['file']);assert boxes[kind]==dict(file=meta['file'],box=[x,y,x+patch.width,y+patch.height]);image.paste(patch,(x,y))
            draw.line((12,110+fh,1616,110+fh),fill=fg)
            assert Image.open(output/sheet['file']).tobytes()==image.tobytes() and digest(output/sheet['file'])==sheet['sha256'];assert sheet['file'] not in expected_files;expected_files.add(sheet['file'])
        assert [g['code'] for g in case['grids']]==[40,41]
        for grid in case['grids']:
            check_grid(output,grid,next(r for r in records if r['code']==grid['code']),font,family,pt);assert grid['file'] not in expected_files;expected_files.add(grid['file']);grid_count+=1
        print(f'checked {family} {pt}pt: exact controls,95 trials,native body/focus,sheets and both parentheses',flush=True)
    assert count==1900 and grid_count==40 and len(manifest['cases'])==20 and core_count>0
    assert {0,1,2}<=inc_values and any(v>2 and v%2 for v in inc_values)
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==expected_files and len(expected_files)==581
    assert len(list((output/'gallery').glob('*.png')))==40 and len(list((output/'diagnostics').glob('*.png')))==40
    assert original_files=={str(p.relative_to(source_root)):digest(p) for p in source_root.rglob('*') if p.is_file()}
    # Literal midpoint, odd, larger, saturated, zero and no-edge contrasts supplement actual masks.
    l=[0,100,100,100,100,100,100,125,255];s=[0,100,101,102,103,104,107,225,255]
    assert trial.trials(l,s)==dict(T=[0,100,100,101,101,101,102,150,255],U=[0,100,101,101,102,102,104,175,255])
    assert trial.trials([],[])==dict(T=[],U=[])
    for sequence in (ordered_calls,list(reversed(ordered_calls))):
        for a,b,expected in sequence:assert trial.trials(a,b)==expected
    assert trial.trials(l[::-1],s[::-1])=={k:v[::-1] for k,v in trial.trials(l,s).items()}
    for a,b in [([1],[]),([2],[1]),([-1],[1]),([0],[256])]:
        try:trial.trials(a,b)
        except ValueError:pass
        else:raise AssertionError('invalid coverage arrays accepted')
    print('PASS retained smoothing:1900 exact trials,all native images/40 sheets/40 grids,unchanged source and guarded real entry',flush=True);print('gallery:',output/'gallery',flush=True)


if __name__=='__main__':main()
