#!/usr/bin/env python3
"""Export same-outline per-pixel references without changing installed rendering."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from PIL import Image, ImageChops, ImageDraw, ImageFont
import supersampling as shared
import native_stems

ROOT = shared.ROOT
sys.path.insert(0, str(ROOT/'tests'))
from browser_stroke_axis_test import Oracle
import pixel_reference_profiles as numerical

FIXTURE = ROOT/'tests/fixtures/pixel-references.json'
METHODS = (('A', 'Native raw'), ('D', 'Accepted baseline'), ('R', '4x same phase'),
           ('O', 'Coherent weak cores'), ('L', 'Local weak cores'), ('S', 'Local + bounded edges'))
TABLES = ('A', 'D', 'R', 'C', 'E', 'dO', 'O', 'dL', 'L', 'dS', 'S')
SOURCES = ('tools/pixel_references.py', 'tests/pixel_reference_profiles.py',
           'tests/pixel_references_test.py', 'tests/fixtures/pixel-references.json', 'tests/supersampling_test.py',
           'tools/native_stems.py', 'tools/supersampling.py', 'tests/browser_stroke_axis_test.py',
           'tests/supersampling_probe.cpp', 'tests/selected_mask_probe.cpp',
           'tests/stem_core_test.py', 'tests/weighted_stroke_profiles.py', 'tests/stroke_profiles.py',
           'tests/thin_stroke_profiles.py', 'tests/small_feature_profiles.py',
           'tests/bridge_coverage_test.py', 'tests/neighbor_coverage_test.py',
           'src/fontreal_coverage.cpp', 'src/fontreal_coverage.h')


def digest(values):
    return hashlib.sha256(bytes(values)).hexdigest()


def process(oracle, outline, raw, d):
    frame = numerical.padded(raw)
    native = numerical.place(numerical.raster(oracle, outline), frame)
    if native != frame:
        raise ValueError('native outline raster does not exactly reproduce the captured raw mask')
    fitted = numerical.padded(raw, d)['pixels']
    high = numerical.high_source(oracle, outline, raw)
    refs, reference_audit = numerical.references(high, fitted, frame['width'])
    results, overlay_audit = numerical.overlays(fitted, frame['width'], refs)
    all_masks=dict(A=frame['pixels'], D=fitted, **refs, **results)
    differences=[b-a for a,b in zip(all_masks['A'],all_masks['R'])]
    return dict(same_phase_difference=dict(changed=sum(v!=0 for v in differences),
                max_abs=max(map(abs,differences),default=0),coverage_delta=sum(differences)),
                coverage_totals={k:sum(v) for k,v in all_masks.items()},
                frame={k:v for k,v in frame.items() if k!='pixels'},
                masks=all_masks,
                high=high, reference=reference_audit, overlay=overlay_audit)


def numbered(output, name, title, record, label, small, note=''):
    frame = record['frame']; width, height = frame['width'], frame['height']
    cell = 20; column = max(280, width*cell+40); row_height = height*cell+94
    image = Image.new('RGB', (column*4+20, 86+row_height*3), (24,24,24))
    draw = ImageDraw.Draw(image)
    draw.text((12,10),title,font=label,fill='white')
    draw.text((12,32),'Coverage: 0 = no ink, 255 = full ink. dO/dL/dS are positive offsets from D.',font=label,fill='white')
    draw.text((12,54),note or 'Common 2px padding. Row/column coordinates start at one. Native previews are not resized.',font=small,fill='white')
    cells=[]; previews=[]; headings=[]
    for number,key in enumerate(TABLES):
        x=12+(number%4)*column; y=86+(number//4)*row_height
        values=record['overlay']['overlays'][key[1:]] if key.startswith('d') else record['masks'][key]
        draw.text((x,y),key,font=label,fill='white');headings.append(dict(text=key,position=[x,y]))
        patch=Image.frombytes('L',(width,height),bytes(values)).convert('RGB')
        image.paste(patch,(x+38,y));previews.append(dict(method=key,box=[x+38,y,x+38+width,y+height]))
        for xx in range(width):draw.text((x+30+xx*cell,y+30),str(xx+1),font=small,fill='white')
        for yy in range(height):
            draw.text((x,y+50+yy*cell),str(yy+1),font=small,fill='white')
            for xx in range(width):
                i=yy*width+xx;value=values[i];left=x+26+xx*cell;top=y+48+yy*cell
                border=(240,150,70) if key in ('O','L','S') and value!=record['masks']['D'][i] else (75,75,75)
                draw.rectangle((left,top,left+cell-1,top+cell-1),fill=(value,)*3,outline=border)
                draw.text((left+1,top+4),str(value),font=small,fill='black' if value>=145 else 'white')
                cells.append(dict(method=key,index=i,value=value,box=[left,top,left+cell,top+cell],border=list(border),text_position=[left+1,top+4]))
    image.save(output/name)
    return dict(file=name,sha256=shared.sha(output/name),size=list(image.size),title=title,note=note,cells=cells,previews=previews,headings=headings,cell_size=cell)


def benchmark(oracle, inputs, records):
    stages=('native_raster','high_raster','references','overlays','stored_apply')
    samples={key:[] for key in stages};runs=[]
    for repeat in range(3):
        checks={key:hashlib.sha256() for key in stages};counts={key:0 for key in stages}
        for item,expected in zip(inputs,records):
            t=time.perf_counter_ns();native=numerical.raster(oracle,item['snapshot']);elapsed=time.perf_counter_ns()-t
            samples['native_raster'].append(elapsed);checks['native_raster'].update(bytes(native['pixels']));counts['native_raster']+=1
            if numerical.place(native,expected['frame'])['pixels']!=expected['masks']['A']:raise ValueError('benchmark native association differs')
            t=time.perf_counter_ns();high=numerical.high_source(oracle,item['snapshot'],item['raw']);elapsed=time.perf_counter_ns()-t
            samples['high_raster'].append(elapsed);checks['high_raster'].update(bytes(high['pixels']));counts['high_raster']+=1
            if high!=expected['high']:raise ValueError('benchmark high source differs')
            d=expected['masks']['D'];width=expected['frame']['width']
            t=time.perf_counter_ns();refs,audit=numerical.references(high,d,width);elapsed=time.perf_counter_ns()-t
            samples['references'].append(elapsed);checks['references'].update(bytes(refs['R']+refs['C']+refs['E']));counts['references']+=1
            if refs!={k:expected['masks'][k] for k in ('R','C','E')} or audit!=expected['reference']:raise ValueError('benchmark references differ')
            t=time.perf_counter_ns();masks,overlay=numerical.overlays(d,width,refs);elapsed=time.perf_counter_ns()-t
            samples['overlays'].append(elapsed);checks['overlays'].update(bytes(overlay['overlays']['O']+overlay['overlays']['L']+overlay['overlays']['S']));counts['overlays']+=1
            if overlay!=expected['overlay']:raise ValueError('benchmark overlay differs')
            stored=bytes(overlay['overlays']['S']);source=bytes(d)
            t=time.perf_counter_ns();applied=bytes(a+b for a,b in zip(source,stored));elapsed=time.perf_counter_ns()-t
            samples['stored_apply'].append(elapsed);checks['stored_apply'].update(applied);counts['stored_apply']+=1
            if list(applied)!=expected['masks']['S']:raise ValueError('benchmark application differs')
        runs.append(dict(repeat=repeat+1,counts=counts,checksums={key:value.hexdigest() for key,value in checks.items()}))
    stats={key:dict(count=len(values),median_ns=statistics.median(values),p95_ns=sorted(values)[math.ceil(.95*len(values))-1],total_ns=sum(values)) for key,values in samples.items()}
    return dict(repetitions=3,glyphs_per_run=len(inputs),stages=stats,runs=runs,
                dimensions=[dict(code=i['code'],native=[i['raw']['width'],i['raw']['height']],common=[r['frame']['width'],r['frame']['height']],high=[r['high']['width'],r['high']['height']]) for i,r in zip(inputs,records)],
                payload_bytes=dict(native=sum(len(i['raw']['pixels']) for i in inputs),common_native=sum(len(r['masks']['D']) for r in records),high=sum(len(r['high']['pixels']) for r in records),one_stored_overlay=sum(len(r['masks']['D']) for r in records),three_stored_overlays=sum(3*len(r['masks']['D']) for r in records)),
                units='nanoseconds per glyph; Python prototype / FreeType FFI',
                clock='perf_counter_ns',python=sys.version.split()[0],
                exclusions=['compilation','Fontconfig','provider capture','image export','Python object overhead'],
                high_stage='one 4x outline raster plus bearing-aware placement',
                application='one retained S byte overlay, addition only; no cache framework or production speed claim')


def prepare(record_path):
    record=json.loads(record_path.read_text());stock=record['libraries']['stock'];provider=Path(stock['library']).resolve(strict=True)
    if shared.sha(provider)!=stock['sha256']:raise ValueError('stock provider differs from paired record')
    for key,path in (('processor','src/fontreal_coverage.cpp'),('declaration','src/fontreal_coverage.h')):
        if shared.sha(ROOT/path)!=record['spec'][key]:raise ValueError('processor differs from paired record')
    env=dict(os.environ);env.pop('LD_PRELOAD',None);env.pop('FREETYPE_PROPERTIES',None);env['LD_LIBRARY_PATH']=str(provider.parent)
    return provider,env


def match_font(family):
    match=subprocess.check_output(['fc-match','-f','%{file}\n%{family}\n%{style}\n%{fontversion}\n',family+':style=Regular'],text=True).splitlines()
    font=Path(match[0]).resolve(strict=True)
    if family not in match[1].split(',') or 'Regular' not in match[2].split(','):raise ValueError(f'genuine {family} Regular required')
    return font,dict(family=family,matched_family=match[1],file=font.name,sha256=shared.sha(font),style=match[2],revision=match[3])


def condition(probe,provider,env,font,points,oracle):
    capture=json.loads(subprocess.check_output([str(probe),str(font),str(points),'--native-mono'],env=env))
    if Path(capture['provider']).resolve()!=provider:raise ValueError('capture loaded a different provider')
    source=next(c for c in capture['captures'] if c['mode']=='native_mono1')
    inputs=[];records=[]
    for glyph in source['glyphs']:
        raw=shared.decode_bitmap(glyph);d=native_stems.treatments(bytes(raw['pixels']),raw['width'])[0]['D']
        item=dict(code=glyph['code'],advance_pixels=int(glyph['advance']+.5),snapshot=numerical.snapshot(glyph),raw=raw)
        value=process(oracle,item['snapshot'],raw,d);value['code']=glyph['code'];value['advance_pixels']=item['advance_pixels'];records.append(value);inputs.append(item)
    return capture,inputs,records


def images(output,inputs,records,font,family,points,methods,prefix='',matrix=False):
    label=ImageFont.truetype(str(font),14)
    glyphs={i['code']:i for i in inputs};places,lines=shared.layout(glyphs,240);crops={};cropmeta=[]
    for key,title in methods:
        image=shared.compose({r['code']:{'final':{**r['frame'],'pixels':r['masks'][key]}} for r in records},places,lines,points)
        for polarity in ('light','dark'):
            crop=ImageChops.invert(image) if polarity=='light' else image;name=f'crops/{prefix}{key}_{polarity}.png';crop.save(output/name);crops[key,polarity]=crop
            cropmeta.append(dict(method=key,polarity=polarity,file=name,sha256=shared.sha(output/name),size=list(crop.size)))
    sheets=[]
    for polarity in ('light','dark'):
        bg,fg=(255,0) if polarity=='light' else (0,255);image=Image.new('L',(268*len(methods)+20,crops['A',polarity].height+116),bg);draw=ImageDraw.Draw(image)
        draw.text((12,10),f'{family} Regular | {points}pt | 96 DPI | same native hinted outline at 4x',font=label,fill=fg)
        subtitle='A/D controls. O coherent and L local weak-core offsets. Local envelope can add excess ink. View at 100%.' if matrix else 'A/D controls. R reference only. O/L/S weak-only overlays. Local envelope can add excess ink. View at 100%.'
        draw.text((12,32),subtitle,font=label,fill=fg)
        boxes=[];headings=[]
        for col,(key,title) in enumerate(methods):
            x=12+268*col;draw.text((x,64),f'{key}: {title}',font=label,fill=fg);headings.append(dict(text=f'{key}: {title}',position=[x,64]))
            crop=crops[key,polarity];image.paste(crop,(x,92));boxes.append(dict(method=key,box=[x,92,x+crop.width,92+crop.height],file=f'crops/{prefix}{key}_{polarity}.png'))
        number=prefix.split('_')[0] if matrix else '01'
        name=f'gallery/{number}_{family.replace(" ","-")}_{points:02}pt_{polarity}.png';image.save(output/name);sheets.append(dict(file=name,sha256=shared.sha(output/name),size=list(image.size),polarity=polarity,crops=boxes,headings=headings))
    return places,lines,cropmeta,sheets


def export_matrix(record_path,output):
    provider,env=prepare(record_path)
    fonts=[match_font(family) for family in native_stems.FONTS]
    probe,_=shared.compile_tools()
    output.mkdir(parents=True,exist_ok=False)
    for name in ('gallery','crops','masks','sources'):(output/name).mkdir()
    methods=tuple(m for m in METHODS if m[0] in 'ADOL')
    manifest=dict(study='pixel-references-matrix',base_git='ff5a8fe9e7508e932935b094104b3f349c5f928a',
                  methods=list(methods),points=list(native_stems.POINTS),target_dpi=96,
                  fonts=[meta for font,meta in fonts],provider=dict(file=provider.name,sha256=shared.sha(provider)),
                  record_sha256=shared.sha(record_path),sources={p:shared.sha(ROOT/p) for p in SOURCES},
                  specimen=shared.SPECIMEN,placement='native MONO whole-pixel advances',blend='encoded',cases=[])
    oracle=Oracle(provider)
    try:
        for fi,(font,meta) in enumerate(fonts):
            for points in native_stems.POINTS:
                capture,inputs,records=condition(probe,provider,env,font,points,oracle)
                files={}
                for key,name,value in (('capture',f'sources/{fi}_{points}_capture.json',capture),('inputs',f'sources/{fi}_{points}_inputs.json',inputs),('masks',f'masks/{fi}_{points}.json',records)):
                    shared.write_json(output/name,value);files[key]=dict(file=name,sha256=shared.sha(output/name))
                places,lines,crops,sheets=images(output,inputs,records,font,meta['family'],points,methods,prefix=f'{fi+1:02}_{points}_',matrix=True)
                manifest['cases'].append(dict(font=fi,points=points,**files,placements=places,lines=lines,crops=crops,sheets=sheets))
        shared.write_json(output/'manifest.json',manifest)
    finally:oracle.close()
    return output


def export(record_path,output):
    provider,env=prepare(record_path);font,font_meta=match_font('Noto Sans');probe,_=shared.compile_tools()
    output.mkdir(parents=True,exist_ok=False)
    for name in ('gallery','crops','masks','sources','diagnostics'):(output/name).mkdir()
    oracle=Oracle(provider)
    try:
        capture,inputs,records=condition(probe,provider,env,font,12,oracle)
        shared.write_json(output/'sources/capture.json',capture)
        fixture=json.loads(FIXTURE.read_text());diagnostics=[]
        for index,item in enumerate(fixture['synthetic']):
            value=process(oracle,item['snapshot'],item['raw'],item['D']);value['name']=item['name'];value['note']=item['note'];diagnostics.append(value)
        timing=benchmark(oracle,inputs,records)
    finally:oracle.close()
    shared.write_json(output/'sources/inputs.json',inputs);shared.write_json(output/'masks/native.json',records);shared.write_json(output/'diagnostics/masks.json',diagnostics);shared.write_json(output/'benchmark.json',timing)
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9)
    places,lines,cropmeta,sheets=images(output,inputs,records,font,'Noto Sans',12,METHODS)
    grids=[]
    for code in map(ord,'i8!'):
        item=next(r for r in records if r['code']==code);grids.append(numbered(output,f'gallery/02_{code}_grid.png',f'Noto Sans Regular / 12pt / {chr(code)} / registered pixel references',item,label,small))
    diagnostic_grids=[]
    for index,item in enumerate(diagnostics):
        name=f'gallery/03_{index:02}_{item["name"]}.png'
        diagnostic_grids.append(numbered(output,name,'Analytic outline / '+item['name'],item,label,small,item['note']))
    manifest=dict(study='pixel-references',base_git='ccc3707a0be25ca081f90f1415c7789fbedd6956',font=font_meta,points=12,target_dpi=96,provider=dict(file=provider.name,sha256=shared.sha(provider),version=capture['version']),record_sha256=shared.sha(record_path),methods=list(METHODS),specimen=shared.SPECIMEN,placement='native MONO whole-pixel advances',blend='encoded',sources={p:shared.sha(ROOT/p) for p in SOURCES},capture=dict(file='sources/capture.json',sha256=shared.sha(output/'sources/capture.json')),inputs=dict(file='sources/inputs.json',sha256=shared.sha(output/'sources/inputs.json')),masks=dict(file='masks/native.json',sha256=shared.sha(output/'masks/native.json')),diagnostics=dict(file='diagnostics/masks.json',sha256=shared.sha(output/'diagnostics/masks.json'),grids=diagnostic_grids),benchmark=dict(file='benchmark.json',sha256=shared.sha(output/'benchmark.json')),placements=places,lines=lines,crops=cropmeta,sheets=sheets,grids=grids)
    shared.write_json(output/'manifest.json',manifest)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--record',required=True,type=Path);parser.add_argument('--matrix',action='store_true',help='compare five Regular fonts at 8,10,11,12pt');args=parser.parse_args()
    output=ROOT/'results/pixel-references'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    print((export_matrix if args.matrix else export)(args.record.resolve(strict=True),output))


if __name__=='__main__':main()
