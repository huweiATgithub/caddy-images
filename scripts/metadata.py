#!/usr/bin/env python3
"""Validate effective inputs and emit safe workflow outputs; never execute values."""
import hashlib
import json
import os
from pathlib import Path
import re
from release_inputs import resolve, validate

root = Path(__file__).resolve().parents[1]
manifest = root / 'images/caddy-s3/image.json'
cfg = validate(json.loads(os.environ.get('RELEASE_CONFIG') or manifest.read_text()))
if os.environ.get('RESOLVE_RELEASE') == 'true':
    cfg = resolve(cfg, os.environ.get('UPSTREAM_TAG', ''), os.environ.get('BUILD_REVISION', ''))
canonical = json.dumps(cfg, sort_keys=True, separators=(',', ':'))
# Hash effective configuration rather than defaults: push and manual release agree.
files = [*root.glob('images/caddy-s3/*'), *root.glob('scripts/*'),
         *root.glob('tests/*'), root / '.github/workflows/caddy-s3.yml']
hash_ = hashlib.sha256()
for path in sorted(p for p in files if p.is_file()):
    data = canonical.encode() if path == manifest else path.read_bytes()
    hash_.update(str(path.relative_to(root)).encode() + b'\0' + data + b'\0')
owner = os.environ.get('GITHUB_REPOSITORY_OWNER', 'OWNER').lower()
if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', owner):
    raise ValueError('Invalid repository owner')
image = f'ghcr.io/{owner}/caddy-s3'
release = f'{cfg["caddy_version"]}-r{cfg["build_revision"]}'
tags = [f'{image}:{release}']
if cfg['build_revision'] == 1:
    tags.append(f'{image}:{cfg["caddy_version"]}')
outputs = {**cfg, 'image': image, 'release': release, 'fingerprint': hash_.hexdigest(),
           'tags': ','.join(tags), 'release_config': canonical}
text = ''.join(f'{key}={value}\n' for key, value in outputs.items())
print(text, end='')
if os.environ.get('GITHUB_OUTPUT'):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
        out.write(text)
if os.environ.get('RESOLVE_RELEASE') == 'true':
    (root / 'resolved-image.json').write_text(json.dumps(cfg, indent=2) + '\n')
