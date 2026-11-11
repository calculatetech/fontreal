#!/usr/bin/env python3
"""Check the real launchers, QWidget pixels, and isolated Konsole lifecycle."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/qt-native"
LIB = WORK / "qt-build/lib"
RUN = ROOT / "tools/run-qt.py"
PROBE = ROOT / "build/qt-native-probe"


def call(command, **kwargs):
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        sys.stderr.write(result.stderr)
        result.check_returncode()
    return result


def widget_checks():
    fonts = [call(["fc-match", "-f", "%{file}", pattern]).stdout for pattern in
             ("Noto Sans:style=Regular", "DejaVu Sans:style=Book")]
    records = []
    with tempfile.TemporaryDirectory(prefix="probe-", dir=WORK) as directory:
        for pixels, scale in ((13, 1), (15, 1), (16, 1), (10, 1.5), (11, 1.5), (13, 1.25)):
            group = {}
            for mode in ("stock", "stock-inherited", "inactive", "linear", "encoded"):
                env = os.environ.copy()
                env.update(QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR=str(scale))
                env.pop("FONTREAL_RENDERING", None)
                env.pop("FONTREAL_BLEND", None)
                env.pop("LD_LIBRARY_PATH", None)
                env["QT_PLUGIN_PATH"] = call(["qtpaths6", "--query", "QT_INSTALL_PLUGINS"]).stdout.strip()
                expected = mode if mode in ("linear", "encoded") else "stock"
                command = [str(PROBE), expected, str(pixels), str(scale), *fonts, directory]
                if mode in ("inactive", "stock-inherited"):
                    env["LD_LIBRARY_PATH"] = str(LIB)
                if mode == "stock-inherited":
                    env.update(FONTREAL_RENDERING="1", FONTREAL_BLEND="linear")
                if mode != "inactive":
                    command = [sys.executable, str(RUN), expected, *command]
                result = call(command, env=env)
                record = json.loads(result.stdout)
                private = str(LIB) in record["qtGui"]
                assert private == (mode in ("inactive", "linear", "encoded")), record["qtGui"]
                group[mode] = record
                records.append(record)
            assert group["stock"]["images"] == group["stock-inherited"]["images"]
            assert group["stock"]["images"] == group["inactive"]["images"]
            assert group["linear"]["masks"] == group["encoded"]["masks"]
            assert group["linear"]["images"] != group["encoded"]["images"]
            assert group["stock"]["masks"] != group["encoded"]["masks"]
            print(f"S1-S4: QWidget masks, pixels, cache, colors, placement, and runtime at {pixels}px x {scale}", flush=True)
    invalid = subprocess.run([sys.executable, str(RUN), "invalid", "/bin/true"], capture_output=True)
    assert invalid.returncode != 0 and b"invalid choice" in invalid.stderr
    build = WORK / "qt-build"
    hidden = WORK / "qt-build-missing-check"
    assert not hidden.exists()
    build.rename(hidden)
    try:
        missing = subprocess.run([sys.executable, str(RUN), "linear", "/bin/true"], capture_output=True)
        assert missing.returncode != 0 and b"Private Qt is missing" in missing.stderr
    finally:
        hidden.rename(build)
    return records


def configuration():
    paths = []
    for key, default in (("CONFIG", ".config"), ("STATE", ".local/state")):
        base = Path(os.environ.get(f"XDG_{key}_HOME", Path.home() / default))
        paths.extend(base / name for name in ("kdeglobals", "konsolerc", "konsolestaterc"))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in paths}


def konsole_checks():
    before = configuration()
    records = []
    for mode, family, pixels in (("stock", "Noto Sans", 15), ("linear", "Noto Sans", 15),
                                 ("encoded", "Noto Sans", 15), ("encoded", "DejaVu Sans", 16)):
        case = mode if family == "Noto Sans" else "encoded-dejavu16"
        env = os.environ.copy()
        env.pop("QT_QPA_PLATFORM", None)
        env["LD_PRELOAD"] = str(ROOT / "build/libqt-native-trace.so")
        log = WORK / f"konsole-{case}.log"
        with log.open("w") as output:
            process = subprocess.Popen([sys.executable, str(ROOT / "tools/preview-konsole.py"), mode,
                                        "--family", family, "--pixels", str(pixels)],
                                       env=env, text=True, stdout=subprocess.PIPE, stderr=output)
            label = process.stdout.readline().strip()
            state = Path(process.stdout.readline().strip().removeprefix("Private state: "))
            deadline = time.monotonic()+15
            child = None
            service = None
            while time.monotonic() < deadline:
                assert process.poll() is None, log.read_text()
                children = Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
                for pid in children:
                    command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")[0]
                    if command.endswith(b"konsole"):
                        child = int(pid)
                if child:
                    names = call(["qdbus6"]).stdout.splitlines()
                    service = next((n.strip() for n in names if "org.kde.konsole" in n and str(child) in n), None)
                if service:
                    break
                time.sleep(0.05)
            assert service and child, "Konsole did not register its separate process"
            kde = configparser.ConfigParser(strict=False, interpolation=None)
            kde.read(state / "config/kdeglobals")
            font_roles = {key: kde.get("General", key, fallback=None) for key in ("font", "menuFont")}
            mappings = Path(f"/proc/{child}/maps").read_text()
            gui = [line[line.index('/'):] for line in mappings.splitlines() if "/libQt6Gui.so." in line][0]
            assert (str(LIB) in gui) == (mode != "stock"), gui
            roots = dict(item.split(b"=", 1) for item in Path(f"/proc/{child}/environ").read_bytes().split(b"\0") if b"=" in item)
            for key in ("CONFIG", "CACHE", "DATA", "STATE"):
                assert Path(os.fsdecode(roots[f"XDG_{key}_HOME".encode()])).is_relative_to(state)
            tree = call(["qdbus6", service]).stdout.splitlines()
            window = next(p.strip() for p in tree if "/konsole/MainWindow_" in p)
            actions = call(["qdbus6", service, window, "org.kde.KMainWindow.actions"]).stdout.splitlines()
            def activate(action):
                assert process.poll() is None
                status = Path(f"/proc/{child}/status").read_text()
                assert re.search(rf"^PPid:\s+{process.pid}$", status, re.MULTILINE)
                owner = call(["qdbus6", "org.freedesktop.DBus", "/org/freedesktop/DBus",
                              "org.freedesktop.DBus.GetConnectionUnixProcessID", service]).stdout.strip()
                assert owner == str(child)
                environment = Path(f"/proc/{child}/environ").read_bytes().split(b"\0")
                assert os.fsencode(f"XDG_CONFIG_HOME={state / 'config'}") in environment
                return call(["qdbus6", service, window, "org.kde.KMainWindow.activateAction", action])
            assert "options_show_menubar" in actions, actions
            for action in ("options_show_menubar", "options_show_menubar"):
                assert activate(action).stdout.strip() == "true"
            time.sleep(2)  # Let Konsole's temporary size overlay disappear before capture.
            capture = WORK / f"konsole-{case}.png"
            call(["spectacle", "--background", "--activewindow", "--nonotify", "--output", str(capture)])
            quit_action = "file_quit" if "file_quit" in actions else "close-window"
            assert quit_action in actions, actions
            assert activate(quit_action).stdout.strip() == "true"
            assert process.wait(timeout=15) == 0, log.read_text()
            assert not state.exists(), state
        expected_font = f"{family},-1,{pixels},5,50,0,0,0,0,0"
        assert all(value == expected_font for value in font_roles.values()), font_roles
        text = log.read_text()
        loads = [int(value, 16) for value in re.findall(r"FONTREAL_TRACE load flags=0x([0-9a-f]+)", text)]
        rasters = [int(value) for value in re.findall(r"FONTREAL_TRACE raster mode=(\d+)", text)]
        assert loads and rasters, text
        assert re.search(rf"FONTREAL_TRACE size width={pixels*64} height={pixels*64} dpi=0,0 family={re.escape(family)}(?:\n|$)", text), text
        if mode != "stock":
            assert any((f & (15 << 16)) == (2 << 16) and f & 32 and not f & 2 for f in loads), loads
            assert 0 in rasters, rasters
        assert configuration() == before, "Normal KDE/Konsole configuration changed"
        records.append({"mode":mode, "family":family, "pixels":pixels, "fontRoles":font_roles, "pid":child, "qtGui":gui, "label":label,
                        "loadFlags":sorted(set(loads)), "renderModes":sorted(set(rasters)),
                        "capture":str(capture), "closedNormally":True, "privateStateRemoved":True})
        print(f"S5: actual {mode} Konsole, runtime/flags, menu repaint, capture, normal close, state cleanup passed", flush=True)
    return records


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    widgets = widget_checks()
    applications = konsole_checks()
    result = {"widgets":widgets, "applications":applications, "configurationPreserved":True}
    (WORK / "test-results.json").write_text(json.dumps(result, indent=2)+"\n")
    print("S1-S5: all native integration checks passed")
