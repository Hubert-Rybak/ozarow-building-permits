"""Regression gates: publication/edit and immutable per-response receipts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from investment_sources import public, public_finance, public_procurement, public_bo, public_news, private

FIX = Path(__file__).parent / 'fixtures' / 'public'
START = '2026-10-03T08:00:00Z'
FIRST = '2026-10-03T09:00:00Z'
SECOND = '2026-10-03T10:00:00Z'
LAST = '2026-10-03T11:00:00Z'


class Reply:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}
        self.content = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
        self.text = self.content.decode()

    def json(self):
        return copy.deepcopy(self.payload)

    def raise_for_status(self):
        pass


class ProvenanceTests(unittest.TestCase):
    def test_actual_tender_initiation_is_not_source_edit(self):
        tid = 'ocds-148610-c370b8b5-bddb-4f4d-bc80-d64c5b20b8a4'
        data = json.loads((FIX / ('ezam-' + tid + '.json')).read_text())
        docs = json.loads((FIX / ('ezam-docs-' + tid + '.json')).read_text())
        row = public_procurement.parse_tender(data, docs, LAST)
        self.assertIsNone(row['sourceUpdatedAt'])
        self.assertIn(data['initiationDate'][:10], [d['date'] for d in row['dates']])
        for state in ('Initiated', 'Agreement'):
            row = public_procurement.parse_tender(dict(data, state=state), docs, LAST)
            self.assertIsNone(row['sourceUpdatedAt'])
            self.assertEqual(row['statusAsOf'], data['initiationDate'][:10] if state == 'Initiated' else None)

    def test_earlier_environment_edit_survives_later_unmodified_decision(self):
        details = [
            {'id': '95482', 'title': 'Obwieszczenie o wszczęciu', 'link': 'a,95482.html', 'basicData': {'originActive': '2026-05-06 10:44:20', 'active': '2026-05-06 10:47:13', 'modify': None}, 'attachments': [], '_fetchedAt': FIRST},
            {'id': '96020', 'title': 'Obwieszczenie o wydaniu decyzji z dnia 17 września 2026 dla przedsięwzięcia', 'link': 'a,96020.html', 'basicData': {'originActive': '2026-09-18 11:00:00', 'active': '2026-09-18 11:00:00', 'modify': None}, 'attachments': [], '_fetchedAt': SECOND}]
        row, = private.parse_environment(details, START)
        self.assertEqual(row['sourceUpdatedAt'], '2026-05-06T08:47:13+00:00')
        self.assertEqual(row['statusAsOf'], '2026-09-17')
        self.assertEqual(row['fetchedAt'], SECOND)
        self.assertIn('2026-09-18', [d['date'] for d in row['dates'] if d['kind'] == 'publication'])
        self.assertIn('2026-09-17', [d['date'] for d in row['dates'] if d['kind'] == 'environmental-decision'])

    def test_environment_source_metadata_uses_all_edits_and_attachment_receipts(self):
        details = [
            {'id': '95482', 'mainMenuId': '23699', 'title': 'Obwieszczenie o wszczęciu', 'link': 'a,95482.html', 'basicData': {'originActive': '2026-05-06 10:44:20', 'active': '2026-05-06 10:47:13', 'modify': None}, 'attachments': [{'id': '1', 'extension': 'pdf'}]},
            {'id': '96020', 'mainMenuId': '23699', 'title': 'Publikacja', 'link': 'a,96020.html', 'basicData': {'active': '2026-09-18 11:00:00', 'modify': None}, 'attachments': []}]
        class Fetcher:
            def json(self, url):
                if url.endswith('api/menu/19681'):
                    return [{'id': '19681', 'children': [{'id': '23699', 'name': '2026', 'link': 'm,23699.html'}]}], FIRST
                if '/articles?' in url:
                    return {'total': 2, 'offset': 0, 'articles': [{'id': d['id']} for d in details]}, FIRST
                return copy.deepcopy(next(d for d in details if url.endswith('/' + d['id']))), SECOND
            def get(self, url):
                return b'PDF mocked at transport boundary', LAST, 'hash'
        with patch.object(private, 'pdf_text', return_value=('public text', 1)), patch.object(private, 'resolve_parcels', return_value={'verified': 0, 'requested': 0, 'unresolved': 0, 'warnings': []}):
            records, meta, _ = private.collect_environment(Fetcher())
        self.assertEqual(meta['fetchedAt'], LAST)
        self.assertEqual(meta['sourceUpdatedAt'], '2026-05-06T08:47:13+00:00')
        self.assertEqual(records[0]['sourceUpdatedAt'], meta['sourceUpdatedAt'])

    def test_client_memo_keeps_original_receipt_without_clock_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = public.Client(Path(tmp))
            with patch.object(client.session, 'get', return_value=Reply({'ok': True})) as request, patch.object(public, 'utcnow', side_effect=[FIRST, LAST]):
                one = client.get('https://example.org/one')
                two = client.get('https://example.org/one')
            self.assertIs(one, two)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(client.fetched_at('https://example.org/one'), FIRST)
            self.assertEqual(len(client.ledger), 1)
            with self.assertRaises(ValueError):
                client.fetched_at('https://example.org/unfetched')

    def test_public_source_metadata_max_includes_memoized_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = public.Client(Path(tmp))
            replies = {'https://example.org/a': Reply('a'), 'https://example.org/b': Reply('b')}
            def loader(sid):
                original.get('https://example.org/a')
                if sid == 'budget':
                    original.get('https://example.org/b')
                row = public.record(sid, '1', 'https://example.org/a', 'Projekt', FIRST)
                return [row], 'complete', None, []
            with patch.object(public, 'Client', return_value=original), patch.object(original.session, 'get', side_effect=lambda url, **kw: replies[url]), patch.object(public, 'utcnow', side_effect=[START, FIRST, SECOND, LAST]):
                result = public.collect(Path(tmp), loaders={sid: lambda sid=sid: loader(sid) for sid in public.SOURCES})
            # Source metadata describes all used receipt evidence, not adapter start.
            self.assertEqual(next(s for s in result['sources'] if s['id'] == 'budget')['fetchedAt'], original.ledger[-1]['fetchedAt'])
            self.assertEqual(next(s for s in result['sources'] if s['id'] == 'wpf')['fetchedAt'], original.ledger[0]['fetchedAt'])
            self.assertEqual(set(result), {'records', 'sources', 'warnings'})

    def test_finance_record_uses_document_receipt(self):
        latest = {'id': '2', 'title': 'Uchwała z dnia 24 września 2026', 'link': 'a,2.html', 'basicData': {'active': '2026-09-29 12:00:00'}, 'attachments': [{'id': '203514', 'extension': 'pdf', 'downloadable': True, 'name': 'WPF'}]}
        original = dict(latest, id='1', title='Uchwała z dnia 15 grudnia 2025', link='a,1.html', attachments=[])
        class Page:
            def get_text(self): return 'WPF'
        with tempfile.TemporaryDirectory() as tmp:
            client = public.Client(Path(tmp))
            def pdf(url):
                client.get(url)
                return [Page()]
            with patch.object(client.session, 'get', side_effect=lambda url, **kw: Reply(latest if url.endswith('/2') else original if url.endswith('/1') else 'PDF')), patch.object(public, 'utcnow', side_effect=[FIRST, SECOND, LAST]), patch.object(public_finance, 'finance_menu', return_value=('23686', 2026)), patch.object(public_finance, 'list_articles', return_value=[{'id': '1'}, {'id': '2'}]), patch.object(client, 'pdf', side_effect=pdf), patch.object(public_finance, 'pdf_tables', return_value=json.loads((FIX / '203514-tables.json').read_text())):
                records, _, _, _ = public_finance.load_finance(client, 'wpf', START)
            self.assertTrue(all(r['fetchedAt'] == LAST for r in records))

    def test_procurement_record_max_tender_documents_bip_receipts(self):
        tid = 'ocds-148610-c370b8b5-bddb-4f4d-bc80-d64c5b20b8a4'
        article = {'id': '1', 'link': 'a,1.html', 'title': 'Ogłoszenie', 'content': tid, 'basicData': {'active': '2026-02-01 12:00:00'}, 'attachments': []}
        data = json.loads((FIX / ('ezam-' + tid + '.json')).read_text())
        docs = json.loads((FIX / ('ezam-docs-' + tid + '.json')).read_text())
        with tempfile.TemporaryDirectory() as tmp:
            client = public.Client(Path(tmp))
            with patch.object(client.session, 'get', side_effect=lambda url, **kw: Reply(article if '/articles/' in url else docs if 'GetTenderDocuments' in url else data)), patch.object(public, 'utcnow', side_effect=[FIRST, SECOND, LAST]), patch.object(public_procurement, 'procurement_leaves', return_value=([{'id': '1', 'name': 'Case', 'link': 'm,1.html'}], '2026')), patch.object(public_procurement, 'list_articles', return_value=[{'id': '1'}]):
                records, _, updated, _ = public_procurement.load_procurement(client, START)
            self.assertEqual(records[0]['fetchedAt'], LAST)
            self.assertIsNone(updated)

    def test_bo_geometry_keeps_card_receipt_separate_from_result_receipt(self):
        cards = json.loads((FIX / 'bo-cards.json').read_text())
        card = next(c for c in cards if 'id="markers"' in c['html'] and '52.' in c['html'])
        url = public.BO + 'projekt/' + card['id']
        results = {card['id']: {'status': 'Wybrany do realizacji', 'votes': 1}}
        proof = public.BIP + 'api/files/203094'
        with tempfile.TemporaryDirectory() as tmp:
            client = public.Client(Path(tmp))
            def implementation(c):
                c.get(proof)
                return 2026, 2027, proof, '2026-09-20T10:00:00Z', c.fetched_at(proof)
            def reply(u, **kw):
                return Reply('<p>Liczba projektów: 1</p><a href="' + url + '">card</a>' if u.endswith('projekty') else card['html'] if u == url else 'results')
            with patch.object(client.session, 'get', side_effect=reply), patch.object(public, 'utcnow', side_effect=[START, SECOND, LAST, FIRST]), patch.object(public_bo, 'parse_bo_results', return_value=results), patch.object(public_bo, 'implementation_evidence', side_effect=implementation):
                records, _, _, _ = public_bo.load_bo(client, START)
            row, = records
            self.assertEqual(row['fetchedAt'], LAST)
            self.assertTrue(row['geometries'])
            self.assertEqual(row['geometries'][0]['properties']['fetchedAt'], FIRST)

    def test_news_each_post_uses_its_own_page_receipt(self):
        def post(key):
            return {'id': key, 'link': public.NEWS + str(key), 'title': {'rendered': 'Budowa'}, 'date_gmt': '2026-09-01T00:00:00', 'modified_gmt': '2026-09-02T00:00:00'}
        with tempfile.TemporaryDirectory() as tmp:
            client = public.Client(Path(tmp))
            with patch.object(client.session, 'get', side_effect=[Reply([post(1)], {'X-WP-Total': '2', 'X-WP-TotalPages': '2'}), Reply([post(2)], {'X-WP-Total': '2', 'X-WP-TotalPages': '2'})]), patch.object(public, 'utcnow', side_effect=[FIRST, LAST]):
                records, _, _, _ = public_news.load_news(client, START)
            self.assertEqual([r['fetchedAt'] for r in records], [FIRST, LAST])

    def test_public_failure_preserves_all_source_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            prior = json.loads((ROOT / 'public/data/investments.json').read_text())
            loaders = {sid: lambda: (_ for _ in ()).throw(ValueError('offline')) for sid in public.SOURCES}
            out = public.collect(Path(tmp), prior, loaders=loaders)
            for src in out['sources']:
                old = next(s for s in prior['sources'] if s['id'] == src['id'])
                self.assertEqual({k: v for k, v in src.items() if k not in ('status', 'warnings')}, {k: v for k, v in old.items() if k not in ('status', 'warnings')})
                self.assertEqual([r for r in out['records'] if r['sourceId'] == src['id']], [r for r in prior['records'] if r['sourceId'] == src['id']])


if __name__ == '__main__':
    unittest.main()
