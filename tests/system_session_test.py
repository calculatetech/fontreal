#!/usr/bin/env python3
"""Exercise real Plasma logins in an explicitly prepared disposable VM."""
import argparse
import configparser
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import system_package_test as package

build = package.build
ROOT = build.ROOT
PROBE = ROOT / "build/qt-kde-probe"


def call(args, **kwargs):
    return package.kde.call(args, kwargs.pop("env", None), timeout=kwargs.pop("timeout", 90), **kwargs)


def wait_for(predicate, description, seconds=45):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.2)
    raise AssertionError("Timed out: " + description)


def pid(name):
    result = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", name], text=True, stdout=subprocess.PIPE)
    return int(result.stdout.split()[0]) if result.returncode == 0 else None


def session_environment():
    values = dict(line.split("=", 1) for line in call(["systemctl", "--user", "show-environment"]).stdout.splitlines())
    return {key: values.get(key, "") for key in ("FONTREAL_RENDERING", "FONTREAL_BLEND", "FONTREAL_CONTRAST", "FONTREAL_FITTING")}


def tools_environment():
    return dict(os.environ, XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}", WAYLAND_DISPLAY="wayland-0",
                DBUS_SESSION_BUS_ADDRESS=f"unix:path=/run/user/{os.getuid()}/bus", QT_QPA_PLATFORM="wayland")


def qdbus(*args):
    return call(["qdbus6", *args], env=tools_environment()).stdout.strip()


def font_state(fonts):
    state = {str(path): build.sha(path) for path in fonts}
    fragment = Path.home() / ".config/fontconfig/conf.d/99-fontreal-test.conf"
    state[str(fragment)] = build.sha(fragment)
    for path in (Path.home() / ".config/kdeglobals", Path.home() / ".local/share/konsole/FontrealTest.profile",
                 Path.home() / ".local/share/konsole/FontrealCff.profile"):
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        parser.optionxform = str
        parser.read(path)
        state[str(path)] = {f"{section}/{key}": value for section in parser.sections()
                            for key, value in parser[section].items() if "font" in key.lower()}
    return state


def process_record(process):
    code = ("import json;from pathlib import Path;"
            f"p=Path('/proc/{process}');"
            "print(json.dumps(dict(environment=[v.decode() for v in (p/'environ').read_bytes().split(b'\\0') "
            "if v.split(b'=',1)[0] in (b'FONTREAL_RENDERING',b'FONTREAL_BLEND',b'FONTREAL_CONTRAST',b'FONTREAL_FITTING',"
            "b'LD_LIBRARY_PATH',b'LD_PRELOAD',b'QT_QUICK_DEFAULT_TEXT_RENDER_TYPE')],"
            "softwareForced=b'LIBGL_ALWAYS_SOFTWARE=1' in (p/'environ').read_bytes().split(b'\\0'),"
            "libraries=sorted(set(line[line.index('/'):] for line in (p/'maps').read_text().splitlines() "
            "if '/libQt6Gui.so.' in line or '/libQt6Quick.so.' in line)),"
            "freetypeLibraries=sorted(set(line[line.index('/'):] for line in (p/'maps').read_text().splitlines() "
            "if '/libfreetype.so.' in line)))))")
    record = json.loads(call(["sudo", "python3", "-c", code]).stdout)
    assert record["libraries"] and all(path.startswith("/usr/lib/") for path in record["libraries"]), record
    reference = str(Path(os.environ["FONTREAL_TEST_REFERENCE_FREETYPE"]).resolve())
    actual_freetype = [path for path in record["freetypeLibraries"] if path != reference]
    assert actual_freetype and all(path.startswith("/usr/lib/") for path in actual_freetype), record
    assert not any(value.startswith(("LD_LIBRARY_PATH=", "LD_PRELOAD=", "QT_QUICK_DEFAULT_TEXT_RENDER_TYPE="))
                   for value in record["environment"]), record
    return record


def desktop_exec(args):
    return " ".join('"' + str(arg).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'
                    for arg in args)


