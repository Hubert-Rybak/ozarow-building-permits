import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { Geometry } from "geojson";
import type { LatLng } from "./geo";
import "leaflet/dist/leaflet.css";

export type Layer = "permits" | "investments";
export interface MapItem {
  key: string;
  layer: Layer;
  id: string;
  at: LatLng;
  color: string;
  shape: "square" | "circle";
  hollow?: boolean;
  label: string;
  areas: Geometry[];
}
export interface Insets { left: number; top: number; bottom: number }
interface Props {
  items: MapItem[];
  selectedKey: string | null;
  onSelect: (layer: Layer, id: string) => void;
  insets: Insets;
  /** Increment to reframe: the selection if any, otherwise every item. */
  fitToken: number;
  /** Increment to show every item even while something is selected. */
  fitAllToken?: number;
}

const HOME: L.LatLngExpression = [52.21, 20.798];
const CELL = 54;
/** From this zoom parcels are big enough to see and tap, so markers give way to outlines. */
const AREA_ZOOM = 17;

function text(tag: string, className: string, value: string) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = value;
  return element;
}

function markerIcon(item: MapItem, selected: boolean) {
  const element = document.createElement("span");
  element.className = `radar-marker ${item.shape}${item.hollow ? " hollow" : ""}${selected ? " selected" : ""}`;
  element.style.setProperty("--marker", item.color);
  const size = selected ? 26 : 18;
  return L.divIcon({ html: element, className: "radar-marker-wrap", iconSize: [size, size] });
}

function clusterIcon(members: MapItem[]) {
  const counts = new Map<string, number>();
  for (const member of members) counts.set(member.color, (counts.get(member.color) || 0) + 1);
  let start = 0;
  const stops = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([color, count]) => {
      const end = start + (count / members.length) * 100;
      const stop = `${color} ${start}% ${end}%`;
      start = end;
      return stop;
    });
  const size = members.length < 10 ? 34 : members.length < 50 ? 40 : 46;
  const element = document.createElement("span");
  element.className = "radar-cluster";
  element.style.background = `conic-gradient(${stops.join(", ")})`;
  element.append(text("span", "radar-cluster-count", String(members.length)));
  return L.divIcon({ html: element, className: "radar-marker-wrap", iconSize: [size, size] });
}

