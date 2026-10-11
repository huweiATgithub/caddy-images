"""Resolve stable upstream tags to a validated, frozen release configuration."""
import json
import re
import urllib.request

VERSION = r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)'
FIELDS = {'caddy_version', 'plugin_module', 'plugin_revision', 'build_revision',
          'platform', 'builder_image', 'runtime_image'}


def validate(cfg):
    if set(cfg) != FIELDS:
        raise ValueError('Unexpected or missing release configuration fields')
    if not re.fullmatch(VERSION, cfg['caddy_version']):
        raise ValueError('Caddy version must be a stable X.Y.Z version')
    if cfg['plugin_module'] != 'github.com/techknowlogick/certmagic-s3':
        raise ValueError('Unexpected plugin module')
    if not re.fullmatch(r'[0-9a-f]{40}', cfg['plugin_revision']):
        raise ValueError('Plugin must be pinned to a full commit')
    if type(cfg['build_revision']) is not int or not 1 <= cfg['build_revision'] <= 999999:
        raise ValueError('Build revision must be an integer between 1 and 999999')
    if cfg['platform'] != 'linux/amd64':
        raise ValueError('Only linux/amd64 is supported')
    for field, suffix in [('builder_image', 'builder-alpine'), ('runtime_image', 'alpine')]:
        prefix = f"caddy:{cfg['caddy_version']}-{suffix}@sha256:"
        if not re.fullmatch(re.escape(prefix) + r'[0-9a-f]{64}', cfg[field]):
            raise ValueError(f'{field} must pin the matching official Caddy image')
    return cfg


def read_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'caddy-images-release'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def resolve(cfg, upstream_tag='', revision='', fetch=read_json):
    cfg = dict(validate(cfg))
    if upstream_tag and not re.fullmatch('v' + VERSION, upstream_tag):
        raise ValueError('upstream_tag must be a stable upstream tag such as v2.11.7')
    if revision and not re.fullmatch(r'[1-9][0-9]{0,5}', revision):
        raise ValueError('build_revision must be an integer between 1 and 999999')
    # Validate all untrusted input before making any network requests.
    version = upstream_tag[1:] if upstream_tag else cfg['caddy_version']
    release = fetch(f'https://api.github.com/repos/caddyserver/caddy/releases/tags/v{version}')
    if release.get('tag_name') != f'v{version}' or release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('An official stable Caddy release is required')
    if version != cfg['caddy_version']:
        cfg['caddy_version'] = version
        cfg['build_revision'] = 1
        for field, suffix in [('builder_image', 'builder-alpine'), ('runtime_image', 'alpine')]:
            tag = f'{version}-{suffix}'
            data = fetch(f'https://hub.docker.com/v2/repositories/library/caddy/tags/{tag}')
            images = [entry for entry in data.get('images', [])
                      if entry.get('os') == 'linux' and entry.get('architecture') == 'amd64'
                      and entry.get('status') == 'active']
            if data.get('name') != tag or len(images) != 1:
                raise ValueError(f'Official image {tag} has no unique active linux/amd64 manifest')
            digest = images[0]['digest']
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                raise ValueError('Invalid official image digest')
            cfg[field] = f'caddy:{tag}@{digest}'
    if revision:
        cfg['build_revision'] = int(revision)
    return validate(cfg)
