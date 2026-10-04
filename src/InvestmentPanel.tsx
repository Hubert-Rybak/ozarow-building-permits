import { useEffect, useMemo, useState } from "react";
import {
  accuracyLabels,
  categoryGroup,
  filterInvestments,
  investmentDefaults,
  isTechnicalFact,
  linkIndex,
  linkedRecords,
  placeHistory,
  investmentsCsv,
  investmentStage,
  investmentTypes,
  investorLabels,
  loadInvestments,
  mapStage,
  mapStageColors,
  mapStageLabels,
  recordMapStage,
  similarRecords,
  type InvestmentDataset,
  type InvestmentFilters,
  type InvestmentLink,
  type InvestmentRecord,
  type InvestmentSource,
  type MapStage,
  type Stage,
} from "./investments";
import { daysBetween, formatDate, formatDateTime, kindLabels, recordDate } from "./model";
import { readAndRemember, type SeenState } from "./seen";
import { BackButton, Chip, MapButton, ChipSelect, ExternalLink, MoreButton, PAGE, SearchBox, ShareButton } from "./ui";
import type { Permit } from "./types";
import { formatDistance } from "./geo";

export const freshness: Record<InvestmentSource["status"], string> = {
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
const dateKinds: Record<string, string> = {
  SubmissionOffersDate: "Termin składania ofert",
  OpenOffersDate: "Otwarcie ofert",
  "procurement-initiation": "Wszczęcie postępowania",
};
function dateLabel(kind: string, label: string) {
  return dateKinds[kind] || label.replace(/\s*\(ważny termin\)$/, "") || "Data";
}

export function useInvestments() {
  const [data, setData] = useState<InvestmentDataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [filters, setFilters] = useState<InvestmentFilters>({ ...investmentDefaults });
  const [seen, setSeen] = useState<SeenState>({ newIds: new Set(), lastVisit: null });
  const [onlyNew, setOnlyNew] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadInvestments(fetch, controller.signal).then(result => {
      if (controller.signal.aborted) return;
      setData(result.dataset);
      setError(result.error);
      setLoading(false);
      if (result.dataset) setSeen(readAndRemember("investments", result.dataset.records.map(r => r.id)));
    });
    return () => controller.abort();
  }, [attempt]);
  const all = data?.records || [];
  const base = useMemo(() => filterInvestments(all, filters), [data, filters]);
  const filtered = useMemo(() => onlyNew ? base.filter(r => seen.newIds.has(r.id)) : base, [base, onlyNew, seen]);
  const mapped = filtered.filter(r => r.geometries.length > 0).length;
  return {
    data, error, loading, filters, setFilters, seen, onlyNew, setOnlyNew, all, filtered, mapped,
    retry: () => setAttempt(n => n + 1),
  };
}
export type InvestmentState = ReturnType<typeof useInvestments>;

