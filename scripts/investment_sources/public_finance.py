"""Adopted PDF finance tables. Fail closed on unsupported or incomplete layouts."""
from __future__ import annotations
import re
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from .public import BIP, clean, money, record, cost, fact, event, iso, categorize, list_articles, menu_node


def parse_budget_tables(tables):
    out, department, chapter, total = [], '', '', None
    chapter_total, chapter_sum = None, Decimal(0)
    for table in tables:
        for index, raw in enumerate(table['rows']):
            if len(raw) != 7:
                raise ValueError('Nieobsługiwany układ tabeli budżetu')
            r = [clean(x) for x in raw]
            if r[0] == 'Dział':
                if r[3] != 'Zadanie' or r[6] != 'Po zmianie':
                    raise ValueError('Brak kolumny końcowego planu')
                continue
            if not any(r):
                continue
            if r[0].isdigit():
                department = r[0]
            if r[1].isdigit():
                if chapter_total is not None and chapter_sum != chapter_total:
                    raise ValueError('Suma rozdziału budżetu niezgodna: ' + chapter)
                chapter, chapter_total, chapter_sum = r[1], money(r[6]), Decimal(0)
            if r[2] == 'Razem':
                if total is not None:
                    raise ValueError('Powtórzony wynik tabeli')
                total = money(r[6])
            if r[3]:
                if not department or not chapter:
                    raise ValueError('Brak klasyfikacji budżetowej')
                amount = money(r[6])
                if amount < 0:
                    raise ValueError('Ujemny plan wydatków')
                chapter_sum += amount
                out.append({'key': f"p{table['page']}-r{index}", 'page': table['page'], 'title': r[3],
                            'department': department, 'chapter': chapter, 'amount': float(amount)})
    if chapter_total is not None and chapter_sum != chapter_total:
        raise ValueError('Suma ostatniego rozdziału niezgodna')
    summed = sum((Decimal(str(r['amount'])) for r in out), Decimal(0))
    if total is None or not out or summed != total:
        raise ValueError('Niekompletna tabela 2a lub niezgodna suma')
    return out, {'rows': len(out), 'annualPlanTotal': float(total)}


def parse_wpf_tables(tables):
    out, right, totals, totals_right = {}, {}, None, None
    for table in tables:
        rows = table['rows']
        header = [clean(c) for r in rows[:3] for c in r]
        if 'Nazwa i cel' in header:
            years = [int(m[1]) for x in header if (m := re.search(r'\bLimit (\d{4})\b', x))]
            if len(years) != 5:
                raise ValueError('Nierozpoznane lata limitów WPF')
            for raw in rows:
                r = [clean(x) for x in raw]
                if r[0] == '1.b':
                    totals = [money(x) for x in r[5:]]
                if not re.fullmatch(r'1\.[123]\.2\.\d+', r[0]):
                    continue
                if len(r) != 11 or r[0] in out or not r[1] or not r[2]:
                    raise ValueError('Duplikat / niepełny wiersz WPF')
                start, end = int(r[3]), int(r[4])
                if not (2000 <= start <= end <= 2100):
                    raise ValueError('Nieprawidłowy okres WPF')
                out[r[0]] = {'key': r[0], 'title': r[1], 'unit': r[2], 'from': start, 'to': end,
                             'amount': float(money(r[5])), 'limits': dict(zip(years, [float(money(x)) for x in r[6:]])), 'page': table['page']}
        elif any(re.fullmatch(r'Limit \d{4}', x) for x in header):
            years = [int(m[1]) for x in header if (m := re.search(r'\bLimit (\d{4})\b', x))]
            if len(years) != 4 or not any('zobowiązań' in x for x in header):
                raise ValueError('Nieobsługiwana kontynuacja WPF')
            for raw in rows:
                r = [clean(x) for x in raw]
                if r[0] == '1.b':
                    totals_right = [money(x) for x in r[1:]]
                if not re.fullmatch(r'1\.[123]\.2\.\d+', r[0]):
                    continue
                if len(r) != 6 or r[0] in right:
                    raise ValueError('Duplikat kontynuacji WPF')
                right[r[0]] = {'limits': dict(zip(years, [float(money(x)) for x in r[1:5]])), 'commitment': float(money(r[5]))}
    if not out or set(out) != set(right) or totals is None or totals_right is None:
        raise ValueError('Niekompletne strony WPF lub brak sumy majątkowej')
    for key, r in out.items():
        r['limits'].update(right[key]['limits'])
        r['commitment'] = right[key]['commitment']
    all_years = sorted(next(iter(out.values()))['limits'])
    observed = [sum((Decimal(str(r['amount'])) for r in out.values()), Decimal(0))]
    observed += [sum((Decimal(str(r['limits'][y])) for r in out.values()), Decimal(0)) for y in all_years]
    observed += [sum((Decimal(str(r['commitment'])) for r in out.values()), Decimal(0))]
    if observed != totals + totals_right:
        raise ValueError('Suma majątkowych przedsięwzięć WPF lub limitów niezgodna')
    return list(out.values()), {'rows': len(out), 'totalOutlay': float(observed[0]),
                               'annualLimits': {str(y): float(observed[i + 1]) for i, y in enumerate(all_years)},
                               'commitmentTotal': float(observed[-1])}


