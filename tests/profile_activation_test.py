#!/usr/bin/env python3
"""Check the persistent choice separately from integration activation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from browser import rendering_profile


def main():
    command = ["sh", str(ROOT / "packaging/session/fontreal-session")]
    with tempfile.TemporaryDirectory(prefix="fontreal-profile-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "custom"),
                   FONTREAL_PROFILE="o", FONTREAL_RENDERING="1")
        fallback = root / "home/.config/fontreal/profile"
        fallback.parent.mkdir(parents=True)
        fallback.write_text("o\n")
        preference = root / "custom/fontreal/profile"
        enabled = preference.with_name("enabled")
        enabled.parent.mkdir(parents=True)
        enabled.write_text("independent native marker\n")
        browser = preference.parent / "browsers/firefox.json"
        browser.parent.mkdir()
        browser.write_text('{"enabled":true,"fixture":"unchanged"}\n')
        registry = preference.parent / "chromium/apps.json"
        registry.parent.mkdir()
        registry.write_text('{"apps":{"teams":{},"bitwarden":{}}}\n')
        owned = {p: p.read_bytes() for p in (fallback, enabled, browser, registry)}

        def call(*args, valid=True):
            result = subprocess.run([*command, *args], env=env, text=True, capture_output=True)
            assert (result.returncode == 0) == valid, (args, result.stdout, result.stderr)
            assert all(p.read_bytes() == value for p, value in owned.items())
            return result.stdout

        assert call("profile") == "o\n" and not preference.exists()
        for value in ("k3", "o"):
            call("profile", value)
            assert preference.read_bytes() == (value + "\n").encode()
            assert preference.stat().st_mode & 0o777 == 0o600
            assert call("profile") == value + "\n"
            observed = subprocess.check_output([sys.executable, "-B", "-c",
                "import sys;sys.path.insert(0,sys.argv[1]);from browser import rendering_profile;print(rendering_profile())",
                str(ROOT / "tools")], env=env, text=True)
            assert observed == value + "\n"
        for args in (("profile", "K3"), ("profile", "unsupported"), ("profile", "k3", "extra"),
                     ("enable", "extra"), ("disable", "extra"), ("status", "extra")):
            before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            call(*args, valid=False)
            assert {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
        call("profile", "k3")
        status = call("status")
        assert "Next-login profile: k3" in status and "profile=o" in status
        assert env["FONTREAL_PROFILE"] == "o" and env["FONTREAL_RENDERING"] == "1"
        for value in (b"K3\n", b"o\n\nk3", b"o \n", b"\xff", b"k3\0", b"k3\n\n"):
            preference.write_bytes(value)
            assert call("profile") == "o\n" and preference.read_bytes() == value
        preference.write_text("k3\n")
        env.pop("XDG_CONFIG_HOME")
        assert call("profile") == "o\n" and preference.read_text() == "k3\n"
        owned.pop(fallback)
        call("profile", "k3")
        assert fallback.read_text() == "k3\n" and preference.read_text() == "k3\n"
    print("PASS persistent profile default, exact values, roots, permissions, status, and independent activation")


if __name__ == "__main__":
    main()
