# Native comparison of B geometry and horizontal fitting


## Outcome and scope


Generate a reproducible native comparison of the user's preferred B stroke balance with sharper vertical stems. Retain B and D as exact controls. Add two diagnostic candidates: E takes X coordinates from automatic monochrome hints and Y coordinates from B. F takes X coordinates from D and Y coordinates from B. X controls horizontal placement, including vertical stroke edges. Y controls vertical placement, including horizontal stroke edges. Neither candidate is a selected browser policy.

The command is `python3 tests/browser_stroke_axis_test.py`. It writes native-size and exact 4x detail images under `results/browser-stroke-axis/`, with raw masks and portable capture metadata. Build output uses `build/freetype-native/`. Run from the repository root with the existing native experiment built.

Base: `f1a813c68c22c6e34bb429674e5b017b0c41ce76`, branch `feature/gtk-rendering`. The task uses the existing task worktree. Build and result directories retain their configured storage destinations.

Prior plan reconciliation: the [working-profile delivery](FR-015-browser-masks.md) remains unchanged. The [common-ground investigation](../research/browser-common-ground.md) records the earlier controls. The latest user chooses D overall, prefers B's line-width balance, and identifies B's vertical blur. This replaces the unfinished selection of a contrast ramp with an axis-isolation experiment. It does not replace the deployed preset or approve a new global rendering algorithm.


## Product boundary and operating model


One user and one writer use normal local filesystems. The bounded inputs are the existing nine static TrueType faces and effective sizes 12, 15, 18.75, and 22.5 pixels. Include light, regular, bold, italic, and bold italic. Use the same font files, text, glyph identities, integral origins, shared unhinted advances, and unfitted kerning for all columns. Use grayscale without coverage clipping and explicit black/white linear-light blending.

| Owner | Classification | Required relationship |
| --- | --- | --- |
| Native probe and new comparison check | composes | Assemble compatible outlines, render, verify provenance, and export all conditions |
| Existing native experiment's origin data | opaque | Retain its unhinted advances and unfitted kerning |
| Pinned stock FreeType load, darkening, outline expansion, and raster APIs | opaque | Use the existing verified builder and actual native APIs |
| Existing probe consumers | opaque | Existing transforms, repeated rendering, and exclusions retain their results |
| Browser profiles, activation, Qt, installed libraries, system configuration | opaque | No changed runtime path or writes |
| Modified hinter rules and a deployed browser replacement | deferred | Require later evidence and a separately defined implementation boundary |

The floor is a faithful comparison, not a guarantee that either candidate wins. The ceiling excludes browser launches, profile edits, installation, global environment changes, font replacement, CSS rules, new dependencies, a new rasterizer, and changes to FreeType's internal fitting policy. Do not infer browser shaping or layout safety from unchanged component advances. No fault recovery, concurrent writers, or generic font fallback is added.


## Smallest implementation


Extend `tests/freetype_mask_probe.cpp` with test-only transform choices `expand-d`, `axis-mono`, and `axis-d`. Existing choices retain their behavior. For axis transforms, load the same glyph from the same face and size with automatic monochrome hints into a second face. For `axis-d`, apply `FT_Outline_EmboldenXY(8,16)` to that source. Require matching outline point counts, contour endpoints, and tags before copying only X coordinates into the original B outline. Preserve B's Y coordinates, tags, contours, metrics, and advances. Apply the operation after each fresh glyph load and before translation or rendering, including the next-glyph observation. A repeated render must not repeat assembly.

`expand-d` supplies the D control from an automatic monochrome source. It applies exactly the existing native expansion once. The test command uses the stock library and clears inherited private-treatment variables in its children. It enables native stem darkening only for B and the axis candidates. An unsupported axis-source face or incompatible topology fails immediately rather than adding a fallback.

Add `tests/browser_stroke_axis_test.py` to compile the probe against the verified stock build, exercise the transform lifecycle, compose shared-origin words, and export the comparison. Use an independent native outline oracle: load ordinary A/B snapshots, call the stock `FT_Outline_EmboldenXY` API for expected D coordinates, assemble the expected axes outside the candidate, and rasterize those expected outlines through `FT_Outline_Get_Bitmap`. The oracle must first reproduce ordinary A/B masks and bearings. Do not use the candidate's assembled outline as the expected input.

