#!/usr/bin/env python3
"""Reject machine-specific references in tracked public documentation."""
import argparse
import html
import ipaddress
import json
from pathlib import Path
import re
import socket
import struct
import subprocess
import urllib.parse
from xml.dom import Node, minidom
from xml.parsers.expat import ExpatError
import zlib

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "personal or mounted filesystem path": r"(?<![\w/.-])/(?:home|Users|storage|mnt|media|run/media|var/home)(?:/|\b)",
    "home-relative path": r"(?<![\w/])~(?:[\w.-]+)?/",
    "Windows filesystem path": r"\b[A-Z]:[\\/]|\\\\[^\s\\]+\\",
    "local file URL": r"\bfile:[/\\]",
    "private work reference": r"(?<![\w])\.(?:agent|codex|repowise)/",
    "machine-specific prose": r"\b(?:this machine|this workspace|development machine|my workstation)\b",
    "absolute documentation link": r"\]\(<?/(?!/)",
}
PATTERNS = {name: re.compile(pattern, re.I) for name, pattern in RULES.items()}
LOCAL_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"))


def local_link(url):
    try:
        host = urllib.parse.urlsplit(url).hostname
    except ValueError:
        return False
    if not host:
        return False
    host = host.rstrip(").,;").lower()
    if host.endswith((".local", ".localhost", ".localdomain")) or ("." not in host and ":" not in host):
        return True
    try:
        address = ipaddress.ip_address(host if ":" in host else socket.inet_aton(host))
    except (ValueError, OSError):
        return False
    if address.version == 6 and address.ipv4_mapped:
        address = address.ipv4_mapped
    return (address.is_loopback or address.is_link_local or address.is_unspecified or
            any(address in network for network in LOCAL_NETWORKS))


def metadata_values(text):
    if not text.lstrip().startswith("<"):
        return [text]
    try:
        document = minidom.parseString(text)
    except ExpatError:
        return [text]
    values, pending = [], [document]
    while pending:
        node = pending.pop()
        values.append(node.nodeValue or "")
        if node.attributes:
            values.extend(attribute.value for attribute in node.attributes.values())
        for name in ("publicId", "systemId", "internalSubset"):
            values.append(getattr(node, name, None) or "")
        text_parts = []
        for child in node.childNodes:
            if child.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
                if node.namespaceURI != "http://www.w3.org/2000/svg" or node.localName not in ("text", "tspan", "textPath"):
                    text_parts.append(child.data)
            else:
                if text_parts:
                    values.append("".join(text_parts))
                    text_parts.clear()
                pending.append(child)
        if text_parts:
            values.append("".join(text_parts))
    document.unlink()
    return values


def issues(text, metadata=False):
    normalized = urllib.parse.unquote(html.unescape(text))
    found = [name for name, pattern in PATTERNS.items() if pattern.search(normalized)]
    if any(local_link(url) for url in re.findall(r"https?://[^\s<>\"'`]+", normalized, re.I)):
        found.append("local network link")
    values = [urllib.parse.unquote(html.unescape(value)) for value in metadata_values(text)] if metadata else []
    if any(value.startswith(("/", "~")) or
           re.search(r"(?<![\w/.-])/(?!/)[\w.~$-]+(?:/[\w.~$-]+)*", value) for value in values):
        found.append("absolute metadata location")
    return found


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def public_document(path):
    suffix = path.suffix.lower()
    return (suffix in (".md", ".rst", ".png") or path.parts[0] == "docs") and suffix in (
        ".md", ".rst", ".txt", ".json", ".png", ".svg", ".html", ".htm", ".yaml", ".yml", ".csv")


def png_text(data):
    assert data.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG signature"
    position = 8
    while position < len(data):
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position+4:position+8]
        payload = data[position+8:position+8+length]
        assert len(payload) == length and position+12+length <= len(data), "Invalid PNG chunk"
        position += length + 12
        if kind == b"tEXt":
            for value in payload.split(b"\0", 1):
                yield value.decode("latin1")
        elif kind == b"zTXt":
            keyword, rest = payload.split(b"\0", 1)
            assert rest[0] == 0, "Unsupported PNG text compression"
            yield keyword.decode("latin1")
            yield zlib.decompress(rest[1:]).decode("latin1")
        elif kind == b"iTXt":
            keyword, rest = payload.split(b"\0", 1)
            compressed, method = rest[:2]
            _, translated, text = rest[2:].split(b"\0", 2)
            assert method == 0 and compressed in (0, 1), "Unsupported PNG text compression"
            yield keyword.decode("latin1")
            yield translated.decode()
            yield (zlib.decompress(text) if compressed else text).decode()
        if kind == b"IEND":
            return
    raise AssertionError("Missing PNG end chunk")


