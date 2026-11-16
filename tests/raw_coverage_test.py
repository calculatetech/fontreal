#!/usr/bin/env python3
"""Verify fully raw browser coverage against an independent nearest reference."""
import argparse
import json
from pathlib import Path
import shlex

import browser_live_recipe_test as recipe
import browser_masks_test as masks
from encoded_refinement_test import EXTRA, NAMES, font_weight, matrix, scalar_mask

OUT = recipe.ROOT/'results/raw-coverage'


def font_paths():
    folder=recipe.FONT_ROOT/'truetype'
    faces={f'{family} {style}':folder/('hack' if family=='Hack' else 'noto')/(family.replace(' ','')+'-'+style+'.ttf')
           for family in ('Noto Sans','Noto Serif','Hack') for style in ('Regular','Bold','Italic','BoldItalic')}
    faces['Lato Light']=folder/'lato/Lato-Light.ttf'
    faces.update({name:folder/path for name,path in EXTRA.items()})
    faces['Arial Regular']=folder/'msttcorefonts/Arial.ttf'
    assert set(faces)==set(NAMES+['Arial Regular'])
    return dict(faces, **recipe.CFF_FONTS)


def input_rows(record):
    OUT.mkdir(parents=True, exist_ok=True)
    faces={name:path for name,path in font_paths().items() if name not in recipe.CFF_FONTS}
    weights={name:font_weight(path) for name,path in faces.items()}
    tt=[dict(id=f'raw-{index}-{point}pt',label=name,point_size=point,logical_dpi=96,scale=1,
             cutoff=128 if weights[name]<400 else 160,font_path=str(path))
        for index,(name,path) in enumerate(faces.items()) for point in range(8,17)]
    tt_input=OUT/'truetype-input.json';tt_input.write_text(json.dumps(tt))
    recipe.run([recipe.BUILD/'chart','stock',tt_input,OUT/'truetype-qt'],env=recipe.environment(record['libraries']['stock']['library']))
    inputs=json.loads((OUT/'truetype-qt/rows.json').read_text())
    cff=[dict(id=f'cff{index}-{point}pt',label=name,point_size=point,cutoff=128 if name=='URW Bookman Light' else 160,
              font_path=str(path)) for index,(name,path) in enumerate(recipe.CFF_FONTS.items()) for point in range(8,17)]
    cff_input=OUT/'cff-input.json';cff_input.write_text(json.dumps(cff))
    recipe.run([recipe.BUILD/'chart','stock',cff_input,OUT/'cff-qt'],env=recipe.environment(record['libraries']['stock']['library']))
    inputs+=json.loads((OUT/'cff-qt/rows.json').read_text())
    source=OUT/'input.json';source.write_text(json.dumps(inputs));names=NAMES+['Arial Regular']+list(recipe.CFF_FONTS)
    return inputs


