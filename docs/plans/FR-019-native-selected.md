# Carry the selected profile into native KDE packages

## Outcome and owners


An enabled ordinary Plasma login uses the accepted native-normal and weighted-stem profile in native Qt widgets, Qt Quick, KWin and Konsole. Chosen fonts, styles and point sizes stay intact. Actual packaged raster output and application pixels must match an independent matching-provider reference. Installation, updates, disabling and offline rollback retain their existing guards.

Base: `main` at `e8303f596998d6231b2d5bbd8c8b273d541c9b01`. Use the isolated `feature/native-selected` worktree. Keep the Chromium delivery checkout intact because active application hooks use it. Generated indexes, builds, downloads, container state, compiler scratch and results belong on the storage volume. Public documents use portable relative paths.

The existing owners are `tools/system-build.py`, `tools/system_install.py`, the FreeType and Qt patches, the capability patches in `packaging/`, and `packaging/session/`. Browser provider resolution and child-helper containment remain owned by the existing browser tools. Reuse their checks. The numerical core in `src/fontreal_coverage.cpp` and `.h`, and the immutable Python references, are opaque and unchanged.

## Prior plan reconciliation and product boundary


Source: `e8303f5:docs/plans/FR-018-axis-study.md`, S37 and native clauses at lines 407–426 and 455–488. S37 replaces the earlier normal-preset nearest-Y/raw geometry and coverage with native-normal plus the final generic selected method. Retain the earlier explicit diagnostic selectors and their meanings. Retain package coherence, coinstalled architectures, independent official updates, browser-provider resolution, activation, full-session proof and rollback. The current user authorizes review, commit, merge, push and deployment. That authority supersedes the earlier no-publication ceiling without weakening technical checks.

The supported builds remain Debian 13 amd64/Qt 6.8.2/FreeType `2.13.3+dfsg-1+deb13u1` and Ubuntu 26.04 amd64/Qt 6.10.2/FreeType `2.14.2+dfsg-1ubuntu0.2`. Preserve installed matching amd64 development packages and coinstalled i386 FreeType. The current [build guide](../build-system.md) owns native operations. The [browser guide](../experiments/browser-masks.md) owns existing-profile activation and restoration.

Distro archives, native package management, login, browser account state and native composition are opaque external owners exercised through their actual interfaces. Do not replace them with mock output. No optical tuning, per-font or per-character rules, extra distro, toolkit, rendering API or installer-udeb support belongs here. Do not add a framework, loader override, global FreeType environment, host package hold or APT priority. Never restart host SDDM, force user logout, reuse unrelated VMs or bypass native authorization.

## Smallest implementation


Add a typed, default-off, per-FreeType-library property for the selected profile beside the unchanged `fontreal-nearest-y-v2` property. The selected property cannot be enabled through FreeType's string environment interface. Converge that property and the existing correctly scoped `FONTREAL_FT_CONTRAST=weighted` selector on one existing load/render processing path. If both select it, process once. Preserve the next-load, next-size and variation lifecycle.

The two supported Qt ports set and query the new property. They use native-normal grayscale hints with `NO_AUTOHINT|NO_BITMAP`, whole-pixel placement and encoded blending. Keep design metrics, outlines, unsupported fonts and explicit old diagnostics on their existing routes. Retain the Gui C ABI readiness functions and Quick's optional weak bridge. Readiness requires actual selected capability, globally and per font. Stock, nearest-only and older private providers fall back truthfully.

Use the unchanged selected sequence: connected 170 plus guarded bridge, gain with ceiling 226, B's strong winner, profile/join and native corner treatment, and weighted stems only. The core receives pixels and an allocation owner, never font identity. Preserve bounds, metrics, outlines, allocation checks and the C exception boundary.

