# Private browser comparison

This experiment brings automatic monochrome hinting, grayscale edges, and mild contrast into actual Firefox and Floorp windows. It targets regular text on white, where the existing browser controls still looked blurry. The page also includes bold, italic, and bold italic on light and dark backgrounds.

This is an early browser experiment. Mozilla still controls layout, glyph placement, caching, and final blending. Its sRGB preblend adjusts the glyph mask using a guessed background. It does not implement the full Qt blend against each actual background.

## Requirements and build

The first build targets amd64 Ubuntu 26.04 with FreeType `2.14.2+dfsg-1ubuntu0.2`. The launcher accepts installed Firefox `160.0` or Floorp `12.21.1@159.0.1`. Version checks stop a mismatched comparison. Debian 13 browser builds remain separate work.

Use Python 3, a C compiler, make, pkg-config, patch, dpkg-source, and APT download access. The builder downloads matching development packages into its private directory. It does not install them. The exact source archives have pinned checksums from Ubuntu's authenticated source index. Both builds preserve the distro security patches and use dynamic HarfBuzz.

Keep the repository's `build` and `results` directories on your build storage. On the development machine they point into `/storage/builds/fontreal`. All source extraction, compilation, temporary profiles, and results use those directories.

```sh
python3 tools/build-freetype.py
```

The final output line names `build.json`. This file records the source archives, patch, build recipe, compiler, development packages, configuration, dependencies, and library hashes. The artifact directory contains separate stock and candidate sources and libraries, plus the FreeType license and notice.

## Compare actual windows

Run each command separately. Close each window when you finish its comparison. The default local page needs no account or remote service.

```sh
python3 tools/preview-browser.py control
python3 tools/preview-browser.py encoded
python3 tools/preview-browser.py preblend
```

| Mode | Private library | Edge blending |
| --- | --- | --- |
| `control` | Unmodified source | Encoded blend, with Mozilla gamma disabled |
| `encoded` | Fontreal masks and mild contrast | Encoded blend, with Mozilla gamma disabled |
| `control-preblend` | Unmodified source | Mozilla sRGB preblend |
| `preblend` | Fontreal masks and mild contrast | Mozilla sRGB preblend |

Every mode requests full automatic hints, grayscale antialiasing, whole-pixel positioning, and no embedded bitmaps through the same private browser and Fontconfig configuration. Mozilla enhanced contrast stays disabled. The two control modes let you distinguish a changed mask from a changed blend. They do not represent every user's default browser configuration.

To test Floorp or another supported scale:

```sh
python3 tools/preview-browser.py preblend --browser floorp --scale 1.25
python3 tools/preview-browser.py preblend --scale 1.5
```

An optional positional URL opens another test page in the same disposable profile. Each launch uses a fresh profile and private XDG configuration directories. Closing the window removes that state. Your normal browser profile, installed FreeType, accepted Qt installation, and Flatpak overrides stay unchanged. There is no system installation to undo.

The patch applies only to explicitly enabled raster requests for scalable, non-color TrueType faces. CFF fonts, color fonts, bitmap-only fonts, and requests for unscaled, unhinted, or metrics-only data retain their original path. Browser shaping and transform restrictions remain in place.

## Repeat the checks

The checks need the installed fonts from the fixture, Qt 6 Core development files, Pillow, Xvfb, KWin Wayland, and the existing `build/qt-kde-probe` from the KDE checks. They use nested software-rendered browser windows and Mozilla's local test protocol. They do not disable the browser sandbox.

```sh
python3 tests/browser_masks_test.py --case all
```

The component check compares public FreeType results with an independent, unmodified FreeType reference. It creates local synthetic font fixtures for embedded bitmaps and FreeType's name-based native-hinter restriction. It also checks transform restrictions and an unavailable auto-hinter through public FreeType APIs. These fixtures derive from the installed Noto font. They are not distributed font files.

Test builds report final glyph masks from real browser raster calls. Actual window captures measure placement and compare encoded and actual-background linear predictions separately. Browser controls have separate captures and must not inherit page-text results.

The generated reports and lossless captures are under `results/browser-masks`. Inspect original PNGs at one image pixel per display pixel. Native window results do not certify every hardware compositor or every browser version.

The current color-emoji browser fixture produces no visible glyph in both control and candidate. Its empty matching regions do not prove visible emoji rendering. The separate FreeType component check uses an actual color bitmap. Browser toolbar font matching remains unresolved even though separate toolbar captures exist.

Report the mode, browser, font, style, size, scale, and background that you prefer. Regular text on white remains the main visual acceptance case. Keep colored backgrounds and the other styles in the comparison.
