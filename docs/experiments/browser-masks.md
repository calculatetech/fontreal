# Firefox and Floorp

Use the approved rendering in your existing working browser profile. Your accounts, bookmarks, history, sessions, and unrelated settings stay in place. Normal commands and desktop launchers keep their browser identity and native actions.

The selected preset uses native normal hinting, grayscale coverage correction, whole-pixel positioning, and encoded blending. Native hints preserve the font’s shape. The coverage pass strengthens weak connected strokes, protects corners and intersections, and concentrates split stems around a single stronger pixel. Sustained thin stems use a weighted average of the glyph’s strongest quarter of pixels. The optional connected-curve extension is not selected. No font or character names select different processing rules.

The recipe is `FONTREAL_FT_CONTRAST=weighted`. Its four preferences disable subpixel antialiasing, fractional glyph positioning, Mozilla gamma (`-1`), and Mozilla enhanced contrast. Mozilla still controls shaping, caching, and final composition. The native processor receives only bitmap pixels and dimensions. Existing activation records retain their treatment until you explicitly enable again. Re-enable selects the new preset and preserves the initial restoration values.

The earlier `raw` diagnostic retains automatic monochrome hints, nearest Latin Y rounding, and unchanged grayscale coverage. It is separate from the selected native-normal method.

The earlier `ramp217` diagnostic remains available. Its light weights below 400 retain raw coverage. Its regular coverage ramp leaves 0–96 unchanged, maps 97–127 with `3*a-192`, and maps 128–159 with `192+((a-128)*50+16)//32`. Values 160–241 become 242. Values 242–255 stay unchanged. Native one-bit dropout correction selects additional support pixels from the original hinted outline. Only those pixels receive the minimum opacity 217 after the ramp, before glyph overlap. The selected preset uses its own coverage pass instead of this earlier ramp.

## Enable the working profile

Use the supported versions and build requirements below. Run the command for each browser you use:

```sh
python3 tools/browser.py enable firefox
python3 tools/browser.py enable floorp
```

Fully quit and reopen each browser to activate the treatment. An already running browser keeps its loaded library until that restart. The tool configures the ordinary Install-default profile and checks that any running profile agrees. If Firefox has different historical installation defaults, first open it normally. Activation can then use the declared default that all ordinary native parents select. Explicit profile, profile-manager and reset launches cannot resolve that ambiguity. A closed ambiguous installation still refuses activation. The tool does not create or copy browser profiles or change their indexes.

Firefox indexes can live in `mozilla/firefox` below `XDG_CONFIG_HOME` or in the legacy `.mozilla/firefox` directory below your home directory. Floorp indexes can live in `floorp` below `XDG_CONFIG_HOME` or in the legacy `.floorp` directory below your home directory. When unset, `XDG_CONFIG_HOME` defaults to `.config` below your home directory. The tool checks all existing indexes in the active roots. Equivalent relative and absolute defaults count as one profile; distinct defaults cause refusal. Floorp has no Firefox historical-default exception. With a custom configuration root, an inactive `.config/floorp` index below your home directory does not select the working profile.

Activation manages four rendering preferences and installs per-user launch hooks. Re-enabling upgrades an older owned preset and preserves its original restoration values. Your font family, display scale, startup settings, normal Fontconfig configuration, and browser data stay in place. Unrelated applications, including Qt helpers launched by the browser, keep their normal rendering.

Keep the checkout and active build artifacts while enabled. Open a new terminal if an existing shell caches the old browser command. If you change the ordinary default profile, disable treatment before that change and enable it again afterward.

To inspect activation:

```sh
python3 tools/browser.py status firefox
python3 tools/browser.py status floorp
```

The status shows the configured working profile, treated parent processes, and processes that still need a restart. Browser updates do not disable Fontreal. Enabled launchers use the saved Fontreal build across browser and system-library updates, without rebuilding or checking installed versions. If the saved library is missing or changed, the wrapper warns and starts the installed browser without it. Disable restores the original rendering settings. After you rebuild Fontreal, run enable again to select that build and retain the original restoration values.

## When Nimbus Sans looks untreated

The selected profile supports TrueType and CFF fonts. Legacy Type 1 fonts keep their native rendering. A loaded Fontreal library alone does not prove that a particular font receives treatment.

Some installations contain both CFF and Type 1 copies of Nimbus Sans. Firefox can select a Type 1 copy for ordinary Nimbus Sans or Helvetica requests, even when `fc-match` reports CFF. Inspect the available copies:

```sh
fc-list 'Nimbus Sans' -f '%{family}|%{style}|%{fontformat}\n'
```

If both formats exist, first make sure that CFF copies cover the styles you use. To exclude only the legacy Nimbus Sans copies, save this optional rule as `51-fontreal-nimbus-cff.conf` in your per-user Fontconfig `conf.d` directory:

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <selectfont>
    <rejectfont>
      <pattern>
        <patelt name="family"><string>Nimbus Sans</string></patelt>
        <patelt name="fontformat"><string>Type 1</string></patelt>
      </pattern>
    </rejectfont>
  </selectfont>