export default function RadarMap({ items, selectedKey, onSelect, insets, fitToken, fitAllToken = 0 }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const drawn = useRef<L.LayerGroup | null>(null);
  const latest = useRef({ items, selectedKey, onSelect, insets });
  latest.current = { items, selectedKey, onSelect, insets };
  const redraw = useRef<() => void>(() => {});
  const fitted = useRef(false);
  const [tileError, setTileError] = useState(false);

  const padding = () => {
    const { left, top, bottom } = latest.current.insets;
    return {
      paddingTopLeft: [left + 28, top + 28] as L.PointExpression,
      paddingBottomRight: [28, bottom + 28] as L.PointExpression,
    };
  };
  const frame = (keys: "selection" | "all") => {
    const m = map.current;
    if (!m || !container.current || container.current.clientWidth === 0) return;
    m.invalidateSize({ animate: false });
    const { items: all, selectedKey: key } = latest.current;
    const chosen = keys === "selection" ? all.filter(item => item.key === key) : all;
    const bounds = L.latLngBounds([]);
    for (const item of chosen) {
      if (item.areas.length)
        for (const area of item.areas) bounds.extend(L.geoJSON(area).getBounds());
      else bounds.extend(item.at);
    }
    if (!bounds.isValid()) {
      if (keys === "all") m.setView(HOME, 12, { animate: false });
      return;
    }
    const pointsOnly = chosen.every(item => !item.areas.length);
    m.fitBounds(bounds, { ...padding(), maxZoom: keys === "selection" && !pointsOnly ? 18 : 16, animate: false });
  };

  useEffect(() => {
    if (!container.current) return;
    const m = L.map(container.current, { zoomControl: false, zoomSnap: 0.5, attributionControl: true })
      .setView(HOME, 12);
    map.current = m;
    L.control.zoom({ position: "topright", zoomInTitle: "Przybliż", zoomOutTitle: "Oddal" }).addTo(m);
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> · działki: ULDK',
    }).addTo(m);
    let failed = 0;
    tiles.on("tileerror", () => { if (++failed >= 3) setTileError(true); });
    tiles.on("tileload", () => { failed = 0; setTileError(false); });
    drawn.current = L.layerGroup().addTo(m);
    const update = () => redraw.current();
    m.on("zoomend moveend", update);
    const observer = new ResizeObserver(() => m.invalidateSize({ animate: false }));
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      m.remove();
      map.current = null;
      drawn.current = null;
      fitted.current = false;
    };
  }, []);

  redraw.current = () => {
    const m = map.current, group = drawn.current;
    if (!m || !group) return;
    group.clearLayers();
    const { items: all, selectedKey: key } = latest.current;
    const zoom = m.getZoom();
    const view = m.getBounds().pad(0.25);
    const choose = (item: MapItem) => () => latest.current.onSelect(item.layer, item.id);
    // Outlines: every visible area from AREA_ZOOM - 1, and the selection at any zoom.
    for (const item of all) {
      const selected = item.key === key;
      if (!item.areas.length || (!selected && zoom < AREA_ZOOM - 1)) continue;
      if (!selected && !view.contains(item.at)) continue;
      const shape = L.geoJSON(item.areas as never, {
        style: {
          color: selected ? "#0B1620" : item.color,
          weight: selected ? 4 : 2,
          fillColor: item.color,
          fillOpacity: selected ? 0.38 : 0.2,
          dashArray: item.hollow ? "5 4" : undefined,
        },
        interactive: true,
      });
      shape.eachLayer(layer => {
        layer.on("click", choose(item));
        layer.bindTooltip(text("span", "", item.label), { sticky: true });
      });
      shape.addTo(group);
      if (selected) shape.eachLayer(layer => (layer as L.Path).bringToFront?.());
    }
    // Markers: hidden behind their outlines once those are large enough to tap.
    const points = all.filter(item =>
      item.key !== key && view.contains(item.at) && (zoom < AREA_ZOOM || !item.areas.length));
    const cells = new Map<string, MapItem[]>();
    for (const item of points) {
      const p = m.project(item.at, zoom);
      const cell = `${Math.floor(p.x / CELL)}:${Math.floor(p.y / CELL)}`;
      cells.set(cell, [...(cells.get(cell) || []), item]);
    }
    for (const members of cells.values()) {
      if (members.length === 1) {
        const item = members[0];
        const marker = L.marker(item.at, { icon: markerIcon(item, false), keyboard: false, riseOnHover: true });
        marker.bindTooltip(text("span", "", item.label), { direction: "top", offset: [0, -8] });
        marker.on("click", choose(item));
        marker.addTo(group);
        continue;
      }
      const bounds = L.latLngBounds(members.map(member => member.at));
      const center = bounds.getCenter();
      const cluster = L.marker(center, { icon: clusterIcon(members), keyboard: false, riseOnHover: true });
      cluster.bindTooltip(text("span", "", `${members.length} obiektów — przybliż`), { direction: "top", offset: [0, -14] });
      const sameSpot = m.project(bounds.getNorthEast(), 18).distanceTo(m.project(bounds.getSouthWest(), 18)) < 8;
      if (sameSpot || zoom >= 18) {
        const list = document.createElement("div");
        list.className = "cluster-popup";
        list.append(text("strong", "", `${members.length} wpisów w tym miejscu`));
        for (const member of members.slice(0, 12)) {
          const button = text("button", "", member.label) as HTMLButtonElement;
          button.type = "button";
          button.addEventListener("click", () => { m.closePopup(); choose(member)(); });
          list.append(button);
        }
        cluster.bindPopup(list, { maxWidth: 300 });
      } else
        cluster.on("click", () => m.fitBounds(bounds, { ...padding(), maxZoom: 18, animate: true }));
      cluster.addTo(group);
    }
    const selected = all.find(item => item.key === key);
    if (selected && (zoom < AREA_ZOOM - 1 || !selected.areas.length)) {
      const marker = L.marker(selected.at, { icon: markerIcon(selected, true), keyboard: false, zIndexOffset: 1000 });
      marker.bindTooltip(text("span", "", selected.label), { direction: "top", offset: [0, -12] });
      marker.addTo(group);
    }
  };

  useEffect(() => {
    if (!fitted.current && items.length && container.current?.clientWidth) {
      fitted.current = true;
      frame(selectedKey ? "selection" : "all");
    }
    redraw.current();
  }, [items, selectedKey]);
  useEffect(() => {
    if (fitToken) frame(latest.current.selectedKey ? "selection" : "all");
  }, [fitToken]);
  useEffect(() => {
    if (fitAllToken) frame("all");
  }, [fitAllToken]);

  return (
    <div className="map-shell">
      <div ref={container} className="leaflet-map" aria-label="Mapa Ożarowa Mazowieckiego z budowami i inwestycjami" />
      {tileError && (
        <p className="tile-warning" role="status">Podkład OSM jest niedostępny. Punkty i lista nadal działają.</p>
      )}
    </div>
  );
}
