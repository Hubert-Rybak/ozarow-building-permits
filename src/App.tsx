import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { emptyParcels, loadData } from "./data";
import {
  defaultFilters,
  exportCsv,
  filterRecords,
  formatDate,
  getRecordParcels,
  kindLabels,
  recordDate,
  safeUrl,
  semanticStatus,
  statusLabels,
  summarize,
} from "./model";
import type { Filters, LoadedData, ParcelCollection, Permit } from "./types";
import ParcelMap from "./ParcelMap";

function SourceLink({
  url,
  children,
  className = "",
}: {
  url: string;
  children: React.ReactNode;
  className?: string;
}) {
  const href = safeUrl(url);
  return href ? (
    <a
      className={className}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
      <span aria-hidden="true"> ↗</span>
    </a>
  ) : (
    <span className="muted">Link źródłowy niedostępny</span>
  );
}
function Detail({
  record,
  parcels,
  onClose,
}: {
  record: Permit;
  parcels: ParcelCollection;
  onClose: () => void;
}) {
  const features = getRecordParcels(record, parcels);
  return (
    <section
      className="detail-panel"
      aria-labelledby="detail-title"
      data-selected-id={record.id}
    >
      <div className="detail-top">
        <div>
          <span className="eyebrow">WYBRANY WPIS</span>
          <h2 id="detail-title">Szczegóły wpisu</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Zamknij szczegóły"
        >
          ×
        </button>
      </div>
      <div className="record-tags">
        <span className={`badge ${semanticStatus(record)}`}>
          {kindLabels[record.kind]}
        </span>
        <span className="badge neutral">
          {record.status || "Brak statusu w źródle"}
        </span>
      </div>
      <h3>{record.title || "Bez tytułu"}</h3>
      {record.kind === "application" && (
        <p className="semantic-note">Wniosek nie jest pozwoleniem na budowę.</p>
      )}
      {record.kind === "notification" && (
        <p className="semantic-note">
          Zgłoszenie nie jest decyzją o pozwoleniu na budowę. Sprawdź jego
          przebieg w źródle.
        </p>
      )}
      {record.kind === "decision" && (
        <p className="semantic-note">
          Wynik: {statusLabels[semanticStatus(record)].toLocaleLowerCase("pl")}.
          Status i treść decyzji należy potwierdzić w źródle.
        </p>
      )}
      {record.description && record.description !== "Bezpieczny skrót rodzaju inwestycji. Swobodny opis GUNB pominięto ze względu na możliwość występowania danych osobowych." && (
        <p className="description">{record.description}</p>
      )}
      <dl className="detail-grid">
        <div>
          <dt>Miejscowość</dt>
          <dd>{record.locality || "Brak danych"}</dd>
        </div>
        <div>
          <dt>Ulica</dt>
          <dd>{record.street || "Nie podano"}</dd>
        </div>
        <div>
          <dt>Data wniosku</dt>
          <dd>{formatDate(record.applicationDate)}</dd>
        </div>
        <div>
          <dt>Data decyzji</dt>
          <dd>{formatDate(record.decisionDate)}</dd>
        </div>
        <div>
          <dt>Numer decyzji</dt>
          <dd>{record.decisionNumber || "Nie podano"}</dd>
        </div>
        <div>
          <dt>Kategoria obiektu</dt>
          <dd>{record.category || "Nie podano"}</dd>
        </div>
        <div>
          <dt>Gmina</dt>
          <dd>{record.municipality || "Nie podano"}</dd>
        </div>
        <div>
          <dt>Obręb w rejestrze</dt>
          <dd>{record.cadastralRegion || "Nie podano"}</dd>
        </div>
      </dl>
      <h4>Działki i ich położenie</h4>
      <p className="parcel-numbers">
        Numery w rejestrze:{" "}
        <strong>{record.parcelNumbers.join(", ") || "Nie podano"}</strong>
      </p>
      {features.length === 0 ? (
        <p className="geometry-note">
          Brak potwierdzonej geometrii — wpis pozostaje dostępny na liście.
        </p>
      ) : (
        <>
          <p className="geometry-note">
            Potwierdzone obrysy: <strong>{features.length}</strong>.{" "}
            {record.geometryStatus === "partial"
              ? "Dopasowanie częściowe — nie wszystkie działki mają geometrię."
              : "Mapa pokazuje tylko dostępne, potwierdzone obrysy."}
          </p>
          <ul className="parcel-list">
            {features.map((f) => (
              <li key={f.properties.id}>
                <strong>Działka {f.properties.parcelNumber}</strong>
                <span>Obręb {f.properties.region || "nie podano"}</span>
                <code>{f.properties.id}</code>
                <SourceLink url={f.properties.sourceUrl}>
                  Źródło geometrii
                </SourceLink>
              </li>
            ))}
          </ul>
        </>
      )}
      {record.geometryNote && <p className="muted">{record.geometryNote}</p>}
      {record.parcelIds.length > features.length && (
        <details className="parcel-identifiers">
          <summary>Identyfikatory działek w danych</summary>
          <ul>
            {record.parcelIds.map((id, index) => (
              <li key={`${id}-${index}`}>
                <code>{id}</code>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="detail-source">
        <SourceLink url={record.sourceUrl} className="source-button">
          Wpis w źródle
        </SourceLink>
        <small>ID: {record.id}</small>
      </div>
    </section>
  );
}
function ResultRow({
  record,
  mapped,
  selected,
  onSelect,
}: {
  record: Permit;
  mapped: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        className={`result-row ${selected ? "selected" : ""}`}
        aria-pressed={selected}
        data-record-id={record.id}
        onClick={onSelect}
      >
        <div className="row-top">
          <span className={`badge ${semanticStatus(record)}`}>
            {kindLabels[record.kind]}
          </span>
          <time dateTime={recordDate(record) || undefined}>
            {formatDate(recordDate(record))}
          </time>
        </div>
        <h3>{record.title || "Bez tytułu"}</h3>
        <p className="row-place">
          {[record.locality, record.street].filter(Boolean).join(" · ") ||
            "Brak adresu w źródle"}
        </p>
        <div className="row-bottom">
          <span>
            Działki: {record.parcelNumbers.join(", ") || "nie podano"}
          </span>
          <span className={mapped ? "mapped-label" : "unmapped-label"}>
            <span aria-hidden="true">{mapped ? "◈" : "○"}</span>{" "}
            {mapped ? record.geometryStatus === "partial" ? "Częściowy obrys" : "Na mapie" : "Bez obrysu"}
          </span>
        </div>
      </button>
    </li>
  );
}
function downloadCsv(records: Permit[], parcels: ParcelCollection, coverage: string | undefined) {
  const blob = new Blob([exportCsv(records, parcels, coverage)], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "budowy-ozarow-wyniki.csv";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const initialData: LoadedData = {
  dataset: null,
  parcels: emptyParcels,
  metadata: null,
  warnings: [],
  error: null,
};
export default function App() {
  const [data, setData] = useState<LoadedData>(initialData);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [filters, setFilters] = useState<Filters>({ ...defaultFilters });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"map" | "list">("map");
  const [selectionDestination, setSelectionDestination] = useState<{ surface: "map" | "detail" }>({ surface: "detail" });
  const resultsRef = useRef<HTMLElement>(null);
  const mapPanelRef = useRef<HTMLElement>(null);
  const returnAfterClose = useRef<{
    view: "map" | "list";
    id: string;
  } | null>(null);
  const [focusResults, setFocusResults] = useState(0);
  useEffect(() => {
    if (focusResults) resultsRef.current?.focus();
  }, [focusResults]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setSelectedId(null);
    loadData(fetch, controller.signal).then((result) => {
      if (!controller.signal.aborted) {
        setData(result);
        setLoading(false);
      }
    });
    return () => controller.abort();
  }, [attempt]);
  const allRecords = data.dataset?.records || [];
  const filtered = useMemo(
    () => filterRecords(allRecords, filters, data.parcels),
    [data.dataset, filters, data.parcels],
  );
  const counts = useMemo(
    () => summarize(filtered, data.parcels),
    [filtered, data.parcels],
  );
  const allCounts = useMemo(
    () => summarize(allRecords, data.parcels),
    [data.dataset, data.parcels],
  );
  const selected = filtered.find((r) => r.id === selectedId) || null;
  useEffect(() => {
    if (selectedId && !filtered.some((r) => r.id === selectedId))
      setSelectedId(null);
  }, [filtered, selectedId]);
  useEffect(() => {
    const isMobile = typeof window.matchMedia === "function" && window.matchMedia("(max-width: 720px)").matches;
    if (selected && (!isMobile || mobileView === "list"))
      resultsRef.current?.querySelector<HTMLElement>(".result-row.selected")?.scrollIntoView?.({block:"nearest", behavior:"auto"});
  }, [selected?.id, mobileView]);
  useEffect(() => {
    if (
      selected &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(max-width: 720px)").matches
    ) {
      const target = selectionDestination.surface === "map"
        ? mapPanelRef.current
        : document.querySelector(".detail-panel");
      target?.scrollIntoView({ block: "start", behavior: "auto" });
    }
  }, [selected?.id, selectionDestination]);
  useEffect(() => {
    const destination = returnAfterClose.current;
    if (selected || !destination) return;
    returnAfterClose.current = null;
    const row = Array.from(
      resultsRef.current?.querySelectorAll<HTMLElement>(".result-row") || [],
    ).find(element => element.dataset.recordId === destination.id);
    const target = destination.view === "map"
      ? mapPanelRef.current
      : row || resultsRef.current;
    target?.scrollIntoView?.({ block: "start", behavior: "auto" });
  }, [selected?.id]);
  const closeDetail = () => {
    if (
      selected &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(max-width: 720px)").matches
    ) {
      returnAfterClose.current = { view: mobileView, id: selected.id };
    }
    setSelectedId(null);
  };
  const select = useCallback((id: string) => {
    setSelectionDestination({ surface: "detail" });
    setSelectedId(id);
  }, []);
  const selectFromList = (record: Permit) => {
    const showMap = typeof window.matchMedia === "function"
      && window.matchMedia("(max-width: 720px)").matches
      && getRecordParcels(record, data.parcels).length > 0;
    setSelectionDestination({ surface: showMap ? "map" : "detail" });
    if (showMap) setMobileView("map");
    setSelectedId(record.id);
  };
  const update = (key: keyof Filters, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }));
  const reset = () => {
    setFilters({ ...defaultFilters });
    setSelectedId(null);
  };
  const activeFilters = Object.entries(filters).filter(
    ([key, value]) =>
      key !== "sort" && value !== defaultFilters[key as keyof Filters],
  ).length;
  const options = useMemo(
    () => ({
      years: [
        ...new Set(
          allRecords
            .map((r) => recordDate(r)?.slice(0, 4))
            .filter((v): v is string => !!v),
        ),
      ]
        .sort()
        .reverse(),
      statuses: [
        ...new Set(allRecords.map((r) => r.status).filter(Boolean)),
      ].sort((a, b) => a.localeCompare(b, "pl")),
      localities: [
        ...new Set(allRecords.map((r) => r.locality).filter(Boolean)),
      ].sort((a, b) => a.localeCompare(b, "pl")),
    }),
    [data.dataset],
  );
  return (
    <>
      <a className="skip-link" href="#results" onClick={(event) => {
        event.preventDefault();
        setMobileView("list");
        setFocusResults(n => n + 1);
      }}>
        Przejdź do wyników
      </a>
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path d="M6 27V12l10-7 10 7v15M3 27h26M12 27V17h8v10M12 12h8" />
            </svg>
          </span>
          <div>
            <h1>
              Budowy <span>· Ożarów Mazowiecki</span>
            </h1>
            <p>Publiczne wpisy budowlane · miasto i gmina</p>
          </div>
        </div>
        <a className="header-link" href="#provenance" onClick={() => {
          const disclosure = document.querySelector<HTMLDetailsElement>("#provenance");
          if (disclosure) disclosure.open = true;
        }}>
          O danych <span aria-hidden="true">↗</span>
        </a>
      </header>
      <main>
        <section className="intro">
          <div>
            <h2>Co powstaje w Twojej okolicy?</h2>
          </div>
        </section>
        <section className="toolbar" aria-label="Wyszukiwanie i filtry">
          <div className="search-wrap">
            <label htmlFor="search">Szukaj w rejestrze</label>
            <div className="search-input">
              <span aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <circle cx="10" cy="10" r="6" />
                  <path d="m15 15 5 5" />
                </svg>
              </span>
              <input
                id="search"
                type="search"
                value={filters.query}
                onChange={(e) => update("query", e.target.value)}
                placeholder="Miejscowość, ulica, działka lub inwestycja"
              />
            </div>
          </div>
          <div className="filter-grid">
            <label>
              Okres
              <select value={filters.period} onChange={(e) => update("period", e.target.value)}>
                <option value="3months">Ostatnie 3 miesiące</option>
                <option value="all">Wszystkie daty</option>
              </select>
            </label>
            <label>
              Rodzaj wpisu
              <select
                value={filters.kind}
                onChange={(e) => update("kind", e.target.value)}
              >
                <option value="">Wszystkie rodzaje</option>
                <option value="application">Wnioski</option>
                <option value="decision">Decyzje</option>
                <option value="notification">Zgłoszenia</option>
              </select>
            </label>
            <label>
              Rok wpisu
              <select
                value={filters.year}
                onChange={(e) => update("year", e.target.value)}
              >
                <option value="">Wszystkie lata</option>
                {options.years.map((y) => (
                  <option key={y}>{y}</option>
                ))}
              </select>
            </label>
            <label>
              Status w źródle
              <select
                value={filters.status}
                onChange={(e) => update("status", e.target.value)}
              >
                <option value="">Wszystkie statusy</option>
                {options.statuses.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              Miejscowość
              <select
                value={filters.locality}
                onChange={(e) => update("locality", e.target.value)}
              >
                <option value="">Cała gmina</option>
                {options.localities.map((l) => (
                  <option key={l}>{l}</option>
                ))}
              </select>
            </label>
            <label>
              Położenie na mapie
              <select
                value={filters.mapping}
                onChange={(e) => update("mapping", e.target.value)}
              >
                <option value="all">Wszystkie wpisy</option>
                <option value="mapped">Z potwierdzonym obrysem</option>
                <option value="partial">Z częściowym dopasowaniem</option>
                <option value="unmapped">Bez potwierdzonego obrysu</option>
              </select>
            </label>
          </div>
          <div className="toolbar-bottom">
            <button
              className="text-button"
              aria-label="Wyczyść filtry"
              onClick={reset}
            >
              Wyczyść filtry
              {activeFilters > 0 && (
                <span
                  className="filter-number"
                  aria-label={`${activeFilters} aktywnych filtrów`}
                >
                  {activeFilters}
                </span>
              )}
            </button>
          </div>
        </section>
        <section
          className="summary-strip"
          aria-label="Liczby dla bieżących filtrów"
        >
          <div>
            <strong>{loading || data.error ? "—" : counts.total}</strong>
            <span>Wpisy w wynikach</span>
          </div>
          <div>
            <strong>{loading || data.error ? "—" : counts.mapped}</strong>
            <span>Z obrysem na mapie</span>
          </div>
          <div>
            <strong>{loading || data.error ? "—" : counts.unmapped}</strong>
            <span>Bez obrysu</span>
          </div>
          <div>
            <strong>{loading || data.error ? "—" : counts.parcelCount}</strong>
            <span>Unikalne działki na mapie</span>
          </div>
        </section>
        <div
          className="data-status"
          role="status"
          aria-live="polite"
          data-testid="data-status"
          data-loading={loading}
          data-record-count={loading ? "" : allCounts.total}
          data-filtered-count={loading ? "" : counts.total}
          data-mapped-count={loading ? "" : allCounts.mapped}
          data-parcel-count={loading ? "" : allCounts.parcelCount}
          data-state={loading ? "loading" : data.error ? "error" : "ready"}
        >
          {loading ? (
            <span>Ładowanie danych…</span>
          ) : data.error ? (
            <span>Dane nie zostały wczytane.</span>
          ) : (
            <>
              <span className="status-dot" aria-hidden="true" />
              <span>
                Wczytano {allCounts.total} wpisów · {allCounts.parcelCount}{" "}
                potwierdzonych działek
              </span>
              <span className="status-date">
                Import: {formatDate(data.dataset?.generatedAt)}
              </span>
            </>
          )}
        </div>
        {data.error && !loading && (
          <section className="error-state" role="alert">
            <h2>Dane są chwilowo niedostępne</h2>
            <p>{data.error}</p>
            <button
              className="primary-button"
              onClick={() => setAttempt((n) => n + 1)}
            >
              Spróbuj ponownie
            </button>
          </section>
        )}
        {!loading && data.warnings.length > 0 && (
          <details className="warnings">
            <summary>
              Ograniczenia zbioru ({data.warnings.length})
            </summary>
            <ul>
              {data.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </details>
        )}
        <div className="mobile-tabs" role="group" aria-label="Widok">
          <button
            aria-pressed={mobileView === "map"}
            onClick={() => setMobileView("map")}
          >
            Mapa
          </button>
          <button
            aria-pressed={mobileView === "list"}
            onClick={() => setMobileView("list")}
          >
            Lista{!loading && !data.error && ` (${counts.total})`}
          </button>
        </div>
        <div
          className={`workspace view-${mobileView} ${selected ? "has-detail" : ""}`}
        >
          <section
            className="map-panel"
            ref={mapPanelRef}
            aria-label="Mapa potwierdzonych działek"
          >
            <ParcelMap
              records={filtered}
              parcels={data.parcels}
              selectedId={selected?.id || null}
              onSelect={select}
              visible={mobileView === "map"}
            />
            <div className="map-caption">
              <strong>Tylko potwierdzone obrysy</strong>
              <span>
                {loading
                  ? "Czekamy na dane źródłowe"
                  : counts.mapped
                    ? "Wybierz działkę lub wpis na liście"
                    : "Brak obrysów dla bieżących wyników — sprawdź listę"}
              </span>
            </div>
          </section>
          <section
            id="results"
            ref={resultsRef}
            className="results-panel"
            aria-labelledby="results-title"
            tabIndex={-1}
          >
            <div className="results-top">
              <div>
                <h2 id="results-title">
                  Wpisy{!loading && !data.error && <span>{counts.total}</span>}
                </h2>
              </div>
              <button
                className="csv-button"
                disabled={loading || !!data.error || !filtered.length}
                onClick={() => downloadCsv(filtered, data.parcels, data.dataset?.source.coverage)}
              >
                Eksport CSV
              </button>
            </div>
            <label className="sort-control">
              Sortowanie
              <select
                value={filters.sort}
                onChange={(e) => update("sort", e.target.value)}
              >
                <option value="newest">Najnowsze najpierw</option>
                <option value="oldest">Najstarsze najpierw</option>
              </select>
            </label>
            {loading ? (
              <div className="empty-state">
                <span className="loading-ring" aria-hidden="true" />
                <h3>Wczytujemy publiczny rejestr</h3>
                <p>Dane pojawią się po odczytaniu plików źródłowych.</p>
              </div>
            ) : data.error ? (
              <div className="empty-state">
                <h3>Lista niedostępna</h3>
                <p>Nie można ustalić liczby wpisów. Spróbuj ponownie.</p>
              </div>
            ) : !filtered.length ? (
              <div className="empty-state">
                <span aria-hidden="true">⌕</span>
                <h3>
                  {allRecords.length
                    ? "Brak wyników dla tych filtrów."
                    : "Brak wpisów w załadowanym zbiorze."}
                </h3>
                <p>
                  {allRecords.length
                    ? "Zmień zapytanie lub wyczyść filtry."
                    : "To nie jest potwierdzenie braku inwestycji w gminie. Sprawdź zakres i źródło danych poniżej."}
                </p>
              </div>
            ) : (
              <ul className="result-list">
                {filtered.map((r) => (
                  <ResultRow
                    key={r.id}
                    record={r}
                    mapped={getRecordParcels(r, data.parcels).length > 0}
                    selected={selected?.id === r.id}
                    onSelect={() => selectFromList(r)}
                  />
                ))}
              </ul>
            )}
          </section>
          {selected && (
            <Detail
              record={selected}
              parcels={data.parcels}
              onClose={closeDetail}
            />
          )}
        </div>
        <details className="data-disclosure" id="provenance">
          <summary>O danych</summary>
          <section
            className="provenance"
            aria-labelledby="provenance-title"
          >
            <div>
              <h2 id="provenance-title">Jak czytać te dane?</h2>
              <p>Wpis w rejestrze nie oznacza zatwierdzenia ani rozpoczęcia budowy.</p>
              <p>Okres, rok i kolejność: data decyzji, a przy jej braku data wniosku. Ostatnie 3 miesiące liczymy od dzisiejszej daty w Polsce.</p>
              <p>
                Mapa przedstawia działki powiązane z wpisami, nie obrysy budynków
                ani postęp prac. Brak działki na mapie oznacza brak potwierdzonej
                geometrii, a nie brak inwestycji.
              </p>
              <p>
                Kolor opisuje rodzaj lub wynik wpisu w źródle. Przy kilku różnych
                wpisach na jednej działce kolor jest neutralny; szczegóły są
                dostępne po jej wybraniu.
              </p>
            </div>
            <div className="source-info">
              {!loading && !data.error && allRecords.length > 0 && !allRecords.some(r => r.kind === "application") && (
                <p className="coverage-note">
                  W tym zbiorze nie ma samodzielnych wniosków. Nie oznacza to braku nierozpatrzonych wniosków w gminie — eksport CSV nie gwarantuje ich kompletności.
                </p>
              )}
              <h3>Zakres załadowanego zbioru</h3>
              <p>
                {data.dataset?.source.coverage ||
                  "Zakres danych nie jest jeszcze dostępny."}
              </p>
              {data.dataset && (
                <>
                  <SourceLink url={data.dataset.source.url}>
                    {data.dataset.source.name}
                  </SourceLink>
                  <p className="muted">
                    Pobranie źródła:{" "}
                    {formatDate(data.dataset.source.downloadedAt)} · Wygenerowanie
                    zbioru: {formatDate(data.dataset.generatedAt)}
                  </p>
                </>
              )}
              {data.metadata?.sources?.map((s, i) => (
                <div key={i}>
                  <SourceLink url={s.url}>{s.name}</SourceLink>
                </div>
              ))}
              <p className="muted">
                Dane inwestorów i projektantów są wyłączone z publicznego zbioru.
                CSV nie gwarantuje kompletności nierozpatrzonych wniosków.
              </p>
              <p className="muted">
                CSV zawiera bieżące wyniki filtrów. Statusy zachowujemy zgodnie ze
                źródłem; wartości chronimy przed interpretacją jako formuły
                arkusza.
              </p>
            </div>
          </section>
        </details>
      </main>
      <footer>
        Budowy · Ożarów Mazowiecki
        <span>Informacja pomocnicza — rozstrzygają dokumenty źródłowe.</span>
      </footer>
    </>
  );
}
