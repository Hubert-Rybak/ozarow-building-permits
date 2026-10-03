import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../../src/App";
import { dataset, metadata, parcels } from "./fixtures";
vi.mock("../../src/ParcelMap", () => ({
  default: ({
    onSelect,
    records,
  }: {
    onSelect: (id: string) => void;
    records: { id: string }[];
  }) => (
    <div aria-label="Mapa działek testowa">
      <button onClick={() => onSelect(records[0]?.id)}>
        TEST: wybierz na mapie
      </button>
    </div>
  ),
}));
afterEach(() => vi.unstubAllGlobals());
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

describe("Polish accessible interface with test-only records", () => {
  it("shows the absence of standalone applications as a source gap, not a zero pending count", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok: true, json: async () => url.includes("permits.json") ? {...dataset, records: dataset.records.filter(r => r.kind !== "application")} : url.includes("parcels.geojson") ? {...parcels, features:[]} : metadata})));
    render(<App />);
    await screen.findByText("TEST: hala");
    expect(screen.getByText(/Nie oznacza to braku nierozpatrzonych wniosków/)).toBeVisible();
  });
  it("reveals the mobile results when using the skip link", async () => {
    mockData();
    const {container} = render(<App />);
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("link", {name:"Przejdź do wyników"}));
    expect(container.querySelector(".workspace")).toHaveClass("view-list");
    await waitFor(() => expect(screen.getByRole("region", {name:/Wpisy/})).toHaveFocus());
  });
  it("labels partial geometry on rows and supports a partial-only filter", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ok:true,json:async()=>url.includes("permits.json") ? {...dataset, records:[{...dataset.records[0], geometryStatus:"partial", parcelIds:["test-parcel","unresolved-parcel"]}, ...dataset.records.slice(1)]} : url.includes("parcels.geojson") ? parcels : metadata})));
    render(<App />);
    await screen.findByText("TEST: budowa domu");
    expect(screen.getByText("Częściowy obrys")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Położenie na mapie"),{target:{value:"partial"}});
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count","1");
    expect(screen.queryByText("TEST: hala")).not.toBeInTheDocument();
  });
  it("shows truthful loading then live counts; distinguishes a pending application", async () => {
    mockData();
    render(<App />);
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
    render(<App />);
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
    fireEvent.click(
      screen.getByRole("button", { name: "TEST: wybierz na mapie" }),
    );
    expect(
      screen.getByRole("heading", { name: "Szczegóły wpisu" }),
    ).toBeInTheDocument();
  });
  it("keeps unresolved records accessible and explicitly explains geometry absence", async () => {
    mockData();
    render(<App />);
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
    render(<App />);
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
    render(<App />);
    await screen.findByText("TEST: hala");
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    await waitFor(() =>
      expect(scroll).toHaveBeenCalledWith({ block: "start", behavior: "auto" }),
    );
  });
  it("shows source coverage and a truthful empty dataset state", async () => {
    mockData(true);
    render(<App />);
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
    render(<App />);
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
