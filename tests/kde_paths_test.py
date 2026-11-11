#!/usr/bin/env python3
"""Measure isolated Qt Quick, Plasma applet, and KWin title rendering."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "build/qt-kde-probe"
RUN = ROOT / "tools/run-qt.py"
WORK = ROOT / "build/kde-paths"


def call(command, env, timeout=45, **kwargs):
    result = subprocess.run([str(x) for x in command], env=env,
                            capture_output=True, text=True, timeout=timeout, **kwargs)
    if result.returncode:
        sys.stderr.write(result.stderr)
        result.check_returncode()
    return result


def selected(mode, command):
    return [sys.executable, RUN, "--contrast", "none" if mode in ("stock", "inactive", "linear-none") else "mild",
            "linear" if mode in ("inactive", "linear-none") else mode, *command]


def snapshot():
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))
    paths = [base/name for name in ("kdeglobals", "kwinrc", "breezerc", "plasmashellrc", "plasma-org.kde.plasma.desktop-appletsrc")]
    paths += [Path(call(["fc-match", "-f", "%{file}", f], os.environ).stdout) for f in
              ("Noto Sans:style=Regular", "Inconsolata Nerd Font:style=Regular", "Nimbus Sans:style=Regular", "Noto Color Emoji")]
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in paths}


def stop(child):
    if child.poll() is None:
        child.terminate()
    child.wait(timeout=10)


def private_environment(directory):
    env = os.environ.copy()
    for name in ("WAYLAND_DISPLAY", "WAYLAND_SOCKET", "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "LD_LIBRARY_PATH",
                 "LD_PRELOAD", "FONTREAL_RENDERING", "FONTREAL_BLEND", "FONTREAL_CONTRAST", "QT_QUICK_DEFAULT_TEXT_RENDER_TYPE"):
        env.pop(name, None)
    for role in ("CONFIG", "CACHE", "DATA", "STATE", "RUNTIME"):
        path = directory/role.lower()
        path.mkdir(mode=0o700)
        env[f"XDG_{role}_HOME" if role != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
    env.update(QT_QPA_PLATFORM="xcb", QT_QPA_PLATFORMTHEME="kde", LIBGL_ALWAYS_SOFTWARE="1",
               QSG_INFO="1", QSG_RENDER_LOOP="basic", QSG_RHI_BACKEND="opengl", QT_NO_XDG_DESKTOP_PORTAL="1")
    env["QML_IMPORT_PATH"] = call(["qtpaths6", "--query", "QT_INSTALL_QML"], env).stdout.strip()
    env["QT_PLUGIN_PATH"] = call(["qtpaths6", "--query", "QT_INSTALL_PLUGINS"], env).stdout.strip()
    return env


@contextlib.contextmanager
def display(env, directory):
    read, write = os.pipe()
    with (directory/"xvfb.log").open("w") as log:
        server = subprocess.Popen(["Xvfb", "-displayfd", str(write), "-screen", "0", "1100x740x24", "-nolisten", "tcp"],
                                  env=env, pass_fds=(write,), stdout=log, stderr=log)
        os.close(write)
        try:
            assert select.select([read], [], [], 10)[0], "Xvfb did not provide a display"
            number = os.read(read, 80).decode().strip()
            assert number.isdecimal(), (directory/"xvfb.log").read_text()
            yield dict(env, DISPLAY=f":{number}")
        finally:
            os.close(read)
            stop(server)


def quick_checks(env, font):
    records = []
    for backend, mode, scale, phase, override in (
        ("opengl", "stock", 1, 0, False),
        ("opengl", "linear", 1, 0, False),
        ("opengl", "encoded", 1, 0, False),
        ("opengl", "linear-none", 1, 0, False),
        ("opengl", "linear", 1, .5, False),
        ("opengl", "linear", 1.25, 0, False),
        ("opengl", "linear", 1.25, 0, True),
        ("software", "linear", 1, 0, False),
        ("software", "encoded", 1, 0, False),
        ("software", "linear", 1.25, 0, True),
    ):
        label = f"quick-{backend}-{mode}-{scale}-{phase}-{'native' if override else 'default'}"
        output = WORK/label
        output.mkdir(exist_ok=True)
        for filename in ("result.json", *(f"frame-{i}.png" for i in range(4))):
            (output/filename).unlink(missing_ok=True)
        case_env = dict(env, QT_SCALE_FACTOR=str(scale))
        if backend == "software":
            case_env["QT_QUICK_BACKEND"] = "software"
        else:
            case_env.pop("QT_QUICK_BACKEND", None)
        if override:
            case_env["QT_QUICK_DEFAULT_TEXT_RENDER_TYPE"] = "nativerendering"
        result = call(selected(mode, [PROBE, "quick", font, output, str(phase)]), case_env)
        (output/"runtime.log").write_text(result.stderr)
        record = json.loads((output/"result.json").read_text())
        assert len(record["frames"]) == 4
        assert record["frames"][0]["hash"] == record["frames"][1]["hash"], "Cached repaint changed output"
        assert record["frames"][1]["hash"] != record["frames"][2]["hash"] != record["frames"][3]["hash"]
        assert record["scale"] == scale
        assert ("qt-native/qt-build/lib" in record["qtGui"]) == (mode != "stock")
        record.update(label=label, backend=backend, selection=mode, nativeOverride=override)
        records.append(record)
        print(f"Captured {label}: API={record['graphicsApi']}", flush=True)
    return records


def spillover_checks(env):
    records = []
    for family, text, gray in (("Noto Sans:style=Regular", "lmnogWVwv", False), ("Nimbus Sans:style=Regular", "lmnogWVwv", False),
                               ("Nimbus Sans:style=Regular", "lmnogWVwv", True), ("Noto Color Emoji", "😀", False)):
        font = call(["fc-match", "-f", "%{file}", family], env).stdout
        group = {}
        for mode in ("stock", "inactive", "linear"):
            output = WORK/f"spillover-{family.split(':')[0].replace(' ', '-')}{'-gray' if gray else ''}-{mode}"
            case_env = dict(env, QT_QPA_PLATFORM="offscreen")
            command = selected(mode, [PROBE, "widget", font, output, text, "gray" if gray else "default"])
            if mode == "inactive":
                command = [str(PROBE), "widget", font, str(output), text, "gray" if gray else "default"]
                case_env["LD_LIBRARY_PATH"] = str(ROOT/"build/qt-native/qt-build/lib")
            result = call(command, case_env)
            output.with_suffix(".log").write_text(result.stderr)
            group[mode] = json.loads(output.with_suffix(".json").read_text())
        assert group["stock"]["imageHash"] == group["inactive"]["imageHash"], "Inactive Qt changed control"
        if family.startswith("Noto Sans:"):
            source = WORK/f"spillover-{family.split(':')[0].replace(' ', '-')}-linear.png"
            output = WORK/"widget-oracle.json"
            call([PROBE, "match", source, font, "1", "0", "0", "760", "70", text, "#000000", "#ffffff", output], dict(env, QT_QPA_PLATFORM="offscreen"))
            oracle = json.loads(output.read_text())
            assert all(g["mild/linear"]["matches"] for g in oracle.values()), "Matcher rejects validated raster control"
            assert any(not g["mild/encoded"]["matches"] for g in oracle.values()), "Matcher cannot reject opposite blend"
        records.append(dict(family=family, font=font, grayscale=gray, records=group,
                            masksUnchanged=group["inactive"]["masks"] == group["linear"]["masks"],
                            pixelsUnchanged=group["inactive"]["imageHash"] == group["linear"]["imageHash"]))
        print(f"Spillover {family} gray={gray}: pixels unchanged={records[-1]['pixelsUnchanged']}", flush=True)
    return records


def configure_plasma(env, font):
    config = Path(env["XDG_CONFIG_HOME"])
    descriptor = "Noto Sans,-1,15,5,50,0,0,0,0,0"
    colors = "\n".join(f"[Colors:{role}]\nBackgroundNormal=255,255,255\nForegroundNormal=0,0,0\n" for role in ("Window", "View", "Header", "Button"))
    (config/"kdeglobals").write_text(f"[General]\nfont={descriptor}\nmenuFont={descriptor}\n\n[WM]\nactiveFont={descriptor}\ninactiveFont={descriptor}\nactiveBackground=255,255,255\nactiveForeground=0,0,0\ninactiveBackground=255,255,255\ninactiveForeground=0,0,0\n{colors}")
    (config/"kwinrc").write_text("[org.kde.kdecoration2]\nlibrary=org.kde.breeze\n\n[Windows]\nPlacement=ZeroCornered\n\n[Compositing]\nAnimationSpeed=0\n")
    (config/"breezerc").write_text("[Windeco]\nDrawBackgroundGradient=false\nShadowSize=0\n")
    package = Path(env["XDG_DATA_HOME"])/"plasma/plasmoids/org.fontreal.textprobe"
    (package/"contents/ui").mkdir(parents=True)
    (package/"metadata.json").write_text(json.dumps({"KPlugin": {"Id": "org.fontreal.textprobe", "Name": "l m n o g W V w v", "Version": "1", "Icon": "preferences-desktop-font"}, "KPackageStructure": "Plasma/Applet", "X-Plasma-API-Minimum-Version": "6.0"}))
    shutil.copyfile(ROOT/"tests/KdeTextGrid.qml", package/"contents/ui/KdeTextGrid.qml")
    return package


def plasma_fixture(package, output):
    (package/"contents/ui/main.qml").write_text('''import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
PlasmoidItem {
    width: 760; height: 370
    Layout.minimumWidth: 760; Layout.minimumHeight: 370
    Layout.preferredWidth: 760; Layout.preferredHeight: 370
    preferredRepresentation: fullRepresentation
    fullRepresentation: KdeTextGrid {
        id: sample
        Timer {
            interval: 1800; running: true
            onTriggered: {
                console.info("FONTREAL_PLASMA " + JSON.stringify(sample.describe()))
                sample.grabToImage(function(result) { result.saveToFile("OUTPUT/plasma.png") })
            }
        }
    }
}
'''.replace("OUTPUT", str(output)))


def nested_checks(env, font):
    records = []
    for mode, scale, override in (("stock", 1, False), ("linear", 1, False), ("encoded", 1, False),
                                   ("linear-none", 1, False), ("linear", 1.25, False), ("linear", 1.25, True)):
        label = f"nested-{mode}-{scale}-{'native' if override else 'default'}"
        output = WORK/label
        output.mkdir(exist_ok=True)
        for filename in ("screen.png", "plasma.png", "title.json", "plasma.json", "composite.json", "plasma-final.json"):
            (output/filename).unlink(missing_ok=True)
        state = Path(env["XDG_RUNTIME_DIR"]).parent/f"n{len(records)}"
        state.mkdir()
        # A fresh configuration prevents KWin's saved output scale overriding the next CLI scale.
        case_env = private_environment(state)
        case_env.update(DISPLAY=env["DISPLAY"], LD_DEBUG="libs", KWIN_FORCE_OWN_QPA="1")
        package = configure_plasma(case_env, font)
        plasma_fixture(package, output)
        case_env.pop("QT_QPA_PLATFORM", None)
        case_env.pop("QT_QUICK_BACKEND", None)
        if override:
            case_env["QT_QUICK_DEFAULT_TEXT_RENDER_TYPE"] = "nativerendering"
        # Explicit loader leaves the installed cap_sys_nice binary untouched and permits private libraries.
        command = selected(mode, ["/lib64/ld-linux-x86-64.so.2", "/usr/bin/kwin_wayland", "--x11-display", env["DISPLAY"], "--width", "1100", "--height", "740", "--scale", str(scale),
                                  "--socket", "fontreal-test", "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities"])
        with (output/"kwin.log").open("w") as log:
            kwin = subprocess.Popen([str(x) for x in command], env=case_env, stdout=log, stderr=log)
            try:
                socket = Path(case_env["XDG_RUNTIME_DIR"])/"fontreal-test"
                deadline = time.monotonic()+15
                while not socket.exists() and kwin.poll() is None and time.monotonic()<deadline:
                    time.sleep(.05)
                assert socket.exists() and kwin.poll() is None, (output/"kwin.log").read_text()
                # KWin disables /proc maps access. The loader records its own resolved library.
                gui = re.findall(rf"{kwin.pid}:\s+calling init: (\S*/libQt6Gui\.so\.\S+)", (output/"kwin.log").read_text())[-1]
                assert ("qt-native/qt-build/lib" in gui) == (mode != "stock")
                client_env = dict(case_env, WAYLAND_DISPLAY="fontreal-test", QT_QPA_PLATFORM="wayland")
                client_env.pop("LD_DEBUG", None)
                call(["kscreen-doctor", f"output.X11-0.scale.{scale}"], client_env)
                display_state = json.loads(call(["kscreen-doctor", "-j"], client_env).stdout)
                assert display_state["outputs"][0]["scale"] == scale, display_state
                (output/"outputs.json").write_text(json.dumps(display_state, indent=2))
                with (output/"plasma.log").open("w") as client_log:
                    client = subprocess.Popen([str(x) for x in selected(mode, ["plasmawindowed", "org.fontreal.textprobe"])],
                                              env=client_env, stdout=client_log, stderr=client_log)
                    try:
                        time.sleep(3)
                        assert client.poll() is None, (output/"plasma.log").read_text()
                        client_maps = Path(f"/proc/{client.pid}/maps").read_text()
                        client_gui = next(line[line.index('/'):] for line in client_maps.splitlines() if "/libQt6Gui.so." in line)
                        assert ("qt-native/qt-build/lib" in client_gui) == (mode != "stock")
                        call([PROBE, "root", output/"screen.png"], dict(env, QT_QPA_PLATFORM="xcb"))
                        call([PROBE, "match", output/"screen.png", font, str(scale), "0", "0", "1100", "40", "lmnogWVwv", "#000000", "#ffffff", output/"title.json"], dict(env, QT_QPA_PLATFORM="offscreen"))
                        call([PROBE, "grid", output/"plasma.png", font, str(scale), output/"plasma.json"], dict(env, QT_QPA_PLATFORM="offscreen"))
                        call([PROBE, "composite", output/"screen.png", output/"plasma.png", output/"composite.json"], dict(env, QT_QPA_PLATFORM="offscreen"))
                        composite = json.loads((output/"composite.json").read_text())
                        call([PROBE, "grid", output/"screen.png", font, str(scale), output/"plasma-final.json", str(composite["x"]), str(composite["y"])], dict(env, QT_QPA_PLATFORM="offscreen"))
                        metadata = json.loads(re.findall(r"FONTREAL_PLASMA (\{.*\})", (output/"plasma.log").read_text())[-1])
                        # Wayland's integer screen scale can differ from the window's fractional buffer scale.
                        assert len(metadata["items"]) == 54
                        assert all(item["family"] == "Noto Sans" and item["pixels"] == 15 for item in metadata["items"])
                        record = dict(label=label, selection=mode, scale=scale, nativeOverride=override, kwinGui=gui, plasmaGui=client_gui,
                                      title=json.loads((output/"title.json").read_text()), plasma=json.loads((output/"plasma.json").read_text()),
                                      metadata=metadata, composite=composite, plasmaFinal=json.loads((output/"plasma-final.json").read_text()))
                        record["outputScale"] = display_state["outputs"][0]["scale"]
                        records.append(record)
                    finally:
                        stop(client)
            finally:
                stop(kwin)
                # KWin owns the socket and removes it during shutdown.
                assert not socket.exists(), "Nested KWin socket survived shutdown"
        print(f"Captured {label}", flush=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside-bus", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--only", choices=("quick", "nested", "spillover", "all"), default="all")
    args = parser.parse_args()
    assert PROBE.exists(), "Build qt-kde-probe first"
    WORK.mkdir(exist_ok=True)
    if not args.inside_bus:
        before = snapshot()
        host_kwin = call(["pgrep", "-x", "kwin_wayland"], os.environ).stdout.split()
        with tempfile.TemporaryDirectory(prefix="session-", dir=WORK) as state:
            state_path = Path(state)
            with display(private_environment(state_path), state_path) as env:
                # This bus has no service directories, so it cannot activate desktop helpers.
                bus_config = state_path/"bus.conf"
                bus_config.write_text(f'''<busconfig><type>session</type><listen>unix:tmpdir={env['XDG_RUNTIME_DIR']}</listen>
<auth>EXTERNAL</auth><policy context="default"><allow user="{os.getuid()}"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>''')
                with (WORK/"session-run.log").open("w") as log:
                    result = subprocess.run(["dbus-run-session", "--config-file", str(bus_config), "--", sys.executable, str(Path(__file__).resolve()), "--inside-bus", "--only", args.only],
                                            env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
                print((WORK/"session-run.log").read_text(), end="", flush=True)
                result.check_returncode()
        assert not state_path.exists()
        assert before == snapshot(), "Host configuration or font changed"
        assert all(Path(f"/proc/{pid}/comm").read_text().strip() == "kwin_wayland" for pid in host_kwin)
        print(f"Completed {args.only}; host configuration and compositor preserved.", flush=True)
        return
    env = os.environ.copy()
    font = call(["fc-match", "-f", "%{file}", "Noto Sans:style=Regular"], env).stdout
    report = {}
    if args.only in ("quick", "all"):
        report["quick"] = quick_checks(env, font)
    if args.only in ("spillover", "all"):
        report["spillover"] = spillover_checks(env)
    if args.only in ("nested", "all"):
        report["nested"] = nested_checks(env, font)
    report["referenceFont"] = dict(path=font, sha256=hashlib.sha256(Path(font).read_bytes()).hexdigest())
    (WORK/f"report-{args.only}.json").write_text(json.dumps(report, indent=2))
    print(f"Diagnostic collection complete. Rendering mismatches remain in {WORK}/report-{args.only}.json", flush=True)


if __name__ == "__main__":
    main()