The existing grayscale provider uses a pixel-rounded control box. The selected TrueType outlines use nonzero winding. Verify the provider contract against the pinned `src/base/ftobjs.c`, `src/base/ftoutln.c`, and `src/smooth/ftgrays.c` source. Retain exact font, library, probe-source, and image hashes. Export every glyph occurrence, including repeated glyphs and spaces, on a canvas covering every column's ink.


## Source-clause inventory


| Authority and clause | Disposition | Boundary |
| --- | --- | --- |
| Latest user: D wins overall, B has better widths but vertical blur | mapped | B1 |
| Original user: prioritize crisp pixel alignment and avoid per-site handling | mapped | B1, B4 |
| Common-ground specification: same font, effective size, style, spacing, and origins | mapped | B2 |
| Existing B and D definitions and no second treatment | mapped | B3 |
| Public probe: outline coordinates, topology, repeated render, and next load | mapped | B1, B5 |
| Full words include all repeated occurrences, spaces, and overhanging ink | mapped | B2, B6 |
| Native text and exact 4x detail presentation on both polarities | mapped | B6 |
| All selected styles and effective sizes owe an output | mapped | B4, B6 |
| Source: italic faces disable horizontal hinting independently of target | mapped | B4 |
| Existing probe consumers retain their supported results | opaque | B7 |
| Working browser data, accepted Qt, installed libraries, and normal environment | opaque | B8 |
| Component images do not establish browser layout, final composition, or preference | mapped | B8 |
| New hinter policy and real-browser candidate validation | deferred | Later implementation scope |
| Incremental commit and branch push | non-boundary | Delivery |


## Boundary inventory and Scenario Proof


All checks below run through `python3 tests/browser_stroke_axis_test.py`, except S7. Font and size selectors, native operations, raw masks, complete condition keys, image rectangles, and provenance must remain observable. Known fonts exercise the normal path. Topology guards do not add support for arbitrary font formats or recovery from malformed inputs.

| Boundary | Discriminator and contrast | Required terminal oracle | Scenario |
| --- | --- | --- | --- |
| B1: Per-axis identity | E versus untouched B; F versus E; source coordinate differences retained | Every loaded X equals its ordinary A/D source, every Y equals ordinary B, matching topology, and native pixels equal an independently assembled/rasterized outline | S1 |
| B2: Shared layout and all occurrences | Single `l`, then `ll3`, then mixed text with spaces and italic overhang | One placement per occurrence at the same shared origins in every column; independent reconstruction equals the exported raw word | S2 |
| B3: Exact B/D controls | Ordinary public B and independent native D expansion versus wrong target, clipping, or repeated expansion | Masks, bearings, and origin-aligned words match independent sources; record fixed library and font identities | S3 |
| B4: Scope of sharpness claim | Regular/italic and bold/bold-italic pairs; light/ordinary faces; small and larger effective sizes | Exact axis provenance for every case; actual stem profiles and explicit italic limitation, without a universal sharpness assertion | S4 |
| B5: Lifecycle | Render twice, then load `g` in the same slot versus fresh `g` | Repeated bitmap/bearing equality and complete next-glyph equality with a fresh request | S5 |
| B6: Faithful complete images | Expected key set versus duplicate/missing rows; full bounds versus reference-only canvas | All 36 unique font/size keys; every nonzero glyph pixel fits; every native crop equals its source; every 4x crop equals exact repeated pixels; labels name actual operations | S6 |
| B7: Existing callers | Original transform modes and exclusions versus unintended helper changes | Existing independent public FreeType regression passes | S7 |
| B8: Isolation and honest claims | Component build/export versus installation or activation | Writes stay in configured build/results and task docs; no browser/profile/system writes; metadata and guide state component-only scope | S8 |

