import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import {
  getRecordParcels,
  kindLabels,
  semanticStatus,
  statusColors,
  statusLabels,
} from "./model";
import type {
  ParcelCollection,
  ParcelFeature,
  Permit,
  SemanticStatus,
} from "./types";
import "leaflet/dist/leaflet.css";

interface Props {
  records: Permit[];
  parcels: ParcelCollection;
  selectedId: string | null;
  onSelect: (id: string) => void;
  visible: boolean;
}
export default function ParcelMap({
  records,
  parcels,
  selectedId,
  onSelect,
  visible,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layers = useRef<L.GeoJSON | null>(null);
  const current = useRef({ selectedId, onSelect });
  current.current = { selectedId, onSelect };
  const featureRecords = useRef(new Map<string, Permit[]>());
  const [tileError, setTileError] = useState(false);
  const [overview, setOverview] = useState(0);
  const fitted = useRef(false);
  useEffect(() => {
    if (!container.current) return;
    const map = L.map(container.current, {
      zoomControl: false,
      scrollWheelZoom: false,
    }).setView([52.21, 20.798], 13);
    mapRef.current = map;
    L.control.zoom({ position: "topright" }).addTo(map);
    const tiles = L.tileLayer(
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
      },
    ).addTo(map);
    let failed = 0;
    tiles.on("tileerror", () => {
      failed += 1;
      if (failed >= 3) setTileError(true);
    });
    tiles.on("tileload", () => {
      failed = 0;
      setTileError(false);
    });
    const observer = new ResizeObserver(() =>
      map.invalidateSize({ animate: false }),
    );
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      fitted.current = false;
    };
  }, []);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    layers.current?.remove();
    const features = new Map<string, ParcelFeature>();
    const byFeature = new Map<string, Permit[]>();
    for (const record of records)
      for (const feature of getRecordParcels(record, parcels)) {
        features.set(feature.properties.id, feature);
        byFeature.set(feature.properties.id, [
          ...(byFeature.get(feature.properties.id) || []),
          record,
        ]);
      }
    featureRecords.current = byFeature;
    const collection: ParcelCollection = {
      type: "FeatureCollection",
      features: [...features.values()],
    };
    const group = L.geoJSON(collection, {
      style: (feature) => {
        const related = byFeature.get(feature?.properties.id) || [];
        const tones = new Set(related.map(semanticStatus));
        const tone: SemanticStatus =
          tones.size === 1 ? semanticStatus(related[0]) : "unknown";
        return {
          color: statusColors[tone],
          fillColor: statusColors[tone],
          weight: 2,
          fillOpacity: 0.28,
        };
      },
      onEachFeature: (feature, layer) => {
        const related = byFeature.get(feature.properties.id) || [];
        const tooltip = document.createElement("span");
        tooltip.textContent = `Działka ${feature.properties.parcelNumber} · ${related.length} wpisów`;
        layer.bindTooltip(tooltip, { sticky: true });
        // Use DOM text nodes, never interpolated HTML from external data.
        const popup = document.createElement("div");
        popup.className = "parcel-popup";
        const title = document.createElement("strong");
        title.textContent = `Działka ${feature.properties.parcelNumber}`;
        popup.append(title);
        const note = document.createElement("p");
        note.textContent = feature.properties.id;
        popup.append(note);
        for (const record of related) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = `${kindLabels[record.kind]} · ${record.title || "Bez tytułu"}`;
          button.addEventListener("click", () =>
            current.current.onSelect(record.id),
          );
          popup.append(button);
        }
        layer.bindPopup(popup, { maxWidth: 300 });
        const choose = () => {
          const preferred =
            related.find((r) => r.id === current.current.selectedId) ||
            related[0];
          if (preferred) current.current.onSelect(preferred.id);
        };
        layer.on("click", choose);
        layer.on("add", () => {
          const element = (layer as L.Path).getElement();
          if (element) {
            element.setAttribute("tabindex", "0");
            element.setAttribute("role", "button");
            element.setAttribute(
              "aria-label",
              `Działka ${feature.properties.parcelNumber}, ${related.length} wpisów — pokaż szczegóły`,
            );
            element.setAttribute("data-parcel-id", feature.properties.id);
            element.addEventListener("keydown", (event) => {
              const key = (event as KeyboardEvent).key;
              if (key === "Enter" || key === " ") {
                event.preventDefault();
                choose();
                layer.openPopup();
              }
            });
          }
        });
      },
    }).addTo(map);
    layers.current = group;
    if (!fitted.current && group.getBounds().isValid()) {
      map.fitBounds(group.getBounds(), {
        padding: [32, 32],
        maxZoom: 15,
        animate: false,
      });
      fitted.current = true;
    }
    return () => {
      group.remove();
    };
  }, [records, parcels]);
  useEffect(() => {
    const map = mapRef.current;
    const group = layers.current;
    if (!map || !group) return;
    const selectedBounds = L.latLngBounds([]);
    group.eachLayer((layer) => {
      const path = layer as L.Polygon & { feature: ParcelFeature };
      const related =
        featureRecords.current.get(path.feature.properties.id) || [];
      const selected = related.some((r) => r.id === selectedId);
      const tones = new Set(related.map(semanticStatus));
      const tone = tones.size === 1 ? semanticStatus(related[0]) : "unknown";
      path.setStyle({
        color: selected ? "#142f3b" : statusColors[tone],
        weight: selected ? 4 : 2,
        fillOpacity: selected ? 0.48 : 0.28,
      });
      path.getElement()?.setAttribute("aria-pressed", String(selected));
      if (selected) {
        path.bringToFront();
        selectedBounds.extend(path.getBounds());
      }
    });
    map.invalidateSize({ animate: false });
    if (
      selectedBounds.isValid() &&
      container.current &&
      container.current.clientWidth > 0
    )
      map.fitBounds(selectedBounds, {
        padding: [48, 48],
        maxZoom: 18,
        animate: false,
      });
  }, [selectedId, records, parcels, visible]);
  useEffect(() => {
    if (!overview || !mapRef.current || !layers.current) return;
    const bounds = layers.current.getBounds();
    if (bounds.isValid())
      mapRef.current.fitBounds(bounds, {
        padding: [32, 32],
        maxZoom: 16,
        animate: false,
      });
    else mapRef.current.setView([52.21, 20.798], 13, { animate: false });
  }, [overview]);
  return (
    <div className="map-shell">
      <div
        ref={container}
        className="leaflet-map"
        aria-label="Interaktywna mapa Ożarowa Mazowieckiego"
      />
      <button
        className="map-overview"
        onClick={() => setOverview((n) => n + 1)}
        title="Pokaż wszystkie działki z wyników"
      >
        <span aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            width="17"
            height="17"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
          >
            <circle cx="12" cy="12" r="6" />
            <path d="M12 2v6M12 16v6M2 12h6M16 12h6" />
          </svg>
        </span>{" "}
        Pokaż wyniki
      </button>
      <details className="map-legend" open>
        <summary>Legenda mapy</summary>
        <ul>
          {(Object.keys(statusLabels) as SemanticStatus[]).map((status) => (
            <li key={status}>
              <span
                style={{ backgroundColor: statusColors[status] }}
                aria-hidden="true"
              />
              {statusLabels[status]}
            </li>
          ))}
        </ul>
        <p>Kolor nie oznacza rozpoczęcia budowy.</p>
      </details>
      {tileError && (
        <p className="tile-warning" role="status">
          Podkład OSM jest niedostępny. Obrysy i lista nadal działają.
        </p>
      )}
    </div>
  );
}
