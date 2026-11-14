#!/usr/bin/env python3
"""Prove existing-profile activation with test-owned data and installed browsers."""
import argparse
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import configparser
import importlib.util
import http.server
import io
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

import browser_masks_test as masks
import browser_live_recipe_test as recipe

ROOT = masks.ROOT
OUT = (ROOT / "results/browser-delivery").resolve()
spec = importlib.util.spec_from_file_location("fontreal_browser", ROOT / "tools/browser.py")
browser_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser_tool)


def main_call(action, browser, failure=None):
    out, err = io.StringIO(), io.StringIO()
    with patch.object(sys, "argv", [str(ROOT / "tools/browser.py"), action, browser]), redirect_stdout(out), redirect_stderr(err):
        try:
            browser_tool.main()
        except SystemExit as error:
            assert failure and error.code == 2, (error, err.getvalue())
        else:
            assert failure is None, "Unsafe activation unexpectedly succeeded"
    if failure:
        assert failure in err.getvalue(), err.getvalue()
    return out.getvalue()


def tree(path):
    return {str(p.relative_to(path)): masks.digest(p) for p in path.rglob("*") if p.is_file()}


@contextmanager
def observations(root, indexes, pids=()):
    """Replace opaque OS observations; all product behavior remains production code."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(Path, "home", return_value=root))
        stack.enter_context(patch.object(browser_tool, "profile_indexes", side_effect=lambda _: indexes))
        stack.enter_context(patch.object(browser_tool, "process_ids", side_effect=lambda: [Path(f"/proc/{p}") for p in pids]))
        stack.enter_context(patch.dict(os.environ, {
            "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data")}))
        yield


def index_fixture(root, profile):
    base = root / "index"
    base.mkdir(parents=True, exist_ok=True)
    unused = base / "unused"
    unused.mkdir(exist_ok=True)
    (unused / "prefs.js").write_text('user_pref("fixture.unused", 17);\n')
    index = base / "profiles.ini"
    index.write_text(f'''[Profile0]
Name=misleading-first
IsRelative=1
Path=unused
Default=1
[Profile1]
Name=misleading-duplicate-prefix
IsRelative=1
Path=unused
Default=1
[InstallTEST]
Default={profile}
Locked=1
[InstallTEST2]
Default={profile}
Locked=1
''')
    return index, unused


def discovery(root):
    results = []
    for browser in browser_tool.VERSIONS:
        home = root / browser
        profile = home / "existing"
        profile.mkdir(parents=True)
        original = b'user_pref("fixture.keep", 23);\n'
        (profile / "prefs.js").write_bytes(original)
        index, unused = index_fixture(home, profile)
        fixed = tree(unused), index.read_bytes()
        with observations(home, [index]):
            main_call("enable", browser)
            state, wrapper, desktop = browser_tool.paths(browser)
            record = json.loads(state.read_text())
            assert Path(record["profile"]) == profile
            assert (profile / "prefs.js").read_bytes() == original
            assert set(p.name for p in profile.iterdir()) == {"prefs.js", "user.js"}
            assert tree(unused) == fixed[0] and index.read_bytes() == fixed[1]
            main_call("disable", browser)
            assert not (profile / "user.js").exists() and not state.exists()
            assert not wrapper.exists() and not desktop.exists()
            main_call("disable", browser)
            for kind, text in (
                ("missing", "[Profile0]\nPath=unused\nDefault=1\n"),
                ("conflicting", f"[InstallA]\nDefault={profile}\n[InstallB]\nDefault={profile}\n[InstallC]\nDefault={unused}\n"),
                ("nonexistent", f"[InstallA]\nDefault={home / 'does-not-exist'}\n"),
            ):
                index.write_text(text)
                before = tree(home)
                main_call("enable", browser, "no profile" if kind != "nonexistent" else "already contain prefs.js")
                assert tree(home) == before, (browser, kind)
                results.append([browser, kind])
            index.write_bytes(fixed[1])
            # Only the installed revision observation differs in this D6 contrast.
            before = tree(home)
            with patch.object(browser_tool, "browser_version", return_value="future-incompatible"):
                main_call("enable", browser, "targets")
            assert tree(home) == before
            main_call("enable", browser)
            record = json.loads(state.read_text())
            # Upgrade the old owned block without losing its first restoration baseline.
            user_js = profile / "user.js"
            original_prefs = record["original_prefs"]
            old_block = "\n" + record["block"].replace('freetype.gamma", -1','freetype.gamma", 0')
            user_js.write_text('user_pref("fixture.no.newline", 19);' + old_block)
            record["block"] = old_block
            record.pop("contrast")
            state.write_text(json.dumps(record))
            legacy = []
            with patch.object(os, "execve", side_effect=lambda *args: legacy.append(args)):
                browser_tool.run(browser, [])
            assert legacy[0][2]["FONTREAL_FT_CONTRAST"] == "mild"
            main_call("enable", browser)
            upgraded = json.loads(state.read_text())
            assert upgraded["contrast"] == "raw" and upgraded["original_prefs"] == original_prefs
            assert upgraded["block"].startswith("\n")
            assert user_js.read_text() == 'user_pref("fixture.no.newline", 19);' + upgraded["block"]
            state.write_text(json.dumps(dict(upgraded,contrast="ramp217")))
            with patch.object(os, "execve", side_effect=lambda *args: legacy.append(args)):
                browser_tool.run(browser, [])
            assert legacy[-1][2]["FONTREAL_FT_CONTRAST"] == "ramp217"
            main_call("enable", browser)
            upgraded = json.loads(state.read_text())
            assert upgraded["contrast"] == "raw" and upgraded["original_prefs"] == original_prefs
            assert user_js.read_text() == 'user_pref("fixture.no.newline", 19);' + upgraded["block"]
            directory = str(Path(record["library"]).parent)
            captured = []
            fallback_before = tree(profile)
            inherited = f":/fixture/loader::{directory}:/fixture/tail:"
            with patch.object(browser_tool, "browser_version", return_value="future-incompatible"), \
                    patch.object(os, "execve", side_effect=lambda *args: captured.append(args)), \
                    patch.dict(os.environ, LD_LIBRARY_PATH=inherited, FONTREAL_FT_RENDERING="1", FONTREAL_FT_CONTRAST="mild", FONTREAL_FT_EXECUTABLE="bad"):
                err = io.StringIO()
                with redirect_stderr(err):
                    browser_tool.run(browser, ["https://example.invalid/a b?$=&"])
                assert "Fontreal inactive: browser version changed" in err.getvalue()
            executable, argv, env = captured.pop()
            assert executable == Path("/usr/bin") / browser
            assert argv == [str(executable), "https://example.invalid/a b?$=&"]
            assert env["LD_LIBRARY_PATH"] == ":/fixture/loader::/fixture/tail:"
            assert not any(k in env for k in ("FONTREAL_FT_RENDERING", "FONTREAL_FT_CONTRAST", "FONTREAL_FT_EXECUTABLE"))
            assert tree(profile) == fallback_before
            for failure in ("freetype", "provider-record", "missing", "changed"):
                incompatible = dict(upgraded)
                if failure == "missing": incompatible["library"] = str(home / "missing-library.so")
                if failure == "changed": incompatible["library_sha256"] = "0" * 64
                state.write_text(json.dumps(incompatible))
                current_directory = str(Path(incompatible["library"]).parent)
                with ExitStack() as stack:
                    if failure == "freetype": stack.enter_context(patch.object(browser_tool, "freetype_version", return_value="future-incompatible"))
                    if failure == "provider-record": stack.enter_context(patch.object(browser_tool, "freetype_version", side_effect=ValueError("Untrusted provider")))
                    stack.enter_context(patch.object(os, "execve", side_effect=lambda *args: captured.append(args)))
                    stack.enter_context(patch.dict(os.environ, LD_LIBRARY_PATH=f":/fixture/loader::{current_directory}:/fixture/tail:", FONTREAL_FT_RENDERING="1", FONTREAL_FT_CONTRAST="ramp217", FONTREAL_FT_EXECUTABLE="bad"))
                    err = io.StringIO()
                    with redirect_stderr(err): browser_tool.run(browser, ["https://example.invalid/a b?$=&"])
                    reason = ("installed FreeType revision changed" if failure == "freetype" else
                              "installed FreeType provider record is unavailable or changed" if failure == "provider-record" else
                              "private library is missing or changed")
                    assert reason in err.getvalue()
                executable, argv, env = captured.pop()
                assert executable == Path("/usr/bin") / browser and argv == [str(executable), "https://example.invalid/a b?$=&"]
                assert env["LD_LIBRARY_PATH"] == ":/fixture/loader::/fixture/tail:"
                assert not any(k.startswith("FONTREAL_FT_") for k in env)
                assert tree(profile) == fallback_before
            state.write_text(json.dumps(upgraded))
            main_call("disable", browser)
            assert user_js.read_text() == 'user_pref("fixture.no.newline", 19);'
            assert [line for line in (profile / "prefs.js").read_text().splitlines(keepends=True)
                    if browser_tool.OWNED_PREF.match(line)] == original_prefs
            original_check_output = subprocess.check_output
            for version,machine in (("unknown", "x86_64"), (upgraded["freetype_version"], "aarch64")):
                before = tree(home)
                def rejected_builder(command, **kwargs):
                    assert command == [sys.executable, str(ROOT / "tools/build-freetype.py")]
                    return original_check_output(recipe.builder_rejection_command(version,machine), stderr=subprocess.STDOUT, **kwargs)
                with patch.object(subprocess, "check_output", side_effect=rejected_builder):
                    try: main_call("enable", browser)
                    except subprocess.CalledProcessError as error:
                        assert error.returncode == 2 and "Requires amd64" in error.output
                    else: raise AssertionError("Unsupported builder activated a profile")
                assert tree(home) == before
        results.append([browser, "unique-install-default", "version-rejection", "version-fallback"])
    return results


def process_observation(root):
    """A normal package replacement leaves a live parent's exe marked deleted."""
    results = []
    for browser in browser_tool.VERSIONS:
        home = root / browser
        profile = home / "existing"
        profile.mkdir(parents=True)
        (profile / "prefs.js").write_text('user_pref("fixture.keep", 43);\n')
        index, unused = index_fixture(home, profile)
        process = home / "proc" / str(os.getpid())
        (process / "fd").mkdir(parents=True)
        (process / "fd/7").symlink_to(profile / ".parentlock")
        main = Path(f"/usr/lib/{browser}/{browser}-bin")
        executable = main.resolve() if main.exists() else browser_tool.binary(browser).resolve()
        agreeing = []
        for offset in (1, 2):
            extra = home / "proc" / str(os.getpid() + offset)
            (extra / "fd").mkdir(parents=True)
            (extra / "exe").symlink_to(executable)
            (extra / "fd/7").symlink_to(profile / ".parentlock")
            agreeing.append(extra)
        for parent in [process, *agreeing]:
            (parent / "cmdline").write_bytes(str(executable).encode() + b"\0")
            (parent / "environ").write_bytes(b"DISPLAY=:1\0")
        with observations(home, [index]), patch.object(browser_tool, "process_ids", return_value=[process]):
            for suffix in ("", " (deleted)"):
                link = process / "exe"
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(str(executable) + suffix)
                found = browser_tool.running_profiles(browser)
                assert found == {os.getpid(): profile}, (browser, suffix, found)
                assert browser_tool.working_profile(browser) == profile
                original = index.read_bytes()
                index.write_text(index.read_text().replace(str(profile), str(unused)))
                before = tree(home)
                main_call("enable", browser, "running profile differs")
                assert tree(home) == before
                index.write_bytes(original)
                results.append([browser, suffix or "current", "retained-live-parent"])
                with patch.object(browser_tool, "process_ids", return_value=[process, *agreeing]):
                    assert browser_tool.working_profile(browser) == profile
                    main_call("enable", browser)
                    state, _, _ = browser_tool.paths(browser)
                    assert json.loads(state.read_text())["profile"] == str(profile)
                    late_lock = agreeing[-1] / "fd/7"
                    late_lock.unlink()
                    late_lock.symlink_to(unused / ".parentlock")
                    before = tree(home)
                    main_call("enable", browser, "running profile differs")
                    assert tree(home) == before
                    late_lock.unlink()
                    late_lock.symlink_to(profile / ".parentlock")
                    with patch.object(browser_tool, "process_ids", return_value=[]):
                        main_call("disable", browser)
                results.append([browser, suffix or "current", "agreeing-prefix-late-conflict"])
            index.write_text(index.read_text() + f"\n[InstallHISTORICAL]\nDefault={unused}\nLocked=1\n")
            before = tree(home)
            if browser != "firefox":
                main_call("enable", browser, "no profile")
                assert tree(home) == before
                continue
            with patch.object(browser_tool, "process_ids", return_value=[process, *agreeing]):
                main_call("enable", browser)
                state, _, _ = browser_tool.paths(browser)
                assert json.loads(state.read_text())["profile"] == str(profile)
                for argument in ("-P", "--profile=other", "-profile", "--ProfileManager", "--createprofile",
                                 "--no-remote", "--new-instance", "--reset-profile", "--migration"):
                    (agreeing[-1] / "cmdline").write_bytes(str(executable).encode() + b"\0" + argument.encode() + b"\0")
                    before = tree(home)
                    main_call("enable", browser, "no profile")
                    assert tree(home) == before
                (agreeing[-1] / "cmdline").write_bytes(str(executable).encode() + b"\0")
                for key in ("XRE_PROFILE_PATH", "XRE_PROFILE_LOCAL_PATH", "SELECTABLE_PROFILE_RESET_PATH",
                            "SELECTABLE_PROFILE_RESET_STORE_ID", "XRE_RESTARTED_BY_PROFILE_MANAGER",
                            "XRE_RESTARTED_BY_PROFILE_SELECTOR", "MOZ_LEGACY_PROFILES",
                            "MOZ_RESET_PROFILE_RESTART", "XRE_RESTART_TO_PROFILE_MANAGER"):
                    for value in ("", "other"):
                        (agreeing[-1] / "environ").write_bytes(f"{key}={value}\0".encode())
                        before = tree(home)
                        main_call("enable", browser, "no profile")
                        assert tree(home) == before
                (agreeing[-1] / "environ").write_bytes(b"DISPLAY=:1\0")
                lock = agreeing[-1] / "fd/7"
                lock.unlink()
                lock.symlink_to(unused / ".parentlock")
                before = tree(home)
                main_call("enable", browser, "no profile")
                assert tree(home) == before
                lock.unlink()
                lock.symlink_to(profile / ".parentlock")
            with patch.object(browser_tool, "process_ids", return_value=[]):
                before = tree(home)
                main_call("enable", browser, "no profile")
                assert tree(home) == before
                main_call("disable", browser)
            results.append([browser, "historical-default", "ordinary-authority-and-selector-rejections"])
    return results


