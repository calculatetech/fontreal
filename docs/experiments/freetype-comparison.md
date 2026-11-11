# First controlled FreeType samples

The initial samples show that an existing FreeType treatment can produce a solid one-column `l` with grayscale output. The same font under native grayscale can spread that stroke across two partially covered columns. After viewing the native comparison, the user selected **Auto mono hints / gray edges** as closest to the desired crispness. That establishes an initial preferred baseline for this sample, not a universal result across fonts and sizes.

## Conditions

These samples use the local FreeType 2.14.2 library and the installed fonts below. Size is 13 pixels, scale is 1 unless named otherwise, and phase is half a device pixel. The layout is shared across treatments. The default uses black text on white with encoded-sRGB blending. Inspect the native application rather than a preview that resizes an image.

| Font | SHA-256 |
| --- | --- |
| Noto Sans Regular | `89c3c497f618fdaa0b2d1e98fef93582f28c71debd2c4a8cdf41f190ced2909d` |
| DejaVu Sans Mono Book | `a54dca07c76d6289e717e75e0a58c0128f6d7269ef3faf76417c9d7d3bba37ab` |

## Open the generated samples

Generated files live under the ignored `results/` directory. They are local experiment outputs and can be regenerated. Each directory contains the annotated comparison, the enlarged `l`, the geometric target, raw masks, rendered text, and JSON provenance.

| Directory | Purpose |
| --- | --- |
| `results/sans-aligned/` | Noto Sans, phase zero, fractional shared origins |
| `results/sans-half-fractional/` | Noto Sans, half-pixel phase, fractional shared origins |
| `results/sans-half-snapped/` | Noto Sans, half-pixel phase, snapped shared origins |
| `results/mono-half-snapped/` | DejaVu Sans Mono, snapped shared origins |
| `results/sans-scale125-snapped/` | Noto Sans, size 13 at software scale 1.25, rasterized at 16.25 pixels |
| `results/sans-dark-linear-snapped/` | Noto Sans, white on black, linear-light blend |

Additional `m/n/o/g` samples use `m` in the pixel-detail inspector. Each pair keeps font, geometry, text, and phase fixed and changes only blending:

| Effective size | Encoded-sRGB directory | Linear-light directory |
| --- | --- | --- |
| 15 px (10 × 1.5) | `results/curves-15-encoded/` | `results/curves-15-linear/` |
| 16 px (16 × 1) | `results/curves-16-encoded/` | `results/curves-16-linear/` |
| 16.5 px (11 × 1.5) | `results/curves-16_5-encoded/` | `results/curves-16_5-linear/` |

Use the window to compare **TT35 mono hints / binary**, **Auto mono hints / gray edges**, and **TT40 normal / grayscale** at normal size. The geometry target illustrates the desired distinction between a full straight core and soft curved or diagonal edges. It is deliberately labeled as synthetic.

## Measured narrow-stroke difference

The following values are raw coverage in the middle row of the isolated lowercase `l`. Zero means empty and 255 means fully covered. Leading and trailing empty columns are omitted from this table. Values are coverage, not displayed brightness.

| Font and condition | Treatment | Active column coverage | Full columns |
| --- | --- | --- | --- |
| Noto Sans, 13 pixels, snapped | Binary mono target | `[255]` | 1 |
| Noto Sans, 13 pixels, snapped | Native TT35 mono target with grayscale output | `[228, 64]` | 0 |
| Noto Sans, 13 pixels, snapped | Forced auto mono target with grayscale output | `[255]` | 1 |
| Noto Sans, 13 pixels, snapped | Native TT40 normal grayscale | `[228, 64]` | 0 |
| Noto Sans, 13 pixels, fractional half-pixel phase | Forced auto mono target with grayscale output | `[128, 128]` | 0 |
| Noto Sans, 13 pixels, fractional half-pixel phase | Native TT40 normal grayscale | `[100, 192]` | 0 |
| DejaVu Sans Mono, 13 pixels, snapped | Native TT35 mono target with grayscale output | `[255]` | 1 |
| DejaVu Sans Mono, 13 pixels, snapped | Native TT40 normal grayscale | `[28, 255, 16]` | 1 |
| Noto Sans, 16.25 pixels, snapped | Forced auto mono target with grayscale output | `[255]` | 1 |
| Noto Sans, 16.25 pixels, snapped | Native TT40 normal grayscale | `[160, 208]` | 0 |

Three useful observations follow. First, rounding the glyph origin alone does not align the internal Noto stem. Second, the forced automatic hinter aligns it in these samples. Third, a later fractional translation can split that fitted stem again. The full path matters.

The DejaVu result also shows that native instructions can reach the straight-stem target in another font. Selecting a mono hinting target is not a universal guarantee of the same internal result across fonts.

## Reproduce

These commands require the same local fonts and new or empty destination directories. Use different directory names when preserving an earlier run.

    ./build/fontreal --phase 0 --fractional --export results/sans-aligned
    ./build/fontreal --fractional --export results/sans-half-fractional
    ./build/fontreal --export results/sans-half-snapped
    ./build/fontreal --font /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf --export results/mono-half-snapped
    ./build/fontreal --scale 1.25 --export results/sans-scale125-snapped
    ./build/fontreal --dark --linear --export results/sans-dark-linear-snapped

For an enlarged `m` in the curve comparison, use the same command with and without `--linear` and separate destination directories:

    ./build/fontreal --size 10 --scale 1.5 --inspect m --text "m n o g   minimum   moon" --export results/curves-15-encoded
    ./build/fontreal --size 10 --scale 1.5 --inspect m --text "m n o g   minimum   moon" --linear --export results/curves-15-linear

Use size 16 and scale 1 for the 16-pixel pair. Use size 11 and scale 1.5 for the 16.5-pixel pair.

## Human judgment and limits

The user's initial preference is **Auto mono hints / gray edges**. Continue comparing letter identity, softness on curves, stroke consistency, spacing, and reading comfort at normal size. Use the enlarged pixels to explain a preference after forming it.

The user reports that the vertical rendering is quite clean, while the crowns of `m` arches look heavier than the upright stems. Related softness appears in `m`, `n`, `o`, and `g`. The selected-glyph inspector exposes those actual two-dimensional masks while retaining `l` as a control. It does not assign an unvalidated perceptual thickness score.

The user also identifies a size-dependent blend preference for the preferred treatment:

| Size | Software scale | Effective raster size | Reported blend preference |
| --- | --- | --- | --- |
| 10 px | 1.5 | 15 px | Linear-light |
| 11 px | 1.5 | 16.5 px | Encoded-sRGB |
| About 16 px | 1.0 | About 16 px | Encoded-sRGB |
| Below about 16 px | 1.0 | Below about 16 px | Linear-light |

This suggests a transition near 16 effective pixels in the viewed font and treatment. It does not establish a universal cutoff. In this tool, size and scale multiply before rasterization. An equivalent-product comparison, such as 10 px at 1.5 and 15 px at 1.0, isolates that relationship. The blend checkbox preserves raw coverage, so the observed arch-weight change is a presentation effect even though it affects perceived stroke thickness.

This first set samples two fonts and two effective sizes. It uses shared natural spacing, not each historical engine's full spacing policy. It does not reproduce a 1990s operating system, measure the physical panel, or diagnose the actual Konsole title bar. The next experiment depends on what looks right to the reader and what still looks wrong.
