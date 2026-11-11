# Bringing the preferred rendering into KDE

## Question

How can KDE reproduce the rendering preferred in the controlled FreeType experiment?

The selected starting point is forced automatic monochrome hinting with grayscale output and integral glyph origins. The user prefers linear-light blending at smaller effective sizes and encoded-sRGB blending at larger sizes. Noto Sans Regular and DejaVu Sans react similarly, with a tipping point that varies by about one pixel. This is a human preference from the current comparison, not a universal 16-pixel rule.

The main integration target is Qt's FreeType text engine and its grayscale composition path. Existing desktop configuration can select some ingredients. It cannot directly express the complete tested combination in the inspected Qt version.

## Repository and desktop constraints

The comparison tool supplies a reproducible reference. Its FreeType rows bypass Qt's text rasterizer. Qt only presents the resulting images. Therefore, a pleasant row does not establish that normal Qt text already takes the same path.

The inspected machine runs Ubuntu 26.04.1, Plasma 6.6.6, Qt 6.10.2, and FreeType 2.14.2. The active display runs at its preferred 1920 by 1200 mode with desktop scale 1. No display mode was changed.

Fontconfig currently resolves Noto Sans Regular with antialiasing enabled, slight hinting, automatic hinting disabled, RGB subpixel rendering, and the default LCD filter. KDE's general font is Noto Sans at 10 points. Points in KDE are not the pixel-size inputs in the experiment.

The investigation reads the installed configuration and traces a separate test process. It does not modify the user's Fontconfig files, KDE settings, installed libraries, or desktop services.

## Options

| Option | Useful reach | Limit |
| --- | --- | --- |
| Fontconfig settings alone | Automatic hinting, hinting strength, antialiasing, grayscale selection | Does not expose the tested mono-target plus gray-output combination or the preferred blend policy |
| An isolated Qt change | Native Qt widgets and QPainter text, including relevant decoration paths | Needs a private build and a real Qt comparison before desktop use |
| A Plasma-only change | Qt Quick text renderer selection | Does not by itself change Qt's FreeType hinting and grayscale blending |

Start with an isolated Qt change. Preserve the current desktop until the native Qt path matches the reference and passes visual comparison.

## Evidence

### Fontconfig reaches only part of the method

Qt reads `FC_AUTOHINT`, `FC_HINT_STYLE`, antialiasing, and subpixel geometry. Its Fontconfig database also disables default hinting when the application's device pixel ratio differs from one. An explicit font hinting preference is handled before that default rule. [Qt Fontconfig database, version 6.10.2](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/text/unix/qfontconfigdatabase.cpp).

Qt's FreeType engine chooses light or normal targets for ordinary grayscale. It chooses `FT_LOAD_TARGET_MONO` for monochrome output. Forced auto-hinting is a separate flag. Full hinting disables fractional glyph positioning in this engine. The same source reports gamma-corrected blending through a driver flag set for qualifying CFF fonts, rather than a general size-dependent TrueType preference. [Qt FreeType implementation](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/text/freetype/qfontengine_ft.cpp), [engine declarations](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/text/freetype/qfontengine_ft_p.h).

These are separate decisions. Setting “full hinting” does not mean that grayscale rendering uses the monochrome hinting target.

### The installed library confirms the target mismatch

A temporary pass-through trace recorded real `FT_Load_Glyph` calls originating in the installed `libQt6Gui`. The trace did not change the flags. Each condition sampled 40 calls while Qt drew annotation text in a separate process.

The private Fontconfig condition included the normal system configuration, then overrode automatic hinting to true, hinting to full, antialiasing to true, and subpixel geometry to none. `FONTCONFIG_FILE` and the tracing library applied only to that process.

| Condition | Observed flags | Relevant meaning |
| --- | --- | --- |
| Current settings, Qt scale 1 | `0x10208` | Light target, no forced auto-hinter |
| Private full/auto/grayscale configuration, Qt scale 1 | `0x228` | Forced auto-hinter, normal target |
| Same private configuration, Qt scale 1.25 | `0x22a` | Same flags plus `FT_LOAD_NO_HINTING` |

