# Geometry and stroke contrast at 16pt

The latest [Firefox Home comparison](#matched-firefox-home-reference) first matches actual application text before testing weak crowns. The earlier [raw curve-weight comparison](#curve-weight-with-raw-coverage) remains component evidence.

Qt defaults are closer to the source outlines than the original Auto mono + 242 benchmark in this test. That benchmark gives stronger stroke contrast and crisp pixel placement. The current goal retains clarity while making pixel rounding respect the source proportions.

Current comparison sizes are integer requests from 8pt through 16pt. Earlier fractional-point studies below are historical evidence. Device-pixel values describe internal measurements, not current font-size selections. The user now selects fully raw coverage for every tested face and condition, with nearest-50% geometry and encoded blending. This supersedes the earlier continuous ramp and native support floor in the normal browser preset. The earlier trials below remain evidence for explicit diagnostic modes. The inner-hole geometry trials offered no useful improvement.

The comparison covers the same 22 faces and text as the [point-size charts](browser-common-ground.md#selected-benchmark-and-816pt-charts). The desktop uses 96 logical DPI and 100% scale. Both paths rasterize the 16pt request at 21 device pixels. The nominal conversion is 21.333 pixels, but Qt resolves this request to 21. This rounding is shared by both columns.

## Noto Sans explains the visible difference

Noto Sans Regular contains modest stroke contrast in its original design. For the lowercase n, the source upright is thicker than the crown. The table measures the upright at mid-height and the crown at mid-width. Values describe the outline before pixel coverage or blending.

| Geometry | Upright thickness | Crown thickness | Upright/crown ratio |
| --- | --- | --- | --- |
| Original design, scaled to 21px | 1.848px | 1.523px | 1.21 |
| Qt defaults, traced before rasterization | 1.859px | 1.562px | 1.19 |
| Benchmark automatic mono hinting | 2.000px | 0.981px | 2.04 |

![Source contours and hinted geometry for Noto Sans n at 16pt](../images/browser-common-ground/noto-sans-n-16pt-contours-24x.png)

The benchmark amplifies the contrast in this example. It does not simply restore contrast that Qt removed. The thicker upright and thinner crown explain the more expressive appearance. The default outline retains the source design's more moderate relationship. The final raster and blending can alter how uniform either result appears.

The 242 floor does not move contour points. It raises selected pixel coverage after rasterization. This changes apparent weight and edge strength. It cannot restore geometry that the hinting step already changed.

## What the geometry measurements show

The reference consists of the font's original unhinted coordinates, scaled exactly to the common 21px raster size. A local trace captures Qt's actual outlines immediately before rasterization. Native reproduction matches every captured nonempty glyph. The benchmark outlines match the existing point-chart samples.

The metric measures movement of corresponding contour points. For each glyph, it removes the best-fit translation, then calculates root-mean-square displacement. This separates shape deformation from moving the entire letter. The table averages that value equally across the 20 nonempty glyphs in each face. Lower values mean closer contour geometry under this metric.

| Face | Qt default error, px | Benchmark error, px |
| --- | --- | --- |
| Noto Sans Regular | 0.262 | 0.435 |
| DejaVu Sans Book | 0.323 | 0.403 |
| Lato Light | 0.163 | 0.187 |
| Lato Regular | 0.197 | 0.226 |
| IBM Plex Sans Light | 0.148 | 0.212 |
| IBM Plex Sans Regular | 0.248 | 0.276 |
| Liberation Sans Regular | 0.197 | 0.230 |
| Noto Serif Regular | 0.261 | 0.351 |
| DejaVu Serif Book | 0.304 | 0.314 |
| Liberation Serif Regular | 0.105 | 0.201 |
| Hack Regular | 0.202 | 0.437 |
| DejaVu Sans Mono Book | 0.359 | 0.449 |
| Liberation Mono Regular | 0.104 | 0.319 |
| Noto Sans Bold | 0.123 | 0.248 |
| Noto Sans Italic | 0.259 | 0.410 |
| Noto Sans Bold Italic | 0.122 | 0.201 |
| Noto Serif Bold | 0.273 | 0.422 |
| Noto Serif Italic | 0.258 | 0.289 |
| Noto Serif Bold Italic | 0.240 | 0.455 |
| Hack Bold | 0.193 | 0.373 |
| Hack Italic | 0.193 | 0.408 |
| Hack Bold Italic | 0.206 | 0.333 |

Qt defaults have the lower mean error for every tested face. Across individual glyphs, defaults are closer in 344 cases, the benchmark in 93, with three ties. The same face-level conclusion holds when the measurement retains whole-glyph translation. This does not make defaults the better visual result.

## Why the results differ

The observed Qt path loads glyphs with normal hinting and uses grayscale rasterization. The benchmark forces automatic monochrome hinting, then also uses grayscale rasterization. FreeType documents that the mono target applies stronger grid fitting, and that selecting different targets can change outlines. Its default loading path prefers a font's native hinter when available. See the [FreeType hinting target and loading contracts](https://freetype.org/freetype2/docs/reference/ft2-glyph_retrieval.html#ft_load_target_xxx).

Stronger fitting can give solid pixel strokes while changing proportions and stroke contrast. This fits the project's preference for crisp low-density text. The measurements show that the resulting character comes with a geometric tradeoff.

## A nearest-pixel rounding experiment

The user identifies the next requirement: a source crown of about 1.52px must snap to two pixels. Preserve the font's proportions through predictable pixel rounding. The more expressive benchmark shape is a comparison control, rather than the final geometry target.

The FreeType strong-hinting branch rounds horizontal-stroke thickness in the vertical dimension with `(dist + 16) & ~63`. One pixel is 64 units. This changes to the next pixel at a 75% remainder. The monochrome branch for vertical-stem widths uses a 50% threshold. Both branches first apply FreeType's standard-width matching. See [the pinned FreeType source](https://raw.githubusercontent.com/freetype/freetype/VER-2-14-2/src/autofit/aflatin.c).

A private test changes only the vertical-dimension rounding bias from 16 to 32. This uses the same 50% threshold for that branch. It preserves the benchmark's 242 floor, cutoffs, blending, layout, and horizontal fitting. It does not replace the standard-width matcher or fit individual glyphs by hand.

For Noto Sans Regular n at 16pt, the measured crown grows from 0.981px to 1.953px. The upright remains approximately 2px. At the same crown pixel column, raw coverage changes from `[250, 9, 0, 0]` to `[246, 255, 8, 0]`. The test therefore has two strong rows before the floor, with a faint curved edge below. A curved cross-section is not necessarily identical to the detected stem width that the hinter rounds.

![Source design, original benchmark, and nearest vertical-dimension rounding](../images/browser-common-ground/noto-sans-n-16pt-nearest-y-24x.png)

The Noto Sans n upright/crown ratio becomes about 1.02. This is close to the nearest-pixel target of two pixels for each stroke. Its original ratio is 1.21. Pixel rounding still changes geometry, but it removes the earlier ratio of about 2.04.

The point sweep covers 220 conditions from 8 through 16pt, including the 11.25pt reference. Every horizontal control coordinate, contour topology, and Qt layout position remains unchanged. The previously tested 15px Noto Sans i remains byte-identical to the benchmark. At 16pt, the original font-unit, unhinted, and normal-hinting controls also remain unchanged.

On the same 16pt contour metric, the new test improves 12 face averages, leaves nine unchanged, and slightly worsens one. Noto Sans Regular improves from 0.435px to 0.291px. Noto Sans Bold Italic changes from 0.201px to 0.208px. This is a bounded experiment, not a complete solution for font proportions.

| Comparison | White background | Black background |
| --- | --- | --- |
| Six faces at 16pt: defaults, benchmark, and nearest-Y test | [Image](../images/browser-common-ground/nearest-y-16pt-contrast-light.png) | [Image](../images/browser-common-ground/nearest-y-16pt-contrast-dark.png) |
| Noto Sans Regular at 8–16pt: benchmark and nearest-Y test | [Image](../images/browser-common-ground/nearest-y-noto-sans-8-16pt-light.png) | [Image](../images/browser-common-ground/nearest-y-noto-sans-8-16pt-dark.png) |

The [experiment record](../images/browser-common-ground/nearest-y-captures.json) includes the exact parameter change, library hashes, numeric results, image hashes, and checks. The private library retains the original exported API and dependency features. Native raster, floor, overlap, blend, and saved-image checks cover the comparisons. No installed library or application setting changes.

## Smaller points and explicit italic comparisons

The user finds 50% fitting more accurate in more cases, but no candidate meets the full visual target. Keep the earlier 16pt result as a geometry reference. Each sheet shows actual Qt point sizes from 8 through 16pt, plus the 11.25pt reference. Italic and bold italic have dedicated sheets.

The left column uses the original 75% horizontal-stroke fitting rule. The middle uses the 50% rule. Both candidates retain the same 242 floor, coverage cutoffs, and linear blending. The right column is stock Qt with Fontreal disabled. It retains Qt's own coverage, origins, and blending. All three use the same font and Qt layout. The percentage describes width fitting before rasterization. It does not describe a coverage cutoff.

For Noto Sans Regular, the 75% and 50% columns are pixel-identical at every tested size below 16pt, on both backgrounds. Returning to 75% cannot improve those rows. Other faces enter the affected range at different sizes. Noto Sans Bold Italic changes at 9, 10, 11, 11.25, and 16pt. Noto Serif Italic changes at 14 and 15pt. These differences require visual judgment rather than a single size boundary for all fonts.

The user requires stock Qt as the control. These sheets replace the earlier normal-hinting-plus-242 diagnostic sheets. That diagnostic was another treatment, not stock output. Its historical images and record remain in commit `073b8e4de0ac446850f21a30bd47306a811e7cce`.

| Face | White background | Black background |
| --- | --- | --- |
| Noto Sans Regular | [Image](../images/browser-common-ground/stockqt-smallpt-noto-sans-regular-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-noto-sans-regular-dark.png) |
| Noto Serif Regular | [Image](../images/browser-common-ground/stockqt-smallpt-noto-serif-regular-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-noto-serif-regular-dark.png) |
| Lato Light | [Image](../images/browser-common-ground/stockqt-smallpt-lato-light-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-lato-light-dark.png) |
| Hack Regular | [Image](../images/browser-common-ground/stockqt-smallpt-hack-regular-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-hack-regular-dark.png) |
| Noto Sans Italic | [Image](../images/browser-common-ground/stockqt-smallpt-noto-sans-italic-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-noto-sans-italic-dark.png) |
| Noto Sans Bold Italic | [Image](../images/browser-common-ground/stockqt-smallpt-noto-sans-bolditalic-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-noto-sans-bolditalic-dark.png) |
| Noto Serif Italic | [Image](../images/browser-common-ground/stockqt-smallpt-noto-serif-italic-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-noto-serif-italic-dark.png) |
| Noto Serif Bold Italic | [Image](../images/browser-common-ground/stockqt-smallpt-noto-serif-bolditalic-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-noto-serif-bolditalic-dark.png) |
| Hack Italic | [Image](../images/browser-common-ground/stockqt-smallpt-hack-italic-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-hack-italic-dark.png) |
| Hack Bold Italic | [Image](../images/browser-common-ground/stockqt-smallpt-hack-bolditalic-light.png) | [Image](../images/browser-common-ground/stockqt-smallpt-hack-bolditalic-dark.png) |

The [capture record](../images/browser-common-ground/stockqt-smallpt-captures.json) covers 220 matched layouts and 100 displayed conditions across these 20 sheets. Every saved crop matches its original stock Qt or candidate strip. The preserved native fixture reproduces all earlier stock, 75%, and 50% outputs on the capture system. The earlier 16pt reference images remain unchanged. The charts cover 96 DPI at 100% scale. They do not establish a new application default. The [handoff](handoff.md) retains source, rebuild instructions, limits, and the next investigation.

## Rounded-edge optical expansion

The next diagnostic strengthens rounded horizontal strokes with a fixed 1/8px expansion. It leaves the 50% control intact. The trial adds eight FreeType units after standard-width matching and nearest-pixel Y rounding, only when both linked edges carry `AF_EDGE_ROUND`. It changes no X-width rule, coverage threshold, or blend. Its fractional expansion is an optical treatment, separate from integer fitting. The [private patch](../../patches/freetype-2.14.2-round-y-experiment.patch) applies to clean pinned FreeType 2.14.2. Do not stack it on the nearest-Y patch.

This capture uses a fresh local Qt 6.8.2 baseline, rather than the earlier Qt 6.10.2 environment. It uses the offscreen Qt platform at 96 logical DPI and 100% scale. The four Hack font hashes differ from the earlier capture. Noto Sans, Noto Serif, and Lato Light match their earlier font identities. These are new component comparisons, not a reproduction of every earlier desktop pixel. The 21px Noto Sans n reference does reproduce its earlier raw crown profiles.

The matrix covers 130 conditions. It includes all ten point sizes, four styles each of Noto Sans, Noto Serif, and Hack, plus Lato Light. Every sheet shows the original 75% treatment, the 50% control, the rounded-edge trial, and actual stock Qt. Both candidates and the trial retain floor 242, the weight cutoffs, whole-pixel origins, and linear blending. Native text retains full-word context. Enlarged details copy strip pixels exactly and can include neighboring italic ink.

The experiment changes 488 of 520 measured n/3/5/8 glyph conditions. It leaves every X coordinate unchanged. All uppercase V/W and lowercase w outlines and masks remain identical to the 50% control. Lowercase v changes in 19 conditions: all ten Noto Serif Bold Italic sizes and nine Noto Serif Italic sizes. Those v shapes contain rounded terminals. Native Y fitting of those terminals also moves other outline points through interpolation. A rounded-edge flag therefore does not guarantee isolation from diagonal glyphs.

For Noto Serif Italic v at 15px, a rounded linked width grows from 64 to 72 units. The top anchor stays at 512. Several inner points move down eight units. At the baseline raster row, summed raw coverage grows from 115 to 165. The center row also changes, from 554 to 550. The operation changes diagonal geometry and pixel distribution even where it does not add weight. This trial does not meet the full isolation target.

The light-face bypass is a separate cause of weak crowns. At 15px, Lato Light's standard Y width is about 0.59px. FreeType marks an axis extra-light below 0.625px and returns its original widths before the strong rounding branch. Its n crown link remains about 0.59px, and this trial never reaches that width. This explains why changing the 50% threshold or adding expansion after it cannot help that condition. At 21px the trial does affect Lato Light.

Noto Sans n at 15px follows a different path. Its crown is linked, the incoming width is about 1.08px, and fitting rounds it to one pixel. The trial increases that fitted width to 1.125px. The central raw crown column changes from `[248, 6, 0]` to `[247, 38, 0]`. Much of the added coverage appears in the fringe below the crown. At 21px, `[246, 255, 8]` becomes `[246, 255, 40]`. More coverage alone does not establish a stronger-looking crown core.

| Requested size | White background | Black background |
| --- | --- | --- |
| 8pt | [Four-column sheet](../images/browser-common-ground/round-y-8pt-light.png) | [Four-column sheet](../images/browser-common-ground/round-y-8pt-dark.png) |
| 11.25pt | [Four-column sheet](../images/browser-common-ground/round-y-11.25pt-light.png) | [Four-column sheet](../images/browser-common-ground/round-y-11.25pt-dark.png) |
| 16pt | [Four-column sheet](../images/browser-common-ground/round-y-16pt-light.png) | [Four-column sheet](../images/browser-common-ground/round-y-16pt-dark.png) |

The [capture record](../images/browser-common-ground/round-y-captures.json) retains the build and font identities, paired native trace samples, profiles, and image hashes. The checker independently rasterizes 12,870 native glyph masks. It also checks per-glyph floors, overlapping composition, both sRGB palettes, all 130 condition keys, and saved native/enlarged pixels. Its 6,608 width decisions include both-round, one-round, and neither-round contrasts. The one-round cases receive no expansion. These checks establish faithful examples, not a visual winner.

Keep this trial as a diagnostic. The next geometry investigation needs a narrower distinction between a rounded stroke and a curved terminal on a diagonal. It must also account for the extra-light bypass before selecting another width change. Preserve all four controls while investigating those two paths. Do not add a font-name or italic exclusion to conceal the v result.

## Mutual segment pairs preserve the tested diagonals

The next preview uses actual linked segments, rather than their aggregate edge flags. An edge groups several nearby segments. In the 15px Noto Serif Italic v, a rounded segment shares an edge with a straight linked segment. The old rule treats that whole edge as round. Its actual mutual stem pair contains one round segment and one straight segment. Noto Sans n instead has a mutual pair with two round segments.

The [segment-pair patch](../../patches/freetype-2.14.2-segment-y-experiment.patch) retains the 50% width function. A private wrapper receives the actual edges at all four width call sites. It adds signed eight units once when two mutually linked round segments connect those edges. It requires strong Y fitting and native stem adjustment. The original fitting, blue-zone placement, and interpolation still run. There are no font-name, italic, or character exclusions.

For extra-light axes, the same expansion follows the original fractional-width return. It does not force the curve to one pixel. At 15px, Lato Light n's central raw crown column changes from `[158, 0, 0]` to `[189, 0, 0]`. At 11px, `[113, 0, 0]` becomes `[144, 0, 0]`. These are increases in the first crown row. They differ from the fringe growth in Noto Sans. The fixed 128 cutoff can amplify their final visible effect.

Across the same 130 conditions, all 520 measured n/3/5/8 cases change. All 520 V/v/W/w cases retain exactly the 50% outlines, bearings, raw masks, and placement. Every X coordinate and contour topology remains unchanged. This includes the nineteen serif italic v conditions that the previous trial changed. This establishes isolation for the measured glyph set. It does not establish isolation for every diagonal in every font.

The native trace contains 6,977 width decisions. It expands 4,626 decisions, including 272 extra-light decisions. In 271 accepted decisions, the first segment does not qualify and a later segment does. The verifier follows the complete segment ring for rejected decisions. It independently checks raw flags, mutual links, edge membership, and signed expansion. A round/straight mutual pair receives no expansion.

Read-only traces also identify how the earlier v change spreads. At 15px, five v points first differ during edge alignment, two during strong-point alignment, and twenty during weak interpolation. Six points remain unchanged. The native strong-point tables retain edge references. The verifier reconstructs weak contour references from touched points and matches the native fixed-point interpolation. Eight traced cases reproduce their original outlines and masks exactly. Their final traced coordinates match the public probe. The [trace header](../../tests/freetype_curve_trace.h) and [instrumentation patch](../../tests/freetype_curve_trace.patch) preserve this observation method.

Use the compact [white-background preview](../images/browser-common-ground/segment-y-preview-light.png) and [black-background preview](../images/browser-common-ground/segment-y-preview-dark.png) to compare the third column with the 50% second column. They show Noto Sans Regular, Noto Serif Italic, and Lato Light at 8pt and 11.25pt. Native text and exact 4x excerpts retain the same pixels as the complete sheets.

| Requested size | White background | Black background |
| --- | --- | --- |
| 8pt | [Complete sheet](../images/browser-common-ground/segment-y-8pt-light.png) | [Complete sheet](../images/browser-common-ground/segment-y-8pt-dark.png) |
| 11.25pt | [Complete sheet](../images/browser-common-ground/segment-y-11.25pt-light.png) | [Complete sheet](../images/browser-common-ground/segment-y-11.25pt-dark.png) |
| 16pt | [Complete sheet](../images/browser-common-ground/segment-y-16pt-light.png) | [Complete sheet](../images/browser-common-ground/segment-y-16pt-dark.png) |

The [segment-pair record](../images/browser-common-ground/segment-y-captures.json) retains profiles, stage ownership, native traces, hashes, and eight image identities. The checker verifies 12,870 native masks independently, along with fixed floors, overlap, high-precision blending, and saved pixels. The original edge-level trial still passes its own checks. Both trials remain available.

This is a preview for visual judgment. The adjustment reaches small light-face crowns and preserves the tested diagonals. Noto Sans still gains much of its coverage below the crown core. Judge the apparent curve weight at native resolution before increasing the amount or selecting a policy. The environment remains the same fresh Qt 6.8.2 component baseline described above. No working application treatment changes.

## Integer-point middle-stroke diagnostics

The user's middle-stroke observation exposes a limit of the segment-pair trial. For Noto Serif Italic at 8pt, two waist rows of 8 lose cutoff-reaching pixels even as the crowns gain coverage. Their counts change from two to one and from three to two. At 11pt, both Noto Sans and Noto Serif Italic also lose some middle coverage. The native traces show changes during edge alignment, strong alignment, and weak interpolation. More total ink and zero changed v masks do not establish a successful repair.

The new study uses thirteen faces and nine actual integer point requests, for 117 conditions. The main previews show the same three faces at 8pt and 11pt. They contain native text and exact 6x excerpts of 8, 3, 5, and v. Larger pages show all nine integer sizes. Font identity, source layout, coverage floors, cutoffs, and original comparison controls remain fixed.

The primary diagnostic applies the existing public outline-expansion API after unchanged 50% hinting. It avoids another round-pair fitting change. The operation uses strengths 8 and 16 in FreeType's internal units. These are expansion parameters, not point-size requests. Expected coordinates come from an independent call on the original 50% outline. The stock raster API then supplies the expected masks and bearings.

For Noto Serif Italic at 11pt, the two measured waist rows gain cutoff-reaching pixels from one to two and from two to three. At 8pt, the first measured row retains two; the next row has two rather than the 50% control's three. This operation can strengthen one region while leaving another wrong. It also adds diagonal weight. The preview must be judged against stock Qt before acceptance.

The composition diagnostic changes no geometry or mask. It uses encoded black/white blending for the 50% masks. A treated coverage of 242 produces a level of about 64 on white under the retained linear-light treatment, versus 13 under encoded blending. The same coverage therefore looks darker without adding a filled pixel. On black, encoded blending gives less brightness for partial coverage. This is a separate diagnostic, not a proposed polarity policy or a combined treatment.

| Diagnostic | White background | Black background |
| --- | --- | --- |
| Post-hint native expansion | [Main preview](../images/browser-common-ground/core-expanded-preview-light.png) | [Main preview](../images/browser-common-ground/core-expanded-preview-dark.png) |
| Same 50% masks, encoded blend | [Main preview](../images/browser-common-ground/core-encoded-preview-light.png) | [Main preview](../images/browser-common-ground/core-encoded-preview-dark.png) |

| Primary geometry comparison at every integer 8–16pt | White background | Black background |
| --- | --- | --- |
| Noto Sans Regular | [All nine sizes](../images/browser-common-ground/core-noto-sans-regular-8-16pt-light.png) | [All nine sizes](../images/browser-common-ground/core-noto-sans-regular-8-16pt-dark.png) |
| Noto Serif Italic | [All nine sizes](../images/browser-common-ground/core-noto-serif-italic-8-16pt-light.png) | [All nine sizes](../images/browser-common-ground/core-noto-serif-italic-8-16pt-dark.png) |
| Lato Light | [All nine sizes](../images/browser-common-ground/core-lato-light-8-16pt-light.png) | [All nine sizes](../images/browser-common-ground/core-lato-light-8-16pt-dark.png) |
| Thirteen-face 16pt reference | [Reference](../images/browser-common-ground/core-expanded-16pt-light.png) | [Reference](../images/browser-common-ground/core-expanded-16pt-dark.png) |

The [capture record](../images/browser-common-ground/core-contrast-captures.json) retains the profiles, native identities, and twelve image hashes. The checker verifies 11,583 independent native masks and all expanded coordinates. It also checks exact condition keys, duplicate/missing/fractional input contrasts, all 33 occurrences, per-glyph floor, overlap, blending, and saved crops. Twenty-four paired ownership observations reproduce the rejected/control glyphs at actual integer points. The final side-bearing translation is checked separately from hint-save coordinates. The source stock chart, private FreeType libraries, and working applications remain unchanged.

Keep both diagnostics available for visual comparison. Neither restores every missing middle pixel under the recorded metric. The user prefers the encoded-blend diagnostic and finds it nearly perfect. The next study retains that reference while addressing light coverage and weak counter bridges separately.

## Encoded light weights and counter bridges

The hard light-weight floor maps raw coverage 127 to 127, then 128 to 242. Under encoded blending this abrupt jump is directly visible. The user reported unreadable white-on-black text at 8pt and excessive darkness on white. The light trial compared no floor with a mild smooth lift, `a + round(a*(255-a)/1020)`, before per-glyph composition. The smooth table maps 127 to 143 and 128 to 144. Its largest adjacent step is two; zero and full coverage remain unchanged. Both trials preserve regular-weight pixels exactly. Neither changes outlines, glyph positions, or raw masks. The user selects no floor: nearly stock Qt weight, with consistent readability in every assessed case. This is the accepted light reference for later research.

| Light coverage, upright and italic | White background | Black background |
| --- | --- | --- |
| Noto Sans, 8pt and 11pt | [Main panel](../images/browser-common-ground/encoded-light-noto-sans-light.png) | [Main panel](../images/browser-common-ground/encoded-light-noto-sans-dark.png) |
| Noto Serif, 8pt and 11pt | [Main panel](../images/browser-common-ground/encoded-light-noto-serif-light.png) | [Main panel](../images/browser-common-ground/encoded-light-noto-serif-dark.png) |
| Lato, 8pt and 11pt | [Main panel](../images/browser-common-ground/encoded-light-lato-light.png) | [Main panel](../images/browser-common-ground/encoded-light-lato-dark.png) |
| Noto Sans, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/encoded-light-noto-sans-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/encoded-light-noto-sans-8-16pt-dark.png) |
| Noto Serif, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/encoded-light-noto-serif-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/encoded-light-noto-serif-8-16pt-dark.png) |
| Lato, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/encoded-light-lato-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/encoded-light-lato-8-16pt-dark.png) |

