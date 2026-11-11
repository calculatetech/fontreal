# KDE rendering-path checks

These checks measure actual KWin titles, a real Plasma applet host, and separate Qt Quick diagnostics. They preserve the normal desktop. A completed diagnostic run does not mean that every renderer matches the reference.

## Build and run

Use the installed Ubuntu 26.04 amd64, Qt 6.10.2, and Plasma/KWin 6.6.6 environment. Build the existing [private Qt prototype](kde-preview.md) first. The optional probe needs Qt Quick and Quick Controls development files, installed Breeze and Plasma QML modules, Xvfb, and D-Bus tools. The existing viewer does not require these additional test modules.

    cmake -S . -B build -G Ninja
    cmake --build build --target qt-kde-probe
    python3 tests/kde_paths_test.py

The runner writes captures, runtime logs, font identity, and `report-all.json` under `build/kde-paths`. For a focused run, use `--only quick`, `--only nested`, or `--only spillover`. A command error stops collection. Inspect its log rather than using a report from an earlier run.

The runner creates private XDG directories, an owned Xvfb display, and a D-Bus session without service-activation directories. It disables desktop-portal requests for these fixtures. This keeps desktop helpers out of the experiment. It checks normal KDE/KWin configuration and font hashes before and after, then checks that the original compositor remains alive.

KWin carries `cap_sys_nice` on this machine. That prevents the ordinary library override and `/proc` inspection used for application previews. The test invokes the installed KWin through the system loader, uses its upstream `KWIN_FORCE_OWN_QPA` switch, and records the loader's resolved Qt library. It does not change the installed file or its capability. This nested test does not request real-time scheduling.

Each KWin condition uses fresh configuration. The runner applies the nested output scale through `kscreen-doctor` and reads it back before starting the client. It also checks the captured buffer dimensions. Wayland's integer screen scale can differ from the window's fractional buffer scale. A requested scale alone is not evidence.

The actual Plasma process uses the installed `plasmawindowed` host and its real Plasma applet item. The test plasmoid displays controlled text through Plasma Components, Breeze controls, and explicit Qt renderers. This establishes applet-host coverage, not full plasmashell or session-activation coverage.

## What the pixels prove

The fixture uses Noto Sans Regular at 15 logical pixels. Its cells contain `l`, `m`, `n`, `o`, `g`, `W`, `V`, `w`, and `v`. Explicit native Text, explicit Qt Text, implicit Text, Breeze Label, Plasma Label, and Breeze Button form separate rows.

Independent FreeType calls generate automatic-MONO grayscale masks. Independent floating-point math applies the mild ramp and both color blends. The probe searches each known cell for each prediction, including a one-pixel background border. A match allows one channel value of rounding error. It records the minimum error and matched location for every hypothesis. An ambiguous glyph such as a fully covered `l` cannot select a treatment by itself.

The widget control must match the accepted mild/linear prediction and reject the opposite blend for at least one glyph. Qt Quick diagnostics record the actual graphics API, font, render type, device scale, and glyph origin. They capture a repeated frame, inverted colors, and nonendpoint colors. A deliberate half-device-pixel shift tests whether the native mask survives a fractional-origin opportunity.

KWin title searches use only the first 40 output pixels. The controlled client starts in the upper-left corner, with its first text row below that region. Thus a client glyph cannot satisfy a title comparison. Plasma records its actual text types and font properties. A separate comparison locates the applet capture in the final composited screen, without resizing either image. Both the applet buffer and final screen cells receive independent glyph comparisons. The composite check reports its own error and does not loosen the one-value glyph threshold.

The OpenGL tests use Mesa llvmpipe on Xvfb. They exercise the real Qt Quick OpenGL shaders and composition code. They do not certify a physical GPU driver. The separate Qt Quick software renderer is a diagnostic control.

## Findings

At 100% scale, all nine enabled KWin title glyphs match the selected mild/linear reference. The encoded and unadjusted controls select their corresponding predictions. The native widget control also matches the reference.

At 125% output scale, all nine KWin title glyphs also match mild/linear at 18.75 device pixels. The explicitly native applet row retains the mild masks and encoded composition. Default applet text and controls select Qt Text instead. The candidate native-rendering environment override does not change those actual applet selections, although it changes relevant standalone diagnostic rows. One environment variable therefore does not establish Plasma coverage.

The actual Plasma applet and standalone native Qt Quick OpenGL paths use the selected mild masks, but compose them with encoded edges. Linear and encoded requests produce the same text pixels there. The blend selector therefore does not reproduce the accepted small-text result on that path. Explicit Qt Text remains a distinct renderer and does not reproduce the automatic-MONO reference.

The selected native glyph cells retain those encoded matches in the final composited screen. The complete applet-buffer comparison has a maximum channel difference of three at 100% and two at 125%. Thus the buffers are not byte-identical as a whole. Those differences do not relax the separate glyph threshold.

At 100% scale, the Qt Quick software control matches mild/linear for the tested rows. This locates the blend difference in the rendering path. It is not a proposal to switch the desktop to software rendering.

The software control does not reproduce every reference glyph at 125%. In the explicit native row, four of nine glyphs meet the strict mild/linear threshold. The native OpenGL row retains exact selected mask shapes under the deliberate half-device-pixel shift at 100%. These are bounded placement results, not certification of arbitrary transforms or decoration origins.

Nimbus Sans CFF and Noto Color Emoji retain equal masks and output under the ordinary fixture. With explicit grayscale CFF text, the masks remain equal but final pixels change. This reproduces the shared A8 transfer-profile spillover outside eligible TrueType text. Broad activation needs a confined profile or an explicit supported result for that path.

These results do not certify all fonts, sizes, scripts, styles, palettes, decorations, GPU drivers, or Plasma components. Full-session D-Bus/systemd inheritance, package installation, official updates, and rollback remain package-pilot work. The [roadmap](../roadmap.md) owns the remaining rendering and deployment work.

## Human comparison

After the complete run, create and open the comparison board:

    ./build/qt-kde-probe board build/kde-paths
    ./build/qt-kde-probe view build/kde-paths/comparison.png

The board contains captured widget text, stock and enabled KWin title strips, actual Plasma applet rows, and software-renderer controls. Labels distinguish requested treatment from measured output. The viewer draws one image pixel per backing pixel. Do not zoom the window or infer native presentation from a resized chat preview. Human preference remains a separate result.
