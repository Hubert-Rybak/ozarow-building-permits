"""Cross-source links between already verified investment records.

Two kinds, never merged and never summed:
- documented: an official document names both sides. Today: the mayor's orders
  appointing a tender commission quote the budget line(s) and the tender number.
- probable: no document joins the sides; same year, same department area and a
  distinctive shared name (e.g. a place). Shown as a hint with its reason.

The step is fail-soft: if the documents cannot be read, the previous verified
documented links whose records still exist are kept and a warning is published.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

LINK_KEYS = frozenset('id kind recordIds basis sourceUrl'.split())
LINK_KINDS = frozenset({'documented', 'probable'})
ORDERS_MENU = '23689'  # Zarządzenia Burmistrza 2026; the finance adapter re-verifies the year.
STOPWORDS = frozenset('budowa przebudowa rozbudowa modernizacja remont ulicy ulica gminie gmina wraz oraz przy zadanie projekt '
                      'realizacja mazowiecki mazowieckim ozarow ozarowie miejscowosci zakresie wykonanie dokumentacji projektowej '
                      'terenie gminy dzial rozdzial paragraf'.split())
STOP_STEMS = frozenset(w[:5] for w in STOPWORDS - {'miejscowosci'})  # keep 'miejskiego'
GENERIC = frozenset('szkol podst infra popra doste inwes obiek zadan proje uwzgl osob niepe'.split())
PROBABLE_MIN_SCORE = 0.45
PROBABLE_MARGIN = 0.1
PLACE_WEIGHT = 3.0


def normalized(value):
    value = unicodedata.normalize('NFD', value or '').replace('ł', 'l').replace('Ł', 'L')
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn').lower()


# Villages / districts of the commune (sołectwa and town districts). Ożarów itself is too common.
GAZETTEER = frozenset(normalized(w)[:5] for w in (
    'bronisze domaniewek duchnice floriany gołaszew jawczyce józefów kaputy konotopa koprki kręczki macierzysz '
    'michałówek mory myszczyn ołtarzew orły piotrkówek pilaszków płochocin strzykuły szeligi świechowice święcice '
    'umiastów wieruchów wolica wolskie sowiny').split())


def stems(title):
    words = re.split(r'[^a-z0-9]+', normalized(title))
    out = set()
    for w in words:
        if w.isdigit():
            out.add(w)
        elif len(w) >= 4 and not w.startswith('miejscow') and w[:5] not in STOP_STEMS and w[:5] not in GENERIC:
            out.add(w[:5])
    return out


def place_stems(title):
    """Village names and street/estate names: the part of a title that says where."""
    t = normalized(title)
    places = {w[:5] for w in re.split(r'[^a-z0-9]+', t) if w[:5] in GAZETTEER and len(w) >= 4}
    for m in re.finditer(r'\b(?:ul|ulicy|ulica|ulic|al|alei|aleja|os|osiedle|osiedla|osiedlu)\.?\s+([a-z]{4,})', t):
        places.add(m.group(1)[:5])
    return places - STOP_STEMS


OBJECT_TYPES = {
    'woda i kanalizacja': r'kanaliz|wodoci|sanitar|deszcz|odwodn|\bsuw\b|ujeci|studni|zbiornik|retencj',
    'drogi': r'\b(?:budow|przebudow|rozbudow|moderniz|remont)\w*\s+(?:\w+\s+)?(?:ulic|drog)|\bdrog|chodnik|skrzyżowa|skrzyzowa|nawierzchn|rond|parking|ścieżk|sciezk',
    'sport i rekreacja': r'boisk|plac\w* zabaw|sport|siłowni|silowni|skatepark',
    'budynki': r'budynk|elewac|dach|termomoderniz',
    'oświetlenie': r'oświetl|oswietl',
    'wydarzenia': r'\bkino|koncert|festyn|potańców|warsztat|zajęci|piknik',
}
NOT_CONSTRUCTION = 'działania społeczne / nie budowa'


def object_types(title):
    t = (title or '').lower()
    return {name for name, pattern in OBJECT_TYPES.items() if re.search(pattern, t)}


def link_id(kind, ids):
    return kind + ':' + '|'.join(ids)


def make_link(kind, a, b, basis, url):
    ids = sorted([a, b])
    return {'id': link_id(kind, ids), 'kind': kind, 'recordIds': ids, 'basis': basis, 'sourceUrl': url}


def fact_value(record, label):
    return next((f['value'] for f in record['facts'] if f['label'] == label), None)


# ---- documented: tender commission orders -------------------------------------------------

def parse_order(text):
    """Return (tender number, [(department, chapter, segment text)]) or None."""
    m = re.search(r'(Dział\s*:?\s*\d{3}.*?)(?:\d\.\s*)?Znak postępowania\s*:?\s*(RZP\.271\.\d+\.\d{4})', text, re.S)
    if not m:
        return None
    body, tender = m.group(1), m.group(2)
    segments = []
    for part in re.split(r'(?=Dział\s*:?\s*\d{3})', body):
        dept = re.match(r'Dział\s*:?\s*(\d{3})', part)
        chapter = re.search(r'(?:Rozdział|rozdz\.)\s*:?\s*-?\s*(\d{5})', part)
        if dept and chapter:
            segments.append((dept.group(1), chapter.group(1), part))
    return (tender, segments) if segments else None


def load_orders(client):
    from investment_sources.public import BIP, list_articles, text
    orders = []
    for entry in list_articles(client, ORDERS_MENU):
        fields = {f['alias']: f['value'] for f in entry.get('aliasFields', [])}
        title = fields.get('title', '')
        if not re.search(r'komisji przetargowej', title, re.I) or re.search(r'nieruchomoś|sprzedaż|lokal', title, re.I):
            continue
        article = client.json(BIP + 'api/articles/' + entry['id'])
        parsed = parse_order(text(article.get('content')))
        if not parsed:
            continue
        orders.append({'id': article['id'], 'title': article['title'], 'url': BIP + article['link'],
                       'appoints': 'powołania' in article['title'].lower(), 'tender': parsed[0], 'segments': parsed[1]})
    if not orders:
        raise ValueError('Brak zarządzeń o komisjach przetargowych z pozycją budżetu')
    # Prefer the appointing order as the cited basis; amendments repeat the same pair.
    orders.sort(key=lambda o: (not o['appoints'], int(o['id'])))
    return orders


def documented_links(records, orders):
    procurement = {}
    for r in records:
        number = fact_value(r, 'Numer sprawy') if r['sourceId'] == 'procurement' else None
        if number:
            procurement.setdefault(number, []).append(r)
    finance = []
    for r in records:
        if r['sourceId'] == 'budget':
            klass = fact_value(r, 'Dział / rozdział') or ''
            m = re.fullmatch(r'(\d{3}) / (\d{5})', klass)
            if m:
                finance.append((r, m.group(1), m.group(2)))
        elif r['sourceId'] == 'wpf':
            finance.append((r, None, None))
    links = {}
    for order in orders:
        targets = procurement.get(order['tender'], [])
        if len(targets) != 1:
            continue
        tender = targets[0]
        all_text = stems(' '.join(s[2] for s in order['segments']))
        for r, dept, chapter in finance:
            own = stems(r['title'])
            if dept is not None:
                segment = next((stems(s[2]) for s in order['segments'] if (s[0], s[1]) == (dept, chapter)), None)
                matched = segment is not None and len(own) >= 2 and own <= segment
            else:
                matched = len(own) >= 3 and own <= all_text
            if not matched:
                continue
            link = make_link('documented', r['id'], tender['id'],
                             f"{order['title']} wskazuje pozycję „{r['title']}” jako zadanie postępowania {order['tender']}.", order['url'])
            links.setdefault(link['id'], link)
    return list(links.values())


# ---- probable: municipal map entry <-> budget / WPF line ----------------------------------

PROBABLE_PAIRS = (('municipal-map', 'budget'), ('municipal-map', 'wpf'), ('municipal-map', 'procurement'),
                  ('budget', 'wpf'), ('budget', 'procurement'), ('wpf', 'procurement'))


def probable_links(records):
    """Mutual best matches, judged separately for every pair of source types."""
    links = []
    for left_source, right_source in PROBABLE_PAIRS:
        links.extend(probable_pairs(records, left_source, right_source))
    return links


def probable_pairs(records, left_source, right_source):
    titles = {r['id']: stems(r['title']) for r in records}
    places = {r['id']: place_stems(r['title']) & titles[r['id']] for r in records}
    df = Counter(s for st in titles.values() for s in st)
    n = len(records) or 1
    idf = {s: math.log(1 + n / c) for s, c in df.items()}  # smoothed: stays positive on tiny sets
    left = [r for r in records if r['sourceId'] == left_source and r['years'] and r['category'] != NOT_CONSTRUCTION]
    right = [r for r in records if r['sourceId'] == right_source and r['years'] and r['category'] != NOT_CONSTRUCTION]

    def weight(rid, token):
        return idf[token] * (PLACE_WEIGHT if token in places[rid] else 1.0)

    kinds = {r['id']: object_types(r['title']) for r in records}

    def score(a, b):
        sa, sb = titles[a['id']], titles[b['id']]
        shared = sa & sb
        where = shared & (places[a['id']] | places[b['id']])
        ka, kb = kinds[a['id']], kinds[b['id']]
        if len(shared) < 2 or not where or not set(a['years']) & set(b['years']) or (ka and kb and not ka & kb):
            return 0.0, shared, where
        total = sum(weight(a['id'], s) for s in sa) + sum(weight(b['id'], s) for s in sb)
        common = sum(weight(a['id'], s) + weight(b['id'], s) for s in shared)
        return common / total, shared, where

    def best(candidates):
        ranked = sorted(candidates, key=lambda x: -x[0][0])
        if not ranked or ranked[0][0][0] < PROBABLE_MIN_SCORE:
            return None
        if len(ranked) > 1 and ranked[0][0][0] - ranked[1][0][0] < PROBABLE_MARGIN:
            return None
        top = ranked[0][0][1]
        # Another candidate matching everything the best one matched is a second plausible
        # answer (e.g. two playgrounds in the same village): do not pick between them.
        if any(other[0][0] > 0 and top <= other[0][1] for other in ranked[1:]):
            return None
        return ranked[0]

    from_left = {a['id']: best([(score(a, b), b) for b in right]) for a in left}
    from_right = {b['id']: best([(score(a, b), a) for a in left]) for b in right}
    by_id = {r['id']: r for r in records}
    links = []
    for a_id, hit in sorted(from_left.items()):
        if not hit:
            continue
        (value, shared, where), b = hit
        back = from_right.get(b['id'])
        if not back or back[1]['id'] != a_id:
            continue
        year = sorted(set(by_id[a_id]['years']) & set(b['years']))[0]
        basis = (f'Brak dokumentu łączącego oba wpisy. Ten sam rok ({year}), to samo miejsce w nazwie '
                 f'i zbieżny opis (zgodność {round(value * 100)}%). Może chodzić o tę samą inwestycję.')
        links.append(make_link('probable', a_id, b['id'], basis, None))
    return links


# ---- orchestration --------------------------------------------------------------------------

def valid_prior(prior, records, kind):
    ids = {r['id'] for r in records}
    return [l for l in (prior or {}).get('links', []) if l['kind'] == kind and all(i in ids for i in l['recordIds'])]


def collect_links(records, prior=None, *, cache=None, orders_loader=None):
    """Return (links, warnings). orders_loader=None means offline (probable links only)."""
    warnings = []
    documented = []
    if orders_loader is not None:
        kept = valid_prior(prior, records, 'documented')
        try:
            documented = documented_links(records, orders_loader())
            if len(kept) >= 4 and len(documented) * 2 < len(kept):
                raise ValueError(f'podejrzany spadek liczby powiązań ({len(documented)} wobec {len(kept)})')
        except Exception as exc:  # noqa: BLE001 — links are additive; never block the refresh
            documented = kept
            warnings.append('Powiązania udokumentowane: zachowano poprzedni odczyt (' + str(exc)[:200] + ').')
    documented_pairs = {tuple(l['recordIds']) for l in documented}
    probable = [l for l in probable_links(records) if tuple(l['recordIds']) not in documented_pairs]
    return sorted(documented + probable, key=lambda l: l['id']), warnings


def network_orders_loader(cache):
    def load():
        from investment_sources.public import Client
        return load_orders(Client(Path(cache) / 'links'))
    return load