The geometry trial keeps the preferred encoded coverage treatment. FreeType identifies contour direction; the trial requires at least two contours wound opposite to the whole outline. A native vertical expansion on a copy supplies new inner-hole coordinates. Only inner-hole Y coordinates are copied back, centered by half the expansion. Every X coordinate and outer point stays fixed. The mild and stronger settings use eight and sixteen internal units. They are geometry parameters, not font sizes. Noto and Lato order their contours differently, so the selector follows direction rather than contour position. Actual Qt `B g O` layouts exercise eligible and ineligible shapes without a character gate.

For Noto Sans Regular at 11pt, one measured 8 waist row changes from raw `[55,233,147,98,192,232,47]` to `[55,235,162,114,206,232,47]` under the mild trial. The 147 sample crosses the regular cutoff of 160. The stronger trial produces `[55,237,175,129,217,232,47]`. This is a local bridge gain; it does not prove that every other part improves. The selector preserves v, 3, 5, and single-hole outlines in the current text. Small holes can close, and native expansion can still lose coverage elsewhere.

| Separate counter geometry trial | White background | Black background |
| --- | --- | --- |
| Main 8pt and 11pt panel | [Main panel](../images/browser-common-ground/encoded-waist-light.png) | [Main panel](../images/browser-common-ground/encoded-waist-dark.png) |
| Noto Sans Regular, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/encoded-waist-noto-sans-regular-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/encoded-waist-noto-sans-regular-8-16pt-dark.png) |
| Noto Serif Italic, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/encoded-waist-noto-serif-italic-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/encoded-waist-noto-serif-italic-8-16pt-dark.png) |

