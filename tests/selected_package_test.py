#!/usr/bin/env python3
"""Check selected native FreeType through its actual public load/render API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

from selected_profile_test import expected_mask

ROOT = Path(__file__).resolve().parents[1]


def run(library, stock, output, fonts, foreign=False):
    fonts = [Path(font) for font in fonts]
    output.mkdir(parents=True)
    source = ROOT / "tests/selected_profile_probe.cpp"
    flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt6Core", "freetype2"], text=True))
    binary = output / "probe"
    subprocess.run(["c++", "-std=c++17", "-O2", "-fPIC", str(source), *flags, "-o", str(binary)], check=True)
    jobs = [dict(id=f"face-{i}", file=str(font), pixels=44/3, flags=0x8008, sizeReturn=True)
            for i, font in enumerate(fonts)]
    config = output / "jobs.json"
    config.write_text(json.dumps(jobs))
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(("FONTREAL_", "QT_")) and k not in ("LD_LIBRARY_PATH", "LD_PRELOAD", "FREETYPE_PROPERTIES")}
    def probe(role, provider, typed=None, scoped=False, properties=True):
        folder = output / role
        env = dict(environment, LD_LIBRARY_PATH=str(provider.parent), FONTREAL_FT_RENDERING="1" if scoped else "0",
                   FONTREAL_FT_CONTRAST="weighted", FONTREAL_FT_EXECUTABLE=str(binary.resolve()),
                   FONTREAL_TEST_QT_DRIVER_PROPERTIES="1" if properties else "0",
                   FREETYPE_PROPERTIES="autofitter:fontreal-selected-v1=1")
        if typed is not None:
            env["FONTREAL_TEST_SELECTED_PROPERTY"] = "1" if typed else "0"
        subprocess.run([str(binary), str(config), str(folder)], env=env, check=True)
        maps = (folder / "maps.txt").read_text()
        loaded = {Path(line.split()[-1]).resolve() for line in maps.splitlines() if "/libfreetype.so." in line}
        assert loaded == {provider.resolve()}, (role, loaded, provider)
        return {job["id"]: json.loads((folder / (job["id"] + ".json")).read_text()) for job in jobs}
    raw = probe("independent-qt-properties", stock)
    fresh = probe("independent-defaults", stock, properties=False)
    assert any(a["rendered"]["mask"] != b["rendered"]["mask"] for key in raw
               for a, b in zip(raw[key]["glyphs"], fresh[key]["glyphs"], strict=True)), "Missing CFF driver-property discriminator"
    variants = {"neither": probe("neither", library, False), "typed": probe("typed", library, True),
                "environment": probe("environment", library, False, True), "both": probe("both", library, True, True)}
    changed = twice_different = count = 0
    def selected(snapshot):
        mask = bytes.fromhex(snapshot["mask"])
        return dict(snapshot, mask=bytes(expected_mask(mask, snapshot["width"]) if mask else mask).hex())
    for job in jobs:
        key = job["id"]
        assert {row["codepoint"] for row in raw[key]["glyphs"]} == set(range(32, 127))
        assert len(raw[key]["glyphs"]) == 95
        for role, records in variants.items():
            assert records[key]["capability"] == dict(selected=role in ("typed", "both"), otherDefaultOff=True, typedOnly=True)
            assert len(records[key]["glyphs"]) == 95
            for original, actual in zip(raw[key]["glyphs"], records[key]["glyphs"], strict=True):
                assert original["codepoint"] == actual["codepoint"] and original["glyph"] == actual["glyph"]
                assert actual["loaded"] == original["loaded"], (role, key, original["codepoint"], "geometry")
                expected = original["rendered"] if role == "neither" else selected(original["rendered"])
                for entry in ("rendered", "repeated", "immediate", "character"):
                    assert actual[entry] == expected, (role, key, original["codepoint"], entry)
                if role == "both":
                    changed += expected != original["rendered"]
                    twice_different += selected(expected) != expected
                    count += 1
            original_steps = raw[key]["sizeReturn"]
            actual_steps = records[key]["sizeReturn"]
            assert len(original_steps) == len(actual_steps) == 3
            for original, actual in zip(original_steps, actual_steps, strict=True):
                assert actual["pixels"] == original["pixels"] and actual["loaded"] == original["loaded"]
                assert actual["rendered"] == (original["rendered"] if role == "neither" else selected(original["rendered"]))
            assert actual_steps[0] == actual_steps[2]
    assert changed and twice_different
    gate_probe = output / "gate-probe"
    subprocess.run(["c++", "-std=c++17", "-O2", "-fPIC", str(ROOT / "tests/freetype_mask_probe.cpp"),
                    *flags, "-o", str(gate_probe)], check=True)
    gates = []
    gate_cases = [(fonts[0], ord('n'), 44/3, value, -1) for value in (1, 2, 0x400, 0x100, 0x400000, 1|4, 2|4, 0x400|4, 0x400000|4)]
    gate_cases += [(Path("/usr/share/fonts/type1/urw-base35/NimbusSans-Regular.t1"), ord('m'), 15, 0x28, 0),
                   (Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"), ord('😀'), 109, 0x100000, 0),
                   (Path("/usr/share/fonts/X11/misc/6x13-ISO8859-1.pcf.gz"), ord('m'), 13, 0, 0)]
    for i, (font, character, pixels, load, mode) in enumerate(gate_cases):
        observations = []
        for role, provider in (("stock", stock), ("typed", library)):
            path = output / f"gate-{i}-{role}.json"
            env = dict(environment, LD_LIBRARY_PATH=str(provider.parent), FONTREAL_FT_RENDERING="0")
            if role == "typed": env["FONTREAL_TEST_SELECTED_PROPERTY"] = "1"
            subprocess.run([str(gate_probe), str(font), str(pixels), hex(load), str(character), str(mode),
                            "0", "0", "2", str(path), "none", "0"], env=env, check=True)
            observations.append(json.loads(path.read_text()))
        assert observations[0] == observations[1], (font, load)
        gates.append(dict(font=font.name, codepoint=character, flags=load, passed=True))
    links = []
    if foreign:
        link_source = ROOT / "tests/freetype_selected_link_probe.c"
        includes = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "freetype2"], text=True))
        dependencies = shlex.split(subprocess.check_output(["pkg-config", "--static", "--libs", "freetype2"], text=True))
        assert "-lstdc++" in dependencies and "-lm" in dependencies
        expected = next(row["rendered"] for row in variants["typed"][jobs[0]["id"]]["glyphs"] if row["codepoint"] == ord('n'))
        for role, compiler, linker in (
            ("static", "cc", ["/usr/lib/x86_64-linux-gnu/libfreetype.a", *[flag for flag in dependencies if flag != "-lfreetype"]]),
            ("i386", "i686-linux-gnu-gcc", ["/usr/lib/i386-linux-gnu/libfreetype.so.6", "-lm"])):
            program = output / ("link-" + role)
            subprocess.run([compiler, str(link_source), *includes, *linker, "-o", str(program)], check=True)
            dynamic = subprocess.check_output(["readelf", "-d", str(program)], text=True)
            if role == "static":
                assert "libfreetype.so" not in dynamic and "libstdc++.so" in dynamic
            else:
                assert "ELF32" in subprocess.check_output(["readelf", "-h", str(program)], text=True)
            text = subprocess.check_output([str(program), str(fonts[0]), str(jobs[0]["pixels"]), str(ord('n'))], text=True).splitlines()
            assert list(map(int, text[0].split())) == [expected[key] for key in ("width", "height", "left", "top")]
            assert text[1] == expected["mask"], role
            links.append(dict(role=role, passed=True, binary_sha256=hashlib.sha256(program.read_bytes()).hexdigest()))
    result = dict(passed=True, glyphs=count, changed=changed, once_twice_discriminators=twice_different,
                  selectors=list(variants), qt_driver_discriminator=True, gates=gates, links=links,
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("stock", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("fonts", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.library.resolve(), args.stock.resolve(), args.output.resolve(), args.fonts)))
