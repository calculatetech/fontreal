#!/usr/bin/env python3
"""Capture stock Qt and qualified V2 O without changing retained V1 evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

from PIL import Image
import docs_test

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/kde-v2'
PUBLIC = ROOT / 'docs/images/kde-v2'
ROLES = [('General', 'Noto Sans', 10), ('Fixed width', 'Hack', 10),
         ('Small', 'Noto Sans', 8), ('Toolbar', 'Noto Sans', 10),
         ('Menu', 'Noto Sans', 10), ('Window title specimen', 'Noto Sans', 10)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixels(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


def qualified(record_path, observed_path, receipt_path):
    receipt = json.loads(receipt_path.read_text())
    assert receipt['record'] == sha(record_path)
    assert receipt['observed_record'] == sha(observed_path)
    assert len(receipt['rows']) == 500
    numerical = ROOT / 'build/v2-coverage/tested-sources.json'
    assert sha(numerical) == receipt['numerical_receipt']
    for group in ('sources', 'opaque_sources'):
        for source, digest in receipt[group].items():
            if not source.startswith('docs/'):
                assert sha(ROOT / source) == digest, source
    records = [json.loads(p.read_text()) for p in (record_path, observed_path)]
    for record in records:
        for library in record['libraries'].values():
            assert sha(library['library']) == library['sha256']
        source = Path(record['libraries']['candidate']['library']).parents[2] / 'candidate-source/src/base'
        for key, name in [('processor', 'fontreal_coverage.cpp'), ('declaration', 'fontreal_coverage.h'),
                          ('v2_processor', 'fontreal_v2_coverage.cpp'), ('v2_declaration', 'fontreal_v2_coverage.h')]:
            assert record['spec'][key] == sha(ROOT / 'src' / name) == sha(source / name)
        assert record['spec']['patch'] == sha(ROOT / 'patches/freetype-2.14.2-fontreal.patch')
    assert records[0]['spec']['v2_observer'] is None
    assert records[1]['spec']['v2_observer'] == sha(ROOT / 'tests/v2_freetype_observe.h')
    assert {k: v for k, v in records[0]['spec'].items() if k != 'v2_observer'} == {
        k: v for k, v in records[1]['spec'].items() if k != 'v2_observer'}
    return records, receipt


def capture(binary, palette, mode, library, qt, fonts):
    output = WORK / f'{palette}-{mode}.png'
    observation = WORK / f'{palette}-{mode}.observation'
    observation.unlink(missing_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('FONTREAL_', 'QT_'))
           and k not in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'FT2_DEBUG', 'FREETYPE_PROPERTIES')}
    env.update(QT_QPA_PLATFORM='offscreen', QT_FONT_DPI='96', QT_SCALE_FACTOR='1',
               QT_PLUGIN_PATH=subprocess.check_output(['qtpaths6', '--query', 'QT_INSTALL_PLUGINS'], text=True).strip(),
               LD_LIBRARY_PATH=os.pathsep.join((str(library.parent), str(qt.resolve()))))
    env['QT_PLUGIN_PATH'] = str(qt / 'qt6/plugins')
    if mode != 'stock':
        env.update(FONTREAL_PROFILE='k3' if mode == 'k3' else 'o', FONTREAL_FT_RENDERING='1',
                   FONTREAL_FT_CONTRAST='weighted', FONTREAL_FT_EXECUTABLE=str(binary.resolve()),
                   FONTREAL_RENDERING='1', FONTREAL_BLEND='encoded', FONTREAL_CONTRAST='weighted',
                   FONTREAL_FITTING='native')
    if mode == 'observed':
        env['FONTREAL_V2_OBSERVATION'] = str(observation.resolve())
    heading = 'Stock Qt' if mode == 'stock' else 'Fontreal V2 ' + ('K3' if mode == 'k3' else 'O') + ' NORMAL'
    with (WORK / f'{palette}-{mode}.log').open('w') as log:
        subprocess.run([str(binary.resolve()), palette, heading, str(output.resolve()), *map(str, fonts)],
                       env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
    maps = Path(str(output) + '.maps').read_text()
    libraries = {}
    for name in ('libfreetype.so.', 'libQt6Core.so.', 'libQt6Gui.so.', 'libQt6Widgets.so.'):
        loaded = {Path(line.split()[-1]).resolve() for line in maps.splitlines() if name in line}
        assert len(loaded) == 1, (mode, name, loaded)
        actual = loaded.pop()
        if name.startswith('libfreetype'):
            assert actual == library.resolve(), (mode, actual, library)
        else:
            assert actual.parent == qt.resolve(), (mode, actual, qt)
        libraries[name] = dict(file=actual.name, sha256=sha(actual))
    metadata = json.loads(Path(str(output) + '.json').read_text())
    assert metadata['dpi'] == 96 and metadata['device_pixel_ratio'] == 1
    assert [(r['role'], r['family'], r['point_size']) for r in metadata['roles']] == ROLES
    image = Image.open(output).convert('RGB')
    assert image.size == (600, 570)
    for role in metadata['roles']:
        x, y, width, height = [role[k] for k in ('x', 'y', 'width', 'height')]
        assert width > 0 and height > 0 and 0 <= x < x + width <= 600 and 0 <= y < y + height <= 570
        crop = image.crop((x, y, x + width, y + height))
        assert len(set(crop.get_flattened_data())) > 4
        role.update(palette=palette, scale=1, crop_pixels_sha256=pixels(crop),
                    font_file=fonts[1 if role['role'] == 'Fixed width' else 0].name,
                    font_table_identity=['head', 'cmap', 'name'])
    result = dict(source_id=f'{palette}-{mode}', mode=mode, palette=palette,
                  libraries=libraries, roles=metadata['roles'], png_sha256=sha(output), pixels_sha256=pixels(image))
    if mode == 'observed':
        header, data = observation.read_bytes().split(b'\n', 1)
        profile, width, rows, left, top, high_width, high_rows = map(int, header.split())
        assert profile == 1 and width > 0 and rows > 0
        assert (high_width, high_rows) == (4 * (width + 6), 4 * (rows + 6))
        assert len(data) == width * rows + high_width * high_rows and any(data[:width * rows])
        result['passive_observation'] = dict(profile=profile, width=width, rows=rows, left=left, top=top,
            high_width=high_width, high_rows=high_rows, sha256=sha(observation),
            registration='Existing SS14 adapter: high origin is four times (left minus 3, top minus 3).')
    return image, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--observed-record', type=Path, required=True)
    parser.add_argument('--qt-bundle', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, default=ROOT / 'results/v2-freetype/receipt.json')
    args = parser.parse_args()
    records, receipt = qualified(args.record, args.observed_record, args.receipt)
    retained = [ROOT / 'tests/kde_selected_comparison.cpp', ROOT / 'tests/kde_selected_comparison_test.py',
                *(ROOT / 'docs/images/kde-selected').rglob('*')]
    before = {str(p.relative_to(ROOT)): sha(p) for p in retained if p.is_file()}
    WORK.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    binary = WORK / 'kde-comparison'
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Widgets'], text=True))
    subprocess.run(['c++', '-std=c++17', '-O2', '-fPIC', str(ROOT / 'tests/kde_selected_comparison.cpp'),
                    *flags, '-o', str(binary)], check=True)
    fonts = [Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'),
             Path('/usr/share/fonts/truetype/hack/Hack-Regular.ttf')]
    font_records = [dict(file=p.name, sha256=sha(p), version_number=subprocess.check_output(
        ['fc-scan', '--format', '%{fontversion}', str(p)], text=True).strip()) for p in fonts]
    ordinary, observed = records
    qt_packages = []
    for variant, folder in [('stock', 'original'), ('candidate', 'packages')]:
        destination = WORK / ('qt-' + variant)
        destination.mkdir(exist_ok=True)
        for package in ('libqt6core6t64', 'libqt6gui6', 'libqt6widgets6', 'libqt6dbus6', 'qt6-qpa-plugins'):
            matches = list((args.qt_bundle / folder).glob(package + '_*_amd64.deb'))
            assert len(matches) == 1, (variant, package, matches)
            archive = matches[0]
            fields = subprocess.check_output(['dpkg-deb', '-f', str(archive), 'Package', 'Version', 'Source'], text=True)
            assert 'qt6-base' in fields and '6.10.2+dfsg-7' in fields, fields
            subprocess.run(['dpkg-deb', '-x', str(archive), str(destination)], check=True)
            qt_packages.append(dict(variant=variant, file=archive.name, sha256=sha(archive), fields=fields.strip()))
    qt_stock = WORK / 'qt-stock/usr/lib/x86_64-linux-gnu'
    qt_candidate = WORK / 'qt-candidate/usr/lib/x86_64-linux-gnu'
    captures, witnesses = [], []
    for palette in ('light', 'dark'):
        images, current = {}, {}
        for mode, record, variant, qt in [('stock', ordinary, 'stock', qt_stock),
                ('o', ordinary, 'candidate', qt_candidate), ('observed', observed, 'candidate', qt_candidate),
                ('k3', ordinary, 'candidate', qt_candidate)]:
            images[mode], current[mode] = capture(binary, palette, mode,
                Path(record['libraries'][variant]['library']), qt, fonts)
            captures.append(current[mode])
        assert images['o'].tobytes() == images['observed'].tobytes()
        witness = dict(palette=palette, ordinary_observed_whole_image_equal=True)
        for mode in ('stock', 'k3'):
            left = images['o'].crop((0, 55, 600, 570))
            right = images[mode].crop((0, 55, 600, 570))
            count = sum(a != b for a, b in zip(left.get_flattened_data(), right.get_flattened_data()))
            assert count > 0, (palette, mode)
            witness[f'o_vs_{mode}_different_pixels_below_heading'] = count
        witnesses.append(witness)
        sheet = Image.new('RGB', (1200, 570))
        sheet.paste(images['stock'], (0, 0))
        sheet.paste(images['o'], (600, 0))
        destination = PUBLIC / f'kde-defaults-{palette}.png'
        sheet.save(destination)
        reopened = Image.open(destination).convert('RGB')
        for mode, offset in [('stock', 0), ('o', 600)]:
            assert reopened.crop((offset, 0, offset + 600, 570)).tobytes() == images[mode].tobytes()
            for role in current[mode]['roles']:
                x, y, width, height = [role[k] for k in ('x', 'y', 'width', 'height')]
                assert pixels(reopened.crop((offset + x, y, offset + x + width, y + height))) == role['crop_pixels_sha256']
    assert before == {name: sha(ROOT / name) for name in before}
    subprocess.run(['git', 'diff', '--exit-code', '--', 'docs/images/kde-selected',
                    'tests/kde_selected_comparison.cpp', 'tests/kde_selected_comparison_test.py'], cwd=ROOT, check=True)
    manifest = dict(profile='Fontreal V2 O NORMAL', alternative='K3 NORMAL (witness only)', logical_dpi=96, scale=1,
        layout='Stock Qt left, Fontreal V2 O NORMAL right. Direct RGB paste without resizing or retouching.',
        configuration='Offscreen Qt Widgets; stock font configuration; active Fontreal uses native fitting, grayscale, whole pixels and encoded blending.',
        scope='Native Qt Widgets, Fusion style, six KDE roles. Window-title row is a font specimen, not a KWin decoration.',
        proof_scope='Actual Qt callback, qualified opaque FreeType libraries, and complete ordinary-observed pixel equality. No independent replay claim for every screenshot glyph.',
        qualification=dict(source_id='SS14 C1 ordinary and observed FreeType', sha256=sha(args.receipt),
            ordinary_record_sha256=sha(args.record), observed_record_sha256=sha(args.observed_record),
            numerical_receipt_sha256=receipt['numerical_receipt'], independent_freetype_rows=len(receipt['rows']),
            freetype_source_version=ordinary['spec']['source']),
        sources=[dict(file=p.name, sha256=sha(p)) for p in (ROOT / 'tests/kde_selected_comparison.cpp', Path(__file__))],
        retained_v1=[dict(file=Path(name).name, sha256=digest) for name, digest in before.items()],
        qt_packages=qt_packages, fonts=font_records, captures=captures, witnesses=witnesses,
        images=[dict(file=p.name, sha256=sha(p), width=1200, height=570) for p in sorted(PUBLIC.glob('*.png'))])
    readme = (ROOT / 'README.md').read_text()
    for name in ('kde-defaults-light.png', 'kde-defaults-dark.png', 'manifest.json'):
        assert 'docs/images/kde-v2/' + name in readme
    assert {p.name for p in PUBLIC.iterdir()} <= {'kde-defaults-light.png', 'kde-defaults-dark.png', 'manifest.json'}
    path = PUBLIC / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    for value in docs_test.strings(manifest):
        assert not docs_test.issues(value, metadata=True), value
    for image_path in PUBLIC.glob('*.png'):
        assert not any(docs_test.issues(v, metadata=True) for v in docs_test.png_text(image_path.read_bytes()))
    (WORK / 'retained-v1.json').write_text(json.dumps(before, indent=2) + '\n')
    print('PASS V2 O, actual callback, eight native captures, six roles, both palettes, whole-image and crop identity, V1 unchanged, portable assets')
    print(json.dumps(witnesses))


if __name__ == '__main__':
    main()
