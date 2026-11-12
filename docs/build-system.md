# Build for the running system

Fontreal builds local Qt packages on demand. It reads the installed distro, architecture, binary packages, and source revisions. It builds matching QtBase and Qt Declarative packages in a disposable Docker container. The build does not install packages on the host.

The initial targets are Debian 13 amd64 with Qt 6.8.2 and Ubuntu 26.04 amd64 with Qt 6.10.2. Distro revisions can change within those source versions. Both exact source packages and the original binary packages must remain available in the official repositories. Unsupported systems, mixed source revisions, and unavailable exact packages stop the build. Update the official system to a coherent supported version before making another plan.

Use Python 3.11 or later, `dpkg`, `dpkg-query`, `dpkg-deb`, and a working local Docker engine. Install QtGui and QtQuick through the distro first. Build dependencies stay inside the container. Architecture-independent Qt documentation stays unchanged. Foreign-architecture Qt and installed debug packages need a separate supported build strategy.

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

The container downloads authenticated distro source packages and original binary packages. It appends the Fontreal patch to each distro patch queue. It uses `dpkg-buildpackage` and the native `debian/rules`. QtBase builds first. Its development packages enter only the container before Declarative builds.

The build preserves distro hardening. It sets `nocheck` because desktop rendering checks run separately. It omits debug packages and compiler debug information to reduce local storage. These options appear in the build record and corresponding source. A successful compile alone does not establish desktop readiness.

## Keep the bundle together

`packages/` contains the rebuilt native binary packages. `original/` contains the exact official packages selected for rollback. `source/` contains both modified source packages, original archives, native patch queues and recipes, copyright notices, and build records.

`system.json` records the original and installed package identities, source versions, local versions, and patch hashes. `build.json` records dependencies and build inputs. `bundle.json` lists artifact hashes. Verification checks the complete package and source sets, including the second source module and archives named by each source descriptor. It checks a retained bundle against its own records. A later checkout change does not invalidate cached original packages. A new build still requires a plan with the current patches.

The local version appends `afontreal` and a numeric build identity. Debian's version comparator checks that it sorts above its official base and below normal update forms. Fontreal adds no package holds or APT priorities. An official Qt update can replace the local build. A new upstream Qt version needs a matching patch port before another Fontreal build.

## Test the installed packages

Run the package checks before desktop installation:

```sh
python3 tools/system-build.py prepare build/system-packages
python3 tests/system_build_test.py --originals build/system-packages/original
python3 tests/system_install_test.py
python3 tests/system_package_test.py build/system-packages --updates
```

The discovery check compares the complete system plan with independent OS, dpkg, and original-package records. The original-package argument also covers a running Fontreal predecessor.

The package check uses another disposable container for the selected release. It unpacks both corresponding source packages and installs the actual binaries through APT. Existing independent probes compare widget and OpenGL pixels, fractional placement, disabled output, mixed fonts, and target transitions. Raster checks include ordinary and cached static text, with TrueType before and after CFF/color draws. Test results stay in `package-checks/` beside the bundle.

The update checks offer retained official binary payloads with synthetic higher version metadata through a local test APT source. They exercise independent QtBase and Declarative replacement. They do not claim to observe a future official release.

Quick uses an optional capability exported by the loaded Gui library. When an official Gui replaces the patched backend, new Quick consumers fall back without a missing Fontreal symbol. These checks cover normal windows, sampled layers, and unexposed targets. They include immediate ELF symbol binding and enabled values inherited from an earlier session.

`prepare` builds the small activation package. It does not rebuild Qt or change `bundle.json` and the native packages. Its separate `deployment.json` binds the activation package, scripts, notice, and package recipe to the native bundle. Keep both manifests and all recorded artifacts together. The package tests must run after preparation. Installation requires both independent update cases and results for these exact manifests.

## Check a complete Plasma session

The VM must provide `spectacle` (`kde-spectacle`), `konsole`, `kscreen-doctor`, `qdbus6`, and `plasma-apply-colorscheme`. Install `fonts-noto-core`, `fonts-noto-color-emoji`, and `fonts-urw-base35` before the test snapshot.

Use a disposable Plasma Wayland VM for the bundle's release. Copy the checkout and complete bundle into that VM. Install the same native Qt package set and versions recorded in `system.json`. Keep the user's Inconsolata Nerd Font file available in the VM. Compile `qt-kde-probe` and `qt-native-probe` in the checkout's `build` directory with the target release's SDK. Restore the captured Qt package snapshot after build dependencies are no longer needed. The session runner rejects a different package set before it changes packages.

After you confirm that the VM is disposable, create the test marker and run the checks as its normal desktop user:

```sh
sudo touch /var/lib/fontreal-test-ready
python3 tests/system_session_test.py build/system-packages
```

The runner restarts SDDM and changes packages inside that VM. It needs working passwordless sudo there and a persistent SSH session for the controller. It checks fresh logins, normal and D-Bus/systemd application launches, actual desktop pixels, 100% and 125% scales, a live scale change, fonts, disabling, independent official updates, and console rollback. It then exercises the guarded production install and rollback commands. A failed final transaction removes its provisional success report.

The runner sets controlled fonts, colors, and a test widget inside the VM before the preservation snapshot. It compares the complete centered title text separately from transparent decoration corners.

If the captured system already contains Fontreal, add `--previous PATH_TO_PREVIOUS_BUNDLE`. Keep that predecessor's verified activation artifacts too. The runner restores the exact captured official and Fontreal package records before the guarded apply check. Restoring only the official baseline does not recreate that predecessor. Missing predecessor artifacts stop the test.

Copy `session-checks/` back with the unchanged bundle. Package and session results must bind both manifests. Keep the virtual display captures separate from human judgments about readability. View captures at one image pixel per display pixel. The accepted reference uses mild contrast and linear blending, with Noto Sans and Inconsolata Nerd Font at 15px.

## Apply, enable, and restore

On the original system, first simulate the exact transaction. Then apply it with sudo:

```sh
python3 tools/system-build.py install build/system-packages --simulate
sudo python3 tools/system-build.py install build/system-packages
fontreal-session enable
```

Log out and back in. Installation starts disabled when the user has no existing activation preference. Rebuilding preserves an existing preference. The session hook enables mild contrast and linear blending only when both installed runtime versions match the prepared package record. It changes no fonts and adds no loader override.

Run `fontreal-session status` from a terminal in the new session. The preference line describes the next login. The current-process line describes that terminal's inherited values. An official Qt update can leave the preference enabled while the next login uses stock rendering. Rebuild for the updated system when its exact sources remain supported.

To disable the treatment, run `fontreal-session disable` and log in again. This keeps the patched packages. To restore all captured official packages and remove the activation package, use the console commands:

```sh
python3 tools/system-build.py rollback build/system-packages --simulate
sudo python3 tools/system-build.py rollback build/system-packages
```

Log out and back in. Rollback uses the complete retained official package set. It permits the required downgrades and refuses removals beyond the activation package. It works without the current checkout's patch hashes or successful deployment reports. Original Qt libraries ignore Fontreal variables that the session manager retains. Keep the bundle for this recovery path.

The selected treatment applies to eligible TrueType fonts in applications that use the system Qt 6 libraries. CFF and color fonts keep their normal rendering. Qt Quick support covers the tested OpenGL path and opaque targets. Other rendering APIs need separate support. Qt 5, GTK/GNOME, Wine, browsers with their own text engines, and bundled Qt runtimes need separate support. See the [roadmap](roadmap.md). The isolated [Konsole preview](experiments/kde-preview.md) remains available for comparisons.
