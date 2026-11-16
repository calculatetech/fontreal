"""Native package application and the separate Plasma activation package."""
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile


def activation(builder, directory, plan):
    if set(plan["sources"]) != set(builder.SOURCES) or not builder.selected_plan(plan):
        raise ValueError("New activation requires FreeType and both Qt source families with the selected profile.")
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
            shutil.copyfile(builder.ROOT / "packaging/session" / name, target)
            target.chmod(0o755 if name == "fontreal-session" else 0o644)
        share = root / "usr/share/fontreal"
        share.mkdir(parents=True)
        builder.write_json(share / "system.json", plan)
        (share / "runtime-versions").write_text("".join(
            f"{name}\t{plan['sources'][source]['build_version']}\n"
            for name, source in (("libfreetype6", "freetype"), ("libqt6gui6", "qt6-base"), ("libqt6quick6", "qt6-declarative"))))
        control = root / "DEBIAN/control"
        control.parent.mkdir()
        control.write_text(
            f"Package: fontreal-session\nVersion: 0~local{plan['identity']}\nArchitecture: all\n"
            "Maintainer: Fontreal local build <fontreal@localhost>\n"
            "Depends: libfreetype6, libqt6gui6, libqt6quick6, coreutils\n"
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
    for name in ("fontreal-session", "fontreal.sh", "NOTICE"):
        shutil.copyfile(builder.ROOT / "packaging/session" / name, destination / name)
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
        if json.loads((root / "usr/share/fontreal/system.json").read_text()) != plan:
            raise ValueError("The session package has a different original-system record.")
        expected_versions = "".join(f"{name}\t{plan['sources'][source]['build_version']}\n" for name, source in (
            ("libfreetype6", "freetype"), ("libqt6gui6", "qt6-base"), ("libqt6quick6", "qt6-declarative"))
            if source in plan["sources"])
        if (root / "usr/share/fontreal/runtime-versions").read_text() != expected_versions:
            raise ValueError("The session package selects different runtime versions.")
        for name, relative in (("fontreal-session", "usr/bin/fontreal-session"),
                               ("fontreal.sh", "etc/xdg/plasma-workspace/env/fontreal.sh"),
                               ("NOTICE", "usr/share/doc/fontreal-session/copyright")):
            if builder.sha(root / relative) != builder.sha(directory / "activation" / name):
                raise ValueError("The session payload differs from its retained source.")


def transaction(builder, directory, rollback=False, simulate=False):
    manifest = json.loads((directory / "bundle.json").read_text())
    plan = builder.verify_artifacts(directory, manifest)
    system = platform.freedesktop_os_release()
    if (system["ID"], system["VERSION_ID"], builder.output(["dpkg", "--print-architecture"])) != (
            plan["os"], plan["release"], plan["arch"]):
        raise ValueError("The bundle does not match this distribution and architecture.")
    if not rollback and (set(plan["sources"]) != set(builder.SOURCES) or not builder.selected_plan(plan)):
        raise ValueError("Installation requires FreeType and both Qt source families with the selected profile. Make a new complete bundle.")
    current = [p for p in builder.installed() if not rollback or p["source"] in plan["sources"]]
    identities = lambda records: {(p["name"], p["arch"]) for p in records}
    if identities(current) != identities(plan["installed"]):
        raise ValueError("The installed native package set changed. Make a new system plan.")
    if not rollback and current != plan["installed"]:
        raise ValueError("The installed native versions changed. Make a new system plan.")
    if rollback:
        for p in current:
            if ("afontreal" in p["source_version"] and
                    p["source_version"] != plan["sources"][p["source"]]["build_version"]):
                raise ValueError("Another Fontreal build is installed. Use its own rollback bundle.")
        selected = sorted((directory / "original").glob("*.deb"))
        selected.append("fontreal-session-")
    else:
        deployment = json.loads((directory / "deployment.json").read_text())
        verify_activation(builder, directory, deployment, plan)
        for filename in ("package-checks/package-results.json", "session-checks/session-results.json"):
            record = json.loads((directory / filename).read_text())
            if (record.get("schema") != 1 or record.get("passed") is not True
                    or record["bundle_sha256"] != builder.sha(directory / "bundle.json")
                    or record.get("deployment_sha256") != builder.sha(directory / "deployment.json")):
                raise ValueError(f"Validation belongs to a different bundle: {filename}")
            if record.get("selected_profile") != builder.SELECTED_PROFILE:
                raise ValueError("Complete the selected-profile package and session checks before installation.")
            if filename.startswith("package-checks/"):
                updates = record.get("updates", [])
                if len(updates) != len(builder.SOURCES) or {r["source"] for r in updates} != set(builder.SOURCES):
                    raise ValueError("Run the package checks with --updates before installation.")
            if filename.startswith("session-checks/") and record.get("complete_runtime") is not True:
                raise ValueError("Complete the real Plasma session checks before installation.")
        inventory = builder.package_inventory(directory / "packages")
        selected = [directory / "packages" / inventory[(p["name"], p["arch"])]["path"]
                    for p in plan["installed"]]
        selected.append(directory / "activation/fontreal-session.deb")
    command = ["apt-get", "install"]
    command += ["--allow-downgrades"] if rollback else ["--no-remove"]
    command += [str(p) for p in selected]
    env = dict(os.environ, LC_ALL="C")
    simulation = builder.output([*command[:2], "--simulate", *command[2:]], env=env)
    print(simulation)
    removals = {line.split()[1].split(":")[0] for line in simulation.splitlines() if line.startswith("Remv ")}
    if removals - ({"fontreal-session"} if rollback else set()):
        raise ValueError("APT proposed removing another package. No transaction was applied.")
    if not simulate:
        if os.geteuid() != 0:
            raise ValueError("Run the package transaction through sudo. Simulation needs no root access.")
        builder.run([*command[:2], "-y", *command[2:]], env=env)
        expected = plan["original"] if rollback else [dict(p, version=plan["sources"][p["source"]]["build_version"],
                                                          source_version=plan["sources"][p["source"]]["build_version"])
                                                        for p in plan["installed"]]
        if [p for p in builder.installed() if not rollback or p["source"] in plan["sources"]] != expected:
            raise ValueError("The final native package identities differ from the requested complete set.")
        print("Packages applied. Log out and back in to start a fresh Plasma session.")
