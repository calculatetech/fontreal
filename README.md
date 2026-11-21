# Fontreal

Fontreal V3 improves text rendering in Qt 6 applications and Plasma. The Ubuntu helper adds Fontreal to ordinary app launches and uses the distro Qt, FreeType, and KWin packages. The comparison images come from a separate Qt build that reproduces the V3 reference.

## Why this project exists

A straight stroke can look fuzzy when it falls across two pixels. A curve can look weak when its coverage drops at a join. Fontreal keeps the shape from the font’s hints and uses a four-times-resolution reference for coverage. It balances stroke strength and edge softness for light and dark text.

## Compare stock Qt, ClearType, and V3

These captures use Noto Sans at KDE’s 8pt and 10pt defaults and Hack at 10pt. The columns show stock Qt, Windows ClearType, and Fontreal V3. Open the PNG at 100% image zoom to see each captured pixel at its original size.

![Stock Qt, ClearType, and Fontreal V3 on light backgrounds](docs/images/kde-v3/kde-fonts-light.png)

![Stock Qt, ClearType, and Fontreal V3 on dark backgrounds](docs/images/kde-v3/kde-fonts-dark.png)

See the [capture record](docs/images/kde-v3/capture-sources.json) for renderer and font details. The [V2 images](docs/images/kde-v2/manifest.json) are also available.

## Install V3 with stock Qt

On a supported Ubuntu 26.04 system, follow the [stock Qt helper guide](docs/build-system.md#install-the-stock-qt-helper-on-ubuntu-2604) to build and install one package. Sign out and back in to Plasma.

Open **Fonts** in Plasma System Settings to choose the subpixel layout for your display. Choose **None** for grayscale. The same helper covers direct Qt Quick text with GPU and software rendering. The selected layout also covers partially opaque Widgets text on opaque backgrounds and direct Qt Quick text placed between pixels. These extra paths require a direct draw on one unrotated Wayland display. Offscreen images, Qt Quick layers, and scaled or rotated text can still use grayscale.

To recreate the comparison build, follow the [patched Qt reference guide](docs/build-system.md#patched-qt-visual-reference).

### Breeze title bars

With stock KWin 6.6.6, opaque Breeze captions can use the selected subpixel layout on one unrotated display. Rotating a display while Plasma is running can leave the previous color edges visible until KWin redraws the caption. Mirrored displays can show color edges when the displays use different orientations, scales, or subpixel layouts. Qt can report a flipped Wayland output as unrotated, which can also produce color edges.

## Suggested fonts

Start with **Noto Sans Display Regular at 10pt** for general UI text, menus and toolbars. This is the preferred starting point with the selected Fontreal profile at 96 DPI and 100% scale. The [font analysis](docs/research/noto-sans-display.md) explains the measured stroke alignment, compares whole-point sizes from 8pt through 16pt, and separates this recommendation from a universal claim about readability.

For terminals, start with **Liberation Mono Regular at 11pt**, or **LiterationMono Nerd Font Regular at 11pt** for the Nerd Font version. These are preferred terminal choices based on their crisp, clean appearance with Fontreal. The terminal recommendation reflects visual use. The linked measurements cover the UI font, not these terminal faces.

## Other applications

The [V2 release](https://github.com/calculatetech/fontreal/tree/v2.0.0) covers Firefox, Floorp, Teams and Bitwarden. The [app-specific guide](docs/app-scenarios.md) lists each integration and its recovery steps. See the [Chromium-based browser status](docs/experiments/chromium-flatpak.md#chromium-based-browsers-are-not-supported) and the [roadmap](docs/roadmap.md) for wider application coverage.

## Feedback welcome

[Open an issue](https://github.com/calculatetech/fontreal/issues/new) with the application, font family and style, point size, display scale, and background. Include a lossless screenshot when possible. Cases where you prefer stock rendering are welcome.

See the [contribution guide](CONTRIBUTING.md) for development and capture requirements.

## License

Fontreal’s original code and documentation use [MIT](LICENSE). Qt-derived patches retain their upstream LGPL/GPL alternatives. FreeType-derived patches use the FreeType Project License. The Skia and Chromium patches retain their upstream BSD licenses. See the [third-party notices](THIRD_PARTY_NOTICES.md).
