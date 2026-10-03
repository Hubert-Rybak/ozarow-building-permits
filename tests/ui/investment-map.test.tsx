import { fireEvent, render } from "@testing-library/react";
import L from "leaflet";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InvestmentsMap from "../../src/InvestmentsMap";
import { accuracyLabels, type InvestmentRecord } from "../../src/investments";

// Test-only records; Leaflet, its FeatureGroups, SVG renderer and events are real.
function record(id = "test:multipoint"): InvestmentRecord {
  return {
    id,
    sourceId: "test",
    sourceRecordId: id,
    sourceUrl: "https://example.org/test",
    title: '<img src=x onerror="alert(1)"> TEST ONLY',
    recordType: "proposal",
    investor: "municipal",
    investorName: null,
    category: "TEST ONLY",
    locality: "TEST ONLY",
    address: "",
    status: "TEST ONLY",
    statusAsOf: null,
    summary: "",
    years: [],
    costs: [],
    dates: [],
    geometries: [{
      type: "Feature",
      geometry: {
        type: "MultiPoint",
        coordinates: [[20.8, 52.2], [20.81, 52.21]],
      },
      properties: {
        id: "test:shared-geometry",
        accuracy: "source-point",
        sourceUrl: "https://example.org/test",
        parcelId: null,
        note: "TEST ONLY",
        fetchedAt: "2026-10-01T10:00:00Z",
        sourceUpdatedAt: null,
      },
    }],
    parcelIds: [],
    events: [],
    facts: [],
    relatedIds: [],
    warnings: [],
    fetchedAt: "2026-10-01T10:00:00Z",
    sourceUpdatedAt: null,
  };
}

