"""Fast, dependency-free unit checks for release identity and input validation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('__pycache__', '.git'))
        self.version = json.loads((self.root / 'images/caddy-s3/image.json').read_text())['caddy_version']
        self.update(build_revision=1)

    def metadata(self, success=True):
        result = subprocess.run(['python3', 'scripts/metadata.py'], cwd=self.root,
            env={**os.environ, 'GITHUB_REPOSITORY_OWNER':'MixedCaseOwner', 'GITHUB_OUTPUT':''},
            text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return dict(line.split('=', 1) for line in result.stdout.splitlines()) if success else {}

    def update(self, **changes):
        p = self.root / 'images/caddy-s3/image.json'
        cfg = json.loads(p.read_text()); cfg.update(changes); p.write_text(json.dumps(cfg))

    def test_initial_tags_and_owner(self):
        m = self.metadata()
        self.assertEqual(m['tags'], f'ghcr.io/mixedcaseowner/caddy-s3:{self.version}-r1,ghcr.io/mixedcaseowner/caddy-s3:{self.version}')

    def test_later_revision_preserves_bare_tag(self):
        self.update(build_revision=2)
        self.assertEqual(self.metadata()['tags'], f'ghcr.io/mixedcaseowner/caddy-s3:{self.version}-r2')

    def test_fingerprint_tracks_inputs_not_readme(self):
        a = self.metadata()['fingerprint']
        (self.root / 'README.md').write_text('Changed documentation')
        self.assertEqual(a, self.metadata()['fingerprint'])
        with (self.root / 'images/caddy-s3/Dockerfile').open('a') as out:
            out.write('\n# Input changed\n')
        self.assertNotEqual(a, self.metadata()['fingerprint'])

    def test_plugin_must_be_full_commit(self):
        self.update(plugin_revision='main'); self.metadata(success=False)

    def test_revision_must_be_positive_integer(self):
        self.update(build_revision=True); self.metadata(success=False)

    def test_base_version_must_match_caddy(self):
        self.update(caddy_version='999.0.0'); self.metadata(success=False)

if __name__ == '__main__':
    unittest.main()
