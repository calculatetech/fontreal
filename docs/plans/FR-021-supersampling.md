# Supersampling: scalar 4× and stem darkening


## Outcome and reconciliation


Produce a simpler native-pixel stock gallery. Every row starts with untreated 1× and Fontreal 1×, followed by paired 4× options with FreeType stem darkening off and on. Remove all LCD and LCD_V settings, filter choices, RGB/BGR variants and their unused capture, decoder, compositor and test paths. Preserve the actual V glyph and the complete ASCII specimen.

Base: `60fed5e8ffe83d04838e1ebc5c1343aebdfe7af1`. Branch: `experiment/font-supersampling`. This is subtask SS-3 of FR-021.

Prior plan reconciliation: the latest user direction supersedes SS-2's stock subpixel inventory, row layout, 2× reference and deferred boolean darkening experiment. Source: `60fed5e8ffe83d04838e1ebc5c1343aebdfe7af1:docs/plans/FR-021-supersampling.md`, SS-2. Status: superseded only in that scope. Reason: the user prefers 4× and explicitly removes the subpixel settings. Replacement: this SS-3 scalar on/off study. The delivered SS-2 source and evidence remain in Git and existing results; do not preserve an unused legacy rendering mode in current code.

Carry the default SS-1 A–G command, all original numerical behavior, frozen selected processor and three regular fonts forward. The authoritative SS-1 implementation is `ff63a7f448f77338f594156d858a02aefea95fe8`. Its full retained capture/mask/placement and 378 native-crop comparison stays in the focused check. Preserve app-support decisions, README recommendations, installed rendering and pending FR-016. Human optical selection remains pending.

The owned paths are `tools/supersampling.py`, `tests/supersampling_probe.cpp`, `tests/supersampling_test.py` and the experiment guide. Paired stock FreeType, its builder, fonts, core and adapter are supporting opaque owners. Deployment, custom darkening amounts, new kernels, per-font tuning, new algorithms and automatic winners remain deferred. The supported model is one local user and writer, normal filesystems and the existing storage-backed ignored build/results roots. There is no service, retry, recovery or asynchronous reopening owner.


## Design and provider contract


Keep the existing `--stock4x` entry point and default SS-1 selection. The replacement stock inventory is unhinted grayscale; native and automatic NORMAL, LIGHT and MONO hint targets rendered in grayscale; unhinted/native/automatic monochrome sources; and the existing available distinct TrueType interpreter and old CFF-engine comparisons. Generate every retained setting in both stem-darkening states. Native TrueType can ignore this property; do not fabricate a pixel change or remove the pair.

Keep Noto Sans Display Regular, Liberation Mono Regular and Nimbus Sans Regular, every integer 8–16pt, 96 target DPI, both backgrounds, full pangram, numbers, punctuation, controls and ASCII 32–126. Original native advances, whole-pixel placement, wrapping and encoded blending stay fixed. All new 4× rows are untreated by Fontreal and use exact rounded 4×4 area means on the baseline-anchored grid. Retain negative bearings, nondivisible support, raw grayscale/packed-mono bitmap rows and native mask bounds. New stock output is scalar grayscale.

For every capture, set `no-stem-darkening = !stem_darkening` on both `cff` and `autofitter` through `FT_Property_Set`, before opening a fresh face and loading glyphs. Read both effective values with `FT_Property_Get`. Each variant starts from the same font input and explicit driver state. Keep default darkening parameters unchanged. Record requested state, set/get success, effective booleans and relevant driver identity. FreeType's [property contract](https://freetype.org/freetype2/docs/reference/ft2-properties.html#no-stem-darkening) covers the auto-hinter and Adobe CFF driver, not native TrueType hinting. Its [darkening curve](https://freetype.org/freetype2/docs/reference/ft2-properties.html#darkening-parameters) depends on raster stroke width, so large 4× strokes can receive zero extra width. Equal pixels remain valid evidence.

Group each sheet into panels containing the two genuine 1× references and one or two paired 4× settings. Every panel starts with A and B, including later rows. Use clear Off/On labels and no 2× reference in this stock gallery. Keep at most six columns, one sheet per font/point/background and all 54 sheets in one folder for Gwenview arrows and native 100% viewing. Every declared method must occur in at least one panel.

Use the current probe, reducer and exporter. Delete superseded LCD functions and tests rather than add another framework or CLI selection. The fixed API mechanism does not select an open architecture; the arXiv gate does not apply.


## Boundary inventory and scenario proof


The exact named check for each runtime row is:

    python3 -B tests/supersampling_test.py --record FREETYPE_BUILD_JSON

It runs both real CLI selections. Every boundary row below is its same-numbered scenario. A complete proof reaches the saved native PNG or manifest through the real entry, not only a component call.

