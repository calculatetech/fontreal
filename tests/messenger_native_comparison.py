#!/usr/bin/env python3
"""Reproduce Messenger CFF text and show a native-size fitting comparison."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from PIL import Image, ImageChops, ImageDraw, ImageFont
import browser_live_recipe_test as recipe

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/messenger-native-comparison'
OUT = ROOT / 'results/messenger-native-comparison'
TEXT = "That's my new profile. 8352 vW ilI1"
WIDTH = 520
FACES = [
    ('Nimbus Sans Regular', '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf'),
    ('Noto Sans Regular', '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'),
    ('Noto Serif Regular', '/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf'),
    ('Hack Regular', '/usr/share/fonts/truetype/hack/Hack-Regular.ttf'),
    ('Lato Light', '/usr/share/fonts/truetype/lato/Lato-Light.ttf'),
    ('Noto Sans Italic', '/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf'),
    ('Noto Sans Bold Italic', '/usr/share/fonts/truetype/noto/NotoSans-BoldItalic.ttf'),
]
PALETTES = {'light': ((0, 0, 0), (255, 255, 255)),
            'dark': ((255, 255, 255), (0, 0, 0)),
            'teal': ((255, 255, 255), (0, 127, 131))}
SOURCE_MATCHES = {'T': [(10, 10), (157, 10)], 'h': [(20, 10), (167, 10)], 'm': [(55, 12)],
                  'n': [(80, 12)], 'e': [(87, 13), (141, 13)], 'r': [(119, 12)],
                  'o': [(123, 13)], 'f': [(131, 10)], 'i': [(135, 10), (174, 10)],
                  'l': [(139, 10)], 's': [(42, 13)], 'w': [(95, 13)]}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, text=True, capture_output=True, **kwargs)


def clean_env(library=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('FONTREAL_')
           and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'FREETYPE_PROPERTIES', 'FT2_DEBUG', 'QT_SCALE_FACTOR')}
    env.update(QT_QPA_PLATFORM='offscreen', QT_FONT_DPI='96', QT_SCALE_FACTOR='1',
               FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')
    if library:
        env['LD_LIBRARY_PATH'] = str(Path(library).parent)
    return env


def matrix(rows, expected):
    assert len(rows) == len(expected), 'incomplete matrix'
    keys = [r['id'] for r in rows]
    assert len(set(keys)) == len(keys) and set(keys) == set(expected), 'duplicate or missing condition'
    for r in rows:
        assert type(r['point_size']) is int and 8 <= r['point_size'] <= 16, 'not an integer point request'
        label, path = FACES[r['face']]
        assert r['id'] == f"face{r['face']}-{r['point_size']}" and r['font_path'] == path, 'wrong font identity'
        assert r['font_sha256'] == sha(path), 'font changed'


def composite(glyphs, height, identity=bytes(range(256))):
    canvas = bytearray(WIDTH * height)
    for g in glyphs:
        raw = bytes.fromhex(g['mask'])
        assert len(raw) == g['width'] * g['height']
        assert g['x'] >= 0 and g['y'] >= 0 and g['x'] + g['width'] <= WIDTH and g['y'] + g['height'] <= height
        for y in range(g['height']):
            for x in range(g['width']):
                a = identity[raw[y * g['width'] + x]]
                i = (y + g['y']) * WIDTH + x + g['x']
                canvas[i] = a + (canvas[i] * (255 - a) + 127) // 255
    return bytes(canvas)


def encoded(mask, size, foreground, background):
    table = [tuple((fg * a + bg * (255 - a) + 127) // 255 for fg, bg in zip(foreground, background)) for a in range(256)]
    return Image.frombytes('RGB', size, bytes(c for a in mask for c in table[a]))


def private_sources():
    chart = (ROOT / 'tests/point_benchmark_chart.cpp').read_text()
    chart = chart.replace('620', str(WIDTH)).replace('600', str(WIDTH - 20))
    chart = chart.replace('ilI1 minimum 0358 VvWw 0123456789', TEXT)
    chart = chart.replace('double y=8/scale', 'double y=4/scale').replace('double yy=8/scale', 'double yy=4/scale')
    chart = chart.replace('int(std::ceil(y*scale))+8', 'int(std::ceil(y*scale))+4')
    chart = chart.replace('FT_LOAD_FORCE_AUTOHINT|FT_LOAD_TARGET_MONO|FT_LOAD_NO_BITMAP',
                          'FT_Int32(qEnvironmentVariableIntValue("MESSENGER_LOAD_FLAGS"))')
    chart = chart.replace('int v=(a>=cutoff&&a<242)?242:a;', 'int v=a;')
    chart = chart.replace('for(bool dark:{false,true}){QImage image', 'for(int palette:{0,1,2}){bool dark=palette!=0;QImage image')
    chart = chart.replace('image.fill(dark?Qt::black:Qt::white);',
                          'image.fill(palette==2?QColor(0,127,131):(dark?Qt::black:Qt::white));')
    chart = chart.replace('(dark?"-dark.png":"-light.png")', '(palette==2?"-teal.png":(dark?"-dark.png":"-light.png"))')
    # Manual RGB comes from independently reconstructed raw masks in Python.
    start = chart.index('  for(int palette:{0,1,2}){bool dark=palette!=0;QImage image', chart.index('r["glyphs"]=glyphs'))
    end = chart.index('FT_Done_Face(face);', start)
    chart = chart[:start] + '  ' + chart[end:]
    (BUILD / 'chart.cpp').write_text(chart)
    probe = (ROOT / 'tests/freetype_mask_probe.cpp').read_text()
    old = 'const auto index = FT_Get_Char_Index(face, std::strtoul(argv[4], nullptr, 0));'
    new = 'const auto index = qEnvironmentVariableIsSet("MESSENGER_GLYPH_INDEX") ? FT_UInt(std::strtoul(argv[4], nullptr, 0)) : FT_Get_Char_Index(face, std::strtoul(argv[4], nullptr, 0));'
    assert old in probe
    (BUILD / 'probe.cpp').write_text(probe.replace(old, new, 1))
    flags = shlex.split(run(['pkg-config', '--cflags', '--libs', 'Qt6Gui', 'freetype2']).stdout)
    for name in ('chart', 'probe'):
        run(['c++', '-std=c++17', '-O2', '-fPIC', '-include', 'algorithm', BUILD / (name + '.cpp'), *flags, '-o', BUILD / name])


def probe(library, font, size, flags, value, glyph=True, enabled=False, contrast='raw'):
    env = clean_env(library)
    if glyph:
        env['MESSENGER_GLYPH_INDEX'] = '1'
    if enabled:
        env.update(FONTREAL_FT_RENDERING='1', FONTREAL_FT_CONTRAST=contrast)
    target = BUILD / 'probe.json'
    run([BUILD / 'probe', font, size, hex(flags), value, 0, 0, 0, 2, target, 'none', 0], env=env)
    r = json.loads(target.read_text())
    assert r['rendered'][0] == r['rendered'][1], 'repeat raster changed'
    return r


def source_matches(source, stock):
    image = Image.open(source).convert('RGB')
    records = []
    for char, positions in SOURCE_MATCHES.items():
        p = probe(stock, FACES[0][1], 15, 0, ord(char), glyph=False)
        g = p['rendered'][0]
        expected = encoded(bytes.fromhex(g['mask']), (g['width'], g['height']), *PALETTES['teal'])
        for x, y in positions:
            actual = image.crop((x, y, x + g['width'], y + g['height']))
            maximum = max(ImageChops.difference(actual, expected).getextrema()[i][1] for i in range(3))
            assert maximum <= 1, (char, x, y, maximum)
            # The red channel directly records white coverage over zero-red teal.
            assert bytes(actual.getchannel('R').getdata()) == bytes.fromhex(g['mask']), (char, 'raw source mask')
        records.append(dict(character=char, positions=positions, glyph=p['glyph'], raw_mask_sha256=hashlib.sha256(bytes.fromhex(g['mask'])).hexdigest()))
    return records


def panels(rows, columns, source):
    label_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    title_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
    inset = Image.open(source).convert('RGB')
    outputs = []
    for face, (name, _) in enumerate(FACES):
        for palette, (fg, bg) in PALETTES.items():
            selected = [r for r in rows if r['face'] == face]
            header = 69
            height = header + sum(r['height'] + 1 for r in selected) + 8
            image = Image.new('RGB', (64 + WIDTH * 4 + 8, height), bg)
            draw = ImageDraw.Draw(image)
            draw.text((8, 5), name + ' — integer point sizes; raw masks; encoded manual columns', font=title_font, fill=fg)
            inset_x = image.width - inset.width - 8
            image.paste(inset, (inset_x, 3))
            assert image.crop((inset_x, 3, inset_x + inset.width, 3 + inset.height)).tobytes() == inset.tobytes()
            headings = ['Native default (untreated CFF)', 'Mono fitting 75% · raw', 'Mono fitting 50% · raw', 'Actual stock Qt']
            for column, title in enumerate(headings):
                draw.text((64 + column * WIDTH, 47), title, font=label_font, fill=fg)
            y = header
            for row in selected:
                draw.text((8, y + 4), str(row['point_size']) + 'pt', font=label_font, fill=fg)
                for column, mode in enumerate(columns):
                    tile = Image.open(OUT / mode / f"{row['id']}-{palette}.png").convert('RGB')
                    assert tile.size == (WIDTH, row['height'])
                    image.paste(tile, (64 + column * WIDTH, y))
                    assert image.crop((64 + column * WIDTH, y, 64 + (column + 1) * WIDTH, y + row['height'])).tobytes() == tile.tobytes()
                y += row['height'] + 1
            path = OUT / f'face{face}-{palette}.png'
            image.save(path)
            assert Image.open(path).convert('RGB').tobytes() == image.tobytes()
            assert Image.open(path).convert('RGB').crop((inset_x, 3, inset_x + inset.width, 3 + inset.height)).tobytes() == inset.tobytes()
            outputs.append(str(path))
        palettes = [Image.open(OUT / f'face{face}-{p}.png').convert('RGB') for p in PALETTES]
        page = Image.new('RGB', (palettes[0].width, sum(p.height for p in palettes)))
        y = 0
        for panel in palettes:
            page.paste(panel, (0, y)); y += panel.height
        path = OUT / f'face{face}-all-palettes.png'
        page.save(path)
        outputs.append(str(path))
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-image', type=Path, required=True)
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    protected_paths = [ROOT / 'tests/point_benchmark_chart.cpp', ROOT / 'tests/freetype_mask_probe.cpp',
                       ROOT / 'patches/freetype-2.14.2-fontreal.patch', ROOT / 'patches/freetype-nearest-property.patch',
                       Path('/usr/lib/x86_64-linux-gnu/libfreetype.so.6'), *[Path(p) for _, p in FACES]]
    protected = {str(p): sha(p) for p in protected_paths}
    host_before = recipe.masks.protected()
    before_env = dict(os.environ)
    record, trace, nearest = recipe.prepare()
    stock = record['libraries']['stock']['library']; candidate = record['libraries']['candidate']['library']
    private_sources()
    source = OUT / 'reported-source.png'
    shutil.copyfile(args.source_image, source)
    assert sha(source) == sha(args.source_image)
    evidence = source_matches(source, stock)
    # The retained mild diagnostic excludes CFF; the normal raw profile now includes it.
    cff = [probe(lib, FACES[0][1], 15, 0, ord('T'), glyph=False, enabled=on, contrast='mild')
           for lib, on in ((stock, False), (candidate, True))]
    assert cff[0] == cff[1] and cff[0]['font_format'] == 'CFF'
    tt = [probe(lib, FACES[1][1], 21.328125, 0x20028, ord('m'), glyph=False, enabled=on)
          for lib, on in ((stock, False), (nearest, False), (candidate, True))]
    assert tt[0]['loaded']['outline'] != tt[1]['loaded']['outline']
    assert tt[1] == tt[2], 'accepted TrueType nearest path changed'
    initial = [dict(id=f'face{face}-{pt}', face=face, point_size=pt, font_path=path,
                    font_sha256=sha(path), base_px=0, cutoff=128 if face == 4 else 160,
                    logical_dpi=96, scale=1) for face, (_, path) in enumerate(FACES) for pt in range(8, 17)]
    expected = [r['id'] for r in initial]
    matrix(initial, expected)
    for malformed in (initial[:-1], initial + [initial[0]], [*initial[:-1], dict(initial[-1], id=initial[0]['id'])],
                      [*initial[:-1], dict(initial[-1], point_size=16.5)]):
        try: matrix(malformed, expected)
        except AssertionError: pass
        else: raise AssertionError('malformed matrix accepted')
    input_path = BUILD / 'input.json'; input_path.write_text(json.dumps(initial))
    stock_out = OUT / 'qt'; stock_out.mkdir(exist_ok=True)
    run([BUILD / 'chart', 'stock', input_path, stock_out], env=clean_env())
    rows = json.loads((stock_out / 'rows.json').read_text()); matrix(rows, expected)
    assert all(r['font_point_size'] == r['point_size'] for r in rows)
    shaped = BUILD / 'shaped.json'; shaped.write_text(json.dumps(rows))
    columns = ['default', 'mono75', 'mono50', 'qt']
    checks = []; cache = {}; outlines_differ = 0; masks_differ = 0
    for mode, library, flags in [('default', stock, 0), ('mono75', stock, 0x20028), ('mono50', nearest, 0x20028)]:
        target = OUT / mode; target.mkdir(exist_ok=True)
        env = clean_env(library); env['MESSENGER_LOAD_FLAGS'] = str(flags)
        run([BUILD / 'chart', 'candidate', shaped, target], env=env)
        actual = json.loads((target / 'rows.json').read_text()); matrix(actual, expected)
        for row, original in zip(actual, rows, strict=True):
            assert row['runs'] == original['runs'] and row['base_px'] == original['base_px']
            assert len(row['runs']) == len(row['glyphs'])
            for occurrence, (run_glyph, g) in enumerate(zip(row['runs'], row['glyphs'], strict=True)):
                key = (library, row['font_path'], row['base_px'], flags, g['glyph'])
                if key not in cache:
                    cache[key] = probe(library, row['font_path'], row['base_px'], flags, g['glyph'])
                independently = cache[key]
                raw = independently['rendered'][0]
                assert g['glyph'] == run_glyph['glyph'] == independently['glyph']
                assert all(g[k] == raw[k] for k in ('width', 'height', 'left', 'top', 'mask'))
                assert g['loaded']['outline'] == independently['loaded']['outline'] and g['loaded']['contours'] == independently['loaded']['contours']
                assert g['x'] == math.floor(run_glyph['x']) + raw['left'] and g['y'] == math.floor(run_glyph['y'] + .5) - raw['top']
            mask = composite(row['glyphs'], row['height'])
            assert mask == (target / f"{row['id']}-mask.bin").read_bytes()
            assert hashlib.sha256(mask).hexdigest() == row['composed_mask_sha256']
            for palette, colors in PALETTES.items():
                image = encoded(mask, (WIDTH, row['height']), *colors)
                path = target / f"{row['id']}-{palette}.png"; image.save(path)
                assert Image.open(path).convert('RGB').tobytes() == image.tobytes()
            checks.append(dict(mode=mode, id=row['id'], occurrences=len(row['glyphs']), mask_sha256=hashlib.sha256(mask).hexdigest()))
    # Controlled overlap proves transfer is applied per occurrence before composition.
    overlap = [dict(x=0, y=0, width=1, height=1, mask='80')] * 2
    assert composite(overlap, 1)[0] == 192
    nonlinear = bytes((a * a + 127) // 255 for a in range(256))
    assert composite(overlap, 1, nonlinear)[0] != nonlinear[composite(overlap, 1)[0]]
    for row in rows:
        a = json.loads((OUT / 'mono75/rows.json').read_text())
        b = json.loads((OUT / 'mono50/rows.json').read_text())
        x = next(r for r in a if r['id'] == row['id']); y = next(r for r in b if r['id'] == row['id'])
        outlines_differ += sum(g['loaded'] != h['loaded'] for g, h in zip(x['glyphs'], y['glyphs']))
        masks_differ += sum(g['mask'] != h['mask'] for g, h in zip(x['glyphs'], y['glyphs']))
    exported = panels(rows, columns, source)
    assert before_env == dict(os.environ) and protected == {str(p): sha(p) for p in protected_paths}
    assert host_before == recipe.masks.protected()
    report = dict(schema=1, passed=True, source_image=str(args.source_image), source_sha256=sha(source),
                  css_family='Helvetica, Arial, sans-serif', reproduced_glyphs=evidence,
                  resolved_source_size=15, fonts=FACES, requested_points=list(range(8, 17)), palettes=PALETTES,
                  conditions=len(rows), manual_conditions=len(checks), occurrence_checks=sum(r['occurrences'] for r in checks),
                  independently_loaded_glyphs=len(cache), mono50_changed_outlines=outlines_differ,
                  mono50_changed_masks=masks_differ, libraries={k:dict(path=str(v),sha256=sha(v)) for k,v in
                  [('stock',stock),('nearest',nearest),('candidate',candidate)]}, protected=protected,
                  host_protected=host_before, checker_sha256=sha(__file__),
                  checks=checks, panels=exported, production_eligibility='raw includes CFF; retained mild diagnostic excludes CFF', display='pending')
    (OUT / 'comparison.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:report[k] for k in ('passed','conditions','manual_conditions','occurrence_checks','independently_loaded_glyphs','mono50_changed_outlines','mono50_changed_masks')}), flush=True)


if __name__ == '__main__':
    main()
