"""Native package application and the separate Plasma activation package."""
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile


def installed_record(plan):
    provider = plan.get("freetype_provider")
    if provider is None:
        return plan
    source = {name: provider[name] for name in ("version", "build_version")}
    original = sorted([*plan["original"], *provider["original"]], key=lambda p: (p["name"], p["arch"]))
    return dict(plan, sources=dict(plan["sources"], freetype=source), original=original)


def runtime_versions(plan):
    runtimes = (("libfreetype6", "freetype"), ("libqt6gui6", "qt6-base"), ("libqt6quick6", "qt6-declarative"))
    return "".join(f"{name}\t{plan['sources'][source]['build_version']}\n"
                   for name, source in runtimes if source in plan["sources"])


def activation(builder, directory, plan):
    qt_v3 = builder.v3_plan(plan)
    if not qt_v3 and (set(plan["sources"]) != set(builder.SOURCES) or not builder.selected_plan(plan)):
        raise ValueError("New activation requires FreeType and both Qt source families with the selected profile.")
    source_dir = builder.ROOT / "packaging/session"
    payloads = {name: source_dir / name for name in ("fontreal-session", "fontreal.sh", "NOTICE")}
    if qt_v3:
        payloads["fontreal.sh"] = source_dir / "fontreal-v3.sh"
    destination = directory / "activation"
    destination.mkdir()
    with tempfile.TemporaryDirectory(prefix=".fontreal-session-", dir=directory) as temporary:
        root = Path(temporary)
        files = {
            "usr/bin/fontreal-session": "fontreal-session",
            "etc/xdg/plasma-workspace/env/fontreal.sh": "fontreal.sh",
            "usr/share/doc/fontreal-session/copyright": "NOTICE",
        }
        for relative, name in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(payloads[name], target)
            target.chmod(0o755 if name == "fontreal-session" else 0o644)
        share = root / "usr/share/fontreal"
        share.mkdir(parents=True)
        builder.write_json(share / "system.json", installed_record(plan))
        (share / "runtime-versions").write_text(runtime_versions(plan))
        control = root / "DEBIAN/control"
        control.parent.mkdir()
        dependencies = "libqt6gui6, libqt6quick6, coreutils"
        if not qt_v3:
            dependencies = "libfreetype6, " + dependencies
        control.write_text(
            f"Package: fontreal-session\nVersion: 0~local{plan['identity']}\nArchitecture: all\n"
            "Maintainer: Fontreal local build <fontreal@localhost>\n"
            f"Depends: {dependencies}\n"
            "Description: Explicit per-user Fontreal activation for Plasma\n"
            " Starts disabled and preserves installed fonts.\n")
        postinst = root / "DEBIAN/postinst"
        postinst.write_text('''#!/bin/sh
set -eu
if [ "${1:-}" = configure ]; then
    directory=/usr/share/fontreal
    if [ -L "$directory" ] || [ ! -d "$directory" ] ||
       [ "$(stat -c %u -- "$directory")" != 0 ] ||
       [ "$(dpkg-query -S "$directory")" != "fontreal-session: $directory" ]; then
        printf '%s\\n' 'The Fontreal source record directory is not a root-owned package directory.' >&2
        exit 1
    fi
    if ! dpkg-statoverride --list "$directory" >/dev/null; then
        chmod 0755 -- "$directory"
    fi
fi
''')
        root.chmod(0o755)
        for path in root.rglob("*"):
            path.chmod(0o755 if path.is_dir() or path in (root / "usr/bin/fontreal-session", postinst) else 0o644)
        builder.run(["dpkg-deb", "--build", "--root-owner-group", root,
                     destination / "fontreal-session.deb"])
    for name, source in payloads.items():
        shutil.copyfile(source, destination / name)
    shutil.copyfile(Path(__file__), destination / "build-session.py")


def prepare(builder, directory):
    manifest = json.loads((directory / "bundle.json").read_text())
    plan = builder.verify_artifacts(directory, manifest)
    if (directory / "deployment.json").exists():
        raise ValueError("This native bundle already has a deployment record.")
    native_hash = builder.sha(directory / "bundle.json")
    activation(builder, directory, plan)
    deployment = dict(schema=1, bundle_sha256=native_hash, artifacts=[
        dict(path=str(path.relative_to(directory)), sha256=builder.sha(path))
        for path in sorted((directory / "activation").iterdir())])
    builder.verify_artifacts(directory, manifest)
    verify_activation(builder, directory, deployment, plan)
    builder.write_json(directory / "deployment.json", deployment)
    print(f"Prepared the disabled Plasma session package using retained Qt packages: {directory}")


