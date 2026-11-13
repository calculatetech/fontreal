#!/usr/bin/env python3
"""Compare retained native stroke minima without post-raster opacity filters."""
import argparse
from decimal import Decimal, ROUND_HALF_UP, localcontext
import importlib.util
import json
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
MODES = {'A': 'half', 'B': 'solid'}
LABELS = {'A': 'A: Previous 0.5px minimum', 'B': 'B: One-pixel minimum / native gray edges'}


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


def measured_profile(glyph, index, vertical=False):
    w, h = glyph['width'], glyph['height']
    data = bytes.fromhex(glyph['mask'])
    values = [data[y * w + index] for y in range(h)] if vertical else list(data[index * w:(index + 1) * w])
    active = [i for i, alpha in enumerate(values) if alpha]
    interval = [active[0], active[-1] + 1] if active else [0, 0]
    profile = values[interval[0]:interval[1]]
    offset = -glyph['top'] if vertical else glyph['left']
    return dict(axis='vertical' if vertical else 'horizontal', index=index, local_interval=interval,
                global_fixed=index + glyph['left'] if vertical else index - glyph['top'],
                global_interval=[offset + value for value in interval],
                values=profile, mean=sum(profile) / len(profile) if profile else None)


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

    label = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    heading = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
    rows, sheets, profiles = [], [], []
    detail_chars = 'Hl358V'
    for size in axis.SIZES:
        source_rows = [next(r for r in words if r['font'] == name and r['size_px'] == size) for name, font in axis.FONTS]
        old_zoom_y = max(58, max(r['bounds'][3] - r['bounds'][1] for r in source_rows) + 24)
        # The retained source PNG layout predates the new 8 detail.
        old_row_height = old_zoom_y + max(g['height'] * 4 for r in source_rows
            for mode in width.MODES for char, g in r['glyphs'][mode].items() if char in 'Hl35V') + 14
        cases = []
        for (name, font), source in zip(axis.FONTS, source_rows):
            assert conditions[name, size]['font_sha256'] == axis.sha(font)
            glyphs, images, independent_glyphs = {}, {}, {}
            row_profiles, crossbars, crowns = {}, {}, {}
            for mode, native_mode in MODES.items():
                glyphs[mode] = source['glyphs'][native_mode]
                independent_glyphs[mode] = {}
                for char, glyph in glyphs[mode].items():
                    provider = probes[(font.name, size, char, native_mode)]['rendered'][0]
                    assert glyph == provider
                    independent_glyphs[mode][char] = provider
                images[mode], placements = axis.compose(axis.TEXT, source['origins_26_6'], glyphs[mode], source['bounds'])
                independent, expected_placements = axis.compose(axis.TEXT, source['origins_26_6'], independent_glyphs[mode], source['bounds'])
                assert images[mode].tobytes() == independent.tobytes()
                assert placements == expected_placements == source['placements'][native_mode]
                l, h = glyphs[mode]['l'], glyphs[mode]['H']
                row_profiles[mode] = measured_profile(l, l['height'] // 2)
                crossbars[mode] = measured_profile(h, h['width'] // 2, vertical=True)
                crowns[mode] = {}
                for char in '358':
                    g = glyphs[mode][char]
                    data = bytes.fromhex(g['mask'])
                    y = next(y for y in range(g['height']) if any(data[y * g['width']:(y + 1) * g['width']]))
                    crowns[mode][char] = measured_profile(g, y)
                    assert crowns[mode][char]['values']
                assert any(0 < a < 255 for a in bytes.fromhex(glyphs[mode]['8']['mask']))
            if size == 12 and name in ('Lato Light', 'Lato Regular'):
                assert crossbars['A']['values'] == ([128] if name == 'Lato Light' else [255])
                assert crossbars['B']['values'] == [255]
                assert row_profiles['A']['values'] == row_profiles['B']['values'] == [255]
            if size == 12 and name == 'Lato Light':
                assert crowns['A']['8']['values'] == [72, 167, 129, 162, 58]
                assert crowns['B']['8']['values'] == [72, 212, 246, 205, 58]
                assert max(crowns['A']['3']['values']) == 151 and max(crowns['B']['3']['values']) == 244
            rows.append(dict(font=name, font_file=font.name, font_sha256=axis.sha(font), size_px=size, weight_class=weights[name]))
            profiles.append(dict(font=name, size_px=size, middle_l=row_profiles,
                                 central_H_column=crossbars, first_nonempty_crowns=crowns))
            cases.append((name, images, glyphs, independent_glyphs))

        zoom_y = max(58, max(im.height for _, ims, _, _ in cases for im in ims.values()) + 24)
        row_height = zoom_y + max(g['height'] * 4 for _, _, gs, _ in cases
            for mode in MODES for char, g in gs[mode].items() if char in detail_chars) + 14
        for dark in (False, True):
            lut = palettes[dark]
            bg, fg = ((0, 255) if dark else (255, 0))
            sheet = Image.new('RGB', (1200, 100 + row_height * len(cases)), (bg,) * 3)
            draw = ImageDraw.Draw(sheet)
            draw.text((12, 10), f'{size:g} device px | native text | H l 3 5 8 V at exact 4x | linear blend', font=heading, fill=(fg,) * 3)
            draw.text((12, 34), 'Native fitted-stroke minima. No opacity lift, light-face dimming, or global edge floor. Crown response can differ by font.', font=label, fill=(fg,) * 3)
            previous_name = f'{size:g}px-width-' + ('dark.png' if dark else 'light.png')
            previous = next(s for s in report['sheets'] if s['file'] == previous_name)
            assert axis.sha(SOURCE / previous_name) == previous['sha256']
            with Image.open(SOURCE / previous_name) as approved:
                assert approved.size == (1800, 100 + old_row_height * 9)
                crops = []
                for col, (mode, caption) in enumerate(LABELS.items()):
                    x = col * 600
                    draw.text((x + 12, 74), caption, font=heading, fill=(fg,) * 3)
                    for number, (name, images, glyphs, independent_glyphs) in enumerate(cases):
                        y = 100 + number * row_height
                        draw.text((x + 12, y), name, font=label, fill=(fg,) * 3)
                        native = images[mode].point(lut).convert('RGB')
                        assert native.width <= 576 and native.height + 18 < zoom_y
                        old_y = 100 + number * old_row_height + 18
                        old_x = 1212 if mode == 'A' else 612
                        assert approved.crop((old_x, old_y, old_x + native.width, old_y + native.height)).tobytes() == native.tobytes()
                        sheet.paste(native, (x + 12, y + 18))
                        crops.append(((x + 12, y + 18), native))
                        for i, char in enumerate(detail_chars):
                            detail = axis.image(independent_glyphs[mode][char]).point(lut).convert('RGB')
                            zoom = detail.resize((detail.width * 4, detail.height * 4), Image.Resampling.NEAREST)
                            assert zoom.width <= 80 and zoom.height + zoom_y < row_height
                            position = (x + 16 + i * 84, y + zoom_y)
                            assert position[0] + zoom.width <= x + 600
                            sheet.paste(axis.image(glyphs[mode][char]).point(lut).convert('RGB').resize(zoom.size, Image.Resampling.NEAREST), position)
                            crops.append((position, zoom))
                filename = f'{size:g}px-balance-' + ('dark.png' if dark else 'light.png')
                sheet.save(OUT / filename)
                with Image.open(OUT / filename) as saved:
                    for (x, y), independent in crops:
                        assert saved.crop((x, y, x + independent.width, y + independent.height)).tobytes() == independent.tobytes()
                sheets.append(dict(file=filename, sha256=axis.sha(OUT / filename), dimensions=list(sheet.size)))
        print(f'PASS {size:g}px: both exact native controls, full cores, native 8 edges and saved pixels', flush=True)

    synthetic = []
    for entry in report['synthetic']:
        original = entry['source_width_26_6']
        values = {}
        for mode, native_mode in MODES.items():
            value = entry['values'][native_mode]
            fitted = 0 if original == 0 else (32 if native_mode == 'half' and original < 32 else max(1, (original + 32) // 64) * 64)
            assert value['width_26_6'] == fitted
            desired = [] if fitted == 0 else ([127] if fitted == 32 else [255] * (fitted // 64))
            assert value['profile'] == desired
            mask = value['mask']
            assert bytes.fromhex(mask['mask']) == bytes(desired) * mask['height']
            values[mode] = value
        synthetic.append(dict(source_width_26_6=original, values=values))
    assert next(s for s in synthetic if s['source_width_26_6'] == 31)['values']['A']['width_26_6'] == 32
    assert next(s for s in synthetic if s['source_width_26_6'] == 31)['values']['B']['width_26_6'] == 64
    assert next(s for s in synthetic if s['source_width_26_6'] == 32)['values']['A']['width_26_6'] == 64
    for original, fitted in ((95, 64), (96, 128)):
        assert all(v['width_26_6'] == fitted for v in next(s for s in synthetic if s['source_width_26_6'] == original)['values'].values())
    for dark in (False, True):
        lut = palettes[dark]
        bg, fg = ((0, 255) if dark else (255, 0))
        sheet = Image.new('RGB', (1200, 90 + len(synthetic) * 74), (bg,) * 3)
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 12), 'Retained native straight bars | exact 8x pixels | fitted width and actual coverage', font=heading, fill=(fg,) * 3)
        crops = []
        for col, (mode, title) in enumerate(LABELS.items()):
            draw.text((12 + 600 * col, 54), title, font=heading, fill=(fg,) * 3)
            for row, entry in enumerate(synthetic):
                value = entry['values'][mode]
                y = 90 + row * 74
                draw.text((12 + col * 600, y), f"{entry['source_width_26_6']/64:g}px -> {value['width_26_6']/64:g}px | coverage {value['profile']}", font=label, fill=(fg,) * 3)
                mask = value['mask']
                if mask['width']:
                    zoom = axis.image(mask).point(lut).convert('RGB').resize((mask['width'] * 8, mask['height'] * 8), Image.Resampling.NEAREST)
                    position = (20 + col * 600, y + 16)
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
    result = dict(kind='native stroke-minimum comparison without opacity transfer',
        input_sha256=input_hashes, source_runner_sha256=report['runner_sha256'],
        source_helper_sha256=report['helper_sha256'], runner_sha256=axis.sha(Path(__file__)),
        conditions=rows, profiles=profiles, synthetic=synthetic, sheets=sheets,
        modes=LABELS, native_modes=MODES, details=detail_chars,
        profile_definition='Each native glyph uses its own first nonempty crown row, middle l row, and central H column; coordinates are reported explicitly',
        checks=['both retained native controls and full metadata match probe records',
                'both original PNG native-word columns match exactly on both palettes',
                'actual light and regular crossbar cores converge without opacity dimming',
                'actual Lato Light 8 core strengthening retains native partial edges',
                'all sRGB blend values against high-precision Decimal oracle',
                'all occurrences and independently checked alpha composition',
                'all 36 conditions and ten saved sheets', 'reopened native and six exact detail crops',
                'retained native synthetic bars and numerical width boundaries',
                'unchanged source inputs, font files and caller environment'],
        limits=['Existing native stem detection, placement, blue zones and italic exemptions remain active',
                'Not every font or crown changes', 'Geometric profiles are native raster observations, not readability scores',
                'No new native build, font substitution, installation or browser qualification'])
    (OUT / 'all.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 36 conditions and ten faithful sheets; ' + str(OUT), flush=True)


if __name__ == '__main__':
    main()
