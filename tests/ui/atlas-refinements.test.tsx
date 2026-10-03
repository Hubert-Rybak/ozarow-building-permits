import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../../src/App";
import { readFileSync } from "node:fs";
const styles = readFileSync("src/styles.css", "utf8");
import { dataset, metadata, parcels } from "./fixtures";

vi.mock("../../src/ParcelMap", () => ({
  default: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <div className="leaflet-map">
      <button className="map-overview">Pokaż wyniki</button>
      <button onClick={() => onSelect("test-application")}>Wybierz działkę testową</button>
    </div>
  ),
}));
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
async function load(mobile = false) {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: mobile })));
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes("permits.json") ? dataset : url.includes("parcels.geojson") ? parcels : metadata })));
  const view = render(<App />);
  await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
  fireEvent.change(screen.getByLabelText("Okres"), { target: { value: "all" } });
  return view;
}
it("keeps auxiliary text at least 11px, mobile search 16px and a 44px input target", () => {
  const sizes = Array.from(styles.matchAll(/font-size:\s*(\d+)px/g), match => Number(match[1]));
  expect(sizes.filter(size => size > 0 && size < 11)).toEqual([]);
  const mobile = styles.slice(styles.indexOf("@media (max-width: 720px)"));
  expect(mobile).toMatch(/\.search-input input\s*\{\s*font-size:\s*16px/);
  expect(styles).toMatch(/\.search-input input\s*\{[^}]*min-height:\s*44px/);
});
it("puts the actual record source before descriptions, facts and long parcel identifiers", async () => {
  const { container } = await load();
  fireEvent.click(screen.getByRole("button", { name: /TEST: budowa domu/ }));
  const source = screen.getByRole("link", { name: "Wpis w źródle" });
  expect(source).toHaveAttribute("href", dataset.records[0].sourceUrl);
  for (const selector of [".description", ".detail-grid", ".parcel-list code"]) {
    expect(source.compareDocumentPosition(container.querySelector(selector)! ) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  }
  expect(screen.getByRole("link", { name: "Źródło geometrii" })).toHaveAttribute("href", parcels.features[0].properties.sourceUrl);
  expect(screen.getByText("Wniosek nie jest pozwoleniem na budowę.")).toBeInTheDocument();
});
it.each(["close", "Escape"])("returns desktop row selection to its origin via %s", async action => {
  const { container } = await load();
  const map = container.querySelector(".leaflet-map");
  const row = screen.getByRole("button", { name: /TEST: budowa domu/ });
  fireEvent.click(row);
  screen.getByRole("button", { name: "Zamknij szczegóły" }).focus();
  if (action === "Escape") fireEvent.keyDown(document, { key: "Escape" });
  else fireEvent.click(screen.getByRole("button", { name: "Zamknij szczegóły" }));
  expect(row).toHaveFocus();
  expect(container.querySelector(".detail-panel")).not.toBeInTheDocument();
  expect(container.querySelector(".leaflet-map")).toBe(map);
});
it.each(["close", "Escape"])("returns desktop polygon selection to the map via %s", async action => {
  await load();
  fireEvent.click(screen.getByRole("button", { name: "Wybierz działkę testową" }));
  screen.getByRole("button", { name: "Zamknij szczegóły" }).focus();
  if (action === "Escape") fireEvent.keyDown(document, { key: "Escape" });
  else fireEvent.click(screen.getByRole("button", { name: "Zamknij szczegóły" }));
  expect(screen.getByRole("button", { name: "Pokaż wyniki" })).toHaveFocus();
});
it("keeps mobile unmapped focus in details then returns Escape to the visible row", async () => {
  const { container } = await load(true);
  fireEvent.click(screen.getByRole("button", { name: /Lista/ }));
  const row = screen.getByRole("button", { name: /TEST: hala/ });
  fireEvent.click(row);
  expect(container.querySelector(".workspace")).toHaveClass("view-list");
  expect(container.querySelector(".detail-panel")).toHaveFocus();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(row).toHaveFocus();
});
it("repeats mobile mapped selection and returns close to the surface currently visible", async () => {
  const { container } = await load(true);
  const map = container.querySelector(".leaflet-map");
  for (let repeat = 0; repeat < 2; repeat++) {
    fireEvent.click(screen.getByRole("button", { name: /Lista/ }));
    fireEvent.click(screen.getByRole("button", { name: /TEST: budowa domu/ }));
    expect(screen.getByRole("button", { name: "Pokaż wyniki" })).toHaveFocus();
  }
  fireEvent.click(screen.getByRole("button", { name: "Wybierz działkę testową" }));
  expect(container.querySelector(".detail-panel")).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: /Lista/ }));
  fireEvent.click(screen.getByRole("button", { name: "Zamknij szczegóły" }));
  expect(screen.getByRole("button", { name: /TEST: budowa domu/ })).toHaveFocus();
  expect(container.querySelector(".leaflet-map")).toBe(map);
});
it("keeps the idle inspector concise without dropping the map/source warnings", async () => {
  const { container } = await load();
  const inspector = container.querySelector(".inspector-idle")!;
  expect(inspector.querySelectorAll(".inspector-guide")).toHaveLength(0);
  expect(inspector.querySelector(".inspector-illustration")).not.toBeInTheDocument();
  expect(styles).toMatch(/\.inspector-idle\s*\{[^}]*align-self:\s*start/);
  expect(inspector.textContent).toContain("Mapa pokazuje działki, nie budynki ani postęp prac.");
  expect(screen.getByText("Wpis nie oznacza zatwierdzenia budowy.")).toBeInTheDocument();
  expect(container.querySelector(".source-ribbon a")).toBeInTheDocument();
});
