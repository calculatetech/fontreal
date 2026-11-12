# KDE rendering-path checks

These checks measure actual KWin titles, a real Plasma applet host, and separate Qt Quick diagnostics. They preserve the normal desktop. A completed diagnostic run does not mean that every renderer matches the reference.

## Build and run

Use the installed Ubuntu 26.04 amd64, Qt 6.10.2, and Plasma/KWin 6.6.6 environment. Build the [private QtGui and QtQuick prototype](kde-preview.md) first. The optional probe needs Qt Quick, Quick Controls, and QtGui private development files, installed Breeze and Plasma QML modules, Xvfb, and D-Bus tools. The existing viewer does not require these additional test modules.

    cmake -S . -B build -G Ninja
    cmake --build build --target qt-kde-probe
    python3 tests/kde_paths_test.py

The runner writes captures, runtime logs, font identity, and `report-all.json` under `build/kde-paths`. For a focused run, use `--only quick`, `--only nested`, or `--only spillover`. A command error stops collection. Inspect its log rather than using a report from an earlier run.

To repeat the Quick checks on the current X display and its physical OpenGL driver, run:

    python3 tests/kde_paths_test.py --hardware --only quick

This command briefly opens comparison windows. It keeps the private configuration and D-Bus isolation, removes the forced software OpenGL device, and checks the reported driver. Its evidence stays separately under `build/kde-hardware`. It does not establish coverage of other devices or full-session activation.

The runner creates private XDG directories, an owned Xvfb display, and a D-Bus session without service-activation directories. It disables desktop-portal requests for these fixtures. This keeps desktop helpers out of the experiment. It checks normal KDE/KWin configuration and font hashes before and after, then checks that the original compositor remains alive.

When KWin carries `cap_sys_nice`, it prevents the ordinary library override and process-map inspection used for application previews. The test invokes the installed KWin through the system loader, uses its upstream `KWIN_FORCE_OWN_QPA` switch, and records the loader's resolved Qt library. It does not change the installed file or its capability. This nested test does not request real-time scheduling.

Each KWin condition uses fresh configuration. The runner applies the nested output scale through `kscreen-doctor` and reads it back before starting the client. It also checks the captured buffer dimensions. Wayland's integer screen scale can differ from the window's fractional buffer scale. A requested scale alone is not evidence.

The actual Plasma process uses the installed `plasmawindowed` host and its real Plasma applet item. The test plasmoid displays controlled text through Plasma Components, Breeze controls, and explicit Qt renderers. This establishes applet-host coverage, not full plasmashell or session-activation coverage.

## What the pixels prove

The fixture uses Noto Sans Regular at 15 logical pixels. Its cells contain `l`, `m`, `n`, `o`, `g`, `W`, `V`, `w`, and `v`. Explicit native Text, explicit Qt Text, implicit Text, Breeze Label, Plasma Label, and Breeze Button form separate rows.

Independent FreeType calls generate automatic-MONO grayscale masks. Independent floating-point math applies the mild ramp and both color blends. The probe searches each known cell for each prediction, including a one-pixel background border. A match allows one channel value of rounding error. It records the minimum error and matched location for every hypothesis. An ambiguous glyph such as a fully covered `l` cannot select a treatment by itself.

The widget control must match the accepted mild/linear prediction and reject the opposite blend for at least one glyph. Qt Quick diagnostics record the actual graphics API and driver, both toolkit paths, requested renderer, font, scale, and origin. Per-run logs record the effective renderer separately. Five frames cover cached repaint, inverted colors, nonendpoint colors, and combined foreground alpha and inherited opacity. A half-device-pixel shift tests mask support and explicit-row coordinates at both scales. Separate linear/encoded cases capture an unexposed window before `show`, through its distinct offscreen target owner. Every frame must contain the complete expected cell set.

KWin title searches use only the first 40 output pixels. The controlled client starts in the upper-left corner, with its first text row below that region. Thus a client glyph cannot satisfy a title comparison. Plasma records its actual text types and font properties. A separate comparison locates the applet capture in the final composited screen, without resizing either image. Both the applet buffer and final screen cells receive independent glyph comparisons. The composite check reports its own error and does not loosen the one-value glyph threshold.

The default OpenGL tests use Mesa llvmpipe on Xvfb. They exercise the real Qt Quick shaders and composition code. The separate Qt Quick software renderer is a diagnostic control. The hardware command provides an additional device-specific result.

