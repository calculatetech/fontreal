# Chromium and Flatpak applications

Teams uses a private Fontreal Electron engine with the current installed application code and its original working data. Firefox and Floorp use the separate [Mozilla integration](browser-masks.md). Edge, Bitwarden and Telegram do not yet have a working activation recipe.

## Enable Teams for daily use

Run commands from the repository root as your normal desktop user. Keep `build` and `results` on your build volume. Keep the checkout and active artifacts in place while enabled.

Use the application `build.json` produced by the setup below as `TEAMS_BUILD_JSON`:

```sh
python3 -B tools/chromium_delivery.py enable teams --record TEAMS_BUILD_JSON
python3 -B tools/chromium_delivery.py status teams
```

Status must show `enabled: true` and `compatibility: null`. Fully quit Teams through its normal menu, then reopen it normally. An existing process keeps its previous engine. Status describes the launch configuration, not an already running window.

The owned hooks cover the desktop entry, `teams-for-linux`, the application-ID command, supported `flatpak run` commands, and existing native autostart. The desktop session must search `$HOME/.local/bin` before `/usr/bin`. A new terminal or normal logout/login can load that PATH. Fontreal does not change it.

Application updates keep treatment enabled. On the first launch after an update, Fontreal prepares a view from the new installed code and resources. Later launches reuse it. Ordinary launches do not build engines, run tests, compare application versions or hash the whole package. Explicit installation selectors choose the corresponding native deployment.

The private Fontreal engine and its matching sidecars remain fixed until you rebuild them. Application code updates do not update that engine. Rebuild it to receive upstream engine security fixes. The selected builder uses complete Electron 44.9.1 sources, including its [Chromium and Node.js certificate mitigation](https://github.com/electron/electron/security/advisories/GHSA-jr5w-w6x2-84p9).

The native application ID, wrapper, fuse settings, application resources and account storage remain in use. Daily activation adds no test profile, E2E data setting, inspector flag or debug listener. Unknown commands and conflicting execution options pass unchanged to native Flatpak.

For stock rendering, fully quit Teams and launch the original deployment explicitly:

```sh
/usr/bin/flatpak run com.github.IsmaelMartinez.teams_for_linux
```

To remove activation, fully quit Teams normally and run:

```sh
python3 -B tools/chromium_delivery.py disable teams
python3 -B tools/chromium_delivery.py status teams
```

Status must show `enabled: false`. Reopen normally for stock rendering. Disable retains accounts and data. Foreign or modified hooks are left untouched. Existing native autostart eligibility stays with the original provider. Fontreal owns one command override on that generated unit and removes it on disable.

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
python3 -B tests/chromium_delivery_test.py --target teams --case actual-app --build-record C2_BUILD_JSON
```

The assembler prints a different application record. Use it as `TEAMS_BUILD_JSON` for activation. The actual-app check writes the adjacent qualification for this Fontreal build. It opens the packaged Join Meeting dialog with temporary comparison data and unsent local text. It retains only a generic input crop. It does not change the working account.

The application check needs KWin Wayland at 100% scale, Node.js with built-in `fetch` and `WebSocket`, Python Pillow, `busctl`, `qdbus6`, `journalctl`, `kreadconfig6`, GIO and Spectacle. Install Arial Regular so the Flatpak resolves `ArialMT` through host fonts. Build the existing Qt capture helper:

```sh
cmake -S . -B build -G Ninja -DBUILD_TESTING=ON
cmake --build build --target qt-kde-probe
```

Keep complete selected notices with the engine. The source-stock and passive diagnostic distributions contain an upstream sample credits page and are not redistributable bundles.

## Checks when Fontreal changes

Run the focused launch contracts after changing delivery code:

```sh
python3 -B tests/chromium_launch_test.py
```

This synthetic check proves current resource selection, cached reopening, installation routing, unchanged arguments, owned reversal and absence of release qualification. It does not establish application rendering.

After changing the pinned engine, run `python3 -B tests/chromium_engine_update_test.py`. It checks complete release sources, packages, credits, cached rebuilding and current application startup with temporary data. Its report distinguishes first credits generation from retained reuse.

After changing the renderer, run `python3 -B tests/chromium_selected_test.py --build-record C2_BUILD_JSON`. This compares actual engine masks and final pixels with independent references. The original paired baseline check is `python3 -B tests/chromium_flatpak_test.py --target teams --case stock-fixture`.

The original-data lifecycle check is `python3 -B tests/chromium_delivery_test.py --target teams --case lifecycle --build-record C2_BUILD_JSON`. It normally quits and reopens Teams through its entry points, then restores stock rendering. It requires disabled Fontreal hooks and the original stock instance running. Its enabled-autostart scenario preserves the current native preference.

These checks belong to Fontreal development. Do not repeat them for every Teams release. The previous exact-release update qualification is retired. Its original fixture and prerequisites are available in Git at `e8c541f:docs/experiments/chromium-flatpak.md`. The updated optional `update-cycle` diagnostic expects treatment to survive the native update.

## Other applications

A loaded host FreeType library does not treat an embedded Chromium renderer. Each application needs its reached text owner. The installed Bitwarden 2026.5.0 uses Electron 39.8.5 and Chromium 142.0.7444.265. Its Fontations owner has the hooks needed for a separate port. Keep its disabled RunAsNode fuse, native modules, process-isolation preload and original wrapper. Teams success does not establish Bitwarden support.

Telegram includes its own static Qt controls. The installed Edge binary has no established hook for this coverage pass. The [fontSettings API](https://developer.chrome.com/docs/extensions/reference/api/fontSettings) controls font families and sizes, not glyph-mask processing. Fontreal currently supplies no Edge activation command. See the [app scenarios](../app-scenarios.md) and [roadmap](../roadmap.md).
