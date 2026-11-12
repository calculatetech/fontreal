# Desktop deployment and distribution

## Question

How can Fontreal cover a normal desktop session and ship maintainable packages without breaking toolkit updates?

## Repository constraints

The initial targets are Debian 13 and Ubuntu 26.04, native amd64. Builds run on demand for the running system. Debian 13 supplies Qt Base `6.8.2+dfsg-9+deb13u2` and Qt Declarative `6.8.2+dfsg-7` at this inspection. The current Ubuntu desktop has Qt Base `6.10.2+dfsg-7`, Qt Declarative `6.10.2+dfsg-3`, and Plasma/KWin `4:6.6.6-0ubuntu0.1`. Detect exact installed binary and source versions for every build. The upstream 6.10.2 prototype remains a separate experiment.

The accepted treatment is automatic monochrome hints with grayscale rasterization, snapped origins, mild contrast, and linear blending. Noto Sans and Inconsolata Nerd Font at 15px are useful starting conditions. Blend preference depends on effective size and font. Preserve explicit controls and the user's font choices.

Native Qt widgets and Konsole have application-level evidence. Separate [KDE checks](../experiments/kde-paths.md) establish matching KWin titles and selected OpenGL Plasma applet glyphs at 100% and 125%. The private Qt Quick correction adds text-only linear composition and stable fractional origins. The A8 profile correction confines the raster transfer table to eligible TrueType draws. Mixed-font GPU and raster checks preserve stock CFF/color pixels. These isolated results do not establish a complete session. GTK, Wine, browsers, bundled runtimes, and full-session activation remain unproven. See the [GPU specification](../plans/FR-013-quick-linear.md) and [profile-scope specification](../plans/FR-014-a8-profile-scope.md).

## Options

| Option | Deployment result | Maintenance cost |
| --- | --- | --- |
| Distro Qt packages plus session configuration | Host Qt applications use the patched library through normal package ownership | Rebuild for each supported distro Qt update |
| Private Qt plus launch wrappers | Useful for isolated application comparisons | Every launch and plugin dependency needs control |
| Fontconfig configuration alone | Can select existing font and hinting preferences | Cannot reproduce the implemented coverage and blend changes |

## Evidence

Debian source packages support a maintained patch queue in `debian/patches`. Ubuntu documents retrieval of complete source packages through `apt source` or a `.dsc` file. Use that packaging rather than converting the prototype's partial library build into an installer. [Debian packaging](https://www.debian.org/doc/manuals/debmake-doc/ch11.en.html), [Ubuntu source retrieval](https://documentation.ubuntu.com/project/contributors/setup/get-the-source-of-a-package/).

