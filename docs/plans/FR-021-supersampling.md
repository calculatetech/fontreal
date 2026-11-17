# Broader per-pixel reference comparison


## Outcome and reconciliation


Show A native raw, D accepted baseline, O coherent alignment and L local references for five genuine Regular fonts at 8, 10, 11 and 12pt. Use Noto Sans, Nimbus Sans, Inconsolata Nerd Font, Arial and Hack. Show the complete existing specimen on both backgrounds at native image resolution in one gallery. O is the user's leading candidate. L remains a comparison because its apparent sharpness needs assessment across more conditions. S adds too many jaggies and does not belong in this broader gallery.

SS-8 starts at `ff5a8fe9e7508e932935b094104b3f349c5f928a` on `experiment/font-supersampling`. Prior plan reconciliation: retain the exact SS-7 numerical reference and overlay contracts from that commit's `docs/plans/FR-021-supersampling.md`. This task changes the comparison scope, not the rendering mathematics. Preserve the existing focused command and completed SS-6 native matrix. The user's O/L feedback supersedes only the unfinished optical comparison. Production adoption, smoothing and cache integration remain deferred.

## Product boundary and smallest implementation


Add an explicit `--matrix` selector to `tools/pixel_references.py`. The existing no-option `--record FREETYPE_BUILD_JSON` command stays the focused Noto Sans Regular 12pt study. Its six overview methods, three numbered grids, synthetic diagnostics and three-repeat benchmark retain their behavior. Generalize only necessary setup, per-condition capture and native sheet composition in the existing exporter. Compile once for the matrix. Use the existing five-family and four-size definitions. Do not spawn twenty focused commands or multiply analytic diagnostics and benchmarks across the matrix.

The exporter owns selection, actual Fontconfig admission, capture association, file output and the manifest. Extend `tests/pixel_references_test.py` with an explicit matrix check. Reuse its independent numerical oracle and native image reconstruction. Add only small portable retained pins for the Noto Sans 12pt overlap. The experiment guide owns commands and limits. This plan owns the accepted design. The roadmap owns lifecycle state.

The numerical helper `tests/pixel_reference_profiles.py`, SS-7 numerical fixtures, native-stems treatments, shared provider compilation/capture/decoding/layout, native probe, public FreeType Oracle and production rendering are opaque and unchanged. Existing focused diagnostics and benchmark are preserved consumers. No font, character or coordinate exception reaches numerical processing.

One user and one writer use normal local filesystems and existing ignored storage-backed build/results roots. Requested fonts and a valid paired stock-provider record are available. Reject unrelated family fallbacks and matches without Regular in their style aliases. Accept genuine Arial's multilingual Regular aliases. No configurable matrix collection, dependency, cache framework, service, concurrency, retry or recovery path is added.

## Reference and image invariants


Every condition captures all ASCII 32–126 at its requested point size and 96 DPI through the paired provider's native MONO hints with grayscale coverage. Retain actual outlines, bearings and advances. A exactly reproduces the native outline raster. D comes from the unchanged native-stems treatment. Each condition passes its own numerical inputs through the unchanged SS-7 same-outline 4× reference and overlay kernel. Do not reload the face at larger DPI or change phase search, thresholds, axes, rounding, offset eligibility or reference bounds.

Show exactly A/D/O/L in matrix overview sheets. Retain numerical audits for all 95 glyphs per condition. Each condition uses its own whole-pixel advances, existing specimen wrapping and actual point size in composition. Both backgrounds use identical coverage bytes with complementary encoded composition. Save native crops and paste them into sheets without resampling. Labels name the genuine family, Regular style and requested point size. Place all forty overviews in one arrow-scroll gallery. Keep detailed numerical files outside that gallery.

Retain actual provider/font/source identities, capture/input/mask relationships, crop coordinates and file hashes. Every condition has distinct paths. Store outputs under the configured ignored results root. Public documents and retained pins contain portable names and hashes, not personal paths. Human inspection at 100% image zoom determines optical preference. The local envelope can still add excess ink; this comparison does not resolve that SS-7 limitation or automatically select a winner.

## Boundary inventory


The source packet is the latest O/L feedback; SS-7 at the base above; `tools/pixel_references.py`, its check and helper; `tools/native_stems.py` family/point definitions and admission pattern; the shared exporter/probe/Oracle; `CONTRIBUTING.md`; and the current experiment guide/roadmap. Retained SS-7 and prior native-matrix artifacts establish input identities and overlap, not a new rendering policy.

