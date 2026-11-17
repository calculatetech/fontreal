#!/usr/bin/env python3
"""Genuine qualified Qt controls and a clearly labeled O NORMAL layout prototype."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
from PIL import Image,ImageDraw,ImageFont
import normal_treatments as previous

ROOT=previous.ROOT
shared=previous.shared
base=previous.base
sys.path.insert(0,str(ROOT/'tests'))
from selected_profile_test import expected_mask
METHODS=(('stock','Stock KDE / Qt'),('approved','Last approved profile'),('O','O NORMAL / Qt-layout prototype'))
NEW_SOURCES=('tests/noto_kde_probe.cpp','tools/noto_kde_comparison.py','tests/noto_kde_comparison_test.py')
EXTRA_SOURCES=('tests/freetype_reference.h','tests/selected_profile_test.py','tests/noto_stem_winner_test.py','tests/inconsolata_gain_test.py','tests/kde_selected_comparison.cpp','tests/kde_selected_comparison_test.py')
SOURCES=tuple(dict.fromkeys((*previous.prior.smooth.SOURCES,*previous.prior.NEW_SOURCES,*previous.NEW_SOURCES,*EXTRA_SOURCES,*NEW_SOURCES)))
BODY=['The quick brown fox jumps over the lazy dog.']+[''.join(map(chr,range(first,min(first+32,127)))) for first in (32,64,96)]+['Repeated spaces: A  B   C','AV To office fi fl']
FOCUS='() O O i8! W'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def admit(record_path,stock_qt,approved_qt,baseline_path):
    baseline=json.loads(baseline_path.read_text());record=json.loads(record_path.read_text())
    if baseline['profile']!='native normal + selected weighted stems only' or baseline['logical_dpi']!=96 or baseline['scale']!=1:raise ValueError('qualified native weighted baseline required')
    expected={role:next(c['libraries'] for c in baseline['captures'] if c['mode']==mode) for role,mode in (('stock','stock'),('approved','selected'))}
    providers={};libraries={}
    for role,key in (('stock','stock'),('approved','candidate')):
        entry=record['libraries'][key];path=Path(entry['library']).resolve(strict=True)
        if sha(path)!=entry['sha256']:raise ValueError('paired FreeType artifact hash differs')
        if entry['sha256']!=expected[role]['libfreetype.so.']['sha256']:raise ValueError('FreeType role differs from qualified baseline: '+role)
        providers[role]=path
    for key,path in (('processor','src/fontreal_coverage.cpp'),('declaration','src/fontreal_coverage.h')):
        if record['spec'][key]!=sha(ROOT/path):raise ValueError('paired core declaration differs')
    for role,folder in (('stock',stock_qt),('approved',approved_qt)):
        entries={}
        for stem in ('libQt6Core.so.','libQt6Gui.so.'):
            path=(folder/(stem+'6')).resolve(strict=True)
            if sha(path)!=expected[role][stem]['sha256']:raise ValueError('Qt role differs from qualified baseline: '+role+' '+stem)
            entries[stem]=path
        libraries[role]=entries
    system_qt=Path(subprocess.check_output(['pkg-config','--variable=libdir','Qt6Widgets'],text=True).strip())
    for role,folder in (('stock',stock_qt),('approved',approved_qt)):
        widgets=folder/'libQt6Widgets.so.6'
        if not widgets.exists():widgets=system_qt/'libQt6Widgets.so.6'
        widgets=widgets.resolve(strict=True)
        if sha(widgets)!=expected[role]['libQt6Widgets.so.']['sha256']:raise ValueError('Qt Widgets differs from qualified baseline')
        libraries[role]['libQt6Widgets.so.']=widgets
    font,meta=base.match_font('Noto Sans');qualified=next(f for f in baseline['fonts'] if f['file']=='NotoSans-Regular.ttf')
    if meta['sha256']!=qualified['sha256']:raise ValueError('Noto Sans differs from qualified baseline')
    for image in baseline['images']:
        if sha(baseline_path.parent/image['file'])!=image['sha256']:raise ValueError('qualified baseline image differs')
    return baseline,providers,libraries,font,meta


def instances(section):
    return [g for line in section['lines'] for run in line['runs'] for g in run['glyphs']]


def compose(section,glyphs,key,polarity):
    width,height=section['width'],section['height'];background=255 if polarity=='light' else 0;foreground=255-background;pixels=[background]*(width*height);layers=[0]*len(pixels)
    for placed in instances(section):
        glyph=glyphs[placed['id']];raw=glyph['raw'];values=glyph[key];left=math.floor(placed['x'])+raw['left'];top=math.floor(placed['y']+.5)+raw['top']
        for y in range(raw['height']):
            for x in range(raw['width']):
                a=values[y*raw['width']+x];xx,yy=left+x,top+y
                if not 0<=xx<width or not 0<=yy<height:
                    if a:raise ValueError('native glyph exceeds capture canvas')
                    continue
                i=yy*width+xx
                if a:layers[i]+=1
                pixels[i]=(foreground*a+pixels[i]*(255-a)+127)//255
    return Image.frombytes('L',(width,height),bytes(pixels)).convert('RGB'),layers


def actual_maps(path,libraries,providers,role,baseline):
    text=path.read_text();result={}
    for stem in ('libQt6Core.so.','libQt6Gui.so.','libQt6Widgets.so.'):
        paths={Path(line.split()[-1]).resolve() for line in text.splitlines() if stem in line};expected=libraries[role][stem]
        if paths!={expected}:raise ValueError('actual Qt mappings differ for '+role+' '+stem)
        result[stem]=dict(file=expected.name,sha256=sha(expected))
    ft={Path(line.split()[-1]).resolve() for line in text.splitlines() if 'libfreetype.so.' in line};required={providers[role],providers['stock']}
    if ft!=required:raise ValueError('actual FreeType role/reference mappings differ')
    result['freetype_roles']=dict(qt=dict(file=providers[role].name,sha256=sha(providers[role])),reference=dict(file=providers['stock'].name,sha256=sha(providers['stock'])))
    return result


def export(record_path,stock_qt,approved_qt,baseline_path,output):
    baseline,providers,libraries,font,font_meta=admit(record_path,stock_qt,approved_qt,baseline_path)
    build=ROOT/'build/noto-kde-comparison';build.mkdir(parents=True,exist_ok=True);probe=build/'noto-kde-probe';flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','freetype2'],text=True));subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/noto_kde_probe.cpp'),'-o',str(probe),*flags],check=True)
    output.mkdir(parents=True,exist_ok=False)
    for name in ('captures','masks','crops','gallery','proofs'):(output/name).mkdir()
    clean={k:v for k,v in os.environ.items() if not k.startswith(('FONTREAL_','QT_')) and k not in ('LD_LIBRARY_PATH','LD_PRELOAD','FT2_DEBUG','FREETYPE_PROPERTIES')}
    plugins=subprocess.check_output(['qtpaths6','--query','QT_INSTALL_PLUGINS'],text=True).strip();clean.update(QT_QPA_PLATFORM='offscreen',QT_FONT_DPI='96',QT_SCALE_FACTOR='1',QT_PLUGIN_PATH=plugins,FREETYPE_PROPERTIES='cff:no-stem-darkening=1 autofitter:no-stem-darkening=1')
    fc=subprocess.check_output(['fc-match','-f','%{antialias}\n%{hintstyle}\n%{autohint}\n%{rgba}\n','Noto Sans:style=Regular'],text=True).splitlines()
    manifest=dict(study='noto-kde-comparison',base_git='9229921266f95c0c29c58a7ee7031abcf192bd24',methods=list(METHODS),body=BODY,focus=FOCUS,font=font_meta,baseline_manifest=os.path.relpath(baseline_path,output.resolve()),baseline_sha256=sha(baseline_path),record_sha256=sha(record_path),sources={p:sha(ROOT/p) for p in SOURCES},fontconfig=dict(antialias=fc[0],hintstyle=int(fc[1]),autohint=fc[2],rgba=int(fc[3])),inputs={role:{**{stem:dict(file=p.name,sha256=sha(p)) for stem,p in libraries[role].items()},'libfreetype.so.':dict(file=providers[role].name,sha256=sha(providers[role]))} for role in libraries},scope='Native Qt GUI text. O is a Qt-layout prototype, not a deployed Qt renderer. No KWin coverage or installed selector.',cases=[])
    oracle=base.Oracle(providers['stock'])
    try:
        for points in (8,10,11,12):
            for polarity in ('light','dark'):
                captures={};metadata={};images={}
                for role in ('stock','approved'):
                    prefix=output/'captures'/f'{points}_{polarity}_{role}';selected=role=='approved';env=dict(clean,LD_LIBRARY_PATH=os.pathsep.join((str(providers[role].parent),str(approved_qt if selected else stock_qt))),FONTREAL_FT_RENDERING='1' if selected else '0',FONTREAL_FT_CONTRAST='weighted',FONTREAL_FT_EXECUTABLE=str(probe.resolve()),FONTREAL_RENDERING='1' if selected else '0',FONTREAL_BLEND='encoded',FONTREAL_CONTRAST='none',FONTREAL_TEST_REFERENCE_FREETYPE=str(providers['stock']))
                    with (build/f'{points}-{polarity}-{role}.log').open('w') as log:subprocess.run([str(probe.resolve()),str(points),polarity,str(font),str(prefix)],env=env,stdout=log,stderr=log,check=True)
                    cap=json.loads(prefix.with_suffix('.json').read_text());maps_path=prefix.with_suffix('.maps');maps=actual_maps(maps_path,libraries,providers,role,baseline);items={}
                    for section in cap['sections']:
                        filename=str(prefix.relative_to(output))+'-'+section['kind']+'.png';image=Image.open(output/filename).convert('RGB');images[role,section['kind']]=image;items[section['kind']]=dict(file=filename,sha256=sha(output/filename),size=list(image.size))
                    metadata[role]=cap;captures[role]=dict(metadata=dict(file=str(prefix.with_suffix('.json').relative_to(output)),sha256=sha(prefix.with_suffix('.json'))),maps=dict(file=str(maps_path.relative_to(output)),sha256=sha(maps_path)),actual_libraries=maps,images=items)
                approved=metadata['approved'];glyphs={};numeric=[]
                for g in approved['glyphs']:
                    raw=g['raw'];selected=list(expected_mask(bytes(raw['pixels']),raw['width'])) if raw['pixels'] else []
                    if (raw['width'],raw['height'],selected)!=(g['qt_alpha']['width'],g['qt_alpha']['height'],g['qt_alpha']['pixels']):raise ValueError('approved Qt alpha differs from shipped reference for gid '+str(g['id']))
                    d=base.native_stems.treatments(bytes(raw['pixels']),raw['width'])[0]['D'];normal=base.process(oracle,dict(outline=g['outline'],contours=g['contours']),raw,d);glyphs[g['id']]={**g,'selected':selected,'O':normal['masks']['O']};numeric.append(dict(id=g['id'],raw=raw,selected=selected,normal=normal))
                    # O is padded by the normal owner; composition keeps its own frame/bearings.
                    glyphs[g['id']]['O_raw']=normal['frame']
                proof=[];prototype={}
                for section in approved['sections']:
                    image,layers=compose(section,glyphs,'selected',polarity);native=images['approved',section['kind']]
                    if image.size!=native.size:raise ValueError('approved native image dimensions differ')
                    reference_bytes,native_bytes=image.tobytes(),native.tobytes();errors=[max(abs(reference_bytes[i+j]-native_bytes[i+j]) for j in range(3)) for i in range(0,len(native_bytes),3)]
                    if any(e>max(1,depth) for e,depth in zip(errors,layers)):raise ValueError('approved native reconstruction exceeds overlap bound')
                    filename=f'proofs/{points}_{polarity}_{section["kind"]}_approved.png';image.save(output/filename);proof.append(dict(kind=section['kind'],file=filename,sha256=sha(output/filename),max_error=max(errors,default=0),max_nonzero_layers=max(layers,default=0)))
                    o_glyphs={gid:{**g,'raw':g['O_raw']} for gid,g in glyphs.items()};o,_=compose(section,o_glyphs,'O',polarity);name=f'crops/{points}_{polarity}_O_{section["kind"]}.png';o.save(output/name);prototype[section['kind']]=dict(file=name,sha256=sha(output/name),size=list(o.size))
                name=f'masks/{points}_{polarity}.json';shared.write_json(output/name,numeric)
                body_h=max(images['stock','body'].height,images['approved','body'].height);focus_h=max(images['stock','focus'].height,images['approved','focus'].height);bg='white' if polarity=='light' else 'black';fg='black' if polarity=='light' else 'white';sheet=Image.new('RGB',(1584,104+focus_h+28+body_h+12),bg);draw=ImageDraw.Draw(sheet);label=ImageFont.truetype(str(font),14);draw.text((12,10),f'Noto Sans Regular | {points}pt | native 96 DPI / 1x',font=label,fill=fg);draw.text((12,32),'Stock RGB is preserved. O uses approved Qt layout and NORMAL source; prototype only. View at 100%.',font=label,fill=fg);boxes=[];headings=[]
                for col,(role,caption) in enumerate(METHODS):
                    x=12+col*524;draw.text((x,64),caption,font=label,fill=fg);headings.append(dict(text=caption,position=[x,64]));entry=dict(method=role)
                    for kind,y in (('focus',96),('body',104+focus_h+28)):
                        meta=prototype[kind] if role=='O' else captures[role]['images'][kind];patch=Image.open(output/meta['file']).convert('RGB');sheet.paste(patch,(x,y));entry[kind]=dict(file=meta['file'],box=[x,y,x+patch.width,y+patch.height])
                    boxes.append(entry)
                sheet_name=f'gallery/{points}_{polarity}.png';sheet.save(output/sheet_name);manifest['cases'].append(dict(points=points,polarity=polarity,captures=captures,masks=dict(file=name,sha256=sha(output/name)),approved_reconstruction=proof,prototype=prototype,sheet=dict(file=sheet_name,sha256=sha(output/sheet_name),size=list(sheet.size),headings=headings,crops=boxes)))
    finally:oracle.close()
    shared.write_json(output/'manifest.json',manifest);return output


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('record','stock-qt','approved-qt','baseline-manifest'):p.add_argument('--'+name,type=Path,required=True)
    return p


def main():
    args=parser().parse_args();output=ROOT/'results/noto-kde-comparison'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');print(export(args.record.resolve(),args.stock_qt.resolve(),args.approved_qt.resolve(),args.baseline_manifest.resolve(),output))


if __name__=='__main__':main()
