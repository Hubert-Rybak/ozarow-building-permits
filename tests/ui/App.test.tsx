import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../../src/App";
import { dataset, metadata, parcels } from "./fixtures";
vi.mock("../../src/ParcelMap", () => ({
  default: ({
    onSelect,
    records,
    selectedId,
  }: {
    onSelect: (id: string) => void;
    records: { id: string }[];
    selectedId: string | null;
  }) => (
    <div aria-label="Mapa działek testowa" data-record-ids={records.map(r => r.id).join(",")}>
      <button onClick={() => onSelect(selectedId || records[0]?.id)}>
        TEST: wybierz na mapie
      </button>
    </div>
  ),
}));
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); vi.restoreAllMocks(); });
const mockData = (empty = false) =>
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes("permits.json")
          ? { ...dataset, records: empty ? [] : dataset.records }
          : url.includes("parcels.geojson")
            ? parcels
            : metadata,
    })),
  );

describe("UX regressions", () => {
  it("keeps explanatory copy and limitations in closed disclosures", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok: true, json: async () => url.includes("permits.json") ? {...dataset, records: dataset.records.filter(r => r.kind !== "application")} : url.includes("parcels.geojson") ? {...parcels, features: []} : {...metadata, warnings: ["TEST limitation"]}})));
    const {container} = render(<App />);
    await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
    expect(container.querySelector(".intro p")).not.toBeInTheDocument();
    expect(container.querySelector(".intro .eyebrow")).not.toBeInTheDocument();
    expect(container.querySelector("details.warnings")).not.toHaveAttribute("open");
    const provenance = container.querySelector("details#provenance");
    expect(provenance).toBeInTheDocument();
    expect(provenance).not.toHaveAttribute("open");
    expect(screen.getByText(/Nie oznacza to braku nierozpatrzonych wniosków/).closest("details")).toBe(provenance);
    expect(container.querySelector(".row-status")).not.toBeInTheDocument();
  });
  it("defaults to recent dates and updates the map, results, counters and CSV together", async () => {
    vi.useFakeTimers({toFake: ["Date"]});
    vi.setSystemTime(new Date("2026-10-03T10:00:00Z"));
    const rows = [
      {...dataset.records[0], applicationDate: "2026-07-03"},
      {...dataset.records[1], decisionDate: "2026-10-03"},
      dataset.records[2],
      {...dataset.records[2], id: "missing-date", applicationDate: null},
      {...dataset.records[2], id: "future", applicationDate: "2026-10-04"},
    ];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok: true, json: async () => url.includes("permits.json") ? {...dataset, records: rows} : url.includes("parcels.geojson") ? parcels : metadata})));
    const {container} = render(<App />);
    await screen.findByText("TEST: budowa domu");
    expect(screen.getByLabelText("Okres")).toHaveValue("3months");
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "2");
    expect(container.querySelectorAll(".result-row")).toHaveLength(2);
    expect(screen.getByLabelText("Mapa działek testowa")).toHaveAttribute("data-record-ids", "test-decision,test-application");
    const create = vi.fn((_blob: Blob) => "blob:test");
    Object.defineProperty(URL, "createObjectURL", {configurable: true, value: create});
    Object.defineProperty(URL, "revokeObjectURL", {configurable: true, value: vi.fn()});
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    fireEvent.click(screen.getByRole("button", {name: "Eksport CSV"}));
    const csv = await new Promise<string>(resolve => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(create.mock.calls[0][0]);
    });
    expect(csv).toContain('"test-application"');
    expect(csv).not.toContain('"test-unknown"');
    click.mockRestore();
    fireEvent.change(screen.getByLabelText("Okres"), {target: {value: "all"}});
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "5");
    fireEvent.click(screen.getByRole("button", {name: "Wyczyść filtry"}));
    expect(screen.getByLabelText("Okres")).toHaveValue("3months");
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "2");
  });
  it.each(["map", "list"])("restores the mobile %s viewport after removing details without changing filters", async (view) => {
    const seen: {element: HTMLElement; hadDetail: boolean}[] = [];
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {configurable: true, value: function(this: HTMLElement) {
      seen.push({element: this, hadDetail: !!document.querySelector(".detail-panel")});
    }});
    vi.stubGlobal("matchMedia", vi.fn(() => ({matches: true})));
    mockData();
    const {container} = render(<App />);
    await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
    fireEvent.change(screen.getByLabelText("Okres"), {target: {value: "all"}});
    fireEvent.change(screen.getByLabelText("Szukaj w rejestrze"), {target: {value: "hala"}});
    if (view === "list") fireEvent.click(screen.getByRole("button", {name: /Lista/}));
    const map = screen.getByLabelText("Mapa działek testowa");
    fireEvent.click(screen.getByRole("button", {name: view === "map" ? "TEST: wybierz na mapie" : /TEST: hala/}));
    expect(screen.getByRole("heading", {name: "Szczegóły wpisu"})).toBeInTheDocument();
    seen.length = 0;
    fireEvent.click(screen.getByRole("button", {name: "Zamknij szczegóły"}));
    await waitFor(() => expect(seen.some(({element, hadDetail}) => !hadDetail && element.classList.contains(view === "map" ? "map-panel" : "result-row"))).toBe(true));
    expect(container.querySelector(".workspace")).toHaveClass(`view-${view}`);
    expect(screen.getByLabelText("Szukaj w rejestrze")).toHaveValue("hala");
    expect(screen.getByLabelText("Okres")).toHaveValue("all");
    expect(screen.getByLabelText("Mapa działek testowa")).toBe(map);
    expect(container.querySelector(".result-row.selected")).not.toBeInTheDocument();
  });
  it.each(["matched", "partial"] as const)("shows a %s list selection on the mobile map, including repeated selections", async (geometryStatus) => {
    const seen: HTMLElement[] = [];
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {configurable: true, value: function(this: HTMLElement) { seen.push(this); }});
    vi.stubGlobal("matchMedia", vi.fn(() => ({matches: true})));
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok: true, json: async () => url.includes("permits.json") ? {...dataset, records: dataset.records.map(r => r.id === "test-application" ? {...r, geometryStatus} : r)} : url.includes("parcels.geojson") ? parcels : metadata})));
    const {container} = renderAllPeriods();
    await screen.findByText("TEST: budowa domu");
    const map = screen.getByLabelText("Mapa działek testowa");
    for (let cycle = 0; cycle < 2; cycle++) {
      fireEvent.click(screen.getByRole("button", {name: /Lista/}));
      seen.length = 0;
      fireEvent.click(screen.getByRole("button", {name: /TEST: budowa domu/}));
      expect(container.querySelector(".workspace")).toHaveClass("view-map");
      expect(container.querySelector('.result-row[data-record-id="test-application"]')).toHaveClass("selected");
      expect(seen.at(-1)).toBe(container.querySelector(".map-panel"));
      expect(screen.getByLabelText("Okres")).toHaveValue("all");
      expect(screen.getByLabelText("Mapa działek testowa")).toBe(map);
    }
    seen.length = 0;
    fireEvent.click(screen.getByRole("button", {name: "TEST: wybierz na mapie"}));
    expect(seen.at(-1)).toBe(container.querySelector(".detail-panel"));
    fireEvent.click(screen.getByRole("button", {name: "Zamknij szczegóły"}));
    expect(seen.at(-1)).toBe(container.querySelector(".map-panel"));
  });
  it("keeps unmapped mobile list selections on the list with their details", async () => {
    const seen: HTMLElement[] = [];
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {configurable: true, value: function(this: HTMLElement) { seen.push(this); }});
    vi.stubGlobal("matchMedia", vi.fn(() => ({matches: true})));
    mockData();
    const {container} = renderAllPeriods();
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("button", {name: /Lista/}));
    fireEvent.click(screen.getByRole("button", {name: /TEST: hala/}));
    expect(container.querySelector(".workspace")).toHaveClass("view-list");
    expect(seen.at(-1)).toBe(container.querySelector(".detail-panel"));
    expect(screen.getByText("Brak potwierdzonej geometrii — wpis pozostaje dostępny na liście.")).toBeInTheDocument();
  });
  it("does not change the desktop view when selecting a mapped list record", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({matches: false})));
    mockData();
    const {container} = renderAllPeriods();
    await screen.findByText("TEST: budowa domu");
    fireEvent.click(screen.getByRole("button", {name: /Lista/}));
    fireEvent.click(screen.getByRole("button", {name: /TEST: budowa domu/}));
    expect(container.querySelector(".workspace")).toHaveClass("view-list");
    expect(screen.getByRole("heading", {name: "Szczegóły wpisu"})).toBeInTheDocument();
  });
  it("omits only the generic privacy description while retaining real record descriptions", async () => {
    const generic = "Bezpieczny skrót rodzaju inwestycji. Swobodny opis GUNB pominięto ze względu na możliwość występowania danych osobowych.";
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok: true, json: async () => url.includes("permits.json") ? {...dataset, records: [{...dataset.records[0], description: generic}, dataset.records[1]]} : url.includes("parcels.geojson") ? parcels : metadata})));
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready"));
    fireEvent.change(screen.getByLabelText("Okres"), {target: {value: "all"}});
    fireEvent.click(screen.getByRole("button", {name: /TEST: budowa domu/}));
    expect(screen.queryByText(generic)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: /TEST: hala/}));
    expect(screen.getByText("Wyłącznie fixture testowa")).toBeInTheDocument();
  });
});

