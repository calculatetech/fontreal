# Fontreal V3 for Qt and KDE

Apply the approved grayscale and subpixel rendering in Qt Widgets and Plasma. Users open the existing Plasma Fonts panel to choose the subpixel layout. With subpixel rendering set to None, Fontreal uses its grayscale result. Verify the window pixels at 100% and 125% scale, then provide comparisons with stock Qt and Windows ClearType.

Work on `feature/fontreal-v3-qt` from `main` at `54b130354287`. V3 applies to Qt and KDE only. The existing Fontreal V2 profile and private FreeType readers retain their documented behavior.

The deployment target uses the distro's Qt and stock KWin. Prefer the distro's FreeType. If a later checkpoint requires a FreeType patch, deliver it through the distro package manager. Keep the patched Qt build as the visual reference. Compare light and dark text before selecting a release path.

Test a filter at the public FreeType glyph rasterization call. That call provides outline and coverage data. The later paint stage owns the ink color and destination pixels. Use one grayscale mask as the initial test. For Qt Quick, opt into native text through `QQuickWindow::setTextRenderType()`. Compare the same scene with native text and the filter off and on. Keep the default text renderer as a separate baseline.

## Stock Qt feasibility and release checks

### V3-8 RGB on additional drawing paths

Use the isolated `feature/fontreal-rgb-paths` worktree from `4c4f141`. When Plasma selects a subpixel layout, the goal is to use it on Breeze captions and on the remaining Widgets and Qt Quick text paths. Keep the distro Qt, FreeType, and KWin packages as the integration target. The Fonts setting **None** and explicit anti-aliasing opt-outs still apply. KWin effects continue to process the submitted window as usual.

Recognize the ordinary stock Breeze caption paint in KWin 6.6.6's OpenGL and software compositors. Use the existing raster provider and the selected layout if the painter, image, and single unrotated output scales agree. Apply the 32-level RGB coverage cap only to the caption pixels that have an opaque destination and a rectangular clip. Before sampling an OpenGL caption mask, account for KWin's rounding of the partial paint origin when it uploads the image. Apply this correction to RGB and grayscale masks. Use the existing paint behavior for other targets. Verify the final caption at 100% and 125% with OpenGL and at 100% with the software compositor. At 125%, compare a caption that KWin repaints at a half-pixel origin with a fresh paint in both RGB and **None**. Compare a caption spanning two outputs of different scales and a caption on a rotated output with their **None** controls. Reverse horizontal and vertical stripe orders on the same caption, and compare explicit anti-aliasing off and ordinary Widgets and image paint with their controls. Use actual Wayland screenshot pixels and verify that the tested process loads the intended provider.

For ordinary transparent Qt Quick layers, keep the layer color and the three channel transmittances independent until the final draw. Transmittance is the share of the background that shows through. A test can capture the same layer against black and white and derive transmittance from the difference. Apply that result to the actual destination. Require agreement within one channel value with an equivalent direct draw, including a spatially changing background. A transformed glyph or layer needs coverage on the final pixel grid. A custom effect that consumes a single flattened texture owns its pixel changes, so its output cannot be inferred from the original text coverage.

### V3-9 Qt Widgets text with opacity

On the stock Ubuntu Qt Wayland path, use the selected layout for partially opaque solid text on an aligned QWidget backing store. Respect the combined opacity that Qt supplies, including both painter opacity and pen alpha. Use RGB only where the destination pixel is opaque and the clip has full coverage. Read clip coverage even when Qt describes the clip as a rectangle. On the RGB path, apply that coverage to gray edge pixels when Qt treats the clip as a rectangle. Use the Qt span compositor at clip edges or on a transparent backdrop. Keep the existing caption path and the grayscale fallback for images. Compare the native mode with the orientation that Qt reports. A newly painted glyph uses grayscale after a reported turn. Qt can keep the previous orientation for a flipped output.

