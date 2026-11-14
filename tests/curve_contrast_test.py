#!/usr/bin/env python3
"""Verify the fixed rounded-Y experiment from four native point-chart exports."""
import argparse
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, ImageChops, ImageDraw, ImageFont

from browser_stroke_axis_test import Oracle

ROOT = Path(__file__).resolve().parents[1]
TEXT = 'ilI1 minimum 0358 VvWw 0123456789'
POINTS = (8, 9, 10, 11, 11.25, 12, 13, 14, 15, 16)
FACES = [f'{family} {style}' for family in ('Noto Sans', 'Noto Serif', 'Hack')
         for style in ('Regular', 'Bold', 'Italic', 'BoldItalic')] + ['Lato Light']
FOLDERS = ('75', '50', 'round', 'qt')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blend_table(dark):
    with localcontext() as ctx:
        ctx.prec = 36
        values = []
        for alpha in range(256):
            linear = Decimal(alpha if dark else 255 - alpha) / 255
            encoded = linear * Decimal('12.92') if linear <= Decimal('0.0031308') else \
                Decimal('1.055') * linear ** (Decimal(1) / Decimal('2.4')) - Decimal('0.055')
            values.append(int((encoded * 255).quantize(Decimal(1), rounding=ROUND_HALF_UP)))
        return values


def compose(glyphs, height, cutoff, table=None):
    canvas = Image.new('RGBA', (620, height))
    for glyph in glyphs:
        w, h = glyph['width'], glyph['height']
        raw = bytes.fromhex(glyph['mask'])
        assert len(raw) == w * h
        assert 0 <= glyph['x'] <= 620 - w and 0 <= glyph['y'] <= height - h
        if not w or not h:
            continue
        treated = bytes(table[a] if table is not None else 242 if cutoff <= a < 242 else a for a in raw)
        overlay = Image.new('RGBA', (w, h))
        overlay.putalpha(Image.frombytes('L', (w, h), treated))
        canvas.alpha_composite(overlay, (glyph['x'], glyph['y']))
    return canvas.getchannel('A')


