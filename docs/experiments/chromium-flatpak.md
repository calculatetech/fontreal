# Chromium and Flatpak engine checks

This workflow identifies the renderer before applying Fontreal to a new engine. It builds the exact Teams Electron engine twice, with and without passive tracing. Both builds draw an isolated test page with temporary data.

The workflow does not activate Fontreal in Teams, Bitwarden, Telegram, Edge or other Chromium browsers. Keep their normal launchers and accounts in place. Use the [Mozilla guide](browser-masks.md) for the selected Firefox and Floorp renderer.

## Inspect and build

Run these commands from the repository root. Put `build` and `results` on your build volume before starting. Downloads, toolchains, caches, temporary profiles and captures use those resolved directories.

```sh
python3 tools/chromium_flatpak.py owners
python3 tools/build-electron.py
```

The inventory reads installed package metadata, wrappers, binaries and source records without starting applications. It keeps a separate record for each target. An unknown renderer remains unknown until a trace proves which code draws text.

The builder requires the recorded amd64 Teams 2.28.0 package with Electron 44.9.0 and Chromium 152.0.7977.167. It refuses another package identity. Follow the upstream [Electron build requirements](https://www.electronjs.org/docs/latest/development/build-instructions-gn) and install `bubblewrap` and `patch`.

This is a full Chromium build and needs substantial disk space and build time. Run one builder at a time. The builder retains the stock distribution, then compiles tracing through private source views without changing the upstream checkout.

The final output line names `build.json`. This record identifies the prepared sources, cache locations, recipes, archives and extracted distributions. A cached build must match those inputs and file hashes.

## Compare actual pixels

The display test needs KWin Wayland, Xvfb and Python 3 with Pillow. Install the Noto Sans, Hack and Nimbus Sans regular fonts.

The screenshot helper needs Qt 6.8+ Widgets, Quick, QuickControls2, DBus and private Gui development files. It also needs FreeType development files.

```sh
cmake -S . -B build -G Ninja -DBUILD_TESTING=ON
cmake --build build --target qt-kde-probe
python3 tests/chromium_flatpak_test.py --target teams --case stock-fixture
```

The test invokes the builder and checks its returned artifact. To require a specific artifact, add `--build-record` with the final path printed by the builder. The test uses a separate nested display and temporary data. It does not open the account-bearing Teams application.

The test compares three fonts at 15px on light and dark backgrounds. It checks the renderer sandbox, exact font bytes, real glyph traces and final window pixels. The entire stock and traced screen crops must match exactly, including the non-text controls.

Native PNG captures also compare exactly within their own representation. Their color encoding can differ from the OS screenshot, so the test does not compare RGB values across those stages. No pixel adjustment or tolerance is applied.

The trace records the raster format. Raw coverage bytes are available only for small A8 grayscale masks. An empty mask field for another format does not establish grayscale coverage or selected processing.

Results go below `results/chromium-flatpak`. A successful fixture proves the isolated engine path only. The [implementation specification](../plans/FR-016-chromium-flatpak.md) defines the separate selected-renderer and application-delivery requirements.