Native FreeType packages use the distro Autoconf/make/libtool rules, not CMake. Add `AC_PROG_CXX` before `LT_INIT`, configured target CXX/CXXFLAGS, and a real C++17/PIC/hidden core object in `BASE_EXT_OBJ`. Use the CXX libtool link tag and retain distro LDFLAGS, exports, SONAME and features. Propagate `-lstdc++ -lm` after objects into shared/static/demo and private package-config dependencies. Compile a separate i386 object with the configured cross CXX. Keep native `CC_BUILD` for build tools. Record `DEB_BUILD_PROFILES=noudeb` in dependency and build contexts. Include the original MIT core notice in corresponding sources and binary notices. Do not link the private builder's manual object twice.

Build identity covers source, core/header, patch, compiler/link recipe and selected profile. Retained bundles validate their own capability metadata. An old FreeType capability of `None` must not acquire the new capability through current checkout defaults. Old complete/raw and Qt-only bundles retain verification, predecessor and rollback authority, but cannot obtain a new selected installation or regenerated selected activation.

Derive output ownership from the mounted output directory inside the container. Host numeric UID/GID cannot be reused blindly in a rootless user namespace. Preserve rootful behavior without changing namespace, Docker context or security policy.

Prepare activation separately from the immutable native bundle. Bind the activation scripts, package and recipe in the deployment manifest. Select only Qt session variables. Clear stale values before the complete three-runtime version gate. Preserve the user's preference across rebuilds and distinguish next-login intent from inherited current-process values.

On configuration, migrate an older package-owned source-record directory to mode 755 unless an administrator's native `dpkg-statoverride` entry applies. Preserve that entry and the root-owner and no-symbolic-link preconditions. Reject unexpected ownership or links. Do not change the shared parent directory or relax the browser's trusted-provider check. Exercise the genuine retained predecessor's mode 775 through the actual native upgrade, ordinary browser/helper continuation and rollback.

## Boundary inventory


Every boundary below is applicable. Its sources are the retained native clauses, S37, the current build guide and their named production owners. The numerical implementation and immutable references are opaque. Other applications and new rendering APIs are deferred. Host forced logout and unrelated VM use are excluded.

| ID | Required invariant | Scenario |
| --- | --- | --- |
| B1 | Exact generic selected method, no optical changes | S1–S2 |
| B2 | Explicit historical diagnostics retain their meanings | S3 |
| B3 | TT/CFF/CFF2/CID scalable noncolor raster eligibility; native Type 1/color/bitmap/nohint/nonraster/metrics/outline paths | S1, S4 |
| B4 | One processing pass per newly rendered outline; geometry and metrics intact; repeated render identity; next load/size/variation independent | S1 |
| B5 | Typed per-library selected capability defaults off; real old/stock fallback; Gui and Quick readiness reflect actual capability | S4–S5 |
| B6 | Selected Qt overrides conflicting hint/AA/subpixel preferences while preserving fonts, styles, sizes and layout | S2, S10 |
| B7 | Complete condition, occurrence and current/legacy profile-index sets; duplicates cannot hide later counterexamples | S1–S6, S14 |
| B8 | Quick ordinary/static/mixed/cache/repaint/placement and OpenGL normal/sampled/unexposed/return paths at 100/125% | S5 |
| B9 | Exact supported coherent plan, revisions and complete packages; unsupported/mixed/missing/duplicate/late mismatch rejected | S6 |
| B10 | Real coherent amd64/development and coinstalled i386 FreeType packages | S7 |
| B11 | Authenticated distro build rules, features and hardening; no host installation; storage and correct rootless ownership | S7 |
| B12 | Complete corresponding sources, notices, provenance, compiler/core/link inputs, exports and runtime/static dependencies | S7 |
| B13 | Retained bundles verify and roll back by their own metadata; Qt-only rollback preserves unowned FreeType; no new selected-install authority | S9 |
| B14 | Local versions above their base and below normal updates; no holds or priorities | S6–S8 |
| B15 | Independent FT/Gui/Quick updates have truthful immediate-consumer and next-login results | S8, S10 |
| B16 | Activation preparation is separately hashed and deployment-bound; native manifest unchanged | S11 |
| B17 | Snapshot, complete manifest-bound package/update/session proof and no-unrelated-removal guards precede real APT | S11 |
| B18 | Fresh installation disabled; existing preference preserved; stale login values cleared; current and next login distinguished | S10–S11 |
| B19 | Actual marked disposable Plasma session, normal/D-Bus/systemd launches and required scales; captured Fontreal predecessor restored before guarded apply | S10–S11 |
| B20 | Offline official rollback independent of current patches and success reports; remove only activation | S9, S11 |
| B21 | Existing Firefox/Floorp activation/data/restoration survive native install, normal restart, real Qt helper and rollback; configured XDG and legacy profile collection, trusted official-provider resolution | S12, S14 |

