#!/usr/bin/env python3
"""Build paired private FreeType libraries for the first browser mask experiment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORK = (ROOT / "build/freetype-native").resolve()
VERSION = "2.14.2+dfsg-1ubuntu0.2"
PATCH = ROOT / "patches/freetype-2.14.2-fontreal.patch"
TRACE = ROOT / "tests/freetype_browser_trace.h"
# These exact archives were checked against Ubuntu's authenticated source index.
ARCHIVES = {
    "freetype_2.14.2+dfsg-1ubuntu0.2.dsc": "37305c65f89ccfdbfdaafba675a203865603180eedd44578fb30a3b38dc6ae0c",
    "freetype_2.14.2+dfsg.orig.tar.xz": "9a2bdc2c992fa82a309eccf5e8bcbf2a380a98ba22f9f2ec7e56767739a19a0a",
    "freetype_2.14.2+dfsg.orig-ft2demos.tar.xz": "ae9ed4b095e73a3fbdb90363c138ea62ac4b0f55aa4bb345b9b2458783f9284f",
    "freetype_2.14.2+dfsg.orig-ft2docs.tar.xz": "0514edfd6a7b480f753aa48789d7112038a218b0b06afdca320c4bcbc2f66e6b",
    "freetype_2.14.2+dfsg.orig-ft2demos.tar.xz.asc": "96e70ae6a1ee502ad6be9ec37ed32e11cb95f14d074863b9ca167468ccb0a8d9",
    "freetype_2.14.2+dfsg.orig-ft2docs.tar.xz.asc": "67ca2966fa57ab5324c87c61dd7bd8ead5101e15e162dcf6b33705c6b5f331ad",
    "freetype_2.14.2+dfsg-1ubuntu0.2.debian.tar.xz": "285fbbf6b784ff571b1751f5c410fc5b3e2c13ce0e1dd7d6708dadf3d81e009b",
}
HEADERS = {
    "libharfbuzz-dev": "libharfbuzz0b",
    "libfreetype-dev": "libfreetype6",
    "libpng-dev": "libpng16-16t64",
    "libbrotli-dev": "libbrotli1",
    "libbz2-dev": "libbz2-1.0",
    "zlib1g-dev": "zlib1g",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output(command):
    return subprocess.check_output(command, text=True).strip()


def installed(package):
    return output(["dpkg-query", "-W", "-f=${Version}", package + ":amd64"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", action="store_true", help="Observe real browser masks in test builds")
    args = parser.parse_args()
    if platform.machine() != "x86_64" or installed("libfreetype6") != VERSION:
        parser.error(f"This first prototype requires amd64 FreeType {VERSION}; it does not install packages.")
    headers = {dev: installed(runtime) for dev, runtime in HEADERS.items()}
    spec = dict(source=VERSION, archives=ARCHIVES, headers=headers, patch=sha(PATCH),
                recipe=sha(Path(__file__)),
                trace=sha(TRACE) if args.trace else None,
                compiler=output(["cc", "--version"]).splitlines()[0])
    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:20]
    destination = WORK / "artifacts" / key
    record = destination / "build.json"
    if record.exists():
        saved = json.loads(record.read_text())
        if saved["spec"] != spec or any(sha(Path(v["library"])) != v["sha256"] for v in saved["libraries"].values()):
            raise SystemExit("Private FreeType artifact no longer matches its recorded inputs.")
        print(record)
        return
    destination.mkdir(parents=True)
    WORK.mkdir(parents=True, exist_ok=True)
    temporary = WORK / "tmp"
    temporary.mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(temporary))
    for name, digest in ARCHIVES.items():
        path = WORK / name
        if not path.exists():
            url = "https://security.ubuntu.com/ubuntu/pool/main/f/freetype/" + name
            with urllib.request.urlopen(url, timeout=120) as response:
                path.write_bytes(response.read())
        if sha(path) != digest:
            raise SystemExit(f"Source checksum mismatch: {path}")
    deps = destination / "headers"
    deps.mkdir()
    subprocess.run(["apt-get", "download", *[f"{name}={version}" for name, version in headers.items()]],
                   cwd=deps, env=env, check=True)
    debs = list(deps.glob("*.deb"))
    if len(debs) != len(headers):
        raise SystemExit("Missing private development packages.")
    for deb in debs:
        subprocess.run(["dpkg-deb", "-x", str(deb), str(deps)], env=env, check=True)
    prefix = deps / "usr"
    for pc in prefix.rglob("*.pc"):
        pc.write_text(pc.read_text().replace("prefix=/usr", f"prefix={prefix}"))
    for link in prefix.rglob("*.so"):
        if link.is_symlink() and not link.exists():
            target = Path("/usr") / link.resolve().relative_to(prefix)
            if target.exists():
                link.unlink()
                link.symlink_to(target)
    stock_source = destination / "stock-source"
    # Pinned archive hashes above provide authentication; no key download is needed.
    subprocess.run(["dpkg-source", "--no-check", "-x", str(WORK / next(iter(ARCHIVES))),
                    str(stock_source)], env=env, check=True)
    candidate_source = destination / "candidate-source"
    shutil.copytree(stock_source, candidate_source, symlinks=True)
    subprocess.run(["patch", "--batch", "-p1", "-i", str(PATCH)], cwd=candidate_source, env=env, check=True)
    env["PKG_CONFIG_PATH"] = str(prefix / "lib/x86_64-linux-gnu/pkgconfig")
    env["CC"] = "cc"
    env["CFLAGS"] = "-O2" + (f" -DFONTREAL_TEST_TRACE -include {TRACE}" if args.trace else "")
    libraries = {}
    for mode, source in (("stock", stock_source), ("candidate", candidate_source)):
        build = destination / mode
        build.mkdir()
        command = [str(source / "configure"), f"--prefix={destination / (mode + '-install')}",
                   "--with-harfbuzz=dynamic"]
        with (build / "configure.log").open("w") as log:
            subprocess.run(command, cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        configured = (build / "configure.log").read_text()
        for feature in ("external zlib: yes", "bzip2:         yes", "libpng:        yes",
                        "harfbuzz:      yes (dynamic)", "brotli:        yes", "pthread:       yes"):
            if feature not in configured:
                raise SystemExit(f"Private build is missing a distro feature: {feature}; see {build / 'configure.log'}")
        with (build / "build.log").open("w") as log:
            subprocess.run(["make", f"-j{min(12, os.cpu_count() or 1)}"], cwd=build, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        library = (build / ".libs/libfreetype.so.6").resolve()
        libraries[mode] = dict(library=str(library), sha256=sha(library), configure=command,
                               cflags=env["CFLAGS"],
                               dependencies=output(["ldd", str(library)]))
    # Addresses change; public symbol names and types must not.
    exports = [{tuple(line.split()[1:]) for line in output(
        ["nm", "-D", "--defined-only", v["library"]]).splitlines()} for v in libraries.values()]
    if exports[0] != exports[1]:
        raise SystemExit("Private FreeType public exports differ from the stock control.")
    shutil.copyfile(stock_source / "docs/FTL.TXT", destination / "FTL.TXT")
    (destination / "NOTICE").write_text(
        "Based in part on the work of the FreeType Team.\n"
        "Portions are copyright 1996-2025 The FreeType Project (https://freetype.org).\n"
        "The candidate adds opt-in monochrome-target grayscale masks and mild contrast.\n"
        "See FTL.TXT, the retained source notices, and the Fontreal patch.\n")
    record.write_text(json.dumps(dict(spec=spec, libraries=libraries,
                                    header_packages={d.name: sha(d) for d in debs}), indent=2) + "\n")
    print(record)


if __name__ == "__main__":
    main()
