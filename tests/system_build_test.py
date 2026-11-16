#!/usr/bin/env python3
"""Check discovery and bundle validation without changing host packages."""
import argparse
import copy
from email.parser import Parser
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("system_build", ROOT / "tools/system-build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def fixture(os_name, release, upstream, base, declarative):
    # Source revisions independently observed in official distro source packages.
    original = [dict(name=name, arch="amd64", version=version, source=source, source_version=version)
                for name, source, version in (("libfreetype6", "freetype", build.FREETYPE[(os_name, release)]),
                    ("libfreetype-dev", "freetype", build.FREETYPE[(os_name, release)]), ("libqt6core6t64", "qt6-base", base),
                    ("libqt6gui6", "qt6-base", base), ("libqt6qml6", "qt6-declarative", declarative),
                    ("libqt6quick6", "qt6-declarative", declarative))]
    original.append(dict(original[0], arch="i386"))
    original.sort(key=lambda p: (p["name"], p["arch"]))
    identity = "20261111190000"
    sources = {source: dict(version=version, build_version=version + "afontreal" + identity,
                           patch_sha256=build.sha(build.patch_file(source, upstream)),
                           capability_sha256=build.sha(build.capability_patch(source)) if build.capability_patch(source) else None)
               for source, version in zip(build.SOURCES, (build.FREETYPE[(os_name, release)], base, declarative))}
    sources["freetype"]["selected"] = build.selected_inputs()
    return dict(schema=1, os=os_name, release=release, arch="amd64", identity=identity,
                installed=copy.deepcopy(original), original=original, sources=sources)


def retained_plan(plan):
    # The retained schema-1 producer at 6ae8559 recorded exactly the two Qt families.
    previous = copy.deepcopy(plan)
    del previous["sources"]["freetype"]
    for key in ("installed", "original"):
        previous[key] = [p for p in previous[key] if p["source"] != "freetype"]
    return previous


def rejected(plan, root, label):
    path = root / f"{label}.json"
    build.write_json(path, plan)
    target = root / f"{label}-output"
    result = subprocess.run([sys.executable, ROOT / "tools/system-build.py", "build", path, "--output", target],
                            capture_output=True, text=True)
    assert result.returncode and result.stderr, (label, result)
    assert not target.exists(), label


def deb(directory, name, source, version, arch="amd64"):
    with tempfile.TemporaryDirectory(dir=directory.parent) as temporary:
        root = Path(temporary)
        (root / "DEBIAN").mkdir()
        (root / "DEBIAN/control").write_text(f"Package: {name}\nVersion: {version}\nArchitecture: {arch}\n"
            f"Source: {source} ({version})\nMaintainer: Test <test@localhost>\nDescription: Synthetic bundle fixture\n")
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", root, directory / (name + ("_" + arch if arch != "amd64" else "") + ".deb")],
                       check=True, stdout=subprocess.DEVNULL)


def bundle(root, plan):
    # Synthetic local artifacts prove the bundle contract, not Qt compatibility.
    for role in ("packages", "original", "source"):
        (root / role).mkdir()
    build.write_json(root / "system.json", plan)
    build.write_json(root / "build.json", {"synthetic": True})
    for package in plan["original"]:
        deb(root / "original", package["name"], package["source"], package["version"], package["arch"])
        deb(root / "packages", package["name"], package["source"], plan["sources"][package["source"]]["build_version"], package["arch"])
    for source in plan["sources"]:
        version = plan["sources"][source]["build_version"]
        archive = root / "source" / f"{source}.tar.xz"
        archive.write_bytes(b"synthetic local archive\n")
        original_version = plan["sources"][source]["version"]
        (root / "source" / f"{source}_{original_version}.dsc").write_text(f"Source: {source}\nVersion: {original_version}\n")
        (root / "source" / f"{source}_{version}.dsc").write_text(f"Source: {source}\nVersion: {version}\n"
            f"Checksums-Sha256:\n {build.sha(archive)} {archive.stat().st_size} {archive.name}\n")
    manifest = dict(schema=1, artifacts=[dict(path=str(p.relative_to(root)), sha256=build.sha(p))
                    for p in sorted(root.rglob("*")) if p.is_file()])
    build.write_json(root / "bundle.json", manifest)
    return manifest


def verify(root, success, message=""):
    result = subprocess.run([sys.executable, ROOT / "tools/system-build.py", "verify", root],
                            capture_output=True, text=True)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    if message:
        assert message in result.stderr, result.stderr