| Scenario | Complete path and runnable check |
| --- | --- |
| S1 | Test command → ordinary A/B source loads → candidate topology gate and X assembly → native gray render → independent expected outline/raster → raw mask assertion. Include `l,H,m,3,5` and source differences that expose an unchanged-B or swapped-axis implementation. Also exercise X=17/64px and Y=-9/64px translation against the independently translated expected outline. |
| S2 | Existing native origin export → full occurrence list → all-column bounds → alpha-over word assembly → independent occurrence reconstruction → raw word export. Exercise `l`, `ll3`, and the mixed study text through the same compositor. |
| S3 | Verified stock library → ordinary B and monochrome A loads → native outline oracle for D → candidate D render → independent masks and bearings → origin-aligned word reconstruction. Use no coverage transfer. |
| S4 | Complete nine-face/four-size selection → exact candidate assembly/render → labeled rows and per-axis/pixel profiles. Compare Noto regular/italic and bold/bold-italic at 15px. Keep the native italic X-fitting bypass visible. |
| S5 | One candidate glyph load/assembly → render → repeated render → next `g` load/assembly/render → comparison with a fresh independent `g` request. Verify both candidate transforms and D's single expansion. |
| S6 | Actual masks → explicit blend → native placement and exact 4x details → PNG/manifest. Require expected-key set equality, not only a count. Reopen saved PNGs and verify all native/detail rectangles fit and equal their sources. |
| S7 | Run `python3 tests/browser_masks_test.py --case freetype` sequentially after the study. This retains the existing independent mask, transform, delayed-render, and exclusion checks for shared probe callers. |
| S8 | Inspect the complete test command and invoked subprocesses. Require the study's declared output paths and unchanged caller environment. Run the public documentation guard and verify portable capture metadata. No browser invocation is part of the experiment. |


## Subtasks and review boundary


S1 is one atomic component experiment: probe transforms, independent verification, reproducible image export, and authoritative documentation. Its owner is the test harness. Its change boundary is the two test files, this specification, the common-ground research, selected public images/provenance, and the FR-018 roadmap entry. Validate the named checks before one native checkpoint review from the stated base. Keep FR-018 Active while broader policy work remains.

Later hinter changes or browser integration are deferred. Promote them only after component evidence identifies the candidate and a new preflight defines that implementation. Do not treat a local coordinate-mixing diagnostic as a complete font engine.


## Decision Log


Use an outline-axis diagnostic before modifying the hinter because native loading and raster APIs already expose both source geometries. This is a cheap, reversible experiment, not selection of a new production architecture. The prior arXiv search remains applicable and supplied no directly usable browser mechanism. No learned renderer or adaptive rule is selected.

Preserve both E and F to distinguish pure monochrome X fitting from the user's preferred D X expansion. Preserve B's Y coordinates exactly, but do not claim preservation of its full shape or perceived weight. Combining coordinates can change curves and diagonal strokes.

Use independent public-native references and saved-pixel checks because coordinate identity alone cannot prove that the displayed image came from the assembled outline. Keep operational results and visual feedback in the ignored task record and authoritative research, not in this specification.

## S2: Rounded widths with a visible thin-stroke control


The user requests examples of rounding a stroke's total width to whole device pixels, with halves rounded up. A second experimental control gives strokes narrower than half a pixel a half-pixel width. At an aligned straight interior, that represents approximately 128 of 255 coverage. This does not impose a minimum on every boundary pixel. Preserve grayscale antialiasing on curved boundaries. These controls are research candidates, not a selected browser policy.

Base: `93583b04e664939e73d960bb06355ef82a0136d8`, existing task branch and worktree. Prior plan reconciliation retains S1 and the source inspection as completed immutable checkpoints. This section adds an unfinished component experiment. The existing F reference and all installed treatment remain unchanged.

The existing entry and terminal owners are the native public probe and the component image exporter. Add a test-only width helper and one standalone test/export command, `python3 tests/browser_stroke_width_test.py`. Copy the pinned stock FreeType source into its own build directory. Insert a child-process-only experimental selector at the existing Latin stem-width function. With the selector absent, the library follows stock behavior. With either candidate selected, use the new width helper before the existing thin-axis bypass and standard-width adjustments. Retain native stroke detection, edge placement, blue zones, italic exemptions, and grayscale rasterization. Record actual width decisions. The standalone C helper check and native decision log must exercise the same helper that the private library calls.

The two controls use automatic monochrome hinting with grayscale rendering and no darkening or outline expansion. The full-pixel control rounds positive magnitudes to the nearest pixel with a one-pixel minimum. The thin control instead gives positive magnitudes below 32 units a width of 32 units. One pixel is 64 units. Zero stays zero and negative distances retain their signs. Thus 31 maps to 32 only in the thin control, 32 maps to 64, 90 maps to 64, and 96 maps to 128. The proposed half-pixel behavior is an experimental interpretation of the user's 128 suggestion, not a new accepted default.

