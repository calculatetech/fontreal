#!/usr/bin/env python3
"""Verify and export native B/D/E/F outline-axis comparisons; no browser changes."""
import argparse
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = (ROOT / "build/freetype-native/stroke-axis").resolve()
OUT = (ROOT / "results/browser-stroke-axis").resolve()
SIZES = (12, 15, 18.75, 22.5)
TEXT = "Hllmnw 035 568 AV"
FONTS = [("Noto Sans " + s, Path("/usr/share/fonts/truetype/noto") / f"NotoSans-{s}.ttf")
         for s in ("Regular", "Bold", "Italic", "BoldItalic")]
FONTS += [("Lato " + s, Path("/usr/share/fonts/truetype/lato") / f"Lato-{s}.ttf")
          for s in ("Light", "Regular")]
FONTS += [("IBM Plex Sans " + s, Path("/usr/share/fonts/truetype/ibm-plex") / f"IBMPlexSans-{s}.ttf")
          for s in ("Light", "Bold")]
FONTS += [("Hack Regular", Path("/usr/share/fonts/truetype/hack/Hack-Regular.ttf"))]
MODES = {"A": (0x20028, "none", False), "B": (0x10028, "none", True),
         "D": (0x20028, "expand-d", False), "E": (0x10028, "axis-mono", True),
         "F": (0x10028, "axis-d", True)}
LABELS = {"B": "B: Light hints + darkening", "D": "D: Mono + X/Y expansion",
          "E": "E: Mono X / B Y", "F": "F: D X / B Y"}
BITMAP = ("width", "height", "left", "top", "mask")


def run(command, **kwargs):
    kwargs.setdefault("env", dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(WORK/"tmp")))
    return subprocess.run(list(map(str, command)), check=True, text=True,
                          capture_output=True, timeout=180, **kwargs)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Vector(C.Structure):
    _fields_ = [("x", C.c_long), ("y", C.c_long)]


class Outline(C.Structure):
    _fields_ = [("n_contours", C.c_short), ("n_points", C.c_short),
                ("points", C.POINTER(Vector)), ("tags", C.POINTER(C.c_char)),
                ("contours", C.POINTER(C.c_short)), ("flags", C.c_int)]


class Bitmap(C.Structure):
    _fields_ = [("rows", C.c_uint), ("width", C.c_uint), ("pitch", C.c_int),
                ("buffer", C.POINTER(C.c_ubyte)), ("num_grays", C.c_ushort),
                ("pixel_mode", C.c_ubyte), ("palette_mode", C.c_ubyte), ("palette", C.c_void_p)]


