import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Geometry } from "geojson";
import RadarMap, { type Insets, type Layer, type MapItem, type UserLocation } from "./RadarMap";
import { PermitDetail, PermitList, placeLine, usePermits, type Nearby } from "./PermitPanel";
import { InvestmentDetail, InvestmentList, freshness, useInvestments } from "./InvestmentPanel";
import { defaultFilters, formatDate, getRecordParcels, kindColors, kindLabels, kindPlural } from "./model";
import { investmentDefaults, mapStageColors, mapStageLabels, recordMapStage, type MapStage } from "./investments";
import { centerOf, distanceMeters, nearest, type LatLng } from "./geo";
import { readHash, shareUrl, writeHash, type Mode } from "./hash";
import { useIsMobile } from "./ui";
import type { RecordKind } from "./types";

type Sheet = "peek" | "half" | "full";
interface Selection { layer: Layer; id: string }
const HEADER = 52;
const GMINA_CENTER: LatLng = [52.21, 20.798];
const PEEK = 196;

function useViewportHeight() {
  const [height, setHeight] = useState(() => window.innerHeight || 800);
  useEffect(() => {
    const update = () => setHeight(window.innerHeight || 800);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return height;
}

function AboutDialog({ onClose, permits, investments }: {
  onClose: () => void;
  permits: ReturnType<typeof usePermits>;
  investments: ReturnType<typeof useInvestments>;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  const { data, loading } = permits;
  const records = permits.all;
  const invData = investments.data;
  const invWarnings = [
    ...(invData?.warnings || []),
    ...(invData?.sources.flatMap(s => [
      ...(s.status === "retained" || s.status === "unavailable" ? [`${s.name}: ${freshness[s.status]}`] : []),
      ...s.warnings.map(w => `${s.name}: ${w}`),
    ]) || []),
  ];
  return (
    <div className="about-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="about" role="dialog" aria-modal="true" aria-labelledby="about-title" id="provenance">
        <div className="about-bar">
          <h2 id="about-title" ref={heading} tabIndex={-1}>O danych</h2>
          <button type="button" className="round-button" onClick={onClose} aria-label="Zamknij informacje o danych">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        </div>
        <div className="about-body">
          <section aria-labelledby="about-permits">
            <h3 id="about-permits">Budowy — rejestr GUNB</h3>
            <ul className="about-points">
              <li>Wpis w rejestrze nie oznacza zatwierdzenia ani rozpoczęcia budowy. Eksport GUNB nie podaje wyniku decyzji.</li>
              <li>Kolor na mapie to rodzaj wpisu (decyzja, zgłoszenie), nie wynik.</li>
              <li>Mapa pokazuje działki z wpisu (ULDK), nie budynki ani postęp prac. Brak działki na mapie to brak potwierdzonej geometrii, a nie brak inwestycji.</li>
              <li>Okres i kolejność liczymy według daty decyzji, a gdy jej brak — daty wniosku. „Ostatnie 3 miesiące” liczymy od dzisiejszej daty w Polsce.</li>
              <li>„Nowe od ostatniej wizyty” zapamiętuje tylko Twoja przeglądarka.</li>
              <li>Przycisk lokalizacji odczytuje położenie dopiero po kliknięciu i tylko rysuje je na mapie — nie jest nigdzie wysyłane ani zapisywane.</li>
            </ul>
            {!loading && !data.error && records.length > 0 && !records.some(r => r.kind === "application") && (
              <p className="coverage-note">W tym zbiorze nie ma samodzielnych wniosków. Nie oznacza to braku nierozpatrzonych wniosków w gminie — eksport CSV nie gwarantuje ich kompletności.</p>
            )}
            <h4>Zakres załadowanego zbioru</h4>
            <p>{data.dataset?.source.coverage || "Zakres danych nie jest jeszcze dostępny."}</p>
            {data.dataset && (
              <p className="muted">Pobranie źródła: {formatDate(data.dataset.source.downloadedAt)} · Wygenerowanie zbioru: {formatDate(data.dataset.generatedAt)}</p>
            )}
            {!loading && data.warnings.length > 0 && (
              <>
                <h4>Ograniczenia zbioru ({data.warnings.length})</h4>
                <ul className="about-warnings">{data.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
              </>
            )}
            <ul className="about-links">
              {data.dataset && <li><a href={data.dataset.source.url} target="_blank" rel="noopener noreferrer">{data.dataset.source.name}</a></li>}
              {data.metadata?.sources?.map((s, i) => <li key={i}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a></li>)}
            </ul>
            <p className="muted">Dane inwestorów i projektantów są wyłączone z publicznego zbioru. CSV zawiera bieżące wyniki filtrów; wartości chronimy przed interpretacją jako formuły arkusza.</p>
          </section>
          <section aria-labelledby="about-investments" id="investment-provenance">
            <h3 id="about-investments">Inwestycje — niezależne źródła</h3>
            <ul className="about-points">
              <li>Liczymy rekordy źródłowe, nie unikalne budowy. Różne dokumenty mogą opisywać to samo przedsięwzięcie — pokazujemy je obok siebie jako „podobne”, ale nie łączymy.</li>
              <li>Etap (Zapowiedziane, W realizacji, Ukończone) to grupowanie zdań statusu ze źródła; oryginalny status jest w karcie rekordu. Ukończone są domyślnie ukryte.</li>
              <li>Punkt, działka i trasa mają różną dokładność. Brak lokalizacji nie oznacza braku inwestycji.</li>
              <li>Budżet, propozycja BO, grant, zamówienie i sprawa środowiskowa nie potwierdzają rozpoczęcia prac. Kwot nie sumujemy; koszt projektu wielogminnego nie jest kosztem samej gminy.</li>
              <li>Import inwestycji: {invData ? formatDate(invData.generatedAt) : "nie wczytano"}.</li>
            </ul>
            {invWarnings.length > 0 && (
              <>
                <h4>Ograniczenia aktualności i integralności</h4>
                <ul className="about-warnings">{invWarnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
              </>
            )}
            <div className="about-sources">
              {invData?.sources.map(s => (
                <article key={s.id}>
                  <h4><a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a></h4>
                  <p>{freshness[s.status]} · {s.recordCount} rekordów</p>
                  <p className="muted">{s.coverage}</p>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const permits = usePermits();
  const investments = useInvestments();
  const mobile = useIsMobile();
  const viewport = useViewportHeight();
  const initialHash = useRef(readHash(window.location.hash));
  const [mode, setMode] = useState<Mode>(initialHash.current.mode);
  const [layers, setLayers] = useState({ permits: true, investments: true });
  const [selection, setSelection] = useState<Selection | null>(null);
  const [sheet, setSheet] = useState<Sheet>("peek");
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const [about, setAbout] = useState(false);
  const [legendOpen, setLegendOpen] = useState(false);
  const [fitToken, setFitToken] = useState(0);
  const [fitAllToken, setFitAllToken] = useState(0);
  const [userLocation, setUserLocation] = useState<UserLocation | null>(null);
  const [locating, setLocating] = useState(false);
  const [locateMessage, setLocateMessage] = useState<string | null>(null);
  const origin = useRef<"list" | "map">("list");
  const [restoreToken, setRestoreToken] = useState(0);
  // The sheet size before the current selection, so dismissing it returns to the same view.
  const sheetBefore = useRef<Sheet>("peek");
  const now = useRef({ selection, sheet });
  now.current = { selection, sheet };
  const restore = useRef<{ origin: "list" | "map"; id: string } | null>(null);
  const aboutOpener = useRef<HTMLElement | null>(null);
  const overview = useRef<HTMLButtonElement>(null);
  const panelBody = useRef<HTMLDivElement>(null);

  const permitGeo = useMemo(() => {
    const result = new Map<string, { at: LatLng; areas: Geometry[] }>();
    for (const record of permits.all) {
      const areas = getRecordParcels(record, permits.data.parcels).map(f => f.geometry);
      const at = centerOf(areas);
      if (at) result.set(record.id, { at, areas });
    }
    return result;
  }, [permits.data]);
  const investmentGeo = useMemo(() => {
    const result = new Map<string, { at: LatLng; areas: Geometry[] }>();
    for (const record of investments.all) {
      const geometries = record.geometries.map(g => g.geometry);
      const at = centerOf(geometries);
      if (at) result.set(record.id, { at, areas: geometries.filter(g => !/Point/.test(g.type)) });
    }
    return result;
  }, [investments.data]);

  const selectedPermit = selection?.layer === "permits" ? permits.all.find(r => r.id === selection.id) || null : null;
  const selectedInvestment = selection?.layer === "investments" ? investments.all.find(r => r.id === selection.id) || null : null;
  const selectedKey = selectedPermit ? `p:${selectedPermit.id}` : selectedInvestment ? `i:${selectedInvestment.id}` : null;

  const items = useMemo(() => {
    const result: MapItem[] = [];
    const permitRows = layers.permits ? permits.filtered : [];
    const investmentRows = layers.investments ? investments.filtered : [];
    const extraPermit = selectedPermit && !permitRows.includes(selectedPermit) ? [selectedPermit] : [];
    const extraInvestment = selectedInvestment && !investmentRows.includes(selectedInvestment) ? [selectedInvestment] : [];
    for (const record of [...permitRows, ...extraPermit]) {
      const geo = permitGeo.get(record.id);
      if (geo) result.push({
        key: `p:${record.id}`, layer: "permits", id: record.id, at: geo.at, areas: geo.areas,
        color: kindColors[record.kind], shape: "square",
        label: `${kindLabels[record.kind]} · ${record.title} · ${placeLine(record)}`,
      });
    }
    for (const record of [...investmentRows, ...extraInvestment]) {
      const geo = investmentGeo.get(record.id);
      const stage = recordMapStage(record);
      if (geo) result.push({
        key: `i:${record.id}`, layer: "investments", id: record.id, at: geo.at, areas: geo.areas,
        color: mapStageColors[stage], shape: "circle", hollow: stage === "other",
        label: `${mapStageLabels[stage]} · ${record.title}`,
      });
    }
    return result;
  }, [permits.filtered, investments.filtered, layers, permitGeo, investmentGeo, selectedPermit, selectedInvestment]);

  const selectedOnMap = !!selectedKey && items.some(item => item.key === selectedKey);
  const sheetHeights = { peek: PEEK, half: Math.round((viewport - HEADER) * 0.55), full: viewport - HEADER - 8 };
  const sheetHeight = dragHeight ?? sheetHeights[sheet];
  const insets: Insets = mobile
    ? { left: 0, top: 56, bottom: Math.min(sheetHeight, sheetHeights.half) }
    : { left: 432, top: 0, bottom: 0 };

  const select = useCallback((layer: Layer, id: string, from: "list" | "map" = "map") => {
    origin.current = from;
    if (!now.current.selection) sheetBefore.current = now.current.sheet;
    setMode(layer);
    setLayers(prev => ({ ...prev, [layer]: true }));
    setSelection({ layer, id });
    setSheet("half");
    setFitToken(n => n + 1);
  }, []);
  /** Selecting a record that current filters hide (a nearby or similar one) widens the filters. */
  const pick = useCallback((layer: Layer, id: string) => {
    if (layer === "permits" && !permits.filtered.some(r => r.id === id)) {
      permits.setFilters({ ...defaultFilters, period: "all" });
      permits.setOnlyNew(false);
    }
    if (layer === "investments" && !investments.filtered.some(r => r.id === id)) {
      investments.setFilters({ ...investmentDefaults, stages: ["upcoming", "progress", "done", "other"] });
      investments.setOnlyNew(false);
    }
    select(layer, id, "list");
  }, [permits.filtered, investments.filtered, select]);
  const close = useCallback(() => {
    if (!selection) return;
    restore.current = { origin: origin.current, id: selection.id };
    setSelection(null);
    if (mobile) setSheet(origin.current === "list" ? "half" : "peek");
  }, [selection, mobile]);

  // Phone: a tap on empty map dismisses the card and returns to the map and sheet as they were before
  // it opened (a full-height list gives way to the map). Without a card it just lowers the sheet.
  const keepView = useRef(false);
  const dismiss = useCallback(() => {
    if (!mobile || (!selection && sheet === "peek")) return;
    const next = selection && sheetBefore.current !== "full" ? sheetBefore.current : "peek";
    if (selection) {
      setSelection(null);
      setRestoreToken(n => n + 1);
    }
    if (sheet !== next) { keepView.current = true; setSheet(next); }
  }, [mobile, selection, sheet]);

  // A filter change that hides the selected record closes its card.
  useEffect(() => {
    if (selectedPermit && !permits.loading && !permits.filtered.includes(selectedPermit)) setSelection(null);
  }, [permits.filtered]);
  useEffect(() => {
    if (selectedInvestment && !investments.loading && !investments.filtered.includes(selectedInvestment)) setSelection(null);
  }, [investments.filtered]);
  // Reframe the map when the result set changes.
  const firstFilter = useRef(true);
  useEffect(() => {
    if (firstFilter.current) { firstFilter.current = false; return; }
    if (!selection) setFitToken(n => n + 1);
  }, [permits.filters, permits.onlyNew, investments.filters, investments.onlyNew, layers]);

  // The sheet covers the lower map, so keep the results (or the selection) in the visible part.
  const firstSheet = useRef(true);
  useEffect(() => {
    if (firstSheet.current) { firstSheet.current = false; return; }
    if (keepView.current) { keepView.current = false; return; }
    if (mobile && sheet !== "full") setFitToken(n => n + 1);
  }, [sheet]);
  useEffect(() => {
    if (selection) {
      const detail = panelBody.current?.querySelector<HTMLElement>(".detail-panel");
      detail?.scrollIntoView?.({ block: "start", behavior: "auto" });
      detail?.focus({ preventScroll: true });
      return;
    }
    const target = restore.current;
    if (!target) return;
    restore.current = null;
    if (target.origin === "list") {
      const row = Array.from(panelBody.current?.querySelectorAll<HTMLElement>(".result-row") || [])
        .find(element => element.dataset.recordId === target.id);
      row?.scrollIntoView?.({ block: "nearest", behavior: "auto" });
      row?.focus({ preventScroll: true });
    } else overview.current?.focus({ preventScroll: true });
  }, [selection]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (about) { event.preventDefault(); setAbout(false); aboutOpener.current?.focus(); }
      else if (selection) { event.preventDefault(); close(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [about, selection, close]);

  // Shareable links: apply the hash once its dataset is loaded, then mirror the state.
  const hashApplied = useRef(false);
  const applyHash = useCallback((hash: string) => {
    const state = readHash(hash);
    setMode(state.mode);
    if (state.permitId && permits.all.some(r => r.id === state.permitId)) {
      if (!permits.filtered.some(r => r.id === state.permitId)) permits.setFilters(prev => ({ ...prev, period: "all" }));
      select("permits", state.permitId);
    } else if (state.investmentId && investments.all.some(r => r.id === state.investmentId)) {
      if (!investments.filtered.some(r => r.id === state.investmentId))
        investments.setFilters({ ...investmentDefaults, stages: ["upcoming", "progress", "done", "other"] });
      select("investments", state.investmentId);
    }
  }, [permits.all, permits.filtered, investments.all, investments.filtered, select]);
  useEffect(() => {
    if (hashApplied.current) return;
    const wanted = initialHash.current;
    if (wanted.permitId ? permits.loading : wanted.investmentId ? investments.loading : false) return;
    hashApplied.current = true;
    if (wanted.permitId || wanted.investmentId) applyHash(window.location.hash);
  }, [permits.loading, investments.loading, applyHash]);
  useEffect(() => {
    if (!hashApplied.current) return;
    const next = writeHash({ mode, id: selection?.id ?? null });
    if (window.location.hash !== next && (window.location.hash || next !== "#budowy"))
      window.history.replaceState(null, "", next);
  }, [mode, selection]);
  useEffect(() => {
    const onHash = () => applyHash(window.location.hash);
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [applyHash]);

  useEffect(() => {
    if (!locateMessage) return;
    const timer = setTimeout(() => setLocateMessage(null), 7000);
    return () => clearTimeout(timer);
  }, [locateMessage]);
  /** The position is read only on request and never leaves the browser. */
  const locate = () => {
    if (!("geolocation" in navigator) || !navigator.geolocation) {
      setLocateMessage("Ta przeglądarka nie udostępnia lokalizacji.");
      return;
    }
    setLocating(true);
    setLocateMessage(null);
    navigator.geolocation.getCurrentPosition(
      position => {
        setLocating(false);
        const at: LatLng = [position.coords.latitude, position.coords.longitude];
        setUserLocation(prev => ({ at, accuracy: position.coords.accuracy, token: (prev?.token || 0) + 1 }));
        if (distanceMeters(at, GMINA_CENTER) > 12_000)
          setLocateMessage("Jesteś poza gminą Ożarów Mazowiecki — dane na mapie dotyczą tylko gminy.");
        else if (position.coords.accuracy > 500)
          setLocateMessage(`Położenie przybliżone (dokładność ok. ${Math.round(position.coords.accuracy / 100) / 10} km).`);
      },
      error => {
        setLocating(false);
        setLocateMessage(error.code === 1
          ? "Brak zgody na lokalizację. Możesz ją włączyć w ustawieniach strony w przeglądarce."
          : error.code === 3
            ? "Ustalanie położenia trwało zbyt długo. Spróbuj ponownie."
            : "Nie udało się ustalić położenia.");
      },
      { enableHighAccuracy: true, timeout: 15_000, maximumAge: 30_000 },
    );
  };

  const changeMode = (next: Mode) => {
    if (next === mode) return;
    if (selection && selection.layer !== next) setSelection(null);
    setMode(next);
    setLayers(prev => ({ ...prev, [next]: true }));
  };
  const openAbout = (event: React.MouseEvent<HTMLElement>) => {
    aboutOpener.current = event.currentTarget;
    setAbout(true);
  };

  // Bottom sheet: tap the handle to step through sizes, or drag it.
  const drag = useRef<{ y: number; height: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const snapTo = (height: number) => {
    const entries = Object.entries(sheetHeights) as [Sheet, number][];
    entries.sort((a, b) => Math.abs(a[1] - height) - Math.abs(b[1] - height));
    setSheet(entries[0][0]);
  };

  const nearbyFor = (at: LatLng | undefined): Nearby => {
    if (!at) return { permits: [], investments: [] };
    const permitPoints = permits.all.flatMap(r => {
      const geo = permitGeo.get(r.id);
      return geo && r.id !== selection?.id ? [{ item: r, at: geo.at }] : [];
    });
    const investmentPoints = investments.all.flatMap(r => {
      const geo = investmentGeo.get(r.id);
      return geo && r.id !== selection?.id && recordMapStage(r) !== "done" ? [{ item: r, at: geo.at }] : [];
    });
    return { permits: nearest(at, permitPoints, 300, 4), investments: nearest(at, investmentPoints, 1000, 3) };
  };

  const permitLegend = useMemo(() => {
    const counts = new Map<RecordKind, number>();
    for (const r of permits.filtered) if (permitGeo.has(r.id)) counts.set(r.kind, (counts.get(r.kind) || 0) + 1);
    return [...counts.entries()];
  }, [permits.filtered, permitGeo]);
  const investmentLegend = useMemo(() => {
    const counts = new Map<MapStage, number>();
    for (const r of investments.filtered) if (investmentGeo.has(r.id)) counts.set(recordMapStage(r), (counts.get(recordMapStage(r)) || 0) + 1);
    return (["upcoming", "progress", "done", "other"] as MapStage[]).filter(s => counts.has(s)).map(s => [s, counts.get(s)!] as const);
  }, [investments.filtered, investmentGeo]);

  const permitReady = !permits.loading && !permits.data.error;
  const investmentReady = !investments.loading && !investments.error;
  const share = shareUrl({ mode, id: selection?.id ?? null });

  return (
    <div className={`app${mobile ? " is-mobile" : ""}`}>
      <a className="skip-link" href="#results" onClick={event => {
        event.preventDefault();
        setSelection(null);
        setSheet("full");
        requestAnimationFrame(() => document.querySelector<HTMLElement>(mode === "permits" ? "#results" : "#investment-results")?.focus());
      }}>Przejdź do wyników</a>
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="11" /><circle cx="16" cy="16" r="5" /><path d="M16 16 25 7" /></svg></span>
          <div><h1>Radar Ożarów</h1><p>Budowy i inwestycje w gminie Ożarów Mazowiecki</p></div>
        </div>
        <button type="button" className="header-link" onClick={openAbout}>O danych</button>
      </header>
      <div className="sr-only" role="status" aria-live="polite" data-testid="data-status"
        data-loading={permits.loading} data-state={permits.loading ? "loading" : permits.data.error ? "error" : "ready"}
        data-record-count={permits.loading ? "" : permits.allCounts.total}
        data-filtered-count={permits.loading ? "" : permits.counts.total}
        data-mapped-count={permits.loading ? "" : permits.allCounts.mapped}
        data-parcel-count={permits.loading ? "" : permits.allCounts.parcelCount}>
        {permits.loading ? "Ładowanie danych…" : permits.data.error ? "Dane nie zostały wczytane." : `Wczytano ${permits.allCounts.total} wpisów budowlanych`}
      </div>
      <div className="sr-only" role="status" aria-live="polite" data-testid="investments-status"
        data-state={investments.loading ? "loading" : investments.error ? "error" : "ready"}
        data-record-count={investmentReady ? investments.all.length : ""}
        data-filtered-count={investmentReady ? investments.filtered.length : ""}
        data-mapped-count={investmentReady ? investments.mapped : ""}>
        {investments.loading ? "Ładowanie inwestycji…" : investments.error ? "Dane inwestycji niewczytane." : `Wczytano ${investments.all.length} rekordów inwestycji`}
      </div>
      <main className="stage">
        <section className="map-area" aria-label="Mapa">
          <RadarMap items={items} selectedKey={selectedKey} insets={insets} fitToken={fitToken} fitAllToken={fitAllToken}
            userLocation={userLocation} onSelect={(layer, id) => select(layer, id, "map")} onBackgroundClick={dismiss} restoreToken={restoreToken} />
          <div className="map-controls">
            <div className={`layer-card${legendOpen || !mobile ? " open" : ""}`}>
              {mobile && (
                <button type="button" className="layer-toggle" aria-expanded={legendOpen} onClick={() => setLegendOpen(!legendOpen)}>
                  Warstwy i legenda
                </button>
              )}
              {(legendOpen || !mobile) && (
                <div className="layer-body">
                  <label className="layer-row">
                    <input type="checkbox" checked={layers.permits} onChange={e => setLayers(prev => ({ ...prev, permits: e.target.checked }))} />
                    <span className="layer-name">Budowy <span className="muted">kwadraty</span></span>
                  </label>
                  {layers.permits && permitLegend.map(([kind, count]) => (
                    <span key={kind} className="legend-row"><span className="legend-mark square" style={{ background: kindColors[kind] }} aria-hidden="true" />{kindPlural[kind]}<strong>{count}</strong></span>
                  ))}
                  <label className="layer-row">
                    <input type="checkbox" checked={layers.investments} onChange={e => setLayers(prev => ({ ...prev, investments: e.target.checked }))} />
                    <span className="layer-name">Inwestycje <span className="muted">koła</span></span>
                  </label>
                  {layers.investments && investmentLegend.map(([stage, count]) => (
                    <span key={stage} className="legend-row"><span className={`legend-mark circle${stage === "other" ? " hollow" : ""}`} style={{ background: mapStageColors[stage], borderColor: mapStageColors[stage] }} aria-hidden="true" />{mapStageLabels[stage]}<strong>{count}</strong></span>
                  ))}
                  <p className="legend-note">Liczby: obiekty na mapie. Kolor budowy = rodzaj wpisu, nie wynik decyzji. Liczba w kole = kilka obiektów obok siebie.</p>
                </div>
              )}
            </div>
          </div>
          <button type="button" className={`map-locate${userLocation ? " active" : ""}`} onClick={locate} disabled={locating}
            aria-label={locating ? "Ustalanie Twojego położenia…" : "Pokaż moje położenie na mapie"}
            title="Pokaż moje położenie (zostaje w przeglądarce)"
            style={mobile ? { bottom: Math.min(sheetHeight, sheetHeights.half) + 68 } : undefined}>
            {locating ? <span className="loading-ring small" aria-hidden="true" /> : (
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /><circle cx="12" cy="12" r="8" />
              </svg>
            )}
          </button>
          {locateMessage && (
            <p className="locate-message" role="status" style={mobile ? { bottom: Math.min(sheetHeight, sheetHeights.half) + 124 } : undefined}>{locateMessage}</p>
          )}
          <button ref={overview} type="button" className="map-overview" onClick={() => selectedOnMap ? setFitToken(n => n + 1) : setFitAllToken(n => n + 1)}
            style={mobile ? { bottom: Math.min(sheetHeight, sheetHeights.half) + 12 } : undefined}>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></svg>
            {selectedOnMap ? "Pokaż wybrany" : "Pokaż wszystkie"}
          </button>
        </section>
        <aside className={`panel sheet-${sheet}${dragHeight !== null ? " dragging" : ""}`} aria-label="Wyniki i szczegóły"
          style={mobile ? { height: sheetHeight } : undefined}>
          {mobile && (
            <button type="button" className="sheet-handle"
              aria-label={sheet === "full" ? "Zmniejsz panel" : "Powiększ panel"}
              onPointerDown={event => {
                drag.current = { y: event.clientY, height: sheetHeight, moved: false };
                event.currentTarget.setPointerCapture?.(event.pointerId);
              }}
              onPointerMove={event => {
                const state = drag.current;
                if (!state) return;
                const delta = state.y - event.clientY;
                if (Math.abs(delta) > 6) state.moved = true;
                if (state.moved) setDragHeight(Math.max(PEEK - 40, Math.min(sheetHeights.full, state.height + delta)));
              }}
              onPointerUp={() => {
                const state = drag.current;
                drag.current = null;
                if (state?.moved) {
                  suppressClick.current = true;
                  snapTo(dragHeight ?? state.height);
                }
                setDragHeight(null);
              }}
              onPointerCancel={() => { drag.current = null; setDragHeight(null); }}
              onClick={() => {
                if (suppressClick.current) { suppressClick.current = false; return; }
                setSheet(sheet === "peek" ? "half" : sheet === "half" ? "full" : "half");
              }}>
              <span aria-hidden="true" />
            </button>
          )}
          <div className="panel-tabs" role="group" aria-label="Rodzaj danych">
            <button type="button" aria-pressed={mode === "permits"} onClick={() => changeMode("permits")}>
              Budowy{permitReady && <span className="tab-count">{permits.counts.total}</span>}
            </button>
            <button type="button" aria-pressed={mode === "investments"} onClick={() => changeMode("investments")}>
              Inwestycje{investmentReady && <span className="tab-count">{investments.filtered.length}</span>}
            </button>
          </div>
          <div className="panel-body" ref={panelBody}>
            {selectedPermit ? (
              <PermitDetail record={selectedPermit} parcels={permits.data.parcels} onClose={close} onPick={pick}
                nearby={nearbyFor(permitGeo.get(selectedPermit.id)?.at)} share={share} isNew={permits.seen.newIds.has(selectedPermit.id)} />
            ) : selectedInvestment ? (
              <InvestmentDetail record={selectedInvestment} all={investments.all} onClose={close} onPick={pick}
                source={investments.data?.sources.find(s => s.id === selectedInvestment.sourceId)}
                nearbyPermits={nearbyFor(investmentGeo.get(selectedInvestment.id)?.at).permits}
                share={share} isNew={investments.seen.newIds.has(selectedInvestment.id)} />
            ) : mode === "permits" ? (
              <PermitList state={permits} selectedId={null} onSelect={id => select("permits", id, "list")}
                onSearchFocus={() => { if (mobile && sheet === "peek") setSheet("full"); }} />
            ) : (
              <InvestmentList state={investments} selectedId={null} onSelect={id => select("investments", id, "list")}
                onSearchFocus={() => { if (mobile && sheet === "peek") setSheet("full"); }}
                onAbout={() => { aboutOpener.current = document.activeElement as HTMLElement | null; setAbout(true); }} />
            )}
          </div>
        </aside>
      </main>
      {about && <AboutDialog permits={permits} investments={investments} onClose={() => { setAbout(false); aboutOpener.current?.focus(); }} />}
    </div>
  );
}
