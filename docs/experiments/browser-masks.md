# Firefox and Floorp

Use the approved rendering in your existing working browser profile. Your accounts, bookmarks, history, sessions, and unrelated settings stay in place. Normal commands and desktop launchers keep their browser identity and native actions.

The preset combines automatic monochrome hints, grayscale edges, mild contrast, and Mozilla sRGB preblend. The user approved the actual-browser samples, including regular text on white. Mozilla still controls layout, caching, and final blending. Its preblend estimates the background. It does not implement full actual-background linear blending.

## Enable the working profile

Use the supported versions and build requirements below. Run the command for each browser you use:

```sh
python3 tools/browser.py enable firefox
python3 tools/browser.py enable floorp
```

Fully quit and reopen each browser to activate the treatment. An already running browser keeps its loaded library until that restart. The tool configures the ordinary Install-default profile and checks that any running profile agrees. It does not create or copy browser profiles.

Activation manages four rendering preferences and installs per-user launch hooks. Your font family, display scale, startup settings, normal Fontconfig configuration, and browser data stay in place. Unrelated applications, including Qt helpers launched by the browser, keep their normal rendering.

Keep the checkout and active build artifacts while enabled. Open a new terminal if an existing shell caches the old browser command. If you change the ordinary default profile, disable treatment before that change and enable it again afterward.

To inspect activation:

```sh
python3 tools/browser.py status firefox
python3 tools/browser.py status floorp
```

The status shows the configured working profile, treated parent processes, and processes that still need a restart. A browser or FreeType update can make the recorded override incompatible. The wrapper then warns and starts the installed browser without the private library. Its rendering preferences remain configured until you disable or rebuild. Matching build support must be updated before enabling an unsupported revision.

## Restore the original rendering

Fully quit the browser before disabling. The browser saves its preferences when it exits, so live edits cannot safely restore the original values.

```sh
python3 tools/browser.py disable firefox
python3 tools/browser.py disable floorp
```

Disable restores the original rendering preferences, removes the owned launch hooks, and keeps unrelated settings and browser data. It also removes treatment values that the browser saved during use. A later normal launch uses the installed library. Existing custom launch hooks or modified Fontreal hooks are left untouched when they prevent safe activation or removal.

## Requirements and build

The first build targets amd64 Ubuntu 26.04 with FreeType `2.14.2+dfsg-1ubuntu0.2`. The launcher accepts installed Firefox `160.0` or Floorp `12.21.1@159.0.1`. Version checks stop a mismatched comparison. Debian 13 browser builds remain separate work.

Use Python 3, a C compiler, make, pkg-config, patch, dpkg-source, and APT download access. The builder downloads matching development packages into its private directory. It does not install them. The exact source archives have pinned checksums from Ubuntu's authenticated source index. Both builds preserve the distro security patches and use dynamic HarfBuzz.

Keep the repository's `build` and `results` directories on storage with enough free space. They can be links to a separate build volume. All source extraction, compilation, temporary profiles, and results use those directories.

```sh
python3 tools/build-freetype.py
```

The final output line names `build.json`. This file records the source archives, patch, build recipe, compiler, development packages, configuration, dependencies, and library hashes. The artifact directory contains separate stock and candidate sources and libraries, plus the FreeType license and notice.

## Compare actual windows

The diagnostic comparison uses disposable profiles. Daily browsing uses the working-profile commands above. The comparison page includes regular, bold, italic, and bold italic on light and dark backgrounds. Run each command separately and close each window when finished. The default local page needs no account or remote service.

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

An optional positional URL opens another test page in the same disposable profile. Each comparison launch uses a fresh profile and private XDG configuration directories. Closing that window removes its state. These diagnostic launches do not change the working profile or its activation. Installed FreeType, accepted Qt, and Flatpak overrides stay unchanged.

The patch applies only to explicitly enabled raster requests for scalable, non-color TrueType faces. CFF fonts, color fonts, bitmap-only fonts, and requests for unscaled, unhinted, or metrics-only data retain their original path. Browser shaping and transform restrictions remain in place.

## Repeat the checks

The checks need the installed fonts from the fixture, Qt 6 Core development files, Pillow, Xvfb, KWin Wayland, and the existing `build/qt-kde-probe` from the KDE checks. They use nested software-rendered browser windows and Mozilla's local test protocol. They do not disable the browser sandbox.

```sh
python3 tests/browser_masks_test.py --case all
python3 tests/browser_delivery_test.py
```

The component check compares public FreeType results with an independent, unmodified FreeType reference. It creates local synthetic font fixtures for embedded bitmaps and FreeType's name-based native-hinter restriction. It also checks transform restrictions and an unavailable auto-hinter through public FreeType APIs. These fixtures derive from the installed Noto font. They are not distributed font files.

Test builds report final glyph masks from real browser raster calls. Actual window captures measure placement and compare encoded and actual-background linear predictions separately. Browser controls have separate captures and must not inherit page-text results.

The generated reports and lossless captures are under `results/browser-masks`. Inspect original PNGs at one image pixel per display pixel. Native window results do not certify every hardware compositor or every browser version.

The delivery check exercises ordinary commands and desktop actions, native profile selection and remoting, and enable/use/disable restoration. Synthetic existing profiles run in an isolated filesystem view with the normal browser sandbox. Real account profiles stay untouched by these checks. Delivery results are under `results/browser-delivery`.

The current color-emoji browser fixture produces no visible glyph in both control and candidate. Its empty matching regions do not prove visible emoji rendering. The separate FreeType component check uses an actual color bitmap. Browser toolbar font matching remains unresolved even though separate toolbar captures exist.

Report the mode, browser, font, style, size, scale, and background that you prefer. Regular text on white remains the main visual acceptance case. Keep colored backgrounds and the other styles in the comparison.
