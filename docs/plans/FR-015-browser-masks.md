# First Firefox mask comparison

## Observable outcome

Open the installed Firefox and Floorp in separate disposable profiles with a private FreeType library. Compare their existing full/auto/grayscale controls with automatic monochrome hinting, grayscale masks, and the accepted mild contrast ramp. Regular Noto Sans at 15px on white is the main problem case. Retain regular, bold, italic, and bold italic on light and dark backgrounds as controls.

This is a mask experiment. Browser layout, glyph placement, and final composition remain Mozilla owners and must be measured separately. The encoded and Mozilla sRGB-preblend choices must keep their actual names. Neither establishes a complete background-aware linear-blending implementation.

## Context and prior plan reconciliation

The user accepts the current Qt result and prioritizes Firefox-based browsers, followed by Electron and Flatpak applications such as Teams for Linux. Existing native-control comparisons favor full/auto hints, grayscale, and whole-pixel positioning, but regular remains blurry and the result suffers on white. No existing Qt implementation decision changes.

The source and native-control evidence is described in [the rendering investigation](../research/non-qt-rendering.md). There is no earlier Firefox implementation plan or pending Plan capture. Other completed engine plans remain outside this prototype.

Git base: `ab206c61228c1f1106284ec904062533a3d55687`. Task branch: `feature/gtk-rendering`, one writable worktree. Local `main` equals `origin/main` at `c481f7980905f92e10c361cc42e72ee7a326e6a2`.

## Product boundary and operating model

One user and one writer use normal local filesystems. All generated sources, builds, profiles, and captures belong under the configured build and result directories. The initial runtime target is Ubuntu 26.04 FreeType `2.14.2+dfsg-1ubuntu0.2`, Firefox 160, and Floorp 12.21.1/Gecko 159.0.1. Preserve the distro's security patches and dynamic HarfBuzz configuration. Debian 13 remains a later delivery target; this prototype must not claim a Debian build that has not been checked.

| Owner | Classification | Required relationship |
| --- | --- | --- |
| Private FreeType load/render code and glyph-slot state | composes | Produce the experimental masks only when explicitly enabled |
| Private build and browser launch tools | composes | Select verified matching sources, libraries, and disposable profiles |
| Local browser fixture, capture, and analysis | composes | Reach actual browser output and distinguish mask, placement, and blending |
| Mozilla shaping, layout, caches, outline translation, and composition | opaque | Keep their behavior; measure results without replacing their decisions |
| Noneligible fonts, normal profiles, host packages, accepted Qt | opaque | Preserve stock behavior and normal launch resolution |
| Full Mozilla GPU blending, Electron, GTK-wide support, Flatpak delivery | deferred | Require separate implementation evidence before promotion |

The normal-use floor is an opt-in comparison that leaves normal applications untouched and supplies independent results for each declared condition. The ceiling excludes system installation, profile migration, global loader changes, sandbox relaxation, browser rebuilds, new automatic blend heuristics, and universal font/renderer claims. I/O faults, hostile changes, concurrent writers, and interrupted-build recovery do not add product behavior.

## Existing owners and smallest implementation

The authenticated distro source has `FT_Load_Glyph`, `FT_Render_Glyph_Internal`, and `FT_Render_Glyph` in `src/base/ftobjs.c`. `FT_Load_Glyph` retains flags in the slot, can render immediately, or can leave an outline for its caller. WebRender translates that outline before its separate render call. Keep this ordering. Do not eagerly render delayed requests or add a second authoritative glyph-state owner.

Add a separate opt-in environment selector for the private FreeType experiment so it cannot apply the Qt profile twice. Select scalable, non-color TrueType faces. Preserve unscaled, no-recurse, no-hinting, advance-only, and bitmap-metrics-only requests. For eligible raster loads, clear incompatible hint-target/monochrome flags and `FT_LOAD_NO_AUTOHINT`, then request forced automatic monochrome hinting without embedded bitmaps. The opt-in profile overrides the caller's auto-hinter preference. Preserve FreeType's existing face and transform restrictions on the hinter.

For an eligible outline render, use grayscale output and apply the optional mild ramp to the new gray bitmap once. Repeated rendering of an existing bitmap must not apply contrast again. Immediate `FT_LOAD_RENDER` and delayed public render calls must both work. Use existing retained load flags and outline/bitmap state rather than adding persistent slot state.

The private builder produces an unchanged-source control and a patched library with identical features and source identity. Pin and verify the source archives authenticated through the distro index. Record source, patch, configuration, library hashes, ABI identity, and notices. The launcher uses explicit separate profiles and private library paths only in its child environment. It must not change normal browser profiles, installed packages, or persistent Flatpak overrides.

