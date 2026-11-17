# Accepted D with compact-feature darkening


## Outcome and reconciliation


Compare the exact accepted D rendering with compact connected-feature darkening. The user selects D with dot fixes and rejects the broader treatments because they make some diagonals too bold. Keep longer connected strokes and W unchanged. Show peak-only and proportional compact intensity so human comparison selects dot strength and softness.

This replaces unfinished SS-6 of FR-021, based on `1ba7c1dde889613cc08c2ae115e70c9b7328d592` on `experiment/font-supersampling`. Prior plan reconciliation: the latest optical decision supersedes the unfinished weighted-stem/crown proposal. Reject its adaptive geometry and broad ridge/bridge lift. Earlier requests for weighted endpoints and H corrections do not override the newly selected exact D geometry. Retain the existing raw weighted target only for compact-feature intensity. The final preset product remains deferred. Completed checkpoints remain unchanged in Git.

This correction removes the broad processing and reuses D plus the existing compact-component mechanism. It adds no selector, dependency, state, recovery path or public CLI option.

## Owners and supported model


The native exporter composes CLI capture, exact D, compact-feature treatment, saved masks and images. A minimal mask-only helper composes positive-component selection and intensity. Existing weighted target calculation is reused unchanged. Native tests, portable retained inputs and the experiment guide compose the supporting edits. Restore concentration/profile helpers and their self-check to the Git base. They, provider/capture/layout, old supersampling CLI, production C++ and application integrations are opaque. Keep their direct regression controls.

One user and one writer use normal filesystems and the configured ignored build/results roots. No service, concurrency, retry, cache or recovery behavior is added. Decisions receive only coverage bytes and bitmap width. No font, glyph or coordinate exceptions are permitted. Retained data uses portable filenames and hashes. Other families, weights, sizes, general connected-stroke repair, preset adoption and deployment remain deferred. The user's suggestion about remaining weak strokes motivates this bounded trial. It does not authorize a new broad weak-subcomponent or crown selector.

## Design and decisions


Keep `python3 -B tools/native_stems.py --record FREETYPE_BUILD_JSON`. Use four columns: A untouched native 1× MONO-gray, D unchanged accepted rendering, F D plus compact peaks, G D plus proportional compact intensity. Explicit letters avoid confusing these treatments with rejected B/C/E. Use Noto Sans, Nimbus Sans, Inconsolata Nerd Font, Arial and Hack Regular at exactly 8, 10, 11 and 12pt. Retain all 95 ASCII records, full specimen, both polarities, encoded blend, native geometry and whole-pixel spacing. Export 40 native sheets and 20 grids in one gallery. Grids show H, i, n, m, 8, W, colon and exclamation at every requested size.

D is precisely the committed near-tie concentration followed by connected profiles and native corner-fringe selection. Call unchanged base helpers. No new stem targeting, join repair, bridge/ridge darkening, geometry-pair lifting or fringe-role machinery runs. A and D must match immutable source/provider controls for every record. Preserve the historical Display12 raw fixture and exact D output.

Calculate T with the unchanged coverage-weighted mean of the strongest quarter of raw positive pixels, including cutoff ties and existing integer rounding. Empty input gives zero. Find every positive 8-connected component in frozen D. Only bounding boxes at most 3×3 qualify. The component peak, membership, eligibility and proportional source all come from frozen D. If its peak is below T, F raises every tied peak to T. G scales every positive component pixel by T/peak with integer rounding and max-merges against D. If peak is at or above T, leave the whole component unchanged. Never concentrate a dot into a winner, fill zeros, borrow support across gaps or cascade proposals. Every pixel outside eligible compact components remains exactly D. Long or large connected components stay D even if weak.

Pin independent expectations before implementation. Regular10 i retains D's eight 240/60 stem rows, its 3/0 tail and blank gap. Its dot is 202/66 in D, 220/66 in F and 220/72 in G. Noto, Inconsolata and Hack require positive dot witnesses at both 8pt and 10pt. Arial's full dots remain unchanged. Identify all 20 dot regions independently, including connected Nimbus8 without assuming a blank separator. Require W, V and Y to remain byte-identical to D throughout this requested matrix.

A synthetic 2×3 component of three 144/124 rows, separated from four 255 references, has T=255. Legacy D fits its rows to 240/28. F gives 255/28, G gives 255/30. This distinguishes frozen-D scaling from raw scaling, which wrongly produces a 220 fringe. Export that case through the same CLI treatment and diagnostic grid. Also save eligible/tied, saturated, disconnected and minimally oversized contrasts as portable synthetic diagnostics. Independent numeric expectations must precede runtime edits. Fixture data is diagnostic input, never an algorithm exception.

