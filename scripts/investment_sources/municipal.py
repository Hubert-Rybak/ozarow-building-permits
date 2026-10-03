"""Verified municipal map contribution. No publication or cross-source reconciliation.

Only source facts and native representative points are returned. Cache evidence is
not a browser payload and must remain outside public assets. See MUNICIPAL.md.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

import requests
from shapely.geometry import shape
from shapely.ops import unary_union

SOURCE_ID = 'municipal-map'
PORTAL = 'https://www.ozarow.gminneinwestycje.pl/'
BASE = 'https://services-eu1.arcgis.com/n7DhHnz2koymALo1/ArcGIS/rest/services/'
LAYER = BASE + 'Ozarow_Maz_inwestycje_/FeatureServer/17'
BOUNDARY = BASE + 'Ozarow_granica/FeatureServer/14'
FIELDS = ('OBJECTID', 'GlobalID', 'Kolejnosc', 'XML_ID', 'Numer', 'Tytul',
          'Kategoria', 'KategorID', 'Status', 'Status_txt', 'Koszt_txt',
          'Koszt_kalk', 'Filtr_rok', 'Obreb', 'Link', 'Zdjecie',
          'CreationDate', 'EditDate')
TEXT_FIELDS = set(FIELDS) - {'OBJECTID', 'Kolejnosc', 'Koszt_kalk', 'CreationDate', 'EditDate'}
RECORD_KEYS = set('id sourceId sourceRecordId sourceUrl title recordType investor investorName category locality address status statusAsOf summary years costs dates geometries parcelIds events facts relatedIds warnings fetchedAt sourceUpdatedAt'.split())
SOURCE_KEYS = set('id name url fetchedAt sourceUpdatedAt status coverage recordCount warnings reuse'.split())
REUSE = ('Fakty i atrybucja: Gmina Ożarów Mazowiecki / gminna mapa inwestycji. '
         'Nie ustalono licencji na opisy i zdjęcia; nie są kopiowane. '
         'Zdjęcia i dokumenty wyłącznie linkowane do źródła.')
POINT_NOTE = ('Punkt reprezentacyjny z gminnej mapy; nie jest obrysem '
              'inwestycji, działką ani trasą. Współrzędne źródłowe WGS84.')
MAX_RECORDS = 50000
MAX_PAGES = 500
PAGE_SIZE = 200
MAX_REQUESTS = 1100
RETRIES = 3


class SourceError(ValueError):
    """Reject an unverified candidate rather than publish partial data."""


def _require(condition, message):
    if not condition:
        raise SourceError(message)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _iso(value):
    if value is None:
        return None
    _require(_finite(value) and value >= 0, 'Nieprawidłowy timestamp ArcGIS')
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _is_iso(value, nullable=False):
    if value is None:
        return nullable
    if not isinstance(value, str) or not value.endswith('Z'):
        return False
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None
    except ValueError:
        return False


def _safe_url(value):
    if not isinstance(value, str) or not value or '\\' in value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    try:
        p = urlsplit(value)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
            return False
        _ = p.port
        sensitive = {'token', 'access_token', 'api_key', 'apikey', 'password', 'secret', 'signature', 'sig', 'auth', 'key'}
        return not any(k.lower() in sensitive for k, _ in parse_qsl(p.query))
    except ValueError:
        return False


def _point(geometry):
    _require(isinstance(geometry, dict) and set(geometry) == {'type', 'coordinates'} and geometry['type'] == 'Point', 'Oczekiwano geometrii Point')
    coords = geometry['coordinates']
    _require(isinstance(coords, list) and len(coords) == 2 and all(_finite(c) for c in coords)
             and -180 <= coords[0] <= 180 and -90 <= coords[1] <= 90, 'Nieprawidłowe współrzędne WGS84 Point')
    return shape(geometry)


class _Client:
    def __init__(self, cache):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        self.path = Path(cache) / ('municipal-' + stamp + '-' + uuid.uuid4().hex[:8])
        self.path.mkdir(parents=True, exist_ok=False)
        self.session = requests.Session()
        self.evidence = {'sourceId': SOURCE_ID, 'startedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'requests': []}
        self.calls = 0
        self.finished = False

    def get(self, url, params=None, text=False):
        for attempt in range(RETRIES):
            self.calls += 1
            _require(self.calls <= MAX_REQUESTS, 'Przekroczono limit zapytań municipal')
            entry = {'url': url, 'params': params, 'attempt': attempt + 1}
            self.evidence['requests'].append(entry)
            try:
                response = self.session.get(url, params=params, timeout=(10, 45), headers={'User-Agent': 'Radar-Ozarow/1.0 source-verification'}, allow_redirects=False)
                entry['httpStatus'] = response.status_code
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    raise requests.ConnectionError('Przejściowy HTTP ' + str(response.status_code))
                response.raise_for_status()
                _require(response.status_code == 200, 'Nieoczekiwany HTTP / redirect')
                _require(len(response.content) <= 20000000, 'Zbyt duża odpowiedź municipal')
                data = response.text if text else response.json()
                if not text:
                    _require(isinstance(data, dict), 'Odpowiedź ArcGIS nie jest obiektem')
                    if 'error' in data:
                        err = data['error']
                        code = err.get('code') if isinstance(err, dict) else None
                        if code in {429, 500, 502, 503, 504}:
                            raise requests.ConnectionError('Przejściowy błąd ArcGIS ' + str(code))
                        raise SourceError('Błąd ArcGIS: ' + str(code))
                filename = f'{len(self.evidence["requests"]):04d}.' + ('txt' if text else 'json')
                encoded = response.text if text else json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
                (self.path / filename).write_text(encoded, encoding='utf-8')
                entry.update({'file': filename, 'sha256': hashlib.sha256(encoded.encode()).hexdigest()})
                return data
            except (requests.Timeout, requests.ConnectionError) as error:
                entry['error'] = type(error).__name__
                if attempt == RETRIES - 1:
                    raise SourceError('Błąd pobrania po 3 próbach: ' + type(error).__name__) from error
                time.sleep(0.5 * (2 ** attempt))
        raise SourceError('Brak odpowiedzi')

    def finish(self):
        if self.finished:
            return
        self.evidence['finishedAt'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        (self.path / 'evidence.json').write_text(json.dumps(self.evidence, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        self.finished = True


def _discover(client):
    html = client.get(PORTAL, text=True)
    assets = re.findall(r'(?:src|href)=[\"\']([^\"\']+\.js)[\"\']', html)
    queue = sorted(set(urljoin(PORTAL, asset) for asset in assets), key=lambda u: ('dataService' not in u, u))
    visited = set()
    for _ in range(20):
        if not queue:
            break
        url = queue.pop(0)
        if url in visited or urlsplit(url).netloc != urlsplit(PORTAL).netloc or not urlsplit(url).path.startswith('/assets/'):
            continue
        visited.add(url)
        module = client.get(url, text=True)
        if LAYER in module and BOUNDARY in module:
            _require(re.search(r'\.filter\([^;]{0,180}\.Kolejnosc\s*!==\s*-1\)', module) is not None,
                     'Niepotwierdzona aktualna reguła wykluczenia szablonu Kolejnosc=-1')
            client.evidence['discovery'] = {'portalUrl': PORTAL, 'moduleUrl': url, 'investmentLayer': LAYER, 'boundaryLayer': BOUNDARY, 'templateRule': 'Kolejnosc !== -1'}
            return
        imports = re.findall(r'[\"\']([^\"\']+\.js)[\"\']', module)
        queue.extend(urljoin(url, asset) for asset in imports if 'dataService' in asset or asset.startswith('./'))
    raise SourceError('Nie odkryto aktualnego modułu usług i reguły szablonu')


def _metadata(client, layer, point):
    meta = client.get(layer, {'f': 'json'})
    oid = 'OBJECTID' if point else 'FID'
    _require(meta.get('objectIdField') == oid and meta.get('geometryType') == ('esriGeometryPoint' if point else 'esriGeometryPolygon'), 'Zmiana schematu / typu geometrii ArcGIS')
    fields = meta.get('fields')
    _require(isinstance(fields, list), 'Brak schematu pól ArcGIS')
    field_types = {f.get('name'): f.get('type') for f in fields if isinstance(f, dict)}
    _require(field_types.get(oid) == 'esriFieldTypeOID', 'Nieprawidłowy OBJECTID/FID')
    if point:
        _require(set(FIELDS) <= set(field_types), 'Brak wymaganych pól w schemacie municipal')
        for name in TEXT_FIELDS:
            _require(field_types[name] == ('esriFieldTypeGlobalID' if name == 'GlobalID' else 'esriFieldTypeString'), 'Zmiana typu pola ' + name)
        _require(field_types['Koszt_kalk'] == 'esriFieldTypeDouble' and field_types['EditDate'] == 'esriFieldTypeDate'
                 and field_types['CreationDate'] == 'esriFieldTypeDate' and field_types['Kolejnosc'] in {'esriFieldTypeSmallInteger', 'esriFieldTypeInteger'}, 'Zmiana typów liczb/dat municipal')
    else:
        _require(field_types.get('JPT_NAZWA1') == 'esriFieldTypeString', 'Brak nazwy oficjalnej granicy')
    max_count = meta.get('maxRecordCount')
    _require(type(max_count) is int and max_count > 0, 'Nieprawidłowy maxRecordCount')
    caps = meta.get('advancedQueryCapabilities', {})
    _require(isinstance(caps, dict) and caps.get('supportsPagination') is True and caps.get('supportsOrderBy') is True, 'ArcGIS nie gwarantuje paginacji / kolejności')
    _iso(meta.get('editingInfo', {}).get('lastEditDate'))
    return meta


def _ids_count(client, layer, oid):
    count_data = client.get(layer + '/query', {'where': '1=1', 'returnCountOnly': 'true', 'f': 'json'})
    count = count_data.get('count')
    _require(type(count) is int and 0 <= count <= MAX_RECORDS, 'Nieprawidłowy / nieograniczony count ArcGIS')
    ids_data = client.get(layer + '/query', {'where': '1=1', 'returnIdsOnly': 'true', 'f': 'json'})
    ids = ids_data.get('objectIds')
    _require(isinstance(ids, list) and all(type(i) is int and i >= 0 for i in ids), 'Brak poprawnych IDs ArcGIS')
    _require(ids_data.get('objectIdFieldName') == oid and not ids_data.get('exceededTransferLimit')
             and len(ids) == count and len(set(ids)) == count, 'Niezgodność count/IDs lub duplikaty / truncation ArcGIS')
    return count, sorted(ids)


def _fetch_layer(client, layer, meta, fields):
    oid = meta['objectIdField']
    count, ids = _ids_count(client, layer, oid)
    size = min(PAGE_SIZE, meta['maxRecordCount'])
    _require(math.ceil(count / size) <= MAX_PAGES, 'Przekroczono limit stron ArcGIS')
    features = []
    seen = []
    for offset in range(0, count, size):
        page = client.get(layer + '/query', {'where': '1=1', 'outFields': ','.join(fields), 'outSR': '4326',
                         'f': 'geojson', 'orderByFields': oid + ' ASC', 'resultOffset': offset, 'resultRecordCount': size, 'returnGeometry': 'true'})
        _require(page.get('type') == 'FeatureCollection' and isinstance(page.get('features'), list), 'Brak GeoJSON FeatureCollection')
        if 'crs' in page:
            crs_name = page.get('crs', {}).get('properties', {}).get('name', '')
            _require(crs_name in {'urn:ogc:def:crs:OGC:1.3:CRS84', 'urn:ogc:def:crs:EPSG::4326', 'EPSG:4326'}, 'Nieprawidłowy CRS odpowiedzi')
        chunk = page['features']
        _require(len(chunk) == min(size, count-offset), 'Truncation: długość strony niezgodna z count')
        flag = page.get('exceededTransferLimit', False)
        _require(type(flag) is bool and not (offset+len(chunk) == count and flag), 'Truncation: końcowa strona exceededTransferLimit')
        for feature in chunk:
            _require(isinstance(feature, dict) and feature.get('type') == 'Feature' and isinstance(feature.get('properties'), dict), 'Nieprawidłowy Feature')
            props = feature['properties']
            _require(set(fields) <= set(props), 'Brak wymaganych atrybutów Feature')
            value = props[oid]
            _require(type(value) is int and value >= 0 and feature.get('id', value) == value, 'Nieprawidłowy ID Feature')
            seen.append(value)
        features.extend(chunk)
    _require(seen == ids and len(set(seen)) == count, 'Niezgodność uporządkowanych IDs / duplikaty')
    count_after, ids_after = _ids_count(client, layer, oid)
    meta_after = client.get(layer, {'f': 'json'})
    _require(count_after == count and ids_after == ids, 'Count/IDs zmieniły się podczas pobrania')
    _require(meta_after.get('editingInfo') == meta.get('editingInfo') and meta_after.get('fields') == meta.get('fields'), 'Metadane/edycja zmieniły się podczas pobrania')
    client.evidence['boundary' if layer == BOUNDARY else 'investments'] = {'rawCount': count, 'uniqueIds': len(set(seen)), 'pages': math.ceil(count/size), 'pageSize': size, 'sourceUpdatedAt': _iso(meta.get('editingInfo', {}).get('lastEditDate')), 'countAfter': count_after, 'ids': ids}
    return features


def _boundary(features):
    _require(features, 'Brak oficjalnej granicy gminy')
    polygons = []
    for feature in features:
        # The observed official layer has JPT_NAZWA1=' ', not a municipality name.
        # Its provenance is the live portal's exact Ozarow_granica endpoint.
        _require(isinstance(feature['properties']['JPT_NAZWA1'], str), 'Nieprawidłowe pole nazwy granicy')
        geometry = feature.get('geometry')
        _require(isinstance(geometry, dict) and geometry.get('type') in {'Polygon', 'MultiPolygon'}, 'Nieprawidłowy typ granicy')
        polygon = shape(geometry)
        _require(not polygon.is_empty and polygon.is_valid and polygon.area > 0, 'Nieprawidłowa geometria granicy')
        _require(all(math.isfinite(c) for c in polygon.bounds) and -180 <= polygon.bounds[0] <= polygon.bounds[2] <= 180
                 and -90 <= polygon.bounds[1] <= polygon.bounds[3] <= 90, 'Nieprawidłowe współrzędne granicy WGS84')
        polygons.append(polygon)
    result = unary_union(polygons)
    _require(result.is_valid, 'Nieprawidłowa suma geometrii granicy')
    return result


def _record(feature, boundary, fetched_at):
    props = feature['properties']
    for key in TEXT_FIELDS:
        _require(props[key] is None or isinstance(props[key], str), 'Nieprawidłowe pole tekstowe ' + key)
    _require(type(props['Kolejnosc']) is int, 'Nieprawidłowe Kolejnosc')
    _require(props['Tytul'] and props['Tytul'].strip(), 'Brak tytułu inwestycji')
    gid = props['GlobalID']
    _require(isinstance(gid, str) and re.fullmatch(r'(?:\{[0-9a-fA-F-]{36}\}|[0-9a-fA-F-]{36})', gid), 'Nieprawidłowy GlobalID')
    try:
        uuid.UUID(gid)
    except ValueError as error:
        raise SourceError('Nieprawidłowy GlobalID') from error
    amount = props['Koszt_kalk']
    _require(amount is None or (_finite(amount) and amount >= 0), 'Nieprawidłowy koszt (ujemny / non-finite)')
    record_id = 'municipal-map:' + str(props['OBJECTID'])
    query_url = LAYER + '/query?' + urlencode({'where': 'OBJECTID=' + str(props['OBJECTID']), 'outFields': ','.join(FIELDS), 'outSR': '4326', 'f': 'geojson'})
    source_url = props['Link'] if _safe_url(props['Link']) else query_url
    warnings = []
    if props['Link'] and not _safe_url(props['Link']):
        warnings.append('Nieprawidłowy/niebezpieczny Link źródłowy pominięto; link do dokładnego OBJECTID.')
    updated = _iso(props['EditDate'])
    created = _iso(props['CreationDate'])
    years_text = props['Filtr_rok'] or ''
    years = sorted(set(int(y) for y in re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', years_text)))
    geometry = feature.get('geometry')
    geometries = []
    if geometry is None:
        warnings.append('Brak punktu w źródle; nie utworzono zastępczej lokalizacji.')
    else:
        point = _point(geometry)
        if not boundary.covers(point):
            warnings.append('Punkt źródłowy poza oficjalną granicą gminy; wymaga weryfikacji, nie usunięto rekordu.')
        geometries.append({'type': 'Feature', 'geometry': copy.deepcopy(geometry), 'properties': {'id': record_id, 'accuracy': 'source-point', 'sourceUrl': query_url, 'parcelId': None, 'note': POINT_NOTE, 'fetchedAt': fetched_at, 'sourceUpdatedAt': updated}})
    facts = []
    for key in FIELDS:
        value = props[key]
        if value is None:
            continue
        if key in {'Link', 'Zdjecie'}:
            if not _safe_url(value):
                if value and key == 'Zdjecie':
                    warnings.append('Nieprawidłowy/niebezpieczny URL zdjęcia pominięto.')
                continue
        facts.append({'label': key, 'value': str(value), 'sourceUrl': value if key in {'Link', 'Zdjecie'} else query_url})
    if created is not None:
        facts.append({'label': 'CreationDate (UTC)', 'value': created, 'sourceUrl': query_url})
    return {'id': record_id, 'sourceId': SOURCE_ID, 'sourceRecordId': str(props['OBJECTID']), 'sourceUrl': source_url,
            'title': props['Tytul'], 'recordType': 'project', 'investor': 'municipal', 'investorName': 'Gmina Ożarów Mazowiecki',
            'category': props['Kategoria'] or '', 'locality': props['Obreb'] or '', 'address': '', 'status': props['Status'] or '',
            'statusAsOf': None, 'summary': 'Wpis gminnej mapy inwestycji; status i koszt według autora źródła.',
            'years': years, 'costs': [{'kind': 'reported', 'amount': amount, 'currency': 'PLN', 'label': props['Koszt_txt'] or '', 'year': None, 'scope': 'unknown', 'sourceUrl': source_url}],
            'dates': [], 'geometries': geometries, 'parcelIds': [], 'events': [], 'facts': facts, 'relatedIds': [], 'warnings': warnings,
            'fetchedAt': fetched_at, 'sourceUpdatedAt': updated}


def _validate_record(record):
    """Validate this adapter's full contract before trusting prior source rows."""
    _require(isinstance(record, dict) and set(record) == RECORD_KEYS, 'Nieprawidłowe klucze rekordu prior')
    _require(record['sourceId'] == SOURCE_ID and isinstance(record['sourceRecordId'], str) and re.fullmatch(r'\d+', record['sourceRecordId'])
             and record['id'] == SOURCE_ID + ':' + record['sourceRecordId'], 'Nieprawidłowy ID rekordu prior')
    _require(record['recordType'] == 'project' and record['investor'] == 'municipal', 'Nieprawidłowy typ/inwestor prior')
    for key in ['id', 'title', 'sourceId', 'sourceRecordId', 'sourceUrl', 'category', 'locality', 'address', 'status', 'summary']:
        _require(isinstance(record[key], str), 'Nieprawidłowy tekst prior')
    _require(bool(record['title'].strip()) and (record['investorName'] is None or isinstance(record['investorName'], str)), 'Nieprawidłowy tytuł/inwestor prior')
    _require(_safe_url(record['sourceUrl']) and _is_iso(record['fetchedAt']) and _is_iso(record['sourceUpdatedAt'], True), 'Nieprawidłowy URL/timestamp prior')
    _require(record['statusAsOf'] is None, 'Niedokumentowana data statusu prior')
    for key in ['years', 'costs', 'dates', 'geometries', 'parcelIds', 'events', 'facts', 'relatedIds', 'warnings']:
        _require(isinstance(record[key], list), 'Nieprawidłowa lista prior')
    _require(all(type(y) is int and 1900 <= y <= 2099 for y in record['years']), 'Nieprawidłowy rok prior')
    _require(not record['dates'] and not record['parcelIds'] and not record['events'] and not record['relatedIds'], 'Niezweryfikowane dodatkowe fakty prior')
    _require(all(isinstance(w, str) for w in record['warnings']), 'Nieprawidłowe ostrzeżenia prior')
    _require(len(record['costs']) == 1, 'Nieprawidłowa liczba kosztów prior')
    for cost in record['costs']:
        _require(isinstance(cost, dict) and set(cost) == set('kind amount currency label year scope sourceUrl'.split()), 'Nieprawidłowe klucze kosztu prior')
        _require(cost['kind'] == 'reported' and cost['currency'] == 'PLN' and cost['scope'] == 'unknown' and cost['year'] is None
                 and isinstance(cost['label'], str) and _safe_url(cost['sourceUrl']), 'Nieprawidłowe znaczenie kosztu prior')
        _require(cost['amount'] is None or (_finite(cost['amount']) and cost['amount'] >= 0), 'Nieprawidłowa kwota prior')
    _require(len(record['geometries']) <= 1, 'Nieprawidłowa liczba geometrii prior')
    for feature in record['geometries']:
        _require(isinstance(feature, dict) and set(feature) == {'type', 'geometry', 'properties'} and feature['type'] == 'Feature', 'Nieprawidłowy Feature prior')
        _point(feature['geometry'])
        p = feature['properties']
        _require(isinstance(p, dict) and set(p) == set('id accuracy sourceUrl parcelId note fetchedAt sourceUpdatedAt'.split()), 'Nieprawidłowe properties prior')
        _require(p['id'] == record['id'] and p['accuracy'] == 'source-point' and p['parcelId'] is None
                 and isinstance(p['note'], str) and _safe_url(p['sourceUrl']) and p['fetchedAt'] == record['fetchedAt']
                 and p['sourceUpdatedAt'] == record['sourceUpdatedAt'], 'Nieprawidłowa proweniencja geometrii prior')
    allowed = set(FIELDS) | {'CreationDate (UTC)'}
    for fact in record['facts']:
        _require(isinstance(fact, dict) and set(fact) == {'label', 'value', 'sourceUrl'}
                 and fact['label'] in allowed and isinstance(fact['value'], str) and _safe_url(fact['sourceUrl']), 'Nieprawidłowy / niepubliczny fakt prior')
        if fact['label'] in {'Link', 'Zdjecie'}:
            _require(_safe_url(fact['value']), 'Niebezpieczny URL w faktach prior')


