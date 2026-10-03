"""Offline tests use explicit observed fixtures, never a production fallback."""
import copy
import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/municipal_observed.json').read_text())
RECORD_KEYS = set('id sourceId sourceRecordId sourceUrl title recordType investor investorName category locality address status statusAsOf summary years costs dates geometries parcelIds events facts relatedIds warnings fetchedAt sourceUpdatedAt'.split())
SOURCE_KEYS = set('id name url fetchedAt sourceUpdatedAt status coverage recordCount warnings reuse'.split())

class ObservedServer:
    def __init__(self, mutation=None):
        self.data = copy.deepcopy(FIXTURE)
        self.mutation = mutation
        self.calls = []
        self.closed = False
    def close(self):
        self.closed = True
    def get(self, url, params=None, **kwargs):
        params = params or {}
        self.calls.append((url, copy.deepcopy(params)))
        if self.mutation == 'timeout' or (self.mutation == 'retry-once' and len(self.calls) == 1):
            raise requests.Timeout('explicit test transport timeout')
        response = requests.Response()
        response.status_code = 200
        response.url = url
        if 'gminneinwestycje.pl' in url:
            text = '<script type="module" src="/assets/dataService-observed.js"></script>' if url.endswith('/') else self.data['module']
            if self.mutation == 'template-rule':
                text = text.replace('Kolejnosc!==-1', 'Kolejnosc!==0')
            response._content = text.encode()
            return response
        boundary = 'Ozarow_granica' in url
        meta = self.data['boundaryMetadata' if boundary else 'metadata']
        feats = self.data['boundary']['features'] if boundary else self.data['features']
        oid = meta['objectIdField']
        if self.mutation == 'empty' and not boundary:
            feats = []
        if self.mutation == 'identity-change' and not boundary and any('Ozarow_Maz_inwestycje_' in u and p and p.get('returnGeometry') for u, p in self.calls[:-1]):
            feats = copy.deepcopy(feats)
            feats[0]['properties'][oid] = 123456
        if not url.endswith('/query'):
            result = copy.deepcopy(meta)
            if self.mutation == 'schema' and not boundary:
                result['fields'] = [f for f in result['fields'] if f['name'] != 'Koszt_kalk']
            if self.mutation == 'malformed-metadata':
                result['advancedQueryCapabilities'] = []
        elif params.get('returnCountOnly') == 'true':
            result = {'count': len(feats)}
            if self.mutation == 'count' and not boundary:
                result['count'] += 1
        elif params.get('returnIdsOnly') == 'true':
            result = {'objectIdFieldName': oid, 'objectIds': [f['properties'][oid] for f in feats]}
        else:
            offset = int(params.get('resultOffset', 0))
            limit = int(params.get('resultRecordCount', 2))
            page = copy.deepcopy(feats[offset:offset+limit])
            result = {'type': 'FeatureCollection', 'features': page, 'exceededTransferLimit': offset+limit < len(feats)}
            if boundary and self.mutation == 'boundary-invalid':
                page[0]['geometry'] = {'type': 'Polygon', 'coordinates': [[[20, 52], [21, 53]]]}
            if self.mutation == 'wrong-crs':
                result['crs'] = {'properties': {'name': 'EPSG:2180'}}
            if not boundary and page:
                if self.mutation == 'duplicate' and offset:
                    page[0] = copy.deepcopy(feats[0])
                elif self.mutation == 'truncated':
                    result['features'] = page[:1]
                    result['exceededTransferLimit'] = False
                elif self.mutation == 'last-transfer' and offset+limit >= len(feats):
                    result['exceededTransferLimit'] = True
                elif self.mutation == 'missing-field':
                    page[0]['properties'].pop('Koszt_txt')
                elif self.mutation == 'cost':
                    page[0]['properties']['Koszt_kalk'] = -1
                elif self.mutation == 'geometry':
                    page[0]['geometry'] = {'type': 'Point', 'coordinates': [999, 52]}
                elif self.mutation == 'unsafe-link':
                    page[0]['properties']['Link'] = 'javascript:alert(1)'
                elif self.mutation == 'literal':
                    page[0]['properties']['Tytul'] = '<script>alert(1)</script>'
                elif self.mutation == 'null-geometry':
                    page[0]['geometry'] = None
        if self.mutation == 'arcgis-error':
            result = {'error': {'code': 500, 'message': 'explicit test service error'}}
        response._content = json.dumps(result).encode()
        return response

