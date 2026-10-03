"""Opt-in independent verification of a real contribution and retrieval evidence.

No network or fallback data: MUNICIPAL_LIVE_ARTIFACT must point at actual collect()
output, and MUNICIPAL_LIVE_EVIDENCE at the corresponding evidence.json.
"""
import hashlib
import json
import os
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from shapely.geometry import shape
from shapely.ops import unary_union

RECORD_KEYS = set('id sourceId sourceRecordId sourceUrl title recordType investor investorName category locality address status statusAsOf summary years costs dates geometries parcelIds events facts relatedIds warnings fetchedAt sourceUpdatedAt'.split())
SOURCE_KEYS = set('id name url fetchedAt sourceUpdatedAt status coverage recordCount warnings reuse'.split())

@unittest.skipUnless(os.getenv('MUNICIPAL_LIVE_ARTIFACT') and os.getenv('MUNICIPAL_LIVE_EVIDENCE'), 'Opt-in verification requires real artifact and exact evidence paths')
class MunicipalLiveEvidenceTests(unittest.TestCase):
    def test_real_contribution_matches_every_retrieved_fact_and_point(self):
        artifact = json.loads(Path(os.environ['MUNICIPAL_LIVE_ARTIFACT']).read_text())
        evidence_path = Path(os.environ['MUNICIPAL_LIVE_EVIDENCE'])
        evidence = json.loads(evidence_path.read_text())
        self.assertEqual(set(artifact), {'records', 'sources', 'warnings'})
        self.assertEqual(len(artifact['sources']), 1)
        source = artifact['sources'][0]
        self.assertEqual(set(source), SOURCE_KEYS)
        self.assertEqual(source['id'], 'municipal-map')
        self.assertEqual(source['status'], 'fresh')
        self.assertEqual(evidence['status'], 'fresh')
        self.assertEqual(evidence['fetchedAt'], source['fetchedAt'])
        self.assertEqual(evidence['investments']['sourceUpdatedAt'], source['sourceUpdatedAt'])
        self.assertEqual(evidence['investments']['countAfter'], evidence['investments']['rawCount'])
        raw, borders = [], []
        for entry in evidence['requests']:
            if 'file' not in entry:
                continue
            data_path = evidence_path.parent / entry['file']
            encoded = data_path.read_bytes()
            self.assertEqual(hashlib.sha256(encoded).hexdigest(), entry['sha256'])
            params = entry.get('params') or {}
            if params.get('f') != 'geojson':
                continue
            data = json.loads(encoded)
            self.assertEqual(data['type'], 'FeatureCollection')
            self.assertEqual(params['outSR'], '4326')
            self.assertNotIn('*', params['outFields'])
            self.assertIn(' ASC', params['orderByFields'])
            if 'Ozarow_granica/' in entry['url']:
                borders.extend(data['features'])
            else:
                raw.extend(data['features'])
        self.assertTrue(borders)
        boundary = unary_union([shape(f['geometry']) for f in borders])
        self.assertTrue(boundary.is_valid)
        ids = [f['properties']['OBJECTID'] for f in raw]
        self.assertEqual(ids, sorted(set(ids)))
        self.assertEqual(ids, evidence['investments']['ids'])
        self.assertEqual(len(raw), evidence['rawCount'])
        features = {str(f['properties']['OBJECTID']): f for f in raw if f['properties']['Kolejnosc'] != -1}
        self.assertEqual(len(raw)-len(features), evidence['excludedTemplates'])
        self.assertEqual(len(features), len(artifact['records']))
        self.assertEqual(source['recordCount'], len(features))
        self.assertEqual({r['sourceRecordId'] for r in artifact['records']}, set(features))
        outside, mapped, null_costs = [], 0, 0
        for record in artifact['records']:
            self.assertEqual(set(record), RECORD_KEYS)
            props = features[record['sourceRecordId']]['properties']
            self.assertEqual(record['id'], 'municipal-map:' + str(props['OBJECTID']))
            self.assertEqual(record['sourceId'], 'municipal-map')
            self.assertEqual(record['recordType'], 'project')
            self.assertEqual(record['title'], props['Tytul'])
            self.assertEqual(record['category'], props['Kategoria'] or '')
            self.assertEqual(record['locality'], props['Obreb'] or '')
            self.assertEqual(record['status'], props['Status'] or '')
            self.assertIsNone(record['statusAsOf'])
            self.assertEqual(record['dates'], [])
            self.assertEqual(record['events'], [])
            self.assertEqual(record['parcelIds'], [])
            self.assertEqual(record['relatedIds'], [])
            self.assertEqual(record['fetchedAt'], source['fetchedAt'])
            self.assertTrue(datetime.fromisoformat(record['fetchedAt'].replace('Z', '+00:00')).tzinfo)
            if props['EditDate'] is not None:
                self.assertEqual(datetime.fromisoformat(record['sourceUpdatedAt'].replace('Z', '+00:00')).timestamp(), props['EditDate']/1000)
            self.assertEqual(len(record['costs']), 1)
            cost = record['costs'][0]
            self.assertEqual(set(cost), set('kind amount currency label year scope sourceUrl'.split()))
            self.assertEqual(cost['amount'], props['Koszt_kalk'])
            self.assertEqual(cost['label'], props['Koszt_txt'] or '')
            self.assertEqual(cost['kind'], 'reported')
            self.assertEqual(cost['scope'], 'unknown')
            self.assertEqual(cost['currency'], 'PLN')
            self.assertIsNone(cost['year'])
            null_costs += cost['amount'] is None
            for url in [source['url'], record['sourceUrl'], cost['sourceUrl']]:
                p = urlsplit(url)
                self.assertIn(p.scheme, {'https', 'http'})
                self.assertTrue(p.hostname)
                self.assertFalse(p.username or p.password)
            facts = {f['label']: f['value'] for f in record['facts']}
            for key, value in props.items():
                self.assertNotIn(key, {'Creator', 'Editor'})
                if value is not None:
                    self.assertEqual(facts[key], str(value))
            for fact in record['facts']:
                self.assertEqual(set(fact), {'label', 'value', 'sourceUrl'})
                self.assertIsInstance(fact['value'], str)
            geometry = features[record['sourceRecordId']]['geometry']
            self.assertEqual(len(record['geometries']), int(geometry is not None))
            for feature in record['geometries']:
                self.assertEqual(set(feature), {'type', 'geometry', 'properties'})
                self.assertEqual(feature['type'], 'Feature')
                self.assertEqual(feature['geometry'], geometry)
                self.assertEqual(geometry['type'], 'Point')
                p = feature['properties']
                self.assertEqual(set(p), set('id accuracy sourceUrl parcelId note fetchedAt sourceUpdatedAt'.split()))
                self.assertEqual(p['id'], record['id'])
                self.assertEqual(p['accuracy'], 'source-point')
                self.assertIsNone(p['parcelId'])
                self.assertEqual(p['fetchedAt'], record['fetchedAt'])
                self.assertEqual(p['sourceUpdatedAt'], record['sourceUpdatedAt'])
                mapped += 1
                if not boundary.covers(shape(geometry)):
                    outside.append(record['sourceRecordId'])
                    self.assertIn('poza oficjalną', ' '.join(record['warnings']))
        self.assertEqual(outside, evidence['outsideObjectIds'])
        self.assertEqual(mapped, evidence['geometryCount'])
        self.assertEqual(null_costs, evidence['nullNumericCosts'])
        self.assertNotIn('Creator', json.dumps(artifact))
        self.assertNotIn('Editor', json.dumps(artifact))
        self.assertNotIn('description', json.dumps(artifact))
        json.dumps(artifact, allow_nan=False)

if __name__ == '__main__':
    unittest.main()
