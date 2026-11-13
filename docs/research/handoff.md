# Fontreal rendering handoff

Resume on branch `feature/gtk-rendering` in `calculatetech/fontreal`. Read this document, the [roadmap](../roadmap.md), and the [geometry analysis](16pt-geometry.md) before changing the renderer. FR-018 remains the active task. This document describes research inputs and resumption steps. The roadmap owns task state.

## Current direction

The latest user judgment is: “50% is more accurate in more cases,” but nothing meets the full visual target. Every comparison needs stock Qt as its control. Normal hinting with a 242 floor is a different treatment and cannot serve as that control.

The earlier 16pt result remains a useful geometry reference. The later judgment supersedes any claim that the rendering is generally accepted. Continue toward crisp strokes with source-based proportions and predictable pixel rounding. Preserve the working Qt and browser presets while this research continues.

The target favors pixel alignment over exact low-density geometry. A detected width of 1.5 pixels must round to two, while 1.4 rounds to one. Curves and diagonals still need softened edges. Avoid weak crowns, inconsistent stroke intensity, and excessive diagonal weight. Test font choice, point size, scale, weight, italic, and background together. Do not add website-specific rules or substitute every light face with regular.

## Exact experiment

The candidates force FreeType automatic monochrome hinting, then rasterize grayscale masks. A per-glyph coverage floor raises values from the cutoff through 241 to 242. The cutoff is 128 for light faces and 160 for regular or heavier faces. Candidate glyphs use whole-device-pixel origins, alpha-over composition, and linear-light black/white blending encoded to sRGB.

The original strong Y-width rule in `af_latin_compute_stem_width` rounds with `(dist + 16) & ~63`. One pixel is 64 units. That gives a 75% remainder threshold for horizontal-stroke thickness. The experiment changes only 16 to 32, giving a 50% threshold. Standard-width matching still runs first. This does not replace stem detection or every alignment rule. The X-width monochrome branch already rounds at 50%.

The [experimental patch](../../patches/freetype-2.14.2-nearest-y-experiment.patch) applies to clean FreeType 2.14.2. It is separate from the deployed browser patch. Do not stack the old width-override experiment or set `FONTREAL_TEST_STROKE_WIDTH` for this comparison. Retain FreeType's source notices and license when distributing modified FreeType.