| Boundary | Required meaning and contrast | Production path and terminal oracle |
| --- | --- | --- |
| B-SD-1 | Retained scalar settings versus removed LCD/LCD_V/filter/RGB/BGR families. The glyph V remains. | Stock CLI through real probe, catalog and gallery. An independent exact source/method inventory permits only NORMAL/LIGHT/MONO targets and grayscale/mono render modes. No removed metadata, labels or unused implementation paths remain. ASCII still includes code 86. |
| B-SD-2 | Every row has genuine A/B references and its own 4× alternatives; contrast the first and a later different row. | Real stock export through row assembly and saved sheet. Every panel starts with A/B; every other method has scale 4 and an explicit darkening state. Independently specified membership and exact native crop-region bytes detect omitted or substituted later references. |
| B-SD-3 | Actual Off/On property selection versus reversed labels, unchanged defaults or prior-state leakage. | Stock CLI through per-capture Set/Get, fresh face, real load/render, raw records, reduction and native crop. Check actual effective booleans before glyph capture. Independent provider references for native CFF and forced-auto NORMAL at 4× must match both labeled outputs exactly. A low-resolution diagnostic can establish a real provider darkening witness when 4× pixels are identical. Never require a fabricated difference for native TrueType or large strokes. |
| B-SD-4 | Each retained stock choice has its intended flags, render mode and driver state; aliases/unavailable settings are honest. | Probe selection through captures and manifest. Independently specify enum/flag and option sets, query actual availability/effective values and check driver-specific labels. Only current non-LCD choices are included. |
| B-SD-5 | Actual 4× raw coverage becomes untreated native-grid area reduction, not enlarged native text, packed-bit resizing or selected processing. | Real provider through scalar decoder, reducer, fixed placement and both encoded polarity PNGs. Independently decode raw mono/gray, accumulate global-coordinate block means and compose exact pixels. Check ppem, positive outline structure and matching native-normal geometry against original native4 under equivalent darkening state, plus negative bearings and nondivisible support. Pre-core equals final on every new stock row. Retain an untreated-versus-selected witness. |
| B-SD-6 | Complete condition/glyph/option output versus truncation or reused later records. | All font/point/method loops through masks, crops, 54 sheets and final manifest. Independent exact sets cover all 27 cases, every paired method and all ASCII. Check blank space with advance, repeated AAAAB, undisplayed Z, later distinct conditions, hashes, native sizes and exact sheet crops. |
| B-SD-7 | Unchanged SS-1 and fixed references versus leaked properties or changed processing. | Default CLI and stock A/B through original capture/reduction/core/composition. Run the frozen ff63 exporter privately under the same provider/fonts. Compare all original geometry/outlines/coverage/advance/mask/placement records and 378 native crop hashes, plus stock A/B against those references. No source changes to core, adapter or protected product files. |
| B-SD-8 | Isolated native experiment versus deployment, obsolete documentation or automatic acceptance. | Both real CLI paths through verified provider/source/font identities and configured roots. Check artifact provenance, no deployment calls and no protected-owner diff. Portable guide and roadmap reflect the new scalar study; FR-021 stays sole Active. Static prose/lifecycle checks are not runtime trace rows. |

Source-clause dispositions: the latest removal instruction maps to B-SD-1, repeated references to B-SD-2 and the stem-darkening request to B-SD-3. The user's explanation about 4× is motivation, not an automatic winner. Retained non-LCD stock choices and honest capabilities map to B-SD-4. Prior fixed geometry/coverage/layout maps to B-SD-5, complete fonts/sizes/specimen and provenance to B-SD-6, strict SS-1 preservation to B-SD-7, and ignored outputs/native viewing/human choice to B-SD-8. CONTRIBUTING's portable docs and prescribed tests remain validation rules; its ignored-output constraint maps to B-SD-8. Installed state, core, paired builder, app decisions and font recommendations remain opaque. Custom amounts, new algorithms and other application/platform tasks remain deferred. The retired SS-2 RGB obligations have no current consumer.


## Independent darkening reference and delivery


Reuse the existing frozen-reference mechanism. For the darkening oracle, take the immutable SS-1 probe from `ff63a7f` in a temporary private build tree. Omit only its fixed CFF default override so documented `FREETYPE_PROPERTIES` supplies the on/off booleans before initialization. For the forced-auto reference, replace only its fixed NO_AUTOHINT flag with FORCE_AUTOHINT. These are explicit controlled reference inputs, not candidate code or a replacement for a production hop.

Compile those tiny reference probes with the existing toolchain and exact stock provider. Use native CFF Nimbus Sans and automatic Noto Sans Display at 8pt. For both on/off states, retain and compare the complete 4× glyph geometry and raw bytes with corresponding real stock-CLI captures; independently reduce and compose the saved crops. The same reference's native-size capture supplies a real lower-density darkening witness if the 4× pair is equal. Label that diagnostic as a provider-control check, not another gallery treatment. Verify actual provider identity. Do not change darkening parameters to manufacture an effect. Remove temporary reference files after their last use.

Finalize the guide and roadmap before review. Run both prescribed documentation checks. Inspect native samples, all sheet layouts and verify Gwenview 100% viewing. A fresh read-only verifier closes the frozen B-SD inventory against exact test/source bytes and results before native correctness review of the full SS-3 candidate against `60fed5e`. One clean full review permits commit/push on the experiment branch. Keep FR-021 Active for the next human assessment; do not deploy or select a profile.
