import type {
  LoadedData,
  Metadata,
  ParcelCollection,
  Permit,
  PermitDataset,
} from "./types";
export const emptyParcels: ParcelCollection = {
  type: "FeatureCollection",
  features: [],
};
function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((v) => typeof v === "string");
}
function date(value: unknown): boolean {
  return (
    value === null ||
    (typeof value === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(value) &&
      !Number.isNaN(Date.parse(value)) &&
      new Date(value).toISOString().slice(0, 10) === value)
  );
}
export function parsePermits(value: unknown): PermitDataset {
  if (
    !object(value) ||
    value.schemaVersion !== 1 ||
    !Array.isArray(value.records) ||
    !object(value.source) ||
    typeof value.generatedAt !== "string"
  )
    throw new Error("Nieprawidłowy format zbioru (wymagany kontrakt v1).");
  for (const key of ["name", "url", "downloadedAt", "coverage"])
    if (typeof value.source[key] !== "string")
      throw new Error("Brak informacji o źródle danych.");
  const ids = new Set<string>();
  for (const row of value.records) {
    if (
      !object(row) ||
      typeof row.id !== "string" ||
      !row.id ||
      ids.has(row.id) ||
      typeof row.kind !== "string" ||
      !["application", "decision", "notification"].includes(row.kind)
    )
      throw new Error(
        "Nieprawidłowy lub powtórzony identyfikator / rodzaj wpisu.",
      );
    for (const key of [
      "title",
      "description",
      "status",
      "locality",
      "street",
      "municipality",
      "cadastralRegion",
      "category",
      "sourceUrl",
      "geometryNote",
    ])
      if (typeof row[key] !== "string")
        throw new Error(`Brak pola ${key} we wpisie.`);
    if (
      !date(row.applicationDate) ||
      !date(row.decisionDate) ||
      !(
        row.decisionNumber === null || typeof row.decisionNumber === "string"
      ) ||
      !strings(row.parcelNumbers) ||
      !strings(row.parcelIds) ||
      typeof row.geometryStatus !== "string" ||
      !["matched", "partial", "unresolved"].includes(row.geometryStatus)
    )
      throw new Error("Nieprawidłowe daty lub dane działki.");
    ids.add(row.id);
  }
  return value as unknown as PermitDataset;
}
function validRing(value: unknown): boolean {
  if (!Array.isArray(value) || value.length < 4) return false;
  if (
    !value.every(
      (p) =>
        Array.isArray(p) &&
        p.length >= 2 &&
        p.every((n) => typeof n === "number" && Number.isFinite(n)) &&
        p[0] >= -180 &&
        p[0] <= 180 &&
        p[1] >= -90 &&
        p[1] <= 90,
    )
  )
    return false;
  return value[0][0] === value.at(-1)[0] && value[0][1] === value.at(-1)[1];
}
function validPolygon(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0 && value.every(validRing);
}
export function parseParcels(value: unknown): ParcelCollection {
  if (
    !object(value) ||
    value.type !== "FeatureCollection" ||
    !Array.isArray(value.features)
  )
    throw new Error("Nieprawidłowy format GeoJSON.");
  const ids = new Set<string>();
  for (const feature of value.features) {
    if (
      !object(feature) ||
      feature.type !== "Feature" ||
      !object(feature.properties) ||
      !object(feature.geometry)
    )
      throw new Error("Nieprawidłowa działka GeoJSON.");
    const p = feature.properties,
      g = feature.geometry;
    if (
      typeof p.id !== "string" ||
      !p.id ||
      ids.has(p.id) ||
      !strings(p.permitIds) ||
      ["parcelNumber", "region", "sourceUrl"].some(
        (k) => typeof p[k] !== "string",
      )
    )
      throw new Error("Brak potwierdzonego identyfikatora działki lub źródła.");
    if (!(
      (g.type === "Polygon" && validPolygon(g.coordinates)) ||
      (g.type === "MultiPolygon" &&
        Array.isArray(g.coordinates) &&
        g.coordinates.length > 0 &&
        g.coordinates.every(validPolygon))
    ))
      throw new Error(
        "Wymagane zamknięte obrysy Polygon/MultiPolygon w WGS84.",
      );
    ids.add(p.id);
  }
  return value as unknown as ParcelCollection;
}
function parseMetadata(value: unknown): Metadata | null {
  if (!object(value)) return null;
  return {
    generatedAt:
      typeof value.generatedAt === "string" ? value.generatedAt : undefined,
    coverage: typeof value.coverage === "string" ? value.coverage : undefined,
    warnings: strings(value.warnings) ? value.warnings : [],
    sources: Array.isArray(value.sources)
      ? value.sources.filter(
          (s): s is { name: string; url: string } =>
            object(s) &&
            typeof s.name === "string" &&
            typeof s.url === "string",
        )
      : [],
  };
}
export async function loadData(
  fetcher: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<LoadedData> {
  async function read(path: string) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) controller.abort();
    const timer = setTimeout(abort, 25_000);
    try {
      const response = await fetcher(path, {
        signal: controller.signal,
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return (await response.json()) as unknown;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    }
  }
  const snapshot = () => Promise.allSettled([
    read(`${import.meta.env.BASE_URL}data/permits.json`).then(parsePermits),
    read(`${import.meta.env.BASE_URL}data/parcels.geojson`).then(parseParcels),
    read(`${import.meta.env.BASE_URL}data/metadata.json`).then(parseMetadata),
  ] as const);
  let [permitResult, parcelResult, metaResult] = await snapshot();
  // A daily Pages deployment may change between requests. Never join mixed data.
  const inconsistent = () => {
    if (permitResult.status !== "fulfilled") return false;
    const dataset = permitResult.value;
    if (metaResult.status === "fulfilled" && metaResult.value &&
        metaResult.value.generatedAt !== dataset.generatedAt) return true;
    if (parcelResult.status !== "fulfilled") return false;
    // Stable IDs cannot detect stale coordinates. Legacy geometry is also untrusted.
    if (typeof parcelResult.value.generatedAt !== "string" ||
        parcelResult.value.generatedAt !== dataset.generatedAt) return true;
    const byRecord = new Map(dataset.records.map(r => [r.id, r]));
    const byParcel = new Map(parcelResult.value.features.map(f => [f.properties.id, f.properties]));
    for (const feature of byParcel.values()) {
      if (!feature.permitIds.length) return true;
      for (const id of feature.permitIds)
        if (!byRecord.get(id)?.parcelIds.includes(feature.id)) return true;
    }
    for (const record of dataset.records)
      for (const id of record.parcelIds) {
        const parcel = byParcel.get(id);
        if (parcel ? !parcel.permitIds.includes(record.id) : record.geometryStatus === "matched") return true;
      }
    return false;
  };
  if (inconsistent() && !signal?.aborted)
    [permitResult, parcelResult, metaResult] = await snapshot();
  const mixedSnapshot = inconsistent();
  if (permitResult.status === "rejected")
    return {
      dataset: null,
      parcels: emptyParcels,
      metadata: null,
      warnings: [],
      error: `Nie udało się wczytać wpisów z permits.json. Sprawdź pliki danych i połączenie. ${permitResult.reason instanceof Error ? permitResult.reason.message : ""}`,
    };
  const metadata = !mixedSnapshot && metaResult.status === "fulfilled" ? metaResult.value : null;
  const warnings = [...(metadata?.warnings || [])];
  if (mixedSnapshot)
    warnings.push("Niespójny zestaw plików po ponownym pobraniu. Lista wpisów pozostaje dostępna, ale obrysy i metadane ukryto, aby nie pokazać błędnych powiązań. Odśwież stronę lub spróbuj ponownie później.");
  else if (!metadata)
    warnings.push("Nie udało się wczytać metadata.json. Szczegółowe ograniczenia i dodatkowe źródła importu mogą być niedostępne.");
  if (parcelResult.status === "rejected")
    warnings.push(
      "Nie udało się wczytać parcels.geojson. Wpisy można przeglądać na liście; obrysy działek są niedostępne.",
    );
  return {
    dataset: permitResult.value,
    parcels:
      !mixedSnapshot && parcelResult.status === "fulfilled" ? parcelResult.value : emptyParcels,
    metadata,
    warnings,
    error: null,
  };
}
