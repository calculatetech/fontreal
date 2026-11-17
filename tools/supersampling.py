#!/usr/bin/env python3
"""Export an isolated supersampling study using a paired stock FreeType build."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/supersampling'
FONTS = ('Noto Sans Display', 'Liberation Mono', 'Nimbus Sans')
METHODS = (
    ('A', 'Untreated FreeType 1x', 'native1', 'none', False),
    ('B', 'Current Fontreal 1x', 'native1', 'none', True),
    ('C', '2x / area / untreated', 'native2', 'area', False),
    ('D', '2x / area / Fontreal', 'native2', 'area', True),
    ('E', '4x / area / Fontreal', 'native4', 'area', True),
    ('F', '4x target hints / Fontreal', 'target4', 'area', True),
    ('G', '4x / Lanczos / Fontreal', 'native4', 'lanczos', True),
)
SPECIMEN = (
    'The quick brown fox jumps over the lazy dog.',
    '0123456789  aeons  bdfpqu  358  HMWVY',
    'Aa Ee Oo Ss  iii mmm nnn www  AAAAB',
    '!?:;., \'" ()[]{} /\\ +-=_ @#$%&*<>|~^`',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')


def compile_tools():
    BUILD.mkdir(parents=True, exist_ok=True)
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
                                               'Qt6Core', 'freetype2'], text=True))
    probe = BUILD / 'supersampling-probe'
    core = BUILD / 'coverage.so'
    subprocess.run(['c++', '-std=c++17', '-O2', '-fPIC', str(ROOT / 'tests/supersampling_probe.cpp'),
                    '-o', str(probe), *flags, '-ldl'], check=True)
    subprocess.run(['c++', '-std=c++17', '-O2', '-fPIC', '-shared',
                    str(ROOT / 'tests/selected_mask_probe.cpp'), str(ROOT / 'src/fontreal_coverage.cpp'),
                    '-o', str(core), *flags], check=True)
    return probe, core


def processor(path):
    library = ctypes.CDLL(str(path))
    function = library.fontreal_test_mask
    function.argtypes = (ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint, ctypes.c_uint, ctypes.c_int)
    function.restype = ctypes.c_int

    def apply(mask):
        if not mask['pixels']:
            return dict(mask)
        pixels = (ctypes.c_ubyte * len(mask['pixels']))(*mask['pixels'])
        result = function(pixels, mask['width'], mask['height'], mask['width'])
        if result:
            raise RuntimeError(f'coverage processor failed: {result}')
        return {**mask, 'pixels': list(pixels)}
    return apply


def trim(image, left, top):
    box = image.getbbox()
    if box is None:
        return {'left': left, 'top': top, 'width': 0, 'height': 0, 'pixels': []}
    cut = image.crop(box)
    return {'left': left + box[0], 'top': top + box[1],
            'width': cut.width, 'height': cut.height, 'pixels': list(cut.tobytes())}


def reduce_mask(glyph, scale, kernel):
    if kernel == 'none':
        return {key: glyph[key] for key in ('left', 'top', 'width', 'height', 'pixels')}
    if not glyph['pixels']:
        return {'left': 0, 'top': 0, 'width': 0, 'height': 0, 'pixels': []}
    # Keep the filter grid anchored to the native baseline, including negative bearings.
    pad = 3 if kernel == 'lanczos' else 0
    left = glyph['left'] // scale - pad
    top = glyph['top'] // scale - pad
    right = -(-(glyph['left'] + glyph['width']) // scale) + pad
    bottom = -(-(glyph['top'] + glyph['height']) // scale) + pad
    width, height = right - left, bottom - top
    high = Image.new('L', (width * scale, height * scale))
    high.paste(Image.frombytes('L', (glyph['width'], glyph['height']), bytes(glyph['pixels'])),
               (glyph['left'] - left * scale, glyph['top'] - top * scale))
    if kernel == 'lanczos':
        reduced = high.resize((width, height), Image.Resampling.LANCZOS)
    else:
        pixels = high.tobytes()
        stride, count = high.width, scale * scale
        means = [
            (sum(pixels[(y * scale + dy) * stride + x * scale + dx]
                 for dy in range(scale) for dx in range(scale)) + count // 2) // count
            for y in range(height) for x in range(width)
        ]
        reduced = Image.frombytes('L', (width, height), bytes(means))
    return trim(reduced, left, top)


def layout(glyphs, width):
    result = []
    line = 0
    for paragraph in SPECIMEN:
        x = 0
        for word in paragraph.split(' '):
            text = word + ' '
            needed = sum(glyphs[ord(c)]['advance_pixels'] for c in text)
            if x and x + needed > width:
                line += 1
                x = 0
            for char in text:
                if x and x + glyphs[ord(char)]['advance_pixels'] > width:
                    line += 1
                    x = 0
                result.append({'code': ord(char), 'x': x, 'line': line})
                x += glyphs[ord(char)]['advance_pixels']
        line += 1
    return result, line


def compose(glyphs, placements, lines, points, width=240):
    line_height = (points * 4 + 2) // 3 + 6
    ascent = (points * 4 + 2) // 3 + 5
    mask = Image.new('L', (width + 12, lines * line_height + 14))
    for place in placements:
        glyph = glyphs[place['code']]['final']
        if not glyph['pixels']:
            continue
        patch = Image.frombytes('L', (glyph['width'], glyph['height']), bytes(glyph['pixels']))
        x = 6 + place['x'] + glyph['left']
        y = ascent + place['line'] * line_height + glyph['top']
        if x < 0 or y < 0 or x + patch.width > mask.width or y + patch.height > mask.height:
            raise RuntimeError('specimen exceeds its native crop')
        mask.paste(ImageChops.screen(mask.crop((x, y, x + patch.width, y + patch.height)), patch), (x, y))
    return mask


def export(record_path, output):
    record = json.loads(record_path.read_text())
    stock = record['libraries']['stock']
    provider = Path(stock['library']).resolve(strict=True)
    if sha(provider) != stock['sha256']:
        raise ValueError('stock FreeType hash differs from build record')
    for key, source in (('processor', 'src/fontreal_coverage.cpp'), ('declaration', 'src/fontreal_coverage.h')):
        if sha(ROOT / source) != record['spec'][key]:
            raise ValueError('coverage source differs from paired build record')
    probe, core = compile_tools()
    apply = processor(core)
    output.mkdir(parents=True, exist_ok=False)
    for name in ('gallery', 'masks', 'captures', 'crops'):
        (output / name).mkdir()
    env = dict(os.environ)
    env.pop('LD_PRELOAD', None)
    env.pop('FREETYPE_PROPERTIES', None)
    env['LD_LIBRARY_PATH'] = str(provider.parent)
    manifest = {'target_dpi': 96, 'points': list(range(8, 17)), 'fonts': [], 'methods': METHODS,
                'specimen': SPECIMEN, 'blend': 'encoded', 'placement': 'native whole-pixel advances',
                'record_sha256': sha(record_path), 'provider_sha256': sha(provider), 'cases': [], 'sheets': [],
                'sources': {p: sha(ROOT / p) for p in ('tools/supersampling.py', 'tests/supersampling_probe.cpp',
                           'tests/selected_mask_probe.cpp', 'src/fontreal_coverage.cpp', 'src/fontreal_coverage.h')}}
    for font_index, family in enumerate(FONTS):
        match = subprocess.check_output(['fc-match', '-f', '%{file}\n%{family}\n%{style}\n%{fontversion}\n',
                                         family + ':style=Regular'], text=True).splitlines()
        font = Path(match[0]).resolve(strict=True)
        if family not in match[1].split(','):
            raise ValueError(f'required font is not installed: {family}')
        label = ImageFont.truetype(str(font), 14)
        manifest['fonts'].append({'family': family, 'file': str(font), 'sha256': sha(font),
                                  'matched_family': match[1], 'style': match[2], 'revision': match[3]})
        font_cases = []
        for points in range(8, 17):
            capture = json.loads(subprocess.check_output([str(probe), str(font), str(points)], env=env))
            actual = Path(capture['provider']).resolve(strict=True)
            if actual != provider or sha(actual) != stock['sha256']:
                raise ValueError('probe loaded a different FreeType provider')
            capture_name = f'captures/{font_index}_{points}.json'
            write_json(output / capture_name, capture)
            modes = {c['mode']: c for c in capture['captures']}
            native = {g['code']: {**g, 'advance_pixels': int(g['advance'] + .5)}
                      for g in modes['native1']['glyphs']}
            placements, lines = layout(native, 240)
            case = {'font': font_index, 'points': points, 'capture': capture_name,
                    'capture_sha256': sha(output / capture_name), 'placements': placements, 'methods': []}
            for key, title, mode, kernel, corrected in METHODS:
                glyphs = []
                for glyph in modes[mode]['glyphs']:
                    reduced = reduce_mask(glyph, modes[mode]['scale'], kernel)
                    final = apply(reduced) if corrected else dict(reduced)
                    baseline = native[glyph['code']]
                    glyphs.append({'code': glyph['code'], 'advance_pixels': baseline['advance_pixels'],
                        'normalized_advance': glyph['advance'] / modes[mode]['scale'],
                        'pre_core': reduced, 'final': final,
                        'coverage_delta_native': sum(final['pixels']) - sum(baseline['pixels'])})
                mask_name = f'masks/{font_index}_{points}_{key}.json'
                write_json(output / mask_name, glyphs)
                rendered = compose({g['code']: g for g in glyphs}, placements, lines, points)
                treatment = {'key': key, 'mode': mode, 'kernel': kernel, 'corrected': corrected,
                             'masks': mask_name, 'masks_sha256': sha(output / mask_name), 'crops': {}}
                for polarity in ('light', 'dark'):
                    image = ImageChops.invert(rendered) if polarity == 'light' else rendered
                    crop_name = f'crops/{font_index}_{points}_{key}_{polarity}.png'
                    image.save(output / crop_name)
                    treatment['crops'][polarity] = {'file': crop_name, 'sha256': sha(output / crop_name),
                                                     'size': list(image.size)}
                case['methods'].append(treatment)
            manifest['cases'].append(case)
            font_cases.append(case)
        for start, end in ((8, 12), (13, 16)):
            group = [c for c in font_cases if start <= c['points'] <= end]
            heights = [Image.open(output / c['methods'][0]['crops']['light']['file']).height + 28 for c in group]
            for polarity in ('light', 'dark'):
                background, foreground = (255, 0) if polarity == 'light' else (0, 255)
                sheet = Image.new('L', (7 * 268 + 20, sum(heights) + 100), background)
                draw = ImageDraw.Draw(sheet)
                draw.text((12, 10), f'{family} Regular | {start}-{end}pt | 96 DPI | {polarity} background | View at 100%',
                          fill=foreground, font=label)
                draw.text((12, 33), 'Same target-size spacing. All samples below are native pixels. No installed renderer changes.',
                          fill=foreground, font=label)
                for col, (key, title, *_rest) in enumerate(METHODS):
                    draw.text((12 + col * 268, 65), f'{key}: {title}', fill=foreground, font=label)
                crops = []
                y = 98
                for case, height in zip(group, heights):
                    for col, treatment in enumerate(case['methods']):
                        x = 12 + col * 268
                        draw.text((x, y), f"{case['points']}pt", fill=foreground, font=label)
                        image = Image.open(output / treatment['crops'][polarity]['file'])
                        sheet.paste(image, (x, y + 23))
                        crops.append({'points': case['points'], 'method': treatment['key'],
                                      'box': [x, y + 23, x + image.width, y + 23 + image.height],
                                      'file': treatment['crops'][polarity]['file']})
                    y += height
                name = f'gallery/{font_index + 1}_{family.replace(" ", "-")}_{start}-{end}pt_{polarity}.png'
                sheet.save(output / name)
                manifest['sheets'].append({'file': name, 'sha256': sha(output / name), 'size': list(sheet.size),
                                           'font': font_index, 'polarity': polarity, 'crops': crops})
    write_json(output / 'manifest.json', manifest)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', required=True, type=Path, help='paired FreeType build.json')
    args = parser.parse_args()
    output = ROOT / 'results/supersampling' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    print(export(args.record.resolve(strict=True), output.resolve()))


if __name__ == '__main__':
    main()
