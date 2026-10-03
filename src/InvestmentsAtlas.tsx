import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import InvestmentsMap from "./InvestmentsMap";
import {
  accuracyLabels,
  filterInvestments,
  investmentDefaults,
  investmentsCsv,
  investmentTypes,
  investmentUrl,
  investorLabels,
  loadInvestments,
  type InvestmentDataset,
  type InvestmentFilters,
  type InvestmentRecord,
  type InvestmentSource,
} from "./investments";
import { formatDate } from "./model";
function Link({ url, children }: { url: string; children: React.ReactNode }) {
  const href = investmentUrl(url);
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <span aria-hidden="true"> ↗</span>
    </a>
  ) : (
    <span className="muted">Link niedostępny</span>
  );
}
const freshness: Record<InvestmentSource["status"], string> = {
  fresh: "Pobrane ze źródła",
  retained: "Zachowany poprzedni odczyt",
  static: "Statyczny odczyt / dokument",
  unavailable: "Źródło niedostępne",
};
const costKinds: Record<string, string> = {
  reported: "Kwota podana w źródle",
  "annual-plan": "Plan roczny",
  "total-outlay": "Łączne nakłady",
  "annual-limit": "Limit roczny",
  "tender-financing": "Finansowanie zamówienia",
  offer: "Oferta",
  contract: "Umowa",
  actual: "Wykonanie",
  "project-total": "Koszt całego projektu",
  "eu-contribution": "Wkład UE",
  eligible: "Koszty kwalifikowalne",
  "proposal-estimate": "Szacunek propozycji",
};
const costScope = {
  local: "Zakres lokalny",
  "multi-municipality": "Cały projekt wielogminny — nie koszt samej gminy",
  unknown: "Zakres kosztu nieustalony",
};
function Detail({
  record: r,
  source,
  onClose,
  onRelated,
}: {
  record: InvestmentRecord;
  source?: InvestmentSource;
  onClose: () => void;
  onRelated: (id: string) => void;
}) {
  return (
    <section
      className="detail-panel"
      tabIndex={-1}
      aria-labelledby="investment-detail-title"
      data-selected-id={r.id}
    >
      <div className="detail-top">
        <div>
          <span className="eyebrow">REKORD ŹRÓDŁOWY</span>
          <h2 id="investment-detail-title">Szczegóły inwestycji</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Zamknij szczegóły inwestycji"
        >
          ×
        </button>
      </div>
      <div className="record-tags">
        <span className="badge unknown">{investmentTypes[r.recordType]}</span>
        <span className="badge neutral">
          {r.status || "Nie podano statusu"}
        </span>
      </div>
      <h3>{r.title || "Bez tytułu"}</h3>
      <p className="semantic-note">
        Rekord źródłowy nie jest potwierdzeniem rozpoczęcia budowy. Status
        dotyczy daty podanej w źródle, nie daty pobrania.
      </p>
      <div className="detail-source">
        <Link url={r.sourceUrl}>Rekord w źródle</Link>
        <small>
          ID: {r.id} · ID źródłowe: {r.sourceRecordId}
        </small>
      </div>
      {!!r.warnings.length && (
        <div className="investment-alert" role="alert">
          <strong>Ograniczenia rekordu</strong>
          <ul>
            {r.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      {r.summary && <p className="description">{r.summary}</p>}
      <dl className="detail-grid">
        {[
          ["Rodzaj", investmentTypes[r.recordType]],
          [
            "Inwestor",
            `${investorLabels[r.investor]}${r.investorName ? ` · ${r.investorName}` : ""}`,
          ],
          ["Kategoria", r.category || "Brak danych"],
          ["Status", r.status || "Brak danych"],
          ["Status na dzień", formatDate(r.statusAsOf)],
          ["Lata", r.years.join(", ") || "Nie podano"],
          ["Miejscowość", r.locality || "Nie podano"],
          ["Adres", r.address || "Nie podano"],
          ["Edycja w źródle", r.sourceUpdatedAt || "Nie podano"],
          ["Pobranie rekordu", r.fetchedAt],
          ["Źródło", source?.name || r.sourceId],
          [
            "Odczyt źródła",
            source ? freshness[source.status] : "Brak metadanych",
          ],
        ].map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <h4>Koszty z dokumentów</h4>
      <p className="geometry-note">
        Kwot nie sumujemy: typy kosztów i różne źródła mogą dotyczyć tej samej
        inwestycji.
      </p>
      {r.costs.length ? (
        <ul className="investment-facts">
          {r.costs.map((c, i) => (
            <li key={i}>
              <strong>
                {c.amount === null
                  ? "Kwota niepodana"
                  : `${c.amount.toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ${c.currency}`}
              </strong>
              <span>
                {costKinds[c.kind] || c.kind} · {c.label}
              </span>
              <span>
                {c.year === null ? "Bez określonego roku" : `Rok ${c.year}`} ·{" "}
                {costScope[c.scope]}
              </span>
              <Link url={c.sourceUrl}>Dokument kosztu</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="geometry-note">
          Brak potwierdzonej kwoty w tym rekordzie.
        </p>
      )}
      <h4>Daty i zdarzenia</h4>
      {!r.dates.length && !r.events.length && (
        <p className="geometry-note">Nie podano dat ani zdarzeń.</p>
      )}
      <ul className="investment-facts">
        {r.dates.map((d, i) => (
          <li key={`d${i}`}>
            <strong>{d.label || d.kind}</strong>
            <span>
              {formatDate(d.date)} · {d.kind}
            </span>
            <Link url={d.sourceUrl}>Źródło daty</Link>
          </li>
        ))}
        {r.events.map((e) => (
          <li key={e.id}>
            <strong>{e.title}</strong>
            <span>
              {e.date ? formatDate(e.date) : "Data niepodana"} · {e.id}
            </span>
            <Link url={e.sourceUrl}>Dokument zdarzenia</Link>
          </li>
        ))}
      </ul>
      {!!r.facts.length && (
        <>
          <h4>Fakty i numery spraw</h4>
          <dl className="investment-facts">
            {r.facts.map((f, i) => (
              <div key={i}>
                <dt>{f.label}</dt>
                <dd>{f.value}</dd>
                <Link url={f.sourceUrl}>Źródło faktu</Link>
              </div>
            ))}
          </dl>
        </>
      )}
      <h4>Położenie i dokładność</h4>
      <p className="parcel-numbers">
        Identyfikatory działek: {r.parcelIds.join(", ") || "Nie podano"}
      </p>
      {r.geometries.length ? (
        <ul className="investment-facts">
          {r.geometries.map((g) => (
            <li key={g.properties.id}>
              <strong>{accuracyLabels[g.properties.accuracy]}</strong>
              <span>
                {g.geometry.type} · {g.properties.id}
              </span>
              {g.properties.parcelId && <code>{g.properties.parcelId}</code>}
              <p>{g.properties.note || "Brak dodatkowej notatki."}</p>
              <small>
                Pobrano: {g.properties.fetchedAt} · Edycja:{" "}
                {g.properties.sourceUpdatedAt || "nie podano"}
              </small>
              <Link url={g.properties.sourceUrl}>Źródło geometrii</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="geometry-note">
          Brak potwierdzonej geometrii — rekord pozostaje dostępny na liście.
        </p>
      )}
      {!!r.relatedIds.length && (
        <>
          <h4>Udokumentowane powiązania</h4>
          <ul className="investment-facts">
            {r.relatedIds.map((id) => (
              <li key={id}>
                <button
                  className="related-button"
                  onClick={() => onRelated(id)}
                >
                  {id}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
function download(records: InvestmentRecord[]) {
  const blob = new Blob([investmentsCsv(records)], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = "radar-ozarow-inwestycje.csv";
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const mobile = () =>
  typeof window.matchMedia === "function" &&
  window.matchMedia("(max-width: 720px)").matches;
export default function InvestmentsAtlas({ active }: { active: boolean }) {
  const [data, setData] = useState<InvestmentDataset | null>(null),
    [error, setError] = useState<string | null>(null),
    [loading, setLoading] = useState(true),
    [attempt, setAttempt] = useState(0);
  const [filters, setFilters] = useState<InvestmentFilters>({
      ...investmentDefaults,
    }),
    [selectedId, setSelectedId] = useState<string | null>(null),
    [mobileView, setMobileView] = useState<"map" | "list">("map");
  const [destination, setDestination] = useState<{
    surface: "map" | "detail";
    token: number;
  }>({ surface: "detail", token: 0 });
  const root = useRef<HTMLElement>(null),
    mapPanel = useRef<HTMLElement>(null),
    results = useRef<HTMLElement>(null),
    origin = useRef<"map" | "list">("list"),
    restore = useRef<{ surface: "map" | "list"; id: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadInvestments(fetch, controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      setData(result.dataset);
      setError(result.error);
      setLoading(false);
    });
    return () => controller.abort();
  }, [attempt]);
  const all = data?.records || [];
  const filtered = useMemo(
    () => filterInvestments(all, filters),
    [data, filters],
  );
  const selected = filtered.find((r) => r.id === selectedId) || null;
  const mapped = filtered.filter((r) => r.geometries.length > 0).length;
  useEffect(() => {
    if (selectedId && !selected) setSelectedId(null);
  }, [selectedId, selected]);
  const update = (key: keyof InvestmentFilters, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }));
  const select = useCallback(
    (id: string, from: "map" | "list" = "map") => {
      origin.current = from;
      const r = filtered.find((row) => row.id === id);
      const showMap = from === "list" && mobile() && !!r?.geometries.length;
      if (showMap) setMobileView("map");
      setSelectedId(id);
      setDestination((prev) => ({
        surface: showMap ? "map" : "detail",
        token: prev.token + 1,
      }));
    },
    [filtered],
  );
  const selectMap = useCallback((id: string) => select(id, "map"), [select]);
  useEffect(() => {
    if (!selected || !active) return;
    if (mobile()) {
      const target =
        destination.surface === "map"
          ? mapPanel.current
          : root.current?.querySelector<HTMLElement>(".detail-panel");
      target?.scrollIntoView?.({ block: "start", behavior: "auto" });
      (destination.surface === "map"
        ? mapPanel.current?.querySelector<HTMLElement>(".map-overview")
        : target
      )?.focus({ preventScroll: true });
    } else
      results.current
        ?.querySelector<HTMLElement>(".result-row.selected")
        ?.scrollIntoView?.({ block: "nearest", behavior: "auto" });
  }, [selected?.id, destination, active]);
  const close = useCallback(() => {
    if (!selected) return;
    restore.current = {
      surface: mobile() ? mobileView : origin.current,
      id: selected.id,
    };
    setSelectedId(null);
  }, [selected, mobileView]);
  useEffect(() => {
    if (selected || !restore.current || !active) return;
    const target = restore.current;
    restore.current = null;
    const row = Array.from(
      results.current?.querySelectorAll<HTMLElement>(".result-row") || [],
    ).find((e) => e.dataset.recordId === target.id);
    const surface =
      target.surface === "map" ? mapPanel.current : row || results.current;
    surface?.scrollIntoView?.({ block: "start", behavior: "auto" });
    (target.surface === "map"
      ? mapPanel.current?.querySelector<HTMLElement>(".map-overview")
      : surface
    )?.focus({ preventScroll: true });
  }, [selected, active]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (active && selected && e.key === "Escape") {
        e.preventDefault();
        close();
      }
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [active, selected, close]);
  const values = (key: "category" | "status") =>
    [...new Set(all.map((r) => r[key]).filter(Boolean))].sort((a, b) =>
      a.localeCompare(b, "pl"),
    );
  const years = [...new Set(all.flatMap((r) => r.years))].sort((a, b) => b - a);
  const warnings = [
    ...(data?.warnings || []),
    ...(data?.sources.flatMap((s) => [
      ...(s.status === "retained" || s.status === "unavailable"
        ? [`${s.name}: ${freshness[s.status]}`]
        : []),
      ...s.warnings.map((w) => `${s.name}: ${w}`),
    ]) || []),
  ];
  const reset = () => {
    setFilters({ ...investmentDefaults });
    setSelectedId(null);
  };
  const activeFilters = Object.entries(filters).filter(
    ([k, v]) =>
      k !== "sort" && v !== investmentDefaults[k as keyof InvestmentFilters],
  ).length;
  return (
    <main className="investment-atlas" ref={root}>
      <a
        className="skip-link"
        href="#investment-results"
        onClick={(e) => {
          e.preventDefault();
          setMobileView("list");
          requestAnimationFrame(() => results.current?.focus());
        }}
      >
        Przejdź do inwestycji
      </a>
      <div className="source-ribbon">
        <div className="source-identity">
          <span className="source-kicker">DANE PUBLICZNE</span>
          <span>Inwestycje · niezależne źródła</span>
        </div>
        <div
          className="data-status"
          data-testid="investments-status"
          role="status"
          aria-live="polite"
          data-state={loading ? "loading" : error ? "error" : "ready"}
          data-record-count={loading || error ? "" : all.length}
          data-filtered-count={loading || error ? "" : filtered.length}
          data-mapped-count={loading || error ? "" : mapped}
        >
          {loading
            ? "Ładowanie inwestycji…"
            : error
              ? "Dane inwestycji niewczytane."
              : `Wczytano ${all.length} rekordów źródłowych`}{" "}
          {!loading && !error && (
            <span className="status-date">
              Import: {formatDate(data?.generatedAt)}
            </span>
          )}
        </div>
        {!loading && error && (
          <section className="error-state" role="alert">
            <h2>Inwestycje są chwilowo niedostępne</h2>
            <p>{error} Pozwolenia działają niezależnie.</p>
            <button
              className="primary-button"
              onClick={() => setAttempt((n) => n + 1)}
            >
              Spróbuj ponownie — inwestycje
            </button>
          </section>
        )}
      </div>
      {!!warnings.length && !loading && (
        <section className="investment-alert" role="alert">
          <strong>Ograniczenia aktualności i integralności danych</strong>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}
      <div
        className={`workspace investment-workspace view-${mobileView} ${selected ? "has-detail" : ""}`}
      >
        <aside className="explore-rail" aria-label="Eksploracja inwestycji">
          <div className="explore-heading">
            <span className="eyebrow">EKSPLORUJ / INWESTYCJE</span>
            <h2>Znajdź w okolicy</h2>
          </div>
          <section className="toolbar" aria-label="Filtry inwestycji">
            <div className="search-wrap">
              <label htmlFor="investment-search">Szukaj inwestycji</label>
              <div className="search-input">
                <input
                  id="investment-search"
                  type="search"
                  value={filters.query}
                  onChange={(e) => update("query", e.target.value)}
                  placeholder="Nazwa, adres, działka, numer sprawy"
                />
              </div>
            </div>
            <div className="period-tools">
              <label>
                Rok inwestycji
                <select
                  value={filters.year}
                  onChange={(e) => update("year", e.target.value)}
                >
                  <option value="">Wszystkie lata</option>
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
              <details className="advanced-filters">
                <summary>
                  Filtry{" "}
                  <span className="filter-count">{activeFilters || "+"}</span>
                </summary>
                <div className="filter-grid">
                  <label>
                    Źródło inwestycji
                    <select
                      value={filters.source}
                      onChange={(e) => update("source", e.target.value)}
                    >
                      <option value="">Wszystkie źródła</option>
                      {data?.sources.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Inwestor
                    <select
                      value={filters.investor}
                      onChange={(e) => update("investor", e.target.value)}
                    >
                      <option value="">Wszyscy inwestorzy</option>
                      {Object.entries(investorLabels).map(([id, label]) => (
                        <option key={id} value={id}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Kategoria inwestycji
                    <select
                      value={filters.category}
                      onChange={(e) => update("category", e.target.value)}
                    >
                      <option value="">Wszystkie kategorie</option>
                      {values("category").map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Status inwestycji
                    <select
                      value={filters.status}
                      onChange={(e) => update("status", e.target.value)}
                    >
                      <option value="">Wszystkie statusy</option>
                      {values("status").map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Położenie inwestycji
                    <select
                      value={filters.mapping}
                      onChange={(e) => update("mapping", e.target.value)}
                    >
                      <option value="all">Wszystkie rekordy</option>
                      <option value="mapped">Z geometrią ze źródła</option>
                      <option value="unmapped">
                        Bez potwierdzonej geometrii
                      </option>
                    </select>
                  </label>
                </div>
              </details>
            </div>
            <div className="toolbar-bottom">
              <button
                className="text-button"
                aria-label="Wyczyść filtry inwestycji"
                onClick={reset}
              >
                Wyczyść filtry
                {activeFilters > 0 && (
                  <span className="filter-number">{activeFilters}</span>
                )}
              </button>
            </div>
          </section>
          <section
            className="summary-strip investment-summary"
            aria-label="Liczby inwestycji dla bieżących filtrów"
          >
            <div>
              <strong>{loading || error ? "—" : filtered.length}</strong>
              <span>rekordy źródłowe</span>
            </div>
            <div>
              <strong>{loading || error ? "—" : mapped}</strong>
              <span>Na mapie</span>
            </div>
            <div>
              <strong>
                {loading || error ? "—" : filtered.length - mapped}
              </strong>
              <span>Bez geometrii</span>
            </div>
          </section>
          <div
            className="mobile-tabs"
            role="group"
            aria-label="Widok inwestycji"
          >
            <button
              aria-pressed={mobileView === "map"}
              onClick={() => setMobileView("map")}
            >
              Mapa inwestycji
            </button>
            <button
              aria-pressed={mobileView === "list"}
              onClick={() => setMobileView("list")}
            >
              Lista inwestycji{!loading && !error && ` (${filtered.length})`}
            </button>
          </div>
          <section
            id="investment-results"
            ref={results}
            className="results-panel"
            aria-labelledby="investment-results-title"
            tabIndex={-1}
          >
            <div className="results-top">
              <h2 id="investment-results-title">
                Rekordy <span>{loading || error ? "—" : filtered.length}</span>
              </h2>
              <button
                className="csv-button"
                aria-label="Eksport CSV inwestycji"
                disabled={loading || !!error || !filtered.length}
                onClick={() => download(filtered)}
              >
                Eksport CSV
              </button>
            </div>
            <label className="sort-control">
              Sortowanie inwestycji
              <select
                value={filters.sort}
                onChange={(e) => update("sort", e.target.value)}
              >
                <option value="newest">Najnowsza data źródłowa / rok</option>
                <option value="oldest">Najstarsza data źródłowa / rok</option>
                <option value="title">Nazwa A–Z</option>
              </select>
            </label>
            {loading ? (
              <div className="empty-state">
                <span className="loading-ring" aria-hidden="true" />
                <h3>Wczytujemy inwestycje</h3>
              </div>
            ) : error ? (
              <div className="empty-state">
                <h3>Lista inwestycji niedostępna</h3>
                <p>Nie można ustalić liczby rekordów. Spróbuj ponownie.</p>
              </div>
            ) : !filtered.length ? (
              <div className="empty-state">
                <h3>
                  {all.length
                    ? "Brak wyników dla tych filtrów."
                    : "Brak rekordów w załadowanym zbiorze."}
                </h3>
                <p>
                  {all.length
                    ? "Zmień zapytanie lub wyczyść filtry."
                    : "To nie jest potwierdzenie braku inwestycji w gminie. Sprawdź pokrycie źródeł."}
                </p>
              </div>
            ) : (
              <ul className="result-list">
                {filtered.map((r) => (
                  <li key={r.id}>
                    <button
                      className={`result-row ${selected?.id === r.id ? "selected" : ""}`}
                      data-record-id={r.id}
                      aria-pressed={selected?.id === r.id}
                      onClick={() => select(r.id, "list")}
                    >
                      <div className="row-top">
                        <span className="badge unknown">
                          {investmentTypes[r.recordType]}
                        </span>
                        <span className="row-years">
                          {r.years.join(", ") || "Rok niepodany"}
                        </span>
                      </div>
                      <h3>{r.title || "Bez tytułu"}</h3>
                      <p className="row-place">
                        {[r.locality, r.address].filter(Boolean).join(" · ") ||
                          "Brak adresu w źródle"}
                      </p>
                      <p className="row-place">
                        {data?.sources.find((s) => s.id === r.sourceId)?.name} ·{" "}
                        {r.status || "Brak statusu"}
                      </p>
                      <div className="row-bottom">
                        <span>{investorLabels[r.investor]}</span>
                        <span
                          className={
                            r.geometries.length
                              ? "mapped-label"
                              : "unmapped-label"
                          }
                        >
                          {r.geometries.length
                            ? `${r.geometries.length} lokalizacje`
                            : "Bez geometrii"}
                        </span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
        <section
          ref={mapPanel}
          className="map-panel"
          aria-label="Mapa inwestycji"
        >
          <div className="map-heading">
            <div>
              <span className="eyebrow">OBSZAR EKSPLORACJI</span>
              <h2>Mapa inwestycji</h2>
            </div>
            <span className="map-region">Ożarów Mazowiecki · gmina</span>
          </div>
          <InvestmentsMap
            records={filtered}
            selectedId={selected?.id || null}
            selectionToken={destination.token}
            onSelect={selectMap}
            visible={mobileView === "map"}
            active={active}
          />
          <div className="map-caption">
            <div>
              <strong>Punkty, działki i trasy ze źródeł</strong>
              <p className="semantic-inline">
                Geometria nie potwierdza rozpoczęcia prac.
              </p>
            </div>
            <span>
              {mapped
                ? "Wybierz geometrię lub rekord na liście"
                : "Brak geometrii w wynikach — sprawdź listę"}
            </span>
          </div>
        </section>
        {selected ? (
          <Detail
            record={selected}
            source={data?.sources.find((s) => s.id === selected.sourceId)}
            onClose={close}
            onRelated={(id) => {
              const record = all.find((r) => r.id === id);
              if (!record) return;
              setFilters({ ...investmentDefaults });
              origin.current = "map";
              setSelectedId(id);
              setDestination((prev) => ({
                surface: "detail",
                token: prev.token + 1,
              }));
            }}
          />
        ) : (
          <aside className="inspector-idle" aria-label="Inspektor inwestycji">
            <span className="eyebrow">INSPEKTOR / SZCZEGÓŁY</span>
            <h2>Wybierz rekord lub lokalizację</h2>
            <p>Źródłowy status, daty, dokumenty i koszty.</p>
            <small>
              Rekordy źródłowe nie oznaczają unikalnych budów. Działka nie
              oznacza obrysu projektu.
            </small>
          </aside>
        )}
      </div>
      <details className="data-disclosure" id="investment-provenance">
        <summary>O danych inwestycji i pokryciu źródeł</summary>
        <section className="provenance" aria-label="Pokrycie źródeł inwestycji">
          <div>
            <h2>Jak czytać inwestycje?</h2>
            <p>
              Liczymy rekordy źródłowe, nie unikalne budowy. Różne dokumenty
              mogą opisywać to samo przedsięwzięcie. Łączymy wyłącznie
              udokumentowane powiązania.
            </p>
            <p>
              Wszystkie lata są domyślnie dostępne. Sortujemy po dacie statusu,
              następnie edycji źródła lub roku. Pobranie nie zastępuje daty
              statusu.
            </p>
            <p>
              Punkt, działka, obrys projektu i trasa mają różną dokładność. Brak
              geometrii nie oznacza braku inwestycji.
            </p>
            <p>
              Budżet, propozycja BO, grant, zamówienie i sprawa środowiskowa nie
              potwierdzają rozpoczęcia prac. Koszt całego projektu wielogminnego
              nie jest kosztem samej gminy.
            </p>
            <p>
              Inwestycje i GUNB są niezależnymi zbiorami. Import inwestycji:{" "}
              {data?.generatedAt || "Nie wczytano"}.
            </p>
            <p>
              CSV zawiera dokładnie bieżące wyniki i kolejność. Pola chronimy
              przed formułami arkusza; nie sumujemy kwot.
            </p>
          </div>
          <div className="source-info">
            {data?.sources.map((s) => (
              <article className="investment-source" key={s.id}>
                <h3>
                  <Link url={s.url}>{s.name}</Link>
                </h3>
                <p>
                  {freshness[s.status]} · {s.recordCount} rekordów źródłowych
                </p>
                <p>{s.coverage}</p>
                <p className="muted">
                  Pobranie źródła: {s.fetchedAt || "Nie podano"} · Edycja
                  źródła: {s.sourceUpdatedAt || "Nie podano"}
                </p>
                <p className="muted">{s.reuse}</p>
                {s.warnings.map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
              </article>
            ))}
          </div>
        </section>
      </details>
    </main>
  );
}