## Scenario Proof and runnable checks


Use these existing commands and extend their actual paths. `BUNDLE` below names the complete current native output for its exact release. Prepare independent matching-provider references before checks. Record actual commands, source identities and terminal results in one ignored task result, not this specification.

| ID | Discriminator and contrast | Production path and independent terminal oracle | Runnable check |
| --- | --- | --- | --- |
| S1 | Typed only, exactly scoped environment only, both, neither; a glyph with once != twice; deferred/immediate/character loads, rerender, next glyph, size-return and variable coordinates | Actual packaged public FT API. Typed/environment/both equal one unchanged `expected_mask` application; neither equals independent stock. Bounds/metrics/outlines intact. Complete declared keys and each occurrence. No direct-core substitute | `python3 tests/system_package_test.py BUNDLE --updates` |
| S2 | Ordinary and static TT/CFF text, requested 8–16pt, styles, colors, scales, opposing preferences and repeated occurrences | Actual packaged QRawFont/QPainter → independent native-normal masks → unchanged selected reference → encoded whole-pixel RGB. Check full expected keys and occurrences | Same package check; `python3 tests/kde_paths_test.py --only all` in the matching private runtime |
| S3 | Selected versus explicit raw/none/mild/ramp217/linear/nearest | Actual retained browser/Qt diagnostic routes → unchanged historical expectations | `python3 tests/selected_profile_test.py --case legacy`; `python3 tests/qt_raw_profile_test.py`; `python3 tests/freetype_nearest_property_test.py` |
| S4 | New selected capability versus actual nearest-only, stock and retained v1 providers; two independent FT libraries; design/outline/color and eligibility gates | Actual FT property and Qt/Quick consumers → selected or independently proven stock fallback. Enabling one library leaves the other off | Package check; `python3 tests/selected_profile_test.py --case gates`; native helper scope check |
| S5 | Ordinary/static mixed TT/CFF around color; initial/repaint/new glyph/cache/placement/layer/unexposed and scale return | Actual packaged Quick/OpenGL → independent masks and final pixels. Every occurrence and terminal target is checked | Package check; `python3 tests/kde_paths_test.py --only all` |
| S6 | Supported OS/dpkg/original/predecessor sets; missing/mixed/duplicate prefix then late mismatch | Actual plan/discovery/verification → exact independent complete records or rejection; native version ordering | `python3 tests/system_build_test.py --originals BUNDLE/original`; `python3 tests/system_install_test.py` |
| S7 | Both supported releases; native/development and actual i386 outputs; source/static/shared/demo and exports | Real authenticated distro source → actual native build and package installation. Independent source/archive/hash/export/dependency checks and compiled i386 core; host package state unchanged and host-owned rootless output | `python3 tools/system-build.py build PLAN --output BUNDLE --jobs 4`; `python3 tools/system-build.py verify BUNDLE`; package check for each release |
| S8 | Separate genuine retained official FT, Gui and Quick payloads offered with higher test metadata | Actual APT replacement → newly launched inherited consumers, then fresh login. FT/Gui capability loss falls back immediately. Official Quick can leave patched Gui treatment before login; complete next-login mismatch clears all selected settings | Package check `--updates`; full session check |
| S9 | Actual retained complete/raw and Qt-only bundles, current patch changes, unowned FT | Own-metadata verify/predecessor/actual rollback succeeds. New selected install and preparation are refused. Qt-only rollback preserves unowned FT | `python3 tests/system_install_test.py`; in the marked VM `python3 tests/system_install_test.py --retained-native OLD_BUNDLE` |
| S10 | Enabled/disabled/stale and independent updates; 100/125% plus live scale; ordinary/D-Bus/systemd launch | Complete native user-manager jobs reach terminal state before one controlled SDDM restart; require new KWin/Plasma PIDs and the same manager. Actual marked disposable session → normal widget/Quick/Plasma/KWin/Konsole pixels, loaded libraries, fonts/sizes and fresh-login environment. No host session restart | `python3 tests/system_session_test.py BUNDLE` with `--previous OLD_BUNDLE` when the captured snapshot contains Fontreal |
| S11 | Separate preparation, snapshot/proof mismatches, captured predecessor versus official-only baseline, offline recovery | New and predecessor bundles satisfy native `_apt` traversal/read access outside a private home, with unchanged private-home permissions and sandbox. Real prepare leaves native manifest intact. Restore actual captured Fontreal payloads, then production guarded APT install. Offline rollback ends with complete official identities and only activation removed. Failed final transaction cannot leave success | Build/install metadata checks and full session command |
| S12 | Existing test-owned activations → exact captured predecessor → native install → normal restart → actual Qt child with new selected or real older private provider → native rollback | Actual browser and helper masks/maps/pixels, trusted installed-provider identity, unchanged account data and first restoration snapshot. Validate the same actual retained predecessor before profile mutation; restore its complete captured payload set before each guarded install. Old provider gives stock helper fallback. End at official originals. No daily profile clone | In the same marked VM: `python3 tests/browser_delivery_test.py --case lifecycle --native-helper --native-bundle BUNDLE`, with `--previous OLD_BUNDLE` when full-session required it |
| S13 | Concrete reviewed host bundle; simulation versus native application; old inherited session versus normal fresh login | Exact guarded production install, enable, then ordinary user logout/login. Observe actual loaded libraries, selected environment and pixels. A configuration change alone cannot prove active rendering | `python3 tools/system-build.py install BUNDLE --simulate`; native-authorized install; `fontreal-session enable`; after ordinary login `fontreal-session status` and native probes |
| S14 | Floorp current/default and nondefault XDG roots versus legacy, inactive default-root decoy, missing target/prefs, equivalent duplicates and late cross-index conflict; owned A versus ordinary B | Real profile-index enumeration and enable preserve the existing unique resolved Install-default rule, Firefox-only exception and retarget refusal. Actual native first-launch files/absence are restored exactly across all eight current/legacy profile and install indexes | `python3 tests/browser_delivery_test.py --case discovery`; `--case process`; `--case lifecycle`; S12 on both marked VMs; `--case docs` and docs checks |

