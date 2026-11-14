#!/usr/bin/env python3
"""Compare original strong-neighbor averages on verified native masks."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/images/browser-common-ground/raw-coverage-grid-captures.json'
OUT = ROOT / 'results/neighbor-coverage'
MODES = ('raw', 'nearby', 'connected')
TITLES = ('Current raw', 'Direct strong neighbors', 'Connected weak run')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def boost(data, width):
    assert isinstance(data, bytes) and width >= 0
    assert not data or width > 0 and len(data) % width == 0
    height = len(data) // width if width else 0

    def neighbors(index):
        y, x = divmod(index, width)
        return {yy*width+xx for yy in range(max(0, y-1), min(height, y+2))
                for xx in range(max(0, x-1), min(width, x+2)) if (yy, xx) != (y, x)}

    def mean(anchors):
        return (2*sum(data[i] for i in anchors)+len(anchors)) // (2*len(anchors))

    weak = {i for i, value in enumerate(data) if 173 <= value < 230}
    nearby, connected, components = bytearray(data), bytearray(data), []
    while weak:
        start = min(weak)
        weak.remove(start)
        pending, pixels, anchors = [start], {start}, set()
        while pending:
            index = pending.pop()
            adjacent = neighbors(index)
            strong = {i for i in adjacent if data[i] >= 230}
            if strong:
                nearby[index] = mean(strong)
            anchors.update(strong)
            following = adjacent & weak
            weak.difference_update(following)
            pixels.update(following)
            pending.extend(sorted(following))
        target = mean(anchors) if anchors else None
        if target is not None:
            for index in pixels:
                connected[index] = target
        components.append(dict(pixels=sorted(pixels), anchors=sorted(anchors), target=target))
    result = dict(raw=data, nearby=bytes(nearby), connected=bytes(connected))
    for mode in MODES:
        assert len(result[mode]) == len(data)
        for before, after in zip(data, result[mode], strict=True):
            assert before == after or 173 <= before < 230 <= after <= 255
    return result, components


def self_check():
    assert boost(b'', 0)[0] == dict.fromkeys(MODES, b'')
    try:
        boost(bytes([200]), 0)
    except AssertionError:
        pass
    else:
        raise AssertionError('nonempty mask with zero width accepted')
    result, _ = boost(bytes([172, 173, 229, 230, 255]), 5)
    assert list(result['nearby']) == [172, 173, 230, 230, 255]
    assert list(result['connected']) == [172, 230, 230, 230, 255]
    result, _ = boost(bytes([240, 173, 180, 229, 250]), 5)
    assert list(result['nearby']) == [240, 240, 180, 250, 250]
    assert list(result['connected']) == [240, 245, 245, 245, 250]
    assert boost(result['connected'], 5)[0]['connected'] == result['connected']
    for data, width in ((bytes([173, 200, 229]), 3), (bytes([0, 0, 240, 173, 0, 0]), 3)):
        assert all(value == data for value in boost(data, width)[0].values())
    assert boost(bytes([240, 0, 0, 173]), 2)[0]['connected'] == bytes([240, 0, 0, 240])
    result, components = boost(bytes([240, 173, 250, 173, 173, 0]), 3)
    assert result['connected'] == bytes([240, 245, 250, 245, 245, 0])
    assert components[0]['anchors'] == [0, 2]
    assert boost(bytes([230, 229, 231]), 3)[0]['connected'][1] == 231
    # Two treated occurrences differ from treatment after their overlap.
    overlap = lambda data: bytes(a+(a*(255-a)+127)//255 for a in data)
    raw = bytes([250, 200, 250])
    assert overlap(boost(raw, 3)[0]['connected'])[1] == 255
    assert boost(overlap(raw), 3)[0]['connected'][1] == 243


def repeat(image, factor):
    data, stride = image.tobytes(), image.width*3
    rows = [b''.join(data[i:i+3]*factor for i in range(y*stride, (y+1)*stride, 3))
            for y in range(image.height)]
    return Image.frombytes('RGB', (image.width*factor, image.height*factor), b''.join(row*factor for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label-font', type=Path, required=True)
    args = parser.parse_args()
    self_check()
    OUT.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE.read_text())
    assert sha(ROOT/'tests/raw_coverage_grid_test.py') == source['checker_sha256']
    glyphs = source['glyphs']
    assert set(glyphs) == set('oseaftVW')
    masks, records = {}, {}
    for char, glyph in glyphs.items():
        data = bytes(a for row in glyph['coverage'] for a in row)
        width, height = glyph['width'], glyph['height']
        assert len(glyph['coverage']) == height and all(len(row) == width for row in glyph['coverage'])
        assert hashlib.sha256(data).hexdigest() == glyph['mask_sha256']
        masks[char], components = boost(data, width)
        assert boost(masks[char]['connected'], width)[0]['connected'] == masks[char]['connected']
        for component in components:
            anchors = [data[i] for i in component['anchors']]
            if anchors:
                assert min(anchors) <= component['target'] <= max(anchors)
        # Spatial transforms catch traversal dependence and accidental row wrapping.
        transforms = ((width, lambda a: bytes(a[y*width+x] for y in range(height) for x in reversed(range(width)))),
                      (width, lambda a: bytes(a[y*width+x] for y in reversed(range(height)) for x in range(width))),
                      (height, lambda a: bytes(a[y*width+x] for x in range(width) for y in range(height))))
        for new_width, transform in transforms:
            transformed, _ = boost(transform(data), new_width)
            assert all(transformed[mode] == transform(masks[char][mode]) for mode in MODES)
        records[char] = dict(components=components, modes={mode: dict(
            changed_pixels=sum(a != b for a, b in zip(data, masks[char][mode], strict=True)),
            coverage=[list(masks[char][mode][y*width:(y+1)*width]) for y in range(height)],
            mask_sha256=hashlib.sha256(masks[char][mode]).hexdigest()) for mode in MODES})

    def encoded(data, size, foreground, background):
        return Image.frombytes('RGB', size, bytes((b*(255-a)+f*a+127)//255
                                                for a in data for f, b in zip(foreground, background)))

    def compose(lines, mode, foreground, background, width=440, height=48):
        alpha = bytearray(width*height)
        independent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        for row, text in enumerate(lines):
            x = 0
            for char in text:
                if char == ' ':
                    x += 4
                    continue
                glyph = glyphs[char]
                xx, yy = x+glyph['left'], 18+row*24-glyph['top']
                data = masks[char][mode]
                assert xx >= 0 and yy >= 0 and xx+glyph['width'] <= width and yy+glyph['height'] <= height
                layer = Image.new('RGBA', (glyph['width'], glyph['height']), (0, 0, 0, 0))
                layer.putalpha(Image.frombytes('L', layer.size, data))
                independent.alpha_composite(layer, (xx, yy))
                for i, value in enumerate(data):
                    at = (yy+i//glyph['width'])*width+xx+i%glyph['width']
                    alpha[at] = value+(alpha[at]*(255-value)+127)//255
                x += (glyph['advance'][0]+32)//64
        assert independent.getchannel('A').tobytes() == bytes(alpha)
        return encoded(alpha, (width, height), foreground, background)

    font = ImageFont.truetype(str(args.label_font), 14)
    head = ImageFont.truetype(str(args.label_font), 19)
    images = []
    preview = Image.new('RGB', (1440, 750), (235, 235, 235))
    draw = ImageDraw.Draw(preview)
    draw.text((14, 10), 'Nimbus Sans: average original strong pixels, without changing low-coverage edges', font=head, fill='black')
    draw.text((14, 40), 'Eligible 173-229; references 230-255. Measured native size 15. No candidate installed.', font=font, fill='black')
    for col, title in enumerate(TITLES):
        draw.text((col*480+14, 78), title, font=head, fill='black')
    crops = []
    for row, (name, foreground, background) in enumerate((
            ('Captured colors: white on teal', (255, 255, 255), (0, 127, 131)),
            ('White on black', (255, 255, 255), (0, 0, 0)),
            ('Black on white', (0, 0, 0), (255, 255, 255)))):
        y = 110+row*195
        draw.rectangle((0, y, 1439, y+189), fill=background)
        draw.text((14, y+5), name, font=font, fill=foreground)
        for col, mode in enumerate(MODES):
            x = col*480+14
            native = compose(('soft safe sea  o s e a', 'ftft   V W'), mode, foreground, background)
            detail_source = compose(('oseaVW',), mode, foreground, background, 84, 24)
            top, bottom = 6, 22
            for discarded in (detail_source.crop((0, 0, 84, top)), detail_source.crop((0, bottom, 84, 24))):
                assert discarded.tobytes() == bytes(background)*(discarded.width*discarded.height)
            detail = repeat(detail_source.crop((0, top, 84, bottom)), 5)
            preview.paste(native, (x, y+30))
            preview.paste(detail, (x, y+85))
            crops.extend(((x, y+30, native), (x, y+85, detail)))
        draw.text((14, y+168), 'Native text above; o s e a V W at exact 5x below. Shared glyph advances and comparison spacing.', font=font, fill=foreground)
    draw.text((14, 712), 'All values below 173 and at/above 230 stay unchanged. Connected averages solve gaps but also change diagonals.', font=font, fill='black')
    target = OUT/'neighbor-coverage-preview.png'
    preview.save(target)
    with Image.open(target) as saved:
        for x, y, crop in crops:
            assert saved.crop((x, y, x+crop.width, y+crop.height)).tobytes() == crop.tobytes()
    images.append(dict(file=target.name, sha256=sha(target)))
    for char, glyph in glyphs.items():
        width, height = glyph['width'], glyph['height']
        cell = min(40, 400//width, 320//height)
        grid = Image.new('RGB', (1440, 550), (24, 24, 24))
        draw = ImageDraw.Draw(grid)
        draw.text((14, 10), f'{char}: original strong-neighbor references / orange borders mark changed pixels', font=head, fill='white')
        draw.text((14, 40), 'Original 173-229 pixels are eligible. Original 230+ pixels supply the mean and remain unchanged.', font=font, fill='white')
        number = ImageFont.truetype(str(args.label_font), 12)
        samples = []
        for col, (mode, title) in enumerate(zip(MODES, TITLES, strict=True)):
            x, y = col*480+34, 145
            draw.text((col*480+14, 78), title, font=head, fill='white')
            draw.text((col*480+14, 108), f"Changed pixels: {records[char]['modes'][mode]['changed_pixels']}", font=font, fill='white')
            values = masks[char][mode]
            for xx in range(width):
                draw.text((x+xx*cell+cell//2, y-12), str(xx+1), font=number, anchor='mm', fill='white')
            for yy in range(height):
                draw.text((x-14, y+yy*cell+cell//2), str(yy+1), font=number, anchor='mm', fill='white')
                for xx in range(width):
                    index = yy*width+xx
                    value = values[index]
                    px, py = x+xx*cell, y+yy*cell
                    edge = (255, 145, 0) if value != masks[char]['raw'][index] else (80,)*3
                    draw.rectangle((px, py, px+cell-1, py+cell-1), fill=(value,)*3, outline=edge)
                    draw.text((px+cell//2, py+cell//2), str(value), font=number, anchor='mm', fill='black' if value >= 128 else 'white')
                    samples.append((px+2, py+2, value))
        draw.text((14, 515), 'One cell = one native pixel. No outline, hinting or placement changes. No new pixels are added.', font=font, fill='white')
        target = OUT/f'neighbor-coverage-{char}.png'
        grid.save(target)
        with Image.open(target) as saved:
            for x, y, value in samples:
                assert saved.getpixel((x, y)) == (value,)*3
        images.append(dict(file=target.name, sha256=sha(target)))
    result = dict(kind='Scientific strong-neighbor coverage comparison, not an installed profile',
                  source_file=SOURCE.name, source_sha256=sha(SOURCE), checker_sha256=sha(Path(__file__)),
                  eligible_minimum=173, original_anchor_minimum=230, connectivity=8,
                  rounding='Nearest integer, halves upward', glyphs=records, images=images,
                  limits=['One font and measured size; broad qualification follows visual acceptance',
                          'Diagonal pixels within the eligible range also change',
                          'Eight-connectivity can combine touching weak branches',
                          'An anchorless weak group stays unchanged'])
    (OUT/'captures.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS synthetic gaps, thresholds, unique anchors, spatial invariance, unchanged ranges, two compositors and saved pixels')
    print('Connected changed pixels:', {char: records[char]['modes']['connected']['changed_pixels'] for char in glyphs})


if __name__ == '__main__':
    main()