The browser fixture includes the problem regular face, actual bold/italic combinations, a small set of independent size/scale/origin contrasts, CFF/color controls, and ordinary shapes. Keep Mozilla enhanced contrast disabled. Measure gamma-disabled encoded output and gamma-0 Mozilla preblend independently. Actual raw browser glyph evidence is required; the earlier pass-through load trace alone is insufficient. Test-only instrumentation may observe the final private-library bitmap without replacing load, outline translation, render, or composition.

## Authoritative source-clause inventory

The local source packet is the exact Ubuntu FreeType source, exact Firefox source stamp, accepted Qt patch/reference tests, the user requirements above, and the rendering investigation. Direct composing-owner expansions are limited to glyph-slot clearing and the called font/render owners. Each clause below has one disposition.

| Clause | Disposition | Boundary |
| --- | --- | --- |
| Preserve accepted Qt and record font, size, scale, polarity, placement, and blend | mapped | B1 |
| Private profiles/libraries and generated data in configured output directories; preserve normal host state | mapped | B1 |
| Opt-in scalable non-color TrueType eligibility; preserve CFF/color/bitmap-only faces | mapped | B2 |
| Forced auto-hinter, monochrome hint target, no embedded bitmap | mapped | B3 |
| Normal grayscale raster output and optional 32..223 mild ramp | mapped | B3 |
| Independent unmodified-FreeType masks and analytic blend reference | mapped | B3 |
| Immediate and delayed render entry points | mapped | B4 |
| Caller outline translation must occur before delayed rasterization | mapped | B4 |
| Retained slot flags and slot reuse must not leak or double-apply treatment | mapped | B4 |
| Preserve non-raster request classes and FreeType hinter restrictions | mapped | B5 |
| Actual Firefox and Floorp output, not only component or sampled-load results | mapped | B6 |
| Page text and browser controls are separate observations | mapped | B6 |
| Measure device placement separately and preserve later ineligible/ordinary drawing | mapped | B7 |
| Compare encoded and Mozilla preblend against the actual-background linear oracle | mapped | B8 |
| Mozilla enhanced contrast differs from the mild ramp; keep it disabled | mapped | B8 |
| Exact-source paired build, dynamic HarfBuzz, source/modification/license notices | mapped | B9 |
| FreeType warns that mono hints plus grayscale can look unattractive | non-boundary | Human evaluation remains necessary |
| Full Mozilla background-aware GPU blend implementation | deferred | Separate engine work |
| Electron, Teams, GTK-wide support, Flatpak, and Debian delivery certification | deferred | Separate roadmap owners |

## Boundary inventory and Scenario Proof

| Boundary | Condition and contrast | Entry points and required oracle | Scenarios |
| --- | --- | --- | --- |
| B1 | Private stock/control/candidate launch versus normal launch resolution | Real launcher through process exit; library/profile identity and protected-state fingerprints | S1 |
| B2 | Enabled eligible TrueType versus off, CFF, color, bitmap-only | Public FreeType load/render; stock-equivalent bytes, format, bearings, and advances for excluded cases | S2, S3 |
| B3 | Auto-mono grayscale/mild versus normal-hinted gray and binary output | Public FreeType load/render; exact independent masks, gray intermediate pixels, and one mild ramp | S2, S4 |
| B4 | Immediate versus delayed rendering, translated outline, repeat render, then next load | One causal slot sequence; independent translated mask, stable repeat, independent next glyph | S4, S5 |
| B5 | Raster request versus preserved non-raster flag classes | Public load entry; stock-equivalent non-raster state and render suppression | S6 |
| B6 | Candidate versus native controls in each installed browser; page versus chrome | Real launcher, actual private raster and final captures; separate results for page and headed controls | S7, S8 |
| B7 | Integral versus fractional origin with other factors fixed | Actual page, raster, and final capture; independently located origin and unchanged neighbor regions | S9 |
| B8 | Same foreground over complementary versus other background; each gamma mode separately | Actual browser captures; independent encoded/actual-background-linear predictions and residual errors | S10 |
| B9 | Unmodified and patched exact-source builds with same features | Real build entry; hashes, configuration, public ABI, dependencies, license and modification acknowledgement | S11 |

