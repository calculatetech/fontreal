# Fontreal rendering handoff

The latest optical studies are on `experiment/raw-curve-darkening` in `calculatetech/fontreal`. Read this document, the [roadmap](../roadmap.md), and the [geometry analysis](16pt-geometry.md) before changing the renderer. Use an isolated task branch for new work. This document describes research inputs and resumption steps. The roadmap owns task state.

## Current direction

The installed browser preset retains nearest-50% geometry, raw coverage and encoded composition from the earlier selection. The latest component studies now favor native-normal + 170 overall. For Inconsolata, the user prefers ×1.375 with a 226 ceiling as subtly better at reducing jaggies. Its weak u right stem at 11pt on black is the next target. Compare added coverage with concentration around a defined core. Preserve the installed preset while this new treatment needs live-application and layout qualification.

Earlier `ramp217`, `none`, and `mild` modes remain explicit diagnostics. The inner-hole contraction trials remain ineffective negative evidence. New comparisons use actual integer point requests, with the current focus at 11–12pt. Keep resolved device units in diagnostic metadata. Retain actual stock Qt controls for the Qt geometry comparisons. The recent glyph studies compare explicit FreeType modes and their coverage treatments.

The earlier 16pt result remains a useful geometry reference. The user authorizes the selected recipe for ordinary live Firefox and Floorp and now requests the same complete profile for KDE. KDE must override rendering preferences with nearest-50% fitting, raw grayscale coverage, whole-pixel placement and encoded blending while preserving chosen fonts and sizes. The native KDE capability and package deployment are specified in S13 of the [native study](../plans/FR-018-axis-study.md). Continue toward crisp strokes with source-based proportions and predictable pixel rounding. The browser activation guide owns the browser preset and its reversal.

Messenger exposed a separate font-selection gap. On the capture system, Helvetica resolves to Nimbus Sans CFF, which the earlier browser predicate excludes. Twelve distinct supplied glyphs exactly match its untouched native masks. The user prefers the local 50% raw CFF comparison and requests Helvetica → Noto Sans. Keep the native per-user alias specified in S15 of the [native study](../plans/FR-018-axis-study.md). The user explicitly requires CFF support as well; the alias is additional. S16 defines the CFF-capable browser and KDE profile, including truthful native capability checks and actual consumer validation. Preserve Arial-first requests and all other chosen families.

The normal raw profile includes CFF, variable CFF2, and CID collections. It uses the existing nearest Latin Y rule and preserves other native script rules, including CJK fitting. KDE requires the actual per-library `fontreal-nearest-y-v2` capability. A stock or older TrueType-only provider cannot satisfy it. Keep the older diagnostics unchanged. Use the [native package guide](../build-system.md) on each machine. Rebuild for that machine's exact provider and package snapshot. Build outputs, virtual machines, ignored results, user profiles, and installed Fontconfig rules do not transfer with Git.

The next deployment must activate the CFF-capable private browser build in each destination profile and verify its loaded libraries after a normal browser restart. Native KDE installation needs the matching three-family bundle, its package and full-session proof, native authorization, and a fresh normal login. Source publication does not perform either deployment. Preserve the destination machine's accounts, fonts and other preferences.

For the requested Helvetica preference, keep this rule in the user's `fontconfig/conf.d/50-helvetica-noto-sans.conf` under their configuration directory. If that file exists, preserve its other rules. Noto Sans must be installed. Explicit Nimbus requests keep their family choice. Check the actual selected face: a Type 1 counterpart can share a CFF family's name. The raw profile applies to eligible CFF faces; Type 1 retains its native path.

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias binding="strong">
    <family>Helvetica</family>
    <prefer><family>Noto Sans</family></prefer>
  </alias>
