"""Strict, shared Radar Ożarów investment artifact contract (no network/side effects)."""
from collections import Counter
from datetime import date, datetime, timedelta
import json
import math
import re
from urllib.parse import parse_qsl, unquote, urlsplit

from shapely.geometry import shape

DATASET_KEYS = frozenset('schemaVersion generatedAt records sources warnings counts'.split())
RECORD_KEYS = frozenset('id sourceId sourceRecordId sourceUrl title recordType investor investorName category locality address status statusAsOf summary years costs dates geometries parcelIds events facts relatedIds warnings fetchedAt sourceUpdatedAt'.split())
SOURCE_KEYS = frozenset('id name url fetchedAt sourceUpdatedAt status coverage recordCount warnings reuse'.split())
COST_KEYS = frozenset('kind amount currency label year scope sourceUrl'.split())
DATE_KEYS = frozenset('kind date label sourceUrl'.split())
EVENT_KEYS = frozenset('id title date sourceUrl'.split())
FACT_KEYS = frozenset('label value sourceUrl'.split())
FEATURE_KEYS = frozenset({'type', 'geometry', 'properties'})
PROPERTY_KEYS = frozenset('id accuracy sourceUrl parcelId note fetchedAt sourceUpdatedAt'.split())
LINK_KEYS = frozenset('id kind recordIds basis sourceUrl'.split())
LINK_KINDS = frozenset({'documented', 'probable'})
COUNT_KEYS = frozenset('records mapped geometries bySource'.split())
RECORD_TYPES = frozenset('project budget-task procurement funding planning-case proposal news regional'.split())
INVESTORS = frozenset('municipal county national private mixed unknown'.split())
SOURCE_STATUSES = frozenset('fresh retained static unavailable'.split())
ACCURACIES = frozenset('source-point parcel project-footprint route marketing'.split())
PARCEL_PATTERN = r'143206_[45]\.[0-9]{4}\.(?:AR_[0-9]+\.)?[0-9]+(?:/[0-9]+)?'
SECRET_KEYS = frozenset('password passwd token accesstoken refreshtoken apikey accesskey jwt authorization cookie cookies secret clientsecret session sessionid signature credential credentials pesel email phone creator editor'.split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(obj, expected, context):
    require(type(obj) is dict and set(obj) == expected, f'{context}: exact required key allowlist')


def text(value, context, *, nonempty=False, nullable=False):
    if nullable and value is None:
        return
    require(type(value) is str and (not nonempty or bool(value.strip())), f'{context}: string required')
    require(not any(ord(char) < 32 and char not in '\n\t' for char in value), f'{context}: control character')


def integer(value, context, *, minimum=0, maximum=None):
    require(type(value) is int and value >= minimum and (maximum is None or value <= maximum), f'{context}: integer out of range')


def items(value, context):
    require(type(value) is list, f'{context}: list required')
    return value


def strings(value, context, *, unique=False, nonempty=False):
    for item in items(value, context):
        text(item, context, nonempty=nonempty)
    if unique:
        require(len(value) == len(set(value)), f'{context}: duplicates')


def iso_date(value, context, *, nullable=False):
    if nullable and value is None:
        return
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), f'{context}: YYYY-MM-DD required')
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{context}: invalid calendar date') from exc


def timestamp(value, context, *, nullable=False, utc=False):
    if nullable and value is None:
        return
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', value), f'{context}: timezone-aware ISO timestamp required')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'{context}: invalid timestamp') from exc
    require(parsed.utcoffset() is not None and (not utc or parsed.utcoffset() == timedelta(0)), f'{context}: UTC timestamp required')


def sensitive_key(value):
    normalized = re.sub(r'[^a-z0-9]', '', value.lower())
    return (normalized in SECRET_KEYS or normalized == 'auth'
            or bool(re.search(r'token|secret|password|passwd|credential|signature|authorization|apikey|accesskey|sessionid|jwt', normalized)))


def safe_url(value, context):
    text(value, context, nonempty=True)
    decoded = value
    for _ in range(3):
        decoded = unquote(decoded)
    require(not any(char.isspace() or ord(char) < 32 for char in decoded) and '\\' not in decoded, f'{context}: unsafe URL characters')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
    except ValueError as exc:
        raise ValueError(f'{context}: malformed URL') from exc
    require(parsed.scheme in {'https', 'http'} and bool(host) and parsed.username is None and parsed.password is None, f'{context}: unsafe scheme/host/userinfo')
    require(not any(char in unquote(parsed.netloc) for char in '@/?#'), f'{context}: unsafe authority')
    decoded_parts = urlsplit(decoded)
    for part in (decoded_parts.query, decoded_parts.fragment):
        for key, _ in parse_qsl(part, keep_blank_values=True):
            require(not sensitive_key(key), f'{context}: secret/contact URL field')
    require(not re.search(r'(?:bearer\s|gh[pousr]_|github_pat_|sk-[A-Za-z0-9]{12})', decoded, re.I), f'{context}: credential in URL')


