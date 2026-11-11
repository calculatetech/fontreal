# Diagonal edge comparison

The user reports that W and V remain fuzzy in both the original experiment and matched Konsole text. The captured Noto Sans 15px Konsole W matches the selected experiment pixels exactly. This study tests a tighter gray transition before changing outline fitting.

The study is separate from the ordinary seven-row experiment. It does not change the private KDE renderer or select a desktop policy. Human judgment at normal size decides whether any candidate helps.

## Open the samples

Build from the repository root, then open the Noto Sans study:

```sh
cmake --build build
./build/fontreal --edges --font /usr/share/fonts/truetype/noto/NotoSans-Regular.ttf \
  --size 15 --scale 1 --linear --inspect W \
  --text 'W V w v   WWWV wwv   m n o g   minimum moon   Illl1| lllm'
```

Repeat with `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`. Both commands start with black text on white. Use the existing background and blend controls to compare polarity and blending independently. Change the inspection character to V, w, or v for enlarged pixels. Keep m/n/o/g and l as controls.

Inspect the Comparison tab at normal size first. Then use Pixel detail to explain the difference. The viewer preserves one source pixel per backing-store pixel. Enlargement repeats each pixel eight times. The compositor and physical display remain separate limits.

## Treatments

All four rows use forced automatic hinting with the monochrome hint target. They share font, size, layout, and origins. The first three use FreeType's normal grayscale rasterization. Only the declared coverage transition changes between them.

| Row | Coverage treatment |
| --- | --- |
| Auto mono hints / gray edges | Unchanged preferred reference |
| Gray edges / mild contrast | Empty at 32 or below, full at 223 or above, linear transition between |
| Gray edges / strong contrast | Empty at 64 or below, full at 191 or above, linear transition between |
| Auto mono hints / binary | FreeType monochrome rasterization of the same automatic hints |

Coverage describes how much of a pixel the glyph fills. The two ramps replace coverage byte `a` with `round(255 × clamp((a − low)/(high − low), 0, 1))`. They preserve empty and fully covered pixels. They can remove weak fringes and strengthen partly covered cores. They can also change apparent weight and expose jagged steps. The fixed cutoffs are experimental choices, not calibrated readability thresholds.

This operation precedes color blending. It changes the mask, so it is distinct from changing the linear-light blend checkbox. It applies to every glyph, including curves and punctuation. It does not detect diagonal strokes or fit a new outline.

## Export and interpretation

Add `--export results/diagonal-noto15-linear` to the first command to write a new or empty destination and exit. Ordinary launches without `--edges` retain the original seven treatments.

The study exports the same image types as the original experiment. The `auto-gray` row preserves raw FreeType coverage. The `edge-mild` and `edge-strong` coverage, ell, and probe files contain adjusted masks. Their `coverage_transfer` metadata records the source row, operation, and cutoffs. Do not interpret those adjusted values as raw geometric area. The metadata root identifies the diagonal study. The binary row uses FreeType's monochrome renderer, which is a separate comparison from applying a numeric threshold to grayscale output.

The tests compare every available isolated glyph with independent FreeType calls and ramp math. They also check blending, the full specimen, GUI updates and exports, and native canvas pixels. These checks establish the declared experiment. They do not establish that either ramp looks better.

The user prefers mild contrast with Noto Sans in the viewed 15px samples and finds it much better than unadjusted gray edges. DejaVu Sans is less successful for this user. Font, size, blend, and polarity remain one comparison condition. This result does not establish a universal setting.

The user also accepts Inconsolata Nerd Font Regular at 15px with mild contrast, linear blending, and black text on white. Lowercase w retains a shape concern but remains recognizable. Its cause is not established. The rest of this viewed sample receives a strong preference.

The user's normal terminal font is Inconsolata Nerd Font. The [native Konsole comparison](kde-preview.md) carries the selected mild treatment into that setting. Structural weight and phase control remain a later research path if the selected treatment fails at other sizes. The [existing research](../research/native-font-rendering.md) covers that prior art. Skia's [raster discussion](https://docs.skia.org/docs/dev/design/raster_tragedy/) explains why coverage changes can also affect weight. The [1995 perceptual grayscale paper](https://lspwww.epfl.ch/publications/typography/ptgogf_95.pdf) concerns structural control and does not validate these cutoffs.
