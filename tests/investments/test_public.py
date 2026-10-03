"""Offline public-only ingestion contracts; fixtures are official numeric tables."""
import importlib.util
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).parent / 'fixtures' / 'public'


class PublicContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            spec = importlib.util.find_spec('scripts.investment_sources.public')
        except ModuleNotFoundError:
            spec = None
        cls.module = __import__('scripts.investment_sources.public', fromlist=['public']) if spec else None

    def adapter(self):
        self.assertIsNotNone(self.module, 'public contribution adapter must exist')
        return self.module

    def test_complete_replacement_budget_totals_and_duplicate_named_lines(self):
        m = self.adapter()
        rows, coverage = m.parse_budget_tables(json.loads((FIX / '203516-tables.json').read_text()))
        self.assertEqual(len(rows), 119)
        self.assertEqual(coverage['annualPlanTotal'], 58525698.97)
        self.assertEqual(round(sum(r['amount'] for r in rows), 2), 58525698.97)
        self.assertEqual(len({r['key'] for r in rows}), 119)
        self.assertEqual(sum(r['title'] == 'Mazowsze bez smogu' for r in rows), 2)
        self.assertEqual(rows[0]['chapter'], '60016')
        self.assertIn('świetlną.', rows[0]['title'])
        self.assertEqual(next(r['amount'] for r in rows if r['title'].startswith('Budowa ulicy Kapuckiej')), 2500000)

    def test_budget_missing_or_corrupt_total_rejected(self):
        m = self.adapter()
        a = json.loads((FIX / '203516-tables.json').read_text())
        a[0]['rows'].pop(3)
        with self.assertRaises(ValueError):
            m.parse_budget_tables(a)

    def test_complete_wpf_capital_rows_limits_units_and_total(self):
        m = self.adapter()
        rows, coverage = m.parse_wpf_tables(json.loads((FIX / '203514-tables.json').read_text()))
        self.assertEqual(len(rows), 46)
        self.assertEqual(coverage['totalOutlay'], 168560681.59)
        self.assertEqual(coverage['annualLimits']['2026'], 39883527.39)
        r = next(r for r in rows if r['key'] == '1.3.2.32')
        self.assertEqual(r['amount'], 5000000)
        self.assertEqual(r['limits'][2027], 2500000)
        self.assertEqual(r['from'], 2026)
        self.assertEqual(r['to'], 2027)
        self.assertIn('Urząd Miejski', r['unit'])
        self.assertEqual(r['commitment'], 5000000)
        self.assertNotIn('1.3.1.1', {r['key'] for r in rows})

    def test_wpf_missing_right_hand_continuation_rejected(self):
        m = self.adapter()
        a = json.loads((FIX / '203514-tables.json').read_text())
        del a[1]
        with self.assertRaises(ValueError):
            m.parse_wpf_tables(a)

    def test_bo_only_explicit_markers_and_implementation_year(self):
        m = self.adapter()
        body = '''<h2 class="project-header">21. Renowacja placu zabaw</h2>
        <div class="box"><p class="title">Edycja</p><span>2026</span></div>
        <div class="box"><p class="title">Planowany koszt</p><span>38 000 zł</span></div>
        <input id="city_lat" value="52.21"><input id="city_lng" value="20.79">
        <input id="markers" value="52.220085,20.800388;52.22,20.81">'''
        result = {'status': 'Wybrany do realizacji', 'votes': 96, 'implementationYear': 2027}
        r = m.parse_bo_card(body, '33516', result, '2026-10-03T00:00:00Z')
        self.assertEqual(r['years'], [2026, 2027])
        self.assertEqual(r['status'], 'Wybrany do realizacji')
        self.assertEqual(r['geometries'][0]['geometry']['type'], 'MultiPoint')
        self.assertEqual(r['geometries'][0]['geometry']['coordinates'][0], [20.800388, 52.220085])
        r = m.parse_bo_card(body.replace('52.220085,20.800388;52.22,20.81', ''), '33516', result, '2026-10-03T00:00:00Z')
        self.assertEqual(r['geometries'], [])
        self.assertEqual(r['recordType'], 'proposal')

    def test_bo_malformed_marker_rejected(self):
        m = self.adapter()
        with self.assertRaises(ValueError):
            m.parse_bo_card('<h2 class="project-header">x</h2><input id="markers" value="52,20;broken">', '1', {}, '2026-10-03T00:00:00Z')

    def test_procurement_valid_terms_and_published_documents_no_build_completion(self):
        m = self.adapter()
        tid = 'ocds-148610-e75ac4dd-1c85-4c03-9ce9-e97e05e963cf'
        data = {'objectId': tid, 'title': 'Budowa ul. Kapuckiej', 'organizationName': 'Gmina Ożarów Mazowiecki', 'referenceNumber': 'RZP.271.37.2026', 'state': 'Agreement', 'stage': 'CompletedContract', 'cancellationDate': '2026-10-02T00:00:00Z', 'amountToFinanced': 4950000, 'isAmountToFinancedPublished': True, 'terms': [{'termType': 'SubmissionOffersDate', 'term': '2026-09-01T00:00:00Z', 'isValid': False}, {'termType': 'SubmissionOffersDate', 'term': '2026-09-02T00:00:00Z', 'isValid': True}]}
        docs = [{'objectId': 'doc1', 'name': 'SWZ', 'url': 'https://ezamowienia.gov.pl/document/1', 'publishedDate': '2026-08-01T00:00:00Z', 'tenderDocumentState': 'Published', 'deleteDate': None}, {'objectId': 'doc2', 'name': 'deleted', 'url': 'https://ezamowienia.gov.pl/document/2', 'tenderDocumentState': 'Published', 'deleteDate': '2026-08-02'}]
        data['initiationDate'] = '2026-08-13T10:00:00Z'
        r = m.parse_tender(data, docs, '2026-10-03T00:00:00Z')
        self.assertEqual([d['date'] for d in r['dates']], ['2026-08-13', '2026-09-02'])
        self.assertIsNone(r['statusAsOf'], 'initiation is not the date of the Agreement stage')
        self.assertEqual(len(r['events']), 1)
        self.assertEqual(r['costs'][0]['kind'], 'tender-financing')
        self.assertNotIn('ukończ', r['status'].lower())
        self.assertNotIn('unieważ', r['status'].lower())
        self.assertTrue(any('CompletedContract' in f['value'] for f in r['facts']))
        self.assertTrue(r['warnings'])

    def test_source_guards_retain_full_prior_and_old_fetch_timestamp(self):
        m = self.adapter()
        old = m.record('budget', 'old', 'https://example.org', 'old', '2026-09-30T00:00:00Z')
        prior = {'records': [old], 'sources': [{'id': 'budget', 'fetchedAt': old['fetchedAt'], 'sourceUpdatedAt': None}], 'warnings': [], 'schemaVersion': 1}
        out = m.collect(Path('.cache/test-public'), prior=prior, loaders={sid: (lambda: (_ for _ in ()).throw(ValueError('blocked'))) for sid in m.SOURCES})
        self.assertEqual(out['records'], [old])
        src = next(s for s in out['sources'] if s['id'] == 'budget')
        self.assertEqual(src['status'], 'retained')
        self.assertEqual(src['fetchedAt'], old['fetchedAt'])
        self.assertEqual(len(out['sources']), 5)

    def test_duplicate_and_loss_guard(self):
        m = self.adapter()
        old = [m.record('bo', str(n), 'https://example.org', str(n), '2026-10-01T00:00:00Z') for n in range(10)]
        with self.assertRaises(ValueError):
            m.guard('bo', old[:7], old)
        with self.assertRaises(ValueError):
            m.guard('bo', [old[0], old[0]], [])

    def test_guard_rejects_missing_required_fields_and_bad_source_urls(self):
        m = self.adapter()
        row = m.record('bo', '1', 'https://example.org', 'x', '2026-10-03T00:00:00Z')
        del row['facts']
        with self.assertRaises(ValueError):
            m.guard('bo', [row], [])
        row = m.record('bo', '1', 'https://example.org', 'x', '2026-10-03T00:00:00Z')
        row['facts'].append({'label': 'bad', 'value': 'x', 'sourceUrl': 'javascript:alert(1)'})
        with self.assertRaises(ValueError):
            m.guard('bo', [row], [])

    def test_all_official_bo_cards_results_counts_and_activity_semantics(self):
        from scripts.investment_sources import public_bo as bo
        results = bo.parse_bo_results((FIX / 'bo-results.html').read_text())
        cards = json.loads((FIX / 'bo-cards.json').read_text())
        rows = [bo.parse_bo_card(c['html'], c['id'], dict(results[c['id']], implementationYear=2027), '2026-10-03T00:00:00Z') for c in cards]
        self.assertEqual(len(rows), 30)
        self.assertEqual(sum(r['status'] == 'Wybrany do realizacji' for r in rows), 29)
        self.assertEqual(sum(bool(r['geometries']) for r in rows), 16)
        self.assertEqual(sum(1 if g['geometry']['type'] == 'Point' else len(g['geometry']['coordinates']) for r in rows for g in r['geometries']), 23)
        self.assertEqual(sum('nie budowa' in r['category'] for r in rows), 12)
        rejected = next(r for r in rows if r['sourceRecordId'] == '33432')
        self.assertEqual(rejected['status'], 'Niezakwalifikowany')
        self.assertEqual(rejected['years'], [2026])
        self.assertIsNone(rejected['costs'][0]['year'])

    def test_later_mayor_budget_change_rejects_current_plan(self):
        from scripts.investment_sources import public_finance as finance
        items = [{'id': '1', 'aliasFields': [{'alias': 'title', 'value': 'Zarządzenie w sprawie zmiany uchwały budżetowej'}, {'alias': 'lead', 'value': 'z dnia 25 września 2026 r.'}]}]
        with self.assertRaises(ValueError):
            finance.check_mayor_changes(items, '2026-09-24')
        self.assertEqual(finance.check_mayor_changes(items, '2026-09-26'), 1)

    def test_news_preserves_future_start_and_unknown_investor(self):
        from scripts.investment_sources.public_news import parse_news
        base = {'id': 1, 'link': 'https://ozarow-mazowiecki.pl/article', 'title': {'rendered': 'Roboty drogowe'}, 'content': {'rendered': '05.10.2026 1600 m'}, 'date_gmt': '2026-10-02T13:22:57', 'modified_gmt': '2026-10-02T13:22:57', 'slug': 'uwaga-roboty-drogowe-w-gm-ozarow-mazowiecki'}
        row = parse_news(base, '2026-10-03T00:00:00Z')
        self.assertEqual(row['investor'], 'county')
        self.assertEqual(row['dates'][0]['date'], '2026-10-05')
        self.assertIn('zapowiedziane', row['status'])
        base['slug'] = 'other'
        base['title']['rendered'] = 'Przebudowa autostrady A2'
        row = parse_news(base, '2026-10-03T00:00:00Z')
        self.assertEqual(row['investor'], 'unknown')
        self.assertIsNone(row['investorName'])

    def test_activity_is_not_classified_as_road_construction(self):
        m = self.adapter()
        for title in ['Edukacyjny Rajd Rowerowy pod tytułem Historia', 'Aktywizacja mieszkańców poprzez Ożarowską Ligę Darta', 'Aktywny Macierzysz', 'Plener rzeźbiarski']:
            body = '<h2 class="project-header">' + title + '</h2><div class="box"><p class="title">Edycja</p><span>2026</span></div>'
            r = m.parse_bo_card(body, '1', {}, '2026-10-03T00:00:00Z')
            self.assertIn('nie budowa', r['category'])

    def test_news_filter_excludes_sale_auctions_and_job_advertisements(self):
        from scripts.investment_sources import public_news as news
        self.assertFalse(news.relevant_title('Przetarg na sprzedaż nieruchomości'))
        self.assertFalse(news.relevant_title('Inspektor Nadzoru Budowlanego poszukuje kandydatów na stanowisko'))
        self.assertTrue(news.relevant_title('Rusza budowa ulicy Kapuckiej'))

    def test_office_tender_identity_links_are_discovered(self):
        import io
        import zipfile
        from scripts.investment_sources import public_procurement as proc
        tid = 'ocds-148610-c370b8b5-bddb-4f4d-bc80-d64c5b20b8a4'
        for extension, name in [('odt', 'content.xml'), ('docx', 'word/_rels/document.xml.rels')]:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as z:
                z.writestr(name, '<link target="https://ezamowienia.gov.pl/mp-client/search/list/' + tid + '"/>')
            self.assertIn(tid, proc.document_identity_text(buffer.getvalue(), extension))

    def test_pagination_total_truncation_and_repeated_page_fail_closed(self):
        m = self.adapter()
        class Client:
            def json(self, url):
                return {'total': 3, 'articles': [{'id': '1'}, {'id': '2'}]}
        with self.assertRaises(ValueError):
            m.list_articles(Client(), '23685')


if __name__ == '__main__':
    unittest.main()