For S1/S2/S5/S10/S12, an independent pristine FreeType reference must mirror Qt's actual CFF `no-stem-darkening=false` and TrueType interpreter 40 before native-normal rendering. Choose a CFF glyph and size whose raw raster differs from fresh FreeType defaults. Assert this discriminator before applying unchanged `expected_mask`. Candidate-off output cannot serve as the independent reference. Preserve nearest and historical CFF expectations.

Do not replace complete collection checks with counts or a successful prefix. Mixed draw orders must include a later distinct glyph after repeated runs. Update and rollback tests keep one stateful sequence through the terminal application or fresh-session result.

## Current Floorp profile refinement

The supported Floorp App.Version remains `12.21.1@159.0.1`; its engine milestone is `159.0.1`. Native provider observations confirm it creates `floorp/profiles.ini` and `floorp/installs.ini` below the configured `XDG_CONFIG_HOME`, including a nondefault root. Add that current root beside the retained `.floorp` directory below the home directory in the existing enumerator. Preserve unique resolved Install-default collection, parent checks, the Firefox-only ambiguity exception, version gates and retarget rules.

Discovery checks must use the real enumerator. Cover modern-only default, configured nondefault root with an unchanged conflicting inactive default-root decoy, legacy-only, no target, missing prefs, relative/absolute equivalents and duplicate-prefix followed by a distinct later cross-index default. Exercise real enable and complete profile/prefs/index/hook preservation or refusal, with only opaque home/process observations supplied by the fixture.

