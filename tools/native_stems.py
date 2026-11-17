#!/usr/bin/env python3
"""Compare native MONO-gray masks with conservative stem cleanup."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont
import supersampling as shared

ROOT = shared.ROOT
sys.path.insert(0, str(ROOT / 'tests'))
from stem_core_test import concentrate
from weighted_stroke_profiles import darken
from stroke_profiles import refine

FONTS = ('Noto Sans', 'Nimbus Sans', 'Inconsolata Nerd Font', 'Arial', 'Hack')
POINTS = (8, 10, 11, 12)
FIXTURE = ROOT / 'tests/fixtures/native-connected-stems.json'
METHODS = (('A', 'Native 1x MONO-gray'), ('B', 'Existing stem cleanup'),
           ('C', 'Cleanup + near ties'), ('D', 'Connected profiles'), ('E', 'D + weighted blend lift'))
GRID_CHARS = 'Hinm8W:!'


def weighted_blend(raw, cleaned, pairs, width):
    """Lift the existing core and its blend together from a frozen mask."""
    _, detail = darken(raw, raw, width)
    target = detail['target']
    result = bytearray(cleaned)
    for pair in pairs:
        core, fringe = pair['core'], pair['fringe']
        peak = max(cleaned[core], target)
        result[core] = peak
        result[fringe] = (cleaned[fringe]*peak + cleaned[core]//2)//cleaned[core]
    return bytes(result), {k: detail[k] for k in ('target', 'reference_cutoff', 'reference_count', 'numerator', 'denominator')}


def weighted_pairs(concentrated, profile):
    candidates = {(p['core'], p['fringe']) for p in concentrated}
    candidates.update((p['core'], p['fringe']) for run in profile['runs'] for p in run['pairs'])
    candidates.update((p['core'], p['fringe']) for p in profile['steps'])
    roles = {}
    for core, fringe in candidates:
        roles.setdefault(core,set()).add(('core',fringe))
        roles.setdefault(fringe,set()).add(('fringe',core))
    return [dict(core=c,fringe=f) for c,f in sorted(candidates) if len(roles[c])==len(roles[f])==1]


def treatments(raw, width):
    b, bp = concentrate(raw, raw, width)
    c, cp = concentrate(raw, raw, width, near_ties=True)
    d, profile = refine(raw, c['native-area'], width, connected=True)
    cleaned = d['corners']
    selected = [p for p in weighted_pairs(cp, profile) if cleaned[p['core']] > cleaned[p['fringe']]]
    e, weighted = weighted_blend(raw, cleaned, selected, width)
    return dict(A=raw, B=b['native-area'], C=c['native-area'], D=cleaned, E=e), dict(B=bp, C=cp, E=selected), weighted, profile


def mask_record(code, advance, raw):
    masks,pairs,weighted,profile = treatments(bytes(raw['pixels']),raw['width'])
    return dict(code=code,advance_pixels=advance,raw=raw,masks={k:list(v) for k,v in masks.items()},
                pairs=pairs,weighted=weighted,profile=profile,coverage_delta_D=sum(masks['D'])-sum(raw['pixels']))


def grid(output, case, records, family, label, small, characters=GRID_CHARS, name=None):
    selected = [next(r for r in records if r['code'] == ord(ch)) for ch in characters]
    cell = 22
    column = max(242, max(r['raw']['width'] for r in selected)*cell+48)
    heights = [r['raw']['height']*cell+100 for r in selected]
    sheet = Image.new('RGB', (column*len(METHODS)+16, 90+sum(heights)), (24,24,24))
    draw = ImageDraw.Draw(sheet)
    draw.text((12,10), f'{family} Regular | {case["points"]}pt | 1x native MONO-gray coverage', font=label, fill='white')
    draw.text((12,32), '0 = no ink, 255 = full ink. Orange borders mark changes from A. Native glyph previews are not resized.', font=label, fill='white')
    cells = []; previews = []; headings = []
    for col, (key,title) in enumerate(METHODS):
        draw.text((12+col*column,60), f'{key}: {title}',font=label,fill='white')
        headings.append(dict(method=key,text=f'{key}: {title}',position=[12+col*column,60]))
    y = 90
    for r, height in zip(selected, heights):
        raw = r['raw'];w,h = raw['width'],raw['height']
        for col,(key,_) in enumerate(METHODS):
            x = 12+col*column
            draw.text((x,y), chr(r['code']), font=label,fill='white')
            values = r['masks'][key]
            if values:
                patch=Image.frombytes('L',(w,h),bytes(values)).convert('RGB')
                sheet.paste(patch,(x+30,y))
                previews.append(dict(code=r['code'],method=key,box=[x+30,y,x+30+w,y+h]))
            for xx in range(w):
                draw.text((x+28+xx*cell+5,y+27),str(xx+1),font=small,fill='white')
            for yy in range(h):
                draw.text((x,y+49+yy*cell),str(yy+1),font=small,fill='white')
                for xx in range(w):
                    i=yy*w+xx;value=values[i];left=x+28+xx*cell;top=y+46+yy*cell
                    edge=(255,170,55) if value!=raw['pixels'][i] else (75,75,75)
                    draw.rectangle((left,top,left+cell-1,top+cell-1), fill=(value,)*3, outline=edge)
                    draw.text((left+2,top+4),str(value),font=small,fill='black' if value>=145 else 'white')
                    cells.append(dict(code=r['code'],method=key,index=i,value=value,
                                      box=[left,top,left+cell,top+cell],text_position=[left+2,top+4],border=list(edge)))
        y+=height
    if name is None:name=f'gallery/{case["font"]+1}_{family.replace(" ","-")}_{case["points"]:02}pt_grids.png'
    sheet.save(output/name)
    return dict(file=name,sha256=shared.sha(output/name),size=list(sheet.size),font=case['font'],points=case['points'],
                cells=cells,previews=previews,headings=headings,cell_size=cell)


def export(record_path, output):
    record=json.loads(record_path.read_text());stock=record['libraries']['stock']
    provider=Path(stock['library']).resolve(strict=True)
    if shared.sha(provider)!=stock['sha256']:
        raise ValueError('stock provider differs from paired build record')
    for name,path in [('processor','src/fontreal_coverage.cpp'),('declaration','src/fontreal_coverage.h')]:
        if shared.sha(ROOT/path)!=record['spec'][name]:
            raise ValueError('selected processor differs from paired build record')
    probe,_=shared.compile_tools()
    env=dict(os.environ);env.pop('LD_PRELOAD',None);env.pop('FREETYPE_PROPERTIES',None)
    env['LD_LIBRARY_PATH']=str(provider.parent)
    output.mkdir(parents=True,exist_ok=False)
    for name in ('captures','masks','crops','gallery','diagnostics'):(output/name).mkdir()
    sources=['tools/native_stems.py','tools/supersampling.py','tests/supersampling_probe.cpp',
             'tests/stem_core_test.py','tests/weighted_stroke_profiles.py','tests/thin_stroke_profiles.py',
             'tests/stroke_profiles.py','tests/fixtures/native-connected-stems.json',
             'src/fontreal_coverage.cpp','src/fontreal_coverage.h','tests/selected_mask_probe.cpp']
    manifest=dict(study='native-stems',target_dpi=96,points=list(POINTS),methods=list(METHODS),
                  specimen=shared.SPECIMEN,blend='encoded',placement='native MONO whole-pixel advances',
                  record_sha256=shared.sha(record_path),provider_sha256=shared.sha(provider),
                  sources={p:shared.sha(ROOT/p) for p in sources},fonts=[],cases=[],sheets=[],grids=[])
    for fi,family in enumerate(FONTS):
        match=subprocess.check_output(['fc-match','-f','%{file}\n%{family}\n%{style}\n%{fontversion}\n',family+':style=Regular'],text=True).splitlines()
        font=Path(match[0]).resolve(strict=True)
        if family not in match[1].split(','):raise ValueError(f'required font missing: {family}')
        if 'Regular' not in match[2].split(','):raise ValueError(f'required Regular style missing: {family}')
        manifest['fonts'].append(dict(family=family,matched_family=match[1],file=str(font),sha256=shared.sha(font),style=match[2],revision=match[3]))
        label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9)
        for points in POINTS:
            cap=json.loads(subprocess.check_output([str(probe),str(font),str(points),'--native-mono'],env=env))
            if Path(cap['provider']).resolve()!=provider or shared.sha(Path(cap['provider']).resolve())!=stock['sha256']:
                raise ValueError('capture loaded a different provider')
            capture_file=f'captures/{fi}_{points}.json';shared.write_json(output/capture_file,cap)
            native=next(c for c in cap['captures'] if c['mode']=='native_mono1')
            glyphs={g['code']:{**g,'advance_pixels':int(g['advance']+.5)} for g in native['glyphs']}
            places,lines=shared.layout(glyphs,240)
            records=[]
            for g in native['glyphs']:
                records.append(mask_record(g['code'],glyphs[g['code']]['advance_pixels'],shared.decode_bitmap(g)))
            mask_file=f'masks/{fi}_{points}.json';shared.write_json(output/mask_file,records)
            case=dict(font=fi,points=points,capture=capture_file,capture_sha256=shared.sha(output/capture_file),
                      masks=mask_file,masks_sha256=shared.sha(output/mask_file),placements=places,lines=lines,methods=[])
            crops={}
            for key,title in METHODS:
                masks={r['code']:{'final':{**r['raw'],'pixels':r['masks'][key]}} for r in records}
                image=shared.compose(masks,places,lines,points)
                method=dict(key=key,title=title,crops={})
                for polarity in ('light','dark'):
                    crop=ImageChops.invert(image) if polarity=='light' else image
                    name=f'crops/{fi}_{points}_{key}_{polarity}.png';crop.save(output/name);crops[key,polarity]=crop
                    method['crops'][polarity]=dict(file=name,sha256=shared.sha(output/name),size=list(crop.size))
                case['methods'].append(method)
            for polarity in ('light','dark'):
                bg,fg=(255,0) if polarity=='light' else (0,255)
                sheet=Image.new('L',(1360,crops['A',polarity].height+116),bg);draw=ImageDraw.Draw(sheet)
                draw.text((12,10),f'{family} Regular | {points}pt | 96 DPI | 1x native MONO hints / gray edges',font=label,fill=fg)
                draw.text((12,32),'A: baseline. B/C: conserve ink. D: connected profiles. E: weighted blend lift. View at 100%.',font=label,fill=fg)
                boxes=[];headings=[]
                for col,(key,title) in enumerate(METHODS):
                    x=12+col*268
                    draw.text((x,64),f'{key}: {title}',font=label,fill=fg)
                    headings.append(dict(method=key,text=f'{key}: {title}',position=[x,64]))
                    crop=crops[key,polarity];sheet.paste(crop,(x,92))
                    boxes.append(dict(method=key,box=[x,92,x+crop.width,92+crop.height],file=case['methods'][col]['crops'][polarity]['file']))
                name=f'gallery/{fi+1}_{family.replace(" ","-")}_{points:02}pt_{polarity}.png';sheet.save(output/name)
                manifest['sheets'].append(dict(file=name,sha256=shared.sha(output/name),size=list(sheet.size),font=fi,points=points,polarity=polarity,crops=boxes,headings=headings))
            if points in (11,12):manifest['grids'].append(grid(output,case,records,family,label,small))
            manifest['cases'].append(case)
    fixture=json.loads(FIXTURE.read_text())
    retained=[mask_record(r['code'],r['advance_pixels'],r['raw']) for r in fixture['records']]
    retained_file='diagnostics/retained-masks.json';shared.write_json(output/retained_file,retained)
    label=ImageFont.truetype(manifest['fonts'][0]['file'],14);small=ImageFont.truetype(manifest['fonts'][0]['file'],9)
    diagnostic=grid(output,dict(font=None,points=fixture['points']),retained,fixture['font']['family']+' (retained masks)',label,small,characters='Hi',name='diagnostics/retained-grids.png')
    manifest['diagnostic']=dict(fixture='tests/fixtures/native-connected-stems.json',fixture_sha256=shared.sha(FIXTURE),masks=retained_file,masks_sha256=shared.sha(output/retained_file),grid=diagnostic)
    shared.write_json(output/'manifest.json',manifest)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',required=True,type=Path)
    args=parser.parse_args()
    output=ROOT/'results/native-stems'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    print(export(args.record.resolve(strict=True),output))


if __name__=='__main__':main()
