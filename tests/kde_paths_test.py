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
PRIVATE_LIBS = [ROOT/"build/qt-native/declarative-build/lib", ROOT/"build/qt-native/qt-build/lib"]


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
                 "LD_PRELOAD", "FONTREAL_RENDERING", "FONTREAL_BLEND", "FONTREAL_CONTRAST", "FONTREAL_FITTING", "QT_QUICK_DEFAULT_TEXT_RENDER_TYPE"):
        env.pop(name, None)
    for role in ("CONFIG", "CACHE", "DATA", "STATE", "RUNTIME"):
        path = directory/role.lower()
        path.mkdir(mode=0o700)
        env[f"XDG_{role}_HOME" if role != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
    env.update(QT_QPA_PLATFORM="xcb", QT_QPA_PLATFORMTHEME="kde", LIBGL_ALWAYS_SOFTWARE="1",
               QSG_INFO="1", QSG_RENDER_LOOP="basic", QSG_RHI_BACKEND="opengl", QT_NO_XDG_DESKTOP_PORTAL="1", FONTREAL_TRACE_QUICK="1")
    env["QML_IMPORT_PATH"] = call(["qtpaths6", "--query", "QT_INSTALL_QML"], env).stdout.strip()
    env["QT_PLUGIN_PATH"] = call(["qtpaths6", "--query", "QT_INSTALL_PLUGINS"], env).stdout.strip()
    return env


@contextlib.contextmanager
def display(env, directory, hardware=False):
    if hardware:
        env = dict(env, DISPLAY=os.environ["DISPLAY"])
        env.pop("LIBGL_ALWAYS_SOFTWARE",None)
        yield env
        return
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
        ("opengl", "stock-inherited", 1, 0, False),
        ("opengl", "inactive", 1, 0, False),
        ("opengl", "linear", 1, 0, False),
        ("opengl", "encoded", 1, 0, False),
        ("opengl", "linear-none", 1, 0, False),
        ("opengl", "linear", 1, .5, False),
        ("opengl", "linear", 1.25, 0, False),
        ("opengl", "encoded", 1.25, 0, False),
        ("opengl", "linear-none", 1.25, 0, False),
        ("opengl", "linear", 1.25, .5, False),
        ("opengl", "linear", 1.25, 0, True),
        ("opengl-hidden", "linear", 1, 0, False),
        ("opengl-hidden", "encoded", 1, 0, False),
        ("software", "linear", 1, 0, False),
        ("software", "encoded", 1, 0, False),
        ("software", "linear", 1.25, 0, True),
    ):
        label = f"quick-{backend}-{mode}-{scale}-{phase}-{'native' if override else 'default'}"
        output = WORK/label
        output.mkdir(exist_ok=True)
        for filename in ("result.json", *(f"frame-{i}.png" for i in range(5))):
            (output/filename).unlink(missing_ok=True)
        case_env = dict(env, QT_SCALE_FACTOR=str(scale), FONTREAL_TRACE_QUICK="1")
        if backend == "software":
            case_env["QT_QUICK_BACKEND"] = "software"
        else:
            case_env.pop("QT_QUICK_BACKEND", None)
        if override:
            case_env["QT_QUICK_DEFAULT_TEXT_RENDER_TYPE"] = "nativerendering"
        entry = "quick-hidden" if backend == "opengl-hidden" else "quick"
        command = selected(mode, [PROBE, entry, font, output, str(phase)])
        if mode in ("inactive", "stock-inherited"):
            case_env["LD_LIBRARY_PATH"] = ":".join(map(str,PRIVATE_LIBS))
            if mode == "inactive":
                command = [PROBE, "quick", font, output, str(phase)]
            else:
                case_env.update(FONTREAL_RENDERING="1", FONTREAL_BLEND="linear", FONTREAL_CONTRAST="mild")
                command = selected("stock", [PROBE, "quick", font, output, str(phase)])
        result = call(command, case_env)
        (output/"runtime.log").write_text(result.stderr)
        record = json.loads((output/"result.json").read_text())
        if backend.startswith("opengl"):
            driver = re.search(r"OpenGL VENDOR: (.*)",result.stderr)
            assert driver, "Missing actual OpenGL driver identity"
            record["openGLDriver"] = driver[1]
        assert len(record["frames"]) == 5
        assert record["frames"][0]["hash"] == record["frames"][1]["hash"], "Cached repaint changed output"
        assert record["frames"][1]["hash"] != record["frames"][2]["hash"] != record["frames"][3]["hash"]
        assert record["scale"] == scale
        assert record["unexposed"] == (backend=="opengl-hidden")
        private = mode not in ("stock", "stock-inherited")
        assert ("qt-native/qt-build/lib" in record["qtGui"]) == private
        assert ("qt-native/declarative-build/lib" in record["qtQuick"]) == private
        for frame in record["frames"]:
            assert {g["cell"] for g in frame["cells"]} == {f"cell/{r}/{c}" for r in range(6) for c in range(9)}
            if backend.startswith("opengl") and mode in ("linear", "encoded", "linear-none"):
                expected = "none/linear" if mode == "linear-none" else f"mild/{mode}"
                assert all(g["hypotheses"][expected]["matches"] for g in frame["cells"]), (label,frame["frame"],[(g["cell"],g["hypotheses"][expected]) for g in frame["cells"] if not g["hypotheses"][expected]["matches"]])
                assert any(not g["hypotheses"][expected.replace("linear","encoded") if "linear" in expected else "mild/linear"]["matches"] for g in frame["cells"])
                assert all(g["hypotheses"][expected]["x"] == g["expectedX"] for g in frame["cells"] if g["path"]==0), (label,"Placement changed")
        if backend.startswith("opengl") and mode in ("linear", "encoded", "linear-none"):
            assert re.search(r"FONTREAL_SELECT font=Noto Sans requested=0 effective=1 eligible=1 glyphs=1",result.stderr), "Default selection owner did not select native glyphs"
            assert "FONTREAL_TARGET eligible=1 linear=" + ("0" if mode=="encoded" else "1") in result.stderr
        record.update(label=label, backend=backend, selection=mode, nativeOverride=override)
        records.append(record)
        print(f"Captured {label}: API={record['graphicsApi']}", flush=True)
    baseline = next(r for r in records if r["selection"]=="stock")
    for mode in ("stock-inherited", "inactive"):
        other = next(r for r in records if r["selection"]==mode)
        assert [f["cellHash"] for f in other["frames"]] == [f["cellHash"] for f in baseline["frames"]], "Stock/inactive controlled pixels changed"
        if env.get("LIBGL_ALWAYS_SOFTWARE") == "1":
            assert [f["hash"] for f in other["frames"]] == [f["hash"] for f in baseline["frames"]]
        else:
            # Separate Intel stock launches vary by one value in annotation LCD edges.
            for frame in range(5):
                output=WORK/f"stock-{mode}-frame-{frame}.json"
                call([PROBE,"composite",WORK/baseline["label"]/f"frame-{frame}.png",WORK/other["label"]/f"frame-{frame}.png",output],env)
                assert json.loads(output.read_text())["matches"], "Stock/inactive annotations changed beyond GPU rounding"
    for scale in (1,1.25):
        pair = [next(r for r in records if r["backend"]=="opengl" and r["selection"]=="linear" and r["scale"]==scale and r["phase"]==phase and not r["nativeOverride"]) for phase in (0,.5)]
        for left,right in zip(pair[0]["frames"][0]["cells"],pair[1]["frames"][0]["cells"],strict=True):
            if left["path"]==0:
                assert left["hypotheses"]["mild/linear"]["y"] == right["hypotheses"]["mild/linear"]["y"]
    return records


