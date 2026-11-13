#!/usr/bin/env python3
"""Check the private browser experiment through public FreeType and real windows."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import select
import shlex
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = (ROOT / "build/freetype-native").resolve()
OUT = (ROOT / "results/browser-masks").resolve()
NOTO = Path("/usr/share/fonts/truetype/noto")
STYLES = {"Regular": "regular", "Bold": "bold", "Italic": "italic", "BoldItalic": "bold-italic"}


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, text=True,
                          capture_output=True, timeout=180, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected():
    paths = [Path.home() / name for name in (
        ".config/kdeglobals", ".config/kcmfonts", ".config/fontconfig/fonts.conf",
        ".config/mozilla/firefox/profiles.ini", ".mozilla/firefox/profiles.ini", ".floorp/profiles.ini")]
    paths += [Path("/usr/lib/x86_64-linux-gnu/libfreetype.so.6").resolve()]
    return {str(p): digest(p) if p.exists() else None for p in paths}


def mild(snapshot):
    result = dict(snapshot)
    result["mask"] = bytes(((max(32, min(223, a)) - 32) * 255 + 95) // 191
                           for a in bytes.fromhex(snapshot["mask"])).hex()
    return result


def probe(record, font, pixels=15, flags=0x28, char="m", mode=0,
          enabled=True, contrast="mild", dx=0, variant="candidate", transform="none", remove_hinter=False):
    env = dict(os.environ, LD_LIBRARY_PATH=str(Path(record["libraries"][variant]["library"]).parent),
               FONTREAL_FT_RENDERING="1" if enabled else "0", FONTREAL_FT_CONTRAST=contrast)
    target = WORK / "probe.json"
    run([WORK / "mask-probe", font, pixels, flags, ord(char), mode, dx, 0, 2, target,
         transform, int(remove_hinter)], env=env)
    return json.loads(target.read_text())


def font_fixtures(glyph):
    """Synthetic local fonts reach real FreeType bitmap/name gates; never distributed."""
    data = (NOTO / "NotoSans-Regular.ttf").read_bytes()
    count = struct.unpack_from(">H", data, 4)[0]
    tables = {}
    for i in range(count):
        tag, _, offset, size = struct.unpack_from(">4sIII", data, 12 + 16*i)
        tables[tag] = data[offset:offset+size]

    def save(path, changed):
        entries = dict(tables)
        entries.update(changed)
        entries.pop(b"DSIG", None)
        entries[b"head"] = entries[b"head"][:8] + b"\0"*4 + entries[b"head"][12:]
        power = (len(entries).bit_length() - 1)
        directory = struct.pack(">4sHHHH", data[:4], len(entries), 16*(1 << power), power,
                                len(entries)*16 - 16*(1 << power))
        body = bytearray()
        head = None
        for tag, contents in sorted(entries.items()):
            padded = contents + b"\0"*((-len(contents)) % 4)
            offset = 12 + 16*len(entries) + len(body)
            checksum = sum(struct.unpack(f">{len(padded)//4}I", padded)) & 0xffffffff
            directory += struct.pack(">4sIII", tag, checksum, offset, len(contents))
            if tag == b"head":
                head = offset
            body.extend(padded)
        result = bytearray(directory) + body
        checksum = sum(struct.unpack(f">{len(result)//4}I", result)) & 0xffffffff
        struct.pack_into(">I", result, head+8, (0xb1b0afba - checksum) & 0xffffffff)
        path.write_bytes(result)

    # OpenType EBLC/EBDT format 1: one deliberately distinct 8x8 monochrome m.
    # https://learn.microsoft.com/en-us/typography/opentype/spec/eblc
    line = bytes([8,0,8,1,0,0,0,0,8,0,0,0])
    size = struct.pack(">IIII", 56, 24, 1, 0) + line + bytes(12)
    size += struct.pack(">HHBBBB", glyph, glyph, 15, 15, 1, 1)
    eblc = struct.pack(">II", 0x20000, 1) + size
    eblc += struct.pack(">HHIHHIII", glyph, glyph, 8, 1, 1, 4, 0, 13)
    embedded = WORK / "synthetic-embedded.ttf"
    save(embedded, {b"EBLC": eblc, b"EBDT": struct.pack(">I", 0x20000) + bytes([8,8,0,8,8]) + b"\xff"*8})

    # Exact upstream tt_check_trickyness_family recognizes this name.
    names = tables[b"name"]
    format_, count, offset = struct.unpack_from(">HHH", names)
    assert format_ == 0
    records, strings = b"", b""
    for i in range(count):
        platform, encoding, language, name, length, start = struct.unpack_from(">6H", names, 6 + i*12)
        value = names[offset+start:offset+start+length]
        if name in (1, 16):
            value = "MingLiU".encode("utf-16-be" if platform in (0, 3) else "ascii")
        records += struct.pack(">6H", platform, encoding, language, name, len(value), len(strings))
        strings += value
    tricky = WORK / "synthetic-tricky.ttf"
    save(tricky, {b"name": struct.pack(">HHH", 0, count, 6+12*count) + records + strings})
    return embedded, tricky


def freetype(record):
    checks = 0
    for style in STYLES:
        font = NOTO / f"NotoSans-{style}.ttf"
        for char in "mnogWV ":
            reference = probe(record, font, flags=0x20028, char=char, variant="stock")
            for flags in (0, 0x8000, 0x10000, 0x28, 0x8028, 0x10028):
                for contrast in ("none", "mild"):
                    actual = probe(record, font, flags=flags, char=char, contrast=contrast)
                    expected = reference["rendered"][0]
                    if contrast == "mild":
                        expected = mild(expected)
                    assert actual["rendered"] == [expected, expected], (style, char, flags, contrast)
                    assert actual["next"] == (mild(reference["next"]) if contrast == "mild" else reference["next"])
                    checks += 1
            off = probe(record, font, char=char, enabled=False)
            assert off == probe(record, font, char=char, variant="stock", enabled=False)
            checks += 1
    font = NOTO / "NotoSans-Regular.ttf"
    for flags in (1, 2, 0x400, 0x100, 0x400000):
        assert probe(record, font, flags=flags, mode=-1) == probe(
            record, font, flags=flags, mode=-1, variant="stock"), flags
        checks += 1
    for flags in (1 | 4, 0x400 | 4, 0x400000 | 4):
        candidate = probe(record, font, flags=flags, mode=-1)
        assert candidate == probe(record, font, flags=flags, mode=-1, variant="stock")
        assert candidate["loaded"]["format"] == 0x6f75746c, "Suppressed render returned a bitmap"
        checks += 1
    for path, char, flags in (
        ("/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf", "m", 0x28),
        (str(NOTO / "NotoColorEmoji.ttf"), "😀", 0x100000),
        ("/usr/share/fonts/X11/misc/6x13-ISO8859-1.pcf.gz", "m", 0)):
        assert probe(record, path, char=char, flags=flags) == probe(
            record, path, char=char, flags=flags, variant="stock")
        checks += 1
    normal = probe(record, font)
    immediate = probe(record, font, flags=0x2c)
    assert immediate["loaded"] == normal["rendered"][0]
    for dx in (0, 32):
        actual = probe(record, font, dx=dx)
        expected = probe(record, font, flags=0x20028, dx=dx, variant="stock")
        assert actual["rendered"] == [mild(expected["rendered"][0])] * 2
        assert actual["next"] == mild(expected["next"])
        checks += 1
    assert normal["rendered"][0]["pixel_mode"] == 2
    assert any(0 < a < 255 for a in bytes.fromhex(normal["rendered"][0]["mask"]))
    assert normal["rendered"][0]["mask"] != probe(record, font, variant="stock")["rendered"][0]["mask"]
    embedded, tricky = font_fixtures(normal["glyph"])
    bitmap = probe(record, embedded, flags=0, mode=-1, variant="stock")
    assert bitmap["fixed_sizes"] == 1 and bitmap["loaded"]["pixel_mode"] == 1
    assert bitmap["loaded"]["mask"] == "ff"*8
    reference = probe(record, embedded, flags=0x20028, variant="stock")
    candidate = probe(record, embedded, flags=0)
    assert candidate["rendered"][0] == mild(reference["rendered"][0])
    assert candidate["rendered"][0]["pixel_mode"] == 2
    assert probe(record, embedded, flags=4)["loaded"] == candidate["rendered"][0]
    gate_results = []
    for path, transform, remove in ((font, "quarter", False), (font, "diagonal", False),
                                    (tricky, "none", False), (font, "none", True)):
        expected = probe(record, path, flags=0x20028, variant="stock", transform=transform, remove_hinter=remove)
        actual = probe(record, path, flags=0, transform=transform, remove_hinter=remove)
        assert actual["rendered"][0] == mild(expected["rendered"][0])
        assert actual["tricky"] == (path == tricky) and actual["autohinter"] == (not remove)
        if transform == "quarter":
            wrong = probe(record, font, flags=0x20008, variant="stock", transform=transform)
        else:
            wrong = probe(record, font, flags=0x20028, variant="stock",
                          transform="deferred-diagonal" if transform == "diagonal" else "none")
        assert expected["rendered"][0]["mask"] != wrong["rendered"][0]["mask"], "Hinter contrast does not discriminate"
        gate_results.append(dict(tricky=actual["tricky"], autohinter=actual["autohinter"],
                                 transform=transform, wrong_mask_differs=True))
    checks += 7
    return dict(passed=checks + 3, scenarios=["S2", "S3", "S4", "S5", "S6"], hinter_gates=gate_results,
                synthetic_embedded_bitmap=True, synthetic_tricky_name=True)


class Marionette:
    """Test-only client for Mozilla's length-prefixed protocol, version 3."""
    def __init__(self, port):
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=15)
        self.stream = self.socket.makefile("rb")
        self.sequence = 0
        assert self.receive()["marionetteProtocol"] == 3
        self.command("WebDriver:NewSession", {})

    def receive(self):
        length = b""
        while True:
            byte = self.stream.read(1)
            if byte == b":":
                break
            assert byte and byte.isdigit() and len(length) < 10, "Invalid Marionette frame"
            length += byte
        data = self.stream.read(int(length))
        assert len(data) == int(length), "Incomplete Marionette frame"
        return json.loads(data)

    def command(self, name, params):
        self.sequence += 1
        data = json.dumps([0, self.sequence, name, params]).encode()
        self.socket.sendall(str(len(data)).encode() + b":" + data)
        kind, sequence, error, result = self.receive()
        assert kind == 1 and sequence == self.sequence and error is None, (name, error)
        return result

    def script(self, script):
        return self.command("WebDriver:ExecuteScript", dict(
            script=script, args=[], newSandbox=False, sandbox=None))["value"]

    def close(self):
        self.stream.close()
        self.socket.close()