The supported inputs are the existing nine static TrueType faces and four effective sizes. Reuse their integral shared origins. Cover regular, bold, italic, bold italic, light, and monospaced text. Retain the F records as an exact reference. Generate light and dark sheets with native text and exact enlarged H, l, 3, 5, and V pixels. Include synthetic straight bars to expose the numerical thresholds independently of font detection. State that coverage is opacity, not the encoded display brightness. Existing native geometry rules can still affect final boundaries, especially italic faces and curves. Do not claim universal pixel alignment or equality of every perceived stroke width.

The normal-use floor is a faithful comparison and measured native behavior. The scope ceiling excludes installation, activation, browser/profile writes, new dependencies, a new stroke detector, website overrides, and an implemented general renderer. Build data stays under `build/freetype-native/stroke-width/`; outputs stay under `results/browser-stroke-width/`. Tests, test fixtures, docs, media, and this specification form the complete change boundary. No production entry point changes.

| Boundary | Source clause and owner | Contrast and terminal oracle | Scenario and runnable check |
| --- | --- | --- | --- |
| B9 | User: round total stroke width with halves up | 90 versus 96 units, both signs and zero; actual native decisions equal independent expected numbers | S9: command compiles the helper check, invokes the native library, and checks every logged input/output decision |
| B10 | User: retain thin strokes with coverage near 128 | Thin versus full minimum at 31 units, compared with 32; an isolated half-pixel straight bar retains half coverage in one pixel rather than raising every fringe | S10: command rasterizes synthetic aligned bars and verifies their native mask profiles; candidate native decisions also show the thin branch |
| B11 | Preserve actual native geometry and grayscale curves | Untreated candidate library versus retained stock A inputs; selected candidates versus F; raster output equals an independent public native outline raster | S11: command checks profile-off stock identity, repeated render/next glyph, source topology, native decision records, independent rasters, and measured straight-stroke profiles |
| B12 | Faithful complete comparison, styles, sizes, and palettes | Exact nine-face/four-size and sheet key sets; all occurrences fit union bounds and share origins; saved native and enlarged pixels equal source pixels | S12: command checks the complete condition set, repeated glyph placement, all ink bounds, retained F identity, linear blend, and reopened image crops |
| B13 | Existing working treatment, storage, and public privacy | Private copy and child-only selector versus source/installed mutation; stock source/library hashes and caller environment remain unchanged | S13: command checks source/library identities and caller environment; public docs guard checks portable metadata and final media |

All user clauses map to B9 through B13 or the stated scope ceiling. Higher density is represented by the existing effective sizes, not a claim of browser scaling support. A new universal detector, diagonal core rule, browser integration, and a final cutoff policy remain deferred. The accepted result is measured examples, so a candidate can look worse without failing the experiment. S2 receives one native checkpoint review and one progress commit after its named checks and final documentation. Keep FR-018 Active for later visual feedback and browser qualification.

## S3: Coverage balance for weak crowns and light faces


This specifies the former lift comparison in Git commit `979bf92725f0cfadd612f61424dae71e57fdba74`. The user rejects that lift. The current exporter follows S4 below.

The user prefers S2's third column at 15px. At 12px, crowns remain too light. Light faces also need less than full coverage on solid pixels. The user suggests a stroke-width average around 75%. Keep the approved half-minimum masks as the new exact reference and compare simple coverage controls before selecting a general stroke-average mechanism.

Base: `2de3e4dd953f6cd6a88b008bbb8a6c2905ce96dc`, existing task branch and worktree. Prior plan reconciliation retains S1, source inspection, and S2 unchanged. This section adds one unfinished test-only export. It does not alter their controls, the native width helper, or the installed preset.

Add `tests/browser_coverage_balance_test.py`. Reuse the retained S2 half-column glyph masks, geometry, origins, metadata, and blend. All four columns retain the same native geometry. A is the unchanged reference. B lifts partial coverage using `1-(1-a)^2`, where `a` is coverage divided by 255. C caps each light-face glyph pixel at 191, the nearest byte to 75% coverage. D applies B and then C. B retains zero and full coverage exactly and maps approximately half coverage to three-quarter coverage. It affects all partial pixels, not only curves. C uses static OpenType `usWeightClass` below 400, not font names or website selectors. The bounded matrix contains two light faces with class 300, ordinary faces with class 400, and bold faces with class 700.

