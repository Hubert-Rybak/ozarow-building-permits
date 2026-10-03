import type {
  Filters,
  ParcelCollection,
  ParcelFeature,
  Permit,
  RecordKind,
  SemanticStatus,
} from "./types";
export const defaultFilters: Filters = {
  period: "3months",
  query: "",
  kind: "",
  year: "",
  status: "",
  locality: "",
  mapping: "all",
  sort: "newest",
};
export const kindLabels: Record<RecordKind, string> = {
  application: "Wniosek",
  decision: "Decyzja",
  notification: "Zgłoszenie",
};
export const statusLabels: Record<SemanticStatus, string> = {
  approved: "Decyzja pozytywna",
  refused: "Odmowa / sprzeciw",
  pending: "Wniosek / zgłoszenie",
  withdrawn: "Wycofane / umorzone",
  unknown: "Wynik nieokreślony",
};
export const statusColors: Record<SemanticStatus, string> = {
  approved: "#247454",
  refused: "#b34d4d",
  pending: "#b17a20",
  withdrawn: "#717786",
  unknown: "#4b709a",
};
export function normalize(value: string): string {
  return value
    .toLocaleLowerCase("pl")
    .replace(/ł/g, "l")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}
/** Tolerates Polish inflection: "boisko" also finds "boiska", "szkoły" finds "szkole". */
export function searchStem(term: string): string {
  if (term.length < 5 || /\d/.test(term)) return term;
  return term.slice(0, term.length - (term.length >= 7 ? 2 : 1));
}
export function searchTerms(query: string): string[] {
  return normalize(query).split(/\s+/).filter(Boolean).map(searchStem);
}
export const kindColors: Record<RecordKind, string> = {
  decision: "#2B5C8A",
  notification: "#D88400",
  application: "#5B6875",
};
export const kindPlural: Record<RecordKind, string> = {
  decision: "Decyzje",
  notification: "Zgłoszenia",
  application: "Wnioski",
};
export function recordDate(record: Permit): string | null {
  return record.decisionDate || record.applicationDate || null;
}
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Nie podano";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Nie podano"
    : new Intl.DateTimeFormat("pl-PL", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Europe/Warsaw",
      }).format(date);
}
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(to.slice(0, 10)) - Date.parse(from.slice(0, 10))) / 86_400_000);
}
export function formatDate(value: string | null | undefined): string {
  if (!value) return "Brak daty";
  const date = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  return Number.isNaN(date.getTime())
    ? "Brak daty"
    : new Intl.DateTimeFormat("pl-PL", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Warsaw",
      }).format(date);
}
export function semanticStatus(record: Permit): SemanticStatus {
  const status = normalize(record.status);
  if (/wycof|umorz|cofniet/.test(status)) return "withdrawn";
  const unknownOutcome = /brak sprzeciw|nie\s*zatwierdz|nieudostepn|nieznan/.test(status);
  // Explicit opposition also matters for notifications; its absence is not a refusal.
  if (!unknownOutcome && /odmow|negatywn|sprzeciw|nie udziel/.test(status))
    return "refused";
  // A filed application/notification is not itself a permission or a decision.
  if (record.kind !== "decision") return "pending";
  if (unknownOutcome) return "unknown";
  // Approve only explicit, recognized outcomes, never a substring in a longer phrase.
  if ([
    "pozytywna",
    "pozytywny",
    "decyzja pozytywna",
    "zatwierdzono projekt",
    "zatwierdzenie projektu",
    "udzielono pozwolenia",
    "udzielenie pozwolenia",
  ].includes(status))
    return "approved";
  return "unknown";
}
const indexes = new WeakMap<
  ParcelCollection,
  {
    byParcel: Map<string, ParcelFeature>;
    byPermit: Map<string, ParcelFeature[]>;
  }
