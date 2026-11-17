#!/usr/bin/env python3
"""Check the native MONO baseline, conservative cleanup and weighted blend export."""
import argparse
import ast
import hashlib
from collections import Counter, defaultdict
from math import floor
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

BASE='02e27d14ba52f0b474b9dea65b07674d852fbf84'
PROBE_BASE='29d3fec5c929bad39e60d3ffbb23aeeb263169a3'
FONTS=('Noto Sans','Nimbus Sans','Inconsolata Nerd Font','Arial','Hack')
POINTS=(8,10,11,12)
CHARS='Hinm8W:!'
TITLES=['Native 1x MONO-gray','Existing stem cleanup','Cleanup + near ties','Connected profiles','D + weighted blend lift']


def read(path,digest=None):
    if digest:assert study.shared.sha(path)==digest,path
    return json.loads(path.read_text())


def decoded(g):
    b=g['bitmap'];assert b['pixel_mode']==2
    data=bytes.fromhex(b['rows_hex']);stride=abs(b['pitch'])
    assert len(data)==stride*b['rows'] and stride>=b['width']
    return dict(left=g['left'],top=g['top'],width=b['width'],height=b['rows'],
                pixels=list(b''.join(data[y*stride:y*stride+b['width']] for y in range(b['rows']))))


def near_oracle(raw,w):
    if not raw:return raw
    h=len(raw)//w; proposals=[]
    for across,along,index in ((w,h,lambda a,b:b*w+a),(h,w,lambda a,b:a*w+b)):
        for a in range(across-1):
            rows=[]
            for b in range(along):
                i,j=index(a,b),index(a+1,b)
                outer=[raw[index(c,b)] if 0<=c<across else 0 for c in (a-1,a+2)]
                rows.append((i,j) if raw[i] and raw[j] and 192<=raw[i]+raw[j]<=384 and max(outer)<=32 else None)
            cursor=0
            while cursor<along:
                if rows[cursor] is None:cursor+=1;continue
                run=[rows[cursor]];first=[raw[i] for i in run[0]];cursor+=1
                while cursor<along and rows[cursor] is not None and all(abs(raw[i]-v)<=8 for i,v in zip(rows[cursor],first)):
                    run.append(rows[cursor]);cursor+=1
                if len(run)>=3:proposals.append(run)
    counts=Counter(i for run in proposals for pair in run for i in pair)
    out=bytearray(raw)
    for run in proposals:
        if any(counts[i]!=1 for pair in run for i in pair):continue
        vote=sum(raw[i]-raw[j] for i,j in run)
        if not vote:continue
        for pair in run:
            i,j=pair if vote>0 else pair[::-1]
            if max(raw[i],raw[j])>=230:continue
            peak=min(240,raw[i]+raw[j]-1)
            if peak>raw[i]:out[i],out[j]=peak,raw[i]+raw[j]-peak
    return bytes(out)


def weighted_oracle(raw,cleaned,pairs):
    positive=sorted((v for v in raw if v),reverse=True)
    if positive:
        cutoff=positive[(len(positive)+3)//4-1];refs=[v for v in positive if v>=cutoff]
        numerator=sum(v*v for v in refs);denominator=sum(refs)
        target=(2*numerator+denominator)//(2*denominator)
    else:cutoff=target=numerator=denominator=0;refs=[]
    result=bytearray(cleaned)
    for p in pairs:
        i,j=p['core'],p['fringe'];peak=max(cleaned[i],target)
        result[i]=peak;result[j]=(2*cleaned[j]*peak+cleaned[i])//(2*cleaned[i])
    return bytes(result),dict(target=target,reference_cutoff=cutoff,reference_count=len(refs),numerator=numerator,denominator=denominator)


def frozen_concentrate():
    source=subprocess.check_output(['git','show',f'{BASE}:tests/stem_core_test.py'],cwd=ROOT,text=True)
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='concentrate')
    namespace=dict(Counter=Counter,MODES=('baseline','native-area','gain-area'))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<immutable concentration>','exec'),namespace)
    return namespace['concentrate']