def scan_keys(value):
    if type(value) is dict:
        for key, child in value.items():
            require(type(key) is str and not sensitive_key(key), 'Sensitive/non-string nested key')
            scan_keys(child)
    elif type(value) is list:
        for child in value:
            scan_keys(child)


def number(value, context):
    require(type(value) in {int, float}, f'{context}: finite number required')
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValueError(f'{context}: number exceeds finite browser range') from exc
    require(finite, f'{context}: finite number required')


def geometry(value):
    keys(value, {'type', 'coordinates'}, 'geometry')
    kind = value['type']
    depths = {'Point': 0, 'MultiPoint': 1, 'LineString': 1, 'MultiLineString': 2, 'Polygon': 2, 'MultiPolygon': 3}
    require(type(kind) is str and kind in depths, 'Unsupported geometry type')

    def coordinates(coords, depth):
        items(coords, 'coordinates')
        if depth == 0:
            require(len(coords) == 2, 'Coordinates must be 2D WGS84')
            number(coords[0], 'longitude'); number(coords[1], 'latitude')
            require(-180 <= coords[0] <= 180 and -90 <= coords[1] <= 90, 'Coordinates outside WGS84')
        else:
            require(bool(coords), 'Empty geometry coordinates')
            for child in coords:
                coordinates(child, depth-1)
    coordinates(value['coordinates'], depths[kind])
    if kind in {'Polygon', 'MultiPolygon'}:
        polygons = [value['coordinates']] if kind == 'Polygon' else value['coordinates']
        for polygon in polygons:
            for ring in polygon:
                require(len(ring) >= 4 and ring[0] == ring[-1], 'Polygon ring must be closed with four positions')
    if kind in {'LineString', 'MultiLineString'}:
        lines = [value['coordinates']] if kind == 'LineString' else value['coordinates']
        require(all(len(line) >= 2 for line in lines), 'Line must have at least two positions')
    try:
        geom = shape(value)
        require(not geom.is_empty and geom.is_valid, 'Invalid/empty geometry topology')
    except (TypeError, KeyError, IndexError) as exc:
        raise ValueError('Invalid GeoJSON geometry') from exc


