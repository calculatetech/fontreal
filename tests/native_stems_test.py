#!/usr/bin/env python3
"""Check exact accepted D with compact-only peak and proportional treatments."""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
from math import ceil,floor
from statistics import median
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import native_stems as study
from supersampling_test import composed_bytes

BASE='1ba7c1dde889613cc08c2ae115e70c9b7328d592'
PROBE_BASE='29d3fec5c929bad39e60d3ffbb23aeeb263169a3'
FONTS=('Noto Sans','Nimbus Sans','Inconsolata Nerd Font','Arial','Hack')
POINTS=(8,10,11,12)
KEYS='ADFG'
TITLES=['Native 1x MONO-gray','Accepted baseline','D + compact peaks','D + compact blend']
CHARS='Hinm8W:!'


def old_function(path,name):
    source=subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT,text=True)
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    env=dict(Counter=Counter,defaultdict=defaultdict,floor=floor,median=median,MODES=('baseline','native-area','gain-area'))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<immutable accepted recipe>','exec'),env)
    return env[name]


def components(values,w):
    remaining={i for i,v in enumerate(values) if v};groups=[];h=len(values)//w if w else 0
    while remaining:
        first=min(remaining);remaining.remove(first);group={first};queue=[first]
        while queue:
            i=queue.pop();y,x=divmod(i,w)
            for yy in range(max(0,y-1),min(h,y+2)):
                for xx in range(max(0,x-1),min(w,x+2)):
                    j=yy*w+xx
                    if j in remaining:remaining.remove(j);group.add(j);queue.append(j)
        groups.append(group)
    return groups


