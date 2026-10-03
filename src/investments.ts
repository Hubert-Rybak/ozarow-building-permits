import type {
  Feature,
  Point,
  MultiPoint,
  Polygon,
  MultiPolygon,
  LineString,
  MultiLineString,
} from "geojson";
export type InvestmentGeometry = Feature<
  Point | MultiPoint | Polygon | MultiPolygon | LineString | MultiLineString,
  {
    id: string;
    accuracy:
      | "source-point"
      | "parcel"
      | "project-footprint"
      | "route"
      | "marketing";
    sourceUrl: string;
    parcelId: string | null;
    note: string;
    fetchedAt: string;
    sourceUpdatedAt: string | null;
  }
>;
export interface InvestmentSource {
  id: string;
  name: string;
  url: string;
  fetchedAt: string | null;
  sourceUpdatedAt: string | null;
  status: "fresh" | "retained" | "static" | "unavailable";
  coverage: string;
  recordCount: number;
  warnings: string[];
  reuse: string;
}
export interface InvestmentRecord {
  id: string;
  sourceId: string;
  sourceRecordId: string;
  sourceUrl: string;
  title: string;
  recordType:
    | "project"
    | "budget-task"
    | "procurement"
    | "funding"
    | "planning-case"
    | "proposal"
    | "news"
    | "regional";
  investor:
    | "municipal"
    | "county"
    | "national"
    | "private"
    | "mixed"
    | "unknown";
  investorName: string | null;
  category: string;
  locality: string;
  address: string;
  status: string;
  statusAsOf: string | null;
  summary: string;
  years: number[];
  costs: {
    kind: string;
    amount: number | null;
    currency: string;
    label: string;
    year: number | null;
    scope: "local" | "multi-municipality" | "unknown";
    sourceUrl: string;
  }[];
  dates: { kind: string; date: string; label: string; sourceUrl: string }[];
  geometries: InvestmentGeometry[];
  parcelIds: string[];
  events: {
    id: string;
    title: string;
    date: string | null;
    sourceUrl: string;
  }[];
  facts: { label: string; value: string; sourceUrl: string }[];
  relatedIds: string[];
  warnings: string[];
  fetchedAt: string;
  sourceUpdatedAt: string | null;
}
export interface InvestmentDataset {
  schemaVersion: 1;
  generatedAt: string;
  records: InvestmentRecord[];
  sources: InvestmentSource[];
  warnings: string[];
  counts: {
    records: number;
    mapped: number;
    geometries: number;
    bySource: Record<string, number>;
  };
}
export interface InvestmentFilters {
  query: string;
  source: string;
  investor: string;
  category: string;
  status: string;
  year: string;
  mapping: "all" | "mapped" | "unmapped";
  sort: "newest" | "oldest" | "title";
}
export const investmentDefaults: InvestmentFilters = {
  query: "",
  source: "",
  investor: "",
  category: "",
  status: "",
  year: "",
  mapping: "all",
  sort: "newest",
};
export const investmentTypes: Record<InvestmentRecord["recordType"], string> = {
  project: "Projekt",
  "budget-task": "Zadanie budżetowe",
  procurement: "Zamówienie",
  funding: "Dofinansowanie",
  "planning-case": "Sprawa środowiskowa / planistyczna",
  proposal: "Propozycja",
  news: "Aktualność",
  regional: "Projekt ponadlokalny",
};
export const investorLabels: Record<InvestmentRecord["investor"], string> = {
  municipal: "Gmina",
  county: "Powiat",
  national: "Krajowy",
  private: "Prywatny",
  mixed: "Mieszany",
  unknown: "Nieustalony",
};
export const accuracyLabels: Record<
  InvestmentGeometry["properties"]["accuracy"],
  string