def self_test():
    for bad in ("/home/alice/project", "/storage/builds/app", "/mnt/disk/app", "C:\\Users\\alice",
                "file:///opt/project", "http://localhost:8000/page", "http://192.168.1.2/page",
                ".agent/test-results/check.md", "[guide](/opt/private.md)", "this machine"):
        assert issues(bad), bad
    for good in ("", "docs/guide.md", "${BUILD_ROOT}/output", "/etc/fonts/fonts.conf",
                 "https://example.org/home/guide", "[guide](docs/guide.md)"):
        assert not issues(good), good
    assert issues("/opt/private/lib.so", metadata=True)
    assert issues("source: /opt/alice/capture.png", metadata=True)
    assert issues('source,"/opt/alice/capture.png"', metadata=True)
    assert issues("[capture](~alice/private-captures/frame.png)")
    assert issues("[capture](~/private-captures/frame.png)")
    assert not issues("source: https://example.org/fonts/face.ttf", metadata=True)
    xmp = '<rdf:RDF xmlns:rdf="https://example.org/rdf"><rdf:Description>Portable capture</rdf:Description></rdf:RDF>'
    assert not issues(xmp, metadata=True)
    assert issues('<rdf:Description source="/opt/alice/capture.png"/>', metadata=True)
    assert issues('</opt/alice/capture.png>', metadata=True)
    assert issues('<rdf:RDF xmlns:rdf="/opt/alice/schema"><rdf:Description/></rdf:RDF>', metadata=True)
    assert issues('<root><child/>' + ' '*17000 + '/opt/alice/capture.png</root>', metadata=True)
    assert issues('<root><!-- source: /opt/alice/capture.png --></root>', metadata=True)
    assert issues('<root><?source /opt/alice/capture.png?></root>', metadata=True)
    assert issues('<!DOCTYPE root SYSTEM "/opt/alice/source.dtd"><root/>', metadata=True)
    assert not issues('<root>https://example.org<![CDATA[/fonts/face.ttf]]></root>', metadata=True)
    assert issues('<root><![CDATA[/op]]>t/alice/capture.png</root>', metadata=True)
    encoded = json.loads('{"nested":["ok","ok",{"path":"\\u002fhome\\u002falice"}]}')
    assert any(issues(s, metadata=True) for s in strings(encoded))
    assert issues("file%3A%2F%2F%2Fopt%2Fprivate")
    for value in ('[capture](http://192.168.1.2)', '<a href="http://localhost">capture</a>',
                  '`http://127.0.0.1`', 'http://desktop.local:8000/capture.png',
                  'https://desktop/capture', 'http://localhost./capture', 'http://[fd00::1]/capture',
                  'http://127.1/capture', 'http://[::ffff:192.168.1.2]/capture'):
        assert issues(value), value
    assert public_document(Path("images/example.png"))
    assert public_document(Path("LICENSES/badge.png"))
    assert public_document(Path("docs/metadata.json"))
    assert not public_document(Path("src/main.cpp"))
    assert not issues('https://192.0.2.1/capture')
    assert not issues('<svg xmlns="http://www.w3.org/2000/svg"><text>/</text></svg>', metadata=True)
    assert issues('<svg xmlns="http://www.w3.org/2000/svg" source="/opt/alice/capture.svg"/>', metadata=True)
    end = struct.pack(">I", 0) + b"IEND" + bytes(4)
    for kind, payload in (
        (b"tEXt", b"Comment\0/opt/private/capture.png"),
        (b"zTXt", b"Comment\0\0" + zlib.compress(b"/opt/private/capture.png")),
        (b"iTXt", b"Comment\0\0\0\0\0/opt/private/capture.png"),
        (b"iTXt", b"Comment\0\1\0\0\0" + zlib.compress(b"/opt/private/capture.png"))):
        chunk = struct.pack(">I", len(payload)) + kind + payload + bytes(4)
        assert any(issues(s, metadata=True) for s in png_text(b"\x89PNG\r\n\x1a\n" + chunk + end)), kind
    print("Documentation guard self-check passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    errors, checked = [], 0
    for name in names:
        path = Path(name)
        if not name or not public_document(path):
            continue
        content = ROOT / path
        if path.suffix.lower() == ".png":
            values = png_text(content.read_bytes())
        elif path.suffix.lower() == ".json":
            values = strings(json.loads(content.read_text()))
        else:
            values = [content.read_text()]
        checked += 1
        for value in values:
            for reason in issues(value, metadata=path.suffix.lower() in (".json", ".png", ".yaml", ".yml", ".csv", ".svg")):
                errors.append(f"{name}: {reason}")
    if errors:
        raise SystemExit("\n".join(dict.fromkeys(errors)))
    print(f"Public documentation check passed ({checked} tracked files)")


if __name__ == "__main__":
    main()