Decision Log: preserve D exactly because the user prefers it. Delete rejected broad processing instead of tuning its diagonal side effects. Reuse whole positive components, rather than selecting weak subsets inside long strokes. This guarantees unchanged larger connected geometry and tests whether the same rule helps other small marks. Keep raw T for consistency with the dot treatments just viewed. Peak-only F isolates strength from G's proportional softness. No production adoption follows automatically.

## Boundary inventory and Scenario Proof


Every mapped row uses `python3 -B tests/native_stems_test.py --record FREETYPE_BUILD_JSON`. It invokes the real provider/exporter through masks, crops and grids. Synthetic contrast records are built-in retained diagnostics and traverse the same treatment function through the real CLI. Pure numerical checks supplement that composed path. The pipeline is synchronous and has no retained work or reopening events.

| Boundary and source | Discriminator and contrast | Required path and terminal oracle |
| --- | --- | --- |
| B-CD-1: latest exact D choice; native controls | D versus F/G on a changed dot; all records including later distinct specimen glyphs. | Real CLI → unchanged base concentration/profile → saved D masks/crops. Immutable `1ba7c1d` recipe and independent provider A match all 1900 records, geometry, flags, advances and historical diagnostics. |
| B-CD-2: latest dot fixes; existing compact rule | Unsaturated compact versus saturated, tied peaks, blank gap and minimally oversized component. A duplicate-prefix component list followed by a later distinct eligible component. | CLI → frozen D positive components → F/G → masks/grid. Exact independently pinned synthetic masks and selected sets. All 20 dot regions checked, six positive Noto/Inconsolata/Hack 8/10 witnesses, full Arial identity and connected Nimbus8. Tails/support remain exact. |
| B-CD-3: existing weighted dot endpoint and softness | Empty/one reference, cutoff ties followed by distinct reference. F peak-only versus G proportional. Already fitted compact component versus raw. | CLI → raw weighted T → frozen D → complete F/G → saved pixels. Independently derive cutoff/numerator/denominator/T. Exact Regular10 i and 240/28→255/28 or255/30 overlap fixture. No processed target, raw rescaling, cascade or unsupported pixel. |
| B-CD-4: latest diagonals too bold; bounded remaining-light trial | Eligible small component versus the nearest component exceeding width or height by one. W/V/Y across the actual matrix. | CLI → whole-component gate → F/G → masks/crops/grids. Every ineligible pixel stays D exactly. Pin oversized/disconnected contrasts and later eligible component. Actual W/V/Y remain D in every font/size. Long weak strokes are explicitly not corrected. |
| B-CD-5: retained matrix, images and portability | Complete five-family/four-size inventory, repeated prefix then distinct/final record, correct versus swapped source/method identity. | Real Fontconfig/provider → 95 records/case → native layout → 40 sheets/20 grids and retained diagnostics. Independent properties, genuine families, spacing/space advance, exact cells/labels/previews/crops/polarities and complete current contributor hashes. Public fixtures contain no personal paths. Earlier supersampling CLI and installed sources remain unchanged. |

Source dispositions: latest D preference and supersession of rejected profiles/crowns map to B-CD-1/4. Dot fixes and generic connected compact mechanism map to B-CD-2. Retained weighted target/softness map to B-CD-3. W and broader remaining-light suggestion map to B-CD-4's bounded trial and explicit deferred long-stroke repair. Earlier matrix/specimen/native control requirements map to B-CD-1/5. Native images, storage and repeatability map to B-CD-5. Opaque base helpers/provider/earlier commands/installed renderer have direct controls in B-CD-1/5. New broad connected-stroke algorithms, final presets and deployment are deferred. Human optical selection, tests, review and branch commit/push are non-boundary delivery requirements. No unresolved contract gap remains.

## Delivery boundary


One atomic candidate owns native orchestration, compact-only helper, focused tests/fixtures and experiment docs. Restore rejected optional-helper changes to the base. Run the named native check and both documentation checks. Reuse the retained supersampling receipt only when its contributing sources match the base and tested hashes. Finalize docs/roadmap before fresh B-CD-1 through B-CD-5 trace and native full review against `1ba7c1d`. Clean review permits branch progress commit/push. Keep FR-021 Active pending optical selection. Do not merge main, release or deploy.