| Scenario | Discriminator and minimal contrast | Complete production path and terminal oracle | Planned command |
| --- | --- | --- | --- |
| S1 | Launch mode/profile identity; same executable and local page | Launcher → loader/profile selection → actual browser output → exit; private identity and unchanged protected state | `python3 tests/browser_masks_test.py --case all` |
| S2 | Opt-in then mild state independently; glyph with different mono/normal gray masks; an otherwise identical `NO_AUTOHINT` request must still select the forced-auto reference | Load → retained outline → render → bitmap; independent exact mask, mode, bearings, metrics | `python3 tests/browser_masks_test.py --case freetype` |
| S3 | Actual face format/color/scalability; each exclusion against its own stock result | Load → original format owner → render/result; bytes, format, metrics unchanged | `python3 tests/browser_masks_test.py --case freetype` |
| S4 | Only immediate-render flag changes | Public load with `FT_LOAD_RENDER` → internal render → bitmap; gray result equals explicit independent delayed reference | `python3 tests/browser_masks_test.py --case freetype` |
| S5 | Outline translation, second render, then next glyph in one slot | Load → caller translate → render → repeat render → next load/render; translated reference, stable repeat, fresh next-glyph reference | `python3 tests/browser_masks_test.py --case freetype` |
| S6 | Only load-purpose flags change | Public load → dependency normalization/hinter gate → returned slot; preserved requests equal stock | `python3 tests/browser_masks_test.py --case freetype` |
| S7 | Candidate versus native-control library with scene fixed, in each browser | Launcher → actual font/load → browser outline processing → final private render → browser composition → page capture; raw mask oracle plus separate final-pixel result | `python3 tests/browser_masks_test.py --case all` |
| S8 | Known browser-control label, distinct from page text | Headed disposable launch → actual chrome text/raster → native window capture; control-specific result or explicit unresolved coverage | `python3 tests/browser_masks_test.py --case all` |
| S9 | Minimal integral/fractional origin pair; fixed geometric markers | Page layout → browser placement → candidate raster → final capture; measured origin/mask and stock-equivalent later CFF/color/solid regions | `python3 tests/browser_masks_test.py --case all` |
| S10 | Same foreground on two backgrounds; gamma mode changed in separate run | Actual page → private raw mask → optional Mozilla preblend → composition → capture; encoded and actual-background-linear errors reported separately | `python3 tests/browser_masks_test.py --case all` |
| S11 | Patch presence only, source/configuration fixed | Real builder → configure → compile/link → private artifacts; hashes, dynamic HarfBuzz, exports, identity, notices | `python3 tests/browser_masks_test.py --case build` |

Use a bounded independent condition set: Noto Sans regular 15px light is the baseline; change true style, dark polarity, one nearby effective size, and 125% scale independently. Include a no-ink space, repeated successful early rows followed by a changed style/background, and every declared browser/condition in the report. An empty capture set or missing raw-raster evidence cannot pass. Do not infer synthetic-italic equivalence from an actual italic face. No retry/deadline/recovery lifecycle is introduced; each draw closes at its bitmap or captured image, while repeated slot and browser repaint state must be exercised explicitly.

The browser scenarios share one actual-window capture run through `--case all`. Separate stock controls use each candidate's gamma mode. Gamma affects excluded fonts too, so an encoded stock control cannot isolate the mask change in a preblend candidate. This fixes the test contrast without changing B1..B9.

## Implementation and proof boundary

One atomic subtask, FR-015-A, owns the private mask experiment, builder/launcher, local fixture, independent probe, browser checks, documentation, and notices. It depends on the accepted Qt reference and authenticated unmodified FreeType baseline. Allowed production changes are the FreeType patch and focused private build/launch tools; accepted Qt code and system activation stay unchanged.

Complete the named checks and human-viewable comparisons before full native correctness review from the task base. Run a fresh read-only boundary trace closure before native review. Keep operational results in the ignored task record. A clean review permits a coherent progress commit and the previously authorized private branch push. Browser integration remains Active while visual acceptance and full composition work remain.

## Decision Log

- Use a private FreeType experiment before a full Mozilla rebuild because the installed `libxul` dynamically links system FreeType. Actual child mappings and final-raster evidence must confirm that opportunity.
- Preserve source-level security patches and distro features in both comparison builds; no host package replacement is part of the experiment.
- Preserve unhinted/design-metric requests and retain delayed outlines. A universal FreeType override would change owners beyond the intended raster experiment.
- Keep encoded and Mozilla preblend as explicit diagnostic choices. The user's white-background failure does not authorize a new background-guessing heuristic.
- Regular weight on white is the principal visual test. Clearer bold and italic results cannot conceal a failing regular row.
- Clear `NO_AUTOHINT` only for eligible opt-in raster loads. The two-phase challenge identified its precedence over `FORCE_AUTOHINT`; the explicit forced-auto requirement defines the result. A paired request must distinguish this preference from the preserved non-raster and face/transform restrictions.
- Prior-art algorithm selection is not reopened: the user already selected the rendering mechanism. Research checks exact framework/source behavior and its integration boundaries.
