#!/usr/bin/env python3
"""Compare existing round-segment expansion with unchanged raw rasterization."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont
from browser_stroke_axis_test import Oracle
from encoded_refinement_test import scalar_mask

ROOT = Path(__file__).resolve().parents[1]
TEXT = 'ilI1 H mno 0358 VvWw'
WORK = ROOT / 'build/raw-curve-darkening'
OUT = ROOT / 'results/raw-curve-darkening'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def traces(text, strength):
    current, segments, count, eligible = None, [], 0, 0
    for line in text.splitlines():
        values = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', line)}
        if line.startswith('FR_PAIR_BEGIN '):
            assert current is None
            current, segments = values, []
        elif line.startswith('FR_PAIR_SEG '):
            assert current is not None
            if segments:
                assert segments[-1]['next'] == values['id']
            segments.append(values)
        elif line.startswith('FR_PAIR_END '):
            assert current is not None and segments
            matches = [s for s in segments if s['flags'] & s['link_flags'] & 1
                       and s['link'] >= 0 and s['back'] == s['id'] and s['link_edge'] == s['stem_edge']]
            assert not matches or matches == [segments[-1]]
            if not matches:
                assert segments[-1]['next'] == segments[0]['id']
            delta = (-strength if current['input'] < 0 else strength) if matches else 0
            assert values['output'] == current['fitted'] + delta
            count += 1
            eligible += bool(matches)
            current = None
    assert current is None and 0 < eligible < count
    return dict(decisions=count, eligible=eligible)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-build', type=Path, required=True)
    parser.add_argument('--nearest-library', type=Path, required=True)
    parser.add_argument('--label-font', type=Path, required=True)
    args = parser.parse_args()
    before = dict(os.environ)
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    record = json.loads(args.stock_build.read_text())
    parent = args.stock_build.resolve().parent
    stock = Path(record['libraries']['stock']['library'])
    assert sha(stock) == record['libraries']['stock']['sha256']
    original = parent / 'stock-source'
    assert sha(original/'src/autofit/aflatin.c') == '30189813d762de77aea2a0d9010a6b7656657809028ac433f92b3c027eeda7f7'
    patch = ROOT/'patches/freetype-2.14.2-segment-y-experiment.patch'
    base_env = {k: v for k, v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
                ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'FT2_DEBUG', 'FREETYPE_PROPERTIES')}
    base_env.update(FONTREAL_RENDERING='0', FONTREAL_FT_RENDERING='0', QT_QPA_PLATFORM='offscreen', QT_FONT_DPI='96',
                    FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')
    libraries, decisions = {}, {}
    for strength in (0, 4, 8):
        folder = WORK/str(strength)
        source, build = folder/'source', folder/'build'
        manifest = folder/'build.json'
        inputs = dict(stock_record_sha256=sha(args.stock_build), patch_sha256=sha(patch), strength=strength,
                      compiler=subprocess.check_output(['cc', '--version'], text=True).splitlines()[0],
                      cflags='-O2 -DFT_DEBUG_LEVEL_TRACE')
        if source.exists():
            saved = json.loads(manifest.read_text())
            assert saved['inputs'] == inputs
            assert saved['source_sha256'] == sha(source/'src/autofit/aflatin.c')
            assert saved['library_sha256'] == sha(build/'.libs/libfreetype.so.6')
        if not source.exists():
            shutil.copytree(original, source, symlinks=True)
            run(['patch', '--batch', '--fuzz=0', '-p1', '-i', patch], cwd=source, stdout=subprocess.DEVNULL)
            p = source/'src/autofit/aflatin.c'
            text = p.read_text()
            needle = 'result += width < 0 ? -8 : 8;'
            assert text.count(needle) == 1
            p.write_text(text.replace(needle, f'result += width < 0 ? -{strength} : {strength};'))
        build.mkdir(exist_ok=True)
        library = build/'.libs/libfreetype.so.6'
        if not library.exists():
            env = dict(base_env, CC='cc', CFLAGS='-O2 -DFT_DEBUG_LEVEL_TRACE', TMPDIR=str(WORK.resolve()),
                       PKG_CONFIG_PATH=str(parent/'headers/usr/lib/x86_64-linux-gnu/pkgconfig'))
            with (folder/'build.log').open('w') as log:
                run([source/'configure', '--with-harfbuzz=dynamic', f'--prefix={folder}/unused-install'], cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT)
                run(['make', '-j8'], cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT)
            manifest.write_text(json.dumps(dict(inputs=inputs, source_sha256=sha(source/'src/autofit/aflatin.c'),
                                                library_sha256=sha(library)), indent=2)+'\n')
        libraries[str(strength)] = library.resolve()
        print('built curve strength', strength, flush=True)
    chart_source = ROOT/'tests/point_benchmark_chart.cpp'
    chart = chart_source.read_text()
    assert chart.count('ilI1 minimum 0358 VvWw 0123456789') == 2
    chart = chart.replace('ilI1 minimum 0358 VvWw 0123456789', TEXT)
    needle = 'int v=(a>=cutoff&&a<242)?242:a;'
    assert chart.count(needle) == 1
    chart = chart.replace(needle, 'int v=a;')
    needle = 'double linear=dark?a/255.:1-a/255.;double encoded=linear<=.0031308?12.92*linear:1.055*std::pow(linear,1/2.4)-.055;int v=std::clamp(int(std::lround(encoded*255)),0,255);'
    assert chart.count(needle) == 1
    chart = chart.replace(needle, 'int v=dark?a:255-a;')
    (WORK/'chart.cpp').write_text(chart)
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Gui', 'freetype2'], text=True))
    run(['c++', '-std=c++17', '-fPIC', '-include', 'algorithm', WORK/'chart.cpp', *flags, '-o', WORK/'chart'])
    fonts = {
        'Noto Sans Regular': '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        'Noto Sans Bold': '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
        'Noto Sans Italic': '/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf',
        'Noto Serif Regular': '/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf',
        'Noto Serif Italic': '/usr/share/fonts/truetype/noto/NotoSerif-Italic.ttf',
        'Lato Light': '/usr/share/fonts/truetype/lato/Lato-Light.ttf',
        'Hack Regular': '/usr/share/fonts/truetype/hack/Hack-Regular.ttf',
        'Hack BoldItalic': '/usr/share/fonts/truetype/hack/Hack-BoldItalic.ttf',
        'Nimbus Sans Regular': '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf',
    }
    inputs = [dict(id=f'curve-{i}-{pt}', label=name, point_size=pt, logical_dpi=96, scale=1,
                   cutoff=128 if name == 'Lato Light' else 160, font_path=file)
              for i, (name, file) in enumerate(fonts.items()) for pt in range(8, 17)]
    assert all(Path(r['font_path']).is_file() for r in inputs)
    (WORK/'input.json').write_text(json.dumps(inputs))
    env = dict(base_env, LD_LIBRARY_PATH=str(stock.parent))
    with (WORK/'stock.log').open('w') as log:
        run([WORK/'chart', 'stock', WORK/'input.json', OUT/'qt'], env=env, stdout=log, stderr=log)
    source = OUT/'qt/rows.json'
    datasets = {}
    for name, library in (libraries | {'reference': args.nearest_library.resolve()}).items():
        env = dict(base_env, LD_LIBRARY_PATH=str(library.parent), FT2_DEBUG='aflatin:5')
        with (WORK/f'{name}.trace').open('w') as trace, (WORK/f'{name}.log').open('w') as log:
            run([WORK/'chart', 'candidate', source, OUT/name], env=env, stdout=log, stderr=trace)
        datasets[name] = json.loads((OUT/name/'rows.json').read_text())
        if name != 'reference':
            decisions[name] = traces((WORK/f'{name}.trace').read_text(), int(name))
    assert datasets['0'] == datasets['reference']
    oracle = Oracle(stock)
    diagonal_changes, straight_changes, curve_changes = {}, {}, {}
    for mode in ('0', '4', '8'):
        rows = datasets[mode]
        assert len(rows) == 81 and {(r['label'], r['point_size']) for r in rows} == {(n, p) for n in fonts for p in range(8, 17)}
        diagonal_changes[mode] = straight_changes[mode] = curve_changes[mode] = 0
        for row, ref in zip(rows, datasets['0']):
            assert all(row[k] == ref[k] for k in ('id', 'runs', 'font_sha256', 'base_px', 'height'))
            assert len(row['glyphs']) == len(TEXT)
            for char, glyph, prior in zip(TEXT, row['glyphs'], ref['glyphs']):
                assert oracle.raster(glyph['loaded']) == {k: glyph[k] for k in ('width', 'height', 'left', 'top', 'mask')}
                assert [p[0] for p in glyph['loaded']['outline']] == [p[0] for p in prior['loaded']['outline']]
                changed = glyph != prior
                diagonal_changes[mode] += changed and char in 'VvWw'
                straight_changes[mode] += changed and char in 'ilI1H'
                curve_changes[mode] += changed and char in 'mno0358'
            pixels = scalar_mask(row['glyphs'], row['height'], list(range(256)))
            assert pixels == (OUT/mode/f'{row["id"]}-mask.bin').read_bytes()
            for palette in ('light', 'dark'):
                expected = pixels if palette == 'dark' else bytes(255-a for a in pixels)
                assert Image.open(OUT/mode/f'{row["id"]}-{palette}.png').convert('L').tobytes() == expected
            assert sha(Path(row['font_path'])) == row['font_sha256']
    oracle.close()
    assert curve_changes['4'] and curve_changes['8']
    font = ImageFont.truetype(str(args.label_font), 13)
    head = ImageFont.truetype(str(args.label_font), 17)
    pages = [('overview-12pt', [r for r in datasets['0'] if r['point_size'] == 12])]
    pages += [(name.lower().replace(' ', '-'), [r for r in datasets['0'] if r['label'] == name]) for name in fonts]
    images = []
    for title, group in pages:
        for palette, bg, fg in (('light', 255, 0), ('dark', 0, 255)):
            height = 100 + sum(r['height'] + 26 for r in group)
            sheet = Image.new('RGB', (1664, height), (bg,)*3)
            draw = ImageDraw.Draw(sheet)
            draw.text((10, 8), 'Raw coverage / encoded blend | curve-width trial | ' + title, font=head, fill=(fg,)*3)
            draw.text((10, 35), 'Actual integer 8-16pt, 96 DPI, 100% scale. No coverage ramp or floor. View at 100% image zoom.', font=font, fill=(fg,)*3)
            for col, label in enumerate(('Current raw / nearest 50%', 'Raw + curve 1/16 pixel', 'Raw + curve 1/8 pixel', 'Stock Qt')):
                draw.text((col*416+10, 61), label, font=head, fill=(fg,)*3)
            y, crops = 90, []
            for row in group:
                draw.text((10, y), f'{row["label"]} | {row["point_size"]}pt', font=font, fill=(fg,)*3)
                y += 20
                for col, mode in enumerate(('0', '4', '8', 'qt')):
                    image = Image.open(OUT/mode/f'{row["id"]}-{palette}.png').convert('RGB')
                    assert all(v == bg for v in image.crop((400, 0, 620, image.height)).tobytes())
                    image = image.crop((0, 0, 400, image.height))
                    x = col*416+10
                    sheet.paste(image, (x, y))
                    crops.append((x, y, image))
                y += row['height']+6
            target = OUT/f'raw-curves-{title}-{palette}.png'
            sheet.save(target)
            with Image.open(target) as saved:
                for x, y, image in crops:
                    assert saved.crop((x, y, x+image.width, y+image.height)).tobytes() == image.tobytes()
            images.append(dict(file=target.name, sha256=sha(target)))
    assert os.environ == before
    result = dict(kind='fixed S6 curve-width strengths with raw coverage; component only', text=TEXT,
                  conditions=[{k: v for k, v in r.items() if k not in ('font_path', 'glyphs', 'runs')} |
                              dict(font_file=Path(r['font_path']).name) for r in datasets['0']],
                  images=images, trace_decisions=decisions, diagonal_changed_occurrences=diagonal_changes,
                  straight_changed_occurrences=straight_changes, curve_changed_occurrences=curve_changes,
                  patch_sha256=sha(patch), renderer_source_sha256=sha(chart_source),
                  checker_sha256=sha(Path(__file__)),
                  libraries={k: sha(p) for k, p in libraries.items()},
                  limits=['Raw rasterization is unchanged, but geometry can move edge pixels',
                          'Only linked round Y segments receive the existing expansion',
                          'No installed libraries or application profiles changed'])
    (OUT/'captures.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS 81 conditions x3, native rasters/raw composition/traces/20 sheets', diagonal_changes, straight_changes, flush=True)


if __name__ == '__main__':
    main()
