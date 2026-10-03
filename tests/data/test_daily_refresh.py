"""Daily publishing safety: fixtures are test-only and never published."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('daily_importer', ROOT / 'scripts/import_data.py')
PARCEL = '143206_5.0003.20/2'
TEXT = '0\nSRID=4326;POLYGON((20.8 52.2,20.81 52.2,20.81 52.21,20.8 52.2))|' + PARCEL


def response(content):
    result = Mock(content=content, headers={})
    result.raise_for_status.return_value = None
    return result


class DailySafety(unittest.TestCase):
    def setUp(self):
        assert SPEC is not None and SPEC.loader is not None
        self.m = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(self.m)

    def stamp(self, days=0):
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace('+00:00', 'Z')

    def test_refresh_sources_cli_is_distinct_from_geometry_refresh(self):
        received = []
        with patch('sys.argv', ['import_data.py', '--refresh-sources']), patch.object(self.m, 'run', side_effect=lambda a: received.append(a)):
            self.m.main()
        self.assertTrue(received[0].refresh_sources)
        self.assertFalse(received[0].refresh)

    def test_refresh_sources_incompatible_with_offline(self):
        with patch('sys.argv', ['import_data.py', '--refresh-sources', '--offline']), patch.object(self.m, 'run', side_effect=AssertionError('must reject before I/O')), patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as raised:
                self.m.main()
            self.assertEqual(raised.exception.code, 2)

    def test_refresh_sources_keeps_valid_geometry_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(directory, refresh_sources=True)
            url = self.m.uldk_url('GetParcelById', PARCEL)
            entry = {'url': url, 'downloadedAt': self.stamp(), 'text': TEXT}
            path = Path(directory) / 'responses' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
            self.m.atomic_file(path, json.dumps(entry).encode())
            with patch.object(self.m.requests, 'get', side_effect=AssertionError('positive geometry should remain cached')):
                self.assertEqual(client.text(url, lambda t: self.m.parse_uldk(t, PARCEL)), TEXT)
                self.assertIn(url, client.cache_hits)

    def test_cached_ttl_uses_evidence_timestamp_not_mtime(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(directory, offline=True)
            url = self.m.uldk_url('GetParcelById', PARCEL)
            path = Path(directory) / 'responses' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
            self.m.atomic_file(path, json.dumps({'url': url, 'downloadedAt': self.stamp(31), 'text': TEXT}).encode())
            with self.assertRaises(ValueError):
                client.text(url, lambda t: self.m.parse_uldk(t, PARCEL))

    def test_future_geometry_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(directory, offline=True)
            url = self.m.uldk_url('GetParcelById', PARCEL)
            path = Path(directory) / 'responses' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
            self.m.atomic_file(path, json.dumps({'url': url, 'downloadedAt': self.stamp(-1), 'text': TEXT}).encode())
            with self.assertRaises(ValueError):
                client.text(url, lambda t: self.m.parse_uldk(t, PARCEL))

    def test_refresh_download_replaces_zip_and_tracks_real_http_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(directory, refresh_sources=True)
            url = self.m.DOWNLOADS['permit']
            content = io.BytesIO()
            with zipfile.ZipFile(content, 'w') as z:
                z.writestr('test.csv', 'test only')
            self.m.atomic_file(Path(directory) / url.rsplit('/', 1)[-1], content.getvalue())
            reply = response(content.getvalue())
            reply.headers = {'Last-Modified': 'Fri, 02 Oct 2026 22:00:00 GMT', 'ETag': 'test-etag'}
            with patch.object(self.m.requests, 'get', return_value=reply) as get:
                archive = client.download(url)
                self.assertEqual(get.call_count, 1)
            evidence = client.archive_evidence(url, archive)
            self.assertEqual(evidence['sha256'], hashlib.sha256(content.getvalue()).hexdigest())
            self.assertEqual(evidence['httpLastModified'], reply.headers['Last-Modified'])
            self.assertEqual(evidence['httpETag'], 'test-etag')
            self.assertLess(abs(datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(evidence['downloadedAt'].replace('Z', '+00:00')).timestamp()), 10)

    def test_complete_csv_schema_is_required_even_when_core_geometry_fields_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('source.csv', 'numer_gunb;terc;numer_dzialki;obreb_numer\nA;1432065;20/2;0003\n')
            with self.assertRaisesRegex(ValueError, 'schema'):
                list(self.m.read_csv_zip(path))

    def test_truncated_csv_row_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.zip'
            # Actual schema, no source personal values in fixture.
            header = ';'.join(sorted(self.m.REQUIRED_COLUMNS['permit']))
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('source.csv', header + '\nonly-one-column\n')
            with self.assertRaisesRegex(ValueError, 'row'):
                list(self.m.read_csv_zip(path, 'permit'))

    def test_public_text_is_safe_when_investor_name_is_missing(self):
        r = {'numer_gunb': 'TEST/1', 'data_wplywu_wniosku': '2025-01-01', 'terc': '1432065', 'jednosta_numer_ew': '143206_5', 'obreb_numer': '0003', 'numer_dzialki': '20/2', 'nazwa_zam_budowlanego': 'Budowa budynku mieszkalnego dla PRIVATEPERSON SECRETNAME', 'nazwa_zamierzenia_bud': 'PRIVATEPERSON SECRETNAME, kontakt secret@example.test, PESEL 12345678901'}
        records, _ = self.m.normalize_rows([r], 'permit', '2025-01-01', '2026-10-03')
        for field in ('title', 'description'):
            self.assertNotIn('PRIVATEPERSON', records[0][field])
            self.assertNotIn('SECRETNAME', records[0][field])
            self.assertNotIn('secret@', records[0][field])
            self.assertNotIn('12345678901', records[0][field])
        self.assertIn('mieszkal', records[0]['title'])

    def previous(self, path, records=100, parcels=100):
        self.m.atomic_publish(path, {'metadata.json': {'recordCount': records, 'parcelCount': parcels, 'dateRange': {'requestedStart': '2025-01-01', 'requestedEnd': '2026-10-02'}, 'kindCounts': {'decision': 80, 'notification': 20}}, 'permits.json': {'old': True}})

    def current(self, **changes):
        result = {'recordCount': 100, 'parcelCount': 100, 'dateRange': {'requestedStart': '2025-01-01', 'requestedEnd': '2026-10-03'}, 'kindCounts': {'decision': 80, 'notification': 20}, 'rawStatistics': {'permit': {'invalidDateRows': 0, 'missingIdRows': 0}, 'notification': {'invalidDateRows': 0, 'missingIdRows': 0}}}
        result.update(changes)
        return result

    def test_drastic_record_loss_preserves_previous_set(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'data'
            self.previous(target)
            before = (target / 'permits.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'loss'):
                self.m.validate_publication(target, self.current(recordCount=70))
            self.assertEqual((target / 'permits.json').read_bytes(), before)

    def test_drastic_geometry_loss_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'data'
            self.previous(target)
            with self.assertRaisesRegex(ValueError, 'loss'):
                self.m.validate_publication(target, self.current(parcelCount=70))

    def test_one_source_cannot_disappear_behind_aggregate_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'data'
            self.previous(target)
            with self.assertRaisesRegex(ValueError, 'loss'):
                self.m.validate_publication(target, self.current(kindCounts={'decision': 95, 'notification': 5}))

    def test_invalid_date_or_missing_system_id_blocks_publication(self):
        for key in ('invalidDateRows', 'missingIdRows'):
            with tempfile.TemporaryDirectory() as directory:
                meta = self.current(rawStatistics={'permit': {key: 1}, 'notification': {key: 0}})
                with self.assertRaisesRegex(ValueError, 'integrity'):
                    self.m.validate_publication(Path(directory) / 'data', meta)

    def test_historical_window_must_use_separate_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'data'
            self.previous(target)
            with self.assertRaisesRegex(ValueError, 'range'):
                self.m.validate_publication(target, self.current(dateRange={'requestedStart': '2026-01-01', 'requestedEnd': '2026-10-03'}))

    def test_normal_daily_change_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'data'
            self.previous(target)
            self.m.validate_publication(target, self.current(recordCount=101, parcelCount=98))

    def test_committed_public_cache_revalidates_exact_id_timestamp_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(Path(directory) / 'private', offline=True)
            url = self.m.uldk_url('GetParcelById', PARCEL)
            evidence = {'url': url, 'downloadedAt': self.stamp(), 'text': TEXT, 'sha256': hashlib.sha256(TEXT.encode()).hexdigest()}
            cache = Path(directory) / 'public-evidence.json'
            cache.write_text(json.dumps({'schemaVersion': 1, 'responses': [evidence]}))
            self.assertEqual(client.seed_public_cache(cache), 1)
            self.assertEqual(client.text(url, lambda t: self.m.parse_uldk(t, PARCEL)), TEXT)
            self.assertEqual(client.entry(url)['downloadedAt'], evidence['downloadedAt'])

    def test_public_cache_never_accepts_private_raw_source_or_forged_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(Path(directory) / 'private', offline=True)
            cache = Path(directory) / 'public-evidence.json'
            good = {'url': self.m.uldk_url('GetParcelById', PARCEL), 'downloadedAt': self.stamp(), 'text': TEXT, 'sha256': hashlib.sha256(TEXT.encode()).hexdigest()}
            bad_entries = [dict(good, url=self.m.DOWNLOADS['permit']), dict(good, sha256='0' * 64), dict(good, downloadedAt=self.stamp(31)), dict(good, url=self.m.uldk_url('GetParcelById', '143206_5.0003.20/3')), dict(good, text='-1 service error', sha256=hashlib.sha256(b'-1 service error').hexdigest())]
            cache.write_text(json.dumps({'schemaVersion': 1, 'responses': bad_entries}))
            self.assertEqual(client.seed_public_cache(cache), 0)
            self.assertEqual(list((Path(directory) / 'private').rglob('*.json')), [])

    def test_public_cache_exports_only_allowlisted_verified_uldk_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.m.CachedHTTP(Path(directory) / 'private', retries=1)
            url = self.m.uldk_url('GetParcelById', PARCEL)
            with patch.object(self.m.requests, 'get', return_value=response(TEXT.encode())):
                client.text(url, lambda t: self.m.parse_uldk(t, PARCEL))
            output = Path(directory) / 'uldk-cache.json'
            client.export_public_cache(output, [url, self.m.DOWNLOADS['permit']])
            entries = json.loads(output.read_text())['responses']
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['text'], TEXT)
            self.assertEqual(entries[0]['sha256'], hashlib.sha256(TEXT.encode()).hexdigest())


    def args(self, directory):
        from argparse import Namespace
        return Namespace(since='2025-01-01', until='2026-10-03', cache=Path(directory) / 'private',
                         output=Path(directory) / 'data', uldk_public_cache=Path(directory) / 'uldk-cache.json',
                         refresh_sources=True, refresh=False, offline=False, workers=1, max_parcels=0)

    def test_private_source_cache_cannot_be_under_public_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(directory)
            args.cache = ROOT / 'public' / 'forbidden-cache'
            with patch.object(self.m, 'CachedHTTP', side_effect=AssertionError('privacy check must precede I/O')):
                with self.assertRaisesRegex(ValueError, 'private'):
                    self.m.run(args)

    def test_private_source_cache_cannot_be_under_custom_output(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(directory)
            args.cache = args.output / 'forbidden-cache'
            with patch.object(self.m, 'CachedHTTP', side_effect=AssertionError('privacy check must precede I/O')):
                with self.assertRaisesRegex(ValueError, 'private'):
                    self.m.run(args)

    def test_malformed_wkt_is_a_controlled_validation_failure(self):
        with self.assertRaises(ValueError):
            self.m.parse_uldk('0\nSRID=4326;POLYGON(INVALID)|' + PARCEL, PARCEL)

    def test_source_schema_failure_keeps_complete_previous_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(directory)
            self.previous(args.output)
            before = {p.name: p.read_bytes() for p in args.output.iterdir()}
            self.m.atomic_file(args.cache / 'broken.zip', b'test fixture only')
            client = self.m.CachedHTTP(args.cache)
            with patch.object(self.m, 'CachedHTTP', return_value=client), patch.object(client, 'text', return_value='0'), patch.object(client, 'download', return_value=args.cache / 'broken.zip'):
                with self.assertRaises(zipfile.BadZipFile):
                    self.m.run(args)
            self.assertEqual({p.name: p.read_bytes() for p in args.output.iterdir()}, before)

    def test_notification_unrecognized_status_cannot_publish_private_text(self):
        r = {'numer_ewidencyjny_system': 'TEST/N', 'data_wplywu_wniosku_do_urzedu': '2025-01-01',
             'terc': '1432065', 'jednostki_numer': '143206_5', 'obreb_numer': '0003', 'numer_dzialki': '20/2',
             'stan': 'PRIVATEPERSON SECRETNAME secret@example.test'}
        records, _ = self.m.normalize_rows([r], 'notification', '2025-01-01', '2026-10-03')
        self.assertNotIn('PRIVATEPERSON', records[0]['status'])
        self.assertNotIn('secret@', records[0]['status'])


if __name__ == '__main__':
    unittest.main()
