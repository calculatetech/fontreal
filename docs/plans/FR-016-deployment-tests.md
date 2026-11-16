# Test Fontreal changes, not routine builds

## Outcome and boundary

Build and enable an unchanged Fontreal profile for supported applications without running regression tests or requiring reports for each build. The user's 2026-11-16 instruction supplies this requirement: tests apply when Fontreal changes, not when it is built for tested applications. The same instruction skips all test execution in this task.

The base is `77ec74eeceaf8b0eeedfb2d660d66dcbcf66ecc4`. One writer uses branch `fix/deployment-test-policy` in the existing checkout. FR-016 remains the active integration task. Its [engine specification](FR-016-chromium-flatpak.md) continues to own rendering, application support and security. The [native specification](FR-019-native-selected.md) continues to own native rendering and package compatibility.

## Preflight

The existing owners are `tools/system_install.py::transaction` and `tools/chromium_delivery.py::enable`. These compose the change. Build manifests, activation payload checks, exact native package identities, safe APT transactions, application resources, fuses, launch ownership and restoration are opaque. Unsupported applications remain deferred.

The normal path builds matching artifacts, verifies their integrity, installs or enables them, and restarts normally. Missing test reports must not block this path. A report is development evidence, not an artifact integrity check. Remove the report preconditions without adding an override flag, a new marker, a qualification cache, a dependency or another state writer. Existing activation records with historical qualification fields remain readable.

This is a strict simplification in the existing owners. It removes test-report gates without expanding application support or adding an interface, dependency or persistent state. It does not change renderer inputs or engine sources. No separate planning challenger is needed.

## Boundary inventory and scenario proof

| Boundary and source | Classification | Contrasts and required result | Owner and future check |
| --- | --- | --- | --- |
| User instruction: routine builds need no tests | Composes | A complete native bundle without reports reaches APT simulation. Reports do not authorize or block deployment. | `transaction`; `python3 -B tests/system_install_test.py` |
| User instruction: same policy for supported apps | Composes | A valid application record without qualification enables ordinary hooks. Historical qualification fields remain compatible. | `enable`; `python3 -B tests/chromium_launch_test.py` |
| Existing native artifact and snapshot contract | Opaque | Corrupt artifacts, incomplete families, a different profile or a changed installed snapshot still fail. Unsafe package removals still fail. | Existing native installer checks and their regression cases |
| Existing app integrity and ownership contract | Opaque | A wrong target, modified artifact or foreign hook still fails. One target and both targets retain independent ownership and reversal. | Existing Flatpak activation owners and launch cases |
| Current application support | Deferred outside existing support | No new runtime, wrapper, engine version, application or rendering path becomes supported through this change. | Existing integration boundaries |

The input distinction is the presence of test evidence, not a new artifact format. The state transition remains ordinary install/enable and existing disable/rollback. Existing complete package and hook collections retain their current checks. No new collection or lifecycle is introduced.

## Atomic change and review

Remove the native per-bundle package/session report gate and the Flatpak per-build qualification gate. Update the existing regression cases to cover missing reports without running them in this task. Keep the rendering tests available for future Fontreal changes.

Make `CONTRIBUTING.md` the test-policy owner and link it from repository instructions. Separate ordinary build/deployment commands from development checks in the native and Flatpak guides. Update the app scenarios and README where they require routine qualification.

One full source review covers this atomic change. Inspect the exact diff and existing check bodies. The commands in the table are the future regression checks and are not executed under the user's current skip instruction. Do not claim test success for this candidate.

## Decision log and reconciliation

The user instruction supersedes only recurring test execution and per-build report preconditions. Sources: `77ec74eeceaf:tools/system_install.py` lines 140–153, `77ec74eeceaf:tools/chromium_delivery.py` lines 113–117 and the corresponding daily deployment guide requirements. Earlier renderer development evidence and source, security, data, compatibility, ownership and rollback contracts remain applicable. Historical qualifications can remain as evidence but are not deployment authority.