Mixed GPU scenes retain identical foreground RGBA and opacity through eligible TrueType and native CFF draws in both orders. They also contain default/explicit Qt CFF, multicolor emoji, translucent geometry after text, and an opaque sampled layer. Offscreen captures and window output receive separate assertions. The default run reads the presented X11 window. On this XWayland hardware session, that capture API returns black. The hardware run therefore reads the real window buffer through RHI before presentation and labels that source explicitly. It does not claim physical-screen capture coverage. Ordinary geometry, native grayscale CFF, and color glyphs must equal stock exactly in both sources. Eligible text must match the independent selected prediction. The color control must visibly contain multiple colors.

Stock/inactive comparisons require exact equality for the entire controlled Quick cell area. Whole images also match exactly on the deterministic software device. Intel shows one-value rounding differences in LCD annotations and explicit/default Qt CFF distance-field edges. Physical-driver comparisons allow at most one channel value in those regions, at fixed coordinates. Ordinary geometry, native grayscale CFF, and color glyphs retain exact comparisons. Shapes, placement, and effective renderer selection receive separate checks.

A real QQuickRenderControl fixture renders to compatible, unmarked external, then compatible RHI targets. RHI means Qt's rendering hardware interface. Actual texture readback checks each result without a screenshot helper. The external target must retain encoded output and report linear composition as unavailable. A nonindexed color draw checks the native sRGB operation and restoration before an ordinary draw. The normal glyph path checks indexed draws.

The same target sequence also exercises Sunken text with distinct, partially opaque foreground and style colors. Independent fitted coverage and shifted style support predict both colors under each blend. This checks the shared style-color uniform used by native shadows and outlines, including target changes with unchanged color values.

## Findings

At 100% and 125%, all nine enabled KWin title glyphs retain the selected reference. The encoded and unadjusted controls discriminate their corresponding treatments. The native widget control also retains its reference.

The corrected Qt Quick OpenGL path matches the selected linear or encoded formula at both scales. All six rows match, including explicit Qt Text and the default Plasma/Breeze controls. Eligible runs now select native glyphs in the actual internal selection owner. Requested properties remain requested metadata. Noneligible default/Qt CFF runs keep their original renderer.

All 54 actual Plasma applet cells match the selected treatment in both the applet buffer and final composited screen. These remain separate glyph assertions. The whole-buffer composite comparison reports its own error and does not loosen the glyph threshold.

The fractional phase contrast exposes a quad stretched by separate floating-point corner rounding. The correction preserves the shared item origin through Qt's existing full-matrix material flag, then snaps it once. Fitted masks and the vertex shader remain unchanged. Every explicit-row glyph matches both its mask and independent X coordinate. Its Y coordinate remains fixed across the horizontal phase contrast. This disables merged batches for eligible materials, so desktop performance remains a pilot measurement.

The mixed GPU and target-transition checks preserve ordinary geometry, CFF, and color output while selected TrueType pixels follow the requested blend. They distinguish an unsupported external target from a compatible owned target and prove both indexed and nonindexed draw behavior. Native sRGB writes apply only around selected draws. Controlled textures use a separate sRGB write view and retain their original encoded sampling/readback view. See the [composition research](../research/quick-composition.md) for the mechanism and limits.

At 100% scale, the Qt Quick software control matches mild/linear for the tested rows. This locates the blend difference in the rendering path. It is not a proposal to switch the desktop to software rendering.

The software control does not reproduce every reference glyph at 125%. In the explicit native row, four of nine glyphs meet the strict mild/linear threshold. The OpenGL checks above are bounded placement results, not certification of arbitrary transforms or decoration origins.

The original prototype changed explicit grayscale Nimbus Sans CFF pixels despite retaining its masks. The corrected A8 profile now applies only during an eligible TrueType draw. Ordinary and grayscale CFF, plus Noto Color Emoji, must retain stock masks and output under both blend selectors.

The preservation checks also paint TrueType, CFF, and color glyphs in one process, with repeated prefixes and reversed order. They exercise ordinary text and QStaticText, cached repaint, and all three palettes. CFF/color regions must equal stock exactly. Eligible regions must match their selected independent blend prediction. A positive multicolor check prevents a blank or missing emoji from passing as a color control.

These results do not certify all fonts, sizes, scripts, styles, palettes, decorations, GPU drivers, or Plasma components. Full-session D-Bus/systemd inheritance, package installation, official updates, and rollback remain package-pilot work. The [roadmap](../roadmap.md) owns the remaining rendering and deployment work.

## Human comparison

After the complete run, create and open the comparison board:

    ./build/qt-kde-probe board build/kde-paths
    ./build/qt-kde-probe view build/kde-paths/comparison.png

The board contains captured widget text, stock and enabled KWin titles, and actual Plasma applet rows with linear and encoded blending. Labels name the measured treatments. The viewer draws one image pixel per backing pixel. Do not zoom the window or infer native presentation from a resized chat preview. Human preference remains a separate result.
