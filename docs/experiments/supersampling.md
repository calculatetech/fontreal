# Font supersampling experiment

Supersampling draws a font at higher resolution, then reduces it. This experiment compares 2× and 4× drawing with native rendering at 96 DPI. It does not change the installed profile.

Build the paired FreeType libraries with `python3 -B tools/build-freetype.py`. The last output line names a `build.json` file. Use that file as `FREETYPE_BUILD_JSON` below. The experiment needs a C++ compiler, Qt 6 Core development files, FreeType development files, Fontconfig, Python, and Pillow.

Install Noto Sans Display, Liberation Mono, and Nimbus Sans Regular. Nimbus Sans supplies the CFF font control. The experiment stops if a required family is missing.

```sh
python3 -B tools/supersampling.py --record FREETYPE_BUILD_JSON
```

The command prints its results directory. Open that directory's `gallery` folder in Gwenview. Use 100% image zoom. Arrow keys move between fonts, sizes, and light or dark backgrounds. The sheets cover 8–16pt. Each sample uses native pixels.

| Column | Rendering |
| --- | --- |
| A | Untreated FreeType at native resolution |
| B | Current Fontreal at native resolution |
| C | Native hints at 2×, area reduction, untreated coverage |
| D | The same 2× reduction, then Fontreal |
| E | Native hints at 4×, area reduction, then Fontreal |
| F | Native-size hints enlarged to 4×, area reduction, then Fontreal |
| G | Native hints at 4×, Lanczos reduction, then Fontreal |

Hints fit outlines to pixels. Column F preserves the native hinted shape. Columns C, D, E, and G recalculate hints at higher resolution. This can change the shape. Area reduction averages coverage. Lanczos uses a sharper filter that can introduce faint fringes. All reductions operate on coverage before color blending. Fontreal processes each corrected mask once, at final resolution.