</fontconfig>
```

Fully quit and reopen Firefox after adding the rule. Reloading a tab does not rebuild its font list. This rule affects Nimbus Sans selection across applications for that user. It preserves the font files and leaves other families available. Remove this rule and restart the affected applications to restore the original selection. The browser enable and disable commands do not manage this separate Fontconfig rule.

In a controlled Firefox comparison, embedded CFF received the raw profile while ordinary Nimbus Sans and Helvetica selected untreated Type 1 copies. Excluding those copies made all three routes match the treated native masks exactly for t, f, e, o, and s. This establishes the format bypass. It does not establish a visual winner for curved strokes or qualify every website.

## Restore the original rendering

Fully quit the browser before disabling. The browser saves its preferences when it exits, so live edits cannot safely restore the original values.

```sh
python3 tools/browser.py disable firefox
python3 tools/browser.py disable floorp
```

Disable restores the original rendering preferences, removes the owned launch hooks, and keeps unrelated settings and browser data. It also removes treatment values that the browser saved during use. A later normal launch uses the installed library. Existing custom launch hooks or modified Fontreal hooks are left untouched when they prevent safe activation or removal.

## Requirements and build

The builder supports amd64 Debian 13 with FreeType `2.13.3+dfsg-1+deb13u1` and amd64 Ubuntu 26.04 with `2.14.2+dfsg-1ubuntu0.2`. These are build-source requirements, not browser launch gates. Firefox and Floorp releases do not need an entry in a version list. Test when Fontreal changes; a browser update does not require a qualification run. The saved private library receives upstream fixes when you rebuild Fontreal and enable that build.

Use Python 3, C and C++17 compilers, make, pkg-config, patch, dpkg-source, and APT download access. The builder downloads matching development packages into its private directory. It does not install them. Exact source archives have pinned checksums from authenticated distro source indexes. Both routes preserve distro security patches. Debian retains its configuration without HarfBuzz. Ubuntu retains dynamic HarfBuzz. The shared patch applies with zero fuzz to both sources.

Keep the repository's `build` and `results` directories on storage with enough free space. They can be links to a separate build volume. All source extraction, compilation, temporary profiles, and results use those directories.

```sh
python3 tools/build-freetype.py
```

The final output line names `build.json`. This file records the source archives, patch, build recipe, compiler, development packages, configuration, dependencies, and library hashes. The selected processor source, declaration, and C++ compiler also participate in the build identity. The candidate links the standard C++ runtime. The artifact directory contains separate stock and candidate sources and libraries, plus the FreeType license and notice.

## Compare actual windows

The diagnostic comparison uses disposable profiles. Daily browsing uses the working-profile commands above. The comparison page includes regular, bold, italic, and bold italic on light and dark backgrounds. Run each command separately and close each window when finished. The default local page needs no account or remote service.

```sh
python3 tools/preview-browser.py control
python3 tools/preview-browser.py weighted
python3 tools/preview-browser.py raw
python3 tools/preview-browser.py encoded
python3 tools/preview-browser.py preblend
python3 tools/preview-browser.py ramp217
```

| Mode | Private library | Edge blending |
| --- | --- | --- |
| `control` | Unmodified source | Encoded blend, with Mozilla gamma disabled |
| `encoded` | Fontreal masks and mild contrast | Encoded blend, with Mozilla gamma disabled |
| `control-preblend` | Unmodified source | Mozilla sRGB preblend |
| `preblend` | Fontreal masks and mild contrast | Mozilla sRGB preblend |
| `weighted` | Selected native normal hints and weighted stem coverage | Encoded blend, with Mozilla gamma disabled |
| `raw` | Earlier nearest Y and fully raw coverage at every weight | Encoded blend, with Mozilla gamma disabled |
| `ramp217` | Earlier nearest Y, weight-aware ramp and native support | Encoded blend, with Mozilla gamma disabled |

The selected mode enforces native normal hints. Earlier modes retain automatic hints. All modes use grayscale antialiasing, whole-pixel positioning, and no embedded bitmaps through the private browser and Fontconfig configuration. Mozilla enhanced contrast stays disabled. The two control modes let you distinguish a changed mask from a changed blend. They do not represent every user's default browser configuration.

To test Floorp or another supported scale:

```sh
python3 tools/preview-browser.py preblend --browser floorp --scale 1.25
python3 tools/preview-browser.py preblend --scale 1.5
```

An optional positional URL opens another test page in the same disposable profile. Each comparison launch uses a fresh profile and private XDG configuration directories. Closing that window removes its state. These diagnostic launches do not change the working profile or its activation. Installed FreeType, accepted Qt, and Flatpak overrides stay unchanged.

The selected and raw presets apply to explicitly enabled raster requests for scalable, non-color TrueType and CFF faces. CFF includes variable CFF2 faces and CID collections. Older `none`, `mild`, and `ramp217` diagnostics keep their earlier CFF behavior. Color fonts, bitmap-only fonts, and unscaled, unhinted, or metrics-only requests retain their original path. Browser shaping and transform restrictions remain in place.

## Repeat the checks

The checks need the installed fonts from the fixture, Qt 6 Core development files, Pillow, Xvfb, KWin Wayland, and the existing `build/qt-kde-probe` from the KDE checks. They use nested software-rendered browser windows and Mozilla's local test protocol. They do not disable the browser sandbox.

```sh
python3 tests/selected_profile_test.py --case native
python3 tests/selected_profile_test.py --case core
python3 tests/selected_profile_test.py --case identity
python3 tests/selected_profile_test.py --case legacy
python3 tests/selected_profile_test.py --case gates --cff2-font /path/to/Cantarell-VF.otf
python3 tests/selected_profile_test.py --case browser --cff2-font /path/to/Cantarell-VF.otf
python3 tests/kde_selected_comparison_test.py
python3 tests/browser_masks_test.py --case all
python3 tests/browser_delivery_test.py
python3 tests/browser_live_recipe_test.py --variable-font /path/to/installed-variable.ttf --case native
python3 tests/browser_live_recipe_test.py --variable-font /path/to/installed-variable.ttf --case browser
python3 tests/raw_coverage_test.py --variable-font /path/to/installed-variable.ttf --case native
python3 tests/raw_coverage_test.py --variable-font /path/to/installed-variable.ttf --case browser
```

The component check compares public FreeType results with an independent, unmodified FreeType reference. It creates local synthetic font fixtures for embedded bitmaps and FreeType's name-based native-hinter restriction. It also checks transform restrictions and an unavailable auto-hinter through public FreeType APIs. These fixtures derive from the installed Noto font. They are not distributed font files.

Test builds report final glyph masks from real browser raster calls. Actual window captures measure placement and compare encoded and actual-background linear predictions separately. Browser controls have separate captures and must not inherit page-text results.

The selected checker compares production API results against the unchanged accepted masks for all saved fonts, sizes, and styles. It also checks bitmap strides, variable-font state, format gates, real browser raster calls, and complete words in actual windows. Its results are under `results/selected-profile`. The KDE comparison checker requires the paired original and private Qt builds and publishes only portable metadata.

The earlier generated reports and lossless captures are under `results/browser-masks`, `results/browser-live-recipe`, and `results/raw-coverage`. The raw checker uses an independent nearest-only reference from the matching distro source. It checks TrueType, CFF, current variable weights, native lifecycle calls, and actual browser words. CID checks include actual CJK glyphs. The earlier live-recipe checker retains `ramp217` diagnostics. Installed fonts are local test inputs and are not redistributed. Historical 2.14.2 captures remain separate evidence from Debian 2.13.3 output. Inspect original PNGs at one image pixel per display pixel. Native window results do not certify every hardware compositor or every browser version.

The delivery check exercises ordinary commands and desktop actions, native profile selection and remoting, and enable/use/disable restoration. Synthetic existing profiles run in an isolated filesystem view with the normal browser sandbox. Real account profiles stay untouched by these checks. Delivery results are under `results/browser-delivery`.

`tests/selected_working_browser_test.py` is a separate, explicit host check. It enables the selected method in existing working profiles and opens local test tabs through the ordinary launchers. It compares actual display pixels on both backgrounds and leaves the browsers running. Close browsers that still use an older renderer normally before running it. It does not disable extensions or alter unrelated preferences. The local fixture declares its own light and dark colors.

After building matching KDE libraries, run the delivery check with `--case lifecycle --native-helper` and their library paths. Export `FONTREAL_TEST_REFERENCE_FREETYPE` with the independent pristine reference. This checks actual browser-child selected Qt output and an upgrade from the retained TrueType-only provider. The newer provider must support the typed selected property for TrueType and CFF. Older providers must fall back to untreated Qt output.

The [native build guide](../build-system.md#check-a-complete-plasma-session) also describes `--native-bundle` for a marked disposable VM. It continues existing browser activations through actual native installation, ordinary restarts, and rollback. Start the native browsers normally once and close them normally; leave their generated indexes untouched. The check snapshots all eight current and legacy profile/install index paths before fixture changes, uses only observed native roots and installation IDs, and restores the original files and absence. Synthetic all-root/history checks remain separate. Both browsers also check refusal to move an existing activation to another ordinary default without disabling it first.

The current color-emoji browser fixture produces no visible glyph in both control and candidate. Its empty matching regions do not prove visible emoji rendering. The separate FreeType component check uses an actual color bitmap. Browser toolbar font matching remains unresolved even though separate toolbar captures exist.

Report the mode, browser, font, style, size, scale, and background that you prefer. Regular text on white remains the main visual acceptance case. Keep colored backgrounds and the other styles in the comparison.