The other observed bits are `FT_LOAD_NO_BITMAP` and the obsolete `FT_LOAD_IGNORE_GLOBAL_ADVANCE_WIDTH`. The preferred direct FreeType row uses the mono target with forced automatic hinting and grayscale rasterization. The trace establishes actual Qt call selection on this installation. It does not establish the beauty of a new Qt result.

A separate direct FreeType comparison checked `l`, `m`, `n`, `o`, and `g` for Noto Sans and DejaVu Sans at 13, 15, 16, and 16.5 pixels. Automatic normal-target and automatic mono-target grayscale masks differed in every checked case, including dimensions or bearings where applicable. Thus the target distinction is observable in the selected fonts.

### Blending needs its own integration

The raster paint engine passes the font engine's gamma-correction decision to its alpha-mask compositor. Grayscale composition can therefore differ even when a mask is identical. [Qt raster text path](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/painting/qpaintengine_raster.cpp), [alpha-mask composition](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/painting/qdrawhelper.cpp).

The Linux grayscale profile shares Qt's font-smoothing gamma profile. That is not automatically the exact piecewise sRGB decode, linear blend, and sRGB encode used by the experiment. Matching the small-text result needs an explicit transfer-function check. A gamma number alone does not prove equality. [Qt text color profiles](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/kernel/qguiapplication.cpp), [transfer-table support](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/painting/qcolortrclut_p.h).

### Plasma has another renderer selection

Qt Quick defaults to its own text rendering type unless changed. That path is distinct from ordinary native raster text. [Qt Quick window implementation](https://raw.githubusercontent.com/qt/qtdeclarative/v6.10.2/src/quick/items/qquickwindow.cpp).

The inspected Breeze integration selects native text at integral device scale and Qt text at fractional scale. It honors `QT_QUICK_DEFAULT_TEXT_RENDER_TYPE` with values including `nativerendering`. This is behavior of that integration, not proof that every Plasma component honors one global environment variable. [Breeze integration, version 6.6.6](https://raw.githubusercontent.com/KDE/qqc2-breeze-style/v6.6.6/kirigami-plasmadesktop-integration/plasmadesktoptheme.cpp).

Native Qt widgets, KWin decoration text, and Plasma Quick text need separate validation. Changing a Konsole process's Fontconfig environment does not change KWin's process or its title-bar rendering.

## Decision

Use the controlled experiment as the pixel and visual reference for an opt-in, isolated Qt prototype. The prototype needs to combine four existing mechanisms:

1. Keep automatic hinting active at the actual device size, including scaled displays.
2. Use the monochrome hinting target while retaining grayscale output for residual curves and diagonals.
3. Use integral glyph placement in the native text path.
4. Reproduce the experiment's transfer function for small text, with a separately tested size policy for larger text.

An opt-in, isolated Qt patch now implements these mechanisms. The [real Konsole comparison](../experiments/kde-preview.md) describes the build, launch choices, and verification. Blend selection remains manual. The exact size policy remains a calibration question. The user's observations place the transition near 16 effective pixels for the viewed fonts, with about one pixel of variation.

The integration checks render actual QWidget text and compare it with independent FreeType masks and blend formulas. Separate Konsole launches provide the real application comparison. Human judgment still determines the preferred appearance. KWin and Plasma require their own later comparisons because they own different processes and rendering paths.

## Rejected options

Do not present a Fontconfig-only change as an exact reproduction of the selected row. The runtime trace shows a different target and a separate scaling rule.

Do not disable all antialiasing to obtain the mono target. That removes the curve softening the user selected.

Do not install a replacement Qt library or restart the compositor as an untested experiment. The prototype uses private libraries and private application settings without changing the desktop.

## Revisit when

Revisit the integration choice if a distro or upstream Qt update exposes the missing controls, if a native Qt comparison gives a different visual preference, or if another font needs a different blend transition. Validate Qt Quick separately before treating a native-widget result as desktop-wide coverage.

## Sources

The linked Qt 6.10.2 and Breeze 6.6.6 sources identify the relevant owners and selection rules. The installed-library trace independently confirms the hinting-target and scaling behavior on this machine. The isolated prototype adds direct widget and application checks. The Qt Quick conclusions remain source analysis pending a separate integration.
