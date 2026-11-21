# Licensing and third-party notices

Fontreal's original code, tests, tools, and documentation use the [MIT License](LICENSE). Qt-derived patches retain their upstream licenses.

## Qt patches

These files contain modifications to Qt and retained Qt source context:

- `patches/qt-6.10.2-fontreal-v3-widgets.patch`
- `patches/qtdeclarative-fontreal-v3.patch`

The affected C++ files in Qt Base and Qt Declarative 6.10.2 carry this license expression:

    LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

The C++ changes and their context retain the upstream open-source alternatives of [LGPL 3.0](LICENSES/LGPL-3.0-only.txt), [GPL 2.0](LICENSES/GPL-2.0-only.txt), or [GPL 3.0](LICENSES/GPL-3.0-only.txt). Fontreal does not grant a Qt commercial license. The root MIT license does not replace these terms.

The Widgets patch also changes Qt Base's `src/gui/CMakeLists.txt`. That build file carries `Copyright (C) 2022 The Qt Company Ltd.` and uses the [BSD 3-Clause license](LICENSES/Qt-BSD-3-Clause.txt).

The affected C++ files retain these upstream notices:

    Copyright (C) 2016 Intel Corporation.
    Copyright (C) 2016 Jolla Ltd, author: <gunnar.sletta@jollamobile.com>
    Copyright (C) 2016 Robin Burchell <robin.burchell@viroteck.net>
    Copyright (C) 2016 The Qt Company Ltd.
    Copyright (C) 2019 The Qt Company Ltd.
    Copyright (C) 2020 The Qt Company Ltd.
    Copyright (C) 2021 The Qt Company Ltd.
    Copyright (C) 2023 The Qt Company Ltd.

Fontreal modifications are Copyright (c) 2026 Michael Beutler and Fontreal contributors. Full per-file notices remain in the corresponding Qt source packages.

## Build dependencies

The release helper uses the system libraries for Qt, FreeType, and Fontconfig. Each library keeps its own license. The optional reference build compiles Qt with the patches above. Keep the original per-file notices and corresponding source if you distribute those Qt binaries. See [Qt licensing](https://doc.qt.io/qt-6.10/licensing.html) and [Qt's LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations).

## Comparison images and fonts

The repository distributes rendered captures. The font files remain under their own licenses and stay with their respective distributors. See the [V3 capture record](docs/images/kde-v3/capture-sources.json) and [font measurement record](docs/images/noto-sans-display/measurements.json) for provenance.

The captures show Qt, KDE, and Windows software. The names, artwork, and software belong to their respective projects and owners.
