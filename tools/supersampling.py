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


def decode_bitmap(glyph):
    bitmap = glyph['bitmap']
    width, height, mode = bitmap['width'], bitmap['rows'], bitmap['pixel_mode']
    stride = abs(bitmap['pitch'])
    raw = bytes.fromhex(bitmap['rows_hex'])
    if len(raw) != stride * height:
        raise ValueError('raw bitmap length does not match its pitch')
    if mode not in (1, 2):
        raise ValueError(f'unsupported stock pixel mode: {mode}')
    pixels = [
        (255 if raw[y * stride + x // 8] & (128 >> (x % 8)) else 0)
        if mode == 1 else raw[y * stride + x]
        for y in range(height) for x in range(width)
    ]
    return {'left': glyph['left'], 'top': glyph['top'], 'width': width, 'height': height, 'pixels': pixels}


def stock_methods(capture):
    methods = list(METHODS[:2])
    for source in capture['captures'][4:]:
        mode = source['mode']
        base, state = mode.rsplit('_dark_', 1)
        title = '4x ' + base.replace('_source', '').replace('_', ' ')
        if base.startswith('tt'):
            title += ' (TT only)'
        if base == 'cff_old_gray':
            title += ' (CFF only)'
        methods.append((mode, title + '\nStem ' + state, mode, 'area', False))
    return methods


def stock_sheets(output, manifest, case, family, label):
    methods = {m['key']: m for m in case['methods']}
    bases = ['native_normal_gray', 'auto_normal_gray', 'native_light_gray', 'auto_light_gray',
             'native_mono_gray', 'auto_mono_gray', 'off_gray', 'off_mono_source',
             'native_mono_source', 'auto_mono_source', 'tt35_gray', 'tt35_mono_source',
             'tt38_gray', 'tt38_mono_source', 'cff_old_gray']
    bases = [base for base in bases if base + '_dark_off' in methods]
    panels = [
        ('4x ' + ' / '.join(base.replace('_source', '').replace('_', ' ') for base in bases[start:start + 2]),
         ['A', 'B'] + [base + '_dark_' + state for base in bases[start:start + 2] for state in ('off', 'on')])
        for start in range(0, len(bases), 2)
    ]
    crop_height = Image.open(output / case['methods'][0]['crops']['light']['file']).height
    panel_height = crop_height + 88
    for polarity in ('light', 'dark'):
        bg, fg = (255, 0) if polarity == 'light' else (0, 255)
        sheet = Image.new('L', (1628, 96 + panel_height * len(panels)), bg)
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 10), f'{family} Regular | {case["points"]}pt | stock 4x to 96 DPI | {polarity} background',
                  font=label, fill=fg)
        draw.text((12, 32), 'View at 100%. Scroll panels; arrows change condition. All 4x rows are untreated. Encoded blend.',
                  font=label, fill=fg)
        draw.text((12, 54), 'Stem darkening applies to auto-hinting and Adobe CFF. Native TrueType and large strokes can be unchanged.',
                  font=label, fill=fg)
        crops = []
        for panel, (title, keys) in enumerate(panels):
            y = 96 + panel * panel_height
            draw.text((12, y), title, font=label, fill=fg)
            for column, key in enumerate(keys):
                x = 12 + column * 268
                treatment = methods[key]
                draw.multiline_text((x, y + 23), treatment['title'], font=label, fill=fg, spacing=1)
                image = Image.open(output / treatment['crops'][polarity]['file'])
                sheet.paste(image, (x, y + 65))
                crops.append({'panel': panel, 'method': key, 'box': [x, y + 65, x + image.width, y + 65 + image.height],
                              'file': treatment['crops'][polarity]['file']})
        name = f'gallery/{case["font"] + 1}_{family.replace(" ", "-")}_{case["points"]:02}pt_{polarity}.png'
        sheet.save(output / name)
        manifest['sheets'].append({'file': name, 'sha256': sha(output / name), 'size': list(sheet.size),
            'font': case['font'], 'points': case['points'], 'polarity': polarity,
            'panels': [{'title': title, 'methods': keys} for title, keys in panels], 'crops': crops})


def export(record_path, output, stock4x=False):
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
    if stock4x:
        manifest['study'] = 'stock4x'
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
            command = [str(probe), str(font), str(points)] + (['--stock4x'] if stock4x else [])
            capture = json.loads(subprocess.check_output(command, env=env))
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
            definitions = stock_methods(capture) if stock4x else METHODS
            if stock4x:
                manifest['methods'] = definitions
                case['capabilities'] = capture['capabilities']
            for key, title, mode, kernel, corrected in definitions:
                glyphs = []
                for glyph in modes[mode]['glyphs']:
                    source = decode_bitmap(glyph) if 'bitmap' in glyph else glyph
                    reduced = reduce_mask(source, modes[mode]['scale'], kernel)
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
                if stock4x:
                    treatment.update(title=title)
                    if key not in ('A', 'B'):
                        treatment['stem_darkening'] = modes[mode]['stem_darkening']
                for polarity in ('light', 'dark'):
                    image = ImageChops.invert(rendered) if polarity == 'light' else rendered
                    crop_name = f'crops/{font_index}_{points}_{key}_{polarity}.png'
                    image.save(output / crop_name)
                    treatment['crops'][polarity] = {'file': crop_name, 'sha256': sha(output / crop_name),
                                                     'size': list(image.size)}
                case['methods'].append(treatment)
            manifest['cases'].append(case)
            font_cases.append(case)
            if stock4x:
                stock_sheets(output, manifest, case, family, label)
        if stock4x:
            continue
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
    parser.add_argument('--stock4x', action='store_true', help='compare scalar stock hinting and stem darkening at 4x')
    args = parser.parse_args()
    output = ROOT / 'results/supersampling' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    print(export(args.record.resolve(strict=True), output.resolve(), args.stock4x))


if __name__ == '__main__':
    main()