def native(record,nearest,variable):
    candidate=record['libraries']['candidate']['library'];stock=record['libraries']['stock']['library']
    inputs = input_rows(record)
    source=OUT/'input.json'; names=NAMES+['Arial Regular']+list(recipe.CFF_FONTS)
    matrix(inputs,names=names)
    for bad in (inputs[:-1]+[inputs[0]],inputs[:-1],
                [dict(inputs[0],point_size=8.5)]+inputs[1:],
                [{k:v for k,v in inputs[0].items() if k!='point_size'}]+inputs[1:]):
        try: matrix(bad,names=names)
        except AssertionError: pass
        else: raise AssertionError('Malformed raw condition matrix accepted')
    for name,library,on in [('reference',nearest,False),('actual',candidate,True)]:
        env=recipe.environment(library,on);env['FONTREAL_FT_CONTRAST']='raw'
        recipe.run([recipe.BUILD/'chart','candidate',source,OUT/name],env=env)
    ref,actual=[matrix(json.loads((OUT/name/'rows.json').read_text()),names=names) for name in ('reference','actual')]
    values=set();glyphs=0;different_from_ramp=0;oracle=recipe.Oracle(Path(stock))
    for key,row in ref.items():
        got=actual[key]
        assert got['glyphs']==row['glyphs'],(key,'native raw identity')
        for glyph in row['glyphs']:
            values.update(bytes.fromhex(glyph['mask']));glyphs+=1
            different_from_ramp+=recipe.expected(oracle,glyph['loaded'],glyph,row['weight'])['mask']!=glyph['mask']
        alpha=recipe.compose(got['glyphs'],got['height'],160,table=list(range(256)))
        assert alpha.tobytes()==scalar_mask(row['glyphs'],row['height'],list(range(256)))
        for palette in ('light','dark'):
            alpha.point(list(range(256)) if palette=='dark' else list(range(255,-1,-1))).convert('RGB').save(OUT/f'{got["id"]}-{palette}.png')
    assert len(ref)==252 and glyphs==8316 and values==set(range(256)) and different_from_ramp
    font=masks.NOTO/'NotoSans-Regular.ttf'
    def probe(library= candidate,**kwargs):
        return recipe.probe(library,font,enabled=library==candidate,contrast='raw',**kwargs)
    for dx in (0,32):
        assert probe(flags=0x28,dx=dx)==probe(nearest,dx=dx)
    delayed=probe(flags=0x28);immediate=probe(flags=0x2c)
    assert immediate['loaded']==delayed['rendered'][0]
    for scope,on in [(str((recipe.BUILD/'probe').resolve()),True),
                     (str((recipe.BUILD/'probe').resolve())+'-prefix',False),
                     ('/wrong:'+str((recipe.BUILD/'probe').resolve()),True),
                     (str((recipe.BUILD/'probe').resolve())+'-prefix:/wrong',False)]:
        got=probe(size=21,char='n',scope=scope)
        want=probe(nearest if on else stock,size=21,char='n')
        assert got==want,scope
    raw=probe(size=21,char='n');old=recipe.probe(stock,font,size=21,char='n')
    assert raw['loaded']['outline']!=old['loaded']['outline']
    for mode in ('none','mild','ramp217'):
        got=recipe.probe(candidate,font,size=21,char='n',enabled=True,contrast=mode)
        base=recipe.probe(nearest if mode=='ramp217' else stock,font,size=21,char='n')
        assert got['loaded']==base['loaded']
        want=recipe.expected(oracle,base['loaded'],base['rendered'][0]) if mode=='ramp217' else masks.mild(base['rendered'][0]) if mode=='mild' else base['rendered'][0]
        assert got['rendered']==[want,want]
    for flags in (1,2,0x400,0x100,0x400000,1|4,0x400|4,0x400000|4):
        assert masks.probe(record,font,flags=flags,mode=-1,contrast='raw')==masks.probe(record,font,flags=flags,mode=-1,contrast='raw',variant='stock')
    embedded,tricky=masks.font_fixtures(delayed['glyph'])
    expected=recipe.probe(nearest,embedded)
    got=recipe.probe(candidate,embedded,flags=0,enabled=True,contrast='raw')
    assert got==expected
    assert recipe.probe(candidate,embedded,flags=4,enabled=True,contrast='raw')['loaded']==got['rendered'][0]
    for path,transform,remove in [(font,'quarter',False),(font,'diagonal',False),(tricky,'none',False),(font,'none',True)]:
        got=recipe.probe(candidate,path,flags=0,enabled=True,contrast='raw',transform=transform,remove=remove)
        want=recipe.probe(nearest,path,transform=transform,remove=remove)
        assert got==want,(str(path),transform)
        for rendered in got['rendered']:
            assert all(rendered[k]==got['loaded'][k] for k in ('outline','contours','outline_flags'))
    for path,char,flags in [(masks.NOTO/'NotoColorEmoji.ttf','😀',0x100000),('/usr/share/fonts/X11/misc/6x13-ISO8859-1.pcf.gz','m',0),
                           ('/usr/share/fonts/type1/urw-base35/NimbusSans-Regular.t1','m',0x28)]:
        assert recipe.probe(candidate,path,char=char,flags=flags,enabled=True,contrast='raw')==recipe.probe(stock,path,char=char,flags=flags,contrast='raw')
    # Use the shaped CFF rows for an independent original-threshold comparison.
    cff_input.write_text((OUT/'cff-qt/rows.json').read_text())
    recipe.run([recipe.BUILD/'chart','candidate',cff_input,OUT/'cff-mono75'],env=recipe.environment(stock))
    cff75=matrix(json.loads((OUT/'cff-mono75/rows.json').read_text()),names=list(recipe.CFF_FONTS))
    changed_cff={name for (name,point),row in cff75.items() if row['glyphs']!=ref[(name,point)]['glyphs']}
    assert 'Nimbus Sans Regular' in changed_cff and len(changed_cff)>=2
    cff_cases=[]
    for name,path in recipe.CFF_FONTS.items():
        for mode in ('none','mild','ramp217'):
            assert recipe.probe(candidate,path,flags=0,enabled=True,contrast=mode)==recipe.probe(stock,path,flags=0,contrast=mode),(name,mode)
        for flags in (1,2,0x400,0x100,0x400000):
            assert masks.probe(record,path,flags=flags,mode=-1,contrast='raw')==masks.probe(record,path,flags=flags,mode=-1,contrast='raw',variant='stock'),(name,flags)
        for scope,on in [(str((recipe.BUILD/'probe').resolve()),True),
                         ('/wrong:'+str((recipe.BUILD/'probe').resolve()),True),
                         (str((recipe.BUILD/'probe').resolve())+'-prefix',False)]:
            got=recipe.probe(candidate,path,flags=0,enabled=True,contrast='raw',scope=scope)
            want=recipe.probe(nearest if on else stock,path,flags=0x20028 if on else 0)
            assert got==want,(name,scope)
        for dx in (0,32):
            assert recipe.probe(candidate,path,flags=0,enabled=True,contrast='raw',dx=dx)==recipe.probe(nearest,path,dx=dx)
        delayed=recipe.probe(candidate,path,flags=0,enabled=True,contrast='raw')
        immediate=recipe.probe(candidate,path,flags=4,enabled=True,contrast='raw')
        assert immediate['loaded']==delayed['rendered'][0],name
        cff_cases.append(name)
    cid=recipe.CFF_FONTS['Noto Sans CJK JP'];cjk=[]
    for point in range(8,17):
        for char in '漢国文':
            size=point*96/72
            got=recipe.probe(candidate,cid,size=size,char=char,flags=0,enabled=True,contrast='raw')
            expected=recipe.probe(nearest,cid,size=size,char=char)
            old=recipe.probe(stock,cid,size=size,char=char)
            assert got==expected and got['font_format']=='CFF'
            assert got['loaded']==old['loaded'] and got['rendered']==old['rendered'],(point,char)
            cjk.append(dict(point_size=point,char=char,glyph=got['glyph']))
    # Reuse the same public variation sequence with raw replacing the old recipe.
    cpp=recipe.ROOT/'tests/freetype_variable_probe.cpp';text=cpp.read_text();assert text.count('"ramp217"')==7
    source=recipe.BUILD/'raw-variable.cpp';source.write_text(text.replace('"ramp217"','"raw"'))
    flags=shlex.split(recipe.run(['pkg-config','--cflags','--libs','Qt6Gui','freetype2']).stdout)
    binary=recipe.BUILD/'raw-variable';recipe.run(['c++','-std=c++17','-fPIC',source,*flags,'-o',binary])
    variants={}
    for name,library,on in [('actual',candidate,True),('nearest',nearest,False),('stock',stock,False)]:
        output=OUT/f'{name}-variable.json'
        recipe.run([binary,variable,15,'0x28' if on else '0x20028',output],env=recipe.environment(library,on))
        variants[name]=json.loads(output.read_text())
        assert [(r['weight'],r['mode']) for r in variants[name]]==[
            (300,'raw'),(399,'raw'),(399.5,'raw'),(400,'raw'),(700,'raw'),
            (300,'raw'),(400,'none'),(400,'mild'),(400,'raw')]
    for got,near,old in zip(variants['actual'],variants['nearest'],variants['stock']):
        ref=near if got['mode']=='raw' else old
        assert got['weight']==got['requested_weight']==ref['weight']
        for a,b in zip(got['glyphs'],ref['glyphs']):
            assert a['loaded']==b['loaded']
            assert a['rendered']==(masks.mild(b['rendered']) if got['mode']=='mild' else b['rendered'])
    cff_variable=recipe.CFF_FONTS['Cantarell Variable'];cff_variants={}
    for name,library,on,load in [('actual',candidate,True,'0'),('nearest',nearest,False,'0x20028'),('legacy',stock,False,'0')]:
        output=OUT/f'{name}-cff2-variable.json'
        recipe.run([binary,cff_variable,15,load,output],env=recipe.environment(library,on))
        cff_variants[name]=json.loads(output.read_text())
    for got,near,old in zip(cff_variants['actual'],cff_variants['nearest'],cff_variants['legacy'],strict=True):
        want=near if got['mode']=='raw' else old
        assert got['weight']==got['requested_weight']==want['weight']
        assert got['glyphs']==want['glyphs'],(got['weight'],got['mode'],'CFF2 current state')
    oracle.close()
    return dict(faces=28,conditions=252,glyphs=glyphs,alpha_inputs=len(values),
                former_recipe_differences=different_from_ramp,variable_steps=9,translations=[0,32],
                cff_faces=cff_cases,cff_changed_families=sorted(changed_cff),cjk=cjk,cff2_variable_steps=9)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variable-font',type=Path,required=True)
    parser.add_argument('--case',choices=('native','browser'),required=True)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True);before=masks.protected()
    record,trace,nearest=recipe.prepare()
    result=native(record,nearest,args.variable_font) if args.case=='native' else [
        row for group in ('tt','tt-tail','cff','cff-tail','cff2') for row in recipe.browser(record,trace,nearest,args.variable_font,mode='raw',font_group=group)]
    if args.case=='browser':
        assert len(result)==10 and {(r['browser'],r['font_group']) for r in result}=={
            (b,g) for b in ('firefox','floorp') for g in ('tt','tt-tail','cff','cff-tail','cff2')}
        assert all(sum(r['conditions'] for r in result if r['browser']==b)==168 for b in ('firefox','floorp'))
    assert before==masks.protected()
    (OUT/(args.case+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS fully raw '+args.case,flush=True)


if __name__=='__main__': main()
