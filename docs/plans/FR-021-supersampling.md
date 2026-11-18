# V2 native rendering


## Outcome and reconciliation


Publish an installable V2 with O NORMAL as the general profile and K3 NORMAL as the per-user alternative. Preserve the approved formulas while further optical experiments use a separate line. The user accepts the current appearance: stock is competitive and sometimes preferred on light backgrounds, while the prototype is clearly preferred on dark backgrounds. Do not claim universal improvement or add background-dependent tuning.

Base: 3f07596aa0707f8d647c299ec8d2c88eff481e7e. Task branch: feature/fontreal-v2, an isolated writable branch in the existing checkout. Local main and origin/main match at task start. Prior plan reconciliation: completed SS-12 and its exact comparison contract remain at that base commit in this path. This revision replaces only its unfinished optical assessment and next work. Historical producers, commands, numerical meanings and installed V1 remain unchanged during the first checkpoint.

V2 names the accepted rendering generation. Select the source version and immutable release tag when the installable scope is fixed. A numerical checkpoint alone is not a V2 release.

## Subtasks and owners


SS-13 ports the accepted numerical kernel to native C++. New owners are src/fontreal_v2_coverage.cpp and src/fontreal_v2_coverage.h, with tests/v2_coverage_probe.cpp and tests/v2_coverage_test.py providing direct proof. The experiment guide owns usage, this plan owns decisions, and docs/roadmap.md alone owns lifecycle state. The checkpoint contains these sources and their affected prose. Its review and local commit boundary is the complete new kernel and proof since the task base.

SS-14 integrates the proven kernel into existing renderer and per-user activation owners. O and K3 must work through ordinary application launches, with the existing stock escape and working data preserved. Each actual renderer must supply its own aligned outline reference. Define that subtask's complete owner packet and Scenario Proof before its implementation. A host library mapping alone is not application coverage.

SS-15 prepares the versioned release, repeatable instructions, accurate comparisons and release notes. Preserve the light/dark tradeoff. Complete cumulative final review and publication gates before a release. These later subtasks require their own accepted preflight within this same plan. No installed change or release follows SS-13 alone.

## SS-13 product boundary and model


The supported model is one synchronous native call, ordinary owned grayscale buffers, a supplied FT_Memory allocator, and genuine retained native NORMAL source data. The source policy is native hints, grayscale, interpreter 40, darkening off and no automatic hints or bitmap strikes. The same numerical rule applies to every font and character.

The accepted Python owners remain opaque and byte-unchanged: tools/native_stems.py::treatments, tests/stem_core_test.py::concentrate, tests/stroke_profiles.py::refine, tests/pixel_reference_profiles.py, tools/pixel_references.py::process and tools/arial_coherence.py::local_coherence. Their reference rasters, source capture and shaping owners remain opaque. The new composition from registered numerical inputs through D, references, O/K3 and returned bytes is in scope. Keep src/fontreal_coverage.cpp and its header, existing producers, patches, builders and activations byte-exact to the base.

Do not port unused weight fitting, compact F/G, K5 or diagnostic branches. Do not add a runtime subprocess, Python dependency inside applications, cache, service, font exception, new hinting rule, polarity heuristic, package change or settings interface in SS-13. Do not run unrelated application qualification. CONTRIBUTING.md owns test policy.

## SS-13 interface and numerical contract


Add a hidden C entry with FT_Memory, a mutable FT_Bitmap raw mask, a const registered FT_Bitmap four-times raster and an explicit O/K3 enum. Both inputs are grayscale with 256 levels. The four-times source has dimensions 4*(raw.width+6) by 4*(raw.rows+6). Its origin is three native pixels outside the original raw left/top. Raw and high inputs independently support the ordinary signed pitch representation. Preserve both bitmap metadata records, high input bytes, raw row padding and external positions, bearings and advance.

Calculate D on the original raw frame using concentrate(raw, raw, near_ties=True), then refine with connected=True and select corners. Internally use the accepted two-pixel native padding and three-pixel high-source padding. Use all 25 phase footprints, eight-connected components, squared-sum scores, exact integer rounding and deterministic distance/dy/dx phase ties. O changes only accepted primary pixels through max(D,C). K3 uses the same-component radius-one neighborhood and axis restrictions, then adds the accepted rounded half of S-minus-L fringe coverage.