def spillover_checks(env):
    records = []
    for family, text, gray in (("Noto Sans:style=Regular", "lmnogWVwv", False), ("Nimbus Sans:style=Regular", "lmnogWVwv", False),
                               ("Nimbus Sans:style=Regular", "lmnogWVwv", True), ("Noto Color Emoji", "😀", False)):
        font = call(["fc-match", "-f", "%{file}", family], env).stdout
        group = {}
        for mode in ("stock", "inactive", "linear", "encoded"):
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
        if not family.startswith("Noto Sans:"):
            for mode in ("linear", "encoded"):
                assert group[mode]["masks"] == group["inactive"]["masks"], "Noneligible masks changed"
                assert group[mode]["imageHash"] == group["inactive"]["imageHash"], "Noneligible pixels changed"
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
    fonts = [call(["fc-match", "-f", "%{file}", family], env).stdout for family in
             ("Noto Sans:style=Regular", "Nimbus Sans:style=Regular", "Noto Color Emoji")]
    for entry in ("ordinary", "static"):
        for order in ("tt-first", "cff-first"):
            group = {}
            for mode in ("stock", "inactive", "linear", "encoded"):
                output = WORK/f"profile-{entry}-{order}-{mode}"
                case_env = dict(env, QT_QPA_PLATFORM="offscreen")
                command = selected(mode, [PROBE, "profile", *fonts, output, entry, order])
                if mode == "inactive":
                    command = [PROBE, "profile", *fonts, output, entry, order]
                    case_env["LD_LIBRARY_PATH"] = str(ROOT/"build/qt-native/qt-build/lib")
                call(command, case_env)
                group[mode] = json.loads(output.with_suffix(".json").read_text())
                assert group[mode]["colorGlyph"]
                assert ("qt-native/qt-build/lib" in group[mode]["qtGui"]) == (mode != "stock")
            assert group["stock"]["regions"] == group["inactive"]["regions"], "Inactive mixed output changed"
            for mode in ("linear", "encoded"):
                for ordinary, enabled in zip(group["stock"]["regions"], group[mode]["regions"], strict=True):
                    assert (ordinary["row"], ordinary["column"], ordinary["role"]) == (enabled["row"], enabled["column"], enabled["role"])
                    if enabled["role"]:
                        assert ordinary["hash"] == enabled["hash"], "Mixed CFF/color output changed"
                    else:
                        assert all(g[f"mild/{mode}"]["matches"] for g in enabled["glyphs"].values()), "Mixed eligible blend changed"
                        assert any(not g[f"mild/{'encoded' if mode=='linear' else 'linear'}"]["matches"] for g in enabled["glyphs"].values()), "Mixed fixture cannot distinguish blend"
            records.append(dict(entry=entry, order=order, records=group))
            print(f"Mixed profile scope: {entry}, {order}", flush=True)
    return records


