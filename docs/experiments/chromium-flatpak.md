# Chromium and Flatpak engine checks

This workflow identifies the renderer before applying Fontreal to a new engine. It builds the exact Teams Electron engine twice, with and without passive tracing. Both builds draw an isolated test page with temporary data.

The engine checks do not activate an installed application. The Teams application workflow below requires separate qualification. Bitwarden, Telegram and Edge remain unqualified. Use the [Mozilla guide](browser-masks.md) for the selected Firefox and Floorp renderer.

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

## Teams application qualification

This workflow supports only the exact Teams package and engine listed above. It copies installed code and resources into private views without copying profiles. It retains the original application ID, wrapper, resources and fuse settings. The original deployment remains available through absolute `/usr/bin/flatpak`.

Run these checks in a KWin Wayland session at 100% scale. Install Node.js with built-in `fetch` and `WebSocket`, `busctl`, `qdbus6`, `journalctl`, `kreadconfig6`, GIO and Spectacle. The actual-dialog oracle requires a locally installed Arial Regular font that the Flatpak resolves as `ArialMT` beneath `/run/host/fonts`. The test refuses a substituted font. Installed fonts are local inputs, not redistributed assets.

The desktop session and user manager must search `$HOME/.local/bin` before `/usr/bin` for ordinary commands and portal autostart. Fontreal installs owned command hooks there. It does not change PATH. If that directory is new, a normal logout/login can be necessary for the session to load its ordinary per-user PATH. The lifecycle check must prove actual selected launches. A PATH listing alone does not establish success.

```sh
python3 -B tools/build-chromium-delivery.py --build-record C2_BUILD_JSON
python3 -B tests/chromium_delivery_test.py --target teams --case actual-app --build-record C2_BUILD_JSON
```

Use the exact selected record from the previous section. The test invokes the actual application assembler and checks its emitted record. It opens the packaged local Join Meeting dialog with temporary comparison data. It enters unsent local text and compares native compositor captures with independent selected-mask expectations. It also checks the original sandbox preferences and the real portal child view.

Only the known generic input crop is retained. The installed Spectacle actor captures the owned active dialog through KWin. Its configuration, history, cache and temporary image stay private below the build root. The effective configuration prevents clipboard copying. A wrong window identity refuses capture before starting the actor.

The source-stock and passive views are private controls with the C1 notice limitation above. The selected normal and trace views retain the complete C2 notices. Zypak retains its BSD license. No application deployment or ordinary launch hook is qualified until the complete application, working-data lifecycle and official-update checks pass.

Autostart uses one owned override for the existing native generated Teams unit. It runs `/usr/bin/gio launch` on the current portal desktop file. The native unit keeps its startup conditions, and GIO reads the current command. Fontreal does not rewrite that portal file or add a service, startup link or global PATH setting. Disable removes only the owned override and launch hooks. Run the working-data and update qualification below before daily activation.

The lifecycle check requires the original stock Teams application to be running, with its existing portal autostart enabled. Fully quit any selected instance first, then open the native deployment with the absolute command in the activation section. Preserve disabled autostart preferences. A disabled setup does not meet this specific live-autostart scenario.

Run the lifecycle check separately:

```sh
python3 -B tests/chromium_delivery_test.py --target teams --case lifecycle --build-record C2_BUILD_JSON
```

The lifecycle check normally quits and reopens Teams with its original data. It checks desktop and command launches, later content renderers, autostart regeneration, the native escape and reversal. It preserves the original autostart intent. The installed desktop has no desktop actions.

The lifecycle check closes its last observed window normally. Before the update check, restore the original stock instance through its existing native autostart unit:

```sh
systemctl --user daemon-reload
systemctl --user start app-com.github.IsmaelMartinez.teams_for_linux@autostart.service
```

Keep that original instance running while preparing the private update fixture. The update check observes and closes it normally before the private transition, then restores it at the end.

### Prepare the genuine update fixture

Prepare a private installation before `update-cycle`. This setup does not update the working installation. The installed system runtime must already satisfy the exact Teams metadata. Use the same selected engine record as above. Replace the value assigned to `C2_BUILD_JSON` with its printed path:

