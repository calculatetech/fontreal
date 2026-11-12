# Licensing and third-party notices

Fontreal's original application, tests, scripts, and documentation use the [MIT License](LICENSE). The Qt-derived and FreeType-derived patches are exceptions. Dependency licenses also remain in effect.

## Qt patches

These files contain modifications to Qt and retained Qt source context:

- `patches/qt-6.8.2-fontreal.patch`
- `patches/qt-6.10.2-fontreal.patch`
- `patches/qtdeclarative-6.8.2-fontreal.patch`
- `patches/qtdeclarative-6.10.2-fontreal.patch`
- `packaging/qt6-base-capability.patch`
- `packaging/qt6-declarative-capability.patch`

The affected upstream files in Qt Base and Qt Declarative 6.8.2 and 6.10.2 carry this license expression:

    LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

The retained source context and Fontreal modifications in these patch files are available under the same open-source alternatives: [LGPL 3.0](LICENSES/LGPL-3.0-only.txt), [GPL 2.0](LICENSES/GPL-2.0-only.txt), or [GPL 3.0](LICENSES/GPL-3.0-only.txt). Fontreal does not grant a Qt commercial license. The root MIT license does not replace these terms.

The affected files retain these upstream notices:

    Copyright (C) 2016 Intel Corporation.
    Copyright (C) 2016 Jolla Ltd, author: <gunnar.sletta@jollamobile.com>
    Copyright (C) 2016 Robin Burchell <robin.burchell@viroteck.net>
    Copyright (C) 2016 The Qt Company Ltd.
    Copyright (C) 2019 The Qt Company Ltd.
    Copyright (C) 2020 The Qt Company Ltd.
    Copyright (C) 2021 The Qt Company Ltd.
    Copyright (C) 2023 The Qt Company Ltd.

Fontreal modifications are Copyright (c) 2026 Michael Beutler and Fontreal contributors. Full per-file notices remain in the corresponding Qt source packages. The license texts above are copied unchanged from the retained Qt source archive.

## FreeType patch

`patches/freetype-2.14.2-fontreal.patch` contains changes and source context from FreeType's `src/base/ftobjs.c`. This file carries Copyright 1996-2025 by David Turner, Robert Wilhelm, and Werner Lemberg. Its upstream license permits use under the FreeType Project License or GPL 2.0. Fontreal distributes this patch under the [FreeType Project License](LICENSES/FTL.TXT). The root MIT license does not replace these terms.

Fontreal modifications are Copyright (c) 2026 Michael Beutler and Fontreal contributors. They add opt-in automatic monochrome hinting with grayscale output, optional mild contrast, and test-only observation of final glyph masks. The changes preserve the original source headers. The private builder retains the distro source patches and creates separate stock and modified source trees.

This software is based in part on the work of the FreeType Team. Portions are copyright 1996-2025 The FreeType Project (https://freetype.org). Retain the unchanged `FTL.TXT`, source notices, modification description, and binary acknowledgement with a distribution. Each private build includes `FTL.TXT` and `NOTICE` beside its source trees and libraries.

## Built packages and dependencies

Patched Qt libraries remain Qt libraries under their upstream licenses. The MIT license for Fontreal's original code does not remove Qt's requirements for corresponding source, notices, or library replacement. Keep the native build bundle's `source/` directory, recipes, copyright files, and original packages with a distribution. The [build guide](docs/build-system.md) explains the bundle.

Qt includes components under other licenses, including GPL-only components and third-party software. The three texts in `LICENSES/` describe the alternatives for the files patched here, not every dependency in a complete Qt build. Retain and inspect each distributed package's own `debian/copyright` and source notices. See [Qt licensing](https://doc.qt.io/qt-6.10/licensing.html) and [Qt's LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations).

FreeType, Fontconfig, KDE applications, and themes retain their own licenses. They are not relicensed by this repository. Qt's existing source headers are not removed or replaced by Fontreal's patches.

## Comparison images and fonts

The comparison images contain rendered text and interface captures. No font files are distributed in this repository. Font files used for capture retain their own licenses. The gallery's [capture metadata](docs/images/comparison/manifest.json) identifies the exact fonts and source versions.

Adwaita Sans and Adwaita Mono come from [GNOME's Adwaita Fonts project](https://gitlab.gnome.org/GNOME/adwaita-fonts), version 51.0, under OFL 1.1. Noto Sans, Hack, and DejaVu fonts come from the installed distro packages. Use of an OFL font in an image does not impose the OFL on that image. See the [OFL FAQ, sections 1.1 and 1.1.1](https://openfontlicense.org/ofl-faq/).

The screenshots depict Qt/KDE software and themes. Their inclusion does not claim ownership of those projects' names, artwork, or software.
