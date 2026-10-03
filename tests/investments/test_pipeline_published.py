"""Real browser artifact is mandatory: missing production data must fail, never skip."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))


class PublishedInvestments(unittest.TestCase):
    def test_real_production_artifact_matches_strict_contract(self):
        artifact = ROOT / 'public/data/investments.json'
        self.assertTrue(artifact.is_file(), 'Missing real adapter-generated investments.json; integration incomplete')
        from investment_validation import load_dataset
        dataset = load_dataset(artifact)
        self.assertGreater(dataset['counts']['records'], 0, 'Production snapshot must contain verified records')
        self.assertTrue(any(s['status'] in {'fresh','static','retained'} and s['recordCount'] > 0 for s in dataset['sources']))


if __name__ == '__main__':
    unittest.main()
