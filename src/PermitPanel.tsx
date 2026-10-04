import { useEffect, useMemo, useState } from "react";
import { emptyParcels, loadData } from "./data";
import {
  daysBetween,
  defaultFilters,
  exportCsv,
  filterRecords,
  formatDate,
  geoportalParcelUrl,
  getRecordParcels,
  gunbNumber,
  gunbSearchUrl,
  kindColors,
  kindLabels,
  kindPlural,
  recordDate,
  semanticStatus,
  sourceFileLabel,
  summarize,
} from "./model";
import { readAndRemember, type SeenState } from "./seen";
import type { Filters, LoadedData, ParcelCollection, Permit, RecordKind } from "./types";
import { BackButton, Chip, MapButton, ChipSelect, CopyButton, ExternalLink, MoreButton, PAGE, SearchBox, ShareButton } from "./ui";
import type { InvestmentRecord } from "./investments";
import { formatDistance } from "./geo";

const initialData: LoadedData = { dataset: null, parcels: emptyParcels, metadata: null, warnings: [], error: null };
export const genericDescription = "Bezpieczny skrót rodzaju inwestycji. Swobodny opis GUNB pominięto ze względu na możliwość występowania danych osobowych.";
const integrityWarning = /^(Niespójny zestaw plików|Nie udało się wczytać)/;

export function usePermits() {
  const [data, setData] = useState<LoadedData>(initialData);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [filters, setFilters] = useState<Filters>({ ...defaultFilters });
  const [onlyNew, setOnlyNew] = useState(false);
  const [seen, setSeen] = useState<SeenState>({ newIds: new Set(), lastVisit: null });
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    loadData(fetch, controller.signal).then(result => {
      if (controller.signal.aborted) return;
      setData(result);
      setLoading(false);
      if (result.dataset) setSeen(readAndRemember("permits", result.dataset.records.map(r => r.id)));
    });
    return () => controller.abort();
  }, [attempt]);
  const all = data.dataset?.records || [];
  const base = useMemo(() => filterRecords(all, filters, data.parcels), [data.dataset, data.parcels, filters]);
  const filtered = useMemo(() => onlyNew ? base.filter(r => seen.newIds.has(r.id)) : base, [base, onlyNew, seen]);
  const counts = useMemo(() => summarize(filtered, data.parcels), [filtered, data.parcels]);
  const allCounts = useMemo(() => summarize(all, data.parcels), [data.dataset, data.parcels]);
  return {
    data, loading, filters, setFilters, onlyNew, setOnlyNew, seen, all, filtered, counts, allCounts,
    retry: () => setAttempt(n => n + 1),
  };
}
export type PermitState = ReturnType<typeof usePermits>;

