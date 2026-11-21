#!/usr/bin/env python3
"""Build, verify, and apply matching distro FreeType and Qt packages."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    ("debian", "13"): ("debian:13-slim", "6.8.2"),
    ("ubuntu", "26.04"): ("ubuntu:26.04", "6.10.2"),
}
SOURCES = ("freetype", "qt6-base", "qt6-declarative")
QT_SOURCES = SOURCES[1:]
QT_V3 = "qt-v3"
V3_FILES = ("fontreal_v3_coverage.cpp", "fontreal_v3_coverage.h", "fontreal_v3_outline.cpp",
            "fontreal_v3_outline.h", "fontreal_v3_thin.cpp")
SYSTEM_RECORD = Path("/usr/share/fontreal/system.json")
FREETYPE = {("debian", "13"): "2.13.3+dfsg-1+deb13u1",
            ("ubuntu", "26.04"): "2.14.2+dfsg-1ubuntu0.2"}
FIELDS = "${Package}\t${Architecture}\t${Version}\t${source:Package}\t${source:Version}\t${db:Status-Status}\n"
SELECTED_PROFILE = "native-normal-o-k3-v2"
SELECTED_KEYS = {"native-normal-weighted-stems-v1": {"profile", "render", "processor", "declaration", "license"},
                 SELECTED_PROFILE: {"profile", "render", "processor", "declaration", "license", "v2_processor", "v2_declaration"}}


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def output(args, **kwargs):
    return run(args, text=True, stdout=subprocess.PIPE, **kwargs).stdout.strip()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def installed():
    records = []
    for line in output(["dpkg-query", "-W", "-f=" + FIELDS]).splitlines():
        name, arch, version, source, source_version, status = line.split("\t")
        if status == "installed" and source in SOURCES and arch != "all":
            records.append(dict(name=name, arch=arch, version=version,
                                source=source, source_version=source_version))
    return sorted(records, key=lambda p: (p["name"], p["arch"]))


def session_version():
    query = subprocess.run(["dpkg-query", "-W", "-f=${db:Status-Status}\t${Version}\n", "fontreal-session"],
                           capture_output=True, text=True)
    if query.returncode == 1 and not query.stdout:
        return None
    query.check_returncode()
    status, _, version = query.stdout.rstrip("\n").partition("\t")
    return version if status == "installed" else None


def patch_file(source, upstream, qt_v3=False):
    if qt_v3:
        name = (f"qt-{upstream}-fontreal-v3-widgets.patch" if source == "qt6-base"
                else "qtdeclarative-fontreal-v3.patch")
        return ROOT / "patches" / name
    if source == "freetype":
        return ROOT / "patches/freetype-nearest-property.patch"
    name = "qt" if source == "qt6-base" else "qtdeclarative"
    return ROOT / "patches" / f"{name}-{upstream}-fontreal.patch"


def capability_patch(source, qt_v3=False):
    if qt_v3:
        return None
    return ROOT / "packaging" / f"{source}-capability.patch"


def selected_inputs():
    return dict(profile=SELECTED_PROFILE, **{name: sha(ROOT / path) for name, path in (
        ("render", "patches/freetype-2.14.2-fontreal.patch"),
        ("processor", "src/fontreal_coverage.cpp"),
        ("declaration", "src/fontreal_coverage.h"), ("license", "LICENSE"),
        ("v2_processor", "src/fontreal_v2_coverage.cpp"), ("v2_declaration", "src/fontreal_v2_coverage.h"))})


def selected_plan(plan):
    entry = plan.get("sources", {}).get("freetype", {})
    return bool(entry.get("capability_sha256")) and entry.get("selected", {}).get("profile") in SELECTED_KEYS


def v3_plan(plan):
    return plan.get("profile") == QT_V3


def v3_inputs():
    return {name: sha(ROOT / "src" / name) for name in V3_FILES} | {"LICENSE": sha(ROOT / "LICENSE")}


def check_retained_freetype(provider, os_release):
    if (not isinstance(provider, dict) or set(provider) != {"version", "build_version", "original"}
            or provider["version"] != FREETYPE[os_release]):
        raise ValueError("The retained FreeType provider has no supported official source revision.")
    version = provider["version"]
    if not re.fullmatch(re.escape(version) + r"(?:\+b[0-9]+)?afontreal[0-9]{14}", provider["build_version"]):
        raise ValueError("The retained FreeType provider has an invalid local version.")
    records = provider["original"]
    if not records or len({(p["name"], p["arch"]) for p in records}) != len(records):
        raise ValueError("The retained FreeType provider needs unique official package records.")
    for p in records:
        if (set(p) != {"name", "arch", "version", "source", "source_version"} or p["source"] != "freetype"
                or p["arch"] not in ("amd64", "i386") or p["source_version"] != version
                or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", p["name"])
                or not re.fullmatch(re.escape(version) + r"(?:\+b[0-9]+)?", p["version"])):
            raise ValueError("The retained FreeType record does not identify an official counterpart.")
        if (p["name"], p["arch"]) == ("libfreetype6", "amd64") and p["version"] != version:
            raise ValueError("The retained amd64 FreeType provider requires its exact official counterpart.")


def trusted_system_record():
    for path in (SYSTEM_RECORD, SYSTEM_RECORD.parent, SYSTEM_RECORD.parent.parent):
        metadata = path.lstat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022 or stat.S_ISLNK(metadata.st_mode):
            raise ValueError("The installed Fontreal source record is not trusted.")
    return json.loads(SYSTEM_RECORD.read_text())


def retained_freetype(records, previous, os_release):
    local = [p for p in records if p["source"] == "freetype" and "afontreal" in p["source_version"]]
    if not local:
        return None
    old = previous["sources"]["freetype"]
    original = []
    for p in local:
        if p["version"] != old["build_version"] or p["source_version"] != old["build_version"]:
            raise ValueError("The installed FreeType differs from its Fontreal source record.")
        matches = [r for r in previous["original"] if (r["name"], r["arch"]) == (p["name"], p["arch"])]
        if len(matches) != 1:
            raise ValueError("The installed FreeType package has no saved official identity.")
        original.append(matches[0])
    provider = dict(version=old["version"], build_version=old["build_version"], original=original)
    check_retained_freetype(provider, os_release)
    return provider


def newer(left, right):
    return subprocess.run(["dpkg", "--compare-versions", left, "gt", right]).returncode == 0


def local_version(base, identity):
    # Letters sort before Ubuntu's build/ubuntu suffixes and Debian's +b/+deb suffixes.
    version = base + "afontreal" + identity
    if not newer(version, base):
        raise ValueError("The Fontreal version must sort above its official base.")
    for suffix in ("build1", "ubuntu0.1", "+b1", "+deb13u1", ".1"):
        if not newer(base + suffix, version):
            raise ValueError("The Fontreal version would block an official update.")
    return version


def check_plan(plan, current_patches=True):
    os_release = (plan["os"], plan["release"])
    profile = PROFILES.get(os_release)
    if plan["schema"] != 1 or not profile or plan["arch"] != "amd64":
        raise ValueError("Supported systems: Debian 13 and Ubuntu 26.04, native amd64.")
    sources = set(plan["sources"])
    qt_v3 = v3_plan(plan)
    if not qt_v3 and {"profile", "freetype_provider", "previous_session"} & plan.keys():
        raise ValueError("The plan has an unsupported rendering profile.")
    if qt_v3:
        valid_sources = sources == set(QT_SOURCES)
        previous_session = plan["previous_session"]
        if previous_session is not None and not re.fullmatch(r"0~local[0-9]{14}", previous_session):
            raise ValueError("Invalid previous Fontreal session package version.")
        if previous_session is None and (plan["installed"] != plan["original"] or "freetype_provider" in plan):
            raise ValueError("The previous Fontreal session package is missing. Restore the recorded installation first.")
        if "freetype_provider" in plan:
            check_retained_freetype(plan["freetype_provider"], os_release)
    else:
        valid_sources = sources == set(SOURCES) or (not current_patches and sources == set(QT_SOURCES))
    if not valid_sources or not plan["installed"] or not plan["original"]:
        raise ValueError("The plan needs the complete package set for each selected source family.")
    if not re.fullmatch(r"[0-9]{14}", plan["identity"]):
        raise ValueError("Invalid numeric build identity.")
    for key in ("installed", "original"):
        records = plan[key]
        identities = [(p["name"], p["arch"]) for p in records]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate package identity in the system plan.")
        if {p["source"] for p in records} != sources:
            raise ValueError("The package set must match the plan's source families.")
        for p in records:
            if (p["arch"] != plan["arch"] and not (p["source"] == "freetype" and p["arch"] == "i386")) or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", p["name"]):
                raise ValueError("Foreign-architecture or invalid native package in the plan.")
    if {(p["name"], p["arch"]) for p in plan["installed"]} != {(p["name"], p["arch"]) for p in plan["original"]}:
        raise ValueError("Original and installed package identities differ.")
    runtimes = {("libqt6gui6", "amd64"), ("libqt6quick6", "amd64")}
    if "freetype" in sources:
        runtimes.add(("libfreetype6", "amd64"))
    if not runtimes <= {(p["name"], p["arch"]) for p in plan["installed"]}:
        raise ValueError("Install native FreeType, QtGui and QtQuick before making a system plan.")
    for source in plan["sources"]:
        entry = plan["sources"][source]
        valid_version = (entry["version"] == FREETYPE[(plan["os"], plan["release"])]) if source == "freetype" else re.fullmatch(
            re.escape(profile[1]) + r"\+dfsg-[A-Za-z0-9.+~]+", entry["version"])
        if not valid_version:
            raise ValueError(f"Unsupported {source} source version: {entry['version']}")
        originals = [p for p in plan["original"] if p["source"] == source]
        if {p["source_version"] for p in originals} != {entry["version"]}:
            raise ValueError(f"Mixed official source revisions for {source}.")
        base = entry["version"]
        for p in originals:
            if newer(p["version"], base):
                base = p["version"]
        if entry["build_version"] != local_version(base, plan["identity"]):
            raise ValueError("The build version does not match the installed source/binary revisions.")
        capability = capability_patch(source, qt_v3)
        if qt_v3:
            valid_capability = entry["capability_sha256"] is None
        else:
            valid_capability = (source == "freetype" and not current_patches and entry["capability_sha256"] is None) or re.fullmatch(
                r"[0-9a-f]{64}", entry["capability_sha256"] or "")
        if not re.fullmatch(r"[0-9a-f]{64}", entry["patch_sha256"]) or not valid_capability:
            raise ValueError("Invalid patch checksum in the system plan.")
        if current_patches and entry["patch_sha256"] != sha(patch_file(source, profile[1], qt_v3)):
            raise ValueError("The plan patch changed. Make a new plan before building.")
        if current_patches and entry["capability_sha256"] != (sha(capability) if capability else None):
            raise ValueError("The package capability patch changed. Make a new plan before building.")
        if source == "freetype" and (current_patches or "selected" in entry):
            selected = entry.get("selected", {})
            if (set(selected) != SELECTED_KEYS.get(selected.get("profile"))
                    or any(not re.fullmatch(r"[0-9a-f]{64}", selected[k]) for k in selected if k != "profile")):
                raise ValueError("The selected FreeType processor inputs are incomplete.")
            if current_patches and selected != selected_inputs():
                raise ValueError("The selected FreeType inputs changed. Make a new plan before building.")
        if qt_v3 and source == "qt6-base":
            selected = entry.get("selected", {})
            if set(selected) != {*V3_FILES, "LICENSE"} or any(
                    not re.fullmatch(r"[0-9a-f]{64}", value) for value in selected.values()):
                raise ValueError("The V3 Qt processor inputs are incomplete.")
            if current_patches and selected != v3_inputs():
                raise ValueError("The V3 Qt processor inputs changed. Make a new plan before building.")
    return profile


def system_plan(qt_v3=False):
    system = platform.freedesktop_os_release()
    key = (system["ID"], system["VERSION_ID"])
    if key not in PROFILES:
        raise ValueError("Supported systems: Debian 13 and Ubuntu 26.04.")
    records = installed()
    sources = QT_SOURCES if qt_v3 else SOURCES
    selected_records = [p for p in records if p["source"] in sources]
    original = [dict(p) for p in selected_records]
    provider = None
    if any("afontreal" in p["source_version"] for p in records):
        if not SYSTEM_RECORD.is_file():
            raise ValueError("The installed Fontreal source record is missing. Restore official Qt before rebuilding.")
        old = trusted_system_record() if qt_v3 else json.loads(SYSTEM_RECORD.read_text())
        if qt_v3:
            provider = retained_freetype(records, old, key)
        for p in original:
            if "afontreal" in p["source_version"]:
                if p["source_version"] != old["sources"][p["source"]]["build_version"]:
                    raise ValueError("The installed Fontreal pair does not match its source record.")
                matches = [r for r in old["original"] if (r["name"], r["arch"]) == (p["name"], p["arch"])]
                if len(matches) != 1:
                    raise ValueError("An installed Fontreal package has no saved official identity.")
                p.update(matches[0])
    identity = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    plan = dict(schema=1, os=key[0], release=key[1], arch=output(["dpkg", "--print-architecture"]),
                identity=identity, installed=selected_records, original=original, sources={})
    if qt_v3:
        plan["profile"] = QT_V3
        plan["previous_session"] = session_version()
        if provider is not None:
            plan["freetype_provider"] = provider
    for source in sources:
        versions = {p["source_version"] for p in original if p["source"] == source}
        if len(versions) != 1:
            raise ValueError(f"Install a coherent official {source} package set before building.")
        version = versions.pop()
        base = version
        for p in original:
            if p["source"] == source and newer(p["version"], base):
                base = p["version"]
        capability = capability_patch(source, qt_v3)
        plan["sources"][source] = dict(version=version, build_version=local_version(base, identity),
                                      patch_sha256=sha(patch_file(source, PROFILES[key][1], qt_v3)),
                                      capability_sha256=sha(capability) if capability else None)
        if source == "freetype":
            plan["sources"][source]["selected"] = selected_inputs()
        if qt_v3 and source == "qt6-base":
            plan["sources"][source]["selected"] = v3_inputs()
    check_plan(plan)
    return plan


def package_inventory(directory):
    packages = {}
    for path in sorted(directory.glob("*.deb")):
        fields = output(["dpkg-deb", "-f", path, "Package", "Architecture", "Version", "Source"])
        values = dict(line.split(": ", 1) for line in fields.splitlines())
        identity = (values["Package"], values["Architecture"])
        if identity in packages:
            raise ValueError(f"Duplicate binary package: {identity}")
        packages[identity] = dict(path=path.name, version=values["Version"], source=values.get("Source", values["Package"]))
    return packages


def source_descriptor(directory, source, version):
    matches = []
    for path in directory.glob(source + "_*.dsc"):
        text = path.read_text()
        if (re.search(r"^Source: " + re.escape(source) + r"$", text, re.M)
                and re.search(r"^Version: " + re.escape(version) + r"$", text, re.M)):
            matches.append(path)
    if len(matches) != 1:
        raise ValueError(f"Missing corresponding source for {source}.")
    return matches[0]


def verify_artifacts(directory, manifest):
    if manifest["schema"] != 1:
        raise ValueError("Unsupported bundle format.")
    seen = set()
    for artifact in manifest["artifacts"]:
        path = Path(artifact["path"])
        if path.is_absolute() or ".." in path.parts or path in seen:
            raise ValueError("Invalid or duplicate bundle artifact path.")
        seen.add(path)
        if sha(directory / path) != artifact["sha256"]:
            raise ValueError(f"Artifact checksum mismatch: {path}")
    for role in ("packages", "original", "source"):
        files = {p.relative_to(directory) for p in (directory / role).iterdir()}
        if not files or files != {p for p in seen if p.parts[0] == role}:
            raise ValueError(f"Incomplete {role} artifact inventory.")
    if not {Path("system.json"), Path("build.json")} <= seen:
        raise ValueError("The bundle needs its exact system and build records.")
    plan = json.loads((directory / "system.json").read_text())
    check_plan(plan, current_patches=False)
    built = package_inventory(directory / "packages")
    if v3_plan(plan) and any(p["source"].split()[0] not in QT_SOURCES for p in built.values()):
        raise ValueError("A V3 bundle contains a package outside its Qt source families.")
    original = package_inventory(directory / "original")
    expected_original = {(p["name"], p["arch"]): p["version"] for p in plan["original"]}
    if {k: v["version"] for k, v in original.items()} != expected_original:
        raise ValueError("The official rollback package set is incomplete or has different versions.")
    for p in plan["original"]:
        candidate = built.get((p["name"], p["arch"]))
        if (not candidate or candidate["version"] != plan["sources"][p["source"]]["build_version"]
                or candidate["source"].split()[0] != p["source"]):
            raise ValueError(f"Missing rebuilt counterpart for {p['name']}.")
    for source in plan["sources"]:
        descriptor = source_descriptor(directory / "source", source, plan["sources"][source]["build_version"]).read_text()
        checksums = re.search(r"^Checksums-Sha256:\n((?: [^\n]+\n)+)", descriptor, re.M)
        if not checksums:
            raise ValueError(f"Missing source archive checksums for {source}.")
        for line in checksums[1].splitlines():
            digest, size, name = line.split()
            if Path(name).name != name:
                raise ValueError("Invalid source archive name.")
            archive = directory / "source" / name
            if archive.stat().st_size != int(size) or sha(archive) != digest:
                raise ValueError(f"Source archive mismatch: {name}")
    return plan


def build(plan_path, destination, jobs):
    plan = json.loads(plan_path.read_text())
    image, _ = check_plan(plan)
    builder_digest = sha(Path(__file__))
    builder_source = Path(__file__).read_bytes()
    destination.mkdir(parents=True, exist_ok=False)
    temporary = destination / "tmp"
    temporary.mkdir()
    temporary.chmod(0o1777)
    write_json(destination / "system.json", plan)
    command = ["docker", "run", "--rm", "--log-driver", "none", "--platform", "linux/amd64",
               "-v", f"{ROOT}:/repo:ro", "-v", f"{destination.resolve()}:/output",
               "-v", f"{temporary.resolve()}:/tmp",
               "-e", "DEBIAN_FRONTEND=noninteractive", "-e", "FONTREAL_BUILD_WORKER=1",
               image, "sh", "-ec",
               "apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && "
               'exec python3 /repo/tools/system-build.py _worker "$@"',
               "fontreal", str(jobs), str(os.getuid()), str(os.getgid())]
    run(command)
    check_plan(plan)
    if sha(Path(__file__)) != builder_digest:
        raise ValueError("The build recipe changed during compilation. Make a new build.")
    (destination / "source/build-tool.py").write_bytes(builder_source)
    metadata = json.loads((destination / "build.json").read_text())
    metadata["image"] = json.loads(output(["docker", "image", "inspect", image]))[0]["Id"]
    metadata["git"] = output(["git", "-C", ROOT, "rev-parse", "HEAD"])
    metadata["builder_sha256"] = builder_digest
    write_json(destination / "build.json", metadata)
    artifacts = []
    for role in ("packages", "original", "source"):
        files = sorted((destination / role).iterdir())
        if not files:
            raise ValueError(f"The build did not emit its {role} artifacts.")
        for path in files:
            artifacts.append(dict(path=str(path.relative_to(destination)), sha256=sha(path)))
    for filename in ("system.json", "build.json"):
        artifacts.append(dict(path=filename, sha256=sha(destination / filename)))
    manifest = dict(schema=1, artifacts=artifacts)
    verify_artifacts(destination, manifest)
    write_json(destination / "bundle.json", manifest)
    print(f"Built packages and corresponding source: {destination}")
    print("No host packages were installed. Session activation is not enabled.")


def worker(jobs):
    if os.environ.get("FONTREAL_BUILD_WORKER") != "1" or not Path("/.dockerenv").is_file():
        raise ValueError("The build worker runs only inside its disposable Docker container.")
    target = Path("/output")
    plan = json.loads((target / "system.json").read_text())
    _, upstream = check_plan(plan)
    qt_v3 = v3_plan(plan)
    for path in Path("/etc/apt/sources.list.d").glob("*.sources"):
        path.write_text(re.sub(r"^Types: deb$", "Types: deb deb-src", path.read_text(), flags=re.M))
    foreign_freetype = any(p["source"] == "freetype" and p["arch"] == "i386" for p in plan["original"])
    if foreign_freetype:
        run(["dpkg", "--add-architecture", "i386"])
    run(["apt-get", "update"])
    run(["apt-get", "install", "-y", "--no-install-recommends", "build-essential", "devscripts",
         "equivs", "ninja-build", "quilt", "pkg-kde-tools"])
    for role in ("packages", "original", "source"):
        (target / role).mkdir()
    run(["apt-get", "download", *[f"{p['name']}:{p['arch']}={p['version']}" for p in plan["original"]]],
        cwd=target / "original")
    metadata = dict(build_options=f"parallel={jobs} nocheck noddebs", build_profiles="noudeb",
                    cxxflags="-g0", dependencies={})
    metadata["selected"] = (plan["sources"]["qt6-base"]["selected"] if qt_v3 else selected_inputs())
    build_environment = dict(os.environ, DEB_BUILD_PROFILES=metadata["build_profiles"])
    for source in QT_SOURCES if qt_v3 else SOURCES:
        parent = Path("/tmp/fontreal") / source
        parent.mkdir(parents=True)
        entry = plan["sources"][source]
        run(["apt-get", "source", "--only-source", f"{source}={entry['version']}"], cwd=parent)
        candidates = [p for p in parent.iterdir() if p.is_dir() and (p / "debian/control").is_file()]
        if len(candidates) != 1:
            raise ValueError(f"Expected one unpacked {source} source tree.")
        tree = candidates[0]
        (tree / "debian/patches").mkdir(exist_ok=True)
        patches = [("fontreal.patch", patch_file(source, upstream, qt_v3))]
        if source == "freetype":
            patches.append(("fontreal-render.patch", ROOT / "patches/freetype-2.14.2-fontreal.patch"))
        patches.append(("fontreal-capability.patch", capability_patch(source, qt_v3)))
        for patch_name, patch in patches:
            if patch is None:
                continue
            run(["patch", "--batch", "--fuzz=0", "--dry-run", "-p1", "-i", patch], cwd=tree)
            shutil.copyfile(patch, tree / "debian/patches" / patch_name)
            with (tree / "debian/patches/series").open("a") as queue:
                queue.write("\n" + patch_name + "\n")
            run(["dpkg-source", "--before-build", tree])
        if source == "freetype" or (qt_v3 and source == "qt6-base"):
            # The generated quilt patch keeps the unchanged core in corresponding source.
            if qt_v3:
                processor_path = "src/gui/text/freetype/"
                files = V3_FILES
                license_path = "LICENSES/Fontreal-MIT.txt"
            else:
                processor_path = "src/base/"
                files = ("fontreal_coverage.cpp", "fontreal_coverage.h", "fontreal_v2_coverage.cpp",
                         "fontreal_v2_coverage.h")
                license_path = "docs/FONTREAL-MIT.TXT"
            additions = {processor_path + name: (ROOT / "src" / name).read_text() for name in files}
            license_text = (ROOT / "LICENSE").read_text()
            additions[license_path] = license_text
            copyright_file = tree / "debian/copyright"
            copyright_text = copyright_file.read_text()
            stanza = ("\nFiles: " + " ".join(additions) + "\n"
                      "Copyright: 2026 Michael Beutler and Fontreal contributors\nLicense: Fontreal-MIT\n "
                      + "\n ".join(line if line else "." for line in license_text.splitlines()) + "\n")
            patch_text = "".join("".join(difflib.unified_diff([], text.splitlines(keepends=True),
                fromfile="/dev/null", tofile="b/" + name)) for name, text in additions.items())
            copyright_file.write_text(copyright_text + stanza)
            (tree / "debian/patches/fontreal-processor.patch").write_text(patch_text)
            with (tree / "debian/patches/series").open("a") as queue:
                queue.write("fontreal-processor.patch\n")
            run(["dpkg-source", "--before-build", tree])
        env = dict(build_environment, DEBEMAIL="fontreal@localhost", DEBFULLNAME="Fontreal local build",
                   DEB_BUILD_OPTIONS=metadata["build_options"], DEB_CXXFLAGS_MAINT_APPEND="-g0")
        run(["dch", "--newversion", entry["build_version"], "--distribution", "UNRELEASED",
             "Apply the local Fontreal rendering patch."], cwd=tree, env=env)
        run(["apt-get", "build-dep", "-y", "--no-install-recommends", "--arch-only",
             f"{source}={entry['version']}"], env=build_environment)
        metadata["dependencies"][source] = output(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"])
        run(["dpkg-buildpackage", "--build=source,any", "-us", "-uc", "-tc", f"-j{jobs}"], cwd=tree, env=env)
        binaries = sorted(parent.glob("*.deb"))
        if not binaries:
            raise ValueError(f"No binary packages were built for {source}.")
        for path in parent.iterdir():
            if path.is_file():
                shutil.copyfile(path, target / ("packages" if path.suffix == ".deb" else "source") / path.name)
        if source in ("freetype", "qt6-base"):
            run(["apt-get", "install", "-y", "--no-install-recommends", *binaries])
        shutil.rmtree(parent)
    if foreign_freetype:
        # Debian 13 has no i386 container image; use the distro's native cross toolchain.
        parent = Path("/tmp/fontreal/freetype-i386")
        parent.mkdir(parents=True)
        entry = plan["sources"]["freetype"]
        tree = parent / "source"
        descriptor = source_descriptor(target / "source", "freetype", entry["build_version"])
        run(["dpkg-source", "--no-check", "-x", descriptor, tree])
        run(["apt-get", "install", "-y", "--no-install-recommends", "crossbuild-essential-i386", "libstdc++6:i386"])
        run(["apt-get", "build-dep", "-y", "--no-install-recommends", "--arch-only", "-a", "i386",
             f"freetype={entry['version']}"], env=build_environment)
        metadata["dependencies"]["freetype:i386"] = output(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"])
        run(["dpkg-buildpackage", "--build=any", "-ai386", "-us", "-uc", "-tc", f"-j{jobs}"], cwd=tree, env=env)
        for path in parent.iterdir():
            if path.is_file():
                shutil.copyfile(path, target / ("packages" if path.suffix == ".deb" else "source") / path.name)
        shutil.rmtree(parent)
    produced = package_inventory(target / "packages")
    for p in plan["original"]:
        if produced.get((p["name"], p["arch"]), {}).get("version") != plan["sources"][p["source"]]["build_version"]:
            raise ValueError(f"Missing rebuilt counterpart for {p['name']}.")
    write_json(target / "build.json", metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan", help="Print a build plan for the running supported system.")
    plan_parser.add_argument("--qt-v3", action="store_true", help="Build V3 Qt packages with stock FreeType APIs.")
    build_parser = sub.add_parser("build", help="Build an existing system plan in a disposable container.")
    build_parser.add_argument("plan", type=Path)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--jobs", type=int, default=4)
    verify_parser = sub.add_parser("verify", help="Verify a complete local build bundle.")
    verify_parser.add_argument("bundle", type=Path)
    prepare_parser = sub.add_parser("prepare", help="Prepare a separate disabled Plasma session package.")
    prepare_parser.add_argument("bundle", type=Path)
    for command in ("install", "rollback"):
        transaction_parser = sub.add_parser(command, help="Apply the verified local packages." if command == "install" else "Restore the retained official packages.")
        transaction_parser.add_argument("bundle", type=Path)
        transaction_parser.add_argument("--simulate", action="store_true")
        if command == "rollback":
            transaction_parser.add_argument("--previous", type=Path, help="Verified predecessor bundle for Qt V3 rollback.")
    worker_parser = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("jobs", type=int)
    worker_parser.add_argument("uid", type=int)
    worker_parser.add_argument("gid", type=int)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            print(json.dumps(system_plan(args.qt_v3), indent=2, sort_keys=True))
        elif args.command == "build":
            if not 1 <= args.jobs <= 64:
                raise ValueError("Build parallelism must be between 1 and 64.")
            build(args.plan, args.output, args.jobs)
        elif args.command == "verify":
            plan = verify_artifacts(args.bundle, json.loads((args.bundle / "bundle.json").read_text()))
            if (args.bundle / "deployment.json").exists():
                import system_install
                system_install.verify_activation(sys.modules[__name__], args.bundle, json.loads((args.bundle / "deployment.json").read_text()), plan)
            print("Complete package, original-package, and source inventories match their checksums.")
        elif args.command in ("prepare", "install", "rollback"):
            import system_install
            if args.command == "prepare":
                system_install.prepare(sys.modules[__name__], args.bundle.resolve())
            else:
                system_install.transaction(sys.modules[__name__], args.bundle.resolve(), rollback=args.command == "rollback",
                                           simulate=args.simulate, previous=getattr(args, "previous", None))
        else:
            owner = Path("/output").stat() if Path("/output").is_dir() else None
            try:
                worker(args.jobs)
            finally:
                if Path("/.dockerenv").is_file() and Path("/output").is_dir():
                    for directory, dirs, files in os.walk("/output"):
                        for name in dirs + files:
                            os.chown(Path(directory) / name, owner.st_uid, owner.st_gid, follow_symlinks=False)
                    os.chown("/output", owner.st_uid, owner.st_gid)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
