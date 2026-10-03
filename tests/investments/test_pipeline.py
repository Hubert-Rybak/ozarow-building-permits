"""Aggregation/security/transaction contracts; adapter fixtures never ship to public/."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
STAMP = '2026-10-03T06:00:00Z'
URL = 'https://example.org/official'


def record(source='official', number='1', mapped=True):
    return dict(id=f'{source}:{number}', sourceId=source, sourceRecordId=number,
                sourceUrl=URL, title='Test-only official record', recordType='project',
                investor='municipal', investorName=None, category='', locality='', address='',
                status='', statusAsOf=None, summary='', years=[2026],
                costs=[dict(kind='reported', amount=None, currency='PLN', label='', year=None,
                            scope='local', sourceUrl=URL)], dates=[],
                geometries=[dict(type='Feature', geometry=dict(type='Point', coordinates=[20.8, 52.2]),
                    properties=dict(id='feature-1', accuracy='source-point', sourceUrl=URL,
                    parcelId=None, note='', fetchedAt=STAMP, sourceUpdatedAt=None))] if mapped else [],
                parcelIds=[], events=[], facts=[], relatedIds=[], warnings=[],
                fetchedAt=STAMP, sourceUpdatedAt=None)


def contribution(source='official', count=1):
    return dict(records=[record(source, str(i)) for i in range(count)], sources=[dict(
        id=source, name='Test-only source', url=URL, fetchedAt=STAMP, sourceUpdatedAt=None,
        status='fresh', coverage='Fixture only', recordCount=count, warnings=[], reuse='Facts only')], warnings=[])


class PipelineContract(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'scripts/import_investments.py').is_file(), 'Central importer not implemented')
        import import_investments
        import investment_validation
        self.pipeline = import_investments
        self.validator = investment_validation
        self.doc = self.pipeline.build_dataset([contribution()], generated_at=STAMP)

    def reject(self, mutate):
        doc = copy.deepcopy(self.doc)
        mutate(doc)
        with self.assertRaises(ValueError):
            self.validator.validate_dataset(doc)

    def test_exact_counts_inline_geometries_and_independent_generation(self):
        self.validator.validate_dataset(self.doc)
        self.assertEqual(self.doc['counts'], dict(records=1, mapped=1, geometries=1, bySource={'official': 1}))
        self.assertNotEqual(self.doc['generatedAt'], json.loads((ROOT / 'public/data/permits.json').read_text())['generatedAt'])

    def test_merge_is_deterministic(self):
        a, b = contribution('a', 2), contribution('b', 2)
        a['records'].reverse()
        one = self.pipeline.build_dataset([a, b], generated_at=STAMP)
        two = self.pipeline.build_dataset([b, a], generated_at=STAMP)
        self.assertEqual(one, two)

    def test_unknown_or_missing_keys_rejected_at_every_nested_level(self):
        targets = [lambda d: d, lambda d: d['records'][0], lambda d: d['sources'][0],
                   lambda d: d['counts'], lambda d: d['records'][0]['costs'][0],
                   lambda d: d['records'][0]['geometries'][0],
                   lambda d: d['records'][0]['geometries'][0]['geometry'],
                   lambda d: d['records'][0]['geometries'][0]['properties']]
        for target in targets:
            for action in ('extra', 'missing'):
                with self.subTest(target=targets.index(target), action=action):
                    def mutate(d):
                        obj = target(d)
                        if action == 'extra': obj['Editor'] = 'forbidden'
                        else: del obj[next(iter(obj))]
                    self.reject(mutate)
        for key, entry in [('dates', dict(kind='start', date='2026-10-03', label='', sourceUrl=URL)),
                           ('events', dict(id='event', title='', date=None, sourceUrl=URL)),
                           ('facts', dict(label='', value='', sourceUrl=URL))]:
            for action in ('extra', 'missing'):
                def mutate(d):
                    obj = dict(entry)
                    if action == 'extra': obj['email'] = 'not-published'
                    else: del obj[next(iter(obj))]
                    d['records'][0][key] = [obj]
                self.reject(mutate)

    def test_strict_scalar_list_and_enum_types(self):
        for key, value in [('title', None), ('id', ''), ('recordType', 'construction'),
                           ('investor', 'developer'), ('years', [True]), ('years', [2026.0]),
                           ('parcelIds', [1]), ('warnings', 'warning'), ('relatedIds', {})]:
            with self.subTest(key=key, value=value):
                self.reject(lambda d: d['records'][0].__setitem__(key, value))
        for key, value in [('schemaVersion', True), ('generatedAt', None), ('warnings', [None])]:
            self.reject(lambda d: d.__setitem__(key, value))
        for value in ('unknown', None):
            self.reject(lambda d: d['sources'][0].__setitem__('status', value))
        self.reject(lambda d: d['counts'].__setitem__('records', True))
        self.reject(lambda d: d['records'][0]['costs'][0].__setitem__('scope', 'municipality'))

    def test_costs_are_finite_nonnegative_or_null(self):
        for value in (-1, float('nan'), float('inf'), True, '123'):
            with self.subTest(value=value):
                self.reject(lambda d: d['records'][0]['costs'][0].__setitem__('amount', value))
        for value in (None, 0, 123.45):
            d = copy.deepcopy(self.doc)
            d['records'][0]['costs'][0]['amount'] = value
            self.validator.validate_dataset(d)

    def test_dates_are_real_and_timestamps_timezone_aware(self):
        for value in ('2026-02-30', '2026-1-01', '2026', STAMP):
            self.reject(lambda d: d['records'][0].__setitem__('statusAsOf', value))
        for value in ('2026-10-03', '2026-10-03T06:00:00', '2026-02-30T00:00:00Z', 'garbage'):
            self.reject(lambda d: d['records'][0].__setitem__('fetchedAt', value))
        self.reject(lambda d: d.__setitem__('generatedAt', '2026-10-03T06:00:00+02:00'))
        self.reject(lambda d: d['records'][0].__setitem__('events', [dict(id='e', title='', date='2026-02-30', sourceUrl=URL)]))
        self.reject(lambda d: d['records'][0].__setitem__('dates', [dict(kind='', label='', date='2026', sourceUrl=URL)]))

    def test_every_url_field_rejects_unsafe_userinfo_and_secrets(self):
        setters = [lambda d,v: d['sources'][0].__setitem__('url',v),
                   lambda d,v: d['records'][0].__setitem__('sourceUrl',v),
                   lambda d,v: d['records'][0]['costs'][0].__setitem__('sourceUrl',v),
                   lambda d,v: d['records'][0]['geometries'][0]['properties'].__setitem__('sourceUrl',v)]
        for setter in setters:
            for value in ('javascript:alert(1)', '//example.org/a', 'https://user:pass@example.org',
                          'https://example.org/?token=secret', 'https://example.org/?api_key=secret',
                          'https://example.org/#access_token=secret', 'https://example.org/\npath',
                          'https://example.org/%0Apath', 'https://example.org:invalid/path'):
                with self.subTest(url=value):
                    self.reject(lambda d: setter(d,value))

    def test_geometries_reject_invalid_coordinates_and_topology(self):
        invalid = [dict(type='Point', coordinates=[181,52]), dict(type='Point', coordinates=[20,91]),
                   dict(type='Point', coordinates=[True,52]), dict(type='Point', coordinates=[20,float('nan')]),
                   dict(type='Point', coordinates=[20,52,2]), dict(type='MultiPoint',coordinates=[]),
                   dict(type='LineString',coordinates=[[20,52]]),
                   dict(type='Polygon',coordinates=[[[20,52],[21,53],[20,53],[21,52],[20,52]]]),
                   dict(type='Polygon',coordinates=[[[20,52],[21,52],[21,53],[20,53]]]),
                   dict(type='GeometryCollection',geometries=[])]
        for value in invalid:
            with self.subTest(geometry=value):
                self.reject(lambda d: d['records'][0]['geometries'][0].__setitem__('geometry', value))
        self.reject(lambda d: d['records'][0]['geometries'][0]['properties'].__setitem__('accuracy','guessed'))

    def test_all_six_geojson_types_supported(self):
        ring = [[20,52],[21,52],[21,53],[20,52]]
        for kind, coords in [('Point',[20,52]), ('MultiPoint',[[20,52],[21,53]]),
                             ('LineString',[[20,52],[21,53]]), ('MultiLineString',[[[20,52],[21,53]]]),
                             ('Polygon',[ring]), ('MultiPolygon',[[ring]])]:
            doc = copy.deepcopy(self.doc)
            doc['records'][0]['geometries'][0]['geometry'] = dict(type=kind, coordinates=coords)
            self.validator.validate_dataset(doc)

    def test_unique_global_record_and_source_ids_and_feature_ids_within_record(self):
        self.reject(lambda d: d['records'].append(copy.deepcopy(d['records'][0])))
        self.reject(lambda d: d['sources'].append(copy.deepcopy(d['sources'][0])))
        def duplicate(d):
            d['records'][0]['geometries'].append(copy.deepcopy(d['records'][0]['geometries'][0]))
            d['counts']['geometries'] = 2
        self.reject(duplicate)
        # The same source feature ID can occur in distinct records.
        self.pipeline.build_dataset([contribution(count=2)], generated_at=STAMP)

    def test_joins_source_record_counts_and_dataset_counts_exact(self):
        self.reject(lambda d: d['records'][0].__setitem__('sourceId','missing'))
        self.reject(lambda d: d['sources'][0].__setitem__('recordCount',2))
        for key in ('records','mapped','geometries'):
            self.reject(lambda d: d['counts'].__setitem__(key,10))
        self.reject(lambda d: d['counts']['bySource'].__setitem__('official',2))
        self.reject(lambda d: d['counts']['bySource'].__setitem__('extra',0))
        self.reject(lambda d: d['records'][0].__setitem__('relatedIds',['missing']))
        self.reject(lambda d: d['records'][0].__setitem__('relatedIds',['official:0']))
        doc = contribution(count=2)
        doc['records'][0]['relatedIds'] = ['official:1']
        self.pipeline.build_dataset([doc],generated_at=STAMP)

    def test_parcel_ids_remain_literal_and_features_join_declared_parcels(self):
        for value in ('143206_5.001.1', '143206_2.0001.1', '143206_5.0001.1/2bad'):
            self.reject(lambda d: d['records'][0].__setitem__('parcelIds',[value]))
        self.reject(lambda d: d['records'][0]['geometries'][0]['properties'].__setitem__('parcelId','143206_5.0001.1'))

    def test_source_specific_loss_guard_cannot_hide_in_total_growth(self):
        prior = self.pipeline.build_dataset([contribution('a',10),contribution('b',1)],generated_at=STAMP)
        with self.assertRaises(ValueError):
            self.pipeline.build_dataset([contribution('a',7),contribution('b',100)],generated_at=STAMP,prior=prior)
        self.pipeline.build_dataset([contribution('a',8),contribution('b',1)],generated_at=STAMP,prior=prior)
        with self.assertRaises(ValueError):
            self.pipeline.build_dataset([contribution('b',1)],generated_at=STAMP,prior=prior)

    def test_source_geometry_loss_guard(self):
        prior = self.pipeline.build_dataset([contribution(count=10)],generated_at=STAMP)
        fresh = contribution(count=10)
        for rec in fresh['records'][:3]: rec['geometries'] = []
        with self.assertRaises(ValueError):
            self.pipeline.build_dataset([fresh],generated_at=STAMP,prior=prior)

    def test_optional_failure_must_be_explicit_unavailable_or_exact_retention(self):
        fresh = contribution(count=0)
        with self.assertRaises(ValueError): self.pipeline.build_dataset([fresh],generated_at=STAMP)
        fresh['sources'][0].update(status='unavailable',fetchedAt=None,warnings=['Unavailable source'])
        self.pipeline.build_dataset([fresh],generated_at=STAMP)
        prior = self.doc
        with self.assertRaises(ValueError): self.pipeline.build_dataset([fresh],generated_at=STAMP,prior=prior)
        retained = contribution()
        retained['sources'][0].update(status='retained',warnings=['Previous verified snapshot retained'])
        self.pipeline.build_dataset([retained],generated_at=STAMP,prior=prior)
        retained['records'][0]['title'] = 'Unverified alteration'
        with self.assertRaises(ValueError): self.pipeline.build_dataset([retained],generated_at=STAMP,prior=prior)

    def test_unavailable_and_retained_cannot_hide_warning_or_records(self):
        self.reject(lambda d: d['sources'][0].__setitem__('status','unavailable'))
        self.reject(lambda d: d['sources'][0].__setitem__('status','retained'))
        self.reject(lambda d: d['sources'][0].__setitem__('fetchedAt',None))

    def test_contribution_extra_fields_and_duplicate_sources_rejected(self):
        c = contribution()
        c['cookies'] = 'forbidden'
        with self.assertRaises(ValueError): self.pipeline.build_dataset([c],generated_at=STAMP)
        with self.assertRaises(ValueError): self.pipeline.build_dataset([contribution(), contribution()],generated_at=STAMP)

    def test_atomic_refresh_passes_full_prior_and_preserves_other_data_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / 'data'
            output.mkdir()
            (output / 'permits.json').write_text('unchanged GUNB')
            (output / 'investments.json').write_text(json.dumps(self.doc))
            seen = []
            def collect(cache,prior=None):
                seen.append((cache,prior))
                return contribution()
            result = self.pipeline.refresh(output,root/'cache',adapters=[collect],generated_at=STAMP)
            self.assertEqual(seen[0][1], self.doc)
            self.assertIsInstance(seen[0][0],Path)
            self.assertEqual(json.loads((output/'investments.json').read_text()),result)
            self.assertEqual((output/'permits.json').read_text(),'unchanged GUNB')
            self.assertEqual(set(p.name for p in output.iterdir()),{'permits.json','investments.json'})

    def test_invalid_adapter_write_and_replace_failure_preserve_old_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / 'data'
            output.mkdir()
            target = output/'investments.json'
            original = json.dumps(self.doc).encode()
            target.write_bytes(original)
            def bad(cache,prior=None):
                c = contribution()
                c['records'][0]['costs'][0]['amount'] = -1
                return c
            with self.assertRaises(ValueError): self.pipeline.refresh(output,root/'cache',adapters=[bad],generated_at=STAMP)
            self.assertEqual(target.read_bytes(),original)
            for boundary in ('os.fsync','os.replace'):
                with patch('import_investments.'+boundary,side_effect=OSError('injected')):
                    with self.assertRaises(OSError):
                        self.pipeline.refresh(output,root/'cache',adapters=[lambda cache,prior=None: contribution()],generated_at=STAMP)
                self.assertEqual(target.read_bytes(),original)
                self.assertEqual(list(output.iterdir()),[target])

    def test_explicit_prior_survives_gunb_directory_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prior = root/'prior-investments.json'
            prior.write_text(json.dumps(self.doc))
            seen = []
            def collect(cache,prior=None):
                seen.append(prior)
                return contribution()
            self.pipeline.refresh(root/'candidate',root/'cache',adapters=[collect],generated_at=STAMP,prior_path=prior)
            self.assertEqual(seen,[self.doc])

    def test_invalid_prior_fails_before_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); output=root/'data'; output.mkdir()
            target=output/'investments.json'; target.write_text('{"schemaVersion":1}')
            called=[]
            with self.assertRaises(ValueError):
                self.pipeline.refresh(output,root/'cache',adapters=[lambda cache,prior=None: called.append(1)])
            self.assertEqual(called,[])
            self.assertEqual(target.read_text(),'{"schemaVersion":1}')

    def test_cache_rejects_repo_public_output_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for cache in (ROOT/'.cache/investments-test', root/'data/cache'):
                with self.assertRaises(ValueError):
                    self.pipeline.refresh(root/'data',cache,adapters=[lambda cache,prior=None: contribution()],generated_at=STAMP)
            link=root/'link'; link.symlink_to(ROOT)
            with self.assertRaises(ValueError):
                self.pipeline.refresh(root/'data',link/'cache',adapters=[lambda cache,prior=None: contribution()],generated_at=STAMP)

    def test_missing_production_adapters_fail_closed(self):
        with patch('import_investments.importlib.import_module',side_effect=ModuleNotFoundError('adapter missing')):
            with self.assertRaises(RuntimeError): self.pipeline.load_adapters()

    def test_urls_for_dates_events_facts_reject_credentials(self):
        for key, entry in [('dates', dict(kind='start', date='2026-10-03', label='', sourceUrl=URL)),
                           ('events', dict(id='event', title='', date=None, sourceUrl=URL)),
                           ('facts', dict(label='', value='', sourceUrl=URL))]:
            for url in ('https://example.org/?auth=secret', 'https://example.org/?X-Amz-Signature=secret',
                        'https://example.org/?session_token=secret', 'https://example.org/?client_secret=secret'):
                with self.subTest(key=key,url=url):
                    def mutate(d):
                        obj=dict(entry); obj['sourceUrl']=url; d['records'][0][key]=[obj]
                    self.reject(mutate)

    def test_extremely_large_cost_is_controlled_validation_failure(self):
        self.reject(lambda d: d['records'][0]['costs'][0].__setitem__('amount', 10**1000))

    def test_adapter_exception_and_all_unavailable_preserve_old_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); output=root/'data'; output.mkdir()
            target=output/'investments.json'; original=json.dumps(self.doc); target.write_text(original)
            def fail(cache,prior=None): raise RuntimeError('Source retrieval failed')
            with self.assertRaises(RuntimeError): self.pipeline.refresh(output,root/'cache',adapters=[fail])
            self.assertEqual(target.read_text(),original)
            target.unlink()
            unavailable=contribution(count=0)
            unavailable['sources'][0].update(status='unavailable',fetchedAt=None,warnings=['Unavailable'])
            with self.assertRaises(ValueError):
                self.pipeline.refresh(output,root/'cache',adapters=[lambda cache,prior=None: unavailable])
            self.assertFalse(target.exists())

    def test_atomic_readback_validation_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); output=root/'data'; output.mkdir()
            target=output/'investments.json'; original=json.dumps(self.doc); target.write_text(original)
            real_load=self.pipeline.load_dataset
            def reject_candidate(path,prior=None):
                if path.name.endswith('.candidate'): raise ValueError('Invalid serialized candidate')
                return real_load(path,prior=prior)
            with patch('import_investments.load_dataset',side_effect=reject_candidate):
                with self.assertRaises(ValueError):
                    self.pipeline.refresh(output,root/'cache',adapters=[lambda cache,prior=None: contribution()])
            self.assertEqual(target.read_text(),original)
            self.assertEqual(list(output.iterdir()),[target])

    def test_json_duplicate_keys_and_nonfinite_literals_rejected(self):
        for text in ('{"schemaVersion":1,"schemaVersion":1}', '{"amount":NaN}', '{"amount":Infinity}'):
            with self.assertRaises(ValueError): self.validator.loads(text)


if __name__ == '__main__':
    unittest.main()
