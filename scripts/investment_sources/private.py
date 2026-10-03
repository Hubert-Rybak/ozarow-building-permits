"""Environmental/private/regional/EU facts; no publication side effects.

Only the cache path is written. Use collect(cache, prior_full_dataset) from the
central importer. Evidence is SHA-256 + original receipt, not filesystem mtime.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

import requests
from shapely import wkt
from shapely.geometry import mapping

from .private_catalog import ENVIRONMENT, REGIONS, AURA, HILLWOOD, HOME, CPK_API, PWZ, A2, GAS, FE_PAGE, FE_SUMMARIES

BIP = 'https://bip.ozarow-mazowiecki.pl/'
ULDK = 'https://uldk.gugik.gov.pl/'
WORKERS = 4
MAX_ARTICLES = 2000
MAX_DOWNLOAD = 100_000_000
RECORD_KEYS = set('id sourceId sourceRecordId sourceUrl title recordType investor investorName category locality address status statusAsOf summary years costs dates geometries parcelIds events facts relatedIds warnings fetchedAt sourceUpdatedAt'.split())
SOURCE_INFO = {
    'environmental': ('BIP — postępowania środowiskowe', BIP + 'm,19681,decyzje-srodowiskowe.html'),
    'private-projects': ('Prospekty deweloperskie i oficjalne źródła inwestorów', AURA),
    'regional': ('Inwestycje kolejowe, krajowe i powiatowe', BIP + 'a,95745,postepowanie-w-sprawie-ustalenia-lokalizacji-linii-kolejowej-w-celu-realizacji-inwestycji-budowa-tun.html'),
    'eu-funding': ('Fundusze Europejskie — miejsce realizacji projektu', FE_PAGE),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_url(value: str) -> str:
    p = urlparse(value)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        raise ValueError('Unsafe source URL')
    return value


def source_time(value: str | None) -> str | None:
    if not value or value == 'Brak danych':
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('Europe/Warsaw'))
    return dt.astimezone(timezone.utc).isoformat()


def edited_time(basic: dict):
    if basic.get('modify'):
        return source_time(basic['modify'])
    if basic.get('originActive') and basic.get('active') != basic['originActive']:
        return source_time(basic['active'])
    return None


def text_html(raw: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', raw))).strip()


class Fetcher:
    """Bounded real downloads, private raw cache, original immutable receipts.

    Source bodies are reusable 24h; ULDK positive verified replies 30 days.
    Every cache reuse validates exact URL/hash/real timestamp/TTL. Never fallback
    to expired raw files after a network error. Unverified ULDK never cached.
    """
    def __init__(self, cache: Path):
        self.root = cache / 'private-http'
        self.root.mkdir(parents=True, exist_ok=True)
        self.receipts: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.stats = {'downloads': 0, 'reused': 0}

    def paths(self, url: str):
        key = digest(url.encode())
        return self.root / (key + '.bin'), self.root / (key + '.json')

    def pwz_ca_bundle(self):
        """Complete PWZ's missing intermediate without disabling TLS.

        AIA issuer inspected from the live certificate. Download it over HTTPS
        from Certum, then verify against EXISTING roots before adding the chain.
        This adds no new trust anchor and never changes system certificates.
        """
        url = 'https://certumovtlsg2r39ca.repository.certum.pl/certumovtlsg2r39ca.cer'
        b,t,h = self.get(url, 30)
        der = self.root / 'pwz-issuer.der'
        pem = self.root / 'pwz-issuer.pem'
        bundle = self.root / 'pwz-chain.pem'
        der.write_bytes(b)
        subprocess.run(['openssl','x509','-inform','DER','-in',str(der),'-out',str(pem)],check=True,capture_output=True,timeout=15)
        subprocess.run(['openssl','verify','-CAfile',requests.certs.where(),str(pem)],check=True,capture_output=True,timeout=15)
        bundle.write_text(Path(requests.certs.where()).read_text() + '\n' + pem.read_text())
        return str(bundle)

    def store(self, url: str, data: bytes, fetched: str):
        safe_url(url)
        stamp = datetime.fromisoformat(fetched)
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('Invalid original receipt timestamp')
        body, meta = self.paths(url)
        evidence = {'url': url, 'fetchedAt': fetched, 'sha256': digest(data), 'bytes': len(data)}
        # Write to thread-specific temporary files, then atomic per-file replace.
        suffix = '.' + str(threading.get_ident()) + '.tmp'
        bt, mt = Path(str(body) + suffix), Path(str(meta) + suffix)
        bt.write_bytes(data)
        mt.write_text(json.dumps(evidence, ensure_ascii=False), encoding='utf-8')
        bt.replace(body)
        mt.replace(meta)
        with self.lock:
            self.receipts[url] = evidence

    def get(self, url: str, ttl_days: float = 1, validator=None):
        safe_url(url)
        body, meta = self.paths(url)
        if body.exists() and meta.exists():
            try:
                e = json.loads(meta.read_text())
                b = body.read_bytes()
                age = datetime.now(timezone.utc) - datetime.fromisoformat(e['fetchedAt'])
                if e['url'] != url or e['sha256'] != digest(b) or not timedelta(0) <= age < timedelta(days=ttl_days):
                    raise ValueError('Expired or changed receipt')
                if validator:
                    validator(b.decode('utf-8'))
                with self.lock:
                    self.receipts[url] = e
                    self.stats['reused'] += 1
                return b, e['fetchedAt'], e['sha256']
            except (ValueError, KeyError, TypeError, OSError):
                pass
        failure = None
        for attempt in range(3):
            try:
                ca = self.pwz_ca_bundle() if urlparse(url).hostname in ('pwz.pl','www.pwz.pl') else True
                with requests.get(url, timeout=(15, 75), stream=True, verify=ca, headers={'User-Agent': 'Radar-Ozarow-source-import/1.0'}) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_content(128 * 1024):
                        size += len(chunk)
                        if size > MAX_DOWNLOAD:
                            raise ValueError('Source download cap exceeded')
                        chunks.append(chunk)
                    b = b''.join(chunks)
                if not b:
                    raise ValueError('Empty source reply')
                if validator:
                    validator(b.decode('utf-8'))
                stamp = now()
                self.store(url, b, stamp)
                with self.lock:
                    self.stats['downloads'] += 1
                return b, stamp, digest(b)
            except (requests.RequestException, ValueError) as exc:
                failure = exc
                if attempt < 2:
                    time.sleep(0.4 * 2 ** attempt)
        raise ValueError(f'Download/validation failed: {url}: {type(failure).__name__}') from failure

    def json(self, url: str):
        b, t, _ = self.get(url)
        return json.loads(b), t


def source_meta(source_id: str) -> dict:
    name, url = SOURCE_INFO[source_id]
    return {'id': source_id, 'name': name, 'url': url, 'fetchedAt': None,
            'sourceUpdatedAt': None, 'status': 'unavailable', 'coverage': '',
            'recordCount': 0, 'warnings': [],
            'reuse': 'Fakty, własne krótkie podsumowania i atrybucja. Bez kopii opisów, zdjęć, kontaktów i geometrii marketingowych o nieustalonych prawach.'}


def new_record(source_id, source_record_id, url, title, stamp):
    safe_url(url)
    return {'id': source_id + ':' + source_record_id, 'sourceId': source_id,
            'sourceRecordId': source_record_id, 'sourceUrl': url, 'title': title,
            'recordType': 'project', 'investor': 'unknown', 'investorName': None,
            'category': 'inne', 'locality': '', 'address': '', 'status': 'Status robót niepotwierdzony',
            'statusAsOf': None, 'summary': '', 'years': [], 'costs': [], 'dates': [],
            'geometries': [], 'parcelIds': [], 'events': [], 'facts': [], 'relatedIds': [],
            'warnings': [], 'fetchedAt': stamp, 'sourceUpdatedAt': None}


def fact(record, label, value, url):
    entry = {'label': label, 'value': str(value), 'sourceUrl': safe_url(url)}
    if entry not in record['facts']:
        record['facts'].append(entry)


def add_date(record, kind, value, label, url):
    date.fromisoformat(value)
    entry = {'kind': kind, 'date': value, 'label': label, 'sourceUrl': safe_url(url)}
    if entry not in record['dates']:
        record['dates'].append(entry)
    record['years'] = sorted(set(record['years'] + [int(value[:4])]))


def parcel_id(unit: str, region: str, parcel: str) -> str:
    if not re.fullmatch(r'143206_[45]', unit) or not re.fullmatch(r'\d{4}', region) or not re.fullmatch(r'[1-9]\d*(?:/[1-9]\d*)?', parcel):
        raise ValueError('Malformed literal cadastral token; no repair')
    return unit + '.' + region + '.' + parcel


def validate_region_reply(reply: str, expected: str):
    lines = [x.strip() for x in reply.splitlines() if x.strip()]
    if len(lines) != 2 or lines[0] != '0':
        raise ValueError('Region status/row count')
    fields = lines[1].split('|')
    if len(fields) != 3 or fields[0] != expected or fields[2] != 'Ożarów Mazowiecki':
        raise ValueError('Region identity/municipality mismatch')
    if expected in REGIONS and fields[1] != REGIONS[expected]:
        raise ValueError('Region name mismatch')
    return fields


def validate_unit_reply(reply: str):
    lines = [s.strip() for s in reply.splitlines() if s.strip()]
    if len(lines) != 2 or lines[0] != '0' or lines[1].split('|') != ['143206_3','Ożarów Mazowiecki','powiat warszawski zachodni']:
        raise ValueError('Expected exact municipality/county mismatch')


def validate_parcel_reply(reply: str, expected: str):
    tokens = expected.split('.')
    if len(tokens) != 3 or parcel_id(*tokens) != expected:
        raise ValueError('Invalid expected parcel')
    lines = [x.strip() for x in reply.splitlines() if x.strip()]
    if len(lines) != 2 or lines[0] != '0':
        raise ValueError('Parcel status/row count')
    fields = lines[1].split('|')
    if len(fields) != 2 or fields[1] != expected or not fields[0].startswith('SRID=4326;'):
        raise ValueError('Parcel identity/SRID mismatch')
    geom = wkt.loads(fields[0][10:])
    if geom.geom_type not in ('Polygon', 'MultiPolygon') or geom.is_empty or not geom.is_valid:
        raise ValueError('Invalid/nonpolygon/empty geometry')
    x1, y1, x2, y2 = geom.bounds
    if not all(math.isfinite(x) for x in (x1, y1, x2, y2)) or not (14 <= x1 <= x2 <= 25 and 49 <= y1 <= y2 <= 55):
        raise ValueError('Geometry coordinate bounds/axes')
    # JSON conversion preserves the original WKT coordinate values, no repair.
    return json.loads(json.dumps(mapping(geom)))


def resolve_parcels(records: list[dict], fetcher: Fetcher):
    ids = sorted({p for r in records for p in r['parcelIds']})
    regions = sorted({p.rsplit('.', 1)[0] for p in ids})
    verified = set()
    evidence = []
    warnings = []
    # Exact units are additionally verified, not substituted for malformed ones.
    for unit in sorted({p.split('.')[0] for p in ids}):
        url = ULDK + '?request=GetCommuneById&id=' + unit + '&result=id,commune,county'
        try:
            b,t,h = fetcher.get(url, 30, validate_unit_reply)
            evidence.append({'kind':'unit','id':unit,'url':url,'fetchedAt':t,'sha256':h,'response':b.decode()})
        except ValueError as exc:
            warnings.append(f'ULDK: niepotwierdzona jednostka {unit}: {exc}')
            continue
        for region in [r for r in regions if r.startswith(unit + '.')]:
            url = ULDK + '?request=GetRegionById&id=' + region + '&result=id,region,commune'
            try:
                b,t,h = fetcher.get(url, 30, lambda raw: validate_region_reply(raw, region))
                verified.add(region)
                evidence.append({'kind':'region','id':region,'url':url,'fetchedAt':t,'sha256':h,'response':b.decode()})
            except ValueError as exc:
                warnings.append(f'ULDK: niepotwierdzony obręb {region}: {exc}')
    def one(pid):
        if pid.rsplit('.', 1)[0] not in verified:
            return pid, None, 'niepotwierdzony obręb'
        url = ULDK + '?request=GetParcelById&id=' + pid + '&result=geom_wkt,id&srid=4326'
        try:
            b,t,h = fetcher.get(url, 30, lambda raw: validate_parcel_reply(raw, pid))
            return pid, {'geometry':validate_parcel_reply(b.decode(),pid), 'url':url,'fetchedAt':t,'sha256':h,'response':b.decode()}, None
        except ValueError:
            return pid, None, 'brak poprawnej odpowiedzi exact ID/SRID/Polygon'
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        results = dict((pid,(data,err)) for pid,data,err in executor.map(one, ids))
    for record in records:
        for pid in record['parcelIds']:
            data, error = results[pid]
            if error:
                record['warnings'].append(f'ULDK: działka {pid} niezmapowana — {error}.')
                continue
            note = 'Działka ewidencyjna wskazana w źródle; nie obrys budynku, całego campusu ani dokładnie zajętej części działki.'
            if 'część działki 7' in record['title'] and pid.endswith('.7'):
                note += ' Źródło dotyczy wyłącznie części działki 7; pokazano pełną działkę EGiB.'
            record['geometries'].append({'type':'Feature','geometry':data['geometry'],'properties':{
                'id':record['id'] + ':parcel:' + pid,'accuracy':'parcel','sourceUrl':data['url'],
                'parcelId':pid,'note':note,'fetchedAt':data['fetchedAt'],'sourceUpdatedAt':None}})
    for pid,(data,err) in results.items():
        if data:
            evidence.append({'kind':'parcel','id':pid,**{k:v for k,v in data.items() if k!='geometry'}})
    return {'requested':len(ids),'verified':sum(bool(d) for d,e in results.values()),'unresolved':sum(not bool(d) for d,e in results.values()),'workers':WORKERS,'retries':3,'evidence':evidence,'warnings':warnings}


MONTHS = {'stycznia':1,'lutego':2,'marca':3,'kwietnia':4,'maja':5,'czerwca':6,'lipca':7,'sierpnia':8,'września':9,'października':10,'listopada':11,'grudnia':12}


def dated_phrase(raw: str) -> str | None:
    m = re.search(r'(\d{1,2})[.](\d{1,2})[.](20\d{2})',raw)
    if m:
        return date(int(m[3]),int(m[2]),int(m[1])).isoformat()
    m = re.search(r'(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(20\d{2})',raw,re.I)
    if m:
        return date(int(m[3]),MONTHS[m[2].lower()],int(m[1])).isoformat()
    return None


def event_type(title: str):
    s = title.lower()
    # Before-decision phrases must be recognized before a positive decision.
    if 'przed wydaniem' in s or 'możliwości zapoznania' in s or 'mozliwości zapoznania' in s:
        return 'Udostępniono dokumentację przed rozstrzygnięciem', 'consultation'
    if 'wyznaczeniu nowego terminu' in s:
        return 'Wyznaczono nowy termin załatwienia sprawy', 'deadline'
    if 'odmowy dopuszczenia organizacji' in s:
        return 'Rozstrzygnięcie o udziale organizacji — nie decyzja o inwestycji', 'participation'
    if 'zawieszeniu' in s:
        return 'Postępowanie zawieszone', 'suspension'
    if 'o wydaniu' in s and 'decyzji' in s:
        return ('Wydano zmianę decyzji środowiskowej' if 'zmiany decyzji' in s else 'Wydano decyzję środowiskową'), 'environmental-decision'
    if 'wszczęci' in s:
        return 'Wszczęto postępowanie środowiskowe', 'initiation'
    return 'Publikacja o postępowaniu środowiskowym', 'publication'


def literal_parcels(title: str) -> list[str]:
    # Only project parcel phrase BEFORE the region; no neighbouring parcels,
    # decision/permit numbers, 100m affected area or historical-before-division IDs.
    m = re.search(r'(?:dz\.\s*ew\.|działk\w*[^;]{0,35}?(?:nr|numerze|ewidencyjnym))\s*(.+?)(?:obręb|z obrębu|w miejscowości)', title, re.I)
    if not m:
        return []
    phrase = re.split(r'\(przed podziałem',m[1],flags=re.I)[0]
    numbers = re.findall(r'(?<![\d/])[1-9]\d*(?:/[1-9]\d*)?(?![\d/])',phrase)
    for ran in re.finditer(r'(\d+)\s+do\s+(?:ew\.|dz\.ew\.)?\s*(\d+)',phrase):
        start,end = map(int,ran.groups())
        if end < start or end-start > 500:
            raise ValueError('Unbounded source parcel range')
        numbers.extend(str(n) for n in range(start,end+1))
    return list(dict.fromkeys(numbers))


def parse_environment(details: list[dict], stamp: str):
    seen = set()
    groups = {}
    catalog = {article: (entry[0][0],entry) for entry in ENVIRONMENT for article in entry[0]}
    for detail in details:
        aid = str(detail['id'])
        if aid in seen:
            raise ValueError('Duplicate environmental publication')
        seen.add(aid)
        if not detail.get('title') or not detail.get('basicData',{}).get('active'):
            raise ValueError('Environmental article schema/date')
        key,entry = catalog.get(aid,(aid,None))
        groups.setdefault(key,[]).append((detail,entry))
    out = []
    for key, items in groups.items():
        items.sort(key=lambda pair:(pair[0]['basicData']['active'],str(pair[0]['id'])))
        latest, entry = items[-1]
        url = urljoin(BIP,latest['link'])
        title = entry[1] if entry else 'Postępowanie środowiskowe — publikacja ' + key
        r = new_record('environmental',key,url,title,stamp)
        r['fetchedAt'] = max([d.get('_fetchedAt',stamp) for d,_ in items] + [a['_fetchedAt'] for d,_ in items for a in d.get('attachments',[]) if a.get('_fetchedAt')])
        r['recordType'] = 'planning-case'
        r['summary'] = 'Historia postępowania środowiskowego. Publikacje i decyzje środowiskowe nie potwierdzają rozpoczęcia budowy.'
        if entry:
            _,_,investor,category,locality,address,region,parcels,investor_document = entry
            r.update(investor='municipal' if investor=='Gmina Ożarów Mazowiecki' else 'private' if investor else 'unknown',investorName=investor,category=category,locality=locality,address=address)
            if investor_document and investor:
                fact(r,'Źródło identyfikacji inwestora',investor,BIP + 'api/files/' + investor_document)
            if region:
                if not parcels:
                    source_title = items[0][0]['title']
                    parcels = literal_parcels(source_title)
                unit, region_number = region.split('.')
                r['parcelIds'] = [parcel_id(unit,region_number,p) for p in parcels]
                fact(r,'Obręb EGiB (weryfikowany ULDK)',region + ' — ' + REGIONS[region],ULDK + '?request=GetRegionById&id=' + region + '&result=id,region,commune')
            else:
                r['warnings'].append('Brak jednoznacznego poprawnego identyfikatora działek przedsięwzięcia; bez geokodowania zastępczego.')
            if key in ('95247','95357'):
                r['warnings'].append('Źródło ma niepoprawny literalny obręb 001/011. Nie dodano zera ani nie odgadnięto miejscowości.')
            if key=='95263':
                r['warnings'].append('Przedsięwzięcie to studnia na działce 143/11, nie cały campus DATA4.')
            if key=='95353':
                r['warnings'].append('Zakres 30–209, 210 i 212–213 jest źródłowy; historyczne 8/146 i 8/147 przed podziałem nie są bieżącym obrysem przedsięwzięcia.')
            if key=='95918':
                r['warnings'].append('Nagłówek BIP opisuje drogę Kapucką, załącznik decyzji opisuje regulację Kanału Ożarowskiego w ramach tej drogi. Zachowano literalną publikację bez automatycznego scalenia odrębnych zakresów.')
        else:
            r['warnings'].append('Nowa publikacja poza ręcznie zweryfikowanymi tożsamościami projektów; zachowana osobno, bez fuzzy scalenia i bez domyślnej geometrii.')
            # Avoid mirroring source prose. Project facts can be reviewed later.
        for d,_ in items:
            au = urljoin(BIP,d['link'])
            publication = d['basicData']['active'][:10]
            label,kind = event_type(d['title'])
            decision_date = dated_phrase(d['title'].split('dla przedsięwzięcia')[0]) if kind=='environmental-decision' else None
            event_date = decision_date or publication
            r['events'].append({'id':'environmental-publication:' + str(d['id']),'title':label,'date':event_date,'sourceUrl':au})
            add_date(r,'publication',publication,'Publikacja BIP — artykuł ' + str(d['id']),au)
            if decision_date:
                add_date(r,'environmental-decision',decision_date,label,au)
            fact(r,'Artykuł BIP',str(d['id']),au)
            for a in d.get('attachments',[]):
                if a.get('deleted') or a.get('extension')!='pdf':
                    continue
                file_url = BIP + 'api/files/' + str(a['id'])
                fact(r,'Dokument źródłowy', 'Załącznik BIP ' + str(a['id']), file_url)
                text = a.get('text','')
                cases = sorted(set(re.findall(r'WOŚiR\.6220\.[\d.]+',text)))
                for case in cases:
                    fact(r,'Znak występujący w dokumencie (bez heurystycznego scalania)',case.rstrip('.'),file_url)
                if a.get('scanned'):
                    r['warnings'].append('Załącznik ' + str(a['id']) + ': skan; bez automatycznej interpretacji działek z OCR.')
            # Explicit dates from application section, not later legal boilerplate.
            texts = ' '.join(a.get('text','') for a in d.get('attachments',[]))
            m = re.search(r'wniosek z dnia\s+([^,]{1,30}),\s*data wpływu do tut\. Urzędu\s+([^,]{1,35})',text_html(texts),re.I)
            if m:
                for kind,phrase in [('application',m[1]),('application-received',m[2])]:
                    dt = dated_phrase(phrase)
                    if dt:
                        add_date(r,kind,dt,'Wniosek' if kind=='application' else 'Wpływ wniosku do urzędu',au)
        label,kind = event_type(latest['title'])
        r['status'] = label + ' — status robót niepotwierdzony'
        r['statusAsOf'] = dated_phrase(latest['title'].split('dla przedsięwzięcia')[0]) if kind=='environmental-decision' else latest['basicData']['active'][:10]
        r['sourceUpdatedAt'] = max((edit for d,_ in items if (edit := edited_time(d['basicData']))), default=None)
        r['events'].sort(key=lambda e:(e['date'] or '',e['id']))
        r['dates'].sort(key=lambda d:(d['date'],d['kind']))
        r['warnings'] = list(dict.fromkeys(r['warnings']))
        out.append(r)
    return sorted(out,key=lambda r:r['id'])


def pdf_text(data: bytes) -> tuple[str, int]:
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError as exc:
            raise ValueError('PDF reader unavailable: install PyMuPDF in importer environment') from exc
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        if len(doc)>600:
            raise ValueError('PDF page cap')
        return '\n'.join(page.get_text() for page in doc),len(doc)


def collect_environment(fetcher: Fetcher):
    tree, tree_stamp = fetcher.json(BIP + 'api/menu/19681')
    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.get('children') or [])
    root = next((n for n in walk(tree) if str(n.get('id'))=='19681'),None)
    if not root:
        raise ValueError('Environmental menu missing')
    current_year = str(datetime.now(timezone.utc).year)
    menus = [n for n in root.get('children',[]) if n.get('name')==current_year]
    if len(menus)!=1:
        raise ValueError('Current environmental year not discovered')
    menu = menus[0]
    articles, offset, total = [],0,None
    while total is None or len(articles)<total:
        url = BIP + f'api/menu/{menu["id"]}/articles?limit=100&offset={offset}'
        page,stamp = fetcher.json(url)
        if not isinstance(page.get('total'),int) or page['total']>MAX_ARTICLES or (total is not None and page['total']!=total) or page.get('offset')!=offset:
            raise ValueError('Environmental total/schema changed')
        total = page['total']
        batch = page.get('articles')
        if not isinstance(batch,list) or (len(articles)<total and not batch):
            raise ValueError('Environmental truncation')
        articles.extend(batch)
        offset += len(batch)
        if total==0:
            break
    if len(articles)!=total or len({str(a['id']) for a in articles})!=total:
        raise ValueError('Environmental duplicate/count mismatch')
    def one(article):
        d,t = fetcher.json(BIP + 'api/articles/' + str(article['id']))
        d['_fetchedAt'] = t
        if str(d.get('id'))!=str(article['id']) or str(d.get('mainMenuId'))!=str(menu['id']):
            raise ValueError('Environmental detail identity/menu mismatch')
        for a in d.get('attachments',[]):
            if not a.get('deleted') and a.get('extension')=='pdf':
                b,at,_ = fetcher.get(BIP + 'api/files/' + str(a['id']))
                a['_fetchedAt'] = at
                text,n = pdf_text(b)
                a['text'] = text
                a['pages'] = n
                a['scanned'] = len(text.strip())<40
        return d,t
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        details = list(executor.map(one,articles))
    latest_receipt = max([tree_stamp,stamp] + [t for d,t in details])
    records = parse_environment([d for d,t in details],latest_receipt)
    latest_receipt = max([latest_receipt] + [r['fetchedAt'] for r in records])
    geometries = resolve_parcels(records,fetcher)
    meta = source_meta('environmental')
    meta.update(url=urljoin(BIP,menu['link']),status='fresh',fetchedAt=latest_receipt,
        sourceUpdatedAt=max([r['sourceUpdatedAt'] for r in records if r['sourceUpdatedAt']],default=None),
        coverage=f'Rocznik {current_year}: komplet {total} publikacji, {len(records)} tożsamości przedsięwzięć; {sum(len(d.get("attachments",[])) for d,t in details)} załączników. To nie {total} projektów ani rejestr wszystkich inwestycji. ULDK: {geometries["verified"]}/{geometries["requested"]} exact działek; {geometries["unresolved"]} niezmapowanych.',
        recordCount=len(records),warnings=geometries['warnings'])
    return records,meta,{'publicationCount':total,'detailCount':len(details),'attachments':sum(len(d.get('attachments',[])) for d,t in details),'uldk':geometries}


def discover_fe_link(page: str):
    links = [urljoin(FE_PAGE,html.unescape(s)) for s in re.findall(r'(?:href|data-url)=["\']([^"\']+\.xlsx(?:\?[^"\']*)?)["\']',page,re.I)]
    links = [u for u in links if urlparse(u).hostname=='funduszeeuropejskie.gov.pl' and '2021_2027' in u]
    if not links:
        raise ValueError('No actual official FE XLSX download link discovered')
    def key(url):
        m = re.search(r'(\d{2})(\d{2})(20\d{2})',url.rsplit('/',1)[-1])
        if m:
            return date(int(m[3]),int(m[2]),int(m[1]))
        return date.min
    return max(links,key=key)


def excel_date(value: str, date1904: bool = False):
    try:
        serial = Decimal(value)
    except InvalidOperation:
        return date.fromisoformat(value[:10]).isoformat()
    if not serial.is_finite() or serial<0 or serial>100000:
        raise ValueError('Invalid Excel date')
    # Floor, never round 23:59:59 into the following calendar day.
    base = date(1904,1,1) if date1904 else date(1899,12,30)
    return (base + timedelta(days=int(serial))).isoformat()


def parse_fe_xlsx(data: bytes, url: str, stamp: str):
    ns = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    tag = '{' + ns['m'] + '}'
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        wb = ET.fromstring(archive.read('xl/workbook.xml'))
        wp = wb.find('m:workbookPr',ns)
        date1904 = wp is not None and wp.attrib.get('date1904') in ('1','true')
        # Exact official sheet identity, not an assumed arbitrary sheet order.
        sheets = wb.findall('m:sheets/m:sheet',ns)
        sheet = next((s for s in sheets if s.attrib['name']=='Lista projektów 2021-2027'),None)
        if sheet is None:
            raise ValueError('FE project sheet missing')
        rid = sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        sheet_path = 'xl/worksheets/sheet1.xml'
        if rid:
            rel = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
            match = next((r for r in rel if r.attrib.get('Id')==rid),None)
            if match is None:
                raise ValueError('FE sheet relation missing')
            target = match.attrib['Target']
            sheet_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            with archive.open('xl/sharedStrings.xml') as stream:
                root = None
                for event,elem in ET.iterparse(stream,events=('start','end')):
                    if root is None:
                        root = elem
                    if event=='end' and elem.tag==tag+'si':
                        strings.append(''.join(t.text or '' for t in elem.iter(tag+'t')))
                        elem.clear()
                        root.clear()
        out,contracts,raw_count = [],set(),0
        snapshot = None
        headers = None
        root = None
        with archive.open(sheet_path) as stream:
            for event,elem in ET.iterparse(stream,events=('start','end')):
                if root is None:
                    root = elem
                if event!='end' or elem.tag!=tag+'row':
                    continue
                values = {}
                for cell in elem:
                    col = re.sub(r'\d','',cell.attrib['r'])
                    typ = cell.attrib.get('t')
                    node = cell.find('m:v',ns)
                    value = node.text or '' if node is not None else ''
                    if typ=='s':
                        value = strings[int(value)]
                    elif typ=='inlineStr':
                        value = ''.join(t.text or '' for t in cell.iter(tag+'t'))
                    values[col] = value
                number = int(elem.attrib['r'])
                if number==1:
                    snapshot = dated_phrase(values.get('A',''))
                elif number==2:
                    headers = values
                    required = {'A':'Nazwa projektu','C':'Numer umowy','D':'Nazwa beneficjenta','I':'Program','L':'Wartość projektu','N':'Dofinansowanie z UE','P':'Miejsce realizacji projektu','Q':'Data rozpoczęcia','R':'Data zakończenia'}
                    for col,phrase in required.items():
                        if phrase.lower() not in re.sub(r'\s+',' ',values.get(col,'')).lower():
                            raise ValueError('FE source columns changed: ' + col)
                elif number>2:
                    if headers is None or snapshot is None:
                        raise ValueError('FE header/snapshot missing')
                    raw_count += 1
                    locations = values.get('P','').split('|')
                    # Each municipality token must match exactly, not substring.
                    municipality_tokens = re.findall(r'GM\.:\s*([^,|\n]+)',values.get('P',''))
                    if 'Ożarów Mazowiecki' in [s.strip() for s in municipality_tokens]:
                        contract = values.get('C','').strip()
                        if not contract or contract in contracts:
                            raise ValueError('FE duplicate/missing local contract ID')
                        contracts.add(contract)
                        r = new_record('eu-funding',contract,url,values['A'].strip(),stamp)
                        r.update(recordType='funding',investorName=values['D'].strip() or None,category='fundusze europejskie',locality='Gmina Ożarów Mazowiecki',status='Umowa/decyzja ujęta w wykazie FE — nie potwierdza rozpoczęcia budowy',statusAsOf=snapshot)
                        r['summary'] = 'Finansowanie projektu w programie ' + values['I'].strip() + '. Gmina występuje w źródłowym miejscu realizacji, nie tylko jako siedziba beneficjenta.'
                        if contract in FE_SUMMARIES:
                            r['summary'] = FE_SUMMARIES[contract] + ' ' + r['summary']
                        beneficiary = values['D'].upper()
                        if beneficiary == 'GMINA OŻARÓW MAZOWIECKI':
                            r['investor'] = 'municipal'
                        elif beneficiary.startswith(('VIGO ', 'POLPHARMA ', 'AB INDUSTRY ', '"AMARGO ', 'SKYNET ')):
                            r['investor'] = 'private'
                        scope = 'multi-municipality' if len(set(s.strip() for s in municipality_tokens))>1 or len(locations)>1 else 'local'
                        for col,kind,label in [('L','project-total','Całkowita wartość projektu'),('N','eu-contribution','Dofinansowanie UE')]:
                            if not values.get(col,''):
                                amount = None
                            else:
                                num = Decimal(values[col])
                                if not num.is_finite() or num<0:
                                    raise ValueError('FE invalid amount')
                                amount = float(num)
                            r['costs'].append({'kind':kind,'amount':amount,'currency':'PLN','label':label + (' — cały projekt wielogminny, nie kwota przypisana gminie' if scope=='multi-municipality' else ' — cały projekt'),'year':None,'scope':scope,'sourceUrl':url})
                            fact(r,'Oryginalna wartość komórki ' + col,values.get(col,'') or 'brak',url)
                        r['costs'].append({'kind':'eligible','amount':None,'currency':'PLN','label':'Koszty kwalifikowalne: brak kolumny w źródłowym wykazie; bez wyliczania z procentu','year':None,'scope':scope,'sourceUrl':url})
                        for col,kind,label in [('Q','project-start','Data rozpoczęcia projektu w wykazie (nie początek budowy)'),('R','project-end','Data zakończenia projektu w wykazie')]:
                            if values.get(col):
                                add_date(r,kind,excel_date(values[col],date1904),label,url)
                                fact(r,'Oryginalna wartość daty Excel ' + col,values[col],url)
                        for col,label in [('C','Numer umowy/decyzji'),('G','Fundusz'),('I','Program'),('J','Priorytet'),('K','Działanie'),('S','Kategoria wsparcia'),('P','Miejsce realizacji — zakres źródłowy'),('M','Unijny poziom dofinansowania (%) — wartość źródłowa')]:
                            if values.get(col):
                                fact(r,label,values[col].strip(),url)
                        r['warnings'].append('Źródło nie zawiera adresu budowy, działek ani geometrii; projekt B+R/usługowy nie musi oznaczać budowy.')
                        if scope=='multi-municipality':
                            r['warnings'].append('Podane koszty obejmują cały projekt wielogminny. Brak podziału środków dla Ożarowa Mazowieckiego.')
                        out.append(r)
                elem.clear()
                # Remove completed rows from sheetData; retain bounded XML memory.
                root.clear()
        if headers is None or snapshot is None:
            raise ValueError('Truncated FE sheet')
        archive.close()
        return out,snapshot,{'nationalRows':raw_count,'localContracts':len(contracts),'dateSystem':'1904' if date1904 else '1900','descriptionMirrored':False}
    except (zipfile.BadZipFile,ET.ParseError,KeyError,InvalidOperation,IndexError) as exc:
        raise ValueError('Invalid/truncated FE XLSX schema') from exc


def collect_eu(fetcher: Fetcher):
    b,pt,_ = fetcher.get(FE_PAGE)
    url = discover_fe_link(b.decode('utf-8'))
    data,stamp,h = fetcher.get(url)
    records,snapshot,stats = parse_fe_xlsx(data,url,stamp)
    meta = source_meta('eu-funding')
    # Snapshot is date-only; do NOT manufacture sourceEdited midnight ISO.
    meta.update(status='fresh',fetchedAt=stamp,recordCount=len(records),coverage=f'Oficjalny XLSX, stan {snapshot}; {stats["nationalRows"]} wierszy krajowych; {len(records)} unikalnych lokalnych umów po exact GM.: Ożarów Mazowiecki w polu miejsca realizacji. Bez filtra siedzib i bez geometrii. Koszty kwalifikowalne nie występują jako kolumna.')
    stats.update(snapshot=snapshot,url=url,sha256=h,fetchedAt=stamp)
    return records,meta,stats


def collect_private(fetcher: Fetcher):
    out = []
    b,stamp,h = fetcher.get(AURA)
    raw,pages = pdf_text(b)
    text = text_html(raw)
    if not all(token in text for token in ['Aura Nova I','46/3','47/1','74/25','0003','Mill-Yon']):
        raise ValueError('Aura prospect project/parcel identity changed')
    r = new_record('private-projects','aura-nova-I',AURA,'Aura Nova I — Kapucka 34 i 36',stamp)
    r.update(investor='private',investorName='Mill-Yon Ożarów Sp. z o.o.',category='mieszkalnictwo',locality='Ożarów Mazowiecki',address='ul. Kapucka 34 i 36',summary='Dwa budynki mieszkalne A i B, garaż podziemny i lokal usługowy. Działki prospektu nie są obrysem budynków.')
    r['parcelIds'] = [parcel_id('143206_4','0003',n) for n in ['46/3','47/1','74/25']]
    # Actual content dates, not the URL directory or HTTP receipt.
    updated = re.search(r'aktualiz\w*[^.]{0,100}?(\d{1,2}\s+(?:' + '|'.join(MONTHS) + r')\s+20\d{2})',text,re.I)
    if updated:
        dt = dated_phrase(updated[1])
        add_date(r,'prospect-updated',dt,'Aktualizacja wskazana w treści prospektu',AURA)
        fact(r,'Data aktualizacji prospektu',dt,AURA)
    else:
        m = re.search(r'24\s*marca\s*2026',text,re.I)
        if m:
            add_date(r,'prospect-updated','2026-03-24','Aktualizacja wskazana w treści prospektu',AURA)
    use = re.search(r'16\s*(?:[.]\s*10\s*[.]|października\s*)\s*2025',text,re.I)
    if use:
        add_date(r,'occupancy-permit','2025-10-16','Prospekt deklaruje pozwolenie na użytkowanie',AURA)
        r.update(status='Prospekt deklaruje pozwolenie na użytkowanie — brak niezależnej kontroli decyzji',statusAsOf='2025-10-16')
    r['warnings'].append('Prospekt wskazuje możliwą inwestycję drogową na części działek 46/3 i 47/1; pokazane działki nie oznaczają wyłącznego zasięgu budynków.')
    fact(r,'Obręb EGiB', '143206_4.0003 — miasto; jednostka i obręb każdorazowo sprawdzane ULDK',AURA)
    out.append(r)
    b,t,_ = fetcher.get(HILLWOOD)
    page = b.decode('utf-8')
    coords = re.search(r'52\.210795\s*[,;]\s*20\.776937',page)
    # Literal sourced point must be demonstrably in actual investor HTML.
    if not coords and not ('52.210795' in page and '20.776937' in page):
        raise ValueError('Hillwood source point changed; manual review required')
    r = new_record('private-projects','hillwood-ozarow-iii',HILLWOOD,'Hillwood Ożarów III — park magazynowy w Ołtarzewie',t)
    r.update(investor='private',investorName='Hillwood',category='magazyny i produkcja',locality='Ołtarzew',address='ul. Poznańska 249; ul. Ceramiczna 7',status='Istniejący park prezentowany w ofercie najmu; oferta nie dowodzi nowej budowy',summary='Oficjalna karta parku magazynowego. Punkt z witryny inwestora; nie granica EGiB ani nowy plac budowy.')
    r['geometries'] = [{'type':'Feature','geometry':{'type':'Point','coordinates':[20.776937,52.210795]},'properties':{'id':r['id'] + ':point','accuracy':'source-point','sourceUrl':HILLWOOD,'parcelId':None,'note':'Punkt z HTML inwestora, nie granica nieruchomości ani hali.','fetchedAt':t,'sourceUpdatedAt':None}}]
    r['warnings'].append('W HTML są marketingowe obrysy hal i terenu; brak potwierdzonej licencji i dokładności. Nie włączono tych kształtów do danych.')
    out.append(r)
    b,t,_ = fetcher.get(HOME)
    raw,pages = pdf_text(b)
    text = text_html(raw)
    if not all(token in text for token in ['Home Premium','77/4','Piłsudskiego']):
        raise ValueError('Home Premium prospect identity changed')
    r = new_record('private-projects','apartamenty-home-premium-ii-etap-II',HOME,'Apartamenty Home Premium II — II etap',t)
    r.update(investor='private',investorName='Home Premium Perfect One Sp. z o.o.',category='mieszkalnictwo',locality='Ożarów Mazowiecki',address='ul. Piłsudskiego',status='Przedsięwzięcie opisane w prospekcie; aktualny status robót niepotwierdzony',summary='Prospekt II etapu wskazuje działkę 77/4. Pełna data sporządzenia w dokumencie jest niewypełniona; URL nie zastępuje daty treści.')
    # Main table malformed '003' stays literal/unrepaired. Later notarial
    # description independently explicitly supplies valid 0003 for this parcel.
    pattern = r'77/4\s*\([^)]*\)\s*z obrębu ewidencyjnego\s*0003'
    if re.search(pattern,text,re.I):
        r['parcelIds'] = [parcel_id('143206_4','0003','77/4')]
        fact(r,'Literalne rozbieżności obrębu','Tabela: 003 (nie naprawiono); niezależna identyfikacja tej samej 77/4 w części notarialnej: 0003.',HOME)
    else:
        r['warnings'].append('Tabela ma literalny niepoprawny obręb 003; działka niezmapowana bez niezależnego poprawnego tokenu.')
    out.append(r)
    geo = resolve_parcels(out,fetcher)
    meta = source_meta('private-projects')
    meta.update(status='static',fetchedAt=max(r['fetchedAt'] for r in out),recordCount=len(out),coverage=f'{len(out)} ręcznie wskazane, ponownie pobrane źródła prywatne (nie pełny rejestr rynku); Aura Nova I, Hillwood Ożarów III i Home Premium II etap. ULDK {geo["verified"]}/{geo["requested"]}; 1 źródłowy punkt Hillwood. Dokumenty/marketing bez mirrorowania.',warnings=geo['warnings'])
    return out,meta,{'uldk':geo,'curated':True,'auraPdfPages':pages}


def collect_regional(fetcher: Fetcher):
    out = []
    d,t = fetcher.json(CPK_API)
    content = text_html(d['content'])
    if not all(token in content for token in ['160/SPEC/2026','8 września 2026','4+762','13+673','14+200']):
        raise ValueError('CPK decision facts changed')
    url = urljoin(BIP,d['link'])
    r = new_record('regional','160/SPEC/2026',url,'CPK / KDP LK85 — lokalizacja tunelu',t)
    r.update(recordType='regional',investor='national',investorName='Centralny Port Komunikacyjny Sp. z o.o.',category='kolej',locality='Gmina Ożarów Mazowiecki; Warszawa',status='Wydano decyzję lokalizacyjną — nie potwierdzenie rozpoczęcia budowy',statusAsOf='2026-09-08',summary='Decyzja lokalizacyjna 160/SPEC/2026 obejmuje tunel LK85. Bez odtwarzania przebiegu z kilometrów lub przybliżonych map.',sourceUpdatedAt=edited_time(d['basicData']))
    add_date(r,'location-decision','2026-09-08','Decyzja 160/SPEC/2026',url)
    if d['basicData'].get('active'):
        add_date(r,'publication',d['basicData']['active'][:10],'Publikacja/aktualizacja artykułu BIP',url)
    if d['basicData'].get('originActive'):
        original = d['basicData']['originActive'][:10]
        add_date(r,'original-publication',original,'Pierwotna publikacja BIP o wszczęciu',url)
        r['events'].append({'id':'regional:95745:original-publication','title':'Pierwotna publikacja o wszczęciu postępowania lokalizacyjnego','date':original,'sourceUrl':url})
    r['events'].append({'id':'regional:160/SPEC/2026:decision','title':'Wydano decyzję lokalizacyjną 160/SPEC/2026','date':'2026-09-08','sourceUrl':url})
    fact(r,'Zakres tunelu','km 4+762–13+673',url)
    fact(r,'Zakres linii LK85 w decyzji','km 4+762–14+200',url)
    pdf_url = BIP + 'api/files/203399'
    b,pt,h = fetcher.get(pdf_url)
    cpk_sha256 = h
    txt,pages = pdf_text(b)
    if pages!=12:
        raise ValueError('CPK notice page count changed')
    fact(r,'Obwieszczenie wojewody','12 stron; skan decyzji lokalizacyjnej',pdf_url)
    fact(r,'Dokument wojewody','Obwieszczenie i decyzja; odnośnik źródłowy','https://bip.mazowieckie.pl/obwieszczenie/o-wir-i-747-2-10-2025-dm')
    r['warnings'].append('OCR obwieszczenia zawiera niejednoznaczne podziały działek i kolejność kolumn. Bez zatwierdzonego literalnego wykazu nie publikujemy działek ani geometrii. Kilometrów tunelu nie zamieniono w trasę.')
    out.append(r)
    # Strict TLS: no verify=False. The original host has a certificate issue;
    # the official www alias is allowed only if it resolves to equivalent text.
    try:
        b,t,h = fetcher.get(PWZ)
        actual = PWZ
    except ValueError:
        actual = PWZ.replace('https://pwz.pl/','https://www.pwz.pl/')
        b,t,h = fetcher.get(actual)
    text = text_html(b.decode('utf-8'))
    if not all(token in text for token in ['4120W','1600','5 października','Pogroszew']):
        raise ValueError('County road source facts changed')
    r = new_record('regional','dp4120w-pogroszew-umiastow',actual,'DP4120W — remont Pogroszew–Umiastów',t)
    r.update(recordType='regional',investor='county',investorName='Powiat Warszawski Zachodni',category='drogi',locality='Pogroszew; Umiastów',status='Zapowiedziano rozpoczęcie robót na 5 października 2026; brak późniejszego potwierdzenia rozpoczęcia',statusAsOf='2026-10-02',summary='Zapowiedź remontu ok. 1600 m drogi, od skrzyżowania z DP4121W do DW718. Na 3 października 2026 planowany start jest przyszły.')
    add_date(r,'publication','2026-10-02','Komunikat powiatu',actual)
    add_date(r,'planned-start','2026-10-05','Planowany początek, nie potwierdzony start robót',actual)
    fact(r,'Zakres','Około 1600 m; DP4121W–DW718',actual)
    r['warnings'].append('Brak źródłowych współrzędnych/parceli; nie narysowano wymyślonej trasy.')
    out.append(r)
    b,t,h = fetcher.get(A2)
    text = text_html(b.decode('utf-8'))
    if 'Ożarów Mazowiecki' not in text or '03.04.2025' not in text:
        raise ValueError('A2 source scope/date changed')
    r = new_record('regional','a2-third-lane-2025-04-03',A2,'A2 — dodatkowe pasy, decyzje wojewody',t)
    r.update(recordType='regional',investor='national',investorName='Generalna Dyrekcja Dróg Krajowych i Autostrad',category='drogi',locality='Gmina Ożarów Mazowiecki i inne gminy',status='Komunikat o decyzjach drogowych; aktualny status robót niepotwierdzony',statusAsOf='2025-04-03',summary='Oficjalny komunikat wskazuje Ożarów Mazowiecki w zakresie decyzji dotyczących dodatkowych pasów A2; nie ustalono dokładnego odcinka w gminie.')
    add_date(r,'publication','2025-04-03','Komunikat wojewody',A2)
    r['warnings'].append('Bez załączników ZRID i zweryfikowanych działek brak geometrii. Decyzja nie jest dowodem rozpoczęcia robót.')
    out.append(r)
    # Historical source deliberately static, not an as-built contemporary pipe.
    b,t,h = fetcher.get(BIP + 'api/menu/20115/articles?limit=100&offset=0')
    listing = json.loads(b)
    if listing.get('total')!=len(listing.get('articles',[])):
        raise ValueError('Gas historical list truncated')
    r = new_record('regional','gas-rembelszczyzna-mory-wola-karczewska-2016',GAS,'Gazociąg Rembelszczyzna–Mory–Wola Karczewska — dokumenty historyczne',t)
    r.update(recordType='regional',investor='national',category='gazownictwo',status='Historyczne dokumenty planowanego gazociągu z 2016; brak potwierdzenia aktualnego przebiegu powykonawczego',statusAsOf='2016-01-15',summary='BIP udostępnia historyczny wykaz działek i mapę poglądową planowanej trasy. Nie jest to aktualna mapa powykonawcza.')
    found = 0
    for a in listing['articles']:
        aliases = {f['alias']:f['value'] for f in a.get('aliasFields',[])}
        if 'działek' in aliases.get('title','').lower() or 'mapa poglądowa' in aliases.get('title','').lower():
            detail,dt = fetcher.json(BIP + 'api/articles/' + str(a['id']))
            au = urljoin(BIP,detail['link'])
            publication = detail['basicData']['active'][:10]
            add_date(r,'publication',publication,'Historyczny dokument BIP',au)
            fact(r,'Dokument historyczny','Wykaz działek' if 'działek' in aliases['title'].lower() else 'Mapa poglądowa',au)
            found += 1
    if found<2:
        raise ValueError('Historical gas evidence missing')
    r['warnings'].append('Nie przeniesiono działek z historycznej mapy 2016 do aktualnych granic inwestycji; bez geometrii.')
    out.append(r)
    meta = source_meta('regional')
    meta.update(status='static',fetchedAt=max(r['fetchedAt'] for r in out),sourceUpdatedAt=max([r['sourceUpdatedAt'] for r in out if r['sourceUpdatedAt']],default=None),recordCount=len(out),coverage=f'{len(out)} sprawdzone źródła: LK85 decyzja 160/SPEC/2026, DP4120W zapowiedź, A2 komunikat 2025, gazociąg dokumenty 2016. Nie pełny rejestr; wszystkie bez odgadniętej trasy.')
    return out,meta,{'curated':True,'cpkPdfPages':12,'cpkPdfSha256':cpk_sha256,'noInventedRoutes':True}


def validate_record(record: dict):
    if set(record)!=RECORD_KEYS:
        raise ValueError('record allowlist')
    string_fields = 'id sourceId sourceRecordId sourceUrl title recordType investor category locality address status summary fetchedAt'.split()
    if any(not isinstance(record[k],str) for k in string_fields):
        raise ValueError('record string type')
    if record['id']!=record['sourceId']+':'+record['sourceRecordId'] or not record['sourceRecordId']:
        raise ValueError('record identity')
    if record['recordType'] not in ('project','budget-task','procurement','funding','planning-case','proposal','news','regional') or record['investor'] not in ('municipal','county','national','private','mixed','unknown'):
        raise ValueError('record enum')
    safe_url(record['sourceUrl'])
    if record['investorName'] is not None and not isinstance(record['investorName'],str):
        raise ValueError('investor name type')
    for key in ('fetchedAt','sourceUpdatedAt'):
        if record[key] is not None:
            stamp = datetime.fromisoformat(record[key])
            if stamp.tzinfo is None:
                raise ValueError('timestamp timezone')
    if record['statusAsOf'] is not None:
        date.fromisoformat(record['statusAsOf'])
    for key in ('years','costs','dates','geometries','parcelIds','events','facts','relatedIds','warnings'):
        if not isinstance(record[key],list):
            raise ValueError('record list type')
    if any(type(y) is not int or not 1900<=y<=2200 for y in record['years']):
        raise ValueError('record year type/range')
    for key in ('parcelIds','relatedIds','warnings'):
        if any(not isinstance(v,str) for v in record[key]):
            raise ValueError('record string-list type')
    for pid in record['parcelIds']:
        if parcel_id(*pid.split('.'))!=pid:
            raise ValueError('literal parcel ID')
    for cost in record['costs']:
        if set(cost)!=set('kind amount currency label year scope sourceUrl'.split()):
            raise ValueError('cost allowlist')
        amount = cost['amount']
        if amount is not None and (type(amount) not in (int,float) or not math.isfinite(amount) or amount<0):
            raise ValueError('cost amount')
        if cost['scope'] not in ('local','multi-municipality','unknown') or (cost['year'] is not None and type(cost['year']) is not int):
            raise ValueError('cost scope/year')
        if any(not isinstance(cost[k],str) for k in ('kind','currency','label','sourceUrl')):
            raise ValueError('cost strings')
        safe_url(cost['sourceUrl'])
    for key,keys in [('dates','kind date label sourceUrl'),('events','id title date sourceUrl'),('facts','label value sourceUrl')]:
        for item in record[key]:
            if set(item)!=set(keys.split()):
                raise ValueError(key+' allowlist')
            if any(not isinstance(v,str) for k,v in item.items() if not (key=='events' and k=='date' and v is None)):
                raise ValueError(key+' strings')
            safe_url(item['sourceUrl'])
            if key!='facts' and item['date'] is not None:
                date.fromisoformat(item['date'])
    if len({e['id'] for e in record['events']})!=len(record['events']):
        raise ValueError('duplicate publication event')
    if len(set(record['parcelIds']))!=len(record['parcelIds']):
        raise ValueError('duplicate parcel ID')
    for feature in record['geometries']:
        if set(feature)!=set(('type','geometry','properties')) or feature['type']!='Feature':
            raise ValueError('geometry feature allowlist')
        props = feature['properties']
        if set(props)!=set('id accuracy sourceUrl parcelId note fetchedAt sourceUpdatedAt'.split()) or props['accuracy'] not in ('source-point','parcel','project-footprint','route','marketing'):
            raise ValueError('geometry properties allowlist')
        safe_url(props['sourceUrl'])
        if datetime.fromisoformat(props['fetchedAt']).tzinfo is None:
            raise ValueError('geometry receipt timestamp')
        from shapely.geometry import shape
        geometry = shape(feature['geometry'])
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Point','MultiPoint','Polygon','MultiPolygon','LineString','MultiLineString'):
            raise ValueError('invalid geometry')
        if not all(math.isfinite(x) for x in geometry.bounds):
            raise ValueError('nonfinite geometry')
        if props['accuracy']=='parcel' and (props['parcelId'] not in record['parcelIds'] or geometry.geom_type not in ('Polygon','MultiPolygon')):
            raise ValueError('geometry parcel join')
    if len({g['properties']['id'] for g in record['geometries']})!=len(record['geometries']):
        raise ValueError('duplicate geometry identity')


def guard_source(source_id, candidate, meta, prior, error=None):
    previous = [copy.deepcopy(r) for r in (prior or {}).get('records',[]) if r.get('sourceId')==source_id]
    oldmeta = next((s for s in (prior or {}).get('sources',[]) if s.get('id')==source_id),None)
    why = error
    if candidate is not None and not why:
        try:
            for record in candidate:
                validate_record(record)
        except (ValueError,TypeError,KeyError) as exc:
            why = 'niezgodny schemat/typ danych: ' + str(exc)
    if candidate is not None and not why:
        ids = [r.get('id') for r in candidate]
        if len(ids)!=len(set(ids)) or any(not i for i in ids):
            why = 'duplikaty lub brak ID'
        elif previous and len(candidate)<len(previous)*0.8:
            why = 'utrata ponad 20% rekordów'
        elif any(set(r)!=RECORD_KEYS for r in candidate):
            why = 'niezgodny schemat rekordu'
        elif any(r['sourceId']!=source_id for r in candidate):
            why = 'niezgodny sourceId'
        elif previous:
            oldevents = {e['id'] for r in previous for e in r.get('events',[])}
            newevents = {e['id'] for r in candidate for e in r.get('events',[])}
            oldgeometries = sum(len(r.get('geometries',[])) for r in previous)
            newgeometries = sum(len(r.get('geometries',[])) for r in candidate)
            if oldevents and len(newevents)<len(oldevents)*0.8:
                why = 'utrata ponad 20% publikacji/zdarzeń'
            elif oldgeometries and newgeometries<oldgeometries*0.8:
                why = 'utrata ponad 20% zweryfikowanych geometrii'
    if why or candidate is None:
        message = source_id + ': źródło nie zastąpiło poprzedniego snapshotu — ' + str(why or 'brak wyniku')
        meta = copy.deepcopy(oldmeta) if oldmeta else source_meta(source_id)
        meta.update(status='retained' if previous else 'unavailable',recordCount=len(previous))
        meta['warnings'] = list(meta.get('warnings',[])) + [message]
        return previous,meta,[message]
    meta['recordCount'] = len(candidate)
    return candidate,meta,list(meta['warnings'])


def collect(cache: Path, prior: dict | None = None) -> dict:
    cache = Path(cache)
    cache.mkdir(parents=True,exist_ok=True)
    fetcher = Fetcher(cache)
    result = {'records':[],'sources':[],'warnings':[]}
    report = {'generatedAt':now(),'sources':{},'receipts':[],'uldk':[],'limits':{'workers':WORKERS,'attempts':3,'maxArticles':MAX_ARTICLES,'maxDownloadBytes':MAX_DOWNLOAD}}
    for source_id,collector in [('environmental',collect_environment),('private-projects',collect_private),('regional',collect_regional),('eu-funding',collect_eu)]:
        try:
            records,meta,stats = collector(fetcher)
            records,meta,warnings = guard_source(source_id,records,meta,prior)
            report['sources'][source_id] = stats
            if stats.get('uldk'):
                report['uldk'].extend(stats['uldk']['evidence'])
        except Exception as exc:
            # Isolate source errors, never fabricate a successful empty snapshot.
            records,meta,warnings = guard_source(source_id,None,source_meta(source_id),prior,str(exc))
            report['sources'][source_id] = {'error':str(exc)}
        result['records'].extend(records)
        result['sources'].append(meta)
        result['warnings'].extend(warnings)
    result['records'].sort(key=lambda r:r['id'])
    report['receipts'] = sorted(fetcher.receipts.values(),key=lambda r:r['url'])
    report['http'] = fetcher.stats
    report['counts'] = {'records':len(result['records']),'mapped':sum(bool(r['geometries']) for r in result['records']),'geometries':sum(len(r['geometries']) for r in result['records']),'bySource':{s['id']:s['recordCount'] for s in result['sources']}}
    # Evidence export is privacy-safe ULDK replies only; raw BIP/PDF/XLSX cache
    # stays private. Contributions are NOT browser assets and never published.
    (cache / 'private-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (cache / 'private-contribution.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return result
