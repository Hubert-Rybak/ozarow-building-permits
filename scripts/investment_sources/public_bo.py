"""All citizen-budget cards/results. No city-centre geometry fallbacks."""
from __future__ import annotations
import re
import math
from bs4 import BeautifulSoup
from .public import BO, BIP, clean, text, money, record, cost, fact, event, categorize, list_articles, menu_node, iso, safe_url


def parse_bo_results(html):
    soup = BeautifulSoup(html, 'html.parser')
    results = {}
    for row in soup.select('.result-row'):
        key = row.get('data-project-id')
        status, votes, amount = row.select_one('.status'), row.select_one('.votes'), row.select_one('.price')
        if not key or not key.isdigit() or key in results or status is None or votes is None or amount is None:
            raise ValueError('Uszkodzone / powtórzone wyniki BO')
        vote_match = re.search(r'\d+', text(str(votes)).replace(' ', ''))
        amount_text = text(str(amount)).replace('Koszt:', '').strip()
        if not vote_match:
            raise ValueError('Brak liczby głosów BO')
        results[key] = {'status': status.get_text(' ', strip=True), 'votes': int(vote_match[0]), 'amount': float(money(amount_text))}
    if not results:
        raise ValueError('Brak wyników BO')
    return results


def parse_bo_card(html, key, result, fetched):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h2.project-header')
    if heading is None:
        raise ValueError('Brak tytułu karty BO')
    title = clean(heading.get_text(' ', strip=True))
    title = re.sub(r'^\d+\.\s*', '', title)
    r = record('bo', key, BO + 'projekt/' + key, title, fetched)
    boxes = {}
    for box in soup.select('.right-sidebar .box, .box'):
        label = box.select_one('.title')
        if label:
            values = [clean(x.get_text(' ', strip=True)) for x in box.find_all(['p', 'span'], recursive=False) if x is not label]
            boxes[clean(label.get_text())] = ' '.join(values)
    edition = boxes.get('Edycja')
    if edition and not re.fullmatch(r'20\d{2}', edition):
        raise ValueError('Nieprawidłowa edycja BO')
    r.update(recordType='proposal', category=categorize(title), status=result.get('status') or boxes.get('Status') or 'Propozycja',
             years=[int(edition)] if edition else [])
    r['summary'] = 'Karta projektu budżetu obywatelskiego. Wybór do realizacji nie potwierdza wykonania.'
    if re.search(r'lig[ęa] darta|edukacyjny rajd|plener rzeźbiarski|aktywny macierzysz|aktywny sąsiad|razem aktywnie|świadomy rodzic|mali kucharze|kino plenerowe|zajęcia|miasteczko bożonarodzeniowe', title, re.I):
        r['category'] = 'działania społeczne / nie budowa'
    if r['category'] == 'działania społeczne / nie budowa':
        r['summary'] = 'Projekt zajęć lub wydarzeń budżetu obywatelskiego; nie jest potwierdzoną budową.'
    if edition:
        fact(r, 'Rok edycji / wyboru', edition)
    implementation = result.get('implementationYear') if r['status'] == 'Wybrany do realizacji' else None
    if implementation:
        r['years'] = sorted(set(r['years'] + [implementation]))
        fact(r, 'Rok realizacji według oficjalnych wyników', implementation, result.get('implementationUrl', BO + 'wyniki'))
    if 'votes' in result:
        fact(r, 'Głosy', result['votes'], BO + 'wyniki')
    if boxes.get('Obszar'):
        fact(r, 'Obszar BO (nie adres)', boxes['Obszar'])
    if boxes.get('Postęp realizacji'):
        fact(r, 'Postęp na karcie', boxes['Postęp realizacji'])
    amount = result.get('amount')
    if boxes.get('Planowany koszt'):
        card_amount = float(money(boxes['Planowany koszt']))
        if amount is not None and card_amount != amount:
            raise ValueError('Koszt karty niezgodny z wynikami BO')
        amount = card_amount
    cost(r, 'proposal-estimate', amount, 'Planowany koszt projektu BO', implementation)
    if result.get('resultsDate'):
        r['statusAsOf'] = result['resultsDate']
        event(r, 'bo-results-' + key, 'Wyniki głosowania', result['resultsDate'], result.get('implementationUrl', BO + 'wyniki'))
    marker = soup.select_one('input#markers')
    value = marker.get('value', '').strip() if marker else ''
    coords = []
    if value:
        for pair in value.split(';'):
            if not re.fullmatch(r'\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*', pair):
                raise ValueError('Niepoprawny marker BO')
            lat, lon = [float(x) for x in pair.split(',')]
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError('Marker BO poza zakresem')
            coords.append([lon, lat])
        if len(coords) != len({tuple(c) for c in coords}):
            raise ValueError('Powtórzone markery BO')
        geometry = {'type': 'Point', 'coordinates': coords[0]} if len(coords) == 1 else {'type': 'MultiPoint', 'coordinates': coords}
        r['geometries'] = [{'type': 'Feature', 'geometry': geometry, 'properties': {'id': r['id'] + ':markers', 'accuracy': 'source-point',
                            'sourceUrl': r['sourceUrl'], 'parcelId': None, 'note': 'Punkt(y) z input#markers karty projektu; nie obrys budowy.',
                            'fetchedAt': fetched, 'sourceUpdatedAt': None}}]
    else:
        r['warnings'].append('Brak markera projektu; city_lat/city_lng nie są lokalizacją projektu.')
    return r


