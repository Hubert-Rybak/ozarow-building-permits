"""Real municipal failure through unchanged central validation/publication."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from investment_sources import municipal
from investment_validation import load_dataset
from import_investments import build_dataset, refresh


class RealRetentionTests(unittest.TestCase):
    def test_real_http_failure_retains_full_verified_source_and_refresh_accepts(self):
        prior_path = ROOT / 'public/data/investments.json'
        prior = load_dataset(prior_path)
        old_records = [r for r in prior['records'] if r['sourceId'] == municipal.SOURCE_ID]
        old_source = next(s for s in prior['sources'] if s['id'] == municipal.SOURCE_ID)
        self.assertGreater(len(old_records), 0)
        self.assertEqual(len(old_records), prior['counts']['bySource'][municipal.SOURCE_ID])
        self.assertEqual(len(old_records), old_source['recordCount'])
        rest = {'records': [r for r in prior['records'] if r['sourceId'] != municipal.SOURCE_ID], 'sources': [s for s in prior['sources'] if s['id'] != municipal.SOURCE_ID], 'warnings': []}
        before = hashlib.sha256(prior_path.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='real-retention-') as tmp, patch.object(requests.Session, 'get', side_effect=requests.ConnectionError('forced cold HTTP failure')), patch.object(municipal.time, 'sleep'):
            tmp = Path(tmp)
            retained = municipal.collect(tmp / 'first-cache', prior=copy.deepcopy(prior))
            self.assertEqual(retained['records'], old_records)
            # This is deliberately before evidence equality: RED must expose the
            # actual integration blocker, not just an adapter-only assertion.
            built = build_dataset([retained, rest], generated_at=prior['generatedAt'], prior=prior)
            result = refresh(tmp / 'output', tmp / 'refresh-cache', adapters=[municipal.collect, lambda cache, prior=None: copy.deepcopy(rest)], generated_at=prior['generatedAt'], prior_path=prior_path)
            published = load_dataset(tmp / 'output/investments.json', prior=prior)
            self.assertEqual(result, published)
            self.assertEqual(built['records'], prior['records'])
            self.assertEqual(result['records'], prior['records'])
            src = next(s for s in result['sources'] if s['id'] == municipal.SOURCE_ID)
            self.assertEqual(src['status'], 'retained')
            self.assertTrue(any('forced cold HTTP failure' in w or 'ConnectionError' in w for w in src['warnings']))
            self.assertEqual({k: v for k, v in src.items() if k not in ('status', 'warnings')}, {k: v for k, v in old_source.items() if k not in ('status', 'warnings')})
            self.assertEqual([s for s in result['sources'] if s['id'] != municipal.SOURCE_ID], rest['sources'])
        self.assertEqual(hashlib.sha256(prior_path.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
