#!/usr/bin/env python3
"""Check deployment metadata with real small .deb archives, not Qt payloads."""
import copy
import contextlib
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
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import system_build_test as fixtures

build = fixtures.build
ROOT = fixtures.ROOT
LEGACY_BASE = "6ae8559d14f2448cd24f320f8d4c480669c80e0c"


def retained_activation(directory, plan, revision=LEGACY_BASE):
    # Use the actual old producer and source, not a new package relabeled as old.
    with tempfile.TemporaryDirectory(prefix="fontreal-retained-source-") as temporary:
        source = Path(temporary)
        for name in ("tools/system_install.py", "packaging/session/fontreal-session", "packaging/session/fontreal.sh", "packaging/session/NOTICE"):
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.check_output(["git", "show", f"{revision}:{name}"], cwd=ROOT))
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
    record = dict(schema=1, passed=True, selected_profile=build.SELECTED_PROFILE, bundle_sha256=build.sha(directory / "bundle.json"),
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


def activation_payload(directory, plan):
    """Run the real extracted command and hook; replace only dpkg discovery."""
    payload=directory/'payload';payload.mkdir()
    build.run(['dpkg-deb','-x',directory/'activation/fontreal-session.deb',payload])
    command=payload/'usr/bin/fontreal-session'
    hook,=payload.rglob('fontreal.sh')
    versions=payload/'usr/share/fontreal/runtime-versions'
    qt_v3 = plan.get("profile") == build.QT_V3
    expected = [("libqt6gui6", "qt6-base"), ("libqt6quick6", "qt6-declarative")]
    if not qt_v3:
        expected.insert(0, ("libfreetype6", "freetype"))
    rows = [f"{package}\t{plan['sources'][source]['build_version']}\n" for package, source in expected]
    assert versions.read_text() == "".join(rows)
    home=directory/'profile-home';home.mkdir()
    provider=directory/'profile-provider';provider.mkdir()
    observed=provider/'versions';observed.write_text(''.join(rows))
    query=provider/'dpkg-query'
    request = " ".join(package + ":amd64" for package, _ in expected)
    fields = '-f=${Package}\\t${Version}\\n'
    query.write_text(f"#!/bin/sh\n[ \"$1\" = -W ] && [ \"$2\" = '{fields}' ] || exit 2\n"
                     f"shift 2\n[ \"$*\" = \"{request}\" ] || exit 2\ncat \"{observed}\"\n")
    query.chmod(0o755)
    env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/'config'),
             PATH=str(provider)+os.pathsep+os.environ['PATH'],FONTREAL_PROFILE='o',
             FONTREAL_RENDERING='1',FONTREAL_BLEND='encoded',FONTREAL_CONTRAST='weighted',FONTREAL_FITTING='native')
    namespace=['bwrap','--unshare-user','--ro-bind','/','/','--dev-bind','/dev','/dev','--bind',str(directory),str(directory),
               '--ro-bind',str(command),'/usr/bin/fontreal-session',
               '--ro-bind',str(payload/'usr/share/fontreal'),'/usr/share/fontreal']
    def call(*args):return subprocess.check_output([*namespace,'/usr/bin/fontreal-session',*args],env=env,text=True)
    call('profile','k3');assert call('profile')=='k3\n'
    assert 'Next-login profile: k3' in call('status') and 'profile=o' in call('status')
    for enabled,mismatch in ((False,None),(True,None),*((True,index) for index in range(len(rows))),
                            (True,None),(False,None)):
        call('enable' if enabled else 'disable')
        current=list(rows)
        if mismatch is not None:current[mismatch]=current[mismatch].rstrip('\n')+'-mismatch\n'
        observed.write_text(''.join(current))
        output=subprocess.check_output([*namespace,'sh','-c','. "$1"; env; /usr/bin/fontreal-session status','sh',str(hook)],env=env,text=True)
        values=dict(line.split('=',1) for line in output.splitlines() if '=' in line and not line.startswith('Current process:'))
        active=enabled and mismatch is None
        assert values['FONTREAL_RENDERING']==(('3' if qt_v3 else '1') if active else '0')
        profile = '' if qt_v3 else ('k3' if active else None)
        assert values.get('FONTREAL_PROFILE') == profile
        if qt_v3:
            assert all(values[field] == '' for field in ('FONTREAL_BLEND', 'FONTREAL_CONTRAST', 'FONTREAL_FITTING'))
        assert 'Next-login profile: k3' in output
        assert ('profile=k3' if profile == 'k3' else 'profile=\n') in output
    print('PASS actual extracted activation payload, O/K3 command, independent native gates and next-login/current status')