def fixture(reports, font, terminal_font):
    config = Path.home() / ".config"
    data = Path.home() / ".local/share"
    # These are initial test fixtures, before the preservation snapshot.
    env = dict(XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(data))
    old = data / "plasma/plasmoids/org.fontreal.textprobe"
    if old.exists():
        assert json.loads((old / "metadata.json").read_text())["KPlugin"]["Id"] == "org.fontreal.textprobe"
        shutil.rmtree(old)
    plasmoid = package.kde.configure_plasma(env, font)
    # The opaque client comparison needs square client corners.
    with (config / "breezerc").open("a") as stream:
        stream.write("\n[Common]\nRoundedCorners=false\n")
    package.kde.plasma_fixture(plasmoid, reports / "current")
    main = plasmoid / "contents/ui/main.qml"
    main.write_text(main.read_text().replace("interval: 1800; running: true", "interval: 1800; running: true; repeat: true"))
    colors = configparser.ConfigParser(interpolation=None)
    colors.optionxform = str
    colors.read("/usr/share/color-schemes/BreezeLight.colors")
    for section in ("Colors:Window", "Colors:View", "Colors:Header", "Colors:Button", "Colors:Header][Inactive"):
        if not colors.has_section(section):
            colors.add_section(section)
        colors[section].update(BackgroundNormal="255,255,255", ForegroundNormal="0,0,0")
    colors["General"]["Name"] = "FontrealTest"
    for key in ("activeBackground", "inactiveBackground"):
        colors["WM"][key] = "255,255,255"
    for key in ("activeForeground", "inactiveForeground"):
        colors["WM"][key] = "0,0,0"
    schemes = data / "color-schemes"
    schemes.mkdir(exist_ok=True)
    with (schemes / "FontrealTest.colors").open("w") as stream:
        colors.write(stream)
    call(["plasma-apply-colorscheme", "FontrealTest"], env=tools_environment())
    (config / "kscreenlockerrc").write_text("[Daemon]\nAutolock=false\n")
    test_hook = config / "plasma-workspace/env/fontreal-test.sh"
    test_hook.parent.mkdir(parents=True, exist_ok=True)
    reference = Path(os.environ["FONTREAL_TEST_REFERENCE_FREETYPE"]).resolve()
    assert reference.is_file()
    test_hook.write_text("export QT_LOGGING_RULES='kwin_scripting.debug=true'\n" +
                         "export FONTREAL_TEST_REFERENCE_FREETYPE=" + shlex.quote(str(reference)) + "\n" +
                         "export FONTREAL_TEST_SELECTED_REFERENCE=" + shlex.quote(str(ROOT / "tests/selected_reference.py")) + "\n")
    fc = config / "fontconfig/conf.d/99-fontreal-test.conf"
    fc.parent.mkdir(parents=True, exist_ok=True)
    fc.write_text('''<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig><selectfont><rejectfont><pattern>
<patelt name="family"><string>Nimbus Mono PS</string></patelt>
<patelt name="fontformat"><string>Type 1</string></patelt>
</pattern></rejectfont></selectfont><match target="font">
<edit name="antialias" mode="assign"><bool>false</bool></edit>
<edit name="hinting" mode="assign"><bool>false</bool></edit>
<edit name="hintstyle" mode="assign"><const>hintnone</const></edit>
<edit name="rgba" mode="assign"><const>rgb</const></edit>
</match></fontconfig>''')
    profiles = data / "konsole"
    profiles.mkdir(parents=True, exist_ok=True)
    (profiles / "FontrealTest.profile").write_text(
        "[General]\nName=FontrealTest\nParent=FALLBACK/\n"
        "[Appearance]\nFont=Inconsolata Nerd Font,-1,15,5,50,0,0,0,0,0\n"
        "[Terminal Features]\nBlinkingCursorEnabled=false\n")
    (profiles / "FontrealCff.profile").write_text(
        "[General]\nName=FontrealCff\nParent=FALLBACK/\n"
        "[Appearance]\nFont=Nimbus Mono PS,-1,15,5,50,0,0,0,0,0\n"
        "[Terminal Features]\nBlinkingCursorEnabled=false\n")
    assert Path(call(["fc-match", "-f", "%{file}", "Inconsolata Nerd Font"]).stdout).resolve() == terminal_font.resolve()
    autostart = config / "autostart"
    autostart.mkdir(exist_ok=True)
    current = reports / "current"
    current.mkdir()
    for kind, args in (("widget", ["client", font, current / "normal-widget"]),
                       ("quick", ["quick", font, current / "normal-quick", "0"])):
        if kind == "quick":
            (current / "normal-quick").mkdir()
        command = desktop_exec(["env", "FONTREAL_TEST_HOLD=1", PROBE, *args])
        (autostart / f"fontreal-{kind}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName=Fontreal {kind} check\nExec={command}\n")
    services = data / "dbus-1/services"
    services.mkdir(parents=True, exist_ok=True)
    for kind, args in (("Widget", ["client", font, current / "dbus-widget"]),
                       ("Quick", ["quick", font, current / "dbus-quick", "0"])):
        if kind == "Quick":
            (current / "dbus-quick").mkdir()
        name = "org.fontreal." + kind + "Probe"
        command = shlex.join(["/usr/bin/env", "FONTREAL_TEST_HOLD=1", "FONTREAL_TEST_DBUS_NAME=" + name,
                              str(PROBE), *map(str, args)])
        (services / (name + ".service")).write_text(f"[D-BUS Service]\nName={name}\nExec={command}\n")
    return plasmoid


def new_login(enabled):
    jobs = []
    units = set()
    started = time.monotonic()
    def settled_jobs():
        output = call(["systemctl", "--user", "list-jobs", "--no-legend", "--no-pager", "--plain"],
                      env=dict(tools_environment(), LC_ALL="C")).stdout
        current = []
        for line in output.splitlines():
            fields = line.split()
            assert len(fields) == 4 and fields[0].isdecimal(), output
            current.append(dict(id=int(fields[0]), unit=fields[1], type=fields[2], state=fields[3]))
            units.add(fields[1])
        if not jobs or jobs[-1]["jobs"] != current:
            jobs.append(dict(seconds=time.monotonic() - started, jobs=current))
            print("Native user jobs: " + json.dumps(current), flush=True)
        return not current
    # Native D-Bus activation can take 120 seconds. Let the complete real job
    # collection terminate before the single controlled logout; do not retry it.
    try:
        wait_for(settled_jobs, "terminal native user-manager jobs before logout", seconds=150)
    except AssertionError as error:
        raise AssertionError("Native startup/stop jobs did not terminate: " + json.dumps(jobs)) from error
    outcomes = call(["systemctl", "--user", "show", *sorted(units), "-p", "Id", "-p", "ActiveState",
                     "-p", "SubState", "-p", "Result"]).stdout if units else ""
    print("Native user job outcomes: " + json.dumps(outcomes), flush=True)
    if enabled is not None:
        call(["fontreal-session", "enable" if enabled else "disable"])
    manager = pid("systemd")
    previous = pid("kwin_wayland")
    previous_plasma = pid("plasmashell")
    call(["sudo", "systemctl", "restart", "sddm"])
    wait_for(lambda: pid("kwin_wayland") and pid("kwin_wayland") != previous and
             pid("plasmashell") and pid("plasmashell") != previous_plasma, "new complete Plasma session")
    wait_for(lambda: ".evaluateScript(" in subprocess.run(
        ["qdbus6", "org.kde.plasmashell", "/PlasmaShell"], env=tools_environment(),
        capture_output=True, text=True, timeout=5).stdout, "Plasma shell interface")
    assert pid("systemd") == manager, "The user manager must survive this logout test."
    call(["systemctl", "--user", "stop", "plasma-powerdevil.service"])
    call(["kscreen-doctor", "--dpms", "on"], env=tools_environment())
    wait_for(lambda: qdbus("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript",
                          "print(desktops().length)") == "1", "Plasma desktop containment")
    qdbus("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript",
          'var d=desktops()[0]; if(d.widgets("org.fontreal.textprobe").length==0) '
          'd.addWidget("org.fontreal.textprobe",0,0,760,370);')
    return dict(manager=manager, environment=session_environment(),
                native_job_readiness=dict(boundSeconds=150, observations=jobs, terminalUnits=outcomes),
                kwin=process_record(pid("kwin_wayland")), plasma=process_record(pid("plasmashell")))