The [capture record](../images/browser-common-ground/encoded-refinement-captures.json) contains nineteen faces at nine integer requests, coverage tables, profiles, and eighteen image hashes. The checker verifies 17,034 native masks, every expected outline coordinate, and saved native/enlarged crops. An independent scalar exporter verifies the real light canvases through final RGB. Two overlapping raw-64 samples distinguish per-glyph smoothing (129) from smoothing after composition (128). Original chart, font, source, and library hashes remain protected. The user rejects both inner-hole strengths as too subtle and ineffective. Keep them as negative evidence. These results do not change working presets or qualify real browser output.

## Regular-weight coverage shoulder

The user proposes raising coverage near 128 to about 192 below the existing 160-to-242 treatment. This study compares two coverage-only candidates. It retains the accepted raw-light result in every column. Regular and heavier faces use the previous encoded result as the reference. No outline point, raster mask, glyph identity, position, or blend changes.

The shoulder raises values 128–159 to 192. The continuous ramp joins 96→96, 128→192, and 160→242 with straight segments, rounded to the nearest integer with halves up. It leaves lower values unchanged and retains the old treatment at and above 160. This extends the transition below 128 to avoid creating another abrupt entry jump. It is a fixed research choice, not a selected production curve.

| Original coverage | Old reference | Shoulder | Continuous ramp |
| --- | --- | --- | --- |
| 96 | 96 | 96 | 96 |
| 112 | 112 | 112 | 144 |
| 127 | 127 | 127 | 189 |
| 128 | 128 | 192 | 192 |
| 144 | 144 | 192 | 217 |
| 159 | 159 | 192 | 240 |
| 160 | 242 | 242 | 242 |
| 242 | 242 | 242 | 242 |