def discovery(originals):
    result = subprocess.run([sys.executable, ROOT / "tools/system-build.py", "plan"],
                            check=True, capture_output=True, text=True)
    actual = json.loads(result.stdout)
    system = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines()
                  if line and not line.startswith("#") and "=" in line)
    assert (actual["os"], actual["release"]) == tuple(shlex.split(system[k])[0] for k in ("ID", "VERSION_ID"))
    architecture = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
    assert actual["arch"] == architecture
    fields = "${binary:Package}\t${Architecture}\t${Version}\t${source:Package}\t${source:Version}\t${db:Status-Status}\n"
    raw = subprocess.check_output(["dpkg-query", "-W", "-f=" + fields], text=True)
    expected = []
    for line in raw.splitlines():
        name, arch, version, source, source_version, status = line.split("\t")
        if status == "installed" and source in ("freetype", "qt6-base", "qt6-declarative") and arch != "all":
            expected.append(dict(name=name.split(":")[0], arch=arch, version=version, source=source, source_version=source_version))
    expected.sort(key=lambda p: (p["name"], p["arch"]))
    assert actual["installed"] == expected, "Public discovery differs from complete independent dpkg records."
    if originals is None:
        assert not any("afontreal" in p["source_version"] for p in expected), "Supply --originals for a prior Fontreal installation."
        official = expected
    else:
        official = []
        for archive in originals.glob("*.deb"):
            metadata = Parser().parsestr(subprocess.check_output(["dpkg-deb", "-f", archive], text=True))
            source = metadata["Source"].split()[0]
            version = metadata["Source"].split(" (", 1)[1][:-1] if " (" in metadata["Source"] else metadata["Version"]
            official.append(dict(name=metadata["Package"], arch=metadata["Architecture"], version=metadata["Version"],
                                 source=source, source_version=version))
        official.sort(key=lambda p: (p["name"], p["arch"]))
    assert actual["original"] == official, "Saved official identities differ from the independent original-package oracle."
    upstream = {("debian", "13"): "6.8.2", ("ubuntu", "26.04"): "6.10.2"}[(actual["os"], actual["release"])]
    for source, prefix in (("qt6-base", "qt"), ("qt6-declarative", "qtdeclarative")):
        assert {p["source_version"] for p in official if p["source"] == source} == {actual["sources"][source]["version"]}
        assert actual["sources"][source]["patch_sha256"] == hashlib.sha256((ROOT / "patches" / f"{prefix}-{upstream}-fontreal.patch").read_bytes()).hexdigest()
    print("PASS: complete public OS, architecture, binary/source discovery and independent official identities", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, help="Independent official .deb oracle for an installed Fontreal predecessor.")
    args = parser.parse_args()
    cases = [fixture("debian", "13", "6.8.2", "6.8.2+dfsg-9+deb13u2", "6.8.2+dfsg-7"),
             fixture("ubuntu", "26.04", "6.10.2", "6.10.2+dfsg-7", "6.10.2+dfsg-3")]
    for plan in cases:
        assert build.check_plan(plan) == build.PROFILES[(plan["os"], plan["release"])]
        for entry in plan["sources"].values():
            assert build.newer(entry["build_version"], entry["version"])
            for suffix in ("build1", "ubuntu0.1", "+b1", "+deb13u1", ".1"):
                assert build.newer(entry["version"] + suffix, entry["build_version"])
    # Full future version fixtures are independent of the constructor's suffix list.
    for base, later in [
            ("6.8.2+dfsg-9+deb13u2", "6.8.2+dfsg-9+deb13u3"),
            ("6.8.2+dfsg-9+deb13u2+b1", "6.8.2+dfsg-9+deb13u2+b2"),
            ("6.8.2+dfsg-7", "6.8.2+dfsg-8"),
            ("6.10.2+dfsg-7", "6.10.2+dfsg-7ubuntu0.1"),
            ("6.10.2+dfsg-3", "6.10.2+dfsg-4"),
    ]:
        candidate = build.local_version(base, "20261111190000")
        assert build.newer(candidate, base) and build.newer(later, candidate)
    with tempfile.TemporaryDirectory(prefix="fontreal-build-test-") as temporary:
        root = Path(temporary)
        for label, change in [
            ("unsupported-os", lambda p: p.update(os="fedora")),
            ("foreign-arch", lambda p: p.update(arch="arm64")),
            ("foreign-qt", lambda p: p["original"][3].update(arch="i386")),
            ("foreign-ft", lambda p: p["original"][1].update(arch="arm64")),
            ("empty", lambda p: p.update(original=[])),
            ("duplicate", lambda p: p["original"].append(dict(p["original"][0]))),
            ("late-source-mismatch", lambda p: p["original"][-1].update(source_version="6.8.2+dfsg-8")),
            ("wrong-qt", lambda p: p["sources"]["qt6-base"].update(version="6.10.2+dfsg-7")),
            ("stale-patch", lambda p: p["sources"]["qt6-declarative"].update(patch_sha256="0" * 64)),
            ("stale-selected-core", lambda p: p["sources"]["freetype"]["selected"].update(processor="0" * 64)),
            ("missing-selected-core", lambda p: p["sources"]["freetype"]["selected"].pop("processor")),
            ("wrong-version", lambda p: p["sources"]["qt6-base"].update(build_version="6.8.2+dfsg-9+deb13u2+fontreal1")),
        ]:
            plan = copy.deepcopy(cases[0])
            change(plan)
            rejected(plan, root, label)
        target = root / "bundle"
        target.mkdir()
        manifest = bundle(target, cases[0])
        verify(target, True)
        # Retained artifacts remain verifiable after the checkout's patches change.
        previous = copy.deepcopy(cases[0])
        for source, entry in previous["sources"].items():
            entry.update(patch_sha256="1" * 64, capability_sha256="2" * 64 if source != "freetype" else None)
        previous["sources"]["freetype"].pop("selected")
        rejected(previous, root, "old-build-inputs")
        old = root / "old-bundle"
        old.mkdir()
        bundle(old, previous)
        verify(old, True)
        for plan in cases:
            retained = retained_plan(plan)
            assert build.check_plan(retained, current_patches=False) == build.PROFILES[(plan["os"], plan["release"])]
            rejected(retained, root, "retained-new-build-" + plan["os"])
            retained_directory = root / ("retained-" + plan["os"])
            retained_directory.mkdir()
            bundle(retained_directory, retained)
            verify(retained_directory, True)
            for source in ("qt6-base", "qt6-declarative"):
                incomplete = copy.deepcopy(retained)
                del incomplete["sources"][source]
                try:
                    build.check_plan(incomplete, current_patches=False)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Incomplete retained source set accepted")
            unknown = copy.deepcopy(retained)
            unknown["sources"]["unknown"] = dict(unknown["sources"]["qt6-base"])
            try:
                build.check_plan(unknown, current_patches=False)
            except ValueError:
                pass
            else:
                raise AssertionError("Unknown retained source family accepted")
        descriptor = target / "source" / f"qt6-declarative_{cases[0]['sources']['qt6-declarative']['build_version']}.dsc"
        original = descriptor.read_bytes()
        descriptor.unlink()
        verify(target, False)
        descriptor.write_bytes(original)
        # A self-consistent file list must still retain both source packages.
        broken = copy.deepcopy(manifest)
        descriptor.unlink()
        broken["artifacts"] = [a for a in broken["artifacts"] if a["path"] != str(descriptor.relative_to(target))]
        build.write_json(target / "bundle.json", broken)
        verify(target, False, "Missing corresponding source for qt6-declarative")
        descriptor.write_bytes(original)
        build.write_json(target / "bundle.json", manifest)
        late = target / "packages/libqt6quick6.deb"
        before = late.read_bytes()
        late.write_bytes(before + b"altered")
        verify(target, False, "Artifact checksum mismatch")
        late.write_bytes(before)
        for role in ("packages", "original"):
            files = sorted((target / role).glob("*.deb"))
            for label, removed in (("empty", files), ("one", files[1:]), ("late", [target / role / "libqt6quick6.deb"])):
                saved = {path: path.read_bytes() for path in removed}
                for path in removed:
                    path.unlink()
                paths = {str(path.relative_to(target)) for path in removed}
                broken = dict(manifest, artifacts=[a for a in manifest["artifacts"] if a["path"] not in paths])
                build.write_json(target / "bundle.json", broken)
                reason = (f"Incomplete {role} artifact inventory" if label == "empty" else
                          "official rollback package set is incomplete" if role == "original" else "Missing rebuilt counterpart")
                verify(target, False, reason)
                for path, data in saved.items():
                    path.write_bytes(data)
                build.write_json(target / "bundle.json", manifest)
                verify(target, True)
            first = next(a for a in manifest["artifacts"] if a["path"].startswith(role + "/"))
            duplicate = dict(manifest, artifacts=[*manifest["artifacts"], first])
            build.write_json(target / "bundle.json", duplicate)
            verify(target, False, "duplicate bundle artifact path")
            copied = target / role / "duplicate.deb"
            copied.write_bytes((target / first["path"]).read_bytes())
            duplicate = dict(manifest, artifacts=[*manifest["artifacts"],
                             dict(path=str(copied.relative_to(target)), sha256=build.sha(copied))])
            build.write_json(target / "bundle.json", duplicate)
            verify(target, False, "Duplicate binary package")
            copied.unlink()
            build.write_json(target / "bundle.json", manifest)
            verify(target, True)
        archive = target / "source/qt6-declarative.tar.xz"
        archive.unlink()
        broken = copy.deepcopy(manifest)
        broken["artifacts"] = [a for a in broken["artifacts"] if a["path"] != str(archive.relative_to(target))]
        build.write_json(target / "bundle.json", broken)
        verify(target, False)
    discovery(args.originals)
    print("PASS: distro/source selection, version ordering, rejected plans, complete artifacts, late-source and archive checksums, real system discovery")


if __name__ == "__main__":
    main()
