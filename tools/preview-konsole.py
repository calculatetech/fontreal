#!/usr/bin/env python3
"""Open a separate Konsole with private settings for visual comparison."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("stock", "linear", "encoded"))
    parser.add_argument("--contrast", choices=("none", "mild"), default="none")
    parser.add_argument("--family", choices=("Noto Sans", "DejaVu Sans"), default="Noto Sans")
    parser.add_argument("--pixels", type=int, choices=range(6, 49), default=15, metavar="6..48")
    parser.add_argument("--scale", type=float, choices=(1.0, 1.25, 1.5, 2.0), default=1.0)
    parser.add_argument("--terminal-family", choices=("builtin", "Inconsolata Nerd Font"), default="builtin")
    parser.add_argument("--terminal-pixels", type=int, choices=range(6, 49), metavar="6..48")
    args = parser.parse_args()
    if args.mode == "stock" and args.contrast != "none":
        parser.error("Stock mode requires --contrast none.")
    if args.terminal_pixels is not None and args.terminal_family == "builtin":
        parser.error("--terminal-pixels requires --terminal-family 'Inconsolata Nerd Font'.")
    previews = ROOT / "build/qt-native/previews"
    previews.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    source = Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kdeglobals"
    with tempfile.TemporaryDirectory(prefix=f"{args.mode}-", dir=previews) as directory:
        state = Path(directory)
        for name in ("CONFIG", "CACHE", "DATA", "STATE"):
            destination = state / name.lower()
            destination.mkdir()
            env[f"XDG_{name}_HOME"] = str(destination)
        kde = state / "config/kdeglobals"
        if source.is_file():
            shutil.copyfile(source, kde)
        font = f"{args.family},-1,{args.pixels},5,50,0,0,0,0,0"
        for role in ("font", "menuFont"):
            subprocess.run(["kwriteconfig6", "--file", str(kde), "--group", "General",
                            "--key", role, font], check=True)
        env["QT_SCALE_FACTOR"] = str(args.scale)
        label = f"Fontreal {args.mode} | {args.family} {args.pixels}px x {args.scale:g}"
        if args.contrast != "none":
            label += f" | {args.contrast} contrast"
        terminal = "built-in fixed-pitch font"
        terminal_options = []
        if args.terminal_family != "builtin":
            point, pixels = (11, -1) if args.terminal_pixels is None else (-1, args.terminal_pixels)
            descriptor = f"{args.terminal_family},{point},{pixels},5,50,0,0,0,0,0"
            terminal_options = ["-p", f"Font={descriptor}"]
            terminal = f"{args.terminal_family} {point}pt" if pixels == -1 else f"{args.terminal_family} {pixels}px"
        print(label, flush=True)
        print(f"Private state: {state}", flush=True)
        command = [sys.executable, str(ROOT / "tools/run-qt.py"), "--contrast", args.contrast, args.mode,
                   "konsole", "--separate", "--builtin-profile", "--notransparency",
                   "--show-menubar", "--hold", "-p", f"LocalTabTitleFormat={label}",
                   *terminal_options, "-e", "/bin/sh", str(ROOT / "tools/konsole-sample.sh"), terminal]
        raise SystemExit(subprocess.run(command, env=env).returncode)


if __name__ == "__main__":
    main()
