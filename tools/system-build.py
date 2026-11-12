#!/usr/bin/env python3
"""Build, verify, and apply matching distro Qt packages for this system."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    ("debian", "13"): ("debian:13-slim", "6.8.2"),
    ("ubuntu", "26.04"): ("ubuntu:26.04", "6.10.2"),
}
SOURCES = ("qt6-base", "qt6-declarative")
FIELDS = "${Package}\t${Architecture}\t${Version}\t${source:Package}\t${source:Version}\t${db:Status-Status}\n"


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


def patch_file(source, upstream):
    name = "qt" if source == "qt6-base" else "qtdeclarative"
    return ROOT / "patches" / f"{name}-{upstream}-fontreal.patch"


def capability_patch(source):
    return ROOT / "packaging" / f"{source}-capability.patch"


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
    profile = PROFILES.get((plan["os"], plan["release"]))
    if plan["schema"] != 1 or not profile or plan["arch"] != "amd64":
        raise ValueError("Supported systems: Debian 13 and Ubuntu 26.04, native amd64.")
    if set(plan["sources"]) != set(SOURCES) or not plan["installed"] or not plan["original"]:
        raise ValueError("The plan needs both Qt source families and their installed package sets.")
    if not re.fullmatch(r"[0-9]{14}", plan["identity"]):
        raise ValueError("Invalid numeric build identity.")
    for key in ("installed", "original"):
        records = plan[key]
        identities = [(p["name"], p["arch"]) for p in records]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate package identity in the system plan.")
        if {p["source"] for p in records} != set(SOURCES):
            raise ValueError("The package set must include both Qt source families.")
        for p in records:
            if p["arch"] != plan["arch"] or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", p["name"]):
                raise ValueError("Foreign-architecture or invalid Qt package in the plan.")
    if {(p["name"], p["arch"]) for p in plan["installed"]} != {(p["name"], p["arch"]) for p in plan["original"]}:
        raise ValueError("Original and installed package identities differ.")
    if not {"libqt6gui6", "libqt6quick6"} <= {p["name"] for p in plan["installed"]}:
        raise ValueError("Install the native QtGui and QtQuick runtimes before making a system plan.")
    for source in SOURCES:
        entry = plan["sources"][source]
        if not re.fullmatch(re.escape(profile[1]) + r"\+dfsg-[A-Za-z0-9.+~]+", entry["version"]):
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
        if not all(re.fullmatch(r"[0-9a-f]{64}", entry[key]) for key in ("patch_sha256", "capability_sha256")):
            raise ValueError("Invalid patch checksum in the system plan.")
        if current_patches and entry["patch_sha256"] != sha(patch_file(source, profile[1])):
            raise ValueError("The plan patch changed. Make a new plan before building.")
        if current_patches and entry["capability_sha256"] != sha(capability_patch(source)):
            raise ValueError("The package capability patch changed. Make a new plan before building.")
    return profile


def system_plan():
    system = platform.freedesktop_os_release()
    key = (system["ID"], system["VERSION_ID"])
    if key not in PROFILES:
        raise ValueError("Supported systems: Debian 13 and Ubuntu 26.04.")
    records = installed()
    original = [dict(p) for p in records]
    previous = Path("/usr/share/fontreal/system.json")
    if any("afontreal" in p["source_version"] for p in records):
        if not previous.is_file():
            raise ValueError("The installed Fontreal source record is missing. Restore official Qt before rebuilding.")
        old = json.loads(previous.read_text())
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
                identity=identity, installed=records, original=original, sources={})
    for source in SOURCES:
        versions = {p["source_version"] for p in original if p["source"] == source}
        if len(versions) != 1:
            raise ValueError(f"Install a coherent official {source} package set before building.")
        version = versions.pop()
        base = version
        for p in original:
            if p["source"] == source and newer(p["version"], base):
                base = p["version"]
        plan["sources"][source] = dict(version=version, build_version=local_version(base, identity),
                                          patch_sha256=sha(patch_file(source, PROFILES[key][1])),
                                          capability_sha256=sha(capability_patch(source)))
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
    original = package_inventory(directory / "original")
    expected_original = {(p["name"], p["arch"]): p["version"] for p in plan["original"]}
    if {k: v["version"] for k, v in original.items()} != expected_original:
        raise ValueError("The official rollback package set is incomplete or has different versions.")
    for p in plan["original"]:
        candidate = built.get((p["name"], p["arch"]))
        if (not candidate or candidate["version"] != plan["sources"][p["source"]]["build_version"]
                or candidate["source"].split()[0] != p["source"]):
            raise ValueError(f"Missing rebuilt counterpart for {p['name']}.")
    for source in SOURCES:
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
    for path in Path("/etc/apt/sources.list.d").glob("*.sources"):
        path.write_text(re.sub(r"^Types: deb$", "Types: deb deb-src", path.read_text(), flags=re.M))
    run(["apt-get", "update"])
    run(["apt-get", "install", "-y", "--no-install-recommends", "build-essential", "devscripts",
         "equivs", "ninja-build", "quilt", "pkg-kde-tools"])
    for role in ("packages", "original", "source"):
        (target / role).mkdir()
    run(["apt-get", "download", *[f"{p['name']}:{p['arch']}={p['version']}" for p in plan["original"]]],
        cwd=target / "original")
    metadata = dict(build_options=f"parallel={jobs} nocheck noddebs", cxxflags="-g0", dependencies={})
    for source in SOURCES:
        parent = Path("/tmp/fontreal") / source
        parent.mkdir(parents=True)
        entry = plan["sources"][source]
        run(["apt-get", "source", "--only-source", f"{source}={entry['version']}"], cwd=parent)
        candidates = [p for p in parent.iterdir() if p.is_dir() and (p / "debian/control").is_file()]
        if len(candidates) != 1:
            raise ValueError(f"Expected one unpacked {source} source tree.")
        tree = candidates[0]
        (tree / "debian/patches").mkdir(exist_ok=True)
        for patch_name, patch in (("fontreal.patch", patch_file(source, upstream)),
                                  ("fontreal-capability.patch", capability_patch(source))):
            run(["patch", "--batch", "--fuzz=0", "--dry-run", "-p1", "-i", patch], cwd=tree)
            shutil.copyfile(patch, tree / "debian/patches" / patch_name)
            with (tree / "debian/patches/series").open("a") as queue:
                queue.write("\n" + patch_name + "\n")
            run(["dpkg-source", "--before-build", tree])
        env = dict(os.environ, DEBEMAIL="fontreal@localhost", DEBFULLNAME="Fontreal local build",
                   DEB_BUILD_OPTIONS=metadata["build_options"], DEB_CXXFLAGS_MAINT_APPEND="-g0")
        run(["dch", "--newversion", entry["build_version"], "--distribution", "UNRELEASED",
             "Apply the local Fontreal rendering patch."], cwd=tree, env=env)
        run(["apt-get", "build-dep", "-y", "--no-install-recommends", "--arch-only",
             f"{source}={entry['version']}"])
        metadata["dependencies"][source] = output(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"])
        run(["dpkg-buildpackage", "--build=source,any", "-us", "-uc", "-tc", f"-j{jobs}"], cwd=tree, env=env)
        binaries = sorted(parent.glob("*.deb"))
        if not binaries:
            raise ValueError(f"No binary packages were built for {source}.")
        for path in parent.iterdir():
            if path.is_file():
                shutil.copyfile(path, target / ("packages" if path.suffix == ".deb" else "source") / path.name)
        if source == "qt6-base":
            run(["apt-get", "install", "-y", "--no-install-recommends", *binaries])
        shutil.rmtree(parent)
    produced = package_inventory(target / "packages")
    for p in plan["original"]:
        if produced.get((p["name"], p["arch"]), {}).get("version") != plan["sources"][p["source"]]["build_version"]:
            raise ValueError(f"Missing rebuilt counterpart for {p['name']}.")
    write_json(target / "build.json", metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Print a build plan for the running supported system.")
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
    worker_parser = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("jobs", type=int)
    worker_parser.add_argument("uid", type=int)
    worker_parser.add_argument("gid", type=int)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            print(json.dumps(system_plan(), indent=2, sort_keys=True))
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
                system_install.transaction(sys.modules[__name__], args.bundle.resolve(), rollback=args.command == "rollback", simulate=args.simulate)
        else:
            try:
                worker(args.jobs)
            finally:
                if Path("/.dockerenv").is_file() and Path("/output").is_dir():
                    for directory, dirs, files in os.walk("/output"):
                        for name in dirs + files:
                            os.chown(Path(directory) / name, args.uid, args.gid, follow_symlinks=False)
                    os.chown("/output", args.uid, args.gid)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