</fontconfig>
```

The target favors pixel alignment over exact low-density geometry. A detected width of 1.5 device pixels must round to two, while 1.4 rounds to one. These are stroke-width measurements, not font-size requests. Curves and diagonals still need softened edges. Avoid weak crowns, weak middle strokes, inconsistent intensity, and excessive diagonal weight. Test font choice, point size, scale, weight, italic, and background together. Do not add website-specific rules or substitute every light face with regular.

## Matched Firefox Home reference

Firefox Home remains a measured light-on-dark reference. The user now identifies weak Nimbus Sans crowns in a website crop as the target. After excluding duplicate Type 1 Nimbus copies and restarting normally, six supplied glyphs match the active raw CFF masks exactly. Small curve-width trials give no reliable preference in the same screen position. The user selects connected weak runs with original 230+ reference pixels, then lowers the main cutoff to 170. The [guarded-bridge preview](16pt-geometry.md#cutoff-170-and-guarded-bridges) also addresses a's 140 pixel without extra bridge changes to the matched W. Colon, exclamation, dotted letters and separated-mark fixtures are explicit controls. The guard cannot repair every disconnected stroke. Preserve the installed raw preset until a new treatment is qualified.

The user requests [broad font coverage](16pt-geometry.md#broad-font-gallery-with-cutoff-170-and-guarded-bridges) with only 170 + guarded bridge visible. That instruction supersedes stock comparison columns for this gallery alone. The native matrix contains 19 families, 94 real faces and 846 font/point conditions. All integer 8–16pt sizes include full phrases, alphabets, digits, symbols and adversarial controls on both backgrounds. The generator puts 764 pages in one folder for one Gwenview launch and arrow browsing. The portable record and eight representative images transfer with Git. The full folder must be generated on the destination machine with its installed fonts. Optical judgment remains necessary before runtime integration.

The user's broad-gallery feedback narrows the [next case studies](16pt-geometry.md#focused-crown-and-diagonal-cases-at-1112pt) to 11–12pt. Hack, Inconsolata and Nimbus Roman retain weak crowns at 11pt. DejaVu Sans has poor S/A/Y and diagonal balance on black. Arial diagonals are too thick on black at 11–12pt. Most other sizes look good. The focused native sheets and numbered grids retain the current treatment. They expose untouched below-170 crowns and adjacent diagonal pixels that both receive a boost. Keep these as separate constraints before choosing a correction. No new filter or installed profile change follows from this diagnostic alone.

The next target is [Hack Regular's 11pt 8](16pt-geometry.md#hack-regular-8-at-11pt-shape-versus-coverage), specifically its upper corners and waist. Stock auto-mono and selected raw have identical outlines and pixels for this condition. The user prefers the local ×1.375 trial but still rejects the deformation. Font-native normal is their only accurate shape reference for this glyph. The local gain remains a one-glyph visual preference, without transferable coordinates or a general detector.

The [native-normal study](16pt-geometry.md#native-normal-shape-and-coverage-at-1112pt) compares current auto-mono + 170, native-normal raw, and native-normal + the existing bridge pass. Hack's four actual styles and the other four case-study families at 11–12pt give sixteen conditions. Explicit alphabets retain S/A/Y and diagonal controls. The seventeen-page folder includes both backgrounds and a numbered Hack 8 grid. Native columns preserve one outline while isolating coverage changes. The probe disables automatic hinting and exactly reproduces the selected S25 Hack control. Original shaped positions remain fixed, so native layout and live-application spacing still need qualification. Keep the installed raw preset unchanged until that qualification is complete.

The user selects native + 170 as best overall and identifies Inconsolata as the main residual case. The [requested gain study](16pt-geometry.md#inconsolata-and-the-requested-1375-gain) shows the accepted baseline, ×1.375 with a 226 strengthening ceiling, and a 255 saturation control. Only remaining 128–229 values change. Strong pixels and lower fringes remain identical. The earlier ×1.375 Hack preview was a local annotation, not a filter already present in the native-normal sheets. This new eight-page study covers 11pt and 12pt, both backgrounds and numbered H/K/M/V/W/u grids. Gain adds coverage rather than aligning split stems. It needs optical and broader font/weight checks before a general policy or installed change.

The user prefers the gain with ceiling 226, while u's right stem stays weak. The [defined-core study](16pt-geometry.md#inconsolata-u-a-defined-core-at-fixed-stem-coverage) compares the chosen 198 + 124 pair with 226 + 124, 240 + 82 and 240 + 28. The latter trials retain the gained or original native area only within four annotated upper-stem pairs. The 240 reference already exists in the native lower stem. Bowl and other pixels stay identical, and all 12pt masks are unchanged controls. Concentration shifts the ink centroid despite fixed outlines and bounds. The three-page folder supplies native, enlarged and numbered views. It is a one-glyph diagnosis rather than a general selector or installed change.

The [actual Home comparison](16pt-geometry.md#matched-firefox-home-reference) retains a separate condition. Its first column is real Home text, and its second reproduces both complete source crops within one RGB level. The source includes a system-caption label and the recent-activity heading. Actual font files, native sizes, measured colors, and per-occurrence origins replace assumptions about pure black/white and a 12pt request.

`tests/firefox_home_curve_test.py` replays the raw profile and the earlier 1/16- and 1/8-device-pixel curve strengths against that source. Supply the existing native probe, three private libraries, the stock raster library, and label font. The curve libraries must keep S17's build records and sources. The public source and comparison records preserve only tight generic text crops and portable metadata. No full Home window or browsing data belongs in public evidence. The older chart and custom-page match remain separate component evidence, not qualification of Home.

The user authorizes the existing activation tool to apply the new raw profile to ordinary Firefox and completes a normal quit/reopen. Preserve the original working account. Do not infer a KDE upgrade from browser activation. No curve strength is selected or deployed. Use Home only as a measured reproduction case; the eventual treatment must remain general.

## Curve-weight follow-up

The latest user reports weak curved strokes and crowns in real use, while explicitly retaining raw processing's softer jaggies. The selected raw profile remains the control. The [new curve-weight study](16pt-geometry.md#curve-weight-with-raw-coverage) replays S6 at zero, 1/16, and 1/8 device pixel of Y expansion, with no coverage boost and with actual stock Qt beside it. It covers nine faces at integer 8–16pt, including light, bold, italic, monospace, serif, and static CFF. No trial strength is selected for deployment.

The reproducible checker is `tests/raw_curve_darkening_test.py`. Supply `--stock-build RECORD`, `--nearest-library LIBRARY`, and `--label-font FONT`. The stock record must identify the retained pinned FreeType 2.14.2 source, headers, and stock library. Output goes to `build/raw-curve-darkening` and `results/raw-curve-darkening`. The checker reuses the committed segment-pair patch and a private copy of the point chart. Original helpers, libraries, and profiles stay unchanged.

Judge crown readability and preserved edge softening together. Both strengths keep all tested V/v/W/w pixels unchanged, but rounded i dots and one serif italic l terminal also change. The rule operates on linked native segments, not character exclusions. The current study does not qualify a new application default.

## Current integer-point diagnostics

The latest raw comparison uses current-provider captures under `results/raw-coverage-review`. Its 12pt overview contains all 19 faces on both backgrounds. Separate sheets cover every integer size 8–16pt, with stock Qt, the old ramp, raw coverage, and raw coverage with support. The user chooses fully raw coverage. Use `tests/raw_coverage_test.py` for the selected raw recipe.

`tests/dropout_continuity_test.py` preserves the earlier comparison. The [white-background preview](../images/browser-common-ground/dropout-preview-light.png) and [black-background preview](../images/browser-common-ground/dropout-preview-dark.png) show the earlier ramp, two native-guided opacity floors, and stock Qt. Their enlarged excerpts explicitly show 2, v, and W. Noto Serif Regular at 11pt is the fifth main row. Light rows retain raw coverage exactly.

FreeType's black-and-white rasterizer has [dropout correction](https://freetype.org/freetype2/docs/reference/ft2-outline_processing.html#ft_outline_xxx) to preserve narrow lines. Grayscale rendering does not use it. The trial compares native one-bit rasters with correction enabled and disabled for the same hinted outline. It applies an opacity floor of 192 or 217 only at added pixels, after the accepted ramp and before per-glyph composition. The user prefers 217, the third column. All other glyph-local pixels retain their accepted opacity. This is a line-continuity signal, not a guarantee of one pixel of perpendicular geometric width.

For the reported Serif 2 at 11pt, the native signal adds exactly four pixels along the weak diagonal. The trial changes those four; it also changes sparse dropout pixels in other strokes. Noto Sans Regular at 11pt keeps 2, v, and W unchanged but changes one pixel in 6. Keep full-word context, v/V/W, and the accepted light controls visible when judging the correction. The [analysis](16pt-geometry.md#native-dropout-continuity) includes all nine integer sizes and the measured limits.

For the selected raw recipe, preserve every eligible glyph's native grayscale coverage at every weight. Compose glyphs with alpha-over and encoded blending. Keep the existing 50% geometry. The following ramp and support sections retain historical evidence and their explicit diagnostic modes.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/dropout_continuity_test.py \
  --source-study results/encoded-refinement --ramp-study results/coverage-shoulder \
  --native-build build/radius-trace --output results/dropout-continuity \
  --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')"
```