function download(records: InvestmentRecord[]) {
  const blob = new Blob([investmentsCsv(records)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob), a = document.createElement("a");
  a.href = url;
  a.download = "radar-ozarow-inwestycje.csv";
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function money(amount: number | null, currency: string) {
  return amount === null ? "Kwota niepodana" : `${amount.toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ${currency === "PLN" ? "zł" : currency}`;
}

const steps: { stage: Stage; label: string }[] = [
  { stage: "plan", label: "Plan" },
  { stage: "preparation", label: "Przygotowanie" },
  { stage: "tender", label: "Przetarg / umowa" },
  { stage: "progress", label: "Realizacja" },
  { stage: "done", label: "Ukończone" },
];

function StageTracker({ record }: { record: InvestmentRecord }) {
  const stage = investmentStage(record.status);
  const color = mapStageColors[mapStage(stage)];
  return (
    <section className="stage-box" aria-label="Etap">
      {stage !== "other" && (
        <ol className="stage-steps">
          {steps.map(step => (
            <li key={step.stage} className={step.stage === stage ? "current" : ""} aria-current={step.stage === stage ? "step" : undefined}
              style={step.stage === stage ? { "--stage": color } as React.CSSProperties : undefined}>
              <span className="stage-dot" aria-hidden="true" />
              <span>{step.label}</span>
            </li>
          ))}
        </ol>
      )}
      <p>Według tego rekordu: <strong>{record.status || "brak statusu"}</strong>{record.statusAsOf ? ` (stan z ${formatDate(record.statusAsOf)})` : ""}. Rekord źródłowy nie potwierdza rozpoczęcia robót.</p>
    </section>
  );
}

function relative(date: string, today: string) {
  const days = daysBetween(today, date);
  if (days > 1) return `za ${days} dni`;
  if (days === 1) return "jutro";
  if (days === 0) return "dziś";
  return null;
}

const linkKinds = {
  documented: { label: "Udokumentowane", hint: "Oficjalny dokument wskazuje oba wpisy." },
  probable: { label: "Prawdopodobne", hint: "Brak dokumentu łączącego; zbieżne miejsce, rok i opis." },
};

function keyCosts(r: InvestmentRecord) {
  // The amount that says the most: chosen offer, then plan/limit, then anything reported.
  for (const kinds of [["offer", "contract", "actual"], ["annual-plan", "total-outlay"], ["tender-financing", "reported", "project-total", "proposal-estimate"]]) {
    const found = r.costs.filter(c => kinds.includes(c.kind) && c.amount);
    if (found.length) return found.slice(0, 3);
  }
  return [];
}

function RelatedSources({ entries, onPick }: { entries: ReturnType<typeof linkedRecords>; onPick: (id: string) => void }) {
  return (
    <>
      <h3 className="section-title">Powiązane źródła</h3>
      <p className="muted">Każdy wpis pochodzi z innego źródła. Kwot nie sumujemy — mogą opisywać plan, przetarg i umowę tej samej inwestycji.</p>
      <ul className="linked-list">
        {entries.map(e => (
          <li key={e.record.id} className={`linked-item ${e.kind}`}>
            <button type="button" className="linked-main" onClick={() => onPick(e.record.id)}>
              <span className={`link-badge ${e.kind}`} title={linkKinds[e.kind].hint}>{linkKinds[e.kind].label}</span>
              <strong>{e.record.title}</strong>
              <span className="muted">{investmentTypes[e.record.recordType]} · {e.record.years.join(", ") || "rok niepodany"} · {e.record.status}</span>
              {keyCosts(e.record).map((c, i) => (
                <span key={i} className="linked-cost"><strong>{money(c.amount, c.currency)}</strong> {c.kind === "offer" ? c.label : costKinds[c.kind] || c.kind}</span>
              ))}
            </button>
            <p className="linked-basis">
              {e.via && <>Przez: „{e.via.title}”. </>}{e.basis}{" "}
              {e.sourceUrl && <ExternalLink url={e.sourceUrl}>Dokument powiązania</ExternalLink>}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}

export function InvestmentDetail({ record: r, source, all, links = [], nearbyPermits, onClose, onBackToMap, onPick, share, isNew }: {
  record: InvestmentRecord;
  source?: InvestmentSource;
  all: InvestmentRecord[];
  links?: InvestmentLink[];
  nearbyPermits: { item: Permit; meters: number }[];
  onClose: () => void;
  onBackToMap?: () => void;
  onPick: (layer: "permits" | "investments", id: string) => void;
  share: string;
  isNew: boolean;
}) {
  const index = useMemo(() => linkIndex(links, all), [links, all]);
  const byId = useMemo(() => new Map(all.map(x => [x.id, x])), [all]);
  const related = useMemo(() => linkedRecords(r, index, byId), [r, index, byId]);
  const history = useMemo(() => placeHistory(r, all), [r, all]);
  const similar = useMemo(() => {
    const shown = new Set([...related.map(e => e.record.id), ...history.map(h => h.record.id)]);
    return similarRecords(r, all.filter(x => !shown.has(x.id)));
  }, [r, all, related, history]);
  const technical = r.facts.filter(isTechnicalFact);
  // A fact that only repeats the record's own link adds nothing next to "Rekord w źródle".
  const documents = r.facts.filter(f => !isTechnicalFact(f) && !(f.sourceUrl === r.sourceUrl && f.value === r.sourceUrl));
  const today = new Date().toISOString().slice(0, 10);
  const dates = [
    ...r.dates.map(d => ({ key: `d-${d.kind}-${d.date}-${d.label}`, label: dateLabel(d.kind, d.label), date: d.date, url: d.sourceUrl })),
    ...r.events.map(e => ({ key: e.id, label: e.title, date: e.date, url: e.sourceUrl })),
  ].sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999"));
  const stage = recordMapStage(r);
  return (
    <section className="detail-panel" tabIndex={-1} aria-labelledby="investment-detail-title" data-selected-id={r.id}>
      <div className="detail-bar">
        <div className="detail-nav">
          <BackButton onClick={onClose} label="Zamknij szczegóły inwestycji" />
          {onBackToMap && <MapButton onClick={onBackToMap} />}
        </div>
        <ShareButton url={share} />
      </div>
      <div className="detail-kicker">
        <span className="kind-badge" style={{ "--kind": mapStageColors[stage] } as React.CSSProperties}>
          {investmentTypes[r.recordType]} · {investorLabels[r.investor]}
        </span>
        {isNew && <span className="new-badge">Nowe</span>}
      </div>
      <h2 id="investment-detail-title" className="detail-title">{r.title || "Bez tytułu"}</h2>
      <p className="detail-place">{[r.locality, r.address].filter(Boolean).join(", ") || "Brak miejscowości w źródle"}</p>
      <p className="detail-sub">
        {r.investorName ? `${r.investorName} · ` : ""}{categoryGroup(r.category)}
        {r.category && r.category !== categoryGroup(r.category) ? <span className="muted"> (w źródle: „{r.category}”)</span> : null}
      </p>
      <StageTracker record={r} />
      {!!r.warnings.length && (
        <div className="alert" role="note">
          <strong>Ograniczenia rekordu</strong>
          <ul>{r.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}
      {r.summary && <p className="description">{r.summary}</p>}
      {dates.length > 0 && (
        <>
          <h3 className="section-title">Ważne daty</h3>
          <ul className="date-list">
            {dates.map(d => (
              <li key={d.key}>
                <span>{d.label}</span>
                <span className="date-value">
                  <strong>{d.date ? formatDate(d.date) : "Data niepodana"}</strong>
                  {d.date && relative(d.date, today) && <span className="muted">{relative(d.date, today)}</span>}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="fact-cards">
        <div className="fact-card">
          <span className="fact-label">Kwota</span>
          {r.costs.length ? r.costs.map((c, i) => (
            <span key={i} className="fact-cost">
              <strong>{money(c.amount, c.currency)}</strong>
              <span>{c.kind === "offer" || /część/.test(c.label) ? c.label : costKinds[c.kind] || c.kind}{c.year ? ` · ${c.year}` : ""}</span>
              {c.scope !== "local" && <span className="muted">{costScope[c.scope]}</span>}
            </span>
          )) : <strong>Brak w tym rekordzie</strong>}
        </div>
        <div className={`fact-card${r.geometries.length ? "" : " dashed"}`}>
          <span className="fact-label">Lokalizacja</span>
          {r.geometries.length
            ? <strong>{[...new Set(r.geometries.map(g => accuracyLabels[g.properties.accuracy]))].join("; ")}</strong>
            : <><strong>Brak w źródle</strong><span className="muted">nie stawiamy pinezki — rekord jest na liście</span></>}
        </div>
      </div>
      {r.costs.length > 1 && <p className="muted">Kwot nie sumujemy: mogą dotyczyć różnych etapów tej samej inwestycji.</p>}
      {related.length > 0 && <RelatedSources entries={related} onPick={id => onPick("investments", id)} />}
      {history.length > 0 && (
        <>
          <h3 className="section-title">Historia miejsca</h3>
          <p className="muted">Wcześniejsze i późniejsze wpisy gminnej mapy w tym samym miejscu (do 150 m) o podobnej nazwie.</p>
          <ol className="history-list">
            {history.map(({ record: x, meters }) => (
              <li key={x.id}><button type="button" onClick={() => onPick("investments", x.id)}>
                <span className="history-year">{x.years.join(", ") || "—"}</span>
                <span className="nearby-main"><strong>{x.title}</strong><span>{x.status}</span></span>
                <span className="nearby-distance">{formatDistance(meters)}</span>
              </button></li>
            ))}
          </ol>
        </>
      )}
      {similar.length > 0 && (
        <>
          <h3 className="section-title">Rekordy o podobnej nazwie</h3>
          <p className="muted">Mogą dotyczyć tej samej inwestycji, ale nie łączymy ich automatycznie i nie sumujemy kwot.</p>
          <ul className="nearby-list">
            {similar.map(x => (
              <li key={x.id}><button type="button" onClick={() => onPick("investments", x.id)}>
                <span className="row-mark circle" style={{ background: mapStageColors[recordMapStage(x)] }} aria-hidden="true" />
                <span className="nearby-main"><strong>{x.title}</strong><span>{investmentTypes[x.recordType]} · {x.years.join(", ") || "rok niepodany"} · {x.status}</span></span>
              </button></li>
            ))}
          </ul>
        </>
      )}
      {nearbyPermits.length > 0 && (
        <>
          <h3 className="section-title">Budowy w pobliżu (do 300 m)</h3>
          <ul className="nearby-list">
            {nearbyPermits.map(({ item, meters }) => (
              <li key={item.id}><button type="button" onClick={() => onPick("permits", item.id)}>
                <span className="nearby-main"><strong>{item.title}</strong><span>{kindLabels[item.kind]} · {formatDate(recordDate(item))}</span></span>
                <span className="nearby-distance">{formatDistance(meters)}</span>
              </button></li>
            ))}
          </ul>
        </>
      )}
      <h3 className="section-title">Dokumenty</h3>
      <div className="verify-list">
        <ExternalLink className="verify-link primary" url={r.sourceUrl} sub={source?.name}>Rekord w źródle</ExternalLink>
        {documents.map((f, i) => (
          <ExternalLink key={i} className="verify-link" url={f.sourceUrl} sub={f.value}>{f.label}</ExternalLink>
        ))}
      </div>
      <details className="tech-details">
        <summary>Dane techniczne</summary>
        <dl>
          <dt>Źródło</dt><dd>{source?.name || r.sourceId}</dd>
          <dt>Odczyt źródła</dt><dd>{source ? freshness[source.status] : "Brak metadanych"}</dd>
          <dt>Kategoria w źródle</dt><dd>{r.category || "Brak danych"}</dd>
          <dt>Lata</dt><dd>{r.years.join(", ") || "Nie podano"}</dd>
          <dt>Edycja w źródle</dt><dd>{formatDateTime(r.sourceUpdatedAt)}</dd>
          <dt>Pobrano</dt><dd>{formatDateTime(r.fetchedAt)}</dd>
          <dt>Identyfikator</dt><dd className="mono">{r.id}</dd>
          <dt>ID w źródle</dt><dd className="mono">{r.sourceRecordId}</dd>
          <dt>Działki</dt><dd className="mono">{r.parcelIds.join(", ") || "Nie podano"}</dd>
          {technical.map((f, i) => (
            <div key={i} className="tech-row"><dt>{f.label}</dt><dd className="mono">{f.value || "—"}</dd></div>
          ))}
        </dl>
        {technical.length > 0 && <ExternalLink url={technical[0].sourceUrl}>Surowy odczyt pól ze źródła</ExternalLink>}
        {r.costs.length > 0 && (
          <ul className="parcel-list">
            {r.costs.map((c, i) => <li key={i}><span>{c.label}</span><ExternalLink url={c.sourceUrl}>Dokument kosztu</ExternalLink></li>)}
          </ul>
        )}
        {r.geometries.length > 0 && (
          <ul className="parcel-list">
            {r.geometries.map(g => (
              <li key={g.properties.id}>
                <span>{accuracyLabels[g.properties.accuracy]}{g.properties.note ? ` — ${g.properties.note}` : ""}</span>
                <ExternalLink url={g.properties.sourceUrl}>Źródło geometrii</ExternalLink>
              </li>
            ))}
          </ul>
        )}
      </details>
    </section>
  );
}

export function InvestmentList({ state, selectedId, onSelect, onSearchFocus, onAbout }: {
  state: InvestmentState;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onSearchFocus: () => void;
  onAbout: () => void;
}) {
  const { data, error, loading, filters, setFilters, seen, onlyNew, setOnlyNew, all, filtered, mapped } = state;
  const [shown, setShown] = useState(PAGE);
  useEffect(() => setShown(PAGE), [filtered]);
  const update = <K extends keyof InvestmentFilters>(key: K, value: InvestmentFilters[K]) => setFilters(prev => ({ ...prev, [key]: value }));
  const reset = () => { setFilters({ ...investmentDefaults }); setOnlyNew(false); };
  const activeFilters = (Object.keys(investmentDefaults) as (keyof InvestmentFilters)[]).filter(key =>
    key !== "sort" && JSON.stringify(filters[key]) !== JSON.stringify(investmentDefaults[key])).length + (onlyNew ? 1 : 0);
  const stageCounts = useMemo(() => {
    const rows = filterInvestments(all, { ...filters, stages: ["upcoming", "progress", "done", "other"] });
    const result = new Map<MapStage, number>();
    for (const row of onlyNew ? rows.filter(r => seen.newIds.has(r.id)) : rows) result.set(recordMapStage(row), (result.get(recordMapStage(row)) || 0) + 1);
    return result;
  }, [all, filters, onlyNew, seen]);
  const newCount = useMemo(() => filterInvestments(all, filters).filter(r => seen.newIds.has(r.id)).length, [all, filters, seen]);
  const options = useMemo(() => {
    const groups = new Map<string, number>(), localities = new Map<string, number>();
    for (const r of all) {
      groups.set(categoryGroup(r.category), (groups.get(categoryGroup(r.category)) || 0) + 1);
      if (r.locality) localities.set(r.locality, (localities.get(r.locality) || 0) + 1);
    }
    return {
      groups: [...groups.entries()].sort((a, b) => b[1] - a[1]),
      localities: [...localities.entries()].sort((a, b) => a[0].localeCompare(b[0], "pl")),
      withoutLocality: all.filter(r => !r.locality).length,
      years: [...new Set(all.flatMap(r => r.years))].sort((a, b) => b - a),
    };
  }, [data]);
  const toggleStage = (stage: MapStage) =>
    update("stages", filters.stages.includes(stage) ? filters.stages.filter(s => s !== stage) : [...filters.stages, stage]);
  const sourceFailures = data?.sources.filter(s => s.status === "retained" || s.status === "unavailable") || [];
  const sourceName = (id: string) => data?.sources.find(s => s.id === id)?.name || id;
  return (
    <div className="panel-list">
      <div className="panel-tools">
        <SearchBox id="investment-search" label="Szukaj inwestycji" value={filters.query} onChange={value => update("query", value)}
          placeholder="Nazwa, ulica, działka, numer sprawy" onFocus={onSearchFocus} />
        <div className="chip-row" role="group" aria-label="Etap inwestycji">
          {(["upcoming", "progress", "done", "other"] as MapStage[]).map(stage => (
            <Chip key={stage} pressed={filters.stages.includes(stage)} dot={mapStageColors[stage]} onClick={() => toggleStage(stage)}>
              {mapStageLabels[stage]} <span className="chip-count">{stageCounts.get(stage) || 0}</span>
            </Chip>
          ))}
          {(newCount > 0 || onlyNew) && (
            <Chip pressed={onlyNew} onClick={() => setOnlyNew(!onlyNew)}>
              Nowe od ostatniej wizyty <span className="chip-count">{newCount}</span>
            </Chip>
          )}
          <ChipSelect label="Rodzaj inwestycji" value={filters.group} onChange={value => update("group", value)} active={!!filters.group}>
            <option value="">Wszystkie rodzaje</option>
            {options.groups.map(([group, count]) => <option key={group} value={group}>{group} ({count})</option>)}
          </ChipSelect>
          <ChipSelect label="Miejscowość inwestycji" value={filters.locality} onChange={value => update("locality", value)} active={!!filters.locality}>
            <option value="">Cała gmina</option>
            {options.localities.map(([locality, count]) => <option key={locality} value={locality}>{locality} ({count})</option>)}
            {options.withoutLocality > 0 && <option value="-">Bez miejscowości w źródle ({options.withoutLocality})</option>}
          </ChipSelect>
        </div>
        <details className="more-filters">
          <summary>Więcej filtrów{activeFilters > 0 && <span className="filter-number" aria-label={`${activeFilters} aktywnych filtrów`}>{activeFilters}</span>}</summary>
          <div className="filter-grid">
            <label>Rok inwestycji
              <select value={filters.year} onChange={e => update("year", e.target.value)}>
                <option value="">Wszystkie lata</option>
                {options.years.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </label>
            <label>Źródło inwestycji
              <select value={filters.source} onChange={e => update("source", e.target.value)}>
                <option value="">Wszystkie źródła</option>
                {data?.sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label>Inwestor
              <select value={filters.investor} onChange={e => update("investor", e.target.value)}>
                <option value="">Wszyscy inwestorzy</option>
                {Object.entries(investorLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select>
            </label>
            <label>Położenie inwestycji
              <select value={filters.mapping} onChange={e => update("mapping", e.target.value as InvestmentFilters["mapping"])}>
                <option value="all">Wszystkie rekordy</option>
                <option value="mapped">Na mapie</option>
                <option value="unmapped">Bez lokalizacji (tylko lista)</option>
              </select>
            </label>
            <label>Sortowanie inwestycji
              <select value={filters.sort} onChange={e => update("sort", e.target.value as InvestmentFilters["sort"])}>
                <option value="newest">Najnowsza data źródłowa / rok</option>
                <option value="oldest">Najstarsza data źródłowa / rok</option>
                <option value="title">Nazwa A–Z</option>
              </select>
            </label>
          </div>
        </details>
      </div>
      <div className="list-summary">
        <p aria-live="polite">
          {loading ? "Wczytywanie inwestycji…" : error ? "Lista inwestycji niedostępna" : (
            <><strong>{filtered.length} {filtered.length === 1 ? "rekord" : "rekordów"}</strong> · {mapped} na mapie{filtered.length - mapped ? ` · ${filtered.length - mapped} bez lokalizacji` : ""}</>
          )}
        </p>
        <div className="list-actions">
          {activeFilters > 0 && <button type="button" className="text-button" onClick={reset} aria-label="Wyczyść filtry inwestycji">Wyczyść</button>}
          <button type="button" className="text-button" aria-label="Eksport CSV inwestycji"
            disabled={loading || !!error || !filtered.length} onClick={() => download(filtered)}>Eksport CSV</button>
        </div>
      </div>
      {!loading && error && (
        <section className="alert error" role="alert">
          <h2>Inwestycje są chwilowo niedostępne</h2>
          <p>{error} Budowy działają niezależnie.</p>
          <button type="button" className="primary-button" onClick={state.retry}>Spróbuj ponownie — inwestycje</button>
        </section>
      )}
      {!!sourceFailures.length && !loading && !error && (
        <section className="alert" role="alert" aria-label="Problemy z pobraniem źródeł">
          <strong>Nie wszystkie źródła udało się odświeżyć.</strong>
          <ul>{sourceFailures.map(s => <li key={s.id}>{s.name}: {freshness[s.status]}</li>)}</ul>
          <button type="button" className="link-button" onClick={onAbout}>Szczegóły w „O danych”</button>
        </section>
      )}
      <section id="investment-results" className="results" aria-labelledby="investment-results-title" tabIndex={-1}>
        <h2 id="investment-results-title" className="sr-only">Rekordy inwestycji</h2>
        {loading ? (
          <div className="empty-state"><span className="loading-ring" aria-hidden="true" /><p>Wczytujemy inwestycje…</p></div>
        ) : error ? (
          <div className="empty-state"><p>Nie można ustalić liczby rekordów. Spróbuj ponownie.</p></div>
        ) : !filtered.length ? (
          <div className="empty-state">
            <h3>{all.length ? "Brak wyników dla tych filtrów." : "Brak rekordów w załadowanym zbiorze."}</h3>
            <p>{all.length ? "Zmień zapytanie, włącz inne etapy lub wyczyść filtry." : "To nie jest potwierdzenie braku inwestycji w gminie. Sprawdź pokrycie źródeł."}</p>
          </div>
        ) : (
          <>
            <ul className="result-list">
              {filtered.slice(0, Math.max(shown, filtered.findIndex(r => r.id === selectedId) + 1)).map(r => (
                <li key={r.id}>
                  <button type="button" className={`result-row${selectedId === r.id ? " selected" : ""}`} data-record-id={r.id}
                    aria-pressed={selectedId === r.id} onClick={() => onSelect(r.id)}>
                    <span className="row-mark circle" style={{ background: mapStageColors[recordMapStage(r)] }} aria-hidden="true" />
                    <span className="row-body">
                      <span className="row-top">
                        <span className="row-kind">{mapStageLabels[recordMapStage(r)]}</span>
                        <span>{r.years.join(", ") || "rok niepodany"}</span>
                        {seen.newIds.has(r.id) && <span className="new-badge">Nowe</span>}
                      </span>
                      <span className="row-title">{r.title || "Bez tytułu"}</span>
                      <span className="row-place">{[r.locality, r.address].filter(Boolean).join(", ") || "Brak miejscowości w źródle"}</span>
                      <span className="row-source">{investmentTypes[r.recordType]} · {sourceName(r.sourceId)}</span>
                      {!r.geometries.length && <span className="row-flag">Tylko na liście — brak lokalizacji</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <MoreButton shown={shown} total={filtered.length} onMore={() => setShown(n => n + PAGE)} />
          </>
        )}
      </section>
      <p className="panel-note">Liczymy rekordy źródłowe, nie unikalne budowy. Rekord nie potwierdza rozpoczęcia robót.</p>
    </div>
  );
}
