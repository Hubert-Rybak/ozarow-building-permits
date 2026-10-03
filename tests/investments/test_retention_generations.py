"""Exercise the unchanged real retention regression on valid next generations.

Synthetic generation probes are written only under private scratch, never public/.
Actual baseline records/source evidence remain untouched.
"""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_real_retention as retention
from investment_sources import municipal
from investment_validation import counts_for, load_dataset, validate_dataset
from import_investments import publish


class RetentionGenerationTests(unittest.TestCase):
    def exercise_generation(self, growing):
        base = load_dataset(retention.ROOT / 'public/data/investments.json')
        generation = copy.deepcopy(base)
        municipal_records = [r for r in generation['records'] if r['sourceId'] == municipal.SOURCE_ID]
        self.assertGreater(len(municipal_records), 5)
        if growing:
            row = copy.deepcopy(municipal_records[0])
            native_id = str(max(int(r['sourceRecordId']) for r in municipal_records) + 1)
            row.update(id=municipal.SOURCE_ID + ':' + native_id, sourceRecordId=native_id,
                       title='TEST ONLY synthetic next-generation growth')
            for feature in row['geometries']:
                feature['properties']['id'] = row['id']
            for fact in row['facts']:
                if fact['label'] == 'OBJECTID':
                    fact['value'] = native_id
            generation['records'].append(row)
            expected_count = len(municipal_records) + 1
        else:
            removed = municipal_records[-1]['id']
            generation['records'] = [r for r in generation['records'] if r['id'] != removed]
            expected_count = len(municipal_records) - 1
        generation['records'].sort(key=lambda r: r['id'])
        source = next(s for s in generation['sources'] if s['id'] == municipal.SOURCE_ID)
        source['recordCount'] = expected_count
        generation['counts'] = counts_for(generation['records'], generation['sources'])
        validate_dataset(generation, prior=base)
        self.assertEqual(generation['counts']['bySource'][municipal.SOURCE_ID], expected_count)
        with tempfile.TemporaryDirectory(prefix='retention-generation-') as tmp:
            root = Path(tmp)
            publish(root / 'public/data', generation, prior=base)
            self.assertEqual(load_dataset(root / 'public/data/investments.json', prior=base), generation)
            with patch.object(retention, 'ROOT', root):
                regression = retention.RealRetentionTests('test_real_http_failure_retains_full_verified_source_and_refresh_accepts')
                regression.test_real_http_failure_retains_full_verified_source_and_refresh_accepts()

    def test_growth_generation_still_passes_full_real_retention_regression(self):
        self.exercise_generation(growing=True)

    def test_allowed_loss_generation_still_passes_full_real_retention_regression(self):
        self.exercise_generation(growing=False)


if __name__ == '__main__':
    unittest.main()
