#!/usr/bin/env python3
"""Build isolated native width controls and export faithful component samples."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = (ROOT / 'build/freetype-native/stroke-width').resolve()
OUT = (ROOT / 'results/browser-stroke-width').resolve()
HELPER = ROOT / 'tests/freetype_stroke_width.h'
spec = importlib.util.spec_from_file_location('axis', ROOT / 'tests/browser_stroke_axis_test.py')
axis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(axis)
MODES = ('F', 'solid', 'half')
LABELS = ('F: previous reference', 'Round widths / minimum 1px', 'Round widths / thin minimum 0.5px')
SELECTOR = 'FONTREAL_TEST_STROKE_WIDTH'
HOOK = r'''
    {
      const char* profile = getenv( "FONTREAL_TEST_STROKE_WIDTH" );
      if ( profile && ( !strcmp( profile, "solid" ) ||
                        !strcmp( profile, "half" ) ) )
      {
        FT_Pos fitted = fontreal_test_stroke_width( width,
                                                   !strcmp( profile, "half" ) );
        fprintf( stderr, "FONTREAL_WIDTH %d %ld %ld\n",
                 (int)dim, (long)width, (long)fitted );
        return fitted;
      }
    }

'''


def expected(width, mode):
    if not width:
        return 0
    magnitude = abs(width)
    pixels = .5 if mode == 'half' and magnitude < 32 else max(1, math.floor(magnitude / 64 + .5))
    return int(pixels * 64) * (-1 if width < 0 else 1)


def blend(dark):
    values = []
    for alpha in range(256):
        value = alpha / 255 if dark else 1 - alpha / 255
        encoded = 12.92 * value if value <= .0031308 else 1.055 * value ** (1 / 2.4) - .055
        values.append(max(0, min(255, math.floor(encoded * 255 + .5))))
    assert values[0] == (0 if dark else 255) and values[255] == (255 if dark else 0)
    return values


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    caller_environment = dict(os.environ)
    for directory in (WORK, OUT, WORK / 'tmp', WORK / 'cache'):
        directory.mkdir(parents=True, exist_ok=True)
    assert WORK.is_relative_to((ROOT / 'build').resolve()) and OUT.is_relative_to((ROOT / 'results').resolve())
    env = {k: v for k, v in os.environ.items() if not k.startswith('FONTREAL_')}
    env.update(TMPDIR=str(WORK / 'tmp'), XDG_CACHE_HOME=str(WORK / 'cache'),
               QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1',
               FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')

    def run(args, **kwargs):
        return subprocess.run(list(map(str, args)), env=kwargs.pop('env', env),
                              text=True, capture_output=True, check=True, timeout=240, **kwargs)

    record_path = Path(run(['python3', ROOT / 'tools/build-freetype.py']).stdout.splitlines()[-1])
    record = json.loads(record_path.read_text())
    stock = Path(record['libraries']['stock']['library'])
    assert axis.sha(stock) == record['libraries']['stock']['sha256']
    native_source = record_path.parent / 'stock-source/src/autofit/aflatin.c'
    native_hash = axis.sha(native_source)
    if not (ROOT / 'results/browser-stroke-axis/all.json').exists():
        run(['python3', ROOT / 'tests/browser_stroke_axis_test.py'])
    old_report = json.loads((ROOT / 'results/browser-stroke-axis/all.json').read_text())
    assert old_report['library_sha256'] == axis.sha(stock)
    assert old_report['probe_source_sha256'] == axis.sha(ROOT / 'tests/freetype_mask_probe.cpp')
    old_words = json.loads((ROOT / 'results/browser-stroke-axis/words.json').read_text())
    old_probes = {tuple(x['key']): x['result'] for x in json.loads((ROOT / 'results/browser-stroke-axis/probes.json').read_text())}
    headers = record_path.parent / 'headers/usr/include/freetype2'
    recipe = dict(stock_source_sha256=native_hash, helper_sha256=axis.sha(HELPER), hook=HOOK, version=1)
    recipe_hash = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()
    build_root = WORK / recipe_hash[:20]
    build_record = build_root / 'build.json'
    if build_record.exists():
        built = json.loads(build_record.read_text())
        library = Path(built['library'])
        assert built['recipe'] == recipe and axis.sha(library) == built['sha256']
    else:
        source, build = build_root / 'source', build_root / 'build'
        build.mkdir(parents=True)
        shutil.copytree(record_path.parent / 'stock-source', source, symlinks=True)
        target = source / 'src/autofit/aflatin.c'
        contents = target.read_text()
        include = '#include "afadjust.h"'
        gate = '    if ( !AF_LATIN_HINTS_DO_STEM_ADJUST( hints ) ||'
        assert contents.count(include) == contents.count(gate) == 1
        contents = contents.replace(include, include + '\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include "fontreal_stroke_width.h"')
        target.write_text(contents.replace(gate, HOOK + gate))
        shutil.copyfile(HELPER, source / 'src/autofit/fontreal_stroke_width.h')
        build_env = dict(env, CC='cc', CFLAGS='-O2',
                         PKG_CONFIG_PATH=str(record_path.parent / 'headers/usr/lib/x86_64-linux-gnu/pkgconfig'))
        configured = run([source / 'configure', '--prefix=' + str(build_root / 'unused-install'),
                          '--with-harfbuzz=dynamic'], cwd=build, env=build_env)
        (build_root / 'configure.log').write_text(configured.stdout + configured.stderr)
        for feature in ('external zlib: yes', 'bzip2:         yes', 'libpng:        yes',
                        'harfbuzz:      yes (dynamic)', 'brotli:        yes', 'pthread:       yes'):
            assert feature in configured.stdout, feature
        compiled = run(['make', '-j' + str(min(12, os.cpu_count() or 1))], cwd=build, env=build_env)
        (build_root / 'compile.log').write_text(compiled.stdout + compiled.stderr)
        library = (build / '.libs/libfreetype.so.6').resolve()
        built = dict(recipe=recipe, library=str(library), sha256=axis.sha(library))
        build_record.write_text(json.dumps(built, indent=2) + '\n')
    exports = [{tuple(line.split()[1:]) for line in run(['nm', '-D', '--defined-only', lib]).stdout.splitlines()}
               for lib in (stock, library)]
    assert exports[0] == exports[1]

    # This numeric table exercises the exact helper included in the private library.
    unit = WORK / 'width-check.c'
    unit.write_text('''#include <assert.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include "freetype_stroke_width.h"
int main(void) {
  long table[][3] = {{0,0,0},{1,64,32},{31,64,32},{32,64,64},
    {63,64,64},{64,64,64},{89,64,64},{90,64,64},{95,64,64},
    {96,128,128},{97,128,128},{159,128,128},{160,192,192}};
  for (unsigned i=0; i<sizeof(table)/sizeof(table[0]); ++i)
    for (int half=0; half<2; ++half)
      for (int sign=-1; sign<=1; sign+=2)
        assert(fontreal_test_stroke_width(sign*table[i][0], half)==sign*table[i][half+1]);
  return 0;
}
''')
    run(['cc', '-std=c99', '-I' + str(headers), '-I' + str(HELPER.parent), unit, '-o', WORK / 'width-check'])
    run([WORK / 'width-check'])
    flags = shlex.split(run(['pkg-config', '--cflags', '--libs', 'Qt6Core']).stdout)
    probe_path = WORK / 'probe'
    run(['c++', '-std=c++17', '-fPIC', ROOT / 'tests/freetype_mask_probe.cpp',
         '-I' + str(headers), '-L' + str(library.parent), '-lfreetype', *flags, '-o', probe_path])
    probe_env = dict(env, LD_LIBRARY_PATH=str(library.parent))
    oracle = axis.Oracle(stock)
    cache, decisions, rows, raw_words, sheets = {}, [], [], [], []

    def probe(font, size, char, mode):
        key = (font.name, size, char, mode)
        if key not in cache:
            scoped = dict(probe_env)
            if mode != 'off':
                scoped[SELECTOR] = mode
            destination = WORK / 'probe.json'
            result = run([probe_path, font, size, '0x20028', ord(char), 0, 0, 0, 2,
                          destination, 'none', 0], env=scoped)
            value = json.loads(destination.read_text())
            calls = []
            for line in result.stderr.splitlines():
                assert line.startswith('FONTREAL_WIDTH '), line
                dim, original, fitted = map(int, line.split()[1:])
                assert mode in ('solid', 'half') and dim in (0, 1)
                assert fitted == expected(original, mode), (key, line)
                calls.append([dim, original, fitted])
            if mode == 'off':
                assert not calls and value == old_probes[(font.name, size, char, 'A', 0, 0)]
            assert value['rendered'][0] == value['rendered'][1]
            assert axis.bitmap(value['rendered'][0]) == oracle.raster(value['loaded'])
            source_outline = old_probes[(font.name, size, char, 'A', 0, 0)]['loaded']
            assert value['loaded']['contours'] == source_outline['contours']
            assert [p[2] for p in value['loaded']['outline']] == [p[2] for p in source_outline['outline']]
            cache[key] = value
            decisions.append(dict(key=list(key), calls=calls))
        return cache[key]

    label = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)

    def save_sheet(filename, cases, title, glyph_order='Hl35V', zoom_factor=4):
        zoom_y = max(58, max(im.height for _, images, _ in cases for im in images.values()) + 24)
        row_height = zoom_y + max(g['height'] * zoom_factor for _, _, glyphs in cases
                                 for mode in MODES for c, g in glyphs[mode].items() if c in glyph_order) + 14
        for dark in (False, True):
            lut = blend(dark)
            bg, fg = ((0, 255) if dark else (255, 0))
            sheet = Image.new('RGB', (1800, 100 + row_height * len(cases)), (bg,) * 3)
            draw = ImageDraw.Draw(sheet)
            draw.text((12, 10), title + ' | linear blend | native text and exact 4x details', font=heading, fill=(fg,) * 3)
            draw.text((12, 34), 'Thin means a detected width below 0.5px. Half coverage is opacity, not screen brightness. Native italic X bypass retained.', font=label, fill=(fg,) * 3)
            crops = []
            for col, (mode, caption) in enumerate(zip(MODES, LABELS)):
                x = col * 600
                draw.text((x + 12, 74), caption, font=heading, fill=(fg,) * 3)
                for number, (name, images, glyphs) in enumerate(cases):
                    y = 100 + number * row_height
                    draw.text((x + 12, y), name, font=label, fill=(fg,) * 3)
                    native = images[mode].point(lut).convert('RGB')
                    assert native.width < 576 and native.height + 18 < zoom_y
                    sheet.paste(native, (x + 12, y + 18))
                    crops.append(((x + 12, y + 18), native))
                    for i, char in enumerate(glyph_order):
                        detail = axis.image(glyphs[mode][char]).point(lut).convert('RGB')
                        zoom = detail.resize((detail.width * zoom_factor, detail.height * zoom_factor), Image.Resampling.NEAREST)
                        assert zoom.width < 100 and zoom.height + zoom_y < row_height
                        position = (x + 20 + i * 108, y + zoom_y)
                        sheet.paste(zoom, position)
                        crops.append((position, zoom))
            name = filename + ('-dark.png' if dark else '-light.png')
            sheet.save(OUT / name)
            with Image.open(OUT / name) as saved:
                for (x, y), image in crops:
                    assert saved.crop((x, y, x + image.width, y + image.height)).tobytes() == image.tobytes()
            sheets.append(dict(file=name, sha256=axis.sha(OUT / name), dimensions=list(sheet.size)))

    try:
        for size in axis.SIZES:
            cases = []
            for name, font in axis.FONTS:
                old = next(r for r in old_words if r['font'] == name and r['size_px'] == size and r['text'] == axis.TEXT)
                assert old['font_sha256'] == axis.sha(font)
                glyphs = {mode: {} for mode in MODES}
                for char in sorted(set(axis.TEXT) | {'g'}):
                    probe(font, size, char, 'off')
                    glyphs['F'][char] = old_probes[(font.name, size, char, 'F', 0, 0)]['rendered'][0]
                    assert axis.bitmap(glyphs['F'][char]) == old['glyphs']['F'][char]
                    for mode in ('solid', 'half'):
                        value = probe(font, size, char, mode)
                        glyphs[mode][char] = value['rendered'][0]
                for mode in ('solid', 'half', 'off'):
                    for char in set(axis.TEXT):
                        assert probe(font, size, char, mode)['next'] == probe(font, size, 'g', mode)['rendered'][0]
                boxes = [old['bounds']]
                for mode in MODES:
                    for char, origin in zip(axis.TEXT, old['origins_26_6']):
                        g = glyphs[mode][char]
                        x, y = origin // 64 + g['left'], -g['top']
                        boxes.append((x, y, x + g['width'], y + g['height']))
                bounds = (min(b[0] for b in boxes) - 2, min(b[1] for b in boxes) - 2,
                          max(b[2] for b in boxes) + 2, max(b[3] for b in boxes) + 2)
                images, placements = {}, {}
                for mode in MODES:
                    images[mode], placements[mode] = axis.compose(axis.TEXT, old['origins_26_6'], glyphs[mode], bounds)
                rows.append(dict(font=name, font_file=font.name, font_sha256=axis.sha(font), size_px=size,
                    profiles={mode: list(bytes.fromhex(glyphs[mode]['l']['mask'])[
                        (glyphs[mode]['l']['height'] // 2) * glyphs[mode]['l']['width']:
                        (glyphs[mode]['l']['height'] // 2 + 1) * glyphs[mode]['l']['width']]) for mode in MODES}))
                raw_words.append(dict(font=name, size_px=size, origins_26_6=old['origins_26_6'], bounds=bounds,
                                      placements=placements, glyphs=glyphs))
                cases.append((name, images, glyphs))
            save_sheet(f'{size:g}px-width', cases, f'{size:g} device px | experimental linked-stem widths')
            print(f'PASS {size:g}px: nine faces, native decisions, independent rasters, lifecycle and saved pixels', flush=True)

        # Controlled straight bands separate the arithmetic from font stem detection.
        numerical = []
        for width in (0, 16, 31, 32, 90, 95, 96, 97, 154, 160, 180):
            values = {}
            for mode in ('raw', 'solid', 'half'):
                fitted = width if mode == 'raw' else expected(width, mode)
                # Half widths stay inside one pixel. Whole widths use pixel edges.
                left = 16 if fitted == 32 else 0
                outline = dict(outline=[[left, 0, 1], [left + fitted, 0, 1],
                    [left + fitted, 7 * 64, 1], [left, 7 * 64, 1]], contours=[3])
                if not fitted:
                    outline = dict(outline=[], contours=[])
                mask = oracle.raster(outline)
                profile = list(bytes.fromhex(mask['mask'])[:mask['width']])
                if mode != 'raw' and width:
                    # This winding quantizes exactly half coverage to 127.
                    assert profile == ([127] if fitted == 32 else [255] * (fitted // 64))
                if not width:
                    assert not mask['mask']
                values[mode] = dict(width_26_6=fitted, mask=mask, profile=profile)
            numerical.append(dict(source_width_26_6=width, values=values))
        assert expected(90, 'solid') == 64 and expected(180, 'solid') == 192
        for dark in (False, True):
            lut = blend(dark)
            bg, fg = ((0, 255) if dark else (255, 0))
            sheet = Image.new('RGB', (1200, 84 + 74 * len(numerical)), (bg,) * 3)
            draw = ImageDraw.Draw(sheet)
            draw.text((12, 12), 'Synthetic straight bars | exact 8x pixels | independent of font detection | linear blend', font=heading, fill=(fg,) * 3)
            for col, title in enumerate(('Original coverage', 'Round / minimum 1px', 'Round / thin minimum 0.5px')):
                draw.text((12 + col * 400, 48), title, font=heading, fill=(fg,) * 3)
            crops = []
            for row, item in enumerate(numerical):
                y = 84 + row * 74
                for col, mode in enumerate(('raw', 'solid', 'half')):
                    value = item['values'][mode]
                    draw.text((12 + col * 400, y), f"{item['source_width_26_6']/64:g}px -> {value['width_26_6']/64:g}px | coverage {value['profile']}", font=label, fill=(fg,) * 3)
                    mask = value['mask']
                    if mask['width']:
                        zoom = axis.image(mask).point(lut).convert('RGB').resize((mask['width'] * 8, mask['height'] * 8), Image.Resampling.NEAREST)
                        position = (20 + col * 400, y + 16)
                        sheet.paste(zoom, position)
                        crops.append((position, zoom))
            filename = 'synthetic-' + ('dark.png' if dark else 'light.png')
            sheet.save(OUT / filename)
            with Image.open(OUT / filename) as saved:
                for (x, y), image in crops:
                    assert saved.crop((x, y, x + image.width, y + image.height)).tobytes() == image.tobytes()
            sheets.append(dict(file=filename, sha256=axis.sha(OUT / filename), dimensions=list(sheet.size)))
        keys = [(x['font'], x['size_px']) for x in rows]
        assert len(keys) == len(set(keys)) == 36 and set(keys) == {(n, s) for n, _ in axis.FONTS for s in axis.SIZES}
        assert {x['file'] for x in sheets} == {f'{s:g}px-width-{p}.png' for s in axis.SIZES for p in ('light', 'dark')} | {'synthetic-light.png', 'synthetic-dark.png'}
        for name, font in axis.FONTS:
            for mode in ('solid', 'half'):
                assert any(d['calls'] for d in decisions if d['key'][0] == font.name and d['key'][3] == mode)
        assert any(abs(call[1]) < 32 and call[1] and abs(call[2]) == 32
                   for d in decisions if d['key'][3] == 'half' for call in d['calls'])
        assert axis.sha(stock) == record['libraries']['stock']['sha256'] and axis.sha(native_source) == native_hash
        assert os.environ == caller_environment
        report = dict(kind='test-only linked-stem experiment; no browser or universal snapping claim',
            source_version=record['spec']['source'], stock_library_sha256=axis.sha(stock),
            experiment_library_sha256=axis.sha(library), native_source_sha256=native_hash,
            helper_sha256=axis.sha(HELPER), runner_sha256=axis.sha(Path(__file__)),
            reference_report_sha256=axis.sha(ROOT / 'results/browser-stroke-axis/all.json'),
            modes=dict(F='retained exact prior F masks', solid='nearest width, half ties up, minimum one pixel',
                       half='as solid, but positive widths below half a pixel become half a pixel'),
            conditions=rows, sheets=sheets, synthetic=numerical,
            coverage_128_encoded_pixels={p: blend(p == 'dark')[128] for p in ('light', 'dark')},
            checks=['same C helper as native library, independent threshold table',
                    'every actual native width decision matches declared formula',
                    'profile-off equals retained stock probe results', 'independent native raster of loaded outlines',
                    'repeated render and next-glyph identity', 'exact F masks and shared origins',
                    'all occurrences, complete ink bounds and independent alpha composition',
                    'all 36 condition and 10 sheet identities', 'saved native and enlarged pixel crops',
                    'unchanged stock source, stock library and caller environment'],
            limits=['Native edge placement, blue zones, unlinked interpolation and italic X bypass remain active',
                    'Half-pixel width does not promise exactly 128 coverage throughout real curves',
                    'Coverage is opacity, not encoded brightness', 'No installation or browser/profile writes'])
        (OUT / 'all.json').write_text(json.dumps(report, indent=2) + '\n')
        (OUT / 'probes.json').write_text(json.dumps([dict(key=list(k), result=v) for k, v in cache.items()]) + '\n')
        (OUT / 'decisions.json').write_text(json.dumps(decisions) + '\n')
        (OUT / 'words.json').write_text(json.dumps(raw_words) + '\n')
        for path in (WORK / 'probe.json', unit, WORK / 'width-check'):
            path.unlink()
        print('PASS: 36 conditions, 10 sheets, thin and full controls; ' + str(OUT), flush=True)
    finally:
        oracle.close()


if __name__ == '__main__':
    main()
