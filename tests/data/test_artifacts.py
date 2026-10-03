"""Validate the actual published vertical slice; no network or synthetic data."""
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]


class PublishedArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.permits = json.loads((ROOT / 'public/data/permits.json').read_text())
        cls.parcels = json.loads((ROOT / 'public/data/parcels.geojson').read_text())
        cls.meta = json.loads((ROOT / 'public/data/metadata.json').read_text())

    def test_counts_are_recomputed_from_real_artifacts(self):
        records = self.permits['records']
        counts = Counter(r['geometryStatus'] for r in records)
        self.assertEqual(self.meta['recordCount'], len(records))
        self.assertEqual(self.meta['parcelCount'], len(self.parcels['features']))
        for name, status in [('matchedRecordCount','matched'), ('partialRecordCount','partial'), ('unresolvedRecordCount','unresolved')]:
            self.assertEqual(self.meta[name], counts[status])
        self.assertEqual(self.meta['kindCounts'], dict(Counter(r['kind'] for r in records)))
        self.assertGreaterEqual(len(records), 50)
        self.assertGreaterEqual(len(self.parcels['features']), 20)

    def test_entire_gmina_not_just_city_is_present(self):
        refs = {f['properties']['id'].split('.')[0] for f in self.parcels['features']}
        self.assertEqual(refs, {'143206_4', '143206_5'})
        localities = {r['locality'] for r in self.permits['records']}
        self.assertTrue({'Duchnice','Płochocin','Ożarów Mazowiecki'}.issubset(localities))

    def test_unique_ids_and_exact_bidirectional_joins(self):
        records = self.permits['records']
        features = self.parcels['features']
        self.assertEqual(len({r['id'] for r in records}), len(records))
        self.assertEqual(len({f['properties']['id'] for f in features}), len(features))
        feature_ids = {f['properties']['id'] for f in features}
        reverse = defaultdict(set)
        for r in records:
            self.assertTrue(set(r['parcelIds']).issubset(feature_ids))
            self.assertEqual(bool(r['parcelIds']), r['geometryStatus'] != 'unresolved')
            for ref in r['parcelIds']:
                reverse[ref].add(r['id'])
        for f in features:
            props = f['properties']
            self.assertEqual(set(props['permitIds']), reverse[props['id']])
            self.assertTrue(props['sourceUrl'].startswith('https://uldk.gugik.gov.pl/?request=GetParcelById&'))

    def test_geometry_valid_wgs84_and_no_point_fallback(self):
        self.assertEqual(self.parcels['type'], 'FeatureCollection')
        for f in self.parcels['features']:
            geom = shape(f['geometry'])
            self.assertIn(geom.geom_type, ('Polygon', 'MultiPolygon'))
            self.assertTrue(geom.is_valid)
            self.assertFalse(geom.is_empty)
            west, south, east, north = geom.bounds
            self.assertTrue(14 <= west <= east <= 25 and 49 <= south <= north <= 55)

    def test_allowlist_and_no_private_source_columns(self):
        required = {'id','kind','title','description','applicationDate','decisionDate','decisionNumber','status','locality','street','municipality','cadastralRegion','parcelNumbers','parcelIds','category','sourceUrl','geometryStatus','geometryNote'}
        for r in self.permits['records']:
            self.assertEqual(set(r), required)
            self.assertIn(r['kind'], ('application','decision','notification'))
            self.assertIn(r['geometryStatus'], ('matched','partial','unresolved'))
            if r['kind'] == 'decision':
                self.assertIn('nieudostępniony', r['status'])
            self.assertTrue(r['sourceUrl'].startswith('https://wyszukiwarka.gunb.gov.pl/pliki_pobranie/'))

    def test_datasets_share_generation_date_and_exact_coverage(self):
        self.assertEqual(self.permits['generatedAt'], self.meta['generatedAt'])
        self.assertEqual(self.parcels.get('generatedAt'), self.meta['generatedAt'])
        dates = sorted(r['applicationDate'] for r in self.permits['records'])
        self.assertEqual(dates[0], self.meta['dateRange']['actualStart'])
        self.assertEqual(dates[-1], self.meta['dateRange']['actualEnd'])
        self.assertTrue(self.meta['warnings'])

    def test_no_pending_rows_does_not_claim_no_pending_applications(self):
        if not any(r['kind'] == 'application' for r in self.permits['records']):
            self.assertTrue(any('Nie oznacza braku nierozpatrzonych' in warning for warning in self.meta['warnings']))

    def test_geometry_snapshot_dates_are_disclosed(self):
        coverage = self.meta['geometryCoverage']
        self.assertIsInstance(coverage.get('downloadedAtStart'), str)
        self.assertIsInstance(coverage.get('downloadedAtEnd'), str)
        self.assertLessEqual(coverage['downloadedAtStart'], coverage['downloadedAtEnd'])

    def test_local_cache_proves_published_geometries_are_uldk_responses(self):
        cache = ROOT / '.cache/responses'
        if not cache.exists():
            self.skipTest('private cache not shipped; cache provenance checked at ingestion time')
        spec = importlib.util.spec_from_file_location('import_data', ROOT / 'scripts/import_data.py')
        assert spec is not None and spec.loader is not None
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        for f in self.parcels['features']:
            url = f['properties']['sourceUrl']
            entry = json.loads((cache / (hashlib.sha256(url.encode()).hexdigest() + '.json')).read_text())
            self.assertEqual(entry['url'], url)
            geometry = m.parse_uldk(entry['text'], f['properties']['id'])
            self.assertEqual(f['geometry'], geometry)


    def test_public_evidence_proves_geometries_without_private_cache(self):
        spec = importlib.util.spec_from_file_location('import_data', ROOT / 'scripts/import_data.py')
        assert spec is not None and spec.loader is not None
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        payload = json.loads((ROOT / 'scripts/uldk-cache.json').read_text())
        self.assertEqual(payload['schemaVersion'], 1)
        self.assertEqual(len(payload['responses']), self.meta['publicEvidenceResponseCount'])
        evidence = {}
        for entry in payload['responses']:
            # A committed historical snapshot must not age out of offline tests;
            # eligibility is measured at publication. Ingestion tests check live TTL.
            with patch.object(m.time, 'time', return_value=m.datetime.fromisoformat(self.meta['generatedAt'].replace('Z', '+00:00')).timestamp()):
                checked = m.verify_public_cache_entry(entry)
            self.assertNotIn('gunb', checked['url'])
            self.assertNotIn('nazwa_inwestor', checked['text'])
            self.assertNotIn('projektant', checked['text'])
            self.assertNotIn(checked['url'], evidence)
            evidence[checked['url']] = checked
        timestamps = []
        for feature in self.parcels['features']:
            props = feature['properties']
            entry = evidence[props['sourceUrl']]
            self.assertEqual(feature['geometry'], m.parse_uldk(entry['text'], props['id']))
            timestamps.append(entry['downloadedAt'])
        self.assertEqual(min(timestamps), self.meta['geometryCoverage']['downloadedAtStart'])
        self.assertEqual(max(timestamps), self.meta['geometryCoverage']['downloadedAtEnd'])

    def test_source_download_evidence_is_exact_and_separate_from_generation(self):
        sources = [source for source in self.meta['sources'] if 'sha256' in source]
        self.assertEqual(len(sources), 2)
        for source in sources:
            self.assertRegex(source['sha256'], r'^[a-f0-9]{64}$')
            self.assertGreater(source['byteCount'], 0)
            self.assertIn('httpLastModified', source)
            self.assertIn('httpETag', source)
            self.assertLessEqual(source['downloadedAt'], self.meta['generatedAt'])
        self.assertEqual(self.permits['source']['downloadedAt'], max(source['downloadedAt'] for source in sources))

    def test_all_parcels_attempted_and_record_contract_remains_v1(self):
        self.assertEqual(self.permits['schemaVersion'], 1)
        coverage = self.meta['geometryCoverage']
        self.assertEqual(coverage['maxParcels'], 0)
        self.assertEqual(coverage['unattemptedParcelCount'], 0)
        self.assertEqual(coverage['candidateParcelCount'], coverage['attemptedParcelCount'])
        self.assertEqual(coverage['confirmedParcelCount'] + coverage['failedParcelCount'], coverage['attemptedParcelCount'])
        self.assertEqual(coverage['reusedParcelCount'] + coverage['freshParcelCount'], coverage['confirmedParcelCount'])
        for f in self.parcels['features']:
            self.assertEqual(set(f['properties']), {'id', 'parcelNumber', 'region', 'permitIds', 'sourceUrl'})

    def test_free_text_is_not_published_as_safe_with_known_names_only(self):
        for record in self.permits['records']:
            self.assertIn('Swobodny opis GUNB pominięto', record['description'])
            self.assertNotRegex(record['title'] + record['description'], r'\b\d{11}\b|[\w.+-]+@[\w.-]+')
        self.assertIn('fixed-vocabulary', self.meta['privacy'])


if __name__ == '__main__':
    unittest.main()
