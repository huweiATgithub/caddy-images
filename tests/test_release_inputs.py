"""Offline resolution, validation and retry identity checks."""
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_inputs import resolve, validate

ROOT = Path(__file__).resolve().parents[1]

class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / 'images/caddy-s3/image.json').read_text())
        self.release = {'tag_name': 'v9.8.7', 'draft': False, 'prerelease': False}
        self.image = {'os': 'linux', 'architecture': 'amd64', 'status': 'active', 'digest': 'sha256:' + 'a' * 64}
        self.fetch = Mock(side_effect=[self.release,
            {'name': '9.8.7-builder-alpine', 'images': [self.image]},
            {'name': '9.8.7-alpine', 'images': [self.image]}])

    def test_new_version_resolves_official_platform_and_preserves_plugin(self):
        cfg = resolve(self.cfg, 'v9.8.7', fetch=self.fetch)
        self.assertEqual(cfg['caddy_version'], '9.8.7')
        self.assertEqual(cfg['build_revision'], 1)
        self.assertEqual(cfg['plugin_revision'], self.cfg['plugin_revision'])
        self.assertEqual(cfg['builder_image'], 'caddy:9.8.7-builder-alpine@sha256:' + 'a' * 64)
        self.assertEqual(self.fetch.call_count, 3)

    def test_explicit_revision(self):
        self.assertEqual(resolve(self.cfg, 'v9.8.7', '2', self.fetch)['build_revision'], 2)

    def test_default_and_same_tag_keep_frozen_bases(self):
        release = dict(self.release, tag_name='v' + self.cfg['caddy_version'])
        for tag in ['', release['tag_name']]:
            fetch = Mock(return_value=release)
            self.assertEqual(resolve(self.cfg, tag, fetch=fetch), self.cfg)
            self.assertEqual(fetch.call_count, 1)

    def test_reject_tag_injection_before_network(self):
        for value in ['2.11.7', 'v2.11.7\nEVIL=1', 'v2.11.7;id', '$(id)', '../main', 'v2.11.7-rc1', 'v02.11.7', 'v٢.١١.٧', ' v2.11.7', 'v2.11.7@sha256:a']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve(self.cfg, value, fetch=self.fetch)
        self.fetch.assert_not_called()

    def test_reject_revision_injection_before_network(self):
        for value in ['0', '-1', '1.0', '01', 'true', '1\nTAG=bad', '1000000', '$(id)']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve(self.cfg, 'v9.8.7', value, self.fetch)
        self.fetch.assert_not_called()

    def test_reject_missing_draft_prerelease_or_mismatched_release(self):
        for release in [{}, dict(self.release, draft=True), dict(self.release, prerelease=True), dict(self.release, tag_name='v9.8.6')]:
            with self.subTest(release=release), self.assertRaises(ValueError):
                resolve(self.cfg, 'v9.8.7', fetch=Mock(return_value=release))

    def test_reject_missing_ambiguous_inactive_wrong_arch_and_invalid_digest(self):
        cases = [[], [self.image, self.image], [dict(self.image, status='inactive')],
                 [dict(self.image, architecture='arm64')], [dict(self.image, digest='sha256:bad')]]
        for images in cases:
            with self.subTest(images=images), self.assertRaises(ValueError):
                resolve(self.cfg, 'v9.8.7', fetch=Mock(side_effect=[self.release, {'name': '9.8.7-builder-alpine', 'images': images}]))

    def test_reject_extra_fields_and_wrong_official_variant(self):
        for cfg in [dict(self.cfg, evil='a\nb=c'), dict(self.cfg, runtime_image=self.cfg['builder_image'])]:
            with self.assertRaises(ValueError):
                validate(cfg)