The [capture record](../images/browser-common-ground/dropout-captures.json) retains all 171 condition identities, native flag choices, registered profiles, occurrence changes, two ownership observations, and eight image hashes. The checker verifies 16,929 native rasters: gray and two one-bit variants for all 5,643 occurrences. Independent native bitmaps and scalar composition predict every actual exported RGB canvas and saved target crop. A private [chart patch](../../tests/point_dropout_continuity.patch) captures one-bit data from outline copies; it preserves the original chart, native libraries, existing helpers, and working presets. Main desktop delivery requires actual 100% zoom and exact saved-PNG/window-capture equality; a mapped but fitted or hidden window is insufficient.

### Accepted continuous ramp

`tests/coverage_shoulder_test.py` preserves the preceding comparison. The user suggested raising 128 to about 192 below the existing 160-to-242 treatment. The [white-background preview](../images/browser-common-ground/shoulder-preview-light.png) and [black-background preview](../images/browser-common-ground/shoulder-preview-dark.png) compare the earlier reference, a 128-to-192 shoulder, the now-accepted continuous ramp, and stock Qt. All light rows retain the accepted no-floor result exactly.

The shoulder maps raw 128–159 to 192. The earlier accepted ramp leaves values through 96 unchanged, then interpolates to 128→192 and 160→242. Both retain the old treatment at and above 160. The ramp's largest adjacent step is three, compared with jumps of 65 and 50 for the shoulder. These are per-glyph coverage tables applied once before composition. Do not apply another hard floor afterward. Geometry, layout, and blending stay fixed in this comparison. The normal browser preset now uses fully raw coverage. The Qt preset stays unchanged.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/coverage_shoulder_test.py \
  --source-study results/encoded-refinement --native-build build/radius-trace \
  --output results/coverage-shoulder \
  --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')"
