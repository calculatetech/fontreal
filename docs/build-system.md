# Build for the running system

Fontreal builds local FreeType and Qt packages on demand. It reads the installed distro, architecture, binary packages, and source revisions. It builds matching FreeType, QtBase, and Qt Declarative packages in a disposable Docker container. The build does not install packages on the host.

The initial targets are Debian 13 amd64 with Qt 6.8.2 and Ubuntu 26.04 amd64 with Qt 6.10.2. FreeType requires `2.13.3+dfsg-1+deb13u1` on Debian or `2.14.2+dfsg-1ubuntu0.2` on Ubuntu. Qt distro revisions can change within the supported source versions. Exact sources and original binary packages must remain available in official repositories. Unsupported systems, mixed source revisions, and unavailable packages stop the build. Update the official system to a coherent supported version before making another plan.

Use Python 3.11 or later, `dpkg`, `dpkg-query`, `dpkg-deb`, and a working local Docker engine. Install FreeType, QtGui, and QtQuick through the distro first. Package build dependencies stay inside the container. Pixel checks also need a C++ compiler, `pkg-config`, matching Qt/FreeType development files, and Pillow. Install those validation prerequisites before capturing the plan. Architecture-independent Qt documentation stays unchanged. Coinstalled i386 FreeType uses the distro cross toolchain and receives the same local version. Foreign-architecture Qt and installed debug packages need a separate supported build strategy.

## Create and build a plan

Run these commands from the repository root as your normal user:

```sh
mkdir -p build
python3 tools/system-build.py plan > build/system.json
python3 tools/system-build.py build build/system.json --output build/system-packages --jobs 4
python3 tools/system-build.py verify build/system-packages
```

The output directory must not exist before `build`. Use a new directory for another build. Keep sufficient free disk space for the container, source archives, and both toolkit builds. The default uses four parallel jobs. Lower `--jobs` when memory is limited.

Compiler scratch files stay in the selected output directory under `tmp/`. Container package checks use `package-checks/tmp/`. Select an output directory on a disk with sufficient space. A `build` directory linked to another disk also works. The container does not retain a second copy of its console log.

The plan records the running system. It selects exact source versions, not the newest upstream Qt. The same command selects the Qt 6.8.2 patch port on Debian 13 and the Qt 6.10.2 port on Ubuntu 26.04. It does not use the private experiment's `LD_LIBRARY_PATH` deployment method.

The container downloads authenticated distro source packages and original binary packages. It appends the Fontreal patch to each distro patch queue. It uses `dpkg-buildpackage` and the native `debian/rules`. FreeType builds first, followed by QtBase and Declarative. Matching development packages enter only the container between builds.

The build preserves distro hardening. It sets `nocheck` because desktop rendering checks run separately. It omits debug packages and compiler debug information to reduce local storage. These options appear in the build record and corresponding source. A successful compile alone does not establish desktop readiness.

## Keep the bundle together

`packages/` contains rebuilt native packages, including required FreeType architectures. `original/` contains the exact official packages selected for rollback. `source/` contains all three modified source packages, original archives, native patch queues and recipes, copyright notices, and build records.

`system.json` records original and installed package identities, source versions, local versions, and patch hashes. `build.json` records dependencies and build inputs. `bundle.json` lists artifact hashes. Verification checks every package family and each source descriptor's archives. It checks a retained bundle against its own records. A later checkout change does not invalidate cached original packages. A new build still requires a plan with the current patches.

Older Qt-only bundles keep their recorded source families for verification, predecessor discovery, and rollback. Their rollback preserves unowned FreeType packages. Build a new complete bundle to install the CFF-capable profile. Installation, new plans, and new activation packages require all three families.

The local version appends `afontreal` and a numeric build identity. Debian's version comparator checks that it sorts above its official base and below normal update forms. Fontreal adds no package holds or APT priorities. An official Qt update can replace the local build. A new upstream Qt version needs a matching patch port before another Fontreal build.

## Test the installed packages

Run the package checks before desktop installation:

