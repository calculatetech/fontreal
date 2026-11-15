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

The final output line names `build.json`. This record identifies the prepared sources, cache locations, recipes, archives and extracted distributions. A cached build must match those inputs and file hashes. The C1 distributions are private baselines. Their `LICENSES.chromium.html` is an upstream sample page, so they are not redistributable binary bundles. The selected workflow below supplies complete notices.

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

## Selected engine fixture

The selected workflow keeps the stock and passive builds above. It adds separate normal and trace builds of the same exact engine. It uses the unchanged coverage processor in the Fontations path raster. These builds are for test fixtures. They do not activate rendering in an installed application.

```sh
python3 tools/build-electron-selected.py
python3 tests/chromium_selected_test.py --build-record C2_BUILD_JSON
```

Replace `C2_BUILD_JSON` with the final path printed by the selected builder. The test invokes that builder again and requires the same record.

The test also gives the real producer a private MIT notice copy with one added blank line through a read-only file view. This must change only the final notice envelope. Runtime, probe and all other payload bytes stay identical. A final unchanged invocation must reuse the original artifact. The tracked notice and rendering sources are not changed.

The builder first retains a probe linked with pristine Fontations and the stock Skia raster. It then builds the selected engines through private source views. Source, compiler, linker, build-input and distribution hashes stay in the record. Run one builder at a time.

The probe supplies independent paths, advances, bounds and raw A8 masks. Ordinary outlines use the interpreter with the smooth-normal target. Fonts marked hinting-reliant by the provider retain its required Mono target. For that input, the test first requires the pristine normal/A8 Skia API to match an independently requested interpreter/Mono result. The selected engine must then match that proven native input.

The test compares each selected mask with the existing numerical reference. It also checks repeated glyphs, repaint, a later glyph, stroke text, styles, variable coordinates and both palettes. Color faces and bitmap-only faces retain stock rendering. Default Chromium local lookup excludes the synthetic non-scalable bitmap-only face. Only that fixture uses a private Fontconfig scan rule to expose its unchanged bytes; it does not establish normal browser bitmap-only support. A grayscale font with embedded strikes uses its outlines. Test-only fonts, fontconfig, profiles and captures stay below the configured build and results roots. The variable-font checks use Ubuntu Sans Mono. If Cantarell is absent, the test downloads and extracts the pinned Ubuntu font package privately; it does not install it.

The final OS-window expectation uses provider-derived selected masks and the pinned Skia integer A8 composition. Native unhinted, non-axis-aligned and large path controls keep their stock pixels. Normal and trace windows must match it exactly. Native PNG files also match within their own color representation. The complete stock/passive fixture runs again after selected construction. Results go below `results/chromium-selected`; installed-application ownership and daily use remain separate requirements.

## Application startup prerequisite

Before assembling an application view, test its normal Flatpak startup:

```sh
/usr/bin/flatpak run --command=/usr/bin/true APP_ID
```

Replace `APP_ID` with an installed application ID. This starts no account-bearing application code. It still requires the normal sandbox and document portal. A running portal service does not prove that its document mount exists. If this command fails because a document-portal `by-app` directory is absent, restore the native session prerequisite before application qualification. Do not substitute a launch that disables the document portal. An already running application does not prove that a new launch works.
