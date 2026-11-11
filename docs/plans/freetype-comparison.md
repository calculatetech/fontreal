# Controlled FreeType comparison

## Outcome and sources

Build a local native comparison tool and repeatable image exports. The benchmark is a solid pixel-aligned stem with softened curves and diagonals. Shape fidelity yields to grid alignment.

Authority: the user's request for a controlled experiment, the subsequent preference for pixel snapping, and the accepted [research findings](../research/native-font-rendering.md). The statement about 1990s fonts supplies aesthetic context. It does not require historical emulation.

Git base: `d9ca77b915e3afbf65c89e0695d182e22d71e37c`. Work on `experiment/freetype-grid` in the original checkout. No remote exists. There is no roadmap or earlier implementation plan. The accepted research remains current. No retained plan decision is superseded.

## Owners and operating model

`src/experiment.cpp` owns FreeType configuration, shared glyph layout, raw coverage, blending, synthetic geometry, and export. `src/window.cpp` owns native viewing and controls. `src/main.cpp` owns command-line validation and dispatch. These owners compose this experiment. Installed font files, FreeType, and Qt are opaque dependencies. System font configuration is opaque and unchanged. An OS-wide renderer and a new font algorithm are deferred.

Support one local user and writer. Use installed Qt 6 Widgets and FreeType with CMake. Use `fc-match` only to locate a default installed font. Support scalable TrueType outlines and printable ASCII samples of 1 to 96 characters. Reject unsupported formats or missing glyphs explicitly. Font sizes are 6 to 48 pixels before an explicit software scale of 0.5 to 3. Phase is 0 to 1 device pixel, quantized to 1/64. These bounds keep the initial comparison small and reproducible.

Inspection selects one visible ASCII character (33 through 126), default `l`. The user identified heavy arches in `m` and softness in `m/n/o/g`, so preserve full two-dimensional coverage for a selected glyph. No single row or column becomes an authoritative thickness score.

The tool has no persistent settings. It writes only an explicitly selected new or empty export directory. Do not install packages, change desktop settings, patch applications, introduce a font format, or claim historical reproduction. The native viewer measures backing-store presentation. It does not prove compositor or physical panel behavior.

## Smallest implementation

Provide seven labeled FreeType treatments: TrueType interpreter 35 with mono target and mono output; interpreter 35 with mono target and grayscale output; automatic mono hinting with grayscale output; interpreter 40 with normal grayscale; interpreter 40 with light grayscale; unhinted grayscale; and interpreter 40 with default-filtered RGB LCD output. Record actual properties, flags, and render modes. Report unsupported engine settings as unavailable instead of substituting another treatment.

Use one unhinted layout and kerning calculation for every row. This isolates the mask treatment from spacing. A shared placement selector either retains fractional glyph origins or rounds them to device pixels. This fixed layout is a controlled experiment, not a claim to reproduce full legacy layout behavior.

Show the same text, size, scale, placement, colors, and blend across all rows. Expose font, size, scale, phase, placement, polarity, and blend controls. Provide native comparison, nearest-neighbor pixel detail, and a synthetic target in tabs. The target contains a straight stem, a ring, and a diagonal. Supersample this known geometry and box-average it. Label it as geometry, not a font renderer. Compare fractional placement with snapped placement.

Export native comparison and detail images, per-mode rendered and coverage images, isolated `l` coverage, target coverage, and JSON provenance. Record font SHA-256, FreeType version, effective size, glyph identities and origins, mode settings, raw stem profiles, and parameters. Keep raw coverage independent of foreground, background, and blend. Apply encoded-sRGB or linear-light blending only after coverage.

Add selected-glyph raw coverage and provenance alongside the retained `l` evidence. The detail tab magnifies the selected glyph. Inspection alone cannot change the full-text comparison, layout, original `l` data, geometry target, or blending.

Draw comparison images with one source pixel per Qt backing-store pixel, canceling Qt's device pixel ratio. Scroll rather than fit. Magnification repeats pixels by an integer factor. Use the same renderer for GUI and export.

## Boundary inventory

| ID | Source and required behavior | Contrast and oracle | Entry points and checks |
| --- | --- | --- | --- |
| B1 | Controlled comparison of existing Linux capabilities | Same glyph/layout and conditions, different declared treatment. Exported isolated glyph coverage and bearings match independent direct FreeType calls for each available mode. | CLI export and window construction/update; S1 and S6 |
| B2 | Observable repeatable experiment | Two identical invocations match in pixels and metadata. Font or size changes are recorded and affect output. | CLI export; S2 |
| B3 | Snap before shape fidelity; expose widened narrow strokes | At phase 0.5, a synthetic one-pixel stem occupies one full column when snapped and two half-covered columns when fractional. Real font origins follow the selected placement. | Shared renderer through CLI export; S3 |
| B4 | Soften curves and angles while retaining crisp stems | Target ring and diagonal contain partial edge coverage while the straight stem retains its full core. Actual monochrome-hinted grayscale remains an identified existing candidate, not a guaranteed new solution. | Shared renderer through CLI export; S4 |
| B5 | Local experiment, no system replacement | Runs read installed fonts and write only selected outputs. Font hash stays unchanged. Nonempty output directories are rejected without overwriting existing content. | CLI export and GUI export callback; S5 and S7 |
| B6 | Native-pixel presentation required by pixel-perfect inspection | Actual window construction and control updates feed exact images to the native canvas at DPR 1 and 1.25. Detail pixels repeat exactly. | Production window and canvas; S6 |
| B7 | A controlled experiment must identify valid inputs and truthful presentation parameters | Bad fonts, unsupported text, and out-of-range numbers fail clearly. Palette changes leave coverage unchanged. Blend pixels follow independent numeric expectations. | CLI parser, shared validation, shared blend, GUI updates; S7 and S8 |
| B8 | User feedback identifies heavy m arches and fuzzy m/n/o/g curves | Selecting m versus o changes actual inspected coverage and identity. Every m/n/o/g/l probe matches direct FreeType; original sample and l evidence stay unchanged. Detail repeats the actual selected mask. | CLI and actual GUI selection/export; S9 and S6 |

