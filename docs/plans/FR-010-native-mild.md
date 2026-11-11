# Mild contrast in the native Qt comparison

## Outcome and authority


Carry the selected mild coverage treatment into an isolated real Konsole comparison. Compare Noto Sans menus and Inconsolata Nerd Font terminal text with the unadjusted reference. Preserve explicit blending. Supply native windows for human judgment.

The user prefers mild contrast with Noto Sans over the original gray edges. The user also states that font, size, and rendering work together, and normally uses Inconsolata Nerd Font. The installed Regular TrueType file is `/usr/local/share/fonts/i/InconsolataNerdFont_Regular.ttf`. The normal Konsole profile uses that family at 11pt. Treat that profile and font file as read-only evidence.

Base: `595754cb1aa82b9f3bfb0df0bc0c4ea1186f8bb4`, `main`. Task branch: `integration/mild-contrast`, one writer in the existing checkout. Prior plan reconciliation: preserve FR-002's opt-in rendering, stock comparison, effective-size fitting, placement, manual blend, and private lifecycle. Preserve FR-009's experiment and exact mild formula. The user now selects mild for the viewed Noto sample, which resolves FR-009's pending preference. This promotes only the mild treatment into native testing. It does not establish a universal font or blend policy. No pending Plan captures exist in the sole worktree.

## Boundary and operating model


The Qt FreeType A8 bitmap/cache owner in `patches/qt-6.10.2-fontreal.patch`, process selector `tools/run-qt.py`, and private preview/font/specimen owners `tools/preview-konsole.py` and `tools/konsole-sample.sh` compose this task. `tests/qt_native_probe.cpp` and `tests/qt_native_test.py` check the real paths.

The pinned Qt build tool and installed Qt/FreeType/font files remain supporting owners. Existing hinting, placement, shaping, scaling, blend math, and the stand-alone experiment remain unchanged. KWin, Qt Quick, other platforms, global configuration, installation, arbitrary transforms, and transparent intermediate targets remain deferred.

Support this local machine with Qt 6.10.2, FreeType 2.14.2, and the three installed TrueType test families. One local user and one writer use normal files and separate preview processes. Add no dependency or persistent preference. Preserve already-open previews during the private rebuild. If a private library is still mapped, move that exact generated library file aside before relinking so the old mapping is not overwritten. Keep that file while its preview remains open.

## Required floor and scope ceiling


Mild must apply the selected per-glyph ramp exactly once before color composition and cache reuse. Unadjusted output and stock remain available. The real preview must identify the selected menu and terminal fonts, units, blend, and contrast. Normal close removes private state without changing the user's settings.

Do not add strong or binary native modes, a new rasterizer, font-specific pixel rules, automatic blend/contrast cutoffs, desktop installation, or profile discovery machinery. Font preference is local evidence. Do not claim that every size, font, palette, icon, or script looks good.

## Smallest implementation


After Qt converts a glyph bitmap to A8 and before it stores the bitmap in its glyph cache, apply the existing mild ramp only when `fontrealEnabled()`, A8 format, and `FONTREAL_CONTRAST=mild` hold. Map byte `a` to `round(255 * clamp((a-32)/191, 0, 1))`. Leave padding, bounds, bearings, advances, other formats, and the unadjusted path unchanged. Cache the adjusted mask so repaint does not reapply it. The setting is fixed at process startup.

Add `--contrast none|mild`, default `none`, to the generic launcher and preview. Place the generic option before the mode/command, because application arguments use `argparse.REMAINDER`. The generic launcher clears inherited contrast before applying its explicit choice. Stock rejects an explicit mild request and clears inherited Fontreal settings. Private Qt without the rendering opt-in ignores contrast. Preserve the existing version and missing-build gates.

Add a bounded preview `--terminal-family` choice of `builtin` or `Inconsolata Nerd Font`, default `builtin`. The explicit family uses the supplied normal 11pt setting. Optional `--terminal-pixels 6..48` overrides that size with explicit pixels. Reject a pixel override with the built-in choice. Override only the separate preview's terminal Font property. Keep both private KDE general/menu roles on the selected UI font. Labels identify launch conditions and distinguish points from pixels. Add W/V/w/v and repeated-prefix specimens. The printed terminal-font label describes the initial selection, since View controls can change it later.

Extend the existing native probe to compare unadjusted and mild coverage independently of both blends. Include Noto Sans, DejaVu Sans as a retained control, and Inconsolata Nerd Font. Add W/V/w/v, a later different glyph after repeats, punctuation, and blank text to existing stem/curve/cache/color/scale cases. Independent FreeType plus floating-point ramp math supplies expected masks. Independent sRGB math supplies all final pixel colors. Retain cold logical metrics and integral placement checks.

Retain the existing one-channel-value tolerance for pixels with one glyph layer. Independently count contributing glyph layers at each pixel. Allow one value per layer because each composition can introduce byte rounding. A fully opaque glyph resets the previous budget. The dedicated two-draw overlap therefore allows at most two values. Require an overlap fixture pixel where per-glyph and post-accumulation predictions differ by more than four channel values, so the opposite ordering cannot pass that tolerance.

Add one test-only capture check to that same executable. It reads a client-only Konsole screenshot for the explicit 15px fixture. Infer each text region's background from its dominant color and foreground from the greatest color distance. Search the menu strip for independent Noto m/n/o/g/V masks and terminal region for independent Inconsolata W/V/w/v masks, composed with the expected blend and contrast. Require each selected raw/mild fixture pair to differ and reject the opposite treatment at the matched location. Compare RGB within one value, including a one-pixel background border. This is a check for the current local desktop fixture, not a general screenshot-analysis interface or dependency. A real Konsole capture with the explicit terminal 15px override supplies this oracle. The 11pt preview separately verifies the actual point descriptor and runtime family, without assuming a universal point-to-pixel conversion.