MONTHS = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia']

def adoption(title):
    m = re.search(r'(?:z dnia|z)\s+(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})', title, re.I)
    if not m:
        raise ValueError('Brak daty przyjęcia uchwały')
    return datetime(int(m[3]), MONTHS.index(m[2].lower()) + 1, int(m[1])).date().isoformat()


def finance_menu(client, sid):
    budget = menu_node(client, '19938')
    year = str(datetime.now(ZoneInfo('Europe/Warsaw')).year)
    matches = [n for n in budget.get('children') or [] if n['name'] == year]
    if len(matches) != 1:
        raise ValueError('Brak odkrytego rocznika budżetu ' + year)
    node = menu_node(client, matches[0]['id'])
    needle = 'budżet ' if sid == 'budget' else 'wieloletnia'
    children = [n for n in node.get('children') or [] if needle in n['name'].lower()]
    if len(children) != 1:
        raise ValueError('Brak jednoznacznego menu ' + sid)
    return children[0]['id'], int(year)


def pdf_tables(doc, sid):
    tables, started, ended = [], False, False
    for number, page in enumerate(doc):
        txt = page.get_text()
        if sid == 'budget':
            if re.search(r'(?:Zmiany w planie|Plan) wydatków majątkowych', txt):
                started = True
            if not started or ended:
                continue
        for table in page.find_tables(strategy='lines_strict').tables:
            rows = table.extract()
            header = ' '.join(clean(c) for row in rows[:3] for c in row)
            if sid == 'budget' and 'Zadanie' in header and 'Po zmianie' in header:
                tables.append({'page': number + 1, 'rows': rows})
                if any(clean(r[2]) == 'Razem' for r in rows if len(r) == 7):
                    ended = True
            if sid == 'wpf' and 'L.p.' in header and ('Nazwa i cel' in header or 'Limit zobowiązań' in header):
                tables.append({'page': number + 1, 'rows': rows})
    if not tables:
        raise ValueError('Brak pełnej obsługiwanej tabeli przyjętej uchwały')
    return tables


def check_mayor_changes(entries, council_date):
    count = 0
    for entry in entries:
        fields = {f['alias']: f['value'] for f in entry.get('aliasFields', [])}
        title = fields.get('title', '')
        if not re.search(r'zmian.*(?:uchwał.*budżet|budżet)', title, re.I):
            continue
        count += 1
        try:
            when = adoption(title + ' ' + fields.get('lead', ''))
        except ValueError as exc:
            raise ValueError('Niezweryfikowana data zarządzenia zmieniającego budżet') from exc
        if when > council_date:
            raise ValueError('Nowsza zmiana burmistrza wymaga uzgodnienia pełnej tabeli: ' + entry['id'])
    return count