def desktop_checks(root):
    results = []
    for browser in browser_tool.VERSIONS:
        home = root / f"{browser} home with spaces"
        profile = home / "existing"
        profile.mkdir(parents=True)
        (profile / "prefs.js").write_text('user_pref("fixture.keep", 31);\n')
        index, _ = index_fixture(home, profile)
        source = home / "native.desktop"
        source.write_bytes(browser_tool.desktop_source(browser).read_bytes())
        with observations(home, [index]), patch.object(browser_tool, "desktop_source", return_value=source):
            main_call("enable", browser)
            state, wrapper, desktop = browser_tool.paths(browser)
            record = json.loads(state.read_text())
            bootstrap = home / "bootstrap"
            bootstrap.mkdir()
            # Only OS home and the external exec boundary are replaced in wrapper children.
            (bootstrap / "sitecustomize.py").write_text('''import json, os
from pathlib import Path
Path.home = classmethod(lambda cls: Path(os.environ["FONTREAL_TEST_HOME"]))
def record(path, argv, env):
    with open(os.environ["FONTREAL_TEST_CAPTURE"], "w") as out:
        json.dump(dict(path=str(path), argv=argv, env=env), out)
    os._exit(0)
os.execve = record
''')
            capture = home / "exec.json"
            env = dict(os.environ, PYTHONPATH=str(bootstrap), FONTREAL_TEST_HOME=str(home),
                       FONTREAL_TEST_CAPTURE=str(capture), LD_LIBRARY_PATH=":/fixture/head::/fixture/tail:",
                       FONTREAL_TEST_UNRELATED="retained $ & value")
            url = "https://example.invalid/a space?$literal=one&two=three"
            def check(arguments):
                for _ in range(100):
                    if capture.exists():
                        break
                    time.sleep(.05)
                assert capture.exists(), (browser, arguments)
                got = json.loads(capture.read_text())
                capture.unlink()
                assert got["path"] == f"/usr/bin/{browser}"
                assert got["argv"] == [f"/usr/bin/{browser}", *arguments], got
                child_env = got["env"]
                library_dir = str(Path(record["library"]).parent)
                assert child_env["LD_LIBRARY_PATH"] == library_dir + ":" + env["LD_LIBRARY_PATH"]
                assert child_env["FONTREAL_FT_EXECUTABLE"].split(":") == record["scope"]
                assert child_env["FONTREAL_FT_RENDERING"] == "1" and child_env["FONTREAL_FT_CONTRAST"] == "raw"
                for key, value in env.items():
                    if key != "LD_LIBRARY_PATH":
                        assert child_env.get(key) == value, (key, child_env.get(key), value)
            masks.run([wrapper, "--new-tab", url], env=env)
            check(["--new-tab", url])
            # Gio parses the actual generated desktop entry and expands native field codes.
            gio = '''import gi, sys
from gi.repository import Gio
app = Gio.DesktopAppInfo.new_from_filename(sys.argv[1])
assert app
if sys.argv[2] == "main":
    assert app.launch_uris([sys.argv[3]], None)
else:
    app.launch_action(sys.argv[2], None)
'''
            config = configparser.ConfigParser(interpolation=None)
            config.read(source)
            actions = config["Desktop Entry"]["Actions"].strip(";").split(";")
            assert len(actions) == 3
            masks.run(["/usr/bin/python3", "-c", gio, desktop, "main", url], env=env)
            check([url])
            results.append([browser, "command", "gio-main"])
            for action in actions:
                original = shlex.split(config[f"Desktop Action {action}"]["Exec"])[1:]
                expected = [arg for arg in original if arg not in ("%u", "%U", "%f", "%F")]
                masks.run(["/usr/bin/python3", "-c", gio, desktop, action], env=env)
                check(expected)
                results.append([browser, action, expected])
            main_call("disable", browser)
    return results