Write only the original raw pixel area, after the entire calculation succeeds. Prove that zero-registering this result into the accepted padded frame equals every reference byte. Frozen support rules leave padding zero. Empty raw input is a no-op whose normalized reference remains the four-by-four zero frame. The harness preserves the positive space advance outside the kernel.

Return zero for success, one for allocation failure and two for invalid arguments. Use checked dimensions and pitch arithmetic, valid format/mode and required pointers. Reject malformed registration without changing either input or metadata. Temporary storage belongs to the supplied FT_Memory owner and is released before return. No per-glyph state survives a call. Do not add injected allocation-failure or environment-failure matrices.

Exact native D observation is mandatory from the same real native-entry call that produces the checked final output. A passive compile-time test observer can copy D through const access. It must not recompute D separately or change numerical behavior. Compile the ordinary kernel too and compare its real final outputs with the observed build. Do not add a public D mode.

## Decision Log


The user accepts O NORMAL for the general V2 choice and K3 for personal use. Existing stock rendering remains a useful comparison and recovery choice. Further tuning must not silently alter the accepted release target.

This is a port of fixed numerical definitions and an existing raster mechanism. No open algorithm selection or new prior-art study is needed for SS-13. A registered four-times bitmap is the explicit opaque source seam; no numerical stage inside the new kernel is replaced by Python or a test callback.

The two-phase independent challenge identified two proof requirements. First, final maxima can hide a wrong D value, so the same-call D observer is mandatory. Second, positive packed inputs cannot prove signed pitch behavior. Use a small successful representation set with negative/padded raw and high inputs independently, rather than a corpus-wide product.

## Boundary inventory and source dispositions


| Boundary | Source and required contrast | Entry and scenarios |
| --- | --- | --- |
| B-V2-1 | Accepted native D versus legacy gain/winner/weighted processing, omitted near ties or omitted connected refinement. Native treatment, concentrate and refine owners. | Native entry; S-V2-1. |
| B-V2-2 | Complete eight-connected component scoring and primary O overlay versus local/prefix/four-connected selection or changed ties/rounding. Pixel reference owners. | Native O entry; S-V2-2. |
| B-V2-3 | Same-component radius-one K3 with allowed axes and ceil-half fringe versus O/K5, forbidden phases or omitted/floor-half fringe. Coherence and overlay owners. | Native K3 entry; S-V2-3. |
| B-V2-4 | Original NORMAL frame, aligned four-times source, actual Qt raster and padded equivalence versus MONO/union/nominal-size substitution, stale empty output or shifted geometry. Native and Qt reference owners. | Both modes; S-V2-4/5. |
| B-V2-5 | Numerical-only generic processing and explicit profile choice versus identity exceptions or a selector that always uses one profile. User requirement and README. | Both modes; S-V2-5/6. |
| B-V2-6 | Supplied allocation ownership, independent signed strides, unchanged guards/metadata and atomic output versus stale state, unowned storage or incorrect row interpretation. Existing native ABI pattern and this interface. | Both modes; S-V2-5. |
| B-V2-7 | Isolated new kernel and truthful acceptance versus activation, retuning, old-source changes or a claimed installed V2. Current scope and user feedback. | Proof CLI; S-V2-6. |
| B-V2-8 | Complete source-bound corpus/profile obligations versus correct-prefix or borrowed output. Retained NORMAL and native Qt owners. | Proof CLI; S-V2-6. |

All near-tie, run-vote, protection, connected-anchor, proposal-conflict, interrupted-channel, step and corner clauses map to B-V2-1. Component membership, full phase collection, footprint rounding and primary selection map to B-V2-2. Local axis restrictions, phase ties, donor eligibility and odd half-edge rounding map to B-V2-3. Native source policy, source raster equality, own-frame registration, CFF distinctions, real Qt sizing, empty geometry and both stride signs map to B-V2-4/6. Generic identity handling maps to B-V2-5. Ordinary allocation balance, input validation and repeated-call independence map to B-V2-6. Preservation and accurate optical acceptance map to B-V2-7. Complete conditions, glyph identities, repeated values, spaces and shaped Qt glyphs map to B-V2-8.

Unused diagnostics, K5, installed integration, release and future tuning are deferred. Old numerical/reference implementations, source capture, shaping and deployed V1 are opaque. Human optical acceptance and test-policy procedures are non-boundary obligations. No unresolved contract gap remains for this checkpoint.

