import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../../src/App";
import { dataset, metadata, parcels } from "./fixtures";
vi.mock("../../src/ParcelMap", () => ({ default: ({ onSelect }: { onSelect: (id: string) => void }) => <div className="leaflet-map"><button className="map-overview">Pokaż wyniki</button><button onClick={() => onSelect("test-application")}>Wybierz działkę testową</button></div> }));
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function load() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes("permits.json") ? dataset : url.includes("parcels.geojson") ? parcels : metadata })));
  return render(<App />);
}
it("groups tools and results in a GIS rail while keeping source attribution outside disclosures", async () => {
  const { container } = load();
  await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
  const rail = container.querySelector(".explore-rail");
  expect(rail?.querySelector(".toolbar")).toBeInTheDocument();
  expect(rail?.querySelector(".results-panel")).toBeInTheDocument();
  expect(container.querySelector(".source-ribbon a")).toHaveAttribute("href", new URL(dataset.source.url).href);
  expect(container.querySelector(".source-ribbon a")?.closest("details")).toBeNull();
});
it("collapses secondary filters without losing the selected filter or remounting the map", async () => {
  const { container } = load();
  await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
  const disclosure = container.querySelector<HTMLDetailsElement>(".advanced-filters")!;
  expect(disclosure).toBeInTheDocument();
  expect(disclosure).not.toHaveAttribute("open");
  expect(screen.getByLabelText("Okres").closest("details")).toBeNull();
  const map = container.querySelector(".leaflet-map");
  disclosure.open = true;
  fireEvent.change(screen.getByLabelText("Miejscowość"), { target: { value: dataset.records[0].locality } });
  disclosure.open = false;
  expect(screen.getByLabelText("Miejscowość")).toHaveValue(dataset.records[0].locality);
  expect(container.querySelector(".leaflet-map")).toBe(map);
});
it("offers a contextual inspector before a selection and a direct source caveat next to the map", async () => {
  load();
  await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
  expect(screen.getByRole("heading", { name: "Wybierz wpis lub działkę" })).toBeInTheDocument();
  expect(screen.getByText("Wpis nie oznacza zatwierdzenia budowy.")).toBeInTheDocument();
});
it("moves mobile focus from a hidden list row to the map, then to polygon details and back", async () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
  const { container } = load();
  await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
  fireEvent.change(screen.getByLabelText("Okres"), { target: { value: "all" } });
  fireEvent.click(screen.getByRole("button", { name: /Lista/ }));
  fireEvent.click(screen.getByRole("button", { name: /TEST: budowa domu/ }));
  expect(screen.getByRole("button", { name: "Pokaż wyniki" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Wybierz działkę testową" }));
  expect(container.querySelector(".detail-panel")).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Zamknij szczegóły" }));
  expect(screen.getByRole("button", { name: "Pokaż wyniki" })).toHaveFocus();
});
it("closes an active inspector with Escape and restores focus to its result row", async () => {
  const { container } = load();
  await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
  fireEvent.change(screen.getByLabelText("Okres"), { target: { value: "all" } });
  const row = screen.getByRole("button", { name: /TEST: budowa domu/ });
  fireEvent.click(row);
  expect(container.querySelector(".detail-panel")).toBeInTheDocument();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(container.querySelector(".detail-panel")).not.toBeInTheDocument();
  expect(row).toHaveFocus();
});
