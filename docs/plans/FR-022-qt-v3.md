# Fontreal V3 for Qt and KDE

Apply the approved grayscale and subpixel rendering in Qt Widgets and Plasma. Users open the existing Plasma Fonts panel to choose the subpixel layout. With subpixel rendering set to None, Fontreal uses its grayscale result. Verify the window pixels at 100% and 125% scale, then provide comparisons with stock Qt and Windows ClearType.

Work on `feature/fontreal-v3-qt` from `main` at `54b130354287`. Keep the native package targets and on-demand builds defined in [Build for the running system](../build-system.md). The new rendering runs in Qt against stock FreeType. The existing Fontreal V2 profile and private FreeType readers retain their documented behavior. V3 applies to Qt and KDE only.

## Decision log

Plasma writes the selected subpixel order to Fontconfig. Qt uses that value for eligible draws and keeps the native outline hints. Explicit application and system anti-aliasing vetoes still apply. Use grayscale when Qt paints through a texture or another intermediate target. This includes Qt Quick scenes and the current KWin decoration path.

Keep stock KWin and its display effects. Ordinary Wayland Widgets paint can use subpixel color when the window, backing store, painter and Wayland platform window agree on the output scale. Check a single unrotated output at 100% and 125%. Application scale overrides, scale rounding, and additional painter scaling use grayscale. Effects such as Zoom keep their usual filtering after Qt submits the window.

Keep the exact approved dark and light tone curves. Dark text uses the core-biased curve with contrast. Light text uses the tapered lift and brightness curve. The RGB projection redistributes those samples at 90% strength while preserving grayscale luminance and the black and white endpoints. Apply physical channel order before luminance projection. Use vertical samples for vertical layouts.

Keep the approved raster geometry from the native NORMAL hinted outline at the target size. Rasterize that outline at four times the output resolution and reduce aligned samples to the native glyph bounds. For thin strokes, use a second, unhinted outline as a reference for the accepted bridge and centerline treatment. Use face style and local geometry to select eligible work. The renderer accepts no font name or character exceptions.

The exact color oracle models black text on white and white text on black. General colors and nonopaque draws must keep native source color and alpha. Use the approved grayscale coverage for general cases until the final color check proves the RGB blend. Do not average projected RGB coverage to obtain that grayscale result.

Test the visible positive path in an ordinary native-resolution Konsole or Qt Widgets window on a configured output. Compare it with a same-font offscreen layer that the display scales after rendering. An opaque intermediate surface does not prove a direct mapping. Test horizontal and vertical order with directional geometry on every renderer that uses color.

V3 builds own the matching Qt libraries. An upgrade over V2 keeps the existing FreeType package and uses its public API with V3 rendering. Exercise a clean stock FreeType install too. Rolling back restores the captured Qt packages and the exact earlier Fontreal session package. Capture the session package version at planning time, including when distro updates have replaced the earlier Qt libraries. The session keeps its saved on or off preference and the V2 profile choice.

## Verification boundaries

| Boundary | Distinguishing case | Required evidence |
| --- | --- | --- |
| B1. Approved coverage and color | Light and dark tone with the same samples. Swap the physical stripe order on an asymmetric pixel. At the glyph level, use a reference with different hinted and unhinted support. | V3-1 matches independent tone and RGB projection bytes. V3-2 matches the isolated glyph oracle and checks final pixels where two glyphs overlap. |
| B2. Font and style regression | Regular, bold and italic faces, light faces, and synthetic slants. | V3-4 compares all retained font, size, style and polarity cases with the approved specimens. |
| B3. Comparison provenance | Each output column from its own genuine renderer. | V3-4 compares matched specimens at native pixel size and records the sources. |
| B4. Native dependencies | Official FreeType and an upgrade from an installed V2 bundle. | V3-4 checks mapped library identity, visible output and Qt-only package rollback. |
| B5. Plasma preferences | None, RGB, BGR, vertical RGB and vertical BGR with the same font and target. | V3-2 and V3-3 compare final channel values to an axis-sensitive oracle. |
| B6. Final display eligibility | Aligned target, resampled offscreen layer, then aligned target with the same font. | V3-2 and V3-3 compare actual Widgets, Plasma and KWin pixels at 100% and 125%. |
| B7. Existing routes | Disabled Fontreal, color glyph, no anti-aliasing, no subpixel rendering, and V2. | V3-2 through V3-4 compare unaffected pixels with their stock or V2 control beside a positive V3 result. |
| B8. Repeated glyphs | Draw the same mask cold and warm. Vary phase, scale, ink and color eligibility on a live font engine. | Count actual outline samples on a repeated repaint. Compare each rendered variant with the same input from the uncached path. |

## Implementation