def compact_oracle(d,w,target):
    f=bytearray(d);g=bytearray(d);audit=[]
    for group in components(d,w):
        left=min(i%w for i in group);right=max(i%w for i in group)+1
        top=min(i//w for i in group);bottom=max(i//w for i in group)+1
        peak=max(d[i] for i in group);eligible=right-left<=3 and bottom-top<=3 and peak<target
        selected=sorted(i for i in group if d[i]==peak) if eligible else []
        audit.append(dict(pixels=sorted(group),box=[left,top,right,bottom],peak=peak,eligible=eligible,peaks=selected))
        if eligible:
            for i in selected:f[i]=target
            for i in group:g[i]=max(d[i],(2*d[i]*target+peak)//(2*peak))
    return bytes(f),bytes(g),dict(components=audit)


def expected(raw,w,recipe):
    concentrate,refine=recipe
    fitted,pairs=concentrate(raw,raw,w,near_ties=True)
    fitted,profile=refine(raw,fitted['native-area'],w,connected=True)
    d=fitted['corners'];weight=target_oracle(raw)
    f,g,audit=compact_oracle(d,w,weight['target'])
    return dict(A=raw,D=d,F=f,G=g),dict(D=pairs),weight,dict(D=profile,compact=audit)


def verify_record(record,recipe):
    raw=bytes(record['raw']['pixels']);w=record['raw']['width']
    masks,pairs,weight,stage=expected(raw,w,recipe)
    assert record['masks']=={k:list(v) for k,v in masks.items()}
    assert record['pairs']==pairs and record['weighted']==weight and record['profile']==stage
    assert record['coverage_deltas']=={k:sum(v)-sum(raw) for k,v in masks.items()}
    assert record['coverage_delta_D']==sum(masks['D'])-sum(raw)
    for data in masks.values():assert len(data)==len(raw) and all(bool(a)==bool(b) for a,b in zip(raw,data))
    selected={i for group in stage['compact']['components'] if group['eligible'] for i in group['pixels']}
    assert all(masks[k][i]==masks['D'][i] for k in 'FG' for i in range(len(raw)) if i not in selected)
    assert all(masks[k][i]>=masks['D'][i] for k in 'FG' for i in range(len(raw)))
    return masks,stage


def pinned_fixtures(recipe):
    fixture=read(study.COMPACT_FIXTURE);assert fixture['source_commit']==BASE
    for path,digest in fixture['sources'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT)).hexdigest()==digest
    for r in fixture['records']:
        actual=study.mask_record(r['code'],r['advance_pixels'],r['raw']);verify_record(actual,recipe)
        assert all(actual['masks'][k]==v for k,v in r['expected'].items())
    for case in fixture['synthetic']:
        actual=study.mask_record(88,0,dict(left=0,top=0,width=case['width'],height=case['height'],pixels=case['raw']))
        verify_record(actual,recipe)
        assert actual['weighted']['target']==case['target']
        assert all(actual['masks'][k]==v for k,v in case['expected'].items()),case['name']
        selected=actual['profile']['compact']['components']
        if case['name']=='duplicate-prefix-later':
            assert [g['pixels'] for g in selected if g['eligible']]==[[0,1],[3,4],[6,7]]
        if case['name'] in ('width-three-four','height-three-four'):
            assert [g['eligible'] for g in selected]==[True,False,True,False]
    historical=read(study.FIXTURE)
    assert study.shared.sha(study.FIXTURE)=='1a1a6ef25df345010d86aad1b2ccf892993278233fd1f80ed1ca8d41a5a29466'
    for r in historical['records']:
        actual=study.mask_record(r['code'],r['advance_pixels'],r['raw']);verify_record(actual,recipe)
        assert actual['masks']['D']==r['expected']['D']
    for raw,w in ((b'',0),(bytes([77]),1),(bytes([0,0]),2)):
        assert study.treatments(raw,w)==expected(raw,w,recipe)
    print('PASS pinned actual dots/D, frozen-D overlap, tied/saturated/disconnected/oversized/later components and weighted targets',flush=True)
def read(path,digest=None):
    if digest:assert study.shared.sha(path)==digest,path
    return json.loads(path.read_text())

def decoded(g):
    b=g['bitmap'];assert b['pixel_mode']==2
    data=bytes.fromhex(b['rows_hex']);stride=abs(b['pitch'])
    assert len(data)==stride*b['rows'] and stride>=b['width']
    return dict(left=g['left'],top=g['top'],width=b['width'],height=b['rows'],
                pixels=list(b''.join(data[y*stride:y*stride+b['width']] for y in range(b['rows']))))

def target_oracle(raw):
    positive=sorted((v for v in raw if v),reverse=True)
    if positive:
        cutoff=positive[(len(positive)+3)//4-1];refs=[v for v in positive if v>=cutoff]
        numerator=sum(v*v for v in refs);denominator=sum(refs)
        target=(2*numerator+denominator)//(2*denominator)
    else:cutoff=target=numerator=denominator=0;refs=[]
    return dict(target=target,reference_cutoff=cutoff,reference_count=len(refs),numerator=numerator,denominator=denominator)

def frozen_layout():
    source=subprocess.check_output(['git','show',f'{BASE}:tools/supersampling.py'],cwd=ROOT,text=True)
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='layout')
    specimen=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SPECIMEN' for t in n.targets))
    namespace=dict(SPECIMEN=ast.literal_eval(specimen))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<immutable layout>','exec'),namespace)
    return namespace['layout'],namespace['SPECIMEN']

def reference_probe(work,provider):
    source=subprocess.check_output(['git','show',f'{PROBE_BASE}:tests/supersampling_probe.cpp'],cwd=ROOT,text=True)
    for old,new in [('FT_Set_Char_Size(face,0,points*64,384,384)','FT_Set_Char_Size(face,0,points*64,96,96)'),
                    ('{{"mode",name},{"scale",4},{"hint_dpi",384}','{{"mode",name},{"scale",1},{"hint_dpi",96}')]:
        assert source.count(old)==1;source=source.replace(old,new)
    path=work/'reference.cpp';path.write_text(source);probe=work/'reference'
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','freetype2'],text=True))
    subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(path),'-o',str(probe),*flags,'-ldl'],check=True)
    env=dict(os.environ);env.pop('LD_PRELOAD',None);env.pop('FREETYPE_PROPERTIES',None);env['LD_LIBRARY_PATH']=str(provider.parent)
    return probe,env