def _verified_prior(prior):
    if prior is None:
        return [], None
    _require(isinstance(prior, dict) and prior.get('schemaVersion') == 1 and isinstance(prior.get('records'), list) and isinstance(prior.get('sources'), list), 'Prior nie jest InvestmentDataset v1')
    records = [copy.deepcopy(r) for r in prior['records'] if isinstance(r, dict) and r.get('sourceId') == SOURCE_ID]
    for record in records:
        _validate_record(record)
    _require(len({r['id'] for r in records}) == len(records), 'Duplikaty prior municipal')
    sources = [s for s in prior['sources'] if isinstance(s, dict) and s.get('id') == SOURCE_ID]
    _require(len(sources) <= 1, 'Duplikaty metadanych prior municipal')
    source = copy.deepcopy(sources[0]) if sources else None
    if source is not None:
        _require(set(source) == SOURCE_KEYS and _safe_url(source['url']) and _is_iso(source['fetchedAt'], True)
                 and _is_iso(source['sourceUpdatedAt'], True) and source['status'] in {'fresh', 'retained', 'static', 'unavailable'}, 'Nieprawidłowe metadane prior municipal')
        _require(type(source['recordCount']) is int and source['recordCount'] == len(records), 'Niezgodny licznik prior municipal')
        _require(not records or (source['status'] in {'fresh', 'retained', 'static'} and source['fetchedAt'] is not None), 'Niezweryfikowany status prior municipal')
        for key in ['name', 'coverage', 'reuse']:
            _require(isinstance(source[key], str), 'Nieprawidłowy tekst metadanych prior')
        _require(isinstance(source['warnings'], list) and all(isinstance(w, str) for w in source['warnings']), 'Nieprawidłowe ostrzeżenia metadanych prior')
    _require(not records or source is not None, 'Rekordy prior bez metadanych municipal')
    return records, source


