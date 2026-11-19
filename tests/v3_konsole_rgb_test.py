#!/usr/bin/env python3
"""Compare native Konsole pixels on a nested stock KWin output."""
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from xml.sax.saxutils import escape

from fontTools.ttLib import TTFont
from PIL import Image, ImageGrab
from kde_paths_test import ROOT, display, private_environment, stop


def wait_for(path, process):
    for _ in range(200):
        if path.exists():
            return
        assert process.poll() is None, (process.args, process.returncode)
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {path}")


def library_mappings(pid, directory, required):
    lines = Path(f"/proc/{pid}/maps").read_text().splitlines()
    for soname in required:
        paths = {Path(line.split()[-1]) for line in lines if f"/{soname}." in line}
        expected = (directory / f"{soname}.6").resolve()
        assert paths == {expected}, (soname, paths, expected)
    return lines


def changed_pixels(before, after):
    a, b = before.tobytes(), after.tobytes()
    return sum(a[i:i + 3] != b[i:i + 3] for i in range(0, len(a), 3))


def edge_faces(work, env):
    source = subprocess.check_output(
        ["fc-match", "-f", "%{file}", "Hack:style=Regular"],
        env=dict(env, FONTCONFIG_FILE=str(work / "fonts.conf")), text=True)
    for case in ("fixture-control", "weight-350", "implicit-autohint"):
        directory = work / case
        directory.mkdir()
        with TTFont(source) as face:
            if case == "weight-350":
                face["OS/2"].usWeightClass = 350
            elif case == "implicit-autohint":
                face["glyf"].removeHinting()
                for tag in ("cvt ", "fpgm", "prep"):
                    del face[tag]
            face.save(directory / "Hack-Regular.ttf")
        yield case, {"fontdir": str(directory)}


def capture(label, order, launcher, reference, env, work, stock, patched,
            *, hint="hintfull", family="Hack", weight=400, rules="", marks=True, fontdir="/usr/share/fonts"):
    config = work / "fonts.conf"
    config.write_text(f"""<fontconfig>
    <dir>{escape(fontdir)}</dir><cachedir>{escape(str(work / 'cache'))}</cachedir>
    <match target="font">
      <edit name="rgba" mode="assign"><const>{order}</const></edit>
      <edit name="antialias" mode="assign"><bool>true</bool></edit>
      <edit name="hintstyle" mode="assign"><const>{hint}</const></edit>
    </match>
    {rules}
    </fontconfig>""")
    child = work / "child"
    child.unlink(missing_ok=True)
    text = "'  " + " ".join("H8oaseiIl!A@W*()") + " ' '" + " ".join("0123456789") + "  '"
    sample = (
        f"printf '\\033[38;2;0;0;0;48;2;255;255;255m%s\\033[1m%s\\033[0m\\n' {text}; "
        f"printf '\\033[38;2;255;255;255;48;2;0;0;0m%s\\033[1m%s\\033[0m\\n' {text}; "
    ) * 2
    sample += (
        "printf '\\033[38;2;0;0;0;48;2;255;255;255m%s\\033[0m\\n' '  HA  ☀  HA  '; "
        "printf '\\033[38;2;255;255;255;48;2;24;32;48m%s\\033[0m\\n' '  The quick brown fox  '; "
    )
    text = "x\u0301\u0301\u0301\u0301\u0301" if marks else "x"
    sample += f"printf '\\033[38;2;0;0;0;48;2;255;255;255m%s\\033[0m\\n' '  {text}  '; "
    sample += "printf '\\033[48;2;24;32;48m   \\033[38;2;0;0;0;48;2;255;255;255ma   a  \\033[0m\\n'; "
    # Also verify that Konsole starts the actual terminal child with its original preload.
    sample += ("printf '%s\\n' \"${LD_PRELOAD-}\" > " + shlex.quote(str(work / "preload")) +
               "; cat /proc/$$/maps > " + shlex.quote(str(work / "maps")) +
               "; touch " + shlex.quote(str(child)) + "; sleep 30")
    runtime = dict(env, WAYLAND_DISPLAY="fr-konsole", QT_QPA_PLATFORM="wayland",
                   QT_QPA_PLATFORMTHEME="", FONTCONFIG_FILE=str(config),
                   LD_LIBRARY_PATH=f"{patched / 'lib'}:{stock}" if reference else str(stock),
                   FONTREAL_RENDERING="3" if reference else "0")
    if reference:
        runtime["QT_PLUGIN_PATH"] = f"{patched / 'plugins'}:{runtime['QT_PLUGIN_PATH']}"
    runtime["LD_PRELOAD"] = "libm.so.6"
    command = (launcher or ["konsole", "--separate"]) + [
        "--notransparency", "--fullscreen", "--hide-menubar", "--hide-tabbar",
        "-p", "ColorScheme=FontrealTrial", "-p", "BoldIntense=true",
        "-p", f"Font={family},10,-1,5,{weight},0,0,0,0,0,0,0,0,0,0,1",
        "-e", "/bin/sh", "-c", sample,
    ]
    with (work / f"{label}.log").open("w") as log:
        app = subprocess.Popen(command, env=runtime, stdout=log, stderr=log)
        try:
            wait_for(child, app)
            time.sleep(0.6)
            maps = library_mappings(app.pid, patched / "lib" if reference else stock,
                                    ("libQt6Gui.so", "libQt6Widgets.so"))
            library_mappings(app.pid, stock, ("libfreetype.so",))
            assert any("/libfontreal-qt-rgb.so" in line for line in maps) == bool(launcher)
            assert (work / "preload").read_text().strip() == "libm.so.6"
            assert "/libfontreal-qt-rgb.so" not in (work / "maps").read_text()
            sample = ImageGrab.grab((0, 0, 680, 160), xdisplay=env["DISPLAY"]).convert("RGB")
            assert sample.histogram()[255] > 45000
            sample.save(work / f"{label}.png")
            return sample
        finally:
            stop(app)


