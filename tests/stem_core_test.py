#!/usr/bin/env python3
"""Broaden the core-240 area diagnostic; retain actual stock Qt for Noto Sans."""
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
from bridge_font_matrix_test import inventory, sha, slug, FAMILIES
from browser_stroke_axis_test import Oracle
from inconsolata_gain_test import gain
from inconsolata_u_test import u_trials

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'build/stem-core-study'
OUT = ROOT/'results/stem-core-study/gallery'
MODES = ('baseline', 'native-area', 'gain-area')
TITLES = ('Native + 170 + gain 226', 'Core 240 / native area', 'Core 240 / gained area')
TEXTS = ['The quick brown fox jumps over the lazy dog.',
         'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz',
         '0123456789   0358   H K M V W u',
         '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~',
         ': ; ! i j .   : :   ! !   () [] {} <>',
         'minimum un nu uuuu  oeas  VvWwYy  S A Y']


def concentrate(raw, chosen, width):
    """Select stable axis-aligned profiles from originals; reject intersecting runs."""
    assert isinstance(raw, bytes) and isinstance(chosen, bytes) and len(raw) == len(chosen)
    assert width >= 0 and (not raw if width == 0 else len(raw) % width == 0)
    if not raw:
        return {m: chosen for m in MODES}, []
    height = len(raw)//width
    runs = []
    for axis in ('vertical', 'horizontal'):
        across, along = (width, height) if axis == 'vertical' else (height, width)
        def index(a, b):
            return b*width+a if axis == 'vertical' else a*width+b
        for a in range(across-1):
            profiles = []
            for b in range(along):
                pair = (index(a, b), index(a+1, b))
                x, y = (raw[i] for i in pair)
                left = raw[index(a-1, b)] if a else 0
                right = raw[index(a+2, b)] if a+2 < across else 0
                eligible = x > 0 and y > 0 and 192 <= x+y <= 384 and abs(x-y) >= 16 and max(left, right) <= 32
                profiles.append((pair, (x, y)) if eligible else None)
            start = 0
            while start < along:
                if profiles[start] is None:
                    start += 1
                    continue
                end = start+1
                first = profiles[start][1]
                while end < along and profiles[end] is not None and all(
                        abs(a-b) <= 8 for a, b in zip(first, profiles[end][1], strict=True)):
                    end += 1
                if end-start >= 3:
                    runs.append(dict(axis=axis, pairs=[list(profiles[b][0]) for b in range(start, end)]))
                start = end
    counts = Counter(i for run in runs for pair in run['pairs'] for i in pair)
    accepted = [r for r in runs if all(counts[i] == 1 for p in r['pairs'] for i in p)]
    outputs = {m: bytearray(chosen) for m in MODES}
    changed = []
    for run in accepted:
        for pair in run['pairs']:
            core, fringe = sorted(pair, key=lambda i: raw[i], reverse=True)
            if max(chosen[i] for i in pair) >= 230:
                continue
            changes = {}
            for mode, source in (('native-area', raw), ('gain-area', chosen)):
                total = sum(source[i] for i in pair)
                peak = min(240, total-1)
                if peak <= chosen[core]:
                    continue
                outputs[mode][core], outputs[mode][fringe] = peak, total-peak
                changes[mode] = dict(total=total, core=peak, fringe=total-peak)
            if changes:
                changed.append(dict(axis=run['axis'], core=core, fringe=fringe, values=changes))
    outputs = {m: bytes(a) for m, a in outputs.items()}
    selected = {i for pair in changed for i in (pair['core'], pair['fringe'])}
    for mode, data in outputs.items():
        assert all((a > 0) == (b > 0) and (a < 230 or a == b) for a, b in zip(chosen, data, strict=True))
        assert all(a == b for i, (a, b) in enumerate(zip(chosen, data, strict=True)) if i not in selected)
        for pair in changed:
            core, fringe = pair['core'], pair['fringe']
            if mode in pair['values']:
                assert data[core]+data[fringe] == pair['values'][mode]['total']
    return outputs, changed


