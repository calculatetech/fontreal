"""Resolve an installed, package-recorded Fontreal build to its official provider."""
import json
from pathlib import Path
import stat
import subprocess


def official_version(version):
    if "afontreal" not in version:
        return version
    try:
        return recorded_version(version)
    except (OSError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise ValueError("Cannot verify the installed Fontreal FreeType provider record.") from error


def recorded_version(version):
    record = Path("/usr/share/fontreal/system.json")
    for path in (record, record.parent, record.parent.parent):
        metadata = path.lstat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022 or stat.S_ISLNK(metadata.st_mode):
            raise ValueError("The installed Fontreal source record is not trusted.")
    plan = json.loads(record.read_text())
    entry = plan["sources"]["freetype"]
    fields = "${Version}\t${source:Package}\t${source:Version}\t${db:Status-Status}"
    installed = subprocess.check_output(
        ["dpkg-query", "-W", "-f=" + fields, "libfreetype6:amd64"], text=True).split("\t")
    if installed != [version, "freetype", entry["build_version"], "installed"] or version != entry["build_version"]:
        raise ValueError("Installed FreeType does not match its Fontreal source record.")
    original = [p for p in plan["original"] if (p["name"], p["arch"]) == ("libfreetype6", "amd64")]
    if (len(original) != 1 or original[0]["source"] != "freetype"
            or original[0]["source_version"] != entry["version"]
            or original[0]["version"] != entry["version"] or "afontreal" in entry["version"]):
        raise ValueError("The exact official FreeType provider is missing from its source record.")
    return entry["version"]
