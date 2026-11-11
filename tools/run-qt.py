#!/usr/bin/env python3
"""Select stock or private Qt for one child process."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "build/qt-native/qt-build/lib"
QUICK_LIB = ROOT / "build/qt-native/declarative-build/lib"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contrast", choices=("none", "mild"), default="none")
    parser.add_argument("mode", choices=("stock", "linear", "encoded"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.mode == "stock" and args.contrast != "none":
        parser.error("Stock mode requires --contrast none.")
    if not args.command:
        parser.error("Supply the Qt application and its arguments.")
    env = os.environ.copy()
    env.pop("FONTREAL_RENDERING", None)
    env.pop("FONTREAL_BLEND", None)
    env.pop("FONTREAL_CONTRAST", None)
    paths = [p for p in env.get("LD_LIBRARY_PATH", "").split(":")
             if p and Path(p).resolve() not in (LIB, QUICK_LIB)]
    if args.mode != "stock":
        if not (LIB / "libQt6Gui.so.6.10.2").is_file() or not (QUICK_LIB / "libQt6Quick.so.6.10.2").is_file():
            parser.error("Private Qt is missing. Run python3 tools/build-qt.py first.")
        version = subprocess.check_output(
            ["pkg-config", "--modversion", "Qt6Core"], text=True).strip()
        if version != "6.10.2":
            parser.error(f"The private build needs installed Qt 6.10.2; found {version}.")
        paths[:0] = [str(QUICK_LIB), str(LIB)]
        plugins = subprocess.check_output(
            ["qtpaths6", "--query", "QT_INSTALL_PLUGINS"], text=True).strip()
        env["QT_PLUGIN_PATH"] = plugins
        env["FONTREAL_RENDERING"] = "1"
        env["FONTREAL_BLEND"] = args.mode
        env["FONTREAL_CONTRAST"] = args.contrast
    if paths:
        env["LD_LIBRARY_PATH"] = ":".join(paths)
    else:
        env.pop("LD_LIBRARY_PATH", None)
    os.execvpe(args.command[0], args.command, env)


if __name__ == "__main__":
    main()
