#!/usr/bin/env python3
"""Build the opt-in Qt 6.10.2 experiment without installing it."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/qt-native"
VERSION = "6.10.2"
NAME = f"qtbase-everywhere-src-{VERSION}"
DIGEST = "aeb78d29291a2b5fd53cb55950f8f5065b4978c25fb1d77f627d695ab9adf21e"
DECLARATIVE_DIGEST = "a249914ff66cdcdbf0df8b5ffad997a2ee6dce01cc17d43c6cc56fdc1d0f4b0f"


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


def sources(name, digest, patch, work=WORK):
    archive = WORK / f"{name}.tar.xz"
    if not archive.exists():
        url = f"https://download.qt.io/archive/qt/6.10/{VERSION}/submodules/{archive.name}"
        with urllib.request.urlopen(url, timeout=120) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise SystemExit(f"Qt source checksum mismatch: {archive}")
    source = work / name
    with tarfile.open(archive) as bundle:
        if not source.exists():
            bundle.extractall(work, filter="data")
        else:
            paths = [line[6:] for line in patch.read_text().splitlines()
                     if line.startswith("+++ b/")]
            for path in paths:
                bundle.extract(f"{name}/{path}", work, filter="data")
    subprocess.run(["patch", "--batch", "-p1", "-i", str(patch)], cwd=source, check=True)
    return source


def shader_tools():
    dependencies = WORK / "shader-build-deps"
    executable = dependencies / "usr/lib/qt6/bin/qsb"
    if not executable.exists():
        dependencies.mkdir(exist_ok=True)
        subprocess.run(["apt-get", "download", "qt6-shader-baker=6.10.2-1",
                        "qt6-shadertools-dev=6.10.2-1", "libqt6shadertools6=6.10.2-1"],
                       cwd=dependencies, check=True)
        for package in dependencies.glob("*.deb"):
            subprocess.run(["dpkg-deb", "-x", str(package), str(dependencies)], check=True)
    return dependencies / "usr"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-widgets", action="store_true",
                        help="Build the isolated V3 Widgets prototype")
    args = parser.parse_args()
    installed = subprocess.check_output(
        ["pkg-config", "--modversion", "Qt6Core"], text=True).strip()
    if installed != VERSION:
        raise SystemExit(f"This experiment needs installed Qt {VERSION}; found {installed}.")
    WORK.mkdir(parents=True, exist_ok=True)
    headers = platform_headers()
    work = (ROOT / "build/v3-qt/widgets").resolve() if args.v3_widgets else WORK
    patch_suffix = "-v3-widgets" if args.v3_widgets else ""
    source = sources(NAME, DIGEST, ROOT / f"patches/qt-{VERSION}-fontreal{patch_suffix}.patch", work)
    if args.v3_widgets:
        for name in ("coverage.cpp", "coverage.h", "outline.cpp", "outline.h", "thin.cpp"):
            filename = f"fontreal_v3_{name}"
            shutil.copyfile(ROOT / "src" / filename, source / "src/gui/text/freetype" / filename)
    output = work / "qt-build"
    env = os.environ.copy()
    pkgconfig = headers / "lib/x86_64-linux-gnu/pkgconfig"
    env["PKG_CONFIG_PATH"] = str(pkgconfig) + ":" + env.get("PKG_CONFIG_PATH", "")
    configure = [
        "cmake", "--fresh", "-S", str(source), "-B", str(output), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX={work / 'unused-install'}",
        # Existing binaries use copy relocations for Qt's public application pointer.
        "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,--dynamic-list-data",
        "-DQT_BUILD_TESTS=OFF", "-DQT_BUILD_EXAMPLES=OFF",
        "-DFEATURE_system_freetype=ON", "-DFEATURE_system_harfbuzz=OFF",
        "-DFEATURE_xcb=ON", "-DFEATURE_xcb_xlib=ON", "-DFEATURE_xkbcommon_x11=ON",
        "-DFEATURE_dbus=ON", "-DFEATURE_accessibility_atspi_bridge=ON",
        "-DQT_NO_FEATURE_AUTO_RESET=ON", f"-DCMAKE_PREFIX_PATH={headers}",
    ]
    if args.v3_widgets:
        configure.append("-DFEATURE_fontconfig=ON")
    subprocess.run(configure, env=env, check=True)
    if args.v3_widgets:
        subprocess.run(["cmake", "--build", str(output), "--target", "Gui", "Widgets",
                        "QXcbIntegrationPlugin", "--parallel", str(min(12, os.cpu_count() or 1))],
                       check=True)
        print(f"Private V3 Widgets ready at {output}")
        return
    subprocess.run(["cmake", "--build", str(output), "--target", "Gui", "Network", "OpenGL",
                    "Widgets_sync_headers", "Test_sync_headers", "qlalr", "qtpaths",
                    "--parallel", str(min(12, os.cpu_count() or 1))], check=True)
    shaders = shader_tools()
    source = sources(f"qtdeclarative-everywhere-src-{VERSION}", DECLARATIVE_DIGEST,
                     ROOT / f"patches/qtdeclarative-{VERSION}-fontreal.patch")
    declarative = WORK / "declarative-build"
    env["LD_LIBRARY_PATH"] = str(shaders / "lib/x86_64-linux-gnu") + ":" + env.get("LD_LIBRARY_PATH", "")
    freetype = subprocess.check_output(["pkg-config", "--cflags", "freetype2"], text=True).strip()
    subprocess.run([
        "cmake", "--fresh", "-S", str(source), "-B", str(declarative), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX={WORK / 'unused-install'}",
        "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,--dynamic-list-data", f"-DCMAKE_CXX_FLAGS={freetype}",
        "-DQT_BUILD_TESTS=OFF", "-DQT_BUILD_EXAMPLES=OFF",
        f"-DCMAKE_PREFIX_PATH={output};{shaders}",
    ], env=env, check=True)
    subprocess.run(["cmake", "--build", str(declarative), "--target", "Quick",
                    "--parallel", str(min(12, os.cpu_count() or 1))], env=env, check=True)
    print(f"Private Qt ready: {output / 'lib'}")
    print(f"Private Qt Quick ready: {declarative / 'lib'}")


if __name__ == "__main__":
    main()
