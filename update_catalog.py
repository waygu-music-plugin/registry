#!/usr/bin/env python3
"""Update the official directory after verifying published plugin releases."""

import base64
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from build_release import ENTRIES, PROTOCOL, RUNTIMES, write_json

ORG = "waygu-music-plugin"
TARGETS = {(os, arch) for os in RUNTIMES for arch in ("amd64", "arm64")}


def update(root):
    public = (root / "publisher-key.txt").read_text().strip()
    key = base64.b64decode(public, validate=True)
    entries = []
    with TemporaryDirectory(prefix="wagyu-catalog-") as tmp:
        work = Path(tmp)
        pubfile = work / "key.der"
        pubfile.write_bytes(bytes.fromhex("302a300506032b6570032100") + key)
        for pack in ENTRIES:
            repo = f"{ORG}/{pack}"
            release = json.loads(subprocess.check_output(["gh", "api", f"repos/{repo}/releases/latest"]))
            tag = release["tag_name"]
            if release["draft"] or release["prerelease"] or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
                raise ValueError(f"{repo} {tag} is not a stable plugin release")
            folder = work / pack
            subprocess.run(["gh", "release", "download", tag, "-R", repo,
                            "--pattern", "manifest.json", "-D", folder], check=True)
            raw, sig = (folder / "manifest.json").read_bytes().removeprefix(b'{"Manifest":').rsplit(b',"Signature":', 1)
            message, signature = folder / "payload", folder / "signature"
            message.write_bytes(raw)
            signature.write_bytes(base64.b64decode(json.loads(sig.strip()[:-1]), validate=True))
            subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-keyform", "DER", "-rawin",
                            "-inkey", pubfile, "-in", message, "-sigfile", signature], check=True)
            manifest = json.loads(raw)
            if (manifest["Format"], manifest["Protocol"], manifest["Package"], manifest["Version"],
                manifest["Entries"]) != (1, PROTOCOL, pack, tag[1:], ENTRIES[pack]):
                raise ValueError(f"unexpected release manifest for {repo}")
            artifacts = manifest["Artifacts"]
            if len(artifacts) != len(TARGETS) or {(a["OS"], a["Arch"]) for a in artifacts} != TARGETS:
                raise ValueError(f"{repo} does not have the six required targets")
            assets = {a["name"]: a for a in release["assets"] if a["state"] == "uploaded"}
            url = f"https://github.com/{repo}/releases/download/{tag}/"
            for item in artifacts:
                name = Path(urlparse(item["URL"]).path).name
                asset = assets[name]
                digest = asset.get("digest")
                if (item["URL"] != url + name or asset["size"] != item["Size"] or
                        (digest and digest != "sha256:" + item["SHA256"])):
                    raise ValueError(f"incorrect GitHub release asset {name}")
            entries.append({"Package": pack, "Manifest": url + "manifest.json", "PublicKey": public})
    write_json(root / "catalog.json", {"Format": 1, "Packages": entries})


if __name__ == "__main__":
    update(Path(__file__).resolve().parent)
