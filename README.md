# Fontreal

The [roadmap](docs/roadmap.md) covers KDE, GNOME, Wine, and conditional Windows 11 support.

The [deployment decision](docs/research/distribution.md) proposes distro Qt packages, separate session activation, tested rollback, and an APT distribution channel. Desktop installation is planned. The current preview remains isolated.

The [KDE path checks](docs/experiments/kde-paths.md) compare real nested KWin titles, a Plasma applet host, and Qt Quick against independent pixel predictions.

The [real Konsole comparison](docs/experiments/kde-preview.md) builds and launches an isolated Qt prototype with stock, linear, and encoded choices, plus optional mild contrast and the user's Inconsolata Nerd Font terminal selection.

The separate [diagonal edge study](docs/experiments/diagonal-edges.md) compares the remaining W/V fuzziness with two tighter gray transitions and automatic-hinted binary output. Open it with `--edges`. The ordinary seven-row experiment stays available without that flag.

A controlled Linux font experiment. The target is solid, pixel-aligned strokes with softened curves and diagonals. Shape fidelity comes second. Human comparison decides whether the result looks right. Coverage measurements explain the pixels.

## Build and open

Requires CMake 3.22 or later, a C++17 compiler, Qt 6.6 or later with Widgets, FreeType development files, and an installed scalable TrueType font. The default font lookup uses `fc-match`.

    cmake -S . -B build -G Ninja
    cmake --build build
    ./build/fontreal

The native window opens with the installed `sans-serif` font. Change the font file, size, software scale, phase, placement, background, or blend. The sample accepts printable ASCII, up to 96 characters. This first experiment uses TrueType outlines and the first face of a collection. It does not perform complex text shaping.

Compare **Auto mono hints / gray edges** with **TT40 normal / grayscale** and the binary reference. Do not assume that every font gives the same result.

## Inspect the samples

The **Comparison** tab shows each treatment at its actual raster size. The **Pixel detail** tab repeats each pixel of the **Inspect glyph** character eight times in each direction. Select `m`, `n`, `o`, or `g` to inspect arches and bowls. The default is `l`, whose original coverage remains exported as a control. The **Geometry target** tab shows a straight stem, a ring, and a diagonal with fractional and snapped placement. That target is synthetic geometry, not a new font renderer.

The window draws one source pixel per Qt backing-store pixel and scrolls larger images. It does not fit images to the window. A compositor or remote desktop can still transform the backing store before display. Tests verify the application path at Qt device pixel ratios 1 and 1.25. They do not measure your physical display.

The **Scale** control changes geometry before FreeType rasterizes it. For example, size 13 at scale 1.25 requests 16.25 pixels. It does not enlarge a finished bitmap. **Phase** moves the common glyph origins in device pixels and is quantized to 1/64 pixel. **Snap origins** rounds those origins. It does not guarantee that a font's internal stems are aligned. That is one of the differences the treatments expose.

The comparison header shows the effective raster size. For example, 10 pixels at scale 1.5 and 15 pixels at scale 1 both request 15 device pixels. Blend preference can change with effective size. Keep the blend control explicit while comparing neighboring sizes.

The RGB LCD row assumes an RGB stripe display. Its color output is a comparison condition, not a display calibration. The grayscale rows do not require that geometry assumption.

## What is controlled

Every row uses the same font file, sample, effective size, and shared layout. That layout uses unhinted advances and unfitted FreeType kerning. It deliberately prevents different advance-width policies from confusing the mask comparison. It is not a reproduction of historical layout.

| Row | Outline treatment | Output |
| --- | --- | --- |
| TT35 mono hints / binary | TrueType interpreter 35, mono target | Binary coverage |
| TT35 mono hints / gray edges | Same interpreter and target | Grayscale coverage |
| Auto mono hints / gray edges | Forced automatic hinter, mono target | Grayscale coverage |
| TT40 normal / grayscale | Interpreter 40, normal target | Grayscale coverage |
| TT40 light / grayscale | Interpreter 40, light target | Grayscale coverage |
| Unhinted / grayscale | Hinting disabled | Grayscale coverage |
| TT40 LCD / default RGB filter | Interpreter 40, LCD target | Filtered RGB coverage |

TT35 and TT40 name FreeType interpreter configurations. They are not historical operating-system emulators. Fonts can respond differently to hinting targets. An unavailable engine property produces an explicit unavailable row, without a substitute treatment.

Coverage is computed before color blending. Switching background or blending does not alter the measured masks. The default blends encoded sRGB values. **Linear-light blend** computes brightness in linear light and then encodes sRGB. Both choices are explicit experimental conditions.

## Export and reproduce

Use the export button and choose a new or empty directory. The same renderer also works without a visible window:

    ./build/fontreal --export results/my-comparison
    ./build/fontreal --fractional --phase 0.5 --export results/my-fractional-comparison
    ./build/fontreal --font /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf --export results/my-mono-comparison
    ./build/fontreal --scale 1.25 --dark --linear --export results/my-scaled-comparison
    ./build/fontreal --inspect m --size 10 --scale 1.5 --linear --export results/my-curve-comparison

Supply a local font path when the example font is not installed. Use `./build/fontreal --help` for all arguments. Export refuses a nonempty directory to preserve existing results.

`comparison.png`, `detail.png`, and `target.png` are annotated viewing images. Each available treatment in the ordinary experiment also exports its rendered text, raw RGB coverage, isolated `l` coverage, and selected-glyph coverage (`*-probe-coverage.png`). The separate `--edges` study labels its adjusted masks in metadata. In coverage images, black means no coverage and white means full coverage. The colors of coverage images are data, not the final text colors. Inspection accepts one visible ASCII character that exists in the chosen font.

`metrics.json` records the font path and SHA-256, family, FreeType version, size, scale, quantized phase, placement, blend, mode settings, glyph identities and origins, the middle-row RGB coverage profile of the isolated `l`, and the selected glyph's identity and bitmap bounds. Keep these files together. Results are repeatable within the same local font and rendering environment. They are not guaranteed identical across FreeType versions or builds.

The generated [first comparisons](docs/experiments/freetype-comparison.md) record the measured differences and the user's initial visual preference.

## Checks

    ctest --test-dir build --output-on-failure

The checks exercise real CLI exports, independent FreeType references, repeatability, font and size changes, snapped and fractional stems, soft target edges, blend formulas, invalid inputs, output preservation, and real GUI controls and export. The viewer checks capture the actual window canvases at device pixel ratios 1 and 1.25. No test declares a treatment beautiful.

The [research report](docs/research/native-font-rendering.md) explains the prior art and limits. The [experiment specification](docs/plans/freetype-comparison.md) defines the controlled scope and proof.

The [KDE integration investigation](docs/research/kde-integration.md) identifies the installed Qt paths that differ from the preferred treatment. It includes a process-local trace and the boundary between configuration and a Qt change.
