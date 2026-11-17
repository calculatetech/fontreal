# Gentle edge lift for the local reference


## Outcome and reconciliation


O is the user's preferred general treatment. L fills weak details usefully, especially for white-on-black terminals, but adds jaggies. Compare exact O/L with two gentler uses of the existing S edge proposals. Use both parentheses as the main jaggy controls, with i, 8, ! and W for detail, taper and diagonal checks. Human inspection determines whether either trial improves L.

SS-9 starts at `8caba95bc396957394b63e5040963d822ccde008` on `experiment/font-supersampling`. Prior plan reconciliation: completed SS-8 and its contracts remain in that commit's `docs/plans/FR-021-supersampling.md`. The latest user feedback resolves its optical question in favor of O and promotes a separate L smoothing experiment. Only unfinished optical scope changes. Keep the SS-7 reference mathematics and all existing focused/matrix commands unchanged. No production adoption is authorized by this experiment.

## Product boundary and smallest implementation


Add one retained-input driver `tools/pixel_reference_smoothing.py --source-manifest MATRIX_MANIFEST` and its direct check `tests/pixel_reference_smoothing_test.py`. Read an approved SS-8 matrix. Reuse its own glyph records, frames, advances and source relationships. Do not capture, compile, rasterize or hint measured glyphs again. Header and grid labels can use the existing image-font drawing. Use existing native composition and sheet helpers without changing them. Source artifacts remain unchanged. Write a separate timestamped directory below the ignored `results/pixel-reference-smoothing` root.

The new driver owns source association, the two fixed trial formulas, numerical records, native focus strips, specimen sheets, parenthesis grids and the final manifest. The new check owns independent arithmetic and image reconstruction. The experiment guide owns commands and limitations. This plan owns the current design, and the roadmap owns lifecycle state.

Existing O/L/S generation, references, native D, provider/probe/Oracle, shared layout/composition, old exporters and old checks are opaque and byte-unchanged. The new numerical calculation accepts only L/S coverage arrays. It cannot receive font names, glyph identities or coordinates. Source selection and labels belong to the driver.

One user and one writer use normal local filesystems and existing ignored storage-backed roots. Input is the fixed approved genuine Regular matrix: Noto Sans, Nimbus Sans, Inconsolata Nerd Font, Arial and Hack at 8, 10, 11 and 12pt, both polarities, all ASCII 32–126 per condition. Preserve every owed record, including empty space with positive advance. No arbitrary collection, new size/style, dependency, cache framework, service, retry, concurrency, recovery, hostile-import handling, application restart or installed-state writer is added.

## Research and decision


Question: can a smaller amount of the existing bounded fringe lift soften L's hard transitions while retaining all of its useful core filling? FreeType defines glyph masks as alpha coverage, not display brightness. The experiment therefore operates on coverage before composition. See [FT_Render_Glyph](https://freetype.org/freetype2/docs/reference/ft2-glyph_retrieval.html#ft_render_glyph) and [bitmap coordinates](https://freetype.org/freetype2/docs/glyphs/glyphs-7.html). The retained masks provide the mechanism evidence. For example, Arial 11pt left parenthesis has a core changed from132 to238 beside an unchanged125 neighbor. Full S raises that neighbor to225, adding substantial extra ink.

Choose fractional existing edge proposals as the smallest first trial. Whole-mask blur changes the accepted base, spreads or removes coverage, and confounds detail preservation. The challenger independently proposed attenuation and spatial redistribution of L's additions. Defer those formulas because they reduce valued core additions. This first trial leaves every L core exact, which also distinguishes it from merely weakening L. Global phase optimization or contour following needs evidence beyond this bounded study.

This is a reversible amplitude comparison on an existing mechanism, not an open or costly architecture choice. The NeuroArxiv pre-flight does not qualify because it is one small trial using retained data. No arXiv result or production performance claim is implied.

## Trial and artifact contract


