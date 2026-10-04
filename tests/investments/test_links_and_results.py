"""Tender outcomes from real notices and cross-source links; offline, real document texts."""
import copy
import unittest.mock
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
FIX = Path(__file__).parent / 'fixtures' / 'public'

from investment_sources.public import BIP, record, fact, cost, text  # noqa: E402
from investment_sources.tender_results import latest_selection, parse_financing, parse_selection  # noqa: E402
from investment_sources import public_procurement  # noqa: E402
import investment_links as links  # noqa: E402
from investment_validation import validate_dataset  # noqa: E402
from import_investments import build_dataset  # noqa: E402

PLAYGROUNDS = '4e1266dc-2d82-45a8-b132-1e82566e8f74'
ROADS = 'f8456b81-860a-4d0b-80c4-3ac3705bd4e7'
KAPUCKA = 'e75ac4dd-1c85-4c03-9ce9-e97e05e963cf'
FETCHED = '2026-10-03T00:00:00Z'


def notice(name):
    return (FIX / 'tender-results' / (name + '.txt')).read_text(encoding='utf-8')


class TenderResults(unittest.TestCase):
    def test_selection_with_parts_in_brackets(self):
        result = parse_selection(notice(PLAYGROUNDS + '_4'))
        self.assertEqual(result['winner'], 'Greentica Sp. z o.o.')
        self.assertEqual([(p['part'], p['amount']) for p in result['prices']], [('A', 426810.0), ('B', 294462.0)])
        self.assertEqual(result['prices'][0]['name'], 'rozbudowa placu zabaw Osiedla Ołtarzew przy ul. Parkowej')
        self.assertEqual(result['contractDate'], '2026-07-21')

    def test_selection_with_parts_after_price_word(self):
        result = parse_selection(notice(ROADS + '_4'))
        self.assertTrue(result['winner'].startswith('PRZEDSIĘBIORSTWO PRODUKCYJNO'))
        self.assertEqual([(p['part'], p['amount']) for p in result['prices']], [('A', 307500.0), ('B', 159900.0)])
        self.assertEqual(result['prices'][1]['name'], 'Modernizacja ul. Wiosennej')

    def test_single_price_selection(self):
        result = parse_selection(notice(KAPUCKA + '_11'))
        self.assertEqual(result['winner'], 'INSTALNIKA Sp. z o. o.')
        self.assertEqual(result['prices'], [{'part': None, 'name': '', 'amount': 4193070.0}])
        self.assertEqual(result['contractDate'], '2026-10-01')

    def test_cancellation_notice_is_not_a_selection(self):
        with self.assertRaises(ValueError):
            parse_selection(notice('e2dcccc5-d1c0-47b6-8158-bc46c382abce_3'))

    def test_two_winners_or_unlabelled_prices_are_rejected(self):
        text_value = notice(PLAYGROUNDS + '_4')
        with self.assertRaisesRegex(ValueError, 'wykonawca'):
            parse_selection(text_value.replace('Uzasadnienie', 'oraz Inna Firma z siedzibą: Kraków Uzasadnienie', 1))
        with self.assertRaisesRegex(ValueError, 'Ceny części'):
            parse_selection(text_value.replace('Uzasadnienie', 'oraz 1 000,00 zł Uzasadnienie', 1))

    def test_financing_per_part_and_yearly_split(self):
        self.assertEqual(parse_financing(notice(PLAYGROUNDS + '_3')), [{'part': 'A', 'amount': 300000.0}, {'part': 'B', 'amount': 300000.0}])
        self.assertEqual(parse_financing(notice(ROADS + '_3')), [{'part': '1', 'amount': 345400.0}, {'part': '2', 'amount': 195600.0}])
        # "w tym: ... – rok 2027" is a split of the same total, not separate amounts.
        self.assertEqual(parse_financing(notice('949059ed-6938-4658-a7d0-c4a2f3e4902f_5')), [{'part': None, 'amount': 5400700.0}])

    def test_latest_selection_skips_superseded_and_cancelled(self):
        doc = lambda n, name, day: {'objectId': f'x_{n}', 'name': name, 'publishedDate': f'2026-09-{day}T10:00:00Z', 'tenderDocumentState': 'Published', 'deleteDate': None}
        reselected = [doc(6, 'Informacja o wyborze oferty', 10), doc(7, 'Zawiadomienie o unieważnieniu czynności Zamawiającego w zakresie wyboru najkorzystniejszej oferty', 12), doc(8, 'Informacja o wyborze oferty', 14)]
        self.assertEqual(latest_selection(reselected)['objectId'], 'x_8')
        self.assertIsNone(latest_selection(reselected[:2]))
        self.assertIsNone(latest_selection([doc(3, 'Informacja z otwarcia ofert', 1)]))

    def test_adapter_adds_costs_and_never_fails_the_source_on_a_bad_pdf(self):
        r = record('procurement', 'ocds-148610-' + PLAYGROUNDS, 'https://ezamowienia.gov.pl/x', 'Place zabaw', FETCHED)
        docs = [{'objectId': f'ocds-148610-{PLAYGROUNDS}_3', 'name': 'Informacja z otwarcia ofert', 'publishedDate': '2026-06-18T10:00:00Z', 'tenderDocumentState': 'Published', 'deleteDate': None},
                {'objectId': f'ocds-148610-{PLAYGROUNDS}_4', 'name': 'Informacja o wyborze oferty', 'publishedDate': '2026-07-13T10:00:00Z', 'tenderDocumentState': 'Published', 'deleteDate': None}]
        texts = {d['objectId']: notice(PLAYGROUNDS + d['objectId'][-2:]) for d in docs}
        with unittest.mock.patch.object(public_procurement, 'pdf_text', lambda client, url: texts[url.rsplit('/', 1)[1]]):
            urls, problem = public_procurement.tender_result_evidence(None, r, docs)
        self.assertIsNone(problem)
        self.assertEqual(len(urls), 2)
        offers = [c for c in r['costs'] if c['kind'] == 'offer']
        self.assertEqual([c['amount'] for c in offers], [426810.0, 294462.0])
        self.assertIn('część A: rozbudowa placu zabaw Osiedla Ołtarzew', offers[0]['label'])
        self.assertEqual([c['amount'] for c in r['costs'] if c['kind'] == 'tender-financing'], [300000.0, 300000.0])
        self.assertEqual([d['kind'] for d in r['dates']], ['planned-contract'])

        broken = record('procurement', 'ocds-148610-' + PLAYGROUNDS, 'https://ezamowienia.gov.pl/x', 'Place zabaw', FETCHED)
        def fail(client, url):
            raise ValueError('Pobranie nieudane')
        with unittest.mock.patch.object(public_procurement, 'pdf_text', fail):
            urls, problem = public_procurement.tender_result_evidence(None, broken, docs)
        self.assertEqual(urls, [])
        self.assertIn('Pobranie nieudane', problem)
        self.assertEqual(broken['costs'], [])


