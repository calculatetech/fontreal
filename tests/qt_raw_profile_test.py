#!/usr/bin/env python3
"""Verify the forced native Qt profile with independent nearest/raw references."""
import argparse
import json
import math
import os
import re
from pathlib import Path
import subprocess
import tempfile

import browser_live_recipe_test as recipe
import kde_paths_test as kde
from encoded_refinement_test import NAMES, matrix

ROOT = recipe.ROOT
OUT = ROOT / "results/qt-raw-profile"


def matrix_cases(probe, fonts, mode="raw"):
    paths = list(fonts.values())
    cases = []
    for point in range(8, 17):
        for start in range(0, len(paths), 3):
            selected = paths[start:start+3]
            while len(selected) < 3:
                selected.append(selected[-1])
            case = probe(point, selected)
            assert case["mode"] == mode and case["requestedSize"] == point and case["sizeUnit"] == "pt"
            assert case["checkedImages"] == sum(f["textCases"] * 6 for f in case["fonts"])
            assert len(case["masks"]) == sum(len(f["testGlyphs"]) for f in case["fonts"])
            for font in case["fonts"]:
                if font["path"] == fonts["Noto Sans CJK JP"]:
                    assert font["testGlyphs"].endswith("漢国文") and font["faceIndex"] == 0
            cases.append(case)
        print(f"PASS {mode} Qt {point}pt", flush=True)
    actual = {(font["path"], case["requestedSize"]) for case in cases for font in case["fonts"]}
    assert actual == {(path, point) for path in paths for point in range(8, 17)}
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, default=ROOT / "build/qt-native-probe")
    parser.add_argument("--variable-font", type=Path, required=True)
    parser.add_argument("--profile", choices=("nearest", "selected"), default="nearest")
    args = parser.parse_args()
    global OUT
    if args.profile == "selected":
        OUT = ROOT / "results/qt-selected-profile"
    OUT.mkdir(parents=True, exist_ok=True)
    record, _, nearest = recipe.prepare()
    from raw_coverage_test import input_rows
    rows = input_rows(record)
    conditions = matrix(rows, names=NAMES + ["Arial Regular"] + list(recipe.CFF_FONTS))
    fonts = {row["label"]: row["font_path"] for row in conditions.values()}
    assert len(fonts) == 28 and len(conditions) == 252
    source = json.loads((recipe.BUILD / "reference.json").read_text())
    assert source["sha256"] == recipe.sha(nearest)
    cases = []
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_FONT_DPI="96", QT_SCALE_FACTOR="1",
               FONTREAL_RENDERING="1", FONTREAL_FITTING="nearest", FONTREAL_BLEND="encoded",
               FONTREAL_CONTRAST="none", FONTREAL_TEST_REFERENCE_FREETYPE=str(nearest.resolve()))
    for key in ("FONTREAL_FT_RENDERING", "FONTREAL_FT_CONTRAST", "FONTREAL_FT_EXECUTABLE"):
        env.pop(key, None)
    if args.profile == "selected":
        env.update(FONTREAL_FITTING="native", FONTREAL_CONTRAST="weighted",
                   FONTREAL_TEST_REFERENCE_FREETYPE=record["libraries"]["stock"]["library"],
                   FONTREAL_TEST_SELECTED_REFERENCE=str(ROOT / "tests/selected_reference.py"))
    paths = list(fonts.values())
    def probe(selected_env, point=16, mode="raw", selected=None):
        selected = selected or paths[:3]
        if args.profile == "selected" and mode == "raw":
            mode = "selected"
        result = subprocess.run([str(args.probe), mode, "none", str(point), "1", *selected, str(OUT)],
                                env=selected_env, text=True, capture_output=True, check=True)
        return json.loads(result.stdout)
    cases = matrix_cases(lambda point, selected: probe(env, point, selected=selected), fonts,
                         "selected" if args.profile == "selected" else "raw")
    selected = [fonts[name] for name in ("Noto Sans Regular", "Nimbus Sans Regular", "URW Bookman Light")]
    opposing = []
    for name, value_type, value in (("antialias", "bool", "false"), ("hinting", "bool", "false"),
                                   ("hintstyle", "const", "hintslight"), ("rgba", "const", "rgb")):
        with tempfile.TemporaryDirectory(prefix="fontconfig-", dir=OUT) as directory:
            config = Path(directory) / "fonts.conf"
            def configuration(changed):
                settings = {"antialias": ("bool", "true"), "hinting": ("bool", "true"),
                            "hintstyle": ("const", "hintfull"), "rgba": ("const", "none")}
                settings.update(changed)
                edits = "".join(f'<edit name="{key}" mode="assign"><{kind}>{value}</{kind}></edit>'
                                for key, (kind, value) in settings.items())
                return f'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig><include>/etc/fonts/fonts.conf</include><match target="font">
{edits}</match></fontconfig>'''
            config.write_text(configuration({}))
            conflict = dict(env, FONTCONFIG_FILE=str(config))
            stock = dict(conflict, FONTREAL_RENDERING="0", FONTREAL_FITTING="")
            stock_default = probe(stock, mode="raw-stock", selected=selected)
            baseline = probe(conflict, selected=selected)
            changed = {name: (value_type, value)}
            if name == "hinting":
                changed["hintstyle"] = ("const", "hintnone")
            config.write_text(configuration(changed))
            got = probe(conflict, selected=selected)
            assert got["masks"] == baseline["masks"], name
            if name in ("antialias", "rgba"):
                assert got["images"] == baseline["images"], name
            control = probe(stock, mode="raw-stock", selected=selected)
            assert control["images"] != got["images"], name
            assert control["images"] != stock_default["images"], (name, "Stock fixture did not change")
            opposing.append(dict(setting=name, forced=got, disabled=control))
    # A scoped private browser provider must also support the ordinary KDE profile.
    helper_path = str(Path(record["libraries"]["candidate"]["library"]).parent)
    if env.get("LD_LIBRARY_PATH"):
        helper_path += ":" + env["LD_LIBRARY_PATH"]
    helper = dict(env, LD_LIBRARY_PATH=helper_path,
                  FONTREAL_FT_RENDERING="1", FONTREAL_FT_CONTRAST="weighted" if args.profile == "selected" else "raw",
                  FONTREAL_FT_EXECUTABLE="/usr/bin/firefox:/usr/lib/firefox/firefox-bin")
    normal, inherited = probe(env, selected=selected), probe(helper, selected=selected)
    assert normal["masks"] == inherited["masks"] and normal["images"] == inherited["images"]
    assert record["libraries"]["candidate"]["library"] in inherited["freetypeLibraries"]
    _, older = recipe.v1_provider(record)
    excluded = probe(dict(env, FONTREAL_TEST_EXCLUSIONS="1"), point=12, selected=selected)
    excluded_stock = probe(dict(env, FONTREAL_TEST_EXCLUSIONS="1", FONTREAL_RENDERING="0", FONTREAL_FITTING=""),
                           point=12, mode="raw-stock", selected=selected)
    assert excluded["masks"] != excluded_stock["masks"]
    for actual, stock in zip(excluded["exclusions"], excluded_stock["exclusions"], strict=True):
        assert actual["outlines"] == stock["outlines"] and actual["designAdvances"] == stock["designAdvances"]
        # Qt rounds each shaped advance when the selected profile disables subpixel positions.
        origin = 0
        expected_positions = []
        for advance in actual["designAdvances"]:
            expected_positions.append([origin, math.floor(stock["designPositions"][0][1] + .5)])
            origin += math.floor(advance + .5)
        assert actual["designPositions"] == expected_positions
        assert actual["designAdvances"] != actual["hintedAdvances"]
    fallbacks = []
    providers = [older, record["libraries"]["stock"]]
    nearest_only = recipe.v1_provider(record, version=2)[1] if args.profile == "selected" else None
    if nearest_only:
        providers.append(nearest_only)
    for provider in providers:
        assert recipe.sha(Path(provider["library"])) == provider["sha256"]
        provider_path = str(Path(provider["library"]).parent) + ":" + env.get("LD_LIBRARY_PATH", "")
        fallback_env = dict(env, LD_LIBRARY_PATH=provider_path)
        actual_fallback = probe(fallback_env, mode="raw-stock", selected=selected)
        disabled = probe(dict(fallback_env, FONTREAL_RENDERING="0", FONTREAL_FITTING=""), mode="raw-stock", selected=selected)
        assert actual_fallback["masks"] == disabled["masks"] and actual_fallback["images"] == disabled["images"]
        assert actual_fallback["images"] != normal["images"]
        assert provider["library"] in actual_fallback["freetypeLibraries"]
        fallbacks.append(actual_fallback)
    quick_fallbacks = []
    with tempfile.TemporaryDirectory(prefix="quick-fallback-", dir=OUT) as temporary:
        directory = Path(temporary)
        graphics = kde.private_environment(directory)
        with kde.display(graphics, directory) as graphics:
            supported = "selected" if args.profile == "selected" else "v2"
            providers = [("v1", older), ("stock", record["libraries"]["stock"]),
                         (supported, record["libraries"]["candidate"])]
            if nearest_only:
                providers.append(("nearest-only-v2", nearest_only))
            for name, provider in providers:
                for factor in (1, 1.25):
                    outputs = []
                    for enabled in (False, True):
                        target = directory / f"{name}-{factor}-{enabled}"
                        target.mkdir()
                        selected_env = dict(graphics, **{k:v for k,v in env.items() if k.startswith("FONTREAL_")})
                        selected_env.update(LD_LIBRARY_PATH=str(Path(provider["library"]).parent) + ":" + env.get("LD_LIBRARY_PATH", ""),
                            QT_SCALE_FACTOR=str(factor), FONTREAL_RENDERING="1" if enabled else "0")
                        capture = subprocess.run([str(ROOT / "build/qt-kde-probe"), "quick", selected[1], str(target), "0.375"],
                                                 env=selected_env, check=True, capture_output=True, text=True)
                        output = json.loads((target / "result.json").read_text())
                        output["selections"] = [list(map(int, m)) for m in re.findall(
                            r"FONTREAL_SELECT font=.* requested=(\d+) effective=(\d+) eligible=(\d+) glyphs=(\d+)", capture.stderr)]
                        outputs.append(output)
                    equal = [f["cellHash"] for f in outputs[0]["frames"]] == [f["cellHash"] for f in outputs[1]["frames"]]
                    assert equal == (name != supported)
                    assert Path(outputs[1]["qtGui"].strip()) == Path(normal["qtGui"].strip())
                    assert Path(outputs[1]["qtQuick"].strip()).parent == Path(normal["qtGui"].strip()).parent
                    selections = outputs[1]["selections"]
                    assert selections and any(requested == 0 for requested, _, _, _ in selections)
                    assert all(eligible == (1 if name == supported else 0) for _, _, eligible, _ in selections)
                    assert all(effective == (1 if name == supported else 0)
                               for requested, effective, _, _ in selections if requested == 0)
                    if name == supported:
                        assert all(c["hypotheses"]["none/encoded"]["matches"]
                                   for frame in outputs[1]["frames"] for c in frame["cells"])
                    assert provider["library"] in outputs[1]["freetypeLibraries"]
                    quick_fallbacks.append(dict(provider=name, scale=factor, disabled=outputs[0], selected=outputs[1]))
    variations = []
    for variable_font in (args.variable_font, recipe.CFF_FONTS["Cantarell Variable"]):
      for weights in ("300,700,300", "399.5,400,399.5"):
        got = probe(dict(env, FONTREAL_TEST_WEIGHTS=weights), point=12,
                    selected=[str(variable_font.resolve())] * 3)
        assert got["masks"][:12] == got["masks"][24:]
        if weights == "300,700,300":
            assert got["masks"][:12] != got["masks"][12:24]
        assert [f["requestedWeight"] for f in got["fonts"]] == [float(w) for w in weights.split(',')]
        variations.append(got)
    (OUT / "native.json").write_text(json.dumps(dict(faces=28, conditions=252, reference=source,
        profile=args.profile, candidate=record["libraries"]["candidate"], cases=cases, opposing=opposing,
        helper=inherited, fallbacks=fallbacks, quick_fallbacks=quick_fallbacks,
        exclusions=dict(selected=excluded, disabled=excluded_stock), variations=variations), indent=2) + "\n")


if __name__ == "__main__":
    main()
