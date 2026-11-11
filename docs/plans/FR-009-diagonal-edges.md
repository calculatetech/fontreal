# Controlled diagonal edge comparison

## Outcome and authority


Open a native comparison of the remaining W/V/w/v fuzziness. Keep the preferred automatic mono hints with grayscale edges as the reference. Add two tighter grayscale transitions and binary output from the same automatic hints. The user judges whether a candidate improves crispness without damaging curves, gaps, or letter identity.

The user's latest feedback says that W is fuzzy in both the experiment and the matched Konsole test, and V suffers too. The original benchmark prioritizes pixel alignment over outline fidelity while retaining softened curves and angles. This task supplies new controlled samples. It does not select a successful treatment or change the desktop renderer.

Base: `3736b78497680895c2802cec5bc5c45b7a946bbe` on `main`. Task branch: `experiment/diagonal-edges`, one writer in the existing checkout. Prior plan reconciliation: retain the default seven treatments and operating limits from [the original specification](freetype-comparison.md). This task adds a separate study. It does not replace a completed checkpoint. The Qt integration specification remains unchanged. No pending Plan captures exist in the sole worktree.

## Product boundary and operating model


`src/main.cpp` selects the study with `--edges`. `Config` carries this startup selection. `src/experiment.cpp` owns its four treatments, masks, blending, metadata, and exports. `src/window.cpp` retains the startup selection through existing control updates and draws the same images as export. These owners compose this task. `tests/experiment_test.cpp` supplies independent FreeType and numerical oracles.

Installed Qt Widgets, FreeType, font files, and the display are opaque dependencies. The existing input validation, export destination gate, geometry target, and pixel canvas remain supporting owners. KDE/Qt integration patches, KWin, GNOME, Wine, Windows, automatic size policies, new outline fitting, and physical display calibration are deferred. This task does not promote them.

Support one local user and one writer on normal local files. Keep existing TrueType, ASCII, size, scale, phase, font-selection, and export bounds. Add no dependency, persistent setting, desktop configuration write, or installation step.

## Normal-use floor and scope ceiling


The ordinary seven-row experiment must retain its pixels and metadata. The separate study must preserve the raw reference, common layout, manual blend choice, and native-pixel presentation. It must identify adjusted masks truthfully and keep its mode through GUI updates and export. Human preference is an observation, not an automated success metric.

Do not add an outline detector, spatial sharpening, new rasterizer, font substitution, or production coverage policy. Do not tune by glyph identity. Treat the fixed ramps as diagnostic candidates. Do not claim that fewer gray pixels prove readability, or that black-on-white success establishes dark-background success.

## Smallest implementation


Add `Config::edges`, default false, and the `--edges` startup flag. In this study, show four labeled rows: unchanged `auto-gray`, `edge-mild`, `edge-strong`, and `auto-mono`. Every row uses forced automatic mono-target hinting. The first three use normal grayscale rasterization. The last uses FreeType's monochrome rasterization, including its own dropout behavior.

For each grayscale glyph bitmap, remap its coverage byte `a` with `round(255 * clamp((a - low)/(high - low), 0, 1))`. Mild uses 32 and 223. Strong uses 64 and 191. These fixed symmetric ranges screen a hypothesis rather than establish an optimal setting. Empty and full pixels stay empty and full. Intermediate values remain possible. Apply the ramp before existing source-over text composition and color blending. Source-over combines overlapping masks as `a + (1-a)*b` in normalized coverage, with byte rounding at each glyph. Layout, bearings, dimensions, and the reference bitmap stay unchanged.

Retain the current export filenames. In the two adjusted rows, `coverage`, `ell`, and `probe` images contain effective masks rather than raw area coverage. Their metadata must identify the source `auto-gray` row, operation, and exact cutoffs. The source row exports raw coverage. Binary output must be identified separately. Record the study at the metadata root only when enabled, so ordinary exports remain unchanged.

Reuse the existing viewer and controls. Change the window title and introduction for the study. Carry `initial.edges` into every redraw. No new slider or preference is needed. Keep selected-glyph detail at exact 8x repeats. Open Noto Sans and DejaVu Sans at 15px, scale 1, snapped origins, linear blend, and black on white for the first human comparison. Include uppercase and lowercase diagonals and the earlier curve/stem controls.

## Boundary inventory


| ID | Source clause and disposition | Required contrast and oracle | Entry points and scenarios |
| --- | --- | --- | --- |
| B1 | Original specification: preserve seven declared treatments, raw reference, and repeatability. Mapped. | Ordinary mode versus study selection. Ordinary outputs retain their independent FreeType contract and captured pre-change hashes. Study reference remains raw `auto-gray`. | CLI export, GUI construction/update/export; S1, S4 |
| B2 | New comparison after user-reported W/V fuzziness. Mapped. | Reference versus each fixed ramp versus auto-mono, holding geometry and conditions fixed. Independent FreeType followed by independent ramp math checks every inspected and `l` pixel. Metadata identifies actual processing. | CLI export, GUI construction/update/export; S2, S4 |
| B3 | Controlled comparison and crisp stems with softened edges. Mapped. | All four rows survive even when `l` coincides. Common glyph identities/origins and raster settings agree. Empty/full endpoints stay fixed, and adjusted W/V/curve samples retain partial values. Repeated prefixes cannot discard later glyphs. These facts do not establish aesthetic acceptance. | Shared renderer through CLI and GUI; S2, S4 |
| B4 | Existing manual blend and polarity controls. Mapped. | Same masks under both polarities and both blends. Every rendered study pixel follows independent sRGB math. No ramp operates on encoded final colors. | CLI export and actual GUI control updates/export; S3, S4 |
| B5 | User requires generated samples at native size. Mapped. | Actual study canvases at DPR 1 and 1.25 versus CLI images. Every source pixel is preserved, and detail uses exact integer repeats. | GUI construction/update, canvas paint, export; S4 |
| B6 | Original GUI updates replace current results or clear invalid output. Mapped. | Valid study → changed font/size/inspection → invalid font → restored font → export. The four-row selection survives every valid transition, invalid output clears, and export reflects current controls. | Actual GUI controls and export callback; S4 |