```sh
python3 tools/system-build.py prepare build/system-packages
python3 tests/system_build_test.py --originals build/system-packages/original
python3 tests/system_install_test.py
python3 - <<'PY'
import os, subprocess, sys
sys.path.insert(0, "tests")
import browser_live_recipe_test as checks
record, _, nearest = checks.prepare()
env = dict(os.environ,
    FONTREAL_TEST_REFERENCE_FREETYPE=str(nearest.resolve()),
    FONTREAL_TEST_STOCK_FREETYPE=record["libraries"]["stock"]["library"])
subprocess.run([sys.executable, "tests/system_package_test.py",
    "build/system-packages", "--updates"], env=env, check=True)
PY
```

The discovery check compares the complete system plan with independent OS, dpkg, and original-package records. The original-package argument also covers a running Fontreal predecessor.

The activation metadata check uses the original Qt-only producer from Git commit `6ae8559d14f2448cd24f320f8d4c480669c80e0c`. Keep that history available. Its optional `--retained-native PATH` mode checks an explicitly labelled representative Qt-only bundle with actual payloads in a marked disposable VM. It checks predecessor discovery and actual rollback while preserving unowned FreeType. This mode does not certify historical rendering.

Reference preparation builds separate stock and nearest-only FreeType libraries from the matching provider. The nearest reference changes only the Latin Y rounding threshold. It retains native CJK fitting. These references supply expected masks without selecting the candidate's native property.

The package check uses another disposable container for the selected release. It unpacks every corresponding source package and installs the actual binaries through APT. Independent probes compare widget and OpenGL pixels, placement, disabled output, mixed fonts, and target transitions. Raw checks include CFF, current CFF2 weights, and actual CID/CJK glyphs. Ordinary and cached static text include repeated TrueType and CFF runs around color draws. Test results stay in `package-checks/` beside the bundle.

Update checks offer retained official payloads with synthetic higher version metadata through a local test APT source. They exercise independent FreeType, QtBase, and Declarative replacement. They do not claim to observe a future official release.

Quick uses optional capabilities from the loaded Gui and FreeType libraries. The normal profile requires the CFF-capable, per-library `fontreal-nearest-y-v2` property. Stock and older TrueType-only providers cannot satisfy it. New consumers fall back when FreeType or Gui loses that capability. An official Quick update can leave patched Gui treatment on native text until the next login. Checks cover actual widget and Quick output, normal windows, sampled layers, unexposed targets, immediate symbol binding, and inherited enabled values.

`prepare` builds the small activation package. It does not rebuild native libraries or change `bundle.json`. Its separate `deployment.json` binds the activation package, scripts, notice, and recipe to the native bundle. Keep both manifests and all recorded artifacts together. Package tests must run after preparation. Installation requires all three independent update cases and results for these exact manifests.

## Check a complete Plasma session

The VM must provide `spectacle` (`kde-spectacle`), `konsole`, `kscreen-doctor`, `qdbus6`, `plasma-apply-colorscheme`, and `powerdevil`. Install `fonts-noto-core`, `fonts-noto-color-emoji`, `fonts-urw-base35`, and `fonts-dejavu-core` before the test snapshot.

Use a disposable Plasma Wayland VM for the bundle's release. Copy the checkout and complete bundle into that VM. Install the exact FreeType and Qt package snapshot recorded in `system.json`. Keep the user's Inconsolata Nerd Font file available in the VM. Copy the independent nearest library and `build/browser-live-recipe/reference.json` too. Preserve the library bytes when copying its symbolic link. Compile `qt-kde-probe` and `qt-native-probe` with the target SDK in the checkout's `build` directory. Restore the captured snapshot after build dependencies are no longer needed. The session runner rejects a different package set before changing packages.

After you confirm that the VM is disposable, create the test marker and run the checks as its normal desktop user:

```sh
sudo touch /var/lib/fontreal-test-ready
export FONTREAL_TEST_REFERENCE_FREETYPE="$PWD/build/browser-live-recipe/nearest/.libs/libfreetype.so.6"
python3 tests/system_session_test.py build/system-packages
```

