# First real Konsole comparison

This test launches the installed Konsole with stock Qt or the private Fontreal Qt build. It compares unadjusted gray edges with the selected mild contrast treatment. Its menus and terminal use real application text. KWin draws the title bar in another process, so this test does not change its lettering.

The private build targets this Ubuntu 26.04 x86-64 installation with Qt 6.10.2. It enables automatic monochrome hinting with grayscale output for scalable, non-color TrueType fonts. Positive uniform display scaling enters the FreeType character size before hinting. Glyph placement remains integral in device pixels. Qt retains its normal shaping and layout.

## Build

The existing CMake, Ninja, C++ compiler, Qt development files, FreeType development files, and Python 3 supply the build tools. The private build also uses Ubuntu's `apt-get download` and `dpkg-deb` commands. It extracts missing platform headers and the versioned Qt shader tools locally. It does not install packages.

The application check uses the installed Konsole, `qdbus6`, `kwriteconfig6`, Spectacle, and the current desktop session. Noto Sans, DejaVu Sans, and Inconsolata Nerd Font Regular must be installed. The private Qt build command uses CMake 3.24 or later for `--fresh`.

Run these commands from the repository root:

```sh
python3 tools/build-qt.py
cmake -S . -B build -G Ninja
cmake --build build
python3 tests/qt_native_test.py
ctest --test-dir build --output-on-failure
```

The build command downloads the official Qt Base and Qt Declarative 6.10.2 archives and checks their pinned SHA-256 values. It builds both QtGui and QtQuick, including their required runtime dependencies. Generated sources, dependencies, libraries, captures, and test evidence stay under ignored `build/qt-native/`. The two patches stay under `patches/`. The launcher requires both private modules. Stock mode removes both private runtime directories from its library search path.

The test command briefly opens stock, linear, and encoded Konsole windows. It verifies each test process before window actions, toggles its menu bar to exercise repaint, captures it, and closes it normally. It checks widget pixels independently and verifies configuration preservation. The interactive launches below remain open for human judgment.

## Open the comparison

Run each command in a separate terminal, or start each command as a background job:

```sh
python3 tools/preview-konsole.py stock
python3 tools/preview-konsole.py linear
python3 tools/preview-konsole.py encoded
```

The window title identifies the treatment and the UI font. The default UI font is Noto Sans at 15 pixels with scale 1. The default contrast is `none`, so these original commands remain the unadjusted reference. Open the menus and compare `l`, arches, round letters, and diagonal edges. By default, the terminal keeps its built-in fixed-pitch font. The sample identifies the initial terminal selection. Menu text and terminal text can test different fonts.

Each launch copies `kdeglobals` into a new private configuration directory. It sets both `General/font` and `General/menuFont` to the selected family and pixel size. KDE uses a separate font role for menus. Separate XDG configuration, cache, data, and state directories contain test writes. Closing the window removes that private directory. Normal Konsole profiles, installed Qt libraries, Fontconfig, and KWin remain unchanged.

## Use the preferred fonts and mild contrast

The user prefers mild contrast with Noto Sans and Inconsolata Nerd Font at the viewed 15px condition. Compare the same fonts and sizes in real Konsole:

```sh
python3 tools/preview-konsole.py linear --contrast none --terminal-family 'Inconsolata Nerd Font' --terminal-pixels 15
python3 tools/preview-konsole.py linear --contrast mild --terminal-family 'Inconsolata Nerd Font' --terminal-pixels 15
python3 tools/preview-konsole.py encoded --contrast mild --terminal-family 'Inconsolata Nerd Font' --terminal-pixels 15
```

The UI stays Noto Sans at 15px. The explicit terminal family overrides only the private built-in profile's Font property. Omit `--terminal-pixels 15` to use the supplied normal Inconsolata setting of 11pt. Points and pixels are different units. This launcher does not read or modify the normal profile. A pixel override requires the explicit Inconsolata family, so the launcher cannot silently ignore it.

The mild treatment maps each glyph's coverage through the same 32..223 clipped linear ramp as the [diagonal study](diagonal-edges.md). It preserves empty and full pixels and runs before color blending and cache storage. Repainting uses the stored adjusted mask. It does not reapply contrast. Both blends remain available, and stock rejects mild contrast. There is no automatic size cutoff or font-specific pixel rule.

The generic `run-qt.py` launcher also accepts `--contrast none|mild`. Put this option before the mode and application command. It clears inherited contrast selection before applying the requested value. Use the preview command above when private Konsole configuration is needed.

Launch labels describe the initial conditions. View controls change only terminal size. The preview keeps the copied desktop palette and built-in terminal color scheme. The accepted experiment used black text on white, so judge the real application palette separately.

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

Real Konsole checks record mapped Qt libraries and observe actual FreeType calls through a pass-through test library. The trace does not change those calls. It complements the pixel checks and screenshots. FreeType calls precede Qt's mild coverage adjustment, so flags alone cannot prove that adjustment. The explicit Noto15/Inconsolata15 fixture also checks client-capture glyph pixels against independent masks and color math, including rejection of the opposite contrast. The 11pt fixture checks its point descriptor and actual runtime family. These checks cannot establish subjective visual preference.

The native probe covers all three fonts, W/V/w/v, curves, stems, punctuation, blank text, cached redraw, recoloring, and two overlapping glyph draws. Independent expected masks track each pixel's contributing glyph layers. Color tolerance is one value per layer, normally one and at most two for the dedicated overlap fixture. Isolated capture glyphs retain the one-value tolerance. The overlap fixture also distinguishes per-glyph adjustment from adjusting accumulated coverage.

The application check also reads both private font roles. A trace of some 15px glyphs alone does not establish the menu size. Before this correction, recorded previews labeled 15px still used 13px menus. Earlier menu comparisons therefore do not establish a 15px blend preference.

In the initial unadjusted application comparison, the user prefers linear blending. Large terminal text favors encoded blending in the limited View-menu test. Black text on white reduces the reported thickness but does not eliminate it. W and V remain fuzzy in that unadjusted treatment. The later mild-contrast study receives the user's preference at the viewed 15px condition. Hold font, actual size, foreground, and background equal when comparing the experiment and Konsole.

In the controlled black-on-white capture, both menus and terminal use Noto Sans at 15px with linear blending. Sampled `m`, `n`, `o`, `g`, and `V` match the selected experiment pixels exactly. The terminal's `W` also matches exactly. This rules out extra raster blur in those captured glyphs. Konsole still uses fixed terminal cells, so the spacing differs from the experiment. Matching pixels does not establish visual acceptance.

That matched unadjusted result motivated the [diagonal edge study](diagonal-edges.md). The native mild option now carries its selected mask treatment into Qt. In the actual dark Konsole palette, the user prefers mild contrast with linear blending at 15px, using Noto Sans menus and Inconsolata Nerd Font terminal text. The user finds Konsole's appearance bolder and less clear than the experiment, but still selects mild/linear as the clear winner and a comfortable compromise. This records perceived weight, not a diagnosis of synthetic bolding. Other sizes and fonts remain calibration work.

This proof covers opaque native raster text in the selected TrueType fonts. The A8 transfer profile applies only during eligible draws. Separate [KDE checks](kde-paths.md) cover KWin, Qt Quick OpenGL, and CFF/color preservation. Transparent intermediate surfaces and arbitrary transforms remain outside these guarantees. See the [roadmap](../roadmap.md) for the remaining platform work.