const svgCapability = Object.getOwnPropertyDescriptor(L.Browser, "svg")!;
beforeEach(() => {
  // jsdom has SVG elements but not createSVGRect/layout/ResizeObserver.
  // Only shim those browser capabilities; do not replace any Leaflet layer.
  Object.defineProperty(L.Browser, "svg", { ...svgCapability, value: true });
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.stubGlobal("ResizeObserver", class {
    observe = vi.fn();
    disconnect = vi.fn();
  });
});
afterEach(() => {
  Object.defineProperty(L.Browser, "svg", svgCapability);
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function mount(records: InvestmentRecord[]) {
  const mapFactory = vi.spyOn(L, "map");
  const geoFactory = vi.spyOn(L, "geoJSON");
  const onSelect = vi.fn();
  const props = { records, selectedId: null as string | null, selectionToken: 0,
    onSelect, visible: true, active: true };
  const view = render(<InvestmentsMap {...props} />);
  const map = mapFactory.mock.results[0].value as L.Map;
  const geo = geoFactory.mock.results[0].value as L.GeoJSON;
  const multipoint = geo.getLayers()[0] as L.FeatureGroup;
  const children = multipoint.getLayers() as L.CircleMarker[];
  const paths = children.map((child) => child.getElement() as SVGPathElement);
  return { ...view, props, map, mapFactory, geoFactory, multipoint, children, paths, onSelect };
}

describe("real Leaflet investment MultiPoint", () => {
  it("renders every real child with shared identity, safe tooltip and one selection per activation", () => {
    const r = record();
    const v = mount([r]);
    expect(v.multipoint).toBeInstanceOf(L.FeatureGroup);
    expect(v.multipoint).not.toBeInstanceOf(L.Path);
    expect("getElement" in v.multipoint).toBe(false);
    expect(v.children).toHaveLength(2);
    expect(v.container.querySelectorAll("svg path.leaflet-interactive")).toHaveLength(2);
    const label = `${r.title} · ${accuracyLabels["source-point"]}`;
    for (const [i, path] of v.paths.entries()) {
      expect(v.children[i]).toBeInstanceOf(L.CircleMarker);
      expect(path).toBeInstanceOf(SVGElement);
      expect(path.getAttribute("d")).toContain("a11,11");
      expect(path).toHaveAttribute("tabindex", "0");
      expect(path).toHaveAttribute("role", "button");
      expect(path).toHaveAttribute("aria-label", `${label} — szczegóły`);
      expect(path).toHaveAttribute("data-investment-id", r.id);
      expect(path).toHaveAttribute("data-geometry-id", r.geometries[0].properties.id);
      expect(path).toHaveAttribute("data-accuracy", "source-point");
      expect(path).toHaveAttribute("aria-pressed", "false");
      path.focus();
      expect(document.activeElement).toBe(path);
      const tooltip = v.container.querySelector(".leaflet-tooltip");
      expect(tooltip).toHaveTextContent(label);
      expect(tooltip?.querySelector("img")).toBeNull();
      expect(tooltip?.firstElementChild?.firstChild?.nodeType).toBe(Node.TEXT_NODE);
      path.blur();
      expect(v.container.querySelector(".leaflet-tooltip")).toBeNull();
      for (const activate of [
        () => fireEvent.click(path),
        // Browsers synthesize a click for a touch activation; native touch is
        // additionally exercised by the Chromium mobile acceptance harness.
        () => { fireEvent.touchStart(path); fireEvent.touchEnd(path); fireEvent.click(path); },
        () => fireEvent.keyDown(path, { key: "Enter" }),
        () => fireEvent.keyDown(path, { key: " " }),
      ]) {
        v.onSelect.mockClear();
        activate();
        expect(v.onSelect).toHaveBeenCalledExactlyOnceWith(r.id);
      }
      v.onSelect.mockClear();
      fireEvent.keyDown(path, { key: "Escape" });
      expect(v.onSelect).not.toHaveBeenCalled();
      expect(fireEvent.keyDown(path, { key: " ", cancelable: true })).toBe(false);
    }
  });

  it("keeps every child focusable while repeatedly selecting, styling and framing without recreating the map", () => {
    const r = record(), other = record("test:other");
    other.geometries = [{ ...other.geometries[0],
      geometry: { type: "Point", coordinates: [20.82, 52.22] } }];
    const v = mount([r, other]);
    const fit = vi.spyOn(v.map, "fitBounds");
    const pane = v.container.querySelector(".leaflet-map-pane");
    const callback = vi.fn();
    for (let token = 1; token <= 2; token++) {
      v.rerender(<InvestmentsMap {...v.props} selectedId={r.id} selectionToken={token} onSelect={callback} />);
      for (const path of v.paths) {
        expect(path).toHaveAttribute("aria-pressed", "true");
        expect(path).toHaveAttribute("stroke-width", "5");
        expect(path).toHaveAttribute("fill-opacity", "0.72");
        path.focus();
        expect(document.activeElement).toBe(path);
      }
      expect([...v.container.querySelectorAll("path.leaflet-interactive")].slice(-2)).toEqual(v.paths);
      const bounds = fit.mock.calls.at(-1)![0] as L.LatLngBounds;
      for (const child of v.children) expect(bounds.contains(child.getLatLng())).toBe(true);
      fireEvent.keyDown(v.paths[0], { key: "Enter" });
      expect(callback).toHaveBeenCalledTimes(token);
      expect(v.onSelect).not.toHaveBeenCalled();
    }
    expect(fit).toHaveBeenCalledTimes(2);
    v.rerender(<InvestmentsMap {...v.props} selectedId={null} selectionToken={2} />);
    for (const path of v.paths) {
      expect(path).toHaveAttribute("aria-pressed", "false");
      expect(path).toHaveAttribute("stroke-width", "2");
      expect(path).toHaveAttribute("fill-opacity", "0.24");
    }
    expect(fit).toHaveBeenCalledTimes(2);
    v.rerender(<InvestmentsMap {...v.props} visible={false} active={false} />);
    v.rerender(<InvestmentsMap {...v.props} />);
    expect(v.mapFactory).toHaveBeenCalledTimes(1);
    expect(v.geoFactory).toHaveBeenCalledTimes(2);
    expect(v.container.querySelector(".leaflet-map-pane")).toBe(pane);
    for (const path of v.paths) expect(path.isConnected).toBe(true);
  });

  it("removes all old child paths and tooltips on filtering and cleans up the real map on unmount", () => {
    const r = record();
    const v = mount([r]);
    const remove = vi.spyOn(v.map, "remove");
    v.paths[0].focus();
    expect(v.container.querySelector(".leaflet-tooltip")).not.toBeNull();
    v.rerender(<InvestmentsMap {...v.props} records={[]} />);
    for (const path of v.paths) expect(path.isConnected).toBe(false);
    for (const child of v.children) expect(v.map.hasLayer(child)).toBe(false);
    expect(v.container.querySelectorAll("path.leaflet-interactive")).toHaveLength(0);
    expect(v.container.querySelector(".leaflet-tooltip")).toBeNull();
    v.rerender(<InvestmentsMap {...v.props} />);
    const newPaths = v.container.querySelectorAll("path.leaflet-interactive");
    expect(newPaths).toHaveLength(2);
    expect(newPaths[0]).not.toBe(v.paths[0]);
    fireEvent.keyDown(newPaths[0], { key: "Enter" });
    expect(v.onSelect).toHaveBeenCalledExactlyOnceWith(r.id);
    expect(v.mapFactory).toHaveBeenCalledTimes(1);
    v.unmount();
    expect(remove).toHaveBeenCalledTimes(1);
    expect(v.map.getContainer().querySelector(".leaflet-map-pane")).toBeNull();
  });
});