def budget(key, title, klass, year=2026):
    r = record('budget', key, BIP + 'api/files/1', title, FETCHED)
    r.update(recordType='budget-task', years=[year], category='sport i rekreacja')
    fact(r, 'Dział / rozdział', klass)
    cost(r, 'annual-plan', 1000, 'Plan')
    return r


def tender(key, number, title='Rozbudowa/przebudowa placów zabaw'):
    r = record('procurement', key, 'https://ezamowienia.gov.pl/' + key, title, FETCHED)
    r.update(recordType='procurement', years=[2026])
    fact(r, 'Numer sprawy', number)
    return r


def mapped(key, title, year=2026):
    r = record('municipal-map', key, 'https://ozarow.gminneinwestycje.pl/' + key, title, FETCHED)
    r.update(years=[year], category='Sport i rekreacja')
    return r


def orders():
    out = []
    for article in json.loads((FIX / 'commission-orders.json').read_text(encoding='utf-8')).values():
        parsed = links.parse_order(text(article['content']))
        if parsed:
            out.append({'id': article['id'], 'title': article['title'], 'url': BIP + article['link'],
                        'appoints': True, 'tender': parsed[0], 'segments': parsed[1]})
    return out


class Links(unittest.TestCase):
    def test_commission_orders_name_budget_lines_and_tender(self):
        parsed = {o['tender']: o for o in orders()}
        self.assertEqual(set(parsed), {'RZP.271.21.2026', 'RZP.271.14.2026'}, 'order without a budget line is ignored')
        segment = parsed['RZP.271.21.2026']['segments']
        self.assertEqual([(s[0], s[1]) for s in segment], [('900', '90095')])
        self.assertIn('Domu Kultury Uśmiech', segment[0][2])

    def test_documented_links_need_same_chapter_and_every_name_word(self):
        records = [
            budget('a', 'Rozbudowa placu zabaw Osiedle Ołtarzew przy ul. Parkowej z uwzględnieniem huśtawki dla osób niepełnosprawnych', '900 / 90095'),
            budget('b', 'Rozbudowa placu zabaw przy Domu Kultury Uśmiech w Józefowie z uwzględnieniem huśtawki dla osób niepełnosprawnych', '900 / 90095'),
            budget('c', 'Rozbudowa placu zabaw przy Przedszkolu w Józefowie', '900 / 90095'),
            budget('d', 'Rozbudowa placu zabaw Osiedle Ołtarzew przy ul. Parkowej z uwzględnieniem huśtawki dla osób niepełnosprawnych', '801 / 80101'),
            tender('t', 'RZP.271.21.2026'),
        ]
        found = links.documented_links(records, orders())
        self.assertEqual(sorted(l['recordIds'][0] for l in found), ['budget:a', 'budget:b'])
        self.assertTrue(all(l['sourceUrl'].startswith(BIP + 'a,95629') for l in found))
        self.assertIn('RZP.271.21.2026', found[0]['basis'])

    def test_probable_link_needs_place_type_year_and_a_single_answer(self):
        oltarzew = budget('o', 'Rozbudowa placu zabaw Osiedle Ołtarzew przy ul. Parkowej', '900 / 90095')
        school = budget('s', 'Rozbudowa i przebudowa placu zabaw przy SP 1 w Ożarowie Mazowieckim', '900 / 90095')
        records = [oltarzew, school, mapped('445', 'Rozbudowa placu zabaw w Parku Ołtarzewskim'),
                   mapped('342', 'Rozbudowa placu zabaw w Ołtarzewie', year=2024)]
        found = links.probable_links(records)
        self.assertEqual([l['recordIds'] for l in found], [['budget:o', 'municipal-map:445']])
        self.assertIsNone(found[0]['sourceUrl'])
        self.assertIn('2026', found[0]['basis'])
        # Two playgrounds in the same village: no guess.
        twins = [mapped('j', 'Przebudowa placu zabaw w Józefowie'),
                 budget('p', 'Rozbudowa placu zabaw przy Przedszkolu w Józefowie', '900 / 90095'),
                 budget('k', 'Rozbudowa placu zabaw przy Domu Kultury w Józefowie', '900 / 90095')]
        self.assertEqual(links.probable_links(twins), [])
        # Same street, different kind of works.
        mixed = [mapped('k1', 'Projekt budowy sieci kanalizacji sanitarnej w miejscowości Kaputy ul. Wygodna'),
                 budget('k2', 'Wykonanie projektu budowy ulicy Wygodnej w Kaputach', '600 / 60016')]
        self.assertEqual(links.probable_links(mixed), [])

    def test_failed_document_read_keeps_prior_links_and_warns(self):
        records = [budget('a', 'Rozbudowa placu zabaw przy Domu Kultury Uśmiech w Józefowie z uwzględnieniem huśtawki dla osób niepełnosprawnych', '900 / 90095'),
                   tender('t', 'RZP.271.21.2026')]
        fresh, warnings = links.collect_links(records, None, orders_loader=orders)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(warnings, [])
        prior = {'links': fresh + [links.make_link('documented', 'budget:gone', 'procurement:t', 'x', BIP)]}
        def broken():
            raise ValueError('BIP nie odpowiada')
        kept, warnings = links.collect_links(records, prior, orders_loader=broken)
        self.assertEqual(kept, fresh, 'only links whose records still exist are kept')
        self.assertIn('BIP nie odpowiada', warnings[0])

    def test_sudden_drop_of_documented_links_keeps_prior(self):
        records = [budget(str(i), f'Budowa ujęcia wody numer {i} w Umiastowie', '900 / 90001') for i in range(5)] + [tender('t', 'RZP.271.1.2026')]
        prior = {'links': [links.make_link('documented', f'budget:{i}', 'procurement:t', 'x', BIP) for i in range(5)]}
        kept, warnings = links.collect_links(records, prior, orders_loader=lambda: [])
        self.assertEqual(len(kept), 5)
        self.assertIn('spadek', warnings[0])

    def test_dataset_carries_validated_links(self):
        records = [budget('a', 'Rozbudowa placu zabaw Osiedle Ołtarzew przy ul. Parkowej', '900 / 90095'),
                   mapped('445', 'Rozbudowa placu zabaw w Parku Ołtarzewskim')]
        source = lambda sid, n: {'id': sid, 'name': sid, 'url': 'https://example.org/', 'fetchedAt': FETCHED, 'sourceUpdatedAt': None,
                                 'status': 'fresh', 'coverage': '', 'recordCount': n, 'warnings': [], 'reuse': ''}
        contribution = {'records': records, 'sources': [source('budget', 1), source('municipal-map', 1)], 'warnings': []}
        dataset = build_dataset([contribution], generated_at=FETCHED)
        self.assertEqual([l['kind'] for l in dataset['links']], ['probable'])
        for broken in ({'recordIds': ['budget:a', 'budget:zzz']}, {'kind': 'other'}, {'sourceUrl': 'https://example.org/'},
                       {'recordIds': ['municipal-map:445', 'budget:a']}, {'id': 'probable:x'}):
            candidate = copy.deepcopy(dataset)
            candidate['links'][0].update(broken)
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                validate_dataset(candidate)
        documented = copy.deepcopy(dataset)
        documented['links'][0].update(kind='documented', id=documented['links'][0]['id'].replace('probable', 'documented'))
        with self.assertRaises(ValueError, msg='documented link needs its source document'):
            validate_dataset(documented)
        legacy = copy.deepcopy(dataset)
        del legacy['links']
        validate_dataset(legacy)


if __name__ == '__main__':
    unittest.main()