def process_scope(record):
    font = masks.NOTO / "NotoSans-Regular.ttf"
    executable = str(masks.WORK / "mask-probe")
    with patch.dict(os.environ):
        os.environ.pop("FONTREAL_FT_EXECUTABLE", None)
        baseline = masks.probe(record, font, variant="stock")["rendered"][0]
        expected = masks.mild(masks.probe(record, font, flags=0x20028, variant="stock")["rendered"][0])
        assert expected != baseline
        checks = [(None, expected), (executable, expected), ("/usr/bin/firefox", baseline),
                  (executable + "-prefix", baseline),
                  (f"{executable}-prefix:{executable}-prefix:{executable}", expected)]
        results = []
        for scope, wanted in checks:
            if scope is None:
                os.environ.pop("FONTREAL_FT_EXECUTABLE", None)
            else:
                os.environ["FONTREAL_FT_EXECUTABLE"] = scope
            actual = masks.probe(record, font)["rendered"][0]
            assert actual == wanted, scope
            results.append(scope)
    font2 = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    cff = Path("/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR="1", FONTREAL_RENDERING="1",
               FONTREAL_BLEND="linear", FONTREAL_CONTRAST="mild", FONTREAL_FITTING="")
    for key in ("FONTREAL_FT_RENDERING", "FONTREAL_FT_CONTRAST", "FONTREAL_FT_EXECUTABLE", "LD_LIBRARY_PATH"):
        env.pop(key, None)
    def qt(name, extra):
        directory = OUT / name
        directory.mkdir(exist_ok=True)
        got = masks.run([ROOT / "build/qt-native-probe", "stock", "mild", 15, 1, font, font2, cff, directory], env=dict(env, **extra))
        (directory / "result.json").write_text(got.stdout)
        return json.loads(got.stdout)
    normal = qt("qt-normal", {})
    inherited = dict(LD_LIBRARY_PATH=str(Path(record["libraries"]["candidate"]["library"]).parent),
                     FONTREAL_FT_RENDERING="1", FONTREAL_FT_CONTRAST="raw", FONTREAL_FT_EXECUTABLE="/usr/bin/firefox:/usr/lib/firefox/firefox-bin")
    scoped = qt("qt-inherited", inherited)
    unscoped = qt("qt-unscoped-control", {k: v for k, v in inherited.items() if k != "FONTREAL_FT_EXECUTABLE"})
    for key in ("masks", "images", "qtGui", "fonts"):
        assert normal[key] == scoped[key], key
    assert normal["masks"][:16] != unscoped["masks"][:16]
    assert normal["masks"][16:] != unscoped["masks"][16:]
    assert normal["images"][180:] != unscoped["images"][180:]
    fc_command = ["fc-match", "-f", "%{file}|%{family}|%{style}|%{hinting}|%{hintstyle}|%{autohint}|%{rgba}\n", "Noto Sans"]
    fontconfig = masks.run(fc_command, env=env).stdout
    assert masks.run(fc_command, env=dict(env, **inherited)).stdout == fontconfig
    return dict(public_masks=results, qt_masks=len(normal["masks"]), qt_images=len(normal["images"]), fontconfig=fontconfig)


