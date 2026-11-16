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

Explicit enable imports an existing owned Teams `teams.json` into the shared registry. It preserves the exact saved Teams build and qualification identities and repoints its commands to the current controller. Ordinary launch and status do not migrate ownership. A foreign existing hook or newly claimed destination refuses the operation before any hook changes.

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

After changing the renderer, run `python3 -B tests/chromium_selected_test.py --build-record C2_BUILD_JSON`. This compares actual engine masks and final pixels with independent references. The original paired baseline check is `python3 -B tests/chromium_flatpak_test.py --target teams --case stock-fixture`.

For changes to the Teams integration, run `python3 -B tests/chromium_delivery_test.py --target teams --case actual-app --build-record C2_BUILD_JSON`. It checks the packaged Join Meeting dialog with temporary comparison data and unsent local text. Its qualification report is development evidence and is not required for ordinary activation.

The original-data lifecycle check is `python3 -B tests/chromium_delivery_test.py --target teams --case lifecycle --build-record C2_BUILD_JSON`. It normally quits and reopens Teams through its entry points, then restores stock rendering. It requires both targets disabled and the original stock Teams instance running. The Teams lifecycle and optional update-cycle diagnostics temporarily own the shared launch hooks. Its enabled-autostart scenario preserves the current native preference.

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

The actual-app check assembles the application view and writes its adjacent qualification only after all four secured roles pass. It uses temporary data and an isolated X11 display. Install Xvfb, `xwininfo`, X11/XTest libraries and the KWin requirements above. Its native input captures must equal the packaged page captures. Independent pristine glyph masks, paths and metrics define the expected selected pixels. Native stderr relay credentials do not identify a renderer process.

The lifecycle check requires disabled Bitwarden hooks and one original stock Bitwarden window. It uses normal Ctrl+Q quit and reopens the same data through command, application-ID, desktop, shared Flatpak and eligible native-autostart routes. It checks stock escape, independent disable, preserved Teams ownership and final stock reopening. It preserves the original data directory, startup preference and background permission. This check operates on the original profile. It adds no account data or alternate data path.

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
