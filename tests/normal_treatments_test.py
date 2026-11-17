#!/usr/bin/env python3
"""Check fresh NORMAL inputs, opaque treatments and display-only union registration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import normal_treatments as study
from browser_stroke_axis_test import Oracle
from pixel_references_test import assert_record,registered,oracle_mask,specimen_layout
from arial_coherence_test import independent,check_panels
from supersampling_test import composed_bytes
BASE='c66b7c63cc4218e6ddaad666883dbf63cacdd6b8'
METHODS=(('H','Historical O (MONO)'),('A','Raw NORMAL'),('O','O NORMAL'),('U','U NORMAL'),('K3','K3 NORMAL'),('K5','K5 NORMAL'))
FOCUS='() O O i8! W'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def read(root,meta):assert sha(root/meta['file'])==meta['sha256'];return json.loads((root/meta['file']).read_text())


def reject(record_path,source_path,message):
    root=ROOT/'results/normal-treatments';before=set(root.iterdir())
    entry=r'''
import pathlib,runpy,sys
root=pathlib.Path(sys.argv[1]);record=sys.argv[2];source=sys.argv[3];message=sys.argv[4];calls=[]
def audit(event,args):
    if event=='subprocess.Popen':calls.append(str(args[0]))
sys.addaudithook(audit);sys.path[:0]=[str(root/'tools'),str(root/'tests')]
sys.argv=[str(root/'tools/normal_treatments.py'),'--record',record,'--source-manifest',source]
try:runpy.run_path(sys.argv[0],run_name='__main__')
except ValueError as error:assert str(error)==message and not calls
else:raise AssertionError('invalid input was admitted')
print('REJECTED before font/compile/capture/output: '+message)
'''
    result=subprocess.run([sys.executable,'-B','-c',entry,str(ROOT),str(record_path),str(source_path),message],cwd=ROOT,text=True,capture_output=True,check=True)
    assert result.stdout.strip()=='REJECTED before font/compile/capture/output: '+message and set(root.iterdir())==before


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',required=True,type=Path);parser.add_argument('--source-manifest',required=True,type=Path);args=parser.parse_args();record_path=args.record.resolve();source_path=args.source_manifest.resolve();source_root=source_path.parent;source=json.loads(source_path.read_text());original={str(p.relative_to(source_root)):sha(p) for p in source_root.rglob('*') if p.is_file()}
    result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/normal_treatments.py'),'--record',str(record_path),'--source-manifest',str(source_path)],cwd=ROOT,text=True,capture_output=True,check=True)
    output=Path(result.stdout.strip().splitlines()[-1]);print('retained export:',output,flush=True);m=json.loads((output/'manifest.json').read_text())
    assert m['base_git']==BASE and m['study']=='normal-treatments' and m['methods']==[list(x) for x in METHODS] and m['focus']==FOCUS and m['specimen']==source['specimen'] and m['fonts']==source['fonts']
    assert m['source_manifest']==os.path.relpath(source_path,output.resolve()) and not Path(m['source_manifest']).is_absolute() and (output/m['source_manifest']).resolve()==source_path and m['source_manifest_sha256']==sha(source_path)
    assert m['target_dpi']==96 and m['blend']=='encoded' and m['record_sha256']==sha(record_path)
    assert set(m['sources'])==set((*study.prior.smooth.SOURCES,*study.prior.NEW_SOURCES,*study.NEW_SOURCES))
    for path,value in m['sources'].items():
        assert value==sha(ROOT/path)
        if path not in study.NEW_SOURCES:assert value==hashlib.sha256(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)).hexdigest(),path
    record=json.loads(record_path.read_text());provider=Path(record['libraries']['stock']['library']).resolve();assert m['provider']==dict(file=provider.name,sha256=sha(provider)) and m['provider']['sha256']==source['provider']['sha256']
    assert [(c['font'],c['points']) for c in m['cases']]==[(fi,pt) for fi in range(5) for pt in (8,10,11,12)]
    fonts=[study.base.match_font(meta['family'])[0] for meta in source['fonts']];oracle=Oracle(provider);files={'manifest.json'};tt_count=cff_count=0;cff_differences=0;normal_mono_differences=0;union_differences=0;count=0
    try:
        for ci,(case,oldcase) in enumerate(zip(m['cases'],source['cases'])):
            fi,pt=case['font'],case['points'];family=source['fonts'][fi]['family'];font=fonts[fi];assert case['source_case']==ci and case['source_masks']==oldcase['masks']
            cap=read(output,case['capture']);numbers=read(output,case['normal']);display=read(output,case['display']);oldrows=read(source_root,oldcase['masks']);oldcap=read(source_root,oldcase['capture']);oldnormal=next(c for c in oldcap['captures'] if c['mode']=='native1')
            assert Path(cap['provider']).resolve()==provider and cap['family']==family and cap['style']=='Regular' and cap['points']==pt and cap['target_dpi']==96 and cap['format']==('CFF' if fi==1 else 'TrueType')
            assert len(cap['captures'])==1;capture=cap['captures'][0]
            expected=dict(mode='native_normal',scale=1,hint_dpi=96,x_ppem=(pt*4+1)//3,policy='native',target=0,render=0,interpreter=40,effective_interpreter=40,cff_hinting_engine=1,stem_darkening=False,load_flags=32776,darkening_properties={k:dict(get_error=0,set_error=0,no_stem_darkening=True) for k in ('cff','autofitter')})
            assert {k:v for k,v in capture.items() if k!='glyphs'}==expected
            assert [g['code'] for g in capture['glyphs']]==[r['code'] for r in numbers]==[r['code'] for r in display]==[r['code'] for r in oldrows]==list(range(32,127))
            for glyph,num,r,old,prior in zip(capture['glyphs'],numbers,display,oldrows,oldnormal['glyphs']):
                bitmap=glyph['bitmap'];rawbytes=bytes.fromhex(bitmap['rows_hex']);assert bitmap['pixel_mode']==2 and len(rawbytes)==abs(bitmap['pitch'])*bitmap['rows']
                raw=dict(left=glyph['left'],top=glyph['top'],width=bitmap['width'],height=bitmap['rows'],pixels=[rawbytes[y*abs(bitmap['pitch'])+x] for y in range(bitmap['rows']) for x in range(bitmap['width'])]);outline=dict(outline=[[*xy,t] for xy,t in zip(glyph['outline'],glyph['tags'])],contours=glyph['contours']);normal=num['normal']
                assert num['raw']==raw and num['outline']==outline and num['actual_advance']==glyph['advance']
                frame=dict(left=raw['left']-2,top=raw['top']-2,width=raw['width']+4,height=raw['height']+4);assert normal['frame']==frame
                assert registered(raw,frame)==normal['masks']['A']==registered(oracle_mask(oracle,outline),frame)
                d=study.base.native_stems.treatments(bytes(raw['pixels']),raw['width'])[0]['D'];assert normal['masks']['D']==registered({**raw,'pixels':list(d)},frame)
                highframe=dict(left=(raw['left']-3)*4,top=(raw['top']-3)*4,width=(raw['width']+6)*4,height=(raw['height']+6)*4)
                assert {k:v for k,v in normal['high'].items() if k!='pixels'}==highframe and normal['high']['pixels']==registered(oracle_mask(oracle,outline,4),highframe)
                assert_record(normal)
                extras,audit=independent(normal['masks']['D'],normal['masks']['L'],normal['masks']['S'],normal['reference']['phase_sums'],normal['reference']['axes'],normal['overlay']['primary'],normal['reference']['components'],frame['width']);u=[a+(b-a+1)//2 for a,b in zip(normal['masks']['L'],normal['masks']['S'])]
                assert num['trials']==dict(U=u,**extras) and num['coherence']==audit
                for k in ('K3','K5'):assert all(d<=v<=upper<=max(d,e) for d,v,upper,e in zip(normal['masks']['D'],num['trials'][k],u,normal['masks']['E']))
                oldraw={k:prior[k] for k in ('left','top','width','height','pixels')}
                if fi!=1:
                    assert raw==oldraw and all(glyph[k]==prior[k] for k in ('code','left','top','advance','outline','tags','contours'))
                elif raw!=oldraw:cff_differences+=1
                if frame!=old['frame']:normal_mono_differences+=1
                historical=dict(frame=old['frame'],pixels=old['masks']['O'],advance_pixels=old['advance_pixels'],source_record_sha256=canonical(old));assert r['historical']==historical
                assert r['advance_pixels']==old['advance_pixels'] and r['actual_normal_advance']==glyph['advance']
                left=min(old['frame']['left'],frame['left']);top=min(old['frame']['top'],frame['top']);right=max(old['frame']['left']+old['frame']['width'],frame['left']+frame['width']);bottom=max(old['frame']['top']+old['frame']['height'],frame['top']+frame['height']);union=dict(left=left,top=top,width=right-left,height=bottom-top)
                assert r['frame']==union and set(r['masks'])=={'H','A','O','U','K3','K5'}
                assert r['masks']['H']==registered({**old['frame'],'pixels':old['masks']['O']},union)
                for k in ('A','O','U','K3','K5'):
                    values=normal['masks'][k] if k in ('A','O') else num['trials'][k];assert r['masks'][k]==registered({**frame,'pixels':values},union)
                if union!=frame:union_differences+=1
                if fi==3 and pt==10 and glyph['code']==79:assert raw['width']==10 and old['frame']['width']==12 and frame!=old['frame']
                count+=1
            if fi==1:cff_count+=1
            else:tt_count+=1
            places,lines=specimen_layout(read(source_root,oldcase['inputs']));assert case['placements']==oldcase['placements']==places and case['lines']==oldcase['lines']==lines
            assert all(s['title']==f'{family} Regular | {pt}pt | native NORMAL treatments' and s['subtitle']=='Historical O: native MONO hints / gray / darkening on. All NORMAL columns: native NORMAL / gray / darkening off.' for s in case['sheets'])
            check_panels(output,case,display,METHODS,font,pt,260)
            assert [p['code'] for p in case['focus_placements']]==list(map(ord,FOCUS))
            # Prove historical focus independently from ORIGINAL frames, without trusting union registration.
            original_glyphs={r['code']:{'final':{**r['frame'],'pixels':r['masks']['O']}} for r in oldrows};focus_size=(272,(pt*4+2)//3+20)
            expected_focus=composed_bytes(original_glyphs,case['focus_placements'],pt,focus_size)
            for polarity in ('light','dark'):
                focus=next(c for c in case['crops'] if c['method']=='H' and c['kind']=='focus' and c['polarity']==polarity);assert Image.open(output/focus['file']).tobytes()==(bytes(255-v for v in expected_focus) if polarity=='light' else expected_focus)
            assert len(case['historical_body_controls'])==2
            for control in case['historical_body_controls']:
                oldcrop=next(c for c in oldcase['crops'] if c['method']=='O' and c['polarity']==control['polarity']);assert control['source']==oldcrop
                body=next(c for c in case['crops'] if c['method']=='H' and c['kind']=='body' and c['polarity']==control['polarity']);assert control['display_file']==body['file'];prior_image=Image.open(source_root/oldcrop['file']);assert control['region']==[0,0,252,prior_image.height] and sha(source_root/oldcrop['file'])==oldcrop['sha256']
                assert Image.open(output/body['file']).crop(control['region']).tobytes()==prior_image.tobytes()
            assert not any(display[0]['masks']['H']) and not any(numbers[0]['normal']['masks']['A']) and display[0]['advance_pixels']>0
            files.update(v['file'] for v in [case['capture'],case['normal'],case['display'],*case['crops'],*case['sheets']]);print('checked',family,pt,'NORMAL own-frame/numerics, historical O and native union images',flush=True)
    finally:oracle.close()
    assert count==1900 and tt_count==16 and cff_count==4 and cff_differences>0 and normal_mono_differences>0 and union_differences>0
    assert len(m['cases'])==20 and len(list((output/'gallery').glob('*.png')))==40 and len(files)==581
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==files
    # Minimal invalid collections must stop at admission, including a correct prefix followed by a bad final case.
    with tempfile.TemporaryDirectory(prefix='admission-',dir=output) as temporary:
        cases=source['cases']
        for name,rows in [('empty',[]),('one',cases[:1]),('duplicate-prefix',[cases[0],cases[0],*cases[2:]]),('later-counterexample',[*cases[:-1],cases[-2]])]:
            fixture={**source,'cases':rows};path=Path(temporary)/(name+'.json');path.write_text(json.dumps(fixture)+'\n');reject(record_path,path,'approved complete matrix required')
        alternate_name,alternate=next((k,v) for k,v in record['libraries'].items() if k!='stock' and v['sha256']!=source['provider']['sha256']);alternate_path=Path(alternate['library']).resolve();assert sha(alternate_path)==alternate['sha256'];genuine=Oracle(alternate_path);genuine.close()
        fixture=json.loads(json.dumps(record));fixture['libraries']['stock']=alternate;fixture['test_input']='Synthetic current core specification with genuine alternate paired FreeType provider';path=Path(temporary)/'provider.json';path.write_text(json.dumps(fixture)+'\n');admitted,_=study.base.prepare(path);assert admitted==alternate_path;reject(path,source_path,'paired FreeType provider differs from retained matrix')
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==files
    assert original=={str(p.relative_to(source_root)):sha(p) for p in source_root.rglob('*') if p.is_file()}
    print('PASS1900 NORMAL sources/references/trials,16TT identities,CFF-off evidence,display-only registration,all images and five early rejections',flush=True);print('gallery:',output/'gallery',flush=True)


if __name__=='__main__':main()