All authoritative source clauses are accounted for. Blur and the title-bar `l` motivate B1/B3. The controlled experiment and Linux comparison map to B1/B2. Snapping and consistent crispness map to B3/B6. Soft curves and angles map to B4. Non-native LCD resolution is excluded. Historical preference is non-boundary context. Konsole changes and universal script support remain deferred. No inherited specification conflict exists.

## Scenario Proof and checks

One test executable invokes the actual application export command with `QProcess`, loads its PNG/JSON outputs, and uses independent numerical and FreeType references. It also constructs the actual production window, drives controls, and captures its canvases. Tests do not substitute an in-scope renderer or viewer hop.

| Scenario | Discriminator and minimal contrast | Production path and terminal oracle | Runnable check |
| --- | --- | --- | --- |
| S1 | Mode settings, holding font/size/phase/layout fixed | CLI → shared rendering → FreeType → exported isolated glyph mask and bearings. Compare each mode with a separate FreeType library/face configured from the declared contract. Verify actual property and expected availability. All seven records appear even when modes coincide. | `ctest --test-dir build -R experiment-core --output-on-failure` |
| S2 | Invocation identity, then size or font identity | CLI → renderer → PNG/JSON. Two equal runs match; changed size or font changes both provenance and relevant pixels. | Same core check |
| S3 | Fractional versus snapped placement at phase 0.5 | CLI → real placement and target geometry → exported coverage/coordinates. One fully covered stem column contrasts with two half-covered columns; actual glyph origins obey placement. Include phase zero. | Same core check |
| S4 | Axis-aligned versus curved/diagonal target boundaries | CLI → synthetic geometry → coverage PNG. Full stem core and partial curved/diagonal edges coexist. The fixture shares geometry and raster policy. | Same core check |
| S5 | Before/after normal local export | Actual CLI → declared output directory. Original font bytes remain equal and results exist only at the selected destination. Inspect source for absence of configuration writers. | Same core check and source review |
| S6 | Actual viewer update at DPR 1 versus 1.25 | Production window → real size/placement controls → shared renderer → tab canvas → widget grab. Compare terminal pixels with the corresponding exported result. Check detail image integer repetition. | `ctest --test-dir build -R experiment-view --output-on-failure` |
| S7 | Valid versus invalid font/text/number; empty versus nonempty export directory | CLI → parser/validation/export gate → exit/error and unchanged existing marker. Invalid inputs cannot silently substitute fonts or produce a claimed comparison. | Core check |
| S8 | Encoded versus linear blend and dark versus light polarity, holding coverage fixed | CLI → renderer → coverage and rendered PNG. Coverage bytes stay equal. At a partial pixel, terminal color matches independently computed sRGB formulas for each palette/blend pair. | Core check |
| S9 | Inspection glyph l versus each of m/n/o/g | CLI → selected character → actual FreeType → raw 2D probe, metadata, detail. All probes agree with independent FreeType, while original sample and l masks remain equal. Empty/multiple/non-ASCII inspection values fail clearly. | Core check, plus actual GUI selector in viewer check |

The viewer check also applies independent FreeType and numerical blend oracles to its real GUI exports, exercises nonempty-directory refusal through the error dialog, and verifies font/working-directory preservation. Production GUI startup rejects invalid size, scale, phase, font, and inspection before a control can clamp them. An invalid edited font clears stale results and recovers after a valid selection.

Collection semantics: every fixed mode produces one row and one metadata record. Equal-looking modes cannot disappear. Every declared glyph reaches layout and output. Arbitrary user-defined streams, empty mode sets, and deduplication are not supported interfaces. The GUI keeps only current controls and images. Each control update either replaces the current output or clears it with an error. It does not retain stale successful images under invalid parameters. No asynchronous reopening exists.

## Atomic subtask

E1 owns the runnable experiment, its direct tests, build configuration, and documentation. All these files form one proof and review boundary. Configure and build with `cmake -S . -B build -G Ninja` and `cmake --build build`. Run the scenario checks above. Generate a small retained comparison under `results/` for installed sans and monospace fonts and inspect it visually. Generated artifacts remain ignored and can be regenerated.

Before review, finish README usage and record actual scenario evidence in the ignored task result. Obtain fresh read-only trace closure for B1 through B8 and then one full native correctness review of the candidate against the base. A clean full review covers this atomic subtask's local commit boundary. No publishing or system installation is part of the task.

## Decision Log

Pixel alignment is the target because the user explicitly prefers it over outline fidelity. The historical claim does not become an unsupported claim that antialiasing began with ClearType.

Use existing FreeType modes first. In particular, monochrome-target hinting with grayscale output is an existing candidate for crisp stems and soft residual edges. Do not invent a selective smoothing algorithm before measuring it.

Use shared natural layout to control the comparison. Study native per-mode advances later if the masks justify a spacing experiment.

Use native Qt viewing because arbitrary image viewers can rescale a PNG. Keep export and GUI rendering identical. No website is needed.

The planning challenge requires actual independent mode references, palette/blend oracles, and a composed viewer test. All three are accepted into S1/S6/S8. No contract gap remains.

The curve-inspection challenge preserves the original baseline and adds a diagnostic selector instead of a new pixel filter. The user reports that linear-light blending resolves the arch problem at 100% while encoded blending looks better at larger scales. Retain manual blend and scale controls. This observation does not define an automatic cutoff or universal preference.