Compare final pixels at 100% and 125%. For each channel, compare the partial draw with the same opaque draw scaled by its opacity over the same backdrop. Include zero opacity, both sources of opacity, both ink polarities, a clip boundary, and a translucent backing pixel in the same draw as opaque pixels. Check the ordinary text and static text entry points. Compare blue-first and red-first edges against **None**. Check explicit anti-aliasing opt-outs and compare the Breeze and offscreen controls with the previous provider.

### V3-10 Qt Quick text placed between pixels

For native Qt Quick text on the existing RGB-capable window path, snap a fractional parent translation to the nearest output pixel before the stock glyph shader runs. Require one Wayland output with a reported orientation that matches its native mode. Refresh this check when the screen geometry, orientation, or output list changes. Keep the original matrix and RGB eligibility for previously aligned draws. Keep the stock matrix for a rotated, scaled, layered, or otherwise ineligible draw.

At 100% and 125%, compare final Quick window pixels with a whole-pixel placement of the same text. Use offsets on each side of the halfway point and at the halfway point on both axes. Include the rotated and layered grayscale controls in the same window. Move direct text back to its original position after the fractional draw. Draw after left, right, and inverted output turns and after returning to normal. Start a new window on an already turned screen. Enable a turned second output and make it the sole output before returning it to normal.

### V3-11 Software Qt Quick

In the existing stock Qt helper, use the raster provider for direct software Qt Quick text in both the basic and threaded render loops. The loaded Quick library must match the package's archived runtime. Activate before the first native draw, including when an application loads Quick after it starts. Keep one package and the same login setup.

Track the active software renderer's window backing store only during a frame. Require an exposed native window on one unrotated Wayland output. Confirm that the painter uses the same backing store at its native scale. Use the existing raster rules for the font setting, opacity, clips, and destination alpha. Layers, redirected images and hidden grabs keep the existing fallback. Read the native scale and output eligibility on the GUI thread and share the result with the renderer. When eligibility changes, ask Qt to repaint the cached scene once.

Compare native window pixels at 100% and 125%, including layouts, opacity, clips, both software render loops, and GPU. Test a delayed Quick load, a hidden grab, and a live window redirected to an image before normal painting resumes. Check that a changed Quick library leaves the software hook inactive. Repaint after an output turn and after return to the original orientation.

### V3-6 Approved white text

On the qualified Ubuntu amd64 Qt build, apply the approved direct RGB white
text from the bowl fit and cleaner ends comparison. Use one coverage function
from the Widgets and Quick providers. Keep the installed 0.10 coverage for
black text and for draws that use grayscale. The Widgets paint target still
selects coverage per pixel. Quick still uses its existing atlas and shader
to select RGB or grayscale at draw time.

Use `feature/fontreal-approved-white` from `ff0e82fa4564` in an isolated
worktree. The package recipe owns the upgrade and the existing Plasma login
hook owns activation. The current host, its Qt revisions, and its single
unrotated display define the test environment. Browser integration and
distribution to other systems remain separate.

Build the 0.11 helper with `tools/build-qt-stock-helper.sh`. For this local
rollout, use the retained comparison captures at 10, 11, and 12 pt as
the white RGB reference and version 0.10 as the black and grayscale
reference. These captures are local development evidence. A fresh checkout
can build and verify activation using the stock helper procedure in
[Build for the running system](../build-system.md).

Use final Wayland window pixels to verify both the direct and fallback
paths. Check mapped providers and stock libraries in fresh app launches
after the simulated and real APT upgrade. Keep the 0.10 archive for
rollback. Review the complete candidate before installing it.

### V3-7 Small light italic reference

Use the approved Less fringe + stronger tips treatment for light italic
faces with light RGB ink below 13.5 device pixels. Blend the existing
RGB result with the earlier coverage from the same hinted glyph.
Reduce the channel spread and lift connected stroke tips by the same
amount in all three channels. Widgets and Quick share this calculation.
Their grayscale coverage and draw selection stay the same.