const renderAllPeriods = () => {
  const rendered = render(<App />);
  fireEvent.change(screen.getByLabelText("Okres"), {target: {value: "all"}});
  return rendered;
};

describe("Polish accessible interface with test-only records", () => {
  it("shows the absence of standalone applications as a source gap, not a zero pending count", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok: true, json: async () => url.includes("permits.json") ? {...dataset, records: dataset.records.filter(r => r.kind !== "application")} : url.includes("parcels.geojson") ? {...parcels, features:[]} : metadata})));
    renderAllPeriods();
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("link", {name: "O danych"}));
    expect(screen.getByText(/Nie oznacza to braku nierozpatrzonych wniosków/)).toBeVisible();
  });
  it("reveals the mobile results when using the skip link", async () => {
    mockData();
    const {container} = renderAllPeriods();
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("link", {name:"Przejdź do wyników"}));
    expect(container.querySelector(".workspace")).toHaveClass("view-list");
    await waitFor(() => expect(screen.getByRole("region", {name:/Wpisy/})).toHaveFocus());
  });
  it("labels partial geometry on rows and supports a partial-only filter", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok:true,json:async()=>url.includes("permits.json") ? {...dataset, records:[{...dataset.records[0], geometryStatus:"partial", parcelIds:["test-parcel","unresolved-parcel"]}, ...dataset.records.slice(1)]} : url.includes("parcels.geojson") ? parcels : metadata})));
    renderAllPeriods();
    await screen.findByText("TEST: budowa domu");
    expect(screen.getByText("Częściowy obrys")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Położenie na mapie"),{target:{value:"partial"}});
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count","1");
    expect(screen.queryByText("TEST: hala")).not.toBeInTheDocument();
  });
  it("shows truthful loading then live counts; distinguishes a pending application", async () => {
    mockData();
    renderAllPeriods();
    expect(screen.getByText("Ładowanie danych…")).toBeInTheDocument();
    await screen.findByText("TEST: budowa domu");
    expect(screen.getByTestId("data-status")).toHaveAttribute(
      "data-record-count",
      "3",
    );
    expect(screen.getByTestId("data-status")).toHaveAttribute(
      "data-mapped-count",
      "1",
    );
    fireEvent.click(screen.getByRole("button", { name: /TEST: budowa domu/ }));
    expect(
      screen.getByRole("heading", { name: "Szczegóły wpisu" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Wniosek nie jest pozwoleniem na budowę."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wpis w źródle" })).toHaveAttribute(
      "href",
      "https://example.org/test-application",
    );
    expect(screen.getByText("test-parcel")).toBeInTheDocument();
  });
  it("filters, clears obsolete selection, resets, and synchronizes map selection", async () => {
    mockData();
    renderAllPeriods();
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    fireEvent.change(screen.getByLabelText("Szukaj w rejestrze"), {
      target: { value: "nieistniejący wynik" },
    });
    expect(
      screen.getByText("Brak wyników dla tych filtrów."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Szczegóły wpisu" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Wyczyść filtry" }));
    fireEvent.change(screen.getByLabelText("Okres"), {target: {value: "all"}});
    fireEvent.click(
      screen.getByRole("button", { name: "TEST: wybierz na mapie" }),
    );
    expect(
      screen.getByRole("heading", { name: "Szczegóły wpisu" }),
    ).toBeInTheDocument();
  });
  it("keeps unresolved records accessible and explicitly explains geometry absence", async () => {
    mockData();
    renderAllPeriods();
    await screen.findByText("TEST: hala");
    fireEvent.change(screen.getByLabelText("Położenie na mapie"), {
      target: { value: "unmapped" },
    });
    expect(screen.queryByText("TEST: budowa domu")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    expect(
      screen.getByText(
        "Brak potwierdzonej geometrii — wpis pozostaje dostępny na liście.",
      ),
    ).toBeInTheDocument();
  });
  it("scrolls the selected list entry into view after selecting a polygon", async () => {
    const seen: HTMLElement[] = [];
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {configurable:true, value:function(this:HTMLElement) {seen.push(this);}});
    mockData();
    renderAllPeriods();
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("button", {name:"TEST: wybierz na mapie"}));
    await waitFor(() => expect(seen.some(element => element.classList.contains("result-row") && element.classList.contains("selected"))).toBe(true));
  });
  it("brings selected details into view on mobile", async () => {
    const scroll = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scroll,
    });
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: true })),
    );
    mockData();
    renderAllPeriods();
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    await waitFor(() =>
      expect(scroll).toHaveBeenCalledWith({ block: "start", behavior: "auto" }),
    );
  });
  it("shows source coverage and a truthful empty dataset state", async () => {
    mockData(true);
    renderAllPeriods();
    await screen.findByText("Brak wpisów w załadowanym zbiorze.");
    expect(screen.getByText("TEST COVERAGE")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eksport CSV" })).toBeDisabled();
  });
  it("shows a recoverable error rather than claiming there are no permits", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("TEST offline");
      }),
    );
    renderAllPeriods();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Nie udało się wczytać wpisów",
      ),
    );
    expect(
      screen.getByRole("button", { name: "Spróbuj ponownie" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Brak wpisów w załadowanym zbiorze."),
    ).not.toBeInTheDocument();
  });
});