def validate_record(record):
    keys(record, RECORD_KEYS, 'record')
    for key in 'id sourceId sourceRecordId title'.split():
        text(record[key], key, nonempty=True)
    for key in 'category locality address status summary'.split():
        text(record[key], key)
    text(record['investorName'], 'investorName', nullable=True)
    require(type(record['recordType']) is str and record['recordType'] in RECORD_TYPES, 'Invalid recordType')
    require(type(record['investor']) is str and record['investor'] in INVESTORS, 'Invalid investor')
    safe_url(record['sourceUrl'], 'record.sourceUrl')
    iso_date(record['statusAsOf'], 'statusAsOf', nullable=True)
    timestamp(record['fetchedAt'], 'record.fetchedAt')
    timestamp(record['sourceUpdatedAt'], 'record.sourceUpdatedAt', nullable=True)
    for year in items(record['years'], 'years'):
        integer(year, 'year', minimum=1000, maximum=9999)
    require(len(record['years']) == len(set(record['years'])), 'Duplicate years')
    strings(record['parcelIds'], 'parcelIds', unique=True, nonempty=True)
    require(all(re.fullmatch(PARCEL_PATTERN, parcel) for parcel in record['parcelIds']), 'Invalid literal local parcel ID')
    strings(record['relatedIds'], 'relatedIds', unique=True, nonempty=True)
    strings(record['warnings'], 'record.warnings')
    for cost in items(record['costs'], 'costs'):
        keys(cost, COST_KEYS, 'cost')
        for key in 'kind currency label'.split(): text(cost[key], 'cost.'+key)
        if cost['amount'] is not None:
            number(cost['amount'], 'cost.amount')
            require(cost['amount'] >= 0, 'Negative cost')
        if cost['year'] is not None: integer(cost['year'], 'cost.year', minimum=1000, maximum=9999)
        require(type(cost['scope']) is str and cost['scope'] in {'local', 'multi-municipality', 'unknown'}, 'Invalid cost scope')
        safe_url(cost['sourceUrl'], 'cost.sourceUrl')
    for event_date in items(record['dates'], 'dates'):
        keys(event_date, DATE_KEYS, 'date')
        text(event_date['kind'], 'date.kind'); text(event_date['label'], 'date.label')
        iso_date(event_date['date'], 'date.date')
        safe_url(event_date['sourceUrl'], 'date.sourceUrl')
    event_ids = set()
    for event in items(record['events'], 'events'):
        keys(event, EVENT_KEYS, 'event')
        text(event['id'], 'event.id', nonempty=True); text(event['title'], 'event.title')
        require(event['id'] not in event_ids, 'Duplicate event ID within record')
        event_ids.add(event['id'])
        iso_date(event['date'], 'event.date', nullable=True)
        safe_url(event['sourceUrl'], 'event.sourceUrl')
    for fact in items(record['facts'], 'facts'):
        keys(fact, FACT_KEYS, 'fact')
        text(fact['label'], 'fact.label'); text(fact['value'], 'fact.value')
        safe_url(fact['sourceUrl'], 'fact.sourceUrl')
    feature_ids = set()
    for feature in items(record['geometries'], 'geometries'):
        keys(feature, FEATURE_KEYS, 'feature')
        require(feature['type'] == 'Feature', 'GeoJSON Feature required')
        geometry(feature['geometry'])
        props = feature['properties']
        keys(props, PROPERTY_KEYS, 'feature.properties')
        text(props['id'], 'feature.id', nonempty=True)
        require(props['id'] not in feature_ids, 'Duplicate feature ID within record')
        feature_ids.add(props['id'])
        require(type(props['accuracy']) is str and props['accuracy'] in ACCURACIES, 'Invalid geometry accuracy')
        safe_url(props['sourceUrl'], 'feature.sourceUrl')
        text(props['note'], 'feature.note')
        timestamp(props['fetchedAt'], 'feature.fetchedAt')
        timestamp(props['sourceUpdatedAt'], 'feature.sourceUpdatedAt', nullable=True)
        if props['parcelId'] is not None:
            require(type(props['parcelId']) is str and props['parcelId'] in record['parcelIds'], 'Feature parcel ID must join declared literal parcel')
        if props['accuracy'] == 'parcel':
            require(props['parcelId'] is not None and feature['geometry']['type'] in {'Polygon','MultiPolygon'}, 'Parcel geometry requires exact parcel ID and polygon')


def validate_links(links, records):
    seen, pairs = set(), set()
    for link in items(links, 'links'):
        keys(link, LINK_KEYS, 'link')
        require(type(link['kind']) is str and link['kind'] in LINK_KINDS, 'Invalid link kind')
        ids = link['recordIds']
        strings(ids, 'link.recordIds', unique=True, nonempty=True)
        require(len(ids) == 2 and ids == sorted(ids), 'Link joins exactly two sorted record IDs')
        require(all(i in records for i in ids), 'Link must join existing records')
        require(link['id'] == link['kind'] + ':' + '|'.join(ids), 'Link ID must derive from kind and records')
        require(link['id'] not in seen, 'Duplicate link ID')
        seen.add(link['id'])
        require(tuple(ids) not in pairs, 'One link per record pair')
        pairs.add(tuple(ids))
        text(link['basis'], 'link.basis', nonempty=True)
        if link['kind'] == 'documented':
            safe_url(link['sourceUrl'], 'link.sourceUrl')
        else:
            require(link['sourceUrl'] is None, 'Probable link has no source document')


def counts_for(records, sources):
    by_source = Counter(r['sourceId'] for r in records)
    return dict(records=len(records), mapped=sum(bool(r['geometries']) for r in records),
                geometries=sum(len(r['geometries']) for r in records),
                bySource={s['id']: by_source[s['id']] for s in sources})