The ramp's largest adjacent step is three. The shoulder has a 65-level jump at 128 and a 50-level jump at 160. A Noto Sans Regular 11pt waist row changes from treated `[55,242,147,98,242,242,47]` to `[55,242,192,98,242,242,47]` under the shoulder and `[55,242,222,102,242,242,47]` under the ramp. These are stronger middle samples without added geometry. A raw 94 in a weak Noto Serif Italic 8pt waist remains unchanged under both candidates. The user selects the continuous ramp: the displayed missing-pixel cases are resolved, with improved white-on-black readability. The next target is Noto Serif Regular 2 at 11pt.

The same coverage range also occurs on diagonals. Across all conditions and both occurrences of 8 in the text, the shoulder changes 1,230 treated samples of 8 and the ramp changes 2,352. For v/V/W/w combined, the respective counts are 2,948 and 5,719. These counts describe where coverage changes, not optical quality. Both candidates therefore need visual judgment of collateral weight. All fifty-four light-face/point conditions remain byte-identical to the accepted raw-light reference on both palettes.

| Coverage-only comparison | White background | Black background |
| --- | --- | --- |
| Main 8pt and 11pt preview | [Main panel](../images/browser-common-ground/shoulder-preview-light.png) | [Main panel](../images/browser-common-ground/shoulder-preview-dark.png) |
| Noto Sans Regular, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/shoulder-noto-sans-regular-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/shoulder-noto-sans-regular-8-16pt-dark.png) |
| Noto Serif Italic, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/shoulder-noto-serif-italic-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/shoulder-noto-serif-italic-8-16pt-dark.png) |
| Accepted Lato Light, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/shoulder-lato-light-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/shoulder-lato-light-8-16pt-dark.png) |

