#!/usr/bin/env python3
"""Observe retained object origins and independently check source/coherence evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import arial_coherence as study
import supersampling as shared
from browser_stroke_axis_test import Oracle
from pixel_references_test import registered,oracle_mask,specimen_layout
from supersampling_test import composed_bytes
BASE='bb54852def911ee26a0a1178c64ce5453101ffa3'
FOCUS='() O O i8! W'
RAW=(('native_mono','Native MONO'),('native_normal','Native NORMAL'),('auto_mono','Auto MONO'),('off_mono','Unhinted MONO'))
TRIALS=(('A','Native raw'),('O','Profile O'),('L','Local cores'),('U','L + half edges'),('K3','3x3 coherence'),('K5','5x5 coherence'))
OBSERVED_ENTRY=r'''
import copy,hashlib,json,pathlib,runpy,sys
root=pathlib.Path(sys.argv[1]);record=sys.argv[2];source=pathlib.Path(sys.argv[3]).resolve();source_root=source.parent;packet=json.loads(source.read_text());target=(root/'tools/arial_coherence.py').resolve()
expected=[(source_root/c['masks']['file'],code) for c in packet['cases'] for code in range(32,127)]
held=[];origins={};calls=[];pending={};exported=[];loader_returns=0
names=('d','l','s','phase_sums','axes','primary','components')
def values(r):return (r['masks']['D'],r['masks']['L'],r['masks']['S'],r['reference']['phase_sums'],r['reference']['axes'],r['overlay']['primary'],r['reference']['components'])
def validate(arguments,path,code):
    found=origins.get(id(arguments[0]))
    if found is None:raise AssertionError('D did not originate at hashed retained loader')
    origin,row=found
    if origin!=path or row['code']!=code or any(a is not b for a,b in zip(arguments,values(row))):raise AssertionError('retained argument object origin mismatch')
    return row

def observer(frame,event,arg):
    global loader_returns
    if frame.f_code.co_name not in ('load_retained','local_coherence','export') or frame.f_code.co_filename!=str(target):return
    name=frame.f_code.co_name
    if name=='load_retained' and event=='return':
        path=pathlib.Path(frame.f_locals['path']).resolve();sha=hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha==frame.f_locals['expected_sha'];held.append(arg);loader_returns+=1
        for row in arg:origins[id(row['masks']['D'])]=(path,row)
    if name=='local_coherence' and event=='call':
        path,code=expected[len(calls)];arguments=tuple(frame.f_locals[n] for n in names);row=validate(arguments,path,code)
        assert frame.f_locals['width']==row['frame']['width']
        entry=dict(source_file=str(path.relative_to(source_root)),code=code,argument_ids=[id(v) for v in arguments],source_record_sha256=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        calls.append(entry);pending[id(frame)]=entry
    if name=='local_coherence' and event=='return':pending.pop(id(frame))['return_sha256']=hashlib.sha256(json.dumps(arg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if name=='export' and event=='return':exported.append(arg)
sys.path[:0]=[str(root/'tools'),str(root/'tests')];sys.argv=[str(target),'--record',record,'--source-manifest',str(source)]
sys.setprofile(observer)
try:namespace=runpy.run_path(str(target),run_name='__main__')
finally:sys.setprofile(None)
assert len(calls)==1900 and loader_returns==24 and not pending
# Equal-by-value copies of every argument must fail the SAME observed origin validator.
first_path,first_code=expected[0];row=next(row for path,row in origins.values() if path==first_path and row['code']==first_code);args=values(row);copy_failures=[]
for i,name in enumerate(names):
    altered=list(args);altered[i]=copy.deepcopy(args[i]);assert altered[i]==args[i] and altered[i] is not args[i]
    try:validate(altered,first_path,first_code)
    except AssertionError:copy_failures.append(name)
    else:raise AssertionError('equal fresh copy passed origin check')
# Also reject genuinely fresh captured native-MONO pixels that equal retained D.
import supersampling as shared
import pixel_references as base
manifest=json.loads((exported[0]/'manifest.json').read_text());native_negative=None
for case in manifest['source_cases']:
    captured=json.loads((exported[0]/case['capture']['file']).read_text());mono=next(c for c in captured['captures'] if c['mode']=='native_mono');source_case=packet['cases'][case['source_case']];path=source_root/source_case['masks']['file']
    for g in mono['glyphs']:
        candidates=[r for p,r in origins.values() if p==path and r['code']==g['code']]
        if not candidates:continue
        row=candidates[-1];fresh=base.numerical.padded(shared.decode_bitmap(g))['pixels']
        if not any(fresh) or fresh!=row['masks']['D']:continue
        modified=list(values(row));modified[0]=fresh
        try:validate(modified,path,g['code'])
        except AssertionError:native_negative=dict(source_file=str(path.relative_to(source_root)),code=g['code'],equal_values=True,different_object=True,rejected=True)
        else:raise AssertionError('equal fresh native-MONO substitute passed origin check')
        break
    if native_negative:break
assert native_negative
proof=dict(calls=calls,loader_returns=loader_returns,copy_failures=copy_failures,native_mono_copy_negative=native_negative)
proof_path=root/'build/arial-coherence'/('origin-proof-'+exported[0].name+'.json')
proof_path.write_text(json.dumps(proof,separators=(',',':'))+'\n')
print('ORIGIN_PROOF '+str(proof_path),file=sys.stderr)
'''


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def read(root,meta):assert sha(root/meta['file'])==meta['sha256'];return json.loads((root/meta['file']).read_text())


def independent(d,l,s,phase_sums,axes,primary,components,width):
    lookup={tuple(p['phase']):p['values'] for p in phase_sums};out={};audit={}
    for name,radius in [('K3',1),('K5',2)]:
        result=d.copy();choices=[]
        for i in primary:
            component=next(c['indices'] for c in components if i in c['indices']);near=sorted(j for j in component if max(abs(j%width-i%width),abs(j//width-i//width))<=radius)
            axis=axes[str(i)]['axis'];phases=sorted(p for p in lookup if not (axis=='x' and p[1]) and not(axis=='y' and p[0]))
            scores=[[*p,sum(lookup[p][j]*lookup[p][j] for j in near)] for p in phases]
            best=sorted(scores,key=lambda a:(-a[2],a[0]*a[0]+a[1]*a[1],a[1],a[0]))[0];q,r=divmod(lookup[tuple(best[:2])][i],16);reference=q+(r>=8);core=max(d[i],reference);result[i]=core
            choices.append(dict(index=i,neighbors=near,axis=axis,phase=best[:2],score=best[2],scores=scores,reference=reference,core=core))
        out[name]=[v+divmod(b-a,2)[0]+(divmod(b-a,2)[1]>=1) for v,a,b in zip(result,l,s)];audit[name]=choices
    return out,audit


def check_panels(output,case,records,methods,font,points,width):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9);focus=[];x=0;adv={r['code']:r['advance_pixels'] for r in records}
    for c in FOCUS:focus.append(dict(code=ord(c),x=x,line=0));x+=adv[ord(c)]
    assert case['focus_placements']==focus and [p['code'] for p in focus]==list(map(ord,FOCUS))
    assert len(case['crops'])==len(methods)*4 and len(case['sheets'])==2
    for crop in case['crops']:
        placements,lines=(focus,1) if crop['kind']=='focus' else (case['placements'],case['lines']);size=(width+12,lines*((points*4+2)//3+6)+14)
        data=composed_bytes({r['code']:{'final':{**r['frame'],'pixels':r['masks'][crop['method']]}} for r in records},placements,points,size)
        if crop['polarity']=='light':data=bytes(255-v for v in data)
        image=Image.open(output/crop['file']);assert list(size)==crop['size'] and image.size==size and image.tobytes()==data and sha(output/crop['file'])==crop['sha256']
    for sheet in case['sheets']:
        fg,bg=(0,255) if sheet['polarity']=='light' else (255,0);fh=(points*4+2)//3+20;bh=case['lines']*((points*4+2)//3+6)+14;by=138+fh;step=width+28;size=(step*len(methods)+20,by+bh+12);assert sheet['size']==list(size) and sheet['body_y']==by and sheet['divider_y']==110+fh
        image=Image.new('L',size,bg);draw=ImageDraw.Draw(image);draw.text((12,10),sheet['title'],font=label,fill=fg);draw.text((12,32),sheet['subtitle'],font=label,fill=fg);draw.text((12,86),'Native focus: '+FOCUS,font=small,fill=fg);draw.text((12,by-16),'Full source specimen',font=small,fill=fg);draw.line((12,110+fh,size[0]-12,110+fh),fill=fg)
        assert len(sheet['crops'])==len(sheet['headings'])==len(methods)
        for col,((key,caption),boxes,heading) in enumerate(zip(methods,sheet['crops'],sheet['headings'])):
            x=12+col*step;assert heading==dict(text=caption,position=[x,64]);draw.text((x,64),caption,font=label,fill=fg);assert boxes['method']==key
            for kind,y in [('body',by),('focus',104)]:
                meta=next(c for c in case['crops'] if c['method']==key and c['kind']==kind and c['polarity']==sheet['polarity']);patch=Image.open(output/meta['file']);assert boxes[kind]==dict(file=meta['file'],box=[x,y,x+patch.width,y+patch.height]);image.paste(patch,(x,y))
        assert Image.open(output/sheet['file']).tobytes()==image.tobytes() and sha(output/sheet['file'])==sheet['sha256']


def check_geometry(output,meta,glyphs,font,oracle):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),10);frame=meta['frame'];reference=glyphs['off_mono'];rasters={k:oracle_mask(oracle,dict(outline=[[*xy,t] for xy,t in zip(g['outline'],g['tags'])],contours=g['contours']),8) for k,g in glyphs.items()};assert meta['rasters']==rasters and meta['scale']==8
    left=min(r['left'] for r in rasters.values())-8;top=min(r['top'] for r in rasters.values())-8;right=max(r['left']+r['width'] for r in rasters.values())+8;bottom=max(r['top']+r['height'] for r in rasters.values())+8;assert frame==dict(left=left,top=top,width=right-left,height=bottom-top)
    column=max(280,frame['width']+24);size=(column*4+20,frame['height']+174);assert meta['size']==list(size);image=Image.new('RGB',size,(24,24,24));draw=ImageDraw.Draw(image);draw.text((12,10),meta['title'],font=label,fill='white');draw.text((12,32),meta['subtitle'],font=small,fill='white')
    assert meta['subtitle']=='NON-NATIVE geometry: captured outline coordinates x8. Not a resized bitmap or larger-DPI hinting.'
    for col,((key,caption),box) in enumerate(zip(RAW,meta['boxes'])):
        g=glyphs[key];assert g['contours']==reference['contours'] and [t&3 for t in g['tags']]==[t&3 for t in reference['tags']]
        delta=[[x-a,y-b] for (x,y),(a,b) in zip(g['outline'],reference['outline'])];xs=[x for x,y in g['outline']];ys=[y for x,y in g['outline']]
        assert meta['metrics'][key]==dict(comparable=True,point_deltas=delta,max_abs_x=max(abs(x) for x,y in delta),max_abs_y=max(abs(y) for x,y in delta),bbox=[min(xs),min(ys),max(xs),max(ys)],bitmap={k:g[k] for k in ('left','top','advance')},bitmap_size=[g['bitmap']['width'],g['bitmap']['rows']])
        x=12+col*column;draw.text((x,58),caption,font=label,fill='white');draw.text((x,82),f'vs unhinted: dx {meta["metrics"][key]["max_abs_x"]}/64, dy {meta["metrics"][key]["max_abs_y"]}/64',font=small,fill='white');patch=Image.frombytes('L',(frame['width'],frame['height']),bytes(registered(rasters[key],frame))).convert('RGB');image.paste(patch,(x,112));baseline=112-frame['top'];draw.line((x,baseline,x+frame['width']-1,baseline),fill=(100,70,30));assert box==dict(method=key,box=[x,112,x+patch.width,112+patch.height],baseline_y=baseline)
    assert Image.open(output/meta['file']).tobytes()==image.tobytes() and sha(output/meta['file'])==meta['sha256']
    return any(g['tags']!=reference['tags'] for g in glyphs.values())


def check_phase(output,meta,r,old,font):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9);w,h=r['frame']['width'],r['frame']['height'];column=max(242,w*20+40);py=h*20+130;positive=[i for i,v in enumerate(old['masks']['D']) if v];size=(column*6+20,py+36+len(positive)*13);assert meta['size']==list(size)
    image=Image.new('RGB',size,(24,24,24));draw=ImageDraw.Draw(image);draw.text((12,10),meta['title'],font=label,fill='white');draw.text((12,32),'Profile O differs from glyph O. Phase rows: row,col | C | E | K3 | K5 (quarter-pixel shifts).',font=small,fill='white');cells=[];previews=[]
    for col,key in enumerate(('D','O','L','U','K3','K5')):
        x=12+col*column;draw.text((x,58),key,font=label,fill='white');data=r['masks'][key];image.paste(Image.frombytes('L',(w,h),bytes(data)).convert('RGB'),(x+36,58));previews.append(dict(method=key,box=[x+36,58,x+36+w,58+h]))
        for xx in range(w):draw.text((x+30+xx*20,82),str(xx+1),font=small,fill='white')
        for yy in range(h):draw.text((x,104+yy*20),str(yy+1),font=small,fill='white')
        for i,value in enumerate(data):
            xx=x+26+(i%w)*20;yy=100+(i//w)*20;draw.rectangle((xx,yy,xx+19,yy+19),fill=(value,)*3,outline=(75,75,75));draw.text((xx+1,yy+4),str(value),font=small,fill='black' if value>=145 else 'white');cells.append(dict(method=key,index=i,row=i//w+1,column=i%w+1,value=value,box=[xx,yy,xx+20,yy+20]))
    assert meta['cells']==cells and meta['previews']==previews and len(meta['rows'])==len(positive)
    for no,(i,row) in enumerate(zip(positive,meta['rows'])):
        c=next(c['phase'] for c in old['reference']['components'] if i in c['indices']);e=old['reference']['axes'][str(i)]['phase'];choices={k:next((a for a in r['audit'][k] if a['index']==i),None) for k in ('K3','K5')};text=f'{i//w+1},{i%w+1} | C {c} | E {e} | K3 {choices["K3"]["phase"] if choices["K3"] else "-"} | K5 {choices["K5"]["phase"] if choices["K5"] else "-"}'
        assert row==dict(index=i,row=i//w+1,column=i%w+1,C=c,E=e,K3=choices['K3'],K5=choices['K5'],text=text,position=[12,py+no*13]);draw.text((12,py+no*13),text,font=small,fill='white')
    assert Image.open(output/meta['file']).tobytes()==image.tobytes() and sha(output/meta['file'])==meta['sha256']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',required=True,type=Path);parser.add_argument('--source-manifest',required=True,type=Path);args=parser.parse_args();source_path=args.source_manifest.resolve();source_root=source_path.parent;source=json.loads(source_path.read_text());original={str(p.relative_to(source_root)):sha(p) for p in source_root.rglob('*') if p.is_file()}
    run=subprocess.run([sys.executable,'-B','-c',OBSERVED_ENTRY,str(ROOT),str(args.record.resolve()),str(source_path)],cwd=ROOT,text=True,capture_output=True,check=True);output=Path(run.stdout.strip().splitlines()[-1]);print('retained export:',output,flush=True);m=json.loads((output/'manifest.json').read_text());proof_path=Path(next(line.removeprefix('ORIGIN_PROOF ') for line in run.stderr.splitlines() if line.startswith('ORIGIN_PROOF ')));proof=json.loads(proof_path.read_text());assert proof['loader_returns']==24 and len(proof['calls'])==1900 and proof['copy_failures']==['d','l','s','phase_sums','axes','primary','components'] and proof['native_mono_copy_negative']['rejected'];print('PASS1900 observed retained origins and equal fresh-native/copy negatives',flush=True)
    assert m['base_git']==BASE and m['study']=='arial-coherence' and m['focus']==FOCUS and m['source_manifest']==os.path.relpath(source_path,output.resolve()) and m['source_manifest_sha256']==sha(source_path);assert m['fonts']==source['fonts'] and m['specimen']==source['specimen']
    assert not Path(m['source_manifest']).is_absolute() and (output/m['source_manifest']).resolve()==source_path
    assert m['raw_methods']==[list(v) for v in RAW] and m['trial_methods']==[list(v) for v in TRIALS]
    for path,digest in m['sources'].items():
        assert sha(ROOT/path)==digest
        if path not in study.NEW_SOURCES:assert digest==hashlib.sha256(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)).hexdigest(),path
    record=json.loads(args.record.read_text());provider=Path(record['libraries']['stock']['library']).resolve();assert m['provider']==dict(file=provider.name,sha256=sha(provider));assert m['record_sha256']==sha(args.record);oracle=Oracle(provider);files={'manifest.json'};fonts={fi:study.base.match_font(meta['family'])[0] for fi,meta in enumerate(source['fonts'])};raw_count=0;geometry_count=0;tag_witnesses=0
    try:
        assert [(c['font'],c['points']) for c in m['source_cases']]==[(0,10),(0,11),(3,10),(3,11)]
        for case in m['source_cases']:
            ci=case['source_case'];oldcase=source['cases'][ci];cap=read(output,case['capture']);raws=read(output,case['records']);font=fonts[case['font']];pt=case['points'];family=source['fonts'][case['font']]['family'];assert Path(cap['provider']).resolve()==provider and cap['points']==pt and cap['target_dpi']==96 and cap['family']==family and cap['style']=='Regular';caps={c['mode']:c for c in cap['captures']};oldcap=read(source_root,oldcase['capture']);oldmono=next(c for c in oldcap['captures'] if c['mode']=='native_mono1');oldnormal=next(c for c in oldcap['captures'] if c['mode']=='native1')
            assert list(caps)==[k for k,t in RAW] and [r['code'] for r in raws]==list(range(32,127));oldrecords=read(source_root,oldcase['masks']);bycode={r['code']:r for r in raws}
            for key,target,policy,flags in [('native_mono',2,'native',163848),('native_normal',0,'native',32776),('auto_mono',2,'auto',131112),('off_mono',2,'off',163850)]:
                c=caps[key];assert c['scale']==1 and c['hint_dpi']==96 and c['x_ppem']==(pt*4+1)//3 and c['target']==target and c['policy']==policy and c['render']==0 and c['load_flags']==flags and c['interpreter']==c['effective_interpreter']==40 and c['cff_hinting_engine']==1 and c['stem_darkening']==False
                assert all(v==dict(get_error=0,set_error=0,no_stem_darkening=True) for v in c['darkening_properties'].values());assert [g['code'] for g in c['glyphs']]==list(range(32,127))
                for g,old,r in zip(c['glyphs'],oldrecords,raws):
                    raw=shared.decode_bitmap(g);outline=dict(outline=[[*xy,t] for xy,t in zip(g['outline'],g['tags'])],contours=g['contours']);assert registered(raw,r['frame'])==r['masks'][key]==registered(oracle_mask(oracle,outline),r['frame']);assert r['advance_pixels']==old['advance_pixels'] and r['actual_advances'][key]==g['advance'];raw_count+=1
                    if key in ('native_mono','native_normal'):
                        prior=(oldmono if key=='native_mono' else oldnormal)['glyphs'][g['code']-32]
                        assert all(g[k]==prior[k] for k in ('code','left','top','advance','outline','tags','contours'))
                        priorraw=shared.decode_bitmap(prior) if key=='native_mono' else {k:prior[k] for k in ('left','top','width','height','pixels')};assert raw==priorraw
            for r in raws:
                masks=[shared.decode_bitmap(caps[k]['glyphs'][r['code']-32]) for k,t in RAW];left=min((a['left'] for a in masks if a['pixels']),default=0)-2;top=min((a['top'] for a in masks if a['pixels']),default=0)-2;right=max((a['left']+a['width'] for a in masks if a['pixels']),default=0)+2;bottom=max((a['top']+a['height'] for a in masks if a['pixels']),default=0)+2;assert r['frame']==dict(left=left,top=top,width=right-left,height=bottom-top)
            assert case['placements']==oldcase['placements'] and case['lines']==oldcase['lines'];assert all(v['title']==f'{family} Regular | {pt}pt | native grayscale SOURCE policies | darkening off' and v['subtitle']=='Same retained MONO advances/baseline. Actual advances recorded separately. No coverage profiles applied.' for v in case['sheets'])
            check_panels(output,case,raws,RAW,font,pt,320)
            assert [g['code'] for g in case['geometry']]==list(map(ord,'O()'))
            normal=caps['native_normal']['glyphs'][79-32];mono=caps['native_mono']['glyphs'][79-32]
            if case['font']==3:
                assert (normal['bitmap']['width'],mono['bitmap']['width'])==((10,8) if pt==10 else (11,10))
                assert max(abs(a[0]-b[0]) for a,b in zip(normal['outline'],mono['outline']))==(64 if pt==10 else 30)
            else:
                assert all(caps['native_normal']['glyphs'][c-32]['outline']==caps['native_mono']['glyphs'][c-32]['outline'] for c in map(ord,'O()'))
            for geom in case['geometry']:
                glyphs={key:caps[key]['glyphs'][geom['code']-32] for key,t in RAW};assert geom['title']==f'{family} Regular {pt}pt | glyph {chr(geom["code"])} | fixed-outline geometry';tag_witnesses+=check_geometry(output,geom,glyphs,font,oracle);geometry_count+=1
            files.update(v['file'] for v in [case['capture'],case['records'],*case['crops'],*case['sheets'],*case['geometry']]);print('checked source',family,pt,flush=True)
    finally:oracle.close()
    assert raw_count==1520 and geometry_count==12 and tag_witnesses>0
    trial_count=0;disagree=agree=0;dot_guard=0;retained_order=[];assert [(c['font'],c['points']) for c in m['cases']]==[(fi,pt) for fi in range(5) for pt in (8,10,11,12)]
    for ci,(case,oldcase) in enumerate(zip(m['cases'],source['cases'])):
        oldrecords=read(source_root,oldcase['masks']);records=read(output,case['masks']);font=fonts[case['font']];pt=case['points'];assert case['source_case']==ci and case['source_masks']==oldcase['masks'] and [r['code'] for r in records]==list(range(32,127))
        for r,old,origin in zip(records,oldrecords,proof['calls'][ci*95:(ci+1)*95]):
            assert origin['source_file']==oldcase['masks']['file'] and origin['code']==r['code'] and origin['source_record_sha256']==canonical(old)
            reference,audits=independent(old['masks']['D'],old['masks']['L'],old['masks']['S'],old['reference']['phase_sums'],old['reference']['axes'],old['overlay']['primary'],old['reference']['components'],old['frame']['width']);u=[a+(b-a+1)//2 for a,b in zip(old['masks']['L'],old['masks']['S'])]
            assert r['source_record_sha256']==canonical(old) and r['frame']==old['frame'] and r['advance_pixels']==old['advance_pixels']
            assert r['masks']=={**{k:old['masks'][k] for k in 'ADOL'},'U':u,**reference} and r['audit']==audits
            assert origin['return_sha256']==canonical([reference,audits]);retained_order.append((old,reference,audits))
            for k in ('K3','K5'):
                assert all(d<=v<=upper<=max(d,e) for d,v,upper,e in zip(old['masks']['D'],r['masks'][k],u,old['masks']['E']))
                assert all(r['masks'][k][i]==u[i] for i in range(len(u)) if i not in old['overlay']['primary'])
                assert all(r['masks'][k][i]<=old['masks']['L'][i] for i in old['overlay']['primary'])
            if r['code']==ord('i'):
                w=r['frame']['width'];allpositive={i for i,v in enumerate(old['masks']['D']) if v}
                for k,radius in [('K3',1),('K5',2)]:
                    for a in audits[k]:
                        i=a['index'];near={j for j in allpositive if max(abs(j%w-i%w),abs(j//w-i//w))<=radius}
                        if near-set(a['neighbors']):dot_guard+=1
            trial_count+=1
        assert not any(records[0]['masks']['K3']) and records[0]['advance_pixels']>0
        places,lines=specimen_layout(read(source_root,oldcase['inputs']));assert case['placements']==places and case['lines']==lines;assert all(v['title']==f'{source["fonts"][case["font"]]["family"]} Regular | {pt}pt | retained local phase-coherence trials' and v['subtitle']=='Profile O is the Arial control. U tentative. K3/K5 can reduce L cores; no optical winner selected.' for v in case['sheets'])
        check_panels(output,case,records,TRIALS,font,pt,240)
        for crop in case['crops']:
            if crop['kind']=='body' and crop['method'] in 'AOL':assert crop['sha256']==next(c['sha256'] for c in oldcase['crops'] if c['method']==crop['method'] and c['polarity']==crop['polarity'])
        # D is retained numerically rather than as a displayed column; its full body is still exact.
        dsize=(252,lines*((pt*4+2)//3+6)+14)
        dbytes=composed_bytes({r['code']:{'final':{**r['frame'],'pixels':r['masks']['D']}} for r in records},places,pt,dsize)
        for polarity in ('light','dark'):
            control=next(c for c in oldcase['crops'] if c['method']=='D' and c['polarity']==polarity)
            expected=bytes(255-v for v in dbytes) if polarity=='light' else dbytes
            assert Image.open(source_root/control['file']).tobytes()==expected and sha(source_root/control['file'])==control['sha256']
        assert [d['code'] for d in case['diagnostics']]==(list(map(ord,'()O')) if case['font']==3 and pt in (10,11) else [])
        for meta in case['diagnostics']:
            r=next(r for r in records if r['code']==meta['code']);old=next(r for r in oldrecords if r['code']==meta['code']);assert meta['title']==f'{source["fonts"][case["font"]]["family"]} Regular {pt}pt | glyph {chr(meta["code"])} | component/local phase choices';check_phase(output,meta,r,old,font)
            for row in meta['rows']:
                if row['C']==row['E']:agree+=1
                else:disagree+=1
        files.update(v['file'] for v in [case['masks'],*case['crops'],*case['sheets'],*case['diagnostics']]);print('checked trials',source['fonts'][case['font']]['family'],pt,flush=True)
    assert trial_count==1900 and agree>0 and disagree>0 and dot_guard>0
    assert len(list((output/'gallery').glob('*.png')))==60 and len(list((output/'diagnostics').glob('*.png')))==6
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==files
    assert original=={str(p.relative_to(source_root)):sha(p) for p in source_root.rglob('*') if p.is_file()}
    # Empty/singleton/half-up/tie/order supplements use only numerical inputs.
    phase=[dict(phase=[x,y],values=[8]) for x in (-1,0,1) for y in (-1,0,1)];axes={'0':dict(axis='xy')};components=[dict(indices=[0])]
    masks,audits=study.local_coherence([0],[0],[0],phase,axes,[],[],1);assert masks==dict(K3=[0],K5=[0])
    masks,audits=study.local_coherence([1],[1],[1],phase,axes,[0],components,1);assert all(a[0]['phase']==[0,0] and a[0]['reference']==1 for a in audits.values())
    assert study.local_coherence([],[],[],[],{},[],[],0)==({'K3':[],'K5':[]},{'K3':[],'K5':[]})
    for phases,expected_phase in [([[-1,0],[1,0],[0,0]],[-1,0]),([[0,-1],[0,1],[0,0]],[0,-1])]:
        sums=[dict(phase=p,values=[0 if p==[0,0] else 2056]) for p in phases]
        result,choices=study.local_coherence([128],[129],[129],sums,{'0':dict(axis='xy')},[0],components,1)
        assert all(v==[129] for v in result.values()) and all(v[0]['phase']==expected_phase for v in choices.values())
    for unrounded,expected_reference in [(2055,128),(2056,129)]:
        result,choices=study.local_coherence([128],[129],[129],[dict(phase=[0,0],values=[unrounded])],{'0':dict(axis='x')},[0],components,1)
        assert all(v[0]['reference']==expected_reference for v in choices.values())
    for old,expected,audits in reversed(retained_order):assert study.local_coherence(old['masks']['D'],old['masks']['L'],old['masks']['S'],list(reversed(old['reference']['phase_sums'])),old['reference']['axes'],old['overlay']['primary'],old['reference']['components'],old['frame']['width'])==(expected,audits)
    # An honestly labeled synthetic record keeps current core declarations and a REAL alternate FT library.
    alternate_name,alternate=next((k,v) for k,v in record['libraries'].items() if k!='stock' and v['sha256']!=source['provider']['sha256'])
    alternate_path=Path(alternate['library']).resolve(strict=True);assert sha(alternate_path)==alternate['sha256']
    genuine=Oracle(alternate_path);genuine.close()
    with tempfile.TemporaryDirectory(prefix='provider-mismatch-',dir=output) as temporary:
        fixture=json.loads(json.dumps(record));fixture['libraries']['stock']=alternate
        fixture['test_input']='Synthetic input: current matching core specification with genuine alternate recorded FreeType provider'
        fixture_path=Path(temporary)/'synthetic-provider-mismatch.json';fixture_path.write_text(json.dumps(fixture)+'\n')
        admitted,_=study.base.prepare(fixture_path);assert admitted==alternate_path
        before_outputs=set((ROOT/'results/arial-coherence').iterdir())
        # The actual entry must reject before even a label-font subprocess, compiler, capture or result writer.
        rejection=r'''
import json,pathlib,runpy,sys
root=pathlib.Path(sys.argv[1]);record=sys.argv[2];source=sys.argv[3];calls=[]
def observe(event,args):
    if event=='subprocess.Popen':calls.append(str(args[0]))
sys.addaudithook(observe)
sys.path[:0]=[str(root/'tools'),str(root/'tests')]
sys.argv=[str(root/'tools/arial_coherence.py'),'--record',record,'--source-manifest',source]
try:runpy.run_path(sys.argv[0],run_name='__main__')
except ValueError as error:
    assert str(error)=='paired FreeType provider differs from retained matrix'
    assert not calls
    print('PASS mismatch rejected before font/compile/capture/output; external calls=0')
else:raise AssertionError('different admitted provider was accepted')
'''
        refused=subprocess.run([sys.executable,'-B','-c',rejection,str(ROOT),str(fixture_path),str(source_path)],cwd=ROOT,text=True,capture_output=True,check=True)
        assert refused.stdout.strip()=='PASS mismatch rejected before font/compile/capture/output; external calls=0'
        assert set((ROOT/'results/arial-coherence').iterdir())==before_outputs
    print('PASS genuine alternate provider admitted by prepare then rejected by retained-provider gate:',alternate_name,alternate['sha256'],flush=True)
    print('PASS source1520/retained1900,causal retained origins,all native/geometry/phase artifacts and complete graph',flush=True);print('gallery:',output/'gallery',flush=True)


if __name__=='__main__':main()