def qt_v3_transactions(root, previous, prior_plan):
    spec = importlib.util.spec_from_file_location("native_install", ROOT / "tools/system_install.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    fresh, upgrade, updated = fixtures.qt_v3_plans(prior_plan)
    os_release = {"ID": prior_plan["os"], "VERSION_ID": prior_plan["release"]}
    original_output = build.output
    calls = []
    proposal = ""

    def output(args, **kwargs):
        if args[:2] == ["apt-get", "install"]:
            assert "--simulate" in args
            calls.append(args)
            return proposal
        return original_output(args, **kwargs)

    def simulate(action, bundle, *options, error=None):
        argv = ["system-build.py", action, str(bundle), "--simulate", *map(str, options)]
        with (patch.object(sys, "argv", argv),
              patch.dict(sys.modules, {build.__name__: build, "system_install": installer})):
            if error is None:
                build.main()
                return
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                try:
                    build.main()
                except SystemExit as stopped:
                    assert stopped.code == 1 and error in stderr.getvalue(), stderr.getvalue()
                else:
                    raise AssertionError(f"The command should have failed with {error}")

    missing_qt = root / f"previous-without-core-{prior_plan['os']}"
    missing_qt.mkdir()
    without_core = copy.deepcopy(prior_plan)
    for group in ("original", "installed"):
        without_core[group] = [p for p in without_core[group] if p["name"] != "libqt6core6t64"]
    fixtures.bundle(missing_qt, without_core)
    cli("prepare", missing_qt)

    qt_proposal = "Inst libqt6gui6 [old] (new [amd64])\nInst libqt6quick6 [old] (new [amd64])"
    ft_update = "\nInst libfreetype6:i386 [old] (update [i386])"
    for label, plan in (("fresh", fresh), ("upgrade", upgrade), ("updated", updated)):
        bundle = root / f"v3-transaction-{prior_plan['os']}-{label}"
        bundle.mkdir()
        fixtures.bundle(bundle, plan)
        cli("prepare", bundle)
        ft = [p for p in prior_plan["original"] if p["source"] == "freetype"]
        ft_version = plan.get("freetype_provider", {}).get("build_version")
        if ft_version:
            ft = [dict(p, version=ft_version, source_version=ft_version) for p in ft]
        local_qt = [dict(p, version=plan["sources"][p["source"]]["build_version"],
                         source_version=plan["sources"][p["source"]]["build_version"])
                    for p in plan["original"]]
        with (patch.object(installer.platform, "freedesktop_os_release", return_value=os_release),
              patch.object(build, "output", side_effect=output),
              patch.object(build, "trusted_system_record", return_value=prior_plan)):
            with (patch.object(build, "installed", return_value=[*plan["installed"], *ft]),
                  patch.object(build, "session_version", return_value=plan["previous_session"])):
                proposal = qt_proposal
                simulate("install", bundle)
                expected = [str(bundle / "packages" / (p["name"] + ".deb")) for p in plan["installed"]]
                assert calls[-1] == ["apt-get", "install", "--simulate", "--no-remove", *expected,
                                     str(bundle / "activation/fontreal-session.deb")]
                proposal += ft_update
                simulate("install", bundle, error="changing FreeType")
                proposal = ""
            with (patch.object(build, "installed", return_value=[*plan["installed"], *ft]),
                  patch.object(build, "session_version", return_value="0~local20991231000000")):
                before = len(calls)
                simulate("install", bundle, error="session package changed")
                assert len(calls) == before
            with (patch.object(build, "installed", return_value=[*local_qt, *ft]),
                  patch.object(build, "session_version", return_value="0~local" + plan["identity"])):
                predecessor = plan["previous_session"] is not None
                options = ["--previous", previous] if predecessor else []
                restore_proposal = qt_proposal if predecessor else qt_proposal + "\nRemv fontreal-session [old]"
                proposal = restore_proposal
                simulate("rollback", bundle, *options)
                original_qt = {(p["name"], p["arch"]): p for p in plan["original"]}
                restored = [str((bundle / "original" if p == original_qt[p["name"], p["arch"]]
                                 else previous / "packages") / (p["name"] + ".deb"))
                            for p in plan["installed"]]
                flags = ["--no-remove"] if predecessor else []
                session = str(previous / "activation/fontreal-session.deb") if predecessor else "fontreal-session-"
                assert calls[-1] == ["apt-get", "install", "--simulate", "--allow-downgrades", *flags,
                                     *restored, session]
                proposal = restore_proposal + ft_update
                simulate("rollback", bundle, *options, error="changing FreeType")
                proposal = restore_proposal + "\nRemv libfreetype6:i386 [old]"
                simulate("rollback", bundle, *options, error="removing another package")
                proposal = ""
                if predecessor:
                    before = len(calls)
                    simulate("rollback", bundle, "--previous", bundle, error="captured Fontreal session package")
                    assert len(calls) == before
                if label == "upgrade":
                    before = len(calls)
                    simulate("rollback", bundle, "--previous", missing_qt,
                             error="captured Qt package libqt6core6t64")
                    assert len(calls) == before
                    without_i386 = [p for p in ft if p["arch"] != "i386"]
                    with patch.object(build, "installed", return_value=[*local_qt, *without_i386]):
                        proposal = restore_proposal
                        simulate("rollback", bundle, *options)
                        assert calls[before:] == [["apt-get", "install", "--simulate", "--allow-downgrades", *flags,
                                                   *restored, session]]
                    different_version = ft_version[:-14] + "20991231000000"
                    different_record = copy.deepcopy(prior_plan)
                    different_record["sources"]["freetype"]["build_version"] = different_version
                    different_ft = [dict(p, version=different_version, source_version=different_version)
                                    for p in without_i386]
                    with (patch.object(build, "installed", return_value=[*local_qt, *different_ft]),
                          patch.object(build, "trusted_system_record", return_value=different_record)):
                        before = len(calls)
                        simulate("rollback", bundle, *options, error="FreeType provider record changed")
                        assert len(calls) == before
    print('PASS V3 simulated APT transactions, retained session after Qt updates, and FreeType preservation')


def retained_native(directory):
    assert Path("/var/lib/fontreal-test-ready").is_file(), "Use the marked disposable VM."
    subprocess.run(["systemd-detect-virt", "--vm"], check=True, capture_output=True)
    metadata = json.loads((directory / "build.json").read_text())
    label = "representative retained" if metadata.get("representative_retained_schema1") is True else "retained"
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
    print(f"PASS: {label} Qt-only verify, predecessor discovery and actual rollback preserve unowned FreeType")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retained-native", type=Path, help="Check a retained Qt-only bundle with actual payloads in a marked disposable VM.")
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
        v1_targets = []
        raw_targets = []
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
            control = subprocess.check_output(["dpkg-deb", "--ctrl-tarfile", directory / "activation/fontreal-session.deb"])
            with tarfile.open(fileobj=io.BytesIO(control)) as payload:
                script = payload.getmember("./postinst")
                assert script.uid == script.gid == 0 and script.mode == 0o755
                subprocess.run(["sh", "-n"], input=payload.extractfile(script).read(), check=True)
            assert build.sha(directory / "bundle.json") == native_hash
            assert all(build.sha(directory / a["path"]) == a["sha256"] for a in native["artifacts"])
            cli("verify", directory)
            activation_payload(directory, plan)
            v3_directory = root / f"v3-{name}"
            v3_directory.mkdir()
            _, upgrade, _ = fixtures.qt_v3_plans(plan)
            fixtures.bundle(v3_directory, upgrade)
            cli("prepare", v3_directory)
            cli("verify", v3_directory)
            activation_payload(v3_directory, upgrade)
            qt_v3_transactions(root, directory, plan)
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

            v1 = fixtures.retained_selected_plan(plan)
            v1_directory = root / ("synthetic-selected-v1-" + name)
            v1_directory.mkdir()
            fixtures.bundle(v1_directory, v1)
            immutable = build.sha(v1_directory / "bundle.json")
            cli("prepare", v1_directory)
            cli("verify", v1_directory)
            assert build.sha(v1_directory / "bundle.json") == immutable
            v1_targets.append((v1_directory, v1))

            raw = copy.deepcopy(plan)
            raw["sources"]["freetype"].pop("selected")
            raw["sources"]["freetype"]["capability_sha256"] = None
            raw_directory = root / ("raw-" + name)
            raw_directory.mkdir()
            fixtures.bundle(raw_directory, raw)
            cli("verify", raw_directory)
            assert "selected profile" in cli("prepare", raw_directory, success=False).stderr
            assert not (raw_directory / "activation").exists()
            # The actual pre-selected three-family producer supplies valid old
            # activation metadata. These small archives remain synthetic tests.
            retained_activation(raw_directory, raw, "e8303f596998d6231b2d5bbd8c8b273d541c9b01")
            cli("verify", raw_directory)
            raw_targets.append((raw_directory, raw))

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
        response = provider / "apt-response.json"
        apt.write_text("#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n"
                       f"log=Path({str(invoked)!r}); calls=json.loads(log.read_text()) if log.exists() else []\n"
                       "calls.append(sys.argv); log.write_text(json.dumps(calls))\n"
                       f"response=Path({str(response)!r})\n"
                       "if response.exists():\n data=json.loads(response.read_text()); print(data['stdout'],end=''); "
                       "print(data['stderr'],end='',file=sys.stderr); raise SystemExit(data['status'])\n"
                       "raise SystemExit(91)\n")
        apt.chmod(0o755)
        env = dict(os.environ, PATH=str(provider) + os.pathsep + os.environ["PATH"])
        # A routine build needs no development reports. The deliberate APT
        # error proves simulation was reached, not successful installation.
        assert not (directory / "package-checks/package-results.json").exists()
        assert not (directory / "session-checks/session-results.json").exists()
        cli("install", directory, "--simulate", success=False, env=env)
        arguments, = json.loads(invoked.read_text())
        assert "--simulate" in arguments and "--no-remove" in arguments
        expected = {str(directory / "packages" / (p["name"] +
                    ("_" + p["arch"] if p["arch"] != "amd64" else "") + ".deb")) for p in plan["installed"]}
        expected.add(str(directory / "activation/fontreal-session.deb"))
        assert {p for p in arguments if p.endswith(".deb")} == expected
        invoked.unlink()
        v1_directory, v1 = next((d, p) for d, p in v1_targets if (p["os"], p["release"]) == (system["ID"], system["VERSION_ID"]))
        cli("install", v1_directory, "--simulate", success=False, env=env)
        arguments, = json.loads(invoked.read_text())
        assert "--simulate" in arguments and "--no-remove" in arguments
        assert {p for p in arguments if p.endswith(".deb")} == {str(v1_directory / "packages" / (p["name"] +
            ("_" + p["arch"] if p["arch"] != "amd64" else "") + ".deb")) for p in v1["installed"]} | {str(v1_directory / "activation/fontreal-session.deb")}
        invoked.unlink()
        raw_directory, raw = next((d, p) for d, p in raw_targets if (p["os"], p["release"]) == (system["ID"], system["VERSION_ID"]))
        assert set(raw["sources"]) == set(build.SOURCES) and not build.selected_plan(raw)
        report(raw_directory, "package-checks", selected_profile=None)
        report(raw_directory, "session-checks", selected_profile=None)
        rejected_install(raw_directory, env, "selected profile")
        assert not invoked.exists(), "Complete/raw installation must stop before APT."
        print("PASS complete/raw three-family own-metadata install refusal before APT (synthetic archives)")
        previous, retained = next((d, p) for d, p in retained_targets if (p["os"], p["release"]) == (system["ID"], system["VERSION_ID"]))
        report(previous, "package-checks", updates=[dict(source=source) for source in retained["sources"]])
        report(previous, "session-checks")
        rejected = cli("install", previous, "--simulate", success=False, env=env)
        assert "Installation requires FreeType" in rejected.stderr
        assert not invoked.exists()
        # The deliberate APT error proves rollback selection, never successful application.
        cli("rollback", previous, "--simulate", success=False, env=env)
        arguments, = json.loads(invoked.read_text())
        assert {p for p in arguments if p.endswith(".deb")} == {str(previous / "original" / (p["name"] + ".deb")) for p in retained["original"]}
        assert "fontreal-session-" in arguments
        invoked.unlink()
        # Native APT emits Remv proposals for rollback without --no-remove.
        # An agreeing allowed prefix cannot hide a later unrelated removal.
        prefix = "Reading package lists...\nBuilding dependency tree...\nReading state information...\n"
        allowed = "Remv fontreal-session [0~local20261111190000]\n"
        for proposal in (prefix, prefix + allowed):
            build.write_json(response, dict(status=0, stdout=proposal, stderr=""))
            cli("rollback", directory, "--simulate", env=env)
            calls = json.loads(invoked.read_text())
            assert (len(calls) == 1 and "--simulate" in calls[0] and "--allow-downgrades" in calls[0]
                    and "--no-remove" not in calls[0])
            invoked.unlink()
        build.write_json(response, dict(status=0, stdout=prefix + allowed + "Remv unrelated:amd64 [1.0]\n", stderr=""))
        rejected = cli("rollback", directory, success=False, env=env)
        assert "APT proposed removing another package" in rejected.stderr
        calls = json.loads(invoked.read_text())
        assert (len(calls) == 1 and "--simulate" in calls[0] and "--no-remove" not in calls[0]), (
            "No real APT call may follow an unsafe proposal.")
        invoked.unlink()
        # Native --no-remove aborts before simulation output; do not invent a
        # successful install Remv proposal that the actual provider cannot emit.
        build.write_json(response, dict(status=100, stdout=prefix,
                                       stderr="E: Packages need to be removed but remove is disabled.\n"))
        rejected = cli("install", directory, success=False, env=env)
        assert "remove is disabled" in rejected.stderr
        calls = json.loads(invoked.read_text())
        assert len(calls) == 1 and "--simulate" in calls[0] and "--no-remove" in calls[0]
        print("PASS safe rollback proposals, later unrelated removal refusal, and native install no-remove error before real APT")
        invoked.unlink()
        response.unlink()
        changed = copy.deepcopy(plan["installed"])
        for p in changed:
            if p["source"] == "qt6-declarative":
                p["version"] = plan["sources"][p["source"]]["version"] + ".1"
                p["source_version"] = p["version"]
        build.write_json(records, changed)
        rejected_install(directory, env, "versions changed")
        assert not invoked.exists()
    print("PASS: immutable native input, deployment without test reports, complete activation inventories, late Quick mismatch and snapshot rejection")


if __name__ == "__main__":
    main()
