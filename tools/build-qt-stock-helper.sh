#!/bin/bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
output=$(realpath -m "${1:-"$root/build/qt-stock-helper"}")
source="$root/integrations/qt-stock"
if [[ $(uname -m) != x86_64 ]]; then
    echo 'Fontreal stock Qt providers currently support x86-64.' >&2
    exit 1
fi

qtpaths=${QT_PATHS:-$(command -v qtpaths6 || command -v qtpaths || true)}
if [[ -z "$qtpaths" ]]; then
    qtpaths=$(pkg-config --variable=libdir Qt6Core)/qt6/bin/qtpaths
fi
headers=$("$qtpaths" --query QT_INSTALL_HEADERS)
runtime=$("$qtpaths" --query QT_INSTALL_LIBS)
qt_version=$("$qtpaths" --query QT_VERSION)
moc=$("$qtpaths" --query QT_HOST_LIBEXECS)/moc
qsb=$("$qtpaths" --query QT_HOST_BINS)/qsb
gui="$runtime/libQt6Gui.so.6"
quick="$runtime/libQt6Quick.so.6"
widgets="$runtime/libQt6Widgets.so.6"
wayland="$runtime/libQt6WaylandClient.so.6"

build_id() {
    local id
    id=$(LC_ALL=C readelf -n "$1" | awk '/Build ID:/ {print $3}') || return 1
    if [[ ! $id =~ ^[0-9a-f]{40}$ ]]; then
        printf 'Missing or unsupported GNU build ID: %s\n' "$1" >&2
        return 1
    fi
    printf '%s' "$id"
}

gui_id=$(build_id "$gui")
quick_id=$(build_id "$quick")
mkdir -p "$output"
work=$(mktemp -d "$output/.provider.XXXXXX")
trap 'rm -rf -- "$work"' EXIT

paint_device=$(LC_ALL=C readelf -Wr "$quick" | awk '
    $3 ~ /^R_X86_64_(GLOB_DAT|JUMP_SLOT)$/ && $5 ~ /^_ZN13QBackingStore11paintDeviceEv@/ {print $1}')
if [[ ! $paint_device =~ ^[0-9a-f]+$ ]]; then
    echo 'Qt Quick must have one relocation for QBackingStore::paintDevice.' >&2
    exit 1
fi

printf '#define FONTREAL_QT_PAINT_DEVICE 0x%s\n' "$paint_device" > "$work/runtime-abi.h"
printf '#define FONTREAL_QT_QUICK_ID %s\n' "$(sed -E 's/(..)/0x\1,/g' <<< "$quick_id")" >> "$work/runtime-abi.h"
for name in GUI QUICK WIDGETS WAYLAND; do
    file=${name,,}
    hash=$(sha256sum "${!file}")
    printf '#define FONTREAL_QT_%s_SHA "%s"\n' "$name" "${hash%% *}" >> "$work/runtime-abi.h"
done

flags=(-I"$headers" "-I$("$qtpaths" --query QT_HOST_DATA)/mkspecs/$("$qtpaths" --query QMAKE_XSPEC)")
for module in QtCore QtGui QtQml QtQmlIntegration QtQmlModels QtQuick QtWidgets; do
    flags+=(-I"$headers/$module" "-I$headers/$module/$qt_version" "-I$headers/$module/$qt_version/$module")
done

"$qsb" --glsl "100 es,120,150,330" -o "$work/coverage.qsb" "$source/coverage.frag"
xxd -i -n coverage_qsb "$work/coverage.qsb" > "$work/coverage_qsb.h"
read -ra ft_cflags <<< "$(pkg-config --cflags freetype2 fontconfig)"
read -ra ft_libs <<< "$(pkg-config --libs freetype2 fontconfig)"
core=("$root/src/fontreal_v3_coverage.cpp" "$root/src/fontreal_v3_outline.cpp" "$root/src/fontreal_v3_thin.cpp")
qt=("$gui" "$runtime/libQt6Core.so.6")

build_provider() {
    local name=$1 binary=$2
    shift 2
    "$moc" "${flags[@]}" -o "$work/$name.moc" "$source/$name.cpp"
    c++ -std=c++17 -DQT_NO_DEBUG -O2 -fPIC -shared "${flags[@]}" -I"$root/src" -I"$work" \
        "${ft_cflags[@]}" "$source/$name.cpp" "${core[@]}" "$@" "${qt[@]}" \
        "${ft_libs[@]}" -ldl -o "$work/$binary"
    if readelf -d "$work/$binary" | grep -E 'RPATH|RUNPATH'; then
        exit 1
    fi
}

build_provider fontreal-cached-probe libfontreal-cached-probe.so
build_provider scenegraph libfontreal_quick_default_probe.so "$quick"
dest="$output/$gui_id-$quick_id"
mkdir -p "$dest"
install -m 644 "$work"/libfontreal*.so "$dest"
printf '%s\n' "$qt_version" > "$dest/qt-version"
printf '%s\n' "$dest"
