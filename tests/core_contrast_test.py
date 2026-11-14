#!/usr/bin/env python3
"""Separate post-hint expansion from blending at integer 8–16pt requests."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFont

from curve_contrast_test import ROOT, FACES, TEXT, Oracle, blend_table, compose, sha

POINTS = tuple(range(8, 17))
EXPECTED = {(face, point) for face in FACES for point in POINTS}


def matrix(rows):
    assert all('point_size' in r and r.get('font_point_size') == r['point_size'] for r in rows)
    keys = [(r['label'], r['point_size']) for r in rows]
    assert len(keys) == len(set(keys)) == len(EXPECTED) and set(keys) == EXPECTED
    return dict(zip(keys, rows))


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, capture_output=True, text=True, **kwargs)


def native_ownership(build, output, source, env):
    cases = []
    for face, folder, font in (('Noto Sans Regular', 'noto', 'NotoSans-Regular.ttf'),
                               ('Noto Serif Italic', 'noto', 'NotoSerif-Italic.ttf'),
                               ('Lato Light', 'lato', 'Lato-Light.ttf')):
        for point in (8, 11):
            for char in '835v':
                pair, translations = {}, {}
                for mode, lib in (('50', 'nearest-owners'), ('round', 'segment-owners')):
                    row = source[mode][face, point]
                    glyph = row['glyphs'][TEXT.index(char)]
                    target = output / f'{Path(font).stem}-{point}pt-{char}-{mode}.json'
                    result = run([build/'probe', Path('/usr/share/fonts/truetype')/folder/font,
                                  row['base_px'], '0x20028', ord(char), 0, 0, 0, 2, target, 'none', 0],
                                 env=dict(env, LD_LIBRARY_PATH=str(build/lib/'.libs'),
                                          FT2_DEBUG='aflatin:6,afhints:7,afmodule:7'))
                    probe = json.loads(target.read_text())
                    assert probe['glyph'] == glyph['glyph']
                    assert all(probe['loaded'][k] == glyph['loaded'][k] for k in ('outline', 'contours'))
                    assert len(probe['rendered']) == 2 and probe['rendered'][0] == probe['rendered'][1]
                    assert all(probe['rendered'][0][k] == glyph[k] for k in ('mask', 'width', 'height', 'left', 'top'))
                    lines, frames = result.stderr.splitlines(), {}
                    for i, line in enumerate(lines):
                        match = re.fullmatch(r'FR_STAGE glyph=(\d+) dim=(\d+) stage=(\w+) count=(\d+)', line)
                        if match and int(match[1]) == glyph['glyph']:
                            points = [dict((k, int(v)) for k, v in re.findall(r'(\w+)=(-?\d+)', s))
                                      for s in lines[i+1:i+1+int(match[4])]]
                            assert [p['id'] for p in points] == list(range(len(glyph['loaded']['outline'])))
                            key = (int(match[2]), match[3])
                            assert key not in frames
                            frames[key] = points
                    dimensions = (1,) if face == 'Noto Serif Italic' else (0, 1)
                    assert set(frames) == {(d, s) for d in dimensions for s in ('edge', 'strong', 'weak', 'final')} | {(1, 'save')}
                    final = frames[1, 'save']
                    shifts = {(int(x)-p['x'], int(y)-p['y']) for p, (x, y, tag) in zip(final, glyph['loaded']['outline'])}
                    assert len(shifts) == 1 and next(iter(shifts))[1] == 0
                    translations[mode] = list(next(iter(shifts)))
                    pair[mode] = {s: frames[1, s] for s in ('edge', 'strong', 'weak', 'final', 'save')}
                    target.unlink()
                assert translations['50'] == translations['round']
                movements = []
                for i in range(len(pair['50']['save'])):
                    first = next((s for s in pair['50'] if pair['50'][s][i]['y'] != pair['round'][s][i]['y']), None)
                    movements.append(dict(id=i, first_stage=first,
                        delta_y=pair['round']['save'][i]['y']-pair['50']['save'][i]['y']))
                cases.append(dict(face=face, point=point, char=char, loader_translations=translations,
                                  first_stage_counts=dict(Counter(p['first_stage'] or 'unchanged' for p in movements)),
                                  movements=movements))
    return cases


def middle_rows(glyph, levels, cutoff):
    raw = bytes.fromhex(glyph['mask'])
    result = []
    for y in levels:
        local = y + glyph['top']
        values = list(raw[local*glyph['width']:(local+1)*glyph['width']]) if 0 <= local < glyph['height'] else []
        result.append(dict(y=y, left=glyph['left'], raw=values,
                           cutoff_pixels=sum(a >= cutoff for a in values)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path, help='Retained study with 75, 50, round, qt folders')
    parser.add_argument('--native-build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label-font', type=Path, required=True)
    args = parser.parse_args()
    original_env = dict(os.environ)
    output, build = args.output.resolve(), args.native_build.resolve()
    work = (ROOT/'build/core-contrast').resolve()
    assert output.is_relative_to((ROOT/'results').resolve()) and build.is_relative_to((ROOT/'build').resolve())
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    datasets, protected = {}, []
    for mode in ('75', '50', 'round', 'qt'):
        path = args.study/mode/'rows.json'
        rows = json.loads(path.read_text())
        assert len(rows) == len({(r['label'], r['point_size']) for r in rows})
        datasets[mode] = matrix([r for r in rows if r['point_size'] in POINTS])
        protected.append(path)
    controls = list(datasets['qt'].values())
    # Matching counts alone must not accept a duplicate prefix or a fractional request.
    for invalid in (controls[:-1]+[controls[0]], controls[:-1],
                    [dict(controls[0], point_size=8.5)]+controls[1:],
                    [{k: v for k, v in controls[0].items() if k != 'point_size'}]+controls[1:]):
        try:
            matrix(invalid)
        except AssertionError:
            pass
        else:
            raise AssertionError('invalid comparison matrix accepted')
    libraries = {name: build/name/'.libs/libfreetype.so' for name in ('stock', 'nearest', 'nearest-owners', 'segment-owners')}
    provenance = json.loads((args.study/'build.json').read_text())
    assert provenance['source_archive_sha256'] == '9a2bdc2c992fa82a309eccf5e8bcbf2a380a98ba22f9f2ec7e56767739a19a0a'
    for name in ('stock', 'nearest'):
        assert sha(libraries[name]) == provenance['libraries'][name]
    source = ROOT/'tests/point_benchmark_chart.cpp'
    patch = ROOT/'tests/point_outline_expansion.patch'
    protected += list(libraries.values()) + [source, patch, args.label_font, args.study/'build.json', ROOT/'tests/freetype_mask_probe.cpp', ROOT/'tests/freetype_curve_trace.h', ROOT/'tests/freetype_curve_trace.patch']
    protected += sorted({Path(r['font_path']) for r in controls})
    before = {str(p): sha(p) for p in protected}
    cpp = work/'source/tests/point_benchmark_chart.cpp'
    cpp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, cpp)
    run(['patch', '--batch', '--fuzz=0', '-p1', '-i', patch], cwd=work/'source')
    flags = shlex.split(run(['pkg-config', '--cflags', '--libs', 'Qt6Gui', 'freetype2']).stdout)
    binary = work/'chart-expanded'
    run(['c++', '-std=c++17', '-fPIC', '-include', 'algorithm', cpp, *flags, '-o', binary])
    env = {k: v for k, v in original_env.items() if not k.startswith('FONTREAL_') and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'FREETYPE_PROPERTIES', 'FT2_DEBUG')}
    env.update(FONTREAL_RENDERING='0', QT_QPA_PLATFORM='offscreen', QT_FONT_DPI='96',
               FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')
    input_file = output/'integer-input.json'
    input_file.write_text(json.dumps(controls, indent=2)+'\n')
    run([binary, 'candidate', input_file, output/'expanded'],
        env=dict(env, LD_LIBRARY_PATH=str(libraries['nearest'].parent)))
    datasets['expanded'] = matrix(json.loads((output/'expanded/rows.json').read_text()))
    ownership = native_ownership(build, output, datasets, env)
    oracle = Oracle(libraries['stock'])
    palettes = {dark: blend_table(dark) for dark in (False, True)}
    images, profiles, glyph_checks = {}, [], 0
    for key in sorted(EXPECTED):
        peers = [datasets[mode][key] for mode in ('75', '50', 'expanded', 'qt')]
        for row in peers:
            for field in ('id', 'label', 'point_size', 'font_point_size', 'font_sha256', 'base_px', 'runs', 'height', 'cutoff', 'logical_dpi', 'scale'):
                assert row[field] == peers[0][field], (key, field)
            assert row['font_sha256'] == before[row['font_path']]
            assert row['logical_dpi'] == 96 and row['scale'] == 1 and len(row['runs']) == len(TEXT) == 33
        for mode, row in zip(('75', '50', 'expanded'), peers[:3]):
            for i, glyph in enumerate(row['glyphs']):
                if mode == 'expanded':
                    expected_outline = oracle.expand(peers[1]['glyphs'][i]['loaded'])
                    assert expected_outline == glyph['loaded']
                native = oracle.raster(glyph['loaded'])
                assert all(native[k] == glyph[k] for k in ('mask', 'width', 'height', 'left', 'top'))
                assert glyph['glyph'] == row['runs'][i]['glyph']
                assert glyph['x'] == int(row['runs'][i]['x']//1)+glyph['left']
                assert glyph['y'] == int(row['runs'][i]['y']+0.5)-glyph['top']
                glyph_checks += 1
            mask = compose(row['glyphs'], row['height'], row['cutoff'])
            folder = output/'expanded' if mode == 'expanded' else args.study/mode
            assert mask.tobytes() == (folder/(row['id']+'-mask.bin')).read_bytes()
            for dark, palette in ((False, 'light'), (True, 'dark')):
                expected = mask.point(palettes[dark]).convert('RGB')
                actual = Image.open(folder/f'{row["id"]}-{palette}.png').convert('RGB')
                assert actual.size == expected.size and actual.tobytes() == expected.tobytes()
                images[mode, key, palette] = actual
                if mode == '50':
                    # Composition alone changes here; the exact treated mask stays fixed.
                    images['encoded', key, palette] = mask.point(list(range(256)) if dark else list(range(255, -1, -1))).convert('RGB')
        for palette in ('light', 'dark'):
            row = peers[-1]
            images['qt', key, palette] = Image.open(args.study/'qt'/f'{row["id"]}-{palette}.png').convert('RGB')
        features = {}
        for char in '835vVWl':
            original = peers[1]['glyphs'][TEXT.index(char)]
            center = -original['top'] + original['height']//2
            levels = (center-1, center)
            features[char] = {mode: middle_rows(datasets[mode][key]['glyphs'][TEXT.index(char)], levels, peers[1]['cutoff'])
                              for mode in ('50', 'round', 'expanded')}
        profiles.append(dict(face=key[0], point=key[1], features=features))
    oracle.close()
    assert glyph_checks == 11583
    glyph = dict(width=2, height=1, x=0, y=0, mask=bytes([159, 160]).hex())
    assert list(compose([glyph], 1, 160).tobytes()[:2]) == [159, 242]
    assert list(compose([glyph, glyph], 1, 160).tobytes()[:2]) == [219, 254]
    label = ImageFont.truetype(str(args.label_font), 13)
    outputs = []

    def sheet(cases, trial, palette, filename, width=520):
        bg, fg = (255, 0) if palette == 'light' else (0, 255)
        modes = ('75', '50', trial, 'qt')
        blocks = []
        for key in cases:
            crops = []
            for mode in modes:
                native = images[mode, key, palette]
                # Full words remain in wide sheets; main panels use the first text excerpt.
                limit = 500 if width == 520 else width-16
                strip = native.crop((0, 0, limit, native.height))
                details, total = [], 0
                row = datasets['qt'][key]
                for char in '835v':
                    at = TEXT.index(char)
                    left, right = int(row['runs'][at]['x'])-1, int(row['runs'][at+1]['x'])+2
                    detail = native.crop((left, 0, right, native.height))
                    details.append(detail)
                    total += detail.width*6+4
                assert total <= limit
                montage = Image.new('RGB', (limit, native.height*6), (bg,)*3)
                xx = 0
                for detail in details:
                    large = detail.resize((detail.width*6, detail.height*6), Image.Resampling.NEAREST)
                    montage.paste(large, (xx, 0));xx += large.width+4
                box = ImageChops.difference(montage, Image.new('RGB', montage.size, (bg,)*3)).getbbox()
                assert box
                crops.append((strip, montage.crop((0, box[1], limit, box[3]))))
            blocks.append((key, crops, 32+max(s.height+d.height for s,d in crops)))
        canvas = Image.new('RGB', (width*4, 76+sum(h for _,_,h in blocks)), (bg,)*3)
        draw = ImageDraw.Draw(canvas)
        title = 'Post-hint native expansion' if trial == 'expanded' else 'Same 50% mask; encoded-blend diagnostic'
        draw.text((8, 8), title+' | integer 8–16pt | native text + 6x excerpts: 8 3 5 v', font=label, fill=(fg,)*3)
        for col, title in enumerate(('75% +242', '50% +242', 'Native expansion' if trial == 'expanded' else 'Same mask; encoded blend', 'Stock Qt')):
            draw.text((col*width+8, 35), title, font=label, fill=(fg,)*3)
        y, rectangles = 66, []
        for key, crops, height in blocks:
            draw.text((8,y), f'{key[0].replace("BoldItalic", "Bold Italic")} | {key[1]}pt', font=label, fill=(fg,)*3)
            for col, (strip, detail) in enumerate(crops):
                x = col*width+8
                for yy, crop in ((y+19, strip), (y+19+strip.height, detail)):
                    canvas.paste(crop, (x,yy));rectangles.append((x,yy,crop))
            y += height
        path = output/filename
        canvas.save(path)
        with Image.open(path) as saved:
            for x,y,crop in rectangles:
                assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes() == crop.tobytes()
        outputs.append(dict(file=filename, sha256=sha(path)))

    for trial in ('expanded', 'encoded'):
        for palette in ('light', 'dark'):
            main = [(face, point) for point in (8,11) for face in ('Noto Sans Regular','Noto Serif Italic','Lato Light')]
            sheet(main, trial, palette, f'core-{trial}-preview-{palette}.png', width=320)
            if trial == 'expanded':
                for face in ('Noto Sans Regular','Noto Serif Italic','Lato Light'):
                    slug=face.lower().replace(' ','-')
                    sheet([(face, point) for point in POINTS], trial, palette, f'core-{slug}-8-16pt-{palette}.png')
                sheet([(face,16) for face in FACES],trial,palette,f'core-expanded-16pt-{palette}.png')
    assert before == {str(p):sha(p) for p in protected} and original_env == dict(os.environ)
    report = dict(point_sizes=list(POINTS), conditions=[{k:r[k] for k in ('id','label','point_size','font_point_size','font_sha256','cutoff')} for r in controls],
                  ownership=ownership, profiles=profiles, images=outputs, native_masks_checked=glyph_checks,
                  native_operation=dict(x_strength=8,y_strength=16,library_sha256=sha(libraries['nearest'])),
                  source_archive_sha256=provenance['source_archive_sha256'],
                  libraries={name:sha(path) for name,path in libraries.items()},
                  qt_version=run(['pkg-config','--modversion','Qt6Gui']).stdout.strip(),
                  probe_sha256=sha(ROOT/'tests/freetype_mask_probe.cpp'),
                  trace_header_sha256=sha(ROOT/'tests/freetype_curve_trace.h'),
                  trace_patch_sha256=sha(ROOT/'tests/freetype_curve_trace.patch'),
                  source_sha256=sha(source), private_source_sha256=sha(cpp), patch_sha256=sha(patch), checker_sha256=sha(Path(__file__)),
                  input_sha256={mode:sha(args.study/mode/'rows.json') for mode in ('75','50','round','qt')},
                  limits=['Native expansion can add diagonal weight', 'Encoded blending is a separate diagnostic, not a new preset',
                          'Resolved device units remain internal metadata; comparisons use integer requested points',
                          'Historical Qt baseline and font identities retained; no browser qualification'])
    (output/'core-contrast-captures.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS {len(EXPECTED)} integer-point conditions; {glyph_checks} independent masks; {len(ownership)} ownership pairs; {len(outputs)} images')


if __name__ == '__main__':
    main()
