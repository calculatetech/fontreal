#!/usr/bin/env python3
"""Build the opt-in Qt 6.10.2 experiment without installing it."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/qt-native"
VERSION = "6.10.2"
NAME = f"qtbase-everywhere-src-{VERSION}"
DIGEST = "aeb78d29291a2b5fd53cb55950f8f5065b4978c25fb1d77f627d695ab9adf21e"


def platform_headers():
    """Supply Ubuntu's missing Qt platform headers without installing packages."""
    dependencies = WORK / "x11-build-deps"
    if not (dependencies / "ready").exists():
        packages = ["libxres-dev", "libatspi2.0-dev", "libdbus-1-dev", "libxcb1-dev", "libx11-xcb-dev", "libxkbcommon-x11-dev", "libxcb-cursor-dev",
                    "libxcb-icccm4-dev", "libxcb-util-dev", "libxcb-image0-dev",
                    "libxcb-keysyms1-dev", "libxcb-render-util0-dev", "libxcb-randr0-dev",
                    "libxcb-shape0-dev", "libxcb-shm0-dev", "libxcb-sync-dev",
                    "libxcb-xfixes0-dev", "libxcb-xkb-dev", "libxcb-render0-dev",
                    "libxcb-glx0-dev", "libxcb-xinput-dev", "libxcb-xinerama0-dev"]
        dependencies.mkdir(exist_ok=True)
        subprocess.run(["apt-get", "download", *packages], cwd=dependencies, check=True)
        for package in dependencies.glob("*.deb"):
            subprocess.run(["dpkg-deb", "-x", str(package), str(dependencies)], check=True)
        prefix = dependencies / "usr"
        for pc in prefix.rglob("*.pc"):
            pc.write_text(pc.read_text().replace("prefix=/usr", f"prefix={prefix}"))
        for link in prefix.rglob("*.so"):
            if link.is_symlink() and not link.exists():
                system = Path("/usr") / link.resolve().relative_to(prefix)
                if not system.exists():
                    raise SystemExit(f"Required installed platform runtime is missing: {system}")
                link.unlink()
                link.symlink_to(system)
        (dependencies / "ready").write_text("Ubuntu Qt platform development headers extracted locally.\n")
    return dependencies / "usr"


def main():
    installed = subprocess.check_output(
        ["pkg-config", "--modversion", "Qt6Core"], text=True).strip()
    if installed != VERSION:
        raise SystemExit(f"This experiment needs installed Qt {VERSION}; found {installed}.")
    WORK.mkdir(parents=True, exist_ok=True)
    headers = platform_headers()
    archive = WORK / f"{NAME}.tar.xz"
    if not archive.exists():
        url = f"https://download.qt.io/archive/qt/6.10/{VERSION}/submodules/{archive.name}"
        with urllib.request.urlopen(url, timeout=120) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != DIGEST:
        raise SystemExit(f"Qt source checksum mismatch: {archive}")
    source = WORK / NAME
    patch = ROOT / f"patches/qt-{VERSION}-fontreal.patch"
    # The source is generated here. Restore only the files owned by our patch.
    with tarfile.open(archive) as bundle:
        if not source.exists():
            bundle.extractall(WORK, filter="data")
        else:
            paths = [line[6:] for line in patch.read_text().splitlines()
                     if line.startswith("+++ b/")]
            for path in paths:
                bundle.extract(f"{NAME}/{path}", WORK, filter="data")
    subprocess.run(["patch", "--batch", "-p1", "-i", str(patch)], cwd=source, check=True)
    output = WORK / "qt-build"
    env = os.environ.copy()
    pkgconfig = headers / "lib/x86_64-linux-gnu/pkgconfig"
    env["PKG_CONFIG_PATH"] = str(pkgconfig) + ":" + env.get("PKG_CONFIG_PATH", "")
    subprocess.run([
        "cmake", "--fresh", "-S", str(source), "-B", str(output), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX={WORK / 'unused-install'}",
        # Existing binaries use copy relocations for Qt's public application pointer.
        "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,--dynamic-list-data",
        "-DQT_BUILD_TESTS=OFF", "-DQT_BUILD_EXAMPLES=OFF",
        "-DFEATURE_system_freetype=ON", "-DFEATURE_system_harfbuzz=OFF",
        "-DFEATURE_xcb=ON", "-DFEATURE_xcb_xlib=ON", "-DFEATURE_xkbcommon_x11=ON",
        "-DFEATURE_dbus=ON", "-DFEATURE_accessibility_atspi_bridge=ON",
        "-DQT_NO_FEATURE_AUTO_RESET=ON", f"-DCMAKE_PREFIX_PATH={headers}",
    ], env=env, check=True)
    subprocess.run(["cmake", "--build", str(output), "--target", "Gui",
                    "--parallel", str(min(12, os.cpu_count() or 1))], check=True)
    print(f"Private Qt ready: {output / 'lib'}")


if __name__ == "__main__":
    main()
