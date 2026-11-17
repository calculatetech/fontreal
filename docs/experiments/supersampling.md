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

## Native MONO-gray and stem cleanup

The next experiment uses the selected native 1× MONO hints with grayscale edges. MONO here selects hinting. The raster still contains gray coverage values. This differs from a black-or-white mono bitmap and from reducing a 4× image.

Use the same paired build record and three regular fonts:

```sh
python3 -B tools/native_stems.py --record FREETYPE_BUILD_JSON
```

Open the printed directory's `gallery` folder in Gwenview at 100% zoom. Arrow keys move between 54 native comparisons and six numbered coverage grids. The samples cover 8–16pt on both backgrounds. The grids focus on H, n, m, 8, W, colon and exclamation at 11pt and 12pt.

| Column | Rendering |
| --- | --- |
| A | Native 1× MONO hints with untouched grayscale coverage |
| B | Existing conservative stem cleanup, without other Fontreal passes |
| C | The same cleanup with a trial for near-equal split stems |
| D | Column C plus weighted darkening of each selected core and its blend |

Columns B and C move existing coverage between two pixels of a stable straight run. Every changed pair and complete glyph keeps its original total coverage. Other pixels, bitmap bounds, advances and line breaks stay unchanged. This can shift the stroke's center toward one pixel. Conservation does not guarantee the same perceived softness.

The existing cleanup requires a coverage difference of at least 16. Column C removes that difference guard and chooses one side from the original coverage summed along the run. A run with a zero vote stays unchanged. An equal pair within a nonzero-vote run follows the run's winner. Both methods require three stable positions, isolated pairs with total coverage 192–384, and weak outside neighbors. Intersecting runs and already strong pairs remain protected. Short, unstable or excluded stems can remain unchanged. Stable segments of curved glyphs can qualify numerically.

Column D deliberately adds coverage. Its target is the existing coverage-weighted average of the strongest quarter of positive baseline pixels, including ties at the cutoff. It raises only cores selected by C. Each adjoining blended pixel receives the same proportional lift, rounded to an integer. This preserves the local blend ratio within 8-bit rounding instead of darkening the core alone. Pixels outside those pairs stay unchanged. The samples test whether this avoids visible jaggies. They do not establish that result automatically.

All columns share the native MONO baseline's whole-pixel spacing and encoded blend. FreeType stem darkening stays on, as in the accepted native baseline. There is no Fontreal bridge, general gain, coverage floor or curve-darkening pass. This command does not change the installed profile or the earlier supersampling commands.

The manifest records actual provider, font and source hashes, capture properties, masks, selected pairs and exact image coordinates. Build data and results remain in the configured ignored roots. The focused check compares the baseline with an independent native provider reference and checks every saved mask, crop and grid:

```sh
python3 -B tests/native_stems_test.py --record FREETYPE_BUILD_JSON
```

The comparison uses regular faces only. Broader font and weight checks follow visual selection. Human assessment remains necessary for softness, geometry and readability.