Save the reference on `feature/fontreal-approved-white`, based on
`95ef337` in the existing isolated worktree. The separate experiment
on gray uses this reference as its first column.

Compare the staged Widgets build with the retained 774 reference captures
at 8 through 16 pt. An additional 14-device-pixel capture checks the first
whole pixel size above the cutoff. Use compositor captures to compare
Widgets and Quick for the same light italic text, both aligned and with
the existing grayscale fallbacks. Verify the loaded providers and compare
black text, regular faces, and layout None with the earlier build.

For the grayscale feasibility test, verify final window pixels and loaded distro libraries in Konsole and a Plasma window on stock KWin. Hold the text renderer, text, palette, and output scale fixed while toggling the filter. Check the default Qt Quick renderer separately. Use the same compiled filter against more than one supported Qt version. Compare both text polarities with the approved V3 reference.

Before release, verify final window pixels at 100% and 125% with the candidate active and the process loading distro Qt and FreeType. Check Plasma’s None, RGB, BGR, vertical RGB, and vertical BGR choices. Check grayscale for antialiased draws that cannot use subpixel color. Compare explicit system and application anti-aliasing opt-outs with unmodified stock Qt. The grayscale feasibility test covers a subset of this behavior.

### Install and reboot acceptance

Provide one install script or distro package. After reboot, a normal Plasma login must activate Fontreal in ordinary Qt Widgets and Qt Quick launches. Run this check in a disposable VM. Compare both text polarities with the approved V3 reference and record the libraries in use. Include a BC1-compressed KTX texture that renders on stock Qt and compare its pixels with the installed result. Remove the installation and reboot again. The same stock comparison must match after removal.

One test package loaded separate Widgets and Quick plug-ins after a Plasma reboot on Ubuntu 26.04. The test used distro QtGui `6.10.2+dfsg-7`, QtQuick `6.10.2+dfsg-3`, FreeType `2.14.2+dfsg-1ubuntu0.2`, KWin `4:6.6.6-0ubuntu0.1` and Plasma's RGB layout. In the two test windows, the application captures and the corresponding text regions in KWin screenshots matched the patched V3 reference at 100% and 125%. The scenes included black and white text. The Quick plug-in selected native rendering for the tested text with the default application settings. It matched at 12, 16 and 20 logical pixels, including a Nimbus Sans CFF fallback. Native package removal and reboot restored the stock application captures. Quick varied by at most one RGB level, the same variation seen in repeated stock captures.

The Quick plug-in preserves the default scene graph and selects V3 at the glyph node, where the text color is available. It uses one Qt atlas for the grayscale and RGB coverage. The draw uses grayscale for a texture or transformed text and uses the selected layout for an aligned draw to the display. Qt populates the atlas during scene graph synchronization and refreshes it when the output scale changes. The Widgets plug-in reaches the shared cached text draw in Qt's raster engine. Both plug-ins build with distro development headers and use Qt private interfaces. Verify the actual running library before enabling each plug-in. A mismatch uses stock Qt.

### V3-5 stock Konsole pilot

Offer an explicit Konsole launch with the user's working profile. Select the light or dark treatment from each terminal draw. Keep both masks in separate Qt cache entries. Test pure black on white and white on black at 100% scale with horizontal RGB on one Plasma Wayland output. Use the same native NORMAL hinting and non-light faces as the reference. Let light faces and other hinting modes use stock rendering. Check positioned glyph bounds, including LCD filter padding, before handing off the ink choice. Confirm that child programs start without the Fontreal library.

Use the stock Qt and FreeType interfaces for this pilot. The stock Qt Quick native renderer can request LCD masks, but it does not pass ordinary text ink to FreeType. Distance field and curve text use other paths. Automatic Qt Quick treatment remains a separate release check.

