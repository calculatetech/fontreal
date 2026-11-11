# First real Konsole comparison

This test launches the installed Konsole with stock Qt or the private Fontreal Qt build. Its menus and terminal use real application text. KWin draws the title bar in another process, so this test does not change its lettering.

The private build targets this Ubuntu 26.04 x86-64 installation with Qt 6.10.2. It enables automatic monochrome hinting with grayscale output for scalable, non-color TrueType fonts. Positive uniform display scaling enters the FreeType character size before hinting. Glyph placement remains integral in device pixels. Qt retains its normal shaping and layout.

## Build

The existing CMake, Ninja, C++ compiler, Qt development files, FreeType development files, and Python 3 supply the build tools. The private build also uses Ubuntu's `apt-get download` and `dpkg-deb` commands. It extracts missing platform development headers locally. It does not install packages.

The application check uses the installed Konsole, `qdbus6`, `kwriteconfig6`, Spectacle, and the current desktop session. The private Qt build command uses CMake 3.24 or later for `--fresh`.

Run these commands from the repository root:

```sh
python3 tools/build-qt.py
cmake -S . -B build -G Ninja
cmake --build build
python3 tests/qt_native_test.py
ctest --test-dir build --output-on-failure
```

The build command downloads the official Qt 6.10.2 archive and verifies its pinned SHA-256. Generated sources, dependency headers, libraries, captures, and test evidence stay under ignored `build/qt-native/`. The patch stays in `patches/qt-6.10.2-fontreal.patch`.

The test command briefly opens stock, linear, and encoded Konsole windows. It verifies each test process before window actions, toggles its menu bar to exercise repaint, captures it, and closes it normally. It checks widget pixels independently and verifies configuration preservation. The interactive launches below remain open for human judgment.

## Open the comparison

Run each command in a separate terminal, or start each command as a background job:

```sh
python3 tools/preview-konsole.py stock
python3 tools/preview-konsole.py linear
python3 tools/preview-konsole.py encoded
```

The window title identifies the treatment and the UI font. The default UI font is Noto Sans at 15 pixels with scale 1. Open the menus and compare `l`, arches, round letters, and diagonal edges. The terminal keeps its built-in fixed-pitch font and displays a short specimen. Menu text and terminal text therefore test different fonts.

Each launch copies `kdeglobals` into a new private configuration directory. It sets both `General/font` and `General/menuFont` to the selected family and pixel size. KDE uses a separate font role for menus. Separate XDG configuration, cache, data, and state directories contain test writes. Closing the window removes that private directory. Normal Konsole profiles, installed Qt libraries, Fontconfig, and KWin remain unchanged.

## Compare the transition

Use explicit pixel sizes for UI text. On the current scale-1 display, effective device size is `pixels × scale`. KDE point-size settings use a different unit. The launcher writes a Qt font descriptor with an explicit pixel size to avoid that conversion.

For each family, compare both blends while holding size and scale constant. Then repeat at the adjacent size:

```sh
python3 tools/preview-konsole.py linear  --family 'Noto Sans' --pixels 15 --scale 1
python3 tools/preview-konsole.py encoded --family 'Noto Sans' --pixels 15 --scale 1
python3 tools/preview-konsole.py linear  --family 'Noto Sans' --pixels 16 --scale 1
python3 tools/preview-konsole.py encoded --family 'Noto Sans' --pixels 16 --scale 1
```

Repeat with `--family 'DejaVu Sans'`. For the earlier fractional-scale observation, use `--pixels 10 --scale 1.5`, then `--pixels 11 --scale 1.5`. Those pairs request 15 and 16.5 device pixels on the current display. The title bar remains a KWin comparison outside this test.

The terminal's View menu can change its own font size. That operation does not change the controlled UI font in these commands. No automatic blend cutoff is selected. Human preference remains the decision criterion.

## Scope of the evidence

The native probe captures an actual QWidget painted with normal QFont and QPainter calls. Independent FreeType calls check the requested glyph masks, dimensions, placement, and effective size. Independent sRGB math checks both blend modes, both polarities, and an opaque colored foreground/background pair. Transfer-table rounding can differ by at most one channel value.

The check retains fonts and glyph caches through repaint and color changes. It also checks logical metrics after a scaled raster request, then another uncached glyph and the complete `lllm` run. Qt supplies shaping and positions for that run. Independent FreeType masks and blend math supply its expected pixels. Stock launches from a Fontreal-modified environment must still select installed Qt. Private Qt without the opt-in switch must retain the stock probe pixels.

Real Konsole checks record mapped Qt libraries and observe actual FreeType calls through a pass-through test library. The trace does not change those calls. It complements the pixel checks and screenshots. It cannot establish subjective visual preference.

The application check also reads both private font roles. A trace of some 15px glyphs alone does not establish the menu size. Before this correction, previews labeled 15px still used 13px menus on this machine. Earlier menu comparisons therefore do not establish a 15px blend preference.

The user prefers linear blending in the initial application comparison. Large terminal text favors encoded blending in the limited View-menu test. Black text on white reduces the remaining thickness, but does not eliminate it. Uppercase `W` remains particularly fuzzy. The overall result improves on stock, but visual calibration remains open. Hold font, actual size, foreground, and background equal when comparing the experiment and Konsole.

In the controlled black-on-white capture, both menus and terminal use Noto Sans at 15px with linear blending. Sampled `m`, `n`, `o`, `g`, and `V` match the selected experiment pixels exactly. The terminal's `W` also matches exactly. This rules out extra raster blur in those captured glyphs. Konsole still uses fixed terminal cells, so the spacing differs from the experiment. Matching pixels does not establish visual acceptance.

The first proof covers opaque native raster text in the selected TrueType fonts. Qt Quick, KWin, transparent intermediate surfaces, arbitrary transforms, color fonts, and other outline formats need separate validation. The opt-in A8 transfer profile also affects other fonts that already request gamma correction. Their appearance is not certified here. See the [roadmap](../roadmap.md) for the remaining platform work.