The [capture record](../images/browser-common-ground/shoulder-captures.json) contains exact coverage tables, source identities, registered middle/crown profiles, changes for every occurrence, and eight image hashes. Independent Decimal interpolation checks every table value. Scalar per-glyph alpha-over and encoded RGB predict every actual exported canvas. Two overlapping raw-128 pixels produce 239 with either candidate per glyph, versus 242 with incorrect post-composition treatment. All 5,643 original native masks reproduce independently, and saved native/enlarged crops match their verified source pixels. Original source, font, library, helper, and stock-image hashes remain unchanged. This study changes no working preset and does not qualify real browser output.

## Native dropout continuity

The remaining target is Noto Serif Regular 2 at 11pt. Its grayscale middle rows contain raw pairs such as `[82,69]` and `[80,75]`. Both samples in each pair remain below the accepted ramp's entry point. Their horizontal coverage sums are 151/255 and 155/255, about 0.6 pixels. These are coverage sums, not perpendicular geometric widths.

Native stage tracing attributes substantial narrowing to weak X interpolation. Two recorded diagonal boundary points have an X separation of 73 internal units before weak interpolation and 45 afterward. One moves right by 18 units; the other moves left by ten. Their final Y coordinates differ by six units. These are source-identified point relationships, not a general stroke-width metric. Normal grayscale and light hinting retain more coverage in this diagonal, but changing the whole hinting target would affect the accepted strokes elsewhere.

