"""Discover tender identities from actual 2026 BIP links/PDFs, not samples."""
from __future__ import annotations
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
from bs4 import BeautifulSoup
from .tender_results import first_opening, latest_selection, parse_financing, parse_selection
from .public import BIP, EZ, record, fact, cost, event, iso, day, clean, categorize, list_articles, menu_node, safe_url, text

TENDER_ID = re.compile(r'ocds-148610-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f-])', re.I)


def parse_tender(data, documents, fetched):
    tid = data.get('objectId', '')
    if not TENDER_ID.fullmatch(tid) or not data.get('title'):
        raise ValueError('Brak prawidłowej tożsamości postępowania')
    if not isinstance(documents, list):
        raise ValueError('Nieprawidłowa lista dokumentów postępowania')
    r = record('procurement', tid, EZ + 'mp-client/search/list/' + tid, data['title'], fetched)
    state, stage = data.get('state') or '', data.get('stage') or ''
    status = {'Initiated': 'Postępowanie wszczęte', 'Agreement': 'Etap zawarcia umowy — nie potwierdzenie zakończenia budowy',
              'Cancelled': 'Postępowanie unieważnione', 'Canceled': 'Postępowanie unieważnione',
              'Finished': 'Zakończone postępowanie — nie potwierdzenie zakończenia budowy'}.get(state, 'Status postępowania: ' + state)
    r.update(recordType='procurement', category=categorize(r['title']), investorName=data.get('organizationName'), status=status,
             statusAsOf=day(data.get('initiationDate')) if state == 'Initiated' else None)
    r['summary'] = 'Metadane zamówienia i linki do opublikowanych dokumentów. Etap zamówienia nie określa etapu budowy.'
    fact(r, 'Numer sprawy', data.get('referenceNumber') or '')
    fact(r, 'ID eZamówienia', tid)
    fact(r, 'Numer BZP', data.get('bzpNumber') or '')
    fact(r, 'Zamawiający', data.get('organizationName') or '')
    fact(r, 'Status / etap API', state + ' / ' + stage)
    if data.get('cancellationDate') and state == 'Agreement':
        r['warnings'].append('API zawiera cancellationDate obok state=Agreement; nie uznano tego pola za unieważnienie ani zakończenie robót.')
    r['years'] = sorted({int(v[:4]) for v in [data.get('initiationDate'), data.get('createdDate')] if v and re.match(r'^20\d{2}-', v)})
    if data.get('initiationDate'):
        r['dates'].append({'kind': 'procurement-initiation', 'date': day(data['initiationDate']), 'label': 'Wszczęcie postępowania', 'sourceUrl': r['sourceUrl']})
    for term in data.get('terms') or []:
        if term.get('isValid') is True:
            d = day(term.get('term'))
            if not d:
                raise ValueError('Ważny termin bez daty')
            r['dates'].append({'kind': term['termType'], 'date': d, 'label': term['termType'] + ' (ważny termin)', 'sourceUrl': r['sourceUrl']})
            fact(r, 'Ważny termin — timestamp ' + term['termType'], term['term'])
    if data.get('isAmountToFinancedPublished') is True and data.get('amountToFinanced') is not None:
        cost(r, 'tender-financing', data['amountToFinanced'], 'Kwota przeznaczona na sfinansowanie (nie cena oferty/umowy)', currency=data.get('amountToFinancedCurrencyText') or 'PLN')
    seen = set()
    for doc in documents:
        if doc.get('tenderDocumentState') != 'Published' or doc.get('deleteDate'):
            continue
        key = doc.get('objectId')
        if not key or key in seen:
            raise ValueError('Duplikat / brak identyfikatora dokumentu')
        seen.add(key)
        url = safe_url(doc.get('url'))
        event(r, key, doc.get('name') or doc.get('fileName') or 'Dokument postępowania', doc.get('publishedDate'), url)
        fact(r, 'Dokument: ' + clean(doc.get('name')), clean(doc.get('fileName')) + ' — ' + url, url)
    # CPV is retained only if the API actually exposes verified codes.
    cpv = data.get('cpvCodes') or []
    if cpv and isinstance(cpv, list):
        codes = [c for c in cpv if isinstance(c, str) and re.fullmatch(r'\d{8}(?:-\d)?', c)]
        if len(codes) != len(cpv):
            raise ValueError('Niepoprawne kody CPV')
        fact(r, 'CPV', ', '.join(codes))
    return r