## Boundary inventory


| ID | Authoritative clause and disposition | Contrast and terminal oracle | Entry points / scenarios |
| --- | --- | --- | --- |
| B1 | Selected FR-009 mild formula reaches eligible native glyphs before blend/cache. Mapped. | None versus mild, same font/effective size/placement. Independent FT and ramp masks, full native backing pixels, actual-app capture fixture. Empty/full endpoints and geometry remain equal, intermediate edges survive. | Generic launcher → Qt widget; preview → Konsole; S1, S3 |
| B2 | Manual blend, unadjusted reference and stock remain independent. Mapped. | Both blends share each contrast mask and follow independent color math. Clean/inherited stock and inactive private Qt agree. Invalid contrast or stock+mild fails clearly. | Generic and preview selectors; S1, S2, S3 |
| B3 | Rendering depends on font and size; use the user's terminal family honestly. Mapped. | Built-in terminal versus explicit Inconsolata 11pt and explicit 15px override. Both Noto UI roles, actual child arguments, FT family/size evidence, labels and captured glyphs agree. Reject ignored pixel requests. | Preview → installed Konsole; S2, S3 |
| B4 | Preserve private build and configuration lifecycle. Mapped. | Running private preview → normal close → absent private state, unchanged normal configuration and font hashes. Stock remains installed Qt. Rebuild stays generated/private and does not overwrite a library mapped by an open preview. | Build procedure; generic launcher; preview; S2, S3 |

The user preference and normal 11pt profile are context for B1/B3, not a universal policy. Existing hinting/metrics/scaling/shaping/blending and source validation remain opaque supporting behavior with direct regressions retained. FR-009's completed experiment remains opaque and unchanged. Incremental private publication is non-boundary delivery authority. Other platforms and non-native LCD resolution remain deferred/excluded. No undefined public result remains.

## Scenario Proof and checks


| ID | Discriminator and minimal contrast | Complete path and oracle | Runnable check |
| --- | --- | --- | --- |
| S1 | None versus mild, then each blend at fixed coverage | Real generic launcher → selected private Qt → real QWidget/QFont/QPainter → adjusted glyph cache → cold/cached/recolored backing capture. Independent FT/ramp and per-glyph color math check the entire requested image for all selected fonts and existing effective-size pairs. Include W/V/w/v and repeated prefixes with a later differing glyph. Draw one partially covered glyph twice at the same position, and require a fixture pixel where ramping each draw differs from ramping accumulated raw coverage. Check logical metrics after scaled raster and a later uncached glyph. | `python3 tests/qt_native_test.py` |
| S2 | Explicit request versus inherited settings and invalid combinations | Real generic/preview parser → child environment/loader → native output. Stock and inactive private Qt preserve stock under inherited mild settings. None and mild remain explicit and correctly labeled. Invalid contrast, stock+mild, and built-in terminal plus pixel override exit with errors before launch. | Same native integration check |
| S3 | Actual menu/terminal roles, point/pixel units and contrast across preview lifetime | Real preview → private KDE roles and terminal Font property → real generic launcher → separate installed Konsole → identified process/environment/library/FT evidence → actual repaint and client-only screenshot. The fixed Noto15/Inconsolata15 fixture reaches the independent capture oracle, with same-font none and mild under both blends as needed to distinguish processing. The Inconsolata11pt fixture retains its point descriptor and actual family evidence. Verify direct parent, D-Bus PID, and private config before every window action. Close normally, check cleanup and original configuration/font hashes. Leave separate human comparison windows open after automated checks. | Same native integration check and documented visible preview commands |

All runtime selectors are startup choices, not mutable settings. Native cached repaint and recoloring retain the same selected mask until the process exits. Each preview owns one child and private directory. Repaint preserves that state, normal close completes the child, and parent context exit clears it. The glyph collection preserves every requested character, including repeats and a later differing glyph. Blank text remains a supported probe. Empty font/case collections are not an interface.

## Atomic subtask and delivery


E1 owns the patch, launchers, sample, direct native checks, font controls and instructions as one proof boundary. Rebuild privately with `python3 tools/build-qt.py`, then `cmake --build build`. Run the native integration check. Do not repeat the unchanged stand-alone experiment suite without a concrete concern.

Finalize substantive documentation, obtain fresh trace closure for B1 through B4, then native review of the complete candidate against `595754c`. A clean review permits the task commit and authorized progress push. The roadmap owns lifecycle state. Keep one ignored task record for source reconciliation, checks, challenge results and reviewed-tree bindings.

## Decision Log


The technical mechanism is fixed by the user's accepted experiment. No new algorithm or prior-art search is needed. The pinned Qt source shows a direct A8 copy/cache boundary, so reuse that owner. Keep contrast independent of blending and font selection. Test actual Konsole pixels because FT load flags precede the new coverage operation and cannot prove it.

Use an explicit private terminal override rather than changing the user's profile. The normal 11pt value and explicit 15px control serve different purposes. Keep their units visible. Retain DejaVu only as a test control, while human comparison centers on Noto Sans menus and Inconsolata Nerd Font terminal text.

The two-phase challenge adds an overlapping native draw to prove per-glyph ordering. It also requires discriminating menu and terminal glyphs that match the selected treatment and reject the opposite one. Accept both obligations before implementation. A clean font/flag trace alone does not prove the new mask operation.