def main():
    if len(sys.argv) != 5:
        raise SystemExit("Usage: v3_konsole_rgb_test.py OFFICIAL_LIB_DIR PATCHED_QT_DIR LIBFONTREAL_RGB OUTPUT")
    stock, patched, library, output = (Path(arg).resolve() for arg in sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temp:
        work = Path(temp)
        env = private_environment(work)
        env.update(XDG_CURRENT_DESKTOP="KDE", KWIN_FORCE_OWN_QPA="1", LD_LIBRARY_PATH=str(stock))
        data = work / "data/konsole"
        data.mkdir()
        (data / "FontrealTrial.colorscheme").write_text(
            "[General]\nDescription=Fontreal trial\nOpacity=1\n"
            "[Background]\nColor=255,255,255\n[Foreground]\nColor=0,0,0\n"
            "[BackgroundIntense]\nColor=255,255,255\n[ForegroundIntense]\nColor=0,0,0\n")
        (work / "config/kwinrc").write_text(
            "[Windows]\nPlacement=ZeroCornered\n\n[Compositing]\nAnimationSpeed=0\n")
        launcher = [ROOT / "tools/run-konsole-rgb", library]
        # Copy the distro executable without file capabilities so the loader accepts the archive path.
        compositor_binary = work / "kwin_wayland"
        shutil.copy(shutil.which("kwin_wayland"), compositor_binary)
        with display(env, work) as xenv, (work / "kwin.log").open("w") as log:
            command = [compositor_binary, "--x11-display", xenv["DISPLAY"], "--width", "1100",
                       "--height", "740", "--socket", "fr-konsole", "--no-lockscreen",
                       "--no-global-shortcuts", "--no-kactivities"]
            compositor = subprocess.Popen(command, env=dict(xenv, LD_DEBUG="libs"), stdout=log, stderr=log)
            try:
                wait_for(Path(xenv["XDG_RUNTIME_DIR"]) / "fr-konsole", compositor)
                logged = (work / "kwin.log").read_text()
                for soname in ("libQt6Gui.so.6", "libQt6Quick.so.6", "libfreetype.so.6"):
                    assert f"calling init: {stock / soname}" in logged, soname
                assert "/libfontreal-qt-rgb.so" not in logged
                for order in ("rgb", "bgr", "none"):
                    baseline = capture(f"{order}-stock", order, None, False, xenv, work, stock, patched)
                    pilot = capture(f"{order}-pilot", order, launcher, False, xenv, work, stock, patched)
                    if order == "rgb":
                        reference = capture("rgb-reference", order, None, True, xenv, work, stock, patched)
                        supported = (0, 0, 680, 75)
                        delta = changed_pixels(pilot.crop(supported), reference.crop(supported))
                        changed = changed_pixels(pilot.crop(supported), baseline.crop(supported))
                        print(f"RGB: {changed} pixels changed from stock, {delta} differ from V3", flush=True)
                        assert changed > 0 and delta == 0
                        for name, area in (("fallback glyph", (45, 75, 70, 92)),
                                           ("colored background", (0, 92, 680, 110)),
                                           ("combining marks", (18, 98, 27, 124)),
                                           ("LCD fringe", (26, 133, 36, 145))):
                            assert baseline.crop(area).histogram()[255] < (area[2] - area[0]) * (area[3] - area[1])
                            assert pilot.crop(area).tobytes() == baseline.crop(area).tobytes(), name
                            print(f"{name}: stock pixels preserved", flush=True)
                        assert changed_pixels(pilot.crop((0, 75, 36, 92)), baseline.crop((0, 75, 36, 92))) > 0
                        assert changed_pixels(pilot.crop((58, 133, 68, 145)), baseline.crop((58, 133, 68, 145))) > 0
                        unmarked = capture("rgb-unmarked", order, None, False, xenv, work, stock, patched,
                                           marks=False)
                        for area in ((18, 98, 27, 110), (18, 112, 27, 116)):
                            assert changed_pixels(baseline.crop(area), unmarked.crop(area)) > 0
                    else:
                        assert pilot.tobytes() == baseline.tobytes(), order
                        print(f"{order}: stock pixels preserved", flush=True)
                qualified_family = "Hack [SRC]"
                qualified_rules = f"""
    <match target="font">
      <test target="pattern" name="family" qual="any"><string>{qualified_family}</string></test>
      <edit name="rgba" mode="assign"><const>bgr</const></edit>
    </match>"""
                resolved_light_rules = """<selectfont>
      <acceptfont><glob>*DejaVuSans-ExtraLight.ttf</glob></acceptfont>
      <rejectfont><glob>*DejaVuSans*</glob></rejectfont>
    </selectfont>"""
                for label, parameters in (
                    ("slight-hint", {"hint": "hintslight"}),
                    ("no-hint", {"hint": "hintnone"}),
                    ("autohint", {"rules": '<match target="font"><edit name="autohint" mode="assign">'
                                           '<bool>true</bool></edit></match>'}),
                    ("light", {"family": "DejaVu Sans", "weight": 200}),
                    ("resolved-light", {"family": "DejaVu Sans", "rules": resolved_light_rules}),
                    ("qualified-family", {"family": qualified_family, "rules": qualified_rules}),
                    *edge_faces(work, xenv),
                ):
                    baseline = capture(f"{label}-stock", "rgb", None, False, xenv, work, stock, patched, **parameters)
                    pilot = capture(f"{label}-pilot", "rgb", launcher, False, xenv, work, stock, patched, **parameters)
                    if label == "fixture-control":
                        assert changed_pixels(pilot, baseline) > 0, label
                        print(f"{label}: RGB treatment applied", flush=True)
                    else:
                        assert pilot.tobytes() == baseline.tobytes(), label
                        print(f"{label}: stock pixels preserved", flush=True)
                    if label == "resolved-light":
                        with Image.open(work / "light-stock.png") as light_stock:
                            regular_text = (0, 0, 375, 75)
                            assert baseline.crop(regular_text).tobytes() == light_stock.crop(regular_text).tobytes()
                        normal_stock = capture("normal-face-stock", "rgb", None, False, xenv, work, stock,
                                               patched, family="DejaVu Sans")
                        normal_pilot = capture("normal-face-pilot", "rgb", launcher, False, xenv, work, stock,
                                               patched, family="DejaVu Sans")
                        assert changed_pixels(normal_stock.crop(regular_text), normal_pilot.crop(regular_text)) > 0
                    if label == "qualified-family":
                        isolated = (0, 0, 680, 75)
                        with Image.open(work / "bgr-stock.png") as bgr_stock:
                            assert baseline.crop(isolated).tobytes() == bgr_stock.crop(isolated).tobytes()
                        with Image.open(work / "rgb-stock.png") as rgb_stock:
                            assert baseline.crop(isolated).tobytes() != rgb_stock.crop(isolated).tobytes()
            finally:
                stop(compositor)
                for path in list(work.glob("*.png")) + list(work.glob("*.log")):
                    path.replace(output / path.name)


if __name__ == "__main__":
    main()
