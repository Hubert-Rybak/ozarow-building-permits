import { fireEvent, render } from "@testing-library/react";
import L from "leaflet";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RadarMap, { type MapItem } from "../../src/RadarMap";

// Test-only items; Leaflet, its markers, SVG renderer and events are real.
const item = (id: string, at: [number, number], extra: Partial<MapItem> = {}): MapItem => ({
  key: `p:${id}`, layer: "permits", id, at, color: "#2B5C8A", shape: "square",
  label: `<img src=x onerror="alert(1)"> TEST ${id}`, areas: [], ...extra,
});
const square = (lon: number, lat: number, d = 0.0004) => ({
  type: "Polygon" as const,
  coordinates: [[[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]],
});
const svgCapability = Object.getOwnPropertyDescriptor(L.Browser, "svg")!;
beforeEach(() => {
  Object.defineProperty(L.Browser, "svg", { ...svgCapability, value: true });
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(800);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.stubGlobal("ResizeObserver", class { observe = vi.fn(); disconnect = vi.fn(); });
});
afterEach(() => {
  Object.defineProperty(L.Browser, "svg", svgCapability);
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function mount(items: MapItem[], selectedKey: string | null = null) {
  const mapFactory = vi.spyOn(L, "map");
  const onSelect = vi.fn();
  const props = { items, selectedKey, onSelect, insets: { left: 0, top: 0, bottom: 0 }, fitToken: 0 };
  const view = render(<RadarMap {...props} />);
  const map = mapFactory.mock.results[0].value as L.Map;
  return { ...view, props, map, onSelect, mapFactory };
}

describe("unified radar map", () => {
  it("draws separate markers without per-marker tab stops and selects on click", () => {
    const v = mount([item("a", [52.2, 20.7]), item("b", [52.25, 20.9])]);
    const markers = v.container.querySelectorAll(".radar-marker");
    expect(markers).toHaveLength(2);
    for (const marker of v.container.querySelectorAll(".leaflet-marker-icon"))
      expect(marker).not.toHaveAttribute("tabindex");
    expect(v.container.querySelectorAll('[tabindex="0"]').length).toBeLessThanOrEqual(1);
    fireEvent.click(v.container.querySelectorAll(".leaflet-marker-icon")[0]);
    expect(v.onSelect).toHaveBeenCalledTimes(1);
    expect(["a", "b"]).toContain(v.onSelect.mock.calls[0][1]);
    expect(v.onSelect.mock.calls[0][0]).toBe("permits");
  });

  it("clusters nearby objects into one counted symbol and zooms into it", () => {
    const v = mount([item("a", [52.2, 20.8]), item("b", [52.2004, 20.8004]), item("c", [52.25, 20.95])]);
    const cluster = v.container.querySelector(".radar-cluster");
    expect(cluster).toHaveTextContent("2");
    const fit = vi.spyOn(v.map, "fitBounds");
    fireEvent.click(cluster!.closest(".leaflet-marker-icon")!);
    expect(fit).toHaveBeenCalled();
  });

  it("lists records sharing one spot instead of zooming forever, using text nodes only", () => {
    const v = mount([item("a", [52.2, 20.8]), item("b", [52.2, 20.8])]);
    fireEvent.click(v.container.querySelector(".radar-cluster")!.closest(".leaflet-marker-icon")!);
    const popup = v.container.querySelector(".cluster-popup")!;
    expect(popup.querySelectorAll("button")).toHaveLength(2);
    expect(popup.querySelector("img")).toBeNull();
    fireEvent.click(popup.querySelectorAll("button")[1]);
    expect(v.onSelect).toHaveBeenCalledWith("permits", "b");
  });

  it("frames and outlines the selected parcel at any zoom, then reframes on request without recreating the map", () => {
    const v = mount([item("a", [52.2, 20.8], { areas: [square(20.8, 52.2)] }), item("b", [52.3, 20.9])]);
    const fit = vi.spyOn(v.map, "fitBounds");
    v.rerender(<RadarMap {...v.props} selectedKey="p:a" fitToken={1} />);
    const bounds = fit.mock.calls.at(-1)![0] as L.LatLngBounds;
    expect(bounds.contains([52.2002, 20.8002])).toBe(true);
    expect(v.container.querySelector('path[stroke-width="4"]')).not.toBeNull();
    v.rerender(<RadarMap {...v.props} selectedKey={null} fitToken={2} />);
    expect(v.container.querySelector('path[stroke-width="4"]')).toBeNull();
    expect(v.mapFactory).toHaveBeenCalledTimes(1);
  });

  it("draws the viewer's position with its accuracy and frames it, without making it clickable", () => {
    const v = mount([item("a", [52.3, 20.9])]);
    const fit = vi.spyOn(v.map, "fitBounds");
    v.rerender(<RadarMap {...v.props} userLocation={{ at: [52.21, 20.8], accuracy: 30, token: 1 }} />);
    const dot = v.container.querySelector("path.user-location");
    expect(dot).not.toBeNull();
    expect(dot).not.toHaveClass("leaflet-interactive");
    expect((fit.mock.calls.at(-1)![0] as L.LatLngBounds).contains([52.21, 20.8])).toBe(true);
    v.rerender(<RadarMap {...v.props} userLocation={null} />);
    expect(v.container.querySelector("path.user-location")).toBeNull();
  });

  it("removes old symbols on filtering and cleans up on unmount", () => {
    const v = mount([item("a", [52.2, 20.7]), item("b", [52.25, 20.9])]);
    const remove = vi.spyOn(v.map, "remove");
    v.rerender(<RadarMap {...v.props} items={[]} />);
    expect(v.container.querySelectorAll(".radar-marker, .radar-cluster")).toHaveLength(0);
    v.unmount();
    expect(remove).toHaveBeenCalledTimes(1);
  });
});
