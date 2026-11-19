#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 ]]; then
    printf 'Usage: bash tests/v3_widgets_test.sh OFFICIAL_PACKAGES_DIR\n' >&2
    exit 2
fi
packages=$(realpath "$1")
cd "$(dirname -- "$(realpath -- "$0")")/.."
root=$(realpath build/v3-qt/widgets)
qt="$root/qt-build"
if [[ ! -f "$qt/lib/libQt6Widgets.so.6.10.2" ]]; then
    printf 'Build the V3 Widgets prototype with python3 tools/build-qt.py --v3-widgets.\n' >&2
    exit 1
fi
"${CXX:-c++}" -std=c++17 -O2 $(pkg-config --cflags Qt6Widgets Qt6Test freetype2) -Isrc \
    tests/v3_widgets_probe.cpp src/fontreal_v3_coverage.cpp src/fontreal_v3_outline.cpp \
    src/fontreal_v3_thin.cpp $(pkg-config --libs Qt6Widgets Qt6Test freetype2) -ldl \
    -o "$root/paint-probe"
cd "$root"
stock=$(mktemp -d -p "$root" stock.XXXXXX)
trap 'rm -r -- "$stock"' EXIT
arch=$(dpkg --print-architecture)
for name in libfreetype6 libqt6core6t64 libqt6gui6 libqt6widgets6; do
    archives=("$packages"/"$name"_*"_$arch.deb")
    if [[ ${#archives[@]} != 1 || ! -f ${archives[0]} ]]; then
        printf 'Expected one official %s package in %s.\n' "$name" "$packages" >&2
        exit 2
    fi
    sha256sum -- "${archives[0]}"
    dpkg-deb -x "${archives[0]}" "$stock"
done
mapfile -t libraries < <(find "$stock" -name libfreetype.so.6 -type l)
if [[ ${#libraries[@]} != 1 ]]; then
    printf 'Expected one libfreetype.so.6 in the official package.\n' >&2
    exit 2
fi
ftdir=$(dirname -- "${libraries[0]}")
export FONTREAL_PROBE_FT=$(realpath "${libraries[0]}")
sha256sum -- "$FONTREAL_PROBE_FT"
mkdir -p "$root/fontconfig/cache" "$root/xvfb-tmp" "$root/captures"
install -d -m 700 "$root/runtime"
export LD_LIBRARY_PATH="$qt/lib:$ftdir"
export QT_PLUGIN_PATH="$qt/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$qt/plugins/platforms"
export TMPDIR="$root/xvfb-tmp" XDG_RUNTIME_DIR="$root/runtime" XDG_CURRENT_DESKTOP=KDE
export QT_QPA_PLATFORM=xcb FONTREAL_RENDERING=3
unset FREETYPE_PROPERTIES
ulimit -c 0
ldd ./paint-probe > "$root/loaded-libraries.txt"
grep -E 'libQt6(Core|Gui|Widgets)\.so\.6 =>|libfreetype\.so\.6 =>' "$root/loaded-libraries.txt"
grep -F "libQt6Gui.so.6 => $qt/lib/" "$root/loaded-libraries.txt" > /dev/null
grep -F "libQt6Widgets.so.6 => $qt/lib/" "$root/loaded-libraries.txt" > /dev/null
grep -F "libfreetype.so.6 => $ftdir/" "$root/loaded-libraries.txt" > /dev/null

config() {
    local file=$1 layout=$2 aa=$3
    cat > "$root/fontconfig/$file.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>/usr/share/fonts/truetype/dejavu</dir>
  <dir>/usr/share/fonts/opentype/urw-base35</dir>
  <dir>/usr/share/fonts/truetype/ubuntu</dir>
  <cachedir>$root/fontconfig/cache</cachedir>
  <match target="font">
    <edit name="rgba" mode="assign"><const>$layout</const></edit>
    <edit name="antialias" mode="assign"><bool>$aa</bool></edit>
  </match>
</fontconfig>
EOF
}

run() {
    local label=$1 config=$2 scale=$3 layout=$4 mode=$5 family=$6 style=$7 font=$8 thin=$9 italic=${10}
    export QT_SCALE_FACTOR="$scale" FONTCONFIG_FILE="$root/fontconfig/$config.conf"
    echo "== $label =="
    xvfb-run -a --server-args="-screen 0 1024x768x24 -nolisten tcp" ./paint-probe "$layout" "$mode" "$family" "$style" "$font" "$thin" "$italic" "$root/captures/$label"
}

regular=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
light=/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf
cff=/usr/share/fonts/opentype/urw-base35/URWBookman-LightItalic.otf
variable='/usr/share/fonts/truetype/ubuntu/UbuntuSans[wdth,wght].ttf'
layouts=(none rgb bgr vrgb vbgr)
for i in "${!layouts[@]}"; do
    layout=${layouts[i]}
    config "$layout" "$layout" true
    run "$layout" "$layout" 1 "$i" v3 "DejaVu Sans" Book "$regular" 0 0
done

config mono rgb false
run system-mono mono 1 1 system-mono "DejaVu Sans" Book "$regular" 0 0
run app-mono rgb 1 1 app-mono "DejaVu Sans" Book "$regular" 0 0
run app-gray rgb 1 1 app-gray "DejaVu Sans" Book "$regular" 0 0
run dpr125 rgb 1.25 1 v3 "DejaVu Sans" Book "$regular" 0 0
run dpr125-system-mono mono 1.25 1 system-mono "DejaVu Sans" Book "$regular" 0 0
run thin-ttf rgb 1 1 v3 "DejaVu Sans" ExtraLight "$light" 1 0
run thin-cff rgb 1 1 v3 "URW Bookman" "Light Italic" "$cff" 1 1
FONTREAL_PROBE_TEXT_AA_OFF=1 run cff-native-clip none 1 0 stock "URW Bookman" "Light Italic" "$cff" 1 1
run float-clip none 1 0 float-clip "DejaVu Sans" Book "$regular" 0 0
FONTREAL_PROBE_TEXT_AA_OFF=1 run float-native-ttf none 1 0 float-clip "DejaVu Sans" Book "$regular" 0 0
run float-native-cff none 1 0 float-native "URW Bookman" "Light Italic" "$cff" 1 1
FONTREAL_PROBE_WEIGHT=300 run axis-light rgb 1 1 v3 "Ubuntu Sans" Regular "$variable" 1 0
FONTREAL_PROBE_WEIGHT=360 run axis-heavy rgb 1 1 v3 "Ubuntu Sans" Light "$variable" 0 0
FONTREAL_PROBE_WEIGHT=400 run axis-ignored rgb 1 1 ignored-axis "DejaVu Sans" ExtraLight "$light" 1 0
FONTREAL_PROBE_OVERLAP=1 run overlap rgb 1 1 v3 "DejaVu Sans" Book "$regular" 0 0
FONTREAL_PROBE_CLIP=1 run tiny-clip rgb 1 1 clip "DejaVu Sans" Book "$regular" 0 0
FONTREAL_PROBE_CLIP=2 run zero-clip rgb 1 1 clip-zero "DejaVu Sans" Book "$regular" 0 0
FONTREAL_PROBE_CLIP=3 run native-zero-clip rgb 1 1 clip-zero "DejaVu Sans" Book "$regular" 0 0
FONTREAL_RENDERING=0 run disabled rgb 1 1 stock "DejaVu Sans" Book "$regular" 0 0
env LD_LIBRARY_PATH="$ftdir" QT_PLUGIN_PATH="$ftdir/qt6/plugins" \
    QT_QPA_PLATFORM_PLUGIN_PATH="$ftdir/qt6/plugins/platforms" FONTREAL_RENDERING=0 \
    QT_SCALE_FACTOR=1 FONTCONFIG_FILE="$root/fontconfig/rgb.conf" \
    xvfb-run -a --server-args="-screen 0 1024x768x24 -nolisten tcp" ./paint-probe 1 stock "DejaVu Sans" Book "$regular" 0 0 "$root/captures/system-qt"
env FONTREAL_PROBE_TEXT_AA_OFF=1 LD_LIBRARY_PATH="$ftdir" QT_PLUGIN_PATH="$ftdir/qt6/plugins" \
    QT_QPA_PLATFORM_PLUGIN_PATH="$ftdir/qt6/plugins/platforms" FONTREAL_RENDERING=0 \
    QT_SCALE_FACTOR=1 FONTCONFIG_FILE="$root/fontconfig/none.conf" \
    xvfb-run -a --server-args="-screen 0 1024x768x24 -nolisten tcp" ./paint-probe 0 stock "URW Bookman" "Light Italic" "$cff" 1 1 "$root/captures/cff-native-stock"
env LD_LIBRARY_PATH="$ftdir" QT_PLUGIN_PATH="$ftdir/qt6/plugins" \
    QT_QPA_PLATFORM_PLUGIN_PATH="$ftdir/qt6/plugins/platforms" FONTREAL_RENDERING=0 \
    QT_SCALE_FACTOR=1 FONTCONFIG_FILE="$root/fontconfig/none.conf" \
    xvfb-run -a --server-args="-screen 0 1024x768x24 -nolisten tcp" ./paint-probe 0 float-native "URW Bookman" "Light Italic" "$cff" 1 1 "$root/captures/float-native-stock"
env LD_LIBRARY_PATH="$ftdir" QT_PLUGIN_PATH="$ftdir/qt6/plugins" \
    QT_QPA_PLATFORM_PLUGIN_PATH="$ftdir/qt6/plugins/platforms" FONTREAL_RENDERING=0 \
    QT_SCALE_FACTOR=1 FONTCONFIG_FILE="$root/fontconfig/none.conf" \
    xvfb-run -a --server-args="-screen 0 1024x768x24 -nolisten tcp" ./paint-probe 0 float-reference "DejaVu Sans" Book "$regular" 0 0 "$root/captures/float-reference-stock"
python3 - "$root/captures" <<'PY'
from pathlib import Path
from struct import iter_unpack
import sys
from PIL import Image

folder = Path(sys.argv[1])
assert (folder / "float-native-cff.rgba32f").read_bytes() == (folder / "float-native-stock.rgba32f").read_bytes()
stock_tt = list(iter_unpack("=ffff", (folder / "float-reference-stock.rgba32f").read_bytes()))
v3_tt = list(iter_unpack("=ffff", (folder / "float-native-ttf.rgba32f").read_bytes()))
assert len(stock_tt) == len(v3_tt) and any(pixel[0] < 1.0 for pixel in stock_tt)
for stock_pixel, v3_pixel in zip(stock_tt, v3_tt):
    assert abs(stock_pixel[0] - v3_pixel[0] / 1.5) <= 2 / 65535, (stock_pixel, v3_pixel)
for target in ("window", "intermediate"):
    def pixels(prefix):
        return Image.open(folder / f"{prefix}-{target}.png").convert("RGB").tobytes()

    assert pixels("cff-native-clip") == pixels("cff-native-stock"), target
    assert pixels("disabled") == pixels("system-qt"), target
    assert pixels("rgb") != pixels("disabled"), target
    print(f"disabled {target} pixels equal packaged stock Qt and differ from V3")
PY
