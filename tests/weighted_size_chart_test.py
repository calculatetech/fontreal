#!/usr/bin/env python3
"""Chart the selected weighted-stem treatment at integer 8-16pt."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_coverage_test import transform
from bridge_font_matrix_test import sha, slug
from browser_stroke_axis_test import Oracle
from inconsolata_gain_test import gain
from noto_stem_winner_test import keep_winner
from stroke_profiles import refine
from weighted_stroke_profiles import darken
from weighted_stroke_test import self_test

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT/'docs/images/browser-common-ground'
WORK = ROOT/'build/weighted-size-chart'
OUT = ROOT/'results/weighted-size-chart/gallery'
FAMILIES = ('Noto Sans','Noto Serif','Hack','DejaVu Sans','DejaVu Serif','Inconsolata Nerd Font',
            'Broadway','Calisto MT','Castellar','Arial','Segoe UI','Nimbus Sans','Nimbus Mono PS','Nimbus Roman')
POINTS = tuple(range(8,17))
TEXTS = ['The quick brown fox jumps over the lazy dog.',
         'ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789',
         '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ bdfpq']


def probe_source():
    source = (ROOT/'tests/stem_core_probe.cpp').read_text()
    for old,new,count in [('for (int point : {11, 12})','for (int point : {8, 9, 10, 11, 12, 13, 14, 15, 16})',1),
                          ('470','680',2),('454','664',2)]:
        assert source.count(old) == count
        source = source.replace(old,new)
    return source


def capture(record, core, library):
    faces = {c['font']['id']:c['font'] for c in record['audit']
             if c['font']['family'] in FAMILIES and c['font']['style'] in ('Regular','Bold')}
    assert len(faces) == 26 and {f['family'] for f in faces.values()} == set(FAMILIES)
    paths = {Path(p).resolve() for p in subprocess.check_output(['fc-list','-f','%{file}\n'],text=True).splitlines()}
    ordered = sorted(faces.values(),key=lambda f:(FAMILIES.index(f['family']),f['style'] != 'Regular'))
    for f in ordered:
        matches = [p for p in paths if p.name == f['font_file'] and sha(p) == f['font_sha256']]
        assert len(matches) == 1, f"Exact recorded source unavailable: {f['label']}"
        f['file'] = str(matches[0])
    config = WORK/'input.json'; config.write_text(json.dumps(dict(faces=ordered,texts=TEXTS),indent=2)+'\n')
    source = WORK/'probe.cpp'; source.write_text(probe_source())
    flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Gui','freetype2'],text=True))
    probe = WORK/'probe'
    subprocess.run(['c++','-std=c++17','-O2','-fPIC','-I',str(ROOT/'tests'),str(source),*flags,'-o',str(probe)],check=True)
    qt = (ROOT/'build/stem-core-study/stock-qt/usr/lib/x86_64-linux-gnu').resolve()
    env = {k:v for k,v in os.environ.items() if not k.startswith(('FONTREAL_','QT_'))
           and k not in ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','FT2_DEBUG')}
    env.update(LD_LIBRARY_PATH=os.pathsep.join((str(library.resolve().parent),str(qt))),QT_QPA_PLATFORM='offscreen',
               QT_FONT_DPI='96',QT_SCALE_FACTOR='1',QT_QPA_PLATFORM_PLUGIN_PATH=str(qt/'qt6/plugins/platforms'))
    native = WORK/'native'
    with (WORK/'native.log').open('w') as log:
        subprocess.run([str(probe.resolve()),str(config.resolve()),str(native.resolve())],env=env,check=True,stdout=log,stderr=log)
    maps = (native/'maps.txt').read_text()
    for prefix,reference in core['libraries'].items():
        loaded = {Path(line.split()[-1]).resolve() for line in maps.splitlines() if prefix in line}
        assert len(loaded) == 1 and sha(loaded.pop()) == reference['sha256']
    assert set(json.loads((native/'index.json').read_text())) == {f"{f['id']}-{pt}" for f in ordered for pt in POINTS}
    return ordered, dict(source_sha256=sha(source),binary_sha256=sha(probe),libraries=core['libraries'],
                         missing_styles={f:[s for s in ('Regular','Bold') if not any(x['family']==f and x['style']==s for x in ordered)] for f in FAMILIES})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true'); parser.add_argument('--stock-library',type=Path)
    parser.add_argument('--label-font',type=Path); args = parser.parse_args(); self_test(); probe_source()
    assert set(''.join(TEXTS)) >= {chr(cp) for cp in range(32,127)}
    if args.self_test: return
    assert args.stock_library and args.label_font
    selected = json.loads((PUBLIC/'weighted-stroke-captures.json').read_text())
    previous = json.loads((PUBLIC/'stroke-profile-captures.json').read_text())
    assert sha(PUBLIC/'stroke-profile-captures.json') == selected['preferred_record_sha256']
    helpers = {**previous['helpers'],'weighted_stroke_profiles.py':selected['processor_sha256'],
               'weighted_stroke_test.py':selected['checker_sha256'],'thin_stroke_profiles.py':selected['selector_sha256'],
               'stroke_profiles.py':previous['processor_sha256'],'stroke_profile_test.py':previous['checker_sha256'],
               'noto_stem_winner_test.py':previous['accepted_checker_sha256']}
    for file,digest in helpers.items(): assert sha(ROOT/'tests'/file) == digest
    core_path = ROOT/'results/stem-core-study/gallery/manifest.json'; assert sha(core_path) == previous['full_source_sha256']
    core = json.loads(core_path.read_text()); assert sha(args.stock_library) == selected['library_sha256']
    old_path = ROOT/'results/weighted-stroke-study/gallery/masks.json'; assert sha(old_path) == selected['processed_masks_sha256']
    old_arrays = {c['id']:{g['glyph']:g for g in c['glyphs']} for c in json.loads(old_path.read_text())}
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    faces,proof = capture(previous,core,args.stock_library); audit = []; cache = {}; oracle = Oracle(args.stock_library.resolve())
    try:
        for face in faces:
            for point in POINTS:
                identifier = f"{face['id']}-{point}"; path = WORK/'native'/(identifier+'.json'); case = json.loads(path.read_text())
                assert case['id'] == identifier and case['point_size'] == point and case['font_id'] == face['id']
                assert case['font_format'] == face['format'] and len(case['rows']) == 3
                assert len(case['glyphs']) == 95 and {g['codepoint'] for g in case['glyphs']} == set(range(32,127))
                glyphs = {}; masks = {m:{} for m in ('raw','previous','selected')}; entries = []; arrays = []
                for g in case['glyphs']:
                    gid = g['glyph']; r = g['rendered'][0]; native = {k:r[k] for k in ('width','height','left','top','mask')}
                    assert g['rendered'][1] == r and oracle.raster(g['loaded']) == native
                    raw = bytes.fromhex(r['mask']); bridge = gain(transform(raw,r['width'])[0]['bridge'],226)
                    winner,_ = keep_winner(raw,bridge,r['width']); b = refine(raw,winner,r['width'])[0]['corners']
                    trials,detail = darken(raw,b,r['width']); chosen = trials['stems']
                    histogram = Counter(b); histogram.pop(0,None); needed = (sum(histogram.values())+3)//4
                    n = numerator = denominator = cutoff = 0
                    for value in sorted(histogram,reverse=True):
                        n += histogram[value]; numerator += value*value*histogram[value]; denominator += value*histogram[value]; cutoff = value
                        if n >= needed: break
                    q,rem = divmod(numerator,denominator) if denominator else (0,0)
                    target = q+int(denominator > 0 and 2*rem >= denominator)
                    assert detail['target'] == target and detail['reference_count'] == n and detail['reference_cutoff'] == cutoff
                    assert detail['numerator'] == numerator and detail['denominator'] == denominator
                    assert all(c >= a and bool(c) == bool(o) and (a < 230 or c == a) for o,a,c in zip(raw,b,chosen,strict=True))
                    assert all(c == (max(b[i],target) if i in detail['cores'] else b[i]) for i,c in enumerate(chosen))
                    if point in (11,12):
                        old = old_arrays[identifier][gid]
                        assert old['width'] == r['width'] and old['height'] == r['height']
                        assert old['masks']['raw'] == raw.hex() and old['masks']['preferred'] == b.hex() and old['masks']['stems'] == chosen.hex()
                    if gid in glyphs:
                        assert glyphs[gid] == dict(loaded=g['loaded'],raster=r)
                        assert masks['previous'][gid] == b and masks['selected'][gid] == chosen
                    else:
                        arrays.append(dict(glyph=gid,width=r['width'],height=r['height'],raw=raw.hex(),previous=b.hex(),selected=chosen.hex(),
                                           target=target,cores=detail['cores']))
                    glyphs[gid] = dict(loaded=g['loaded'],raster=r)
                    masks['raw'][gid] = raw; masks['previous'][gid] = b; masks['selected'][gid] = chosen
                    entries.append(dict(codepoint=g['codepoint'],glyph=gid,target=target,reference_cutoff=cutoff,reference_count=n,
                        numerator=numerator,denominator=denominator,changed=sum(a!=c for a,c in zip(b,chosen,strict=True)),
                        masks_sha256={m:hashlib.sha256(masks[m][gid]).hexdigest() for m in masks},coverage_sums={m:sum(masks[m][gid]) for m in masks}))
                cache[identifier] = dict(case=case,glyphs=glyphs,masks=masks)
                audit.append(dict(id=identifier,font={k:v for k,v in face.items() if k!='file'},point_size=point,
                    native_size=case['native_size'],capture_sha256=sha(path),unique_glyphs=len(glyphs),glyphs=entries,arrays=arrays))
            assert sha(Path(face['file'])) == face['font_sha256']
            print('PASS native / accepted overlap / selected coverage',face['label'],flush=True)
    finally: oracle.close()
    old = OUT/'manifest.json'
    if old.exists():
        record = json.loads(old.read_text()); assert record['producer'] == 'fontreal-weighted-size-chart'
        for r in record['images']:
            p = OUT/r['file']; assert p.parent == OUT and sha(p) == r['sha256']; p.unlink()
    assert not list(OUT.glob('*.png'))
    heading = ImageFont.truetype(str(args.label_font),20); label = ImageFont.truetype(str(args.label_font),14)
    images = []
    for face in faces:
        for dark in (True,False):
            for points in (POINTS[:5],POINTS[5:]):
                page = Image.new('RGB',(1440,800),(24,24,24)); d = ImageDraw.Draw(page); crops = []
                d.text((14,12),f"{face['family']} / {face['style']} / {points[0]}-{points[-1]}pt | selected weighted stems",font=heading,fill='white')
                d.text((14,44),'Native-normal hints / 96 DPI / scale 1 / whole-pixel placement / encoded coverage. No resampling.',font=label,fill='white')
                for column,mode in enumerate(('previous','selected')):
                    x = 10+column*740
                    d.text((x,78),'Previous B (not stock Qt)' if mode=='previous' else 'Selected: B + weighted stems only',font=label,fill='white')
                    d.rectangle((x,106,x+679,106+120*len(points)-1),fill='black' if dark else 'white')
                    for n,point in enumerate(points):
                        data = cache[f"{face['id']}-{point}"]
                        for line,row in enumerate(data['case']['rows']):
                            rgb = compose(row,data['glyphs'],data['masks'][mode],0).convert('RGB')
                            if not dark: rgb = ImageOps.invert(rgb)
                            assert rgb.size == (680,40); y = 106+120*n+40*line
                            page.paste(rgb,(x,y)); crops.append((x,y,rgb))
                for n,point in enumerate(points): d.text((720,151+120*n),str(point)+'pt',font=label,fill='white',anchor='mt')
                note = 'White on black.' if dark else 'Black on white.'
                if proof['missing_styles'][face['family']]: note += ' Bold unavailable; no synthesis.'
                d.text((14,760),note+' Selected treatment only; optional curve extension omitted.',font=label,fill='white')
                name = f"{len(images):03}_{slug(face['family'])}_{slug(face['style'])}_{points[0]}-{points[-1]}pt_{'dark' if dark else 'light'}.png"
                path = OUT/name; page.save(path)
                with Image.open(path) as saved:
                    for x,y,crop in crops: assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes() == crop.tobytes()
                images.append(dict(file=name,sha256=sha(path),font_id=face['id'],points=list(points),dark=dark))
    assert len(audit) == len(faces)*9 == 234 and len(images) == len(faces)*4 == 104
    assert {p.name for p in OUT.glob('*.png')} == {r['file'] for r in images}
    arrays = OUT/'masks.json'; arrays.write_text(json.dumps([dict(id=c['id'],glyphs=c.pop('arrays')) for c in audit],indent=2)+'\n')
    result = dict(producer='fontreal-weighted-size-chart',checker_sha256=sha(Path(__file__)),
        selected_record_sha256=sha(PUBLIC/'weighted-stroke-captures.json'),previous_record_sha256=sha(PUBLIC/'stroke-profile-captures.json'),
        helpers=helpers,probe=proof,library_sha256=sha(args.stock_library),label_font=dict(file=args.label_font.name,sha256=sha(args.label_font)),
        families=list(FAMILIES),points=list(POINTS),texts=TEXTS,logical_dpi=96,scale=1,codepoint_cases=sum(len(c['glyphs']) for c in audit),
        unique_glyph_cases=sum(c['unique_glyphs'] for c in audit),processed_masks_sha256=sha(arrays),audit=audit,images=images,
        limits=['Fixed 96 DPI and scale 1; generated masks do not qualify live application layout or deployment',
                'Previous B is a diagnostic comparator, not stock KDE or Qt',
                'No synthesized bold, italic, light or optional curve extension'])
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f"PASS {len(faces)} faces / 234 conditions / {result['codepoint_cases']} codepoints / {result['unique_glyph_cases']} unique glyphs / 104 charts",flush=True)
    print(OUT,flush=True)


if __name__ == '__main__': main()
