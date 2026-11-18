# Chromium and Flatpak applications

Chromium-based browsers are not supported by Fontreal. The [support explanation](#chromium-based-browsers-are-not-supported) below describes the limits. Teams and Bitwarden use separate private Fontreal Electron engines with current installed application code and original working data. Those application recipes do not add browser support. Firefox and Floorp use the separate [Mozilla integration](browser-masks.md). Telegram has no activation recipe.

## Enable Teams or Bitwarden for daily use

Run commands from the repository root as your normal desktop user. Keep `build` and `results` on your build volume. Keep the checkout and active artifacts in place while enabled.

Build each target's engine and application view as described below. Follow the [test policy](../../CONTRIBUTING.md#when-to-run-tests). Use each printed application `build.json` as `TEAMS_BUILD_JSON` or `BITWARDEN_BUILD_JSON`:

```sh
python3 -B tools/chromium_delivery.py enable teams --record TEAMS_BUILD_JSON
python3 -B tools/chromium_delivery.py status teams
python3 -B tools/chromium_delivery.py enable bitwarden --record BITWARDEN_BUILD_JSON
python3 -B tools/chromium_delivery.py status bitwarden
```

Status must show `enabled: true` and `compatibility: null`. Fully quit the target through its normal menu, then reopen it normally. An existing process keeps its previous engine. Status describes the launch configuration, not an already running window.

Each target owns its desktop entry, command (`teams-for-linux` or `bitwarden`), application-ID command and existing native autostart override. Both targets share one `flatpak` adapter. The single ownership registry is `$XDG_CONFIG_HOME/fontreal/chromium/apps.json`, with `.config` under `$HOME` as the default configuration directory. The desktop session must search `$HOME/.local/bin` before `/usr/bin`. A new terminal or normal logout/login can load that PATH. Fontreal does not change it.

Application updates keep treatment enabled. On the first launch after an update, Fontreal prepares a view from the new installed code and resources. Later launches reuse it. Ordinary launches do not build engines, run tests, compare application versions or hash the whole package. Explicit installation selectors choose the corresponding native deployment.

The private Fontreal engine and its matching sidecars remain fixed until you rebuild them. Application code updates do not update that engine. Rebuild it to receive upstream engine security fixes. Teams uses complete Electron 44.9.1 sources, including its [Chromium and Node.js certificate mitigation](https://github.com/electron/electron/security/advisories/GHSA-jr5w-w6x2-84p9).

The native application ID, wrapper, fuse settings, application resources and account storage remain in use. Bitwarden retains its process-isolation preload and disabled RunAsNode fuse. Daily activation adds no test profile, E2E data setting, inspector flag or debug listener. Unknown commands and conflicting execution options pass unchanged to native Flatpak.

For stock rendering, fully quit the target and launch its original deployment explicitly:

```sh
/usr/bin/flatpak run com.github.IsmaelMartinez.teams_for_linux
/usr/bin/flatpak run com.bitwarden.desktop
```

To remove activation, fully quit the target normally and run its disable command:

```sh
python3 -B tools/chromium_delivery.py disable teams
python3 -B tools/chromium_delivery.py status teams
python3 -B tools/chromium_delivery.py disable bitwarden
python3 -B tools/chromium_delivery.py status bitwarden
```

Status must show `enabled: false`. Reopen normally for stock rendering. Disable retains accounts and data. Foreign or modified hooks are left untouched. Existing native autostart eligibility stays with the original provider. Fontreal owns one command override on each generated unit and removes it when that target is disabled. Disabling one target preserves the other target and the shared adapter. The final disable removes the adapter.

Explicit enable imports an existing owned Teams `teams.json` into the shared registry. Enable and re-enable validate all owned hooks, then repoint all surviving commands to the current controller. Both saved engine identities and independent enabled states remain intact. The controller hash records the new owner for both targets. Ordinary launch and status do not migrate ownership. A foreign existing hook or newly claimed destination refuses the operation before any hook changes.

## Build the Fontreal engine and application view

This is a full Chromium build. It needs substantial storage and time. Follow the upstream [Electron build requirements](https://www.electronjs.org/docs/latest/development/build-instructions-gn). Install `bubblewrap` and `patch`. The engine source is pinned to Electron 44.9.1, Chromium 152.0.7977.167 and the recorded Skia revision. A retained 44.9.0 checkout supplies unchanged dependencies and independent numerical references. The builder prepares the complete release in private source views. The installed Teams release is not a build gate.

```sh
python3 -B tools/chromium_flatpak.py owners
/usr/bin/flatpak run --command=/usr/bin/true com.github.IsmaelMartinez.teams_for_linux
python3 -B tools/build-electron-selected.py
```

The final output names the selected engine `build.json`. Use that exact path as `C2_BUILD_JSON` below. The normal sandbox and document portal must work. Do not disable them to make a test launch succeed.

```sh
python3 -B tools/build-chromium-delivery.py --build-record C2_BUILD_JSON
```

The assembler prints a different application record. Use it as `TEAMS_BUILD_JSON` for activation. No per-build application qualification is required.

Keep complete selected notices with the engine. The source-stock and passive diagnostic distributions contain an upstream sample credits page and are not redistributable bundles.

## Private V2 rendering preference

Both selected Electron engines include the unchanged V1 core and frozen V2 O/K3 core. Set `FONTREAL_PROFILE=o` or `FONTREAL_PROFILE=k3` before the rendering process starts. Exact lowercase tokens select O or K3 for that process lifetime. Absence and every other value preserve V1. A full restart applies a changed preference.

Enabled ordinary launches read the [shared O/K3 preference](../build-system.md#choose-o-or-k3), with O as the default. Use `sh packaging/session/fontreal-session profile k3` or `profile o`, then fully quit and reopen the application. The actual selected view and inherited directory descriptor stay the same when only the choice changes. Zypak forwards exact O/K3 choices into portal children. Native passthrough adds no profile or view options.

The preference selects coverage inside an already selected engine. It adds no application activation authority and does not upgrade an older saved engine. Direct absent or unsupported values retain V1. Configuration alone does not establish installed V2.

Eligible work retains the existing native NORMAL hinting, whole-pixel placement, grayscale mask and ignored preblend. Hinting-reliant fonts retain the provider's Mono target. Excluded faces and requests keep their native behavior. Chromium 152 supports the grayscale EBDT strike fixture. Chromium 142 keeps its native negative EBDT decoder result. The integration adds no decoder.

V2 rasterizes a separate owned copy of the current hinted, aligned and effect-applied path at four-times coordinates. The high frame expands native bounds by three pixels before scaling. V1 skips this raster. Empty native masks bypass processing. Neither font size nor raw geometry, stride, bearings, advance or source path changes. Both image completion routes process new images once before native mask filtering. Cached reuse adds no pass.

## Checks when Fontreal changes

The application check needs KWin Wayland at 100% scale, Node.js with built-in `fetch` and `WebSocket`, Python Pillow, `busctl`, `qdbus6`, `journalctl`, `kreadconfig6`, GIO and Spectacle. Install Arial Regular so the Flatpak resolves `ArialMT` through host fonts. Build the existing Qt capture helper:

```sh
cmake -S . -B build -G Ninja -DBUILD_TESTING=ON
cmake --build build --target qt-kde-probe
```

Run the focused launch contracts after changing delivery code:

```sh
python3 -B tests/chromium_launch_test.py
```

This synthetic check covers both targets, current resource selection, cached reopening, installation routing, unchanged arguments, legacy Teams migration and independent reversal. It does not establish application rendering.

After changing the pinned engine, run `python3 -B tests/chromium_engine_update_test.py`. It checks complete release sources, packages, credits, cached rebuilding and current application startup with temporary data. Its report distinguishes first credits generation from retained reuse.

After changing the renderer, run the complete check for each supported engine:

```sh
python3 -B tests/chromium_selected_test.py --target teams --build-record C2_BUILD_JSON
python3 -B tests/chromium_selected_test.py --target bitwarden --build-record BITWARDEN_ENGINE_JSON
```

The checks run the ordinary target builder before qualification. They compare V1, O and K3 through actual normal and trace engines. Each mode runs the complete font, size, palette and cache sequence. A focused unsupported token preserves V1. Independent pristine Fontations paths and native Skia rasters define raw coverage, four-times support, metrics and final expected pixels. The checks compare separate operating-system captures and native page PNGs. Neither trace output nor page PNG equality alone establishes displayed pixels.

The native API check requests stroke width zero through `SkFont`, `SkPaint`, `SkStrikeSpec` and `SkGlyph::setImage`. It checks actual hairline masks, high support and final coverage against the pristine provider. Its high raster retains one native pixel of physical width. A one-high-pixel alternative must produce a different final mask. A separate nonzero canvas stroke reaches the direct completion route and displayed pixels. Native mask-filter requests check processing before filtering when the temporary destination differs from the source glyph. Repeated image requests and later glyphs check once-only treatment.

Both native API executables use the same source view and link graph as their corresponding engine. The pristine executable excludes both Fontreal numerical cores. Build checks bind both cores and headers, original sources, tools, packages and complete notices. An unchanged rebuild reuses the exact artifact. A notice-only change preserves every runtime byte. The original paired baseline check is `python3 -B tests/chromium_flatpak_test.py --target teams --case stock-fixture`.

For changes to the Teams integration, run `python3 -B tests/chromium_delivery_test.py --target teams --case actual-app --build-record C2_BUILD_JSON`. It checks the packaged Join Meeting dialog with temporary comparison data and unsent local text. Its qualification report is development evidence and is not required for ordinary activation.

For a V2 engine, this command checks activation through the actual generated hook. A private native Flatpak installation uses exact local application and runtime bundles. Its native override selects private data before startup. The check observes the selected view descriptor and exact O/K3 child masks. Direct absent and unsupported preferences retain V1. Startup files, native permissions, working instances and host overrides remain preserved. The result is `activation-check.json`, separate from full engine qualification.

The original-data lifecycle check is `python3 -B tests/chromium_delivery_test.py --target teams --case lifecycle --build-record C2_BUILD_JSON`. It normally quits and reopens Teams through its entry points, then restores stock rendering. It requires disabled Teams hooks, the O preference and the original stock Teams instance running. Record and restore an existing profile choice around this fixture. The Teams lifecycle and optional update-cycle diagnostics temporarily own the shared launch hooks. Its enabled-autostart scenario preserves the current native preference.

These checks belong to Fontreal development. Do not repeat them for every application release. The previous exact-release update qualification is retired. Its original fixture and prerequisites are available in Git at `e8c541f:docs/experiments/chromium-flatpak.md`. The updated optional `update-cycle` diagnostic expects treatment to survive the native update.

## Build and qualify Bitwarden

Bitwarden uses a separate Electron 39.8.5 source build. Its builder and qualification are separate from Teams. Install `gperf` alongside the build requirements above. The private build environment also searches `build/chromium-flatpak/bitwarden/host-tools/usr/bin` for build tools.

For routine deployment, build the engine and application view:

```sh
python3 -B tools/build-electron-selected.py --target bitwarden
python3 -B tools/build-chromium-delivery.py --target bitwarden --build-record BITWARDEN_ENGINE_JSON
```

Use the engine record printed by the first command as `BITWARDEN_ENGINE_JSON`. Use the application record printed by the second command as `BITWARDEN_BUILD_JSON` for activation.

The remaining commands in this section are development checks for changes to Fontreal. They do not apply to routine builds for supported applications. Start development checks with `python3 -B tests/bitwarden_delivery_test.py --case native-stock`. It uses temporary comparison data and preserves the original application's startup preference, background permission and native fuses.

Use the final engine record path as `BITWARDEN_ENGINE_JSON` for these development checks:

```sh
python3 -B tests/chromium_engine_update_test.py --target bitwarden
python3 -B tests/chromium_selected_test.py --target bitwarden --build-record BITWARDEN_ENGINE_JSON
python3 -B tests/chromium_sdk_test.py
```

The engine check assembles the real application with preserved resources, modules, wrapper and fuses. It checks private startup for all four source and selected roles. The fixture check compares masks and displayed pixels with the independent source provider. These checks establish engine behavior and secured startup. Continue with packaged input pixels and the original-data lifecycle below.

The transport build uses the available Freedesktop SDK 25.08 and records its actual commit and compiler. It does not require Bitwarden's unavailable historical vendor SDK. SDK setup stays in private build storage. The offline SDK test checks selection and receipts. Actual compilation and packaged startup provide separate compatibility evidence.


For changes to the Bitwarden integration, check the packaged email input and original-data lifecycle:

```sh
python3 -B tests/chromium_delivery_test.py --target bitwarden --case actual-app --build-record BITWARDEN_ENGINE_JSON
python3 -B tests/chromium_delivery_test.py --target bitwarden --case lifecycle --build-record BITWARDEN_ENGINE_JSON
```

The actual-app check uses temporary data and an isolated X11 display. Install Xvfb, `xwininfo`, X11/XTest libraries and the KWin requirements above. Its native input captures must equal the packaged page captures. With a V2 engine, the private native installation and generated hook supply O/K3 child witnesses in the actual input. The check writes `activation-check.json`. Existing V1 records keep their four-role qualification. Native stderr relay credentials do not identify a renderer process. Actual input evidence and opaque engine qualification remain separate parts of the proof.

The lifecycle check requires disabled Bitwarden hooks, the O preference and one original stock Bitwarden window. Record and restore an existing profile choice around this fixture. It uses normal Ctrl+Q quit and reopens the same data through command, application-ID, desktop, shared Flatpak and eligible native-autostart routes. It checks K3 reopening, stock escape, independent disable, preserved Teams engine identity and final stock reopening. It preserves the original data directory, startup preference and background permission. This check operates on the original profile. It adds no account data or alternate data path.

The actual-app report identifies the same application record for development evidence. Ordinary activation uses the assembler's record without a qualification report. Bitwarden does not support the optional Teams `update-cycle` diagnostic.

## Applications without activation

A loaded host FreeType library does not treat an embedded Chromium renderer. Each application needs its reached text owner. Teams and Bitwarden use distinct exact-source engines and separate application qualification.

Telegram includes its own static Qt controls. Fontreal supplies no Telegram activation command. See the [app scenarios](../app-scenarios.md) and [roadmap](../roadmap.md).

### Chromium-based browsers are not supported

Chrome, Edge, Brave, Vivaldi and other Chromium-based browsers are not supported by Fontreal. These browsers draw page text inside their own browser engine. Installing Fontreal's desktop libraries does not apply its stroke adjustments to that text. Fontreal has no supported connection to the part of these engines that draws letters.

Browser extensions cannot provide that connection. The [font settings API](https://developer.chrome.com/docs/extensions/reference/api/fontSettings) lets an extension choose fonts and sizes. The [debugger API](https://developer.chrome.com/docs/extensions/reference/api/debugger) lets it change page content and styles. Neither provides access to apply Fontreal while the engine draws each letter. [Native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging) runs a helper outside the browser engine and does not provide that access either.

Support needs changes inside the browser engine. Fontreal does not provide custom Chromium browser builds or patches to installed browser binaries. Maintaining those changes across browser security updates is beyond this project's current scope. The separate Teams and Bitwarden engine recipes apply only to those applications. They do not make Chromium-based browsers supported.

### Native Edge settings experiment

Edge 157.0.4341.46 on Linux produces identical page captures with and without `--text-gamma=1 --text-contrast=0`. The comparison uses native Wayland windows, separate temporary profiles, six loaded font files and a device scale of 1. It includes Noto Sans Display at integer sizes from 8pt through 16pt, plus Noto Sans, Noto Serif, Arial, Liberation Mono and Lato Light.

The embedded Chromium version is 157.0.8103.39. Its [renderer launch code](https://github.com/chromium/chromium/blob/157.0.8103.39/content/browser/renderer_host/render_process_host_impl.cc) forwards these two switches only on Windows. Their presence in the Linux binary does not establish page support. A host FreeType preload also does not establish coverage of this bundled renderer.

A second native configuration changes the captured glyphs. It forces full native hinting and grayscale antialiasing through a process-specific Fontconfig file. It also uses `--disable-font-subpixel-positioning` and `--disable-lcd-text`, alongside the two ineffective gamma and contrast switches. Chromium's [Linux font configuration](https://github.com/chromium/chromium/blob/157.0.8103.39/ui/gfx/font_render_params_linux.cc) reads Fontconfig rendering preferences. This configuration changes native fitting. It does not run Fontreal's selected mask processing or reproduce its 50% fitting rule.

The previews show stock Edge on the left and the native experiment on the right. The experiment changes 28,758 pixels across both themes. These counts include labels. One 9pt row also moves vertically by one device pixel. The captures use the same fonts and page content. They do not establish matching geometry or the exact Fontreal profile.

[Light preview](../images/edge-native/light.png) · [Dark preview](../images/edge-native/dark.png)

The visual comparison favors stock Edge, so full native hinting is not adopted. No persistent Edge launcher or account-profile change accompanies this experiment. Inspection of the installed binary finds no exported `FT_Load_Glyph`, `FT_Render_Glyph` or `SkScalerContext` entry point for a preload hook. Exact Fontreal support still needs an integration point in Edge's bundled page renderer. Native settings do not provide that integration.