def verify_activation(builder, directory, manifest, plan):
    if manifest["schema"] != 1 or manifest["bundle_sha256"] != builder.sha(directory / "bundle.json"):
        raise ValueError("The deployment record does not match the native bundle.")
    paths = {Path(a["path"]) for a in manifest["artifacts"]}
    expected = {Path("activation") / name for name in ("fontreal-session.deb", "fontreal-session", "fontreal.sh", "NOTICE", "build-session.py")}
    if (len(manifest["artifacts"]) != len(expected) or paths != expected
            or {p.relative_to(directory) for p in (directory / "activation").iterdir()} != expected):
        raise ValueError("The complete hashed session package and its source are required.")
    for artifact in manifest["artifacts"]:
        if builder.sha(directory / artifact["path"]) != artifact["sha256"]:
            raise ValueError("An activation artifact checksum does not match the deployment record.")
    package = directory / "activation/fontreal-session.deb"
    fields = builder.output(["dpkg-deb", "-f", package, "Package", "Architecture", "Version"])
    if fields.splitlines() != ["Package: fontreal-session", "Architecture: all", "Version: 0~local" + plan["identity"]]:
        raise ValueError("The session package does not match this bundle.")
    with tempfile.TemporaryDirectory(prefix="fontreal-session-check-") as temporary:
        root = Path(temporary)
        builder.run(["dpkg-deb", "-x", package, root])
        if json.loads((root / "usr/share/fontreal/system.json").read_text()) != installed_record(plan):
            raise ValueError("The session package has a different original-system record.")
        if (root / "usr/share/fontreal/runtime-versions").read_text() != runtime_versions(plan):
            raise ValueError("The session package selects different runtime versions.")
        for name, relative in (("fontreal-session", "usr/bin/fontreal-session"),
                               ("fontreal.sh", "etc/xdg/plasma-workspace/env/fontreal.sh"),
                               ("NOTICE", "usr/share/doc/fontreal-session/copyright")):
            if builder.sha(root / relative) != builder.sha(directory / "activation" / name):
                raise ValueError("The session payload differs from its retained source.")


def v3_rollback_packages(builder, directory, plan, previous):
    provider = plan.get("freetype_provider")
    previous_session = plan["previous_session"]
    if previous_session is None:
        return [*sorted((directory / "original").glob("*.deb")), "fontreal-session-"]
    if previous is None:
        raise ValueError("This V3 bundle replaced Fontreal. Give its retained predecessor with --previous.")
    previous = previous.resolve()
    old = builder.verify_artifacts(previous, json.loads((previous / "bundle.json").read_text()))
    verify_activation(builder, previous, json.loads((previous / "deployment.json").read_text()), old)
    if (old["os"], old["release"], old["arch"]) != (plan["os"], plan["release"], plan["arch"]):
        raise ValueError("The predecessor does not match the distribution and architecture.")
    if "0~local" + old["identity"] != previous_session:
        raise ValueError("The predecessor does not contain the captured Fontreal session package.")
    if provider is not None:
        record = installed_record(old)
        source = record["sources"].get("freetype", {})
        if (any(source.get(key) != provider[key] for key in ("version", "build_version"))
                or any(p not in record["original"] for p in provider["original"])):
            raise ValueError("The predecessor does not own the retained FreeType source record.")
    originals = builder.package_inventory(directory / "original")
    old_packages = builder.package_inventory(previous / "packages")
    original_records = {(p["name"], p["arch"]): p for p in plan["original"]}
    old_records = {(p["name"], p["arch"]): p for p in old["original"]}
    selected = []
    for p in plan["installed"]:
        identity = (p["name"], p["arch"])
        original = original_records[identity]
        if p == original:
            selected.append(directory / "original" / originals[identity]["path"])
            continue
        version = old["sources"].get(p["source"], {}).get("build_version")
        artifact = old_packages.get(identity)
        if (p["source_version"] != version or p["version"] != version or not artifact
                or artifact["version"] != version or artifact["source"].split()[0] != p["source"]
                or old_records.get(identity) != original):
            raise ValueError(f"The predecessor does not contain the captured Qt package {p['name']}.")
        selected.append(previous / "packages" / artifact["path"])
    selected.append(previous / "activation/fontreal-session.deb")
    return selected