```sh
export C2_BUILD_JSON='build/chromium-flatpak/selected/BUILD_ID/build.json'
python3 -B - <<'PY'
import json
import os
from pathlib import Path
import subprocess

app = 'com.github.IsmaelMartinez.teams_for_linux'
selected = json.loads(Path(os.environ['C2_BUILD_JSON']).read_text())
stock = json.loads(Path(selected['spec']['c1_record']).read_text())
commit = stock['spec']['target_commit']
root = (Path('build/chromium-delivery') / 'update').resolve()
root.mkdir(parents=True, exist_ok=True)
private = {
    'FLATPAK_USER_DIR': str(root / 'installation'),
    'XDG_CONFIG_HOME': str(root / 'config'),
    'XDG_DATA_HOME': str(root / 'data'),
    'XDG_STATE_HOME': str(root / 'state'),
    'XDG_CACHE_HOME': str(root / 'cache'),
    'FLATPAK_SYSTEM_CACHE_DIR': str(root / 'system-cache'),
    'TMPDIR': str(root / 'tmp'),
}
for path in private.values():
    Path(path).mkdir(parents=True, exist_ok=True)
env = dict(os.environ, **private)
commands = [
    ['/usr/bin/flatpak', '--user', 'remote-add', '--if-not-exists',
     'flathub', 'https://dl.flathub.org/repo/flathub.flatpakrepo'],
]
present = subprocess.run(
    ['/usr/bin/flatpak', '--user', 'info', app], env=env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
if not present:
    commands.append(['/usr/bin/flatpak', '--user', 'install',
        '--noninteractive', '--assumeyes', '--no-related', '--no-deps',
        'flathub', app + '/x86_64/stable'])
commands.append(['/usr/bin/flatpak', '--user', 'update',
    '--noninteractive', '--assumeyes', '--no-related', '--commit=' + commit, app])
for command in commands:
    subprocess.run(command, env=env, check=True)
actual = subprocess.check_output(
    ['/usr/bin/flatpak', '--user', 'info', '--show-commit', app],
    env=env, text=True).strip()
assert actual == commit
(root / 'install-command.json').write_text(
    json.dumps({'commands': commands, 'environment': private}, indent=2) + '\n')
PY
python3 -B tests/chromium_delivery_test.py --target teams --case update-cycle --build-record "$C2_BUILD_JSON"
```

The remote must still supply the qualified old commit and a genuinely newer official deployment. Missing history or no newer deployment stops this scenario. Do not fabricate an update or substitute a modified build record. Repeat the preparation when rerunning this scenario because its completed private installation contains the newer deployment.

The update check uses a genuine private Flatpak installation and separate test data. A temporary environment override selects that installation for the same native unit. The application's original early E2E data support selects the private data directory. Before starting application code, the check proves the effective installation and data environment. It updates the official deployment and requires the old qualification to select current stock. It then disables the hooks, checks stock autostart, removes its temporary override and restores the original host stock service.

## Enable Teams for daily use

Run the three application checks above in order: `actual-app`, `lifecycle`, then `update-cycle`. Each must exit zero with `passed: true` in its `report.json` below `results/chromium-delivery`. These checks temporarily manage launch hooks. They finish with the original host application on stock rendering.

Use the application `build.json` printed by `tools/build-chromium-delivery.py` for activation. This is a different record from `C2_BUILD_JSON`, which identifies the selected engine. Replace `TEAMS_BUILD_JSON` below with that exact application record:

```sh
python3 -B tools/chromium_delivery.py enable teams --record TEAMS_BUILD_JSON
python3 -B tools/chromium_delivery.py status teams
```

Activation requires the adjacent successful `qualification.json` to identify this exact application record. Status must show `enabled: true` and `compatibility: null`. Status describes launch configuration, not the code in an already running window. Fully quit Teams through its normal menu, then reopen it from its ordinary desktop launcher.

The owned hooks cover the desktop entry, `teams-for-linux`, the application-ID command, ordinary supported `flatpak run` commands, and existing native autostart. Open a new terminal if a shell caches an older command. Keep the checkout and qualified artifacts at their original locations while enabled. Disable before moving, removing or switching branches in the activated checkout. No comparison profile, E2E data setting, inspector flag or debug listener is part of daily activation.

An application or runtime update invalidates the qualification and selects current native stock. Run status to see the reason. Rebuild and repeat all three application checks for a newly supported package before enabling again. The builder refuses package revisions without a matching source route. Do not edit a record or remove its version guard to accept an update.

For temporary native rendering, fully quit Teams and launch the unchanged deployment explicitly:

```sh
/usr/bin/flatpak run com.github.IsmaelMartinez.teams_for_linux
```

To remove activation, fully quit Teams normally and run:

```sh
python3 -B tools/chromium_delivery.py disable teams
python3 -B tools/chromium_delivery.py status teams
```

Status must show `enabled: false`. Reopen Teams normally for stock rendering. Disable retains accounts and application data. Modified or foreign hooks stop removal rather than overwriting a user's customization.