def gpu_checks(env, font):
    fonts = [font, *(call(["fc-match", "-f", "%{file}", family], env).stdout for family in
                    ("Nimbus Sans:style=Regular", "Noto Color Emoji"))]
    records = []
    def same_region(a,b,order,mode):
        assert (a["id"],a["role"]) == (b["id"],b["role"])
        assert a["ordinary"] == b["ordinary"] and a["windowOrdinary"] == b["windowOrdinary"], "Ordinary geometry changed"
        for key in ("text","windowText"):
            if env.get("LIBGL_ALWAYS_SOFTWARE") != "1" and a["role"]>=3:
                output=WORK/f"gpu-{order}-{mode}"/(b[key+"Image"]+".json")
                call([PROBE,"composite",WORK/f"gpu-{order}-stock"/a[key+"Image"],WORK/f"gpu-{order}-{mode}"/b[key+"Image"],output],env)
                assert json.loads(output.read_text())["matches"], "CFF Qt pixels changed beyond GPU rounding"
            else:
                assert a[key] == b[key], (order,mode,a["id"],"Preserved font pixels changed")
    for order in ("tt-first", "cff-first"):
        group = {}
        for mode in ("stock", "inactive", "linear", "encoded"):
            output = WORK/f"gpu-{order}-{mode}"
            output.mkdir(exist_ok=True)
            case_env = dict(env, FONTREAL_TRACE_QUICK="1")
            command = selected(mode,[PROBE,"gpu",*fonts,output,order])
            if mode == "inactive":
                command = [PROBE,"gpu",*fonts,output,order]
                case_env["LD_LIBRARY_PATH"] = ":".join(map(str,PRIVATE_LIBS))
            result = call(command,case_env)
            (output/"runtime.log").write_text(result.stderr)
            group[mode] = json.loads((output/"result.json").read_text())
            assert [f["frame"] for f in group[mode]["frames"]] == [0,1,2]
            assert group[mode]["graphicsApi"] == 3
            assert ("declarative-build/lib" in group[mode]["qtQuick"]) == (mode!="stock")
            assert group[mode]["frames"][0]["hash"] == group[mode]["frames"][1]["hash"]
            assert group[mode]["frames"][1]["hash"] != group[mode]["frames"][2]["hash"]
            if mode != "stock":
                assert re.search(r"FONTREAL_SELECT font=Nimbus Sans requested=0 effective=0 eligible=0",result.stderr), "CFF Qt/default selector changed"
        if env.get("LIBGL_ALWAYS_SOFTWARE") == "1":
            assert [f["hash"] for f in group["stock"]["frames"]] == [f["hash"] for f in group["inactive"]["frames"]]
        for a,b in zip(group["stock"]["frames"],group["inactive"]["frames"],strict=True):
            for ordinary,inactive in zip(a["regions"],b["regions"],strict=True): same_region(ordinary,inactive,order,"inactive")
        for mode in ("linear", "encoded"):
            for baseline,frame in zip(group["stock"]["frames"],group[mode]["frames"],strict=True):
                assert {r["id"] for r in frame["regions"]} == {f"region/{row}/{col}" for row in range(2) for col in range(7)}
                for ordinary,enabled in zip(baseline["regions"],frame["regions"],strict=True):
                    assert (ordinary["id"],ordinary["role"]) == (enabled["id"],enabled["role"])
                    assert ordinary["ordinary"] == enabled["ordinary"], (order,mode,enabled["id"],"Ordinary geometry changed")
                    assert ordinary["windowOrdinary"] == enabled["windowOrdinary"], (order,mode,enabled["id"],"Presented ordinary geometry changed")
                    if enabled["role"]:
                        same_region(ordinary,enabled,order,mode)
                    else:
                        for key in ("glyphs","windowGlyphs"):
                            assert all(g[f"mild/{mode}"]["matches"] for g in enabled[key].values()), (order,mode,enabled)
                            assert any(not g[f"mild/{'encoded' if mode=='linear' else 'linear'}"]["matches"] for g in enabled[key].values())
        records.append(dict(order=order,records=group))
        print(f"Mixed GPU colors, fonts, cached repaint and sampled layer: {order}",flush=True)
    for style in ("", "sunken"):
        output = WORK/("gpu-target-linear"+("-"+style if style else ""))
        output.mkdir(exist_ok=True)
        result = call(selected("linear",[PROBE,"target",font,output,*([style] if style else [])]),dict(env,FONTREAL_TRACE_QUICK="1"))
        (output/"runtime.log").write_text(result.stderr)
        target = json.loads((output/"result.json").read_text())
        assert [f["frame"] for f in target["frames"]] == [0,1,2]
        assert target["nonindexed"] and target["sunken"] == bool(style)
        assert target["frames"][0]["hash"] == target["frames"][2]["hash"] != target["frames"][1]["hash"]
        for frame in target["frames"]:
            expected = "mild/linear" if frame["compatible"] else "mild/encoded"
            assert set(frame["glyphs"]) == set("lmnogWVwv")
            assert all(g[expected]["matches"] for g in frame["glyphs"].values()), frame
            assert any(not g["mild/encoded" if frame["compatible"] else "mild/linear"]["matches"] for g in frame["glyphs"].values())
        assert "FONTREAL_TARGET eligible=1 linear=0" in result.stderr and "FONTREAL_TARGET eligible=1 linear=1" in result.stderr
        records.append(dict(target=target))
        print(f"GPU {style or 'normal'} compatible/external/compatible target and draw restoration passed",flush=True)
    return records


