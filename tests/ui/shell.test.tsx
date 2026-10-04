import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../../src/App";
import { dataset, metadata, parcels } from "./fixtures";
import { fixture } from "./investment-fixtures";

// The map is replaced by a probe exposing the props the shell passes to it.
const map = vi.hoisted(() => ({ props: null as null | Record<string, any> }));
vi.mock("../../src/RadarMap", () => ({
  default: (props: Record<string, any>) => {
    map.props = props;
    return (
      <div aria-label="Mapa testowa" data-keys={props.items.map((i: { key: string }) => i.key).join(",")}>
        <button onClick={() => props.onSelect("permits", "test-application")}>TEST: wybierz działkę</button>
        <button onClick={() => props.onSelect("investments", "test:1")}>TEST: wybierz inwestycję</button>
        <button onClick={() => props.onBackgroundClick?.()}>TEST: puste miejsce mapy</button>
      </div>
    );
  },
}));

type Overrides = { permits?: unknown; parcels?: unknown; metadata?: unknown; investments?: unknown; failInvestments?: boolean; failPermits?: boolean };
function stub(o: Overrides = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (o.failPermits && !url.includes("investments")) throw new Error("TEST offline");
    const fail = o.failInvestments && url.includes("investments.json");
    return {
      ok: !fail, status: fail ? 503 : 200,
      json: async () => url.includes("investments.json") ? (o.investments ?? fixture())
        : url.includes("permits.json") ? (o.permits ?? dataset)
          : url.includes("parcels.geojson") ? (o.parcels ?? parcels) : (o.metadata ?? metadata),
    };
  }));
}
async function load(o: Overrides = {}, { allDates = true } = {}) {
  stub(o);
  const view = render(<App />);
  await waitFor(() => expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", o.failPermits ? "error" : "ready"));
  await waitFor(() => expect(screen.getByTestId("investments-status")).not.toHaveAttribute("data-state", "loading"));
  if (allDates && !o.failPermits) fireEvent.change(screen.getByLabelText("Okres"), { target: { value: "all" } });
  return view;
}
const mobile = (on: boolean) => vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: on, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("record card", () => {
  it("never presents a GUNB decision as a permit and verifies via search, Geoportal and the labelled archive", async () => {
    await load();
    fireEvent.click(screen.getByRole("button", { name: /TEST: budowa domu/ }));
    expect(screen.getByRole("heading", { level: 2, name: "TEST: budowa domu" })).toBeInTheDocument();
    expect(screen.getByText(/Wniosek nie jest pozwoleniem na budowę/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Wyszukiwarka GUNB/ })).toHaveAttribute("href", "https://wyszukiwarka.gunb.gov.pl/");
    expect(screen.getByRole("button", { name: "Kopiuj numer" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Działka 12\/3 w Geoportalu/ })).toHaveAttribute("href", expect.stringContaining("identifyParcel=test-parcel"));
    expect(screen.getByRole("link", { name: /Plik źródłowy GUNB/ })).toHaveAttribute("href", dataset.records[0].sourceUrl);
    for (const link of screen.getAllByRole("link")) if (link.getAttribute("target") === "_blank") expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(window.location.hash).toBe("#wpis=test-application");
    fireEvent.click(screen.getByRole("button", { name: "Zamknij szczegóły" }));
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    expect(screen.getByText(/Źródło podaje odmowę lub sprzeciw/)).toBeInTheDocument();
  });

  it("states that the decision outcome is unknown when GUNB does not publish it", async () => {
    await load({ permits: { ...dataset, records: [{ ...dataset.records[1], status: "Decyzja odnotowana — wynik nieudostępniony w CSV" }] } });
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    expect(screen.getByText(/Dane GUNB nie mówią, czy była pozytywna/)).toBeInTheDocument();
    expect(screen.getByText("Brak potwierdzonej geometrii — wpis pozostaje dostępny na liście.", { exact: false })).toBeInTheDocument();
  });

  it.each(["close", "Escape"])("returns a list selection to its row via %s without remounting the map", async action => {
    await load();
    const probe = screen.getByLabelText("Mapa testowa");
    fireEvent.click(screen.getByRole("button", { name: /TEST: budowa domu/ }));
    expect(map.props?.selectedKey).toBe("p:test-application");
    expect(document.activeElement).toHaveClass("detail-panel");
    if (action === "Escape") fireEvent.keyDown(document, { key: "Escape" });
    else fireEvent.click(screen.getByRole("button", { name: "Zamknij szczegóły" }));
    expect(screen.getByRole("button", { name: /TEST: budowa domu/ })).toHaveFocus();
    expect(screen.getByLabelText("Mapa testowa")).toBe(probe);
    expect(window.location.hash).toBe("#budowy");
  });

  it("returns a map selection to the map controls and repeats the same selection", async () => {
    await load();
    for (let i = 0; i < 2; i++) {
      const before = map.props?.fitToken;
      fireEvent.click(screen.getByRole("button", { name: "TEST: wybierz działkę" }));
      expect(map.props?.fitToken).toBeGreaterThan(before);
      expect(screen.getByRole("heading", { level: 2, name: "TEST: budowa domu" })).toBeInTheDocument();
      fireEvent.keyDown(document, { key: "Escape" });
      expect(screen.getByRole("button", { name: /Pokaż wszystkie/ })).toHaveFocus();
    }
  });

  it("closes a card that a new search hides and shows an honest empty state", async () => {
    await load();
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    fireEvent.click(screen.getByRole("button", { name: "Zamknij szczegóły" }));
    fireEvent.click(screen.getByRole("button", { name: /TEST: hala/ }));
    expect(screen.queryByLabelText("Szukaj w rejestrze")).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.change(screen.getByLabelText("Szukaj w rejestrze"), { target: { value: "nieistniejący" } });
    expect(screen.getByText("Brak wyników dla tych filtrów.")).toBeInTheDocument();
  });
});

