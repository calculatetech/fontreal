#!/usr/bin/env python3
"""Check deployment metadata with real small .deb archives, not Qt payloads."""
import copy
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import types

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import system_build_test as fixtures

build = fixtures.build
ROOT = fixtures.ROOT
LEGACY_BASE = "6ae8559d14f2448cd24f320f8d4c480669c80e0c"


def retained_activation(directory, plan):
    # Use the actual old producer and source, not a new package relabeled as old.
    with tempfile.TemporaryDirectory(prefix="fontreal-retained-source-") as temporary:
        source = Path(temporary)
        for name in ("tools/system_install.py", "packaging/session/fontreal-session", "packaging/session/fontreal.sh", "packaging/session/NOTICE"):
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.check_output(["git", "show", f"{LEGACY_BASE}:{name}"], cwd=ROOT))
        spec = importlib.util.spec_from_file_location("retained_installer", source / "tools/system_install.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        builder = types.SimpleNamespace(**vars(build))
        builder.ROOT = source
        installer.activation(builder, directory, plan)
    deployment = dict(schema=1, bundle_sha256=build.sha(directory / "bundle.json"), artifacts=[
        dict(path=str(path.relative_to(directory)), sha256=build.sha(path))
        for path in sorted((directory / "activation").iterdir())])
    build.write_json(directory / "deployment.json", deployment)


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


def retained_native(directory):
    assert Path("/var/lib/fontreal-test-ready").is_file(), "Use the marked disposable VM."
    subprocess.run(["systemd-detect-virt", "--vm"], check=True, capture_output=True)
    metadata = json.loads((directory / "build.json").read_text())
    assert metadata.get("representative_retained_schema1") is True, "Do not label these current Qt payloads as a historical build."
    cli("verify", directory)
    plan = build.verify_artifacts(directory, json.loads((directory / "bundle.json").read_text()))
    assert set(plan["sources"]) == {"qt6-base", "qt6-declarative"}
    before = build.installed()
    assert [p for p in before if p["source"] in plan["sources"]] == plan["original"]
    unowned = [p for p in before if p["source"] == "freetype"]
    assert {p["arch"] for p in unowned} == {"amd64", "i386"}
    inventory = build.package_inventory(directory / "packages")
    selected = [directory / "packages" / inventory[(p["name"], p["arch"])]["path"] for p in plan["installed"]]
    # Seed real retained-format state; no synthetic proof authorizes an install.
    subprocess.run(["sudo", "apt-get", "install", "-y", "--no-remove", *map(str, selected),
                    str(directory / "activation/fontreal-session.deb")], check=True)
    try:
        captured = json.loads(cli("plan").stdout)
        assert set(captured["sources"]) == set(build.SOURCES)
        assert captured["original"] == before
        assert [p for p in captured["installed"] if p["source"] == "freetype"] == unowned
        assert [p for p in captured["installed"] if p["source"] in plan["sources"]] == [
            dict(p, version=plan["sources"][p["source"]]["build_version"],
                 source_version=plan["sources"][p["source"]]["build_version"]) for p in plan["installed"]]
        # This is the same retained-plan/activation validation used by --previous.
        cli("verify", directory)
        subprocess.run(["sudo", sys.executable, ROOT / "tools/system-build.py", "rollback", directory], check=True)
        assert build.installed() == before
        assert [p for p in build.installed() if p["source"] == "freetype"] == unowned
        assert subprocess.run(["dpkg-query", "-W", "-f=${db:Status-Status}", "fontreal-session"],
                              capture_output=True).stdout != b"installed"
    finally:
        if build.installed() != before:
            subprocess.run(["sudo", "apt-get", "install", "-y", "--allow-downgrades",
                            *map(str, sorted((directory / "original").glob("*.deb"))), "fontreal-session-"], check=True)
    print("PASS: representative retained Qt-only verify, predecessor discovery and actual rollback preserve unowned FreeType")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retained-native", type=Path, help="Check an explicitly labeled retained-format Qt-only fixture with actual payloads in a marked disposable VM.")
    args = parser.parse_args()
    if args.retained_native:
        retained_native(args.retained_native.resolve())
        return
    # These synthetic archives test metadata and rejection. Real package/session
    # runners establish rendering, APT application, and activation behavior.
    with tempfile.TemporaryDirectory(prefix="fontreal-install-") as temporary:
        root = Path(temporary)
        targets = []
        retained_targets = []
        for name, release, upstream, base, declarative in (
                ("debian", "13", "6.8.2", "6.8.2+dfsg-9+deb13u2", "6.8.2+dfsg-7"),
                ("ubuntu", "26.04", "6.10.2", "6.10.2+dfsg-7", "6.10.2+dfsg-3")):
            plan = fixtures.fixture(name, release, upstream, base, declarative)
            directory = root / name
            directory.mkdir()
            native = fixtures.bundle(directory, plan)
            native_hash = build.sha(directory / "bundle.json")
            previous_umask = os.umask(0o002)
            try:
                cli("prepare", directory)
            finally:
                os.umask(previous_umask)
            archive = subprocess.check_output(["dpkg-deb", "--fsys-tarfile", directory / "activation/fontreal-session.deb"])
            with tarfile.open(fileobj=io.BytesIO(archive)) as payload:
                for member in payload.getmembers():
                    assert member.uid == member.gid == 0
                    expected_mode = 0o755 if member.isdir() or member.name == "./usr/bin/fontreal-session" else 0o644
                    assert member.mode == expected_mode, (member.name, oct(member.mode))
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

            retained = fixtures.retained_plan(plan)
            previous = root / ("retained-" + name)
            previous.mkdir()
            fixtures.bundle(previous, retained)
            rejected = cli("prepare", previous, success=False)
            assert "New activation requires FreeType" in rejected.stderr
            assert not (previous / "activation").exists()
            retained_activation(previous, retained)
            cli("verify", previous)
            retained_targets.append((previous, retained))

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
        apt.write_text("#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n"
                       f"Path({str(invoked)!r}).write_text(json.dumps(sys.argv))\nraise SystemExit(91)\n")
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
        previous, retained = next((d, p) for d, p in retained_targets if (p["os"], p["release"]) == (system["ID"], system["VERSION_ID"]))
        report(previous, "package-checks", updates=[dict(source=source) for source in retained["sources"]])
        report(previous, "session-checks")
        rejected = cli("install", previous, "--simulate", success=False, env=env)
        assert "Installation requires FreeType" in rejected.stderr
        assert not invoked.exists()
        # The deliberate APT error proves rollback selection, never successful application.
        cli("rollback", previous, "--simulate", success=False, env=env)
        arguments = json.loads(invoked.read_text())
        assert {p for p in arguments if p.endswith(".deb")} == {str(previous / "original" / (p["name"] + ".deb")) for p in retained["original"]}
        assert "fontreal-session-" in arguments
        invoked.unlink()
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