def lifecycle(root, record):
    root.mkdir(parents=True)
    real_home = Path.home()
    native_bundle = os.environ.get("FONTREAL_TEST_NATIVE_BUNDLE")
    home = real_home if native_bundle else root / "home"
    if not native_bundle:
        (home / "Projects/fontreal").mkdir(parents=True)
    metadata = {}
    saved_indexes = {}
    if native_bundle:
        for base in (home / ".config/mozilla/firefox", home / ".mozilla/firefox", home / ".floorp"):
            for name in ("profiles.ini", "installs.ini"):
                path = base / name
                saved_indexes[path] = path.read_bytes() if path.exists() else None
    for browser in browser_tool.VERSIONS:
        if native_bundle:
            assert not browser_tool.paths(browser)[0].exists(), "Use an unconfigured disposable browser account."
        config = configparser.ConfigParser(interpolation=None)
        config.read(browser_tool.profile_indexes(browser))
        if native_bundle:
            assert config.sections() and all(s.startswith("Install") and config[s].get("Default") == "unused"
                                             for s in config.sections()), "Use only seeded disposable installation identities."
            for path in browser_tool.profile_indexes(browser):
                unused = path.parent / "unused"
                if unused.exists():
                    assert list(unused.iterdir()) == [unused / "prefs.js"]
                    assert (unused / "prefs.js").read_text() == 'user_pref("fixture.unused", 49);\n'
        metadata[browser] = [section for section in config.sections() if section.startswith("Install")]
        assert metadata[browser]
    namespace = [] if native_bundle else ["bwrap", "--bind", "/", "/", "--bind", str(home), str(real_home),
                 "--bind", str(ROOT), str(ROOT), "--proc", "/proc", "--dev-bind", "/dev", "/dev"]
    output = root / "lifecycle.json"
    metadata_path = root / "installation-identities.json"
    metadata_path.write_text(json.dumps(metadata))
    record_path = root / "build.json"
    record_path.write_text(json.dumps(record))
    runner = """import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import browser_delivery_test as test
root = Path(sys.argv[2])
results = test.lifecycle_inside(root, json.loads((root/'build.json').read_text()), json.loads((root/'installation-identities.json').read_text()))
(root/'lifecycle.json').write_text(json.dumps(results))
"""
    try:
        subprocess.run([*namespace, sys.executable, "-c", runner, str(ROOT / "tests"), str(root)], check=True,
                       timeout=1200 if native_bundle else 300)
    finally:
        if native_bundle:
            for browser in browser_tool.VERSIONS:
                state = browser_tool.paths(browser)[0]
                if state.exists():
                    activation = json.loads(state.read_text())
                    assert Path(activation["profile"]).is_relative_to(root)
                    subprocess.run([sys.executable, ROOT / "tools/browser.py", "disable", browser], check=True,
                                   text=True, capture_output=True)
            for path, content in saved_indexes.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)
    results = json.loads(output.read_text())
    for result in results:
        result["namespace"] = namespace
    return results


