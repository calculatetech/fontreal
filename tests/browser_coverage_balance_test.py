#!/usr/bin/env python3
"""Compare opacity controls over retained native half-minimum masks."""
import argparse
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
import importlib.util
import json
import math
import os
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = (ROOT / 'build/freetype-native/coverage-balance').resolve()
OUT = (ROOT / 'results/browser-coverage-balance').resolve()
SOURCE = ROOT / 'results/browser-stroke-width'
spec = importlib.util.spec_from_file_location('width', ROOT / 'tests/browser_stroke_width_test.py')
width = importlib.util.module_from_spec(spec)
spec.loader.exec_module(width)
axis = width.axis
MODES = ('A', 'B', 'C', 'D')
LABELS = ('A: Approved half-minimum', 'B: Lift partial coverage',
          'C: Light glyphs capped at 75%', 'D: Lift + light glyph cap')


def coverage(alpha, mode, weight):
    value = 255 - ((255 - alpha) ** 2 + 127) // 255 if mode in ('B', 'D') else alpha
    return min(value, 191) if mode in ('C', 'D') and weight < 400 else value


def expected(alpha, mode, weight):
    value = Fraction(alpha, 255)
    if mode in ('B', 'D'):
        value = 1 - (1 - value) ** 2
    quantized = math.floor(value * 255 + Fraction(1, 2))
    if mode in ('C', 'D') and weight < 400:
        quantized = min(quantized, 191)
    return quantized


def font_weight(path):
    data = path.read_bytes()
    assert data[:4] == b'\0\1\0\0'
    count = struct.unpack_from('>H', data, 4)[0]
    assert 12 + 16 * count <= len(data)
    for i in range(count):
        tag, checksum, offset, length = struct.unpack_from('>4sIII', data, 12 + 16 * i)
        if tag == b'OS/2':
            assert length >= 6 and offset + length <= len(data)
            weight = struct.unpack_from('>H', data, offset + 4)[0]
            assert 1 <= weight <= 1000
            return weight
    raise AssertionError('Selected static font lacks its weight class')