FreeType's [outline flags](https://freetype.org/freetype2/docs/reference/ft2-outline_processing.html#ft_outline_xxx) provide native dropout correction for the black-and-white rasterizer. The smooth rasterizer ignores these flags. The bounded trial renders the same original hinted outline twice: flags zero enable simple dropout correction without stubs; flags eight disable it. Every contour-start scanmode tag is checked, so it cannot override the selected flag. The added pixels give a native line-continuity signal without a new geometric, font, or character classifier.

The reported 2 has exactly four added pixels, at baseline-relative `(y,x)` coordinates `(-5,4)`, `(-4,3)`, `(-3,2)`, and `(-2,1)`. Its gray bitmap origin supplies the registration. The trial raises only these selected weak samples to opacity 192 or 217 after applying the accepted ramp. Stronger samples retain their opacity. The raw `[82,69]` pair becomes `[192,69]` or `[217,69]`; `[80,75]` becomes `[192,75]` or `[217,75]`. This makes the selected line more visible without moving its outline. The user prefers 217 over 192. Carry 217 forward with the accepted ramp and raw-light bypass; it does not establish a physical minimum width.

| Native dropout comparison | White background | Black background |
| --- | --- | --- |
| Main 8pt and 11pt preview, exact 6x 2/v/W | [Main panel](../images/browser-common-ground/dropout-preview-light.png) | [Main panel](../images/browser-common-ground/dropout-preview-dark.png) |
| Noto Serif Regular, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/dropout-noto-serif-regular-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/dropout-noto-serif-regular-8-16pt-dark.png) |
| Noto Sans Regular, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/dropout-noto-sans-regular-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/dropout-noto-sans-regular-8-16pt-dark.png) |
| Accepted Lato Light, all integer 8–16pt | [Nine sizes](../images/browser-common-ground/dropout-lato-light-8-16pt-light.png) | [Nine sizes](../images/browser-common-ground/dropout-lato-light-8-16pt-dark.png) |