| Boundary/source | Invariant, contrast and required oracle | Entry points and scenarios |
| --- | --- | --- |
| B-MX-1: latest feedback and comparison scope | Exactly A/D/O/L in the broader gallery, versus six methods or automatic adoption. Exact method and visible-column inventories. Installed selection owners remain unchanged. | Matrix CLI; S-MX-1/4. |
| B-MX-2: native-stems family/point definitions | Every requested family/size owes its own result. Complete ordered twenty-condition inventory, including later families and Hack 12pt, versus totals or a repeated first case. Unique paths and ninety-five records per case. | Matrix CLI; S-MX-1/3. |
| B-MX-3: genuine Regular admission | Actual family and Regular membership, including Arial aliases, versus unrelated fallback or non-Regular style. Genuine matrix plus explicit rejection through the real CLI with only Fontconfig metadata substituted. | Matrix CLI; S-MX-2. |
| B-MX-4: SS-7 native controls and capture | Actual paired provider, target size, outlines, bounds, advances and A/D versus reused or wrong-sized inputs. Independent raster, decoding, D and capture-property oracles for every case. | Matrix CLI; S-MX-3. |
| B-MX-5: unchanged generic kernel | Own inputs and exact SS-7 O/L, versus changed kernel, metadata exceptions or stale association. Frozen helper hash, independent arithmetic and exact retained Noto 12pt overlap. | Both CLIs; S-MX-3/5. |
| B-MX-6: complete native specimen/images | Full specimen at actual point size, correct method and complementary polarity, versus scaling, fixed 12pt layout, swaps or omissions. Independent crop/sheet reconstruction, labels and placement sequence. | Matrix CLI; S-MX-4. |
| B-MX-7: existing focused interface | No selector retains six-method focused export, grids, diagnostics and benchmark. Explicit matrix selection has the new fixed collection. Execute the original composed focused check independently. | Both CLIs; S-MX-5. |
| B-MX-8: provenance and portability | Every case references its own current hashed inputs/images under ignored roots, versus cross-case or stale relationships. Exact complete artifact graph and documentation checks. | Both CLIs; S-MX-1/3/4/5. |

Source dispositions: fixed scope and exclusion of S map to B-MX-1. Each family/size maps to B-MX-2. Genuine-family/Regular and alias membership map to B-MX-3. Paired provider, native target, complete ASCII, geometry and A/D map to B-MX-4. Generic unchanged processing maps to B-MX-5. Full specimen, native composition, size labels and both polarities map to B-MX-6. Existing focused invocation maps to B-MX-7. Current hashes, distinct paths, source associations, ignored roots and public portability map to B-MX-8. Detailed SS-7 reference mathematics, numerical fixture, focused diagnostics/benchmark, prior native matrix, shared owners and production paths are opaque. New weights/sizes, R/S matrix columns, matrix grids, repeated analytic/performance studies, smoothing, cache integration and deployment are deferred. Human optical judgment, normal one-writer use, required checks and branch delivery are non-boundary obligations. No inherited specification conflict or undefined public result remains.

## Scenario Proof and runnable checks


Use `python3 -B tests/pixel_references_test.py --record FREETYPE_BUILD_JSON --matrix` for S-MX-1 through S-MX-4. It invokes the real matrix CLI once for the genuine complete run. Synthetic admission checks replace only the opaque Fontconfig response, using real retained provider tuples. Do not replace capture, processing, numerical, layout or artifact writers. The matrix is fixed and nonempty; an empty source glyph with positive advance still owes a result. This synchronous exporter has no retained work or reopening event.

| Scenario | Discriminator and nearest contrast | Complete path and terminal oracle |
| --- | --- | --- |
| S-MX-1: complete collection | Ordered family/point identity, including repeated-family prefixes followed by distinct later families. | CLI selector→all twenty captures→records/artifacts→manifest. Exactly twenty unique conditions, forty overviews, 160 native crops and ninety-five ASCII records per condition. Complete manifest-to-file inventory. |
| S-MX-2: actual admission | Keep the real font filename; vary only returned family/style tuples. Accept Arial's actual Regular aliases; reject unrelated family and missing Regular. | CLI→Fontconfig response→real validation→admission or explicit terminal error. Genuine run proves compatibility. Labeled synthetic responses prove rejection predicates without a completed mislabeled matrix. |
| S-MX-3: numerical association | Same codes across sizes/families, empty space with positive advance and retained Noto Sans 12pt overlap. | CLI→paired-provider validation→native capture→decode/snapshot→unchanged D→unchanged references/offsets→saved records. Independent metadata/raw/A/D, all high rasters and every reference/offset through existing scalar arithmetic. Pin complete overlap and helper hash. |
| S-MX-4: visible truth | Actual size, method and polarity, holding the condition's placement constant. | CLI→records→specimen layout→point-specific composition→polarity→crops→sheets. Independently reconstruct all 160 crops and forty sheets. Check complete placements, dimensions, exact pixels, labels, boxes, unique paths and hashes. No resampling. |
| S-MX-5: preserved focused entry | No selector versus explicit matrix selector. | Existing focused CLI→actual source, diagnostics, benchmark and image owners→original artifact graph. Run `python3 -B tests/pixel_references_test.py --record FREETYPE_BUILD_JSON`. Preserve current numerical pins and semantic assertions; durations vary while stage counts, associations and byte payloads do not. Bind unchanged owners to source hashes. |

Run both documentation checks after finalizing guide/plan/roadmap: `python3 -B tests/docs_test.py --self-test` and `python3 -B tests/docs_test.py`. Bind results to exact contributing sources. Unchanged broader suites use existing exact receipts rather than another run. GUI inspection supplements these checks.

## Decision Log and delivery boundary


O leads because the user judged its balance better than S. L remains because one font/size cannot establish a general winner. The broader gallery therefore changes only scope. Preserve the focused study for diagnostic and performance evidence instead of duplicating it across the matrix. Reuse the existing exporter and kernels; no new rendering architecture or research decision is needed.

SS-8 is one atomic candidate for exporter selection/composition, focused/matrix checks, portable overlap evidence and experiment documentation. Depend on SS-7. Finalize substantive docs and the active roadmap before fresh B-MX-1..8 trace closure and one full native review against the SS-8 base. Clean review permits branch progress commit/push. FR-021 remains Active for optical qualification. No main merge, release, application restart or installed-state change belongs to this candidate.
