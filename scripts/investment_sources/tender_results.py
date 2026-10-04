"""Tender outcome facts read from the contracting authority's own published PDFs.

Only two document types are parsed, and only when their wording is unambiguous:
"Informacja o wyborze oferty" (winner, gross offer price per part, planned
contract date) and "Informacja z otwarcia ofert" (amount reserved per part).
Anything that does not fit is left as a plain document link: a guessed price
is worse than no price.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .public import clean

MONTHS = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia',
          'września', 'października', 'listopada', 'grudnia']
AMOUNT = r'(\d{1,3}(?:[ . ]\d{3})+|\d+),(\d{2})\s*(?:zł|PLN)'
PART = r'(?:\(\s*)?(?:część|cz\.)\s*([A-Z]|\d{1,2})\s*\)?\s*:\s*(?:cena\s*)?'
SELECTION_NAME = re.compile(r'wybor\w*\s+(?:najkorzystniejszej\s+)?ofert', re.I)
CANCELLATION_NAME = re.compile(r'unieważni', re.I)
OPENING_NAME = re.compile(r'otwarci\w*\s+ofert', re.I)


def amount(whole, cents):
    value = Decimal(re.sub(r'[ . ]', '', whole) + '.' + cents)
    if value <= 0 or value > Decimal('10000000000'):
        raise ValueError('Kwota poza zakresem')
    return float(value)


def polish_date(text):
    m = re.search(r'(\d{1,2})[ .-]+(' + '|'.join(MONTHS) + r'|\d{1,2})[ .-]+(\d{4})', text, re.I)
    if not m:
        return None
    month = int(m[2]) if m[2].isdigit() else MONTHS.index(m[2].lower()) + 1
    try:
        return date(int(m[3]), month, int(m[1])).isoformat()
    except ValueError:
        return None


def part_names(text):
    """Map part letter/number -> short description from the subject sentence."""
    subject = text.split('decyzją', 1)[0]
    marker = r'(?:(?:Cz\.|cz\.|część)\s*|(?<=części: ))([A-Z]|\d{1,2})\s*[–-]\s*'
    starts = list(re.finditer(marker, subject))
    names = {}
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(subject)
        name = re.sub(r'\s*(?:oraz|i)\s*$', '', subject[m.end():end].strip(' ,;:„”"’\''))
        name = name.rstrip(' ,;:„”"’\'')
        if name and m[1] not in names:
            names[m[1]] = name[:160]
    return names


def parse_selection(text):
    """Return {'winner', 'prices': [{'part', 'name', 'amount'}], 'contractDate'} or raise."""
    t = clean(text)
    if not re.search(r'INFORMACJA O WYBORZE OFERTY', t, re.I):
        raise ValueError('To nie jest informacja o wyborze oferty')
    if re.search(r'unieważni\w* postępowani', t[:600], re.I):
        raise ValueError('Dokument dotyczy unieważnienia')
    head = re.search(r'została wybrana oferta(.*?)Uzasadnienie', t, re.S)
    if not head:
        raise ValueError('Brak sekcji wyboru oferty')
    head = head.group(1)
    if len(re.findall(r'z siedzibą', head)) != 1:
        raise ValueError('Niejednoznaczny wykonawca')
    winner = re.search(r'[Ww]ykonawc\w*\s*:\s*(?:w zakresie [^:]{0,60}:\s*)?(.+?)\s*,?\s*z siedzibą', head)
    if not winner or not 3 <= len(winner.group(1)) <= 160:
        raise ValueError('Brak nazwy wykonawcy')
    priced = head.split('brutto', 1)
    if len(priced) != 2:
        raise ValueError('Brak ceny brutto')
    amounts = re.findall(AMOUNT, priced[1])
    parts = re.findall(PART + AMOUNT, priced[1])
    names = part_names(t)
    if parts:
        if len(parts) != len(amounts) or len({p[0] for p in parts}) != len(parts):
            raise ValueError('Ceny części niejednoznaczne')
        prices = [{'part': p, 'name': names.get(p, ''), 'amount': amount(w, c)} for p, w, c in parts]
    elif len(amounts) == 1:
        prices = [{'part': None, 'name': '', 'amount': amount(*amounts[0])}]
    else:
        raise ValueError('Niejednoznaczna cena oferty')
    signed = re.search(r'zostanie podpisana w dniu\s+(.{6,30}?\d{4})', t)
    return {'winner': clean(winner.group(1)), 'prices': prices, 'contractDate': polish_date(signed.group(1)) if signed else None}


def parse_financing(text):
    """Amount reserved per part from the opening notice: [{'part', 'amount'}]."""
    t = clean(text)
    m = re.search(r'Kwota przeznaczona na realizację zamówienia to\s*:?\s*(.{0,260}?)(?:\s2\.\s|Otwarto)', t)
    if not m:
        raise ValueError('Brak kwoty przeznaczonej na realizację')
    body = m.group(1)
    body = re.split(r',?\s*w tym\s*:', body)[0]
    after = re.findall(AMOUNT + r'\s*[–-]\s*część\s+([A-Z]|\d{1,2})\b', body)
    before = re.findall(r'część\s+([A-Z]|\d{1,2})\s*:\s*' + AMOUNT, body)
    amounts = re.findall(AMOUNT, body)
    if after and len(after) == len(amounts):
        return [{'part': p, 'amount': amount(w, c)} for w, c, p in after]
    if before and len(before) == len(amounts):
        return [{'part': p, 'amount': amount(w, c)} for p, w, c in before]
    if len(amounts) == 1:
        return [{'part': None, 'amount': amount(*amounts[0])}]
    raise ValueError('Niejednoznaczna kwota na sfinansowanie')


def published(documents):
    rows = [d for d in documents if d.get('tenderDocumentState') == 'Published' and not d.get('deleteDate')]
    def order(d):
        suffix = re.search(r'_(\d+)$', d.get('objectId') or '')
        return (d.get('publishedDate') or '', int(suffix.group(1)) if suffix else 0)
    return sorted(rows, key=order)


def latest_selection(documents):
    """The newest selection notice, unless something was cancelled after it."""
    rows = published(documents)
    picks = [i for i, d in enumerate(rows) if SELECTION_NAME.search(d.get('name') or '') and not CANCELLATION_NAME.search(d.get('name') or '')]
    if not picks:
        return None
    last = picks[-1]
    if any(CANCELLATION_NAME.search(d.get('name') or '') for d in rows[last + 1:]):
        return None
    return rows[last]


def first_opening(documents):
    rows = [d for d in published(documents) if OPENING_NAME.search(d.get('name') or '') and 'dodatkow' not in (d.get('name') or '').lower()]
    return rows[0] if rows else None
