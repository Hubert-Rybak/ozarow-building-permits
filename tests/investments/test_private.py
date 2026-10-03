"""Offline behavior gates for the private contribution (no network)."""
import copy
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))


def module():
    try:
        return importlib.import_module('investment_sources.private')
    except ModuleNotFoundError:
        return None


STAMP = '2026-10-03T10:00:00+00:00'
POLYGON = '0\nSRID=4326;POLYGON((20.8 52.2,20.801 52.2,20.801 52.201,20.8 52.2))|143206_5.0005.44/2'


def workbook(rows):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    from xml.sax.saxutils import escape
    header = {'A': 'Nazwa projektu', 'C': 'Numer umowy/decyzji', 'D': 'Nazwa beneficjenta', 'I': 'Program', 'L': 'Wartość projektu', 'M': 'Poziom unijnego dofinansowania w procentach', 'N': 'Dofinansowanie z UE', 'P': 'Miejsce realizacji projektu', 'Q': 'Data rozpoczęcia projektu', 'R': 'Data zakończenia projektu'}
    xml = f'<worksheet xmlns="{ns}"><sheetData>'
    allrows = [{'A': 'stan na 30 września 2026 roku'}, header] + rows
    for n, row in enumerate(allrows, 1):
        xml += f'<row r="{n}">'
        for col, v in row.items():
            xml += f'<c r="{col}{n}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
        xml += '</row>'
    xml += '</sheetData></worksheet>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}"><sheets><sheet name="Lista projektów 2021-2027" sheetId="1"/></sheets></workbook>')
        z.writestr('xl/worksheets/sheet1.xml', xml)
    return out.getvalue()