class MunicipalTests(unittest.TestCase):
    def adapter(self):
        spec = importlib.util.find_spec('investment_sources.municipal') if (ROOT / 'scripts/investment_sources').exists() else None
        self.assertIsNotNone(spec, 'municipal adapter must exist before collection can run')
        return importlib.import_module('investment_sources.municipal')
    def run_collect(self, mutation=None, prior=None):
        adapter = self.adapter()
        server = ObservedServer(mutation)
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter.requests, 'Session', return_value=server), patch.object(adapter.time, 'sleep'):
            result = adapter.collect(Path(tmp), prior)
        return result, server
    def assert_contract(self, result):
        self.assertEqual(set(result), {'records', 'sources', 'warnings'})
        self.assertEqual(set(result['sources'][0]), SOURCE_KEYS)
        self.assertEqual(result['sources'][0]['recordCount'], len(result['records']))
        for r in result['records']:
            self.assertEqual(set(r), RECORD_KEYS)
            self.assertEqual(r['id'], 'municipal-map:' + r['sourceRecordId'])
            self.assertEqual(r['sourceId'], 'municipal-map')
            for c in r['costs']:
                self.assertEqual(set(c), set('kind amount currency label year scope sourceUrl'.split()))
            for f in r['facts']:
                self.assertEqual(set(f), {'label', 'value', 'sourceUrl'})
            for g in r['geometries']:
                self.assertEqual(set(g), {'type', 'geometry', 'properties'})
                self.assertEqual(set(g['properties']), set('id accuracy sourceUrl parcelId note fetchedAt sourceUpdatedAt'.split()))
                self.assertEqual(g['properties']['accuracy'], 'source-point')
    def test_complete_paged_observed_contract(self):
        result, server = self.run_collect()
        self.assert_contract(result)
        self.assertEqual(result['sources'][0]['status'], 'fresh')
        self.assertEqual([r['sourceRecordId'] for r in result['records']], ['1', '9', '400'])
        r = result['records'][0]
        self.assertEqual(r['title'], FIXTURE['features'][0]['properties']['Tytul'])
        self.assertEqual(r['geometries'][0]['geometry'], FIXTURE['features'][0]['geometry'])
        self.assertEqual(r['years'], [2018])
        self.assertEqual(r['costs'][0]['amount'], 1612251.45)
        self.assertIsNone(r['costs'][0]['year'])
        self.assertIsNone(r['statusAsOf'])
        self.assertEqual(result['records'][1]['costs'][0]['amount'], None)
        self.assertNotEqual(r['sourceUpdatedAt'], result['sources'][0]['sourceUpdatedAt'])
        self.assertIn('GlobalID', [f['label'] for f in r['facts']])
        self.assertTrue(result['records'][-1]['warnings'])
        self.assertIn('poza', ' '.join(result['records'][-1]['warnings']))
        self.assertNotIn('Creator', json.dumps(result))
        self.assertNotIn('Editor', json.dumps(result))
        for url, params in server.calls:
            if params and params.get('f') == 'geojson':
                self.assertEqual(params['outSR'], '4326')
                self.assertIn(' ASC', params['orderByFields'])
                self.assertNotIn('*', params['outFields'])
    def test_reject_corruption_without_prior(self):
        for mutation in ['count','schema','duplicate','truncated','last-transfer','missing-field','cost','geometry','arcgis-error','template-rule','timeout','malformed-metadata']:
            with self.subTest(mutation=mutation):
                result, _ = self.run_collect(mutation)
                self.assert_contract(result)
                self.assertEqual(result['records'], [])
                self.assertEqual(result['sources'][0]['status'], 'unavailable')
                self.assertTrue(result['warnings'])
    def test_retains_only_verified_municipal_prior(self):
        fresh, _ = self.run_collect()
        prior = {'schemaVersion': 1, 'generatedAt': fresh['sources'][0]['fetchedAt'], **fresh, 'counts': {}}
        prior['records'].append({'sourceId': 'other'})
        result, _ = self.run_collect('schema', prior)
        self.assertEqual(result['sources'][0]['status'], 'retained')
        self.assertEqual(result['records'], fresh['records'][:-1])
        self.assertEqual(result['sources'][0]['fetchedAt'], fresh['sources'][0]['fetchedAt'])
        self.assert_contract(result)
    def test_loss_guard_and_invalid_prior(self):
        fresh, _ = self.run_collect()
        prior = {'schemaVersion': 1, **copy.deepcopy(fresh)}
        for i in range(4):
            row = copy.deepcopy(fresh['records'][0]); row['sourceRecordId'] = str(1000+i); row['id'] = 'municipal-map:' + row['sourceRecordId']
            row['geometries'][0]['properties']['id'] = row['id']
            prior['records'].append(row)
        prior['sources'][0]['recordCount'] = len(prior['records'])
        result, _ = self.run_collect(prior=prior)
        self.assertEqual(result['sources'][0]['status'], 'retained')
        self.assertEqual(len(result['records']), 7)
        self.assertIn('20%', ' '.join(result['warnings']))
        prior['records'][0]['sourceUrl'] = 'javascript:bad'
        result, _ = self.run_collect('schema', prior)
        self.assertEqual(result['sources'][0]['status'], 'unavailable')
        self.assertEqual(result['records'], [])
    def test_unsafe_url_fallback_and_external_literal_text(self):
        result, _ = self.run_collect('unsafe-link')
        self.assertEqual(result['sources'][0]['status'], 'fresh')
        self.assertIn('OBJECTID', result['records'][0]['sourceUrl'])
        self.assertTrue(result['records'][0]['sourceUrl'].startswith('https://'))
        result, _ = self.run_collect('literal')
        self.assertEqual(result['records'][0]['title'], '<script>alert(1)</script>')
    def test_missing_point_is_not_fabricated(self):
        result, _ = self.run_collect('null-geometry')
        self.assertEqual(result['sources'][0]['status'], 'fresh')
        self.assertEqual(result['records'][0]['geometries'], [])
        self.assertTrue(result['records'][0]['warnings'])

    def test_cache_failure_returns_explicit_source_failure(self):
        adapter = self.adapter()
        server = ObservedServer()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter.requests, 'Session', return_value=server), patch.object(Path, 'write_text', side_effect=OSError('explicit test disk failure')):
            result = adapter.collect(Path(tmp))
        self.assertEqual(result['sources'][0]['status'], 'unavailable')
        self.assertTrue(server.closed)
    def test_geometry_loss_guard_keeps_prior_points(self):
        fresh, _ = self.run_collect()
        prior = {'schemaVersion': 1, **copy.deepcopy(fresh)}
        result, _ = self.run_collect('null-geometry', prior)
        self.assertEqual(result['sources'][0]['status'], 'retained')
        self.assertEqual(result['records'], fresh['records'])

    def test_invalid_boundary_is_source_failure_not_crash(self):
        result, _ = self.run_collect('boundary-invalid')
        self.assertEqual(result['sources'][0]['status'], 'unavailable')
        self.assertTrue(result['warnings'])
    def test_retry_is_bounded_and_recovers(self):
        result, server = self.run_collect('retry-once')
        self.assertEqual(result['sources'][0]['status'], 'fresh')
        self.assertEqual(server.calls[0][0], server.calls[1][0])
        result, server = self.run_collect('timeout')
        self.assertEqual(len(server.calls), 3)
        self.assertEqual(result['sources'][0]['status'], 'unavailable')
    def test_identity_change_and_wrong_crs_are_rejected(self):
        for mutation in ['identity-change', 'wrong-crs']:
            result, _ = self.run_collect(mutation)
            self.assertEqual(result['sources'][0]['status'], 'unavailable')
    def test_empty_verified_source_is_distinguished_from_unavailable(self):
        result, _ = self.run_collect('empty')
        self.assertEqual(result['sources'][0]['status'], 'fresh')
        self.assertEqual(result['records'], [])
    def test_prior_source_count_must_be_verified(self):
        fresh, _ = self.run_collect()
        prior = {'schemaVersion': 1, **copy.deepcopy(fresh)}
        prior['sources'][0]['recordCount'] = 999
        result, _ = self.run_collect('schema', prior)
        self.assertEqual(result['sources'][0]['status'], 'unavailable')
    def test_unsafe_backslash_url_cannot_pass_browser_url_parser(self):
        self.assertFalse(self.adapter()._safe_url('https://official.example\\\\@evil.example/path'))
        self.assertFalse(self.adapter()._safe_url('https://official.example\\\\evil/path'))
        self.assertFalse(self.adapter()._safe_url('https://official.example/path?token=secret'))
        self.assertFalse(self.adapter()._safe_url('https://user:password@official.example/path'))

if __name__ == '__main__':
    unittest.main()