def self_test():
    reference = json.loads((ROOT/'docs/images/browser-common-ground/inconsolata-u-captures.json').read_text())['conditions'][0]['u']
    raw = bytes.fromhex(reference['raw']['mask']); chosen = bytes.fromhex(reference['chosen'])
    result, pairs = concentrate(raw, chosen, 7)
    expected = u_trials(raw, chosen, 7)
    assert result['native-area'] == expected['native-area'] and result['gain-area'] == expected['gain-area']
    assert len(pairs) == 4
    def transpose(data, w):
        h = len(data)//w
        return bytes(data[y*w+x] for x in range(w) for y in range(h))
    for mode in MODES:
        assert concentrate(transpose(raw, 7), transpose(chosen, 7), 7)[0][mode] == transpose(result[mode], 7)
        flip = lambda a: b''.join(a[i:i+7][::-1] for i in range(0, len(a), 7))
        assert concentrate(flip(raw), flip(chosen), 7)[0][mode] == flip(result[mode])
    for raw, w in [(b'', 0), (bytes([144,124]*2), 2), (bytes([255,124]*4), 2),
                   (bytes([144,124,130]*4), 3), (bytes([150,120,0,0,145,125,0,0,140,130]), 5),
                   (bytes([144,124,0,0,0,0,0,0,144,124,0,0,0,0,0,0,144,124]), 6)]:
        chosen = gain(raw, 226)
        assert all(a == chosen for a in concentrate(raw, chosen, w)[0].values())
    # Ambiguous small squares must stay untouched.
    raw = bytes([100]*9)
    assert not concentrate(raw, gain(raw,226), 3)[1]
    raw = bytes([120,80]*3); chosen = gain(raw,226)
    outputs, pairs = concentrate(raw,chosen,2)
    assert len(pairs)==3 and outputs['native-area']==bytes([199,1]*3)
    assert all(sum(outputs['gain-area'][i:i+2])==sum(chosen[i:i+2]) for i in range(0,6,2))
    assert concentrate(bytes([144,124]*3), bytes([240,124]*3), 2)[1] == []
    raw=bytes([144,124]*3); chosen=gain(raw,226)
    for mode,data in concentrate(raw,chosen,2)[0].items():
        assert concentrate(transpose(raw,2),transpose(chosen,2),3)[0][mode]==transpose(data,2)
    print('PASS selector / exact S28 u / transposition / reflection / exclusions / area and support')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--stock-library', type=Path)
    parser.add_argument('--stock-qt-directory', type=Path)
    parser.add_argument('--label-font', type=Path)
    args = parser.parse_args(); self_test()
    if args.self_test:
        return
    assert all((args.stock_library,args.stock_qt_directory,args.label_font))
    WORK.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    old = OUT/'manifest.json'
    if old.exists():
        previous = json.loads(old.read_text()); assert previous['producer']=='fontreal-stem-core-study'
        for record in previous['images']:
            p=OUT/record['file']; assert p.parent==OUT and sha(p)==record['sha256']; p.unlink()
    assert not list(OUT.glob('*.png'))
    all_faces,_ = inventory(); faces=[]; missing={}
    for family in FAMILIES[:-2]:
        available = {f['style']:f for f in all_faces if f['family']==family}
        assert available, f'Required font family is not installed: {family}'
        missing[family]=[]
        for style in ('Regular','Bold','Italic','Light'):
            actual = 'ExtraLight' if style=='Light' and family=='DejaVu Sans' else style
            if actual not in available:
                missing[family].append(style)
            else:
                faces.append(available[actual])
    assert len({(f['family'],f['style']) for f in faces})==len(faces)
    stock = WORK/'stock-qt'; stock.mkdir(exist_ok=True)
    packages=[]
    for name in ('libqt6core6t64','libqt6gui6','libqt6dbus6','qt6-qpa-plugins'):
        matches=list(args.stock_qt_directory.glob(name+'_*.deb')); assert len(matches)==1
        p=matches[0]; version=subprocess.check_output(['dpkg-deb','-f',str(p),'Version'],text=True).strip()
        assert 'fontreal' not in version
        subprocess.run(['dpkg-deb','-x',str(p),str(stock)],check=True)
        packages.append(dict(file=p.name,version=version,sha256=sha(p)))
    libdir=stock/'usr/lib/x86_64-linux-gnu'
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Gui','freetype2'],text=True))
    probe=WORK/'probe'
    subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/stem_core_probe.cpp'),*flags,'-o',str(probe)],check=True)
    config=WORK/'input.json'; config.write_text(json.dumps(dict(faces=faces,texts=TEXTS)))
    env={k:v for k,v in os.environ.items() if not k.startswith(('FONTREAL_','QT_')) and k not in
         ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','FT2_DEBUG')}
    env.update(LD_LIBRARY_PATH=os.pathsep.join((str(args.stock_library.resolve().parent),str(libdir.resolve()))),
               QT_QPA_PLATFORM='offscreen',QT_FONT_DPI='96',QT_SCALE_FACTOR='1',
               QT_QPA_PLATFORM_PLUGIN_PATH=str((libdir/'qt6/plugins/platforms').resolve()))
    native=WORK/'native'
    with (WORK/'native.log').open('w') as log:
        subprocess.run([str(probe.resolve()),str(config.resolve()),str(native.resolve())],env=env,check=True,stdout=log,stderr=log)
    maps=(native/'maps.txt').read_text(); libraries={}
    for prefix, expected in [('libQt6Gui.so.',libdir),('libQt6Core.so.',libdir),('libfreetype.so.',args.stock_library.resolve().parent)]:
        loaded={Path(line.split()[-1]).resolve() for line in maps.splitlines() if prefix in line}
        assert len(loaded)==1
        p=loaded.pop(); assert p.parent==expected.resolve()
        libraries[prefix]=dict(file=p.name,sha256=sha(p))
    assert libraries['libfreetype.so.']['sha256']==sha(args.stock_library)
    expected={f"{f['id']}-{pt}" for f in faces for pt in (11,12)}
    assert set(json.loads((native/'index.json').read_text()))==expected
    oracle=Oracle(args.stock_library.resolve()); records=[]; images=[]
    heading=ImageFont.truetype(str(args.label_font),20); label=ImageFont.truetype(str(args.label_font),14)

    def save(image,name,crops):
        assert image.width==1440 and image.height<=880
        path=OUT/name; image.save(path)
        with Image.open(path) as saved:
            for x,y,crop in crops:
                assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
        images.append(dict(file=name,sha256=sha(path)))

    try:
        for face in faces:
            for point in (11,12):
                identifier=f"{face['id']}-{point}"; path=native/(identifier+'.json'); case=json.loads(path.read_text())
                assert case['point_size']==point and case['font_id']==face['id'] and case['font_format']==face['format']
                assert sha(Path(face['file']))==face['font_sha256'] and len(case['glyphs'])==95
                glyphs={}; masks={m:{} for m in MODES}; captured=[]
                for g in case['glyphs']:
                    gid=g['glyph']; raw=g['rendered'][0]
                    assert g['rendered'][1]==raw and oracle.raster(g['loaded'])=={k:raw[k] for k in ('width','height','left','top','mask')}
                    assert raw['pixel_mode']==2 and raw['grays']==256
                    original=bytes.fromhex(raw['mask']); baseline=gain(transform(original,raw['width'])[0]['bridge'],226)
                    trials,pairs=concentrate(original,baseline,raw['width'])
                    glyphs[gid]=dict(loaded=g['loaded'],raster=raw)
                    for mode in MODES:masks[mode][gid]=trials[mode]
                    captured.append(dict(glyph=gid,codepoint=g['codepoint'],raw={k:raw[k] for k in ('width','height','left','top','mask')},
                        loaded_sha256=hashlib.sha256(json.dumps(g['loaded'],sort_keys=True).encode()).hexdigest(),
                        masks={m:trials[m].hex() for m in MODES},pairs=pairs,
                        changed={m:sum(a!=b for a,b in zip(baseline,trials[m],strict=True)) for m in MODES}))
                assert len(glyphs)==95 and [r['text'] for r in case['rows']]==TEXTS
                pages=[(False,MODES,TITLES)]
                if face['family']=='Noto Sans':
                    pages.insert(0,(True,('stock','native-area','gain-area'),('Actual stock Qt',TITLES[1],TITLES[2])))
                for stock_page,modes,titles in pages:
                    page=Image.new('RGB',(1440,800),(24,24,24)); d=ImageDraw.Draw(page); crops=[]
                    d.text((14,12),f"{face['family']} / {face['style']} / {point}pt | {'stock Qt control' if stock_page else 'core coverage study'}",font=heading,fill='white')
                    d.text((14,43),'96 DPI / 100%. Native hints, 170 + guarded bridge, gain 226; eligible straight profiles only.',font=label,fill='white')
                    d.text((14,65),'Stock: actual Qt paint and placement. Trials: fixed native outlines, whole-pixel positions, encoded coverage.' if stock_page else
                           'Native-area restores original pair totals. Gained-area retains gained totals. Unselected strokes stay identical.',font=label,fill='white')
                    changes=sum(bool(g['pairs']) for g in captured)
                    absent=', '.join(missing[face['family']]) or 'none'
                    d.text((14,87),f'{changes}/95 glyphs have eligible changed pairs. Unavailable styles: {absent}. Light faces are never synthesized.',font=label,fill='white')
                    for column,mode in enumerate(modes):
                        x=6+column*476; d.text((x+8,118),titles[column],font=heading,fill='white')
                        for palette,dark in enumerate((True,False)):
                            top=150+palette*320; d.rectangle((x,top,x+469,top+309),fill='black' if dark else 'white')
                            d.text((x+8,top+4),'White on black' if dark else 'Black on white',font=label,fill='white' if dark else 'black')
                            for n,row in enumerate(case['rows']):
                                if mode=='stock':
                                    source=native/row['stock_dark' if dark else 'stock_light']
                                    rgb=Image.open(source).convert('RGB')
                                    ink=rgb if dark else ImageOps.invert(rgb)
                                    box=ink.getbbox(); assert box and box[0]>0 and box[1]>0 and box[2]<470 and box[3]<40
                                else:
                                    alpha=compose(row,glyphs,masks[mode],0)
                                    rgb=alpha.convert('RGB') if dark else ImageOps.invert(alpha.convert('RGB'))
                                assert rgb.size==(470,40)
                                y=top+28+n*40; page.paste(rgb,(x,y)); crops.append((x,y,rgb))
                    name=f"{len(images):03}_{slug(face['family'])}_{slug(face['style'])}_{point}pt{'_stock-Qt' if stock_page else ''}.png"
                    save(page,name,crops)
                records.append(dict(id=identifier,font={k:v for k,v in face.items() if k!='file'},point_size=point,native_size=case['native_size'],
                                    capture_sha256=sha(path),glyphs=captured,
                                    layouts=case['rows'],stock_images=[dict(file=r[key],sha256=sha(native/r[key])) for r in case['rows']
                                    for key in ('stock_dark','stock_light') if key in r]))
                print(f"PASS {face['family']} {face['style']} {point}pt",flush=True)
    finally:
        oracle.close()
    assert {r['id'] for r in records}==expected
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    bindings={name:sha(ROOT/'tests'/name) for name in ('stem_core_test.py','stem_core_probe.cpp','freetype_mask_probe.cpp',
              'bridge_case_study_test.py','bridge_coverage_test.py','neighbor_coverage_test.py','inconsolata_gain_test.py',
              'inconsolata_u_test.py','bridge_font_matrix_test.py','browser_stroke_axis_test.py')}
    result=dict(producer='fontreal-stem-core-study',logical_dpi=96,scale=1,texts=TEXTS,styles=['Regular','Bold','Italic','Light'],
                missing_styles=missing,sources=bindings,stock_packages=packages,libraries=libraries,probe_sha256=sha(probe),load_flags=32776,
                qt_platform='offscreen',label_font=dict(file=args.label_font.name,sha256=sha(args.label_font)),
                conditions=records,images=images,limits=['Scientific selector trial, not an installed rendering policy',
                    'Only stable axis-aligned two-pixel runs qualify; short, diagonal, thick and already strong strokes can remain unchanged',
                    'Core concentration changes ink centroids; outline identity does not imply identical perceived geometry',
                    'Native-area preserves only selected native pairs, not whole-glyph original coverage',
                    'Qt uses its own placement and blending; candidate masks use whole-pixel placement and encoded coverage'])
    old.write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS {len(records)} conditions / {len(records)*95} independently rasterized glyphs / {len(images)} complete pages')
    print(OUT)


if __name__=='__main__':
    main()