class PrivateTests(unittest.TestCase):
    def setUp(self):
        self.p = module()
        self.assertIsNotNone(self.p, 'Missing private investment adapter')

    def test_exact_parcel_reply(self):
        g = self.p.validate_parcel_reply(POLYGON, '143206_5.0005.44/2')
        self.assertEqual(g['type'], 'Polygon')

    def test_reject_bad_geometry_identity_srid_status(self):
        for bad in [POLYGON.replace('44/2', '44/3'), POLYGON.replace('4326', '2180'), POLYGON.replace('0\n', '-1\n'), POLYGON.replace('POLYGON((20.8 52.2,20.801 52.2,20.801 52.201,20.8 52.2))', 'POLYGON EMPTY'), POLYGON + '\n' + POLYGON.split('\n')[1]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.p.validate_parcel_reply(bad, '143206_5.0005.44/2')

    def test_no_malformed_region_repair(self):
        for region in ['001', '011', '003', '00005']:
            with self.assertRaises(ValueError):
                self.p.parcel_id('143206_5', region, '44/2')

    def test_region_exact_municipality(self):
        self.p.validate_region_reply('0\n143206_5.0005|Jawczyce|Ożarów Mazowiecki\n', '143206_5.0005')
        for bad in ['0\n143206_5.0006|Jawczyce|Ożarów Mazowiecki', '0\n143206_5.0005|Jawczyce|Warszawa', '-1 brak wyników']:
            with self.assertRaises(ValueError):
                self.p.validate_region_reply(bad, '143206_5.0005')

    def test_fe_exact_implementation_not_headquarters(self):
        local = {'A':'Projekt', 'C':'FENG.01-X/26','D':'Spółka Ożarów Mazowiecki','I':'FENG','L':'100.000000000001','N':'50','P':'WOJ.: MAZOWIECKIE, POW.: warszawski zachodni, GM.: Ożarów Mazowiecki | WOJ.: MAZOWIECKIE, GM.: Warszawa','Q':'45536.083333333336','R':'46752.999988425923'}
        headquarters = dict(local, C='OTHER', P='GM.: Warszawa')
        wrong = dict(local, C='WRONG', P='GM.: Ożarów Mazowiecki Zachodni')
        rows, snapshot, stats = self.p.parse_fe_xlsx(workbook([local, headquarters, wrong]), 'https://example.org/a.xlsx', STAMP)
        self.assertEqual(len(rows), 1)
        self.assertEqual(snapshot, '2026-09-30')
        self.assertEqual(rows[0]['sourceRecordId'], 'FENG.01-X/26')
        self.assertEqual(rows[0]['costs'][0]['amount'], float(local['L']))
        self.assertTrue(all(c['scope']=='multi-municipality' for c in rows[0]['costs']))
        self.assertEqual(rows[0]['geometries'], [])
        self.assertEqual(rows[0]['dates'][0]['date'], '2024-09-01')
        self.assertTrue(any(c['kind']=='eligible' and c['amount'] is None for c in rows[0]['costs']))
        self.assertNotIn('Project summary', rows[0]['summary'])

    def test_fe_duplicate_contract_refuses_snapshot(self):
        row = {'A':'Projekt', 'C':'X','D':'Firma','I':'Program','L':'100','N':'10','P':'GM.: Ożarów Mazowiecki','Q':'45536','R':'46752'}
        with self.assertRaises(ValueError):
            self.p.parse_fe_xlsx(workbook([row,row]), 'https://example.org/a.xlsx', STAMP)

    def test_fe_bad_schema_refuses_snapshot(self):
        with self.assertRaises(ValueError):
            self.p.parse_fe_xlsx(b'not a ZIP', 'https://example.org/a.xlsx', STAMP)

    def test_environment_groups_publications_keeps_event_chronology(self):
        path = ROOT / 'tests/investments/fixtures/private_environment.json'
        ds = json.loads(path.read_text())
        records = self.p.parse_environment(ds, STAMP)
        self.assertEqual(len(records), 2)
        ajs = next(r for r in records if r['investorName'] and 'AJS' in r['investorName'])
        self.assertEqual([e['date'] for e in ajs['events']], ['2026-06-10','2026-07-16'])
        self.assertEqual(len(ajs['parcelIds']), 6)
        self.assertNotIn('budowa rozpoczęta', ajs['status'])
        energy = next(r for r in records if '147/8' in r['title'])
        self.assertIn('2026-09-17',[d['date'] for d in energy['dates']])
        self.assertEqual(energy['statusAsOf'],'2026-09-17')

    def test_retention_loss_duplicate_failure_and_prior_full_dataset(self):
        prior = {'records':[{'id':f'environmental:{n}','sourceId':'environmental','fetchedAt':STAMP} for n in range(10)], 'sources':[{'id':'environmental','fetchedAt':STAMP,'sourceUpdatedAt':None}]}
        for candidate in [prior['records'][:7], [prior['records'][0]]*10, None]:
            records, source, warnings = self.p.guard_source('environmental', candidate, self.p.source_meta('environmental'), prior, 'test failure' if candidate is None else None)
            self.assertEqual(records,prior['records'])
            self.assertEqual(source['status'],'retained')
            self.assertEqual(source['fetchedAt'],STAMP)
            self.assertTrue(warnings)

    def test_cached_geometry_never_restamps_original_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.p.Fetcher(Path(tmp))
            url = 'https://example.org/parcel'
            f.store(url, POLYGON.encode(), STAMP)
            b,t,h = f.get(url, ttl_days=30)
            self.assertEqual(t,STAMP)
            self.assertEqual(b,POLYGON.encode())
            self.assertEqual(len(h),64)

    def test_collect_independent_failures_returns_exact_api(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(self.p, 'collect_environment', side_effect=ValueError('schema')), patch.object(self.p, 'collect_private', side_effect=ValueError('schema')), patch.object(self.p, 'collect_regional', side_effect=ValueError('schema')), patch.object(self.p, 'collect_eu', side_effect=ValueError('schema')):
            result = self.p.collect(Path(tmp))
            self.assertEqual(set(result), {'records','sources','warnings'})
            self.assertEqual(len(result['sources']),4)
            self.assertTrue(all(s['status']=='unavailable' for s in result['sources']))

    def test_public_record_exact_allowlist_and_no_technical_contacts(self):
        r = self.p.new_record('private-projects','x','https://example.org/x','Projekt',STAMP)
        self.assertEqual(set(r),set('id sourceId sourceRecordId sourceUrl title recordType investor investorName category locality address status statusAsOf summary years costs dates geometries parcelIds events facts relatedIds warnings fetchedAt sourceUpdatedAt'.split()))

    def test_nested_invalid_candidate_retains_prior(self):
        good = self.p.new_record('environmental','x','https://example.org/x','Projekt',STAMP)
        prior = {'records':[good], 'sources':[self.p.source_meta('environmental')]}
        for bad in [dict(good,years=['2026']), dict(good,sourceUrl='javascript:alert(1)'), dict(good,statusAsOf='2026-02-30'), dict(good,costs=[{'kind':'reported','amount':float('nan'),'currency':'PLN','label':'Koszt','year':None,'scope':'local','sourceUrl':'https://example.org/x'}])]:
            with self.subTest(bad=bad):
                records,source,warnings = self.p.guard_source('environmental',[bad],self.p.source_meta('environmental'),prior)
                self.assertEqual(records,[good])
                self.assertEqual(source['status'],'retained')
                self.assertTrue(warnings)

    def test_environment_preserves_detail_receipts_and_edited_date(self):
        ds = json.loads((ROOT / 'tests/investments/fixtures/private_environment.json').read_text())
        for d in ds:
            d['_fetchedAt'] = '2026-10-03T09:00:00+00:00'
            d['basicData']['originActive'] = d['basicData']['active']
        ds[0]['basicData']['originActive'] = '2026-09-01 10:00:00'
        records = self.p.parse_environment(ds, STAMP)
        self.assertTrue(all(r['fetchedAt']=='2026-10-03T09:00:00+00:00' for r in records))
        energy = next(r for r in records if '147/8' in r['title'])
        self.assertEqual(energy['sourceUpdatedAt'],'2026-09-18T09:17:56+00:00')

    def test_fe_own_concise_description_and_explicit_investor_type(self):
        row = {'A':'HyperPIC','B':'A protected long description must not be mirrored', 'C':'FENG.02.10-IP.01-0005/23','D':'VIGO Photonics Spółka Akcyjna','I':'FENG','L':'100','N':'10','P':'GM.: Ożarów Mazowiecki','Q':'45536','R':'46752'}
        records,_,_ = self.p.parse_fe_xlsx(workbook([row]),'https://example.org/a.xlsx',STAMP)
        self.assertEqual(records[0]['investor'],'private')
        self.assertIn('średniej podczerwieni',records[0]['summary'])
        self.assertNotIn(row['B'],json.dumps(records[0]))

    def test_county_missing_intermediate_is_verified_not_tls_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.p.Fetcher(Path(tmp))
            self.assertTrue(callable(getattr(f, 'pwz_ca_bundle', None)))
            # The method must verify the issuer against the existing trust roots.
            import inspect
            body = inspect.getsource(f.pwz_ca_bundle)
            self.assertIn('verify',body)
            self.assertNotIn('verify=False',body)

    def test_official_unit_reply_includes_literal_county_prefix(self):
        self.p.validate_unit_reply('0\n143206_3|Ożarów Mazowiecki|powiat warszawski zachodni\n')
        with self.assertRaises(ValueError):
            self.p.validate_unit_reply('0\n143206_3|Ożarów Mazowiecki|powiat pruszkowski\n')

    def test_fe_actual_download_button_data_url(self):
        page = '<button data-filename="Lista_projektow_FE_2021_2027_30092026.xlsx" data-url="/wp-content/uploads/2026/10/Lista_projektow_FE_2021_2027_30092026-1.xlsx">pobierz</button>'
        self.assertTrue(self.p.discover_fe_link(page).endswith('30092026-1.xlsx'))

    def test_xlsx_link_discovery_not_guessed_path(self):
        html = '<a href="/wp-content/uploads/2026/10/Lista_projektow_FE_2021_2027_30092026-1.xlsx">X</a>'
        self.assertEqual(self.p.discover_fe_link(html), 'https://funduszeeuropejskie.gov.pl/wp-content/uploads/2026/10/Lista_projektow_FE_2021_2027_30092026-1.xlsx')
        with self.assertRaises(ValueError):
            self.p.discover_fe_link('<p>Brak pliku</p>')


if __name__ == '__main__':
    unittest.main()