Qt Quick has a separate text choice. Its default is `QtRendering`, while `NativeRendering` selects platform text rendering. Breeze 6.6.6 chooses native text at integral display scales and Qt text at fractional scales. Its source accepts `QT_QUICK_DEFAULT_TEXT_RENDER_TYPE=nativerendering`. This is a candidate for testing, not proof that every Qt Quick item reproduces the widget result. Applications can select their own render type. [Qt Text](https://doc.qt.io/qt-6.10/qml-qtquick-text.html), [Breeze source](https://raw.githubusercontent.com/KDE/qqc2-breeze-style/v6.6.6/kirigami-plasmadesktop-integration/plasmadesktoptheme.cpp).

Plasma 6.6.6 sources scripts from configuration directories under `plasma-workspace/env/*.sh`. System scripts run before user scripts. The Wayland startup sequence calls this before session startup. This provides a candidate activation hook for KWin and applications. Actual inheritance through D-Bus and systemd activation still needs a session test. [Environment hook](https://raw.githubusercontent.com/KDE/plasma-workspace/v6.6.6/startkde/startplasma.cpp), [Wayland startup](https://raw.githubusercontent.com/KDE/plasma-workspace/v6.6.6/startkde/startplasma-wayland.cpp).

Flatpak applications use runtimes and can bundle dependencies. Replacing host Qt does not establish coverage of those runtimes. AppImages, Snaps, and other bundled libraries also require separate inspection. [Flatpak runtime model](https://docs.flatpak.org/en/latest/basic-concepts.html).

APT authenticates signed archive metadata and its package checksum chain. Use a dedicated repository key through `Signed-By`. This differs from signing each `.deb` individually. [APT authentication](https://manpages.debian.org/trixie/apt/apt-secure.8.en.html).

## Decision

Use distro Qt source packages and their build rules, with a small Fontreal patch queue. Start with on-demand builds for Debian 13 and Ubuntu 26.04 amd64. Use separate ports for Qt 6.8.2 and 6.10.2. Keep the existing package names and package-manager ownership. Build a coherent package set in a clean container for the detected release. Record exact installed and source versions, patches, build dependencies, checksums, and validation results. Retain original packages for rollback and corresponding modified source. The [build guide](../build-system.md) owns commands. Unknown versions stop instead of using a different Qt.

Use a downstream package revision that sorts above its base and below the next official revision. Prove that ordering for each release. Do not hold Qt or install broad priority rules that block Ubuntu updates. A newer official Qt must remain installable even if Fontreal support temporarily disappears. Activation must detect an unsupported backend and avoid leaving a Qt Quick override active after that fallback.

Ship a separate activation package. Installation first leaves Fontreal disabled. Support per-user activation, then optional machine defaults after full-session validation. The proposed enabled values are:

```sh
export FONTREAL_RENDERING=1
export FONTREAL_BLEND=linear
export FONTREAL_CONTRAST=mild
```

These are the implemented backend controls, not a complete installation procedure. Apply them before session startup, then log in again. The private Qt Quick implementation selects native rendering per eligible OpenGL glyph run. The tested Plasma path does not need an additional default-renderer environment override. Preserve installed font choices. An optional font preset can recommend the tested families without replacing user configuration or bundling fonts.

Test the package set in a disposable Plasma session or VM before the host desktop. Compare KWin titles, Plasma controls, widgets, and Konsole at integral and fractional scales. Include regular, bold, italic, fallback, symbol, CFF, and color fonts. Check light and dark colors, disabled text, and monitor scale changes. Compare actual rendered output and human readability, not only process environment variables.

Provide two recovery levels. Disabling activation restores the stock conditional path after a new login. Full rollback removes activation and reinstalls the coherent official Qt package set. Removing the activation package alone does not restore the original libraries. Test both recovery levels, including recovery from a text console, before host installation.

The first delivery is a local on-demand build bundle. A hosted APT repository with signed metadata and a dedicated trust key follows under FR-012. The repository remains private. Each supported distro release and architecture needs its own builds and update checks.

Distribute the corresponding modified Qt source, build instructions, and required notices with a reliable source-access route for recipients. Qt's LGPL guidance requires source for modified libraries and user replacement rights. Confirm the licenses of the actual shipped components. Fontreal has no root project license yet. Choose that license before a public release, and inspect each font license before bundling fonts. [Qt distribution obligations](https://www.qt.io/development/open-source-lgpl-obligations).

Keep Debian and Ubuntu security updates flowing. For each new Qt source revision, reapply the patch, build, run the existing widget/application checks, and repeat the supported desktop checks. Publish supported version ranges and known gaps. Upstreaming the controls can reduce this maintenance cost later.

The initial claim is KDE and supported host Qt 6 paths. GNOME, Wine, Windows 11, Qt 5, browsers, and bundled runtimes remain separate work. A Qt package cannot establish those results. The [roadmap](../roadmap.md) owns the order of work.

## Rejected options

Do not deploy the prototype with a permanent session-wide `LD_LIBRARY_PATH`, `LD_PRELOAD`, or manual copies into `/usr`. The isolated build already required a linker adjustment for application compatibility. Distro build rules and package ownership provide a better deployment base.

Keep wrappers for experiments. A universal AppImage can carry a viewer, but it cannot replace every host application's renderer. Fontconfig alone cannot add the current Qt coverage and composition behavior.

## Revisit when

Revisit the package boundaries after KWin and Qt Quick tests identify their actual requirements. Revisit the platform list when another distro has a test environment and a named maintenance owner. Revisit the downstream Qt patch when upstream exposes equivalent controls.

## Sources

The linked upstream documents and versioned KDE sources were read on 2026-11-11. The deployment choice is a Fontreal proposal based on those sources. It is not an upstream support claim or an installation result.
