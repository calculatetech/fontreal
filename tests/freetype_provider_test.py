#!/usr/bin/env python3
"""Verify exact provider mapping and refusal of untrusted local identities."""
import copy
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from freetype_provider import official_version
import freetype_provider as provider


def main():
    official = "2.13.3+dfsg-1+deb13u1"
    local = official + "afontreal20261113210000"
    base = dict(sources={"freetype": dict(version=official, build_version=local)},
                original=[dict(name="libfreetype6", arch="amd64", source="freetype",
                               version=official, source_version=official)])
    trusted = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644)
    assert official_version(official) == official
    assert official_version("unknown-official-version") == "unknown-official-version"
    with tempfile.TemporaryDirectory(prefix="provider-", dir=ROOT / "build") as directory:
        record = Path(directory) / "system.json"
        record.write_text(json.dumps(base))
        with patch.object(provider, "Path", return_value=record):
            try:
                official_version(local)
            except ValueError:
                pass
            else:
                raise AssertionError("An ordinary user-owned source record was trusted")
            fields = "\t".join([local, "freetype", local, "installed"])
            with patch.object(Path, "lstat", return_value=trusted), \
                    patch.object(provider.subprocess, "check_output", return_value=fields) as query:
                assert official_version(local) == official
                assert query.call_args.args[0][-1] == "libfreetype6:amd64"
                for changed in (
                    dict(sources={"freetype": dict(version=official, build_version=local+"1")}),
                    dict(original=[]), dict(original=base["original"] * 2),
                    dict(original=[dict(base["original"][0], source="other")]),
                    dict(original=[dict(base["original"][0], source_version=official+".1")]),
                    dict(original=[dict(base["original"][0], version=official+".1")]),
                ):
                    plan = copy.deepcopy(base)
                    plan.update(changed)
                    record.write_text(json.dumps(plan))
                    try:
                        official_version(local)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError(changed)
                record.write_text(json.dumps(base))
                for replacement in ("\t".join([local,"other",local,"installed"]),
                                    "\t".join([local,"freetype",official,"installed"]),
                                    "\t".join([local,"freetype",local,"not-installed"])):
                    with patch.object(provider.subprocess, "check_output", return_value=replacement):
                        try:
                            official_version(local)
                        except ValueError:
                            pass
                        else:
                            raise AssertionError(replacement)
                record.unlink()
                try:
                    official_version(local)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Missing source record was accepted")
            for metadata in (SimpleNamespace(st_uid=1000, st_mode=stat.S_IFREG|0o644),
                             SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG|0o664),
                             SimpleNamespace(st_uid=0, st_mode=stat.S_IFLNK|0o777)):
                with patch.object(Path, "lstat", return_value=metadata):
                    try:
                        official_version(local)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Untrusted source-record owner or mode")
    print("PASS exact native FreeType provider mapping, version ties and trust refusal")


if __name__ == "__main__":
    main()