1. **V3-1 numerical core.** Port the selected coverage tables and projection to `src/fontreal_v3_coverage.cpp`. The core receives coverage and pixel size. Verify both polarities across the six approved sizes. Compare the output with independent reference bytes, including asymmetric samples, reversed channel order and both endpoints. Configure with `cmake -S . -B build/v3-qt/coverage -G Ninja`. Build with `cmake --build build/v3-qt/coverage --target v3-coverage-test`. Run `ctest --test-dir build/v3-qt/coverage -R v3-coverage --output-on-failure`. This checkpoint proves the numerical operation only.
2. **V3-2 glyph coverage and Qt Widgets.** Port the registered outline sampling and the accepted thin-stroke treatment. Verify TrueType and CFF, empty glyphs, variation changes, supported transforms and repeated color draws. Compare resolved light upright, light italic, ordinary italic and synthetic slant. Include a case that needs the unhinted reference and one that protects the fitted stroke. Use stock FreeType's public API. Route through Qt's Fontconfig and native raster cache in both distro Qt versions. Run the production paths in `tests/qt_native_test.py` with a private Fontconfig fixture. Verify actual library identity, stable geometry, black and white output, all five modes, disabled and explicit app opt-outs, and an aligned to unsafe to aligned repaint with the same font. Exercise overlapping italic glyphs and combining marks in the final paint. Compare with the candidate grayscale output in those regions to detect changes from compositing more than one glyph.
3. **V3-3 Qt Quick and KWin.** Use the same coverage in the existing native OpenGL glyph path. For text in an unsafe target, keep the approved grayscale output. Run `python3 -B tests/kde_paths_test.py --only quick` for repeated, recolored and transformed inputs at both scales. Run `python3 -B tests/kde_paths_test.py --only nested` to verify actual Plasma text and Breeze captions in composited pixels. Compare channel direction, neutral pixels and geometry. The Qt settings and a trace alone do not prove visible output.
4. **V3-4 native delivery and comparisons.** Build and verify matching Qt packages through the native build and activation commands documented in the build guide. Prove stock FreeType provides the glyphs, the previous profile remains usable and turning off Fontreal restores stock pixels. Confirm the full face, style, size and polarity inventory in the approved regression set, including the original thin italic cases. Add matched images whose source metadata identifies the actual stock Qt, ClearType and V3 renders. Inspect the display crops at one image pixel per display pixel. Run both documentation checks in [CONTRIBUTING.md](../../CONTRIBUTING.md#when-to-run-tests).

Validate and review each checkpoint before its local commit. Review the full candidate before release. Keep temporary test outputs in the ignored build and results directories.

For the native recipe, run `tests/system_build_test.py` and `tests/system_install_test.py` with Python. Check fresh Qt, an installed V2 package set, and stock Qt with the earlier session package still installed. Verify the captured predecessor version, the selected APT arguments, and the packaged login hook with independent version inputs. Also use the built Qt packages in the native application and rollback checks before release.

## Repaint cache

Keep successful masks with their FreeType font engine. Use a 128 KiB limit for stored image bytes. The key includes the glyph, both fractional position offsets, device scale, ink polarity, the light-weight request and effective subpixel layout. The renderer reads the cache under the existing face lock and returns a copy so clipping and overlap changes stay local to the draw. A cache miss follows the original V3 path.

## Isolated Qt Widgets checkpoint

Use Qt 6.10.2 development packages, Xvfb, DejaVu Sans, URW Base35, and Ubuntu Sans to run this checkpoint. Supply the directory with the system's official FreeType, QtCore, QtGui, and QtWidgets packages. A native bundle's `original/` directory supplies these packages.

    python3 tools/build-qt.py --v3-widgets
    bash tests/v3_widgets_test.sh OFFICIAL_PACKAGES_DIR

The XCB fixture compares native window pixels for each Fontconfig subpixel setting at 100% scale. It checks grayscale in the nested offscreen image and at 125% XCB scale. It compares partial and full repaints of isolated and overlapping glyphs, checks a narrow antialiased clip and variable-weight selection, and verifies that disabling the prototype restores stock Qt pixels. The Wayland comparison uses the stock compositor's real output scale at 100% and 125% and exercises a live scale change on the same window.

## Isolated Qt Quick checkpoint

The Qt Quick prototype uses the same grayscale coverage as Widgets. It draws eligible plain text through Qt's existing OpenGL glyph cache. The shader keeps the original ink color and opacity. It uses two sets of coverage, one for dark ink and one for light ink.

Use the same Ubuntu Qt development packages and official package directory as the Widgets checkpoint. Install Mesa software OpenGL for the isolated display.

    python3 tools/build-qt.py --v3-quick
    bash tests/v3_quick_test.sh OFFICIAL_PACKAGES_DIR

The fixture checks pixels from a visible window and an OpenGL readback at 100% and 125% scale. It checks Fontconfig None and RGB, both OpenGL render loops, a change from dark ink to light ink and back, and colored ink. It also runs patched Qt Quick with official QtGui and compares the result with official Qt throughout. The QtGui hooks are optional, so Qt Quick can use its stock path after an independent QtGui update.
