# Build for the running system

## Fontreal V3 for Qt and Plasma

### Install the stock Qt helper

Get one package from the [Fontreal V3 release](https://github.com/calculatetech/fontreal/releases/tag/v3.0.0). Use the package for your x86-64 Plasma Wayland system.

| System | Install the downloaded file |
| --- | --- |
| Debian 13 or Ubuntu 26.04 | `sudo apt install ./fontreal_3.0.0_amd64.deb` |
| Fedora 43, 44 or 45 | `sudo dnf install ./fontreal-3.0.0-1.x86_64.rpm` |
| openSUSE Leap 16.0 or 16.1 | `sudo zypper install --allow-unsigned-rpm ./fontreal-3.0.0-1.x86_64.rpm` |
| Arch Linux | `sudo pacman -U ./fontreal-3.0.0-1-x86_64.pkg.tar.zst` |

For KDE Linux Testing, the release supplies a system extension for snapshot `202611210254`. Install the archive with `sudo tar --zstd --no-overwrite-dir -xf fontreal-3.0.0-kde-linux-x86_64.tar.zst -C /` and reboot. To remove it, remove `/var/lib/extensions/fontreal` and `/etc/xdg/plasma-workspace/env/fontreal.sh`, then reboot.

Sign out and back in to Plasma. Open **Fonts** in System Settings and select the layout for your display. **None** uses Fontreal grayscale. Fontreal treats eligible text from 8 to 32 screen pixels. [The README](../README.md#install-v3-with-stock-qt) describes when Qt or Breeze uses color.

The shared DEB and RPM use the loaded Qt libraries to select the right helper. Distro updates run as usual. When a library needs a different helper, Fontreal skips that library's integration. Other matching libraries can still use Fontreal. If an earlier bundle replaced your Qt libraries, use its [restore instructions](https://github.com/calculatetech/fontreal/blob/v2.0.0/docs/build-system.md) first.

To restore stock rendering, remove `fontreal` with `apt remove`, `dnf remove`, `zypper remove` or `pacman -R` as appropriate. Sign out and back in.

### Build for stock Qt

Install the matching Qt 6 private headers for Qt Base and Qt Declarative, the Qt shader baker, and the FreeType and Fontconfig development files. The build also uses Bash, a C and C++ compiler, Binutils, `pkg-config` and `xxd`. On Debian 13 and Ubuntu 26.04:

```sh
sudo apt install build-essential binutils pkg-config xxd libfontconfig-dev libfreetype-dev qt6-base-private-dev qt6-declarative-private-dev qt6-shader-baker
tools/build-qt-stock-helper.sh build/providers
tools/package-qt-stock-helper.sh deb build/packages build/providers/*
```

On Fedora or openSUSE, install `rpm-build` and use the `rpm` format. On Arch, use the `arch` format with `makepkg` and `fakeroot`. On KDE Linux Testing, use the `kde-linux` format with GNU Tar and Zstandard. To build one package for multiple Qt builds, compile each provider on its own distro and combine the provider directories in the packaging command. Run packaging on the oldest supported system for that format.

### Konsole pilot with distro libraries

The pilot uses the distro versions of Qt, FreeType, and KWin. Launch it from a Plasma Wayland session with one unrotated display at 100% scale. In **Fonts**, enable anti-aliasing and select RGB subpixel rendering. Select **Full** hinting and a regular face such as Hack Regular.

The pilot treats pure black on white and white on black in the terminal. It uses the coverage of a single static outline font in each draw. Menus, light faces, and other colors use stock rendering. A draw also uses stock rendering when its glyphs can touch pixels outside the expected solid background.

Install the Qt Widgets, FreeType, and Fontconfig development packages. Build and launch as your normal user.

```sh
cmake -S . -B build/konsole-rgb -DFONTREAL_KONSOLE_RGB=ON
cmake --build build/konsole-rgb --target fontreal-qt-rgb
tools/run-konsole-rgb build/konsole-rgb/libfontreal-qt-rgb.so
```

The launcher opens a separate Konsole process with your usual profiles. Restart the pilot after changing the subpixel mode. A normal launch uses the stock path. The pilot uses one Konsole paint call, so wider Qt Widgets and Qt Quick coverage still needs a release path.

### Patched Qt visual reference

This experimental recipe patches and compiles QtBase and Qt Declarative from source to reproduce the V3 visual reference. The bundle supplies replacements for the installed packages from these two modules. The current V3 deployment work targets stock Qt packages. The reference uses the installed FreeType through its public API. Its build targets are Debian 13 amd64 with Qt 6.8.2 and Ubuntu 26.04 amd64 with Qt 6.10.2. Use Python, the distro package tools, and Docker. Keep the bundle on a disk with space for the Qt builds and in a location APT can read.

Remove the stock `fontreal` package before simulating or installing this reference bundle. Run the build as your normal user.

```sh
mkdir -p build
python3 tools/system-build.py plan --qt-v3 > build/system-v3.json
python3 tools/system-build.py build build/system-v3.json --output build/system-packages-v3
python3 tools/system-build.py verify build/system-packages-v3
python3 tools/system-build.py prepare build/system-packages-v3
python3 tools/system-build.py install build/system-packages-v3 --simulate
```

Check the simulated list. It should contain matching Qt packages and the Fontreal session package. Apply the bundle when you are ready, then enable it as your normal user.

```sh
sudo python3 tools/system-build.py install build/system-packages-v3
fontreal-session enable
```

Sign out and back in to Plasma. Open **Fonts** in System Settings and select the subpixel mode for your display. **None** uses Fontreal grayscale. A stock KWin single-output setup was checked at 100% and 125%. Fontreal also provides grayscale rendering for eligible offscreen text and the Qt Quick OpenGL text path. KWin applies effects such as Zoom after Qt submits a window.

Use `fontreal-session disable` and sign in again to turn off the profile. To restore the original Qt packages, use the verified bundle with `sudo python3 tools/system-build.py rollback build/system-packages-v3`. If a Fontreal session package was already installed, keep its verified bundle and pass it with `--previous`. This applies to a V2 upgrade, a V3 rebuild, and a system where a distro update had already replaced Qt.

```sh
sudo python3 tools/system-build.py rollback build/system-packages-v3 --previous build/previous-fontreal-bundle
```

Keep both bundles for as long as you need that rollback. The `fontreal-session profile` command still records the V2 O or K3 preference.

An official Qt update can replace the local Qt packages. Build a new bundle when your installed Qt version has a supported patch. The session checks the Qt packages once when Plasma starts.

## Fontreal V2 packages and integrations

Fontreal builds local FreeType and Qt packages on demand. It reads the installed distro, architecture, binary packages, and source revisions. It builds matching FreeType, QtBase, and Qt Declarative packages in a disposable Docker container. The build does not install packages on the host.

Follow the [test policy](../CONTRIBUTING.md#when-to-run-tests). For routine deployment, build, verify and prepare the bundle, then continue to [Apply, enable, and restore](#apply-enable-and-restore). The package and VM checks below apply when Fontreal changes.

The initial targets are Debian 13 amd64 with Qt 6.8.2 and Ubuntu 26.04 amd64 with Qt 6.10.2. FreeType requires `2.13.3+dfsg-1+deb13u1` on Debian or `2.14.2+dfsg-1ubuntu0.2` on Ubuntu. Qt distro revisions can change within the supported source versions. Exact sources and original binary packages must remain available in official repositories. Unsupported systems, mixed source revisions, and unavailable packages stop the build. Update the official system to a coherent supported version before making another plan.

Use Python 3.11 or later, `dpkg`, `dpkg-query`, `dpkg-deb`, and a working local Docker engine. Install FreeType, QtGui, and QtQuick through the distro first. Package build dependencies stay inside the container. Development pixel checks also need a C++ compiler, `pkg-config`, matching Qt/FreeType development files, and Pillow. For development checks, install those prerequisites before capturing the plan. Architecture-independent Qt documentation stays unchanged. Coinstalled i386 FreeType uses the distro cross toolchain and receives the same local version. Foreign-architecture Qt and installed debug packages need a separate supported build strategy.

Choose bundle storage outside a private home directory. Native APT's `_apt` user must be able to traverse the resolved directories and read every package archive, including originals, activation and any retained predecessor. Keep private home permissions and APT's sandbox unchanged. A source-tree link to a suitable build-storage directory works; `build/system-packages` in the examples names that readable location or link. Check access again after copying a bundle to another machine.

## Create and build a plan

Run these commands from the repository root as your normal user:

```sh
mkdir -p build
python3 tools/system-build.py plan > build/system.json
python3 tools/system-build.py build build/system.json --output build/system-packages --jobs 4
python3 tools/system-build.py verify build/system-packages
python3 tools/system-build.py prepare build/system-packages
```

The output directory must not exist before `build`. Use a new directory for another build. Keep sufficient free disk space for the container, source archives, and both toolkit builds. The default uses four parallel jobs. Lower `--jobs` when memory is limited.

Compiler scratch files stay in the selected output directory under `tmp/`. Container package checks use `package-checks/tmp/`. Select an output directory on a disk with sufficient space. A `build` directory linked to another disk also works. The container does not retain a second copy of its console log.

The plan records the running system. It selects exact source versions, not the newest upstream Qt. The same command selects the Qt 6.8.2 patch port on Debian 13 and the Qt 6.10.2 port on Ubuntu 26.04. It does not use the private experiment's `LD_LIBRARY_PATH` deployment method.

The container downloads authenticated distro source packages and original binary packages. It appends the Fontreal patch to each distro patch queue. It uses `dpkg-buildpackage` and the native `debian/rules`. FreeType builds first, followed by QtBase and Declarative. Matching development packages enter only the container between builds.

The build preserves distro hardening. FreeType compiles both C++17 processors with the configured target compiler. Each declared i386 counterpart contains both objects. Its shared library, static library and demos retain the standard C++ runtime and math dependencies. The exact public export list hides private C++ symbols. The build records `noudeb` because installer packages are outside this desktop target. It sets `nocheck` because desktop rendering checks run separately. It omits debug packages and compiler debug information to reduce local storage. These options appear in the build record and corresponding source. A successful compile alone does not establish desktop readiness. Output ownership follows the mounted directory, so a rootless Docker build remains writable by its host user.

## Keep the bundle together

`packages/` contains rebuilt native packages, including required FreeType architectures. `original/` contains the exact official packages selected for rollback. `source/` contains all three modified source packages, original archives, native patch queues and recipes, copyright notices, and build records.

`system.json` records original and installed package identities, source versions, local versions, and patch hashes. The `native-normal-o-k3-v2` identity also records both processor and header pairs, the render patch, and the MIT license. `build.json` records dependencies and build inputs. `bundle.json` lists artifact hashes. Verification checks every package family and each source descriptor's archives. It checks a retained bundle against its own records. A later checkout change does not invalidate cached original packages. A new build still requires a plan with the current patches and all six selected-input hashes. Verification keeps literal V1 records in their original four-hash shape.

Older Qt-only bundles keep their recorded source families for verification, predecessor discovery, and rollback. Their rollback preserves unowned FreeType packages. Retained complete bundles with the older raw profile also keep verification, predecessor and rollback support. Retained selected V1 bundles keep preparation and installation support. Build a current bundle for V2 capability. Installation, new plans, and new activation packages require all three families.

The local version appends `afontreal` and a numeric build identity. Debian's version comparator checks that it sorts above its official base and below normal update forms. Fontreal adds no package holds or APT priorities. An official Qt update can replace the local build. A new upstream Qt version needs a matching patch port before another Fontreal build.

## Test the installed packages

For changes to Fontreal, run the package checks below. Routine builds and installations do not require these checks or their reports:

```sh
python3 tests/system_build_test.py --originals build/system-packages/original
python3 tests/system_install_test.py
python3 - <<'PY'
import os, subprocess, sys
sys.path.insert(0, "tests")
import browser_live_recipe_test as checks
checks.BUILD = checks.ROOT / "build/system-reference"
checks.OUT = checks.ROOT / "results/system-reference"
checks.masks.WORK = checks.BUILD / "mask-probe-build"
checks.masks.OUT = checks.OUT / "mask-probe"
record, _, nearest = checks.prepare()
env = dict(os.environ,
    FONTREAL_TEST_REFERENCE_RECORD=str((checks.BUILD / "reference.json").resolve()),
    FONTREAL_TEST_REFERENCE_FREETYPE=str(nearest.resolve()),
    FONTREAL_TEST_STOCK_FREETYPE=record["libraries"]["stock"]["library"])
subprocess.run([sys.executable, "tests/system_package_test.py",
    "build/system-packages", "--updates"], env=env, check=True)
PY
```

The discovery check compares the complete system plan with independent OS, dpkg, and original-package records. The original-package argument also covers a running Fontreal predecessor.

The activation metadata check uses the original Qt-only producer from Git commit `6ae8559d14f2448cd24f320f8d4c480669c80e0c`. Keep that history available. Its optional `--retained-native PATH` mode checks a retained Qt-only bundle with actual payloads in a marked disposable VM. Keep representative fixtures labelled as representative. The check verifies predecessor discovery and actual rollback while preserving unowned FreeType. This mode does not certify historical rendering.

During configuration, the activation package sets its root-owned source-record directory to mode 755. This also secures the directory after an upgrade from older packages. It preserves an administrator's `dpkg-statoverride` entry and refuses an unexpected owner or symbolic link. The browser provider check keeps its existing trust requirements.

The complete font matrix needs the 28 faces declared by `tests/raw_coverage_test.py`: Noto Sans/Serif, Hack, Lato, Arial and the CFF controls. Install the required licensed fonts before running it. To keep test-only fonts outside the system, set `FONTREAL_TEST_FONT_ROOT` to a directory with the same relative structure as `/usr/share/fonts`. The checker records every font hash and binds that directory read-only inside the container. Font files are not distributed by this repository.

Run reference preparation on the matching distro and FreeType provider. Do not use Ubuntu references to qualify Debian packages. Reference preparation builds separate stock and nearest-only FreeType libraries from that provider. The nearest reference changes only the Latin Y rounding threshold. It retains native CJK fitting. These references supply expected masks without selecting the candidate's native property. V1 checks use pristine native-normal rasters with Qt's CFF stem-darkening and TrueType interpreter settings. V2 checks use native NORMAL hints, interpreter 40, and CFF darkening off. They rasterize each current hinted outline at four-times coordinates through the independent stock provider. Separate Python helpers apply the frozen V1 or O/K3 arithmetic. The checks include a raw CFF case that distinguishes those settings from fresh FreeType defaults. They inspect every source family and FreeType notice, shared exports for each architecture, unconditional amd64 static linkage, and real i386 callers. Static callers use the packaged dependency metadata and cannot borrow a shared FreeType implementation.

The package check uses another disposable container for the selected release. It unpacks every corresponding source package and installs the actual binaries through APT. Independent probes compare widget and OpenGL pixels, placement, disabled output, mixed fonts, and target transitions. Raw checks include CFF, current CFF2 weights, and actual CID/CJK glyphs. Ordinary and cached static text include repeated TrueType and CFF runs around color draws. Test results stay in `package-checks/` beside the bundle.

Update checks offer retained official payloads with synthetic higher version metadata through a local test APT source. They exercise independent FreeType, QtBase, and Declarative replacement. They do not claim to observe a future official release.

Quick uses optional capabilities from the loaded Gui and FreeType libraries. The selected profile requires the default-off, typed, per-library `fontreal-selected-v1` property. Stock, nearest-only and older TrueType-only providers cannot satisfy it. The `fontreal-nearest-y-v2` property remains available for explicit older diagnostics. New consumers fall back when FreeType or Gui loses that capability. An official Quick update can leave patched Gui treatment on native text until the next login. Checks cover actual widget and Quick output, normal windows, sampled layers, unexposed targets, immediate symbol binding, and inherited enabled values.

`prepare` builds the small activation package. It does not rebuild native libraries or change `bundle.json`. Its separate `deployment.json` binds the activation package, scripts, notice, and recipe to the native bundle. Keep both manifests and all recorded artifacts together. During Fontreal development, run package tests after preparation so their evidence identifies the exact manifests. Installation checks artifact integrity and package compatibility without requiring test reports.

## Check a complete Plasma session

This is a development check under the test policy. It is not a routine build or installation step.

The VM must provide `spectacle` (`kde-spectacle`), `konsole`, `kscreen-doctor`, `qdbus6`, `plasma-apply-colorscheme`, and `powerdevil`. Install `fonts-noto-core`, `fonts-noto-color-emoji`, `fonts-urw-base35`, and `fonts-dejavu-core` before the test snapshot.

Use a disposable Plasma Wayland VM for the bundle's release. Copy the checkout and complete bundle into that VM. Keep the new and retained predecessor bundles in APT-readable storage outside its private home directory, using source-tree links if useful. Run the package-access check below on all those bundles. Install the exact FreeType and Qt package snapshot recorded in `system.json`. Keep the user's Inconsolata Nerd Font file available in the VM. Install the [browser check prerequisites](experiments/browser-masks.md#repeat-the-checks), then prepare the independent references in that VM:

```sh
python3 - <<'PY'
import shutil
import sys
sys.path.insert(0, "tests")
from browser_live_recipe_test import BUILD, prepare
record, _, _ = prepare()
stock = BUILD / "stock/libfreetype.so.6"
stock.parent.mkdir(exist_ok=True)
shutil.copyfile(record["libraries"]["stock"]["library"], stock)
PY
```

Use a fresh reference directory or its complete existing cache. A copied `reference.json` alone is not a prepared cache: its nearest library and exact build inputs must also match. The command keeps the pristine library bytes and their matching record available for both the session and browser checks.

Compile `qt-kde-probe` and `qt-native-probe` with the target SDK in the checkout's `build` directory. Restore the captured snapshot after build dependencies are no longer needed. The session runner rejects a different package set before changing packages.

After you confirm that the VM is disposable, create the test marker and run the checks as its normal desktop user:

```sh
sudo touch /var/lib/fontreal-test-ready
export FONTREAL_TEST_REFERENCE_FREETYPE="$PWD/build/browser-live-recipe/stock/libfreetype.so.6"
python3 tests/system_session_test.py build/system-packages
```

The runner restarts SDDM and changes packages inside that VM. It needs working passwordless sudo there and a persistent SSH session for the controller. Before each single controlled restart, it allows up to 150 seconds for the complete native user-manager job collection to finish and records the outcomes. It then requires new KWin and Plasma processes with the same user manager. It checks fresh logins, normal and D-Bus/systemd application launches, actual desktop pixels, 100% and 125% scales, a live scale change, fonts, disabling, independent official updates, and console rollback. It then exercises the guarded production install and rollback commands. A failed final transaction removes its provisional success report.

The runner sets controlled fonts, colors, and a test widget inside the VM before the preservation snapshot. It compares the complete centered title text separately from transparent decoration corners.

If the captured system already contains Fontreal, add `--previous PATH_TO_PREVIOUS_BUNDLE`. Keep that predecessor's verified activation artifacts too. The runner restores the exact captured official and Fontreal package records before the guarded apply check. Restoring only the official baseline does not recreate that predecessor. Missing predecessor artifacts stop the test.

Copy `session-checks/` back with the unchanged bundle. Package and session results must bind both manifests. Keep virtual display captures separate from human judgments about readability. View captures at one image pixel per display pixel. The normal profile uses native-normal hinting, the selected coverage correction, whole-pixel placement and encoded blending. Session fixtures exercise CFF desktop text, CFF and TrueType terminal text, and retained TrueType controls. Earlier mild/linear diagnostics remain separate.

After the full-session check passes, test an existing browser activation across native installation and rollback in that same marked VM. Install the supported Firefox and Floorp packages and the [browser check prerequisites](experiments/browser-masks.md#repeat-the-checks). Use its disposable desktop account with no existing Fontreal browser activation. Start each browser normally once, then quit normally. Leave its generated profiles and indexes untouched. Do not copy account data or install IDs from another machine.

The check snapshots those original files before fixture preparation. It uses only provider-observed existing profile roots and actual installation IDs for the native proof. It verifies ordinary browser launches, preserves unrelated profile trees, and restores all eight current and legacy `profiles.ini` and `installs.ini` paths, including absent files. Current roots follow `XDG_CONFIG_HOME`; the default is the user's `.config` directory. Synthetic all-root and historical-default cases remain separate from this native authority check.

Account file bytes stay unchanged. The check permits a new empty `.parentlock` synchronization file only when it is regular, is not a link, and is unlocked. Existing file changes and other new files fail.

Extract the matching native runtime for the initial Qt helper, then run the continuation:

```sh
mkdir -p build/native-test-runtime
for package in build/system-packages/packages/*_amd64.deb; do
    dpkg-deb --extract "$package" build/native-test-runtime
done
LD_LIBRARY_PATH="$PWD/build/native-test-runtime/usr/lib/x86_64-linux-gnu" \
QT_PLUGIN_PATH="$PWD/build/native-test-runtime/usr/lib/x86_64-linux-gnu/qt6/plugins" \
QT_FONT_DPI=96 \
python3 tests/browser_delivery_test.py --case lifecycle --native-helper \
    --native-bundle build/system-packages
```

Keep `FONTREAL_TEST_REFERENCE_FREETYPE` exported as above. This check uses test-owned profiles, a process-only grayscale Fontconfig configuration, guarded native installation, and actual rollback. It checks ordinary browser restarts, selected CFF Qt helper pixels after installation, untreated Qt fallback after rollback, account data, and original preferences. It preserves the separate Plasma fixture's conflicting rendering settings. Run this command only in the disposable VM.

If the full-session check required `--previous PATH_TO_PREVIOUS_BUNDLE`, add the same argument and exact bundle to this browser command. The check validates that predecessor before browser/index changes. Before each guarded install, with the browser normally closed, it restores the verified captured package set and original activation package. Every rollback still ends at the complete official package set. A missing or mismatched predecessor is an error; the check does not substitute an official-only baseline for it.

## Choose O or K3

A current bundle contains O and K3. This capability does not activate either profile. The existing typed Boolean property and scoped environment request remain the activation authorities.

Set the shared preference from the checkout:

```sh
sh packaging/session/fontreal-session profile
sh packaging/session/fontreal-session profile k3
sh packaging/session/fontreal-session profile o
```

The getter prints the choice. Missing configuration selects O NORMAL, the general V2 choice. K3 NORMAL is the alternative. The installed command is `fontreal-session profile k3` or `fontreal-session profile o`.

The plain file is `fontreal/profile` below `XDG_CONFIG_HOME`, or `$HOME/.config` when that variable is unset. The command accepts only exact `o` and `k3`. Unsupported values and extra arguments leave state unchanged. A malformed external file uses the O default.

One choice supplies enabled native Qt/KDE, Firefox, Floorp, Teams and Bitwarden launches. Fully quit and reopen applications after a change. Native desktop applications receive the choice at the next login. Fresh browser and selected Flatpak launches use the file instead of a stale inherited `FONTREAL_PROFILE`.

The choice does not enable an integration or upgrade a saved library or engine. Keep the existing activation and exact-runtime requirements. Complete selected-V1 bundles retain their recorded compatibility. They do not become V2 through this file. Raw and Qt-only bundles remain ineligible for new activation.

Direct library users can still set exact `FONTREAL_PROFILE=o` or `FONTREAL_PROFILE=k3` before startup. An absent or unsupported direct value retains V1 behind independent activation. Do not change the build plan or rebuild an engine to switch profiles.

## Apply, enable, and restore

Check native APT access to the complete prepared bundle. If using a retained predecessor, add its path to the first command's arguments too:

```sh
python3 - build/system-packages <<'PY'
from pathlib import Path
import subprocess
import sys
for argument in sys.argv[1:]:
    bundle = Path(argument).resolve()
    for role in ("packages", "original", "activation"):
        for package in (bundle / role).glob("*.deb"):
            subprocess.run(["sudo", "-u", "_apt", "test", "-r",
                            str(package.resolve())], check=True)
PY
```

On the original system, first simulate the exact transaction. Then apply it with sudo:

```sh
python3 tools/system-build.py install build/system-packages --simulate
sudo python3 tools/system-build.py install build/system-packages
fontreal-session enable
```

Log out and back in. Installation starts disabled when the user has no existing activation preference. Rebuilding preserves an existing preference. The session hook requires matching FreeType, Gui, and Quick runtime versions. It selects native-normal hinting, the selected weighted-stem coverage correction, whole-pixel placement, and encoded blending. It overrides conflicting rendering preferences while preserving chosen fonts and sizes. It adds no loader override.

Run `fontreal-session status` from a terminal in the new session. The preference and profile lines describe the next login. The current-process line includes that terminal's inherited profile and activation values. Neither line proves that a V2 renderer loaded. An official Qt update can leave the preference enabled while the next login uses stock rendering. Rebuild for the updated system when its exact sources remain supported.

After rollback removes the activation hook, Plasma can restore environment values from an earlier login. Check the loaded official libraries and stock output to confirm rollback. Retained environment values alone cannot show that Fontreal rendering is active.

To disable the treatment, run `fontreal-session disable` and log in again. This keeps the patched packages. To restore all captured official packages and remove the activation package, use the console commands:

```sh
python3 tools/system-build.py rollback build/system-packages --simulate
sudo python3 tools/system-build.py rollback build/system-packages
```

Log out and back in. Rollback uses the complete retained official package set. It permits the required downgrades and refuses removals beyond the activation package. It works without the current checkout's patch hashes or successful deployment reports. Original Qt libraries ignore Fontreal variables that the session manager retains. Keep the bundle for this recovery path.

The selected treatment applies to eligible scalable, non-color TrueType and CFF fonts through system Qt 6. It includes CFF2 variations and CID collections while preserving native rules for other scripts. Color fonts keep their normal rendering. Older diagnostics retain their earlier CFF behavior. Qt Quick support covers the tested OpenGL path and opaque targets. Other rendering APIs need separate support. Qt 5, GTK/GNOME, Wine, browsers with their own engines, and bundled Qt runtimes remain separate. See the [roadmap](roadmap.md). The isolated [Konsole preview](experiments/kde-preview.md) remains available for comparisons.
