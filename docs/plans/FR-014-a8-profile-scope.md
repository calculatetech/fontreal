# Confine the selected A8 text profile

## Outcome and authority


Eligible TrueType text retains the selected exact sRGB blend. Ordinary fonts retain their own transfer profile in the same enabled process. The grayscale Nimbus Sans CFF fixture must keep both its masks and final pixels equal to stock. Color glyphs and the accepted widget, Konsole, and KWin results must remain unchanged.

The user accepts the viewed KWin title result and requests the remaining work. The [roadmap](../roadmap.md) assigns profile confinement to FR-014. The [KDE checks](../experiments/kde-paths.md) reproduce the CFF spillover. Prior plan reconciliation retains [FR-002](FR-002-qt-native.md), [FR-010](FR-010-native-mild.md), and [FR-004](FR-004-kde-paths.md) except for FR-002's disclosed process-wide A8 profile choice. This task replaces that choice only. Hinting, coverage, geometry, shaping, and explicit blending remain authoritative.

Base: `42a925fbeb41b216c3586d2fb3c458352c8699fe`, main. Branch: `fix/fontreal-profile-scope`, one writer in the existing checkout. There is one worktree and no pending Plan capture. GPU composition and fractional Qt Quick changes remain FR-013. Installation remains FR-011.

## Product boundary and operating model


`patches/qt-6.10.2-fontreal.patch` composes the correction. Its QFontEngineFT eligibility decision identifies the current scalable, noncolor TrueType face. Raster `drawTextItem` and `drawStaticTextItem` reach `drawCachedGlyphs`, then `alphaPenBlt` and the shared A8 profile lookup. This font-to-profile-to-composition path composes the task. Existing geometry, mask adjustment, caches, alpha compositors, and layout remain supporting owners.

The supported environment is the installed Qt 6.10.2/FreeType 2.14.2 Linux stack. Preserve installed toolkit class layouts, virtual slots, callable signatures, and alpha-blit function-pointer contracts. Preserve ordinary behavior without opt-in. Use private builds, isolated test processes, and normal local files. Preserve running previews by moving an already-mapped generated QtGui file aside before relinking it. Do not overwrite its mapped inode.

The floor is per-current-font profile selection through both ordinary and static raster text. Cold and cached drawing, later fonts, and different colors must keep that authority. The ceiling excludes mask changes, altered eligibility, new user controls, persistent state, GPU composition, arbitrary transforms, new transparent-target guarantees, global configuration, and installed package changes. No public contract gap is open.

## Smallest implementation


Replace the process-wide profile condition with a private thread-local draw condition. Declare a hidden namespace variable in QtGui's existing private application header and define it in the corresponding source. Add no member, virtual function, exported interface, or changed parameter type.

At the shared `drawCachedGlyphs` entry, derive this condition from the actual FreeType engine's existing `fontrealEnabled()` result. Use Qt's scoped value rollback to restore the previous condition on return. Set false for other engines, including CFF and color faces. Both internal-cache and image-cache branches remain under the same scope. The shared A8 lookup returns exact sRGB only inside that eligible draw. All other calls retain the upstream platform profile. Encoded text keeps its existing false gamma-correction decision and bypasses the profile.

Use FreeType feature guards around the engine-specific include and cast. The new condition is neither a preference nor a cached mask attribute. Its lifetime is one raster glyph-run draw on one thread. A later font draw selects its own value. The existing alpha-blit code and transfer tables remain unchanged.

Extend the existing KDE probe with one mixed-font widget. Paint repeated eligible text, grayscale CFF, a real color glyph, and a later eligible region in one painter. Include the reverse order, ordinary text and QStaticText, cached repaint, and three existing palettes. Compare CFF/color regions exactly with stock and inactive controls. Compare eligible regions with independent masks and blend predictions. Require a visible chromatic emoji, not a missing-glyph box.

Turn the existing spillover observations into preservation assertions and add encoded mode. Retain a control that distinguishes the original CFF spillover. The existing native integration check independently gates all accepted TrueType pixels and Konsole output. Add explicit accepted-title assertions to the nested checks, since a successful diagnostic collection alone cannot prove preservation.

## Boundary inventory and Scenario Proof


