#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 1 ]]; then
    printf 'Usage: bash tests/v3_quick_test.sh OFFICIAL_PACKAGES_DIR\n' >&2
    exit 2
fi
repo=$(cd "$(dirname "$0")/.." && pwd -P)
packages=$(realpath "$1")
base=$(realpath -m "$repo/build/v3-qt/widgets/qt-build")
quick=$(realpath -m "$repo/build/v3-qt/quick/qt-build")
if [[ ! -f $quick/lib/libQt6Quick.so.6.10.2 ]]; then
    printf 'Build the V3 prototypes with python3 tools/build-qt.py --v3-quick.\n' >&2
    exit 1
fi
work="$(dirname "$quick")/repository-test"
mkdir -p "$work"/{cache,config,source}
install -d -m 700 "$work/runtime"
stock=$(mktemp -d -p "$work" stock.XXXXXX)
captures=$(mktemp -d -p "$work" captures.XXXXXX)
printf 'Captures in %s\n' "$captures"
trap 'rm -r -- "$stock"' EXIT
arch=$(dpkg --print-architecture)
for name in libfreetype6 libqt6core6t64 libqt6dbus6 libqt6gui6 libqt6network6 libqt6opengl6 \
    libqt6qml6 libqt6qmlmodels6 libqt6quick6 libqt6widgets6 qt6-qpa-plugins; do
    archives=("$packages"/"$name"_*"_$arch.deb")
    if [[ ${#archives[@]} != 1 || ! -f ${archives[0]} ]]; then
        printf 'Expected one official %s package in %s.\n' "$name" "$packages" >&2
        exit 2
    fi
    dpkg-deb -x "${archives[0]}" "$stock"
done
stocklib="$stock/usr/lib/x86_64-linux-gnu"
stock_plugins="$stocklib/qt6/plugins"
mkdir -p "$work/mixed" "$work/plugins"/{platforms,xcbglintegrations}
ln -sfn "$quick/lib/libQt6Quick.so.6" "$work/mixed/libQt6Quick.so.6"
ln -sfn "$base/plugins/platforms/libqxcb.so" "$work/plugins/platforms/libqxcb.so"
ln -sfn "$stock_plugins/xcbglintegrations/libqxcb-glx-integration.so" \
    "$work/plugins/xcbglintegrations/libqxcb-glx-integration.so"

cat > "$work/source/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.25)
project(FontrealQuickProbe LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(Qt6 6.10.2 EXACT REQUIRED COMPONENTS Quick Widgets QuickPrivate)
find_package(Freetype REQUIRED)
add_executable(quick-probe "${CHECKOUT}/tests/v3_quick_probe.cpp"
    "${CHECKOUT}/src/fontreal_v3_coverage.cpp" "${CHECKOUT}/src/fontreal_v3_outline.cpp"
    "${CHECKOUT}/src/fontreal_v3_thin.cpp")
target_include_directories(quick-probe PRIVATE "${CHECKOUT}/src")
target_link_libraries(quick-probe PRIVATE Qt6::QuickPrivate Qt6::Widgets Freetype::Freetype ${CMAKE_DL_LIBS})
CMAKE
cmake -S "$work/source" -B "$work/build" -G Ninja "-DCMAKE_PREFIX_PATH=$quick;$base" \
    "-DQT_ADDITIONAL_PACKAGES_PREFIX_PATH=$quick" "-DCHECKOUT=$repo"
cmake --build "$work/build" --parallel 4

for layout in rgb none; do
    cat > "$work/config/$layout.conf" <<CONFIG
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>/usr/share/fonts/truetype/dejavu</dir>
  <cachedir>$work/cache</cachedir>
  <match target="font">
    <edit name="rgba" mode="assign"><const>$layout</const></edit>
    <edit name="antialias" mode="assign"><bool>true</bool></edit>
  </match>
</fontconfig>
CONFIG
done

export XDG_RUNTIME_DIR="$work/runtime" XDG_CACHE_HOME="$work/cache"
export QT_QPA_PLATFORM=xcb QT_XCB_GL_INTEGRATION=xcb_glx LIBGL_ALWAYS_SOFTWARE=1 LD_BIND_NOW=1
export FONTREAL_PROBE_DEFAULT_QML=1 FONTREAL_PROBE_FT="$(realpath "$stocklib/libfreetype.so.6")"
unset FREETYPE_PROPERTIES FONTREAL_PROBE_RICH_INK FONTREAL_PROBE_STOCK_STYLE
ulimit -c 0
font=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf

capture() {
    local label=$1 libs=$2 plugins=$3 rendering=$4 expected_status=$5 status=0
    printf '%s %s %s %s\n' "$label" "$QSG_RENDER_LOOP" "$QT_SCALE_FACTOR" "$layout"
    LD_LIBRARY_PATH="$libs:$stocklib" QT_PLUGIN_PATH="$plugins" FONTREAL_RENDERING="$rendering" \
        xvfb-run -a -s '-screen 0 1024x600x24 +extension GLX' \
        "$work/build/quick-probe" "$font" "$captures/$label" || status=$?
    test "$status" -eq "$expected_status"
}

for scale in 1 1.25; do
    export QT_SCALE_FACTOR="$scale"
    for layout in rgb none; do
        export FONTCONFIG_FILE="$work/config/$layout.conf" QSG_RENDER_LOOP=basic
        stock_label="stock-$scale-$layout"
        mixed_label="mixed-$scale-$layout"
        capture "$stock_label" "$stocklib" "$stock_plugins" 0 0
        capture "$mixed_label" "$work/mixed" "$stock_plugins" 3 1
        for frame in 0 1 2; do
            for target in visible buffer; do
                cmp "$captures/$stock_label-$frame-$target.png" \
                    "$captures/$mixed_label-$frame-$target.png"
            done
        done
        for loop in basic threaded; do
            export QSG_RENDER_LOOP="$loop"
            capture "paired-$loop-$scale-$layout" "$quick/lib:$base/lib" "$work/plugins" 3 0
            FONTREAL_PROBE_RICH_INK=1 capture "colored-$loop-$scale-$layout" \
                "$quick/lib:$base/lib" "$work/plugins" 3 0
        done
    done
done

export QT_SCALE_FACTOR=1.25 FONTCONFIG_FILE="$work/config/none.conf" QSG_RENDER_LOOP=basic
layout=none
for style in large outline; do
    FONTREAL_PROBE_STOCK_STYLE="$style" capture "$style-stock" "$stocklib" "$stock_plugins" 0 0
    FONTREAL_PROBE_STOCK_STYLE="$style" capture "$style-paired" "$quick/lib:$base/lib" "$work/plugins" 3 0
    for frame in 0 1 2; do
        for target in visible buffer; do
            cmp "$captures/$style-stock-$frame-$target.png" "$captures/$style-paired-$frame-$target.png"
        done
    done
done