These are pointwise mask controls. A 75% pixel ceiling is not a normalization of arbitrary stroke-width averages. Measure actual middle-scanline profiles for l, naming the horizontal measurement interval explicitly. Also record the first nonempty raster row of 3 and 5 to expose actual crown changes. Include declared-width synthetic profiles with actual arithmetic averages and zero-padding contrasts. Show that a cap reduces an opaque pixel while leaving an already lighter pixel unchanged. Do not claim automatic stem classification, equal curve thickness, or a general width-average solver. Antialiased geometry remains the existing native raster input. Check the retained linear blend table against an independent high-precision sRGB calculation before comparing saved pixels on both palettes.

Apply each operation to glyph masks before alpha-over composition. Preserve dimensions, bearings, metrics, advances, origins, and every zero pixel. A light-face glyph mask obeys C's ceiling, but overlapping treated glyphs can exceed it in the final word. An explicit synthetic overlap must expose that distinction. The exporter owns coverage treatment, per-occurrence composition, measurements, image layout, and portable provenance. The retained S2 generator, native library, font files, and approved desktop/browser treatment remain opaque unchanged inputs. Production integration, a new stroke detector, variable-font weight selection, and a coherent average-per-stroke policy remain deferred.

The supported output is nine static faces at 12, 15, 18.75, and 22.5 device pixels, with both palettes, native text, and exact 4x H, l, 3, 5, V details. The new command is `python3 tests/browser_coverage_balance_test.py`, after the S2 command. It writes only `build/freetype-native/coverage-balance/` and `results/browser-coverage-balance/`. The normal-use floor is faithful measured examples. The ceiling excludes native rebuilds, library/profile installation, new dependencies, browser changes, and a selected global policy. Use the existing public research document and portable images for explanation.

| Boundary | Source clause, discriminator, and contrast | Required terminal oracle and runnable check |
| --- | --- | --- |
| B14 | User: retain the winning 15px third column; unchanged A versus any second treatment | S14: command checks retained input and source hashes, exact half glyph/word identity, and A's native saved pixels against the prior half-column sheets on both palettes |
| B15 | User: weak 12px crowns; zero/full versus partial coverage | S15: command checks all 256 transfer inputs against independent rational arithmetic; actual exported 12px crown profiles must equal independently derived values and differ from A; reopened detail crops must match that independent expectation, while zero/full pixels stay unchanged in B |
| B16 | User: light faces need less than 255 coverage; light class 300 versus regular class 400 and bold class 700 | S16: command reads the actual OpenType weight field, checks the supported class map, and asserts cap eligibility and exact per-glyph output; synthetic profiles and real l scanlines report their declared intervals and averages |
| B17 | Existing mask-stage contract; one treated glyph versus overlapping repeated glyphs | S17: command verifies all per-occurrence origins and independent alpha composition, with a synthetic pair that exceeds the per-glyph ceiling after overlap; geometry fields remain identical |
| B18 | User needs visible examples across supported styles and densities; complete keys versus duplicate or missing conditions | S18: command asserts every unique face/size/mode and palette output, all text occurrences, native and exact enlarged saved pixels, accurate labels, and portable image hashes |
| B19 | Preserve working treatment and existing storage; read-only inputs versus task-owned export | S19: command verifies input/source/font hashes and caller environment before and after; public docs guard checks final media metadata and documentation |

All latest user clauses map to B14 through B19. The 75% average suggestion is represented by explicit profile measurements and a separately named ceiling control. A general average-based stroke operator remains a research question, not a delivered implementation claim. Native detection, hinting, and rasterization stay unchanged, so no new systems architecture or prior-art search is required for these fixed numerical controls. S3 receives one native checkpoint review and progress commit after its named checks and final documentation. FR-018 remains Active for visual comparison and later browser qualification.

## S4: Full-intensity thin-stroke cores and enlarged 8


Base: `979bf92725f0cfadd612f61424dae71e57fdba74`, existing task branch and worktree. Prior plan reconciliation retains the approved 15px half-minimum reference. The user rejects S3's lift as too strong and ineffective for crowns. The subsequent user instruction sets near-regular intensity on single-pixel light strokes as the target. This supersedes the tentative 191 ceiling and the unfinished low pointwise floors in the earlier S4 draft. Scope: unfinished S4 only. The user also identifies font-dependent weak crowns in 8.

