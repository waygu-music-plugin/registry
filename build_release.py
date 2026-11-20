#!/usr/bin/env python3
"""Build the six plugin archives and the signed catalog entry on Linux."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import zipfile

ENTRIES = {
    "songloft": ["songloft"],
    "subsonic": ["navidrome", "jellyfin", "gonic", "subsonic"],
    "netease": ["netease"],
    "qqmusic": ["qqmusic"],
}
NAMES = {
    "songloft": "Songloft",
    "subsonic": "Subsonic",
    "netease": "网易云音乐",
    "qqmusic": "QQ 音乐",
}
RUNTIMES = {
    "windows": ["Windows 10 or 11"],
    "darwin": ["macOS 13 or later"],
    "linux": ["glibc", "GTK 3", "X11 or Wayland session"],
}
PROTOCOL = 1


def write_json(output, obj):
    output.write_text(json.dumps(obj, separators=(",", ":")) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def publisher_key(path):
    key = subprocess.check_output(["openssl", "pkey", "-in", path, "-pubout", "-outform", "DER"])
    prefix = bytes.fromhex("302a300506032b6570032100")
    if not key.startswith(prefix) or len(key) != len(prefix) + 32:
        raise ValueError("publisher key must be Ed25519")
    return base64.b64encode(key[len(prefix):]).decode("ascii")


def build(source, tag, key, out):
    env = dict(os.environ, GOWORK="off", CGO_ENABLED="0")
    module = subprocess.check_output(["go", "list", "-m"], cwd=source, env=env, text=True).strip()
    owner_repo = module.removeprefix("github.com/")
    if not module.startswith("github.com/") or not re.fullmatch(r"[\w.-]+/[\w.-]+", owner_repo):
        raise ValueError("expected a GitHub Go module")
    name = owner_repo.split("/")[1]
    if name not in ENTRIES or not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", tag):
        raise ValueError("expected a supported plugin and a version tag")
    public_key = publisher_key(key)
    origin = f"https://github.com/{owner_repo}/releases/download/{tag}"
    out.mkdir(parents=True, exist_ok=False)
    artifacts = []
    with TemporaryDirectory(prefix="wagyu-plugin-build-") as temporary:
        work = Path(temporary)
        for goos in RUNTIMES:
            for goarch in ("amd64", "arm64"):
                exe = f"{name}-plugin" + (".exe" if goos == "windows" else "")
                binary = work / exe
                linker = ["-ldflags=-H=windowsgui"] if goos == "windows" else []
                subprocess.run(["go", "build", "-mod=readonly", "-trimpath", *linker, "-o", binary,
                                f"./cmd/{name}-plugin"], cwd=source,
                               env=dict(env, GOOS=goos, GOARCH=goarch), check=True)
                archive = out / f"{name}-{tag}-{goos}-{goarch}.zip"
                with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as files:
                    files.write(binary, exe)
                    files.write(source / "LICENSE", "LICENSE")
                artifacts.append({"OS": goos, "Arch": goarch, "URL": f"{origin}/{archive.name}", "Entry": exe,
                                  "Size": archive.stat().st_size, "SHA256": digest(archive),
                                  "EntrySHA256": digest(binary), "Runtime": RUNTIMES[goos]})
        release = {"Format": 1, "Protocol": PROTOCOL, "Package": name, "Version": tag[1:],
                   "Name": NAMES[name], "Entries": ENTRIES[name], "Artifacts": artifacts}
        payload = work / "manifest.json"
        raw = json.dumps(release, separators=(",", ":")).encode()
        payload.write_bytes(raw)
        signature = subprocess.check_output(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", key, "-in", payload])
        encoded = json.dumps(base64.b64encode(signature).decode("ascii")).encode()
        (out / "manifest.json").write_bytes(b'{"Manifest":' + raw + b',"Signature":' + encoded + b'}\n')
        write_json(out / "catalog.json", {"Format": 1, "Packages": [
            {"Package": name, "Name": NAMES[name], "Manifest": f"{origin}/manifest.json", "PublicKey": public_key}]})
        (out / "SHA256SUMS").write_text("".join(f"{a['SHA256']}  {Path(a['URL']).name}\n" for a in artifacts),
                                        encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.source.resolve(), args.tag, args.key.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
