"""Public facts-only contribution. Raw evidence stays under caller's private cache."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BIP = 'https://bip.ozarow-mazowiecki.pl/'
BO = 'https://budzetobywatelski.ozarow-mazowiecki.pl/'
NEWS = 'https://ozarow-mazowiecki.pl/'
EZ = 'https://ezamowienia.gov.pl/'
SOURCES = {
    'budget': ('Budżet — przyjęta tabela wydatków majątkowych', BIP),
    'wpf': ('WPF — przyjęte przedsięwzięcia majątkowe', BIP),
    'procurement': ('Zamówienia publiczne — rocznik BIP i eZamówienia', BIP),
    'bo': ('Budżet obywatelski — projekty i wyniki', BO + 'projekty'),
    'municipal-news': ('Komunikaty inwestycyjne gminy', NEWS),
}
REUSE = 'Publiczne tytuły, daty, liczby i własne krótkie podsumowania; atrybucja i linki. Bez kopiowania opisów, zdjęć i dokumentacji. Licencja opisów/zdjęć nieustalona.'


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def clean(value):
    return ' '.join(str(value or '').split())


def text(html):
    return clean(BeautifulSoup(html or '', 'html.parser').get_text(' ', strip=True))


def safe_url(value, base=None):
    value = urljoin(base, value) if base else value
    u = urlsplit(value or '')
    if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password:
        raise ValueError('Nieprawidłowy URL źródła')
    return value


def money(value):
    s = clean(value).replace(' ', '').replace('zł', '').replace('PLN', '').replace(',', '.')
    if not re.fullmatch(r'-?\d+(?:\.\d{1,2})?', s):
        raise ValueError('Niepoprawna kwota: ' + s[:60])
    return Decimal(s)


def iso(value):
    if not value or value == 'Brak danych':
        return None
    v = str(value).replace(' ', 'T')
    if not re.match(r'^\d{4}-\d{2}-\d{2}T', v):
        raise ValueError('Niepoprawny timestamp')
    # BIP and BO expose local Warsaw wall time, not UTC.
    d = datetime.fromisoformat(v.replace('Z', '+00:00'))
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo('Europe/Warsaw'))
    return d.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def day(value):
    if not value:
        return None
    value = value[:10]
    datetime.strptime(value, '%Y-%m-%d')
    return value


def record(sid, key, url, title, fetched):
    return {'id': sid + ':' + key, 'sourceId': sid, 'sourceRecordId': key,
            'sourceUrl': safe_url(url), 'title': clean(title), 'recordType': 'project',
            'investor': 'municipal', 'investorName': 'Gmina Ożarów Mazowiecki',
            'category': 'inne', 'locality': '', 'address': '', 'status': 'Brak potwierdzonego etapu robót',
            'statusAsOf': None, 'summary': '', 'years': [], 'costs': [], 'dates': [],
            'geometries': [], 'parcelIds': [], 'events': [], 'facts': [], 'relatedIds': [],
            'warnings': [], 'fetchedAt': fetched, 'sourceUpdatedAt': None}


def fact(r, label, value, url=None):
    r['facts'].append({'label': label, 'value': str(value), 'sourceUrl': safe_url(url or r['sourceUrl'])})


def cost(r, kind, amount, label, year=None, url=None, currency='PLN'):
    amount = float(amount) if amount is not None else None
    if amount is not None and (not math.isfinite(amount) or amount < 0):
        raise ValueError('Niepoprawny koszt')
    r['costs'].append({'kind': kind, 'amount': amount, 'currency': currency, 'label': label,
                       'year': year, 'scope': 'local', 'sourceUrl': safe_url(url or r['sourceUrl'])})


def event(r, key, title, date, url):
    r['events'].append({'id': key, 'title': clean(title), 'date': day(date), 'sourceUrl': safe_url(url)})


def categorize(title):
    t = title.lower()
    for words, category in [(['kanaliz', 'wodociąg', 'suw ', 'ściek', 'retenc', 'wody'], 'wod-kan'),
                            (['drog', 'ulic', 'chodnik', 'skrzyż', 'przepraw', 'rower', 'parking'], 'drogi i transport'),
                            (['szko', 'przedszkol'], 'oświata'), (['boisk', 'skate', 'sport', 'plac zabaw', 'workout'], 'sport i rekreacja'),
                            (['ziele', 'ogród', 'smog', 'odpad', 'śmieci'], 'środowisko'),
                            (['zaję', 'liga darta', 'kino', 'świadomy rodzic', 'kucharze', 'miasteczko bożonarodzeniowe', 'aktywny sąsiad', 'razem aktywnie', 'bez ograniczeń'], 'działania społeczne / nie budowa')]:
        if any(w in t for w in words):
            return category
    return 'inne'


class Client:
    """Bounded HTTP retry; never silently serves old bytes as a fresh request."""
    def __init__(self, cache):
        self.cache = Path(cache) / 'public-http'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; RadarOzarowFacts/1.0)'
        self.memo = {}
        self.ledger = []
        self.used_urls = set()

    def get(self, url):
        url = safe_url(url)
        if url in self.memo:
            self.used_urls.add(url)
            return self.memo[url]
        failure = None
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=(10, 45))
                response.raise_for_status()
                raw = response.content
                if not raw or len(raw) > 50000000:
                    raise ValueError('Puste lub zbyt duże źródło')
                name = hashlib.sha256(url.encode()).hexdigest()
                (self.cache / name).write_bytes(raw)
                self.memo[url] = response
                self.ledger.append({'url': url, 'fetchedAt': utcnow(), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'file': name})
                self.used_urls.add(url)
                (self.cache / 'ledger.json').write_text(json.dumps(self.ledger, ensure_ascii=False, indent=2))
                return response
            except (requests.RequestException, ValueError) as exc:
                failure = exc
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        raise ValueError('Pobranie nieudane: ' + url + ': ' + str(failure))

    def fetched_at(self, *urls):
        """Maximum original receipt of explicit inputs; never job time/fallback."""
        receipts = {entry['url']: entry['fetchedAt'] for entry in self.ledger}
        if not urls or any(url not in receipts for url in urls):
            raise ValueError('Brak rzeczywistego potwierdzenia pobrania źródła')
        return max((receipts[url] for url in urls), key=lambda stamp: datetime.fromisoformat(stamp.replace('Z', '+00:00')))

    def json(self, url):
        return self.get(url).json()

    def html(self, url):
        return self.get(url).text

    def pdf(self, url):
        import pymupdf
        raw = self.get(url).content
        if not raw.startswith(b'%PDF-'):
            raise ValueError('Załącznik nie jest PDF')
        return pymupdf.open(stream=raw, filetype='pdf')


def list_articles(client, menu):
    result, seen, total = [], set(), None
    for _ in range(100):
        payload = client.json(BIP + 'api/menu/' + str(menu) + '/articles?limit=100&offset=' + str(len(result)))
        n = payload.get('total')
        rows = payload.get('articles')
        if not isinstance(n, int) or n < 0 or not isinstance(rows, list) or (total is not None and total != n):
            raise ValueError('Niespójny licznik paginacji BIP')
        total = n
        if not rows and len(result) != total:
            raise ValueError('Ucięta lista BIP')
        for r in rows:
            key = r.get('id')
            if not isinstance(key, str) or not key.isdigit() or key in seen:
                raise ValueError('Powtórzona lub uszkodzona strona BIP')
            seen.add(key)
        result.extend(rows)
        if len(result) == total:
            return result
        if len(result) > total:
            raise ValueError('Przekroczony licznik BIP')
    raise ValueError('Przekroczony limit stron BIP')


def flatten(nodes):
    for node in nodes:
        yield node
        yield from flatten(node.get('children') or [])


def menu_node(client, key):
    nodes = client.json(BIP + 'api/menu/' + str(key))
    if not isinstance(nodes, list):
        raise ValueError('Niepoprawne drzewo BIP')
    found = [n for n in flatten(nodes) if str(n.get('id')) == str(key)]
    if len(found) != 1:
        raise ValueError('Nieodnalezione menu BIP: ' + str(key))
    return found[0]


def guard(sid, rows, old):
    required = set('id sourceId sourceRecordId sourceUrl title recordType investor investorName category locality address status statusAsOf summary years costs dates geometries parcelIds events facts relatedIds warnings fetchedAt sourceUpdatedAt'.split())
    for r in rows:
        if not isinstance(r, dict) or set(r) != required:
            raise ValueError('Niekompletny / nadmiarowy schemat rekordu')
        safe_url(r['sourceUrl'])
        for key in ['costs', 'dates', 'geometries', 'parcelIds', 'events', 'facts', 'relatedIds', 'warnings', 'years']:
            if not isinstance(r[key], list):
                raise ValueError('Niepoprawna lista ' + key)
        for key in ['fetchedAt', 'sourceUpdatedAt']:
            if r[key]:
                iso(r[key])
        if r['statusAsOf']:
            day(r['statusAsOf'])
        for key in ['costs', 'dates', 'events', 'facts']:
            for item in r[key]:
                safe_url(item['sourceUrl'])
        for item in r['costs']:
            value = item['amount']
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError('Niepoprawny koszt rekordu')
        for item in r['dates'] + r['events']:
            if item['date']:
                day(item['date'])
    keys = [r['id'] for r in rows]
    if len(keys) != len(set(keys)) or any(r['sourceId'] != sid or not r['title'] for r in rows):
        raise ValueError('Duplikaty / uszkodzone rekordy')
    if not rows:
        raise ValueError('Brak rekordów; nie uznano za pusty sukces')
    if old and len(rows) < 0.8 * len(old):
        raise ValueError('Podejrzana utrata ponad 20% rekordów')


# Pure parsers are re-exported for offline contracts; loaders imported lazily.
def parse_budget_tables(tables):
    from .public_finance import parse_budget_tables as parse
    return parse(tables)


def parse_wpf_tables(tables):
    from .public_finance import parse_wpf_tables as parse
    return parse(tables)


def parse_bo_card(*args, **kwargs):
    from .public_bo import parse_bo_card as parse
    return parse(*args, **kwargs)


def parse_tender(*args, **kwargs):
    from .public_procurement import parse_tender as parse
    return parse(*args, **kwargs)


def collect(cache: Path, prior: dict | None = None, *, loaders=None) -> dict:
    from .public_finance import load_finance
    from .public_bo import load_bo
    from .public_procurement import load_procurement
    from .public_news import load_news
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    client = Client(cache)
    if loaders is None:
        loaders = {'budget': lambda: load_finance(client, 'budget'),
                   'wpf': lambda: load_finance(client, 'wpf'),
                   'procurement': lambda: load_procurement(client),
                   'bo': lambda: load_bo(client),
                   'municipal-news': lambda: load_news(client)}
    prior = prior or {}
    records, sources, warnings = [], [], []
    for sid, (name, url) in SOURCES.items():
        old = [r for r in prior.get('records', []) if r.get('sourceId') == sid]
        prev = next((s for s in prior.get('sources', []) if s.get('id') == sid), {})
        try:
            # Include discovery/coverage reads and memo hits for THIS source.
            client.used_urls = set()
            rows, coverage, source_updated, notes = loaders[sid]()
            guard(sid, rows, old)
            status, stamp = 'fresh', client.fetched_at(*client.used_urls)
        except Exception as exc:
            rows, status, stamp = old, ('retained' if old else 'unavailable'), prev.get('fetchedAt')
            source_updated = prev.get('sourceUpdatedAt')
            coverage = prev.get('coverage', 'Brak zweryfikowanego pokrycia')
            notes = [sid + ': ' + str(exc)]
        records.extend(rows)
        sources.append({'id': sid, 'name': name, 'url': url, 'fetchedAt': stamp, 'sourceUpdatedAt': source_updated,
                        'status': status, 'coverage': coverage, 'recordCount': len(rows), 'warnings': notes, 'reuse': REUSE})
        warnings.extend(notes)
    return {'records': records, 'sources': sources, 'warnings': warnings}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=Path('.cache'))
    parser.add_argument('--prior', type=Path)
    args = parser.parse_args()
    previous = json.loads(args.prior.read_text()) if args.prior else None
    result = collect(args.cache, previous)
    (args.cache / 'public-contribution.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    report = {'records': len(result['records']), 'sources': result['sources'], 'mapped': sum(bool(r['geometries']) for r in result['records']),
              'geometries': sum(len(r['geometries']) for r in result['records']), 'warnings': result['warnings']}
    (args.cache / 'public-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