class Oracle:
    """Separate public-native expansion and raster calls, without candidate assembly."""
    def __init__(self, library):
        self.ft = C.CDLL(str(library))
        self.handle = C.c_void_p()
        self.ft.FT_Init_FreeType.argtypes = [C.POINTER(C.c_void_p)]
        self.ft.FT_Done_FreeType.argtypes = [C.c_void_p]
        self.ft.FT_Outline_EmboldenXY.argtypes = [C.POINTER(Outline), C.c_long, C.c_long]
        self.ft.FT_Outline_Get_Bitmap.argtypes = [C.c_void_p, C.POINTER(Outline), C.POINTER(Bitmap)]
        assert self.ft.FT_Init_FreeType(C.byref(self.handle)) == 0

    def outline(self, snapshot, dx=0, dy=0):
        values = snapshot["outline"]
        points = (Vector * len(values))(*(Vector(int(x)+dx, int(y)+dy) for x, y, tag in values))
        tags = (C.c_char * len(values))(*(bytes([tag]) for x, y, tag in values))
        ends = (C.c_short * len(snapshot["contours"]))(*snapshot["contours"])
        return Outline(len(ends), len(points), points, tags, ends, 0)

    def expand(self, snapshot):
        outline = self.outline(snapshot)
        assert self.ft.FT_Outline_EmboldenXY(C.byref(outline), 8, 16) == 0
        result = dict(snapshot)
        result["outline"] = [[p.x, p.y, snapshot["outline"][i][2]]
                             for i, p in enumerate(outline.points[:outline.n_points])]
        return result

    def raster(self, snapshot, shift=(0, 0)):
        outline = self.outline(snapshot, *shift)
        if not outline.n_points:
            return dict(width=0, height=0, left=0, top=0, mask="")
        points = outline.points[:outline.n_points]
        left = min(p.x for p in points) // 64
        bottom = min(p.y for p in points) // 64
        right = -(-max(p.x for p in points) // 64)
        top = -(-max(p.y for p in points) // 64)
        width, height = right-left, top-bottom
        for p in points:
            p.x -= left*64
            p.y -= bottom*64
        pixels = (C.c_ubyte * (width*height))()
        bitmap = Bitmap(height, width, width, pixels, 256, 2, 0, None)
        assert self.ft.FT_Outline_Get_Bitmap(self.handle, C.byref(outline), C.byref(bitmap)) == 0
        return dict(width=width, height=height, left=left, top=top, mask=bytes(pixels).hex())

    def close(self):
        self.ft.FT_Done_FreeType(self.handle)


def bitmap(snapshot):
    return {key: snapshot[key] for key in BITMAP}


def image(snapshot):
    return Image.frombytes("L", (snapshot["width"], snapshot["height"]),
                           bytes.fromhex(snapshot["mask"]))


def compose(text, origins, glyphs, bounds):
    left, top, right, bottom = bounds
    width, height = right-left, bottom-top
    pixels = [0] * (width*height)
    independent = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    placements = []
    for index, (char, origin) in enumerate(zip(text, origins)):
        glyph = glyphs[char]
        x, y = int(origin)//64 + glyph["left"] - left, -glyph["top"] - top
        w, h = glyph["width"], glyph["height"]
        assert 0 <= x <= width-w and 0 <= y <= height-h
        placements.append(dict(index=index, char=char, origin=origin, rectangle=[x, y, w, h]))
        if not w or not h:
            assert not glyph["mask"]
            continue
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        overlay.putalpha(image(glyph))
        independent.alpha_composite(overlay, (x, y))
        for i, alpha in enumerate(bytes.fromhex(glyph["mask"])):
            at = (y+i//w)*width + x+i%w
            pixels[at] = alpha + (pixels[at]*(255-alpha)+127)//255
    result = Image.frombytes("L", (width, height), bytes(pixels))
    assert result.tobytes() == independent.getchannel("A").tobytes()
    assert [p["index"] for p in placements] == list(range(len(text)))
    assert [p["char"] for p in placements] == list(text)
    return result, placements


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    caller_environment = dict(os.environ)
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("tmp", "cache"):
        (WORK/name).mkdir(exist_ok=True)
    assert WORK.is_relative_to((ROOT/"build").resolve()) and OUT.is_relative_to((ROOT/"results").resolve())
    record_path = Path(run([sys.executable, ROOT/"tools/build-freetype.py"]).stdout.splitlines()[-1])
    record = json.loads(record_path.read_text())
    library = Path(record["libraries"]["stock"]["library"])
    assert sha(library) == record["libraries"]["stock"]["sha256"]
    assert all(path.is_file() for name, path in FONTS)
    flags = shlex.split(run(["pkg-config", "--cflags", "--libs", "Qt6Core"]).stdout)
    probe_path = WORK/"probe"
    run(["c++", "-std=c++17", "-fPIC", ROOT/"tests/freetype_mask_probe.cpp",
         "-I"+str(record_path.parent/"headers/usr/include/freetype2"),
         "-L"+str(library.parent), "-lfreetype", *flags, "-o", probe_path])
    env = {k: v for k, v in os.environ.items() if not k.startswith("FONTREAL_FT_")}
    env.update(LD_LIBRARY_PATH=str(library.parent), QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(WORK/"tmp"), XDG_CACHE_HOME=str(WORK/"cache"),
               FREETYPE_PROPERTIES="autofitter:no-stem-darkening=1")
    oracle = Oracle(library)
    cache = {}

    def probe(font, size, char, mode, shift=(0, 0)):
        key = (font.name, size, char, mode, *shift)
        if key not in cache:
            load, transform, darkening = MODES[mode]
            scoped = dict(env, FREETYPE_PROPERTIES="autofitter:no-stem-darkening=" + ("0" if darkening else "1"))
            target = WORK/"probe.json"
            run([probe_path, font, size, hex(load), ord(char), 0, *shift, 2, target, transform, 0], env=scoped)
            cache[key] = json.loads(target.read_text())
            assert cache[key]["rendered"][0] == cache[key]["rendered"][1]
        return cache[key]

    def verify(font, size, char, shift=(0, 0)):
        a = probe(font, size, char, "A")["loaded"]
        b = probe(font, size, char, "B")["loaded"]
        assert a["contours"] == b["contours"]
        assert [p[2] for p in a["outline"]] == [p[2] for p in b["outline"]]
        d = oracle.expand(a)
        expected = {"A": a, "B": b, "D": d}
        for mode, source in (("E", a), ("F", d)):
            expected[mode] = dict(b, outline=[[x[0], y[1], y[2]] for x, y in zip(source["outline"], b["outline"])])
        actual = {}
        for mode in MODES:
            value = probe(font, size, char, mode, shift)
            loaded = value["loaded"]
            for key in ("outline", "contours", "advance", "metrics"):
                assert loaded[key] == expected[mode][key], (font.name, size, char, mode, key)
            actual[mode] = value["rendered"][0]
            assert bitmap(actual[mode]) == oracle.raster(expected[mode], shift), (font.name, size, char, mode, "raster")
            assert actual[mode]["pixel_mode"] == 2 and actual[mode]["grays"] == 256
            assert value["next"] == probe(font, size, "g", mode)["rendered"][0], (mode, "next glyph")
        return actual

    expected_keys = {(name, size) for name, font in FONTS for size in SIZES}
    rows = []
    raw_records = []
    sheets = []
    label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    heading = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    try:
        with tempfile.TemporaryDirectory(prefix="native-", dir=WORK) as scratch:
            def words(name, font, size, text, serial):
                target = Path(scratch)/str(serial)
                run([ROOT/"build/fontreal", "--font", font, "--size", size, "--phase", 0,
                     "--edges", "--text", text, "--inspect", "5", "--export", target], env=env)
                meta = json.loads((target/"metrics.json").read_text())
                origins = meta["modes"][0]["origins_26_6"]
                assert len(origins) == len(text) and all(x % 64 == 0 for x in origins)
                glyphs = {mode: {} for mode in MODES}
                for char in sorted(set(text) | {"g"}):
                    for mode, value in verify(font, size, char).items():
                        glyphs[mode][char] = value
                native = Image.open(target/"auto-gray-coverage.png").convert("L")
                boxes = [(-meta["left_padding"], -meta["baseline"],
                          native.width-meta["left_padding"], native.height-meta["baseline"])]
                for mode in MODES:
                    for char, origin in zip(text, origins):
                        g = glyphs[mode][char]
                        x, y = int(origin)//64+g["left"], -g["top"]
                        boxes.append((x, y, x+g["width"], y+g["height"]))
                bounds = (min(b[0] for b in boxes)-4, min(b[1] for b in boxes)-4,
                          max(b[2] for b in boxes)+4, max(b[3] for b in boxes)+4)
                images, placements = {}, {}
                for mode in MODES:
                    images[mode], placements[mode] = compose(text, origins, glyphs[mode], bounds)
                reference = Image.new("L", images["A"].size, 0)
                reference.paste(native, (-meta["left_padding"]-bounds[0], -meta["baseline"]-bounds[1]))
                assert reference.tobytes() == images["A"].tobytes(), (name, size, text, "native word")
                raw_records.append(dict(font=name, font_file=font.name, font_sha256=sha(font), size_px=size,
                    text=text, origins_26_6=origins, bounds=bounds, placements=placements,
                    glyphs={mode: {c: bitmap(g) for c, g in gs.items()} for mode, gs in glyphs.items()}))
                return images, glyphs

            for size in SIZES:
                cases = []
                for number, (name, font) in enumerate(FONTS):
                    images, glyphs = words(name, font, size, TEXT, f"{size:g}-{number}")
                    for mode, mask in images.items():
                        destination = OUT/"raw"/f"{size:g}"/f"{number:02}-{mode}.png"
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        mask.save(destination)
                    rows.append(dict(font=name, font_sha256=sha(font), size_px=size,
                                     stem_profiles={mode: list(bytes.fromhex(glyphs[mode]["l"]["mask"])[
                                         (glyphs[mode]["l"]["height"]//2)*glyphs[mode]["l"]["width"]:
                                         (glyphs[mode]["l"]["height"]//2+1)*glyphs[mode]["l"]["width"]]) for mode in LABELS}))
                    cases.append((name, images, glyphs))
                zoom_y = max(54, max(im.height for _, ims, _ in cases for im in ims.values())+24)
                row_height = zoom_y+max(g["height"]*4 for _, _, gs in cases for mode in LABELS for c, g in gs[mode].items() if c in "l35")+10
                for dark in (False, True):
                    bg, fg = ((0, 255) if dark else (255, 0))
                    lut = []
                    for alpha in range(256):
                        value = alpha/255 if dark else 1-alpha/255
                        value = 12.92*value if value <= .0031308 else 1.055*value**(1/2.4)-.055
                        lut.append(max(0, min(255, math.floor(value*255+.5))))
                    sheet = Image.new("RGB", (1840, 92+row_height*len(cases)), (bg,)*3)
                    draw = ImageDraw.Draw(sheet)
                    draw.text((12, 10), f"{size:g} device px | native text | l, 3, 5 at exact 4x | linear-light blend", font=heading, fill=(fg,)*3)
                    draw.text((12, 34), "Diagnostic coordinate mixing, not a browser preset. Same fonts and origins; no contrast clipping. Italic X fitting remains limited.", font=label, fill=(fg,)*3)
                    crops = []
                    for col, (mode, title) in enumerate(LABELS.items()):
                        x = col*460
                        draw.text((x+12, 66), title, font=heading, fill=(fg,)*3)
                        for number, (name, images, glyphs) in enumerate(cases):
                            y = 92+number*row_height
                            draw.text((x+12, y), name, font=label, fill=(fg,)*3)
                            native = images[mode].point(lut).convert("RGB")
                            expected_native = Image.frombytes("RGB", images[mode].size, bytes(
                                channel for a in images[mode].tobytes() for channel in (lut[a],)*3))
                            assert native.size == images[mode].size and native.tobytes() == expected_native.tobytes()
                            assert native.width <= 436 and native.height+16 < zoom_y
                            sheet.paste(native, (x+12, y+16))
                            crops.append(((x+12, y+16), expected_native))
                            for i, char in enumerate("l35"):
                                detail = image(glyphs[mode][char]).point(lut).convert("RGB")
                                zoom = detail.resize((detail.width*4, detail.height*4), Image.Resampling.NEAREST)
                                assert zoom.width <= 66 and zoom.height+zoom_y < row_height
                                position = (x+18+i*82, y+zoom_y)
                                sheet.paste(zoom, position)
                                crops.append((position, zoom))
                                assert all(zoom.getpixel((xx*4+dx, yy*4+dy)) == detail.getpixel((xx, yy))
                                           for yy in range(detail.height) for xx in range(detail.width) for dy in range(4) for dx in range(4))
                    filename = f"{size:g}px-axis-{'dark' if dark else 'light'}.png"
                    sheet.save(OUT/filename)
                    with Image.open(OUT/filename) as saved:
                        for (x, y), expected in crops:
                            assert saved.crop((x, y, x+expected.width, y+expected.height)).tobytes() == expected.tobytes()
                    sheets.append(dict(file=filename, sha256=sha(OUT/filename), dimensions=list(sheet.size)))
                print(f"PASS {size:g}px: all nine faces, independent axes/rasters/lifecycle and saved image pixels", flush=True)
            for serial, text in enumerate(("l", "ll3")):
                words("Noto Sans Italic", FONTS[2][1], 15, text, f"occurrences-{serial}")
            for char in "lHm35":
                verify(FONTS[0][1], 15, char, (17, -9))
            assert probe(FONTS[0][1], 15, "l", "B")["rendered"] != probe(FONTS[0][1], 15, "l", "E")["rendered"]
            assert probe(FONTS[0][1], 15, "l", "E")["rendered"] != probe(FONTS[0][1], 15, "l", "F")["rendered"]
        assert {(row["font"], row["size_px"]) for row in rows} == expected_keys and len(rows) == len(expected_keys)
        assert {s["file"] for s in sheets} == {f"{size:g}px-axis-{palette}.png" for size in SIZES for palette in ("light", "dark")}
        assert os.environ == caller_environment
        report = dict(kind="native component diagnostic; no browser or layout claim", text=TEXT,
            conditions=rows, modes={key: dict(load_flags=hex(v[0]), transform=v[1], native_darkening=v[2]) for key, v in MODES.items()},
            library_sha256=sha(library), source_version=record["spec"]["source"],
            probe_source_sha256=sha(ROOT/"tests/freetype_mask_probe.cpp"),
            runner_source_sha256=sha(Path(__file__)), sheets=sheets,
            checks=["independent ordinary A/B raster calibration", "exact D expansion and E/F coordinate provenance",
                    "native masks equal independently assembled/rasterized outlines", "translated raster at (17,-9)/64",
                    "repeated render and next glyph", "single/repeated/mixed word occurrences and complete ink bounds",
                    "exact condition and sheet key sets", "reopened native and exact 4x image crops"],
            limits=["No installed rendering change", "No browser shaping/layout/composition qualification",
                    "Axis mixing can change curves and apparent weight", "Italic X fitting is not universal snapping"])
        (OUT/"all.json").write_text(json.dumps(report, indent=2)+"\n")
        (OUT/"words.json").write_text(json.dumps(raw_records, indent=2)+"\n")
        (OUT/"probes.json").write_text(json.dumps([dict(key=list(key), result=value) for key, value in cache.items()], indent=2)+"\n")
        (WORK/"probe.json").unlink()
        print(f"PASS stroke axis study: {len(rows)} conditions, {len(sheets)} sheets; {OUT}")
    finally:
        oracle.close()


if __name__ == "__main__":
    main()