> = {
  "source-point": "Punkt ze źródła — nie obrys",
  parcel: "Działka — nie obrys inwestycji",
  "project-footprint": "Obrys projektu",
  route: "Trasa ze źródła",
  marketing: "Lokalizacja marketingowa — orientacyjna",
};
export function investmentUrl(value: unknown): string | null {
  if (
    typeof value !== "string" ||
    !/^https?:\/\//i.test(value) ||
    /[\u0000-\u0020\u007f\\]/.test(value)
  )
    return null;
  try {
    let decoded = value;
    for (let i = 0; i < 3; i++) decoded = decodeURIComponent(decoded);
    if (
      /[\s\u0000-\u001f\u007f\\]/.test(decoded) ||
      /(?:bearer\s|gh[pousr]_|github_pat_|sk-[A-Za-z0-9]{12})/i.test(decoded)
    )
      return null;
    const url = new URL(value);
    if (!url.hostname || url.username || url.password) return null;
    const secret =
      /(?:token|secret|password|passwd|credential|signature|authorization|api[-_]?key|access[-_]?key|session[-_]?id|jwt)/i;
    const contact =
      /^(?:auth|email|phone|creator|editor|cookie|cookies|session)$/i;
    for (const part of [
      new URL(decoded).search,
      new URL(decoded).hash.slice(1),
    ]) {
      for (const key of new URLSearchParams(part).keys()) {
        const normalized = key.replace(/[^a-z0-9]/gi, "");
        if (secret.test(key) || contact.test(normalized)) return null;
      }
    }
    return url.href;
  } catch {
    return null;
  }
}
function fail(path: string): never {
  throw new Error(`Nieprawidłowy kontrakt inwestycji v1: ${path}.`);
}
function obj(
  value: unknown,
  keys?: string[],
  path = "obiekt",
): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    return fail(path);
  const o = value as Record<string, unknown>;
  if (
    keys &&
    (Object.keys(o).length !== keys.length ||
      keys.some((k) => !Object.hasOwn(o, k)))
  )
    fail(path);
  return o;
}
function text(v: unknown, p: string, nonempty = false): asserts v is string {
  if (typeof v !== "string" || (nonempty && !v.trim())) fail(p);
}
function list(v: unknown, p: string): unknown[] {
  if (!Array.isArray(v)) fail(p);
  return v;
}
function strings(v: unknown, p: string): string[] {
  const a = list(v, p);
  a.forEach((x) => text(x, p));
  return a as string[];
}
function unique(v: string[], p: string) {
  if (new Set(v).size !== v.length) fail(p);
}
function enumeration(v: unknown, values: string[], p: string) {
  if (typeof v !== "string" || !values.includes(v)) fail(p);
}
function day(v: unknown, p: string, nullable = false) {
  if (nullable && v === null) return;
  if (
    typeof v !== "string" ||
    !/^\d{4}-\d{2}-\d{2}$/.test(v) ||
    !Number.isFinite(Date.parse(v)) ||
    new Date(v).toISOString().slice(0, 10) !== v
  )
    fail(p);
}
function time(v: unknown, p: string, nullable = false, utc = false) {
  if (nullable && v === null) return;
  if (
    typeof v !== "string" ||
    !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(
      v,
    ) ||
    !Number.isFinite(Date.parse(v))
  )
    fail(p);
  day(v.slice(0, 10), p);
  if (utc && !/(?:Z|[+-]00:00)$/.test(v)) fail(p);
}
function url(v: unknown, p: string) {
  if (!investmentUrl(v)) fail(p);
}
function number(v: unknown, p: string, integer = false) {
  if (
    typeof v !== "number" ||
    !Number.isFinite(v) ||
    v < 0 ||
    (integer && !Number.isInteger(v))
  )
    fail(p);
}
function year(v: unknown, p: string) {
  number(v, p, true);
  if ((v as number) < 1000 || (v as number) > 9999) fail(p);
}
const parcelPattern = /^143206_[45]\.\d{4}\.(?:AR_\d+\.)?\d+(?:\/\d+)?$/;
function parcel(v: unknown, p: string) {
  if (typeof v !== "string" || !parcelPattern.test(v)) fail(p);
}
function position(v: unknown): v is number[] {
  return (
    Array.isArray(v) &&
    v.length === 2 &&
    v.every((x) => typeof x === "number" && Number.isFinite(x)) &&
    v[0] >= -180 &&
    v[0] <= 180 &&
    v[1] >= -90 &&
    v[1] <= 90
  );
}
function line(v: unknown): v is number[][] {
  return Array.isArray(v) && v.length >= 2 && v.every(position);
}
function ring(v: unknown): boolean {
  if (
    !line(v) ||
    v.length < 4 ||
    v[0].length !== v.at(-1)!.length ||
    v[0].some((x, i) => x !== v.at(-1)![i])
  )
    return false;
  if (new Set(v.slice(0, -1).map((x) => x.slice(0, 2).join(","))).size < 3)
    return false;
  return (
    v
      .slice(0, -1)
      .reduce((s, p, i) => s + p[0] * v[i + 1][1] - v[i + 1][0] * p[1], 0) !== 0
  );
}
function polygon(v: unknown): boolean {
  return Array.isArray(v) && v.length > 0 && v.every(ring);
}
function geometries(
  value: unknown,
  record: Record<string, unknown>,
  ids: Set<string>,
) {
  for (const raw of list(value, "geometries")) {
    const f = obj(raw, ["type", "geometry", "properties"], "feature");
    if (f.type !== "Feature") fail("Feature");
    const g = obj(f.geometry, ["type", "coordinates"], "geometry"),
      p = obj(
        f.properties,
        [
          "id",
          "accuracy",
          "sourceUrl",
          "parcelId",
          "note",
          "fetchedAt",
          "sourceUpdatedAt",
        ],
        "geometry properties",
      );
    text(p.id, "geometry id", true);
    if (ids.has(p.id)) fail("powtórzona geometria");
    ids.add(p.id);
    text(p.note, "geometry note");
    url(p.sourceUrl, "geometry source");
    time(p.fetchedAt, "geometry fetchedAt");
    time(p.sourceUpdatedAt, "geometry sourceUpdatedAt", true);
    enumeration(p.accuracy, Object.keys(accuracyLabels), "accuracy");
    const c = g.coordinates;
    const valid =
      g.type === "Point"
        ? position(c)
        : g.type === "MultiPoint"
          ? Array.isArray(c) && c.length > 0 && c.every(position)
          : g.type === "Polygon"
            ? polygon(c)
            : g.type === "MultiPolygon"
              ? Array.isArray(c) && c.length > 0 && c.every(polygon)
              : g.type === "LineString"
                ? line(c)
                : g.type === "MultiLineString"
                  ? Array.isArray(c) && c.length > 0 && c.every(line)
                  : false;
    if (!valid) fail("typ / współrzędne / zamknięty obrys WGS84");
    const point = ["Point", "MultiPoint"].includes(g.type as string),
      area = ["Polygon", "MultiPolygon"].includes(g.type as string),
      route = ["LineString", "MultiLineString"].includes(g.type as string);
    if (
      (p.accuracy === "source-point" && !point) ||
      (p.accuracy === "parcel" && !area) ||
      (p.accuracy === "project-footprint" && !area) ||
      (p.accuracy === "route" && !route) ||
      (p.accuracy === "marketing" && !point && !area)
    )
      fail("dokładność nie odpowiada geometrii");
    if (p.parcelId !== null) {
      parcel(p.parcelId, "geometry parcelId");
      if (!(record.parcelIds as string[]).includes(p.parcelId as string))
        fail("geometry parcel join");
    }
    if (p.accuracy === "parcel" && p.parcelId === null)
      fail("brak identyfikatora potwierdzonej działki");
  }
}
export function parseInvestments(value: unknown): InvestmentDataset {
  const d = obj(
    value,
    [
      "schemaVersion",
      "generatedAt",
      "records",
      "sources",
      "warnings",
      "counts",
    ],
    "dataset",
  );
  if (d.schemaVersion !== 1) fail("schemaVersion");
  time(d.generatedAt, "generatedAt", false, true);
  strings(d.warnings, "warnings");
  const sources = new Map<string, Record<string, unknown>>(),
    totals = new Map<string, number>();
  for (const raw of list(d.sources, "sources")) {
    const s = obj(
      raw,
      [
        "id",
        "name",
        "url",
        "fetchedAt",
        "sourceUpdatedAt",
        "status",
        "coverage",
        "recordCount",
        "warnings",
        "reuse",
      ],
      "source",
    );
    for (const k of ["id", "name", "coverage", "reuse"])
      text(s[k], k, k === "id");
    url(s.url, "source url");
    time(s.fetchedAt, "source fetchedAt", true);
    time(s.sourceUpdatedAt, "sourceUpdatedAt", true);
    enumeration(
      s.status,
      ["fresh", "retained", "static", "unavailable"],
      "source status",
    );
    number(s.recordCount, "source recordCount", true);
    strings(s.warnings, "source warnings");
    if (sources.has(s.id as string)) fail("powtórzone źródło");
    sources.set(s.id as string, s);
    totals.set(s.id as string, 0);
  }
  const recordIds = new Set<string>();
  let mapped = 0,
    geometryCount = 0;
  for (const raw of list(d.records, "records")) {
    const r = obj(
      raw,
      [
        "id",
        "sourceId",
        "sourceRecordId",
        "sourceUrl",
        "title",
        "recordType",
        "investor",
        "investorName",
        "category",
        "locality",
        "address",
        "status",
        "statusAsOf",
        "summary",
        "years",
        "costs",
        "dates",
        "geometries",
        "parcelIds",
        "events",
        "facts",
        "relatedIds",
        "warnings",
        "fetchedAt",
        "sourceUpdatedAt",
      ],
      "record",
    );
    for (const k of [
      "id",
      "sourceId",
      "sourceRecordId",
      "title",
      "category",
      "locality",
      "address",
      "status",
      "summary",
    ])
      text(r[k], k, ["id", "sourceId", "sourceRecordId"].includes(k));
    if (recordIds.has(r.id as string)) fail("powtórzony rekord");
    recordIds.add(r.id as string);
    if (!sources.has(r.sourceId as string)) fail("nieznane źródło");
    totals.set(r.sourceId as string, totals.get(r.sourceId as string)! + 1);
    url(r.sourceUrl, "record sourceUrl");
    enumeration(r.recordType, Object.keys(investmentTypes), "recordType");
    enumeration(r.investor, Object.keys(investorLabels), "investor");
    if (r.investorName !== null) text(r.investorName, "investorName");
    day(r.statusAsOf, "statusAsOf", true);
    time(r.fetchedAt, "record fetchedAt");
    time(r.sourceUpdatedAt, "record sourceUpdatedAt", true);
    const ys = list(r.years, "years");
    ys.forEach((v) => year(v, "year"));
    if (new Set(ys).size !== ys.length) fail("powtórzony rok");
    const ps = strings(r.parcelIds, "parcelIds");
    ps.forEach((v) => parcel(v, "parcelId"));
    unique(ps, "powtórzona działka");
    unique(strings(r.relatedIds, "relatedIds"), "powtórzona relacja");
    strings(r.warnings, "record warnings");
    for (const raw of list(r.costs, "costs")) {
      const c = obj(
        raw,
        ["kind", "amount", "currency", "label", "year", "scope", "sourceUrl"],
        "cost",
      );
      for (const k of ["kind", "currency", "label"]) text(c[k], k);
      if (c.amount !== null) number(c.amount, "amount");
      if (c.year !== null) year(c.year, "cost year");
      enumeration(
        c.scope,
        ["local", "multi-municipality", "unknown"],
        "cost scope",
      );
      url(c.sourceUrl, "cost source");
    }
    for (const raw of list(r.dates, "dates")) {
      const e = obj(raw, ["kind", "date", "label", "sourceUrl"], "date");
      text(e.kind, "date kind");
      text(e.label, "date label");
      day(e.date, "date");
      url(e.sourceUrl, "date source");
    }
    const eventIds = new Set<string>();
    for (const raw of list(r.events, "events")) {
      const e = obj(raw, ["id", "title", "date", "sourceUrl"], "event");
      text(e.id, "event id", true);
      if (eventIds.has(e.id)) fail("powtórzone zdarzenie");
      eventIds.add(e.id);
      text(e.title, "event title");
      day(e.date, "event date", true);
      url(e.sourceUrl, "event source");
    }
    for (const raw of list(r.facts, "facts")) {
      const f = obj(raw, ["label", "value", "sourceUrl"], "fact");
      text(f.label, "fact label");
      text(f.value, "fact value");
      url(f.sourceUrl, "fact source");
    }
    geometries(r.geometries, r, new Set<string>());
    geometryCount += (r.geometries as unknown[]).length;
    if ((r.geometries as unknown[]).length) mapped++;
  }
  for (const raw of d.records as Record<string, unknown>[])
    for (const id of raw.relatedIds as string[])
      if (id === raw.id || !recordIds.has(id))
        fail("niepotwierdzone powiązanie");
  const counts = obj(
    d.counts,
    ["records", "mapped", "geometries", "bySource"],
    "counts",
  );
  for (const key of ["records", "mapped", "geometries"])
    number(counts[key], key, true);
  if (
    counts.records !== recordIds.size ||
    counts.mapped !== mapped ||
    counts.geometries !== geometryCount
  )
    fail("liczniki");
  const bySource = obj(counts.bySource, undefined, "counts bySource");
  if (Object.keys(bySource).length !== sources.size) fail("liczniki źródeł");
  for (const [id, s] of sources)
    if (s.recordCount !== totals.get(id) || bySource[id] !== totals.get(id))
      fail("liczniki źródła");
  return value as InvestmentDataset;
}
let requestNumber = 0;
export async function loadInvestments(
  fetcher: typeof fetch = fetch,
  signal?: AbortSignal,
  timeout = 25000,
): Promise<{ dataset: InvestmentDataset | null; error: string | null }> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let rejectAbort: (reason: Error) => void = () => {};
  const cancelled = new Promise<never>((_, reject) => {
    rejectAbort = reject;
  });
  const abort = () => {
    controller.abort();
    rejectAbort(
      new Error("Pobieranie anulowano lub przekroczono czas oczekiwania."),
    );
  };
  signal?.addEventListener("abort", abort, { once: true });
  try {
    if (signal?.aborted) throw new Error("Pobieranie anulowano.");
    timer = setTimeout(abort, timeout);
    const read = async () => {
      const response = await fetcher(
        `${import.meta.env.BASE_URL}data/investments.json?v=${Date.now()}-${++requestNumber}`,
        { signal: controller.signal, cache: "no-store" },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const contentType = response.headers?.get("content-type");
      if (contentType && !contentType.includes("json"))
        throw new Error("Odpowiedź nie jest JSON.");
      return parseInvestments(await response.json());
    };
    return { dataset: await Promise.race([read(), cancelled]), error: null };
  } catch (error) {
    return {
      dataset: null,
      error: `Nie udało się wczytać investments.json. ${error instanceof Error ? error.message : "Błąd danych."}`,
    };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
function normalized(v: string) {
  return v
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ł/g, "l")
    .replace(/Ł/g, "L")
    .toLocaleLowerCase("pl");
}
export function filterInvestments(
  records: InvestmentRecord[],
  filters: InvestmentFilters,
): InvestmentRecord[] {
  const words = normalized(filters.query).trim().split(/\s+/).filter(Boolean);
  const result = records.filter((r) => {
    const haystack = normalized(
      [
        r.id,
        r.sourceRecordId,
        r.title,
        r.address,
        r.locality,
        r.summary,
        ...r.parcelIds,
        ...r.facts.flatMap((f) => [f.label, f.value]),
      ].join(" "),
    );
    return (
      words.every((w) => haystack.includes(w)) &&
      (!filters.source || r.sourceId === filters.source) &&
      (!filters.investor || r.investor === filters.investor) &&
      (!filters.category || r.category === filters.category) &&
      (!filters.status || r.status === filters.status) &&
      (!filters.year || r.years.includes(Number(filters.year))) &&
      (filters.mapping === "all" ||
        (filters.mapping === "mapped"
          ? r.geometries.length > 0
          : r.geometries.length === 0))
    );
  });
  const dateKey = (r: InvestmentRecord) =>
    r.statusAsOf ||
    r.sourceUpdatedAt?.slice(0, 10) ||
    String(Math.max(0, ...r.years));
  return result.sort(
    (a, b) =>
      (filters.sort === "title"
        ? a.title.localeCompare(b.title, "pl")
        : filters.sort === "oldest"
          ? dateKey(a).localeCompare(dateKey(b))
          : dateKey(b).localeCompare(dateKey(a))) ||
      a.id.localeCompare(b.id, "pl"),
  );
}
export function investmentsCsv(records: InvestmentRecord[]): string {
  const cell = (value: unknown) => {
    let s = value === null ? "" : String(value);
    if (/^[\s\u0000-\u001f]*[=+@-]/.test(s)) s = "'" + s;
    return `"${s.replaceAll('"', '""')}"`;
  };
  const rows: unknown[][] = [
    [
      "ID",
      "Źródło ID",
      "ID źródłowy",
      "Tytuł",
      "Typ rekordu",
      "Inwestor",
      "Nazwa inwestora",
      "Kategoria",
      "Miejscowość",
      "Adres",
      "Status",
      "Status na dzień",
      "Lata",
      "Koszty (typ / zakres / rok)",
      "Działki",
      "Geometria (dokładność)",
      "Fakty",
      "Daty",
      "Zdarzenia",
      "Powiązane ID",
      "Ostrzeżenia",
      "Pobrano",
      "Edycja źródła",
      "URL źródła",
    ],
  ];
  for (const r of records)
    rows.push([
      r.id,
      r.sourceId,
      r.sourceRecordId,
      r.title,
      r.recordType,
      r.investor,
      r.investorName,
      r.category,
      r.locality,
      r.address,
      r.status,
      r.statusAsOf,
      r.years.join(", "),
      JSON.stringify(r.costs),
      r.parcelIds.join(", "),
      JSON.stringify(r.geometries.map((g) => g.properties)),
      JSON.stringify(r.facts),
      JSON.stringify(r.dates),
      JSON.stringify(r.events),
      r.relatedIds.join(", "),
      r.warnings.join(" | "),
      r.fetchedAt,
      r.sourceUpdatedAt,
      r.sourceUrl,
    ]);
  return (
    "\uFEFF" + rows.map((row) => row.map(cell).join(";")).join("\r\n") + "\r\n"
  );
}