def transaction(builder, directory, rollback=False, simulate=False, previous=None):
    manifest = json.loads((directory / "bundle.json").read_text())
    plan = builder.verify_artifacts(directory, manifest)
    system = platform.freedesktop_os_release()
    if (system["ID"], system["VERSION_ID"], builder.output(["dpkg", "--print-architecture"])) != (
            plan["os"], plan["release"], plan["arch"]):
        raise ValueError("The bundle does not match this distribution and architecture.")
    qt_v3 = builder.v3_plan(plan)
    if previous is not None and not (qt_v3 and rollback):
        raise ValueError("--previous applies to V3 rollback.")
    if not qt_v3 and not rollback and (set(plan["sources"]) != set(builder.SOURCES) or not builder.selected_plan(plan)):
        raise ValueError("Installation requires FreeType and both Qt source families with the selected profile. Make a new complete bundle.")
    installed = builder.installed()
    current = [p for p in installed if p["source"] in plan["sources"]]
    freetype = [p for p in installed if p["source"] == "freetype"] if qt_v3 else []
    if qt_v3:
        session = builder.session_version()
        captured = plan["previous_session"]
        if not rollback and session != captured:
            raise ValueError("The Fontreal session package changed. Make a new system plan.")
        if rollback and session not in (None, "0~local" + plan["identity"]):
            if session == captured and current == plan["installed"]:
                print("The captured Qt and session packages are already installed.")
                return
            raise ValueError("Another Fontreal session package is installed. Use its own rollback bundle.")
        previous_record = None
        if any("afontreal" in p["source_version"] for p in freetype):
            if rollback and session is None and plan.get("freetype_provider") is not None:
                previous_record = installed_record(plan)
            else:
                previous_record = builder.trusted_system_record()
        provider = builder.retained_freetype(freetype, previous_record, (plan["os"], plan["release"]))
        captured_provider = plan.get("freetype_provider")
        if rollback and captured_provider is not None and provider is not None:
            captured_provider = dict(captured_provider, original=[p for p in captured_provider["original"]
                                                                 if p in provider["original"]])
        if provider != captured_provider and (not rollback or provider is not None):
            raise ValueError("The installed FreeType provider record changed since this V3 plan.")
    identities = lambda records: {(p["name"], p["arch"]) for p in records}
    if identities(current) != identities(plan["installed"]):
        raise ValueError("The installed native package set changed. Make a new system plan.")
    if not rollback and current != plan["installed"]:
        raise ValueError("The installed native versions changed. Make a new system plan.")
    expected = plan["original"]
    if rollback:
        for p in current:
            if ("afontreal" in p["source_version"] and
                    p["source_version"] != plan["sources"][p["source"]]["build_version"]):
                raise ValueError("Another Fontreal build is installed. Use its own rollback bundle.")
        if qt_v3:
            selected = v3_rollback_packages(builder, directory, plan, previous)
            expected = plan["installed"]
        else:
            selected = [*sorted((directory / "original").glob("*.deb")), "fontreal-session-"]
    else:
        deployment = json.loads((directory / "deployment.json").read_text())
        verify_activation(builder, directory, deployment, plan)
        inventory = builder.package_inventory(directory / "packages")
        selected = [directory / "packages" / inventory[(p["name"], p["arch"])]["path"]
                    for p in plan["installed"]]
        selected.append(directory / "activation/fontreal-session.deb")
        expected = [dict(p, version=plan["sources"][p["source"]]["build_version"],
                         source_version=plan["sources"][p["source"]]["build_version"]) for p in plan["installed"]]
    command = ["apt-get", "install"]
    remove_session = selected[-1] == "fontreal-session-"
    if rollback:
        command.append("--allow-downgrades")
    if not remove_session:
        command.append("--no-remove")
    command += [str(p) for p in selected]
    env = dict(os.environ, LC_ALL="C")
    simulation = builder.output([*command[:2], "--simulate", *command[2:]], env=env)
    print(simulation)
    removals = {line.split()[1].split(":")[0] for line in simulation.splitlines() if line.startswith("Remv ")}
    if removals - ({"fontreal-session"} if remove_session else set()):
        raise ValueError("APT proposed removing another package. No transaction was applied.")
    if qt_v3:
        changing = {line.split()[1].split(":")[0] for line in simulation.splitlines() if line.startswith("Inst ")}
        if changing & {p["name"] for p in freetype}:
            raise ValueError("APT proposed changing FreeType during a Qt-only transaction.")
    if not simulate:
        if os.geteuid() != 0:
            raise ValueError("Run the package transaction through sudo. Simulation needs no root access.")
        builder.run([*command[:2], "-y", *command[2:]], env=env)
        installed = builder.installed()
        if qt_v3 and [p for p in installed if p["source"] == "freetype"] != freetype:
            raise ValueError("The installed FreeType package identities changed during a Qt-only transaction.")
        if [p for p in installed if p["source"] in plan["sources"]] != expected:
            raise ValueError("The final native package identities differ from the requested complete set.")
        print("Packages applied. Log out and back in to start a fresh Plasma session.")
