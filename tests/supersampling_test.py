#!/usr/bin/env python3
"""Check the real supersampling exporter; retain its gallery for human inspection."""
import argparse
import ctypes
import importlib.util
import json
import math
import os
import shlex
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
    library.FT_Property_Set.argtypes = library.FT_Property_Get.argtypes = (
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p)
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
    for enabled in (False, True):
        for module in (b'cff', b'autofitter'):
            disabled, actual = ctypes.c_ubyte(not enabled), ctypes.c_ubyte()
            assert library.FT_Property_Set(handle, module, b'no-stem-darkening', ctypes.byref(disabled)) == 0
            assert library.FT_Property_Get(handle, module, b'no-stem-darkening', ctypes.byref(actual)) == 0
            assert bool(actual.value) == (not enabled)
    library.FT_Done_FreeType.argtypes = (ctypes.c_void_p,)
    assert library.FT_Done_FreeType(handle) == 0
    return {'interpreters': properties[0], 'cff_engines': properties[1]}


def expected_stock_sources(capabilities):
    # Independent public enum values and retained option inventory.
    bases = {'off_gray': ('off', 0, 0, 40)}
    for policy in ('native', 'auto'):
        for target, name in enumerate(('normal', 'light', 'mono')):
            bases[f'{policy}_{name}_gray'] = (policy, target, 0, 40)
    for policy in ('off', 'native', 'auto'):
        bases[f'{policy}_mono_source'] = (policy, 2, 2, 40)
    for property in capabilities['interpreters'][:2]:
        version = property['requested']
        if property['set_error'] == 0 and (version == 35 or property['effective'] != 40):
            bases[f'tt{version}_gray'] = ('native', 0, 0, version)
            bases[f'tt{version}_mono_source'] = ('native', 2, 2, version)
    old = capabilities['cff_engines'][0]
    if old['set_error'] == 0 and old['effective'] == 0:
        bases['cff_old_gray'] = ('native', 0, 0, 40)
    return {base + '_dark_' + state: (*values, state == 'on')
            for base, values in bases.items() for state in ('off', 'on')}


