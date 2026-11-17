#!/usr/bin/env python3
"""Compare exact historical O with unchanged treatments on fresh native NORMAL masks."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
from PIL import Image
import arial_coherence as prior

base=prior.base
shared=prior.shared
ROOT=shared.ROOT
METHODS=(('H','Historical O (MONO)'),('A','Raw NORMAL'),('O','O NORMAL'),
         ('U','U NORMAL'),('K3','K3 NORMAL'),('K5','K5 NORMAL'))
NEW_SOURCES=('tests/normal_treatments_probe.cpp','tools/normal_treatments.py','tests/normal_treatments_test.py')


def export(record_path,source_path,output):
    source=json.loads(source_path.read_text());source_root=source_path.parent
    if [(c['font'],c['points']) for c in source['cases']]!=[(f,p) for f in range(5) for p in (8,10,11,12)]:raise ValueError('approved complete matrix required')
    if [f['family'] for f in source['fonts']]!=list(base.native_stems.FONTS):raise ValueError('approved matrix fonts required')
    for path,sha in source['sources'].items():
        if shared.sha(ROOT/path)!=sha:raise ValueError('retained source producer changed')
    provider,env=base.prepare(record_path)
    if shared.sha(provider)!=source['provider']['sha256']:raise ValueError('paired FreeType provider differs from retained matrix')
    fonts=[base.match_font(f['family']) for f in source['fonts']]
    for (_,meta),expected in zip(fonts,source['fonts']):
        if meta!=expected:raise ValueError('retained font changed')
    build=ROOT/'build/normal-treatments';build.mkdir(parents=True,exist_ok=True);probe=build/'normal-treatments-probe'
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','freetype2'],text=True));subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/normal_treatments_probe.cpp'),'-o',str(probe),*flags,'-ldl'],check=True)
    output.mkdir(parents=True,exist_ok=False)
    for name in ('gallery','crops','captures','normal','display'):(output/name).mkdir()
    manifest=dict(study='normal-treatments',base_git='c66b7c63cc4218e6ddaad666883dbf63cacdd6b8',source_manifest=os.path.relpath(source_path,output.resolve()),source_manifest_sha256=shared.sha(source_path),record_sha256=shared.sha(record_path),
                  sources={p:shared.sha(ROOT/p) for p in (*prior.smooth.SOURCES,*prior.NEW_SOURCES,*NEW_SOURCES)},provider=dict(file=provider.name,sha256=shared.sha(provider)),fonts=source['fonts'],methods=list(METHODS),
                  focus=prior.FOCUS,specimen=source['specimen'],target_dpi=96,blend='encoded',placement='retained MONO whole-pixel advances; NORMAL actual advances recorded separately',cases=[])
    oracle=base.Oracle(provider)
    try:
        for ci,case in enumerate(source['cases']):
            fi,points=case['font'],case['points'];font=fonts[fi][0];family=source['fonts'][fi]['family'];cap=json.loads(subprocess.check_output([str(probe),str(font),str(points)],env=env))
            if Path(cap['provider']).resolve()!=provider:raise ValueError('probe loaded a different provider')
            capture=cap['captures'][0];retained=prior.load_retained(source_root/case['masks']['file'],case['masks']['sha256']);numbers=[];display=[]
            if [g['code'] for g in capture['glyphs']]!=list(range(32,127)) or [g['code'] for g in retained]!=list(range(32,127)):raise ValueError('complete own-case ASCII required')
            for glyph,old in zip(capture['glyphs'],retained):
                raw=shared.decode_bitmap(glyph);outline=base.numerical.snapshot(glyph);d=base.native_stems.treatments(bytes(raw['pixels']),raw['width'])[0]['D'];normal=base.process(oracle,outline,raw,d)
                extra,audit=prior.local_coherence(normal['masks']['D'],normal['masks']['L'],normal['masks']['S'],normal['reference']['phase_sums'],normal['reference']['axes'],normal['overlay']['primary'],normal['reference']['components'],normal['frame']['width'])
                trials=dict(U=[a+(b-a+1)//2 for a,b in zip(normal['masks']['L'],normal['masks']['S'])],**extra)
                numbers.append(dict(code=glyph['code'],raw=raw,outline=outline,actual_advance=glyph['advance'],normal=normal,trials=trials,coherence=audit))
                historical=dict(frame=old['frame'],pixels=old['masks']['O'],advance_pixels=old['advance_pixels'],source_record_sha256=prior.smooth.canonical(old))
                frame=prior.common_frame([{**old['frame'],'pixels':old['masks']['O']},{**normal['frame'],'pixels':normal['masks']['A']}],0)
                masks={'H':base.numerical.place({**old['frame'],'pixels':old['masks']['O']},frame)['pixels']}
                display_masks={**normal['masks'],**trials}
                for key in ('A','O','U','K3','K5'):masks[key]=base.numerical.place({**normal['frame'],'pixels':display_masks[key]},frame)['pixels']
                display.append(dict(code=glyph['code'],frame=frame,advance_pixels=old['advance_pixels'],actual_normal_advance=glyph['advance'],historical=historical,masks=masks))
            metas={}
            for key,name,value in [('capture',f'captures/{fi}_{points}.json',cap),('normal',f'normal/{fi}_{points}.json',numbers),('display',f'display/{fi}_{points}.json',display)]:
                shared.write_json(output/name,value);metas[key]=dict(file=name,sha256=shared.sha(output/name))
            images=prior.panels(output,display,METHODS,case['placements'],case['lines'],points,260,font,f'{fi+1:02}_{points}',f'{family} Regular | {points}pt | native NORMAL treatments',
                                'Historical O: native MONO hints / gray / darkening on. All NORMAL columns: native NORMAL / gray / darkening off.')
            controls=[]
            for crop in images['crops']:
                if crop['method']=='H' and crop['kind']=='body':
                    oldcrop=next(c for c in case['crops'] if c['method']=='O' and c['polarity']==crop['polarity']);control=Image.open(source_root/oldcrop['file']);region=Image.open(output/crop['file']).crop((0,0,control.width,control.height))
                    if shared.sha(source_root/oldcrop['file'])!=oldcrop['sha256'] or region.tobytes()!=control.tobytes():raise ValueError('historical O body region changed')
                    controls.append(dict(polarity=crop['polarity'],source=oldcrop,display_file=crop['file'],region=[0,0,control.width,control.height]))
            manifest['cases'].append(dict(font=fi,points=points,source_case=ci,source_masks=case['masks'],**metas,placements=case['placements'],lines=case['lines'],historical_body_controls=controls,**images))
    finally:oracle.close()
    shared.write_json(output/'manifest.json',manifest);return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--record',required=True,type=Path);parser.add_argument('--source-manifest',required=True,type=Path);args=parser.parse_args();output=ROOT/'results/normal-treatments'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');print(export(args.record.resolve(strict=True),args.source_manifest.resolve(strict=True),output))


if __name__=='__main__':main()