def document_identity_text(raw, extension):
    """Read public identity-office XML and hyperlink relationships without Office."""
    import io
    import zipfile
    import xml.etree.ElementTree as ET
    if extension not in ('docx', 'odt'):
        raise ValueError('Nieobsługiwany format tożsamości postępowania')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [n for n in archive.namelist() if n.endswith(('.xml', '.rels'))]
        result = []
        for name in names:
            item = archive.getinfo(name)
            if item.file_size > 2000000:
                raise ValueError('Nadmierny rozmiar XML')
            root = ET.fromstring(archive.read(name))
            result.extend(root.itertext())
            result.extend(value for element in root.iter() for value in element.attrib.values())
    return '\n'.join(result)


def tender_links(client, article):
    html = article.get('content') or ''
    ids = set(TENDER_ID.findall(html))
    for attachment in article.get('attachments') or []:
        extension = attachment.get('extension')
        if attachment.get('deleted') or extension not in ('pdf', 'docx', 'odt'):
            continue
        title = (attachment.get('name') or '') + ' ' + article['title']
        if not any(word in title.lower() for word in ['id post', 'adres strony', 'ogłoszeni', 'ogloszeni']):
            continue
        url = BIP + 'api/files/' + str(attachment['id'])
        if extension == 'pdf':
            doc = client.pdf(url)
            content = '\n'.join(p.get_text() for p in doc)
            links = [link.get('uri', '') for p in doc for link in p.get_links()]
        else:
            content = document_identity_text(client.get(url).content, extension)
            links = []
        ids.update(TENDER_ID.findall(content + '\n' + '\n'.join(links)))
    return ids


def procurement_leaves(client):
    root = menu_node(client, '19884')
    year = str(datetime.now(ZoneInfo('Europe/Warsaw')).year)
    years = [n for n in root.get('children') or [] if n['name'] == year]
    if len(years) != 1:
        raise ValueError('Brak odkrytego rocznika zamówień ' + year)
    year_node = menu_node(client, years[0]['id'])
    leaves = []
    for category in year_node.get('children') or []:
        if 'plan postępowań' in category['name'].lower():
            continue  # plan is not a launched tender
        current = menu_node(client, category['id'])
        children = current.get('children') or []
        if children:
            leaves.extend(children)
        else:
            leaves.append(current)
    if len({n['id'] for n in leaves}) != len(leaves):
        raise ValueError('Powtórzone menu zamówień')
    return leaves, year


def attach_bip(r, articles):
    seen = {e['id'] for e in r['events']}
    for article in articles:
        url = BIP + article['link']
        if 'bip-' + article['id'] not in seen:
            stamp = iso(article['basicData'].get('modify') or article['basicData'].get('active'))
            event(r, 'bip-' + article['id'], article['title'], stamp, url)
            seen.add('bip-' + article['id'])
        for attachment in article.get('attachments') or []:
            if attachment.get('deleted') or not attachment.get('downloadable'):
                continue
            key = 'bip-file-' + str(attachment['id'])
            if key in seen:
                continue
            seen.add(key)
            link = BIP + 'api/files/' + str(attachment['id'])
            event(r, key, attachment['name'], iso(attachment.get('publishDate')), link)
            fact(r, 'Dokument BIP', attachment['name'], link)


def document_url(tid, doc):
    return EZ + 'mp-readmodels/api/Tender/DownloadDocument/' + tid + '/' + doc['objectId']


def pdf_text(client, url):
    return ' '.join(page.get_text() for page in client.pdf(url))


def part_label(price):
    if not price['part']:
        return ''
    return ' — część ' + price['part'] + (': ' + price['name'] if price['name'] else '')


def tender_result_evidence(client, r, documents):
    """Winner/price and reserved amounts from the authority's own notices.

    Returns (urls actually read, problem or None). A document that cannot be
    read or parsed unambiguously stays a plain link and never stops the source.
    """
    tid = r['sourceRecordId']
    urls, problems = [], []
    opening = first_opening(documents)
    if opening:
        url = document_url(tid, opening)
        try:
            reserved = parse_financing(pdf_text(client, url))
            urls.append(url)
            api_amount = next((c['amount'] for c in r['costs'] if c['kind'] == 'tender-financing'), None)
            for item in reserved:
                if item['part'] is None and api_amount is not None:
                    continue
                label = 'Kwota przeznaczona na sfinansowanie' + (' — część ' + item['part'] if item['part'] else '') + ' (nie cena oferty/umowy)'
                cost(r, 'tender-financing', item['amount'], label, url=url)
        except Exception as exc:  # noqa: BLE001 — a bad PDF must not drop the source
            problems.append('otwarcie ofert: ' + str(exc))
    selection = latest_selection(documents)
    if selection:
        url = document_url(tid, selection)
        try:
            result = parse_selection(pdf_text(client, url))
            urls.append(url)
            fact(r, 'Wybrany wykonawca (oferta)', result['winner'], url)
            for price in result['prices']:
                cost(r, 'offer', price['amount'], 'Wybrana oferta' + part_label(price) + ' — ' + result['winner'] + '; brutto, nie koszt końcowy', url=url)
            if result['contractDate']:
                r['dates'].append({'kind': 'planned-contract', 'date': result['contractDate'],
                                   'label': 'Planowane podpisanie umowy (wg informacji o wyborze oferty)', 'sourceUrl': url})
        except Exception as exc:  # noqa: BLE001 — a bad PDF must not drop the source
            problems.append('wybór oferty: ' + str(exc))
    return urls, ('; '.join(problems) or None)