For each pixel let e=S−L, using the unchanged saved masks. Require equal lengths and integer values with 0≤L≤S≤255. T is `L+(e+2)//4`, a quarter of the existing edge increment with nonnegative half-up rounding. U is `L+(e+1)//2`, half of that increment. Compute both from frozen L/S once. No result feeds another result, pixel or glyph. No clamp, average, spatial blur, new phase search or replacement reference is introduced.

Thus L≤T≤U≤S. Existing primary cores retain L exactly because S already leaves them unchanged. Zero support and pixels with no S edge proposal retain L. Every increase stays within the existing S/E reference bound. A one-byte increment rounds to zero in T and one in U. A two-byte increment rounds to one in both. These are declared hypotheses, not proof of reduced jaggies. Extra fringe coverage can still make strokes heavier.

Show A/D/O/L/T/U in forty native overview sheets. Each column includes a clearly separated native `() () i8! W` focus strip and the complete unchanged source specimen. Keep original body crops and native spacing exact. Existing sheet helpers can make the body; add the focus strip without resampling. Keep actual point-size labels and complementary polarities of identical masks.

Export numbered O/L/T/U coverage grids for both parentheses in all twenty conditions. Keep these forty diagnostic grids outside the arrow-scroll overview gallery. Native previews must not be resized. Record the original coverage, changed fringe values, coordinates, labels and method identities. All 1900 source glyphs owe trial records. Preserve source manifest/case/record/font/contributor hashes and the complete image graph. Public documents and retained evidence use portable names and hashes. The ignored output can reference its retained source through relative paths.

## Boundary inventory


The source packet is the latest two user messages; the exact SS-8 source/guide/plan/roadmap and retained matrix; current numerical O/L/S generation; native family/point definitions; shared native composition; and `CONTRIBUTING.md`. The independent challenger proposed a different smoothing hypothesis, not a new user requirement. Its B-LS-2/S-LS-2 are refined below to the coordinator's selected fixed trial before implementation. All other supported boundaries are retained.

| Boundary/source | Invariant and nearest contrast | Entry points, oracle and scenarios |
| --- | --- | --- |
| B-LS-1: user O/L preference | Exact, visibly identified O/L controls versus silently replaced or relabeled controls. | New CLI; exact source control bytes and body crop pixels, full labels; S-LS-1/4. |
| B-LS-2: useful detail and jaggy trial | Frozen quarter/half S−L edge increments versus weaker L, full S, altered core values, different rounding or cascading. | New CLI; independent complete arithmetic, hand-readable witnesses, all core/zero/no-proposal identities and own-reference bounds; S-LS-2/4. |
| B-LS-3: requested glyph controls | Both parentheses plus i/8/!/W versus one missing curve or collateral control. | New CLI; exact focus sequence and both numbered grid inventories, native image reconstruction; S-LS-4. |
| B-LS-4: retained source/provenance | Own approved records, hashes and geometry in a fresh ignored result tree versus reused first-case data, stale associations, recapture or overwrite. | New CLI; complete source-to-record-to-image graph, unchanged source files and fail guards at opaque native-work boundaries; S-LS-1/3/5. |
| B-LS-5: complete fixed collection | All twenty ordered conditions and all95 ASCII per case versus early limits, repeated prefixes or glyph-only association. | New CLI; exact identities through Hack12, 1900 records, forty sheets, forty grids and unique paths; S-LS-3. |
| B-LS-6: native visible truth | Correct size, mask, polarity and placement versus resampling, fixed12pt, method swaps or automatic ranking. | New CLI; independently reconstructed native bodies/focus strips/sheets/grids and their coordinates; S-LS-4. |
| B-LS-7: preserved entry points | Separate opt-in driver versus changed old focused/matrix behavior. | Existing focused/matrix CLIs remain opaque; exact source-bound SS-8 receipts, rerun only affected paths; S-LS-5. |
| B-LS-8: generic experiment | Same fixed numerical function for all records, output-only writes and no deployed selection versus metadata exceptions or adoption. | New CLI; all-record arithmetic, generic inputs, bounded artifact graph and honest docs; S-LS-2/5. |