Original input bounds, unavailable-mode handling, output preservation, and source-font preservation remain opaque supporting behavior, with their existing regressions retained. Historical 1990s preference and measured pixel counts are non-boundary context. Non-native LCD resolution remains excluded. Other platform work and production algorithm selection remain deferred. No public result is undefined.

## Scenario Proof


| ID | Discriminator and minimal contrast | Production path and terminal oracle | Runnable check |
| --- | --- | --- | --- |
| S1 | Study flag absent versus present, same Noto15 conditions | Actual CLI → Config → renderer → PNG/JSON. Default has seven independently checked modes. Study has four named modes. Compare ordinary outputs to pre-change captures for Noto and DejaVu. Study source masks match independent auto-gray FreeType. | `ctest --test-dir build -R experiment-core --output-on-failure`, plus before/after artifact hashes |
| S2 | Fixed treatment, then selected W/V/w/v or curve/stem control | CLI → mode selection → FreeType → optional per-glyph ramp → coverage and metadata export. Independently rasterize both fonts and apply declared math. Check every inspected pixel and bearing for all four modes, endpoint preservation, distinct W/V candidate masks, and retained partial edges. Independently reconstruct unhinted advances, unfitted kerning, origins, glyph bitmaps, canvas bounds, and complete specimen composition. Compare every full-text coverage pixel and expected origin. Use `WWWV wwv mno g lllm` to retain a later differing glyph after repeats. | Core check |
| S3 | Encoded versus linear and light versus dark, same mask | Actual CLI → ramp before blend → exported full-text coverage and color. Study coverage stays identical across all four color/blend conditions. Every rendered pixel, including later glyphs, matches independent blend math. | Core check |
| S4 | Retained study selection through actual controls and export | Construct real study window and immediately grab all three actual canvases. After each valid control event, observe the current result before another control event. Isolate a dark toggle and export through the actual callback before changing blend. Enter invalid font and observe all three canvases cleared and export disabled. Restore font, observe recovery, and export before any other edit. Independent references, full-specimen reconstruction from S2, and blend math check exported masks/colors. Canvas bytes equal CLI images at both tested DPRs. | `ctest --test-dir build -R experiment-view --output-on-failure` |

Input-domain checks reuse the existing validators because the new selection is a Boolean flag and the ramps have no public numeric input. GUI control updates are synchronous. They advance the current result, invalid input clears it, and recovery replaces it. No timer, asynchronous reopening, persistence, or stream lifecycle is added. Every fixed row and every requested sample glyph owes an output. There is no row deduplication or early limit.

## Atomic subtask and checks


E1 owns the new study, its direct checks, and user instructions as one review boundary. Build with `cmake --build build`. Run the core and viewer commands above. Keep ordinary comparison hashes, per-scenario results, preflight responses, and review evidence in one ignored task result. Do not repeat unchanged Qt-native integration tests.

Before native review, finalize documentation and obtain fresh trace closure for B1 through B6. Review the full candidate against `3736b78`. A clean full review permits the task commit and the user's authorized progress push. Keep generated samples for the pending human comparison. The roadmap owns lifecycle state.

## Decision Log


Choose a coverage-only contrast experiment before outline refitting because it isolates one reversible variable using the existing engine. Skia's [raster discussion](https://docs.skia.org/docs/dev/design/raster_tragedy/) separates coverage changes from geometry and warns that broad coverage changes can affect weight. This study uses a symmetric clipped ramp, not Skia's broad coverage boost. Its benefit remains unproven.

The [1995 perceptual grayscale paper](https://lspwww.epfl.ch/publications/typography/ptgogf_95.pdf) supports structural weight and phase control as a later path. It does not validate these ramp cutoffs. Reuse the existing [prior-art screening](../research/native-font-rendering.md) rather than select a new costly rendering mechanism for this bounded diagnostic. Accurate area coverage, global weight changes, and structural fitting remain distinct options. If clipped coverage fails visual judgment or damages curves, revisit geometry instead of claiming that more contrast solved the problem.

No treatment is selected for KDE by this experiment. The remaining decision is the user's visual preference among these samples.

The two-phase challenge requires full independent specimen reconstruction in addition to probe checks. Accept that proof because complete metadata alone cannot detect a skipped later glyph or shared misplaced advances. Group the unchanged validation, target, and export-gate clauses as retained supporting behavior. Their owners and existing regressions remain unchanged.