def load_procurement(client, fetched=None):
    leaves, year = procurement_leaves(client)
    records, count_articles, count_docs, linked = {}, 0, 0, 0
    no_ids, unread = [], []
    for leaf in leaves:
        entries = list_articles(client, leaf['id'])
        articles = [client.json(BIP + 'api/articles/' + entry['id']) for entry in entries]
        article_urls = [BIP + 'api/articles/' + entry['id'] for entry in entries]
        count_articles += len(articles)
        ids = set()
        for article in articles:
            ids.update(tender_links(client, article))
        if not ids:
            if not articles:
                continue
            r = record('procurement', 'bip-menu-' + leaf['id'], BIP + leaf['link'], leaf['name'], client.fetched_at(*article_urls))
            r.update(recordType='procurement', years=[int(year)], category=categorize(r['title']), status='Publikacje zamówienia w BIP — brak zweryfikowanego ID eZamówień')
            r['summary'] = 'Karta zamówienia w oficjalnym roczniku BIP; dokumenty linkowane, etap robót nieustalony.'
            no_ids.append(leaf['id'])
            attach_bip(r, articles)
            records[r['id']] = r
        else:
            linked += 1
            for tid in sorted(ids):
                key = 'procurement:' + tid
                if key not in records:
                    tender_url = EZ + 'mp-readmodels/api/Search/GetTender?id=' + tid
                    documents_url = EZ + 'mp-readmodels/api/Search/GetTenderDocuments?tenderId=' + tid
                    data = client.json(tender_url)
                    if data.get('objectId') != tid or data.get('organizationName') != 'Gmina Ożarów Mazowiecki':
                        raise ValueError('ID / zamawiający niezgodny z gminą')
                    docs = client.json(documents_url)
                    r = parse_tender(data, docs, client.fetched_at(tender_url, documents_url))
                    result_urls, problem = tender_result_evidence(client, r, docs)
                    if result_urls:
                        r['fetchedAt'] = client.fetched_at(tender_url, documents_url, *result_urls)
                    if problem:
                        unread.append(r['sourceRecordId'] + ' (' + problem + ')')
                    count_docs += sum(d.get('tenderDocumentState') == 'Published' and not d.get('deleteDate') for d in docs)
                    records[key] = r
                attach_bip(records[key], articles)
                # The record includes BIP events as well as API metadata/docs;
                # a repeated identity keeps the maximum across all its cards.
                records[key]['fetchedAt'] = max(records[key]['fetchedAt'], client.fetched_at(*article_urls))
                fact(records[key], 'Odkryte menu BIP', leaf['name'], BIP + leaf['link'])
    notes = []
    if no_ids:
        notes.append('Zamówienia bez zweryfikowanego ID eZamówień zachowano jako karty BIP: ' + ', '.join(no_ids))
    if unread:
        notes.append('Nie odczytano jednoznacznie wyniku/kwot z PDF (pozostają linki): ' + ', '.join(unread))
    notes.append('Komplet odkrytych kart zamówień BIP ' + year + ', nie pełny eksport wszystkich zamówień gminy poza BIP. CPV i ceny wybranych ofert tylko z jednoznacznych informacji zamawiającego o wyborze oferty; pozostałe dokumenty są linkowane.')
    coverage = f'Rocznik {year}: {len(leaves)} menu/kart; {count_articles} artykułów (pełna paginacja); {linked} kart z ID; {len(records)} rekordów; {count_docs} opublikowanych dokumentów eZamówień; bez ID: {len(no_ids)}.'
    updated = max((r['sourceUpdatedAt'] for r in records.values() if r['sourceUpdatedAt']), default=None)
    return list(records.values()), coverage, updated, notes
