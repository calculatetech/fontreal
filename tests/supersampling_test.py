#!/usr/bin/env python3
"""Check the real supersampling exporter; retain its gallery for human inspection."""
import argparse
import ctypes
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops

from selected_profile_test import expected_mask

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('supersampling', ROOT / 'tools/supersampling.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def read(path):
    return json.loads(path.read_text())


def cropped(image, left, top):
    bounds = image.getbbox()
    if bounds is None:
        return {'left': left, 'top': top, 'width': 0, 'height': 0, 'pixels': []}
    pixels = image.crop(bounds)
    return {'left': left + bounds[0], 'top': top + bounds[1], 'width': pixels.width,
            'height': pixels.height, 'pixels': list(pixels.tobytes())}


def area_oracle(glyph, scale):
    if not glyph['pixels']:
        return {'left': 0, 'top': 0, 'width': 0, 'height': 0, 'pixels': []}
    sums = {}
    for i, value in enumerate(glyph['pixels']):
        coordinate = ((glyph['left'] + i % glyph['width']) // scale,
                      (glyph['top'] + i // glyph['width']) // scale)
        sums[coordinate] = sums.get(coordinate, 0) + value
    left = min(x for x, _ in sums)
    top = min(y for _, y in sums)
    right = max(x for x, _ in sums) + 1
    bottom = max(y for _, y in sums) + 1
    count = scale * scale
    image = Image.new('L', (right - left, bottom - top))
    image.putdata([(sums.get((x, y), 0) + count // 2) // count
                   for y in range(top, bottom) for x in range(left, right)])
    return cropped(image, left, top)


def lanczos_oracle(glyph, scale):
    if not glyph['pixels']:
        return {'left': 0, 'top': 0, 'width': 0, 'height': 0, 'pixels': []}
    # Construct each source pixel independently on the global native grid.
    left = math.floor(glyph['left'] / scale) - 3
    top = math.floor(glyph['top'] / scale) - 3
    right = math.ceil((glyph['left'] + glyph['width']) / scale) + 3
    bottom = math.ceil((glyph['top'] + glyph['height']) / scale) + 3
    source = Image.new('L', ((right - left) * scale, (bottom - top) * scale))
    for i, value in enumerate(glyph['pixels']):
        source.putpixel((glyph['left'] + i % glyph['width'] - left * scale,
                         glyph['top'] + i // glyph['width'] - top * scale), value)
    return cropped(source.resize((right - left, bottom - top), Image.Resampling.LANCZOS), left, top)


def composed_bytes(glyphs, placements, points, size):
    width, height = size
    pixels = bytearray(width * height)
    for placement in placements:
        glyph = glyphs[placement['code']]['final']
        origin_x = 6 + placement['x'] + glyph['left']
        origin_y = (points * 4 + 2) // 3 + 5 + placement['line'] * ((points * 4 + 2) // 3 + 6) + glyph['top']
        for i, value in enumerate(glyph['pixels']):
            x, y = origin_x + i % glyph['width'], origin_y + i // glyph['width']
            assert 0 <= x < width and 0 <= y < height
            index = y * width + x
            pixels[index] = 255 - ((255 - pixels[index]) * (255 - value) // 255)
    return bytes(pixels)


def frozen_first_study(directory, record):
    files = ('tools/supersampling.py', 'tests/supersampling_probe.cpp', 'tests/selected_mask_probe.cpp',
             'src/fontreal_coverage.cpp', 'src/fontreal_coverage.h')
    with tempfile.TemporaryDirectory(prefix='ss1-reference-', dir=study.BUILD) as temporary:
        reference = Path(temporary)
        for name in files:
            target = reference / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(['git', 'show', f'ff63a7f448f77338f594156d858a02aefea95fe8:{name}'], cwd=ROOT))
        output = subprocess.check_output([sys.executable, '-B', str(reference / files[0]),
                                         '--record', str(record.resolve())], text=True)
        baseline = Path(output.splitlines()[-1])
        before, after = read(baseline / 'manifest.json'), read(directory / 'manifest.json')
        assert before['fonts'] == after['fonts'] and before['methods'] == after['methods']
        for old, new in zip(before['cases'], after['cases']):
            assert old['placements'] == new['placements']
            # Includes Z and all other retained glyphs that the displayed specimen omits.
            assert read(baseline / old['capture']) == read(directory / new['capture'])
            for a, b in zip(old['methods'], new['methods']):
                assert read(baseline / a['masks']) == read(directory / b['masks'])
                assert a['crops'] == b['crops']
    assert not reference.exists()


def provider_capabilities(record):
    library = ctypes.CDLL(read(record)['libraries']['stock']['library'])
    handle = ctypes.c_void_p()
    properties_env = os.environ.pop('FREETYPE_PROPERTIES', None)
    try:
        assert library.FT_Init_FreeType(ctypes.byref(handle)) == 0
    finally:
        if properties_env is not None:
            os.environ['FREETYPE_PROPERTIES'] = properties_env
    library.FT_Library_SetLcdFilter.argtypes = (ctypes.c_void_p, ctypes.c_int)
    library.FT_Property_Set.argtypes = library.FT_Property_Get.argtypes = (
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p)
    filters = {key: library.FT_Library_SetLcdFilter(handle, value)
               for key, value in (('none', 0), ('default', 1), ('light', 2), ('legacy1', 3), ('legacy', 16))}
    properties = []
    for module, name, choices in ((b'truetype', b'interpreter-version', (35, 38, 40)),
                                  (b'cff', b'hinting-engine', (0, 1))):
        results = []
        for requested in choices:
            value, effective = ctypes.c_uint(requested), ctypes.c_uint()
            error = library.FT_Property_Set(handle, module, name, ctypes.byref(value))
            get = library.FT_Property_Get(handle, module, name, ctypes.byref(effective))
            results.append({'requested': requested, 'set_error': error, 'get_error': get, 'effective': effective.value})
        properties.append(results)
    library.FT_Done_FreeType.argtypes = (ctypes.c_void_p,)
    assert library.FT_Done_FreeType(handle) == 0
    return {'lcd_filters': filters, 'interpreters': properties[0], 'cff_engines': properties[1],
            'cff_no_stem_darkening': False, 'auto_no_stem_darkening': True}


def expected_stock_sources(capabilities):
    # Independent public enum values and option inventory, not the production catalog.
    result = {'off_gray': ('off', 0, 0, 'n/a', 40)}
    for policy in ('native', 'auto'):
        for target, name in enumerate(('normal', 'light', 'mono', 'lcd', 'lcd_v')):
            result[f'{policy}_{name}_gray'] = (policy, target, 0, 'n/a', 40)
    for policy in ('off', 'native', 'auto'):
        result[f'{policy}_mono_source'] = (policy, 2, 2, 'n/a', 40)
        for target, axis in ((3, 'lcd'), (4, 'lcd_v')):
            for name, error in capabilities['lcd_filters'].items():
                if error == 0:
                    result[f'{policy}_{axis}_{name}'] = (policy, target, target, name, 40)
    for property in capabilities['interpreters'][:2]:
        version = property['requested']
        if property['set_error'] == 0 and (version == 35 or property['effective'] != 40):
            result[f'tt{version}_gray'] = ('native', 0, 0, 'n/a', version)
            result[f'tt{version}_mono_source'] = ('native', 2, 2, 'n/a', version)
    old = capabilities['cff_engines'][0]
    if old['set_error'] == 0 and old['effective'] == 0:
        result['cff_old_gray'] = ('native', 0, 0, 'n/a', 40)
    return result


def decoded_oracle(glyph):
    bitmap = glyph['bitmap']
    mode, columns, rows = bitmap['pixel_mode'], bitmap['width'], bitmap['rows']
    stride = abs(bitmap['pitch'])
    source = bytes.fromhex(bitmap['rows_hex'])
    assert len(source) == rows * stride
    if mode == 5:
        assert columns % 3 == 0
    if mode == 6:
        assert rows % 3 == 0
    width, height = columns // (3 if mode == 5 else 1), rows // (3 if mode == 6 else 1)
    channels = 3 if mode in (5, 6) else 1
    pixels = []
    for row in range(height):
        for column in range(width):
            for channel in range(channels):
                sy = row * 3 + channel if mode == 6 else row
                sx = column * 3 + channel if mode == 5 else column
                value = source[sy * stride + (sx // 8 if mode == 1 else sx)]
                pixels.append(((value >> (7 - sx % 8)) & 1) * 255 if mode == 1 else value)
    result = {'left': glyph['left'], 'top': glyph['top'], 'width': width, 'height': height,
              'channels': channels, 'pixels': pixels}
    return result


def channel_area_oracle(glyph, scale=4):
    channels = glyph['channels']
    if not glyph['pixels']:
        return {**{k: 0 for k in ('left', 'top', 'width', 'height')},
                **({'channels': 3} if channels == 3 else {}), 'pixels': []}
    totals = {}
    for index in range(glyph['width'] * glyph['height']):
        key = ((glyph['left'] + index % glyph['width']) // scale,
               (glyph['top'] + index // glyph['width']) // scale)
        sums = totals.setdefault(key, [0] * channels)
        for channel in range(channels):
            sums[channel] += glyph['pixels'][index * channels + channel]
    left, top = min(x for x, y in totals), min(y for x, y in totals)
    right, bottom = max(x for x, y in totals) + 1, max(y for x, y in totals) + 1
    count = scale * scale
    values = [(v + count // 2) // count for y in range(top, bottom) for x in range(left, right)
              for v in totals.get((x, y), [0] * channels)]
    image = Image.frombytes('RGB' if channels == 3 else 'L', (right - left, bottom - top), bytes(values))
    result = cropped(image, left, top)
    if channels == 3:
        result['channels'] = 3
    return result


def composed_rgb_bytes(glyphs, placements, points, size):
    width, height = size
    pixels = bytearray(width * height * 3)
    for placement in placements:
        glyph = glyphs[placement['code']]['final']
        channels = glyph.get('channels', 1)
        origin_x = 6 + placement['x'] + glyph['left']
        origin_y = (points * 4 + 2) // 3 + 5 + placement['line'] * ((points * 4 + 2) // 3 + 6) + glyph['top']
        for index in range(glyph['width'] * glyph['height']):
            x, y = origin_x + index % glyph['width'], origin_y + index // glyph['width']
            assert 0 <= x < width and 0 <= y < height
            for channel in range(3):
                value = glyph['pixels'][index * channels + (channel if channels == 3 else 0)]
                offset = (y * width + x) * 3 + channel
                pixels[offset] = 255 - ((255 - pixels[offset]) * (255 - value) // 255)
    return bytes(pixels)


def bitmap_fixtures():
    # Synthetic padding, mono-bit and channel distinctions supplement real provider captures.
    fixtures = (
        (1, 9, 2, 2, bytes((128, 128, 64, 0))),
        (2, 3, 2, 4, bytes((255, 100, 50, 99, 40, 20, 10, 99))),
        (5, 9, 2, 12, bytes((255, 0, 0, 0, 128, 0, 0, 0, 64, 99, 99, 99,
                            32, 0, 0, 0, 16, 0, 0, 0, 8, 99, 99, 99))),
        (6, 3, 6, 4, bytes((255, 0, 0, 99, 0, 128, 0, 99, 0, 0, 64, 99,
                            32, 0, 0, 99, 0, 16, 0, 99, 0, 0, 8, 99))),
    )
    for mode, width, rows, pitch, raw in fixtures:
        source = {'left': -1, 'top': -1, 'bitmap': {'width': width, 'rows': rows, 'pitch': pitch,
                  'pixel_mode': mode, 'rows_hex': raw.hex()}}
        expected = decoded_oracle(source)
        assert study.decode_bitmap(source) == expected
        assert study.reduce_stock(study.decode_bitmap(source), 4) == channel_area_oracle(expected)
        if mode in (5, 6):
            assert expected['pixels'] == [255, 0, 0, 0, 128, 0, 0, 0, 64, 32, 0, 0, 0, 16, 0, 0, 0, 8]
        if mode == 1:
            assert expected['pixels'] == [255, 0, 0, 0, 0, 0, 0, 0, 255, 0, 255, 0, 0, 0, 0, 0, 0, 0]


def stock_check(record, original):
    output = subprocess.check_output([sys.executable, '-B', str(ROOT / 'tools/supersampling.py'),
                                     '--record', str(record.resolve()), '--stock4x'], text=True)
    directory = Path(output.splitlines()[-1])
    assert directory.resolve().is_relative_to((ROOT / 'results/supersampling').resolve())
    manifest, previous = read(directory / 'manifest.json'), read(original / 'manifest.json')
    capabilities = provider_capabilities(record)
    bitmap_fixtures()
    sources = expected_stock_sources(capabilities)
    expected = {'A', 'B', 'C'}
    for name, (_, _, render, _, _) in sources.items():
        expected.update([name + '_RGB', name + '_BGR'] if render in (3, 4) else [name])
    assert manifest['study'] == 'stock4x' and manifest['fonts'] == previous['fonts']
    assert {(c['font'], c['points']) for c in manifest['cases']} == {(f, p) for f in range(3) for p in range(8, 17)}
    witnesses = {'mono': False, 'lcd': False, 'lcd_v': False, 'fringe': False, 'negative': False,
                 'nondivisible': False, 'untreated': False, 'native_difference': False}
    for case, old in zip(manifest['cases'], previous['cases']):
        assert case['capabilities'] == capabilities and case['placements'] == old['placements']
        capture = read(directory / case['capture'])
        assert study.sha(capture['provider']) == manifest['provider_sha256']
        assert study.sha(directory / case['capture']) == case['capture_sha256']
        assert capture['captures'][:4] == read(original / old['capture'])['captures']
        modes = {c['mode']: c for c in capture['captures']}
        assert set(modes) == {'native1', 'native2', 'native4', 'target4'} | set(sources)
        native = {g['code']: g for g in modes['native1']['glyphs']}
        old_masks = {method['key']: {g['code']: g for g in read(original / method['masks'])}
                     for method in old['methods'] if method['key'] in ('A', 'B', 'C', 'E')}
        oracles = {}
        for name, (policy, target, render, filter, version) in sources.items():
            mode = modes[name]
            assert (mode['policy'], mode['target'], mode['render'], mode['filter'], mode['interpreter']) == (
                policy, target, render, filter, version)
            flags = 8 | (target << 16) | (32 if policy == 'auto' else 32768) | (2 if policy == 'off' else 0)
            assert mode['load_flags'] == flags and mode['hint_dpi'] == 384 and mode['scale'] == 4
            assert mode['x_ppem'] == modes['native4']['x_ppem']
            effective = next(p['effective'] for p in capabilities['interpreters'] if p['requested'] == version)
            assert mode['effective_interpreter'] == effective
            assert mode['cff_hinting_engine'] == (0 if name == 'cff_old_gray' else 1)
            assert [g['code'] for g in mode['glyphs']] == list(range(32, 127))
            for glyph in mode['glyphs']:
                assert glyph['bitmap']['pixel_mode'] == {0: 2, 2: 1, 3: 5, 4: 6}[render]
                assert len(glyph['outline']) == len(glyph['tags'])
                assert all(len(point) == 2 for point in glyph['outline'])
                if glyph['code'] != 32:
                    assert glyph['outline'] and glyph['contours']
                    assert glyph['contours'] == sorted(set(glyph['contours']))
                    assert glyph['contours'][-1] == len(glyph['outline']) - 1
                    assert all(0 <= end < len(glyph['outline']) for end in glyph['contours'])
                decoded = decoded_oracle(glyph)
                if name == 'native_normal_gray':
                    control = modes['native4']['glyphs'][glyph['code'] - 32]
                    for field in ('outline', 'tags', 'contours', 'advance'):
                        assert glyph[field] == control[field]
                    assert {k: decoded[k] for k in ('left', 'top', 'width', 'height', 'pixels')} == {
                        k: control[k] for k in ('left', 'top', 'width', 'height', 'pixels')}
                actual = study.decode_bitmap(glyph)
                assert actual == decoded
                reduced = channel_area_oracle(decoded)
                oracles[name, glyph['code']] = reduced
                witnesses['negative'] |= glyph['left'] < 0
                witnesses['nondivisible'] |= bool(decoded['width'] % 4 or decoded['height'] % 4)
                if render == 2:
                    witnesses['mono'] |= 0 < min([p for p in reduced['pixels'] if p] or [255]) < 255
                if render in (3, 4):
                    distinct = any(len(set(reduced['pixels'][i:i + 3])) > 1 for i in range(0, len(reduced['pixels']), 3))
                    witnesses['lcd' if render == 3 else 'lcd_v'] |= distinct
                    none_name = f'{policy}_{"lcd" if render == 3 else "lcd_v"}_none'
                    if filter != 'none' and none_name in modes and decoded['pixels']:
                        plain = decoded_oracle(modes[none_name]['glyphs'][glyph['code'] - 32])
                        a = Image.frombytes('RGB', (decoded['width'], decoded['height']), bytes(decoded['pixels'])).getbbox()
                        b = Image.frombytes('RGB', (plain['width'], plain['height']), bytes(plain['pixels'])).getbbox()
                        if a and b:
                            witnesses['fringe'] |= (decoded['left'] + a[0] < plain['left'] + b[0] or
                                decoded['top'] + a[1] < plain['top'] + b[1] or
                                decoded['left'] + a[2] > plain['left'] + b[2] or
                                decoded['top'] + a[3] > plain['top'] + b[3])
        assert {m['key'] for m in case['methods']} == expected
        by_key = {}
        for treatment in case['methods']:
            key, mode, order = treatment['key'], treatment['mode'], treatment['order']
            glyphs = read(directory / treatment['masks'])
            assert study.sha(directory / treatment['masks']) == treatment['masks_sha256']
            assert [g['code'] for g in glyphs] == list(range(32, 127))
            by_key[key] = {g['code']: g for g in glyphs}
            assert treatment['corrected'] == (key == 'B')
            for glyph in glyphs:
                code = glyph['code']
                if key in ('A', 'B', 'C'):
                    assert glyph == old_masks[key][code]
                else:
                    reference = oracles[mode, code]
                    if order == 'BGR':
                        values = reference['pixels']
                        reference = {**reference, 'pixels': [v for i in range(0, len(values), 3) for v in values[i:i + 3][::-1]]}
                    assert glyph['pre_core'] == reference == glyph['final']
                    if key == 'native_normal_gray':
                        assert glyph['pre_core'] == old_masks['E'][code]['pre_core']
                        witnesses['untreated'] |= glyph['final'] != old_masks['E'][code]['final']
                assert glyph['advance_pixels'] == int(native[code]['advance'] + .5)
                if code == 32:
                    assert not any(glyph['final']['pixels']) and glyph['advance_pixels'] > 0
                else:
                    assert any(glyph['final']['pixels'])
            light_info, dark_info = (treatment['crops'][p] for p in ('light', 'dark'))
            light, dark = (Image.open(directory / c['file']) for c in (light_info, dark_info))
            assert light.mode == dark.mode == 'RGB'
            assert list(light.size) == light_info['size'] == dark_info['size']
            assert study.sha(directory / light_info['file']) == light_info['sha256']
            assert study.sha(directory / dark_info['file']) == dark_info['sha256']
            assert ImageChops.difference(light, ImageChops.invert(dark)).getbbox() is None
            assert composed_rgb_bytes(by_key[key], case['placements'], case['points'], dark.size) == dark.tobytes()
        for code in map(ord, 'Hn8oW:pZ'):
            untreated = by_key['native_normal_gray'][code]['final']
            witnesses['native_difference'] |= untreated != by_key['A'][code]['final']
        assert 'AAAAB' in ''.join(chr(p['code']) for p in case['placements'])
    assert all(witnesses.values()), witnesses
    assert len(manifest['sheets']) == 54
    assert {(s['font'], s['points'], s['polarity']) for s in manifest['sheets']} == {
        (f, p, polarity) for f in range(3) for p in range(8, 17) for polarity in ('light', 'dark')}
    for sheet in manifest['sheets']:
        image = Image.open(directory / sheet['file'])
        assert list(image.size) == sheet['size'] and image.width == 1896
        assert study.sha(directory / sheet['file']) == sheet['sha256']
        assert all(1 <= len(panel['methods']) <= 7 for panel in sheet['panels'])
        assert set(c['method'] for c in sheet['crops']) == expected
        for crop in sheet['crops']:
            assert image.crop(crop['box']).tobytes() == Image.open(directory / crop['file']).tobytes()
    print(f'PASS: stock 4x, {len(expected)} treatments, 27 cases, both polarities, 54 native sheets\n{directory}')
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path)
    args = parser.parse_args()
    output = subprocess.check_output([sys.executable, '-B', str(ROOT / 'tools/supersampling.py'),
                                      '--record', str(args.record)], text=True)
    directory = Path(output.splitlines()[-1])
    assert directory.resolve().is_relative_to((ROOT / 'results/supersampling').resolve())
    rejected = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/supersampling.py'),
                               '--record', str(args.record), '--output', str(directory / 'outside')],
                              capture_output=True, text=True)
    assert rejected.returncode == 2 and not (directory / 'outside').exists()
    manifest = read(directory / 'manifest.json')
    assert len(manifest['fonts']) == 3 and len(manifest['cases']) == 27
    assert {(c['font'], c['points']) for c in manifest['cases']} == {
        (f, p) for f in range(3) for p in range(8, 17)}
    apply = study.processor(study.BUILD / 'coverage.so')
    changed = repeated = negative = irregular = larger = fringe = False
    for case in manifest['cases']:
        capture = read(directory / case['capture'])
        assert study.sha(directory / case['capture']) == case['capture_sha256']
        assert study.sha(capture['provider']) == manifest['provider_sha256']
        assert capture['points'] == case['points'] and capture['target_dpi'] == 96
        if case['font'] == 2:
            assert capture['format'] == 'CFF'
        modes = {c['mode']: c for c in capture['captures']}
        for mode, factor in (('native1', 1), ('native2', 2), ('native4', 4), ('target4', 4)):
            assert modes[mode]['scale'] == factor
            assert modes[mode]['hint_dpi'] == (96 if mode == 'target4' else 96 * factor)
            assert [g['code'] for g in modes[mode]['glyphs']] == list(range(32, 127))
        native = {g['code']: g for g in modes['native1']['glyphs']}
        control = {g['code']: g for g in modes['target4']['glyphs']}
        assert modes['native1']['x_ppem'] == modes['target4']['x_ppem']
        assert modes['native4']['x_ppem'] > modes['native1']['x_ppem'] * 3
        for code, glyph in native.items():
            assert control[code]['outline'] == [[x * 4, y * 4] for x, y in glyph['outline']]
            assert control[code]['tags'] == glyph['tags']
            assert control[code]['contours'] == glyph['contours']
        assert native[32]['advance'] > 0 and not any(native[32]['pixels'])
        assert len(case['methods']) == 7 and [m['key'] for m in case['methods']] == list('ABCDEFG')
        mask_sets = {}
        for treatment, definition in zip(case['methods'], study.METHODS):
            key, _, mode, kernel, corrected = definition
            assert (treatment['key'], treatment['mode'], treatment['kernel'], treatment['corrected']) == (
                key, mode, kernel, corrected)
            masks = read(directory / treatment['masks'])
            assert study.sha(directory / treatment['masks']) == treatment['masks_sha256']
            assert [g['code'] for g in masks] == list(range(32, 127))
            mask_sets[key] = {g['code']: g for g in masks}
            for source, glyph in zip(modes[mode]['glyphs'], masks):
                assert glyph['advance_pixels'] == int(native[glyph['code']]['advance'] + .5)
                if kernel != 'none':
                    oracle = area_oracle(source, modes[mode]['scale']) if kernel == 'area' else lanczos_oracle(source, 4)
                    assert glyph['pre_core'] == oracle, (case['font'], case['points'], key, glyph['code'])
                    negative |= source['left'] < 0
                    irregular |= source['width'] % modes[mode]['scale'] != 0
                    if kernel == 'lanczos' and oracle['pixels']:
                        area = area_oracle(source, 4)
                        fringe |= (oracle['left'] < area['left'] or oracle['top'] < area['top'] or
                                   oracle['left'] + oracle['width'] > area['left'] + area['width'] or
                                   oracle['top'] + oracle['height'] > area['top'] + area['height'])
                else:
                    assert glyph['pre_core'] == {k: source[k] for k in ('left', 'top', 'width', 'height', 'pixels')}
                assert glyph['final'] == (apply(glyph['pre_core']) if corrected else glyph['pre_core'])
                if glyph['code'] != 32:
                    assert any(glyph['final']['pixels'])
            light_info, dark_info = (treatment['crops'][p] for p in ('light', 'dark'))
            light, dark = (Image.open(directory / i['file']) for i in (light_info, dark_info))
            assert list(light.size) == light_info['size'] == dark_info['size']
            assert study.sha(directory / light_info['file']) == light_info['sha256']
            assert study.sha(directory / dark_info['file']) == dark_info['sha256']
            assert ImageChops.difference(light, ImageChops.invert(dark)).getbbox() is None
            assert composed_bytes(mask_sets[key], case['placements'], case['points'], dark.size) == dark.tobytes()
        # Existing scalar oracle is independent of this experiment and its C++ adapter.
        for code in map(ord, 'Hn8oW:p'):
            raw = native[code]
            accepted = mask_sets['B'][code]['final']['pixels']
            assert list(expected_mask(bytes(raw['pixels']), raw['width'])) == accepted
            changed |= raw['pixels'] != accepted
            repeated |= list(expected_mask(bytes(accepted), raw['width'])) != accepted
        for source in modes['native4']['glyphs']:
            raw = native[source['code']]
            if raw['width'] and raw['height'] and source['width'] == raw['width'] * 4 and source['height'] == raw['height'] * 4:
                enlarged = [raw['pixels'][(y // 4) * raw['width'] + x // 4]
                            for y in range(source['height']) for x in range(source['width'])]
                larger |= enlarged != source['pixels']
        sequence = ''.join(chr(p['code']) for p in case['placements'])
        assert 'AAAAB' in sequence and all(c in sequence for c in 'abcdefghijklmnopqrstuvwxyz0123456789!?:;')
        assert len(set((p['x'], p['line']) for p in case['placements'])) == len(case['placements'])
    assert all((changed, repeated, negative, irregular, larger, fringe))
    fixture = {'left': -1, 'top': -1, 'width': 5, 'height': 5, 'pixels': [255] * 25}
    area, lanczos = area_oracle(fixture, 4), lanczos_oracle(fixture, 4)
    assert study.reduce_mask(fixture, 4, 'area') == area
    assert study.reduce_mask(fixture, 4, 'lanczos') == lanczos
    assert lanczos != area and (lanczos['width'] > area['width'] or lanczos['height'] > area['height'])
    assert len(manifest['sheets']) == 12
    for sheet in manifest['sheets']:
        image = Image.open(directory / sheet['file'])
        assert list(image.size) == sheet['size'] and study.sha(directory / sheet['file']) == sheet['sha256']
        assert len(sheet['crops']) == (35 if '8-12pt' in sheet['file'] else 28)
        for crop in sheet['crops']:
            assert image.crop(crop['box']).tobytes() == Image.open(directory / crop['file']).tobytes()
    print(f'PASS: 27 font/size cases, 7 treatments, both polarities, 12 native-pixel sheets\n{directory}')
    frozen_first_study(directory, args.record)
    print('PASS: all SS-1 capture/mask/placement records and 378 native crops match frozen ff63a7f')
    stock_check(args.record, directory)


if __name__ == '__main__':
    main()
