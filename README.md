# Fontreal

Fontreal V3 improves text rendering in Qt 6 applications and Plasma. It installs a Qt helper and a Plasma session script. Qt, FreeType, and KWin stay under your distro's package manager. Browsers and Flatpaks keep their original rendering. The comparison images come from a separate Qt build of the V3 reference.

## Why this project exists

A straight stroke can look fuzzy when it falls across two pixels. A curve can look weak when its coverage drops at a join. Fontreal keeps the shape from the font’s hints and uses a four-times-resolution reference for coverage. It balances stroke strength and edge softness for light and dark text.

## Compare stock Qt, ClearType, and V3

These captures use Noto Sans at KDE’s 8pt and 10pt defaults and Hack at 10pt. The columns show stock Qt, Windows ClearType, and Fontreal V3. Open the PNG at 100% image zoom to see each captured pixel at its original size.

![Stock Qt, ClearType, and Fontreal V3 on light backgrounds](docs/images/kde-v3/kde-fonts-light.png)

![Stock Qt, ClearType, and Fontreal V3 on dark backgrounds](docs/images/kde-v3/kde-fonts-dark.png)

See the [capture record](docs/images/kde-v3/capture-sources.json) for renderer and font details. The [V2 images](docs/images/kde-v2/manifest.json) are also available.

## Install V3 with stock Qt

Download the package for your x86-64 distro and follow the [installation guide](docs/build-system.md#install-the-stock-qt-helper). Sign out and back in to Plasma.

Open **Fonts** in Plasma System Settings to choose the subpixel layout for your display. Choose **None** for grayscale. The same helper covers direct Qt Quick text with OpenGL and software rendering. The selected layout also covers partially opaque Widgets text on opaque backgrounds and direct Qt Quick text placed between pixels. These extra paths require a direct draw on one unrotated Wayland display. Offscreen images, Qt Quick layers, and scaled or rotated text can still use grayscale. An app that first loads Qt Quick into an offscreen widget can keep stock rendering for that panel.

To recreate the comparison build, follow the [patched Qt reference guide](docs/build-system.md#patched-qt-visual-reference).

### Breeze title bars

Opaque Breeze captions can use the selected subpixel layout on one unrotated display when KWin's output interface is compatible. The helper checks the interface before using color and uses grayscale for captions if the check fails. Rotating a display while Plasma is running can leave the previous color edges visible until KWin redraws the caption. Mirrored displays can show color edges when the displays use different orientations, scales, or subpixel layouts. Qt can report a flipped Wayland output as unrotated, which can also produce color edges.

In the release tests, Breeze captions used grayscale on Debian 13 and openSUSE Leap 16.0. Eligible app text used the selected layout on both systems.

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
