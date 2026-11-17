# Native MONO-gray baseline and conservative stem cleanup


## Outcome and reconciliation


Show native 1× MONO hinting with grayscale rasterization beside two conservative stem-cleanup trials and a separate weighted-darkening comparison. Preserve softer native coverage outside selected straight runs. Move existing coverage between competing pixels without adding ink. The user selects this as the new experimental baseline, not an installed profile.

This is SS-4 of FR-021. Base: `29d3fec5c929bad39e60d3ffbb23aeeb263169a3`. Branch: `experiment/font-supersampling`. The latest user choice supersedes pending optical selection and the active 4× direction in `29d3fec:docs/plans/FR-021-supersampling.md`. Preserve the original A–G and stock4x commands, their output contracts and installed selected processing. Keep the original immutable reference at `ff63a7f`. Earlier source and specifications remain in Git. The preceding local pixel audit motivates this choice but is not an input required to reproduce the new command.

The new exporter, native MONO capture and optional concentration trial compose this task. Existing exporters, installed core/adapter, provider/builder, fonts and app integrations remain opaque. Deployment, production changes, shaping, new kernels, font/character exceptions, generalized curve or exact-tie repair and automatic optical winners remain deferred. Supported model: one local user/writer, normal filesystems and the existing ignored storage-backed build/results roots. No service, retry, recovery or cache is needed.


## Design and decisions


Add `tools/native_stems.py --record FREETYPE_BUILD_JSON`. Reuse `tools/supersampling.py` compilation, scalar decoding, layout and native composition. Add probe selection `--native-mono` and an optional `stockCapture` scale argument defaulting to its existing 4. The new capture uses scale 1, 96 DPI, NO_AUTOHINT, NO_BITMAP, MONO target, NORMAL grayscale rasterization, interpreter 40 and FreeType stem-darkening ON, matching the selected baseline. Record effective properties and actual provider identity. Preserve existing probe selections and metadata.

Column A is untouched baseline. Column B uses existing `tests/stem_core_test.py::concentrate(raw, raw, width)` native-area cleanup. Column C adds an optional `near_ties` argument, default false. Columns B and C run no bridge, gain, floor, profile-corner processing or weighted-stem darkening. Both retain isolated positive pairs, total 192–384, outside neighbors at most 32, stability within eight of the first pair, at least three positions, overlap rejection and already-strong protection. Column C alone removes the difference-at-least-16 guard. Choose one core side for its whole run by summed original coverage. A zero vote leaves the run unchanged. Do not alternate winners along the run.

For B and C, retain the existing peak `min(240, total - 1)`. Transfer only when this increases its core, with a positive fringe. In B and C, every changed pair and glyph keeps its exact coverage sum and nonzero support. Other pixels, dimensions and bearings stay identical. Conservation preserves ink quantity, not individual alpha values or the coverage centroid. Stable segments in curved glyphs can qualify numerically. Do not claim semantic curve detection or guaranteed perceived softness.

Use the same three regular fonts and complete ASCII 32–126, specimen, integer 8–16pt and both polarities at 96 DPI. Noto Sans Display and Liberation Mono supply TrueType controls. Nimbus Sans supplies CFF. Column D starts from C and adds the newest user-authorized weighted darkening. Reuse the existing weighted target calculation from `tests/weighted_stroke_profiles.py::darken(raw, raw, width)`: the coverage-weighted mean of the strongest quarter of positive baseline pixels, including cutoff ties. For each accepted C pair, raise its core only to `max(current core, target)`. Scale its adjoining fringe by the same core ratio, rounded to the nearest integer. Use the frozen C mask for all proposals. Selected pairs are disjoint. This deliberately adds ink, with a proportional blend lift instead of isolated core hardening. It changes no pixels outside C pairs and preserves support. Conservation applies to B/C, not D. Actual perceived jaggies remain a human comparison.

All columns share the MONO baseline's advances, placements, wrapping and encoded blend. Export 54 native sheets and numbered H, n, m, 8, W, colon and exclamation grids at 11pt and 12pt. Save masks, changed pairs, geometry, properties, source/font/provider hashes, crops, sheet boxes and cell coordinates in fresh ignored results directories. Open one Gwenview gallery at 100% for human assessment.

Decision Log: the user selects native 1× MONO-gray for its geometry and softness. Interpret “without touching coverage” as no added ink, since cleanup necessarily changes individual alpha values. Compare unchanged conservative cleanup with a bounded near-tie extension to expose its effect. Zero-vote runs remain unchanged to avoid arbitrary lateral choices. An equal pair within a nonzero-vote run follows that run’s supported winner. This reuses the existing stable-run concentration mechanism, rather than choosing an open architecture or new systems algorithm, so the arXiv gate is not applicable. Existing default concentration stays byte-identical. Production adoption and broader font/weight validation follow human assessment.


## Boundary inventory and scenario proof


The new exact runnable check is:

    python3 -B tests/native_stems_test.py --record FREETYPE_BUILD_JSON

