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
python3 tests/system_build_test.py --originals build/system-packages/original
python3 tests/system_package_test.py build/system-packages --updates
```

The discovery check compares the complete system plan with independent OS, dpkg, and original-package records. The original-package argument also covers a running Fontreal predecessor.

The package check uses another disposable container for the selected release. It unpacks both corresponding source packages and installs the actual binaries through APT. Existing independent probes compare widget and OpenGL pixels, fractional placement, disabled output, mixed fonts, and target transitions. Raster checks include ordinary and cached static text, with TrueType before and after CFF/color draws. Test results stay in `package-checks/` beside the bundle.

The update checks offer retained official binary payloads with synthetic higher version metadata through a local test APT source. They exercise independent QtBase and Declarative replacement. They do not claim to observe a future official release.

Quick uses an optional capability exported by the loaded Gui library. When an official Gui replaces the patched backend, new Quick consumers fall back without a missing Fontreal symbol. These checks cover normal windows, sampled layers, and unexposed targets. They include immediate ELF symbol binding and enabled values inherited from an earlier session.

Do not install an untested bundle on the desktop. Package application, disabled session activation, complete-session tests, and official rollback belong to the [desktop pilot](plans/FR-011-system-builds.md). The [roadmap](roadmap.md) records that work. The isolated [Konsole preview](experiments/kde-preview.md) remains available for comparisons.
