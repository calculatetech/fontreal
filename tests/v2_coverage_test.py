#!/usr/bin/env python3
"""Prove the private numerical V2 entry against complete retained NORMAL sources."""
import argparse
import ctypes as C
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'tools')]
from browser_stroke_axis_test import Bitmap, Oracle
from stem_core_test import concentrate
from stroke_profiles import refine
from pixel_references_test import reference, registered, oracle_mask
from arial_coherence_test import independent
from selected_profile_test import expected_mask as legacy_mask
import pixel_reference_profiles as profiles

BASE = '3f07596aa0707f8d647c299ec8d2c88eff481e7e'
OWNED = ('src/fontreal_v2_coverage.cpp', 'src/fontreal_v2_coverage.h',
         'tests/v2_coverage_probe.cpp', 'tests/v2_coverage_test.py', 'docs/experiments/supersampling.md')
PHASES = [(x, y) for x in range(-2, 3) for y in range(-2, 3)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def tree(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}


def load(root, meta):
    path = root/meta['file']
    assert sha(path) == meta['sha256'], path
    return json.loads(path.read_text())


def d_reference(raw, near=True, connected=True):
    values = bytes(raw['pixels'])
    fitted = concentrate(values, values, raw['width'], near_ties=near)[0]['native-area']
    return list(refine(values, fitted, raw['width'], connected=connected)[0]['corners'])


class Buffer:
    def __init__(self, mask, padding=0, negative=False):
        self.w, self.h = mask['width'], mask['height']
        self.stride = self.w+padding if self.w else 0
        self.data = (C.c_ubyte * (64+self.stride*self.h))(*([173]*(64+self.stride*self.h)))
        origin = 32+(self.h-1)*self.stride if negative and self.h else 32
        self.bitmap = Bitmap(self.h, self.w, -self.stride if negative else self.stride,
                             C.cast(C.byref(self.data, origin), C.POINTER(C.c_ubyte)), 256, 2, 0, None)
        self.origin = origin
        for y in range(self.h):
            for x in range(self.w):
                self.data[origin+y*self.bitmap.pitch+x] = mask['pixels'][y*self.w+x]
        self.before = bytes(self.data)
        self.metadata = bytes(self.bitmap)

    def pixels(self):
        return [self.data[self.origin+y*self.bitmap.pitch+x] for y in range(self.h) for x in range(self.w)]

    def check(self, writable):
        assert bytes(self.bitmap) == self.metadata
        allowed = {self.origin+y*self.bitmap.pitch+x for y in range(self.h) for x in range(self.w)} if writable else set()
        assert all(i in allowed or v == self.before[i] for i, v in enumerate(self.data))


class Kernel:
    def __init__(self, path, observed):
        self.library = C.CDLL(str(path))
        self.entry = self.library.fontreal_v2_test
        self.entry.argtypes = [C.POINTER(Bitmap), C.POINTER(Bitmap), C.c_int,
                               C.POINTER(C.c_ubyte), C.c_size_t, C.POINTER(C.c_long), C.c_int]
        self.entry.restype = C.c_int
        self.observed = observed
        self.calls = 0
        self.allocations = 0

    def call(self, raw, high, mode, expected, d, representation=(0, False, 0, False), invalid=None):
        rp, rn, hp, hn = representation
        a, b = Buffer(raw, rp, rn), Buffer(high, hp, hn)
        d_buffer = (C.c_ubyte * len(d))(*([91]*len(d)))
        stats = (C.c_long * 6)()
        null_memory = 0
        raw_pointer, high_pointer = C.byref(a.bitmap), C.byref(b.bitmap)
        if invalid == 'mode': mode = 7
        elif invalid == 'format': a.bitmap.pixel_mode = 1
        elif invalid == 'levels': b.bitmap.num_grays = 255
        elif invalid == 'pitch': a.bitmap.pitch = max(0, a.w-1)
        elif invalid == 'high-pitch': b.bitmap.pitch = 0
        elif invalid == 'registration': b.bitmap.width -= 1
        elif invalid == 'null-buffer': a.bitmap.buffer = C.POINTER(C.c_ubyte)()
        elif invalid == 'null-high': high_pointer = None
        elif invalid == 'null-raw': raw_pointer = None
        elif invalid == 'null-memory': null_memory = 1
        elif invalid == 'overflow': a.bitmap.width = 0xffffffff
        elif invalid == 'min-pitch': b.bitmap.pitch = -2147483648
        a.metadata, b.metadata = bytes(a.bitmap), bytes(b.bitmap)
        status = self.entry(raw_pointer, high_pointer, mode, d_buffer, len(d), stats, null_memory)
        self.calls += 1
        assert status == (2 if invalid else 0), (invalid, status)
        assert stats[0] == stats[3] == 0 and stats[1] == stats[2]
        if invalid:
            assert stats[1] == stats[4] == 0
            assert bytes(a.data) == a.before
        else:
            assert a.pixels() == expected
            if raw['pixels']: assert stats[1] > 0
            self.allocations += stats[1]
            if self.observed:
                assert stats[4] == 1 and stats[5] == 1
                assert list(d_buffer) == d
            else:
                assert stats[4] == 0 and list(d_buffer) == [91]*len(d)
        a.check(not invalid); b.check(False)
        return a.pixels(), list(d_buffer), list(stats)


def choose(phases, score, reverse=False):
    return min(phases, key=lambda p: (-score(p), (-1 if reverse else 1)*(p[0]*p[0]+p[1]*p[1]),
                                      (-1 if reverse else 1)*p[1], (-1 if reverse else 1)*p[0]))


def alternative(d, audit, variant):
    """Deliberately wrong terminal O/K3 alternatives for discrimination witnesses."""
    sums, w = audit['sums'], audit['width']
    result = list(d)
    primary = audit['primary']
    groups = [c['indices'] for c in audit['components']]
    if variant == 'four-connected':
        unseen = {i for i, v in enumerate(d) if v}; groups = []
        while unseen:
            todo = [min(unseen)]; unseen.remove(todo[0]); group = []
            while todo:
                i = todo.pop(); group.append(i)
                for j in (i-w, i+w, i-1, i+1):
                    if j in unseen and abs(i%w-j%w)+abs(i//w-j//w) == 1:
                        todo.append(j); unseen.remove(j)
            groups.append(group)
    if variant in ('prefix', 'four-connected', 'reverse-tie', 'floor-reference', 'all-pixels'):
        selected = set(primary) if variant != 'all-pixels' else set(i for i, v in enumerate(d) if v)
        for group in groups:
            scored = group[:max(1, len(group)//2)] if variant == 'prefix' else group
            best = choose(PHASES, lambda p: sum(sums[p][i]**2 for i in scored), variant == 'reverse-tie')
            for i in group:
                if i in selected: result[i] = max(d[i], (sums[best][i]+(0 if variant == 'floor-reference' else 8))//16)
        return result
    for i in primary:
        group = next(g for g in groups if i in g)
        radius = 2 if variant == 'K5' else 1
        near = [j for j in group if max(abs(j%w-i%w), abs(j//w-i//w)) <= radius]
        if variant == 'cross-component':
            near = [j for j, v in enumerate(d) if v and max(abs(j%w-i%w), abs(j//w-i//w)) <= 1]
        axis = audit['axes'][str(i)]['axis']
        allowed = PHASES if variant == 'forbidden-axis' else [p for p in PHASES if not(axis == 'x' and p[1]) and not(axis == 'y' and p[0])]
        best = choose(allowed, lambda p: sum(sums[p][j]**2 for j in near))
        result[i] = max(d[i], (sums[best][i]+8)//16)
    if variant != 'no-fringe':
        result = [v+(b-a+(0 if variant == 'floor-fringe' else 1))//2 for v, a, b in zip(result, audit['L'], audit['S'])]
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('record', 'normal-manifest', 'qt-manifest'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, default=ROOT/'build/v2-coverage')
    parser.add_argument('--output', type=Path, default=ROOT/'results/v2-coverage')
    args = parser.parse_args()
    build, output = args.build_dir.resolve(), args.output.resolve()
    build.mkdir(parents=True, exist_ok=True)
    paths = {k: getattr(args, k.replace('-', '_')).resolve() for k in ('record', 'normal-manifest', 'qt-manifest')}
    record = json.loads(paths['record'].read_text())
    normal = json.loads(paths['normal-manifest'].read_text()); qt = json.loads(paths['qt-manifest'].read_text())
    assert normal['study'] == 'normal-treatments' and qt['study'] == 'noto-kde-comparison'
    assert [(c['font'], c['points']) for c in normal['cases']] == [(fi, pt) for fi in range(5) for pt in (8, 10, 11, 12)]
    assert [(c['points'], c['polarity']) for c in qt['cases']] == [(pt, pol) for pt in (8, 10, 11, 12) for pol in ('light', 'dark')]
    assert all(qt['sources'][k] == v for k, v in normal['sources'].items())
    sources = {**normal['sources'], **qt['sources']}
    for path, value in sources.items():
        assert sha(ROOT/path) == value == hashlib.sha256(subprocess.check_output(['git', 'show', BASE+':'+path], cwd=ROOT)).hexdigest(), path
    provider = Path(record['libraries']['stock']['library']).resolve()
    assert sha(provider) == record['libraries']['stock']['sha256'] == normal['provider']['sha256'] == qt['inputs']['stock']['libfreetype.so.']['sha256']
    protected = {str(root): tree(root) for root in (paths['normal-manifest'].parent, paths['qt-manifest'].parent)}
    provider_before = sha(provider)
    owned_before = {s: sha(ROOT/s) for s in OWNED}
    commands = []
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'freetype2'], text=True))
    for observed in (False, True):
        destination = build/('observed.so' if observed else 'ordinary.so')
        command = ['c++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-fvisibility=hidden', *flags,
                   *(['-DFONTREAL_V2_OBSERVE_D'] if observed else []), str(ROOT/'src/fontreal_v2_coverage.cpp'),
                   str(ROOT/'tests/v2_coverage_probe.cpp'), '-o', str(destination)]
        subprocess.run(command, check=True); commands.append(command)
    kernels = [Kernel(build/'ordinary.so', False), Kernel(build/'observed.so', True)]
    witnesses = {}; rows = []; oracle = Oracle(provider); corpus = []; inventories = []
    for ci, case in enumerate(normal['cases']):
        numbers = load(paths['normal-manifest'].parent, case['normal'])
        capture = load(paths['normal-manifest'].parent, case['capture'])
        assert [r['code'] for r in numbers] == list(range(32, 127))
        cap = capture['captures'][0]
        assert len(capture['captures']) == 1 and cap['mode'] == 'native_normal' and cap['target'] == cap['render'] == 0
        assert cap['load_flags'] == 32776 and cap['effective_interpreter'] == 40 and not cap['stem_darkening']
        assert cap['policy'] == 'native' and cap['x_ppem'] == (case['points']*4+1)//3
        assert all(v['no_stem_darkening'] for v in cap['darkening_properties'].values())
        assert [g['code'] for g in cap['glyphs']] == list(range(32, 127))
        for r, g in zip(numbers, cap['glyphs']):
            b = g['bitmap']; pixels = bytes.fromhex(b['rows_hex'])
            raw = dict(left=g['left'], top=g['top'], width=b['width'], height=b['rows'],
                       pixels=[pixels[y*abs(b['pitch'])+x] for y in range(b['rows']) for x in range(b['width'])])
            outline = dict(outline=[[*xy, t] for xy, t in zip(g['outline'], g['tags'])], contours=g['contours'])
            assert r['raw'] == raw and r['outline'] == outline and r['actual_advance'] == g['advance']
            corpus.append((('normal', ci, r['code']), raw, outline, r['normal'], r['trials']['K3'], g['advance']))
        inventories.append(dict(kind='normal', condition=ci, identities=[r['code'] for r in numbers]))
    for ci, case in enumerate(qt['cases']):
        numbers = load(paths['qt-manifest'].parent, case['masks'])
        capture = load(paths['qt-manifest'].parent, case['captures']['approved']['metadata'])
        px = {8: 11, 10: 13, 11: 15, 12: 16}[case['points']]
        assert capture['point_size'] == case['points'] and capture['pixel_size'] == px
        source = capture['source']
        assert source['x_ppem'] == px and source['char_size_26_6'] == px*64 and source['dpi'] == 72
        assert source['load_flags'] == 32776 and source['target'] == source['render'] == 0 and source['interpreter'] == 40
        assert all(v['no_stem_darkening'] for v in source['darkening_properties'].values())
        ids = sorted({g['id'] for s in capture['sections'] for line in s['lines'] for run in line['runs'] for g in run['glyphs']})
        assert len(ids) == 98 and [r['id'] for r in numbers] == [g['id'] for g in capture['glyphs']] == ids
        for r, g in zip(numbers, capture['glyphs']):
            assert r['raw'] == g['raw']
            corpus.append((('qt', ci, r['id']), r['raw'], g, r['normal'], None, g['advance']))
        inventories.append(dict(kind='qt', condition=ci, points=case['points'], polarity=case['polarity'], identities=ids))
    assert len(corpus) == 2684
    cache = {}; empty = None; stride_case = None
    try:
        for sequence, (identity, raw, outline, n, retained_k3, advance) in enumerate(corpus):
            frame = dict(left=raw['left']-2, top=raw['top']-2, width=raw['width']+4, height=raw['height']+4)
            assert n['frame'] == frame and n['masks']['A'] == registered(raw, frame)
            assert registered(oracle_mask(oracle, outline), frame) == n['masks']['A']
            highframe = dict(left=(raw['left']-3)*4, top=(raw['top']-3)*4, width=(raw['width']+6)*4, height=(raw['height']+6)*4)
            assert {k: v for k, v in n['high'].items() if k != 'pixels'} == highframe
            assert registered(oracle_mask(oracle, outline, 4), highframe) == n['high']['pixels']
            d = d_reference(raw)
            assert registered({**raw, 'pixels': d}, frame) == n['masks']['D']
            key = canonical(n)
            if key not in cache:
                expected, audit = reference(n['high'], n['masks']['D'], frame['width'])
                assert all(n['masks'][k] == v for k, v in expected.items())
                assert n['reference']['components'] == audit['components'] and n['reference']['axes'] == audit['axes']
                assert n['reference']['phase_sums'] == [dict(phase=list(p), values=v) for p, v in sorted(audit['sums'].items())]
                assert n['overlay']['primary'] == audit['primary'] and n['overlay']['edges'] == audit['edges']
                k3 = independent(n['masks']['D'], expected['L'], expected['S'], n['reference']['phase_sums'], audit['axes'], audit['primary'], audit['components'], frame['width'])[0]['K3']
                audit.update(width=frame['width'], L=expected['L'], S=expected['S'])
                cache[key] = k3, audit
            k3, audit = cache[key]
            if retained_k3 is not None: assert retained_k3 == k3
            actuals = {}
            for mode, name, expected in ((0, 'O', n['masks']['O']), (1, 'K3', k3)):
                cropped = [expected[(y+2)*frame['width']+x+2] for y in range(raw['height']) for x in range(raw['width'])]
                assert registered({**raw, 'pixels': cropped}, frame) == expected
                outputs = [kernel.call(raw, n['high'], mode, cropped, d)[0] for kernel in kernels]
                assert outputs[0] == outputs[1]
                actuals[name] = registered({**raw, 'pixels': outputs[0]}, frame)
            rows.append(dict(identity=identity, raw=canonical(raw), high=canonical(n['high']), D=canonical(n['masks']['D']),
                             O=canonical(actuals['O']), K3=canonical(actuals['K3']), advance=advance))
            for variant in ('prefix', 'four-connected', 'reverse-tie', 'floor-reference', 'all-pixels', 'K5', 'forbidden-axis', 'no-fringe', 'floor-fringe'):
                if variant in witnesses: continue
                expected = actuals['O'] if variant in ('prefix', 'four-connected', 'reverse-tie', 'floor-reference', 'all-pixels') else actuals['K3']
                wrong = alternative(n['masks']['D'], audit, variant)
                if wrong != expected:
                    i = next(i for i, (a, b) in enumerate(zip(expected, wrong)) if a != b)
                    witnesses[variant] = dict(identity=identity, index=i, actual=expected[i], alternative=wrong[i])
            if actuals['O'] != actuals['K3'] and 'profile-choice' not in witnesses:
                i = next(i for i, (a, b) in enumerate(zip(actuals['O'], actuals['K3'])) if a != b)
                witnesses['profile-choice'] = dict(identity=identity, index=i, O=actuals['O'][i], K3=actuals['K3'][i])
            for variant in ('omitted-near-ties', 'omitted-refinement', 'zero-vote-connected', 'legacy-treatment'):
                if variant in witnesses: continue
                values = bytes(raw['pixels'])
                wrong_d = (list(legacy_mask(values, raw['width'])) if variant == 'legacy-treatment' else
                           d_reference(raw, near=False) if variant == 'omitted-near-ties' else
                           list(concentrate(values, values, raw['width'], near_ties=True)[0]['native-area']) if variant == 'omitted-refinement' else
                           d_reference(raw, connected=False))
                if wrong_d != d:
                    pd = registered({**raw, 'pixels': wrong_d}, frame)
                    refs, _ = profiles.references(n['high'], pd, frame['width']); wrong = profiles.overlays(pd, frame['width'], refs)[0]['O']
                    if wrong != actuals['O']:
                        i = next(i for i, (a, b) in enumerate(zip(actuals['O'], wrong)) if a != b)
                        witnesses[variant] = dict(identity=identity, index=i, actual=actuals['O'][i], alternative=wrong[i])
            if not raw['pixels']:
                assert frame['width'] == frame['height'] == 4 and not any(k3) and advance > 0
                empty = identity, raw, outline, n, retained_k3, advance
            elif stride_case is None and actuals['O'] != actuals['K3'] and raw['pixels'] != list(reversed(raw['pixels'])):
                stride_case = identity, raw, outline, n, k3, advance
            if identity == ('normal', 0, 33):
                assert n['masks']['D'][38] == 211 and actuals['O'][38] == actuals['K3'][38] == 212
                witnesses['hidden-D'] = dict(identity=identity, index=38, D=211, O=212, K3=212)
            if sequence % 95 == 94: print('checked', sequence+1, 'source rows, both profiles/builds', flush=True)
    finally:
        oracle.close()
    assert empty and stride_case
    identity, raw, _, n, k3, _ = stride_case
    d = d_reference(raw); frame = n['frame']; extra_calls = []
    for mode, name, full in ((0, 'O', n['masks']['O']), (1, 'K3', k3)):
        expected = [full[(y+2)*frame['width']+x+2] for y in range(raw['height']) for x in range(raw['width'])]
        for representation in ((5, True, 0, False), (0, False, 7, True)):
            for kernel in kernels: kernel.call(raw, n['high'], mode, expected, d, representation)
            extra_calls.append(dict(identity=identity, profile=name, representation=representation))
        for kernel in kernels:
            eraw, en = empty[1], empty[3]
            kernel.call(eraw, en['high'], 1-mode, [], [])
            kernel.call(raw, n['high'], mode, expected, d)
            relabeled = json.loads(json.dumps(raw)); relabeled['font'] = 'unrelated'; relabeled['code'] = 0x12345
            assert kernel.call(relabeled, n['high'], mode, expected, d)[0] == expected
    invalids = ('mode', 'format', 'levels', 'pitch', 'high-pitch', 'registration', 'null-buffer', 'null-high', 'null-raw', 'null-memory', 'overflow', 'min-pitch')
    for invalid in invalids:
        for kernel in kernels: kernel.call(raw, n['high'], 0, [], d, invalid=invalid)
    # Synthetic arithmetic fixture: diagonal support, not a captured font glyph.
    toy = dict(left=0, top=0, width=2, height=2, pixels=[160, 0, 0, 160])
    toy_high = dict(left=-12, top=-12, width=32, height=32, pixels=[0]*1024)
    for left, top in ((10, 12), (18, 16)):
        for y in range(top, top+4):
            for x in range(left, left+4): toy_high['pixels'][y*32+x] = 255
    toy_frame = dict(left=-2, top=-2, width=6, height=6)
    toy_d = d_reference(toy); toy_padded = registered({**toy, 'pixels': toy_d}, toy_frame)
    toy_expected, toy_audit = reference(toy_high, toy_padded, 6)
    toy_audit['width'] = 6
    four = alternative(toy_padded, toy_audit, 'four-connected')
    assert toy_expected['O'][14] == 160 and four[14] == 255
    toy_k3 = independent(toy_padded, toy_expected['L'], toy_expected['S'],
                         [dict(phase=list(p), values=v) for p, v in toy_audit['sums'].items()],
                         toy_audit['axes'], toy_audit['primary'], toy_audit['components'], 6)[0]['K3']
    for mode, full in ((0, toy_expected['O']), (1, toy_k3)):
        cropped = [full[(y+2)*6+x+2] for y in range(2) for x in range(2)]
        assert registered({**toy, 'pixels': cropped}, toy_frame) == full
        for kernel in kernels: kernel.call(toy, toy_high, mode, cropped, toy_d)
    witnesses['four-connected'] = dict(identity='synthetic-diagonal-arithmetic', index=14,
                                        actual=160, alternative=255, raw=toy, high=toy_high,
                                        scope='Supplemental numerical fixture. No captured glyph, outline or provider claim.')
    required = {'prefix', 'four-connected', 'reverse-tie', 'floor-reference', 'all-pixels', 'K5', 'forbidden-axis', 'no-fringe', 'floor-fringe', 'profile-choice', 'omitted-near-ties', 'omitted-refinement', 'zero-vote-connected', 'legacy-treatment', 'hidden-D'}
    assert required <= witnesses.keys(), required-witnesses.keys()
    for path, value in sources.items(): assert sha(ROOT/path) == value
    assert owned_before == {s: sha(ROOT/s) for s in OWNED}
    assert sha(provider) == provider_before
    assert protected == {str(root): tree(root) for root in (paths['normal-manifest'].parent, paths['qt-manifest'].parent)}
    output = output/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output.mkdir(parents=True)
    result = dict(study='v2-coverage', base_git=BASE, scope='Private numerical kernel; no installed V2 or application coverage.',
                  sources=owned_before, opaque_sources=sources,
                  inputs={k: dict(file=os.path.relpath(v, output), sha256=sha(v)) for k, v in paths.items()},
                  provider=dict(file=provider.name, sha256=provider_before), conditions=inventories,
                  source_rows=len(rows), native_calls_per_build=[k.calls for k in kernels],
                  allocation_counts=[k.allocations for k in kernels], rows=rows, witnesses=witnesses,
                  stride_cases=extra_calls, invalid_arguments=list(invalids),
                  oracle_cache=dict(distinct=len(cache), note='Only scalar expectations are shared for equal complete source objects. Every identity calls both real native builds and profiles.'))
    (output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    receipt = dict(result, compile_commands=commands, input_graphs=protected,
                   output=os.path.relpath(output, ROOT), output_graph=tree(output),
                   check_command=[sys.executable, '-B', 'tests/v2_coverage_test.py', *sys.argv[1:]],
                   compiler=subprocess.check_output(['c++', '--version'], text=True).splitlines()[0])
    (build/'tested-sources.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS:', len(rows), 'rows; O/K3 ordinary/observed, exact same-call D, source rasters, guards, strides and ownership')
    print(output)


if __name__ == '__main__':
    main()
