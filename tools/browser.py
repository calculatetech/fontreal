#!/usr/bin/env python3
"""Enable the approved Fontreal treatment in existing Firefox/Floorp profiles."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from freetype_provider import official_version
WORK = (ROOT / "build/freetype-native").resolve()
BROWSERS = ("firefox", "floorp")
PREFS = {
    "gfx.text.subpixel-position.force-disabled": True,
    "gfx.webrender.enable-subpixel-aa": False,
    "gfx.font_rendering.freetype.gamma": -1,
    "gfx.font_rendering.freetype.enhanced_contrast": 0,
}
BEGIN = "// Fontreal browser rendering: begin\n"
END = "// Fontreal browser rendering: end\n"
OWNED_PREF = re.compile(r'^\s*user_pref\(\s*"(?:' + "|".join(map(re.escape, PREFS)) + r')"\s*,')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_profile(path, text):
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".fontreal-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            os.fchmod(output.fileno(), mode)
            output.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def binary(browser):
    return Path("/usr/bin") / browser


def desktop_source(browser):
    return Path("/usr/share/applications") / f"{browser}.desktop"


def profile_indexes(browser):
    bases = ([Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mozilla/firefox",
              Path.home() / ".mozilla/firefox"] if browser == "firefox" else [
              Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "floorp", Path.home() / ".floorp"])
    return [base / "profiles.ini" for base in bases if (base / "profiles.ini").exists()]


def browser_version(browser):
    application = configparser.ConfigParser(interpolation=None)
    application.read(f"/usr/lib/{browser}/application.ini")
    return application.get("App", "Version", fallback="unknown")


def freetype_version():
    return official_version(subprocess.check_output(
        ["dpkg-query", "-W", "-f=${Version}", "libfreetype6:amd64"], text=True).strip())


def process_ids():
    return [p for p in Path("/proc").iterdir() if p.name.isdecimal()]


def running_profiles(browser):
    executables = {binary(browser).resolve()}
    main = Path(f"/usr/lib/{browser}/{browser}-bin")
    if main.exists():
        executables.add(main.resolve())
    found = {}
    for process in process_ids():
        try:
            executable = os.readlink(process / "exe").removesuffix(" (deleted)")
            if Path(executable).resolve() not in executables:
                continue
            for fd in (process / "fd").iterdir():
                target = os.readlink(fd)
                if target.endswith("/.parentlock"):
                    found[int(process.name)] = Path(target).parent.resolve()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return found


def working_profile(browser):
    defaults = set()
    for index in profile_indexes(browser):
        config = configparser.ConfigParser(interpolation=None)
        config.read(index)
        for section in config.sections():
            if section.startswith("Install") and config.has_option(section, "Default"):
                path = Path(config[section]["Default"])
                defaults.add((path if path.is_absolute() else index.parent / path).resolve())
    parents = running_profiles(browser)
    if len(defaults) > 1 and browser == "firefox" and parents:
        observed = set(parents.values())
        if len(observed) == 1 and observed <= defaults and ordinary_invocations(set(parents)):
            defaults = observed
    if len(defaults) != 1:
        raise ValueError("Need one unambiguous ordinary Install-default profile; no profile was changed.")
    profile = defaults.pop()
    if not (profile / "prefs.js").is_file():
        raise ValueError("The ordinary profile must already contain prefs.js; no profile was created.")
    if any(path != profile for path in parents.values()):
        raise ValueError("A running profile differs from the ordinary default; no profile was changed.")
    return profile


def ordinary_invocations(pids):
    selectors = {"p", "profile", "profilemanager", "createprofile", "no-remote", "new-instance",
                 "reset-profile", "migration"}
    environment_selectors = {
        b"XRE_PROFILE_PATH", b"XRE_PROFILE_LOCAL_PATH", b"SELECTABLE_PROFILE_RESET_PATH",
        b"SELECTABLE_PROFILE_RESET_STORE_ID", b"XRE_RESTARTED_BY_PROFILE_MANAGER",
        b"XRE_RESTARTED_BY_PROFILE_SELECTOR", b"MOZ_LEGACY_PROFILES",
        b"MOZ_RESET_PROFILE_RESTART", b"XRE_RESTART_TO_PROFILE_MANAGER",
    }
    observed = set()
    for process in process_ids():
        if int(process.name) not in pids:
            continue
        try:
            argv = (process / "cmdline").read_bytes().split(b"\0")
            environment = (process / "environ").read_bytes().split(b"\0")
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            return False
        if not argv[0] or any(arg.startswith(b"-") and
                arg.lstrip(b"-").split(b"=", 1)[0].decode("utf-8", "replace").lower() in selectors
                for arg in argv[1:]):
            return False
        if any(entry.split(b"=", 1)[0] in environment_selectors for entry in environment):
            return False
        observed.add(int(process.name))
    return observed == pids


def paths(browser):
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return (config / "fontreal/browsers" / f"{browser}.json",
            Path.home() / ".local/bin" / browser,
            data / "applications" / f"{browser}.desktop")


def rendering_profile():
    path = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "fontreal/profile"
    try:
        value = path.read_bytes()
    except FileNotFoundError:
        return "o"
    return "k3" if value in (b"k3", b"k3\n") else "o"


def desktop_arg(value):
    # Desktop entries unescape strings before parsing their quoted Exec arguments.
    quoted = "".join("\\" + c if c in '\\"`$' else "%%" if c == "%" else c for c in str(value))
    return '"' + quoted.replace("\\", "\\\\") + '"'


def require_owned(record):
    for entry in record["hooks"]:
        path = Path(entry["path"])
        if not path.is_file() or sha(path) != entry["sha256"]:
            raise ValueError(f"Launch hook changed outside Fontreal; left untouched: {path}")


def enable(browser):
    profile = working_profile(browser)
    state, wrapper, desktop = paths(browser)
    previous = json.loads(state.read_text()) if state.exists() else None
    user_js = profile / "user.js"
    content = user_js.read_bytes().decode("utf-8") if user_js.exists() else ""
    if previous:
        if Path(previous["profile"]) != profile:
            raise ValueError("Disable the previous profile treatment before changing the ordinary default.")
        require_owned(previous)
        if content.count(previous["block"]) != 1:
            raise ValueError("The owned user.js block changed; no settings were overwritten.")
    else:
        if any(p.exists() or p.is_symlink() for p in (wrapper, desktop)):
            raise ValueError("An existing per-user browser launch customization was left untouched.")
        if BEGIN in content or END in content:
            raise ValueError("An existing Fontreal preference block was left untouched.")
    build_path = Path(subprocess.check_output(
        [sys.executable, str(ROOT / "tools/build-freetype.py")], text=True).splitlines()[-1])
    build = json.loads(build_path.read_text())
    library = build["libraries"]["candidate"]
    if sha(Path(library["library"])) != library["sha256"]:
        raise ValueError("The candidate library does not match its build record.")
    leading_newline = previous["block"].startswith("\n") if previous else content and not content.endswith("\n")
    block = (("\n" if leading_newline else "") + BEGIN + "".join(
        f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k, v in PREFS.items()) + END)
    record = previous or dict(profile=str(profile), user_js_existed=user_js.exists(), block=block,
        original_prefs=[line for line in (profile / "prefs.js").read_bytes().decode("utf-8").splitlines(keepends=True)
                        if OWNED_PREF.match(line)])
    program = binary(browser)
    main = Path(f"/usr/lib/{browser}/{browser}-bin")
    scope = list(dict.fromkeys(map(str, (program, program.resolve(), main.resolve() if main.exists() else program.resolve()))))
    command = [sys.executable, str(Path(__file__).resolve()), "run", browser, "--"]
    wrapper_text = "#!/bin/sh\nexec " + " ".join(map(shlex.quote, command)) + ' "$@"\n'
    original_desktop = desktop_source(browser).read_text()
    pattern = re.compile(r"^Exec=(?:" + re.escape(browser) + "|" + re.escape(str(program)) + r")(?=\s|$)", re.M)
    desktop_text, count = pattern.subn(lambda _: "Exec=" + desktop_arg(wrapper), original_desktop)
    if not count or count != len(re.findall(r"^Exec=", original_desktop, re.M)):
        raise ValueError("Unsupported desktop command; no launch hook was installed.")
    if re.search(r"^DBusActivatable=", desktop_text, re.M):
        desktop_text = re.sub(r"^DBusActivatable=.*$", "DBusActivatable=false", desktop_text, flags=re.M)
    else:
        desktop_text = desktop_text.replace("[Desktop Entry]\n", "[Desktop Entry]\nDBusActivatable=false\n", 1)
    for p in (state.parent, wrapper.parent, desktop.parent):
        p.mkdir(parents=True, exist_ok=True)
    updated = content.replace(record["block"], block, 1) if previous else content + block
    record["block"] = block
    if updated != content:
        write_profile(user_js, updated)
    if not record["user_js_existed"]:
        user_js.chmod(0o600)
    wrapper.write_text(wrapper_text)
    wrapper.chmod(0o755)
    desktop.write_text(desktop_text)
    record.update(browser_version=browser_version(browser), freetype_version=build["spec"]["source"], contrast="weighted",
        library=library["library"], library_sha256=library["sha256"], build=str(build_path), scope=scope,
        hooks=[dict(path=str(p), sha256=sha(p)) for p in (wrapper, desktop)])
    state.write_text(json.dumps(record, indent=2) + "\n")
    state.chmod(0o600)
    print(f"Enabled {browser} in its existing working profile. Fully quit and reopen it to activate.")


def disable(browser):
    state, _, _ = paths(browser)
    if not state.exists():
        print(f"{browser}: disabled")
        return
    record = json.loads(state.read_text())
    profile = Path(record["profile"])
    if profile in running_profiles(browser).values():
        raise ValueError(f"Fully quit {browser} before disabling; its preferences were left untouched.")
    require_owned(record)
    user_js = profile / "user.js"
    content = user_js.read_bytes().decode("utf-8")
    if content.count(record["block"]) != 1:
        raise ValueError("The owned user.js block changed; no settings were overwritten.")
    remainder = content.replace(record["block"], "", 1)
    prefs = profile / "prefs.js"
    restored = "".join(line for line in prefs.read_bytes().decode("utf-8").splitlines(keepends=True) if not OWNED_PREF.match(line))
    if restored and not restored.endswith("\n"):
        restored += "\n"
    restored += "".join(record["original_prefs"])
    write_profile(prefs, restored)
    if remainder or record["user_js_existed"]:
        write_profile(user_js, remainder)
    else:
        user_js.unlink()
    for entry in record["hooks"]:
        Path(entry["path"]).unlink()
    state.unlink()
    print(f"Disabled {browser}; original rendering preferences restored. Browser data retained.")


def compatibility(browser, record):
    library = Path(record["library"])
    if not library.is_file() or sha(library) != record["library_sha256"]:
        return "private library is missing or changed"
    return None


def run(browser, arguments):
    state, _, _ = paths(browser)
    record = json.loads(state.read_text()) if state.exists() else None
    env = os.environ.copy()
    for key in ("FONTREAL_FT_RENDERING", "FONTREAL_FT_CONTRAST", "FONTREAL_FT_EXECUTABLE", "FONTREAL_PROFILE"):
        env.pop(key, None)
    if record:
        directory = str(Path(record["library"]).parent)
        existing = env.get("LD_LIBRARY_PATH")
        inherited = [p for p in existing.split(":") if p != directory] if existing is not None else []
        if inherited:
            env["LD_LIBRARY_PATH"] = ":".join(inherited)
        else:
            env.pop("LD_LIBRARY_PATH", None)
        reason = compatibility(browser, record)
        if reason:
            print(f"Fontreal inactive: {reason}; using the installed browser library. Re-enable after rebuilding.", file=sys.stderr)
        else:
            env.update(FONTREAL_FT_RENDERING="1", FONTREAL_FT_CONTRAST=record.get("contrast", "mild"),
                       FONTREAL_PROFILE=rendering_profile(),
                       FONTREAL_FT_EXECUTABLE=":".join(record["scope"]),
                       LD_LIBRARY_PATH=":".join([directory, *inherited]))
    os.execve(binary(browser), [str(binary(browser)), *arguments], env)


def status(browser):
    state, _, _ = paths(browser)
    if not state.exists():
        print(json.dumps(dict(browser=browser, enabled=False)))
        return
    record = json.loads(state.read_text())
    parents = {pid: path for pid, path in running_profiles(browser).items() if path == Path(record["profile"])}
    active, pending = [], []
    for pid in parents:
        maps = Path(f"/proc/{pid}/maps").read_text()
        environment = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        expected = [b"FONTREAL_FT_RENDERING=1",
                    ("FONTREAL_PROFILE=" + rendering_profile()).encode(),
                    ("FONTREAL_FT_CONTRAST=" + record.get("contrast", "mild")).encode(),
                    ("FONTREAL_FT_EXECUTABLE=" + ":".join(record["scope"])).encode()]
        (active if record["library"] in maps and all(v in environment for v in expected) else pending).append(pid)
    print(json.dumps(dict(browser=browser, enabled=True, profile=record["profile"],
        active_pids=active, restart_required_pids=pending, contrast=record.get("contrast", "mild"),
        rendering_profile=rendering_profile(),
        compatibility=compatibility(browser, record))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "disable", "status", "run"))
    parser.add_argument("browser", choices=BROWSERS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    if args.action != "run" and arguments:
        parser.error("Only run accepts browser arguments.")
    try:
        if args.action == "run":
            run(args.browser, arguments)
        else:
            {"enable": enable, "disable": disable, "status": status}[args.action](args.browser)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