def check_grid(directory,grid,records,font_file,characters):
    assert study.shared.sha(directory/grid['file'])==grid['sha256'];im=Image.open(directory/grid['file'])
    assert list(im.size)==grid['size'] and im.mode=='RGB'
    rs={r['code']:r for r in records}
    column=max(242,max(rs[ord(ch)]['raw']['width'] for ch in characters)*22+48)
    tops={};y=90
    for ch in characters:
        tops[ord(ch)]=y;y+=rs[ord(ch)]['raw']['height']*22+100
    assert grid['cell_size']==22 and list(im.size)==[column*4+16,y]
    small=ImageFont.truetype(font_file,9)
    label=ImageFont.truetype(font_file,14)
    assert len(grid['headings'])==4
    for col,heading in enumerate(grid['headings']):
        key='ADFG'[col];assert heading['method']==key and heading['text']==f'{key}: {TITLES[col]}'
        x,y=heading['position'];width=column
        assert [x,y]==[12+col*width,60]
        patch=Image.new('RGB',(width,24),(24,24,24))
        ImageDraw.Draw(patch).text((0,0),heading['text'],font=label,fill='white')
        assert im.crop((x,y,x+width,y+24)).tobytes()==patch.tobytes()
    expected_cells={(ord(ch),key,i) for ch in characters for key in 'ADFG' for i in range(len(rs[ord(ch)]['raw']['pixels']))}
    assert {(c['code'],c['method'],c['index']) for c in grid['cells']}==expected_cells and len(grid['cells'])==len(expected_cells)
    for cell in grid['cells']:
        r=rs[cell['code']];v=r['masks'][cell['method']][cell['index']];assert cell['value']==v
        col='ADFG'.index(cell['method']);yy,xx=divmod(cell['index'],r['raw']['width'])
        x=12+col*column+28+xx*22;y=tops[cell['code']]+46+yy*22
        assert cell['box']==[x,y,x+22,y+22] and cell['text_position']==[x+2,y+4]
        border=(255,170,55) if v!=r['raw']['pixels'][cell['index']] else (75,75,75)
        assert cell['border']==list(border)
        patch=Image.new('RGB',(22,22));draw=ImageDraw.Draw(patch)
        draw.rectangle((0,0,21,21),fill=(v,)*3,outline=border)
        draw.text((2,4),str(v),font=small,fill='black' if v>=145 else 'white')
        assert im.crop(tuple(cell['box'])).tobytes()==patch.tobytes()
    expected_previews={(ord(ch),key) for ch in characters for key in 'ADFG'}
    assert {(p['code'],p['method']) for p in grid['previews']}==expected_previews
    assert len(grid['previews'])==len(expected_previews)
    for preview in grid['previews']:
        r=rs[preview['code']];expected_im=Image.frombytes('L',(r['raw']['width'],r['raw']['height']),bytes(r['masks'][preview['method']])).convert('RGB')
        x=12+'ADFG'.index(preview['method'])*column+30;y=tops[preview['code']]
        assert preview['box']==[x,y,x+r['raw']['width'],y+r['raw']['height']]
        assert im.crop(tuple(preview['box'])).tobytes()==expected_im.tobytes()