describe("filters drive list, map, counters and CSV together", () => {
  it("defaults to the last three months, then widens, narrows by kind chip and resets", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-03T10:00:00Z"));
    const rows = [
      { ...dataset.records[0], applicationDate: "2026-07-03" },
      { ...dataset.records[1], decisionDate: "2026-10-03" },
      dataset.records[2],
    ];
    await load({ permits: { ...dataset, records: rows } }, { allDates: false });
    expect(screen.getByLabelText("Okres")).toHaveValue("3months");
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "2");
    expect(screen.getByLabelText("Mapa testowa")).toHaveAttribute("data-keys", "p:test-application,i:test:1");
    fireEvent.click(screen.getByRole("button", { name: /^Decyzje/ }));
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "1");
    expect(screen.getByLabelText("Mapa testowa").getAttribute("data-keys")).not.toContain("p:");
    const create = vi.fn((_blob: Blob) => "blob:test");
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: create });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    fireEvent.click(screen.getByRole("button", { name: "Eksport CSV" }));
    const csv = await new Promise<string>(resolve => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(create.mock.calls[0][0]);
    });
    expect(csv).toContain('"test-decision"');
    expect(csv).not.toContain('"test-application"');
    fireEvent.change(screen.getByLabelText("Okres"), { target: { value: "all" } });
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "2");
    fireEvent.click(screen.getByRole("button", { name: "Wyczyść filtry" }));
    expect(screen.getByLabelText("Okres")).toHaveValue("3months");
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "2");
  });

  it("summarises results in one line and keeps unmapped records on the list", async () => {
    await load();
    expect(screen.getByText(/1 na mapie · 2 tylko na liście/)).toBeInTheDocument();
    expect(screen.getAllByText("Tylko na liście — brak obrysu")).toHaveLength(2);
    fireEvent.click(screen.getByText("Więcej filtrów"));
    fireEvent.change(screen.getByLabelText("Położenie na mapie"), { target: { value: "unmapped" } });
    expect(screen.queryByText("TEST: budowa domu")).not.toBeInTheDocument();
  });

  it("builds the legend from mapped results only", async () => {
    await load();
    const legend = document.querySelector(".layer-body") as HTMLElement;
    expect(within(legend).getByText("Wnioski")).toBeInTheDocument();
    expect(within(legend).queryByText("Decyzje")).not.toBeInTheDocument();
    expect(legend).not.toHaveTextContent("Decyzja pozytywna");
    fireEvent.click(within(legend).getByRole("checkbox", { name: /Budowy/ }));
    expect(screen.getByLabelText("Mapa testowa").getAttribute("data-keys")).not.toContain("p:");
  });

  it("marks records new since the last visit and filters them with a chip", async () => {
    window.localStorage.setItem("radar-ozarow:seen:permits", JSON.stringify({ ids: ["test-decision", "test-unknown"], at: "2026-09-01T00:00:00Z" }));
    await load();
    expect(within(screen.getByRole("button", { name: /TEST: budowa domu/ })).getByText("Nowe")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Nowe od ostatniej wizyty/ }));
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-filtered-count", "1");
  });

  it("switches datasets without losing permit filters or the map", async () => {
    await load();
    fireEvent.change(screen.getByLabelText("Szukaj w rejestrze"), { target: { value: "hala" } });
    const probe = screen.getByLabelText("Mapa testowa");
    fireEvent.click(screen.getByRole("button", { name: /^Inwestycje/ }));
    expect(window.location.hash).toBe("#inwestycje");
    fireEvent.click(screen.getByRole("button", { name: /^Budowy/ }));
    expect(screen.getByLabelText("Szukaj w rejestrze")).toHaveValue("hala");
    expect(screen.getByLabelText("Okres")).toHaveValue("all");
    expect(screen.getByLabelText("Mapa testowa")).toBe(probe);
  });
});