function downloadCsv(records: Permit[], parcels: ParcelCollection, coverage: string | undefined) {
  const blob = new Blob([exportCsv(records, parcels, coverage)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "budowy-ozarow-wyniki.csv";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function placeLine(record: Permit) {
  return [record.locality, record.street].filter(Boolean).join(", ") || "Brak adresu w źródle";
}

function statusSentence(record: Permit) {
  if (record.kind === "application") return "Wniosek nie jest pozwoleniem na budowę. Rozstrzygnięcie sprawdzisz w źródle.";
  if (record.kind === "notification")
    return /brak sprzeciw/i.test(record.status)
      ? "Urząd nie wniósł sprzeciwu wobec zgłoszenia (według GUNB). Zgłoszenie nie jest decyzją o pozwoleniu na budowę."
      : "Zgłoszenie nie jest decyzją o pozwoleniu na budowę. Jego przebieg sprawdzisz w źródle.";
  const number = record.decisionNumber ? ` nr ${record.decisionNumber}` : "";
  const status = semanticStatus(record);
  if (status === "refused") return `Źródło podaje odmowę lub sprzeciw („${record.status}”) dla decyzji${number}. Treść sprawdzisz w źródle.`;
  if (status === "withdrawn") return `Źródło podaje, że sprawa${number} została wycofana lub umorzona („${record.status}”).`;
  if (status === "approved") return `Źródło podaje decyzję pozytywną${number} („${record.status}”). Treść i zakres potwierdź w źródle.`;
  return `Urząd odnotował decyzję${number}. Dane GUNB nie mówią, czy była pozytywna — treść sprawdzisz w źródle.`;
}

export interface Nearby {
  permits: { item: Permit; meters: number }[];
  investments: { item: InvestmentRecord; meters: number }[];
}

export function PermitDetail({ record, parcels, onClose, onBackToMap, onPick, nearby, share, isNew }: {
  record: Permit;
  parcels: ParcelCollection;
  onClose: () => void;
  /** Phone only: close the card and return to the map view from before it. */
  onBackToMap?: () => void;
  onPick: (layer: "permits" | "investments", id: string) => void;
  nearby: Nearby;
  share: string;
  isNew: boolean;
}) {
  const features = getRecordParcels(record, parcels);
  const date = recordDate(record);
  return (
    <section className="detail-panel" aria-labelledby="detail-title" data-selected-id={record.id} tabIndex={-1}>
      <div className="detail-bar">
        <div className="detail-nav">
          <BackButton onClick={onClose} label="Zamknij szczegóły" />
          {onBackToMap && <MapButton onClick={onBackToMap} />}
        </div>
        <ShareButton url={share} />
      </div>
      <div className="detail-kicker">
        <span className="kind-badge" style={{ "--kind": kindColors[record.kind] } as React.CSSProperties}>
          {kindLabels[record.kind]}
        </span>
        <span>{formatDate(date)}</span>
        {isNew && <span className="new-badge">Nowe</span>}
      </div>
      <h2 id="detail-title" className="detail-title">{record.title || "Bez tytułu"}</h2>
      <p className="detail-place">{placeLine(record)}</p>
      <p className="detail-sub">
        {record.parcelNumbers.length ? `działka ${record.parcelNumbers.slice(0, 4).join(", ")}${record.parcelNumbers.length > 4 ? ` i ${record.parcelNumbers.length - 4} więcej` : ""}` : "działka nie podana"}
        {features.length === 0 ? " · brak obrysu na mapie" : record.geometryStatus === "partial" ? ` · na mapie ${features.length} z ${record.parcelIds.length} działek` : ""}
      </p>
      <p className="status-sentence">{statusSentence(record)}</p>
      {record.description && record.description !== genericDescription && <p className="description">{record.description}</p>}
      {record.applicationDate && record.decisionDate && (
        <div className="timeline" aria-label="Przebieg">
          <div><span>Wniosek</span><strong>{formatDate(record.applicationDate)}</strong></div>
          <span className="timeline-line"><span>{daysBetween(record.applicationDate, record.decisionDate)} dni</span></span>
          <div className="end"><span>Decyzja</span><strong>{formatDate(record.decisionDate)}</strong></div>
        </div>
      )}
      <h3 className="section-title">Sprawdź u źródła</h3>
      <div className="verify-list">
        <div className="verify-primary">
          <ExternalLink url={gunbSearchUrl} sub={`Wpisz numer ${gunbNumber(record)}`}>Wyszukiwarka GUNB</ExternalLink>
          <CopyButton value={gunbNumber(record)} label="Kopiuj numer" />
        </div>
        {features.slice(0, 3).map(feature => (
          <ExternalLink key={feature.properties.id} className="verify-link" url={geoportalParcelUrl(feature.properties.id)}>
            Działka {feature.properties.parcelNumber} w Geoportalu
          </ExternalLink>
        ))}
        <ExternalLink className="file-link" url={record.sourceUrl}>{sourceFileLabel(record.sourceUrl)}</ExternalLink>
      </div>
      {nearby.permits.length > 0 && (
        <>
          <h3 className="section-title">W pobliżu (do 300 m)</h3>
          <ul className="nearby-list">
            {nearby.permits.map(({ item, meters }) => (
              <li key={item.id}>
                <button type="button" onClick={() => onPick("permits", item.id)}>
                  <span className="nearby-main"><strong>{item.title}</strong><span>{kindLabels[item.kind]} · {formatDate(recordDate(item))}</span></span>
                  <span className="nearby-distance">{formatDistance(meters)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {nearby.investments.length > 0 && (
        <>
          <h3 className="section-title">Inwestycje publiczne w pobliżu (do 1 km)</h3>
          <ul className="nearby-list">
            {nearby.investments.map(({ item, meters }) => (
              <li key={item.id}>
                <button type="button" onClick={() => onPick("investments", item.id)}>
                  <span className="nearby-main"><strong>{item.title}</strong><span>{item.status}</span></span>
                  <span className="nearby-distance">{formatDistance(meters)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <details className="tech-details">
        <summary>Dane techniczne</summary>
        <dl>
          <dt>Numer w GUNB</dt><dd className="mono">{gunbNumber(record)}</dd>
          <dt>Numer decyzji</dt><dd>{record.decisionNumber || "Nie podano"}</dd>
          <dt>Data wniosku</dt><dd>{formatDate(record.applicationDate)}</dd>
          <dt>Data decyzji</dt><dd>{formatDate(record.decisionDate)}</dd>
          <dt>Status w źródle</dt><dd>{record.status || "Brak statusu w źródle"}</dd>
          <dt>Kategoria obiektu (GUNB)</dt><dd>{record.category || "Nie podano"}</dd>
          <dt>Gmina</dt><dd>{record.municipality || "Nie podano"}</dd>
          <dt>Obręb w rejestrze</dt><dd className="mono">{record.cadastralRegion || "Nie podano"}</dd>
          <dt>Działki w rejestrze</dt><dd>{record.parcelNumbers.join(", ") || "Nie podano"}</dd>
          <dt>Geometria</dt><dd>{features.length ? `Obrysy ULDK: ${features.length} z ${record.parcelIds.length}` : "Brak potwierdzonej geometrii — wpis pozostaje dostępny na liście."}{record.geometryNote ? ` ${record.geometryNote}` : ""}</dd>
        </dl>
        {record.parcelIds.length > 0 && (
          <ul className="parcel-list">
            {record.parcelIds.map((id, index) => {
              const feature = features.find(f => f.properties.id === id);
              return (
                <li key={`${id}-${index}`}>
                  <code>{id}</code>
                  {feature ? <ExternalLink url={feature.properties.sourceUrl}>Odpowiedź ULDK (WKT)</ExternalLink> : <span className="muted">bez obrysu</span>}
                </li>
              );
            })}
          </ul>
        )}
      </details>
    </section>
  );
}

export function PermitRow({ record, mapped, selected, isNew, onSelect }: {
  record: Permit;
  mapped: boolean;
  selected: boolean;
  isNew: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button type="button" className={`result-row${selected ? " selected" : ""}`} aria-pressed={selected}
        data-record-id={record.id} onClick={onSelect}>
        <span className="row-mark square" style={{ background: kindColors[record.kind] }} aria-hidden="true" />
        <span className="row-body">
          <span className="row-top">
            <span className="row-kind">{kindLabels[record.kind]}</span>
            <time dateTime={recordDate(record) || undefined}>{formatDate(recordDate(record))}</time>
            {isNew && <span className="new-badge">Nowe</span>}
          </span>
          <span className="row-title">{record.title || "Bez tytułu"}</span>
          <span className="row-place">{placeLine(record)}</span>
          {!mapped
            ? <span className="row-flag">Tylko na liście — brak obrysu</span>
            : record.geometryStatus === "partial" ? <span className="row-flag">Częściowy obrys</span> : null}
        </span>
      </button>
    </li>
  );
}

export function PermitList({ state, selectedId, onSelect, onSearchFocus }: {
  state: PermitState;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onSearchFocus: () => void;
}) {
  const { data, loading, filters, setFilters, onlyNew, setOnlyNew, seen, all, filtered, counts } = state;
  const [shown, setShown] = useState(PAGE);
  useEffect(() => setShown(PAGE), [filtered]);
  const update = (key: keyof Filters, value: string) => setFilters(prev => ({ ...prev, [key]: value }));
  const reset = () => { setFilters({ ...defaultFilters }); setOnlyNew(false); };
  const activeFilters = Object.entries(filters).filter(([key, value]) =>
    key !== "sort" && value !== defaultFilters[key as keyof Filters]).length + (onlyNew ? 1 : 0);
  const options = useMemo(() => ({
    years: [...new Set(all.map(r => recordDate(r)?.slice(0, 4)).filter((v): v is string => !!v))].sort().reverse(),
    statuses: [...new Set(all.map(r => r.status).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pl")),
    localities: [...new Set(all.map(r => r.locality).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pl")),
  }), [data.dataset]);
  const kindCounts = useMemo(() => {
    const rows = filterRecords(all, { ...filters, kind: "" }, data.parcels);
    const result = new Map<RecordKind, number>();
    for (const row of onlyNew ? rows.filter(r => seen.newIds.has(r.id)) : rows) result.set(row.kind, (result.get(row.kind) || 0) + 1);
    return result;
  }, [all, filters, data.parcels, onlyNew, seen]);
  const kinds = (["decision", "notification", "application"] as RecordKind[]).filter(kind => kindCounts.has(kind) || filters.kind === kind);
  const newCount = useMemo(() => filterRecords(all, filters, data.parcels).filter(r => seen.newIds.has(r.id)).length, [all, filters, data.parcels, seen]);
  const ready = !loading && !data.error;
  const mappedIds = useMemo(() => new Set(filtered.filter(r => getRecordParcels(r, data.parcels).length).map(r => r.id)), [filtered, data.parcels]);
  return (
    <div className="panel-list">
      <div className="panel-tools">
        <SearchBox id="search" label="Szukaj w rejestrze" value={filters.query} onChange={value => update("query", value)}
          placeholder="Miejscowość, ulica, działka, rodzaj" onFocus={onSearchFocus} />
        <div className="chip-row" role="group" aria-label="Filtry budów">
          <ChipSelect label="Okres" value={filters.period} onChange={value => update("period", value)} active={filters.period !== "3months"}>
            <option value="3months">Ostatnie 3 miesiące</option>
            <option value="all">Wszystkie daty</option>
          </ChipSelect>
          {kinds.map(kind => (
            <Chip key={kind} pressed={filters.kind === kind} dot={kindColors[kind]} shape="square"
              onClick={() => update("kind", filters.kind === kind ? "" : kind)}>
              {kindPlural[kind]} <span className="chip-count">{kindCounts.get(kind) || 0}</span>
            </Chip>
          ))}
          {(newCount > 0 || onlyNew) && (
            <Chip pressed={onlyNew} onClick={() => setOnlyNew(!onlyNew)}>
              Nowe od ostatniej wizyty <span className="chip-count">{newCount}</span>
            </Chip>
          )}
          <ChipSelect label="Miejscowość" value={filters.locality} onChange={value => update("locality", value)} active={!!filters.locality}>
            <option value="">Cała gmina</option>
            {options.localities.map(l => <option key={l}>{l}</option>)}
          </ChipSelect>
        </div>
        <details className="more-filters">
          <summary>Więcej filtrów{activeFilters > 0 && <span className="filter-number" aria-label={`${activeFilters} aktywnych filtrów`}>{activeFilters}</span>}</summary>
          <div className="filter-grid">
            <label>Rodzaj wpisu
              <select value={filters.kind} onChange={e => update("kind", e.target.value)}>
                <option value="">Wszystkie rodzaje</option>
                <option value="application">Wnioski</option>
                <option value="decision">Decyzje</option>
                <option value="notification">Zgłoszenia</option>
              </select>
            </label>
            <label>Rok wpisu
              <select value={filters.year} onChange={e => update("year", e.target.value)}>
                <option value="">Wszystkie lata</option>
                {options.years.map(y => <option key={y}>{y}</option>)}
              </select>
            </label>
            <label>Status w źródle
              <select value={filters.status} onChange={e => update("status", e.target.value)}>
                <option value="">Wszystkie statusy</option>
                {options.statuses.map(s => <option key={s}>{s}</option>)}
              </select>
            </label>
            <label>Położenie na mapie
              <select value={filters.mapping} onChange={e => update("mapping", e.target.value)}>
                <option value="all">Wszystkie wpisy</option>
                <option value="mapped">Z obrysem działki</option>
                <option value="partial">Z częściowym obrysem</option>
                <option value="unmapped">Bez obrysu (tylko lista)</option>
              </select>
            </label>
            <label>Sortowanie
              <select value={filters.sort} onChange={e => update("sort", e.target.value)}>
                <option value="newest">Najnowsze najpierw</option>
                <option value="oldest">Najstarsze najpierw</option>
              </select>
            </label>
          </div>
        </details>
      </div>
      <div className="list-summary">
        <p aria-live="polite">
          {loading ? "Wczytywanie…" : data.error ? "Lista niedostępna" : (
            <><strong>{counts.total} {counts.total === 1 ? "wpis" : "wpisów"}</strong> · {counts.mapped} na mapie{counts.unmapped ? ` · ${counts.unmapped} tylko na liście` : ""}</>
          )}
        </p>
        <div className="list-actions">
          {activeFilters > 0 && <button type="button" className="text-button" onClick={reset} aria-label="Wyczyść filtry">Wyczyść</button>}
          <button type="button" className="text-button" disabled={!ready || !filtered.length}
            onClick={() => downloadCsv(filtered, data.parcels, data.dataset?.source.coverage)}>Eksport CSV</button>
        </div>
      </div>
      {!loading && data.warnings.some(w => integrityWarning.test(w)) && (
        <section className="alert" role="alert">
          <strong>Ograniczenia odczytu budów</strong>
          <ul>{data.warnings.filter(w => integrityWarning.test(w)).map((w, i) => <li key={i}>{w}</li>)}</ul>
          <button type="button" className="primary-button" onClick={state.retry}>Ponów odczyt</button>
        </section>
      )}
      {data.error && !loading && (
        <section className="alert error" role="alert">
          <h2>Dane są chwilowo niedostępne</h2>
          <p>{data.error}</p>
          <button type="button" className="primary-button" onClick={state.retry}>Spróbuj ponownie</button>
        </section>
      )}
      <section id="results" className="results" aria-labelledby="results-title" tabIndex={-1}>
        <h2 id="results-title" className="sr-only">Wpisy{ready ? ` (${counts.total})` : ""}</h2>
        {loading ? (
          <div className="empty-state"><span className="loading-ring" aria-hidden="true" /><p>Wczytujemy publiczny rejestr…</p></div>
        ) : data.error ? (
          <div className="empty-state"><p>Nie można ustalić liczby wpisów. Spróbuj ponownie.</p></div>
        ) : !filtered.length ? (
          <div className="empty-state">
            <h3>{all.length ? "Brak wyników dla tych filtrów." : "Brak wpisów w załadowanym zbiorze."}</h3>
            <p>{all.length
              ? filters.period === "3months" ? "Zmień zapytanie albo wybierz „Wszystkie daty”." : "Zmień zapytanie lub wyczyść filtry."
              : "To nie jest potwierdzenie braku inwestycji w gminie. Sprawdź zakres i źródło w „O danych”."}</p>
          </div>
        ) : (
          <>
            <ul className="result-list">
              {filtered.slice(0, Math.max(shown, filtered.findIndex(r => r.id === selectedId) + 1)).map(r => (
                <PermitRow key={r.id} record={r} mapped={mappedIds.has(r.id)} selected={r.id === selectedId}
                  isNew={seen.newIds.has(r.id)} onSelect={() => onSelect(r.id)} />
              ))}
            </ul>
            <MoreButton shown={shown} total={filtered.length} onMore={() => setShown(n => n + PAGE)} />
          </>
        )}
      </section>
      <p className="panel-note">Wpis w rejestrze nie oznacza zgody na budowę. Mapa pokazuje działki, nie budynki.</p>
    </div>
  );
}
