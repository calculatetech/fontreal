#!/usr/bin/env python3
"""Qualify conservative one-pixel bridges against native punctuation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
from browser_stroke_axis_test import Oracle
from neighbor_coverage_test import boost, repeat, self_check, sha

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'docs/images/browser-common-ground/raw-coverage-grid-captures.json'
OUT = ROOT/'results/bridge-coverage'
WORK = ROOT/'build/bridge-coverage'
MODES = ('accepted', 'lower', 'bridge')
TITLES = ('Connected / cutoff 173', 'Connected / cutoff 170', '170 + guarded bridge')
PUNCTUATION = ':;ij!.…'
FORM_CONTROLS = 'CcGgQO0(){}[]'


def neighbors(index, width, height):
    y, x = divmod(index, width)
    return {yy*width+xx for yy in range(max(0, y-1), min(height, y+2))
            for xx in range(max(0, x-1), min(width, x+2)) if (yy, xx) != (y, x)}


def components(pixels, width, height):
    remaining, result = set(pixels), []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        pending, group = [start], {start}
        while pending:
            following = neighbors(pending.pop(), width, height) & remaining
            remaining.difference_update(following)
            pending.extend(sorted(following))
            group.update(following)
        result.append(group)
    return result


def choose_bridges(data, width):
    assert isinstance(data, bytes) and width >= 0
    assert not data or width > 0 and len(data) % width == 0
    height = len(data)//width if width else 0
    core = {i for i, value in enumerate(data) if value >= 170}
    groups = components(core, width, height)
    labels = {i: label for label, group in enumerate(groups) for i in group}
    candidates, decisions = {}, {}
    for index, value in enumerate(data):
        if not 140 <= value < 170:
            continue
        ring = neighbors(index, width, height) & core
        local = components(ring, width, height)
        original_labels = {labels[i] for i in ring}
        reason = 'not_two_local_groups' if len(local) != 2 else 'different_original_components'
        if len(local) == 2 and len(original_labels) == 1:
            candidates[index] = next(iter(original_labels))
            reason = 'selected'
        decisions[index] = dict(value=value, local_groups=len(local),
                                original_components=sorted(original_labels), reason=reason)
    selected = set()
    for group in components(candidates, width, height):
        if len({candidates[i] for i in group}) == 1:
            selected.update(group)
        else:
            for i in group:
                decisions[i]['reason'] = 'adjacent_component_conflict'
    return selected, decisions


def transform(data, width):
    selected, decisions = choose_bridges(data, width)
    bridge_masks, runs = boost(data, width, minimum=170, bridges=selected)
    for run in runs:
        anchors = [data[i] for i in run['anchors']]
        if anchors:
            assert min(anchors) <= run['target'] <= max(anchors)
            assert all(bridge_masks['connected'][i] == run['target'] for i in run['pixels'])
    masks = dict(accepted=boost(data, width)[0]['connected'],
                 lower=boost(data, width, minimum=170)[0]['connected'],
                 bridge=bridge_masks['connected'])
    height = len(data)//width if width else 0
    before = components({i for i, v in enumerate(data) if v >= 170}, width, height)
    after = components({i for i, v in enumerate(masks['bridge']) if v >= 170}, width, height)
    labels = {i: label for label, group in enumerate(after) for i in group}
    assert len(before) == len(after)
    original_ids = []
    for group in before:
        group_ids = {labels[i] for i in group}
        assert len(group_ids) == 1
        original_ids.append(next(iter(group_ids)))
    assert len(set(original_ids)) == len(before)
    assert all((a > 0) == (b > 0) for a, b in zip(data, masks['bridge'], strict=True))
    assert all(a == b for i, (a, b) in enumerate(zip(data, masks['bridge'], strict=True))
               if a >= 230 or a < 170 and i not in selected)
    return masks, selected, decisions


def bridge_checks():
    self_check()
    loop = bytes([0,0,0,0,0, 0,0,140,230,230, 0,230,0,0,230,
                  230,0,0,230,230, 230,230,230,230,0])
    assert choose_bridges(loop, 5)[0] == {7}
    assert transform(loop, 5)[0]['bridge'][7] == 230
    colon = bytes([0,240,0, 0,240,0, 0,140,0, 0,240,0, 0,240,0])
    exclamation = bytes([0,240,0, 0,240,0, 0,240,0, 0,140,0, 0,240,0, 0,0,0])
    for data in (colon, exclamation):
        assert not choose_bridges(data, 3)[0]
        assert transform(data, 3)[0]['bridge'] == data
    horizontal = bytes(colon[y*3+x] for x in range(3) for y in range(5))
    assert not choose_bridges(horizontal, 5)[0]
    conflict = bytes([0]*6+[240,240,0,0,240,240]+[240,0,140,140,0,240]+
                     [240,240,0,0,240,240]+[0]*6)
    selected, decisions = choose_bridges(conflict, 6)
    assert not selected
    assert decisions[14]['reason'] == decisions[15]['reason'] == 'adjacent_component_conflict'
    transform(conflict, 6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('probe', 'library', 'stock-library', 'font', 'label-font'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    bridge_checks()
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE.read_text())
    assert sha(args.font) == source['font_sha256']
    assert sha(args.library) == source['library_sha256']
    assert sha(ROOT/'tests/raw_coverage_grid_test.py') == source['checker_sha256']
    glyphs = dict(source['glyphs'])
    env = {k: v for k, v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
           ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'FREETYPE_PROPERTIES', 'FT2_DEBUG')}
    env.update(LD_LIBRARY_PATH=str(args.library.resolve().parent), FONTREAL_FT_RENDERING='1',
               FONTREAL_FT_CONTRAST='raw', FONTREAL_FT_EXECUTABLE=str(args.probe.resolve()),
               FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')
    cases, masks, records = [], {}, {}
    oracle = Oracle(args.stock_library.resolve())
    try:
        for point in range(8, 17):
            size = (point*96+36)//72
            for char in PUNCTUATION+FORM_CONTROLS:
                target = WORK/f'{point}-{ord(char)}.json'
                subprocess.run([str(args.probe.resolve()), str(args.font.resolve()), str(size), '0x20028',
                                str(ord(char)), '0', '0', '0', '2', str(target), 'none', '0'],
                               env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                capture = json.loads(target.read_text())
                assert capture['glyph'] != 0
                glyph = capture['rendered'][0]
                assert glyph == capture['rendered'][1]
                assert glyph['pixel_mode'] == 2 and glyph['grays'] == 256
                assert oracle.raster(capture['loaded']) == {k: glyph[k] for k in ('width','height','left','top','mask')}
                data = bytes.fromhex(glyph['mask'])
                versions, selected, _ = transform(data, glyph['width'])
                cases.append(dict(point_size=point, logical_dpi=96, scale=1, native_size=size, character=char,
                                  source_mask_sha256=hashlib.sha256(data).hexdigest(), bridge_indices=sorted(selected),
                                  bridge_changes=sum(a != b for a,b in zip(versions['lower'], versions['bridge'], strict=True))))
                if point == 11:
                    assert size == 15
                    glyphs[char] = dict(width=glyph['width'], height=glyph['height'], left=glyph['left'], top=glyph['top'],
                                        advance=glyph['advance'], coverage=[list(data[y*glyph['width']:(y+1)*glyph['width']])
                                        for y in range(glyph['height'])])
    finally:
        oracle.close()
    expected = {(p,c) for p in range(8,17) for c in PUNCTUATION+FORM_CONTROLS}
    assert {(r['point_size'],r['character']) for r in cases} == expected
    assert len(cases) == len(expected)
    for char, glyph in glyphs.items():
        width, height = glyph['width'], glyph['height']
        data = bytes(a for row in glyph['coverage'] for a in row)
        masks[char], selected, decisions = transform(data, width)
        for new_width, spatial in (
            (width, lambda a: bytes(a[y*width+x] for y in range(height) for x in reversed(range(width)))),
            (width, lambda a: bytes(a[y*width+x] for y in reversed(range(height)) for x in range(width))),
            (height, lambda a: bytes(a[y*width+x] for x in range(width) for y in range(height)))):
            other = transform(spatial(data), new_width)[0]
            assert all(other[m] == spatial(masks[char][m]) for m in MODES)
        records[char] = dict(bridge_indices=sorted(selected), decisions=decisions, modes={m:dict(
            coverage=[list(masks[char][m][y*width:(y+1)*width]) for y in range(height)],
            new_changes=sum(a!=b for a,b in zip(masks[char]['accepted'],masks[char][m],strict=True))) for m in MODES})
    assert records['a']['bridge_indices'] == [23]
    assert masks['a']['lower'][23] == 140 and masks['a']['bridge'][23] >= 230
    assert masks['s']['accepted'][46] == 172 and masks['s']['lower'][46] >= 230
    assert not records['W']['bridge_indices'] and masks['W']['lower'] == masks['W']['bridge']
    label = ImageFont.truetype(str(args.label_font), 14)
    head = ImageFont.truetype(str(args.label_font), 19)

    def rgb(data, size, fg, bg):
        return Image.frombytes('RGB',size,bytes((b*(255-a)+f*a+127)//255 for a in data for f,b in zip(fg,bg)))

    def text_image(lines, mode, fg, bg, width=440, height=50):
        alpha=bytearray(width*height)
        independent=Image.new('RGBA',(width,height),(0,0,0,0))
        for row,text in enumerate(lines):
            x=0
            for char in text:
                if char==' ': x+=4; continue
                g=glyphs[char];xx=x+g['left'];yy=18+row*24-g['top'];data=masks[char][mode]
                assert xx>=0 and yy>=0 and xx+g['width']<=width and yy+g['height']<=height
                layer=Image.new('RGBA',(g['width'],g['height']),(0,0,0,0))
                layer.putalpha(Image.frombytes('L',layer.size,data));independent.alpha_composite(layer,(xx,yy))
                for i,a in enumerate(data):
                    at=(yy+i//g['width'])*width+xx+i%g['width'];alpha[at]=a+(alpha[at]*(255-a)+127)//255
                x+=(g['advance'][0]+32)//64
        assert independent.getchannel('A').tobytes()==bytes(alpha)
        return rgb(alpha,(width,height),fg,bg)

    preview=Image.new('RGB',(1440,750),(235,235,235));draw=ImageDraw.Draw(preview)
    draw.text((14,10),'Connected averages: cutoff 170 and a guarded one-pixel bridge',font=head,fill='black')
    draw.text((14,40),'Bridge range 140-169; original 230+ references. No letter-specific rules. No candidate installed.',font=label,fill='black')
    for col,title in enumerate(TITLES):draw.text((col*480+14,78),title,font=head,fill='black')
    crops=[]
    for row,(fg,bg) in enumerate((((255,)*3,(0,127,131)),((255,)*3,(0,)*3),((0,)*3,(255,)*3))):
        y=110+row*195;draw.rectangle((0,y,1439,y+189),fill=bg)
        for col,mode in enumerate(MODES):
            x=col*480+14;native=text_image(('soft safe sea  o s e a','V W : ; ! i j'),mode,fg,bg)
            detail_source=text_image(('aW:!',),mode,fg,bg,84,26);top,bottom=5,23
            for discarded in (detail_source.crop((0,0,84,top)),detail_source.crop((0,bottom,84,26))):
                assert discarded.tobytes()==bytes(bg)*(discarded.width*discarded.height)
            detail=repeat(detail_source.crop((0,top,84,bottom)),5)
            preview.paste(native,(x,y+12));preview.paste(detail,(x,y+72));crops.extend(((x,y+12,native),(x,y+72,detail)))
        draw.text((14,y+168),'Native text above; a W : ! at exact 5x below. Same geometry and placement in all columns.',font=label,fill=fg)
    draw.text((14,712),'A bridge must stay within one original core component. Separate marks are protected by connectivity.',font=label,fill='black')
    target=OUT/'bridge-coverage-preview.png';preview.save(target)
    with Image.open(target) as saved:
        for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
    images=[dict(file=target.name,sha256=sha(target))]
    for char in 'asW:!;':
        g=glyphs[char];width,height=g['width'],g['height'];cell=min(40,400//width,320//height)
        grid=Image.new('RGB',(1440,550),(24,)*3);draw=ImageDraw.Draw(grid)
        draw.text((14,10),f'{char}: orange borders mark changes versus the accepted 173 connected result',font=head,fill='white')
        number=ImageFont.truetype(str(args.label_font),12);samples=[]
        for col,(mode,title) in enumerate(zip(MODES,TITLES,strict=True)):
            x,y=col*480+34,145;draw.text((col*480+14,70),title,font=head,fill='white')
            draw.text((col*480+14,104),f"New changed pixels: {records[char]['modes'][mode]['new_changes']}",font=label,fill='white')
            for xx in range(width):draw.text((x+xx*cell+cell//2,y-12),str(xx+1),font=number,anchor='mm',fill='white')
            for yy in range(height):
                draw.text((x-14,y+yy*cell+cell//2),str(yy+1),font=number,anchor='mm',fill='white')
                for xx in range(width):
                    i=yy*width+xx;v=masks[char][mode][i];px,py=x+xx*cell,y+yy*cell
                    edge=(255,145,0) if v!=masks[char]['accepted'][i] else (80,)*3
                    draw.rectangle((px,py,px+cell-1,py+cell-1),fill=(v,)*3,outline=edge)
                    draw.text((px+cell//2,py+cell//2),str(v),font=number,anchor='mm',fill='black' if v>=128 else 'white')
                    samples.append((px+2,py+2,v))
        draw.text((14,515),'One cell = one native pixel. No new nonzero pixels. Original 230+ references remain unchanged.',font=label,fill='white')
        token=char if char.isalpha() else f'u{ord(char):04x}'
        target=OUT/f'bridge-coverage-{token}.png';grid.save(target)
        with Image.open(target) as saved:
            for x,y,v in samples:assert saved.getpixel((x,y))==(v,)*3
        images.append(dict(file=target.name,sha256=sha(target)))
    result=dict(source_file=SOURCE.name,source_sha256=sha(SOURCE),checker_sha256=sha(Path(__file__)),
                average_checker_sha256=sha(ROOT/'tests/neighbor_coverage_test.py'),font_sha256=sha(args.font),
                library_sha256=sha(args.library),stock_library_sha256=sha(args.stock_library),probe_sha256=sha(args.probe),
                main_minimum=170,bridge_minimum=140,anchor_minimum=230,glyphs=records,
                punctuation_cases=[r for r in cases if r['character'] in PUNCTUATION],
                form_cases=[r for r in cases if r['character'] in FORM_CONTROLS],images=images,
                limits=['One font; broader family and style qualification remains open',
                        'A disconnected main-stroke break is conservatively left unchanged',
                        'Punctuation checks prove these masks and sizes, not all fonts'])
    (OUT/'captures.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS loop/colon/exclamation/adjacent-bridge fixtures, spatial transforms, original component identities, native Oracle and saved pixels')
    print('Native cases',len(cases),'punctuation bridge hits',sum(len(c['bridge_indices']) for c in cases if c['character'] in PUNCTUATION))
    print('a 140 ->',masks['a']['bridge'][23],'; s 172 ->',masks['s']['lower'][46],'; W extra bridge changes 0')


if __name__=='__main__':
    main()
