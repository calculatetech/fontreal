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