def decoded_oracle(glyph):
    bitmap = glyph['bitmap']
    mode, columns, rows = bitmap['pixel_mode'], bitmap['width'], bitmap['rows']
    stride = abs(bitmap['pitch'])
    source = bytes.fromhex(bitmap['rows_hex'])
    assert mode in (1, 2) and len(source) == rows * stride
    values = [
        (((source[row * stride + column // 8] >> (7 - column % 8)) & 1) * 255)
        if mode == 1 else source[row * stride + column]
        for row in range(rows) for column in range(columns)
    ]
    return {'left': glyph['left'], 'top': glyph['top'], 'width': columns, 'height': rows, 'pixels': values}


def bitmap_fixtures():
    fixtures = [
        {'left': -1, 'top': -5, 'bitmap': {'width': 9, 'rows': 3, 'pitch': 4, 'pixel_mode': 1,
            'rows_hex': 'aa80ffff5500ffffff80ffff'}},
        {'left': -1, 'top': -5, 'bitmap': {'width': 3, 'rows': 3, 'pitch': 4, 'pixel_mode': 2,
            'rows_hex': '01c8ff7f80fa3c7fffa0557f'}},
    ]
    for glyph in fixtures:
        expected = decoded_oracle(glyph)
        assert study.decode_bitmap(glyph) == expected
        assert study.reduce_mask(expected, 4, 'area') == area_oracle(expected, 4)


def darkening_references(record, fonts):
    source = subprocess.check_output(['git', 'show',
        'ff63a7f448f77338f594156d858a02aefea95fe8:tests/supersampling_probe.cpp'], cwd=ROOT, text=True)
    override = '        check(FT_Property_Set(library,"cff","no-stem-darkening",&darkening));\n'
    assert source.count(override) == 1
    source = source.replace(override, '')
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core', 'freetype2'], text=True))
    provider = Path(read(record)['libraries']['stock']['library']).resolve()
    environment = dict(os.environ)
    environment.pop('LD_PRELOAD', None)
    environment['LD_LIBRARY_PATH'] = str(provider.parent)
    references, witnesses = {}, []
    with tempfile.TemporaryDirectory(prefix='stem-reference-', dir=study.BUILD) as temporary:
        root = Path(temporary)
        for policy, font_index in (('native', 2), ('auto', 0)):
            text = source
            if policy == 'auto':
                old = 'FT_LOAD_NO_AUTOHINT|FT_LOAD_NO_BITMAP'
                assert text.count(old) == 1
                text = text.replace(old, 'FT_LOAD_FORCE_AUTOHINT|FT_LOAD_NO_BITMAP')
            cpp, probe = root / f'{policy}.cpp', root / policy
            cpp.write_text(text)
            subprocess.run(['c++', '-std=c++17', '-O2', '-fPIC', str(cpp), '-o', str(probe), *flags, '-ldl'], check=True)
            pair = []
            for enabled in (False, True):
                environment['FREETYPE_PROPERTIES'] = (
                    f'cff:no-stem-darkening={int(not enabled)} autofitter:no-stem-darkening={int(not enabled)}')
                capture = json.loads(subprocess.check_output([str(probe), fonts[font_index]['file'], '8'], env=environment))
                assert Path(capture['provider']).resolve() == provider
                assert study.sha(capture['provider']) == read(record)['libraries']['stock']['sha256']
                modes = {m['mode']: m for m in capture['captures']}
                references[font_index, enabled] = modes['native4']['glyphs']
                pair.append(modes['native1']['glyphs'])
            witnesses.append(pair[0] != pair[1])
    assert not root.exists() and any(witnesses), 'no lower-density provider darkening witness'
    print('PASS: independent native-CFF/forced-auto property references and lower-density witness')
    return references


def stock_check(record, original):
    output = subprocess.check_output([sys.executable, '-B', str(ROOT / 'tools/supersampling.py'),
                                     '--record', str(record.resolve()), '--stock4x'], text=True)
    directory = Path(output.splitlines()[-1])
    assert directory.resolve().is_relative_to((ROOT / 'results/supersampling').resolve())
    manifest, previous = read(directory / 'manifest.json'), read(original / 'manifest.json')
    capabilities = provider_capabilities(record)
    bitmap_fixtures()
    references = darkening_references(record, manifest['fonts'])
    sources = expected_stock_sources(capabilities)
    expected = {'A', 'B'} | set(sources)
    base_titles = {
        'off_gray': '4x off gray',
        'native_normal_gray': '4x native normal gray',
        'native_light_gray': '4x native light gray',
        'native_mono_gray': '4x native mono gray',
        'auto_normal_gray': '4x auto normal gray',
        'auto_light_gray': '4x auto light gray',
        'auto_mono_gray': '4x auto mono gray',
        'off_mono_source': '4x off mono',
        'native_mono_source': '4x native mono',
        'auto_mono_source': '4x auto mono',
        'tt35_gray': '4x tt35 gray (TT only)',
        'tt35_mono_source': '4x tt35 mono (TT only)',
        'tt38_gray': '4x tt38 gray (TT only)',
        'tt38_mono_source': '4x tt38 mono (TT only)',
        'cff_old_gray': '4x cff old gray (CFF only)',
    }
    titles = {'A': 'Untreated FreeType 1x', 'B': 'Current Fontreal 1x'}
    for key, (_, _, _, _, enabled) in sources.items():
        titles[key] = base_titles[key.rsplit('_dark_', 1)[0]] + '\nStem ' + ('on' if enabled else 'off')
    assert manifest['study'] == 'stock4x' and manifest['fonts'] == previous['fonts']
    assert len(manifest['cases']) == 27
    assert {(c['font'], c['points']) for c in manifest['cases']} == {(f, p) for f in range(3) for p in range(8, 17)}
    witnesses = {'mono': False, 'negative': False, 'nondivisible': False,
                 'untreated': False, 'native_difference': False}
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
                     for method in old['methods'] if method['key'] in ('A', 'B', 'E')}
        oracles = {}
        for name, (policy, target, render, version, enabled) in sources.items():
            mode = modes[name]
            assert (mode['policy'], mode['target'], mode['render'], mode['interpreter'], mode['stem_darkening']) == (
                policy, target, render, version, enabled)
            for module in ('cff', 'autofitter'):
                assert mode['darkening_properties'][module] == {
                    'set_error': 0, 'get_error': 0, 'no_stem_darkening': not enabled}
            flags = 8 | (target << 16) | (32 if policy == 'auto' else 32768) | (2 if policy == 'off' else 0)
            assert mode['load_flags'] == flags and mode['hint_dpi'] == 384 and mode['scale'] == 4
            assert mode['x_ppem'] == modes['native4']['x_ppem']
            effective = next(p['effective'] for p in capabilities['interpreters'] if p['requested'] == version)
            assert mode['effective_interpreter'] == effective
            assert mode['cff_hinting_engine'] == (0 if name.startswith('cff_old_gray') else 1)
            assert [g['code'] for g in mode['glyphs']] == list(range(32, 127))
            for glyph in mode['glyphs']:
                assert glyph['bitmap']['pixel_mode'] == {0: 2, 2: 1}[render]
                assert len(glyph['outline']) == len(glyph['tags'])
                assert all(len(point) == 2 for point in glyph['outline'])
                if glyph['code'] != 32:
                    assert glyph['outline'] and glyph['contours']
                    assert glyph['contours'] == sorted(set(glyph['contours']))
                    assert glyph['contours'][-1] == len(glyph['outline']) - 1
                    assert all(0 <= end < len(glyph['outline']) for end in glyph['contours'])
                decoded = decoded_oracle(glyph)
                control = None
                if name == 'native_normal_gray_dark_on':
                    control = modes['native4']['glyphs'][glyph['code'] - 32]
                if case['points'] == 8 and ((case['font'] == 2 and name.startswith('native_normal_gray_dark_')) or
                                           (case['font'] == 0 and name.startswith('auto_normal_gray_dark_'))):
                    control = references[case['font'], enabled][glyph['code'] - 32]
                if control is not None:
                    for field in ('outline', 'tags', 'contours', 'advance'):
                        assert glyph[field] == control[field], (case['font'], name, glyph['code'], field)
                    assert decoded == {k: control[k] for k in ('left', 'top', 'width', 'height', 'pixels')}
                assert study.decode_bitmap(glyph) == decoded
                reduced = area_oracle(decoded, 4)
                oracles[name, glyph['code']] = reduced
                witnesses['negative'] |= glyph['left'] < 0
                witnesses['nondivisible'] |= bool(decoded['width'] % 4 or decoded['height'] % 4)
                if render == 2:
                    witnesses['mono'] |= 0 < min([p for p in reduced['pixels'] if p] or [255]) < 255
        assert {m['key'] for m in case['methods']} == expected
        by_key = {}
        for treatment in case['methods']:
            key, mode = treatment['key'], treatment['mode']
            assert treatment['title'] == titles[key]
            glyphs = read(directory / treatment['masks'])
            assert study.sha(directory / treatment['masks']) == treatment['masks_sha256']
            assert [g['code'] for g in glyphs] == list(range(32, 127))
            by_key[key] = {g['code']: g for g in glyphs}
            assert treatment['corrected'] == (key == 'B')
            if key not in ('A', 'B'):
                assert treatment['stem_darkening'] == modes[mode]['stem_darkening']
            for glyph in glyphs:
                code = glyph['code']
                if key in ('A', 'B'):
                    assert glyph == old_masks[key][code]
                else:
                    assert glyph['pre_core'] == oracles[mode, code] == glyph['final']
                    if key == 'native_normal_gray_dark_on':
                        assert glyph['pre_core'] == old_masks['E'][code]['pre_core']
                        witnesses['untreated'] |= glyph['final'] != old_masks['E'][code]['final']
                assert glyph['advance_pixels'] == int(native[code]['advance'] + .5)
                if code == 32:
                    assert not any(glyph['final']['pixels']) and glyph['advance_pixels'] > 0
                else:
                    assert any(glyph['final']['pixels'])
            light_info, dark_info = (treatment['crops'][p] for p in ('light', 'dark'))
            light, dark = (Image.open(directory / c['file']) for c in (light_info, dark_info))
            assert light.mode == dark.mode == 'L'
            assert list(light.size) == light_info['size'] == dark_info['size']
            assert study.sha(directory / light_info['file']) == light_info['sha256']
            assert study.sha(directory / dark_info['file']) == dark_info['sha256']
            assert ImageChops.difference(light, ImageChops.invert(dark)).getbbox() is None
            assert composed_bytes(by_key[key], case['placements'], case['points'], dark.size) == dark.tobytes()
        for code in map(ord, 'Hn8oW:pZV'):
            untreated = by_key['native_normal_gray_dark_on'][code]['final']
            witnesses['native_difference'] |= untreated != by_key['A'][code]['final']
        assert 'AAAAB' in ''.join(chr(p['code']) for p in case['placements'])
    assert all(witnesses.values()), witnesses
    assert len(manifest['sheets']) == 54
    assert {(s['font'], s['points'], s['polarity']) for s in manifest['sheets']} == {
        (f, p, polarity) for f in range(3) for p in range(8, 17) for polarity in ('light', 'dark')}
    ordering = ('native_normal_gray', 'auto_normal_gray', 'native_light_gray', 'auto_light_gray',
                'native_mono_gray', 'auto_mono_gray', 'off_gray', 'off_mono_source',
                'native_mono_source', 'auto_mono_source', 'tt35_gray', 'tt35_mono_source',
                'tt38_gray', 'tt38_mono_source', 'cff_old_gray')
    bases = [base for base in ordering if base + '_dark_off' in expected]
    rows = [['A', 'B'] + [base + '_dark_' + state for base in bases[i:i + 2] for state in ('off', 'on')]
            for i in range(0, len(bases), 2)]
    for sheet in manifest['sheets']:
        image = Image.open(directory / sheet['file'])
        assert image.mode == 'L' and list(image.size) == sheet['size'] and image.width == 1628
        assert study.sha(directory / sheet['file']) == sheet['sha256']
        assert [panel['methods'] for panel in sheet['panels']] == rows
        assert all(panel['methods'][:2] == ['A', 'B'] and 4 <= len(panel['methods']) <= 6 for panel in sheet['panels'])
        assert set(c['method'] for c in sheet['crops']) == expected
        for crop in sheet['crops']:
            assert image.crop(crop['box']).tobytes() == Image.open(directory / crop['file']).tobytes()
    print(f'PASS: scalar stock 4x, {len(expected)} treatments, 27 cases, both polarities, 54 native sheets\n{directory}')
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