def frozen_refine(connected=False):
    source=subprocess.check_output(['git','show',f'{BASE}:tests/stroke_profiles.py'],cwd=ROOT,text=True)
    if connected:
        guard='                    if (native,chosen,side)<(0,0,0):continue'
        assert source.count(guard)==1
        source=source.replace(guard,'                    if native==0 and chosen==0:continue\n'+guard)
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='refine')
    namespace=dict(defaultdict=defaultdict,floor=floor,median=median)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<immutable profile reference>','exec'),namespace)
    return namespace['refine']


def pair_oracle(concentrated,profile):
    unique={(p['core'],p['fringe']) for p in concentrated}
    unique|={(p['core'],p['fringe']) for run in profile['runs'] for p in run['pairs']}
    unique|={(p['core'],p['fringe']) for p in profile['steps']}
    count=Counter(i for pair in unique for i in pair)
    return [dict(core=c,fringe=f) for c,f in sorted(unique) if count[c]==count[f]==1]


def frozen_layout():
    source=subprocess.check_output(['git','show',f'{BASE}:tools/supersampling.py'],cwd=ROOT,text=True)
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='layout')
    specimen=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SPECIMEN' for t in n.targets))
    namespace=dict(SPECIMEN=ast.literal_eval(specimen))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<immutable layout>','exec'),namespace)
    return namespace['layout'],namespace['SPECIMEN']


