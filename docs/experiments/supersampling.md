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

## Stock hinting and LCD at 4×

Use the same build record and fonts for the second study:

```sh
python3 -B tools/supersampling.py --record FREETYPE_BUILD_JSON --stock4x
```

Open its `gallery` folder in Gwenview at 100% zoom. Each font, point size, and background has one sheet. Scroll down for more panels. Arrow keys change the condition. All 54 sheets cover regular faces from 8–16pt. The earlier command still produces the original A–G comparison.

The overview includes untreated 1×, untreated 2×, untreated 4×, and current Fontreal at 1×. The new 4× rows receive no Fontreal correction. All rows retain the original native spacing and encoded blending. Area reduction averages each block of 4×4 high-resolution pixels before blending.

The next panels compare native and automatic hinting with all five stock targets: normal, light, mono, LCD, and vertical LCD. These panels use grayscale output to isolate hinting. Native drivers can ignore a requested target. Separate panels compare unhinted, native, and automatic monochrome source rendering. A monochrome 4× source becomes grayscale after reduction.

The manifest records availability, API return codes, and effective driver values. Unavailable presets receive no substituted output. Interpreter 38 is recorded as an alias when it selects version 40. Version 35 rows apply to TrueType fonts. The CFF control retains its own driver. Extra panels appear only when a distinct older interpreter or CFF engine is available.

LCD means separate coverage for the red, green, and blue channels. The LCD panels compare horizontal and vertical layouts, RGB and BGR channel order, and the available built-in filters. Each panel starts with a grayscale reference using the same hint target. Each decoded coverage channel is reduced independently on the logical pixel grid. The exporter does not resize the packed subpixel strip as a grayscale image. RGB and BGR reverse the red and blue coverage channels. The resulting colors assume the labeled order and orientation of the display panel.

This sweep's LCD panels require FreeType's LCD-filter API. A Harmony-only build's default geometry is not represented. The manifest records unavailable presets without substituting a different filter. It also records effective interpreter values. Version 38 can alias version 40. The version 35 comparisons apply to TrueType fonts and do not change the CFF control. An old CFF engine appears only when the provider actually supports it.

The manifest records actual API results for the none, default, light, and legacy LCD filters. It also records TrueType interpreter and CFF engine availability. Unsupported choices have no substituted image. Version 38 can be an alias of version 40. Version 35 supplies separate grayscale and monochrome comparisons when available. Interpreter choices affect TrueType fonts, not the CFF control. The old CFF engine gets a comparison only when the provider supports it. Custom filter weights and other driver tuning are outside this study.

The focused check now runs both studies. It independently decodes raw grayscale, monochrome and LCD bitmap rows, reduces coverage, and composes native RGB pixels. It also runs the original exporter from commit `ff63a7f` in a temporary private build tree. This requires that commit in local Git history. The check compares every original glyph capture, outline, mask, advance and placement, plus all 378 original native crops. It removes the temporary reference tree after use. The first study's seven columns retain their behavior.

The implementation follows the [FreeType hint-target contract](https://freetype.org/freetype2/docs/reference/ft2-glyph_retrieval.html#ft_load_target_xxx), [bitmap format contract](https://freetype.org/freetype2/docs/reference/ft2-basic_types.html#ft_bitmap), and [LCD contract](https://freetype.org/freetype2/docs/reference/ft2-lcd_rendering.html). The recorded provider's API results decide which presets are available. No appearance winner or installed profile changes follow from these numerical checks.