```

The [capture record](../images/browser-common-ground/shoulder-captures.json) binds all nineteen faces and nine actual integer point requests, original stock images, tables, registered profiles, and eight comparison images. The checker independently verifies all 5,643 original native masks and every actual candidate canvas through Decimal tables, scalar alpha-over, and final encoded RGB. Two overlapping raw-128 samples distinguish per-glyph treatment (239) from an incorrect post-composition treatment (242). Saved native and exact 6x crops are reopened and compared. All nine sizes, including 16pt, are linked in the [coverage analysis](16pt-geometry.md#regular-weight-coverage-shoulder). Main desktop delivery still requires mapped files at 100% and exact PNG/window-capture equality on both palettes.

### Accepted light treatment and rejected geometry trial

`tests/encoded_refinement_test.py` preserves the preceding comparison. It captures nineteen faces at nine actual integer point requests, for 171 conditions. Six light faces cover Noto Sans, Noto Serif, and Lato in upright and italic styles. Same-family regular rows show that the light coverage trials preserve the preferred regular result.

The four columns are encoded reference, light with no floor, light with a smooth coverage lift, and stock Qt. The [Lato light-background panel](../images/browser-common-ground/encoded-light-lato-light.png) and [dark-background panel](../images/browser-common-ground/encoded-light-lato-dark.png) show 8pt and 11pt. Equivalent panels cover [Noto Sans on white](../images/browser-common-ground/encoded-light-noto-sans-light.png), [Noto Sans on black](../images/browser-common-ground/encoded-light-noto-sans-dark.png), [Noto Serif on white](../images/browser-common-ground/encoded-light-noto-serif-light.png), and [Noto Serif on black](../images/browser-common-ground/encoded-light-noto-serif-dark.png). All nine sizes and the separate geometry panels are linked in the [refinement analysis](16pt-geometry.md#encoded-light-weights-and-counter-bridges).

The rejected [waist panel on white](../images/browser-common-ground/encoded-waist-light.png) and [on black](../images/browser-common-ground/encoded-waist-dark.png) retain the old coverage. They shorten only the inner holes of outlines with at least two opposite-winding contours. All X coordinates and outer contour points stay fixed. The user found neither strength useful. Keep these panels as negative evidence; the next trial must address the weak pixels by a different mechanism.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/encoded_refinement_test.py \
  --source-study results/segment-curve --native-build build/radius-trace \
  --output results/encoded-refinement \
  --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')"
```

The [capture record](../images/browser-common-ground/encoded-refinement-captures.json) preserves all 171 font identities, coverage tables, profiles, native library hashes, and eighteen image hashes. The checker verifies 17,034 independent native masks. It independently assembles every real light-trial canvas from original glyph masks through Decimal coverage tables, scalar alpha-over, and final encoded RGB. Actual Qt `B g O` micro-layouts distinguish the contour selector from a character-specific rule. View the main panels at 100% zoom and verify exact saved-PNG/window-capture equality; an opener result alone is insufficient.

### Earlier stage-isolation controls

`tests/core_contrast_test.py` retains the preceding comparison. It consumes the retained Qt point layouts and selects exactly 117 conditions: thirteen faces at each integer point from 8 through 16. It rejects incomplete, duplicate, fractional, and direct-pixel comparison inputs. The earlier fractional-point previews below are historical studies, not the active comparison format.

