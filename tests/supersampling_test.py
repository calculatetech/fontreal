#!/usr/bin/env python3
"""Check the real supersampling exporter; retain its gallery for human inspection."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

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


if __name__ == '__main__':
    main()