## Scenario Proof


Use one exact named command:

    python3 -B tests/v2_coverage_test.py --record FREETYPE_BUILD_JSON --normal-manifest NORMAL_MANIFEST --qt-manifest QT_MANIFEST

Use the complete retained 20-condition, 1900-row NORMAL corpus and the eight-condition, 784-row native Qt source set. Keep duplicate polarity rows and their identities. Qualify the supplied stock provider against both sources for independent 1x/4x raster checks. Load original raw masks, hinted outlines and registered high sources, rather than historical display unions. The proof CLI compiles the new ordinary and observed native entries and calls them for every source row and both profiles. No in-scope numerical hop is replaced.

A tiny, explicitly labeled numerical fixture can supplement a local arithmetic contrast absent from the genuine corpus. It does not establish font geometry or provider compatibility and cannot replace any genuine source proof. In particular, diagonal support must expose an incorrect four-connected O selector even when genuine final bytes happen to match.

| Scenario | Discriminator and minimal contrast | Complete path and required terminal oracle |
| --- | --- | --- |
| S-V2-1 | D eligibility/votes and connected refinement. Include active near-tie and refinement witnesses, zero-vote/strong protection and rejected proposals. Final max can hide D errors. | Real native entry to passive same-call D observation to final O/K3. Compare every observed D byte with the frozen independent reference and its padded equivalence. Require output witnesses exposing legacy or omitted-stage alternatives. |
| S-V2-2 | O component completeness, connectivity, deterministic phase ties, rounding and primary membership versus local, truncated or four-connected choices. | Real raw/high inputs to native D, complete component scoring and O overlay to actual returned bitmap. Compare full padded O with independent scalar references. Retain non-vacuous terminal-byte contrasts, including a prefix whose later pixels alter the result. |
| S-V2-3 | K3 radius, component and axis restrictions, plus odd half-fringe rounding, versus O/K5, forbidden phases and omitted/floor-half fringe. | Real native D through references, local scoring and fringe addition to returned K3. Compare all bytes with the independent scalar K3 oracle. Record active/protected and odd-delta terminal witnesses. |
| S-V2-4 | Own NORMAL source geometry, CFF distinction and Qt 10pt resolved to 13 pixels versus historical MONO/union or nominal fractional points. Empty versus intervening nonempty calls. | Source qualification to independent 1x/raw and 4x registration to both native modes. Exact original bitmap, padded result, zero support and preserved metadata/advance. Space stays empty and normalized to the accepted four-by-four zero frame. |
| S-V2-5 | Explicit O/K3 choice, ordinary buffer ownership, signed stride and previous-call state. | Same real native entry on packed inputs, one asymmetric genuine glyph with padded negative raw/positive high and positive raw/padded negative high, both modes. Hold numerical pixels constant. Exact output, same-call D, metadata, row guards, immutable high source and balanced FT_Memory counts. Repeat a glyph after another profile/glyph and space. Invalid mode/format/pitch/high dimensions reject with status two and no input mutation. No injected allocation failure. |
| S-V2-6 | Complete declared input/profile set and generic rules versus borrowed prefix data, identity dispatch or changed historical state. | Real proof CLI to actual ordinary/observed native calls to per-row results and isolated output. Check independent condition/glyph/profile inventories through the last case, source hashes, all expected calls and source/input preservation. Relabel identical numerical input and require identical bytes. Compare ordinary and observed output. Inspect the bounded write graph and truthful V2 acceptance docs. |

Reuse exact source-bound retained receipts only for opaque compatibility. New numerical composition and all current output require this named check. The kernel and proof are synchronous with no retained-work reopening event. Do not invent a new corpus import API to test accounting.

## Checks and checkpoint boundary


Keep compiled output below build/v2-coverage and scientific records below results/v2-coverage. Use the existing storage-backed roots. Finalize affected prose, then run the named check and the documentation checks required by CONTRIBUTING.md:

    python3 -B tests/docs_test.py --self-test
    python3 -B tests/docs_test.py

Before the SS-13 checkpoint commit, complete fresh boundary trace closure and native review of its complete candidate since 3f07596. Current results belong in the ignored task evidence. Keep FR-021 active while native integration and release remain. This checkpoint changes no installed app and makes no application coverage or performance claim.