def profile(glyph):
    w, h = glyph['width'], glyph['height']
    raw = bytes.fromhex(glyph['mask'])
    return dict(ink=sum(raw) / 255, left=glyph['left'], top=glyph['top'],
                center_x=glyph['left'] + w // 2,
                center_column=list(raw[w // 2::w]) if w else [],
                row_ink=[sum(raw[y*w:(y+1)*w]) for y in range(h)],
                first_row=list(raw[:w]))


def segment_decisions(trace):
    decisions, current, segments = [], None, []
    for line in trace.splitlines():
        if line.startswith('FR_PAIR_BEGIN '):
            assert current is None
            current = dict((k, int(v)) for k, v in re.findall(r'(\w+)=(-?\d+)', line))
            segments = []
        elif line.startswith('FR_PAIR_SEG '):
            assert current is not None
            seg = dict((k, int(v)) for k, v in re.findall(r'(\w+)=(-?\d+)', line))
            if segments:
                assert segments[-1]['next'] == seg['id']
            segments.append(seg)
        elif line.startswith('FR_PAIR_END '):
            assert current is not None and segments
            matches = [s for s in segments if s['flags'] & 1 and s['link_flags'] & 1
                       and s['link'] >= 0 and s['back'] == s['id'] and s['link_edge'] == s['stem_edge']]
            if not matches:
                assert segments[-1]['next'] == segments[0]['id']
            else:
                assert matches == [segments[-1]]
            output = int(line.split('=')[1])
            assert output == current['fitted'] + ((-8 if current['input'] < 0 else 8) if matches else 0)
            if current['extra']:
                assert current['fitted'] == current['input']
            decisions.append(current | dict(eligible=bool(matches), output=output, segments=segments))
            current = None
    assert current is None and decisions
    assert any(d['eligible'] and d['extra'] for d in decisions)
    assert any(not d['eligible'] for d in decisions)
    assert any(d['eligible'] and len(d['segments']) > 1 for d in decisions)
    assert any(s['flags'] & 1 and not s['link_flags'] & 1 and s['back'] == s['id']
               for d in decisions for s in d['segments'])
    return decisions


def verify_ownership(path, baseline):
    data = json.loads(path.read_text())
    assert data['header_sha256'] == sha(ROOT / 'tests/freetype_curve_trace.h')
    assert data['patch_sha256'] == sha(ROOT / 'tests/freetype_curve_trace.patch')
    cases = {(c['face'], c['point'], c['mode']): c for c in data['cases']}
    expected = {(f, p, m) for f, p in (('Noto Sans Regular', 11.25), ('Noto Serif Italic', 11.25),
                                     ('Lato Light', 11.25), ('Lato Light', 16)) for m in ('50', 'round')}
    assert len(cases) == len(data['cases']) == 8 and set(cases) == expected
    for (face, point, mode), case in cases.items():
        glyph = baseline[mode][face, point]['glyphs'][TEXT.index(case['char'])]
        assert glyph['loaded'] == case['loaded']
        assert all(glyph[k] == case['rendered'][k] for k in ('mask', 'width', 'height', 'left', 'top'))
        frames = {(f['dim'], f['stage']): f['points'] for f in case['frames']}
        dimensions = (1,) if face == 'Noto Serif Italic' else (0, 1)
        expected_frames = {(dim, stage) for dim in dimensions for stage in ('edge', 'strong', 'weak', 'final')}
        expected_frames.add((1, 'save'))
        assert len(frames) == len(case['frames']) and set(frames) == expected_frames
        final = frames[1, 'save']
        assert [[p['x'], p['y']] for p in final] == [p[:2] for p in glyph['loaded']['outline']]
        for points in frames.values():
            assert [p['id'] for p in points] == list(range(len(final)))
        strong, weak = frames[1, 'strong'], frames[1, 'weak']
        refs = {}
        for p in strong:
            if p['flags'] & 8:
                continue
            previous, following = p['prev'], p['next']
            while previous != p['id'] and not strong[previous]['flags'] & 8:
                previous = strong[previous]['prev']
            while following != p['id'] and not strong[following]['flags'] & 8:
                following = strong[following]['next']
            refs[p['id']] = [previous, following]
            if previous == p['id']:
                want = p['y']
            else:
                a, b = strong[previous], strong[following]
                if a['oy'] > b['oy']:
                    a, b = b, a
                v = p['oy']
                if v <= a['oy']:
                    want = v + a['y'] - a['oy']
                elif v >= b['oy']:
                    want = v + b['y'] - b['oy']
                elif a['y'] == b['y'] or a['oy'] == b['oy']:
                    want = a['y']
                else:
                    # FreeType rounds signed fixed-point products away from zero at halves.
                    n, d = b['y'] - a['y'], b['oy'] - a['oy']
                    scale = (1 if n >= 0 else -1) * (((abs(n) << 16) + d // 2) // d)
                    product = (v - a['oy']) * scale
                    want = a['y'] + (1 if product >= 0 else -1) * ((abs(product) + 32768) >> 16)
            assert weak[p['id']]['y'] == want, (face, point, mode, p['id'])
        case['weak_references'] = refs
    movements = []
    for face, point in (('Noto Sans Regular', 11.25), ('Noto Serif Italic', 11.25)):
        pair = [{f['stage']: f['points'] for f in cases[face, point, mode]['frames'] if f['dim'] == 1}
                for mode in ('50', 'round')]
        points = []
        for i in range(len(pair[0]['save'])):
            first = next((stage for stage in ('edge', 'strong', 'weak', 'final', 'save')
                          if pair[0][stage][i]['y'] != pair[1][stage][i]['y']), None)
            points.append(dict(id=i, first_changed_stage=first,
                               delta_y=pair[1]['save'][i]['y'] - pair[0]['save'][i]['y']))
        movements.append(dict(face=face, point=point, points=points))
    return data | dict(first_movements=movements)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path, help='Folder containing 75/, 50/, round/, qt/ and round.trace')
    parser.add_argument('--libraries', type=Path, nargs=3, required=True, metavar=('STOCK', 'NEAREST', 'ROUND'))
    parser.add_argument('--label-font', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--segment-pairs', action='store_true', help='Verify the narrower native segment-pair trial')
    args = parser.parse_args()
    assert args.output.resolve().is_relative_to((ROOT / 'results').resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    protected = [args.study / folder / 'rows.json' for folder in FOLDERS]
    build = json.loads((args.study / 'build.json').read_text())
    assert build['source_archive_sha256'] == '9a2bdc2c992fa82a309eccf5e8bcbf2a380a98ba22f9f2ec7e56767739a19a0a'
    assert build['source_sha256'] == '30189813d762de77aea2a0d9010a6b7656657809028ac433f92b3c027eeda7f7'
    assert build['renderer_sha256'] == sha(ROOT / 'tests/point_benchmark_chart.cpp')
    assert build['flags'] == '-O2 -DFT_DEBUG_LEVEL_TRACE'
    for name, digest in build['patches'].items():
        assert sha(ROOT / 'patches' / name) == digest
    for role, library in zip(('stock', 'nearest', 'round'), args.libraries):
        assert build['libraries'][role] == sha(library)
    protected += args.libraries + [args.label_font]
    datasets = [json.loads(path.read_text()) for path in protected[:4]]
    protected += [args.study / name for name in ('build.json', 'round.trace', 'trace-samples.json')]
    if args.segment_pairs:
        protected += [args.study / 'ownership.json', args.study / 'prior-round/rows.json']
    fonts = {Path(row['font_path']) for rows in datasets for row in rows}
    protected += sorted(fonts)
    before = {str(p): sha(p) for p in protected}
    expected = {(name, point) for name in FACES for point in POINTS}
    maps = []
    for rows in datasets:
        keys = [(r['label'], r['point_size']) for r in rows]
        assert len(keys) == len(set(keys)) == 130 and set(keys) == expected
        assert len({r['id'] for r in rows}) == 130
        maps.append(dict(zip(keys, rows)))

    # The real one-round contrast distinguishes BOTH from an accidental OR.
    trace = (args.study / 'round.trace').read_text()
    decisions = [tuple(map(int, m)) for m in re.findall(
        r'FR_ROUND dim=(\d+) base=(\d+) stem=(\d+) input=(-?\d+) matched=(\d+) rounded=(\d+) output=(\d+)', trace)]
    flag_cases = set()
    ownership = None
    if args.segment_pairs:
        decisions = segment_decisions(trace)
        prior_rows = json.loads((args.study / 'prior-round' / 'rows.json').read_text())
        baseline = {'50': maps[1], 'round': {(r['label'], r['point_size']): r for r in prior_rows}}
        ownership = verify_ownership(args.study / 'ownership.json', baseline)
    else:
        assert decisions and len(decisions) == trace.count('FR_ROUND')
        for dim, base, stem, width, matched, rounded, output in decisions:
            assert dim == 1 and rounded >= 64 and rounded % 64 == 0
            assert rounded == max(64, (matched + 32) & ~63)
            eligible = bool(base & 1) and bool(stem & 1)
            assert output == rounded + (8 if eligible else 0)
            flag_cases.add((bool(base & 1), bool(stem & 1)))
        assert (True, True) in flag_cases and (False, False) in flag_cases
        assert (True, False) in flag_cases or (False, True) in flag_cases
    samples = json.loads((args.study / 'trace-samples.json').read_text())
    sample_keys = {(face, point, char, mode) for face, point, char in (
        ('Noto Sans Regular', 11.25, 'n'), ('Noto Sans Regular', 16, 'n'),
        ('Lato Light', 11.25, 'n'), ('Noto Serif Italic', 11.25, 'v')) for mode in ('50', 'round')}
    if args.segment_pairs:
        sample_keys |= {('Lato Light', 16, 'n', mode) for mode in ('50', 'round')}
    assert len(samples) == len(sample_keys)
    assert {(s['face'], s['point'], s['char'], s['mode']) for s in samples} == sample_keys
    for sample in samples:
        row = maps[FOLDERS.index(sample['mode'])][sample['face'], sample['point']]
        glyph = row['glyphs'][TEXT.index(sample['char'])]
        result = sample['result']
        assert sample['pixels'] == row['base_px']
        assert sample['probe_sha256'] == sha(ROOT / 'tests/freetype_mask_probe.cpp')
        assert result['glyph'] == glyph['glyph']
        assert all(result['loaded'][k] == glyph['loaded'][k] for k in ('outline', 'contours'))
        assert len(result['rendered']) == 2 and result['rendered'][0] == result['rendered'][1]
        assert all(result['rendered'][0][k] == glyph[k] for k in ('mask', 'left', 'top', 'width', 'height'))
        if sample['face'] == 'Lato Light' and sample['point'] == 11.25 and not args.segment_pairs:
            assert 'style is extra light' in sample['trace'] and 'FR_ROUND' not in sample['trace']

    # Exercise the same compositor at the cutoff and with overlapping glyphs.
    glyph = dict(width=2, height=1, x=0, y=0, mask=bytes([159, 160]).hex())
    assert list(compose([glyph], 1, 160).tobytes()[:2]) == [159, 242]
    overlap = compose([glyph, glyph], 1, 160).tobytes()
    assert list(overlap[:2]) == [219, 254]

    palettes = {dark: blend_table(dark) for dark in (False, True)}
    oracle = Oracle(args.libraries[0])
    measurements, diagonal_changes, curve_changes = [], [], []
    checked = 0
    for key in sorted(expected):
        peers = [m[key] for m in maps]
        for row in peers:
            for field in ('id', 'label', 'point_size', 'base_px', 'runs', 'height',
                          'font_sha256', 'cutoff', 'logical_dpi', 'scale'):
                assert row[field] == peers[0][field], (key, field)
            assert row['logical_dpi'] == 96 and row['scale'] == 1
            assert row['font_sha256'] == before[row['font_path']]
            assert row['cutoff'] == (128 if row['weight'] < 400 else 160)
            assert len(row['runs']) == len(TEXT) == 33
        for folder, row in zip(FOLDERS[:3], peers[:3]):
            assert len(row['glyphs']) == len(TEXT)
            for run, glyph in zip(row['runs'], row['glyphs']):
                assert run['glyph'] == glyph['glyph']
                expected_raster = oracle.raster(glyph['loaded'])
                assert all(expected_raster[k] == glyph[k] for k in ('mask', 'width', 'height', 'left', 'top'))
                assert glyph['x'] == int(run['x'] // 1) + glyph['left']
                assert glyph['y'] == int(run['y'] + 0.5) - glyph['top']
                checked += 1
            mask = compose(row['glyphs'], row['height'], row['cutoff'])
            assert mask.tobytes() == (args.study / folder / (row['id'] + '-mask.bin')).read_bytes()
            assert hashlib.sha256(mask.tobytes()).hexdigest() == row['composed_mask_sha256']
            for dark, palette in ((False, 'light'), (True, 'dark')):
                want = mask.point(palettes[dark]).convert('RGB')
                with Image.open(args.study / folder / f'{row["id"]}-{palette}.png') as actual:
                    assert actual.size == want.size and actual.convert('RGB').tobytes() == want.tobytes()
        nearest, trial = peers[1:3]
        features = {}
        for char, old, new in zip(TEXT, nearest['glyphs'], trial['glyphs']):
            assert old['loaded']['contours'] == new['loaded']['contours']
            assert [(x, tag) for x, y, tag in old['loaded']['outline']] == \
                [(x, tag) for x, y, tag in new['loaded']['outline']], (key, char, 'X changed')
            changed = old != new
            if char in 'VvWw' and changed:
                diagonal_changes.append(dict(face=key[0], point=key[1], char=char,
                                             nearest=profile(old), trial=profile(new)))
            if char in 'n358':
                features[char] = dict(nearest=profile(old), trial=profile(new), changed=changed)
                if changed:
                    curve_changes.append((key[0], key[1], char))
        measurements.append(dict(face=key[0], point=key[1], pixels=nearest['base_px'], features=features))
    oracle.close()
    assert checked == 12870
    noto = maps[0]['Noto Sans Regular', 16]['glyphs'][TEXT.index('n')]
    near = maps[1]['Noto Sans Regular', 16]['glyphs'][TEXT.index('n')]
    assert profile(noto)['center_column'][:3] == [250, 9, 0]
    assert profile(near)['center_column'][:3] == [246, 255, 8]

    label = ImageFont.truetype(str(args.label_font), 13)
    images = []
    for point in (8, 11.25, 16):
        for palette, bg, fg in (('light', 255, 0), ('dark', 0, 255)):
            row_height = 90 + 4 * max(maps[0][name, point]['height'] for name in FACES)
            sheet = Image.new('RGB', (2080, 90 + len(FACES) * row_height), (bg,) * 3)
            draw = ImageDraw.Draw(sheet)
            draw.text((12, 8), f'{point:g}pt | fresh local Qt baseline | 96 DPI / 100% | native text + 4x strip excerpts', font=label, fill=(fg,) * 3)
            rectangles = []
            trial_title = '50% + mutual round segments 1/8px +242' if args.segment_pairs else '50% + rounded Y 1/8px +242'
            for col, title in enumerate(('75% +242', '50% +242', trial_title, 'Stock Qt; Fontreal disabled')):
                draw.text((col * 520 + 12, 38), title, font=label, fill=(fg,) * 3)
            for index, name in enumerate(FACES):
                y = 70 + index * row_height
                draw.text((12, y), name.replace('BoldItalic', 'Bold Italic'), font=label, fill=(fg,) * 3)
                for col, folder in enumerate(FOLDERS):
                    row = maps[col][name, point]
                    source = Image.open(args.study / folder / f'{row["id"]}-{palette}.png').convert('RGB')
                    assert source.size == (620, row['height']) and source.height < 65
                    assert not Image.eval(source.crop((500, 0, 620, source.height)).convert('L'), lambda a: abs(a-bg)).getbbox()
                    x = col * 520 + 12
                    native = source.crop((0, 0, 500, source.height))
                    sheet.paste(native, (x, y + 22))
                    rectangles.append((x, y + 22, native))
                    xx = x
                    for char in 'n358VvW':
                        at = TEXT.index(char)
                        left = int(row['runs'][at]['x']) - 1
                        right = int(row['runs'][at+1]['x']) + 1
                        detail = source.crop((left, 0, right, source.height)).resize(
                            ((right-left) * 4, source.height * 4), Image.Resampling.NEAREST)
                        assert xx + detail.width <= x + 500 and 76 + detail.height <= row_height
                        sheet.paste(detail, (xx, y + 76))
                        rectangles.append((xx, y + 76, detail))
                        xx += detail.width + 4
            prefix = 'segment-y' if args.segment_pairs else 'round-y'
            target = args.output / f'{prefix}-{point:g}pt-{palette}.png'
            sheet.save(target)
            with Image.open(target) as saved:
                for x, y, crop in rectangles:
                    assert saved.crop((x, y, x+crop.width, y+crop.height)).tobytes() == crop.tobytes()
            images.append(dict(file=target.name, sha256=sha(target)))
    if args.segment_pairs:
        for palette, bg, fg in (('light', 255, 0), ('dark', 0, 255)):
            pieces = []
            for point in (8, 11.25):
                source = Image.open(args.output / f'segment-y-{point:g}pt-{palette}.png').convert('RGB')
                row_height = (source.height - 90) // len(FACES)
                for name in ('Noto Sans Regular', 'Noto Serif Italic', 'Lato Light'):
                    y = 70 + FACES.index(name) * row_height
                    native = source.crop((0, y+22, source.width, y+76))
                    details = source.crop((0, y+76, source.width, y+row_height))
                    box = ImageChops.difference(details, Image.new('RGB', details.size, (bg,) * 3)).getbbox()
                    assert box
                    details = details.crop((0, box[1], details.width, box[3]))
                    pieces.append((f'{name} | {point:g}pt', native, details))
            compact = Image.new('RGB', (2080, 90 + sum(84 + d.height for _, _, d in pieces)), (bg,) * 3)
            draw = ImageDraw.Draw(compact)
            draw.text((12, 8), 'Genuine rounded segment pairs | 8pt and 11.25pt | native text and exact 4x excerpts', font=label, fill=(fg,) * 3)
            for col, title in enumerate(('75% +242', '50% +242', trial_title, 'Stock Qt; Fontreal disabled')):
                draw.text((col*520+12, 38), title, font=label, fill=(fg,) * 3)
            y, crops = 72, []
            for title, native, details in pieces:
                draw.text((12, y), title, font=label, fill=(fg,) * 3)
                for offset, crop in ((20, native), (74, details)):
                    compact.paste(crop, (0, y+offset))
                    crops.append((y+offset, crop))
                y += 84 + details.height
            target = args.output / f'segment-y-preview-{palette}.png'
            compact.save(target)
            with Image.open(target) as saved:
                for y, crop in crops:
                    assert saved.crop((0, y, crop.width, y+crop.height)).tobytes() == crop.tobytes()
            images.append(dict(file=target.name, sha256=sha(target)))
    assert before == {str(p): sha(p) for p in protected}
    reference = json.loads((ROOT / 'docs/images/browser-common-ground/point-benchmark242-captures.json').read_text())
    ref_fonts = {r['label']: r['font_sha256'] for r in reference['conditions']}
    conditions = [{k: row[k] for k in ('id', 'label', 'point_size', 'base_px', 'font_sha256', 'cutoff')}
                  | dict(font_file=Path(row['font_path']).name,
                         matches_reference_font=row['font_sha256'] == ref_fonts[row['label']]) for row in datasets[3]]
    report = dict(build=build, ownership=ownership, trace_samples=samples, conditions=conditions, measurements=measurements, images=images,
                  native_masks_checked=checked, curve_changes=len(set(curve_changes)), diagonal_changes=diagonal_changes,
                  width_decisions=len(decisions), round_flag_cases=sorted(flag_cases),
                  libraries=[dict(role=role, sha256=sha(path)) for role, path in zip(('75', '50', 'round'), args.libraries)],
                  rows_sha256={folder: sha(args.study / folder / 'rows.json') for folder in FOLDERS},
                  trace_sha256=sha(args.study / 'round.trace'), checker_sha256=sha(Path(__file__)),
                  limits=['Fresh local Qt baseline; differs from earlier capture environment',
                          'AF_EDGE_ROUND is an edge heuristic; diagonal changes are measured, not excluded',
                          '4x details are strip excerpts and can contain neighboring ink',
                          'Static Latin component experiment; no browser or production policy qualification'])
    if args.segment_pairs:
        report['segment_pair_summary'] = dict(eligible=sum(d['eligible'] for d in decisions),
            extra_light_expanded=sum(d['eligible'] and d['extra'] for d in decisions),
            later_segment_match=sum(d['eligible'] and len(d['segments']) > 1 for d in decisions))
    (args.output / (prefix + '-captures.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS {len(expected)} conditions; {checked} native masks; {len(decisions)} width decisions; '
          f'{len(set(curve_changes))} curve changes; {len(diagonal_changes)} diagonal changes; {len(images)} verified images')


if __name__ == '__main__':
    main()
