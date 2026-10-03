"""Fail-closed candidate validation and evidence/publication rollback (offline)."""
from argparse import Namespace
from contextlib import redirect_stdout
from copy import deepcopy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('publication_importer', ROOT / 'scripts/import_data.py')
PARCEL = '143206_5.0003.20/2'
TEXT = '0\nSRID=4326;POLYGON((20.8 52.2,20.81 52.2,20.81 52.21,20.8 52.2))|' + PARCEL


class PublicationSafety(unittest.TestCase):
    def setUp(self):
        assert SPEC is not None and SPEC.loader is not None
        self.m = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(self.m)
        self.candidate = {name: json.loads((ROOT / 'public/data' / name).read_text())
                          for name in ('permits.json', 'parcels.geojson', 'metadata.json')}
        self.candidate['parcels.geojson']['generatedAt'] = self.candidate['permits.json']['generatedAt']
        self.evidence = json.loads((ROOT / 'scripts/uldk-cache.json').read_text())

    def validate(self, candidate=None, evidence=None):
        validator = getattr(self.m, 'validate_artifacts', None)
        self.assertTrue(callable(validator), 'shared candidate validator must exist')
        assert callable(validator)
        publication_time = self.m.datetime.fromisoformat(self.candidate["metadata.json"]["generatedAt"].replace("Z", "+00:00")).timestamp()
        # Snapshot contracts must remain testable when real evidence later expires.
        # Ingestion/run tests independently exercise the live 30-day TTL.
        with patch.object(self.m.time, "time", return_value=publication_time):
            return validator(candidate or self.candidate, evidence=evidence or self.evidence)

    def rejects(self, mutate):
        candidate = deepcopy(self.candidate)
        mutate(candidate)
        with self.assertRaises(ValueError):
            self.validate(candidate)

    def test_real_candidate_passes_shared_validator(self):
        self.validate()

    def test_title_and_description_are_fixed_vocabulary(self):
        for field, value in [('title', 'Budowa dla UNKNOWNPERSON secret@example.test'),
                             ('title', 'Budowa — nieznany opis'), ('description', 'UNKNOWNPERSON')]:
            with self.subTest(field=field, value=value):
                self.rejects(lambda c: c['permits.json']['records'][0].__setitem__(field, value))

    def test_all_published_strings_reject_contact_identifiers(self):
        for field in ('locality', 'street', 'decisionNumber', 'category', 'status', 'geometryNote'):
            with self.subTest(field=field):
                self.rejects(lambda c: c['permits.json']['records'][0].__setitem__(field, 'secret@example.test'))
        self.rejects(lambda c: c['metadata.json']['warnings'].append('secret@example.test'))

    def test_allowlists_reject_extra_nested_fields(self):
        for mutate in [lambda c: c['permits.json']['records'][0].__setitem__('investor', 'PRIVATE'),
                       lambda c: c['parcels.geojson']['features'][0]['properties'].__setitem__('investor', 'PRIVATE'),
                       lambda c: c['metadata.json'].__setitem__('investor', 'PRIVATE'),
                       lambda c: c['permits.json']['source'].__setitem__('investor', 'PRIVATE'),
                       lambda c: c['parcels.geojson'].__setitem__('crs', {'name': 'EPSG:2180'})]:
            self.rejects(mutate)

    def test_unique_ids_and_unique_join_members(self):
        self.rejects(lambda c: c['permits.json']['records'].append(deepcopy(c['permits.json']['records'][0])))
        self.rejects(lambda c: c['parcels.geojson']['features'].append(deepcopy(c['parcels.geojson']['features'][0])))
        self.rejects(lambda c: c['parcels.geojson']['features'][0]['properties']['permitIds'].append(c['parcels.geojson']['features'][0]['properties']['permitIds'][0]))

    def test_joins_are_exact_in_both_directions(self):
        self.rejects(lambda c: c['parcels.geojson']['features'][0]['properties']['permitIds'].append('permit:unknown'))
        self.rejects(lambda c: c['parcels.geojson']['features'][0]['properties']['permitIds'].clear())
        self.rejects(lambda c: c['permits.json']['records'][0]['parcelIds'].append('143206_5.0003.999999'))

    def test_dates_kinds_and_field_types_are_strict(self):
        for field, value in [('kind', 'permit'), ('applicationDate', '2025-02-30'),
                             ('applicationDate', 20250101), ('decisionDate', 'yesterday'),
                             ('parcelIds', '143206_5.0003.20/2'), ('id', 'permit:wrong-kind')]:
            with self.subTest(field=field):
                self.rejects(lambda c: c['permits.json']['records'][0].__setitem__(field, value))

    def test_all_artifacts_require_same_generation_timestamp(self):
        self.rejects(lambda c: c['parcels.geojson'].pop('generatedAt'))
        for filename in ('permits.json', 'parcels.geojson', 'metadata.json'):
            self.rejects(lambda c: c[filename].__setitem__('generatedAt', '2026-10-01T00:00:00Z'))
        self.rejects(lambda c: [c[n].__setitem__('generatedAt', 'not-a-date') for n in c])

    def test_counts_and_coverage_sums_are_recomputed(self):
        for key in ('recordCount', 'parcelCount', 'matchedRecordCount', 'partialRecordCount',
                    'unresolvedRecordCount', 'publicEvidenceResponseCount'):
            with self.subTest(key=key):
                self.rejects(lambda c: c['metadata.json'].__setitem__(key, c['metadata.json'][key] + 1))
        for key in ('confirmedParcelCount', 'attemptedParcelCount', 'candidateParcelCount',
                    'failedParcelCount', 'freshParcelCount', 'unattemptedParcelCount'):
            with self.subTest(key=key):
                self.rejects(lambda c: c['metadata.json']['geometryCoverage'].__setitem__(key, c['metadata.json']['geometryCoverage'][key] + 1))
        self.rejects(lambda c: c['metadata.json']['kindCounts'].__setitem__('decision', 1))
        self.rejects(lambda c: c['metadata.json']['localityCounts'].__setitem__('Duchnice', 1))
        self.rejects(lambda c: c['metadata.json']['dateRange'].__setitem__('actualEnd', '2026-10-03'))

    def test_geometry_is_exact_valid_polygon_with_official_source(self):
        for mutate in [lambda c: c['parcels.geojson']['features'][0]['geometry'].__setitem__('type', 'Point'),
                       lambda c: c['parcels.geojson']['features'][0]['geometry'].__setitem__('coordinates', [[[52, 20], [53, 20], [53, 21], [52, 20]]]),
                       lambda c: c['parcels.geojson']['features'][0]['properties'].__setitem__('sourceUrl', 'https://example.test/'),
                       lambda c: c['parcels.geojson']['features'][0]['properties'].__setitem__('id', '143206_2.0003.20/2'),
                       lambda c: c['parcels.geojson']['features'][0]['geometry'].__setitem__('coordinates', [[[20.8, 52.2], [20.81, 52.2], [20.81, 52.21], [20.8, 52.2]]])]:
            self.rejects(mutate)

    def test_invalid_or_incomplete_evidence_cannot_prove_geometry(self):
        for field, value in [('sha256', '0' * 64), ('downloadedAt', '2020-01-01T00:00:00Z'),
                             ('text', TEXT + 'tampered')]:
            evidence = deepcopy(self.evidence)
            evidence['responses'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(evidence=evidence)
        evidence = deepcopy(self.evidence)
        evidence['responses'].pop()
        with self.assertRaises(ValueError):
            self.validate(evidence=evidence)

    def offline_args(self, directory):
        directory = Path(directory)
        args = Namespace(since='2025-01-01', until='2026-10-03', cache=directory / 'private',
                         output=directory / 'data', uldk_public_cache=directory / 'uldk-cache.json',
                         refresh=False, refresh_sources=False, offline=True, workers=1, max_parcels=0)
        client = self.m.CachedHTTP(args.cache, offline=True)
        for kind, url in self.m.DOWNLOADS.items():
            fields = sorted(self.m.REQUIRED_COLUMNS[kind])
            row = dict.fromkeys(fields, '')
            row.update(terc='1432065', miasto='Duchnice', obreb_numer='0003', numer_dzialki='20/2',
                       nazwa_zam_budowlanego='Budowa budynku')
            if kind == 'permit':
                row.update(numer_gunb='TEST/P', jednosta_numer_ew='143206_5', data_wplywu_wniosku='2025-01-09')
            else:
                row.update(numer_ewidencyjny_system='TEST/N', jednostki_numer='143206_5',
                           data_wplywu_wniosku_do_urzedu='2025-01-10', stan='Brak sprzeciwu')
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=fields, delimiter=';')
            writer.writeheader()
            writer.writerow(row)
            archive = args.cache / url.rsplit('/', 1)[-1]
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('fixture.csv', buffer.getvalue())
            evidence = dict(url=url, downloadedAt=self.m.utc_now(), sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                            byteCount=archive.stat().st_size, httpLastModified=None, httpETag=None)
            Path(str(archive) + '.evidence.json').write_text(json.dumps(evidence))
        replies = {self.m.uldk_url('GetCommuneById', unit, 'id,commune,county'):
                   '0\n143206_3|Ożarów Mazowiecki|powiat warszawski zachodni' for unit in self.m.UNITS}
        replies[self.m.uldk_url('GetRegionById', '143206_5.0003', 'id,region,commune')] = '0\n143206_5.0003|Duchnice|Ożarów Mazowiecki'
        replies[self.m.uldk_url('GetParcelById', PARCEL)] = TEXT
        entries = []
        for url, text in replies.items():
            entry = dict(url=url, downloadedAt=self.m.utc_now(), text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
            self.m.atomic_file(client.response_path(url), json.dumps(entry).encode())
            entries.append(entry)
        args.uldk_public_cache.write_text(json.dumps({'schemaVersion': 1, 'responses': entries[:2]}))
        self.m.atomic_publish(args.output, {name: {'previous': name} for name in self.candidate})
        # No regression baseline is needed for the deliberately tiny fixture.
        (args.output / 'metadata.json').write_text(json.dumps({'recordCount': 2, 'parcelCount': 1,
            'kindCounts': {'application': 1, 'notification': 1},
            'dateRange': {'requestedStart': args.since, 'requestedEnd': args.until}}))
        return args

    def snapshot(self, args):
        paths = [args.uldk_public_cache] + sorted(args.output.iterdir())
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    def run_offline(self, args):
        with redirect_stdout(io.StringIO()), patch.object(self.m.requests, 'get', side_effect=AssertionError('network forbidden')):
            return self.m.run(args)

    def test_run_rejects_malformed_candidate_before_export_or_publish(self):
        for fault in ('title', 'join'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                args = self.offline_args(directory)
                before = self.snapshot(args)
                original = self.m.attach_geometry
                def corrupt(records, geometries, errors):
                    features = original(records, geometries, errors)
                    if fault == 'title':
                        records[0]['title'] = 'secret@example.test'
                    else:
                        features[0]['properties']['permitIds'].append('permit:unknown')
                    return features
                with patch.object(self.m, 'attach_geometry', side_effect=corrupt), \
                     patch.object(self.m.CachedHTTP, 'export_public_cache', side_effect=AssertionError('must validate before export')):
                    with self.assertRaises(ValueError):
                        self.run_offline(args)
                self.assertEqual(self.snapshot(args), before)

    def test_publication_failure_rolls_back_old_evidence_and_three_files(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.offline_args(directory)
            before = self.snapshot(args)
            with patch.object(self.m, 'atomic_publish', side_effect=OSError('injected public commit failure')):
                with self.assertRaises(OSError):
                    self.run_offline(args)
            self.assertEqual(self.snapshot(args), before)

    def test_export_uses_staging_path_not_tracked_evidence_target(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.offline_args(directory)
            paths = []
            original = self.m.CachedHTTP.export_public_cache
            def track(client, path, urls):
                paths.append(Path(path))
                return original(client, path, urls)
            with patch.object(self.m.CachedHTTP, 'export_public_cache', new=track):
                metadata = self.run_offline(args)
            self.assertTrue(paths)
            self.assertNotIn(args.uldk_public_cache, paths)
            self.assertEqual(metadata['publicEvidenceResponseCount'], 4)
            published = json.loads((args.output / 'parcels.geojson').read_text())
            self.assertEqual(published.get('generatedAt'), metadata['generatedAt'])

    def test_dataset_is_staged_before_evidence_target_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.offline_args(directory)
            prior = args.uldk_public_cache.read_bytes()
            original = self.m.atomic_file
            writes = []
            def observe(path, content):
                if Path(path).name in self.candidate:
                    writes.append(Path(path))
                    self.assertEqual(args.uldk_public_cache.read_bytes(), prior,
                                     'all candidate JSON must be staged before evidence commit')
                return original(path, content)
            with patch.object(self.m, 'atomic_file', side_effect=observe):
                self.run_offline(args)
            self.assertEqual(len(writes), 3)
            self.assertTrue(all(path.parent != args.output for path in writes))

    def test_write_and_commit_failures_preserve_both_previous_states(self):
        for fault in ('evidence-stage', 'dataset-stage', 'cache-commit', 'public-after-commit'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                args = self.offline_args(directory)
                before = self.snapshot(args)
                atomic_file, replace, publish = self.m.atomic_file, self.m.os.replace, self.m.atomic_publish
                def fail_write(path, content):
                    path = Path(path)
                    if ((fault == 'evidence-stage' and path.name == args.uldk_public_cache.name and path != args.uldk_public_cache)
                        or (fault == 'dataset-stage' and path.name == 'permits.json')):
                        raise OSError('injected stage write failure')
                    return atomic_file(path, content)
                def fail_replace(src, dst):
                    if fault == 'cache-commit' and Path(dst) == args.uldk_public_cache:
                        raise OSError('injected evidence commit failure')
                    return replace(src, dst)
                def fail_publish(target, artifacts, **kwargs):
                    result = publish(target, artifacts, **kwargs)
                    if fault == 'public-after-commit' and Path(target) == args.output:
                        raise OSError('injected failure after public commit')
                    return result
                with patch.object(self.m, 'atomic_file', side_effect=fail_write), \
                     patch.object(self.m.os, 'replace', side_effect=fail_replace), \
                     patch.object(self.m, 'atomic_publish', side_effect=fail_publish):
                    with self.assertRaises(OSError):
                        self.run_offline(args)
                self.assertEqual(self.snapshot(args), before)


if __name__ == '__main__':
    unittest.main()
