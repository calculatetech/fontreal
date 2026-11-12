#!/usr/bin/env python3
"""Check deployment metadata with real small .deb archives, not Qt payloads."""
import copy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import system_build_test as fixtures

build = fixtures.build
ROOT = fixtures.ROOT


def cli(*args, success=True, env=None):
    result = subprocess.run([sys.executable, ROOT / "tools/system-build.py", *map(str, args)],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert (result.returncode == 0) == success, (args, result.stdout, result.stderr)
    return result


def report(directory, name, **changes):
    record = dict(schema=1, passed=True, bundle_sha256=build.sha(directory / "bundle.json"),
                  deployment_sha256=build.sha(directory / "deployment.json"))
    if name == "package-checks":
        record["updates"] = [dict(source=source) for source in build.SOURCES]
    else:
        record["complete_runtime"] = True
    record.update(changes)
    target = directory / name
    target.mkdir(exist_ok=True)
    build.write_json(target / ("package-results.json" if name == "package-checks" else "session-results.json"), record)


def rejected_install(directory, env, reason):
    result = cli("install", directory, "--simulate", success=False, env=env)
    assert reason in result.stderr, (reason, result.stderr)


def main():
    # These synthetic archives test metadata and rejection. Real package/session
    # runners establish rendering, APT application, and activation behavior.
    with tempfile.TemporaryDirectory(prefix="fontreal-install-") as temporary:
        root = Path(temporary)
        targets = []
        for name, release, upstream, base, declarative in (
                ("debian", "13", "6.8.2", "6.8.2+dfsg-9+deb13u2", "6.8.2+dfsg-7"),
                ("ubuntu", "26.04", "6.10.2", "6.10.2+dfsg-7", "6.10.2+dfsg-3")):
            plan = fixtures.fixture(name, release, upstream, base, declarative)
            directory = root / name
            directory.mkdir()
            native = fixtures.bundle(directory, plan)
            native_hash = build.sha(directory / "bundle.json")
            cli("prepare", directory)
            assert build.sha(directory / "bundle.json") == native_hash
            assert all(build.sha(directory / a["path"]) == a["sha256"] for a in native["artifacts"])
            cli("verify", directory)
            cli("prepare", directory, success=False)
            path = directory / "deployment.json"
            deployment = json.loads(path.read_text())
            for artifacts in ([], deployment["artifacts"][:-1], [*deployment["artifacts"], deployment["artifacts"][0]]):
                build.write_json(path, dict(deployment, artifacts=artifacts))
                cli("verify", directory, success=False)
            build.write_json(path, deployment)
            notice = directory / "activation/NOTICE"
            original = notice.read_bytes()
            notice.write_bytes(original + b"altered\n")
            cli("verify", directory, success=False)
            notice.write_bytes(original)
            cli("verify", directory)
            targets.append((directory, plan))

        directory, plan = targets[0]
        staging = root / "wrong-session"
        archive = directory / "activation/fontreal-session.deb"
        original_archive = archive.read_bytes()
        original_deployment = (directory / "deployment.json").read_bytes()
        build.run(["dpkg-deb", "-R", archive, staging])
        versions = staging / "usr/share/fontreal/runtime-versions"
        lines = versions.read_text().splitlines(keepends=True)
        lines[1] = lines[1].rstrip("\n") + "1\n"
        versions.write_text("".join(lines))
        build.run(["dpkg-deb", "--build", "--root-owner-group", staging, archive])
        path = directory / "deployment.json"
        deployment = json.loads(path.read_text())
        for artifact in deployment["artifacts"]:
            if artifact["path"] == "activation/fontreal-session.deb":
                artifact["sha256"] = build.sha(archive)
        build.write_json(path, deployment)
        assert "runtime versions" in cli("verify", directory, success=False).stderr
        archive.write_bytes(original_archive)
        path.write_bytes(original_deployment)
        cli("verify", directory)

        # Model only the external dpkg discovery boundary for pre-APT rejection.
        # No fake APT result is used to claim successful application.
        system = platform.freedesktop_os_release()
        directory, plan = next((d, p) for d, p in targets if (p["os"], p["release"]) == (system["ID"], system["VERSION_ID"]))
        provider = root / "provider"
        provider.mkdir()
        records = provider / "records.json"
        build.write_json(records, plan["installed"])
        invoked = provider / "apt-was-invoked"
        query = provider / "dpkg-query"
        query.write_text("#!/usr/bin/env python3\nimport json\nfrom pathlib import Path\n"
                         f"records=json.loads(Path({str(records)!r}).read_text())\n"
                         "for p in records:\n print('\\t'.join([p['name'],p['arch'],p['version'],p['source'],p['source_version'],'installed']))\n")
        query.chmod(0o755)
        apt = provider / "apt-get"
        apt.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\n"
                       f"Path({str(invoked)!r}).write_text('unexpected APT call')\nraise SystemExit(91)\n")
        apt.chmod(0o755)
        env = dict(os.environ, PATH=str(provider) + os.pathsep + os.environ["PATH"])
        rejected_install(directory, env, "package-results.json")
        assert not invoked.exists()
        report(directory, "session-checks")
        for changes, reason in (({"passed": False}, "package-results.json"),
                                ({"updates": []}, "--updates"),
                                ({"updates": [{"source": "qt6-base"}, {"source": "qt6-base"}]}, "--updates"),
                                ({"updates": [{"source": "qt6-base"}, {"source": "qt6-declarative"},
                                               {"source": "qt6-declarative"}]}, "--updates"),
                                ({"deployment_sha256": "0" * 64}, "package-results.json")):
            report(directory, "package-checks", **changes)
            rejected_install(directory, env, reason)
            assert not invoked.exists()
        report(directory, "package-checks")
        for changes, reason in (({"passed": False}, "session-results.json"),
                                ({"complete_runtime": False}, "session checks"),
                                ({"bundle_sha256": "0" * 64}, "session-results.json")):
            report(directory, "session-checks", **changes)
            rejected_install(directory, env, reason)
            assert not invoked.exists()
        report(directory, "session-checks")
        changed = copy.deepcopy(plan["installed"])
        for p in changed:
            if p["source"] == "qt6-declarative":
                p["version"] = plan["sources"][p["source"]]["version"] + ".1"
                p["source_version"] = p["version"]
        build.write_json(records, changed)
        rejected_install(directory, env, "versions changed")
        assert not invoked.exists()
    print("PASS: immutable native input, both deployment profiles, complete activation inventories, late Quick mismatch and pre-APT validation/snapshot rejection")


if __name__ == "__main__":
    main()
