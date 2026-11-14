#!/usr/bin/env python3
"""Replay curve strengths against tightly cropped, actual Firefox Home text."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
from browser_stroke_axis_test import Oracle

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT/'docs/images/browser-common-ground'
OUT = ROOT/'results/firefox-home-curves'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compose(case, glyphs):
    image = Image.open(SOURCES/case['source_image']).convert('RGB')
    width, height = image.size
    alpha = bytearray(width*height)
    independent = Image.new('RGBA', image.size, (0, 0, 0, 0))
    for origin, glyph in zip(case['origins'], glyphs, strict=True):
        x, y = origin['x']+glyph['left'], origin['y']-glyph['top']
        assert x >= 0 and y >= 0 and x+glyph['width'] <= width and y+glyph['height'] <= height
        data = bytes.fromhex(glyph['mask'])
        for i, value in enumerate(data):
            at = (y+i//glyph['width'])*width+x+i%glyph['width']
            alpha[at] = value+(alpha[at]*(255-value)+127)//255
        layer = Image.new('RGBA', (glyph['width'], glyph['height']), (0, 0, 0, 0))
        layer.putalpha(Image.frombytes('L', layer.size, data))
        independent.alpha_composite(layer, (x, y))
    assert independent.getchannel('A').tobytes() == bytes(alpha)
    pixels = bytes((background*(255-a)+foreground*a+127)//255
                   for a in alpha for background, foreground in zip(case['background'], case['foreground']))
    return Image.frombytes('RGB', image.size, pixels), alpha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--libraries', type=Path, nargs=3, required=True, metavar=('RAW', 'SMALL', 'LARGER'))
    parser.add_argument('--stock-library', type=Path, required=True)
    parser.add_argument('--label-font', type=Path, required=True)
    args = parser.parse_args()
    before = dict(os.environ)
    OUT.mkdir(parents=True, exist_ok=True)
    source = json.loads((SOURCES/'home-source-captures.json').read_text())
    for strength, library in zip((4, 8), args.libraries[1:], strict=True):
        folder = library.resolve().parents[2]
        record = json.loads((folder/'build.json').read_text())
        assert record['inputs']['strength'] == strength
        assert record['inputs']['patch_sha256'] == sha(ROOT/'patches/freetype-2.14.2-segment-y-experiment.patch')
        assert record['library_sha256'] == sha(library)
        assert record['source_sha256'] == sha(folder/'source/src/autofit/aflatin.c')
    installed = [Path(p) for p in subprocess.check_output(['fc-list', '-f', '%{file}\n'], text=True).splitlines()]
    env = {k: v for k, v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
           ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'FREETYPE_PROPERTIES', 'FT2_DEBUG')}
    env.update(FONTREAL_FT_RENDERING='1', FONTREAL_FT_CONTRAST='raw',
               FONTREAL_FT_EXECUTABLE=str(args.probe.resolve()), FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')
    oracle = Oracle(args.stock_library.resolve())
    records, panels = [], []
    for case in source['cases']:
        assert sha(SOURCES/case['source_image']) == case['source_image_sha256']
        matches = [p for p in installed if p.name == case['font_file'] and sha(p) == case['font_sha256']]
        assert matches, case['font_file']
        font = matches[0]
        actual = Image.open(SOURCES/case['source_image']).convert('RGB')
        images, modes = [actual], []
        baseline = None
        for mode, library in zip(('raw', 'small', 'larger'), args.libraries, strict=True):
            glyphs = []
            child_env = dict(env, LD_LIBRARY_PATH=str(library.resolve().parent))
            for index, origin in enumerate(case['origins']):
                target = OUT/f'{case["id"]}-{mode}-{index}.json'
                subprocess.run([str(args.probe.resolve()), str(font), str(case['native_size']), '0x20028',
                                str(ord(origin['char'])), '0', '0', '0', '2', str(target), 'none', '0'],
                               env=child_env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                capture = json.loads(target.read_text())
                assert capture['rendered'][0] == capture['rendered'][1]
                glyph = dict(capture['rendered'][0], outline=capture['loaded']['outline'])
                assert oracle.raster(capture['loaded']) == {k: glyph[k] for k in ('width', 'height', 'left', 'top', 'mask')}
                glyphs.append(glyph)
            image, alpha = compose(case, glyphs)
            if baseline is None:
                baseline = glyphs
                errors = [abs(a-b) for a, b in zip(actual.tobytes(), image.tobytes(), strict=True)]
                assert max(errors) <= 1
                error = dict(maximum_channel_error=max(errors), mean_channel_error=sum(errors)/len(errors))
                for origin, glyph in zip(case['origins'], glyphs, strict=True):
                    x, y = origin['x']+glyph['left'], origin['y']-glyph['top']
                    expected = bytes((bg*(255-a)+fg*a+127)//255 for a in bytes.fromhex(glyph['mask'])
                                     for bg, fg in zip(case['background'], case['foreground']))
                    captured = actual.crop((x, y, x+glyph['width'], y+glyph['height'])).tobytes()
                    assert max(abs(a-b) for a, b in zip(expected, captured, strict=True)) <= 1
                error['matched_nonempty_occurrences'] = len(glyphs)
                # A wrong comparison size must fail against this same real-world crop.
                target = OUT/f'{case["id"]}-wrong-size.json'
                subprocess.run([str(args.probe.resolve()), str(font), '16' if case['id'] == 'caption' else '13',
                                '0x20028', str(ord(case['origins'][0]['char'])), '0', '0', '0', '2', str(target), 'none', '0'],
                               env=child_env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                wrong = json.loads(target.read_text())['rendered'][0]
                assert wrong != glyphs[0]
                origin = case['origins'][0]
                x, y = origin['x']+wrong['left'], origin['y']-wrong['top']
                wrong_pixels = bytes((bg*(255-a)+fg*a+127)//255 for a in bytes.fromhex(wrong['mask'])
                                     for bg, fg in zip(case['background'], case['foreground']))
                source_pixels = actual.crop((x, y, x+wrong['width'], y+wrong['height'])).tobytes()
                error['wrong_size_maximum_channel_error'] = max(abs(a-b) for a, b in zip(source_pixels, wrong_pixels, strict=True))
                assert error['wrong_size_maximum_channel_error'] > 20
                def decode(c):
                    value = c/255
                    return value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4
                def encode(v):
                    return round(255*(12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055))
                linear = bytes(encode(decode(bg)*(1-a/255)+decode(fg)*(a/255))
                               for a in alpha for bg, fg in zip(case['background'], case['foreground']))
                error['linear_blend_maximum_channel_error'] = max(abs(a-b) for a, b in zip(actual.tobytes(), linear, strict=True))
                assert error['linear_blend_maximum_channel_error'] > 20
            else:
                assert all([p[0] for p in a['outline']] == [p[0] for p in b['outline']]
                           for a, b in zip(glyphs, baseline, strict=True))
            file = f'home-{case["id"]}-{mode}.png'
            image.save(OUT/file)
            images.append(image)
            modes.append(dict(mode=mode, file=file, sha256=sha(OUT/file)))
        panels.append((case, images))
        records.append(dict(case=case['id'], baseline_error=error, images=modes))
    oracle.close()
    label = ImageFont.truetype(str(args.label_font), 14)
    head = ImageFont.truetype(str(args.label_font), 18)
    sheet = Image.new('RGB', (1720, 440), tuple(source['cases'][0]['background']))
    draw = ImageDraw.Draw(sheet)
    color = tuple(source['cases'][0]['foreground'])
    draw.text((12, 10), 'Firefox Home: actual text and matched curve-width trials', font=head, fill=color)
    draw.text((12, 38), 'Same font files, native sizes, measured colors and glyph origins. Raw coverage and encoded blending.', font=label, fill=color)
    for col, title in enumerate(('Actual Firefox Home crop', 'Matched native raw', 'Raw + curve 1/16 pixel', 'Raw + curve 1/8 pixel')):
        draw.text((col*430+12, 76), title, font=head, fill=color)
    crops = []
    for row, (case, images) in enumerate(panels):
        y = 112+row*150
        draw.text((12, y), case['label'], font=label, fill=color)
        for col, image in enumerate(images):
            x = col*430+12
            sheet.paste(image, (x, y+25))
            zoom = image.resize((image.width*3, image.height*3), Image.Resampling.NEAREST)
            sheet.paste(zoom, (x, y+60))
            crops.extend([(x, y+25, image), (x, y+60, zoom)])
    draw.text((12, 416), 'Top in each row: native pixels. Below: exact 3x detail. No curve treatment installed.', font=label, fill=color)
    target = OUT/'firefox-home-curves.png'
    sheet.save(target)
    with Image.open(target) as saved:
        for x, y, image in crops:
            assert saved.crop((x, y, x+image.width, y+image.height)).tobytes() == image.tobytes()
    assert os.environ == before
    result = dict(kind='Actual Firefox Home matched before curve comparison', cases=records,
                  source_sha256=sha(SOURCES/'home-source-captures.json'), checker_sha256=sha(Path(__file__)),
                  libraries=[sha(p) for p in args.libraries], stock_library_sha256=sha(args.stock_library),
                  image=dict(file=target.name, sha256=sha(target)),
                  limits=['Two measured Home text runs, not all application text',
                          'Matched baseline allows one RGB quantization level',
                          'Curve trials change geometry; visual edge quality remains unselected'])
    (OUT/'captures.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS actual Home baseline, 22 occurrences x3, native rasters, raw composition and saved crops', records)


if __name__ == '__main__':
    main()