def fixtures():
    def check(raw,w,b,c):
        got,pairs,_,_=study.treatments(raw,w)
        assert got['A']==raw and got['B']==b and got['C']==c,(list(raw),w,list(got['B']),list(got['C']))
        assert c==near_oracle(raw,w)
        for k in ('B','C'):
            assert sum(got[k])==sum(raw)
            assert all(bool(a)==bool(b) for a,b in zip(raw,got[k]))
        assert got['E']==weighted_oracle(raw,got['D'],pairs['E'])[0]
    check(bytes([144,124]*3),2,bytes([240,28]*3),bytes([240,28]*3))
    check(bytes([172,164]*3),2,bytes([172,164]*3),bytes([240,96]*3))
    check(bytes([144,129]*3),2,bytes([144,129]*3),bytes([240,33]*3))
    check(bytes([144,124,32]*3),3,bytes([240,28,32]*3),bytes([240,28,32]*3))
    check(bytes([144,124,152,132,144,124]),2,bytes([240,28,240,44,240,28]),bytes([240,28,240,44,240,28]))
    check(bytes([172,164,168,168,172,164]),2,bytes([172,164,168,168,172,164]),bytes([240,96]*3))
    check(bytes([170,166,166,170,170,166]),2,bytes([170,166,166,170,170,166]),bytes([240,96]*3))
    raw=bytes([172,164,0,0,164,172]*3)
    check(raw,6,raw,bytes([240,96,0,0,96,240]*3))
    for raw,w in [(b'',0),(bytes([168,168]*3),2),(bytes([144,124]*2),2),
                  (bytes([100,91]*3),2),(bytes([200,185]*3),2),(bytes([230,120]*3),2),
                  (bytes([144,124,33]*3),3),(bytes([172,164,181,164,172,164]),2),
                  (bytes([100]*9),3),(bytes([20,200,20]*3),3),(bytes([200,0]*3),2)]:check(raw,w,raw,raw)
    for row in ([104,88],[144,128],[176,208]):
        raw=bytes(row*3);c=bytes([min(240,sum(row)-1),sum(row)-min(240,sum(row)-1)]*3)
        if row[0]<row[1]:c=bytes(sum(([sum(row)-min(240,sum(row)-1),min(240,sum(row)-1)] for _ in range(3)),[]))
        check(raw,2,c,c)
    raw=bytes([172,164]*4)
    transpose=lambda x,w:bytes(x[y*w+a] for a in range(w) for y in range(len(x)//w))
    c=study.treatments(raw,2)[0]['C']
    assert study.treatments(transpose(raw,2),4)[0]['C']==transpose(c,2)
    flip=lambda x:b''.join(x[i:i+2][::-1] for i in range(0,len(x),2))
    assert study.treatments(flip(raw),2)[0]['C']==flip(c)
    raw=bytes([100,92,0,0,0,0]*3+[0,0,255,200,200,200])
    masks,pairs,weighted,_=study.treatments(raw,6)
    assert weighted['target']==216 and weighted['reference_count']==4
    assert masks['C']==bytes([191,1,0,0,0,0]*3+[0,0,255,200,200,200])
    assert masks['E']==bytes([216,1,0,0,0,0]*3+[0,0,255,200,200,200])
    # Explicit fractional fringe lift and identity when the target is below the core.
    clean=bytes([240,96,0,248]);pairs=[dict(core=0,fringe=1)]
    out,detail=study.weighted_blend(bytes([172,164,0,248]),clean,pairs,4)
    assert detail['target']==248 and out==bytes([248,99,0,248])
    out,detail=study.weighted_blend(bytes([100,92,0,180]),clean,pairs,4)
    assert detail['target']==180 and out==clean
    print('PASS exact conservative/near-tie guards, coherent mixed ties, later opposing run, weighted cutoff ties and blend lift',flush=True)


def connected_fixtures(prior,reference):
    fixture=read(study.FIXTURE)
    assert fixture['source_commit']==BASE and fixture['points']==12 and fixture['target_dpi']==96
    assert fixture['font']['family']=='Noto Sans Display' and fixture['font']['file']=='NotoSansDisplay-Regular.ttf'
    assert fixture['provider']['version']=='2.14.2' and fixture['controls']['target']==2 and fixture['controls']['render']==0
    assert fixture['controls']['scale']==1 and fixture['controls']['hint_dpi']==96
    assert fixture['controls']['load_flags']==(32768|8|(2<<16))
    assert fixture['controls']['stem_darkening'] and fixture['controls']['effective_interpreter']==40
    assert all(v==dict(set_error=0,get_error=0,no_stem_darkening=False) for v in fixture['controls']['darkening_properties'].values())
    assert '/' not in fixture['font']['file'] and '/' not in fixture['provider']['file'] and '/' not in fixture['capture']['file']
    for path,digest in fixture['sources'].items():
        original=subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT)
        assert hashlib.sha256(original).hexdigest()==digest
    for r in fixture['records']:
        raw=bytes(r['raw']['pixels']);w=r['raw']['width'];m,p,_,detail=study.treatments(raw,w)
        assert all(list(m[k])==r['expected'][k] for k in 'ABCD')
        assert sum(m['D'])==(10349 if r['code']==72 else 3769)
        assert study.refine(raw,m['C'],w,connected=True)==reference(raw,m['C'],w)
        assert detail==reference(raw,m['C'],w)[1]
        for chosen in ('A','B','C'):
            assert study.refine(raw,m[chosen],w)==prior(raw,m[chosen],w)
        flip=lambda data:b''.join(data[i:i+w][::-1] for i in range(0,len(data),w))
        trans=lambda data:bytes(data[y*w+x] for x in range(w) for y in range(len(data)//w))
        assert study.refine(flip(raw),flip(m['C']),w,connected=True)[0]['corners']==flip(m['D'])
        assert study.refine(trans(raw),trans(m['C']),r['raw']['height'],connected=True)[0]['corners']==trans(m['D'])
    h=fixture['records'][0];gap=bytearray(h['raw']['pixels']);gap[6*9+7:6*9+9]=bytes([0,0])
    m,_,_,_=study.treatments(bytes(gap),9)
    assert all(m['D'][y*9+7:y*9+9]==bytes([184,184]) for y in range(7,12))
    assert m['D'][6*9+7:6*9+9]==bytes([0,0])
    raw=bytes([160,160]*4);m,_,_,_=study.treatments(raw,2)
    assert m['C']==m['D']==raw
    conflict=bytes([180,160]*3+[168,168]*3+[160,180]*3)
    m,_,_,detail=study.treatments(conflict,2)
    assert m['C']==m['D']==bytes([240,100]*3+[168,168]*3+[100,240]*3) and not detail['runs']
    raw=bytes([121,120]*2+[105,125]*3+[121,120]*2+[0,0]+[255,255]*5)
    masks,pairs,weighted,_=study.treatments(raw,2)
    assert masks['D']==bytes([240,1]*2+[240,229]*3+[240,1]*2+[0,0]+[255,255]*5)
    assert masks['E']==bytes([255,1]*2+[240,229]*3+[255,1]*2+[0,0]+[255,255]*5)
    assert weighted['target']==255
    assert {(p['core'],p['fringe']) for p in pairs['E']}=={(0,1),(2,3),(10,11),(12,13)}
    raw=bytes([172,164]*3+[248]*4);clean=bytes([240,96]*3+[248]*4)
    pair=lambda a,b:dict(core=a,fringe=b)
    cases=[([],[],[],[],clean),
      ([pair(0,1)],[],[],[pair(0,1)],bytes([248,99,240,96,240,96]+[248]*4)),
      ([pair(0,1),pair(0,1)],[pair(0,3)],[pair(4,5)],[pair(4,5)],bytes([240,96,240,96,248,99]+[248]*4)),
      ([pair(0,1),pair(0,1)],[pair(1,0)],[pair(4,5)],[pair(4,5)],bytes([240,96,240,96,248,99]+[248]*4)),
      ([pair(0,1),pair(0,1)],[],[pair(2,3)],[pair(0,1),pair(2,3)],bytes([248,99,248,99,240,96]+[248]*4))]
    for cp,runs,steps,expected,result in cases:
        profile=dict(runs=[dict(pairs=runs)],steps=steps)
        selected=study.weighted_pairs(cp,profile)
        assert selected==expected==pair_oracle(cp,profile)
        actual,detail=study.weighted_blend(raw,clean,selected,10)
        assert actual==result==weighted_oracle(raw,clean,expected)[0] and detail['target']==248
    print('PASS retained H/i, broken connection, zero-vote/conflict guards, transforms and complete weighted-pair composition',flush=True)


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
    assert grid['cell_size']==22 and list(im.size)==[column*5+16,y]
    small=ImageFont.truetype(font_file,9)
    label=ImageFont.truetype(font_file,14)
    assert len(grid['headings'])==5
    for col,heading in enumerate(grid['headings']):
        key=chr(65+col);assert heading['method']==key and heading['text']==f'{key}: {TITLES[col]}'
        x,y=heading['position'];width=column
        assert [x,y]==[12+col*width,60]
        patch=Image.new('RGB',(width,24),(24,24,24))
        ImageDraw.Draw(patch).text((0,0),heading['text'],font=label,fill='white')
        assert im.crop((x,y,x+width,y+24)).tobytes()==patch.tobytes()
    expected_cells={(ord(ch),key,i) for ch in characters for key in 'ABCDE' for i in range(len(rs[ord(ch)]['raw']['pixels']))}
    assert {(c['code'],c['method'],c['index']) for c in grid['cells']}==expected_cells and len(grid['cells'])==len(expected_cells)
    for cell in grid['cells']:
        r=rs[cell['code']];v=r['masks'][cell['method']][cell['index']];assert cell['value']==v
        col='ABCDE'.index(cell['method']);yy,xx=divmod(cell['index'],r['raw']['width'])
        x=12+col*column+28+xx*22;y=tops[cell['code']]+46+yy*22
        assert cell['box']==[x,y,x+22,y+22] and cell['text_position']==[x+2,y+4]
        border=(255,170,55) if v!=r['raw']['pixels'][cell['index']] else (75,75,75)
        assert cell['border']==list(border)
        patch=Image.new('RGB',(22,22));draw=ImageDraw.Draw(patch)
        draw.rectangle((0,0,21,21),fill=(v,)*3,outline=border)
        draw.text((2,4),str(v),font=small,fill='black' if v>=145 else 'white')
        assert im.crop(tuple(cell['box'])).tobytes()==patch.tobytes()
    expected_previews={(ord(ch),key) for ch in characters for key in 'ABCDE'}
    assert {(p['code'],p['method']) for p in grid['previews']}==expected_previews
    assert len(grid['previews'])==len(expected_previews)
    for preview in grid['previews']:
        r=rs[preview['code']];expected_im=Image.frombytes('L',(r['raw']['width'],r['raw']['height']),bytes(r['masks'][preview['method']])).convert('RGB')
        x=12+'ABCDE'.index(preview['method'])*column+30;y=tops[preview['code']]
        assert preview['box']==[x,y,x+r['raw']['width'],y+r['raw']['height']]
        assert im.crop(tuple(preview['box'])).tobytes()==expected_im.tobytes()


def diagnostic_check(directory,manifest,prior,reference):
    diagnostic=manifest['diagnostic'];fixture=read(study.FIXTURE)
    assert diagnostic['fixture']=='tests/fixtures/native-connected-stems.json'
    assert diagnostic['fixture_sha256']==study.shared.sha(study.FIXTURE)
    assert diagnostic['masks']=='diagnostics/retained-masks.json'
    records=read(directory/diagnostic['masks'],diagnostic['masks_sha256'])
    assert [r['code'] for r in records]==[72,105]
    for r,f in zip(records,fixture['records']):
        assert r['raw']==f['raw'] and r['advance_pixels']==f['advance_pixels']
        assert all(r['masks'][key]==f['expected'][key] for key in 'ABCD')
        raw=bytes(r['raw']['pixels']);w=r['raw']['width'];c=bytes(r['masks']['C'])
        assert r['profile']==reference(raw,c,w)[1]
        assert r['coverage_delta_D']==sum(r['masks']['D'])-sum(raw)
        for chosen in 'ABC':assert study.refine(raw,bytes(r['masks'][chosen]),w)==prior(raw,bytes(r['masks'][chosen]),w)
        selected=[p for p in pair_oracle(r['pairs']['C'],r['profile']) if r['masks']['D'][p['core']]>r['masks']['D'][p['fringe']]]
        assert selected==r['pairs']['E']
        expected,detail=weighted_oracle(raw,bytes(r['masks']['D']),selected)
        assert list(expected)==r['masks']['E'] and detail==r['weighted']
    h=records[0]
    lower={(y*9+7,y*9+8) for y in range(7,12)}
    assert lower<={(p['core'],p['fringe']) for p in h['pairs']['E']}
    assert not lower&{(p['core'],p['fringe']) for p in h['pairs']['C']}
    grid=diagnostic['grid']
    assert grid['file']=='diagnostics/retained-grids.png' and grid['font'] is None and grid['points']==12
    check_grid(directory,grid,records,manifest['fonts'][0]['file'],'Hi')
    assert {p.name for p in (directory/'diagnostics').iterdir()}=={'retained-masks.json','retained-grids.png'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',required=True,type=Path);args=parser.parse_args()
    fixtures();frozen=frozen_concentrate();layout,specimen=frozen_layout();prior_refine=frozen_refine();connected_refine=frozen_refine(True)
    connected_fixtures(prior_refine,connected_refine)
    record=read(args.record);provider=Path(record['libraries']['stock']['library']).resolve()
    output=subprocess.check_output([sys.executable,'-B',str(ROOT/'tools/native_stems.py'),'--record',str(args.record.resolve())],text=True)
    directory=Path(output.strip().splitlines()[-1]);manifest=read(directory/'manifest.json')
    assert directory.parent.resolve()==(ROOT/'results/native-stems').resolve()
    assert manifest['study']=='native-stems' and manifest['target_dpi']==96 and manifest['blend']=='encoded'
    assert manifest['specimen']==list(specimen) and manifest['placement']=='native MONO whole-pixel advances'
    assert manifest['methods']==[[k,t] for k,t in zip('ABCDE',TITLES)]
    assert manifest['points']==list(POINTS) and manifest['record_sha256']==study.shared.sha(args.record)
    assert manifest['provider_sha256']==study.shared.sha(provider)==record['libraries']['stock']['sha256']
    assert set(manifest['sources'])=={'tools/native_stems.py','tools/supersampling.py',
        'tests/supersampling_probe.cpp','tests/stem_core_test.py','tests/weighted_stroke_profiles.py',
        'tests/thin_stroke_profiles.py','tests/stroke_profiles.py','tests/fixtures/native-connected-stems.json','src/fontreal_coverage.cpp','src/fontreal_coverage.h',
        'tests/selected_mask_probe.cpp'}
    for p,digest in manifest['sources'].items():assert study.shared.sha(ROOT/p)==digest
    assert {p:(manifest['sources'][p]) for p in ('src/fontreal_coverage.cpp','src/fontreal_coverage.h')}=={
        'src/fontreal_coverage.cpp':record['spec']['processor'],'src/fontreal_coverage.h':record['spec']['declaration']}
    assert [f['family'] for f in manifest['fonts']]==list(FONTS)
    assert all('Regular' in f['style'].split(',') and f['family'] in f['matched_family'].split(',') for f in manifest['fonts'])
    assert {(c['font'],c['points']) for c in manifest['cases']}=={(f,p) for f in range(5) for p in POINTS}
    assert len(manifest['cases'])==20
    by_case={};witness=Counter()
    with tempfile.TemporaryDirectory(prefix='native-stems-reference-',dir=ROOT/'build/supersampling') as temporary:
        probe,env=reference_probe(Path(temporary),provider)
        for case in manifest['cases']:
            fi,pt=case['font'],case['points'];font=manifest['fonts'][fi]
            matched=subprocess.check_output(['fc-match','-f','%{file}',font['family']+':style=Regular'],text=True)
            assert Path(matched).resolve()==Path(font['file']).resolve() and study.shared.sha(Path(font['file']))==font['sha256']
            cap=read(directory/case['capture'],case['capture_sha256']);native=next(c for c in cap['captures'] if c['mode']=='native_mono1')
            assert cap['style']=='Regular'
            ref=json.loads(subprocess.check_output([str(probe),font['file'],str(pt),'--stock4x'],env=env))
            refs={r['mode']:r for r in ref['captures']};expected=refs['native_mono_gray_dark_on']
            assert Path(cap['provider']).resolve()==Path(ref['provider']).resolve()==provider
            assert {k:v for k,v in native.items() if k!='mode'}=={k:v for k,v in expected.items() if k!='mode'}
            assert native['target']==2 and native['render']==0 and native['scale']==1 and native['hint_dpi']==96
            assert native['load_flags']==(32768|8|(2<<16)) and native['effective_interpreter']==40
            assert native['stem_darkening'] and all(x==dict(set_error=0,get_error=0,no_stem_darkening=False) for x in native['darkening_properties'].values())
            placements,lines=layout({g['code']:{'advance_pixels':int(g['advance']+.5)} for g in expected['glyphs']},240)
            assert case['placements']==placements and case['lines']==lines
            records=read(directory/case['masks'],case['masks_sha256']);by_case[fi,pt]=(case,records)
            assert [r['code'] for r in records]==list(range(32,127))==[g['code'] for g in expected['glyphs']]
            glyphs={}
            for r,g in zip(records,expected['glyphs']):
                raw=decoded(g);assert r['raw']==raw and r['masks']['A']==raw['pixels']
                original=bytes(raw['pixels']);assert r['advance_pixels']==int(g['advance']+.5)
                assert bytes(r['masks']['B'])==frozen(original,original,raw['width'])[0]['native-area']
                assert bytes(r['masks']['C'])==frozen(original,original,raw['width'],near_ties=True)[0]['native-area']
                assert r['pairs']['B']==frozen(original,original,raw['width'])[1] and r['pairs']['C']==frozen(original,original,raw['width'],near_ties=True)[1]
                for chosen in ('A','B','C'):
                    assert study.refine(original,bytes(r['masks'][chosen]),raw['width'])==prior_refine(original,bytes(r['masks'][chosen]),raw['width'])
                connected,profile=connected_refine(original,bytes(r['masks']['C']),raw['width'])
                assert bytes(r['masks']['D'])==connected['corners'] and r['profile']==profile
                assert r['coverage_delta_D']==sum(r['masks']['D'])-sum(original)
                assert all(bool(a)==bool(b) for a,b in zip(original,r['masks']['D']))
                expected_pairs=[p for p in pair_oracle(r['pairs']['C'],profile) if connected['corners'][p['core']]>connected['corners'][p['fringe']]]
                assert r['pairs']['E']==expected_pairs
                weighted,detail=weighted_oracle(original,bytes(r['masks']['D']),expected_pairs)
                assert bytes(r['masks']['E'])==weighted and r['weighted']==detail
                for key in 'BC':
                    values=r['masks'][key];pairs=r['pairs'][key]
                    assert len(values)==len(original) and sum(values)==sum(original)
                    assert all(bool(a)==bool(b) for a,b in zip(original,values))
                    selected=[i for p in pairs for i in (p['core'],p['fringe'])]
                    assert len(selected)==len(set(selected))
                    assert set(selected)=={i for i,v in enumerate(values) if v!=original[i]}
                    assert all(v==original[i] for i,v in enumerate(values) if i not in selected)
                    for p in pairs:
                        i,j=p['core'],p['fringe'];assert values[i]+values[j]==original[i]+original[j] and values[i]>values[j]>0
                        assert values[i]>original[i] and values[j]<original[j]
                        assert values[i]==min(240,original[i]+original[j]-1)
                        assert p['axis'] in ('vertical','horizontal')
                        assert abs(i-j)==(1 if p['axis']=='vertical' else raw['width'])
                        if p['axis']=='vertical':assert i//raw['width']==j//raw['width']
                c,d=r['masks']['D'],r['masks']['E'];selected={i for p in expected_pairs for i in (p['core'],p['fringe'])}
                assert all(d[i]>=c[i] and bool(d[i])==bool(c[i]) and (i in selected or d[i]==c[i]) for i in range(len(c)))
                witness['cleanup']+=r['masks']['A']!=r['masks']['B'];witness['near']+=r['masks']['B']!=r['masks']['C']
                witness['fringe']+=sum(d[p['fringe']]>c[p['fringe']] for p in expected_pairs)
                witness['connected']+=r['masks']['D']!=r['masks']['C']
                witness['new_pairs']+=bool({(p['core'],p['fringe']) for p in expected_pairs}-{(p['core'],p['fringe']) for p in r['pairs']['C']})
                previous_pairs={(p['core'],p['fringe']) for p in r['pairs']['C']}
                witness['connected_fringe']+=sum((p['core'],p['fringe']) not in previous_pairs and
                    (r['masks']['D'][p['core']]!=r['masks']['C'][p['core']] or r['masks']['D'][p['fringe']]!=r['masks']['C'][p['fringe']]) and
                    r['masks']['E'][p['fringe']]>r['masks']['D'][p['fringe']] for p in expected_pairs)
                glyphs[r['code']]=r
            witness['normal']+=any(decoded(a)!=decoded(b) for a,b in zip(native['glyphs'],refs['native_normal_gray_dark_on']['glyphs']))
            assert glyphs[32]['raw']['pixels']==[] and glyphs[32]['advance_pixels']>0
            codes=''.join(chr(p['code']) for p in case['placements']);assert 'AAAAB' in codes and 90 in glyphs
            rendered_dark={}
            for method in case['methods']:
                key=method['key'];assert key in 'ABCDE' and method['title']==TITLES[ord(key)-65]
                masks={r['code']:{'final':{**r['raw'],'pixels':r['masks'][key]}} for r in records}
                for polarity in ('light','dark'):
                    crop=method['crops'][polarity];image=Image.open(directory/crop['file'])
                    assert study.shared.sha(directory/crop['file'])==crop['sha256'] and list(image.size)==crop['size'] and image.mode=='L'
                    expected_bytes=composed_bytes(masks,case['placements'],pt,image.size)
                    if polarity=='light':expected_bytes=bytes(255-v for v in expected_bytes)
                    assert image.tobytes()==expected_bytes
                    if polarity=='dark':rendered_dark[key]=image.tobytes()
            assert [m['key'] for m in case['methods']]==list('ABCDE')
            witness['near_crop']+=rendered_dark['B']!=rendered_dark['C']
            witness['weighted_crop']+=rendered_dark['D']!=rendered_dark['E']
    assert all(witness[k] for k in ('cleanup','near','fringe','normal','near_crop','weighted_crop','connected','new_pairs','connected_fringe')),witness
    assert len(manifest['sheets'])==40 and len(manifest['grids'])==10
    assert {(s['font'],s['points'],s['polarity']) for s in manifest['sheets']}=={(f,p,b) for f in range(5) for p in POINTS for b in ('light','dark')}
    for sheet in manifest['sheets']:
        path=directory/sheet['file'];assert study.shared.sha(path)==sheet['sha256'];image=Image.open(path)
        assert list(image.size)==sheet['size'] and image.width==1360
        fi=sheet['font'];label=ImageFont.truetype(manifest['fonts'][fi]['file'],14)
        case,_=by_case[fi,sheet['points']]
        assert [r['method'] for r in sheet['crops']]==list('ABCDE')
        assert [h['method'] for h in sheet['headings']]==list('ABCDE')
        for col,(region,head) in enumerate(zip(sheet['crops'],sheet['headings'])):
            key=chr(65+col);assert region['method']==head['method']==key and head['text']==f'{key}: {TITLES[col]}'
            assert head['position']==[12+col*268,64]
            fg,bg=(0,255) if sheet['polarity']=='light' else (255,0)
            header=Image.new('L',(252,24),bg);ImageDraw.Draw(header).text((0,0),head['text'],font=label,fill=fg)
            x,y=head['position'];assert image.crop((x,y,x+252,y+24)).tobytes()==header.tobytes()
            expected_file=case['methods'][col]['crops'][sheet['polarity']]['file']
            assert region['file']==expected_file
            crop=Image.open(directory/expected_file)
            assert region['box']==[12+col*268,92,12+col*268+crop.width,92+crop.height]
            assert image.crop(tuple(region['box'])).tobytes()==crop.tobytes()
    assert {(g['font'],g['points']) for g in manifest['grids']}=={(f,p) for f in range(5) for p in (11,12)}
    for grid in manifest['grids']:
        _,records=by_case[grid['font'],grid['points']]
        check_grid(directory,grid,records,manifest['fonts'][grid['font']]['file'],CHARS)
    assert {p.name for p in (directory/'gallery').glob('*.png')}=={Path(s['file']).name for s in manifest['sheets']+manifest['grids']}
    diagnostic_check(directory,manifest,prior_refine,connected_refine)
    print('PASS B-CS1..8: independent native baseline, frozen A/B/C/default profiles, connected D/weighted E, all 20 conditions/95 glyphs/50 main images and retained diagnostic; witnesses',dict(witness))
    print(directory)


if __name__=='__main__':main()