| ID | Source clause and disposition | Discriminator and minimal contrast | Production path, oracle, and command |
| --- | --- | --- | --- |
| B1 | FR-014 confines the profile to current eligible text. Existing eligibility and manual blend are mapped here. | Eligible linear versus encoded at fixed mask; enabled versus inactive; current TrueType versus CFF in the same process. | Launcher → real painter → current FT engine → scoped cached-glyph draw → A8 lookup/composition → capture. Independent FT/ramp/color predictions for eligible text. `python3 tests/qt_native_test.py` and mixed profile cases in `python3 tests/kde_paths_test.py --only spillover` (S1). |
| B2 | FR-014 preserves ordinary and grayscale CFF. Equal masks alone are insufficient. Mapped. | Same Nimbus CFF font/strategy/palette under stock, private inactive, linear, and encoded. | Real ordinary/static painter entries → current CFF gamma decision → upstream A8 profile → final capture. Exact mask and CFF-region equality, including a partial-coverage fixture that failed before the correction. Spillover and mixed cases (S2). |
| B3 | FR-014 preserves color output and excludes color faces from the new profile. Mapped. | Same visible Noto Color Emoji under stock/inactive/enabled, including after an eligible draw. | Real painter → color engine → ARGB image draw → captured multicolor region. Exact image/mask equality plus positive chromatic pixels. Spillover and mixed cases (S3). |
| B4 | Per-font ownership must survive shared draw state and retained caches. Mapped from B1/B2 and FR-010 cache contract. | TT, TT, CFF, color, TT versus reversed order, then cached repaint and different colors. Ordinary versus static text selects separate production entries. | One retained widget and painter → both real raster entries → shared scoped draw → terminal per-region pixels. Each CFF/color region equals its stock counterpart, later eligible regions keep the selected independent prediction, and cached captures remain equal. Mixed cases (S4). |
| B5 | FR-014 preserves toolkit compatibility and accepted widget/title results. Mapped. | Stock versus private installed consumers; linear versus encoded/unadjusted controls; 100% versus 125% KWin output. | Existing installed Konsole and nested KWin/Plasma paths. Unchanged signatures/layouts, mapped private library, independent widget/Konsole/title assertions, and private cleanup. Native integration check plus `python3 tests/kde_paths_test.py` (S5). |

Every mapped source clause above reaches its real production entry. Existing hinting, mild ramp, metrics, layout, opacity, alpha function-pointer types, and source validation are opaque supporting behavior with direct regression checks. Existing build/linker policy and private configuration lifecycle remain opaque and unchanged. User appearance feedback is context, not an automatic blend policy. GPU gaps, distribution, session activation, and other platforms are deferred. Progress publication is non-boundary delivery authority.

The scoped condition begins at the shared raster draw, remains fixed while its glyphs compose, and restores on return. Each later run, including a later CFF counterexample after repeated TrueType runs, selects from its current engine. Caches retain only their existing glyph data. Repaint and recoloring reopen the same real path. Both entry points must reach the terminal image oracle. Empty text retains existing native checks; an empty font list is not an interface. No fault injection or speculative concurrent-writer lifecycle is added.

## Atomic subtask and checks


P1 owns the patch, focused regression additions, and maintained instructions as one proof boundary. Rebuild privately with `python3 tools/build-qt.py` after preserving any mapped QtGui inode. Build the probes with `cmake --build build`. Run the native integration check and KDE path checks. Record named scenario outcomes in the ignored task result.

Finalize substantive documentation, obtain fresh production trace closure for B1 through B5, and run native full review against the base before the task commit and authorized progress push. Retain the completed test specification while FR-013 and the package pilot consume it. The roadmap owns lifecycle state.

## Decision Log


Confinement is a fixed correction to the already-reproduced process-wide profile choice. It does not need a new rendering algorithm or literature mechanism. The smallest owner with current-face authority is the shared raster cached-glyph entry. A private scoped condition preserves existing toolkit layouts and function signatures. A process-wide switch or a mask-only check cannot prove the required result.

Source: `42a925f:docs/plans/FR-002-qt-native.md`, A8 profile choice. Status: superseded. Reason: explicit grayscale CFF demonstrates spillover. Replacement: per-current-font draw scope. Scope: A8 transfer-profile selection only. All other completed behavior remains authoritative.
