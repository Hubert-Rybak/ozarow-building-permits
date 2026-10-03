import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { accuracyLabels, type InvestmentRecord } from "./investments";
import "leaflet/dist/leaflet.css";
interface Props {
  records: InvestmentRecord[];
  selectedId: string | null;
  selectionToken: number;
  onSelect: (id: string) => void;
  visible: boolean;
  active: boolean;
}
export default function InvestmentsMap({
  records,
  selectedId,
  selectionToken,
  onSelect,
  visible,
  active,
}: Props) {
  const container = useRef<HTMLDivElement>(null),
    map = useRef<L.Map | null>(null),
    group = useRef<L.FeatureGroup | null>(null);
  const layers = useRef<{ recordId: string; layer: L.GeoJSON }[]>([]),
    current = useRef(onSelect);
  current.current = onSelect;
  const [tileError, setTileError] = useState(false),
    [overview, setOverview] = useState(0);
  const previousFrame = useRef<{
    records: InvestmentRecord[];
    token: number;
    visible: boolean;
    active: boolean;
  } | null>(null);
  const fit = (bounds: L.LatLngBounds, maxZoom = 16) => {
    const m = map.current;
    if (!m) return;
    m.invalidateSize({ animate: false });
    if (bounds.isValid())
      m.fitBounds(bounds, {
        paddingTopLeft: [54, 64],
        paddingBottomRight: [54, 84],
        maxZoom,
        animate: false,
      });
    else m.setView([52.21, 20.798], 13, { animate: false });
  };
  useEffect(() => {
    if (!container.current) return;
    const m = L.map(container.current, {
      zoomControl: false,
      scrollWheelZoom: false,
    }).setView([52.21, 20.798], 13);
    map.current = m;
    L.control.zoom({ position: "topright" }).addTo(m);
    let failed = 0;
    const tiles = L.tileLayer(
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
      },
    ).addTo(m);
    tiles.on("tileerror", () => {
      if (++failed >= 3) setTileError(true);
    });
    tiles.on("tileload", () => {
      failed = 0;
      setTileError(false);
    });
    const observer = new ResizeObserver(() =>
      m.invalidateSize({ animate: false }),
    );
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      m.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    group.current?.remove();
    const all = L.featureGroup().addTo(m);
    group.current = all;
    layers.current = [];
    for (const record of records)
      for (const feature of record.geometries) {
        const precision = feature.properties.accuracy,
          color =
            precision === "route"
              ? "#985928"
              : precision === "parcel"
                ? "#367257"
                : precision === "marketing"
                  ? "#8057a0"
                  : "#155cc3";
        const choose = () => current.current(record.id);
        const leaf = L.geoJSON(feature, {
          style: {
            color,
            weight: precision === "route" ? 5 : 2,
            fillColor: color,
            fillOpacity: 0.24,
            dashArray: precision === "marketing" ? "6 4" : undefined,
          },
          pointToLayer: (_f, latlng) =>
            L.circleMarker(latlng, {
              radius: 11,
              color,
              weight: 3,
              fillColor: color,
              fillOpacity: 0.65,
            }),
          onEachFeature: (_f, layer) => {
            const tooltip = document.createElement("span");
            tooltip.textContent = `${record.title || "Bez tytułu"} · ${accuracyLabels[precision]}`;
            layer.bindTooltip(tooltip, { sticky: true });
            layer.on("click", choose);
            layer.on("add", () => {
              const decorate = (target: L.Layer) => {
                // GeoJSON MultiPoint is a FeatureGroup, not an SVG Path.
                if (target instanceof L.LayerGroup) {
                  target.eachLayer(decorate);
                  return;
                }
                if (!(target instanceof L.Path)) return;
                const element = target.getElement();
                if (!element) return;
                element.setAttribute("tabindex", "0");
                element.setAttribute("role", "button");
                element.setAttribute(
                  "aria-label",
                  `${record.title || "Bez tytułu"} · ${accuracyLabels[precision]} — szczegóły`,
                );
                element.setAttribute("data-investment-id", record.id);
                element.setAttribute("data-geometry-id", feature.properties.id);
                element.setAttribute("data-accuracy", precision);
                element.addEventListener("keydown", (event) => {
                  const key = (event as KeyboardEvent).key;
                  if (key === "Enter" || key === " ") {
                    event.preventDefault();
                    choose();
                  }
                });
              };
              decorate(layer);
            });
          },
        }).addTo(all);
        layers.current.push({ recordId: record.id, layer: leaf });
      }
    return () => {
      all.remove();
    };
  }, [records]);
  useEffect(() => {
    const prior = previousFrame.current;
    previousFrame.current = { records, token: selectionToken, visible, active };
    if (!map.current || !active) return;
    const bounds = L.latLngBounds([]);
    for (const entry of layers.current) {
      const selected = entry.recordId === selectedId;
      entry.layer.setStyle({
        weight: selected ? 5 : 2,
        fillOpacity: selected ? 0.72 : 0.24,
      });
      const mark = (layer: L.Layer) => {
        if (layer instanceof L.LayerGroup) {
          layer.eachLayer(mark);
          return;
        }
        const path = layer as L.Path;
        path.getElement()?.setAttribute("aria-pressed", String(selected));
        if (selected) path.bringToFront();
      };
      entry.layer.eachLayer(mark);
      if (selected) bounds.extend(entry.layer.getBounds());
    }
    // Closing details clears styling, not the camera. Filters, repeat selection and reactivation reframe.
    const shouldFit =
      !!selectedId ||
      !prior ||
      prior.records !== records ||
      prior.token !== selectionToken ||
      prior.visible !== visible ||
      !prior.active;
    if (shouldFit && container.current && container.current.clientWidth > 0)
      fit(
        bounds.isValid()
          ? bounds
          : group.current?.getBounds() || L.latLngBounds([]),
        bounds.isValid() ? 17 : 15,
      );
  }, [records, selectedId, selectionToken, visible, active]);
  useEffect(() => {
    if (overview) fit(group.current?.getBounds() || L.latLngBounds([]), 15);
  }, [overview]);
  return (
    <div className="map-shell">
      <div
        ref={container}
        className="leaflet-map"
        aria-label="Interaktywna mapa inwestycji"
      />
      <button
        className="map-overview"
        onClick={() => setOverview((n) => n + 1)}
      >
        Pokaż wyniki inwestycji
      </button>
      <details className="map-legend">
        <summary>Legenda inwestycji</summary>
        <ul>
          {Object.entries(accuracyLabels).map(([id, label]) => (
            <li key={id}>
              <span className={`precision-${id}`} aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
        <p>Położenie nie potwierdza rozpoczęcia prac.</p>
      </details>
      {tileError && (
        <p className="tile-warning" role="status">
          Podkład OSM jest niedostępny. Geometrie i lista nadal działają.
        </p>
      )}
    </div>
  );
}
