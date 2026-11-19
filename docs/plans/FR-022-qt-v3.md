# Fontreal V3 for Qt and KDE

Apply the approved grayscale and subpixel rendering in Qt Widgets and Plasma. Users open the existing Plasma Fonts panel to choose the subpixel layout. With subpixel rendering set to None, Fontreal uses its grayscale result. Verify the window pixels at 100% and 125% scale, then provide comparisons with stock Qt and Windows ClearType.

Work on `feature/fontreal-v3-qt` from `main` at `54b130354287`. Keep the native package targets and on-demand builds defined in [Build for the running system](../build-system.md). The new rendering runs in Qt against stock FreeType. The existing Fontreal V2 profile and private FreeType readers retain their documented behavior. V3 applies to Qt and KDE only.

## Decision log

Plasma writes the selected subpixel order to Fontconfig. Qt's resolved setting is the input. The subpixel choice applies to eligible draws and is independent of the native outline hints. Explicit application and system anti-aliasing vetoes still apply. Use grayscale whenever a draw cannot map its samples to the physical channels of the final display. This includes the current KWin decoration path, which composites a texture with transparency.

Keep the exact approved dark and light tone curves. Dark text uses the core-biased curve with contrast. Light text uses the tapered lift and brightness curve. The RGB projection redistributes those samples at 90% strength while preserving grayscale luminance and the black and white endpoints. Apply physical channel order before luminance projection. Use vertical samples for vertical layouts.

Keep the approved raster geometry from the native NORMAL hinted outline at the target size. Rasterize that outline at four times the output resolution and reduce aligned samples to the native glyph bounds. For thin strokes, use a second, unhinted outline as a reference for the accepted bridge and centerline treatment. Use face style and local geometry to select eligible work. The renderer accepts no font name or character exceptions.

The exact color oracle models black text on white and white text on black. General colors and nonopaque draws must keep native source color and alpha. Use the approved grayscale coverage for general cases until the final color check proves the RGB blend. Do not average projected RGB coverage to obtain that grayscale result.

Test the visible positive path in an ordinary native-resolution Konsole or Qt Widgets window on a configured output. Compare it with a same-font offscreen layer that the display scales after rendering. An opaque intermediate surface does not prove a direct mapping. Test horizontal and vertical order with directional geometry on every renderer that uses color.

V3 builds own the matching Qt libraries. A Qt-only upgrade over V2 keeps the existing FreeType package and uses its public API, with the V2 private rendering selector inactive in the V3 path. Also exercise a clean stock FreeType install. Rolling back Qt-only work restores the earlier Qt libraries without changing the installed FreeType.

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

## Implementation

1. **V3-1 numerical core.** Port the selected coverage tables and projection to `src/fontreal_v3_coverage.cpp`. The core receives coverage and pixel size. Verify both polarities across the six approved sizes. Compare the output with independent reference bytes, including asymmetric samples, reversed channel order and both endpoints. Configure with `cmake -S . -B build/v3-qt/coverage -G Ninja`. Build with `cmake --build build/v3-qt/coverage --target v3-coverage-test`. Run `ctest --test-dir build/v3-qt/coverage -R v3-coverage --output-on-failure`. This checkpoint proves the numerical operation only.
2. **V3-2 glyph coverage and Qt Widgets.** Port the registered outline sampling and the accepted thin-stroke treatment. Verify TrueType and CFF, empty glyphs, variation changes, supported transforms and repeated color draws. Compare resolved light upright, light italic, ordinary italic and synthetic slant. Include a case that needs the unhinted reference and one that protects the fitted stroke. Use stock FreeType's public API. Route through Qt's Fontconfig and native raster cache in both distro Qt versions. Run the production paths in `tests/qt_native_test.py` with a private Fontconfig fixture. Verify actual library identity, stable geometry, black and white output, all five modes, disabled and explicit app opt-outs, and an aligned to unsafe to aligned repaint with the same font. Exercise overlapping italic glyphs and combining marks in the final paint. Compare with the candidate grayscale output in those regions to detect changes from compositing more than one glyph.
3. **V3-3 Qt Quick and KWin.** Use the same coverage in the existing native OpenGL glyph path. For text in an unsafe target, keep the approved grayscale output. Run `python3 -B tests/kde_paths_test.py --only quick` for repeated, recolored and transformed inputs at both scales. Run `python3 -B tests/kde_paths_test.py --only nested` to verify actual Plasma text and Breeze captions in composited pixels. Compare channel direction, neutral pixels and geometry. The Qt settings and a trace alone do not prove visible output.
4. **V3-4 native delivery and comparisons.** Build and verify matching Qt packages through the native build and activation commands documented in the build guide. Prove stock FreeType provides the glyphs, the previous profile remains usable and turning off Fontreal restores stock pixels. Confirm the full face, style, size and polarity inventory in the approved regression set, including the original thin italic cases. Add matched images whose source metadata identifies the actual stock Qt, ClearType and V3 renders. Inspect the display crops at one image pixel per display pixel. Run both documentation checks in [CONTRIBUTING.md](../../CONTRIBUTING.md#when-to-run-tests).

Validate and review each checkpoint before its local commit. Review the full candidate before release. Keep temporary test outputs in the ignored build and results directories.