The corrected [small-point sheets](16pt-geometry.md#smaller-points-and-explicit-italic-comparisons) show 75% fitting, 50% fitting, and stock Qt. The [capture record](../images/browser-common-ground/stockqt-smallpt-captures.json) identifies fonts, source strips, layouts, sizes, and image hashes. These are lossless component images. View them at one image pixel per display pixel.

The reference capture uses Qt 6.10.2, FreeType 2.14.2, 96 logical DPI, and 100% scale. Qt resolves points as follows:

| Requested pt | 8 | 9 | 10 | 11 | 11.25 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Resolved px | 11 | 12 | 13 | 15 | 15 | 16 | 17 | 19 | 20 | 21 |

All 22 faces and ten sizes form 220 conditions. The corrected sheets display ten faces, including six italic or bold italic faces. The full original [point-size record](../images/browser-common-ground/point-benchmark242-captures.json) retains the 22-face selection and font hashes.

For Noto Sans Regular, 75% and 50% produce identical pixels at all tested points below 16pt. Changing this constant alone cannot improve those rows. At 16pt, the n crown grows from about 0.981px to 1.953px, while its upright stays near 2px. Raw crown-column coverage changes from `[250, 9, 0, 0]` to `[246, 255, 8, 0]`. This fixes that particular two-pixel crown. It does not establish a general solution.

The [16pt geometry analysis](16pt-geometry.md) compares original outlines, traced Qt outlines, and candidate outlines. Original Qt is closer to source geometry than the original 75% benchmark under the recorded contour metric. The 50% change improves twelve face averages, leaves nine unchanged, and slightly worsens Noto Sans Bold Italic. Geometric error is not a readability score. The [nearest-Y record](../images/browser-common-ground/nearest-y-captures.json) retains the measurements and build identity.

## Resume on another machine

Clone the repository and select the task branch:

```sh
git clone git@github.com:calculatetech/fontreal.git
cd fontreal
git switch feature/gtk-rendering
```

Builds and raw results are ignored. They are not transferred by Git. Configure `build/` and `results/` on a suitable storage volume before building. Existing symlinks are local configuration and are not part of the checkout. Keep new output under those two roots. The committed images and capture records remain available without rebuilding.

The preserved [C++ fixture](../../tests/point_benchmark_chart.cpp) is the exact renderer used for the point experiments. Its `stock` mode uses Qt's painter with Fontreal disabled. Its `candidate` mode consumes the recorded Qt layout and uses the selected FreeType library. The [sheet assembler](../../tests/point_benchmark_sheets.py) copies native pixels from those outputs and checks every saved crop.

Use a C++17 compiler, Qt 6 Gui development files, FreeType development files, `pkg-config`, Fontconfig, Python 3, and Pillow. Run from a graphical Qt session at 96 logical DPI and 100% scale for the reference comparison. The assembler rejects other recorded DPI or scale values. Different Qt, FreeType, Fontconfig, or font versions need a fresh recorded baseline.

Prepare the 220 inputs from installed font files. This checks exact font hashes and stops if a reference font is unavailable. Install the matching font version before retrying. Do not silently substitute a font.

```sh
mkdir -p build/point-handoff results/point-handoff
python3 - <<'PY'
from pathlib import Path
import hashlib, json, subprocess
record = json.loads(Path('docs/images/browser-common-ground/point-benchmark242-captures.json').read_text())
files = [Path(p) for p in subprocess.check_output(['fc-list', '-f', '%{file}\n'], text=True).splitlines()]
rows = []
for r in record['conditions']:
    matches = [p for p in files if p.name == r['font_file'] and hashlib.sha256(p.read_bytes()).hexdigest() == r['font_sha256']]
    assert matches, 'Missing exact font: ' + r['font_file']
    rows.append({k: r[k] for k in ('id', 'label', 'point_size', 'cutoff')} |
                dict(font_path=str(matches[0].resolve()), logical_dpi=96, scale=1))
assert len(rows) == 220
Path('build/point-handoff/input.json').write_text(json.dumps(rows, indent=2) + '\n')
PY
c++ -std=c++17 -fPIC -include algorithm tests/point_benchmark_chart.cpp \
  $(pkg-config --cflags --libs Qt6Gui freetype2) -o build/point-handoff/chart
```

Use two isolated builds from the same FreeType source and build configuration. Keep one unchanged and apply the experimental patch to the other. The original native builder, `tools/build-freetype.py`, requires its exact Ubuntu amd64 package revision. It is not a generic Debian 13 builder. On other systems, build the research libraries locally from the pinned source with that system's development dependencies. Do not install an Ubuntu library into Debian.

The pinned source archive is `freetype_2.14.2+dfsg.orig.tar.xz`, SHA-256 `9a2bdc2c992fa82a309eccf5e8bcbf2a380a98ba22f9f2ec7e56767739a19a0a`. The authenticated source inventory and download location are in [the native builder](../../tools/build-freetype.py). Extract it into a clean storage-backed directory. The original `src/autofit/aflatin.c` SHA-256 is `30189813d762de77aea2a0d9010a6b7656657809028ac433f92b3c027eeda7f7`. Make sure that this hash matches before applying the patch. Apply it with `patch --batch -p1 -i` and the absolute patch filename, from the copied source root.

For both builds, use `CFLAGS=-O2` and `configure --with-harfbuzz=dynamic` in separate build directories. Retain the same zlib, bzip2, PNG, HarfBuzz, Brotli, and pthread features. Save configuration logs, source hashes, exported-symbol comparisons, and new library hashes. Compiler and dependency changes can alter binary hashes. The old hashes identify the earlier builds and are not expected outputs for another toolchain.

Set `FONTREAL_STOCK_FT_DIR` to the unchanged build's `.libs` directory. Set `FONTREAL_NEAREST_FT_DIR` to the patched build's `.libs` directory. Then render all three columns:

```sh
python3 - <<'PY'
from pathlib import Path
import os, subprocess
base = {k: v for k, v in os.environ.items()
        if not k.startswith('FONTREAL_') and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'FREETYPE_PROPERTIES')}
base['FONTREAL_RENDERING'] = '0'
stock = str(Path(os.environ['FONTREAL_STOCK_FT_DIR']).resolve())
nearest = str(Path(os.environ['FONTREAL_NEAREST_FT_DIR']).resolve())
out = Path('results/point-handoff')
steps = [('stock', stock, 'build/point-handoff/input.json', out/'stock'),
         ('candidate', stock, str(out/'stock/rows.json'), out/'75'),
         ('candidate', nearest, str(out/'stock/rows.json'), out/'50')]
for mode, library, source, target in steps:
    env = dict(base, LD_LIBRARY_PATH=library)
    if mode == 'candidate':
        env['FREETYPE_PROPERTIES'] = 'autofitter:no-stem-darkening=1'
    subprocess.run(['build/point-handoff/chart', mode, source, str(target)], env=env, check=True)
PY
python3 tests/point_benchmark_sheets.py \
  results/point-handoff/75 results/point-handoff/50 results/point-handoff/stock \
  results/point-handoff/sheets --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')"
```

The stock column keeps Qt's own fitting, coverage, glyph origins, and blending. Both candidates consume the same Qt glyph identities and positions, then apply their own whole-pixel origins. Stock Qt reflects the desktop's font configuration. It is not a universal KDE configuration. Record that configuration on the new machine before attributing a difference to the patch.

The corrected images and native fixture were checked against all earlier 220 stock, 75%, and 50% outputs on the capture system. The new-machine rebuild itself remains untested. Before experimenting further, reproduce the Noto n crown result and check native masks independently with the existing `Oracle` in `tests/browser_stroke_axis_test.py`. Keep per-glyph floor, overlap, and final blend checks separate from geometry checks. The saved sheet checks alone do not prove the rasterizer correct.

## Next investigation

Trace the smaller-size horizontal-stroke path before selecting another filter. Inspect segment classification, stem links, standard-width matching, the strong Y-width branch, blue-zone alignment, and final edge placement. Measure source widths, fitted widths, and raw coverage on the same glyphs. Distinguish a missing link from a width rule that does not apply, or later alignment that changes the crown.

Use stock Qt, the original 75% benchmark, and the 50% candidate in every chart. Include Noto Sans, Noto Serif, Hack, and a light face. Keep i/l/I/1, 3/5/8, V/W, full words, italic, and bold italic visible. Preserve a fixed 16pt reference while investigating 8–15pt. Do not vary coverage thresholds while testing fitting geometry. Define a bounded experiment before changing further native rules.

After a component result wins, qualify actual Firefox and Floorp output with downloaded and variable fonts, both backgrounds, small labels, headings, and mixed styles. Keep the user's working browser data. Further coverage includes Electron/Teams and Flatpak, GTK/GNOME, Wine, and a feasibility study for Windows 11. Their order and remaining requirements belong to the roadmap.

The existing [Qt package workflow](../build-system.md) targets the running Debian 13 or Ubuntu system. The [browser activation guide](../experiments/browser-masks.md) describes the earlier deployed browser preset. Neither workflow deploys this new fitting experiment. This handoff makes no system, profile, repository-visibility, or release change.
