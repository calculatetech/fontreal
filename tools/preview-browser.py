#!/usr/bin/env python3
"""Open a disposable Firefox/Floorp mask experiment without changing normal profiles."""
import argparse
import configparser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/freetype-native"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("control", "control-preblend", "encoded", "preblend", "ramp217", "raw", "weighted"))
    parser.add_argument("url", nargs="?", help="Optional test page; defaults to the local font fixture")
    parser.add_argument("--browser", choices=("firefox", "floorp"), default="firefox")
    parser.add_argument("--scale", type=float, choices=(1.0, 1.25, 1.5), default=1.0)
    parser.add_argument("--trace", action="store_true", help="Use the test build that reports final glyph masks")
    parser.add_argument("--marionette-port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    application = configparser.ConfigParser(interpolation=None)
    application.read(f"/usr/lib/{args.browser}/application.ini")
    version = application.get("App", "Version", fallback="unknown")
    build_command = [sys.executable, str(ROOT / "tools/build-freetype.py")]
    if args.trace:
        build_command.append("--trace")
    record_path = Path(subprocess.check_output(build_command, text=True).splitlines()[-1])
    record = json.loads(record_path.read_text())
    control = args.mode.startswith("control")
    library = Path(record["libraries"]["stock" if control else "candidate"]["library"])
    previews = WORK / "previews"
    previews.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{args.browser}-{args.mode}-", dir=previews) as directory:
        state = Path(directory).resolve()
        env = os.environ.copy()
        env.pop("FONTREAL_FT_EXECUTABLE", None)
        for role in ("CONFIG", "CACHE", "DATA", "STATE"):
            path = state / role.lower()
            path.mkdir()
            env[f"XDG_{role}_HOME"] = str(path)
        temporary = state / "tmp"
        temporary.mkdir()
        env["TMPDIR"] = str(temporary)
        profile = state / "profile"
        profile.mkdir()
        prefs = {
            "browser.shell.checkDefaultBrowser": False,
            "browser.aboutwelcome.enabled": False,
            "browser.startup.page": 0,
            "datareporting.policy.dataSubmissionEnabled": False,
            # Mozilla's own test profile suppresses first-run notifications this way.
            "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
            "datareporting.healthreport.uploadEnabled": False,
            "layout.css.devPixelsPerPx": str(args.scale),
            "gfx.webrender.enable-subpixel-aa": False,
            "gfx.text.subpixel-position.force-disabled": True,
            "gfx.font_rendering.freetype.gamma": 0 if args.mode.endswith("preblend") else -1,
            "gfx.font_rendering.freetype.enhanced_contrast": 0,
        }
        if args.marionette_port is not None:
            if not 1024 <= args.marionette_port <= 65535:
                parser.error("Test port must be between 1024 and 65535.")
            prefs["marionette.port"] = args.marionette_port
        (profile / "user.js").write_text("".join(
            f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k, v in prefs.items()))
        fontconfig = state / "fonts.conf"
        fontconfig.write_text('''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig><include>/etc/fonts/fonts.conf</include><match target="font">
<edit name="autohint" mode="assign"><bool>true</bool></edit>
<edit name="hinting" mode="assign"><bool>true</bool></edit>
<edit name="hintstyle" mode="assign"><const>hintfull</const></edit>
<edit name="antialias" mode="assign"><bool>true</bool></edit>
<edit name="rgba" mode="assign"><const>none</const></edit>
<edit name="embeddedbitmap" mode="assign"><bool>false</bool></edit>
</match></fontconfig>
''')
        env["FONTCONFIG_FILE"] = str(fontconfig)
        env["FONTREAL_FT_RENDERING"] = "0" if control else "1"
        env["FONTREAL_FT_CONTRAST"] = args.mode if args.mode in ("ramp217", "raw", "weighted") else "mild"
        env["LD_LIBRARY_PATH"] = str(library.parent) + (
            ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        url = args.url or (ROOT / "tests/browser_masks.html").as_uri() + "#" + args.mode
        command = [f"/usr/bin/{args.browser}", "--new-instance", "--no-remote", "--profile", str(profile)]
        if args.marionette_port is not None:
            command.append("--marionette")
        command.append(url)
        child = subprocess.Popen(command, env=env)
        print("FONTREAL_BROWSER " + json.dumps(dict(
            browser=args.browser, version=version, mode=args.mode, scale=args.scale, pid=child.pid,
            profile=str(profile), state=str(state), library=str(library),
            build=str(record_path), url=url)), flush=True)
        try:
            return child.wait()
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=20)


if __name__ == "__main__":
    raise SystemExit(main())