def dot_region(g):
    contours=[];start=0
    for end in g['contours']:
        contours.append(g['outline'][start:end+1]);start=end+1
    dot=max(contours,key=lambda ps:min(p[1] for p in ps))
    top=-ceil(max(p[1] for p in dot)/64);bottom=-floor(min(p[1] for p in dot)/64)
    mask=decoded(g)
    return {i for i,v in enumerate(mask['pixels']) if v and top<=mask['top']+i//mask['width']<bottom},[top,bottom]


def diagnostic_check(directory,manifest,recipe):
    diagnostic=manifest['diagnostic'];historical=read(study.FIXTURE)
    assert diagnostic['fixture']=='tests/fixtures/native-connected-stems.json' and diagnostic['fixture_sha256']==study.shared.sha(study.FIXTURE)
    assert diagnostic['masks']=='diagnostics/retained-masks.json'
    rows=read(directory/diagnostic['masks'],diagnostic['masks_sha256']);assert [r['code'] for r in rows]==[72,105]
    for r,source in zip(rows,historical['records']):
        assert r['raw']==source['raw'];verify_record(r,recipe);assert r['masks']['D']==source['expected']['D']
    assert diagnostic['grid']['file']=='diagnostics/retained-grids.png'
    check_grid(directory,diagnostic['grid'],rows,manifest['fonts'][0]['file'],'Hi')
    compact=manifest['compact_diagnostics'];fixture=read(study.COMPACT_FIXTURE)
    assert compact['fixture']=='tests/fixtures/native-compact-features.json' and compact['fixture_sha256']==study.shared.sha(study.COMPACT_FIXTURE)
    assert [(g['font'],g['points']) for g in compact['cases']]==[(0,8),(0,10),(2,8),(4,8)]
    expected_files={'retained-masks.json','retained-grids.png'}
    for case in compact['cases']:
        stem=f'diagnostics/actual-{case["font"]}-{case["points"]}'
        assert case['masks']==stem+'.json' and case['grid']['file']==stem+'.png'
        rows=read(directory/case['masks'],case['masks_sha256'])
        source=[r for r in fixture['records'] if (r['font'],r['points'])==(case['font'],case['points'])]
        assert [r['code'] for r in rows]==[r['code'] for r in source]
        for r,s in zip(rows,source):
            assert r['raw']==s['raw'];verify_record(r,recipe)
            assert all(r['masks'][k]==v for k,v in s['expected'].items())
        check_grid(directory,case['grid'],rows,manifest['fonts'][0]['file'],''.join(chr(r['code']) for r in source))
        expected_files|={Path(case['masks']).name,Path(case['grid']['file']).name}
    assert [c['name'] for c in compact['synthetic']]==[c['name'] for c in fixture['synthetic']]
    for case,source in zip(compact['synthetic'],fixture['synthetic']):
        stem='diagnostics/compact-'+source['name']
        assert case['masks']==stem+'.json' and case['grid']['file']==stem+'.png'
        rows=read(directory/case['masks'],case['masks_sha256']);assert len(rows)==1 and rows[0]['code']==88
        record=rows[0];assert record['raw']==dict(left=0,top=0,width=source['width'],height=source['height'],pixels=source['raw'])
        verify_record(record,recipe)
        assert record['weighted']['target']==source['target'] and all(record['masks'][k]==v for k,v in source['expected'].items())
        assert case['grid']['font'] is None and case['grid']['points']==0
        check_grid(directory,case['grid'],rows,manifest['fonts'][0]['file'],'X')
        image=Image.open(directory/case['grid']['file']);header=Image.new('RGB',(image.width,24),(24,24,24))
        ImageDraw.Draw(header).text((12,0),'Synthetic '+source['name']+' | numerical coverage mask',font=ImageFont.truetype(manifest['fonts'][0]['file'],14),fill='white')
        assert image.crop((0,10,image.width,34)).tobytes()==header.tobytes()
        expected_files|={Path(case['masks']).name,Path(case['grid']['file']).name}
    assert {p.name for p in (directory/'diagnostics').iterdir()}==expected_files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',required=True,type=Path);args=parser.parse_args()
    recipe=(old_function('tests/stem_core_test.py','concentrate'),old_function('tests/stroke_profiles.py','refine'))
    pinned_fixtures(recipe);layout,specimen=frozen_layout();record=read(args.record);provider=Path(record['libraries']['stock']['library']).resolve()
    output=subprocess.check_output([sys.executable,'-B',str(ROOT/'tools/native_stems.py'),'--record',str(args.record.resolve())],text=True)
    directory=Path(output.strip().splitlines()[-1]);manifest=read(directory/'manifest.json')
    assert directory.parent.resolve()==(ROOT/'results/native-stems').resolve()
    assert manifest['study']=='native-stems' and manifest['target_dpi']==96 and manifest['blend']=='encoded'
    assert manifest['methods']==[[k,t] for k,t in zip(KEYS,TITLES)] and manifest['points']==list(POINTS)
    assert manifest['specimen']==list(specimen) and manifest['placement']=='native MONO whole-pixel advances'
    assert manifest['record_sha256']==study.shared.sha(args.record) and manifest['provider_sha256']==study.shared.sha(provider)==record['libraries']['stock']['sha256']
    sources={'tools/native_stems.py','tools/supersampling.py','tests/supersampling_probe.cpp','tests/stem_core_test.py',
        'tests/weighted_stroke_profiles.py','tests/thin_stroke_profiles.py','tests/stroke_profiles.py','tests/small_feature_profiles.py',
        'tests/bridge_coverage_test.py','tests/neighbor_coverage_test.py','tests/fixtures/native-connected-stems.json',
        'tests/fixtures/native-compact-features.json','src/fontreal_coverage.cpp','src/fontreal_coverage.h','tests/selected_mask_probe.cpp'}
    assert set(manifest['sources'])==sources
    for path,digest in manifest['sources'].items():assert study.shared.sha(ROOT/path)==digest
    for path in sources-{'tools/native_stems.py','tests/small_feature_profiles.py','tests/fixtures/native-compact-features.json'}:
        assert study.shared.sha(ROOT/path)==hashlib.sha256(subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT)).hexdigest()
    assert manifest['sources']['src/fontreal_coverage.cpp']==record['spec']['processor'] and manifest['sources']['src/fontreal_coverage.h']==record['spec']['declaration']
    assert [f['family'] for f in manifest['fonts']]==list(FONTS)
    assert all('Regular' in f['style'].split(',') and f['family'] in f['matched_family'].split(',') for f in manifest['fonts'])
    assert len(manifest['cases'])==20 and {(c['font'],c['points']) for c in manifest['cases']}=={(fi,p) for fi in range(5) for p in POINTS}
    by_case={};witness=Counter();dots=set();regions=read(study.COMPACT_FIXTURE)['dot_regions']
    with tempfile.TemporaryDirectory(prefix='compact-features-reference-',dir=ROOT/'build/supersampling') as temporary:
        probe,env=reference_probe(Path(temporary),provider)
        for case in manifest['cases']:
            fi,pt=case['font'],case['points'];font=manifest['fonts'][fi]
            matched=subprocess.check_output(['fc-match','-f','%{file}',font['family']+':style=Regular'],text=True)
            assert Path(matched).resolve()==Path(font['file']).resolve() and study.shared.sha(Path(font['file']))==font['sha256']
            cap=read(directory/case['capture'],case['capture_sha256']);assert cap['style']=='Regular'
            native=next(c for c in cap['captures'] if c['mode']=='native_mono1')
            reference=json.loads(subprocess.check_output([str(probe),font['file'],str(pt),'--stock4x'],env=env))
            captures={c['mode']:c for c in reference['captures']};expected_native=captures['native_mono_gray_dark_on']
            assert Path(cap['provider']).resolve()==Path(reference['provider']).resolve()==provider
            assert {k:v for k,v in native.items() if k!='mode'}=={k:v for k,v in expected_native.items() if k!='mode'}
            assert native['target']==2 and native['render']==0 and native['scale']==1 and native['hint_dpi']==96
            assert native['load_flags']==(32768|8|(2<<16)) and native['effective_interpreter']==40
            assert native['stem_darkening'] and all(p==dict(set_error=0,get_error=0,no_stem_darkening=False) for p in native['darkening_properties'].values())
            places,lines=layout({g['code']:{'advance_pixels':int(g['advance']+.5)} for g in native['glyphs']},240)
            assert case['placements']==places and case['lines']==lines
            rows=read(directory/case['masks'],case['masks_sha256']);by_case[fi,pt]=(case,rows)
            assert [r['code'] for r in rows]==list(range(32,127))==[g['code'] for g in expected_native['glyphs']]
            for r,g in zip(rows,expected_native['glyphs']):
                assert r['raw']==decoded(g) and r['advance_pixels']==int(g['advance']+.5)
                masks,stage=verify_record(r,recipe);witness['D_control']+=1
                assert all(a<=b for a,b in zip(masks['F'],masks['G']))
                if r['code'] in (86,87,89):assert masks['F']==masks['G']==masks['D'];witness['VWY']+=1
                if r['code']==105:
                    dot,bounds=dot_region(g);pinned=next(x for x in regions if (x['font'],x['points'])==(fi,pt))
                    assert sorted(dot)==pinned['indices'] and bounds==pinned['bounds'] and hashlib.sha256(bytes(r['raw']['pixels'])).hexdigest()==pinned['raw_sha256']
                    if fi in (0,2,4) and pt in (8,10):
                        assert any(masks['F'][i]>masks['D'][i] for i in dot);dots.add((fi,pt))
                    if fi==3:assert all(masks[k][i]==masks['A'][i]==255 for k in 'DFG' for i in dot)
                    if fi==1 and pt==8:
                        assert not any(not any(r['raw']['pixels'][y*r['raw']['width']:(y+1)*r['raw']['width']]) for y in range(r['raw']['height']))
                witness['changed']+=masks['F']!=masks['D'];witness['proportional']+=masks['G']!=masks['F']
            assert rows[0]['raw']['pixels']==[] and rows[0]['advance_pixels']>0
            assert 'AAAAB' in ''.join(chr(p['code']) for p in places) and any(r['code']==90 for r in rows)
            assert [m['key'] for m in case['methods']]==list(KEYS)
            for col,method in enumerate(case['methods']):
                key=KEYS[col];assert method['title']==TITLES[col]
                glyphs={r['code']:{'final':{**r['raw'],'pixels':r['masks'][key]}} for r in rows}
                for polarity in ('light','dark'):
                    crop=method['crops'][polarity];image=Image.open(directory/crop['file'])
                    assert crop['file']==f'crops/{fi}_{pt}_{key}_{polarity}.png'
                    assert study.shared.sha(directory/crop['file'])==crop['sha256'] and list(image.size)==crop['size'] and image.mode=='L'
                    expected_pixels=composed_bytes(glyphs,places,pt,image.size)
                    if polarity=='light':expected_pixels=bytes(255-v for v in expected_pixels)
                    assert image.tobytes()==expected_pixels
            witness['normal']+=any(decoded(a)!=decoded(b) for a,b in zip(native['glyphs'],captures['native_normal_gray_dark_on']['glyphs']))
    assert dots=={(fi,pt) for fi in (0,2,4) for pt in (8,10)}
    assert all(witness[k]>0 for k in ('normal','changed','proportional')) and witness['VWY']==60
    assert len(manifest['sheets'])==40 and len(manifest['grids'])==20
    assert {(s['font'],s['points'],s['polarity']) for s in manifest['sheets']}=={(fi,p,b) for fi in range(5) for p in POINTS for b in ('light','dark')}
    for sheet in manifest['sheets']:
        assert study.shared.sha(directory/sheet['file'])==sheet['sha256'];image=Image.open(directory/sheet['file'])
        assert list(image.size)==sheet['size'] and image.width==1092
        case,_=by_case[sheet['font'],sheet['points']];label=ImageFont.truetype(manifest['fonts'][sheet['font']]['file'],14)
        assert [p['method'] for p in sheet['crops']]==[h['method'] for h in sheet['headings']]==list(KEYS)
        for col,(p,h) in enumerate(zip(sheet['crops'],sheet['headings'])):
            key=KEYS[col];x=12+col*268
            assert h==dict(method=key,text=f'{key}: {TITLES[col]}',position=[x,64])
            fg,bg=(0,255) if sheet['polarity']=='light' else (255,0)
            header=Image.new('L',(252,24),bg);ImageDraw.Draw(header).text((0,0),h['text'],font=label,fill=fg)
            assert image.crop((x,64,x+252,88)).tobytes()==header.tobytes()
            expected_file=case['methods'][col]['crops'][sheet['polarity']]['file'];crop=Image.open(directory/expected_file)
            assert p['file']==expected_file and p['box']==[x,92,x+crop.width,92+crop.height]
            assert image.crop(tuple(p['box'])).tobytes()==crop.tobytes()
    assert {(g['font'],g['points']) for g in manifest['grids']}=={(fi,p) for fi in range(5) for p in POINTS}
    for grid in manifest['grids']:
        _,rows=by_case[grid['font'],grid['points']]
        check_grid(directory,grid,rows,manifest['fonts'][grid['font']]['file'],CHARS)
    assert {p.name for p in (directory/'gallery').glob('*.png')}=={Path(g['file']).name for g in manifest['sheets']+manifest['grids']}
    diagnostic_check(directory,manifest,recipe)
    print('PASS B-CD1..5: exact A/D, compact-only F/G, all20 dots/60VWY controls/60main images and complete saved synthetic contrasts; witnesses',dict(witness),flush=True)
    print(directory)


if __name__=='__main__':main()
