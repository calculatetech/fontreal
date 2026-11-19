# Fontreal

Fontreal V3 improves text rendering in Qt 6 applications and Plasma on Debian 13 and Ubuntu 26.04. It builds matching QtBase and Qt Declarative packages for the running system. V3 uses your installed FreeType, font files, and application settings. Plasma uses stock KWin.

## Why this project exists

A straight stroke can look fuzzy when it falls across two pixels. A curve can look weak when its coverage drops at a join. Fontreal keeps the shape from the font’s hints and uses a four-times-resolution reference for coverage. It balances stroke strength and edge softness for light and dark text.

## Compare stock Qt, ClearType, and V3

These captures use Noto Sans at KDE’s 8pt and 10pt defaults and Hack at 10pt. The columns show stock Qt, Windows ClearType, and Fontreal V3. Open the PNG at 100% image zoom to see each captured pixel at its original size.

![Stock Qt, ClearType, and Fontreal V3 on light backgrounds](docs/images/kde-v3/kde-fonts-light.png)

![Stock Qt, ClearType, and Fontreal V3 on dark backgrounds](docs/images/kde-v3/kde-fonts-dark.png)

See the [capture record](docs/images/kde-v3/capture-sources.json) for renderer and font details. The [V2 images](docs/images/kde-v2/manifest.json) are also available.

## Try V3

Follow the [Qt and Plasma build guide](docs/build-system.md#fontreal-v3-for-qt-and-plasma) to build for your system, check the bundle, and install it. Use `fontreal-session enable` and sign in to Plasma again.

Open **Fonts** in Plasma System Settings to choose the subpixel layout for your display. Choose **None** for grayscale. Subpixel rendering applies to eligible native Qt Widgets text. Fontreal also provides grayscale rendering for eligible offscreen text and the Qt Quick OpenGL text path.

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