def configure_plasma(env, font):
    config = Path(env["XDG_CONFIG_HOME"])
    family = call(["fc-scan", "-f", "%{family[0]}", font], env).stdout.strip()
    assert family and "," not in family and "\n" not in family
    descriptor = family + ",-1,15,5,50,0,0,0,0,0"
    colors = "\n".join(f"[Colors:{role}]\nBackgroundNormal=255,255,255\nForegroundNormal=0,0,0\n" for role in ("Window", "View", "Header", "Button"))
    (config/"kdeglobals").write_text(f"[General]\nfont={descriptor}\nmenuFont={descriptor}\n\n[WM]\nactiveFont={descriptor}\ninactiveFont={descriptor}\nactiveBackground=255,255,255\nactiveForeground=0,0,0\ninactiveBackground=255,255,255\ninactiveForeground=0,0,0\n{colors}")
    (config/"kwinrc").write_text("[org.kde.kdecoration2]\nlibrary=org.kde.breeze\n\n[Windows]\nPlacement=ZeroCornered\n\n[Compositing]\nAnimationSpeed=0\n")
    (config/"breezerc").write_text("[Windeco]\nDrawBackgroundGradient=false\nShadowSize=0\n")
    package = Path(env["XDG_DATA_HOME"])/"plasma/plasmoids/org.fontreal.textprobe"
    (package/"contents/ui").mkdir(parents=True)
    (package/"metadata.json").write_text(json.dumps({"KPlugin": {"Id": "org.fontreal.textprobe", "Name": "l m n o g W V w v", "Version": "1", "Icon": "preferences-desktop-font"}, "KPackageStructure": "Plasma/Applet", "X-Plasma-API-Minimum-Version": "6.0"}))
    shutil.copyfile(ROOT/"tests/KdeTextGrid.qml", package/"contents/ui/KdeTextGrid.qml")
    grid = package/"contents/ui/KdeTextGrid.qml"
    grid.write_text(grid.read_text().replace('family: "Noto Sans"', 'family: ' + json.dumps(family)))
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
                                   ("linear-none", 1, False), ("linear", 1.25, False), ("encoded", 1.25, False), ("linear", 1.25, True)):
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
                        client_quick = next(line[line.index('/'):] for line in client_maps.splitlines() if "/libQt6Quick.so." in line)
                        assert ("qt-native/qt-build/lib" in client_gui) == (mode != "stock")
                        assert ("qt-native/declarative-build/lib" in client_quick) == (mode != "stock")
                        call([PROBE, "root", output/"screen.png"], dict(env, QT_QPA_PLATFORM="xcb"))
                        call([PROBE, "match", output/"screen.png", font, str(scale), "0", "0", "1100", "40", "lmnogWVwv", "#000000", "#ffffff", output/"title.json"], dict(env, QT_QPA_PLATFORM="offscreen"))
                        call([PROBE, "grid", output/"plasma.png", font, str(scale), output/"plasma.json"], dict(env, QT_QPA_PLATFORM="offscreen"))
                        call([PROBE, "composite", output/"screen.png", output/"plasma.png", output/"composite.json"], dict(env, QT_QPA_PLATFORM="offscreen"))
                        composite = json.loads((output/"composite.json").read_text())
                        call([PROBE, "grid", output/"screen.png", font, str(scale), output/"plasma-final.json", str(composite["x"]), str(composite["y"])], dict(env, QT_QPA_PLATFORM="offscreen"))
                        metadata = json.loads(re.findall(r"FONTREAL_PLASMA (\{.*\})", (output/"plasma.log").read_text())[-1])
                        # Wayland's integer screen scale can differ from the window's fractional buffer scale.
                        assert len(metadata["items"]) == 54
                        assert {item["cell"] for item in metadata["items"]} == {f"cell/{r}/{c}" for r in range(6) for c in range(9)}
                        assert all(item["family"] == "Noto Sans" and item["pixels"] == 15 for item in metadata["items"])
                        record = dict(label=label, selection=mode, scale=scale, nativeOverride=override, kwinGui=gui, plasmaGui=client_gui, plasmaQuick=client_quick,
                                      title=json.loads((output/"title.json").read_text()), plasma=json.loads((output/"plasma.json").read_text()),
                                      metadata=metadata, composite=composite, plasmaFinal=json.loads((output/"plasma-final.json").read_text()))
                        record["outputScale"] = display_state["outputs"][0]["scale"]
                        if mode != "stock":
                            expected = "none/linear" if mode == "linear-none" else f"mild/{mode}"
                            opposite = "mild/encoded" if mode == "linear" else "mild/linear"
                            assert all(g[expected]["matches"] for g in record["title"].values()), "Accepted KWin title changed"
                            assert any(not g[opposite]["matches"] for g in record["title"].values()), "Title does not discriminate treatment"
                            for captured in (record["plasma"],record["plasmaFinal"]):
                                assert {(g["path"],g["glyph"]) for g in captured["cells"]} == {(r,c) for r in range(6) for c in "lmnogWVwv"}
                                assert all(g["hypotheses"][expected]["matches"] for g in captured["cells"]), (label,"Actual Plasma selected blend differs",[(g["path"],g["glyph"],g["hypotheses"][expected]) for g in captured["cells"] if not g["hypotheses"][expected]["matches"]])
                                assert any(not g["hypotheses"][opposite]["matches"] for g in captured["cells"])
                            assert re.search(r"FONTREAL_SELECT font=Noto Sans requested=0 effective=1 eligible=1 glyphs=1",(output/"plasma.log").read_text())
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
    global WORK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hardware",action="store_true",help="Run Quick checks on the current X display and physical OpenGL driver")
    parser.add_argument("--inside-bus", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--only", choices=("quick", "nested", "spillover", "all"), default="all")
    args = parser.parse_args()
    if args.hardware:
        if args.only != "quick":
            parser.error("--hardware requires --only quick")
        WORK = ROOT/"build/kde-hardware"
    assert PROBE.exists(), "Build qt-kde-probe first"
    WORK.mkdir(exist_ok=True)
    if not args.inside_bus:
        before = snapshot()
        host_kwin = call(["pgrep", "-x", "kwin_wayland"], os.environ).stdout.split()
        with tempfile.TemporaryDirectory(prefix="session-", dir=WORK) as state:
            state_path = Path(state)
            with display(private_environment(state_path), state_path,args.hardware) as env:
                # This bus has no service directories, so it cannot activate desktop helpers.
                bus_config = state_path/"bus.conf"
                bus_config.write_text(f'''<busconfig><type>session</type><listen>unix:tmpdir={env['XDG_RUNTIME_DIR']}</listen>
<auth>EXTERNAL</auth><policy context="default"><allow user="{os.getuid()}"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>''')
                with (WORK/"session-run.log").open("w") as log:
                    result = subprocess.run(["dbus-run-session", "--config-file", str(bus_config), "--", sys.executable, str(Path(__file__).resolve()), "--inside-bus", "--only", args.only, *(["--hardware"] if args.hardware else [])],
                                            env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
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
        report["gpu"] = gpu_checks(env, font)
        if args.hardware:
            assert all(not re.search(r"llvmpipe|softpipe|software",r["openGLDriver"],re.I) for r in report["quick"] if r["backend"].startswith("opengl")), "Hardware run used a software OpenGL driver"
    if args.only in ("spillover", "all"):
        report["spillover"] = spillover_checks(env)
    if args.only in ("nested", "all"):
        report["nested"] = nested_checks(env, font)
    report["referenceFont"] = dict(path=font, sha256=hashlib.sha256(Path(font).read_bytes()).hexdigest())
    (WORK/f"report-{args.only}.json").write_text(json.dumps(report, indent=2))
    print(f"Rendering checks complete: {WORK}/report-{args.only}.json", flush=True)


if __name__ == "__main__":
    main()