If a later path requires a FreeType patch, use a native package for each supported distro. Build from the distro source, preserve its package names and dependencies, and let the package manager own the files. Simulate replacement and rollback, including matching library packages for multiple architectures. Limit package selection rules to the specific build and make sure that a newer official security update can replace it.

| Boundary | Distinguishing case | Required evidence |
| --- | --- | --- |
| B9. Ink and cache | Alternate pure black and white terminal rows. Compare other hinting modes, a light request, and a regular request that resolves to a light face. | V3-5 compares both ink colors with the patched Qt reference. Unsupported face and hinting conditions match stock. |
| B10. Target and glyph | Compare a fallback glyph, a colored background, combining marks, and the LCD fringe at a background boundary. | V3-5 checks stock pixels in unsupported regions and changed pixels in neighboring terminal text. |
| B11. Effective layout | Keep the face and draw while changing RGB to BGR or None. Include a request with a font foundry name that sets BGR. | V3-5 compares each unsupported mode with stock. |
| B12. Launch scope | Live Konsole with a pre-existing preload and a normal shell child. | V3-5 checks app and compositor library identities, then checks the shell's preload and mappings. |

Run the pilot check with Ubuntu 26.04, Xvfb, Pillow with XCB, FontTools, Konsole, KWin, and Hack. Install DejaVu Sans, DejaVu Sans Mono, and DejaVu Sans ExtraLight. Ubuntu supplies ExtraLight in `fonts-dejavu-extra`. Extract the official Qt and FreeType packages into a staging directory. Pass the directory that contains the extracted shared libraries, the V3 Widgets Qt build, the pilot library, and an output directory to `tests/v3_konsole_rgb_test.py` in that order.

## Patched Qt reference

The remaining checkpoints describe the existing reference renderer. Its package and display checks reproduce the reference. Use the stock Qt checks above for release acceptance.

## Decision log

Plasma writes the selected subpixel order to Fontconfig. Qt uses that value for eligible Widgets and Qt Quick draws and keeps the native outline hints. Explicit application and system anti-aliasing vetoes still apply. Use grayscale for intermediate targets without a proven pixel mapping. V3-8 defines the separate Breeze caption path.

Keep stock KWin and its display effects. Ordinary Wayland Widgets paint can use subpixel color when the window, backing store, painter and Wayland platform window agree on the output scale. Check a single unrotated output at 100% and 125%. Application scale overrides, scale rounding, and additional painter scaling use grayscale. Effects such as Zoom keep their usual filtering after Qt submits the window.

Keep the exact approved dark and light tone curves. Dark text uses the core-biased curve with contrast. Light text uses the tapered lift and brightness curve. The RGB projection redistributes those samples at 90% strength while preserving grayscale luminance and the black and white endpoints. Apply physical channel order before luminance projection. Use vertical samples for vertical layouts.

Keep the approved raster geometry from the native NORMAL hinted outline at the target size. Rasterize that outline at four times the output resolution and reduce aligned samples to the native glyph bounds. For thin strokes, use a second, unhinted outline as a reference for the accepted bridge and centerline treatment. Use face style and local geometry to select eligible work. The renderer accepts no font name or character exceptions.

Use the native source color and alpha for both the black and white controls and ordinary Plasma theme colors. Retain the independent grayscale coverage so the same glyph can use it in a Quick effect while its aligned draw uses RGB on the window. Check that the effect stops requesting frames after the window settles. Check the visible tail of a run longer than Qt's 16-bit glyph index limit.

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

Validate and review each reference checkpoint before its local commit. Keep temporary test outputs in the ignored build and results directories.

For the reference package recipe, run `tests/system_build_test.py` and `tests/system_install_test.py` with Python. Check fresh Qt, an installed V2 package set, and stock Qt with the earlier session package still installed. Verify the captured predecessor version, the selected APT arguments, and the packaged login hook with independent version inputs. Use the built reference packages in the native application and rollback checks.

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
