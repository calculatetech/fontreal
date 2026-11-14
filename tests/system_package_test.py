#!/usr/bin/env python3
"""Install and check a build bundle inside a disposable distro container."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("system_build", ROOT / "tools/system-build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
sys.path.insert(0, str(ROOT / "tools"))
import system_install
sys.path.insert(0, str(ROOT / "tests"))
import kde_paths_test as kde


def capture(command, env):
    return kde.call(command, env, timeout=90)


def treatment(env, mode, contrast="mild"):
    env = dict(env)
    for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "FONTREAL_RENDERING", "FONTREAL_BLEND", "FONTREAL_CONTRAST",
                 "FONTREAL_FITTING", "QT_QUICK_DEFAULT_TEXT_RENDER_TYPE"):
        env.pop(name, None)
    if mode != "stock":
        env.update(FONTREAL_RENDERING="1", FONTREAL_BLEND="encoded" if mode == "raw" else mode,
                   FONTREAL_CONTRAST="none" if mode == "raw" else contrast)
        if mode == "raw":
            env["FONTREAL_FITTING"] = "nearest"
    env["FONTREAL_TEST_REFERENCE_FREETYPE"] = env["FONTREAL_TEST_NEAREST_FREETYPE"] if mode == "raw" else env["FONTREAL_TEST_STOCK_FREETYPE"]
    return env


def native(probe, env, fonts, directory, mode, selection=None):
    records = []
    sizes = ((8, 1), (11, 1.25), (16, 1)) if mode in ("raw", "raw-stock") else ((15, 1), (15, 1.25), (10, 1.5))
    for pixels, scale in sizes:
        for contrast in (("none",) if mode in ("stock", "raw", "raw-stock") else ("none", "mild")):
            selected = dict(treatment(env, selection or ("stock" if mode == "raw-stock" else mode), contrast), QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR=str(scale))
            result = capture([probe, mode, contrast, pixels, scale, *fonts, directory], selected)
            record = json.loads(result.stdout)
            assert "/usr/lib/" in record["qtGui"] and "qt-native" not in record["qtGui"], record
            records.append(record)
    return records


def quick(probe, env, font, directory, mode, scale=1, phase=0, contrast="mild", hidden=False, fallback=False):
    directory.mkdir()
    if mode == "raw":
        contrast = "none"
    selected = dict(treatment(env, mode, contrast), QT_SCALE_FACTOR=str(scale))
    if fallback:
        selected["FONTREAL_TEST_STOCK_FALLBACK"] = "1"
    result = capture([probe, "quick-hidden" if hidden else "quick", font, directory, phase], selected)
    (directory / "runtime.log").write_text(result.stderr)
    record = json.loads((directory / "result.json").read_text())
    record.update(selection=mode, phase=phase, contrast=contrast)
    assert record["graphicsApi"] == 3 and record["scale"] == scale and record["unexposed"] == hidden
    assert all("/usr/lib/" in record[key] and "qt-native" not in record[key] for key in ("qtGui", "qtQuick"))
    assert len(record["frames"]) == 5
    assert record["frames"][0]["hash"] == record["frames"][1]["hash"]
    for frame in record["frames"]:
        assert {g["cell"] for g in frame["cells"]} == {f"cell/{r}/{c}" for r in range(6) for c in range(9)}
        if mode != "stock" and not fallback:
            blend = "encoded" if mode == "raw" else mode
            expected = f"{contrast}/{blend}"
            opposite = f"{contrast}/{'encoded' if blend == 'linear' else 'linear'}"
            assert all(g["hypotheses"][expected]["matches"] for g in frame["cells"]), (directory, frame)
            assert any(not g["hypotheses"][opposite]["matches"] for g in frame["cells"])
            assert all(g["hypotheses"][expected]["x"] == g["expectedX"] for g in frame["cells"] if g["path"] == 0)
    return record


def mixed(probe, env, fonts, directory, mode, order):
    directory.mkdir()
    result = capture([probe, "gpu", *fonts, directory, order], treatment(env, mode))
    (directory / "runtime.log").write_text(result.stderr)
    record = json.loads((directory / "result.json").read_text())
    assert [f["frame"] for f in record["frames"]] == [0, 1, 2] and record["graphicsApi"] == 3
    assert record["frames"][0]["hash"] == record["frames"][1]["hash"] != record["frames"][2]["hash"]
    for frame in record["frames"]:
        assert {r["id"] for r in frame["regions"]} == {f"region/{row}/{col}" for row in range(2) for col in range(7)}
    return record


def raster_profile(probe, env, fonts, directory, mode, entry, order):
    directory.mkdir()
    prefix = directory / "profile"
    capture([probe, "profile", *fonts, prefix, entry, order], treatment(dict(env, QT_QPA_PLATFORM="offscreen"), mode))
    record = json.loads(prefix.with_suffix(".json").read_text())
    roles = [0, 0, 1, 2, 0] if order == "tt-first" else [1, 2, 0, 0, 1]
    assert record["colorGlyph"] and record["entry"] == entry and record["order"] == order
    assert record["qtGui"].startswith("/usr/lib/")
    assert len(record["regions"]) == 15 and {(r["row"], r["column"], r["role"]) for r in record["regions"]} == {
        (row, column, roles[column]) for row in range(3) for column in range(5)}
    return record


def update_checks(probe, graphics, font, reports, originals, candidates, references, mixed_fonts, mixed_references, plan,
                  native_probe, raw_fonts, raw_native, raw_quick):
    """Offer control-only future versions of retained official payloads through real APT."""
    results = []
    original_packages = build.package_inventory(originals)
    before_packages = build.installed()
    for source in build.SOURCES:
        future = plan["sources"][source]["version"] + ".1"
        assert build.newer(future, plan["sources"][source]["build_version"])
        # A lower-version reset is test setup, not evidence of an ordinary upgrade.
        build.run(["apt-get", "install", "-y", "--allow-downgrades", "--reinstall", "--no-remove", *candidates])
        repository = reports / ("future-" + source)
        pool = repository / "pool"
        pool.mkdir(parents=True)
        family = [p for p in before_packages if p["source"] == source]
        names = {p["name"] for p in family}
        versions = {p["version"] for p in plan["original"] if p["source"] == source}
        versions.add(plan["sources"][source]["version"])
        versions.update(original_packages[(p["name"], p["arch"])]["version"] for p in family)
        for p in family:
            original = original_packages[(p["name"], p["arch"])]
            with tempfile.TemporaryDirectory(prefix="fontreal-future-") as temporary:
                staging = Path(temporary) / "package"
                build.run(["dpkg-deb", "-R", originals / original["path"], staging])
                control = staging / "DEBIAN/control"
                text = control.read_text()
                text = re.sub(r"^Version:.*$", "Version: " + future, text, flags=re.M)
                if re.search(r"^Source:", text, re.M):
                    text = re.sub(r"^Source:.*$", f"Source: {source} ({future})", text, flags=re.M)
                else:
                    text += f"Source: {source} ({future})\n"
                # Keep cross-family requirements intact. Advance only internal version ties.
                for name in names:
                    pattern = (r"(\b" + re.escape(name) + r"(?::[a-z0-9-]+)?\s*\((?:=|>=|<=|<<|>>)\s*)"
                               + "(?:" + "|".join(re.escape(v) for v in sorted(versions, key=len, reverse=True)) + r")(\))")
                    text = re.sub(pattern, lambda m: m[1] + future + m[2], text)
                control.write_text(text)
                build.run(["dpkg-deb", "--build", "--root-owner-group", staging, pool / (p["name"] + "_" + p["arch"] + ".deb")])
        with (repository / "Packages").open("w") as index:
            build.run(["dpkg-scanpackages", "--multiversion", "pool", "/dev/null"], cwd=repository, stdout=index)
        entries = []
        for stanza in (repository / "Packages").read_text().strip().split("\n\n"):
            fields = dict(line.split(": ", 1) for line in stanza.splitlines() if ": " in line and not line.startswith(" "))
            entries.append((fields["Package"], fields["Architecture"], fields["Version"]))
        assert len(entries) == len(family) and set(entries) == {(p["name"], p["arch"], future) for p in family}
        Path("/etc/apt/sources.list.d/fontreal-test.list").write_text(f"deb [trusted=yes] file:{repository} ./\n")
        build.run(["apt-get", "update"])
        # APT chooses its candidate normally. No forced version or downgrade option is used.
        build.run(["apt-get", "install", "-y", "--only-upgrade", "--no-remove", *sorted(names)])
        installed = build.installed()
        assert {(p["name"], p["arch"]) for p in installed} == {(p["name"], p["arch"]) for p in before_packages}
        for p in installed:
            expected = future if p["source"] == source else plan["sources"][p["source"]]["build_version"]
            assert p["version"] == expected, p
        group = dict(source=source, synthetic_provider_version=future, payload="Retained authenticated official packages; control metadata only changed", records=[])
        for mode in ("linear", "stock"):
            for hidden in (False, True):
                case = reports / f"updated-{source}-{mode}-{hidden}"
                record = quick(probe, dict(graphics, LD_BIND_NOW="1"), font, case, mode, hidden=hidden, fallback=True)
                if source == "qt6-base" or mode == "stock":
                    assert [f["hash"] for f in record["frames"]] == [f["hash"] for f in references[hidden]["frames"]]
                log = (case / "runtime.log").read_text()
                if source == "qt6-base":
                    assert not re.search(r"FONTREAL_SELECT .*eligible=1", log)
                group["records"].append(record)
            for order, reference in mixed_references.items():
                record = mixed(probe, dict(graphics, LD_BIND_NOW="1"), mixed_fonts,
                               reports / f"updated-{source}-{mode}-{order}", mode, order)
                if source == "qt6-base" or mode == "stock":
                    assert [f["hash"] for f in record["frames"]] == [f["hash"] for f in reference["frames"]]
                for original_frame, frame in zip(reference["frames"], record["frames"], strict=True):
                    for original_region, region in zip(original_frame["regions"], frame["regions"], strict=True):
                        assert original_region["id"] == region["id"] and original_region["role"] == region["role"]
                        keys = ("ordinary", "windowOrdinary")
                        if region["role"]:
                            keys += ("text", "windowText")
                        assert all(original_region[key] == region[key] for key in keys), region
                group.setdefault("layers", []).append(dict(mode=mode, order=order, pixels=record))
        assert not build.output(["apt-mark", "showhold"])
        fallback = source in ("freetype", "qt6-base")
        widget = native(native_probe, graphics, raw_fonts, reports, "raw-stock" if fallback else "raw", selection="raw")
        expected = raw_native["stock" if fallback else "raw"]
        assert [r["images"] for r in widget] == [r["images"] for r in expected]
        group["raw_widget"] = widget
        import browser as browser_provider
        expected_provider = future if source == "freetype" else plan["sources"]["freetype"]["version"]
        assert browser_provider.freetype_version() == expected_provider
        group["browser_provider"] = browser_provider.freetype_version()
        for hidden in (False, True):
            record = quick(probe, dict(graphics, LD_BIND_NOW="1"), mixed_fonts[1],
                           reports / f"updated-{source}-raw-{hidden}", "raw", hidden=hidden, fallback=True)
            if fallback:
                reference = raw_quick[hidden]
                assert [f["cellHash"] for f in record["frames"]] == [f["cellHash"] for f in reference["frames"]]
                for index, (actual, original) in enumerate(zip(record["frames"], reference["frames"], strict=True)):
                    if actual["hash"] != original["hash"]:
                        target = reports / f"updated-{source}-raw-{hidden}"
                        result = target / f"annotation-{index}.json"
                        capture([probe, "composite", reports / f"official-cff-{hidden}/frame-{index}.png",
                                 target / f"frame-{index}.png", result], dict(graphics, QT_QPA_PLATFORM="offscreen"))
                        assert json.loads(result.read_text())["matches"], "Only one-level annotation variation is allowed."
            else:
                for frame in record["frames"]:
                    cells = [c for c in frame["cells"] if c["path"] == 0]
                    assert len(cells) == 9 and all(c["hypotheses"]["none/encoded"]["matches"] for c in cells)
            group.setdefault("raw_quick", []).append(record)
        results.append(group)
    return results


def baseline_packages(originals, plan):
    if any(p["arch"] == "i386" for p in plan["original"]):
        build.run(["dpkg", "--add-architecture", "i386"])
        build.run(["apt-get", "update"])
    versions = {p["source"]: p["version"] for p in plan["original"] if p["name"] in ("libqt6gui6", "libqt6quick6")}
    base, declarative = versions["qt6-base"], versions["qt6-declarative"]
    packages = ["build-essential", "cmake", "ninja-build", "libfreetype-dev", f"qt6-base-dev={base}", f"qt6-base-private-dev={base}",
                f"qt6-declarative-dev={declarative}", f"qt6-declarative-private-dev={declarative}", "fontconfig", "fonts-noto-core", "fonts-dejavu-core", "fonts-cantarell", "fonts-noto-cjk",
                "fonts-urw-base35", "fonts-noto-color-emoji", "xvfb", "xauth", "dbus-x11",
                "libplasmaquick6" if plan["os"] == "debian" else "libplasmaquick7",
                "plasma-desktoptheme", "qml6-module-org-kde-breeze", "qml6-module-org-kde-kirigami",
                f"qml6-module-qtqml-workerscript={declarative}", f"qml6-module-qtquick-window={declarative}", "plasma-integration"]
    build.run(["apt-get", "install", "-y", "--no-install-recommends", "--allow-downgrades", "--no-remove",
               *packages, *sorted(originals.glob("*.deb"))])


def inside(directory, reports, updates=False):
    assert Path("/.dockerenv").is_file() and os.geteuid() == 0, "This check installs packages only inside its disposable container."
    plan = build.verify_artifacts(directory, json.loads((directory / "bundle.json").read_text()))
    deployment = json.loads((directory / "deployment.json").read_text())
    system_install.verify_activation(build, directory, deployment, plan)
    for name in ("FONTREAL_TEST_NEAREST_FREETYPE", "FONTREAL_TEST_STOCK_FREETYPE"):
        assert Path(os.environ[name]).is_file(), "Use actual independent FreeType references."
    baseline_packages(directory / "original", plan)
    actual_originals = build.installed()
    assert all(p["source_version"] == plan["sources"][p["source"]]["version"] for p in actual_originals)
    references = reports / "reference-packages"
    references.mkdir()
    build.run(["apt-get", "download", *[f"{p['name']}:{p['arch']}={p['version']}" for p in actual_originals]], cwd=references)
    inventory = build.package_inventory(directory / "packages")
    candidates = [directory / "packages" / inventory[(p["name"], p["arch"])]["path"] for p in actual_originals]
    for source in build.SOURCES:
        with tempfile.TemporaryDirectory(prefix="fontreal-source-") as temporary:
            descriptor = build.source_descriptor(directory / "source", source, plan["sources"][source]["build_version"])
            target = Path(temporary) / "source"
            build.run(["dpkg-source", "--no-check", "-x", descriptor, target])
            assert build.sha(target / "debian/patches/fontreal.patch") == plan["sources"][source]["patch_sha256"]
            if plan["sources"][source]["capability_sha256"] is not None:
                assert build.sha(target / "debian/patches/fontreal-capability.patch") == plan["sources"][source]["capability_sha256"]
            assert "fontreal.patch" in (target / "debian/patches/series").read_text().splitlines()
            assert (target / "debian/copyright").is_file()
    build.run(["cmake", "-S", ROOT, "-B", "/tmp/fontreal-probes", "-G", "Ninja"])
    build.run(["cmake", "--build", "/tmp/fontreal-probes", "--target", "qt-native-probe", "qt-kde-probe", "--parallel", "2"])
    native_probe = Path("/tmp/fontreal-probes/qt-native-probe")
    quick_probe = Path("/tmp/fontreal-probes/qt-kde-probe")
    fonts = [build.output(["fc-match", "-f", "%{file}", family]) for family in ("Noto Sans", "DejaVu Sans", "DejaVu Sans Mono")]
    gpu_fonts = [fonts[0], *[build.output(["fc-match", "-f", "%{file}", family]) for family in ("Nimbus Sans", "Noto Color Emoji")]]
    raw_fonts = [fonts[0], gpu_fonts[1], build.output(["fc-match", "-f", "%{file}", "URW Bookman:style=Light"])]
    results = dict(schema=1, passed=False, raw_profile=False, bundle_sha256=build.sha(directory / "bundle.json"),
                   deployment_sha256=build.sha(directory / "deployment.json"), native={}, raster=[], quick=[], gpu=[])
    with tempfile.TemporaryDirectory(prefix="fontreal-render-") as temporary:
        state = Path(temporary)
        env = kde.private_environment(state)
        results["native"]["official"] = native(native_probe, env, fonts, state, "stock")
        raw_native = dict(stock=native(native_probe, env, raw_fonts, state, "raw-stock"))
        raster_baseline = {(entry, order): raster_profile(quick_probe, env, gpu_fonts,
                           reports / f"official-raster-{entry}-{order}", "stock", entry, order)
                           for entry in ("ordinary", "static") for order in ("tt-first", "cff-first")}
        with kde.display(env, state) as graphics:
            baseline = quick(quick_probe, graphics, fonts[0], reports / "official", "stock")
            hidden_baseline = quick(quick_probe, graphics, fonts[0], reports / "official-hidden", "stock", hidden=True)
            raw_quick = {hidden: quick(quick_probe, graphics, gpu_fonts[1], reports / f"official-cff-{hidden}",
                                       "stock", hidden=hidden) for hidden in (False, True)}
            mixed_baseline = {order: mixed(quick_probe, graphics, gpu_fonts, reports / ("official-" + order), "stock", order)
                              for order in ("tt-first", "cff-first")}
            build.run(["apt-get", "install", "-y", "--no-install-recommends", "--no-remove", *candidates,
                       directory / "activation/fontreal-session.deb"])
            assert build.output(["dpkg-query", "-W", "-f=${Version}", "fontreal-session"]) == "0~local" + plan["identity"]
            assert json.loads(Path("/usr/share/fontreal/system.json").read_text()) == plan
            for path in ("/usr/bin/fontreal-session", "/etc/xdg/plasma-workspace/env/fontreal.sh"):
                assert build.output(["dpkg-query", "-S", path]).startswith("fontreal-session: ")
            assert not (Path.home() / ".config/fontreal/enabled").exists()
            installed = {(p["name"], p["arch"]): p for p in build.installed()}
            assert set(installed) == {(p["name"], p["arch"]) for p in actual_originals}
            results["native"]["raw"] = native(native_probe, env, raw_fonts, state, "raw")
            raw_native["raw"] = results["native"]["raw"]
            sys.path.insert(0, str(ROOT / "tools"))
            import browser as browser_provider
            assert browser_provider.freetype_version() == plan["sources"]["freetype"]["version"]
            results["browser_provider"] = browser_provider.freetype_version()
            for identity in installed:
                assert installed[identity]["version"] == inventory[identity]["version"], identity
            for module in ("Gui", "Quick"):
                version = build.check_plan(plan, current_patches=False)[1]
                owner = build.output(["dpkg-query", "-S", f"/usr/lib/x86_64-linux-gnu/libQt6{module}.so.{version}"])
                assert "libqt6" + module.lower() + "6" in owner
            symbols = build.output(["readelf", "--dyn-syms", "--wide", f"/usr/lib/x86_64-linux-gnu/libQt6Quick.so.{version}"])
            assert any("WEAK" in line and "UND" in line and "qt_fontrealFontV1" in line for line in symbols.splitlines())
            assert "QFontEngineFT15fontrealEnabled" not in symbols
            results["native"]["inactive"] = native(native_probe, env, fonts, state, "stock")
            assert [r["images"] for r in results["native"]["official"]] == [r["images"] for r in results["native"]["inactive"]]
            for mode in ("linear", "encoded"):
                results["native"][mode] = native(native_probe, env, fonts, state, mode)
            for (entry, order), reference in raster_baseline.items():
                group = dict(official=reference)
                for mode in ("stock", "linear", "encoded", "raw"):
                    record = raster_profile(quick_probe, env, gpu_fonts, reports / f"raster-{entry}-{order}-{mode}", mode, entry, order)
                    if mode == "stock":
                        assert record["regions"] == reference["regions"]
                    for original, region in zip(reference["regions"], record["regions"], strict=True):
                        assert (original["row"], original["column"], original["role"]) == (region["row"], region["column"], region["role"])
                        treated = mode != "stock" and (region["role"] == 0 or (mode == "raw" and region["role"] == 1))
                        if not treated:
                            assert original["hash"] == region["hash"], region
                        else:
                            assert set(region["glyphs"]) == set("mnogWV")
                            profile = "none/encoded" if mode == "raw" else f"mild/{mode}"
                            opposite = "none/linear" if mode == "raw" else "mild/" + ("encoded" if mode == "linear" else "linear")
                            assert all(g[profile]["matches"] for g in region["glyphs"].values()), region
                            assert any(not g[opposite]["matches"] for g in region["glyphs"].values()), region
                    group[mode] = record
                results["raster"].append(dict(entry=entry, order=order, records=group))
            inactive = quick(quick_probe, graphics, fonts[0], reports / "inactive", "stock")
            assert [f["hash"] for f in baseline["frames"]] == [f["hash"] for f in inactive["frames"]]
            for mode, scale, phase, contrast, hidden in (
                    ("linear", 1, 0, "mild", False), ("encoded", 1, 0, "mild", False),
                    ("linear", 1, 0, "none", False), ("linear", 1, .5, "mild", False),
                    ("linear", 1.25, 0, "mild", False), ("encoded", 1.25, 0, "mild", False),
                    ("linear", 1.25, .5, "mild", False), ("linear", 1, 0, "mild", True),
                    ("encoded", 1, 0, "mild", True)):
                label = f"quick-{mode}-{scale}-{phase}-{contrast}-{hidden}"
                results["quick"].append(quick(quick_probe, graphics, fonts[0], reports / label, mode, scale, phase, contrast, hidden))
            for scale in (1, 1.25):
                pair = [r for r in results["quick"] if r["scale"] == scale and not r["unexposed"] and
                        r["selection"] == "linear" and r["contrast"] == "mild"]
                assert len(pair) == 2 and {r["phase"] for r in pair} == {0, .5}
                for a, b in zip(pair[0]["frames"][0]["cells"], pair[-1]["frames"][0]["cells"], strict=True):
                    if a["path"] == 0:
                        assert a["hypotheses"]["mild/linear"]["y"] == b["hypotheses"]["mild/linear"]["y"]
            for scale, phase, hidden in ((1, 0, False), (1, .5, False), (1.25, 0, False), (1.25, .5, False), (1, 0, True)):
                label = f"raw-cff-{scale}-{phase}-{hidden}"
                results["quick"].append(quick(quick_probe, graphics, gpu_fonts[1], reports / label,
                                               "raw", scale, phase, hidden=hidden))
            variable = build.output(["fc-match", "-f", "%{file}", "Cantarell"])
            for sequence in ("300,700,300", "399.5,400,399.5"):
                variable_env = dict(graphics, FONTREAL_TEST_WEIGHT=sequence.split(',')[0], FONTREAL_TEST_WEIGHT_SEQUENCE=sequence)
                record = quick(quick_probe, variable_env, variable, reports / ("raw-cff2-" + sequence), "raw")
                weights = sequence.split(',')
                assert [frame["weight"] for frame in record["frames"]] == [weights[0], weights[0], weights[1], weights[2], weights[2]]
                results["quick"].append(record)
            cid = build.output(["fc-match", "-f", "%{file}", "Noto Sans CJK JP"])
            letters = "漢国文漢国文漢国文"
            for scale in (1, 1.25):
                record = quick(quick_probe, dict(graphics, FONTREAL_TEST_LETTERS=letters), cid,
                               reports / f"raw-cid-{scale}", "raw", scale)
                assert all({cell["glyph"] for cell in frame["cells"]} == set(letters) for frame in record["frames"])
                results["quick"].append(record)
            for order, reference in mixed_baseline.items():
                group = dict(official=reference)
                for mode in ("stock", "linear", "encoded", "raw"):
                    group[mode] = mixed(quick_probe, graphics, gpu_fonts, reports / (order + "-" + mode), mode, order)
                    for original, frame in zip(reference["frames"], group[mode]["frames"], strict=True):
                        if mode == "stock":
                            assert original["hash"] == frame["hash"]
                        for before, region in zip(original["regions"], frame["regions"], strict=True):
                            assert (before["id"], before["role"]) == (region["id"], region["role"])
                            assert all(before[k] == region[k] for k in ("ordinary", "windowOrdinary"))
                            treated = mode != "stock" and (region["role"] == 0 or (mode == "raw" and region["role"] != 2))
                            if not treated:
                                assert all(before[k] == region[k] for k in ("text", "windowText"))
                            else:
                                for key in ("glyphs", "windowGlyphs"):
                                    profile = "none/encoded" if mode == "raw" else f"mild/{mode}"
                                    assert all(g[profile]["matches"] for g in region[key].values()), region
                                    opposite = "none/linear" if mode == "raw" else f"mild/{'encoded' if mode == 'linear' else 'linear'}"
                                    assert any(not g[opposite]["matches"] for g in region[key].values())
                results["gpu"].append(dict(order=order, records=group))
            for mode, target_font in (("linear", fonts[0]), ("raw", gpu_fonts[1])):
              for style in ("", "sunken"):
                target = reports / ("target-" + mode + "-" + (style or "normal"))
                target.mkdir()
                capture([quick_probe, "target", target_font, target, *([style] if style else [])], treatment(graphics, mode))
                record = json.loads((target / "result.json").read_text())
                assert [f["frame"] for f in record["frames"]] == [0, 1, 2] and record["nonindexed"]
                assert record["frames"][0]["hash"] == record["frames"][2]["hash"]
                assert (record["frames"][0]["hash"] == record["frames"][1]["hash"]) == (mode == "raw")
                for frame in record["frames"]:
                    expected = "none/encoded" if mode == "raw" else "mild/linear" if frame["compatible"] else "mild/encoded"
                    assert set(frame["glyphs"]) == set("lmnogWVwv")
                    assert all(g[expected]["matches"] for g in frame["glyphs"].values()), frame
                results["gpu"].append(record)
            if updates:
                results["updates"] = update_checks(quick_probe, graphics, fonts[0], reports, references, candidates,
                                                     {False: baseline, True: hidden_baseline}, gpu_fonts, mixed_baseline, plan,
                                                     native_probe, raw_fonts, raw_native, raw_quick)
                # Exact probe dependencies must win even when newer revisions are available.
                Path("/etc/apt/sources.list.d/fontreal-test.list").write_text("".join(
                    f"deb [trusted=yes] file:{reports / ('future-' + source)} ./\n" for source in build.SOURCES))
                build.run(["apt-get", "update"])
                for name, source in (("qt6-base-dev", "qt6-base"), ("qt6-declarative-private-dev", "qt6-declarative")):
                    assert "Candidate: " + plan["sources"][source]["version"] + ".1" in build.output(["apt-cache", "policy", name])
                # Model a host whose saved originals do not include probe SDK packages.
                sdk = {"qt6-base-dev", "qt6-base-private-dev", "qt6-declarative-dev", "qt6-declarative-private-dev"}
                with tempfile.TemporaryDirectory(prefix="fontreal-runtime-originals-") as temporary:
                    runtime_originals = Path(temporary)
                    runtime_originals.chmod(0o755)
                    for (name, _), package in build.package_inventory(references).items():
                        if name not in sdk:
                            (runtime_originals / package["path"]).write_bytes((references / package["path"]).read_bytes())
                    assert not sdk.intersection(name for name, _ in build.package_inventory(runtime_originals))
                    baseline_packages(runtime_originals, plan)
                assert build.installed() == actual_originals
                fresh = "/tmp/fontreal-baseline-probes"
                build.run(["cmake", "-S", ROOT, "-B", fresh, "-G", "Ninja"])
                build.run(["cmake", "--build", fresh, "--target", "qt-native-probe", "qt-kde-probe", "--parallel", "2"])
                record = quick(Path(fresh) / "qt-kde-probe", graphics, fonts[0], reports / "baseline-reselection", "stock")
                assert [f["hash"] for f in record["frames"]] == [f["hash"] for f in baseline["frames"]]
                results["baseline_reselection"] = record
    results["passed"] = True
    results["raw_profile"] = True
    build.write_json(reports / "package-results.json", results)
    print("PASS: actual corresponding source, native package ownership, installed widget/Quick pixels, inactive preservation, fractional placement and target transitions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--updates", action="store_true", help="Also test independent official-family update fixtures and runtime fallback.")
    args = parser.parse_args()
    if args.inside:
        inside(args.bundle, Path("/reports"), args.updates)
        return
    directory = args.bundle.resolve()
    plan = build.verify_artifacts(directory, json.loads((directory / "bundle.json").read_text()))
    system_install.verify_activation(build, directory, json.loads((directory / "deployment.json").read_text()), plan)
    reports = directory / "package-checks"
    reports.mkdir()
    temporary = reports / "tmp"
    temporary.mkdir()
    temporary.chmod(0o1777)
    image, _ = build.check_plan(plan, current_patches=False)
    nearest = Path(os.environ["FONTREAL_TEST_REFERENCE_FREETYPE"]).resolve()
    stock = Path(os.environ["FONTREAL_TEST_STOCK_FREETYPE"]).resolve()
    reference_record = json.loads((ROOT / "build/browser-live-recipe/reference.json").read_text())
    assert build.sha(nearest) == reference_record["sha256"] and reference_record["inputs"]["provider"] == plan["sources"]["freetype"]["version"]
    assert stock.is_file() and stock != nearest
    try:
        build.run(["docker", "run", "--rm", "--log-driver", "none", "--platform", "linux/amd64", "-v", f"{ROOT}:/repo:ro",
                   "-v", f"{directory}:/bundle:ro", "-v", f"{reports}:/reports", "-e", "DEBIAN_FRONTEND=noninteractive",
                   "-v", f"{nearest}:/fontreal-reference/nearest/libfreetype.so.6:ro",
                   "-v", f"{stock}:/fontreal-reference/stock/libfreetype.so.6:ro",
                   "-e", "FONTREAL_TEST_NEAREST_FREETYPE=/fontreal-reference/nearest/libfreetype.so.6",
                   "-e", "FONTREAL_TEST_STOCK_FREETYPE=/fontreal-reference/stock/libfreetype.so.6",
                   "-v", f"{temporary}:/tmp",
                   image, "sh", "-ec", "apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates dbus-daemon && "
                   'exec dbus-run-session -- python3 /repo/tests/system_package_test.py /bundle --inside "$@"',
                   "fontreal", *(["--updates"] if args.updates else [])])
    finally:
        # Container files remain useful to the local user after normal completion or a failed assertion.
        build.run(["docker", "run", "--rm", "-v", f"{reports}:/reports", image,
                   "chown", "-R", f"{os.getuid()}:{os.getgid()}", "/reports"])


if __name__ == "__main__":
    main()
