"""Exercise registry error handling and immutable release retry behavior offline."""
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check-release.py'
DIGEST = 'sha256:' + 'a' * 64

class Response(io.BytesIO):
    def __init__(self, body=b'', digest=DIGEST):
        super().__init__(body)
        self.headers = {'Docker-Content-Digest': digest}

class ImmutableReleaseTests(unittest.TestCase):
    def run_check(self, replies, fingerprint='expected', error=None):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            env = {'IMAGE': 'ghcr.io/owner/caddy-s3', 'GITHUB_ACTOR': 'owner', 'GHCR_TOKEN': 'test-only',
                   'TAGS': 'ghcr.io/owner/caddy-s3:2.11.7-r1,ghcr.io/owner/caddy-s3:2.11.7',
                   'FINGERPRINT': 'expected', 'GITHUB_OUTPUT': str(output)}
            with patch.dict(os.environ, env), patch('urllib.request.urlopen', side_effect=[Response(json.dumps({'token': 'test-only'}).encode()), *replies]), patch('subprocess.run') as pull, patch('subprocess.check_output', return_value=fingerprint):
                if error:
                    with self.assertRaisesRegex(SystemExit, error):
                        runpy.run_path(str(SCRIPT))
                    self.assertFalse(output.exists())
                    return
                runpy.run_path(str(SCRIPT))
                return output.read_text(), pull.call_count

    def missing(self):
        return HTTPError('https://ghcr.io/test', 404, 'not found', {}, None)

    def test_missing_tags_allow_first_release(self):
        self.assertEqual(self.run_check([self.missing(), self.missing()]), ('exists=false\ndigest=\n', 0))

    def test_matching_release_reuses_digest(self):
        self.assertEqual(self.run_check([Response(), Response()]), (f'exists=true\ndigest={DIGEST}\n', 2))

    def test_partial_promotion_reuses_surviving_tag(self):
        for replies in [[Response(), self.missing()], [self.missing(), Response()]]:
            self.assertEqual(self.run_check(replies), (f'exists=true\ndigest={DIGEST}\n', 1))

    def test_different_inputs_cannot_overwrite(self):
        self.run_check([Response()], fingerprint='different', error='different inputs')

    def test_disagreeing_aliases_cannot_overwrite(self):
        self.run_check([Response(), Response(digest='sha256:' + 'b' * 64)], error='tags disagree')

    def test_auth_rate_limit_and_server_errors_fail_closed(self):
        for code in [401, 403, 429, 500]:
            self.run_check([HTTPError('https://ghcr.io/test', code, 'failure', {}, None)], error='refusing to treat')