It invokes the real CLI, provider, capture, cleanup and final PNG export. Synthetic masks supplement the corpus as labeled algorithm checks. They do not replace an in-scope capture or export hop.

| Boundary | Discriminator and contrast | Path and required oracle |
| --- | --- | --- |
| B-NS-1 | Native MONO-gray versus NORMAL hints, binary raster or reduced 4×. | Real CLI through probe to baseline PNG. Compare all glyph geometry, advances and bytes with an independent provider reference from immutable `29d3fec` probe source with only stock DPI/scale changed to 96/1. Check target, render, flags, ppem, properties and provider. Retain a real NORMAL-versus-MONO witness. |
| B-NS-2 | Balanced redistribution versus core-only boost or full selected processing. | Real CLI through concentration to masks and native crops. Independently check exact pair and glyph totals, support, geometry and unchanged unselected values. Exact synthetic transfers supplement actual affected glyphs through the complete path. |
| B-NS-3 | Existing guard versus near-tie selection and coherent winner. | Shared concentration and real B/C outputs. Independent fixtures isolate difference 16/below 16, nonzero/zero run vote, changing per-row preference, length, sum bounds, outer guard, stability, strong protection and overlap. Check exact outcomes and conservation. Require a real near-tie witness in saved masks and crops. A three-row mask with rows `[172,164,0,0,164,172]` must leave B unchanged and produce C rows `[240,96,0,0,96,240]`, proving both disjoint runs and their opposing winners. Also check `[172,164],[168,168],[172,164]`: its local tied pair follows the nonzero run vote. |
| B-NS-4 | Generic mask handling versus identity rules or changed layout. | Real CLI through cleanup, baseline placement and native composition. All treatments keep advances, geometry and layout. Transposed/reflected nonambiguous fixtures produce transformed expected bytes. No identity-specific selector exists. |
| B-NS-5 | Complete output versus truncation or reused later records. | Real CLI loops through manifest and saved files. Independent exact sets cover 27 conditions, four methods and ASCII. Check empty space with advance, repeated AAAAB then B, undisplayed Z, later distinct conditions and both polarities. |
| B-NS-6 | Exact displayed values versus scaling, wrong polarity or labels. | Real CLI through masks, independent composition, crops, gallery and grids. Sheet regions equal native crop bytes. Cell backgrounds and numeric labels match exact coverage and method identity. Check dimensions, hashes and encoded inversion, then inspect native images and grids. |
| B-NS-7 | New experiment versus regression of existing commands or core. | Run `python3 -B tests/supersampling_test.py --record FREETYPE_BUILD_JSON` through both old CLIs and immutable reference. Preserve all original captures/masks/layout, 378 crops and stock4x assertions. Run the concentration self-check and compare its default with immutable `29d3fec` on the complete new raw corpus. No core/adapter/integration diff. |
| B-NS-9 | Weighted core-only hardening versus proportional blend lift, and lower targets versus actual lifts. | Real CLI through C pairs, existing raw weighted-target computation and D masks/crops. Independently compute the strongest-quarter target and exact pair scaling from frozen C. Synthetic fixtures distinguish no lift, core lift with fractional rounding and an unselected neighbor. Require a real exported fringe-lift witness. A raw mask with three selected `[100,92]` pairs and detached positive references `[255,200,200,200]` has ten positive pixels. Including cutoff ties must give target 216, not 221, and lift C core 191 to D core 216 with exact rounded fringe output. D never reduces coverage, changes support or touches an unselected pixel. |
| B-NS-8 | Isolated reproducible experiment versus unverified inputs or deployment. | New CLI validates actual provider/source/font hashes and writes only configured ignored roots. Check complete provenance. Portable guide states commands, conservation, exclusions, centroid movement and optical limits. FR-021 remains sole Active. Static docs/lifecycle checks are separate from runtime trace. |

Source dispositions: baseline choice maps to B-NS-1, cleanup without added coverage to B-NS-2, undecided stems and bounded extension to B-NS-3, generic handling and fixed geometry/layout to B-NS-4, full fonts/sizes/specimen to B-NS-5, native viewing/grids to B-NS-6, separately authorized weighted darkening and blended-edge lift to B-NS-9, retained commands/profile to B-NS-7 and ignored outputs/provenance/portable docs to B-NS-8. Softness motivates human assessment, not an automatic winner. Test policy and branch delivery authorization are validation/delivery rules. App support, builder, provider and font owners remain opaque. Production adoption, new kernels, identity exceptions and generalized exact-tie repair remain deferred.


## Delivery boundary


Owned changes: new exporter/check, isolated probe selection, optional concentration trial, existing experiment guide, the weighted-comparison wrapper, this specification and FR-021 text. The existing weighted helper remains unchanged. Do not change installed state or expand app support.

Finalize guide and roadmap. Run both named runtime checks, the concentration self-check and both prescribed documentation checks. Record operational results only in the existing ignored task result. A fresh read-only trace verifier closes B-NS-1 through B-NS-9 before native full correctness review against `29d3fec`. One clean full review permits branch progress commit/push. Keep FR-021 Active pending optical selection. No merge, release or deployment follows automatically.
