#!/usr/bin/env python3
"""Expose unchanged native glyph coverage as numbered pixel grids."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
from browser_stroke_axis_test import Oracle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/raw-coverage-grids'
WORK = ROOT / 'build/raw-coverage-grids'
GROUPS = {'curves': 'osea', 'stems': 'ft', 'diagonals': 'VW'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('probe', 'library', 'stock-library', 'font', 'label-font'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    original_env = dict(os.environ)
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
           ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'FREETYPE_PROPERTIES', 'FT2_DEBUG')}
    env.update(LD_LIBRARY_PATH=str(args.library.resolve().parent), FONTREAL_FT_RENDERING='1',
               FONTREAL_FT_CONTRAST='raw', FONTREAL_FT_EXECUTABLE=str(args.probe.resolve()),
               FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')
    oracle = Oracle(args.stock_library.resolve())
    glyphs = {}
    try:
        for char in 'oseaftVW':
            target = WORK / f'{ord(char)}.json'
            subprocess.run([str(args.probe.resolve()), str(args.font.resolve()), '15', '0x20028',
                            str(ord(char)), '0', '0', '0', '2', str(target), 'none', '0'],
                           env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            capture = json.loads(target.read_text())
            glyph = capture['rendered'][0]
            assert glyph == capture['rendered'][1]
            assert oracle.raster(capture['loaded']) == {k: glyph[k] for k in ('width', 'height', 'left', 'top', 'mask')}
            assert glyph['pixel_mode'] == 2 and glyph['grays'] == 256
            assert glyph['width'] > 0 and glyph['height'] > 0
            assert len(bytes.fromhex(glyph['mask'])) == glyph['width'] * glyph['height']
            glyphs[char] = glyph
    finally:
        oracle.close()
    assert set(glyphs) == set('oseaftVW') and len(glyphs) == 8
    font = ImageFont.truetype(str(args.label_font), 14)
    head = ImageFont.truetype(str(args.label_font), 19)
    records, images = {}, []
    for group, characters in GROUPS.items():
        cell = 40
        sheet = Image.new('RGB', (1440, 660), (24, 24, 24))
        column_width = sheet.width // len(characters)
        draw = ImageDraw.Draw(sheet)
        draw.text((14, 10), f'{args.font.name}: raw coverage / {group}', font=head, fill='white')
        draw.text((14, 39), '0 = empty; 255 = fully covered. Every numbered cell is one native pixel. No coverage adjustment.', font=font, fill='white')
        draw.text((14, 62), 'Native masks follow current nearest hinting at the measured 15-device-unit condition.', font=font, fill='white')
        samples, natives = [], []
        for column, char in enumerate(characters):
            glyph = glyphs[char]
            width, height = glyph['width'], glyph['height']
            data = bytes.fromhex(glyph['mask'])
            x, y = column * column_width + 34, 153
            assert x + width * cell <= (column+1)*column_width - 8 and y + height * cell <= 615
            number = ImageFont.truetype(str(args.label_font), 12)
            draw.text((column * column_width + 14, 100), char + ' / native:', font=head, fill='white')
            native = Image.frombytes('L', (width, height), data).convert('RGB')
            teal = Image.frombytes('RGB', (width, height), bytes(
                (background * (255-a) + 255*a + 127)//255 for a in data for background in (0, 127, 131)))
            for nx, image in ((column * column_width + 160, native), (column * column_width + 205, teal)):
                sheet.paste(image, (nx, 104))
                natives.append((nx, 104, image))
            values = [list(data[row*width:(row+1)*width]) for row in range(height)]
            records[char] = dict(width=width, height=height, left=glyph['left'], top=glyph['top'],
                                 coverage=values, mask_sha256=hashlib.sha256(data).hexdigest())
            for col in range(width):
                draw.text((x+col*cell+cell//2, y-12), str(col+1), font=number, anchor='mm', fill='white')
            for row in range(height):
                draw.text((x-14, y+row*cell+cell//2), str(row+1), font=number, anchor='mm', fill='white')
                for col in range(width):
                    a = values[row][col]
                    xx, yy = x+col*cell, y+row*cell
                    draw.rectangle((xx, yy, xx+cell-1, yy+cell-1), fill=(a,)*3, outline=(80,)*3)
                    draw.text((xx+cell//2, yy+cell//2), str(a), font=number, anchor='mm',
                              fill='black' if a >= 128 else 'white')
                    samples.append((xx+2, yy+2, a))
        draw.text((14, 630), 'Rows run top to bottom. Grayscale cells show coverage, with exact values printed inside.', font=font, fill='white')
        target = OUT / f'raw-coverage-{group}.png'
        sheet.save(target)
        with Image.open(target) as saved:
            for x, y, value in samples:
                assert saved.getpixel((x, y)) == (value,)*3
            for x, y, native in natives:
                assert saved.crop((x, y, x+native.width, y+native.height)).tobytes() == native.tobytes()
        images.append(dict(file=target.name, sha256=sha(target), native_pixels=len(samples)))
    assert set(records) == set(glyphs)
    result = dict(kind='Unadjusted native coverage values, not a selected filter', native_size=15,
                  font_file=args.font.name, font_sha256=sha(args.font),
                  library_sha256=sha(args.library), stock_library_sha256=sha(args.stock_library),
                  probe_sha256=sha(args.probe),
                  checker_sha256=sha(Path(__file__)), glyphs=records, images=images,
                  limits=['One font and measured size', 'Cell intensity represents coverage, not physical display luminance',
                          'Coverage alone does not classify stroke cores or curved boundaries'])
    (OUT/'captures.json').write_text(json.dumps(result, indent=2)+'\n')
    assert os.environ == original_env
    print('PASS eight native rasters/repeats, every coverage cell, native crops and portable metadata')


if __name__ == '__main__':
    main()