Modify the existing `tests/browser_coverage_balance_test.py`, without another exporter or native rebuild. Remove the quadratic lift and every weight-dependent opacity cap. Compare two exact retained native controls: A uses S2 `half`, with a half-pixel minimum below the half-pixel width threshold. B uses S2 `solid`, with a one-pixel minimum. Both retain nearest-integer fitting above the threshold and native grayscale antialiasing. Reuse the existing provider's raw masks, native provenance, verified width decisions, and synthetic bars. Do not infer a stroke core from an alpha threshold or apply a high floor to every partial pixel.

The stronger minimum acts on detected stroke geometry before rasterization. An isolated aligned one-pixel stem has 255 coverage, the natural maximum. Antialiased edge pixels remain below that value. Native placement, blue zones, unlinked interpolation, and italic exemptions remain active. The method does not promise full coverage for every crown. Light and regular one-pixel cores receive no artificial opacity distinction. Their original font identities and design differences remain intact. The official OpenType weight definition concerns stroke thickness and related design changes, not a required opacity percentage. No universal font or density policy is selected.

Add 8 to the enlarged set, now `Hl358V`, and to recorded crown profiles. Use each native glyph's own first nonempty row and record its bearing-relative coordinates, since the minimum can change geometry. Also record l's middle row and H's central vertical column. The latter distinguishes a half-covered light crossbar from a full regular crossbar. In the retained 12px Lato Light data, H's central crossbar changes from 128 to 255, while Lato Regular stays 255. Lato Light 8 changes its first-row peak from 167 to 246 while retaining native partial edge values. Verify those actual provider fixtures and saved details. Do not require every font to change or improve.

Both columns must match their respective source probe records and original S2 PNG columns exactly, including complete metadata. Source-sheet geometry continues to use its original `Hl35V` set. New sheets reserve six nonoverlapping detail rectangles. Keep the nine-face/four-size matrix, shared origins, complete source bounds, independent alpha composition, high-precision blend oracle, source/font/environment hashes, and configured storage. Synthetic panels show actual retained half and solid native bar masks and their fitted widths. Numerical controls are these two labeled trials, not a new configuration interface.

| Boundary | Source clause and discriminator | Required terminal oracle and runnable check |
| --- | --- | --- |
| B20 | User rejects lift and requests a high stroke floor; half versus full native minimum | S20: command checks exact half and solid native provider identities, retained synthetic width decisions at 31 versus 32 units and 95 versus 96 units, and native bar profiles of approximately 128 versus 255; no opacity transfer remains |
| B21 | User wants light and regular single-pixel intensity to converge | S21: command checks the actual 12px Lato Light H crossbar at 128 versus 255, Lato Regular at 255 in both controls, and uncapped 255 l cores; no font substitution or weight-dependent dimming occurs |
| B22 | User identifies weak font-dependent 8 crowns; core versus native fringe in the same glyph | S22: command verifies all 8 source keys, actual 3/5/8 profiles, the retained Lato Light 8 core/fringe fixture, and every saved 8 detail crop; native partial pixels below the core target remain present; no universal improvement claim |
| B23 | Preserve accepted reference and candidate provenance; old source layout versus expanded new layout | S23: command retains exact A and B masks and metadata, matches both original S2 native PNG crops with original layout, and checks six nonoverlapping enlarged rectangles against exact repeated provider pixels |
| B24 | All supported inputs, composition, palette and isolation obligations | S24: command retains exact 36-condition and ten-sheet sets, every occurrence and shared origin, independent alpha-over and Decimal blend oracles, unchanged source/font/environment hashes, configured storage, and portable captures |

The normal-use floor is faithful labeled examples from independently verified native provider data. Candidate geometry may differ from A only as already captured by S2's native operation. The ceiling excludes new detectors, native rebuilds, opacity clamps, automatic font substitution, variable-font policy, a solved stroke-average operator, installation, or browser changes. All active writes remain in the existing test, public docs/media, and configured output directories. Lifted outputs remain available in Git commit `979bf92725f0cfadd612f61424dae71e57fdba74`. Run `python3 tests/browser_coverage_balance_test.py`, finalize documentation and images, then perform one native checkpoint review. Keep FR-018 Active for visual feedback and later browser qualification.

Delivery also requires opening or showing the revised 12px and 15px comparisons, including 8 details on both palettes. Inspect them with the image-view tool and open the selected sheets on the desktop. Record the observed result in the ignored task record. Correct files alone do not complete the visual comparison.