Before any native fixture rewriting, snapshot untouched provider-created General/Profile/Install content and all eight current/legacy `profiles.ini` and `installs.ini` paths, including absence. Record actual observed existing bases and installation IDs. Seed only those bases inside the restoration extent; absent legacy indexes cannot assist modern-only success. Native stock-pending Floorp launches ordinarily without profile/new-instance selectors. Keep test-owned bootstrap and synthetic all-root/history cases labelled separately. Native retarget uses actual current IDs: owned A versus unique ordinary B must reject and preserve both profile trees, every index/hook/state and the first restoration baseline. Cover both browsers; add no Floorp ambiguity exception. Restore original native bytes and absence, preserving unrelated profile trees and cleaning only owned fixture data.

Preserve the complete raw profile maps. A newly created empty top-level `.parentlock` is native synchronization state only when it is an actual regular file, is not a symbolic link, and is unlocked. Do not delete it or ignore existing-file changes, deletions, nonempty locks or other new paths. Check the immutable observed native delta and account-data, nonempty-lock and symbolic-link counterexamples before repeating the same full lifecycle command.

The matching [Gecko 159 Unix lock implementation](https://hg.mozilla.org/releases/mozilla-release/file/FIREFOX_159_0_1_RELEASE/toolkit/profile/nsProfileLock.cpp#l533) closes the lock descriptor and keeps the empty file after release.

Focused Phase 1 and the same challenger Phase 2 accepted these two proof requirements: untouched native snapshot precedes fixture preparation, and Floorp receives the existing retarget-refusal proof too. No numerical or native-build boundary changes follow from this refinement.

## Subtask and review boundary


N1 is the atomic native migration. Its observable outcome is a coherent distributable selected bundle with actual matching package, update, full-session and browser-helper evidence. Its primary owners are the existing builder, native patches, activation and their checks. Its allowed edits are those owners and their current documentation. It depends on the immutable selected method already on main. Complete S1–S12 and S14 before the cumulative checkpoint review and local commit. Distro-dependent S7 and current S10–S12 require both exact new bundles. S9 uses genuine complete retained Ubuntu Qt-only artifacts for the actual old-format install/predecessor/offline rollback sequence, both-distro metadata cases, and actual incomplete Debian artifact refusal. Do not manufacture missing metadata or require a historical-format by distro rebuild. Do not commit a passing component as proof of an unfinished stateful installation sequence.

Finalize the build guide, README behavior claims and relevant app instructions before review. Keep the roadmap Active during review. Obtain fresh read-only boundary trace closure against this inventory and the exact staged tree, then native correctness review of the complete candidate. Classify findings against the source contract before changing code. After a clean review, publish through the existing repository process. S13 follows that concrete reviewed bundle and remains unverified until the user's ordinary fresh login is observed.

## Decision Log


The fixed selected method needs no new algorithm research. Native integration follows the existing FreeType load/render and memory contracts and actual distro build rules. Reuse one processor path and existing optional capability bridges to minimize changes and preserve default-off containment.

[Debian Policy 10.10 and footnote 14](https://www.debian.org/doc/debian-policy/ch-files.html#permissions-and-owners) explain that existing directory modes persist across upgrades. The activation package's configuration step corrects its private directory. Section 10.10.1 retains native administrator permission overrides.

The same fresh read-only preflight challenger derived native boundaries and challenged the full card. There is no contract gap. Its accepted addition requires typed-only/environment-only/both/neither proof through the packaged public API with a once-versus-twice discriminator. The source-based CFF-reference and rootless-ownership requirements above prevent false raster comparisons and unusable package output.

Historical diagnostic modes and retained bundle recovery remain supported. Only the ordinary selected preset changes. Real future official implementations cannot be predicted by the retained-payload update fixture; describe its proof accurately.