def lifecycle_inside(root, record, installation_identities):
    native_helper = os.environ.get("FONTREAL_TEST_NATIVE_HELPER") == "1"
    native_bundle = os.environ.get("FONTREAL_TEST_NATIVE_BUNDLE")
    if native_bundle:
        assert native_helper and Path("/var/lib/fontreal-test-ready").is_file()
        subprocess.run(["systemd-detect-virt", "--vm"], check=True, capture_output=True)
        native_bundle = Path(native_bundle).resolve()
    real_home = Path.home()
    home = real_home if native_bundle else root / "home"
    # The native home provider changes only inside this mount namespace.
    namespace = []
    class StoragePage(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<!doctype html><title>Test-owned browser data</title><p>storage fixture</p>")
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StoragePage)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    storage_url = f"http://127.0.0.1:{server.server_port}/"
    results = []
    owned_pids = root / "owned-pids.json"
    owned_pids.write_text("[]")
    provider = root / "os-process-provider.py"
    provider.write_text("""import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('working_browser', sys.argv.pop(1))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
inventory = Path(sys.argv.pop(1))
module.process_ids = lambda: [Path('/proc') / str(pid) for pid in json.loads(inventory.read_text())]
module.main()
""")
    normal_fonts = root / "normal-fonts.conf"
    if native_bundle:
        normal_fonts.write_text('''<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig><include>/etc/fonts/fonts.conf</include><match target="font">
<edit name="antialias" mode="assign"><bool>true</bool></edit>
<edit name="hinting" mode="assign"><bool>true</bool></edit>
<edit name="hintstyle" mode="assign"><const>hintfull</const></edit>
<edit name="autohint" mode="assign"><bool>false</bool></edit>
<edit name="rgba" mode="assign"><const>none</const></edit>
</match></fontconfig>''')
    def indexes(browser, profile):
        installs = installation_identities[browser]
        bases = [home / ".config/mozilla/firefox", home / ".mozilla/firefox"] if browser == "firefox" else [home / ".floorp"]
        for base in bases:
            base.mkdir(parents=True, exist_ok=True)
            unused = base / "unused"
            unused.mkdir(exist_ok=True)
            (unused / "prefs.js").write_text('user_pref("fixture.unused", 49);\n')
            text = "[General]\nStartWithLastProfile=1\nVersion=2\n"
            for number in range(2):
                text += f"[Profile{number}]\nName=misleading-{number}\nIsRelative=1\nPath=unused\nDefault=1\n"
            text += f"[Profile2]\nName=working\nIsRelative=0\nPath={profile}\n"
            for install in installs:
                text += f"[{install}]\nDefault={profile}\nLocked=1\n"
            if browser == "firefox":
                text += f"[InstallHISTORICAL]\nDefault={unused}\nLocked=1\n"
            (base / "profiles.ini").write_text(text)
            (base / "installs.ini").write_text("".join(f"[{install[7:]}]\nDefault={profile}\nLocked=1\n" for install in installs))
        return {str(p): masks.digest(p) for base in bases for p in base.rglob("*") if p.is_file()}
    try:
        with masks.nested_display() as display:
            for browser in browser_tool.VERSIONS:
                for explicit in (False, True):
                    label = f"{browser}-{'explicit' if explicit else 'absent'}"
                    directory = OUT / label
                    directory.mkdir(exist_ok=True)
                    profile = root / label
                    profile.mkdir()
                    with socket.socket() as reservation:
                        reservation.bind(("127.0.0.1", 0))
                        port = reservation.getsockname()[1]
                    settings = {
                        "browser.shell.checkDefaultBrowser": False, "browser.aboutwelcome.enabled": False,
                        "browser.startup.page": 0, "datareporting.policy.dataSubmissionEnabled": False,
                        "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
                        "datareporting.healthreport.uploadEnabled": False, "layout.css.devPixelsPerPx": "1",
                        "marionette.port": port, "fixture.keep": 53,
                    }
                    (profile / "user.js").write_text("".join(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k,v in settings.items()))
                    # Native XDG selection stays fixed across enable, remote, cold launch, and reversal.
                    env = dict(display, XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                               TMPDIR=str(root), GDK_BACKEND="wayland", MOZ_ENABLE_WAYLAND="1", MOZ_REMOTE_ALLOW_SYSTEM_ACCESS="1",
                               FONTREAL_RENDERING="1", FONTREAL_BLEND="encoded" if native_helper else "linear",
                               FONTREAL_CONTRAST="none" if native_helper else "mild",
                               FONTREAL_FITTING="nearest" if native_helper else "")
                    if native_helper:
                        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
                    if native_bundle:
                        env["FONTCONFIG_FILE"] = str(normal_fonts)
                    child = client = log = None
                    def command(arguments):
                        return [*namespace, *map(str, arguments)]
                    def tool(action, failure=None):
                        result = subprocess.run(command([sys.executable, provider, ROOT / "tools/browser.py", owned_pids, action, browser]),
                                                env=env, text=True, capture_output=True, timeout=180)
                        if failure:
                            assert result.returncode == 2 and failure in result.stderr, result.stderr
                        else:
                            assert result.returncode == 0, result.stderr
                        return result.stdout
                    def chrome(script):
                        client.command("Marionette:SetContext", {"value": "chrome"})
                        try:
                            return client.script(script)
                        finally:
                            client.command("Marionette:SetContext", {"value": "content"})
                    def identity():
                        return chrome("return {profile: Services.dirsvc.get('ProfD', Ci.nsIFile).path, pid: Services.appinfo.processID};")
                    def owned():
                        return chrome("return Object.fromEntries(" + json.dumps(list(browser_tool.PREFS)) + ".map(k => [k, {user: Services.prefs.prefHasUserValue(k), value: Services.prefs.getPrefType(k) === 128 ? Services.prefs.getBoolPref(k) : Services.prefs.getIntPref(k)}]));")
                    helper = directory / "qt-helper.sh"
                    qt_command = [str(ROOT / "build/qt-native-probe"), "raw" if native_helper else "stock",
                                  "none" if native_helper else "mild", "12" if native_helper else "15", "1",
                                  str(masks.NOTO / "NotoSans-Regular.ttf"), "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                  "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf", str(directory)]
                    fc_command = ["fc-match", "-f", "%{file}|%{family}|%{style}|%{hinting}|%{hintstyle}|%{autohint}|%{rgba}", "Noto Sans"]
                    def browser_helper(phase, fallback=False, disabled=False):
                        selected_command = list(qt_command)
                        if fallback:
                            selected_command[1] = "raw-stock"
                        prefix = "FONTREAL_RENDERING=0 FONTREAL_FITTING= " if disabled else ""
                        helper.write_text('#!/bin/sh\nset -eu\nprintf \'%s\\n\' "${FONTREAL_FT_RENDERING-}" "${FONTREAL_FT_CONTRAST-}" "${FONTREAL_FT_EXECUTABLE-}" "${LD_LIBRARY_PATH-}" > "$1.env"\n' +
                                          shlex.join(fc_command) + ' > "$1.fc"\n' + prefix +
                                          'QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1 exec ' + shlex.join(selected_command) + ' > "$1"\n')
                        helper.chmod(0o755)
                        output = directory / f"qt-child-{phase}.json"
                        code = ("const file = Cc['@mozilla.org/file/local;1'].createInstance(Ci.nsIFile);"
                                "file.initWithPath(" + json.dumps(str(helper)) + ");"
                                "const task = Cc['@mozilla.org/process/util;1'].createInstance(Ci.nsIProcess);"
                                "task.init(file); task.run(true, [" + json.dumps(str(output)) + "], 1); return task.exitValue;")
                        assert chrome(code) == 0, (browser, phase)
                        return (json.loads(output.read_text()), Path(str(output) + ".env").read_text().splitlines(),
                                Path(str(output) + ".fc").read_text())
                    def navigate(url):
                        client.command("WebDriver:Navigate", {"url": url})
                    def launch(phase, bootstrap=False, expected_profile=None):
                        nonlocal child, client, log
                        log_path = directory / f"{phase}.log"
                        log = log_path.open("w")
                        args = [f"/usr/bin/{browser}", "--new-instance", "--profile", profile] if bootstrap else [real_home / ".local/bin" / browser]
                        if phase == "stock-pending" and browser == "firefox":
                            args = [f"/usr/bin/{browser}"]
                        args += ["--marionette", storage_url]
                        child = subprocess.Popen(command(args), env=env, stdout=log, stderr=log)
                        for _ in range(300):
                            assert child.poll() is None, log_path.read_text()[-4000:]
                            if "Marionette\tINFO\tListening on port" in log_path.read_text():
                                break
                            time.sleep(.1)
                        else:
                            raise AssertionError(log_path.read_text()[-4000:])
                        client = masks.Marionette(port)
                        client.command("WebDriver:SetWindowRect", dict(x=0, y=0, width=1380, height=1240))
                        got = identity()
                        owned_pids.write_text(json.dumps([got["pid"]]))
                        assert Path(got["profile"]) == (expected_profile or profile), got
                        assert env["HOME"] == os.environ["HOME"]
                        return got
                    def quit():
                        nonlocal child, client, log
                        client.command("Marionette:Quit", {"flags": ["eAttemptQuit"]})
                        client.close()
                        client = None
                        assert child.wait(timeout=30) == 0
                        child = None
                        owned_pids.write_text("[]")
                        log.close()
                        log = None
                    def storage(marker=None):
                        navigate(storage_url)
                        if marker:
                            return client.script("document.cookie='fontreal=' + " + json.dumps(marker) + " + ' ; Max-Age=3600; Path=/'; localStorage.setItem('fontreal', " + json.dumps(marker) + "); return true;")
                        return client.script("return {cookie: document.cookie, stored: localStorage.getItem('fontreal')};")
                    try:
                        launch("create-existing", bootstrap=True)
                        storage("early")
                        storage("early")
                        quit()
                        assert (profile / "prefs.js").is_file()
                        prefs = profile / "prefs.js"
                        original_values = {key: value for key, value in zip(browser_tool.PREFS, (True, False, 2, 77))} if explicit else {}
                        content = "".join(line for line in prefs.read_text().splitlines(keepends=True) if not browser_tool.OWNED_PREF.match(line))
                        prefs.write_text(content + "".join(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k,v in original_values.items()))
                        user_js = profile / "user.js"
                        original_user = b'// Existing working settings\r\nuser_pref("fixture.keep", 53);\r\n' if explicit else None
                        if original_user is None:
                            user_js.unlink()
                        else:
                            user_js.write_bytes(original_user)
                        fixed = indexes(browser, profile)
                        stock = launch("stock-pending", bootstrap=True)
                        stock_owned = owned()
                        assert all(item["user"] == explicit for item in stock_owned.values()), stock_owned
                        stock_maps = Path(f"/proc/{stock['pid']}/maps").read_text()
                        library = record["libraries"]["candidate"]["library"]
                        assert library not in stock_maps
                        normal_helper, normal_helper_env, normal_fc = browser_helper("stock")
                        assert normal_helper_env[:3] == ["", "", ""]
                        if native_bundle:
                            assert normal_fc.split("|")[-4:] == ["True", "3", "False", "5"], normal_fc
                        state = home / ".config/fontreal/browsers" / f"{browser}.json"
                        index_paths = [Path(path) for path in fixed if path.endswith("/profiles.ini")]
                        index_bytes = {path: path.read_bytes() for path in index_paths}
                        misleading_active = index_paths[0].parent / "unused"
                        original_user_bytes = user_js.read_bytes() if user_js.exists() else None
                        try:
                            for path in index_paths:
                                path.write_text(path.read_text().replace(str(profile), str(misleading_active)))
                            tool("enable", "no profile" if browser == "firefox" else "running profile differs")
                            assert not state.exists()
                            assert (user_js.read_bytes() if user_js.exists() else None) == original_user_bytes
                        finally:
                            for path, content in index_bytes.items():
                                path.write_bytes(content)
                        tool("enable")
                        activation = json.loads(state.read_text())
                        older_helper = None
                        if native_helper:
                            # Given an existing real v1 activation, upgrade through the production launcher.
                            older_path, older_library = recipe.v1_provider(record)
                            assert masks.digest(Path(older_library["library"])) == older_library["sha256"]
                            activation.update(library=older_library["library"], library_sha256=older_library["sha256"], build=str(older_path))
                            state.write_text(json.dumps(activation, indent=2) + "\n")
                        original_prefs = activation["original_prefs"][:]
                        diagnostic = subprocess.run(command([sys.executable, "-c", "import os, pathlib, sys; p=pathlib.Path('/proc') / sys.argv[1]; print('EXE', os.readlink(p/'exe')); print('LOCKS', [(str(f), os.readlink(f)) for f in (p/'fd').iterdir() if 'lock' in os.readlink(f)])", str(stock["pid"])]), env=env, text=True, capture_output=True)
                        (directory / "process-observation.log").write_text(diagnostic.stdout + diagnostic.stderr)
                        status = json.loads(tool("status"))
                        assert status["restart_required_pids"] == [stock["pid"]] and status["active_pids"] == [], status
                        remote_url = storage_url + "?ordinary-remote=1#same-parent"
                        remote = masks.run(command([real_home / ".local/bin" / browser, remote_url]), env=env)
                        for _ in range(100):
                            handles = client.command("WebDriver:GetWindowHandles", {})
                            locations = []
                            for handle in handles:
                                client.command("WebDriver:SwitchToWindow", {"handle": handle})
                                locations.append(client.command("WebDriver:GetCurrentURL", {})["value"])
                            if remote_url in locations:
                                break
                            time.sleep(.1)
                        else:
                            raise AssertionError(locations)
                        assert identity() == stock and owned() == stock_owned
                        assert library not in Path(f"/proc/{stock['pid']}/maps").read_text()
                        before_live = owned(), user_js.read_bytes(), state.read_bytes()
                        tool("disable", "Fully quit")
                        assert (owned(), user_js.read_bytes(), state.read_bytes()) == before_live
                        quit()
                        if native_helper:
                            older_process = launch("older-v1")
                            assert older_library["library"] in Path(f"/proc/{older_process['pid']}/maps").read_text()
                            older_helper, older_env, _ = browser_helper("older-v1", fallback=True)
                            disabled_helper, _, _ = browser_helper("older-v1-disabled", fallback=True, disabled=True)
                            assert older_library["library"] in older_helper["freetypeLibraries"]
                            for key in ("masks", "images"):
                                assert older_helper[key] == disabled_helper[key]
                            assert older_helper["images"] != normal_helper["images"]
                            tool("enable")
                            activation = json.loads(state.read_text())
                            assert activation["original_prefs"] == original_prefs and activation["library"] == library
                            assert json.loads(tool("status"))["restart_required_pids"] == [older_process["pid"]]
                            quit()
                        treated = launch("treated")
                        assert treated["pid"] != stock["pid"]
                        assert library in Path(f"/proc/{treated['pid']}/maps").read_text()
                        actual_argv = Path(f"/proc/{treated['pid']}/cmdline").read_bytes().decode().rstrip("\0").split("\0")
                        assert not any(arg in ("--profile", "--no-remote", "--new-instance", "-P", "--name") for arg in actual_argv), actual_argv
                        actual_env = dict(item.split("=", 1) for item in Path(f"/proc/{treated['pid']}/environ").read_bytes().decode().split("\0") if "=" in item)
                        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
                            assert actual_env[key] == env[key], (key, actual_env.get(key), env[key])
                        assert "FONTCONFIG_FILE" not in actual_env or actual_env["FONTCONFIG_FILE"] == env.get("FONTCONFIG_FILE")
                        effective = owned()
                        assert {k:v["value"] for k,v in effective.items()} == browser_tool.PREFS
                        assert all(v["user"] for v in effective.values())
                        assert json.loads(tool("status"))["active_pids"] == [treated["pid"]]
                        inherited_helper, inherited_helper_env, inherited_fc = browser_helper("treated")
                        assert inherited_helper_env[:3] == ["1", "raw", ":".join(activation["scope"])]
                        assert str(Path(library).parent) in inherited_helper_env[3].split(":")
                        for key in ("masks", "images", "qtGui", "fonts"):
                            assert inherited_helper[key] == normal_helper[key], (browser, key)
                        assert inherited_fc == normal_fc
                        saved = storage()
                        assert saved == {"cookie": "fontreal=early", "stored": "early"}, saved
                        storage("later-changed")
                        storage("later-changed")
                        navigate((ROOT / "tests/browser_masks.html").as_uri() + "?size=15#preblend")
                        for _ in range(100):
                            if client.script("return !!window.fontreal && document.fonts.status === 'loaded'"):
                                break
                            time.sleep(.1)
                        measurement = client.script("return window.fontreal.measure()")
                        for _ in range(50):
                            image = masks.screenshot(env, directory / "treated.png")
                            if (17,91,143) in set(image.getdata()):
                                break
                            time.sleep(.1)
                        origin = next(cell["box"] for cell in measurement["cells"] if cell["name"] == "origin")
                        glyph = masks.crop(image, measurement, origin)
                        raw = recipe.probe(recipe.BUILD/'nearest/.libs/libfreetype.so.6', masks.NOTO / "NotoSans-Regular.ttf", char='m')
                        reference = raw['rendered'][0]
                        error = masks.fit(glyph, reference["width"], reference["height"], masks.blend(bytes.fromhex(reference["mask"]), (0,0,0), (255,255,255), False))
                        assert error["error"] <= 1, (browser, error)
                        tool("enable")
                        quit()
                        repeated = json.loads(state.read_text())
                        assert repeated["original_prefs"] == original_prefs
                        assert repeated["block"] == activation["block"]
                        assert user_js.read_text().count(browser_tool.BEGIN) == 1
                        native_transitions = []
                        if native_bundle:
                            saved_state = state.read_bytes(), user_js.read_bytes()
                            inherited_library_path = env["LD_LIBRARY_PATH"]
                            native_command = [sys.executable, ROOT / "tools/system-build.py"]
                            try:
                                subprocess.run(["sudo", *map(str, native_command), "install", str(native_bundle)], check=True,
                                               text=True, capture_output=True)
                                installed_version = subprocess.check_output(
                                    ["dpkg-query", "-W", "-f=${Version}", "libfreetype6:amd64"], text=True)
                                assert "afontreal" in installed_version
                                assert browser_tool.freetype_version() == record["spec"]["source"]
                                env["LD_LIBRARY_PATH"] = ""
                                native_parent = launch("native-installed")
                                assert library in Path(f"/proc/{native_parent['pid']}/maps").read_text()
                                assert json.loads(tool("status"))["active_pids"] == [native_parent["pid"]]
                                native_qt, _, _ = browser_helper("native-installed")
                                assert native_qt["qtGui"].strip().startswith("/usr/lib/")
                                for key in ("masks", "images"):
                                    assert native_qt[key] == normal_helper[key], (browser, "native-installed", key)
                                assert storage() == {"cookie": "fontreal=later-changed", "stored": "later-changed"}
                                quit()
                                assert (state.read_bytes(), user_js.read_bytes()) == saved_state
                                native_transitions.append(dict(phase="installed", provider=installed_version,
                                                               parent=native_parent, helper=native_qt))
                            finally:
                                if client:
                                    quit()
                                subprocess.run(["sudo", *map(str, native_command), "rollback", str(native_bundle)], check=True,
                                               text=True, capture_output=True)
                            assert browser_tool.freetype_version() == record["spec"]["source"]
                            restored_parent = launch("native-rolled-back")
                            assert library in Path(f"/proc/{restored_parent['pid']}/maps").read_text()
                            assert json.loads(tool("status"))["active_pids"] == [restored_parent["pid"]]
                            restored_qt, _, _ = browser_helper("native-rolled-back", fallback=True)
                            disabled_qt, _, _ = browser_helper("native-rolled-back-disabled", fallback=True, disabled=True)
                            assert restored_qt["qtGui"].strip().startswith("/usr/lib/")
                            for key in ("masks", "images"):
                                assert restored_qt[key] == disabled_qt[key]
                            assert restored_qt["images"] != normal_helper["images"]
                            assert storage() == {"cookie": "fontreal=later-changed", "stored": "later-changed"}
                            quit()
                            assert (state.read_bytes(), user_js.read_bytes()) == saved_state
                            native_transitions.append(dict(phase="rolled-back", parent=restored_parent, helper=restored_qt))
                            env["LD_LIBRARY_PATH"] = inherited_library_path
                        if browser == "firefox":
                            native_indexes = {Path(path): Path(path).read_bytes() for path in fixed
                                              if path.endswith(("/profiles.ini", "/installs.ini"))}
                            unused_prefs = (misleading_active / "prefs.js").read_bytes()
                            (misleading_active / "user.js").write_text("".join(
                                f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k, v in settings.items()))
                            try:
                                for path, content in native_indexes.items():
                                    text = content.decode().replace(str(profile), str(misleading_active))
                                    if path.name == "profiles.ini":
                                        text += f"\n[InstallPREVIOUS]\nDefault={profile}\nLocked=1\n"
                                    path.write_text(text)
                                alternate = launch("alternate-ordinary", expected_profile=misleading_active)
                                chrome("Services.prefs.savePrefFile(null); return true;")
                                before_retarget = state.read_bytes(), user_js.read_bytes(), owned()
                                protected_files = [state, user_js, home / ".local/bin" / browser,
                                                   home / ".local/share/applications" / f"{browser}.desktop",
                                                   profile / "prefs.js", misleading_active / "prefs.js",
                                                   misleading_active / "user.js", *native_indexes]
                                before_files = {path: path.read_bytes() for path in protected_files}
                                tool("enable", "Disable the previous profile")
                                assert (state.read_bytes(), user_js.read_bytes(), owned()) == before_retarget
                                assert {path: path.read_bytes() for path in protected_files} == before_files, [
                                    str(path) for path in protected_files if path.read_bytes() != before_files[path]]
                                assert alternate["pid"] != treated["pid"]
                                quit()
                            finally:
                                if client:
                                    quit()
                                for path, content in native_indexes.items():
                                    path.write_bytes(content)
                                for path in misleading_active.iterdir():
                                    if path.is_dir():
                                        import shutil
                                        shutil.rmtree(path)
                                    else:
                                        path.unlink()
                                (misleading_active / "prefs.js").write_bytes(unused_prefs)
                        with user_js.open("ab") as output:
                            output.write(b'user_pref("fixture.added.later", 71);\n')
                        tool("disable")
                        restored_user = (original_user or b"") + b'user_pref("fixture.added.later", 71);\n'
                        assert user_js.read_bytes() == restored_user
                        assert [line for line in prefs.read_text().splitlines(keepends=True) if browser_tool.OWNED_PREF.match(line)] == original_prefs
                        assert not state.exists()
                        # The ordinary command falls back to native PATH once the owned hook is removed.
                        log_path = directory / "restored-stock.log"
                        log = log_path.open("w")
                        child = subprocess.Popen(command([f"/usr/bin/{browser}", "--marionette", storage_url]), env=env, stdout=log, stderr=log)
                        for _ in range(300):
                            assert child.poll() is None, log_path.read_text()[-4000:]
                            if "Marionette\tINFO\tListening on port" in log_path.read_text():
                                break
                            time.sleep(.1)
                        client = masks.Marionette(port)
                        restored = identity()
                        assert Path(restored["profile"]) == profile
                        restored_owned = owned()
                        assert restored_owned == stock_owned, (restored_owned, stock_owned, original_prefs)
                        assert library not in Path(f"/proc/{restored['pid']}/maps").read_text()
                        assert storage() == {"cookie": "fontreal=later-changed", "stored": "later-changed"}
                        kept = chrome("return [Services.prefs.getIntPref('fixture.keep'), Services.prefs.getIntPref('fixture.added.later'), Services.prefs.getCharPref('layout.css.devPixelsPerPx'), Services.prefs.getIntPref('browser.startup.page')];")
                        assert kept == [53,71,"1",0], kept
                        quit()
                        before_repeat = tree(profile)
                        tool("disable")
                        assert tree(profile) == before_repeat
                        assert all(Path(path).exists() and masks.digest(Path(path)) == digest for path,digest in fixed.items()), "Unused profiles or native indexes changed"
                        results.append(dict(browser=browser, explicit=explicit, stock=stock, treated=treated,
                                            restored=restored, pixel_error=error, namespace=namespace,
                                            home_value=env["HOME"], original_prefs=original_prefs,
                                            scope=activation["scope"], actual_argv=actual_argv, xdg={key:value for key,value in actual_env.items() if key.startswith("XDG_")},
                                            browser_spawned_qt=dict(masks=len(inherited_helper["masks"]), images=len(inherited_helper["images"]),
                                                                    fontconfig=inherited_fc, inherited_environment=inherited_helper_env),
                                            older_qt_fallback=older_helper,
                                            native_transitions=native_transitions,
                                            kept=kept, storage="later-changed"))
                        print(f"PASS actual working profile {label}", flush=True)
                    finally:
                        if client:
                            try:
                                quit()
                            except Exception:
                                client.close()
                        if child and child.poll() is None:
                            # Cleanup is limited to this test-owned namespace child.
                            child.terminate()
                            child.wait(timeout=30)
                        if log:
                            log.close()
    finally:
        server.shutdown()
        server.server_close()
    return results


def diagnostic(root):
    home = root / "home"
    home.mkdir(parents=True)
    indexes = {}
    inherited_scope = None
    for browser in browser_tool.VERSIONS:
        profile = root / browser
        profile.mkdir()
        (profile / "prefs.js").write_text('user_pref("fixture.keep", 83);\n')
        indexes[browser], _ = index_fixture(profile, profile)
        with observations(home, [indexes[browser]]):
            main_call("enable", browser)
            if inherited_scope is None:
                state, _, _ = browser_tool.paths(browser)
                inherited_scope = json.loads(state.read_text())["scope"]
    env = dict(os.environ, PATH=str(home / ".local/bin") + os.pathsep + os.environ["PATH"],
               FONTREAL_FT_RENDERING="1", FONTREAL_FT_CONTRAST="mild", FONTREAL_FT_EXECUTABLE=":".join(inherited_scope))
    try:
        result = masks.run([sys.executable, ROOT / "tests/browser_masks_test.py", "--case", "all"], env=env)
        (OUT / "diagnostic.log").write_text(result.stdout)
        report = json.loads((masks.OUT / "all.json").read_text())
        assert len(report["browser"]["runs"]) == 18
        return dict(runs=18, normal_hooks=str(home / ".local/bin"), report=str(masks.OUT / "all.json"))
    finally:
        for browser in browser_tool.VERSIONS:
            with observations(home, [indexes[browser]]):
                main_call("disable", browser)


def docs():
    result = []
    for arguments in (["--self-test"], []):
        got = masks.run([sys.executable, ROOT / "tests/docs_test.py", *arguments])
        result.append(got.stdout.strip())
    page = (ROOT / "docs/experiments/browser-masks.md").read_text()
    for action in ("enable", "disable", "status"):
        assert f"tools/browser.py {action} firefox" in page, action
    assert "Floorp" in page and "restart" in page.lower()
    assert "preblend" in page.lower() and re.search(r"actual[- ]background", page.lower())
    for version in browser_tool.VERSIONS.values():
        assert all(part in page for part in version.split("@")), version
    help_text = masks.run([sys.executable, ROOT / "tools/browser.py", "--help"]).stdout
    assert "{enable,disable,status,run}" in help_text and "{firefox,floorp}" in help_text
    for command in re.findall(r"^python3 tools/browser\.py (.+)$", page, re.M):
        arguments = shlex.split(command)
        assert arguments[0] in ("enable", "disable", "status", "run")
        assert arguments[1] in browser_tool.VERSIONS
    assert "(docs/experiments/browser-masks.md)" in (ROOT / "README.md").read_text()
    for target in re.findall(r"\]\(([^)]+)\)", page):
        if ":" not in target and not target.startswith("#"):
            assert (ROOT / "docs/experiments" / target.split("#", 1)[0]).exists(), target
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", "discovery", "process", "desktop", "scope", "lifecycle", "diagnostic", "docs"), default="all")
    parser.add_argument("--native-helper", action="store_true", help="Check the actual forced raw Qt helper and a retained v1 activation.")
    parser.add_argument("--native-bundle", type=Path, help="In a marked disposable VM, continue an existing activation across guarded native install and rollback.")
    args = parser.parse_args()
    if args.native_helper:
        os.environ["FONTREAL_TEST_NATIVE_HELPER"] = "1"
    if args.native_bundle:
        assert args.native_helper and Path("/var/lib/fontreal-test-ready").is_file()
        subprocess.run(["systemd-detect-virt", "--vm"], check=True, capture_output=True)
        os.environ["FONTREAL_TEST_NATIVE_BUNDLE"] = str(args.native_bundle.resolve())
    OUT.mkdir(parents=True, exist_ok=True)
    masks.OUT.mkdir(parents=True, exist_ok=True)
    before = masks.protected()
    record_path = Path(masks.run([sys.executable, ROOT / "tools/build-freetype.py"]).stdout.splitlines()[-1])
    record = json.loads(record_path.read_text())
    if args.case in ("all", "lifecycle"):
        recipe.prepare()
    assert record_path.resolve().is_relative_to((ROOT / "build").resolve())
    assert OUT.is_relative_to((ROOT / "results").resolve())
    results = {}
    with tempfile.TemporaryDirectory(prefix="browser-delivery-", dir=masks.WORK) as temporary:
        root = Path(temporary)
        for case, check in (("discovery", lambda: discovery(root / "discovery")),
                            ("process", lambda: process_observation(root / "process")),
                            ("desktop", lambda: desktop_checks(root / "desktop")),
                            ("scope", lambda: process_scope(record)),
                            ("lifecycle", lambda: lifecycle(root / "lifecycle", record)),
                            ("diagnostic", lambda: diagnostic(root / "diagnostic")),
                            ("docs", docs)):
            if args.case in ("all", case):
                results[case] = check()
                print(f"PASS working-profile {case}", flush=True)
    assert masks.protected() == before, "Protected host configuration changed"
    (OUT / f"{args.case}.json").write_text(json.dumps(dict(build=str(record_path), results=results, protected=before), indent=2) + "\n")


if __name__ == "__main__":
    main()