def implementation_evidence(client):
    root = menu_node(client, '23550')
    # Published BIP result entries, never guessed attachment IDs.
    year_nodes = [n for n in root.get('children') or [] if n['name'] == '2026']
    if len(year_nodes) != 1:
        raise ValueError('Brak menu wyników dla edycji 2026')
    year_node = menu_node(client, year_nodes[0]['id'])
    result_nodes = [n for n in year_node.get('children') or [] if 'wynik' in n['name'].lower()]
    if not result_nodes:
        raise ValueError('Brak menu wyników głosowania')
    candidates = []
    for child in result_nodes:
        candidates.extend(list_articles(client, child['id']))
    matches = []
    for entry in candidates:
        title = next((f['value'] for f in entry.get('aliasFields', []) if f['alias'] == 'title'), '')
        if 'wynik' in title.lower():
            matches.append(client.json(BIP + 'api/articles/' + entry['id']))
    if not matches:
        raise ValueError('Brak odkrytych oficjalnych wyników BO 2026')
    latest = max(matches, key=lambda a: a['basicData']['active'])
    for attachment in latest['attachments']:
        if attachment.get('deleted') or attachment.get('extension') != 'pdf':
            continue
        url = BIP + 'api/files/' + str(attachment['id'])
        doc = client.pdf(url)
        txt = ' '.join(p.get_text() for p in doc)
        m = re.search(r'DO REALIZACJI W\s+(20\d{2})\s+ROKU', txt, re.I)
        ed = re.search(r'BUDŻET OBYWATELSKI\s+(20\d{2})', txt, re.I)
        if m and ed:
            return int(ed[1]), int(m[1]), url, iso(latest['basicData']['active']), client.fetched_at(url, BIP + 'api/articles/' + latest['id'])
    raise ValueError('Niezweryfikowany rok wykonania BO')


def load_bo(client, fetched=None):
    html = client.html(BO + 'projekty')
    soup = BeautifulSoup(html, 'html.parser')
    m = re.search(r'Liczba projektów:\s*(\d+)', soup.get_text(' ', strip=True))
    if not m:
        raise ValueError('Brak całkowitego licznika projektów BO')
    total = int(m[1])
    links = {safe_url(a['href'], BO) for a in soup.select('a[href*="/projekt/"]')}
    # Follow observed paging only. No invented page params.
    pages = {safe_url(a['href'], BO) for a in soup.select('a[href]') if re.search(r'(?:page=|/strona/)', a['href'])}
    for url in sorted(pages):
        page = BeautifulSoup(client.html(url), 'html.parser')
        links.update(safe_url(a['href'], BO) for a in page.select('a[href*="/projekt/"]'))
    if len(links) != total:
        raise ValueError('Niekompletna lista kart BO')
    results = parse_bo_results(client.html(BO + 'wyniki'))
    ids = {url.rsplit('/', 1)[-1] for url in links}
    if set(results) != ids:
        raise ValueError('Wyniki BO nie pokrywają wszystkich kart')
    edition, year, proof_url, updated, proof_fetched = implementation_evidence(client)
    records = []
    for url in sorted(links):
        key = url.rsplit('/', 1)[-1]
        result = dict(results[key], implementationYear=year, implementationUrl=proof_url, resultsDate=updated[:10])
        html = client.html(url)
        # Geometry belongs only to the card; status/year/votes also use results.
        r = parse_bo_card(html, key, result, client.fetched_at(url))
        r['fetchedAt'] = max(client.fetched_at(url, BO + 'wyniki'), proof_fetched)
        if edition not in r['years']:
            raise ValueError('Edycja kart niezgodna z wynikami')
        records.append(r)
    mapped = sum(bool(r['geometries']) for r in records)
    points = sum(1 if g['geometry']['type'] == 'Point' else len(g['geometry']['coordinates']) for r in records for g in r['geometries'])
    selected = sum(r['status'] == 'Wybrany do realizacji' for r in records)
    coverage = f'{len(records)}/{total} kart; {len(results)} wyników. Edycja {edition}, realizacja {year}. Wybrane: {selected}; z markerami: {mapped}; punktów: {points}; bez geometrii: {total - mapped}.'
    return records, coverage, updated, []
