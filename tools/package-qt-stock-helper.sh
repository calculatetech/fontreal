#!/bin/bash
set -euo pipefail
umask 022

root=$(cd "$(dirname "$0")/.." && pwd)
source="$root/integrations/qt-stock"
version=$(cat "$root/VERSION")
format=${1:?Usage: package-qt-stock-helper.sh deb|rpm|arch|kde-linux OUTPUT PROVIDER...}
output=$(realpath -m "${2:?Set the output directory}")
shift 2
if [[ $# == 0 || ! $format =~ ^(deb|rpm|arch|kde-linux)$ ]]; then
    echo 'Provide a package format and at least one stock Qt provider.' >&2
    exit 1
fi

mkdir -p "$output"
work=$(mktemp -d "$output/.package.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
pack="$work/root"
plugins="$pack/usr/lib/fontreal/qt6/plugins/generic"
painter=libfontreal-cached-probe.so
quick=libfontreal_quick_default_probe.so
mkdir -p "$plugins/providers"
ids="$work/providers.inc"
for input in "$@"; do
    key=$(basename "$input")
    if [[ ! $key =~ ^([0-9a-f]{40})-([0-9a-f]{40})$ || -e "$plugins/providers/$key" ]]; then
        printf 'Invalid or duplicate provider directory: %s\n' "$input" >&2
        exit 1
    fi
    gui_id=${BASH_REMATCH[1]}
    quick_id=${BASH_REMATCH[2]}
    install -D -m 644 "$input/$painter" "$plugins/providers/$key/$painter"
    install -D -m 644 "$input/$quick" "$plugins/providers/$key/$quick"
    printf '    {{%s}, {%s}, "%s"},\n' \
        "$(sed -E 's/(..)/0x\1,/g' <<< "$gui_id")" \
        "$(sed -E 's/(..)/0x\1,/g' <<< "$quick_id")" "$key" >> "$ids"
    qt_version=$(cat "$input/qt-version")
    [[ $qt_version =~ ^6\.[0-9]+\.[0-9]+$ ]]
    printf '%s %s\n' "$qt_version" "$key" >> "$work/versions"
done

read -r _ oldest < <(sort -V "$work/versions")
build_loader() {
    local name=$1
    shift
    local note="$work/plugin.note"
    objcopy --dump-section ".note.qt.metadata=$note" "$plugins/providers/$oldest/$name" "$work/provider-copy"
    cc -O2 -fPIC -shared -fvisibility=hidden -I "$work" \
        "-DFONTREAL_METADATA=\"$note\"" "-DMETADATA_SIZE=$(stat -c %s "$note")" "-DPROVIDER_FILE=\"$name\"" \
        "$@" "$source/loader.c" "$source/metadata.S" -ldl -o "$plugins/$name"
}
build_loader "$painter"
build_loader "$quick" -DFONTREAL_QUICK_LOADER

install -D -m 644 "$source/plasma-env.sh" "$pack/etc/xdg/plasma-workspace/env/fontreal.sh"
install -D -m 644 "$root/LICENSE" "$pack/usr/share/licenses/fontreal/LICENSE"
install -D -m 644 "$root/THIRD_PARTY_NOTICES.md" "$pack/usr/share/doc/fontreal/THIRD_PARTY_NOTICES.md"

case "$format" in
deb)
    install -m 644 "$root/LICENSE" "$pack/usr/share/doc/fontreal/copyright"
    mkdir "$pack/DEBIAN"
    cat > "$pack/DEBIAN/control" <<CONTROL
Package: fontreal
Version: $version
Architecture: amd64
Depends: libfontconfig1, libfreetype6, libqt6gui6, libqt6quick6, libqt6waylandclient6
Conflicts: fontreal-qt-helper-study, fontreal-session
Replaces: fontreal-qt-helper-study
Maintainer: Fontreal Project <fontreal@localhost>
Description: Fontreal V3 text rendering for Qt and Plasma
CONTROL
    dpkg-deb --build --root-owner-group "$pack" "$output/fontreal_${version}_amd64.deb"
    ;;
rpm)
    cat > "$work/fontreal.spec" <<SPEC
%global debug_package %{nil}
%global __os_install_post %{nil}
%global _build_id_links none
Name: fontreal
Version: $version
Release: 1
Summary: Fontreal V3 text rendering for Qt and Plasma
License: MIT
AutoReqProv: no
Requires: libQt6Gui.so.6()(64bit), libQt6Quick.so.6()(64bit)
Requires: libQt6WaylandClient.so.6()(64bit), libfontconfig.so.1()(64bit), libfreetype.so.6()(64bit)

%description
Applies Fontreal V3 to compatible stock Qt libraries in Plasma sessions.

%install
mkdir -p "%{buildroot}"
cp -a "$pack/." "%{buildroot}/"

%files
/etc/xdg/plasma-workspace/env/fontreal.sh
/usr/lib/fontreal
%license /usr/share/licenses/fontreal/LICENSE
%doc /usr/share/doc/fontreal/THIRD_PARTY_NOTICES.md
SPEC
    rpmbuild -bb --define "_topdir $work/rpm" "$work/fontreal.spec"
    install -m 644 "$work/rpm/RPMS/x86_64/"*.rpm "$output"
    ;;
arch)
    cat > "$work/PKGBUILD" <<PKGBUILD
pkgname=fontreal
pkgver=$version
pkgrel=1
pkgdesc='Fontreal V3 text rendering for Qt and Plasma'
arch=(x86_64)
license=(MIT)
depends=(qt6-base qt6-declarative qt6-wayland fontconfig freetype2)
options=(!strip !debug)
package() {
    cp -a '$pack/.' "\$pkgdir/"
}
PKGBUILD
    (cd "$work" && PKGDEST="$output" makepkg --nodeps --noconfirm)
    ;;
kde-linux)
    extension="$pack/var/lib/extensions/fontreal"
    mkdir -p "$extension"
    mv "$pack/usr" "$extension/usr"
    mkdir -p "$extension/usr/lib/extension-release.d"
    printf 'ID=_any\n' > "$extension/usr/lib/extension-release.d/extension-release.fontreal"
    tar --zstd --owner=0 --group=0 -C "$pack" -cf "$output/fontreal-$version-kde-linux-x86_64.tar.zst" etc var
    ;;
esac