The 192 trial changes four samples of the target Serif 2 at 11pt. In that same row, it changes one sample each of 8, v, and W; V stays unchanged. Noto Sans Regular at 11pt keeps its 2, v, and W pixels, but one pixel in 6 changes under both guards. Across the complete matrix, the 192 trial changes thirteen samples of 2, ten of v, nine of V, twenty of W, and one of l. These counts include all occurrences. Other narrow features can therefore change too; the signal is not unique to the reported defect. Every light condition bypasses the guard exactly.

The [capture record](../images/browser-common-ground/dropout-captures.json) retains full registered raw/treated profiles, changes for all 33 occurrences, native provider flags, source/library hashes, and eight image hashes. A private chart copy captures the native one-bit pair before unchanged gray rendering. An independent original-outline Oracle predicts both bitmaps and all gray masks: 16,929 rasters across 171 actual point/font conditions. Independent packed-bit decoding and scalar alpha-over predict final RGB through the real exported branch. The saved native and exact 6x 2 crops are reopened and verified. Two selected raw-64 glyphs produce 239 or 249 after the per-glyph guard, unlike incorrectly guarding after composition (192 or 217). Existing helpers, accepted input captures, fonts, native libraries, and application settings remain unchanged. Visual acceptance and later browser qualification remain necessary.

## Limits and decision

Contour-point displacement is a measure of geometric proximity. It is not a readability, beauty, or optical-quality score. Different placement of control points can affect this metric, so comparisons use matching points from the same font. The reference also excludes the designer's size-specific hinting instructions. It measures fidelity to the outline, rather than every aspect of design intent.

The stroke ratios describe one cross-section of one letter. They are not a contrast score for the whole font. The broader measurements cover 440 nonempty glyphs at one resolved size. They do not establish results for other sizes, scripts, variable fonts, or displays.

Keep Auto mono + 242 as the visual comparison control. The current target is crisp text with source-based stroke proportions and predictable nearest-pixel rounding. Judge the nearest-Y test against both that control and the original design. The remaining FreeType width matching and alignment stages still need qualification. This analysis does not change application settings.

The [capture record](../images/browser-common-ground/geometry16-captures.json) contains font hashes, versions, measured values, method limits, and the figure hash. The traced Qt run reproduces all 44 original stock strips exactly. Native and benchmark outlines match their respective captures. Contour topology matches throughout. The n measurements converge within 0.001px when curve sampling doubles.

## Curve weight with raw coverage

The user reports that the raw profile softens jaggies but leaves curved strokes and crowns too light in real use. Preserve raw coverage and encoded blending while testing a small change to curve thickness. This experiment reuses the mutual round-segment mechanism from S6. It adds zero, 1/16, or 1/8 device pixel to the fitted Y width. It does not add a coverage floor, ramp, clipping, or a new curve classifier.

The four columns are current raw, raw with 1/16-pixel curve expansion, raw with 1/8-pixel expansion, and actual stock Qt. Every outline still uses the native grayscale rasterizer. A geometry change can move an edge or change its coverage. Unchanged rasterization does not prove that edge appearance remains equally good. Visual judgment must include the soft edges as well as the stronger crowns.

![Nine faces at 12pt, raw curve-weight trials and stock Qt on white](../images/browser-common-ground/raw-curves-overview-12pt-light.png)

[The same overview on black](../images/browser-common-ground/raw-curves-overview-12pt-dark.png) retains all four columns. The complete matrix covers nine faces at every actual integer size from 8 through 16pt, at 96 DPI and 100% scale. Requested sizes remain point labels. The expansion strengths describe device-space stroke width, not font sizes.