def validate_dataset(dataset, prior=None):
    """Reject malformed schema, unsafe exposure, inconsistent joins and source-level loss."""
    scan_keys(dataset)
    # 'links' was added after the first published generation; older priors lack it.
    keys(dataset, DATASET_KEYS | ({'links'} if type(dataset) is dict and 'links' in dataset else set()), 'dataset')
    require(type(dataset['schemaVersion']) is int and dataset['schemaVersion'] == 1, 'Unsupported schemaVersion')
    timestamp(dataset['generatedAt'], 'generatedAt', utc=True)
    strings(dataset['warnings'], 'dataset.warnings')
    sources = {}
    for source in items(dataset['sources'], 'sources'):
        keys(source, SOURCE_KEYS, 'source')
        for key in 'id name'.split(): text(source[key], 'source.'+key, nonempty=True)
        for key in 'coverage reuse'.split(): text(source[key], 'source.'+key)
        require(source['id'] not in sources, 'Duplicate global source ID')
        sources[source['id']] = source
        safe_url(source['url'], 'source.url')
        timestamp(source['fetchedAt'], 'source.fetchedAt', nullable=True)
        timestamp(source['sourceUpdatedAt'], 'source.sourceUpdatedAt', nullable=True)
        require(type(source['status']) is str and source['status'] in SOURCE_STATUSES, 'Invalid source status')
        integer(source['recordCount'], 'source.recordCount')
        strings(source['warnings'], 'source.warnings')
        if source['status'] in {'retained', 'unavailable'}:
            require(any(w.strip() for w in source['warnings']), 'Failed/retained source must disclose warning')
        if source['status'] == 'fresh':
            require(source['fetchedAt'] is not None and source['recordCount'] > 0, 'No synthetic empty fresh success')
        if source['status'] == 'unavailable':
            require(source['recordCount'] == 0 and source['fetchedAt'] is None, 'Unavailable source cannot claim records/fetch')
    require(bool(sources), 'At least one declared source required')
    records = {}
    source_native_ids = set()
    for record in items(dataset['records'], 'records'):
        validate_record(record)
        require(record['id'] not in records, 'Duplicate global record ID')
        records[record['id']] = record
        require(record['sourceId'] in sources, 'Record must join declared source')
        native_id = (record['sourceId'], record['sourceRecordId'])
        require(native_id not in source_native_ids, 'Duplicate native source record ID')
        source_native_ids.add(native_id)
    for record in records.values():
        require(all(ref in records and ref != record['id'] for ref in record['relatedIds']), 'relatedIds must join exact other record IDs')
    validate_links(dataset.get('links', []), records)
    keys(dataset['counts'], COUNT_KEYS, 'counts')
    for key in 'records mapped geometries'.split(): integer(dataset['counts'][key], 'counts.'+key)
    require(type(dataset['counts']['bySource']) is dict, 'counts.bySource must be dictionary')
    for value in dataset['counts']['bySource'].values(): integer(value, 'counts.bySource count')
    expected = counts_for(dataset['records'], dataset['sources'])
    require(dataset['counts'] == expected, 'Dataset counts must exactly match records/features/sources')
    for source in sources.values():
        require(source['recordCount'] == expected['bySource'][source['id']], 'Source recordCount must equal source join count')
    if prior is not None:
        validate_dataset(prior)
        old_sources = {s['id']: s for s in prior['sources']}
        for source_id, old_source in old_sources.items():
            require(source_id in sources, f'Source disappeared: {source_id}')
            old_records = {r['id']: r for r in prior['records'] if r['sourceId'] == source_id}
            new_records = {r['id']: r for r in records.values() if r['sourceId'] == source_id}
            new_source = sources[source_id]
            require(len(new_records)*5 >= len(old_records)*4, f'Source record loss >20%: {source_id}')
            old_geoms = sum(len(r['geometries']) for r in old_records.values())
            new_geoms = sum(len(r['geometries']) for r in new_records.values())
            require(new_geoms*5 >= old_geoms*4, f'Source geometry loss >20%: {source_id}')
            if new_source['status'] == 'retained':
                require(old_records == new_records, f'Retention altered verified records: {source_id}')
                for key in SOURCE_KEYS - {'status', 'warnings'}:
                    require(new_source[key] == old_source[key], f'Retention altered source evidence: {source_id}.{key}')
        for source_id, source in sources.items():
            if source['status'] == 'retained':
                require(source_id in old_sources and old_sources[source_id]['status'] != 'unavailable', 'Retained source needs verified prior')


def loads(text_value):
    """Standard JSON with no duplicate keys or non-finite extension literals."""
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Non-finite JSON literal rejected')
    return json.loads(text_value, object_pairs_hook=pairs, parse_constant=constant)


def load_dataset(path, prior=None):
    dataset = loads(path.read_text(encoding='utf-8'))
    validate_dataset(dataset, prior=prior)
    return dataset