def _source(records, fetched_at, updated, status, coverage, warnings):
    return {'id': SOURCE_ID, 'name': 'Gminna mapa inwestycji — Ożarów Mazowiecki', 'url': PORTAL,
            'fetchedAt': fetched_at, 'sourceUpdatedAt': updated, 'status': status, 'coverage': coverage,
            'recordCount': len(records), 'warnings': warnings, 'reuse': REUSE}


def collect(cache: Path, prior: dict | None = None) -> dict:
    """Retrieve a complete verified independent source contribution or retain prior."""
    old_records, old_source = [], None
    prior_error = None
    try:
        old_records, old_source = _verified_prior(prior)
    except (SourceError, TypeError, KeyError, ValueError) as error:
        prior_error = 'Nie użyto niezweryfikowanego prior municipal: ' + str(error)
    client = None
    source = None
    warnings = []
    try:
        client = _Client(cache)
        _discover(client)
        meta = _metadata(client, LAYER, True)
        boundary_meta = _metadata(client, BOUNDARY, False)
        boundary_features = _fetch_layer(client, BOUNDARY, boundary_meta, ('FID', 'JPT_NAZWA1'))
        boundary = _boundary(boundary_features)
        raw = _fetch_layer(client, LAYER, meta, FIELDS)
        _require(all(type(f['properties']['Kolejnosc']) is int for f in raw), 'Nieprawidłowe Kolejnosc w pobraniu')
        retained = [f for f in raw if f['properties']['Kolejnosc'] != -1]
        gids = [f['properties']['GlobalID'] for f in raw]
        _require(all(isinstance(g, str) for g in gids) and len(set(g.lower().strip('{}') for g in gids)) == len(gids), 'Brak / duplikaty GlobalID')
        fetched_at = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        records = [_record(f, boundary, fetched_at) for f in retained]
        for record in records:
            _validate_record(record)
        _require(not old_records or 5 * len(records) >= 4 * len(old_records), 'Spadek liczby rekordów municipal >20%; zachowano prior')
        old_mapped = sum(bool(r['geometries']) for r in old_records)
        new_mapped = sum(bool(r['geometries']) for r in records)
        _require(not old_mapped or 5 * new_mapped >= 4 * old_mapped, 'Spadek liczby geometrii municipal >20%; zachowano prior')
        warnings = ['Status i koszt są informacją autora mapy, nie potwierdzeniem stanu budowy na dzień pobrania. Punkty nie są obrysami.']
        if prior_error:
            warnings.append(prior_error)
        outside = [r['sourceRecordId'] for r in records if any('poza oficjalną' in w for w in r['warnings'])]
        missing = sum(not r['geometries'] for r in records)
        if outside:
            warnings.append('Punkty poza oficjalną granicą gminy (nie usunięto): OBJECTID ' + ', '.join(outside) + '.')
        if missing:
            warnings.append(f'{missing} rekordów bez źródłowej geometrii; pozostają na liście.')
        raw_count, templates, mapped = len(raw), len(raw)-len(records), len(records)-missing
        coverage = (f'Pełna warstwa gminnej mapy: {raw_count} surowych, {templates} szablonów Kolejnosc=-1 wykluczonych zgodnie z aktualnym modułem, '
                    f'{len(records)} rekordów, {mapped} źródłowych punktów, {missing} bez geometrii, {len(outside)} punktów poza granicą. '
                    'Count/IDs przed i po pobraniu, unikalność, transfer limits i metadane zgodne. '
                    'Nie jest to pełny rejestr wszystkich inwestycji publicznych i prywatnych w gminie.')
        source = _source(records, fetched_at, _iso(meta.get('editingInfo', {}).get('lastEditDate')), 'fresh', coverage, warnings)
        client.evidence.update({'status': 'fresh', 'fetchedAt': fetched_at, 'rawCount': raw_count, 'excludedTemplates': templates,
                                'recordCount': len(records), 'mapped': mapped, 'geometryCount': mapped, 'outsideObjectIds': outside,
                                'missingGeometry': missing, 'nullNumericCosts': sum(r['costs'][0]['amount'] is None for r in records), 'warnings': warnings})
        client.finish()
        return {'records': records, 'sources': [source], 'warnings': warnings}
    except (SourceError, requests.RequestException, ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        warning = 'Nie odświeżono municipal-map: ' + str(error)
        warnings = [warning] + ([prior_error] if prior_error else [])
        if old_records:
            source = copy.deepcopy(old_source)
            source.update({'status': 'retained', 'warnings': list(source['warnings']) + warnings})
        else:
            source = _source([], None, None, 'unavailable', 'Brak zweryfikowanego snapshotu; źródło niedostępne lub nie przeszło kontroli.', warnings)
        if client:
            client.evidence.update({'status': source['status'], 'recordCount': len(old_records), 'warnings': warnings})
        return {'records': old_records, 'sources': [source], 'warnings': warnings}
    finally:
        if client:
            try:
                client.finish()
            except OSError as error:
                cache_warning = 'Nie zapisano dowodu municipal w cache: ' + str(error)
                warnings.append(cache_warning)
                if source is not None and source['warnings'] is not warnings:
                    source['warnings'].append(cache_warning)
            finally:
                client.session.close()