| Face | White background | Black background |
| --- | --- | --- |
| Noto Sans Regular | [Image](../images/browser-common-ground/raw-curves-noto-sans-regular-light.png) | [Image](../images/browser-common-ground/raw-curves-noto-sans-regular-dark.png) |
| Noto Sans Bold | [Image](../images/browser-common-ground/raw-curves-noto-sans-bold-light.png) | [Image](../images/browser-common-ground/raw-curves-noto-sans-bold-dark.png) |
| Noto Sans Italic | [Image](../images/browser-common-ground/raw-curves-noto-sans-italic-light.png) | [Image](../images/browser-common-ground/raw-curves-noto-sans-italic-dark.png) |
| Noto Serif Regular | [Image](../images/browser-common-ground/raw-curves-noto-serif-regular-light.png) | [Image](../images/browser-common-ground/raw-curves-noto-serif-regular-dark.png) |
| Noto Serif Italic | [Image](../images/browser-common-ground/raw-curves-noto-serif-italic-light.png) | [Image](../images/browser-common-ground/raw-curves-noto-serif-italic-dark.png) |
| Lato Light | [Image](../images/browser-common-ground/raw-curves-lato-light-light.png) | [Image](../images/browser-common-ground/raw-curves-lato-light-dark.png) |
| Hack Regular | [Image](../images/browser-common-ground/raw-curves-hack-regular-light.png) | [Image](../images/browser-common-ground/raw-curves-hack-regular-dark.png) |
| Hack BoldItalic | [Image](../images/browser-common-ground/raw-curves-hack-bolditalic-light.png) | [Image](../images/browser-common-ground/raw-curves-hack-bolditalic-dark.png) |
| Nimbus Sans Regular | [Image](../images/browser-common-ground/raw-curves-nimbus-sans-regular-light.png) | [Image](../images/browser-common-ground/raw-curves-nimbus-sans-regular-dark.png) |

Both strengths preserve every tested V/v/W/w occurrence and every X contour coordinate. The rule also changes i in seven faces at all nine sizes, and l in Noto Serif Italic. Those 72 occurrences include rounded dots or terminals. H, I, and 1 remain unchanged throughout this matrix. The selector follows native rounded segments, rather than letter names. Do not describe it as changing only crowns.

The [capture record](../images/browser-common-ground/raw-curves-captures.json) includes font and library hashes, all 81 conditions, native pair decisions, changed-occurrence counts, and twenty image hashes. Zero expansion reproduces the earlier nearest reference exactly. For each strength, 1,883 traced decisions include 1,223 eligible round pairs. Independent rasterization reproduces every glyph. Scalar identity-coverage composition predicts each raw mask and encoded final canvas. Saved crops reproduce the source pixels. These checks establish faithful evidence, not a visual winner.

Run `tests/raw_curve_darkening_test.py --stock-build RECORD --nearest-library LIBRARY --label-font FONT` from the repository root. The stock record must identify the existing pinned FreeType 2.14.2 source and private headers. The script keeps build output and images under their configured storage roots. It records and checks cached source/library identities. The experiment has no installed-library or application-profile writes. CFF coverage includes static Nimbus Sans here. Variable CFF2, other scripts, fractional display scales, and real-application curve treatment need later qualification.

## Matched Firefox Home reference

The user reports that the earlier samples look darker than normal application text. Their requested reference is Firefox Home's light-on-dark text, especially its soft crowns. The earlier 12pt, pure black/white chart is not a qualified optical reference for those conditions. It remains a valid component comparison. Matching a custom page to that chart alone does not establish a match to Firefox Home.

The native Home capture supplies two generic text runs: a shortcut label and the recent-activity heading. The shortcut uses the system caption font, Noto Sans at 10pt. Its native size is about 13.333 device units, rather than Qt's rounded 13-unit result for the same point request. The heading uses the installed Noto Sans Bold face. The packaged Home style requests 600 weight and a 1.133rem heading at a 15px root. Its native raster size rounds to 17 units. These device values describe the diagnostic, not new synthetic comparison-size labels.

The measured capture background is RGB 19,18,21 and the opaque text color is RGB 242,240,248. The first comparison assumed pure black and white. Both size and color must stay fixed when judging the actual Home condition. Source stylesheet and Fontconfig observations identify candidate settings. Matching the complete captured text verifies the selected font and native size.

![Actual Firefox Home text, matched native baseline, and two small curve-width trials](../images/browser-common-ground/firefox-home-curves.png)

The first column contains actual Home text crops. The second reconstructs those same pixels with the native raw profile. Every one of the 22 nonempty glyph occurrences and both complete crops agree within one RGB level per channel. Mean absolute error is about 0.04 per channel over each full crop. A wrong-size control differs by up to 227 levels. Linear-light composition differs by up to 57. The matching raw/encoded baseline therefore distinguishes the earlier mismatched size and blend conditions.

Columns three and four retain the measured fonts, native sizes, colors, and glyph origins. They replay the existing round-segment rule at 1/16 and 1/8 device pixel, with raw coverage and encoded blending. Native pixels appear above exact 3x details. The displayed 1720×440 figure matches its saved PNG at actual 100% zoom. Neither strength is installed or selected by this evidence. Home is a measured fixture, not a page-specific rendering rule.

The [source record](../images/browser-common-ground/home-source-captures.json) binds the two tight generic-text crops, font hashes, measured colors, native sizes, and occurrence origins. It contains no full window, browsing history, bookmarks, or account data. The [comparison record](../images/browser-common-ground/home-curves-captures.json) binds native library and checker hashes, six result images, the figure, and the baseline/error contrasts. Earlier 12pt charts retain their distinct capture identity.

Use `tests/firefox_home_curve_test.py --probe PROBE --libraries RAW SMALL LARGER --stock-library STOCK --label-font FONT`. The two curve libraries retain S17's private build records and source files. The checker binds their actual strengths, patch hashes, source hashes, and library hashes before calling the probe. It rasterizes pre-render outlines independently, checks repeated renders and X coordinates, reconstructs raw alpha-over composition by two methods, and reopens every native/detail crop. FreeType can clear outline storage after rasterization, so the Oracle consumes the separately captured pre-render outline.

The matched reference covers two Home runs on one recorded desktop. It does not establish optical quality for every face, weight, application, or scale. Continue judging the actual weak crowns and preserved edge softness before choosing a curve rule.
