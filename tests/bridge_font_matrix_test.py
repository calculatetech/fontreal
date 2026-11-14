#!/usr/bin/env python3
"""Build a native-size, candidate-only gallery from installed font faces."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_coverage_test import bridge_checks, transform
from browser_stroke_axis_test import Oracle

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'build/bridge-font-matrix'
OUT = ROOT/'results/bridge-font-matrix'
GALLERY = OUT/'gallery'
POINTS = list(range(8, 17))
FAMILIES = ['Noto Sans', 'Noto Serif', 'DejaVu Sans', 'DejaVu Serif', 'Arial',
            'Calibri', 'Segoe UI', 'Liberation Sans', 'Liberation Serif', 'Lato',
            'Hack', 'Inconsolata Nerd Font', 'DejaVu Sans Mono', 'Liberation Mono',
            'Nimbus Sans', 'Nimbus Roman', 'Nimbus Mono PS', 'Wingdings', 'Webdings']
TEXTS = [
    'The quick brown fox jumps over the lazy dog.',
    'THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG.',
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz',
    '0123456789   0O oO 1Il| rn m   :;!? i j . …',
    '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~',
    '€ £ ¥ ¢ © ® ™ ± × ÷ ≠ ≤ ≥ → ← ↑ ↓ ✓ ✗',
    'ÀÁÂÃÄÅ Æ Ç é é ö ö ß œ Ø',
    'fi fl ffi ffl  office affine  AV VA To Wa',
    ': ; ! i j . …   : :   ! !   () [] {} <>   0358 a e o s VvWw',
    'Greek: ΑΒΓΔ Ω αβγδ ω   Cyrillic: АБВГ Я абвг я',
]
WIDTH, PAGE_HEIGHT = 1440, 880


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(value):
    return re.sub('[^A-Za-z0-9]+', '-', value).strip('-')


def inventory():
    found = defaultdict(lambda: defaultdict(list))
    for line in subprocess.check_output(['fc-list', '-f', '%{family}|%{style}|%{fontformat}|%{file}\n'], text=True).splitlines():
        family, styles, format_, file = line.split('|', 3)
        family, style = family.split(',')[0], styles.split(',')[0]
        if family not in FAMILIES or format_ not in ('TrueType', 'CFF'):
            continue
        if any(word in style.lower() for word in ('condensed', 'narrow')):
            continue
        if family.startswith('Nimbus') and format_ != 'CFF':
            continue
        canonical = {'Book':'Regular', 'Oblique':'Italic', 'Bold Oblique':'Bold Italic'}.get(style, style)
        found[family][canonical].append((style, format_, file))
    faces, unavailable = [], {}
    order = ['Regular','Italic','Bold','Bold Italic','Hairline','Hairline Italic','Thin','Thin Italic',
             'ExtraLight','Light','Light Italic','Semilight','Semilight Italic','Medium','Medium Italic',
             'Semibold','Semibold Italic','Heavy','Heavy Italic','Black','Black Italic']
    for family in FAMILIES:
        unavailable[family] = [s for s in ('Regular','Italic','Bold','Bold Italic') if s not in found[family]]
        for canonical in sorted(found[family], key=lambda s: (order.index(s) if s in order else len(order), s)):
            candidates = found[family][canonical]
            match = subprocess.check_output(['fc-match','-f','%{file}',family+':style='+candidates[0][0]], text=True)
            style, format_, file = sorted(candidates, key=lambda r: (r[2] != match, r[2]))[0]
            faces.append(dict(id=f'f{len(faces)+1:03}', family=family, style=canonical,
                              label=family+' / '+canonical, format=format_, file=str(Path(file).resolve()),
                              font_file=Path(file).name, font_sha256=sha(Path(file)),
                              symbols=family in ('Wingdings','Webdings'), nerd=family=='Inconsolata Nerd Font'))
    assert faces and len({(r['family'],r['style']) for r in faces}) == len(faces)
    return faces, unavailable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('library','stock-library','label-font'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    bridge_checks()
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    faces, unavailable = inventory()
    config = dict(width=1400, points=POINTS, texts=TEXTS, faces=faces)
    input_file = WORK/'input.json'
    input_file.write_text(json.dumps(config, ensure_ascii=False, sort_keys=True))
    flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Gui','freetype2'], text=True))
    binary = WORK/'probe'
    subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/font_matrix_probe.cpp'),*flags,'-o',str(binary)], check=True)
    recipe = dict(input_sha256=sha(input_file), batch_source_sha256=sha(ROOT/'tests/font_matrix_probe.cpp'),
                  snapshot_source_sha256=sha(ROOT/'tests/freetype_mask_probe.cpp'), binary_sha256=sha(binary),
                  library_sha256=sha(args.library), qt_version=subprocess.check_output(['pkg-config','--modversion','Qt6Gui'],text=True).strip())
    native = WORK/'native'
    native.mkdir(exist_ok=True)
    cache_file = WORK/'native-cache.json'
    cached = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    reuse = cached.get('recipe') == recipe and all((native/r['file']).exists() and sha(native/r['file']) == r['sha256'] for r in cached.get('cases',[]))
    if not reuse:
        env = {k:v for k,v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
               ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','FT2_DEBUG','QT_SCALE_FACTOR','QT_SCREEN_SCALE_FACTORS')}
        env.update(QT_QPA_PLATFORM='offscreen',QT_FONT_DPI='96',FONTREAL_RENDERING='0',FONTREAL_FT_RENDERING='1',
                   FONTREAL_FT_CONTRAST='raw',FONTREAL_FT_EXECUTABLE=str(binary.resolve()),
                   FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1',LD_LIBRARY_PATH=str(args.library.resolve().parent))
        with (WORK/'native.log').open('w') as log:
            subprocess.run([str(binary.resolve()),str(input_file.resolve()),str(native.resolve())],env=env,check=True,stdout=log,stderr=log)
        index = json.loads((native/'index.json').read_text())
        cached = dict(recipe=recipe, cases=[dict(r,sha256=sha(native/r['file'])) for r in index])
        cache_file.write_text(json.dumps(cached,indent=2)+'\n')
    expected = {f"{f['id']}-{p:02}" for f in faces for p in POINTS}
    rows = cached['cases']
    assert len(rows) == len(expected) and {r['id'] for r in rows} == expected
    case_files = {r['id']:native/r['file'] for r in rows}
    print('Native capture ready:',len(faces),'faces,',len(rows),'conditions',flush=True)
    label = ImageFont.truetype(str(args.label_font),14)
    heading = ImageFont.truetype(str(args.label_font),20)
    oracle = Oracle(args.stock_library.resolve())
    gallery_rows, cases, overview = [], [], []
    GALLERY.mkdir(exist_ok=True)
    previous = GALLERY/'manifest.json'
    if previous.exists():
        owned = json.loads(previous.read_text())
        assert owned['producer'] == 'fontreal-bridge-font-matrix'
        for item in owned['images']:
            name = item['file']
            assert Path(name).name == name and name.endswith('.png')
            path = GALLERY/name
            if path.exists():
                assert sha(path) == item['sha256'], 'An existing gallery image was modified'
                path.unlink()
    assert not list(GALLERY.glob('*.png')), 'Gallery contains images outside its previous manifest'
    number = 2

    def save_page(face, blocks):
        nonlocal number
        height = 106+sum(b['height']+38 for b in blocks)+24
        assert height <= PAGE_HEIGHT
        for palette in ('Dark','Light'):
            background, foreground = ((0,0,0),(255,255,255)) if palette=='Dark' else ((255,255,255),(0,0,0))
            image = Image.new('RGB',(WIDTH,height),background)
            draw = ImageDraw.Draw(image)
            draw.text((20,12),face['label']+' | '+face['format']+' | 170 + guarded bridge',font=heading,fill=foreground)
            draw.text((20,43),'Native size at 96 DPI / 100% scale. Red boxes mark glyphs unavailable in this exact face.',font=label,fill=foreground)
            if face['symbols']:
                draw.text((20,68),'Symbol font: letters display as pictures. Extra rows contain the U+F020-F0FF symbol bank.',font=label,fill=foreground)
            y, crops = 98, []
            for b in blocks:
                draw.text((20,y),f"{b['point_size']}pt",font=heading,fill=foreground)
                body = b[palette]
                image.paste(body,(20,y+28));crops.append((20,y+28,body));y+=b['height']+38
            name=f"{number:04}_{slug(face['family'])}_{slug(face['style'])}_{blocks[0]['point_size']:02}-{blocks[-1]['point_size']:02}pt_{palette}.png"
            target=GALLERY/name;image.save(target)
            with Image.open(target) as saved:
                for x,y,body in crops:assert saved.crop((x,y,x+body.width,y+body.height)).tobytes()==body.tobytes()
            gallery_rows.append(dict(file=name,sha256=sha(target),font_id=face['id'],points=[b['point_size'] for b in blocks],palette=palette))
            number+=1

    try:
        for face in faces:
            blocks, used_height = [], 130
            for point in POINTS:
                path=case_files[f"{face['id']}-{point:02}"]
                case=json.loads(path.read_text());assert case['font_id']==face['id'] and case['point_size']==point
                assert case['font_format']==face['format']
                texts=list(TEXTS)
                if face['symbols']:texts += [''.join(chr(c) for c in range(start,start+32)) for start in range(0xf020,0xf100,32)]
                if face['nerd']:texts += ['Nerd icons: \uf120 \uf07b \uf013 \ue0b0 \ue0b2']
                assert case['texts']==texts
                for index,text in enumerate(texts):
                    frames=[r for r in case['frames'] if r['text']==index];cursor=0
                    for frame in frames:assert frame['start']==cursor;cursor+=frame['length']
                    assert cursor==len(text)
                glyphs={g['glyph']:g for g in case['glyphs']};filtered={};changed=0;unboosted=0;bridges=0
                if face['family']=='Nimbus Sans' and face['style']=='Regular' and point==11:
                    baseline=json.loads((ROOT/'docs/images/browser-common-ground/raw-coverage-grid-captures.json').read_text())
                    if face['font_sha256']==baseline['font_sha256']:
                        assert case['native_size']==15
                        for char in 'oseaftVW':
                            gid=case['character_map'][str(ord(char))]
                            assert hashlib.sha256(bytes.fromhex(glyphs[gid]['raster']['mask'])).hexdigest()==baseline['glyphs'][char]['mask_sha256']
                for gid,g in glyphs.items():
                    r=g['raster'];data=bytes.fromhex(r['mask'])
                    assert len(data)==r['width']*r['height']
                    assert oracle.raster(g['loaded'])=={k:r[k] for k in ('width','height','left','top','mask')}
                    modes,selected,_=transform(data,r['width']);filtered[gid]=modes['bridge']
                    changed+=sum(a!=b for a,b in zip(data,filtered[gid],strict=True));bridges+=len(selected)
                    unboosted+=sum(170<=a<230 and a==b for a,b in zip(data,filtered[gid],strict=True))
                width,height=case['width'],case['height'];alpha=bytearray(width*height)
                independent=Image.new('RGBA',(width,height),(0,0,0,0))
                assert len(case['missing'])==sum(o['glyph']==0 for o in case['occurrences'])
                for o in case['occurrences']:
                    gid=o['glyph']
                    if not gid:continue
                    r=glyphs[gid]['raster'];data=filtered[gid];x=o['x']+r['left'];y=o['y']-r['top']
                    assert x>=0 and y>=0 and x+r['width']<=width and y+r['height']<=height
                    if not data:continue
                    layer=Image.new('RGBA',(r['width'],r['height']),(0,0,0,0));layer.putalpha(Image.frombytes('L',layer.size,data));independent.alpha_composite(layer,(x,y))
                    for i,a in enumerate(data):
                        at=(y+i//r['width'])*width+x+i%r['width'];alpha[at]=a+(alpha[at]*(255-a)+127)//255
                assert independent.getchannel('A').tobytes()==bytes(alpha)
                dark=Image.frombytes('L',(width,height),bytes(alpha)).convert('RGB');light=ImageOps.invert(dark)
                missing_codes=sorted({ord(texts[o['text']][o['string_index']]) for o in case['missing']})
                missing_boxes=[]
                for image in (dark,light):
                    draw=ImageDraw.Draw(image)
                    for o in case['missing']:
                        size=case['native_size'];x=o['x']+1;y=o['y']-max(3,int(size*.75));w=max(3,min(int(o['missing_advance'])-2,int(size*.6)));h=max(3,int(size*.75))
                        assert x>=0 and y>=0 and x+w<width and y+h<height
                        draw.rectangle((x,y,x+w,y+h),outline=(220,70,70))
                        if image is dark and o['text']==0:missing_boxes.append((x,y,x+w+1,y+h+1))
                b=dict(point_size=point,height=height,Dark=dark,Light=light)
                assert height+168<=PAGE_HEIGHT, f"Single point block too tall: {face['label']} {point}pt"
                if blocks and used_height+height+38>PAGE_HEIGHT:save_page(face,blocks);blocks=[];used_height=130
                blocks.append(b);used_height+=height+38
                if face['style']=='Regular' and point==11:
                    ink=list(missing_boxes)
                    for o in case['occurrences']:
                        if o['text']==0 and o['glyph']:
                            r=glyphs[o['glyph']]['raster']
                            if r['height']:ink.append((o['x']+r['left'],o['y']-r['top'],o['x']+r['left']+r['width'],o['y']-r['top']+r['height']))
                    assert ink
                    bounds=(0,max(0,min(r[1] for r in ink)-1),1100,min(height,max(r[3] for r in ink)+1))
                    # The overview crop must retain all pangram ink.
                    for o in case['occurrences']:
                        if o['text']==0 and o['glyph']:
                            r=glyphs[o['glyph']]['raster']
                            assert o['x']+r['left']+r['width']<=1100
                            assert bounds[1]<=o['y']-r['top'] and o['y']-r['top']+r['height']<=bounds[3]
                        elif o['text']!=0 and o['glyph']:
                            r=glyphs[o['glyph']]['raster'];top=o['y']-r['top']
                            assert not r['height'] or top>=bounds[3] or top+r['height']<=bounds[1]
                    overview.append((face,{p:img.crop(bounds) for p,img in [('Dark',dark),('Light',light)]}))
                cases.append(dict(id=case['id'],font_id=face['id'],point_size=point,native_size=case['native_size'],
                                  native_capture_sha256=sha(path),glyphs=len(glyphs),occurrences=len(case['occurrences']),
                                  missing_codepoints=missing_codes,changed_pixels=changed,bridge_candidates=bridges,
                                  unboosted_eligible_pixels=unboosted,candidate_alpha_sha256=hashlib.sha256(alpha).hexdigest()))
            if blocks:save_page(face,blocks)
            assert sha(Path(face['file']))==face['font_sha256']
            print('Verified',face['label'],flush=True)
    finally:
        oracle.close()
    assert len(cases)==len(expected) and {c['id'] for c in cases}==expected
    overview_groups=[];group=[];height=100
    for row in overview:
        h=max(img.height for img in row[1].values())+12
        if group and height+h>PAGE_HEIGHT-24:overview_groups.append(group);group=[];height=100
        group.append(row);height+=h
    if group:overview_groups.append(group)
    for page,group in enumerate(overview_groups):
        height=100+sum(max(img.height for img in images.values())+12 for _,images in group)+24
        for palette in ('Dark','Light'):
            bg,fg=((0,)*3,(255,)*3) if palette=='Dark' else ((255,)*3,(0,)*3)
            image=Image.new('RGB',(WIDTH,height),bg);draw=ImageDraw.Draw(image)
            draw.text((20,12),'170 + guarded bridge | regular faces | 11pt',font=heading,fill=fg)
            draw.text((20,44),'Arrow keys browse all fonts, actual styles, sizes and backgrounds in this folder.',font=label,fill=fg)
            y=90;crops=[]
            for face,images in group:
                draw.text((20,y),face['family'],font=label,fill=fg);strip=images[palette];image.paste(strip,(270,y));crops.append((270,y,strip));y+=strip.height+12
            name=f'000{page}_Overview_{palette}.png';target=GALLERY/name;image.save(target)
            with Image.open(target) as saved:
                for x,y,strip in crops:assert saved.crop((x,y,x+strip.width,y+strip.height)).tobytes()==strip.tobytes()
            gallery_rows.append(dict(file=name,sha256=sha(target),overview=True,palette=palette))
    assert len({r['file'] for r in gallery_rows})==len(gallery_rows)
    assert {p.name for p in GALLERY.glob('*.png')}=={r['file'] for r in gallery_rows}
    portable=[{k:v for k,v in f.items() if k!='file'} for f in faces]
    result=dict(producer='fontreal-bridge-font-matrix',profile='170 + guarded bridge only',texts=TEXTS,
                logical_dpi=96,scale=1,points=POINTS,faces=portable,unavailable_styles=unavailable,
                conditions=cases,images=sorted(gallery_rows,key=lambda r:r['file']),
                library_sha256=sha(args.library),stock_library_sha256=sha(args.stock_library),
                checker_sha256=sha(Path(__file__)),batch_source_sha256=sha(ROOT/'tests/font_matrix_probe.cpp'),
                filter_sha256=sha(ROOT/'tests/bridge_coverage_test.py'),average_sha256=sha(ROOT/'tests/neighbor_coverage_test.py'),
                native_recipe_sha256=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest(),
                limits=['Scientific component gallery, not installed application output','No synthetic font styles or fallback fonts',
                        'Symbols render as pictures in symbol families; red diagnostic boxes mark unavailable glyphs'])
    previous.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',len(faces),'faces,',len(cases),'point conditions,',len(gallery_rows),'native-size candidate-only gallery pages')
    print(GALLERY)


if __name__=='__main__':
    main()