FreeType already calculates outline coverage accurately. Extra resolution alone does not guarantee sharper text. See the [FreeType FAQ](https://freetype.org/freetype2/docs/ft2faq.html) and its [transformation rules](https://freetype.org/freetype2/docs/reference/ft2-sizing_and_scaling.html#ft_set_transform).

All columns share native whole-pixel spacing, line breaks, and encoded blending. These are FreeType raster comparisons, not stock Qt captures or shaping tests. The first study uses regular faces only. The images cannot establish a readability winner without visual assessment.

The results include raw outlines, high-resolution masks, reduced masks before correction, final masks, native text crops, and a manifest. The manifest records font and provider identities, code hashes, crop coordinates, and image hashes. Build data and results use the repository's configured `build` and `results` roots. Each run creates a new results directory.

To run the focused numerical check and retain its complete gallery:

```sh
python3 -B tests/supersampling_test.py --record FREETYPE_BUILD_JSON
```

The check compares reductions with independent references, preserves the accepted native baseline, and checks exported pixels. It does not choose a preferred appearance.

## Scalar 4× and stem darkening

Use the same build record and fonts for the current stock study:

```sh
python3 -B tools/supersampling.py --record FREETYPE_BUILD_JSON --stock4x
```

Open its `gallery` folder in Gwenview at 100% zoom. Each of the 54 sheets covers one regular font, point size and background. Scroll down for more panels. Arrow keys change the condition. The range remains 8–16pt.

Every panel starts with untreated 1× and current Fontreal 1×. The remaining columns pair each 4× setting with stem darkening Off and On. The stock study has no 2× column, subpixel settings or vertical LCD settings. The original A–G command still retains its earlier 2× and 4× comparisons.

The retained 4× settings cover unhinted grayscale, native and automatic NORMAL/LIGHT/MONO hint targets, and monochrome sources. Available distinct older TrueType interpreters and CFF engines have labeled comparisons. The manifest records actual availability and effective values. Aliases and unavailable choices receive no substituted image.

Stem darkening uses FreeType's existing boolean property. The probe sets `no-stem-darkening` to the inverse of the requested state on both the CFF driver and auto-hinter. It records actual set/get results before opening a fresh face and loading glyphs. Custom darkening amounts are not used.

The switch applies to automatic hinting and the native Adobe CFF engine. Native TrueType can remain unchanged. FreeType calculates darkening from raster stroke width, so 4× strokes can receive little or no extra width. Identical Off/On pixels are valid results. See the [FreeType property contract](https://freetype.org/freetype2/docs/reference/ft2-properties.html#no-stem-darkening) and [darkening curve](https://freetype.org/freetype2/docs/reference/ft2-properties.html#darkening-parameters).

All 4× rows remain untreated by Fontreal. The exporter decodes grayscale bytes or packed monochrome bits, then averages coverage in exact 4×4 blocks. It uses the original native spacing and encoded blending. The output is grayscale at native pixel dimensions.

The focused check runs both studies and verifies actual provider properties, independent raw decoding, area means, native pixels, and every panel's two fixed references. Independent probes from immutable `ff63a7f` use `FREETYPE_PROPERTIES` for both states. They compare native CFF and automatic 4× captures with the real stock export. A lower-density capture verifies that the provider can apply darkening when 4× pairs are identical. This diagnostic is not another gallery treatment.

The check also runs the original exporter from `ff63a7f` in a temporary private build tree. That commit must exist in local Git history. Every original glyph capture, outline, mask, advance and placement, plus all 378 original native crop hashes, must match. Temporary reference trees are removed after use. The original seven columns retain their behavior.

The earlier stock subpixel study remains in Git at `60fed5e`. Its unused rendering paths are removed from the current implementation. The installed profile and appearance selection do not change automatically.

## Accepted D with compact-feature darkening

The current native study keeps the exact accepted D rendering and adds two compact-feature treatments. Larger connected strokes keep their accepted appearance. This replaces the rejected broad weighted-stem and crown trial.

Install genuine Noto Sans, Nimbus Sans, Inconsolata Nerd Font, Arial and Hack Regular faces. The native command checks family identity instead of accepting an unrelated Fontconfig fallback. Arial can list Regular among several language aliases. The manifest retains actual face metadata.

```sh
python3 -B tools/native_stems.py --record FREETYPE_BUILD_JSON
```

Open the printed directory's `gallery` folder in Gwenview at 100% zoom. Its 40 native sheets and 20 numbered grids cover all five families at 8, 10, 11 and 12pt. Both backgrounds use the same masks. The grids show H, i, n, m, 8, W, colon and exclamation at every requested size.

| Column | Rendering |
| --- | --- |
| A | Untouched native 1× MONO hints with grayscale coverage |
| D | The exact accepted connected rendering from `1ba7c1d` |
| F | D with compact peaks raised toward the raw weighted target |
| G | D with proportional intensity across each eligible compact component |

The target is the existing coverage-weighted average of the strongest quarter of positive raw pixels, including cutoff ties. D retains the committed near-tie concentration, connected profiles and native corner-fringe selection. Its geometry and values stay exact. No new stem targeting, crown pass or geometry-pair lifting runs.

The compact filter finds whole positive components in frozen D. Pixels connect across shared edges or corners. Only components with bounds at most 3×3 can qualify. If a component's peak is below the target, F raises every tied peak to that target. G scales all its positive pixels by the same target-to-peak ratio, with integer rounding. If the peak is already at or above the target, both treatments leave the entire component unchanged.

The filter uses D for membership, eligibility and proportional values. It never rescales raw fringes after D already fits them. Zero pixels stay zero. Disconnected components cannot borrow support across a gap. Proposals do not feed later proposals. Every pixel outside eligible compact components remains exactly D.

This same rule can affect other small connected marks. It does not select weak subsets inside larger strokes. W, V and Y remain D throughout the current font and size matrix. Longer weak connected strokes remain outside this trial. Human comparison selects the preferred dot strength and softness.

All four columns share native glyph bounds, whole-pixel advances, wrapping and encoded blend. FreeType stem darkening stays on. Earlier supersampling commands, production processing and installed applications remain unchanged.

The `diagnostics` directory separates historical Noto Sans Display 12pt masks, actual small-font inputs and explicitly labeled synthetic masks. The Regular 10pt i keeps D's 240/60 stem and faint tail. Its 202/66 dot becomes 220/66 in F or 220/72 in G. A fitted 240/28 compact component becomes 255/28 in F or 255/30 in G. Retained contrasts also cover tied peaks, saturation, gaps, repeated components and components exceeding the width or height limit by one. Synthetic masks have no font or point-size claim.

The manifest records actual provider, font, source and fixture hashes, native controls, frozen D, all component decisions, exact output masks and image coordinates. Build data and results stay in the configured ignored roots. The focused check follows actual export through native pixels, grids and all retained synthetic contrasts:

```sh
python3 -B tests/native_stems_test.py --record FREETYPE_BUILD_JSON
```

The prior connected study remains in Git at `1ba7c1d`. This experiment covers Regular only and does not select production presets. Intensity changes can alter apparent weight even when pixel support stays fixed. Human assessment remains necessary for softness and readability.

## Same-glyph pixel references

This focused study compares Noto Sans Regular at 12pt and 96 DPI. It measures a reference for each pixel from the same hinted outline. It does not use a shared intensity target. The existing native matrix, production renderer and installed applications stay unchanged.

Install genuine Noto Sans Regular and use the paired build record described above:

```sh
python3 -B tools/pixel_references.py --record FREETYPE_BUILD_JSON
```

Open the printed directory's `gallery` folder in Gwenview at 100% zoom. The two overview sheets share native whole-pixel advances, wrapping and encoded blending. Both backgrounds use identical coverage masks. Numbered i, 8 and exclamation grids show input coverage, references, offsets and final values. Analytic diagnostics use supplied numerical outlines and explicitly identified upstream masks. They have no font or point-size claim.

| Column | Rendering |
| --- | --- |
| A | Untouched native MONO hints with grayscale coverage |
| D | Exact accepted native baseline, without the compact filter |
| R | Same native hinted outline at 4×, reduced at its original position |
| O | D plus weak-core offsets from a coherent component reference |
| L | D plus weak-core offsets from a local pixel reference |
| S | L plus reference-bounded edge offsets |

The exporter first reproduces all 95 native ASCII masks through an independent public FreeType outline call. It requires exact equality with A. It then multiplies those same native outline coordinates by four and rasterizes once. It does not reload the font at a higher DPI or recalculate hints. Explicit bearings and padding keep every method on one coordinate frame.

The reference search tests 25 placements, from −0.5 to +0.5 native pixels in quarter-pixel steps on each axis. Each reference value is the rounded coverage of a 4×4 footprint. R uses the original placement. Curve rasterization precision can make R slightly different from A. The results record that difference without treating it as an error.

The coherent reference C chooses one placement for each whole connected component in D. Its score measures squared coverage, with deterministic ties. Disconnected regions choose independently. The local reference E considers placement across each pixel's shorter positive run. Equal run lengths allow both axes. This preserves the row position of a vertical taper. The numbered grids retain both C and E, although they are not additional overview columns.

A primary pixel must have at least 128 coverage and form a local ridge across that shorter run. Equal run lengths require a ridge on both axes. Tied ridges can both qualify. O adds the positive difference between C and D at primary pixels. L does the same with E. A pixel already as strong as its own reference stays unchanged. Zero pixels never acquire ink. There is no collected intensity average or saturation clamp.

S also considers positive neighbors of lifted primary pixels. It scales each eligible neighbor by that core's final-to-original ratio, with half-up rounding. Its proposal cannot exceed that neighbor's own E value. Multiple proposals use their maximum, from frozen inputs. No proposal feeds another proposal. All three stored overlays contain only positive byte offsets. Adding an overlay to D produces the saved final mask directly.

The local envelope is not one simultaneously realizable placement. The tied-stem diagnostic makes this limitation visible. This provider produces 127/127 native coverage for its exact half-pixel rectangle, and the native D recipe keeps those values. A separate, explicitly supplied analytic D of 128/128 exercises the majority gate. L raises both columns to 255 using opposite phases. O raises only one, retaining the other at 128. The extra local coverage can overdraw an undecided stem. No clipping does not imply no excess weight. The native 127/127 contrast remains unchanged because it falls below the gate.

The results retain source outlines, the padded high-resolution raster, all phase sums and component scores, local axes, coverage totals and positive overlays. The manifest binds provider, font, contributor and fixture hashes to exact masks, crops, grids and labels. Public fixtures use filenames and hashes. Generated data stays in the configured ignored build and results roots.

`benchmark.json` reports three numerical repetitions over all 95 actual glyphs. It separates native rasterization, one 4× raster and placement, reference construction from that raster, overlay construction and stored-overlay addition. Each stage records median, 95th percentile and total time, with byte checksums and exact payload sizes. Compilation, font lookup, provider capture and image export are excluded. Byte counts exclude Python object overhead.

These are Python prototype and FreeType call timings. They do not forecast a production frame time. A renderer can retain the final mask instead of supersampling at every repaint. This study adds no cache framework and makes no measured cache-speed claim.

Run the focused numerical and image check with the same record:

```sh
python3 -B tests/pixel_references_test.py --record FREETYPE_BUILD_JSON
```

The check uses actual native inputs and independent analytic geometry. It verifies registration, every phase footprint, component choices, local axes, offsets, timing associations and final exported pixels. Human comparison must still assess softness, weight and readability. The local reference is an experimental geometric hypothesis, not proof of a font author's intended opacity.

## Broader O and L comparison

The broader comparison tests O and L across more fonts and sizes. It excludes S because its edge lifting added unwanted jaggies. This changes the comparison scope, not the numerical treatment.

Install genuine Regular faces of Noto Sans, Nimbus Sans, Inconsolata Nerd Font, Arial and Hack. The exporter rejects unrelated family fallbacks and matches without Regular among their style aliases. Genuine Arial can list Regular with other language aliases.

```sh
python3 -B tools/pixel_references.py --record FREETYPE_BUILD_JSON --matrix
```

Open the printed directory's `gallery` folder in Gwenview at 100% zoom. Arrow keys move through forty overview sheets. Each family appears at 8, 10, 11 and 12pt on both backgrounds. Every sheet shows exactly A native raw, D accepted baseline, O coherent weak-core offsets and L local weak-core offsets. Each condition uses the complete specimen, its own native spacing and its actual point size. Crops are pasted without resizing.

The matrix compiles the shared probe once. It retains all 95 ASCII records per condition, including outlines, controls, high-resolution sources, references and offset audits. Distinct capture, input, mask and image paths bind every result to its condition. Detailed numerical files stay outside the gallery. The matrix exports 160 native crops without duplicating the focused grids, analytic diagnostics or benchmark.

The no-selector command above still produces the original six-column Noto Sans 12pt study and its diagnostic and performance evidence. The numerical kernel, native matrix and installed rendering stay unchanged. The local envelope still can add excess ink. Human comparison must select the preferred softness and readability.

Run the broader check separately from the focused check:

```sh
python3 -B tests/pixel_references_test.py --record FREETYPE_BUILD_JSON --matrix
```

It independently checks all twenty conditions and all native image pixels. Retained Noto Sans 12pt pins preserve exact overlap with the focused study. The check also exercises family and style rejection through the real command while retaining a genuine font file.

## Gentler edges for L

L usefully fills weak details, especially for white-on-black terminals, but can add jaggies. This separate study compares two smaller fractions of the existing S edge lift. It preserves all L core values.

First run the matrix command above. Keep that complete results directory and use its `manifest.json` as `MATRIX_MANIFEST`. The retained producer sources and original font files must still match their recorded hashes. The new command reads these records without capturing, compiling or rasterizing the measured glyphs again. Fontconfig and image-font drawing supply labels.

```sh
python3 -B tools/pixel_reference_smoothing.py --source-manifest MATRIX_MANIFEST
```

Open the printed directory's `gallery` folder in Gwenview at 100% zoom. Its forty sheets cover the same five Regular families and four sizes on both backgrounds. Each sheet shows A/D/O/L/T/U. A separate native `() () i8! W` strip provides curve, detail, taper and diagonal controls. The complete source specimen follows below. Original A/D/O/L body crops remain byte-identical to the source images.

For each pixel, the existing edge increment is `e=S-L`. T adds `(e+2)//4` to L. U adds `(e+1)//2`. These quarter and half increments use nonnegative half-up rounding. Each result uses frozen L/S inputs once. Neither trial weakens L or changes its primary cores. Zeros and pixels without an edge increment remain unchanged. Both trials stay within S and its existing reference bound.

For example, an L fringe of 125 with an S value of 225 becomes 150 in T or 175 in U. A one-byte increment contributes zero to T and one to U. A two-byte increment contributes one to both. This changes edge amplitude without a blur, new reference, clamp or cascading update. Added fringe coverage can still make a stroke heavier. Human comparison must determine whether it reduces the unwanted jaggies.

The `diagnostics` folder contains forty numbered O/L/T/U grids for both parentheses in every condition. Native previews are not resized. Orange borders identify T/U fringe additions to L. Saved cells retain original L/S values, final coverage and row/column coordinates. Numerical records cover all 1900 retained glyphs, with their own geometry, advances and source hashes. Relative source links require the original matrix directory to remain available.

Run the focused check against that same source manifest:

```sh
python3 -B tests/pixel_reference_smoothing_test.py --source-manifest MATRIX_MANIFEST
```

The check runs the real entry point with fail guards at native compilation, capture and outline-raster boundaries. It independently reconstructs all trials, native images, sheets and coverage grids, and rehashes the source afterward. Existing focused and matrix commands remain unchanged. This experiment selects no production profile and makes no production performance claim.

## Arial hinting and local phase coherence

The user tentatively prefers U overall, while profile O still works best for Arial. Arial Regular at 10pt and 11pt needs a separate source check. The capital glyph O can look poor across several treatments. Both parentheses expose the curved-edge jaggies. This study separates native hinting evidence from two new reference trials.

Use the paired build record and the retained matrix manifest from the commands above. Keep the matrix directory and matching fonts and producer sources available.

```sh
python3 -B tools/arial_coherence.py --record FREETYPE_BUILD_JSON --source-manifest MATRIX_MANIFEST
```

Open the printed directory's `gallery` folder at 100% zoom. Its sixty sheets contain eight raw-source comparisons, twelve fixed-outline geometry views and forty retained-trial comparisons. Both native branches show the complete specimen and the exact `() O O i8! W` focus strip. Profile O means the rendering treatment. Glyph O means the capital letter.

The raw study covers Noto Sans and Arial Regular at 10pt and 11pt. Its separate probe reuses the unchanged FreeType capture implementation. Four policies compare native MONO, native NORMAL, automatic MONO and unhinted MONO targets. All render grayscale at 96 DPI with scale one, interpreter 40 and stem darkening off. No coverage profile processes these source masks. The panels share retained MONO spacing and baseline. Actual advances are recorded separately, and wider sources are not recentered or resized.

The captured Arial O changes width between native targets: NORMAL/MONO gives 10/8 pixels at 10pt and 11/10 at 11pt. Corresponding points move horizontally by up to 64/64 and 30/64 pixels. The checked Noto Sans O and parentheses retain identical outlines between these two targets at both sizes. Identical outlines here do not mean that the font lacks native instructions. These measurements identify a source difference without proving that hinting explains every visual defect.

The geometry sheets rasterize the captured outline coordinates at eight times their size. They are explicitly non-native geometry evidence. They do not resize a native bitmap or reload the font at a higher DPI. Bearings, common frames, baselines and point differences against the unhinted outline remain recorded. Curve types use FreeType's tag semantics while all original hint-tag bits remain intact. These views do not rank beauty or define an ideal opacity.

The retained branch uses the unchanged twenty-condition matrix and all 1900 glyph records. It shows exact A, profile O, L and U controls beside K3 and K5. D stays exact in the numerical records. K3 uses a 3×3 neighborhood, and K5 uses 5×5. Each primary pixel considers only positive D pixels in its own connected component. A nearby disconnected dot cannot lend support.

For each neighborhood, the trial scores the existing phase footprints by squared coverage. It considers only the shifts permitted by that pixel's original local axis. Deterministic ties use shift distance, then vertical and horizontal position. The selected phase supplies that pixel's reference. The new core is at least D. Both trials add the same half-edge increment as U. Other pixels match U exactly.

K3 and K5 can reduce L's primary-core values. This is a change in reference selection, unlike T/U's preserved L cores. Both trials stay between D and U and within the existing reference bound. They add no blur, clamp, new raster or recursive update. Local phase changes can still produce jaggies. Human comparison must select the preferred balance.

The `diagnostics` folder contains Arial 10pt and 11pt phase grids for both parentheses and glyph O. They expose component-wide C, per-pixel E and the K3/K5 choices, with actual coverage, coordinates and neighborhood audits. Native body controls preserve the source pixels. Source records and input trees remain unchanged, and relative links require the retained matrix to stay available.

Run the composed check with the same inputs:

```sh
python3 -B tests/arial_coherence_test.py --record FREETYPE_BUILD_JSON --source-manifest MATRIX_MANIFEST
```

The check independently verifies all 1520 focused captures and 1900 retained trials, including native and eight-times outline rasters. A non-mutating observer ties each numerical argument to the actual hashed retained loader by object identity. Equal newly allocated data must fail that origin check. The check also reconstructs every native image, geometry view and phase grid. Existing commands and installed rendering stay unchanged. This study selects no production profile and makes no performance claim.