Source dispositions: O general preference maps to B-LS-1. L weak-detail filling, rejected full S and the selected fixed fractional-edge hypothesis map to B-LS-2. Parentheses and the four collateral controls map to B-LS-3. Approved own-case inputs, geometry, hashes, relative source relationships, ignored roots and portability map to B-LS-4. Five families/four points/all ASCII map to B-LS-5. Both polarities/native100%/native placement map to B-LS-6. Preserved existing invocations map to B-LS-7. Generic/no exceptions/no new scope dimensions/no installed-state writes map to B-LS-8. Existing C/E/O/L/S/reference/probe/native mechanisms are opaque. Human optical judgment, normal one-writer use and required checks are non-boundary obligations. Production adoption, caching, other smoothing mechanisms and performance integration remain deferred. No inherited conflict or unresolved public result remains.

## Scenario Proof and checks


The named composed check is `python3 -B tests/pixel_reference_smoothing_test.py --source-manifest MATRIX_MANIFEST`. It invokes the real new CLI on the actual retained SS-8 matrix, then independently checks the complete saved results. It cannot replace source association, trial calculation, layout, composition or writers. Pure arithmetic examples supplement this path. This synchronous trial has no retained work or reopening events.

| Scenario | Discriminator and nearest contrast | Complete path and terminal oracle |
| --- | --- | --- |
| S-LS-1: retained source and exact controls | Same glyph codes from different case identities, not just counts. | CLI→source validation→own case load→trials→fresh manifest/images. Compare all A/D/O/L bytes, native frames/advances, body crops and source relationships. Rehash source files after execution; no old artifact changes. |
| S-LS-2: exact edge amplitude | Actual S−L values 0,1,2,odd and larger increments; primary versus fringe; quarter versus half/full S and weakened L. | CLI→frozen L/S→T/U→saved records/native crops. Independent divmod rounding checks every pixel. Literal L125/S225 gives T150/U175; actual parenthesis witnesses reach those relative effects. Core values are exactly L; zeros and no-proposal values remain unchanged. Bounds/no overflow and record-order independence supplement complete real-path proof. |
| S-LS-3: complete collection | Repeated ASCII prefixes followed by different later families and Hack12; empty space retains advance. | CLI→all cases/glyphs→distinct records/artifacts→manifest. Exact ordered20 identities/95 codes each,1900 outputs, all own-case arithmetic and complete file inventory. |
| S-LS-4: visible optical evidence | Actual size/method/polarity, holding each case's placement fixed. | CLI→source geometry/trials→native focus/body composition→polarity→sheets/grids. Independent scalar composition checks all native pixels. Exact O/L body crops match source PNGs. Reconstruct all forty sheets and forty grids, every coverage cell/coordinate/heading/preview and six-control sequence. Human100%comparison separately judges jaggies and weight. |
| S-LS-5: no implicit adoption or native work | New explicit command versus old entry/activation/native-capture owners. | New CLI→retained readers→numerical calculation→fresh results only. The same real-entry check installs fail guards only at opaque compilation, native-capture and Oracle boundaries. External process guards allow genuine Fontconfig for labels but reject compile/probe launches. Retained loading, trials, composition and writers remain real. Successful complete output proves those prohibited boundaries are not reached. Exact unchanged old producer/check hashes and valid SS-8 receipts separately preserve old commands. No import/callee writes installed selection. If an opaque owner changes, run its original composed check before review. |

Finalize guide/plan/roadmap, then run `python3 -B tests/docs_test.py --self-test` and `python3 -B tests/docs_test.py`. Use current source and test hash bindings. Do not repeat unchanged native/provider/application suites.

## Delivery boundary


SS-9 is one atomic candidate for the new retained-input driver/check, experiment guide and current plan/roadmap. Finish the declared check, source-bound opaque reuse and 100% GUI inspection before fresh B-LS-1..8 trace and native full review against8caba95. Clean review permits a branch progress commit/push. FR-021 remains Active for optical assessment. No main merge, release, profile activation or production performance claim belongs to this candidate.