def stop(child):
    if child.poll() is None:
        child.terminate()
    child.wait(timeout=20)


def screenshot(env, path):
    run([ROOT / "build/qt-kde-probe", "root", path], env=dict(env, QT_QPA_PLATFORM="xcb"))
    return Image.open(path).convert("RGB")


def raw_masks(path):
    return [json.loads(line.split("FONTREAL_MASK ", 1)[1])
            for line in path.read_text().splitlines() if line.startswith("FONTREAL_MASK ")]


def crop(image, measurement, rect):
    scale = measurement["dpr"]
    marker = next(n["rect"] for n in measurement["neighbors"] if n["id"] == "marker")
    if "_offset" not in measurement:
        points = [(i % image.width, i // image.width) for i, color in enumerate(image.getdata())
                  if color == (17, 91, 143)]
        assert points, "Actual fixture marker was not painted"
        measurement["_offset"] = (min(x for x, y in points) - round(marker["x"] * scale),
                                  min(y for x, y in points) - round(marker["y"] * scale))
    offset = measurement["_offset"]
    box = (math.floor(rect["x"] * scale) + offset[0], math.floor(rect["y"] * scale) + offset[1],
           math.ceil((rect["x"] + rect["width"]) * scale) + offset[0],
           math.ceil((rect["y"] + rect["height"]) * scale) + offset[1])
    return image.crop(box)


def blend(mask, foreground, background, linear):
    def decode(c):
        c /= 255
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    def encode(c):
        return round(255 * (12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055))
    result = []
    for alpha in mask:
        a = alpha / 255
        result.append(tuple(encode(decode(f) * a + decode(b) * (1-a)) if linear else
                            round(f*a + b*(1-a)) for f, b in zip(foreground, background)))
    return result


def fit(image, width, height, pixels):
    assert width and height and width <= image.width and height <= image.height
    best = None
    for y in range(image.height - height + 1):
        for x in range(image.width - width + 1):
            actual = list(image.crop((x, y, x + width, y + height)).getdata())
            error = max(abs(a-b) for p, q in zip(actual, pixels) for a, b in zip(p, q))
            if best is None or error < best["error"]:
                best = dict(error=error, x=x, y=y)
    return best


def browser_run(record, env, browser, mode, scale, pixels=15):
    directory = OUT / (f"{browser}-{mode}-{scale:g}" + (f"-{pixels}" if pixels != 15 else ""))
    directory.mkdir(exist_ok=True)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    log_path = directory / "browser.log"
    inherited_scope = "/usr/lib/floorp/floorp" if browser == "firefox" else "/usr/lib/firefox/firefox-bin"
    with log_path.open("w") as log:
        child = subprocess.Popen([sys.executable, str(ROOT / "tools/preview-browser.py"), mode,
            (ROOT / "tests/browser_masks.html").as_uri() + f"?size={pixels}#{mode}",
            "--browser", browser, "--scale", str(scale), "--trace", "--marionette-port", str(port)],
            env=dict(env, GDK_BACKEND="wayland", MOZ_ENABLE_WAYLAND="1", FONTREAL_FT_EXECUTABLE=inherited_scope),
            stdout=log, stderr=log, start_new_session=True)
        client = None
        try:
            for _ in range(200):
                assert child.poll() is None, log_path.read_text()[-3000:]
                if "Marionette\tINFO\tListening on port" in log_path.read_text():
                    break
                time.sleep(.1)
            else:
                raise AssertionError("Marionette did not start")
            client = Marionette(port)
            client.command("WebDriver:SetWindowRect", dict(x=0, y=0, width=1380, height=1240))
            for _ in range(100):
                if client.script("return !!window.fontreal && document.fonts.status === 'loaded'"):
                    break
                time.sleep(.1)
            else:
                raise AssertionError("Local fixture did not load")
            measured = client.script("return window.fontreal.measure()")
            assert len(measured["samples"]) == 24 and len(measured["cells"]) == 4
            assert abs(measured["dpr"] - scale) < .001
            assert measured["pixels"] == pixels
            image = None
            for _ in range(50):
                image = screenshot(env, directory / "screen.png")
                if (17, 91, 143) in set(image.getdata()):
                    break
                time.sleep(.1)
            else:
                raise AssertionError("Fixture not painted in actual window")
            identities = [json.loads(line.split("FONTREAL_BROWSER ", 1)[1])
                          for line in log_path.read_text().splitlines() if line.startswith("FONTREAL_BROWSER ")]
            assert len(identities) == 1
            identity = identities[0]
            assert not any(entry.startswith(b"FONTREAL_FT_EXECUTABLE=") for entry in
                           Path(f"/proc/{identity['pid']}/environ").read_bytes().split(b"\0")), "Preview retained caller process scope"
            assert Path(identity["profile"]).is_relative_to(WORK)
            assert Path(identity["library"]).resolve() == Path(record["libraries"][
                "stock" if mode.startswith("control") else "candidate"]["library"])
            maps = Path(f"/proc/{identity['pid']}/maps").read_text()
            assert identity["library"] in maps, "Launcher library did not reach browser"
            neighbors = {n["id"]: crop(image, measured, n["rect"]) for n in measured["neighbors"]}
            assert (53, 89, 131) in set(neighbors["solid"].getdata())
            rows = raw_masks(log_path)
            if not mode.startswith("control"):
                assert rows, "No final private-library raster evidence"
                seen = set()
                fonts = [("Noto Sans", NOTO / f"NotoSans-{s}.ttf") for s in STYLES]
                fonts += [("Hack", Path(f"/usr/share/fonts/truetype/hack/Hack-{s}.ttf")) for s in STYLES]
                fonts += [("DejaVu Sans", Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans" + suffix + ".ttf"))
                          for suffix in ("", "-Bold", "-Oblique", "-BoldOblique")]
                for family, font in fonts:
                    ref = probe(record, font, pixels=pixels*scale,
                                flags=0x20028, variant="stock")
                    expected = mild(ref["rendered"][0])
                    selected = [r for r in rows if bytes.fromhex(r["family"]).decode() == family
                                and bytes.fromhex(r["style"]).decode() == ref["style"]
                                and r["glyph"] == ref["glyph"]
                                and abs(r["y_scale"]*r["units"]/65536/64 - pixels*scale) < .02]
                    assert selected and all(all(r[k] == expected[k] for k in ("mask", "width", "height")) for r in selected), (browser, family, ref["style"], scale)
                    seen.add((family, ref["style"]))
                assert len(seen) == 12
            cells = {c["name"]: crop(image, measured, c["box"]) for c in measured["cells"]}
            reference = mild(probe(record, NOTO / "NotoSans-Regular.ttf", pixels=pixels*scale,
                                   flags=0x20028, variant="stock")["rendered"][0])
            errors = {}
            for name, bg in (("origin", (255,255,255)), ("phase-low", (255,255,255)),
                             ("phase-high", (255,255,255)), ("colored", (181,207,223))):
                errors[name] = {label: fit(cells[name], reference["width"], reference["height"],
                    blend(bytes.fromhex(reference["mask"]), (0,0,0), bg, linear))
                    for label, linear in (("encoded", False), ("actual-background-linear", True))}
            if mode == "encoded":
                assert max(errors[n]["encoded"]["error"] for n in errors) <= 1, errors
            if mode == "preblend":
                assert errors["origin"]["actual-background-linear"]["error"] <= 1, errors
            dark = next(s for s in measured["samples"] if s["family"] == "Noto Sans"
                        and s["style"] == "regular" and s["palette"] == "dark")
            dark_rect = dict(dark["rect"], width=60)
            errors["dark"] = {label: fit(crop(image, measured, dark_rect), reference["width"], reference["height"],
                blend(bytes.fromhex(reference["mask"]), (241,243,244), (32,33,36), linear))
                for label, linear in (("encoded", False), ("actual-background-linear", True))}
            if mode == "encoded":
                assert errors["dark"]["encoded"]["error"] <= 1, errors
            if mode in ("encoded", "preblend") and scale == 1:
                label = "encoded" if mode == "encoded" else "actual-background-linear"
                assert errors["phase-low"][label]["error"] <= 1 and errors["phase-high"][label]["error"] <= 1
                assert errors["phase-high"][label]["x"] == errors["phase-low"][label]["x"] + 1, errors
            # The unchanged marker anchors page geometry; the title/chrome stays a separate capture.
            chrome_height = measured["_offset"][1]
            assert 60 < chrome_height < image.height
            assert client.command("WebDriver:GetTitle", {})["value"] == f"Fontreal lmnogWVwv · {mode}"
            chrome = image.crop((0,0,image.width,chrome_height))
            assert len(set(chrome.getdata())) > 20, "Headed controls were not painted"
            chrome.save(directory / "chrome.png")
            client.script("window.fontreal.change(); return true")
            for _ in range(50):
                changed = screenshot(env, directory / "repaint.png")
                if (91,17,143) in set(changed.getdata()):
                    break
                time.sleep(.1)
            else:
                raise AssertionError("Later repaint did not reach final window")
            new_measurement = client.script("return window.fontreal.measure()")
            new_measurement["_offset"] = measured["_offset"]
            for sample in measured["samples"]:
                assert crop(changed, measured, sample["rect"]).tobytes() == crop(
                    image, measured, sample["rect"]).tobytes(), (browser, mode, "retained text repaint")
            for name in ("cff", "emoji", "solid"):
                rect = next(n["rect"] for n in new_measurement["neighbors"] if n["id"] == name)
                after = crop(changed, new_measurement, rect)
                if name != "cff":
                    assert after.tobytes() == neighbors[name].tobytes(), (name, "repaint")
                neighbors["repaint-" + name] = after
            result = dict(identity=identity, inherited_scope=inherited_scope, measure=measured, masks=len(rows), blend_errors=errors,
                          placement={c["name"]: c["rect"] for c in measured["cells"]},
                          chrome="captured through measured content origin; exact control-font coverage unresolved",
                          chrome_rect=[0, 0, image.width, chrome_height])
            (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            client.command("Marionette:Quit", {"flags": ["eForceQuit"]})
            client.close()
            client = None
            assert child.wait(timeout=20) == 0
            assert not Path(identity["state"]).exists(), "Disposable browser state was retained"
            print(f"PASS actual {browser} {mode} {scale:g}", flush=True)
            return result, neighbors, cells
        finally:
            if client:
                client.close()
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
                child.wait(timeout=25)


@contextmanager
def nested_display():
    with tempfile.TemporaryDirectory(prefix="browser-test-", dir=WORK) as temporary:
        state = Path(temporary)
        env = os.environ.copy()
        for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "WAYLAND_SOCKET", "WAYLAND_DISPLAY",
                    "FONTREAL_RENDERING", "FONTREAL_BLEND", "FONTREAL_CONTRAST",
                    "FONTREAL_FT_RENDERING", "FONTREAL_FT_CONTRAST", "FONTREAL_FT_EXECUTABLE",
                    "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QT_QPA_PLATFORM"):
            env.pop(key, None)
        for role in ("CONFIG", "CACHE", "DATA", "STATE", "RUNTIME"):
            path = state / role.lower()
            path.mkdir(mode=0o700)
            env["XDG_RUNTIME_DIR" if role == "RUNTIME" else f"XDG_{role}_HOME"] = str(path)
        read, write = os.pipe()
        with (state / "xvfb.log").open("w") as xlog, (OUT / "kwin.log").open("w") as klog:
            server = subprocess.Popen(["Xvfb", "-displayfd", str(write), "-screen", "0", "1600x1400x24", "-nolisten", "tcp"],
                                      env=env, pass_fds=(write,), stdout=xlog, stderr=xlog)
            os.close(write)
            kwin = None
            try:
                assert select.select([read], [], [], 10)[0]
                number = os.read(read, 80).decode().strip()
                assert number.isdecimal()
                env.update(DISPLAY=f":{number}", LIBGL_ALWAYS_SOFTWARE="1", KWIN_FORCE_OWN_QPA="1",
                           QT_NO_XDG_DESKTOP_PORTAL="1", WAYLAND_DISPLAY="fr-browser-test")
                kwin = subprocess.Popen(["dbus-run-session", "--", "/lib64/ld-linux-x86-64.so.2",
                    "/usr/bin/kwin_wayland", "--x11-display", env["DISPLAY"], "--width", "1400", "--height", "1300",
                    "--socket", "fr-browser-test", "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities"],
                    env=env, stdout=klog, stderr=klog)
                for _ in range(100):
                    if (state / "runtime/fr-browser-test").exists():
                        break
                    assert kwin.poll() is None
                    time.sleep(.1)
                else:
                    raise AssertionError("Nested display did not start")
                yield env
            finally:
                os.close(read)
                if kwin:
                    stop(kwin)
                stop(server)


def browser_checks(record):
    results = []
    with nested_display() as env:
        for browser in ("firefox", "floorp"):
            controls = {}
            for mode in ("control", "control-preblend", "encoded", "preblend"):
                result, neighbors, cells = browser_run(record, env, browser, mode, 1)
                results.append(result)
                blend_mode = "preblend" if mode.endswith("preblend") else "encoded"
                if mode.startswith("control"):
                    controls[blend_mode] = neighbors
                else:
                    for name in ("cff", "emoji", "solid", "repaint-cff", "repaint-emoji", "repaint-solid"):
                        assert neighbors[name].tobytes() == controls[blend_mode][name].tobytes(), (browser, mode, name)
            for scale in (1.25, 1.5):
                result, control_neighbors, _ = browser_run(record, env, browser, "control-preblend", scale)
                results.append(result)
                result, neighbors, _ = browser_run(record, env, browser, "preblend", scale)
                results.append(result)
                for name in ("cff", "emoji", "solid", "repaint-cff", "repaint-emoji", "repaint-solid"):
                    assert neighbors[name].tobytes() == control_neighbors[name].tobytes(), (browser, scale, name)
            result, _, _ = browser_run(record, env, browser, "preblend", 1, pixels=16)
            results.append(result)
        assert len(results) == 18
    return dict(scenarios=["S1", "S7", "S8", "S9", "S10"], runs=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", "build", "freetype", "isolation", "page", "chrome", "placement", "blend"), default="all")
    args = parser.parse_args()
    os.environ.pop("FONTREAL_FT_EXECUTABLE", None)
    OUT.mkdir(parents=True, exist_ok=True)
    before = protected()
    record_path = Path(run([sys.executable, ROOT / "tools/build-freetype.py", "--trace"]).stdout.splitlines()[-1])
    record = json.loads(record_path.read_text())
    cached = run([sys.executable, ROOT / "tools/build-freetype.py", "--trace"]).stdout.strip()
    assert cached == str(record_path), "Cache did not select the verified paired build"
    artifact = record_path.parent
    assert (artifact / "FTL.TXT").exists() and (artifact / "NOTICE").exists()
    for v in record["libraries"].values():
        assert digest(Path(v["library"])) == v["sha256"]
        assert "--with-harfbuzz=dynamic" in v["configure"]
        assert "[libfreetype.so.6]" in run(["readelf", "-d", v["library"]]).stdout
    flags = shlex.split(run(["pkg-config", "--cflags", "--libs", "Qt6Core"]).stdout)
    run(["c++", "-std=c++17", "-fPIC", ROOT / "tests/freetype_mask_probe.cpp",
         "-I" + str(artifact / "headers/usr/include/freetype2"),
         "-L" + str(Path(record["libraries"]["stock"]["library"]).parent), "-lfreetype", *flags,
         "-o", WORK / "mask-probe"])
    report = dict(build=str(record_path), case=args.case, build_scenario="S11")
    if args.case in ("all", "freetype"):
        report["freetype"] = freetype(record)
    if args.case not in ("build", "freetype"):
        report["browser"] = browser_checks(record)
    assert before == protected(), "Protected host state changed"
    (OUT / f"{args.case}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS {args.case}: {OUT / (args.case + '.json')}")


if __name__ == "__main__":
    main()
