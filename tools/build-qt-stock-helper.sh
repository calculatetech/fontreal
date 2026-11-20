#!/bin/bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
output=$(realpath -m "${1:-"$root/build/qt-stock-helper"}")
sdk=${FONTREAL_QT_SDK:-}
shader_sdk=${FONTREAL_QT_SHADER_SDK:-"$sdk"}
source="$root/integrations/qt-stock"
runtime=/usr/lib/x86_64-linux-gnu
headers="$sdk/usr/include/x86_64-linux-gnu/qt6"
qt_major_minor=6.10.2
gui="$runtime/libQt6Gui.so.$qt_major_minor"
quick="$runtime/libQt6Quick.so.$qt_major_minor"
widgets="$runtime/libQt6Widgets.so.$qt_major_minor"

if [[ $(dpkg --print-architecture) != amd64 ]] ||
    [[ $(dpkg-query -W -f='${Version}' libqt6gui6) != 6.10.2+dfsg-7 ]] ||
    [[ $(dpkg-query -W -f='${Version}' libqt6quick6) != 6.10.2+dfsg-3 ]]; then
    echo 'This helper requires the qualified Ubuntu 26.04 amd64 Qt packages.' >&2
    exit 1
fi

printf '%s  %s\n' \
    1cccdc5c19b4d9706f67b928155dc6f46c44799e9fff8ea441de0c6b8a5176c1 "$gui" \
    36d8d5518e6479ab710c0ce4e378fcebb59b7bf7b0c277124aabcc8f7bd9c7d4 "$quick" \
    655542813ae4a1a51f42d20930b70e8dda31a3b7873234cce4cf24879ae9a3a2 "$widgets" |
    sha256sum --check --status

mkdir -p "$output"
work=$(mktemp -d "$output/.qt-helper.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
pack="$work/package"
plugins="$pack$runtime/qt6/plugins/generic"
mkdir -p "$plugins/providers" "$pack/DEBIAN" "$pack/etc/xdg/plasma-workspace/env"

moc="$sdk/usr/lib/qt6/libexec/moc"
qsb="$shader_sdk/usr/lib/qt6/bin/qsb"
flags=(-I"$headers")
for module in QtCore QtGui QtQml QtQmlIntegration QtQmlModels QtQuick QtWidgets; do
    flags+=(-I"$headers/$module" -I"$headers/$module/$qt_major_minor" -I"$headers/$module/$qt_major_minor/$module")
done

LD_LIBRARY_PATH="$shader_sdk$runtime" "$qsb" --glsl "100 es,120,150,330" \
    -o "$work/coverage.qsb" "$source/coverage.frag"
xxd -i -n coverage_qsb "$work/coverage.qsb" > "$work/coverage_qsb.h"
read -ra freetype_cflags <<< "$(pkg-config --cflags freetype2 fontconfig)"
read -ra freetype_libs <<< "$(pkg-config --libs freetype2 fontconfig)"
core=("$root/src/fontreal_v3_coverage.cpp" "$root/src/fontreal_v3_outline.cpp" "$root/src/fontreal_v3_thin.cpp")
qt=("$gui" "$runtime/libQt6Core.so.$qt_major_minor")

build_provider() {
    local name=$1 binary=$2
    shift 2
    "$moc" "${flags[@]}" -o "$work/$name.moc" "$source/$name.cpp"
    c++ -std=c++17 -DQT_NO_DEBUG -O2 -fPIC -shared "${flags[@]}" -I"$root/src" -I"$work" \
        "${freetype_cflags[@]}" "$source/$name.cpp" "${core[@]}" "$@" "${qt[@]}" \
        "${freetype_libs[@]}" -ldl -o "$plugins/providers/$binary"
    chmod 644 "$plugins/providers/$binary"
    if readelf -d "$plugins/providers/$binary" | grep -E 'RPATH|RUNPATH'; then
        exit 1
    fi
}

build_id() {
    local id
    id=$(LC_ALL=C readelf -n "$1" | awk '/Build ID:/ {print $3}')
    [[ $id =~ ^[0-9a-f]{40}$ ]]
    printf '%s' "$id" | sed -E 's/(..)/0x\1,/g'
}

build_loader() {
    local name=$1 library=$2 prefix=$3
    shift 3
    local note="$work/plugin.note"
    objcopy --dump-section ".note.qt.metadata=$note" "$plugins/providers/$name" "$work/provider-copy"
    cc -O2 -fPIC -shared -fvisibility=hidden \
        "-DFONTREAL_METADATA=\"$note\"" "-DMETADATA_SIZE=$(stat -c %s "$note")" \
        "-DRUNTIME_ID=$(build_id "$library")" "-DRUNTIME_PREFIX=\"$prefix\"" "-DPROVIDER_PATH=\"providers/$name\"" \
        "$@" "$source/loader.c" "$source/metadata.S" -ldl -o "$plugins/$name"
}

build_provider fontreal-cached-probe libfontreal-cached-probe.so
build_provider scenegraph libfontreal_quick_default_probe.so "$quick"
build_loader libfontreal-cached-probe.so "$gui" libQt6Gui.so.
build_loader libfontreal_quick_default_probe.so "$quick" libQt6Quick.so. "-DGUI_ID=$(build_id "$gui")"

install -m 644 "$source/plasma-env.sh" "$pack/etc/xdg/plasma-workspace/env/fontreal-qt-helper-study.sh"
mkdir -p "$pack/usr/share/doc/fontreal-qt-helper-study"
install -m 644 "$root/LICENSE" "$pack/usr/share/doc/fontreal-qt-helper-study/copyright"
cat > "$pack/DEBIAN/control" <<'CONTROL'
Package: fontreal-qt-helper-study
Version: 0.10
Architecture: amd64
Depends: libfontconfig1, libfreetype6, libqt6gui6, libqt6quick6
Maintainer: Fontreal Project <fontreal@localhost>
Description: Fontreal V3 Plasma helper with RGB text
CONTROL

dpkg-deb --build --root-owner-group "$pack" "$output/fontreal-qt-helper-study-0.10.deb"