The runner restarts SDDM and changes packages inside that VM. It needs working passwordless sudo there and a persistent SSH session for the controller. It checks fresh logins, normal and D-Bus/systemd application launches, actual desktop pixels, 100% and 125% scales, a live scale change, fonts, disabling, independent official updates, and console rollback. It then exercises the guarded production install and rollback commands. A failed final transaction removes its provisional success report.

The runner sets controlled fonts, colors, and a test widget inside the VM before the preservation snapshot. It compares the complete centered title text separately from transparent decoration corners.

If the captured system already contains Fontreal, add `--previous PATH_TO_PREVIOUS_BUNDLE`. Keep that predecessor's verified activation artifacts too. The runner restores the exact captured official and Fontreal package records before the guarded apply check. Restoring only the official baseline does not recreate that predecessor. Missing predecessor artifacts stop the test.

Copy `session-checks/` back with the unchanged bundle. Package and session results must bind both manifests. Keep virtual display captures separate from human judgments about readability. View captures at one image pixel per display pixel. The normal profile uses raw coverage and encoded blending. Session fixtures exercise CFF desktop text, CFF and TrueType terminal text, and retained TrueType controls. Earlier mild/linear diagnostics remain separate.

After the full-session check passes, test an existing browser activation across native installation and rollback in that same marked VM. Install the supported Firefox and Floorp packages and the [browser check prerequisites](experiments/browser-masks.md#repeat-the-checks). Use its disposable desktop account with no existing Fontreal browser activation. Start each browser normally once, then quit normally. Keep only the provider-generated `Install...` section names in its `profiles.ini`; set each section's `Default=unused` and `Locked=1`. Do not copy account data or install IDs from another machine. The check verifies the current installation through ordinary browser launches. It temporarily uses the VM account's native home and restores all six profile-index paths, including absent files.

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

Keep `FONTREAL_TEST_REFERENCE_FREETYPE` exported as above. This check uses test-owned profiles, a process-only grayscale Fontconfig configuration, guarded native installation, and actual rollback. It checks ordinary browser restarts, raw CFF Qt helper pixels after installation, untreated Qt fallback after rollback, account data, and original preferences. It preserves the separate Plasma fixture's conflicting rendering settings. Run this command only in the disposable VM.

## Apply, enable, and restore

On the original system, first simulate the exact transaction. Then apply it with sudo:

```sh
python3 tools/system-build.py install build/system-packages --simulate
sudo python3 tools/system-build.py install build/system-packages
fontreal-session enable
```

Log out and back in. Installation starts disabled when the user has no existing activation preference. Rebuilding preserves an existing preference. The session hook requires matching FreeType, Gui, and Quick runtime versions. It selects nearest Latin Y fitting, raw coverage, whole-pixel placement, and encoded blending. It overrides conflicting rendering preferences while preserving chosen fonts and sizes. It adds no loader override.

Run `fontreal-session status` from a terminal in the new session. The preference line describes the next login. The current-process line describes that terminal's inherited values. An official Qt update can leave the preference enabled while the next login uses stock rendering. Rebuild for the updated system when its exact sources remain supported.

To disable the treatment, run `fontreal-session disable` and log in again. This keeps the patched packages. To restore all captured official packages and remove the activation package, use the console commands:

```sh
python3 tools/system-build.py rollback build/system-packages --simulate
sudo python3 tools/system-build.py rollback build/system-packages
```

Log out and back in. Rollback uses the complete retained official package set. It permits the required downgrades and refuses removals beyond the activation package. It works without the current checkout's patch hashes or successful deployment reports. Original Qt libraries ignore Fontreal variables that the session manager retains. Keep the bundle for this recovery path.

The selected treatment applies to eligible scalable, non-color TrueType and CFF fonts through system Qt 6. It includes CFF2 variations and CID collections while preserving native rules for other scripts. Color fonts keep their normal rendering. Older diagnostics retain their earlier CFF behavior. Qt Quick support covers the tested OpenGL path and opaque targets. Other rendering APIs need separate support. Qt 5, GTK/GNOME, Wine, browsers with their own engines, and bundled Qt runtimes remain separate. See the [roadmap](roadmap.md). The isolated [Konsole preview](experiments/kde-preview.md) remains available for comparisons.
