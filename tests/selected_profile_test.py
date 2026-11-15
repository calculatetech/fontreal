#!/usr/bin/env python3
"""Check the selected production profile against the immutable optical references."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import tempfile
import importlib.util
from unittest.mock import patch

from bridge_coverage_test import transform
from bridge_font_matrix_test import sha
from inconsolata_gain_test import gain
from noto_stem_winner_test import keep_winner
from stroke_profiles import refine
from weighted_stroke_profiles import darken

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/selected-profile'
OUT=ROOT/'results/selected-profile'


def expected_mask(raw,width):
    gained=gain(transform(raw,width)[0]['bridge'],226)
    winner=keep_winner(raw,gained,width)[0]
    previous=refine(raw,winner,width)[0]['corners']
    return darken(raw,previous,width)[0]['stems']


def build(trace=False):
    command=['python3',str(ROOT/'tools/build-freetype.py')]
    if trace: command.append('--trace')
    result=subprocess.check_output(command,text=True)
    path=Path(result.splitlines()[-1]); record=json.loads(path.read_text())
    for v in record['libraries'].values(): assert sha(Path(v['library']))==v['sha256']
    assert record['spec']['processor']==sha(ROOT/'src/fontreal_coverage.cpp')
    assert record['spec']['declaration']==sha(ROOT/'src/fontreal_coverage.h')
    return path,record


def references():
    sources=[]
    for label,folder,public in [('sizes','weighted-size-chart','weighted-size-captures.json'),
                                ('styles','weighted-stroke-study','weighted-stroke-captures.json')]:
        record_path=ROOT/'docs/images/browser-common-ground'/public
        record=json.loads(record_path.read_text()); folder=ROOT/'results'/folder/'gallery'
        assert sha(folder/'manifest.json')==record['full_manifest_sha256']
        assert sha(folder/'masks.json')==record['processed_masks_sha256']
        full=json.loads((folder/'manifest.json').read_text())
        arrays={c['id']:{g['glyph']:g for g in c['glyphs']} for c in json.loads((folder/'masks.json').read_text())}
        for condition in full['audit']:
            sources.append((label,condition,arrays[condition['id']]))
    assert sum(len(c['glyphs']) for _,c,_ in sources)==33440
    return sources


def native(record):
    sources=references(); paths={Path(p).resolve() for p in subprocess.check_output(
        ['fc-list','-f','%{file}\n'],text=True).splitlines()}; files={}; jobs=[]
    for label,case,_ in sources:
        font=case['font']; digest=font['font_sha256']
        if digest not in files:
            choices=[p for p in paths if p.name==font['font_file'] and sha(p)==digest]
            assert len(choices)==1,font['label']; files[digest]=choices[0]
        jobs.append(dict(id=label+'-'+case['id'],file=str(files[digest]),pixels=case['native_size'],
                         flags=0x20028))
    config=WORK/'native-input.json'; config.write_text(json.dumps(jobs,indent=2)+'\n')
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','freetype2'],text=True))
    probe=WORK/'native-probe'
    subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/selected_profile_probe.cpp'),*flags,'-o',str(probe)],check=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('FONTREAL_','QT_'))
         and k not in ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','FT2_DEBUG')}
    qt=ROOT/'build/stem-core-study/stock-qt/usr/lib/x86_64-linux-gnu'
    library=Path(record['libraries']['candidate']['library'])
    env.update(FONTREAL_FT_RENDERING='1',FONTREAL_FT_CONTRAST='weighted',FONTREAL_FT_EXECUTABLE=str(probe.resolve()),
               LD_LIBRARY_PATH=os.pathsep.join((str(library.parent),str(qt.resolve()))),TMPDIR=str((WORK/'tmp').resolve()))
    captured=WORK/'native'
    started=time.monotonic()
    with (WORK/'native.log').open('w') as log:
        subprocess.run([str(probe.resolve()),str(config.resolve()),str(captured.resolve())],env=env,check=True,stdout=log,stderr=log)
    maps=(captured/'maps.txt').read_text()
    loaded={Path(line.split()[-1]).resolve() for line in maps.splitlines() if 'libfreetype.so.' in line}
    assert loaded=={library.resolve()}
    count=0
    for label,case,arrays in sources:
        result=json.loads((captured/(label+'-'+case['id']+'.json')).read_text())
        assert len(result['glyphs'])==95
        source_path=(ROOT/'build/weighted-size-chart/native' if label=='sizes' else
                     ROOT/('build/stroke-profile-study/decorative-native' if case['id'].startswith('x') else 'build/stem-core-study/native'))/(case['id']+'.json')
        assert sha(source_path)==case['capture_sha256']; original=json.loads(source_path.read_text())
        for source,actual in zip(original['glyphs'],result['glyphs'],strict=True):
            gid=source['glyph']; assert actual['codepoint']==source['codepoint'] and actual['glyph']==gid
            assert actual['loaded']==source['loaded'],(label,case['id'],source['codepoint'],'loaded')
            values=arrays[gid]; values=values['masks'] if label=='styles' else values
            expected=dict(source['rendered'][0]); expected['mask']=values['stems' if label=='styles' else 'selected']
            assert actual['rendered']==expected,(label,case['id'],source['codepoint'],'mask')
            assert actual['repeated']==actual['immediate']==actual['character']==expected
            count+=1
    assert count==33440
    return dict(conditions=len(sources),codepoint_cases=count,public_api_calls=count*4,
                seconds=time.monotonic()-started,probe_sha256=sha(probe),library_sha256=sha(library))


def core():
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','freetype2'],text=True))
    library=WORK/'mask-core.so'
    subprocess.run(['c++','-std=c++17','-O2','-shared','-fPIC',str(ROOT/'tests/selected_mask_probe.cpp'),
                    str(ROOT/'src/fontreal_coverage.cpp'),*flags,'-o',str(library)],check=True)
    call=ctypes.CDLL(str(library)).fontreal_test_mask
    call.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_int]; call.restype=ctypes.c_int
    count=0
    for label,case,arrays in references():
        for glyph in arrays.values():
            values=glyph['masks'] if label=='styles' else glyph
            raw=bytes.fromhex(values['raw']); width=glyph['width']; height=glyph['height']
            want=bytes.fromhex(values['stems' if label=='styles' else 'selected'])
            for padding,sign in ((0,1),(3,1),(3,-1)):
                pitch=width+padding; buffer=bytearray([73]*(pitch*height))
                for y in range(height):
                    at=(y if sign>0 else height-1-y)*pitch
                    buffer[at:at+width]=raw[y*width:(y+1)*width]
                pointer=(ctypes.c_ubyte*len(buffer)).from_buffer(buffer)
                offset=0 if sign>0 or not height else (height-1)*pitch
                assert call(ctypes.byref(pointer,offset),width,height,sign*pitch)==0
                for y in range(height):
                    at=(y if sign>0 else height-1-y)*pitch
                    assert buffer[at:at+width]==want[y*width:(y+1)*width]
                    assert buffer[at+width:at+pitch]==bytes([73]*padding)
            count+=1
    assert call(None,0,0,0)==0 and call(None,1,1,1)==2
    guard=(ctypes.c_ubyte*4)(1,2,3,4)
    assert call(guard,2,2,1)==2 and bytes(guard)==bytes((1,2,3,4))
    return dict(arrays=count,layouts=3,balanced_allocations=True,library_sha256=sha(library))


def identity(path,record):
    spec=importlib.util.spec_from_file_location('selected_builder',ROOT/'tools/build-freetype.py')
    builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    class ReachedKey(Exception):pass
    keys={}
    original_output=builder.output
    with tempfile.TemporaryDirectory(prefix='key-',dir=WORK) as temporary:
        directory=Path(temporary); source=directory/'coverage.cpp'; header=directory/'coverage.h'
        builder.PROCESSOR=source; builder.DECLARATION=header; builder.WORK=directory/'artifacts-root'
        def reached(destination,*args,**kwargs):
            assert destination.parent==builder.WORK/'artifacts'
            keys[case]=destination.name
            raise ReachedKey()
        for case in ('same','processor','declaration','compiler'):
            source.write_bytes((ROOT/'src/fontreal_coverage.cpp').read_bytes()+(b'\n' if case=='processor' else b''))
            header.write_bytes((ROOT/'src/fontreal_coverage.h').read_bytes()+(b'\n' if case=='declaration' else b''))
            def output(command):
                text=original_output(command)
                return 'different compiler identity\n'+text if case=='compiler' and command==['c++','--version'] else text
            with patch.object(builder,'output',side_effect=output), patch.object(Path,'mkdir',reached), patch('sys.argv',['build-freetype.py']):
                try:builder.main()
                except ReachedKey:pass
                else:raise AssertionError('Artifact-key path was not reached')
        assert keys['same']==path.parent.name and len(set(keys.values()))==4,keys
        assert record['spec']['processor']==sha(ROOT/'src/fontreal_coverage.cpp')
    return keys


def gates(record,cff2):
    import browser_live_recipe_test as recipe
    import browser_masks_test as masks
    recipe.prepare()
    stock=record['libraries']['stock']['library']; selected=record['libraries']['candidate']['library']
    noto=masks.NOTO/'NotoSans-Regular.ttf'; count=0
    def converted(snapshot):
        result=dict(snapshot)
        result['mask']=expected_mask(bytes.fromhex(result['mask']),result['width']).hex()
        return result
    cff_fonts=[path for name,path in recipe.CFF_FONTS.items() if name!='Cantarell Variable']+[cff2]
    for font in [noto,*cff_fonts]:
        for flags in (0,0x28,0x10000,0x20000):
            for char in ('n','8','W'):
                raw=recipe.probe(stock,font,flags=0x8008,char=char)
                got=recipe.probe(selected,font,flags=flags,char=char,enabled=True,contrast='weighted')
                assert got['loaded']==raw['loaded'],(font.name,flags,'native load')
                assert got['rendered']==[converted(raw['rendered'][0])]*2
                assert got['next']==converted(raw['next']); count+=1
        for flags in (1,2,0x400,0x100,0x400000,1|4,0x400|4,0x400000|4):
            got=masks.probe(record,font,flags=flags,mode=-1,contrast='weighted')
            want=masks.probe(record,font,flags=flags,mode=-1,contrast='weighted',variant='stock')
            assert got==want,(font.name,flags,'non-raster gate'); count+=1
        for on,scope in ((False,None),(True,'/wrong'),(True,str((recipe.BUILD/'probe').resolve())+'-prefix')):
            got=recipe.probe(selected,font,flags=0,enabled=on,contrast='weighted',scope=scope)
            assert got==recipe.probe(stock,font,flags=0); count+=1
    for font,char,flags in ((masks.NOTO/'NotoColorEmoji.ttf','😀',0x100000),
                            (Path('/usr/share/fonts/X11/misc/6x13-ISO8859-1.pcf.gz'),'m',0),
                            (Path('/usr/share/fonts/type1/urw-base35/NimbusSans-Regular.t1'),'m',0x28)):
        assert recipe.probe(selected,font,char=char,flags=flags,enabled=True,contrast='weighted')==recipe.probe(stock,font,char=char,flags=flags)
        count+=1
    embedded,tricky=masks.font_fixtures(recipe.probe(stock,noto)['glyph'])
    for font,transform,remove in ((noto,'quarter',False),(noto,'diagonal',False),
                                  (tricky,'none',False),(noto,'none',True),(embedded,'none',False)):
        raw=recipe.probe(stock,font,flags=0x8008,transform=transform,remove=remove)
        got=recipe.probe(selected,font,flags=0,enabled=True,contrast='weighted',transform=transform,remove=remove)
        assert got['loaded']==raw['loaded']
        assert got['rendered']==[converted(raw['rendered'][0])]*2
        assert got['next']==converted(raw['next']); count+=1
    # One slot crosses variable outlines and old selectors before returning to selected.
    source=ROOT/'tests/freetype_variable_probe.cpp'; text=source.read_text()
    assert text.count('"ramp217"')==7
    cpp=WORK/'weighted-variable.cpp'; cpp.write_text(text.replace('"ramp217"','"weighted"'))
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Gui','freetype2'],text=True))
    binary=WORK/'weighted-variable'
    subprocess.run(['c++','-std=c++17','-fPIC',str(cpp),*flags,'-o',str(binary)],check=True)
    tt=Path('/usr/share/fonts/truetype/ubuntu/UbuntuSansMono[wght].ttf')
    assert tt.exists()
    for font in (tt,cff2):
        variants={}
        for key,lib,on,load in (('selected',selected,True,'0'),('normal',stock,False,'0x8008'),('legacy',stock,False,'0x20028' if font==tt else '0')):
            out=WORK/(key+'-variable.json')
            subprocess.run([str(binary),str(font),'15',load,str(out)],env=recipe.environment(lib,on),check=True)
            variants[key]=json.loads(out.read_text())
        for got,normal,legacy in zip(*variants.values(),strict=True):
            assert got['weight']==got['requested_weight']==normal['weight']
            want=normal if got['mode']=='weighted' else legacy
            for a,b in zip(got['glyphs'],want['glyphs'],strict=True):
                assert a['loaded']==b['loaded']
                expected=converted(b['rendered']) if got['mode']=='weighted' else masks.mild(b['rendered']) if got['mode']=='mild' and font==tt else b['rendered']
                assert a['rendered']==expected,(font.name,got['weight'],got['mode'])
            count+=1
    return dict(checks=count,formats=['TrueType','CFF','CID','CFF2','Type 1','color','bitmap'],variable_steps=18)


def browser(record,cff2):
    import browser_live_recipe_test as recipe
    _,trace,nearest=recipe.prepare()
    recipe.CFF_FONTS['Cantarell Variable']=cff2.resolve()
    variable=Path('/usr/share/fonts/truetype/ubuntu/UbuntuSansMono[wght].ttf')
    return [item for group in ('tt','tt-tail','cff','cff-tail','cff2')
            for item in recipe.browser(record,trace,nearest,variable,mode='weighted',font_group=group)]


def legacy(record):
    import browser_live_recipe_test as recipe
    import browser_masks_test as masks
    _,trace,nearest=recipe.prepare(); stock=record['libraries']['stock']['library']
    selected=record['libraries']['candidate']['library']; oracle=recipe.Oracle(Path(stock)); checks=0
    try:
        for font in (masks.NOTO/'NotoSans-Regular.ttf',recipe.CFF_FONTS['Nimbus Sans Regular']):
            for mode in ('none','mild','raw','ramp217'):
                got=recipe.probe(selected,font,size=21,char='n',flags=0,enabled=True,contrast=mode)
                active=font.suffix=='.ttf' or mode=='raw'
                library=nearest if mode in ('raw','ramp217') and active else stock
                raw=recipe.probe(library,font,size=21,char='n',flags=0x20028 if active else 0)
                assert got['loaded']==raw['loaded'],(font.name,mode)
                def wanted(snapshot,loaded):
                    if active and mode=='ramp217':return recipe.expected(oracle,loaded,snapshot)
                    if active and mode=='mild':return masks.mild(snapshot)
                    return snapshot
                assert got['rendered']==[wanted(raw['rendered'][0],raw['loaded'])]*2
                # The retained raw/none/mild transforms are stateless across next glyphs.
                if mode!='ramp217':assert got['next']==wanted(raw['next'],raw['loaded'])
                checks+=1
    finally:oracle.close()
    variable=Path('/usr/share/fonts/truetype/ubuntu/UbuntuSansMono[wght].ttf')
    runs=recipe.browser(record,trace,nearest,variable,mode='raw',font_group='tt-tail')
    runs+=recipe.browser(record,trace,nearest,variable,mode='ramp217')
    return dict(native_checks=checks,preview_runs=runs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('native','core','identity','lifecycle','gates','browser','legacy','comparison'),default='native')
    parser.add_argument('--cff2-font',type=Path,default=Path('/usr/share/fonts/opentype/cantarell/Cantarell-VF.otf'))
    args=parser.parse_args()
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True); (WORK/'tmp').mkdir(exist_ok=True)
    path,record=build()
    if args.case=='core': result=core()
    elif args.case=='identity': result=identity(path,record)
    elif args.case=='gates': result=gates(record,args.cff2_font)
    elif args.case=='browser': result=browser(record,args.cff2_font)
    elif args.case=='legacy': result=legacy(record)
    elif args.case=='comparison':
        import kde_selected_comparison_test
        result=kde_selected_comparison_test.main()
    else: result=native(record)
    (OUT/(args.case+'.json')).write_text(json.dumps(dict(build=str(path),result=result),indent=2)+'\n')
    print('PASS selected production native',json.dumps(result),flush=True)


if __name__=='__main__':main()
