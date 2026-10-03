"""Official WordPress read API; source-dated short factual news, no mirrored prose."""
from __future__ import annotations
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from .public import NEWS, record, fact, event, iso, day, text, categorize, safe_url

RELEVANT = re.compile(r'budow|przebudow|rozbudow|moderniz|remont|skatepark|boisk|inwestyc|kanaliz|wodoci|roboty drogowe|zbiornik|\bsuw\b|plac(?:u|ów)? zabaw|przetarg', re.I)


def relevant_title(title):
    return bool(RELEVANT.search(title)) and not re.search(r'na sprzedaż|sprzedaż nieruchomości|poszukuje kandydatów|na stanowisko', title, re.I)


def parse_news(post, fetched):
    key = str(post['id'])
    url = safe_url(post['link'])
    title = text(post['title']['rendered'])
    content = text(post.get('content', {}).get('rendered', ''))
    published = iso(post['date_gmt'] + 'Z')
    updated = iso(post['modified_gmt'] + 'Z')
    r = record('municipal-news', key, url, title, fetched)
    r.update(recordType='news', category=categorize(title), investor='unknown', investorName=None, status='Komunikat źródłowy — etap robót do odczytu w źródle',
             statusAsOf=published[:10], sourceUpdatedAt=updated, years=[int(published[:4])])
    r['summary'] = 'Urząd opublikował informację dotyczącą infrastruktury lub postępowania inwestycyjnego. Szczegóły w linkowanym źródle.'
    event(r, 'wp-' + key, 'Publikacja komunikatu gminy', published, url)
    fact(r, 'Publikacja źródła', published)
    slug = post.get('slug')
    if slug == 'skatepark-przy-szkole-w-plochocinie':
        if not re.search(r'zakończ', content, re.I):
            raise ValueError('Zmienił się dowód zakończenia skateparku')
        r.update(status='Prace zakończone — komunikat gminy', investor='municipal', investorName='Gmina Ożarów Mazowiecki', locality='Płochocin', category='sport i rekreacja')
        r['summary'] = 'Gmina poinformowała o zakończeniu budowy skateparku przy szkole w Płochocinie.'
        if '24' in content and '16' in content:
            fact(r, 'Wymiary podane przez gminę', '24 × 16 m; brak zweryfikowanego obrysu GIS')
    elif slug == 'rusza-budowa-ulicy-kapuckiej':
        if not re.search(r'umow', content, re.I):
            raise ValueError('Zmienił się dowód umowy Kapuckiej')
        r.update(status='Umowa podpisana — planowana budowa', investor='municipal', investorName='Gmina Ożarów Mazowiecki', locality='Ożarów Mazowiecki', address='ul. Kapucka', category='drogi i transport')
        r['summary'] = 'Gmina ogłosiła zawarcie umowy na pierwszy etap ulicy Kapuckiej. Pozostałe odcinki są odrębnymi pracami projektowymi.'
        if '285' in content:
            fact(r, 'Odcinek I etapu', 'Widok–Kanał Ożarowski; około 285 m')
        if re.search(r'wrze[śs].*2027', content, re.I):
            fact(r, 'Planowany koniec (precyzja: miesiąc)', 'wrzesień 2027; nie przypisano sztucznej daty dziennej')
            r['years'].append(2027)
    elif slug == 'boisko-sportowe-szkola-podstawowa-umiastow':
        r.update(status='Przetarg ogłoszony — nie rozpoczęta budowa', investor='municipal', investorName='Gmina Ożarów Mazowiecki', locality='Umiastów', category='sport i rekreacja')
        r['summary'] = 'Gmina poinformowała o przetargu na szkolne boisko w Umiastowie.'
        if re.search(r'9\s*miesi', content):
            fact(r, 'Termin względny', '9 miesięcy od podpisania umowy — nie od daty komunikatu')
    elif slug == 'uwaga-roboty-drogowe-w-gm-ozarow-mazowiecki':
        r.update(status='Rozpoczęcie zapowiedziane — data przyszła względem komunikatu', investor='county', investorName='Zarząd Dróg Powiatowych',
                 locality='Pogroszew / Umiastów', category='drogi i transport')
        r['summary'] = 'Zarząd dróg powiatowych zapowiedział wzmocnienie nawierzchni drogi 4120W między Pogroszewem a Umiastowem.'
        m = re.search(r'(\d{2})\.(\d{2})\.(20\d{2})', content)
        if m:
            date = day(f'{m[3]}-{m[2]}-{m[1]}')
            r['dates'].append({'kind': 'planned-start', 'date': date, 'label': 'Zapowiedziany początek robót', 'sourceUrl': url})
        if '1600' in content:
            fact(r, 'Zakres', 'DP 4120W; około 1600 m, DP 4121W–DW 718')
    return r


def load_news(client, fetched=None):
    year = datetime.now(ZoneInfo('Europe/Warsaw')).year
    after = f'{year}-01-01T00:00:00'
    posts, seen, total, pages = [], set(), None, 0
    receipts = {}
    for page in range(1, 101):
        url = NEWS + f'wp-json/wp/v2/posts?per_page=100&page={page}&after={after}&orderby=date&order=desc'
        response = client.get(url)
        n = response.headers.get('X-WP-Total')
        max_page = response.headers.get('X-WP-TotalPages')
        if n is None or max_page is None or not n.isdigit() or not max_page.isdigit():
            raise ValueError('Brak kanonicznych liczników WordPress')
        if total is not None and total != int(n):
            raise ValueError('Zmieniony licznik WordPress podczas pobierania')
        total, pages = int(n), int(max_page)
        data = response.json()
        if not isinstance(data, list) or (not data and total):
            raise ValueError('Ucięta lista aktualności')
        for post in data:
            if not isinstance(post.get('id'), int) or post['id'] in seen:
                raise ValueError('Powtórzona / uszkodzona strona aktualności')
            seen.add(post['id'])
            receipts[post['id']] = client.fetched_at(url)
        posts.extend(data)
        if page >= pages:
            break
    if len(posts) != total:
        raise ValueError('Niekompletny rocznik aktualności')
    relevant = [p for p in posts if relevant_title(text(p['title']['rendered']))]
    records = [parse_news(p, receipts[p['id']]) for p in relevant]
    coverage = f'WordPress {year}: {len(posts)}/{total} komunikatów, {pages} stron; {len(records)} tytułów spełnia jawny filtr infrastruktury/zamówień. Nie jest to pełny rejestr wszystkich inwestycji; pozostałe tytuły nie zostały zakwalifikowane.'
    updated = max((r['sourceUpdatedAt'] for r in records), default=None)
    return records, coverage, updated, ['Aktualności są odrębnymi datowanymi dowodami; nie nadpisują historycznych statusów innych źródeł. Filtr tytułów może pominąć artykuły bez infrastruktury w tytule.']