>();
function parcelIndex(parcels: ParcelCollection) {
  let index = indexes.get(parcels);
  if (!index) {
    index = { byParcel: new Map(), byPermit: new Map() };
    for (const feature of parcels.features) {
      index.byParcel.set(feature.properties.id, feature);
      for (const id of feature.properties.permitIds)
        index.byPermit.set(id, [...(index.byPermit.get(id) || []), feature]);
    }
    indexes.set(parcels, index);
  }
  return index;
}
export function getRecordParcels(
  record: Permit,
  parcels: ParcelCollection,
): ParcelFeature[] {
  const index = parcelIndex(parcels);
  const matched = new Map(
    (index.byPermit.get(record.id) || []).map((p) => [p.properties.id, p]),
  );
  for (const id of record.parcelIds) {
    const feature = index.byParcel.get(id);
    if (feature) matched.set(id, feature);
  }
  return [...matched.values()];
}
function dateWindow(referenceDate: Date) {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Europe/Warsaw",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(referenceDate);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find(p => p.type === type)?.value);
  const year = part("year"), month = part("month"), day = part("day");
  const today = new Date(Date.UTC(year, month - 1, day));
  // Subtract calendar months before clamping the day (May 31 → February 28/29).
  const cutoff = new Date(Date.UTC(year, month - 4, 1));
  const lastDay = new Date(Date.UTC(
    cutoff.getUTCFullYear(), cutoff.getUTCMonth() + 1, 0,
  )).getUTCDate();
  cutoff.setUTCDate(Math.min(day, lastDay));
  return {
    cutoff: cutoff.toISOString().slice(0, 10),
    today: today.toISOString().slice(0, 10),
  };
}
export function filterRecords(
  records: Permit[],
  filters: Filters,
  parcels: ParcelCollection,
  referenceDate = new Date(),
): Permit[] {
  const terms = searchTerms(filters.query);
  const window = filters.period === "3months" ? dateWindow(referenceDate) : null;
  return records
    .filter((record) => {
      if (window) {
        const date = recordDate(record)?.slice(0, 10);
        if (!date || date < window.cutoff || date > window.today) return false;
      }
      if (filters.kind && record.kind !== filters.kind) return false;
      if (filters.year && recordDate(record)?.slice(0, 4) !== filters.year)
        return false;
      if (filters.status && record.status !== filters.status) return false;
      if (filters.locality && record.locality !== filters.locality)
        return false;
      const mapped = getRecordParcels(record, parcels).length > 0;
      if (
        (filters.mapping === "mapped" && !mapped) ||
        (filters.mapping === "unmapped" && mapped) ||
        (filters.mapping === "partial" && (!mapped || record.geometryStatus !== "partial"))
      )
        return false;
      const searchable = normalize(
        [
          record.locality,
          record.street,
          record.title,
          record.description,
          record.cadastralRegion,
          ...record.parcelNumbers,
          ...record.parcelIds,
        ].join(" "),
      );
      return terms.every((term) => searchable.includes(term));
    })
    .sort((a, b) => {
      const left = recordDate(a),
        right = recordDate(b);
      if (!left) return right ? 1 : a.id.localeCompare(b.id, "pl");
      if (!right) return -1;
      return (
        (filters.sort === "newest"
          ? right.localeCompare(left)
          : left.localeCompare(right)) || a.id.localeCompare(b.id, "pl")
      );
    });
}
export function summarize(records: Permit[], parcels: ParcelCollection) {
  const ids = new Set<string>();
  let mapped = 0;
  for (const record of records) {
    const features = getRecordParcels(record, parcels);
    if (features.length) mapped += 1;
    features.forEach((feature) => ids.add(feature.properties.id));
  }
  return {
    total: records.length,
    mapped,
    unmapped: records.length - mapped,
    parcelCount: ids.size,
  };
}
export function safeUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}
export function csvCell(value: string | null): string {
  let text = value ?? "";
  // Spreadsheet formulas remain dangerous even behind whitespace or control characters.
  if (/^[\s\u0000-\u001f]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text))
    text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}
export const sourceLimitations = "CSV nie gwarantuje kompletności nierozpatrzonych wniosków ani wszystkich inwestycji. Decyzja nie oznacza pozwolenia; wynik należy potwierdzić w źródle. Obrysy to działki, nie budynki ani postęp prac.";

export function exportCsv(
  records: Permit[],
  parcels: ParcelCollection,
  coverage = "Zakres należy sprawdzić w źródle danych.",
): string {
  const header = [
    "ID",
    "Rodzaj",
    "Tytuł",
    "Opis",
    "Data wniosku",
    "Data decyzji",
    "Numer decyzji",
    "Status w źródle",
    "Miejscowość",
    "Ulica",
    "Obręb",
    "Działki",
    "Identyfikatory działek",
    "Kategoria",
    "Geometria dostępna",
    "Status geometrii",
    "Informacja o geometrii",
    "Źródło",
    "Zakres zbioru",
    "Ograniczenia zbioru",
  ];
  return (
    "\ufeff" +
    [
      header,
      ...records.map((record) => [
        record.id,
        kindLabels[record.kind],
        record.title,
        record.description,
        record.applicationDate,
        record.decisionDate,
        record.decisionNumber,
        record.status,
        record.locality,
        record.street,
        record.cadastralRegion,
        record.parcelNumbers.join(", "),
        record.parcelIds.join(", "),
        record.category,
        getRecordParcels(record, parcels).length ? "tak" : "nie",
        record.geometryStatus,
        record.geometryNote,
        safeUrl(record.sourceUrl) || "",
        coverage,
        sourceLimitations,
      ]),
    ]
      .map((row) => row.map(csvCell).join(";"))
      .join("\r\n")
  );
}

/** System number used by the GUNB search engine, e.g. "ST-MZ-OZ/WNIOSEK/24879/2026". */
export function gunbNumber(record: Permit): string {
  return record.id.replace(/^(?:permit|decision|application|notification):/, "");
}
/** The GUNB CSV is one archive for a whole voivodeship or country, never a single record. */
export function sourceFileLabel(url: string): string {
  if (/zgloszenia/i.test(url)) return "Plik źródłowy GUNB: archiwum ZIP zgłoszeń z całego kraju (duży plik)";
  if (/\.zip(?:$|\?)/i.test(url)) return "Plik źródłowy GUNB: archiwum ZIP całego województwa (duży plik)";
  return "Plik źródłowy GUNB";
}
export const gunbSearchUrl = "https://wyszukiwarka.gunb.gov.pl/";
export function geoportalParcelUrl(parcelId: string): string {
  return `https://mapy.geoportal.gov.pl/imapnext/imap/?identifyParcel=${encodeURI(parcelId)}`;
}