def measured_profile(glyph, y, interval=None):
    w = glyph['width']
    data = bytes.fromhex(glyph['mask'])
    row = list(data[y * w:(y + 1) * w])
    if interval is None:
        active = [i for i, alpha in enumerate(row) if alpha]
        interval = (active[0], active[-1] + 1) if active else (0, 0)
    profile = row[interval[0]:interval[1]]
    return dict(row=y, x_interval=list(interval), values=profile,
                mean=sum(profile) / len(profile) if profile else None)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    caller_environment = dict(os.environ)
    for directory in (WORK, OUT):
        directory.mkdir(parents=True, exist_ok=True)
    assert WORK.is_relative_to((ROOT / 'build').resolve()) and OUT.is_relative_to((ROOT / 'results').resolve())
    inputs = [SOURCE / name for name in ('all.json', 'words.json', 'probes.json')]
    input_hashes = {p.name: axis.sha(p) for p in inputs}
    report = json.loads(inputs[0].read_text())
    words = json.loads(inputs[1].read_text())
    probes = {tuple(x['key']): x['result'] for x in json.loads(inputs[2].read_text())}
    assert report['runner_sha256'] == axis.sha(ROOT / 'tests/browser_stroke_width_test.py')
    assert report['helper_sha256'] == axis.sha(ROOT / 'tests/freetype_stroke_width.h')
    expected_keys = {(name, size) for name, font in axis.FONTS for size in axis.SIZES}
    keys = [(r['font'], r['size_px']) for r in words]
    assert len(keys) == len(set(keys)) == 36 and set(keys) == expected_keys
    conditions = {(r['font'], r['size_px']): r for r in report['conditions']}
    assert len(conditions) == len(report['conditions']) == 36 and set(conditions) == expected_keys
    weights = {name: font_weight(font) for name, font in axis.FONTS}
    assert tuple(weights.values()) == (400, 700, 400, 700, 300, 400, 300, 700, 400)
    font_hashes = {font.name: axis.sha(font) for name, font in axis.FONTS}

    tables = {(mode, weight): [coverage(a, mode, weight) for a in range(256)]
              for mode in MODES for weight in (300, 399, 400, 700)}
    for (mode, weight), table in tables.items():
        assert table == [expected(a, mode, weight) for a in range(256)]
        assert table[0] == 0 and table == sorted(table)
    assert tables['B', 400][127] == 191 and tables['B', 400][128] == 192
    assert tables['B', 400][255] == 255
    assert tables['C', 300][255] == tables['C', 399][255] == 191
    assert tables['C', 400] == list(range(256))
    palettes = {}
    for dark in (False, True):
        independent = []
        with localcontext() as context:
            context.prec = 36
            for alpha in range(256):
                linear = Decimal(alpha if dark else 255 - alpha) / Decimal(255)
                encoded = linear * Decimal('12.92') if linear <= Decimal('0.0031308') else \
                    Decimal('1.055') * linear ** (Decimal(1) / Decimal('2.4')) - Decimal('0.055')
                independent.append(int((encoded * 255).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
        assert width.blend(dark) == independent
        palettes[dark] = independent

    def treat(glyph, mode, weight):
        original = bytes.fromhex(glyph['mask'])
        actual = bytes(coverage(a, mode, weight) for a in original)
        independent = bytes(expected(a, mode, weight) for a in original)
        assert actual == independent
        result = dict(glyph, mask=actual.hex())
        assert all(result[k] == glyph[k] for k in glyph if k != 'mask')
        assert all(not a or b for a, b in zip(original, actual))
        assert all(b == 0 for a, b in zip(original, actual) if a == 0)
        return result, dict(glyph, mask=independent.hex())

    label = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
    rows, sheets, profiles = [], [], []
    detail_chars = 'Hl35V'
    for size in axis.SIZES:
        source_rows = [next(r for r in words if r['font'] == name and r['size_px'] == size) for name, font in axis.FONTS]
        old_zoom_y = max(58, max(r['bounds'][3] - r['bounds'][1] for r in source_rows) + 24)
        old_row_height = old_zoom_y + max(g['height'] * 4 for r in source_rows
            for mode in width.MODES for char, g in r['glyphs'][mode].items() if char in detail_chars) + 14
        cases = []
        for (name, font), source in zip(axis.FONTS, source_rows):
            assert conditions[name, size]['font_sha256'] == axis.sha(font)
            weight = weights[name]
            source_glyphs = source['glyphs']['half']
            glyphs, independent_glyphs, images = {}, {}, {}
            for mode in MODES:
                glyphs[mode], independent_glyphs[mode] = {}, {}
                for char, glyph in source_glyphs.items():
                    assert glyph == probes[(font.name, size, char, 'half')]['rendered'][0]
                    actual, independent = treat(glyph, mode, weight)
                    glyphs[mode][char], independent_glyphs[mode][char] = actual, independent
                images[mode], placements = axis.compose(axis.TEXT, source['origins_26_6'], glyphs[mode], source['bounds'])
                independently_composed, independent_placements = axis.compose(axis.TEXT, source['origins_26_6'], independent_glyphs[mode], source['bounds'])
                assert images[mode].tobytes() == independently_composed.tobytes()
                assert placements == independent_placements == source['placements']['half']
            assert glyphs['A'] == source_glyphs
            l = source_glyphs['l']
            l_source = measured_profile(l, l['height'] // 2)
            row_profiles = {mode: measured_profile(glyphs[mode]['l'], l_source['row'], l_source['x_interval']) for mode in MODES}
            if weight < 400:
                assert 255 in l_source['values']
                for i, alpha in enumerate(l_source['values']):
                    if alpha == 255:
                        assert row_profiles['C']['values'][i] == row_profiles['D']['values'][i] == 191
            crown_profiles = {}
            for char in '35':
                g = source_glyphs[char]
                y = next(y for y in range(g['height']) if any(bytes.fromhex(g['mask'])[y * g['width']:(y + 1) * g['width']]))
                src = measured_profile(g, y)
                crown_profiles[char] = {mode: measured_profile(glyphs[mode][char], y, src['x_interval']) for mode in MODES}
                if size == 12:
                    assert any(0 < a < 255 for a in src['values'])
                    wanted = [expected(a, 'B', weight) for a in src['values']]
                    assert crown_profiles[char]['B']['values'] == wanted != src['values']
            rows.append(dict(font=name, font_file=font.name, font_sha256=axis.sha(font), size_px=size, weight_class=weight))
            profiles.append(dict(font=name, size_px=size, middle_l=row_profiles, first_nonempty_crowns=crown_profiles))
            cases.append((name, images, glyphs, independent_glyphs))

        zoom_y = max(58, max(im.height for _, ims, _, _ in cases for im in ims.values()) + 24)
        row_height = zoom_y + max(g['height'] * 4 for _, _, gs, _ in cases
            for mode in MODES for char, g in gs[mode].items() if char in detail_chars) + 14
        for dark in (False, True):
            lut = palettes[dark]
            bg, fg = ((0, 255) if dark else (255, 0))
            sheet = Image.new('RGB', (1840, 100 + row_height * len(cases)), (bg,) * 3)
            draw = ImageDraw.Draw(sheet)
            draw.text((12, 10), f'{size:g} device px | same native geometry | native text and exact 4x details | linear blend', font=heading, fill=(fg,) * 3)
            draw.text((12, 34), 'A is the previous third column. Lift affects all partial pixels. Light cap applies before glyph overlap; it is not a stroke-average solver.', font=label, fill=(fg,) * 3)
            previous_name = f'{size:g}px-width-' + ('dark.png' if dark else 'light.png')
            previous = next(s for s in report['sheets'] if s['file'] == previous_name)
            assert axis.sha(SOURCE / previous_name) == previous['sha256']
            with Image.open(SOURCE / previous_name) as approved:
                assert approved.size == (1800, 100 + old_row_height * 9)
                crops = []
                for col, (mode, caption) in enumerate(zip(MODES, LABELS)):
                    x = col * 460
                    draw.text((x + 12, 74), caption, font=heading, fill=(fg,) * 3)
                    for number, (name, images, glyphs, independent_glyphs) in enumerate(cases):
                        y = 100 + number * row_height
                        draw.text((x + 12, y), name, font=label, fill=(fg,) * 3)
                        native = images[mode].point(lut).convert('RGB')
                        assert native.width <= 436 and native.height + 18 < zoom_y
                        if mode == 'A':
                            old_y = 100 + number * old_row_height + 18
                            assert approved.crop((1212, old_y, 1212 + native.width, old_y + native.height)).tobytes() == native.tobytes()
                        sheet.paste(native, (x + 12, y + 18))
                        crops.append(((x + 12, y + 18), native))
                        for i, char in enumerate(detail_chars):
                            # Detail expectations come from rational transforms, not selected output masks.
                            detail = axis.image(independent_glyphs[mode][char]).point(lut).convert('RGB')
                            zoom = detail.resize((detail.width * 4, detail.height * 4), Image.Resampling.NEAREST)
                            assert zoom.width <= 80 and zoom.height + zoom_y < row_height
                            position = (x + 16 + i * 84, y + zoom_y)
                            sheet.paste(axis.image(glyphs[mode][char]).point(lut).convert('RGB').resize(zoom.size, Image.Resampling.NEAREST), position)
                            crops.append((position, zoom))
                filename = f'{size:g}px-balance-' + ('dark.png' if dark else 'light.png')
                sheet.save(OUT / filename)
                with Image.open(OUT / filename) as saved:
                    for (x, y), independent in crops:
                        assert saved.crop((x, y, x + independent.width, y + independent.height)).tobytes() == independent.tobytes()
                sheets.append(dict(file=filename, sha256=axis.sha(OUT / filename), dimensions=list(sheet.size)))
        print(f'PASS {size:g}px: exact approved control, real crown response, weight cap and saved pixels', flush=True)

    # Expose the per-glyph stage: overlapping capped pixels can exceed the cap.
    one = dict(width=1, height=1, left=0, top=1, mask='ff')
    capped, _ = treat(one, 'C', 300)
    overlap, placements = axis.compose('ll', [0, 0], {'l': capped}, (0, -1, 1, 0))
    assert list(overlap.tobytes()) == [239] and len(placements) == 2
    assert coverage(255, 'C', 300) == 191 < overlap.getpixel((0, 0))

    synthetic = []
    for weight in (300, 400):
        for source_profile in ([255], [255, 0], [127], [255, 127], [255, 255], [128, 128]):
            outputs = {}
            for mode in MODES:
                actual = [coverage(a, mode, weight) for a in source_profile]
                assert actual == [expected(a, mode, weight) for a in source_profile]
                outputs[mode] = dict(values=actual, cells=len(actual), mean=sum(actual) / len(actual))
            synthetic.append(dict(weight_class=weight, source=source_profile, outputs=outputs))
    assert synthetic[0]['outputs']['C']['mean'] == 191
    assert synthetic[1]['outputs']['C']['mean'] == 95.5
    for dark in (False, True):
        lut = palettes[dark]
        bg, fg = ((0, 255) if dark else (255, 0))
        sheet = Image.new('RGB', (1840, 90 + len(synthetic) * 70), (bg,) * 3)
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 12), 'Synthetic declared pixel spans | exact 8x coverage profiles | means include every declared cell, including zeros', font=heading, fill=(fg,) * 3)
        crops = []
        for col, (mode, title) in enumerate(zip(MODES, LABELS)):
            draw.text((12 + 460 * col, 54), title, font=heading, fill=(fg,) * 3)
            for row, entry in enumerate(synthetic):
                value = entry['outputs'][mode]
                y = 90 + row * 70
                draw.text((12 + col * 460, y), f"w{entry['weight_class']} {entry['source']} -> {value['values']} mean {value['mean']:g}", font=label, fill=(fg,) * 3)
                mask = Image.frombytes('L', (value['cells'], 4), bytes(value['values']) * 4)
                zoom = mask.point(lut).convert('RGB').resize((value['cells'] * 8, 32), Image.Resampling.NEAREST)
                position = (20 + col * 460, y + 22)
                sheet.paste(zoom, position)
                crops.append((position, zoom))
        filename = 'synthetic-' + ('dark.png' if dark else 'light.png')
        sheet.save(OUT / filename)
        with Image.open(OUT / filename) as saved:
            for (x, y), independent in crops:
                assert saved.crop((x, y, x + independent.width, y + independent.height)).tobytes() == independent.tobytes()
        sheets.append(dict(file=filename, sha256=axis.sha(OUT / filename), dimensions=list(sheet.size)))
    assert {(r['font'], r['size_px']) for r in rows} == expected_keys and len(rows) == 36
    assert {s['file'] for s in sheets} == {f'{size:g}px-balance-{p}.png' for size in axis.SIZES for p in ('light', 'dark')} | {'synthetic-light.png', 'synthetic-dark.png'}
    assert len(sheets) == 10
    assert input_hashes == {p.name: axis.sha(p) for p in inputs}
    assert font_hashes == {font.name: axis.sha(font) for name, font in axis.FONTS}
    assert os.environ == caller_environment
    result = dict(kind='coverage controls over unchanged native geometry, not a stroke-average solver',
        input_sha256=input_hashes, source_runner_sha256=report['runner_sha256'],
        source_helper_sha256=report['helper_sha256'], runner_sha256=axis.sha(Path(__file__)),
        conditions=rows, profiles=profiles, synthetic=synthetic, sheets=sheets,
        modes=dict(zip(MODES, LABELS)), cap_byte=191, light_weight_predicate='weight_class below 400',
        l_profile_interval='Source middle horizontal raster row from first to last nonzero pixel, endpoints shared by all modes',
        crown_profile_interval='First nonempty source raster row, horizontal nonzero extent shared by all modes',
        synthetic_mean_interval='Every explicitly declared horizontal pixel cell, including zero cells',
        overlap=dict(per_glyph=191, two_identical_overlapping_glyphs=239),
        checks=['exact retained third-column native pixels on both palettes', 'all alpha inputs against rational oracle',
                'actual 12px crown lift and independently expected saved detail crops', 'real light-face opacity ceiling and weight eligibility',
                'all sRGB blend values against high-precision Decimal oracle', 'unchanged mask geometry and zero pixels',
                'all occurrences and independently checked alpha composition', 'precomposition cap and explicit overlap counterexample',
                'all 36 conditions and ten saved sheets', 'reopened native and exact detail pixel crops',
                'unchanged source inputs, font files and caller environment'],
        limits=['Lift affects every partial pixel, not only curves', 'Cap applies per light-face glyph before overlap',
                'Measured horizontal raster profiles are not geometric stroke-normal averages',
                'Static weight metadata only, no variable font claim', 'No installation or browser qualification'])
    (OUT / 'all.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 36 conditions and ten faithful sheets; ' + str(OUT), flush=True)


if __name__ == '__main__':
    main()
