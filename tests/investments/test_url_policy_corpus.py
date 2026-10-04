"""Shared fake-only URL corpus: validator and real scratch publisher fail closed."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from import_investments import publish, refresh
from investment_validation import load_dataset, safe_url, validate_dataset

CORPUS = json.loads((Path(__file__).parent / 'fixtures/url_policy_corpus.json').read_text())
URL_PATHS = [
    ('sources', 0, 'url'),
    ('records', 0, 'sourceUrl'),
    ('records', 0, 'costs', 0, 'sourceUrl'),
    ('records', 0, 'dates', 0, 'sourceUrl'),
    ('records', 0, 'events', 0, 'sourceUrl'),
    ('records', 0, 'facts', 0, 'sourceUrl'),
    ('records', 0, 'geometries', 0, 'properties', 'sourceUrl'),
]


def with_url(path, url):
    dataset = copy.deepcopy(CORPUS['baseDataset'])
    target = dataset
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = url
    return dataset


class UrlPolicyCorpusTests(unittest.TestCase):
    def test_url_helper_matches_shared_query_and_fragment_policy(self):
        for case in CORPUS['cases']:
            with self.subTest(case=case['id']):
                if case['accepted']:
                    safe_url(case['url'], 'corpus')
                else:
                    with self.assertRaisesRegex(ValueError, 'secret/contact URL field'):
                        safe_url(case['url'], 'corpus')

    def test_every_dataset_url_field_matches_shared_policy(self):
        for path in URL_PATHS:
            for case in CORPUS['cases']:
                with self.subTest(path=path, case=case['id']):
                    dataset = with_url(path, case['url'])
                    if case['accepted']:
                        validate_dataset(dataset)
                    else:
                        with self.assertRaisesRegex(ValueError, 'secret/contact URL field'):
                            validate_dataset(dataset)

    def test_real_publish_rejects_corpus_without_replacing_verified_bytes(self):
        with tempfile.TemporaryDirectory(prefix='url-policy-') as tmp:
            output = Path(tmp) / 'output'
            baseline = copy.deepcopy(CORPUS['baseDataset'])
            publish(output, baseline)
            target = output / 'investments.json'
            before = target.read_bytes()
            for path in URL_PATHS:
                for case in CORPUS['cases']:
                    with self.subTest(path=path, case=case['id']):
                        target.write_bytes(before)
                        dataset = with_url(path, case['url'])
                        if case['accepted']:
                            publish(output, dataset, prior=baseline)
                            self.assertEqual(load_dataset(target, prior=baseline), dataset)
                        else:
                            with self.assertRaisesRegex(ValueError, 'secret/contact URL field'):
                                publish(output, dataset, prior=baseline)
                            self.assertEqual(target.read_bytes(), before)
                            self.assertEqual(load_dataset(target), baseline)
                        self.assertEqual(list(output.iterdir()), [target])

    def test_real_refresh_rejects_corpus_without_replacing_verified_bytes(self):
        with tempfile.TemporaryDirectory(prefix='url-refresh-') as tmp:
            root = Path(tmp)
            output = root / 'output'
            baseline = copy.deepcopy(CORPUS['baseDataset'])
            publish(output, baseline)
            target = output / 'investments.json'
            before = target.read_bytes()
            for case in CORPUS['cases']:
                with self.subTest(case=case['id']):
                    target.write_bytes(before)
                    dataset = with_url(('records', 0, 'sourceUrl'), case['url'])
                    contribution = {key: dataset[key] for key in ('records', 'sources', 'warnings')}
                    def collect(cache, prior=None):
                        self.assertEqual(prior, baseline)
                        return copy.deepcopy(contribution)
                    if case['accepted']:
                        result = refresh(output, root / 'cache', adapters=[collect], generated_at=baseline['generatedAt'])
                        expected = {**dataset, 'links': []}  # current generations always carry links
                        self.assertEqual(result, expected)
                        self.assertEqual(load_dataset(target, prior=baseline), expected)
                    else:
                        with self.assertRaisesRegex(ValueError, 'secret/contact URL field'):
                            refresh(output, root / 'cache', adapters=[collect], generated_at=baseline['generatedAt'])
                        self.assertEqual(target.read_bytes(), before)
                        self.assertEqual(load_dataset(target), baseline)
                    self.assertEqual(list(output.iterdir()), [target])


if __name__ == '__main__':
    unittest.main()