The new [middle-stroke investigation](16pt-geometry.md#integer-point-middle-stroke-diagnostics) separates two mechanisms. The primary diagnostic uses unchanged 50% fitting, then applies the public `FT_Outline_EmboldenXY(8,16)` operation after hinting. The [small chart patch](../../tests/point_outline_expansion.patch) applies to a private copy of the point chart. It changes neither the source chart nor the FreeType libraries. The independent `Oracle.expand` supplies expected coordinates from original 50% outlines. The second diagnostic retains the exact 50% masks and changes blending alone. Do not combine these operations or select a working preset from their numerical checks.

The [native-expansion light preview](../images/browser-common-ground/core-expanded-preview-light.png) and [dark preview](../images/browser-common-ground/core-expanded-preview-dark.png) show the primary third column. The [encoded-blend light preview](../images/browser-common-ground/core-encoded-preview-light.png) and [dark preview](../images/browser-common-ground/core-encoded-preview-dark.png) show the separate composition control. Each retains 75%, 50%, and stock Qt. Their narrow panels show 8pt and 11pt. The linked analysis provides all nine integer sizes and the fixed 16pt reference.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/core_contrast_test.py results/segment-curve \
  --native-build build/radius-trace \
  --output results/core-contrast \
  --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')"
```

Prepare the existing stock/nearest libraries, native probe, and nearest/segment ownership builds before this command. The previous sections preserve the source, trace-header, and instrumentation-patch recipe. The checker builds only a private chart copy. It captures the six rejected/control rows at integer 8pt and 11pt for 8/3/5/v through both ownership libraries. It verifies the loader's uniform horizontal translation after hint-save before matching public outlines. The [capture record](../images/browser-common-ground/core-contrast-captures.json) retains the native identities, middle-row profiles, 24 paired ownership observations, and twelve image hashes.

The checker independently verifies 11,583 native glyph masks, expanded coordinates, floors, overlap, and high-precision blending. It reopens every saved native and enlarged crop. For desktop delivery, open both main panels at 100% zoom. Verify the intended filename, mapped window, and exact saved-PNG/window-capture equality. A successful image opener or fit-to-window view is insufficient. Keep application presets unchanged and obtain visual judgment before selecting another treatment.

## Exact experiment

The candidates force FreeType automatic monochrome hinting, then rasterize grayscale masks. A per-glyph coverage floor raises values from the cutoff through 241 to 242. The cutoff is 128 for light faces and 160 for regular or heavier faces. Candidate glyphs use whole-device-pixel origins, alpha-over composition, and linear-light black/white blending encoded to sRGB.

The original strong Y-width rule in `af_latin_compute_stem_width` rounds with `(dist + 16) & ~63`. One pixel is 64 units. That gives a 75% remainder threshold for horizontal-stroke thickness. The experiment changes only 16 to 32, giving a 50% threshold. Standard-width matching still runs first. This does not replace stem detection or every alignment rule. The X-width monochrome branch already rounds at 50%.

The [experimental patch](../../patches/freetype-2.14.2-nearest-y-experiment.patch) applies to clean FreeType 2.14.2. It is separate from the deployed browser patch. Do not stack the old width-override experiment or set `FONTREAL_TEST_STROKE_WIDTH` for this comparison. Retain FreeType's source notices and license when distributing modified FreeType.

The corrected [small-point sheets](16pt-geometry.md#smaller-points-and-explicit-italic-comparisons) show 75% fitting, 50% fitting, and stock Qt. The [capture record](../images/browser-common-ground/stockqt-smallpt-captures.json) identifies fonts, source strips, layouts, sizes, and image hashes. These are lossless component images. View them at one image pixel per display pixel.

The reference capture uses Qt 6.10.2, FreeType 2.14.2, 96 logical DPI, and 100% scale. Qt resolves points as follows:

| Requested pt | 8 | 9 | 10 | 11 | 11.25 | 12 | 13 | 14 | 15 | 16 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Resolved px | 11 | 12 | 13 | 15 | 15 | 16 | 17 | 19 | 20 | 21 |

All 22 faces and ten sizes form 220 conditions. The corrected sheets display ten faces, including six italic or bold italic faces. The full original [point-size record](../images/browser-common-ground/point-benchmark242-captures.json) retains the 22-face selection and font hashes.

For Noto Sans Regular, 75% and 50% produce identical pixels at all tested points below 16pt. Changing this constant alone cannot improve those rows. At 16pt, the n crown grows from about 0.981px to 1.953px, while its upright stays near 2px. Raw crown-column coverage changes from `[250, 9, 0, 0]` to `[246, 255, 8, 0]`. This fixes that particular two-pixel crown. It does not establish a general solution.

The [16pt geometry analysis](16pt-geometry.md) compares original outlines, traced Qt outlines, and candidate outlines. Original Qt is closer to source geometry than the original 75% benchmark under the recorded contour metric. The 50% change improves twelve face averages, leaves nine unchanged, and slightly worsens Noto Sans Bold Italic. Geometric error is not a readability score. The [nearest-Y record](../images/browser-common-ground/nearest-y-captures.json) retains the measurements and build identity.

## Rounded-edge trial

The [rounded-edge analysis](16pt-geometry.md#rounded-edge-optical-expansion) adds one diagnostic after the 50% rule. It expands a horizontal stroke by 1/8px only when both linked edges carry FreeType's round flag. The [separate patch](../../patches/freetype-2.14.2-round-y-experiment.patch) includes the 50% change and applies to clean pinned source. Do not stack the two patches. Native traces expose the original width, standard-matched width, rounded width, flags, and expanded width.

This trial uses Qt 6.8.2 and an offscreen 96-DPI baseline. All four Hack font hashes differ from the earlier captures. The other nine faces match. It measures 130 conditions across thirteen faces and the same ten point sizes. Stock Qt, 75%, and 50% remain visible beside the trial. The [capture record](../images/browser-common-ground/round-y-captures.json) includes build identity, paired native traces, raw profiles, and six sheet hashes.

The trial changes 488 n/3/5/8 conditions and preserves all X coordinates. V, W, and w remain identical to 50%. Lowercase v changes in nineteen Noto Serif italic conditions. Its rounded terminal fitting moves other points through interpolation. Lato Light at 15px follows another path: its Y axis is extra-light, so width fitting returns before either rounding or this expansion. Neither result supports a general deployment.

The checker is `tests/curve_contrast_test.py`. It consumes four folders from the unchanged point chart: `75/`, `50/`, `round/`, and `qt/`. It also consumes `build.json`, `round.trace`, and `trace-samples.json` beside those folders. The capture record preserves the schema and exact trace samples. `build.json` records the source hashes, compiler flags, Qt version, renderer hash, patch hashes, and three private library hashes. Build all three with `CFLAGS='-O2 -DFT_DEBUG_LEVEL_TRACE'` and the same configuration. Capture the round chart's complete standard error with `FT2_DEBUG=aflatin:5` into `round.trace`.

Use the same font basenames as the point-size record. Select the twelve Noto Sans/Noto Serif/Hack style combinations and Lato Light. For a fresh baseline, explicitly record changed hashes rather than claiming an earlier capture. The stock chart still determines actual point sizes, glyphs, and positions. The paired trace samples use the unchanged native probe with flags `0x20028`, render mode `0`, no translation, two repeats, transform `none`, and no removed auto-hinter. Capture both nearest and round libraries for Noto Sans n at 15px and 21px, Lato Light n at 15px, and Noto Serif Italic v at 15px. Their corresponding point labels are 11.25pt and 16pt.

With these inputs under `results/radius-trace`, run the checker against the three private libraries:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/curve_contrast_test.py results/radius-trace \
  --libraries build/radius-trace/stock/.libs/libfreetype.so \
              build/radius-trace/nearest/.libs/libfreetype.so \
              build/radius-trace/round/.libs/libfreetype.so \
  --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')" \
  --output results/radius-trace/verified
```

The checker verifies 12,870 independent native rasters, fixed coverage and blend, complete keys, native trace contrasts, and saved pixels. Its assertions establish faithful component evidence. They do not require a visual winner or conceal diagonal changes. The recorded six sheets display 8pt, 11.25pt, and 16pt on both backgrounds. No application preset changes.

## Segment-pair preview

The [next trial](16pt-geometry.md#mutual-segment-pairs-preserve-the-tested-diagonals) narrows the gate to actual mutually linked round segments. It uses the [standalone segment-pair patch](../../patches/freetype-2.14.2-segment-y-experiment.patch) on clean pinned source. This patch includes nearest-Y fitting. Do not stack it with either earlier patch. A wrapper preserves the original width result, then adds signed eight units once for an eligible strong-Y pair. Extra-light curves retain their fractional width plus that expansion.

This preview changes all 520 measured n/3/5/8 cases. All 520 V/v/W/w cases remain identical to 50%, including the earlier nineteen serif italic v changes. All X coordinates remain unchanged. The 130-condition environment, coverage, fonts, and stock Qt control match the rounded-edge trial. The third column in the [compact light preview](../images/browser-common-ground/segment-y-preview-light.png) and [compact dark preview](../images/browser-common-ground/segment-y-preview-dark.png) is the new candidate. These are concrete visual comparisons, not an accepted application preset.

The new study uses `results/segment-curve`. Its `75/`, `50/`, and `qt/` folders retain the prior controls. Its `round/` folder contains the new candidate. Its `prior-round/` folder retains S5's old candidate for ownership comparisons. Update `build.json` and capture the new `round.trace` with `FT2_DEBUG=aflatin:5`. Pair the unchanged probe under nearest and segment-pair libraries for the earlier four cases plus Lato Light n at 21px. Preserve all ten records in `trace-samples.json`.

For ownership traces, copy the nearest and S5-round sources privately. Apply the [trace patch](../../tests/freetype_curve_trace.patch) and force-include the [trace header](../../tests/freetype_curve_trace.h). Build with `-O2 -DFT_DEBUG_LEVEL_TRACE -DFT_DEBUG_AUTOFIT`. Use `FT2_DEBUG=aflatin:6,afhints:7,afmodule:7`. The native tables record segment/edge ownership and strong-point references. The header adds snapshots after edge, strong, weak, final-separation, and save stages. Capture nearest and S5-round for Noto n at 15px, serif italic v at 15px, and Lato n at 15px and 21px. The new record's `ownership` object preserves the `ownership.json` input schema, header/patch hashes, all eight cases, and native tables.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/curve_contrast_test.py results/segment-curve \
  --segment-pairs \
  --libraries build/radius-trace/stock/.libs/libfreetype.so \
              build/radius-trace/nearest/.libs/libfreetype.so \
              build/radius-trace/segment/.libs/libfreetype.so \
  --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')" \
  --output results/segment-curve/verified
```

The [capture record](../images/browser-common-ground/segment-y-captures.json) includes 6,977 independently checked width decisions, 12,870 independent native masks, and eight verified images. The default checker mode still reproduces the earlier edge-level trial. Human judgment of the third column is the next input, especially whether the small-size curve weight is useful. Continue through findings until there is a concrete preview, blocker, or actionable handoff.

## Resume on another machine

Clone the repository and select the task branch:

```sh
git clone git@github.com:calculatetech/fontreal.git
cd fontreal
git switch feature/gtk-rendering
```

Builds and raw results are ignored. They are not transferred by Git. Configure `build/` and `results/` on a suitable storage volume before building. Existing symlinks are local configuration and are not part of the checkout. Keep new output under those two roots. The committed images and capture records remain available without rebuilding.

The preserved [C++ fixture](../../tests/point_benchmark_chart.cpp) is the exact renderer used for the point experiments. Its `stock` mode uses Qt's painter with Fontreal disabled. Its `candidate` mode consumes the recorded Qt layout and uses the selected FreeType library. The [sheet assembler](../../tests/point_benchmark_sheets.py) copies native pixels from those outputs and checks every saved crop.

Use a C++17 compiler, Qt 6 Gui development files, FreeType development files, `pkg-config`, Fontconfig, Python 3, and Pillow. Run from a graphical Qt session at 96 logical DPI and 100% scale for the reference comparison. The assembler rejects other recorded DPI or scale values. Different Qt, FreeType, Fontconfig, or font versions need a fresh recorded baseline.

Prepare the 220 inputs from installed font files. This checks exact font hashes and stops if a reference font is unavailable. Install the matching font version before retrying. Do not silently substitute a font.

```sh
mkdir -p build/point-handoff results/point-handoff
python3 - <<'PY'
from pathlib import Path
import hashlib, json, subprocess
record = json.loads(Path('docs/images/browser-common-ground/point-benchmark242-captures.json').read_text())
files = [Path(p) for p in subprocess.check_output(['fc-list', '-f', '%{file}\n'], text=True).splitlines()]
rows = []
for r in record['conditions']:
    matches = [p for p in files if p.name == r['font_file'] and hashlib.sha256(p.read_bytes()).hexdigest() == r['font_sha256']]
    assert matches, 'Missing exact font: ' + r['font_file']
    rows.append({k: r[k] for k in ('id', 'label', 'point_size', 'cutoff')} |
                dict(font_path=str(matches[0].resolve()), logical_dpi=96, scale=1))
assert len(rows) == 220
Path('build/point-handoff/input.json').write_text(json.dumps(rows, indent=2) + '\n')
PY
c++ -std=c++17 -fPIC -include algorithm tests/point_benchmark_chart.cpp \
  $(pkg-config --cflags --libs Qt6Gui freetype2) -o build/point-handoff/chart
```

Use two isolated builds from the same FreeType source and build configuration. Keep one unchanged and apply the experimental patch to the other. The original native builder, `tools/build-freetype.py`, requires its exact Ubuntu amd64 package revision. It is not a generic Debian 13 builder. On other systems, build the research libraries locally from the pinned source with that system's development dependencies. Do not install an Ubuntu library into Debian.

The pinned source archive is `freetype_2.14.2+dfsg.orig.tar.xz`, SHA-256 `9a2bdc2c992fa82a309eccf5e8bcbf2a380a98ba22f9f2ec7e56767739a19a0a`. The authenticated source inventory and download location are in [the native builder](../../tools/build-freetype.py). Extract it into a clean storage-backed directory. The original `src/autofit/aflatin.c` SHA-256 is `30189813d762de77aea2a0d9010a6b7656657809028ac433f92b3c027eeda7f7`. Make sure that this hash matches before applying the patch. Apply it with `patch --batch -p1 -i` and the absolute patch filename, from the copied source root.

For both builds, use `CFLAGS=-O2` and `configure --with-harfbuzz=dynamic` in separate build directories. Retain the same zlib, bzip2, PNG, HarfBuzz, Brotli, and pthread features. Save configuration logs, source hashes, exported-symbol comparisons, and new library hashes. Compiler and dependency changes can alter binary hashes. The old hashes identify the earlier builds and are not expected outputs for another toolchain.

Set `FONTREAL_STOCK_FT_DIR` to the unchanged build's `.libs` directory. Set `FONTREAL_NEAREST_FT_DIR` to the patched build's `.libs` directory. Then render all three columns:

```sh
python3 - <<'PY'
from pathlib import Path
import os, subprocess
base = {k: v for k, v in os.environ.items()
        if not k.startswith('FONTREAL_') and k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'FREETYPE_PROPERTIES')}
