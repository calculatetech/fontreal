# Supersampling comparison

## Outcome and boundary

Produce native-pixel font sheets that compare the accepted Fontreal rendering with rendering at twice and four times the resolution before reduction. Human judgment chooses whether any candidate merits further work. No candidate becomes the installed profile.

Base: `cce894b1af20a2daabdaf647abba8d07ef60025c`. Task branch: `experiment/font-supersampling`. Preserve the current app-support decisions and README font recommendations. The user explicitly prioritizes this experiment next. Keep FR-016 pending, with its existing scope.

The experiment composes a small FreeType probe, a mask reducer and PNG exporter. The stock FreeType provider, font files and unchanged selected coverage processor are supporting owners. Installed libraries, application launchers and the existing comparison viewer are opaque. Deployment, learned reconstruction, new hinting algorithms, per-font exceptions and automatic readability claims are deferred.

The supported model is one local user, one writer, existing scalable fonts, paired private FreeType artifacts, and normal local filesystems. Do not add concurrency, fault recovery, cache management or a service.

## Research and decisions

This is supersampling, rather than reconstruction from a low-resolution image. FreeType already computes outline coverage without ordinary image supersampling. Therefore higher raster resolution with unchanged geometry is a control, not an assumed improvement. See the [FreeType FAQ](https://freetype.org/freetype2/docs/ft2faq.html).

[FreeType transformations](https://freetype.org/freetype2/docs/reference/ft2-sizing_and_scaling.html#ft_set_transform) follow hinting. Use that documented ordering to scale the target-size hinted outline without changing its shape. Contrast it with loading and hinting at the larger physical size. This separates sampling from geometry and size-dependent driver behavior.

Reduce coverage values before color composition. Area reduction uses the rounded arithmetic mean of each complete source block. A separate [Lanczos reduction](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters) tests a sharper kernel and its possible fringes. Apply the frozen coverage processor once at final resolution, not at the larger resolution. Use encoded blending and whole-pixel text placement throughout.

The arXiv preflight is not applicable: the user fixed the inexpensive experimental mechanism, and no costly architecture or new algorithm is being selected. Official API and rasterizer documentation answer the implementation questions.

Seven columns: native grayscale at 1×, current Fontreal at 1×, 2× native hints with area reduction, the same 2× mask with Fontreal, 4× native hints with area reduction and Fontreal, 4× target-size hints with area reduction and Fontreal, and 4× native hints with Lanczos reduction and Fontreal. Only final-resolution masks receive Fontreal correction.

Use Noto Sans Display Regular, Liberation Mono Regular and Nimbus Sans Regular. The last supplies a CFF control. Cover integer 8–16pt at 96 DPI, black on white and white on black. These choices are initial study parameters, not new font recommendations. Use the full pangram, digits, weak-crown and diagonal controls, and common punctuation. Record all ASCII glyphs, including space.

Compose every column with the same target-size whole-pixel advances and line wrapping. Report changes in glyph bounds and normalized advance separately. This is a raster comparison, not a shaping or kerning experiment. Align reduction blocks to the glyph baseline and native pixel boundaries, including negative bearings. Preserve native tight bounds for the accepted reference. Pad filters with zero coverage and retain any genuine output fringe.

Write build data and results beneath the existing configured build and results roots. Produce lossless native-size PNGs, masks, numeric differences and a local provenance manifest. Distinguish untreated FreeType from genuine stock Qt. Use no installed renderer as an unverified reference. Open the gallery in Gwenview at native image zoom for visual judgment.

## Boundary inventory and proof

| Boundary | Source and invariant | Contrast and terminal oracle | Entry and check |
| --- | --- | --- | --- |
| B-SS-1 | User requests actual higher-resolution rendering followed by native reduction. | Larger raster with a constant logical size versus enlarging a finished image or changing point size. Actual provider dimensions, normalized outline coordinates, native output dimensions and exported masks identify the method. | Experiment CLI through probe, reduction and PNG export. Focused test and full gallery generation. |
| B-SS-2 | Existing accepted profile and recommendations stay intact. | Exact native mask followed by the unchanged selected processor versus a retuned or twice-processed reference. Compare with the existing independent scalar reference. Protected source and recommendation files stay unchanged. | Processor invocation and baseline export. Focused test plus protected Git diff. |
| B-SS-3 | Higher resolution must not hide geometry or blend changes. | Target-size hints scaled after loading versus hints recalculated at high resolution. Normalized outlines establish the control. Both use the same placement, coverage-space reduction and encoded blend. | Probe modes through composition. Focused test and saved raw/method metadata. |
| B-SS-4 | All requested sizes, fonts, polarities and characters owe an output. | Space, one glyph, duplicate prefix and later different glyph versus omitted, reused or cropped output. Inspect the complete collection, bounds, hashes, repeated glyphs and exact exported pixels. | Full gallery command and focused test. |
| B-SS-5 | The study must be repeatable and visually judgeable. | Recorded stock provider, font and code identities and native-size PNGs versus an unidentified provider, resized screenshots or installed-profile changes. Numeric data and masks accompany the gallery. Human assessment is separate from numerical assertions. | CLI, manifest and image export. Focused test, visual inspection and opening the gallery. |
| B-SS-6 | User requests an isolated experiment. | Writes under ignored experiment roots versus installed packages, settings or activation mutations. The complete CLI path has no deployment calls. Protected files remain unchanged. | CLI and final source/diff inspection. |
| B-SS-7 | User explicitly makes this the next task; roadmap identifiers stay permanent. | One active FR-021 and pending FR-016 versus a second active task or discarded existing work. | Static roadmap and generated-view check. |

Source-clause disposition: the higher-resolution request maps to B-SS-1; the accepted renderer and current font/app decisions map to B-SS-2; consistent geometry, point units, placement and blend map to B-SS-3; the requested comparison matrix and full specimen map to B-SS-4; native-pixel human acceptance and portable provenance map to B-SS-5. Installed application lifecycles and the existing renderer implementation remain opaque. New deployment and new rendering algorithms are deferred. No open product contract is required to choose ordinary sampling factors or filters for this isolated study.

The focused check must invoke the real experiment entry point. It must compare area reduction with independently computed integer block means, including a negative-bearing case. The target-hint control must preserve outline coordinates after division by the sampling factor. Native Fontreal masks must agree with `tests/selected_profile_test.py::expected_mask`; at least one sample must distinguish identity and repeated processing. The complete gallery must include every requested condition and no blank positive specimen. Space remains a legitimate blank glyph. PNG dimensions and sample crops must retain native pixels, and both polarities must use the same coverage values.

Compare the real exported pre-processor Lanczos mask with an independently assembled zero-padded Pillow reference from its retained high-resolution source. Include a small edge fixture that differs from area reduction and retains filter support beyond the original tight bounds. Compare mask bytes and native-grid bounds before coverage correction, so correction cannot conceal clipped fringes. This is the accepted independent preflight correction.

| Scenario | Boundary, discriminator and contrast | Complete path and required result | Named check |
| --- | --- | --- | --- |
| S-SS-1 | B-SS-1/3: native size versus genuinely larger native-hinted captures and the target-hint control. | Real CLI, actual stock provider, recorded outlines, bitmap sizes, reducer and final exported masks. Target-hint normalized points equal native points; larger native hints are separately attributed. | Focused test invokes the CLI; full gallery generation. |
| S-SS-2 | B-SS-1/3: aligned support versus a negative bearing and a nondivisible source extent. | Real reduction pads the native-coordinate grid, then exports correctly placed masks. An independent integer block-mean oracle and a real negative-bearing glyph detect clipping and origin shifts. | Focused test and recorded mask bounds. |
| S-SS-3 | B-SS-3/5: one fixed condition across methods and opposite polarities. | Shared native layout, distinct raster paths, final coverage and encoded blend reach PNG output. Font identity, target advances, origins and point labels stay fixed. Pixel channels equal coverage or its complement. | Focused test compares real CLI masks, crop pixels and metadata. |
| S-SS-4 | B-SS-4: space, one glyph, duplicate prefix and later distinct glyph; all declared condition tuples. | Complete glyph and condition arrays, composition and output manifest. Space has zero ink and retained advance; repeated glyphs and the final distinct glyph remain present. No early truncation or reused wrong condition. | Focused test plus complete full-gallery manifest audit. |
| S-SS-5 | B-SS-2: unchanged selected processing versus identity, repeated processing or identity-specific rules. | Actual compiled frozen processor receives each final raw mask once. Native baseline equals the existing independent scalar oracle. Identical numerical masks receive identical processing without a font or glyph selector. | Focused test invokes the real processor and scalar reference. |
| S-SS-6 | B-SS-5: native crop versus resized presentation or unsupported visual verdict. | Native mask, encoded image, sheet crop and manifest remain traceable. Crop pixels are unchanged, diagnostics are labeled and original image dimensions are recorded. No automatic winner is declared. | Focused test, complete gallery audit, visual inspection and documentation checks. |
| S-SS-7 | B-SS-6/7: isolated execution versus deployment and lost task priority. | Actual CLI subprocess list and writes use ignored build/results roots. Protected source/recommendation files stay unchanged, FR-021 is sole Active, and FR-016 remains pending. | Complete source/diff and roadmap checks. |

The independent Phase 1 source inventory has these additional explicit dispositions. CONTRIBUTING's portable documentation, provenance and ignored output clauses map to B-SS-5/6. Its targeted-test and documentation-test instructions are non-boundary validation rules; routine deployment obligations remain opaque. README's experimental framing and split-stroke motivation are non-boundary context. Its existing native renderer, Qt captures, earlier diagnostics, app-support states, recommendations and viewer controls remain opaque. README's native-pixel viewing rule maps to B-SS-5. Roadmap point units and condition identity map to B-SS-3/4; human judgment maps to B-SS-5; permanent identifiers and one active priority map to B-SS-7. Its generic-renderer rule maps to B-SS-2. Completed delivery remains opaque; optional curves, other applications, platform work and non-native LCD operation are deferred. The private processor and paired builder APIs remain opaque. Their test adapters and existing raster/blend helpers are non-boundary reuse evidence. These dispositions retain all Phase 1 clauses without promoting the older viewer's pixel-size controls into point-size references.

## Implementation and review

Use a small probe under `tests/` and an exporter under `tools/`. Reuse `tests/selected_mask_probe.cpp` and the frozen coverage source. Accept the existing paired FreeType build record and verify the stock library hash and actual loaded provider. Do not rebuild or change the production renderer for this experiment.

One implementation subtask covers the CLI, supporting probe, focused test, gallery and experiment guide. Its check is `python3 -B tests/supersampling_test.py --record FREETYPE_BUILD_JSON`, followed by `python3 -B tools/supersampling.py --record FREETYPE_BUILD_JSON`. Output is under the configured build and results roots. Run only checks for these new behaviors and affected documentation, in accordance with CONTRIBUTING.md.

Before commit, finish the guide, inspect native-size and enlarged diagnostic images, complete independent boundary trace closure and native correctness review. Keep FR-021 Active while visual acceptance remains pending. Do not publish a winning profile before the user chooses it.

## Decision log

The first study is a separate exporter rather than another installed rendering mode. This keeps the existing approved renderer and all app-support decisions unchanged. Existing FreeType APIs and Pillow supply the experiment. A geometry-locked control is necessary because the provider already calculates pixel coverage. Numerical correctness establishes what each column does; the user decides whether it looks better.