def scale(value):
    call(["kscreen-doctor", f"output.Virtual-1.scale.{value}"], env=tools_environment())
    record = json.loads(call(["kscreen-doctor", "-j"], env=tools_environment()).stdout)
    assert len(record["outputs"]) == 1 and record["outputs"][0]["scale"] == value, record
    return record


def screenshot(path):
    call(["spectacle", "-b", "-n", "-f", "-o", path], env=tools_environment())
    assert path.is_file()


def read_capture(path, factor):
    def ready():
        try:
            record = json.loads(path.read_text())
            return record if record["scale"] == factor and Path(f"/proc/{record['pid']}").exists() else None
        except (OSError, ValueError, KeyError):
            return None
    return wait_for(ready, "complete current capture: " + str(path))


def kwin_script(directory, source):
    name = "fontreal-test-" + str(time.monotonic_ns())
    path = directory / "window.js"
    path.write_text("var reports=[];" + source + f'; console.warn("{name} data "+JSON.stringify(reports)); console.warn("{name} done");')
    identifier = qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript", path, name)
    qdbus("org.kde.KWin", "/Scripting/Script" + identifier, "org.kde.kwin.Script.run")
    def completed():
        result = subprocess.run(["journalctl", "--user", "-u", "plasma-kwin_wayland.service", "--grep", name, "--no-pager"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode not in (0, 1):
            result.check_returncode()
        log = result.stdout
        return log if name + " done" in log else None
    log = wait_for(completed, "KWin script completion")
    qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", name)
    return json.loads(re.findall(re.escape(name) + r" data (\[.*\])", log)[-1])


def plasma_capture(directory, current, font, factor):
    kwin_script(directory, "for (var w of workspace.windowList()) { if (w.normalWindow) w.minimized=true; }")
    geometry = qdbus("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript",
                     'for (var w of desktops()[0].widgets()) { if(w.type=="org.fontreal.textprobe") print(JSON.stringify(w.geometry)); }')
    rect = json.loads(geometry)
    source = current / "plasma.png"
    after = time.time()
    wait_for(lambda: source.exists() and source.stat().st_mtime > after and source.read_bytes().endswith(b"IEND\xaeB`\x82"),
             "fresh complete Plasma capture")
    shutil.copyfile(source, directory / "plasma.png")
    screenshot(directory / "desktop.png")
    env = dict(tools_environment(), QT_QPA_PLATFORM="offscreen")
    call([PROBE, "grid", directory / "plasma.png", font, factor, directory / "plasma-grid.json", "0", "0"], env=env)
    call([PROBE, "grid", directory / "desktop.png", font, factor, directory / "desktop-grid.json",
          round(rect["x"] * factor), round(rect["y"] * factor)], env=env)
    records = [json.loads((directory / name).read_text()) for name in ("plasma-grid.json", "desktop-grid.json")]
    assert all({(c["path"], c["glyph"]) for c in r["cells"]} == {(row, letter) for row in range(6) for letter in "lmnogWVwv"}
               for r in records)
    call([PROBE, "crop", directory / "desktop.png", round(rect["x"] * factor), round(rect["y"] * factor),
          round(rect["width"] * factor), round(rect["height"] * factor), directory / "plasma-presented.png"], env=env)
    # An item grab has a local origin. Its actual desktop placement can have
    # another pixel phase. The independent glyph oracle checks each image.
    return dict(geometry=rect, buffers=records, presented_sha256=build.sha(directory / "plasma-presented.png"))


def window_capture(directory, process, buffer, font, factor, title=False):
    geometry = kwin_script(directory,
        f"for (var w of workspace.windowList()) {{ if (w.pid=={process}) {{ "
        "w.minimized=false; w.frameGeometry={x:0,y:0,width:w.frameGeometry.width,height:w.frameGeometry.height}; "
        "workspace.activeWindow=w; reports.push({frame:w.frameGeometry,client:w.clientGeometry}); } }")
    assert len(geometry) == 1, geometry
    time.sleep(.7)
    screenshot(directory / "window.png")
    env = dict(tools_environment(), QT_QPA_PLATFORM="offscreen")
    frame = geometry[0]["frame"]
    client = geometry[0]["client"]
    call([PROBE, "crop", directory / "window.png", round(client["x"] * factor), round(client["y"] * factor),
          round(client["width"] * factor), round(client["height"] * factor), directory / "client.png"], env=env)
    # The whole opaque content must survive presentation without resampling.
    if buffer is not None:
        call([PROBE, "equal", buffer, directory / "client.png"], env=env)
    result = dict(geometry=geometry[0], client_sha256=build.sha(directory / "client.png"))
    if title:
        call([PROBE, "crop", directory / "window.png", round(frame["x"] * factor), round(frame["y"] * factor),
              round(frame["width"] * factor), round((client["y"] - frame["y"]) * factor), directory / "title.png"], env=env)
        call([PROBE, "match", directory / "title.png", font, factor, "0", "0", round(frame["width"] * factor),
              round((client["y"] - frame["y"]) * factor), "lmnogWVwv", "#000000", "#ffffff", directory / "title.json"], env=env)
        # The centered text fixture excludes transparent decoration corners.
        width = round(frame["width"] * factor)
        call([PROBE, "crop", directory / "title.png", width // 4, "0", width // 2,
              round((client["y"] - frame["y"]) * factor), directory / "title-text.png"], env=env)
        result.update(title=json.loads((directory / "title.json").read_text()), title_sha256=build.sha(directory / "title.png"),
                      title_text_sha256=build.sha(directory / "title-text.png"))
    return result


def actors(directory, current, font, factor, enabled, launch=True, expected_environment=None):
    records = {}
    for entry in ("normal", "dbus", "systemd"):
        if launch and entry == "dbus":
            for name in ("Widget", "Quick"):
                qdbus("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.StartServiceByName",
                      "org.fontreal." + name + "Probe", "0")
        elif launch and entry == "systemd":
            (current / "systemd-quick").mkdir(exist_ok=True)
            for kind, args in (("widget", ["client", font, current / "systemd-widget"]),
                               ("quick", ["quick", font, current / "systemd-quick", "0"])):
                call(["systemd-run", "--user", "--collect", "--unit=fontreal-" + kind,
                      "env", "FONTREAL_TEST_HOLD=1", PROBE, *args])
        group = {}
        for kind in ("widget", "quick"):
            source = current / (entry + "-" + kind)
            path = source.with_suffix(".json") if kind == "widget" else source / "result.json"
            record = read_capture(path, factor)
            group[kind] = dict(pixels=record, process=process_record(record["pid"]))
            expected_env = expected_environment if expected_environment is not None else [{
                "FONTREAL_RENDERING=" + ("1" if enabled else "0"),
                "FONTREAL_BLEND=" + ("encoded" if enabled else ""),
                "FONTREAL_CONTRAST=" + ("weighted" if enabled else ""),
                "FONTREAL_FITTING=" + ("native" if enabled else "")}]
            assert set(group[kind]["process"]["environment"]) in expected_env, group[kind]
            destination = directory / (entry + "-" + kind)
            destination.mkdir()
            if kind == "quick":
                assert record["graphicsApi"] == 3 and record["scale"] == factor and len(record["frames"]) == 5
                for frame in record["frames"]:
                    assert frame["scale"] == factor and abs(frame["imageWidth"] - 760 * factor) <= 1 and abs(frame["imageHeight"] - 370 * factor) <= 1, frame
                    assert {c["cell"] for c in frame["cells"]} == {f"cell/{r}/{c}" for r in range(6) for c in range(9)}
                    if enabled:
                        assert all(c["hypotheses"]["none/encoded"]["matches"] for c in frame["cells"]), frame
                        assert any(not c["hypotheses"]["none/linear"]["matches"] for c in frame["cells"])
                for image in source.glob("frame-*.png"):
                    shutil.copyfile(image, destination / image.name)
                buffer = destination / "frame-1.png"
            else:
                shutil.copyfile(source.with_suffix(".png"), destination / "widget.png")
                buffer = destination / "widget.png"
                call([PROBE, "match", buffer, font, factor, "0", "0", round(760 * factor), round(70 * factor),
                      "lmnogWVwv", "#000000", "#ffffff", destination / "glyphs.json"],
                     env=dict(tools_environment(), QT_QPA_PLATFORM="offscreen"))
                group[kind]["glyphs"] = json.loads((destination / "glyphs.json").read_text())
                if enabled:
                    assert all(g["none/encoded"]["matches"] for g in group[kind]["glyphs"].values())
            group[kind]["presented"] = window_capture(destination, record["pid"], buffer, font, factor,
                                                     title=entry == "normal" and kind == "widget")
            if enabled and "title" in group[kind]["presented"]:
                assert set(group[kind]["presented"]["title"]) == set("lmnogWVwv")
                assert all(g["none/encoded"]["matches"] for g in group[kind]["presented"]["title"].values())
        records[entry] = group
    return records


def font_checks(directory, fonts, factor, enabled):
    records = {}
    for name, font, text, letters, eligible in (
            ("bold", fonts["bold"], "lmnogWVwv", "lmnogWVwv", True),
            ("italic", fonts["italic"], "lmnogWVwv", "lmnogWVwv", True),
            ("symbols", fonts["terminal"], "mnogWV\uf120", "mnogWV\uf120", True),
            ("fallback", fonts["regular"], "mnogWV😀", "mnogWV", True),
            ("cff", fonts["cff"], "lmnogWVwv", "lmnogWVwv", True)):
        target = directory / name
        target.mkdir()
        prefix = target / "widget"
        call(["systemd-run", "--user", "--collect", "--unit=fontreal-font-" + name,
              PROBE, "client", font, prefix, text, *(["gray"] if name == "cff" else ["emoji"] if name == "fallback" else [])])
        record = read_capture(prefix.with_suffix(".json"), factor)
        record["process"] = process_record(record["pid"])
        record["image_sha256"] = build.sha(prefix.with_suffix(".png"))
        if eligible:
            call([PROBE, "match", prefix.with_suffix(".png"), font, factor, "0", "0", round(760 * factor),
                  round(70 * factor), letters, "#000000", "#ffffff", target / "glyphs.json"],
                 env=dict(tools_environment(), QT_QPA_PLATFORM="offscreen"))
            record["glyphs"] = json.loads((target / "glyphs.json").read_text())
            if enabled:
                assert all(g["none/encoded"]["matches"] for g in record["glyphs"].values()), (name, record)
        if name == "symbols":
            assert record["missingPrimaryGlyphs"] == 0, "The Nerd Font must supply the symbol itself."
        if name == "fallback":
            assert record["missingPrimaryGlyphs"] > 0 and len(record["fallbackColors"]) > 10, record
        record["presented"] = window_capture(target, record["pid"], prefix.with_suffix(".png"), font, factor)
        os.kill(record["pid"], signal.SIGTERM)
        records[name] = record
    return records


def konsole_check(directory, fonts, factor, enabled, profile="FontrealTest"):
    call(["systemd-run", "--user", "--collect", "--unit=fontreal-konsole", "konsole", "--separate",
          "--profile", profile, "--notransparency", "--show-menubar", "--hold",
          "-p", "LocalTabTitleFormat=Fontreal test", "-e", "/bin/sh", ROOT / "tools/konsole-sample.sh",
          "Fontreal session sample"])
    process = wait_for(lambda: int(call(["systemctl", "--user", "show", "-p", "MainPID", "--value",
                                       "fontreal-konsole.service"]).stdout), "Konsole process")
    service = wait_for(lambda: next((line.strip() for line in qdbus().splitlines()
                                    if "org.kde.konsole" in line and str(process) in line), None), "Konsole service")
    assert int(qdbus("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.GetConnectionUnixProcessID", service)) == process
    window = next(line.strip() for line in qdbus(service).splitlines() if "/konsole/MainWindow_" in line)
    actions = qdbus(service, window, "org.kde.KMainWindow.actions").splitlines()
    for _ in range(2):
        assert qdbus(service, window, "org.kde.KMainWindow.activateAction", "options_show_menubar") == "true"
    time.sleep(2)
    record = dict(process=process_record(process), pixels=window_capture(directory, process, None, fonts["regular"], factor))
    if profile == "FontrealCff":
        mapped = Path(f"/proc/{process}/maps").read_text()
        assert str(fonts["cff_terminal"]) in mapped and "NimbusMonoPS-Regular.pfb" not in mapped
    if enabled:
        record["oracle"] = call([ROOT / "build/qt-native-probe", "--capture", directory / "client.png",
                                  fonts["regular"], fonts["cff_terminal"] if profile == "FontrealCff" else fonts["terminal"], "encoded", "none", factor],
                                 env=dict(tools_environment(), QT_QPA_PLATFORM="offscreen")).stdout
    action = "file_quit" if "file_quit" in actions else "close-window"
    assert qdbus(service, window, "org.kde.KMainWindow.activateAction", action) == "true"
    wait_for(lambda: not Path(f"/proc/{process}").exists(), "normal Konsole close")
    return record


def selected(directory, plan):
    inventory = build.package_inventory(directory / "packages")
    return [directory / "packages" / inventory[(p["name"], p["arch"])]["path"] for p in plan["installed"]]


def setup_packages(packages):
    # Lower-version resets are disposable test setup, never ordinary update proof.
    call(["sudo", "apt-get", "install", "-y", "--allow-downgrades", "--no-remove",
          *packages], timeout=300)


def captured_predecessor(directory, plan, previous):
    """Resolve the actual captured snapshot, using its owning retained bundle."""
    if plan["installed"] == plan["original"]:
        return None, None
    assert previous is not None, "The captured Fontreal predecessor needs --previous and its actual retained artifacts."
    predecessor = Path(previous).resolve()
    old = build.verify_artifacts(predecessor, json.loads((predecessor / "bundle.json").read_text()))
    package.system_install.verify_activation(build, predecessor, json.loads((predecessor / "deployment.json").read_text()), old)
    original_records = {(p["name"], p["arch"]): p for p in plan["original"]}
    old_originals = {(p["name"], p["arch"]): p for p in old["original"]}
    originals_inventory = build.package_inventory(directory / "original")
    previous_inventory = build.package_inventory(predecessor / "packages")
    files = []
    for p in plan["installed"]:
        identity = (p["name"], p["arch"])
        if p == original_records[identity]:
            files.append(directory / "original" / originals_inventory[identity]["path"])
        else:
            version = old["sources"][p["source"]]["build_version"]
            artifact = previous_inventory[identity]
            assert p["version"] == p["source_version"] == artifact["version"] == version
            assert artifact["source"] in (p["source"], f"{p['source']} ({version})")
            assert old_originals[identity] == original_records[identity]
            files.append(predecessor / "packages" / artifact["path"])
    return predecessor, files


def clear_actors(current):
    processes = set()
    for path in [*current.glob("*-widget.json"), *current.glob("*-quick/result.json")]:
        try:
            processes.add(json.loads(path.read_text())["pid"])
        except (OSError, ValueError, KeyError):
            pass
    for name in ("Widget", "Quick"):
        service = "org.fontreal." + name + "Probe"
        if qdbus("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.NameHasOwner", service) == "true":
            processes.add(int(qdbus("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                    "org.freedesktop.DBus.GetConnectionUnixProcessID", service)))
    for unit in ("fontreal-widget", "fontreal-quick", "fontreal-inherited", "fontreal-inherited-widget",
                 *["fontreal-font-" + name for name in ("bold", "italic", "symbols", "fallback", "cff")]):
        value = subprocess.run(["systemctl", "--user", "show", "-p", "MainPID", "--value", unit],
                               capture_output=True, text=True).stdout.strip()
        if value.isdigit() and int(value):
            processes.add(int(value))
    for process in processes:
        try:
            if str(Path(f"/proc/{process}/exe").resolve()).removesuffix(" (deleted)") == str(PROBE.resolve()):
                os.kill(process, signal.SIGTERM)
        except ProcessLookupError:
            pass
    wait_for(lambda: all(qdbus("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.NameHasOwner",
                              "org.fontreal." + name + "Probe") == "false" for name in ("Widget", "Quick")),
             "test D-Bus services stopped")
    for path in list(current.iterdir()):
        if path.name == "plasma.png":
            continue
        if path.is_dir():
            shutil.rmtree(path)
            path.mkdir()
        else:
            path.unlink()


def live_scale(directory, current, font, before):
    """Check the already presented scene before any test-driven recapture."""
    process = before["systemd"]["quick"]["pixels"]["pid"]
    kwin_script(directory, f"for(var w of workspace.windowList()) if(w.pid=={process}) {{ w.minimized=false; workspace.activeWindow=w; }}")
    time.sleep(.7)
    scale(1.25)
    surface = current / "systemd-quick/surface.json"
    wait_for(lambda: read_surface(surface, process, 1.25), "existing Quick surface at the new scale")
    time.sleep(.7)
    geometry = kwin_script(directory,
        f"for(var w of workspace.windowList()) if(w.pid=={process}) reports.push(w.clientGeometry);")
    assert len(geometry) == 1
    screenshot(directory / "live-desktop.png")
    rect = geometry[0]
    env = dict(tools_environment(), QT_QPA_PLATFORM="offscreen")
    call([PROBE, "grid", directory / "live-desktop.png", font, "1.25", directory / "live-grid.json",
          round(rect["x"] * 1.25), round(rect["y"] * 1.25)], env=env)
    record = json.loads((directory / "live-grid.json").read_text())
    assert {(c["path"], c["glyph"]) for c in record["cells"]} == {(r, c) for r in range(6) for c in "lmnogWVwv"}
    assert all(c["hypotheses"]["none/encoded"]["matches"] for c in record["cells"]), record
    assert any(not c["hypotheses"]["none/linear"]["matches"] for c in record["cells"])
    assert Path(f"/proc/{process}").exists()
    # Only after the presentation oracle do we refresh the static capture matrix.
    recapture(directory, current, 1.25)
    return dict(pid=process, geometry=rect, pixels=record)


def read_surface(path, process, factor):
    try:
        record = json.loads(path.read_text())
        return record if record["pid"] == process and record["scale"] == factor else None
    except (OSError, ValueError, KeyError):
        return None


def recapture(directory, current, factor):
    processes = []
    captures = [*current.glob("*-widget.json"), *current.glob("*-quick/result.json")]
    for path in captures:
        record = json.loads(path.read_text())
        surface = path.with_suffix(".surface.json") if path.name != "result.json" else path.parent / "surface.json"
        wait_for(lambda: read_surface(surface, record["pid"], factor), "all existing actors at the new scale")
        processes.append(record["pid"])
    # Hidden Quick windows can retain an old swapchain size. Static matrix
    # captures use exposed windows, after the separate live presentation check.
    kwin_script(directory, "var ids=" + json.dumps(processes) + "; for(var w of workspace.windowList()) if(ids.indexOf(w.pid)>=0) w.minimized=false;")
    time.sleep(.7)
    for path in captures:
        path.unlink()
        (path.parent / "recapture" if path.name == "result.json" else path.with_suffix(".recapture")).touch()


def same_frames(actual, reference, directory, original, software):
    assert [f["cellHash"] for f in actual["frames"]] == [f["cellHash"] for f in reference["frames"]]
    if software:
        assert [f["hash"] for f in actual["frames"]] == [f["hash"] for f in reference["frames"]]
    else:
        # FR-013 permits one value in hardware LCD annotations, outside exact controlled cells.
        for frame in range(5):
            output = directory / f"stock-frame-{frame}.json"
            call([PROBE, "composite", original / f"frame-{frame}.png", directory / f"frame-{frame}.png", output],
                 env=dict(tools_environment(), QT_QPA_PLATFORM="offscreen"))
            assert json.loads(output.read_text())["matches"]


def same_stock(actual, reference):
    for entry in ("normal", "dbus", "systemd"):
        for kind in ("widget", "quick"):
            a, b = actual["actors"][entry][kind], reference["actors"][entry][kind]
            if kind == "quick":
                directory, original = (Path(case["directory"]) / (entry + "-" + kind) for case in (actual, reference))
                software = a["process"]["softwareForced"] or b["process"]["softwareForced"]
                same_frames(a["pixels"], b["pixels"], directory, original, software)
                if software:
                    assert a["presented"]["client_sha256"] == b["presented"]["client_sha256"]
                else:
                    output = directory / "stock-client.json"
                    call([PROBE, "composite", original / "client.png", directory / "client.png", output],
                         env=dict(tools_environment(), QT_QPA_PLATFORM="offscreen"))
                    assert json.loads(output.read_text())["matches"]
            else:
                assert a["presented"]["client_sha256"] == b["presented"]["client_sha256"], (entry, kind)
    assert actual["actors"]["normal"]["widget"]["presented"]["title_text_sha256"] == reference["actors"]["normal"]["widget"]["presented"]["title_text_sha256"]
    assert actual["plasma"]["image_sha256"] == reference["plasma"]["image_sha256"]
    for name in actual["fonts"]:
        assert actual["fonts"][name]["image_sha256"] == reference["fonts"][name]["image_sha256"], name


def session_case(directory, current, fonts, enabled, reference=None, live=False, preference=None, inherited=None):
    directory.mkdir()
    clear_actors(current)
    scale(1)
    login = new_login(preference)
    expected = {
        "FONTREAL_RENDERING": "1" if enabled else "0", "FONTREAL_BLEND": "encoded" if enabled else "",
        "FONTREAL_CONTRAST": "weighted" if enabled else "", "FONTREAL_FITTING": "native" if enabled else ""}
    allowed = [expected]
    if inherited is not None:
        # After removal, launch paths can retain or clear their old values independently.
        assert not enabled
        allowed.append(inherited)
    assert login["environment"] in allowed, login
    result = dict(login=login, scales={})
    previous = None
    for factor in (1, 1.25):
        target = directory / str(factor)
        target.mkdir()
        if factor != 1:
            if live:
                result["live_scale"] = live_scale(target, current, fonts["regular"], previous)
            else:
                scale(factor)
                recapture(target, current, factor)
        group = dict(directory=str(target), actors=actors(target, current, fonts["regular"], factor, enabled, launch=factor == 1,
                                  expected_environment=[{k + "=" + v for k, v in state.items()} for state in allowed]))
        previous = group["actors"]
        group["plasma"] = plasma_capture(target, current, fonts["regular"], factor)
        group["plasma"]["image_sha256"] = build.sha(target / "plasma.png")
        if enabled:
            for record in group["plasma"]["buffers"]:
                assert all(c["hypotheses"]["none/encoded"]["matches"] for c in record["cells"]), record
        group["fonts"] = font_checks(target, fonts, factor, enabled)
        group["konsole"] = konsole_check(target, fonts, factor, enabled)
        cff_terminal = target / "konsole-cff"
        cff_terminal.mkdir()
        group["konsole_cff"] = konsole_check(cff_terminal, fonts, factor, enabled, "FontrealCff")
        if reference is not None:
            if not enabled:
                same_stock(group, reference["scales"][str(factor)])
            else:
                original = reference["scales"][str(factor)]["fonts"]
                assert group["fonts"]["fallback"]["fallbackColors"] == original["fallback"]["fallbackColors"]
        result["scales"][str(factor)] = group
    build.write_json(directory / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--previous", type=Path, help="Actual retained predecessor bundle when the captured system already uses Fontreal.")
    args = parser.parse_args()
    assert Path("/var/lib/fontreal-test-ready").is_file(), "Use an explicitly prepared disposable full Plasma VM."
    call(["systemd-detect-virt", "--vm"])
    directory = args.bundle.resolve()
    reference = Path(os.environ["FONTREAL_TEST_REFERENCE_FREETYPE"]).resolve()
    reference_record = json.loads((ROOT / "build/browser-live-recipe/reference.json").read_text())
    assert reference.is_file() and build.sha(reference) == reference_record["stock_sha256"], "Use the independent pristine FreeType reference."
    os.environ["FONTREAL_TEST_SELECTED_REFERENCE"] = str(ROOT / "tests/selected_reference.py")
    manifest = json.loads((directory / "bundle.json").read_text())
    plan = build.verify_artifacts(directory, manifest)
    system = platform.freedesktop_os_release()
    assert (system["ID"], system["VERSION_ID"], build.output(["dpkg", "--print-architecture"])) == (
        plan["os"], plan["release"], plan["arch"]), "Use the supported distribution and architecture recorded in the bundle."
    sys.path.insert(0, str(ROOT / "tools"))
    import system_install
    deployment = json.loads((directory / "deployment.json").read_text())
    system_install.verify_activation(build, directory, deployment, plan)
    report = json.loads((directory / "package-checks/package-results.json").read_text())
    assert report["passed"] is True and report["schema"] == 1 and report["selected_profile"] == build.SELECTED_PROFILE
    assert report["bundle_sha256"] == build.sha(directory / "bundle.json")
    assert report["deployment_sha256"] == build.sha(directory / "deployment.json")
    assert len(report["updates"]) == len(build.SOURCES) and {r["source"] for r in report["updates"]} == set(build.SOURCES)
    assert build.installed() == plan["installed"], "Start with the real captured package snapshot."
    predecessor, predecessor_files = captured_predecessor(directory, plan, args.previous)
    reports = directory / "session-checks"
    reports.mkdir()
    fonts = {key: Path(call(["fc-match", "-f", "%{file}", family]).stdout) for key, family in (
        ("regular", "Nimbus Sans:style=Regular"), ("bold", "Noto Sans:style=Bold"), ("italic", "Noto Sans:style=Italic"),
        ("terminal", "Inconsolata Nerd Font"), ("cff", "Nimbus Sans"), ("cff_terminal", "Nimbus Mono PS"), ("emoji", "Noto Color Emoji"))}
    fixture(reports, fonts["regular"], fonts["terminal"])
    originals = sorted((directory / "original").glob("*.deb"))
    candidate = selected(directory, plan)
    activation = directory / "activation/fontreal-session.deb"
    marker = Path.home() / ".config/fontreal/enabled"
    marker.unlink(missing_ok=True)
    setup_packages([*originals, activation])
    assert not marker.exists(), "Package installation must start disabled."
    current = reports / "current"
    results = dict(schema=1, passed=False, complete_runtime=False, selected_profile=build.SELECTED_PROFILE,
                   bundle_sha256=build.sha(directory / "bundle.json"),
                   deployment_sha256=build.sha(directory / "deployment.json"))
    baseline = session_case(reports / "official", current, fonts, False)
    saved_fonts = font_state(fonts.values())
    results["official"] = baseline
    setup_packages([*candidate, activation])
    assert not marker.exists()
    results["initial_disabled"] = session_case(reports / "initial-disabled", current, fonts, False, baseline)
    results["enabled"] = session_case(reports / "enabled", current, fonts, True, baseline, live=True, preference=True)
    results["capture_cost"] = {
        "scope": "Median of five actual Quick grabWindow calls, render plus readback only. Excludes mask classification and PNG writing. Not a general frame-rate benchmark.",
        "scales": {factor: {mode: statistics.median(case["scales"][factor]["actors"]["normal"]["quick"]["pixels"]["captureNanoseconds"])
                           for mode, case in (("official", baseline), ("enabled", results["enabled"]))}
                   for factor in ("1", "1.25")}}
    results["disabled"] = session_case(reports / "disabled", current, fonts, False, baseline, preference=False)
    results["updates"] = []
    for source in build.SOURCES:
        setup_packages([*candidate, activation])
        clear_actors(current)
        new_login(True)
        scale(1)
        pool = directory / "package-checks" / ("future-" + source)
        assert (pool / "Packages").is_file()
        repository = "/etc/apt/sources.list.d/fontreal-session-test.list"
        call(["sudo", "python3", "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).write_text(sys.argv[2])",
              repository, f"deb [trusted=yes] file:{pool} ./\n"])
        call(["sudo", "apt-get", "update"])
        names = sorted(p["name"] for p in plan["installed"] if p["source"] == source)
        call(["sudo", "apt-get", "install", "-y", "--only-upgrade", "--no-remove", *names])
        actual = build.installed()
        assert {(p["name"], p["arch"]) for p in actual} == {(p["name"], p["arch"]) for p in plan["installed"]}
        for p in actual:
            expected = plan["sources"][source]["version"] + ".1" if p["source"] == source else plan["sources"][p["source"]]["build_version"]
            assert p["version"] == expected, p
        target = reports / ("updated-" + source)
        target.mkdir()
        clear_actors(current)
        prefix = target / "inherited"
        prefix.mkdir()
        # This is a new actual consumer of the retained user-manager environment.
        call(["systemd-run", "--user", "--collect", "--unit=fontreal-inherited", "env", "LD_BIND_NOW=1", "FONTREAL_TEST_HOLD=1",
              PROBE, "quick", fonts["regular"], prefix, "0"])
        record = read_capture(prefix / "result.json", 1)
        record["process"] = process_record(record["pid"])
        assert set(record["process"]["environment"]) == {"FONTREAL_RENDERING=1", "FONTREAL_BLEND=encoded", "FONTREAL_CONTRAST=weighted", "FONTREAL_FITTING=native"}
        stock = baseline["scales"]["1"]["actors"]["normal"]["quick"]["pixels"]
        widget_prefix = target / "inherited-widget"
        call(["systemd-run", "--user", "--collect", "--unit=fontreal-inherited-widget", "env", "LD_BIND_NOW=1",
              PROBE, "client", fonts["regular"], widget_prefix])
        widget = read_capture(widget_prefix.with_suffix(".json"), 1)
        widget["process"] = process_record(widget["pid"])
        assert set(widget["process"]["environment"]) == set(record["process"]["environment"])
        if source in ("freetype", "qt6-base"):
            same_frames(record, stock, prefix, reports / "official/1/normal-quick", record["process"]["softwareForced"])
            assert build.sha(widget_prefix.with_suffix(".png")) == build.sha(reports / "official/1/normal-widget/widget.png")
        else:
            # Gui remains patched in this inherited enabled session. Native
            # runs can retain its treatment until the version hook runs again.
            assert len(record["frames"]) == 5 and all(len(f["cells"]) == 54 for f in record["frames"])
            for frame in record["frames"]:
                native_cells = [cell for cell in frame["cells"] if cell["path"] == 0]
                assert len(native_cells) == 9 and all(cell["hypotheses"]["none/encoded"]["matches"] for cell in native_cells)
            call([PROBE, "match", widget_prefix.with_suffix(".png"), fonts["regular"], 1, 0, 0, 760, 70,
                  "lmnogWVwv", "#000000", "#ffffff", target / "widget-glyphs.json"],
                 env=dict(tools_environment(), QT_QPA_PLATFORM="offscreen"))
            assert all(g["none/encoded"]["matches"] for g in json.loads((target / "widget-glyphs.json").read_text()).values())
        inherited_before_fallback = session_environment()
        assert inherited_before_fallback["FONTREAL_RENDERING"] == "1" and marker.exists()
        fallback = session_case(target / "next-login", current, fonts, False, baseline)
        assert marker.exists(), "An unsupported pair must preserve the user's preference."
        call(["sudo", "rm", repository])
        call(["sudo", "apt-get", "update"])
        results["updates"].append(dict(source=source, inherited=record, widget=widget, fallback=fallback,
                                       inherited_before_fallback=inherited_before_fallback,
                                       payload="Retained official payload with synthetic higher control version"))
    command = [sys.executable, ROOT / "tools/system-build.py"]
    call(["sudo", "unshare", "--net", *command, "rollback", directory])
    assert build.installed() == plan["original"]
    assert subprocess.run(["dpkg-query", "-W", "-f=${db:Status-Status}", "fontreal-session"], capture_output=True).stdout != b"installed"
    # Plasma can restore the pre-fallback manager environment on logout after
    # the activation hook is removed. Rendering must still match official pixels.
    results["rollback"] = session_case(reports / "rollback", current, fonts, False, baseline,
                                       inherited=inherited_before_fallback)
    if predecessor is None:
        assert build.installed() == plan["installed"]
    else:
        setup_packages([*predecessor_files, predecessor / "activation/fontreal-session.deb"])
        assert build.installed() == plan["installed"]
    assert font_state(fonts.values()) == saved_fonts, "Package/session operations changed the user's fonts."
    # Record session evidence before exercising production install and rollback.
    # A failed continuation removes this provisional development result.
    results.update(passed=True, complete_runtime=True)
    result_path = reports / "session-results.json"
    build.write_json(result_path, results)
    try:
        call([*command, "install", directory, "--simulate"])
        call(["sudo", *command, "install", directory])
        results["guarded_install"] = session_case(reports / "guarded-install", current, fonts, True, baseline)
        inherited = session_environment()
        call(["sudo", "unshare", "--net", *command, "rollback", directory])
        assert build.installed() == plan["original"] and font_state(fonts.values()) == saved_fonts
        results["guarded_rollback"] = session_case(reports / "guarded-rollback", current, fonts, False, baseline, inherited=inherited)
        build.write_json(result_path, results)
    except BaseException:
        result_path.unlink(missing_ok=True)
        raise
    print("PASS: complete Plasma activation, presented pixels, live scale, ordinary updates, guarded apply and console rollback")


if __name__ == "__main__":
    main()
