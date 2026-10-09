#!/usr/bin/env python3
"""Fail closed on registry errors; detect immutable tags without exposing credentials."""
import base64
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

image = os.environ['IMAGE']
path = image.removeprefix('ghcr.io/')
creds = base64.b64encode(f'{os.environ["GITHUB_ACTOR"]}:{os.environ["GHCR_TOKEN"]}'.encode()).decode()
url = 'https://ghcr.io/token?' + urllib.parse.urlencode({'service':'ghcr.io','scope':f'repository:{path}:pull'})
req=urllib.request.Request(url,headers={'Authorization':f'Basic {creds}'})
with urllib.request.urlopen(req,timeout=60) as response:
    token=json.load(response)['token']
headers={'Authorization':f'Bearer {token}', 'Accept': ', '.join([
    'application/vnd.oci.image.index.v1+json', 'application/vnd.oci.image.manifest.v1+json',
    'application/vnd.docker.distribution.manifest.list.v2+json', 'application/vnd.docker.distribution.manifest.v2+json'])}
digests=[]
for ref in os.environ['TAGS'].split(','):
    tag=ref.rsplit(':',1)[1]
    req=urllib.request.Request(f'https://ghcr.io/v2/{path}/manifests/{tag}',headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=60) as response:
            digest=response.headers['Docker-Content-Digest']
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            continue
        raise SystemExit(f'Registry returned {exc.code} for {ref}; refusing to treat this as a missing tag.')
    subprocess.run(['docker','pull','--platform','linux/amd64',f'{image}@{digest}'],check=True)
    actual=subprocess.check_output(['docker','image','inspect',f'{image}@{digest}', '--format',
          '{{ index .Config.Labels "io.caddy-images.inputs-sha256" }}'],text=True).strip()
    if actual != os.environ['FINGERPRINT']:
        raise SystemExit(f'{ref} already exists with different inputs. Increment build_revision; immutable tags are never overwritten.')
    digests.append(digest)
if len(set(digests)) > 1:
    raise SystemExit('Release tags disagree; refusing to replace either existing tag.')
with open(os.environ['GITHUB_OUTPUT'],'a') as out:
    out.write(f'exists={str(bool(digests)).lower()}\n')
    out.write(f'digest={digests[0] if digests else ""}\n')
