#!/usr/bin/env python3
"""Validate the manifest and emit workflow outputs without executing its values."""
import hashlib
import json
import os
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
cfg = json.loads((root / "images/caddy-s3/image.json").read_text())
assert re.fullmatch(r"\d+\.\d+\.\d+", cfg["caddy_version"])
assert cfg["plugin_module"] == "github.com/techknowlogick/certmagic-s3"
assert re.fullmatch(r"[0-9a-f]{40}", cfg["plugin_revision"])
assert type(cfg["build_revision"]) is int and cfg["build_revision"] >= 1
assert cfg["platform"] == "linux/amd64"
for field in ["builder_image", "runtime_image"]:
    assert re.fullmatch(r"caddy:[\w.-]+@sha256:[0-9a-f]{64}", cfg[field])
    assert cfg[field].startswith(f'caddy:{cfg["caddy_version"]}-')
# A release is identified by all build and verification inputs, not documentation.
files = [*root.glob("images/caddy-s3/*"), *root.glob("scripts/*"),
         *root.glob("tests/*"), root / ".github/workflows/caddy-s3.yml"]
hash_ = hashlib.sha256()
for path in sorted(p for p in files if p.is_file()):
    hash_.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "OWNER").lower()
image = f"ghcr.io/{owner}/caddy-s3"
release = f'{cfg["caddy_version"]}-r{cfg["build_revision"]}'
# The requested bare version belongs permanently to r1; later revisions use -rN.
tags = [f"{image}:{release}"]
if cfg["build_revision"] == 1:
    tags.append(f'{image}:{cfg["caddy_version"]}')
outputs = {**cfg, "image": image, "release": release, "fingerprint": hash_.hexdigest(),
           "tags": ",".join(tags)}
text = "".join(f"{key}={value}\n" for key, value in outputs.items())
print(text, end="")
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as out:
        out.write(text)