def load_finance(client, sid, fetched=None):
    menu, year = finance_menu(client, sid)
    entries = list_articles(client, menu)
    articles = [client.json(BIP + 'api/articles/' + e['id']) for e in entries]
    adopted = [a for a in articles if 'uchwała' in a['title'].lower() and 'projekt' not in a['title'].lower()]
    if not adopted:
        raise ValueError('Brak uchwał przyjętych')
    latest = max(adopted, key=lambda a: adoption(a['title']))
    date = adoption(latest['title'])
    mayor_coverage = ''
    if sid == 'budget':
        mayor_entries = list_articles(client, '23689')
        changes = check_mayor_changes(mayor_entries, date)
        mayor_coverage = f' Zarządzenia burmistrza 2026 (menu 23689): {len(mayor_entries)} pełnych pozycji; {changes} zmian budżetu, żadna późniejsza od uchwały.'
        if year != 2026:
            raise ValueError('Rocznik zarządzeń 2026 wymaga ponownego odkrycia dla nowego roku')
    original = min(adopted, key=lambda a: adoption(a['title']))
    attachments = [a for a in latest['attachments'] if not a.get('deleted') and a.get('extension', '').lower() == 'pdf' and a.get('downloadable')]
    if len(attachments) != 1:
        raise ValueError('Niejednoznaczny załącznik uchwały')
    attachment = attachments[0]
    url = BIP + 'api/files/' + str(attachment['id'])
    doc = client.pdf(url)
    # Require a replacement, not an amendment-only delta list.
    content = ' '.join(page.get_text() for page in list(doc)[:2])
    if sid == 'budget' and not re.search(r'Tabela nr 2a.*?otrzymuje brzmienie', content, re.S):
        raise ValueError('Najnowsza uchwała nie potwierdza zastępującej tabeli 2a')
    rows, totals = (parse_budget_tables if sid == 'budget' else parse_wpf_tables)(pdf_tables(doc, sid))
    # Table bytes and both article identities supply the record's facts.
    fetched = client.fetched_at(url, BIP + 'api/articles/' + latest['id'], BIP + 'api/articles/' + original['id'])
    updated = iso(latest['basicData'].get('modify') or latest['basicData'].get('active'))
    output = []
    for row in rows:
        key = str(attachment['id']) + '-' + row['key']
        r = record(sid, key, url, row['title'], fetched)
        r.update(recordType='budget-task', category=categorize(row['title']), status='Plan przyjęty — nie potwierdzenie wykonania',
                 statusAsOf=date, sourceUpdatedAt=updated, years=[year] if sid == 'budget' else list(range(row['from'], row['to'] + 1)))
        r['summary'] = 'Pozycja pełnej przyjętej tabeli finansowej; kwoty nie oznaczają zapłaty ani zakończenia robót.'
        fact(r, 'Uchwała', latest['title'], BIP + latest['link'])
        fact(r, 'Uchwała pierwotna (bez mieszania kwot)', original['title'], BIP + original['link'])
        for initial in original.get('attachments', []):
            if not initial.get('deleted') and initial.get('downloadable'):
                fact(r, 'Dokument pierwotny', initial['name'], BIP + 'api/files/' + str(initial['id']))
        fact(r, 'Załącznik', attachment['name'], url)
        fact(r, 'Strona PDF / wiersz źródłowy', str(row['page']) + ' / ' + row['key'])
        event(r, 'adoption-' + latest['id'], 'Przyjęcie uchwały', date, BIP + latest['link'])
        if sid == 'budget':
            fact(r, 'Dział / rozdział', row['department'] + ' / ' + row['chapter'])
            cost(r, 'annual-plan', row['amount'], 'Plan wydatków majątkowych po zmianie', year)
        else:
            fact(r, 'Jednostka odpowiedzialna / koordynująca', row['unit'])
            fact(r, 'Okres realizacji', str(row['from']) + '–' + str(row['to']))
            cost(r, 'total-outlay', row['amount'], 'Łączne nakłady wieloletnie')
            for y, amount in sorted(row['limits'].items()):
                cost(r, 'annual-limit', amount, 'Limit wydatków WPF', y)
            fact(r, 'Limit zobowiązań (nie wartość umowy)', f"{row['commitment']:.2f} PLN")
        output.append(r)
    coverage = f"Menu {menu}: {len(entries)}/{len(entries)} artykułów. Najnowsza przyjęta uchwała: {date}, załącznik {attachment['id']}. Pełne wiersze majątkowe: {len(rows)}; sumy uzgodnione: " + str(totals) + mayor_coverage
    return output, coverage, updated, []
