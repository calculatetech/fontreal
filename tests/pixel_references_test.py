#!/usr/bin/env python3
"""Check the real same-outline reference export and its independent numerical evidence."""
import argparse
import ast
import os
import tempfile
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import supersampling as shared
import native_stems
import pixel_references as driver
import pixel_reference_profiles as candidate
from browser_stroke_axis_test import Oracle
from supersampling_test import composed_bytes
BASE='ccc3707a0be25ca081f90f1415c7789fbedd6956'
PHASES=[(x,y) for x in range(-2,3) for y in range(-2,3)]


def reference(high,d,w):
    """Independent direct sample enumeration, flood fill and scalar cross-sections."""
    h=len(d)//w;hw=high['width'];sums={}
    for dx,dy in PHASES:
        sums[dx,dy]=[sum(high['pixels'][(4*y+4-dy+v)*hw+4*x+4-dx+u]
                          for v in range(4) for u in range(4)) for y in range(h) for x in range(w)]
    def around(i):
        return [j for j in range(len(d)) if j!=i and abs(j//w-i//w)<=1 and abs(j%w-i%w)<=1]
    remaining={i for i,v in enumerate(d) if v};groups=[]
    while remaining:
        component={min(remaining)}
        while True:
            expanded=component|{j for i in component for j in around(i) if j in remaining}
            if component==expanded:break
            component=expanded
        remaining-=component;groups.append(sorted(component))
    order=lambda p:(p[0]*p[0]+p[1]*p[1],p[1],p[0])
    C=[0]*len(d);E=C.copy();decisions=[];axes={};primary=[]
    for group in groups:
        scores={p:sum(sums[p][i]*sums[p][i] for i in group) for p in PHASES}
        phase=sorted(PHASES,key=lambda p:(-scores[p],*order(p)))[0]
        for i in group:C[i]=(sums[phase][i]+8)//16
        decisions.append(dict(indices=group,phase=list(phase),scores=[[*p,scores[p]] for p in PHASES]))
    def pixel(x,y):return d[y*w+x] if 0<=x<w and 0<=y<h else 0
    for i,value in enumerate(d):
        if not value:continue
        x,y=i%w,i//w
        H=1;V=1
        for direction in (-1,1):
            offset=1
            while pixel(x+direction*offset,y):H+=1;offset+=1
            offset=1
            while pixel(x,y+direction*offset):V+=1;offset+=1
        axis='x' if H<V else 'y' if V<H else 'xy'
        allowed=[p for p in PHASES if (H>=V or p[1]==0) and(V>=H or p[0]==0)]
        best=sorted(allowed,key=lambda p:(-sums[p][i],*order(p)))[0]
        E[i]=(sums[best][i]+8)//16;axes[str(i)]=dict(horizontal=H,vertical=V,axis=axis,phase=list(best))
        hor=value>=pixel(x-1,y) and value>=pixel(x+1,y) and(value>pixel(x-1,y) or value>pixel(x+1,y))
        ver=value>=pixel(x,y-1) and value>=pixel(x,y+1) and(value>pixel(x,y-1) or value>pixel(x,y+1))
        if value>=128 and(H>=V or hor) and(V>=H or ver) and(H!=V or hor and ver):primary.append(i)
    O=d.copy();L=d.copy()
    for i in primary:O[i]=max(d[i],C[i]);L[i]=max(d[i],E[i])
    S=L.copy();edges=[]
    for i in primary:
        if L[i]<=d[i]:continue
        for j in around(i):
            if j not in primary and 0<d[j]<d[i] and E[j]>d[j]:
                numerator=d[j]*L[i];q,remainder=divmod(numerator,d[i]);value=min(E[j],q+(2*remainder>=d[i]));S[j]=max(S[j],value);edges.append([i,j,value])
    values=dict(R=[(v+8)//16 for v in sums[0,0]],C=C,E=E,O=O,L=L,S=S)
    return values,dict(components=decisions,axes=axes,primary=primary,edges=edges,sums=sums)


def assert_record(record):
    assert record['coverage_totals']=={k:sum(v) for k,v in record['masks'].items()}
    difference=[b-a for a,b in zip(record['masks']['A'],record['masks']['R'])]
    assert record['same_phase_difference']==dict(changed=sum(v!=0 for v in difference),max_abs=max(map(abs,difference),default=0),coverage_delta=sum(difference))
    w=record['frame']['width'];d=record['masks']['D'];expected,audit=reference(record['high'],d,w)
    for key,values in expected.items():assert record['masks'][key]==values,key
    assert record['reference']['components']==audit['components']
    assert record['reference']['axes']==audit['axes']
    assert record['reference']['phase_sums']==[dict(phase=list(p),values=v) for p,v in sorted(audit['sums'].items())]
    assert record['overlay']['primary']==audit['primary'];assert record['overlay']['edges']==audit['edges']
    for key in ('O','L','S'):
        final=record['masks'][key];delta=record['overlay']['overlays'][key]
        assert delta==[b-a for a,b in zip(d,final)]
        assert all(0<=v<=255 for v in delta)
        assert bytes(a+b for a,b in zip(d,delta))==bytes(final)
        assert all(b==0 for a,b in zip(d,final) if a==0)
        if key!='S':assert all(final[i]==v for i,v in enumerate(d) if i not in audit['primary'])
        ref=record['masks']['C' if key=='O' else 'E']
        assert all(final[i]==v for i,v in enumerate(d) if v>=ref[i])
        assert all(final[i]<=max(v,ref[i]) for i,v in enumerate(d))
    # Ordered phase enumeration is not a hidden tie-breaking input.
    refs,other=candidate.references(record['high'],d,w,tuple(reversed(candidate.PHASES)))
    assert refs=={k:record['masks'][k] for k in ('R','C','E')}
    assert other==record['reference']
    return audit


def registered(source,frame):
    # Independent bearing placement, with image-down top already explicit.
    values=[]
    for y in range(frame['height']):
        for x in range(frame['width']):
            xx=x+frame['left']-source['left'];yy=y+frame['top']-source['top']
            values.append(source['pixels'][yy*source['width']+xx] if 0<=xx<source['width'] and 0<=yy<source['height'] else 0)
    return values


def oracle_mask(oracle,snapshot,scale=1,shift=(0,0)):
    value=oracle.raster(dict(outline=[[x*scale,y*scale,t] for x,y,t in snapshot['outline']],contours=snapshot['contours']),shift)
    return dict(left=value['left'],top=-value['top'],width=value['width'],height=value['height'],pixels=list(bytes.fromhex(value['mask'])))


def verify_grid(output,grid,record,font):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9)
    size=grid['size'];image=Image.new('RGB',size,(24,24,24));draw=ImageDraw.Draw(image)
    draw.text((12,10),grid['title'],font=label,fill='white')
    draw.text((12,32),'Coverage: 0 = no ink, 255 = full ink. dO/dL/dS are positive offsets from D.',font=label,fill='white')
    draw.text((12,54),grid['note'] or 'Common 2px padding. Row/column coordinates start at one. Native previews are not resized.',font=small,fill='white')
    w,h=record['frame']['width'],record['frame']['height'];cell=20;column=max(280,w*cell+40);rh=h*cell+94
    assert size==[column*4+20,86+rh*3]
    assert [v['text'] for v in grid['headings']]==list(driver.TABLES)
    expected_cells=[];expected_previews=[]
    for number,key in enumerate(driver.TABLES):
        x=12+(number%4)*column;y=86+(number//4)*rh
        assert grid['headings'][number]==dict(text=key,position=[x,y])
        draw.text((x,y),key,font=label,fill='white')
        values=record['overlay']['overlays'][key[1:]] if key[0]=='d' else record['masks'][key]
        image.paste(Image.frombytes('L',(w,h),bytes(values)).convert('RGB'),(x+38,y))
        expected_previews.append(dict(method=key,box=[x+38,y,x+38+w,y+h]))
        for xx in range(w):draw.text((x+30+xx*cell,y+30),str(xx+1),font=small,fill='white')
        for yy in range(h):
            draw.text((x,y+50+yy*cell),str(yy+1),font=small,fill='white')
            for xx in range(w):
                i=yy*w+xx;value=values[i];left=x+26+xx*cell;top=y+48+yy*cell
                border=[240,150,70] if key in ('O','L','S') and value!=record['masks']['D'][i] else [75,75,75]
                expected_cells.append(dict(method=key,index=i,value=value,box=[left,top,left+cell,top+cell],border=border,text_position=[left+1,top+4]))
                draw.rectangle((left,top,left+cell-1,top+cell-1),fill=(value,)*3,outline=tuple(border));draw.text((left+1,top+4),str(value),font=small,fill='black' if value>=145 else 'white')
    assert grid['cells']==expected_cells;assert grid['previews']==expected_previews
    actual=Image.open(output/grid['file']).convert('RGB');assert actual.size==image.size and actual.tobytes()==image.tobytes()
    assert shared.sha(output/grid['file'])==grid['sha256']


MATRIX_BASE='ff5a8fe9e7508e932935b094104b3f349c5f928a'
OVERLAP_INPUTS='bde36b2ff327b1a682f3860e21c551234cbab4ef5c1df160756a1403800ddb56'
OVERLAP_RECORDS='f1ea1da468167f733ed01f969d8086d7b2e152b71c820974cf176080e13718a1'
OVERLAP_CROPS={
 'A_light':'cda6ab0d16dec12a562abd0103e888508fd0b177727a39b267fb72acc6265807',
 'A_dark':'adfe009d2e60707a45d7b63a3385bbe1f1cbb336d95fbad75b6b8a254abd4764',
 'D_light':'d0571c090133af757bc53654041f4e3997b9550f7b6ca59032e013fafae57103',
 'D_dark':'cd2c346c5849cd3cf3831dd7175620d658d5260bbf8bd75a687f958c62ccaa2d',
 'O_light':'293ecf62afd533dfea9a21504a5035c18defdd28270909065f2e2ca46dd89e64',
 'O_dark':'2a219a95667df520ffbe6fc7129a51d54c7265f8e5b6752ef511676e100aeae0',
 'L_light':'b4b351fa7c28e45e17fbb712b882498e12949be97e32c303e969519452af1c63',
 'L_dark':'474d3aa75caac6a83b8d417b0a01743c168ca7968d1241436f6f0109479320dd'}


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def specimen_layout(inputs):
    advances={i['code']:i['advance_pixels'] for i in inputs}
    result=[];row=0
    for paragraph in shared.SPECIMEN:
        cursor=0
        for word in paragraph.split(' '):
            codes=list(map(ord,word+' '))
            if cursor and cursor+sum(advances[c] for c in codes)>240:row+=1;cursor=0
            for code in codes:
                if cursor and cursor+advances[code]>240:row+=1;cursor=0
                result.append(dict(code=code,x=cursor,line=row));cursor+=advances[code]
        row+=1
    return result,row


def matrix_check(record_path):
    run=subprocess.run([sys.executable,'-B',str(ROOT/'tools/pixel_references.py'),'--record',str(record_path.resolve()),'--matrix'],text=True,capture_output=True,check=True,cwd=ROOT)
    output=Path(run.stdout.strip().splitlines()[-1]);manifest=json.loads((output/'manifest.json').read_text());print('retained matrix export:',output,flush=True)
    families=('Noto Sans','Nimbus Sans','Inconsolata Nerd Font','Arial','Hack');points=(8,10,11,12)
    methods=[['A','Native raw'],['D','Accepted baseline'],['O','Coherent weak cores'],['L','Local weak cores']]
    assert tuple(native_stems.FONTS)==families and tuple(native_stems.POINTS)==points
    assert manifest['study']=='pixel-references-matrix' and manifest['base_git']==MATRIX_BASE
    assert manifest['methods']==methods and manifest['points']==list(points) and manifest['target_dpi']==96
    assert [(c['font'],c['points']) for c in manifest['cases']]==[(f,p) for f in range(5) for p in points]
    assert [f['family'] for f in manifest['fonts']]==list(families)
    assert set(manifest['sources'])==set(driver.SOURCES)
    for path,sha in manifest['sources'].items():
        assert sha==shared.sha(ROOT/path)
        if path not in ('tools/pixel_references.py','tests/pixel_references_test.py'):
            assert sha==hashlib.sha256(subprocess.check_output(['git','show',MATRIX_BASE+':'+path],cwd=ROOT)).hexdigest(),path
    old=ast.parse(subprocess.check_output(['git','show',MATRIX_BASE+':tools/pixel_references.py'],cwd=ROOT,text=True));current=ast.parse((ROOT/'tools/pixel_references.py').read_text())
    for name in ('process','numbered','benchmark'):
        before=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name);after=next(n for n in current.body if isinstance(n,ast.FunctionDef) and n.name==name)
        assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False),name
    paired=json.loads(record_path.read_text());provider=Path(paired['libraries']['stock']['library']).resolve();assert manifest['provider']==dict(file=provider.name,sha256=shared.sha(provider))
    assert manifest['record_sha256']==shared.sha(record_path)
    assert manifest['provider']['sha256']==paired['libraries']['stock']['sha256']
    fixture=json.loads(driver.FIXTURE.read_text());expected_files={'manifest.json'};overviews=[];crops=[];native_count=0;oracle=Oracle(provider);matches=[]
    for family,meta in zip(families,manifest['fonts']):
        match=subprocess.check_output(['fc-match','-f','%{file}\n%{family}\n%{style}\n%{fontversion}\n',family+':style=Regular'],text=True).splitlines();font=Path(match[0]);matches.append(match)
        assert family in match[1].split(',') and 'Regular' in match[2].split(',')
        assert meta==dict(family=family,matched_family=match[1],file=font.name,sha256=shared.sha(font),style=match[2],revision=match[3])
    try:
        for case in manifest['cases']:
            fi,pt=case['font'],case['points'];family=families[fi];font=Path(matches[fi][0]);label=ImageFont.truetype(str(font),14)
            for key in ('capture','inputs','masks'):
                meta=case[key];assert shared.sha(output/meta['file'])==meta['sha256'];assert meta['file'] not in expected_files;expected_files.add(meta['file'])
            cap=json.loads((output/case['capture']['file']).read_text());inputs=json.loads((output/case['inputs']['file']).read_text());records=json.loads((output/case['masks']['file']).read_text())
            assert family in cap['family'].split(',') and cap['style']=='Regular' and cap['points']==pt and cap['target_dpi']==96
            assert Path(cap['provider']).resolve()==provider and cap['version']==fixture['provider']['version']
            source=next(c for c in cap['captures'] if c['mode']=='native_mono1');properties={k:v for k,v in source.items() if k!='glyphs'};expected_properties={**fixture['properties'],'x_ppem':(pt*4+1)//3};assert properties==expected_properties
            assert [g['code'] for g in source['glyphs']]==[i['code'] for i in inputs]==[r['code'] for r in records]==list(range(32,127))
            for glyph,item,r in zip(source['glyphs'],inputs,records):
                # Independent bitmap decode from the actual pitch and row bytes.
                bm=glyph['bitmap'];rawbytes=bytes.fromhex(bm['rows_hex']);assert bm['pixel_mode']==2
                raw=dict(left=glyph['left'],top=glyph['top'],width=bm['width'],height=bm['rows'],pixels=[rawbytes[y*abs(bm['pitch'])+x] for y in range(bm['rows']) for x in range(bm['width'])])
                assert raw==item['raw'];assert item['snapshot']==dict(outline=[[*xy,t] for xy,t in zip(glyph['outline'],glyph['tags'])],contours=glyph['contours'])
                assert item['advance_pixels']==int(glyph['advance']+.5)==r['advance_pixels']
                frame=dict(left=raw['left']-2,top=raw['top']-2,width=raw['width']+4,height=raw['height']+4);assert frame==r['frame']
                assert registered(raw,frame)==r['masks']['A']==registered(oracle_mask(oracle,item['snapshot']),frame)
                d=native_stems.treatments(bytes(raw['pixels']),raw['width'])[0]['D'];assert registered({**raw,'pixels':list(d)},frame)==r['masks']['D']
                highframe=dict(left=(raw['left']-3)*4,top=(raw['top']-3)*4,width=(raw['width']+6)*4,height=(raw['height']+6)*4)
                assert {k:v for k,v in r['high'].items() if k!='pixels'}==highframe
                assert registered(oracle_mask(oracle,item['snapshot'],4),highframe)==r['high']['pixels'];assert_record(r);native_count+=1
            assert records[0]['advance_pixels']>0 and not any(records[0]['masks']['S'])
            places,lines=specimen_layout(inputs);assert case['placements']==places and case['lines']==lines
            size=(252,lines*((pt*4+2)//3+6)+14);assert len(case['crops'])==8 and len(case['sheets'])==2
            assert [(c['method'],c['polarity']) for c in case['crops']]==[(k,p) for k,title in methods for p in ('light','dark')]
            for crop in case['crops']:
                key,polarity=crop['method'],crop['polarity'];glyphs={r['code']:{'final':{**r['frame'],'pixels':r['masks'][key]}} for r in records}
                pixels=composed_bytes(glyphs,places,pt,size)
                if polarity=='light':pixels=bytes(255-v for v in pixels)
                image=Image.open(output/crop['file']);assert image.size==size==tuple(crop['size']) and image.mode=='L' and image.tobytes()==pixels
                assert shared.sha(output/crop['file'])==crop['sha256'];assert crop['file'] not in expected_files;expected_files.add(crop['file']);crops.append(crop)
                if fi==0 and pt==12:assert crop['sha256']==OVERLAP_CROPS[key+'_'+polarity]
            for sheet in case['sheets']:
                polarity=sheet['polarity'];bg,fg=(255,0) if polarity=='light' else (0,255);sheet_size=(1092,size[1]+116);assert tuple(sheet['size'])==sheet_size
                image=Image.new('L',sheet_size,bg);draw=ImageDraw.Draw(image)
                draw.text((12,10),f'{family} Regular | {pt}pt | 96 DPI | same native hinted outline at 4x',font=label,fill=fg)
                draw.text((12,32),'A/D controls. O coherent and L local weak-core offsets. Local envelope can add excess ink. View at 100%.',font=label,fill=fg)
                assert len(sheet['headings'])==len(sheet['crops'])==4
                for col,((key,title),heading,box) in enumerate(zip(methods,sheet['headings'],sheet['crops'])):
                    x,y=12+col*268,92;assert heading==dict(text=f'{key}: {title}',position=[x,64]);draw.text((x,64),heading['text'],font=label,fill=fg)
                    crop=next(c for c in case['crops'] if c['method']==key and c['polarity']==polarity);patch=Image.open(output/crop['file'])
                    assert box==dict(method=key,box=[x,y,x+patch.width,y+patch.height],file=crop['file']);image.paste(patch,(x,y))
                assert Image.open(output/sheet['file']).tobytes()==image.tobytes() and shared.sha(output/sheet['file'])==sheet['sha256']
                assert sheet['file'] not in expected_files;expected_files.add(sheet['file']);overviews.append(sheet)
            assert {s['polarity'] for s in case['sheets']}=={'light','dark'}
            if fi==0 and pt==12:assert canonical(inputs)==OVERLAP_INPUTS and canonical(records)==OVERLAP_RECORDS
            print(f'checked {family} {pt}pt:95 records,8 crops,2 sheets',flush=True)
    finally:oracle.close()
    assert native_count==1900 and len(crops)==160 and len(overviews)==40
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==expected_files
    assert {p.name for p in (output/'gallery').iterdir()}=={Path(p['file']).name for p in overviews}
    assert not (output/'diagnostics').exists() and not (output/'benchmark.json').exists()
    # Real CLI rejection changes only the opaque fc-match metadata, retaining the real font file.
    response=matches[0]
    for family,style in [('Unrelated Family',response[2]),(response[1],'Bold')]:
        with tempfile.TemporaryDirectory(prefix='admission-',dir=output) as directory:
            script=Path(directory)/'fc-match';payload='\n'.join((response[0],family,style,response[3]))+'\n'
            script.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(payload)+')\n');script.chmod(0o755)
            env=dict(os.environ);env['PATH']=directory+os.pathsep+env['PATH']
            rejected=subprocess.run([sys.executable,'-B',str(ROOT/'tools/pixel_references.py'),'--record',str(record_path.resolve()),'--matrix'],cwd=ROOT,env=env,text=True,capture_output=True)
            assert rejected.returncode!=0 and 'genuine Noto Sans Regular required' in rejected.stderr and not rejected.stdout.strip()
            assert payload.splitlines()[0]==response[0] and shared.sha(Path(response[0]))==manifest['fonts'][0]['sha256']
    print('PASS matrix:20 genuine conditions,1900 independently checked glyphs,160 crops,40 sheets,SS7 overlap and real admission rejection',flush=True)
    print('gallery:',output/'gallery',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',required=True,type=Path);parser.add_argument('--matrix',action='store_true');args=parser.parse_args()
    if args.matrix:return matrix_check(args.record)
    # The real CLI is the only exporter entry used for the composed proof.
    run=subprocess.run([sys.executable,'-B',str(ROOT/'tools/pixel_references.py'),'--record',str(args.record.resolve())],text=True,capture_output=True,check=True,cwd=ROOT)
    output=Path(run.stdout.strip().splitlines()[-1]);manifest=json.loads((output/'manifest.json').read_text());fixture=json.loads(driver.FIXTURE.read_text())
    assert not any(token in driver.FIXTURE.read_text() for token in ('/home/','/storage/','20261117T','/tmp/'))
    assert fixture['source_git']==BASE
    for path,sha in fixture['source_hashes'].items():assert sha==shared.sha(ROOT/path)
    print('retained export:',output,flush=True)
    assert manifest['base_git']==BASE
    expected_methods=[['A','Native raw'],['D','Accepted baseline'],['R','4x same phase'],['O','Coherent weak cores'],['L','Local weak cores'],['S','Local + bounded edges']]
    assert manifest['methods']==expected_methods
    for path,sha in manifest['sources'].items():assert sha==shared.sha(ROOT/path)
    assert set(manifest['sources'])==set(driver.SOURCES)
    for path,sha in manifest['sources'].items():
        if path not in ('tools/pixel_references.py','tests/pixel_reference_profiles.py','tests/pixel_references_test.py','tests/fixtures/pixel-references.json'):
            assert hashlib.sha256(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)).hexdigest()==sha,('opaque source changed',path)
    for key in ('capture','inputs','masks','diagnostics','benchmark'):assert shared.sha(output/manifest[key]['file'])==manifest[key]['sha256']
    inputs=json.loads((output/manifest['inputs']['file']).read_text());records=json.loads((output/manifest['masks']['file']).read_text());diagnostics=json.loads((output/manifest['diagnostics']['file']).read_text())
    assert [r['code'] for r in records]==list(range(32,127));assert [i['code'] for i in inputs]==list(range(32,127))
    assert canonical(inputs)==OVERLAP_INPUTS and canonical(records)==OVERLAP_RECORDS
    cap=json.loads((output/manifest['capture']['file']).read_text());source=next(c for c in cap['captures'] if c['mode']=='native_mono1')
    assert cap['family']=='Noto Sans' and cap['style']=='Regular' and cap['points']==12 and cap['target_dpi']==96
    assert {k:v for k,v in source.items() if k!='glyphs'}==fixture['properties']
    paired=json.loads(args.record.read_text());provider=Path(paired['libraries']['stock']['library']).resolve()
    assert manifest['provider']['sha256']==shared.sha(provider)==paired['libraries']['stock']['sha256']
    assert Path(cap['provider']).resolve()==provider
    match=subprocess.check_output(['fc-match','-f','%{file}\n%{family}\n%{style}\n%{fontversion}\n','Noto Sans:style=Regular'],text=True).splitlines();font=Path(match[0])
    assert manifest['font']==dict(family='Noto Sans',matched_family=match[1],file=font.name,sha256=shared.sha(font),style=match[2],revision=match[3])
    assert fixture['font']['sha256']==shared.sha(font)
    oracle=Oracle(provider)
    try:
        for item,r,g in zip(inputs,records,source['glyphs']):
            raw=shared.decode_bitmap(g);assert raw==item['raw'];assert item['snapshot']==dict(outline=[[*xy,t] for xy,t in zip(g['outline'],g['tags'])],contours=g['contours'])
            assert item['advance_pixels']==int(g['advance']+.5)==r['advance_pixels']
            frame=dict(left=raw['left']-2,top=raw['top']-2,width=raw['width']+4,height=raw['height']+4)
            assert frame==r['frame'];assert registered(raw,frame)==r['masks']['A']
            assert registered(oracle_mask(oracle,item['snapshot']),frame)==r['masks']['A']
            d=native_stems.treatments(bytes(raw['pixels']),raw['width'])[0]['D'];assert registered({**raw,'pixels':list(d)},frame)==r['masks']['D']
            highframe=dict(left=(raw['left']-3)*4,top=(raw['top']-3)*4,width=(raw['width']+6)*4,height=(raw['height']+6)*4)
            assert {k:v for k,v in r['high'].items() if k!='pixels'}==highframe
            assert registered(oracle_mask(oracle,item['snapshot'],4),highframe)==r['high']['pixels']
            assert_record(r)
        for pin in fixture['actual']:
            r=next(r for r in records if r['code']==pin['code']);item=next(i for i in inputs if i['code']==pin['code'])
            assert item['snapshot']==pin['snapshot'] and item['raw']==pin['raw']
            expected=pin['expected']
            assert r['frame']==expected['frame'] and r['high']==expected['high']
            assert all(r['masks'][key]==expected[key] for key in ('A','D','R','C','E','O','L','S'))
            assert r['reference']['components']==expected['components'];assert r['reference']['axes']==expected['axes'];assert r['overlay']['primary']==expected['primary'];assert r['overlay']['edges']==expected['edges']
        assert len(diagnostics)==len(fixture['synthetic'])
        for pin,r in zip(fixture['synthetic'],diagnostics):
            assert pin['name']==r['name'];assert oracle_mask(oracle,pin['snapshot'])==pin['raw'];assert_record(r)
            assert r['frame']==pin['expected']['frame'];assert r['high']==pin['expected']['high']
            assert all(r['masks'][k]==pin['expected'][k] for k in ('A','D','R','C','E','O','L','S'))
            # Directly translate the same high-res outline; do not shift its final native bitmap.
            highframe={k:v for k,v in r['high'].items() if k!='pixels'}
            for dx,dy in ((-2,1),(1,0),(0,-2)):
                pixels=registered(oracle_mask(oracle,pin['snapshot'],4,(dx*64,-dy*64)),highframe)
                hw=highframe['width'];w=r['frame']['width'];h=r['frame']['height']
                reduced=[(sum(pixels[(4*y+4+v)*hw+4*x+4+u] for v in range(4) for u in range(4))+8)//16 for y in range(h) for x in range(w)]
                expected=next(p['values'] for p in r['reference']['phase_sums'] if p['phase']==[dx,dy])
                assert reduced==[(v+8)//16 for v in expected]
    finally:oracle.close()
    # External analytic geometry pins, rather than only the scalar algorithm.
    diag={r['name']:r for r in diagnostics}
    assert not any(diag['empty']['masks']['A'])
    assert diag['aligned']['masks']['A']==diag['aligned']['masks']['R']
    hole=next(v for v in fixture['synthetic'] if v['name']=='hole')['raw']
    assert hole['left']==-1 and hole['top']==-5 and hole['width']==4 and hole['height']==5
    assert hole['pixels']==[255,255,255,255]+[255,0,0,255]*3+[255,255,255,255]
    negative=next(v for v in fixture['synthetic'] if v['name']=='negative-bearing-y')['raw']
    assert negative['left']==-2 and negative['top']==-3 and negative['pixels']==[31,31]+[127,127]*2+[31,31]
    assert set(v for v in diag['tied-stem']['masks']['A'] if v)=={127}
    t=diag['tied-stem'];w=t['frame']['width'];mid=4*w+2
    assert t['masks']['D'][mid:mid+2]==[128,128]
    assert t['masks']['E'][mid:mid+2]==[255,255] and t['masks']['L'][mid:mid+2]==[255,255]
    assert t['masks']['O'][mid:mid+2]==[255,128]
    assert t['reference']['components'][0]['phase']==[-2,0] and 'limitation' in t['note']
    assert sum(t['masks']['L'])>sum(t['masks']['O'])>sum(t['masks']['D'])
    nativehalf=diag['native-half-stem'];assert nativehalf['masks']['A']==nativehalf['masks']['D']==nativehalf['masks']['O']==nativehalf['masks']['L']==nativehalf['masks']['S']
    halfsource=next(v for v in fixture['synthetic'] if v['name']=='native-half-stem');assert list(native_stems.treatments(bytes(halfsource['raw']['pixels']),halfsource['raw']['width'])[0]['D'])==halfsource['D']
    assert diag['one-pixel']['overlay']['primary'] and not diag['below-majority']['overlay']['primary']
    assert diag['strong-thin']['masks']['S']==diag['strong-thin']['masks']['D']
    edge=diag['edge-midpoint-overlap'];D=edge['masks']['D'];L=edge['masks']['L'];E=edge['masks']['E'];edges=edge['overlay']['edges']
    assert any((D[j]*L[i])%D[i]*2==D[i] for i,j,value in edges)
    assert any(n>1 for n in Counter(j for i,j,value in edges).values())
    bound=diag['edge-own-bound'];bd=bound['masks']['D'];bl=bound['masks']['L'];be=bound['masks']['E']
    assert any(value==be[j] and (2*bd[j]*bl[i]+bd[i])//(2*bd[i])>be[j] for i,j,value in bound['overlay']['edges'])
    assert any(r['masks']['D'][j]>=r['masks']['E'][j] and r['masks']['S'][j]==r['masks']['D'][j] for r in records for i in r['overlay']['primary'] if r['masks']['L'][i]>r['masks']['D'][i] for j in candidate.neighbors(i,r['frame']['width'],r['frame']['height']) if 0<r['masks']['D'][j]<r['masks']['D'][i])
    assert len(diag['diagonal-contact']['reference']['components'])==1
    assert len(diag['disconnected']['reference']['components'])==3
    dup=diag['duplicate-prefix-later']['reference']['components'];assert len(dup)==3 and dup[0]['scores']==dup[1]['scores'] and dup[2]['scores']!=dup[0]['scores']
    assert diag['horizontal']['reference']['components'][0]['phase']==[0,-2]
    assert diag['half-square']['reference']['components'][0]['phase']==[-2,-2]
    assert {'x','y','xy'}<={a['axis'] for r in diagnostics for a in r['reference']['axes'].values()}
    # Removing unrelated components leaves a retained component's entire phase scores unchanged.
    r=diag['disconnected'];first=r['reference']['components'][0];d=[v if i in first['indices'] else 0 for i,v in enumerate(r['masks']['D'])]
    _,audit=candidate.references(r['high'],d,r['frame']['width']);assert audit['components']==[first]
    i=next(r for r in records if r['code']==ord('i'));bang=next(r for r in records if r['code']==ord('!'));eight=next(r for r in records if r['code']==ord('8'))
    assert [next(r for r in records if r['code']==ord(ch))['same_phase_difference']['max_abs'] for ch in 'i8!W']==[13,12,9,4]
    assert [c['phase'] for c in i['reference']['components']]==[[1,0],[1,0]]
    assert [c['phase'] for c in bang['reference']['components']]==[[1,0],[-1,0]]
    assert len(set(v for v in i['overlay']['overlays']['O'] if v))>1
    assert any(eight['overlay']['overlays']['O']) and any(eight['overlay']['overlays']['L'])
    assert len({bang['masks']['L'][j] for j in bang['overlay']['primary']})>1
    higher=next(c for c in cap['captures'] if c['mode']=='native4')
    assert any([[x*4,y*4] for x,y in g['outline']]!=next(h for h in higher['glyphs'] if h['code']==g['code'])['outline'] for g in source['glyphs'])
    assert set(records[0]['masks'])=={'A','D','R','C','E','O','L','S'} and not any(records[0]['masks']['S']) and records[0]['advance_pixels']>0
    # The real CLI consumes A,B earlier, then renamed B',A' later.
    names=[r['name'] for r in fixture['synthetic']]
    assert len(names)==len(set(names))
    assert names.index('aligned')<names.index('taper')<names.index('reordered-taper')<names.index('relabeled-aligned')
    assert names[-2:]==['reordered-taper','relabeled-aligned']
    upstream={r['name']:r for r in fixture['synthetic']}
    assert upstream['aligned']['snapshot']!=upstream['taper']['snapshot']
    for original,renamed in [('aligned','relabeled-aligned'),('taper','reordered-taper')]:
        assert original!=renamed
        for key in ('snapshot','raw','D','expected'):assert upstream[original][key]==upstream[renamed][key]
        # All saved source rasters, C/E audits, overlays and final masks agree.
        assert {k:v for k,v in diag[original].items() if k not in ('name','note')}=={k:v for k,v in diag[renamed].items() if k not in ('name','note')}

    places,lines=shared.layout({v['code']:v for v in inputs},240);assert places==manifest['placements'] and lines==manifest['lines']
    for meta in manifest['crops']:
        glyphs={r['code']:{'final':{**r['frame'],'pixels':r['masks'][meta['method']]}} for r in records}
        size=(252,lines*22+14)
        image=Image.frombytes('L',size,composed_bytes(glyphs,places,12,size))
        if meta['polarity']=='light':image=ImageChops.invert(image)
        saved=Image.open(output/meta['file']);assert saved.size==tuple(meta['size']) and saved.tobytes()==image.tobytes() and shared.sha(output/meta['file'])==meta['sha256']
        if meta['method'] in 'ADOL':assert meta['sha256']==OVERLAP_CROPS[meta['method']+'_'+meta['polarity']]
    for sheet in manifest['sheets']:
        bg,fg=(255,0) if sheet['polarity']=='light' else (0,255);image=Image.new('L',tuple(sheet['size']),bg);draw=ImageDraw.Draw(image);label=ImageFont.truetype(str(font),14)
        draw.text((12,10),'Noto Sans Regular | 12pt | 96 DPI | same native hinted outline at 4x',font=label,fill=fg)
        draw.text((12,32),'A/D controls. R reference only. O/L/S weak-only overlays. Local envelope can add excess ink. View at 100%.',font=label,fill=fg)
        for col,((key,title),box,heading) in enumerate(zip(driver.METHODS,sheet['crops'],sheet['headings'])):
            assert heading==dict(text=f'{key}: {title}',position=[12+268*col,64]);draw.text(tuple(heading['position']),heading['text'],font=label,fill=fg)
            patch=Image.open(output/box['file']);x,y=12+268*col,92;assert box['box']==[x,y,x+patch.width,y+patch.height] and box['method']==key;image.paste(patch,(x,y))
        assert Image.open(output/sheet['file']).tobytes()==image.tobytes();assert shared.sha(output/sheet['file'])==sheet['sha256']
    assert len(manifest['grids'])==3
    for grid,code in zip(manifest['grids'],map(ord,'i8!')):
        assert grid['title']==f'Noto Sans Regular / 12pt / {chr(code)} / registered pixel references' and grid['note']==''
        verify_grid(output,grid,next(r for r in records if r['code']==code),font)
    assert len(manifest['diagnostics']['grids'])==len(diagnostics)
    for grid,r in zip(manifest['diagnostics']['grids'],diagnostics):
        assert grid['title']=='Analytic outline / '+r['name'] and grid['note']==r['note']
        verify_grid(output,grid,r,font)
    grids_by_name={r['name']:g for r,g in zip(diagnostics,manifest['diagnostics']['grids'])}
    for original,renamed in [('aligned','relabeled-aligned'),('taper','reordered-taper')]:
        first,second=grids_by_name[original],grids_by_name[renamed]
        assert first['title']!=second['title'] and first['file']!=second['file']
        assert [v['method'] for v in first['previews']]==list(driver.TABLES)==[v['method'] for v in second['previews']]
        for a,b in zip(first['previews'],second['previews']):
            assert Image.open(output/first['file']).crop(a['box']).tobytes()==Image.open(output/second['file']).crop(b['box']).tobytes()
    assert len(manifest['crops'])==12 and len(manifest['sheets'])==2
    expected_files={'manifest.json','benchmark.json','sources/capture.json','sources/inputs.json','masks/native.json','diagnostics/masks.json'}|{m['file'] for m in manifest['crops']+manifest['sheets']+manifest['grids']+manifest['diagnostics']['grids']}
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==expected_files
    # Three real numeric repetitions must reproduce independently associated stage bytes.
    timing=json.loads((output/'benchmark.json').read_text());assert timing['repetitions']==3 and timing['glyphs_per_run']==95
    expected_stage={'native_raster':b''.join(bytes(i['raw']['pixels']) for i in inputs),'high_raster':b''.join(bytes(r['high']['pixels']) for r in records),'references':b''.join(bytes(r['masks']['R']+r['masks']['C']+r['masks']['E']) for r in records),'overlays':b''.join(bytes(r['overlay']['overlays']['O']+r['overlay']['overlays']['L']+r['overlay']['overlays']['S']) for r in records),'stored_apply':b''.join(bytes(r['masks']['S']) for r in records)}
    for run in timing['runs']:
        assert run['counts']==dict.fromkeys(expected_stage,95)
        assert run['checksums']=={k:hashlib.sha256(v).hexdigest() for k,v in expected_stage.items()}
    assert len(timing['runs'])==3 and set(timing['stages'])==set(expected_stage)
    for stats in timing['stages'].values():assert stats['count']==285 and 0<=stats['median_ns']<=stats['p95_ns']<=stats['total_ns']
    payload=timing['payload_bytes'];assert payload['native']==len(expected_stage['native_raster']) and payload['high']==len(expected_stage['high_raster'])
    assert payload['common_native']==payload['one_stored_overlay']==sum(len(r['masks']['D']) for r in records) and payload['three_stored_overlays']==3*payload['common_native']
    assert timing['dimensions']==[dict(code=i['code'],native=[i['raw']['width'],i['raw']['height']],common=[r['frame']['width'],r['frame']['height']],high=[r['high']['width'],r['high']['height']]) for i,r in zip(inputs,records)]
    print('PASS: all95 actual glyphs, pinned/analytic references, all O/L/S bytes, timing stages and final PNGs',flush=True)
    print('gallery:',output/'gallery',flush=True)


if __name__=='__main__':main()
