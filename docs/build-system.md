# Build for the running system

## Fontreal V3 for Qt and Plasma

### Install the stock Qt helper

Get one package from the [Fontreal V3 release](https://github.com/calculatetech/fontreal/releases/tag/v3.0.0). Use the package for your x86-64 Plasma Wayland system.

| System | Install the downloaded file |
| --- | --- |
| Debian 13 or Ubuntu 26.04 | `sudo apt install ./fontreal_3.0.0_amd64.deb` |
| Fedora 43, 44 or 45 | `sudo dnf install ./fontreal-3.0.0-1.x86_64.rpm` |
| openSUSE Leap 16.0 or 16.1 | `sudo zypper install --allow-unsigned-rpm ./fontreal-3.0.0-1.x86_64.rpm` |
| Arch Linux | `sudo pacman -U ./fontreal-3.0.0-1-x86_64.pkg.tar.zst` |

For KDE Linux Testing, the release supplies a system extension for snapshot `202611210254`. Qualification used the live image. On an installed test system, install the archive with `sudo tar --zstd --no-overwrite-dir -xf fontreal-3.0.0-kde-linux-x86_64.tar.zst -C /` and reboot. To remove it, remove `/var/lib/extensions/fontreal` and `/etc/xdg/plasma-workspace/env/fontreal.sh`, then reboot.

Sign out and back in to Plasma. Open **Fonts** in System Settings and select the layout for your display. **None** uses Fontreal grayscale. Fontreal treats eligible text from 8 to 32 screen pixels. [The README](../README.md#install-v3-with-stock-qt) describes when Qt or Breeze uses color.

The shared DEB and RPM use the loaded Qt libraries to select the right helper. Distro updates run as usual. When a library needs a different helper, Fontreal skips that library's integration. Other matching libraries can still use Fontreal.

If you installed an earlier bundle that replaced Qt, restore the distro packages before installing this helper. For the experimental V3 replacement, run its [rollback instructions](https://github.com/calculatetech/fontreal/blob/v3.0.0/docs/build-system.md#patched-qt-visual-reference) from a `v3.0.0` checkout. If a V3 bundle replaced an earlier Fontreal session package, pass the exact retained predecessor bundle with `--previous`. Repeat the V3 rollback for each experimental V3 bundle it restores. If V1 or V2 is installed or a rollback restores either version, use the [legacy rollback instructions](https://github.com/calculatetech/fontreal/blob/v2.0.0/docs/build-system.md#apply-enable-and-restore) from a `v2.0.0` checkout.

To restore stock rendering, remove `fontreal` with `apt remove`, `dnf remove`, `zypper remove` or `pacman -R` as appropriate. Sign out and back in.

### Build for stock Qt

Install the matching Qt 6 private headers for Qt Base and Qt Declarative, the Qt shader baker, and the FreeType and Fontconfig development files. The build also uses Bash, a C and C++ compiler, Binutils, `pkg-config` and `xxd`. On Debian 13 and Ubuntu 26.04:

```sh
sudo apt install build-essential binutils pkg-config xxd libfontconfig-dev libfreetype-dev qt6-base-private-dev qt6-declarative-private-dev qt6-shader-baker
tools/build-qt-stock-helper.sh build/providers
tools/package-qt-stock-helper.sh deb build/packages build/providers/*
```

On Fedora or openSUSE, install `rpm-build` and use the `rpm` format. On Arch, use the `arch` format with `makepkg` and `fakeroot`. On KDE Linux Testing, use the `kde-linux` format with GNU Tar and Zstandard. To build one package for multiple Qt builds, compile each provider on its own distro and combine the provider directories in the packaging command. Run packaging on the oldest supported system for that format. The builder requires Qt Quick’s `QBackingStore::paintDevice` relocation to be on a linker-protected read-only page.

### Konsole pilot with distro libraries

The pilot uses the distro versions of Qt, FreeType, and KWin in a session without the system-wide Fontreal helper. Launch it from a Plasma Wayland session with one unrotated display at 100% scale. In **Fonts**, enable anti-aliasing and select RGB subpixel rendering. Select **Full** hinting and a regular face such as Hack Regular.

The pilot treats pure black on white and white on black in the terminal. It uses the coverage of a single static outline font in each draw. Menus, light faces, and other colors use stock rendering. A draw also uses stock rendering when its glyphs can touch pixels outside the expected solid background.

Install the Qt Widgets, FreeType, and Fontconfig development packages. Build and launch as your normal user.

```sh
cmake -S . -B build/konsole-rgb -DFONTREAL_KONSOLE_RGB=ON
cmake --build build/konsole-rgb --target fontreal-qt-rgb
tools/run-konsole-rgb build/konsole-rgb/libfontreal-qt-rgb.so
```

The launcher opens a separate Konsole process with your usual profiles. Restart the pilot after changing the subpixel mode. A normal launch in that session uses stock Qt. Use the stock Qt helper package for wide Qt Widgets and Qt Quick coverage.

### Patched Qt visual reference

The comparison gallery uses a private Qt 6.10.2 build. This recipe reproduces the reference renderer on Ubuntu 26.04 with the matching Qt development files. It leaves the installed Qt packages in place. Build the Widgets renderer alone, or build both Widgets and Quick.

```sh
python3 tools/build-qt.py --v3-widgets
python3 tools/build-qt.py --v3-quick
```

The libraries are in `build/v3-qt/widgets/qt-build/lib` and `build/v3-qt/quick/qt-build/lib`. The builder uses CMake, Ninja, a C++ compiler, FreeType and Fontconfig development files, and matching Qt shader tools. It downloads Qt source archives and verifies their hashes.

Run the reference checks after changing the reference renderer. Install Xvfb, Pillow, the Qt Test development files and the fonts required by the checks. Download the official runtime packages into a fresh directory for each run.

```sh
mkdir -p build/v3-qt
official=$(mktemp -d build/v3-qt/official.XXXXXX)
(cd "$official" && apt-get download libfreetype6 libqt6core6t64 \
    libqt6dbus6 libqt6gui6 libqt6network6 libqt6opengl6 libqt6qml6 \
    libqt6qmlmodels6 libqt6quick6 libqt6widgets6 qt6-qpa-plugins)
bash tests/v3_widgets_test.sh "$official"
bash tests/v3_quick_test.sh "$official"
```

The Widgets test uses DejaVu Sans, DejaVu Sans ExtraLight, URW Bookman Light Italic and Ubuntu Sans. The optional [Konsole pilot](#konsole-pilot-with-distro-libraries) comparison also needs Konsole, KWin Wayland, Hack, DejaVu Sans Mono, FontTools and Pillow with XCB support. Ubuntu supplies ExtraLight in `fonts-dejavu-extra`. Extract the official packages to one directory, then pass the directory containing the extracted shared libraries, the private Widgets build directory, the pilot library and an output directory to `tests/v3_konsole_rgb_test.py`.

### Development checks for the stock Qt helper

The helper uses Qt's private rendering interfaces. Each provider builds with matching development headers and checks the build IDs of the libraries it uses before enabling a rendering hook. The Quick helper keeps Qt's normal scene graph. It uses grayscale for intermediate targets and the display's selected subpixel layout for eligible direct text.

For a helper or package change, take native Wayland captures on the supported platforms after installation and a fresh Plasma login. Check both text polarities, 100% and 125% scale, Widgets, Qt Quick with OpenGL and both software render loops, and Breeze captions. Include a Quick view opened after the application loads Qt Quick at runtime. Include a visible BC1-compressed KTX texture next to Qt Quick text. Confirm that the texture's pixels stay the same while eligible text changes. Check the loaded library identities. Remove the package, restart the session and compare with stock. See [the test policy](../CONTRIBUTING.md#when-to-run-tests).