describe("shareable links", () => {
  it("opens a linked record even outside the default period", async () => {
    window.history.replaceState(null, "", "/#wpis=test-decision");
    await load({}, { allDates: false });
    await screen.findByRole("heading", { level: 2, name: "TEST: hala" });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByLabelText("Okres")).toHaveValue("all");
  });
  it("opens a linked investment in its tab", async () => {
    window.history.replaceState(null, "", "/#inwestycja=test%3A1");
    await load({}, { allDates: false });
    await screen.findByRole("heading", { level: 2, name: "TEST ONLY park" });
    expect(screen.getByRole("button", { name: /^Inwestycje/ })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("phone bottom sheet", () => {
  it("starts with a peek sheet, steps up via the handle and keeps the selection above the sheet", async () => {
    mobile(true);
    const { container } = await load();
    const panel = container.querySelector(".panel")!;
    expect(panel).toHaveClass("sheet-peek");
    fireEvent.click(screen.getByRole("button", { name: "Powiększ panel" }));
    expect(panel).toHaveClass("sheet-half");
    fireEvent.click(screen.getByRole("button", { name: /TEST: budowa domu/ }));
    expect(panel).toHaveClass("sheet-half");
    expect(map.props?.selectedKey).toBe("p:test-application");
    expect(map.props?.insets.bottom).toBeGreaterThan(150);
    expect(map.props?.insets.left).toBe(0);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("button", { name: /TEST: budowa domu/ })).toHaveFocus();
  });
  it("hides the card and lowers the sheet on a tap on empty map, without reframing it", async () => {
    mobile(true);
    const { container } = await load();
    const panel = container.querySelector(".panel")!;
    fireEvent.click(screen.getByRole("button", { name: "TEST: wybierz działkę" }));
    expect(panel).toHaveClass("sheet-half");
    expect(screen.getByRole("heading", { level: 2, name: "TEST: budowa domu" })).toBeInTheDocument();
    const fits = map.props?.fitToken;
    fireEvent.click(screen.getByRole("button", { name: "TEST: puste miejsce mapy" }));
    expect(panel).toHaveClass("sheet-peek");
    expect(screen.queryByRole("heading", { level: 2, name: "TEST: budowa domu" })).not.toBeInTheDocument();
    expect(map.props?.selectedKey).toBeNull();
    expect(map.props?.fitToken).toBe(fits);
    fireEvent.click(screen.getByRole("button", { name: "Powiększ panel" }));
    fireEvent.click(screen.getByRole("button", { name: "Powiększ panel" }));
    expect(panel).toHaveClass("sheet-full");
    fireEvent.click(screen.getByRole("button", { name: "TEST: puste miejsce mapy" }));
    expect(panel).toHaveClass("sheet-peek");
  });
  it("keeps the desktop card open on a tap on empty map", async () => {
    mobile(false);
    await load();
    fireEvent.click(screen.getByRole("button", { name: "TEST: wybierz działkę" }));
    fireEvent.click(screen.getByRole("button", { name: "TEST: puste miejsce mapy" }));
    expect(map.props?.selectedKey).toBe("p:test-application");
  });
  it("expands the sheet when searching", async () => {
    mobile(true);
    const { container } = await load();
    fireEvent.focus(screen.getByLabelText("Szukaj w rejestrze"));
    expect(container.querySelector(".panel")).toHaveClass("sheet-full");
  });
  it("offsets the desktop map by the floating panel", async () => {
    mobile(false);
    await load();
    expect(map.props?.insets.left).toBeGreaterThanOrEqual(400);
  });
});

describe("source transparency and failure states", () => {
  it("keeps limitations in the O danych dialog and restores focus after Escape", async () => {
    await load({
      permits: { ...dataset, records: dataset.records.filter(r => r.kind !== "application") },
      parcels: { ...parcels, features: [] },
      metadata: { ...metadata, warnings: ["TEST limitation"] },
    });
    expect(screen.queryByText("TEST limitation")).not.toBeInTheDocument();
    const opener = screen.getByRole("button", { name: "O danych" });
    fireEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "O danych" });
    expect(within(dialog).getByText("TEST COVERAGE")).toBeInTheDocument();
    expect(within(dialog).getByText("TEST limitation")).toBeInTheDocument();
    expect(within(dialog).getByText(/Nie oznacza to braku nierozpatrzonych wniosków/)).toBeInTheDocument();
    expect(within(dialog).getByText("TEST ONLY source")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("keeps permit integrity failures visible outside the dialog", async () => {
    await load({ parcels: { ...parcels, generatedAt: "2020-01-01T00:00:00Z" } });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Niespójny zestaw plików");
    expect(screen.getByRole("button", { name: "Ponów odczyt" })).toBeInTheDocument();
  });

  it("shows a recoverable permit error, never an empty register", async () => {
    await load({ failPermits: true });
    expect(screen.getAllByRole("alert").some(a => a.textContent?.includes("Nie udało się wczytać wpisów"))).toBe(true);
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
    expect(screen.queryByText("Brak wpisów w załadowanym zbiorze.")).not.toBeInTheDocument();
  });

  it("says an empty dataset is not proof of no construction", async () => {
    await load({ permits: { ...dataset, records: [] } });
    expect(screen.getByText("Brak wpisów w załadowanym zbiorze.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eksport CSV" })).toBeDisabled();
  });

  it("reveals and focuses the results with the skip link", async () => {
    await load();
    fireEvent.click(screen.getByRole("link", { name: "Przejdź do wyników" }));
    await waitFor(() => expect(document.querySelector("#results")).toHaveFocus());
  });
});

describe("investments tab", () => {
  const withDone = () => {
    const d = fixture();
    d.records[1].status = "Ukończone";
    return d;
  };
  it("hides completed records by default, explains stages and never sums costs", async () => {
    await load({ investments: withDone() });
    fireEvent.click(screen.getByRole("button", { name: /^Inwestycje/ }));
    expect(screen.getByTestId("investments-status")).toHaveAttribute("data-filtered-count", "1");
    expect(screen.queryByText("TEST ONLY unmapped")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Ukończone/ }));
    expect(screen.getByText("TEST ONLY unmapped")).toBeInTheDocument();
    expect(screen.getByText("Tylko na liście — brak lokalizacji")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /TEST ONLY park/ }));
    const card = document.querySelector(".detail-panel") as HTMLElement;
    expect(within(card).getByRole("heading", { level: 2, name: "TEST ONLY park" })).toBeInTheDocument();
    expect(within(card).getByText(/Cały projekt wielogminny/)).toBeInTheDocument();
    expect(within(card).getByText("TEST ONLY caveat")).toBeInTheDocument();
    expect(within(card).getByText(/nie potwierdza rozpoczęcia robót/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /Rekord w źródle/ })).toHaveAttribute("rel", "noopener noreferrer");
    expect(within(card).getByText("Udokumentowane powiązania")).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: /TEST ONLY unmapped/ }));
    expect(screen.getByRole("heading", { level: 2, name: "TEST ONLY unmapped" })).toBeInTheDocument();
    expect(screen.getByText("Brak w źródle")).toBeInTheDocument();
  });

  it("selects an investment from the map into its own tab", async () => {
    await load();
    fireEvent.click(screen.getByRole("button", { name: "TEST: wybierz inwestycję" }));
    expect(screen.getByRole("button", { name: /^Inwestycje/ })).toHaveAttribute("aria-pressed", "true");
    expect(map.props?.selectedKey).toBe("i:test:1");
    expect(window.location.hash).toBe("#inwestycja=test%3A1");
  });

  it("isolates an investment outage with a retry while permits keep working", async () => {
    await load({ failInvestments: true });
    fireEvent.click(screen.getByRole("button", { name: /^Inwestycje/ }));
    expect(screen.getByRole("button", { name: "Spróbuj ponownie — inwestycje" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Eksport CSV inwestycji" })).toBeDisabled();
    stub();
    fireEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie — inwestycje" }));
    await screen.findByText("TEST ONLY park");
    expect(screen.getByTestId("data-status")).toHaveAttribute("data-state", "ready");
  });

  it("keeps a source refresh failure visible and links it to O danych", async () => {
    const d = fixture();
    d.sources[0].status = "retained";
    await load({ investments: d });
    fireEvent.click(screen.getByRole("button", { name: /^Inwestycje/ }));
    const alert = screen.getByRole("alert", { name: "Problemy z pobraniem źródeł" });
    expect(alert).toHaveTextContent("Zachowany poprzedni odczyt");
    fireEvent.click(within(alert).getByRole("button", { name: "Szczegóły w „O danych”" }));
    expect(screen.getByRole("dialog", { name: "O danych" })).toBeInTheDocument();
  });
});

describe("locate me", () => {
  const geo = (impl: (ok: PositionCallback, fail: PositionErrorCallback) => void) => {
    const getCurrentPosition = vi.fn(impl);
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition } });
    return getCurrentPosition;
  };
  const position = (latitude: number, longitude: number, accuracy = 20) =>
    ({ coords: { latitude, longitude, accuracy } }) as GeolocationPosition;
  afterEach(() => { delete (navigator as { geolocation?: unknown }).geolocation; });

  it("asks for the position only on click and passes it to the map, again on each click", async () => {
    const call = geo(ok => ok(position(52.21, 20.8)));
    await load();
    expect(call).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Pokaż moje położenie na mapie" }));
    expect(map.props?.userLocation).toMatchObject({ at: [52.21, 20.8], accuracy: 20, token: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Pokaż moje położenie na mapie" }));
    expect(map.props?.userLocation.token).toBe(2);
    expect(document.querySelector(".locate-message")).toBeNull();
  });

  it("explains a denied permission and a position outside the municipality", async () => {
    geo((_ok, fail) => fail({ code: 1 } as GeolocationPositionError));
    await load();
    fireEvent.click(screen.getByRole("button", { name: "Pokaż moje położenie na mapie" }));
    expect(screen.getByText(/Brak zgody na lokalizację/)).toBeInTheDocument();
    expect(map.props?.userLocation).toBeNull();
    geo(ok => ok(position(50.06, 19.94)));
    fireEvent.click(screen.getByRole("button", { name: "Pokaż moje położenie na mapie" }));
    expect(screen.getByText(/poza gminą Ożarów Mazowiecki/)).toBeInTheDocument();
    expect(map.props?.userLocation.at).toEqual([50.06, 19.94]);
  });

  it("says so when the browser has no geolocation", async () => {
    await load();
    fireEvent.click(screen.getByRole("button", { name: "Pokaż moje położenie na mapie" }));
    expect(screen.getByText("Ta przeglądarka nie udostępnia lokalizacji.")).toBeInTheDocument();
  });
});
