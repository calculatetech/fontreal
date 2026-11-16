# Simplify browser launch activation

## Outcome and scope


Enabled Firefox and Floorp use the saved Fontreal artifact. Disabled launches use stock rendering. Browser and installed FreeType updates do not disable an intact activation or require a qualification run. Tests validate Fontreal changes. Keep missing/changed-artifact detection, existing profiles, accounts, original restoration values, native arguments, sandboxing, remoting and executable scoping.

Base: `main` at `f89f1734a93eedc18150eb8a65f003858e0764d3`. Use the existing isolated feature branch and storage-backed build/results roots. Preserve the daily Teams checkout and hooks. One user and one writer use normal local filesystems.

Latest user direction supersedes the unfinished FR-020 exact-Floorp qualification proposal and historical browser/runtime-provider gates in FR-015-B, FR-018 S37 and FR-019. It changes launch policy only. The existing private builder still owns supported source revisions and provenance. Do not loosen its checks. Numerical processing and native packages remain unchanged. Edge and Flatpak Teams/Bitwarden delivery follow under FR-016/FR-017.

## Smallest implementation


Change only the existing browser enable/run/status and preview gates, their direct checks and current guide. Replace the release table with browser identities. Remove exact browser refusals and runtime installed-provider comparisons. Keep saved artifact existence and hash checks and their existing stock fallback. Old version fields are informational and need no migration. Keep `freetype_version()` for its existing native integration callers; ordinary launch does not consult it. Keep legacy saved contrast until explicit re-enable.

Profile selection, preferences, hooks, restoration and argument forwarding are opaque preserved owners. The private build-source machinery, processor, references, Mozilla internals and installed Qt/FreeType packages are opaque. New rendering APIs and Chromium/Flatpak implementation are deferred from this focused deletion. Add no registry, ABI detector, automatic rebuild, new state, dependency or recovery mechanism.

## Boundaries and focused proof


The latest launch requirement maps to B1/B2/B4; artifact integrity maps to B3; retained activation/restoration values map to B5. The test schedule and superseded version policies are non-boundary instructions. Other existing owner clauses above are opaque or deferred. The same fresh read-only challenger derives these boundaries and challenges the complete card. No contract gap remains.

| Boundary | Discriminator and contrast | Real production entry and terminal oracle | Check |
| --- | --- | --- | --- |
| B1 / S1–S2 | Same artifact/state before and after external browser/provider metadata changes | Real main run and status → artifact check → exact native exec environment/argv or status JSON. Both remain usable without provider queries, rebuilding or state writes. | Existing delivery discovery case |
| B2 / S3–S4 | Same browser identity/build with formerly targeted versus different version metadata | Real main enable → existing profile/build/hash/write owners; preview main → real disposable profile setup → opaque native child boundary and cleanup. Both proceed without a browser-version gate. | Discovery activation and preview checks |
| B3 / S5–S7 | Artifact intact versus absent/digest mismatch, with other inputs fixed | Real main run/status retain truthful stock fallback and loader cleanup; real enable refuses a wrong builder-record digest before writes. Preserve unrelated argv/loader entries and profile bytes. | Discovery artifact checks |
| B4 / S8 | Same account fixture enabled versus after normal disable | Real enable → run → disable → run. Original nonempty preferences and unrelated bytes survive; owned hooks/state disappear; only the enabled exec receives browser treatment. | Discovery restoration check |
| B5 / S1,S3 | Current record versus legacy record with obsolete metadata and saved contrast | Real main run uses the saved artifact/contrast without migration; explicit re-enable keeps the first restoration snapshot. | Discovery legacy-record checks |

Run `python3 tests/browser_delivery_test.py --case discovery`, `--case desktop` and `--case docs` for this Fontreal change. Retain complete existing profile-default and desktop-action assertions. Use real in-scope gates and writers; seams replace only opaque OS observations, the unchanged builder result and native exec/child boundaries. Do not repeat font matrices, browser-release qualification or native package/session lifecycle checks for this deletion.

## Delivery


F1 is one atomic simplification with the boundaries above. Finalize current usage, obtain fresh read-only trace closure and native correctness review of the complete candidate, then publish. After review, apply through existing ordinary profiles and launchers. Preserve an old active parent until normal exit; distinguish configured from active rendering. Keep FR-020 Active until the actual launch result is observed. Retain current artifact/source records for native integration and recovery consumers.