base['FONTREAL_RENDERING'] = '0'
stock = str(Path(os.environ['FONTREAL_STOCK_FT_DIR']).resolve())
nearest = str(Path(os.environ['FONTREAL_NEAREST_FT_DIR']).resolve())
out = Path('results/point-handoff')
steps = [('stock', stock, 'build/point-handoff/input.json', out/'stock'),
         ('candidate', stock, str(out/'stock/rows.json'), out/'75'),
         ('candidate', nearest, str(out/'stock/rows.json'), out/'50')]
for mode, library, source, target in steps:
    env = dict(base, LD_LIBRARY_PATH=library)
    if mode == 'candidate':
        env['FREETYPE_PROPERTIES'] = 'autofitter:no-stem-darkening=1'
    subprocess.run(['build/point-handoff/chart', mode, source, str(target)], env=env, check=True)
PY
python3 tests/point_benchmark_sheets.py \
  results/point-handoff/75 results/point-handoff/50 results/point-handoff/stock \
  results/point-handoff/sheets --label-font "$(fc-match -f '%{file}' 'DejaVu Sans')"
```

The stock column keeps Qt's own fitting, coverage, glyph origins, and blending. Both candidates consume the same Qt glyph identities and positions, then apply their own whole-pixel origins. Stock Qt reflects the desktop's font configuration. It is not a universal KDE configuration. Record that configuration on the new machine before attributing a difference to the patch.

The corrected images and native fixture were checked against all earlier 220 stock, 75%, and 50% outputs on the capture system. The new-machine rebuild itself remains untested. Before experimenting further, reproduce the Noto n crown result and check native masks independently with the existing `Oracle` in `tests/browser_stroke_axis_test.py`. Keep per-glyph floor, overlap, and final blend checks separate from geometry checks. The saved sheet checks alone do not prove the rasterizer correct.

## Next investigation

Continue real-world qualification of fully raw coverage with nearest-50% geometry and encoded blending. The latest user selection supersedes the continuous ramp and native support floor in the normal preset. Native outline expansion, inner-hole adjustments, adaptive coverage rules, and an Arial-specific exception are not selected. Preserve earlier modes for research replay while collecting actual browser defects.

Use stock Qt, the original 75% benchmark, and the 50% reference in every chart. Include Noto Sans, Noto Serif, Hack, and a light face. Keep i/l/I/1, 3/5/8, V/W, full words, italic, and bold italic visible. Use actual integer points 8–16 and retain the fixed 16pt reference. Do not vary coverage thresholds while testing fitting geometry. Keep the encoded-blend diagnostic separate. Define a bounded experiment before changing further native rules.

The user authorizes building and applying this recipe to ordinary live Firefox and Floorp. Qualify downloaded and variable fonts, both backgrounds, small labels, headings, and mixed styles. Keep the user's working browser data and normal sandbox. Further coverage includes Electron/Teams and Flatpak, GTK/GNOME, Wine, and a feasibility study for Windows 11. Their order and remaining requirements belong to the roadmap.

The existing [Qt package workflow](../build-system.md) targets the running Debian 13 or Ubuntu system. The [browser activation guide](../experiments/browser-masks.md) owns deployment and reversal of this browser recipe. It supports exact matching Debian 2.13.3 and Ubuntu 2.14.2 providers. This browser change does not deploy a new Qt build or replace host packages.
