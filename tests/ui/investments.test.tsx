import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../../src/App";
import {
  parseInvestments,
  loadInvestments,
  filterInvestments,
  investmentDefaults,
  investmentsCsv,
  investmentUrl,
} from "../../src/investments";
import { dataset, parcels, metadata } from "./fixtures";

// Invented records below are strictly test fixtures, never production data.
function fixture() {
  const source = {
    id: "test",
    name: "TEST ONLY source",
    url: "https://example.org/source",
    fetchedAt: "2026-10-01T10:00:00Z",
    sourceUpdatedAt: null,
    status: "static",
    coverage: "TEST ONLY coverage",
    recordCount: 2,
    warnings: [],
    reuse: "Test facts",
  };
  const row = {
    id: "test:1",
    sourceId: "test",
    sourceRecordId: "1",
    sourceUrl: "https://example.org/1",
    title: "TEST ONLY park",
    recordType: "project",
    investor: "municipal",
    investorName: "TEST ONLY municipality",
    category: "Park",
    locality: "TEST locality",
    address: "TEST street",
    status: "Plan",
    statusAsOf: "2020-06-30",
    summary: "Test summary",
    years: [2020],
    costs: [
      {
        kind: "project-total",
        amount: 123,
        currency: "PLN",
        label: "Test cost",
        year: 2020,
        scope: "multi-municipality",
        sourceUrl: "https://example.org/cost",
      },
    ],
    dates: [
      {
        kind: "plan",
        date: "2020-06-30",
        label: "Test date",
        sourceUrl: "https://example.org/date",
      },
    ],
    geometries: [
      {
        type: "Feature",
        geometry: { type: "Point", coordinates: [20.8, 52.2] },
        properties: {
          id: "test-geometry",
          accuracy: "source-point",
          sourceUrl: "https://example.org/map",
          parcelId: null,
          note: "Test point, not footprint",
          fetchedAt: "2026-10-01T10:00:00Z",
          sourceUpdatedAt: null,
        },
      },
    ],
    parcelIds: [] as string[],
    events: [
      {
        id: "event-test",
        title: "Test event",
        date: null,
        sourceUrl: "https://example.org/event",
      },
    ],
    facts: [
      {
        label: "Numer sprawy",
        value: "TEST-ABC",
        sourceUrl: "https://example.org/case",
      },
    ],
    relatedIds: ["test:2"],
    warnings: ["TEST ONLY caveat"],
    fetchedAt: "2026-10-01T10:00:00Z",
    sourceUpdatedAt: null,
  };
  return {
    schemaVersion: 1,
    generatedAt: "2026-10-02T10:00:00Z",
    sources: [source],
    records: [
      row,
      {
        ...row,
        id: "test:2",
        sourceRecordId: "2",
        title: "TEST ONLY unmapped",
        years: [2018],
        costs: [],
        geometries: [],
        relatedIds: [],
        warnings: [],
      },
    ],
    warnings: [],
    counts: { records: 2, mapped: 1, geometries: 1, bySource: { test: 2 } },
  };
}
vi.mock("../../src/ParcelMap", () => ({
  default: () => <div className="leaflet-map" aria-label="Permit test map" />,
}));
vi.mock("../../src/InvestmentsMap", () => ({
  default: ({
    records,
    onSelect,
  }: {
    records: { id: string }[];
    onSelect: (id: string) => void;
  }) => (
    <div
      className="leaflet-map"
      aria-label="Investment test map"
      data-record-ids={records.map((r) => r.id).join(",")}
    >
      <button className="map-overview">Pokaż wyniki inwestycji</button>
      <button onClick={() => onSelect(records[0].id)}>
        TEST choose investment geometry
      </button>
    </div>
  ),
}));
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("investment v1 validation", () => {
  it("accepts the exact independent single-file contract", () =>
    expect(parseInvestments(fixture()).records).toHaveLength(2));
  it("accepts shared-contract offset timestamps and UTC +00:00 generation", () => {
    const d = fixture();
    d.generatedAt = "2026-10-02T10:00:00+00:00";
    d.records[0].fetchedAt = "2026-10-01T12:00:00+02:00";
    expect(parseInvestments(d).records).toHaveLength(2);
  });
  it("accepts exact AR parcel identifiers without repairing their region tokens", () => {
    const d = fixture();
    d.records[0].parcelIds = ["143206_5.0005.AR_1.044/2"];
    expect(parseInvestments(d).records[0].parcelIds).toEqual([
      "143206_5.0005.AR_1.044/2",
    ]);
  });
  it("allows a geometry ID reused by another source record, but counts both source geometries", () => {
    const d = fixture();
    d.records[1].geometries = structuredClone(d.records[0].geometries);
    d.counts.mapped = 2;
    d.counts.geometries = 2;
    expect(parseInvestments(d).counts.geometries).toBe(2);
  });
  it.each([
    [
      "nonUTC generation",
      (d: any) => (d.generatedAt = "2026-10-01T12:00:00+02:00"),
    ],
    [
      "non2D coordinate",
      (d: any) =>
        (d.records[0].geometries[0].geometry.coordinates = [20, 52, 5]),
    ],
    ["duplicate records", (d: any) => d.records.push(d.records[0])],
    [
      "timestamp rollover",
      (d: any) => (d.records[0].fetchedAt = "2026-10-01T24:00:00Z"),
    ],
    [
      "missing required source timestamp",
      (d: any) => delete d.sources[0].fetchedAt,
    ],
    [
      "required event title type",
      (d: any) => (d.records[0].events[0].title = 0),
    ],
    ["required fact value type", (d: any) => (d.records[0].facts[0].value = 0)],
    [
      "unproven parcel geometry join",
      (d: any) => {
        d.records[0].geometries[0].properties.parcelId = "143206_4.0001.1";
      },
    ],
    [
      "zero area ring",
      (d: any) => {
        d.records[0].geometries[0].geometry = {
          type: "Polygon",
          coordinates: [
            [
              [20, 52],
              [21, 53],
              [22, 54],
              [20, 52],
            ],
          ],
        };
        d.records[0].geometries[0].properties.accuracy = "project-footprint";
      },
    ],
    ["missing key", (d: any) => delete d.records[0].summary],
    ["unknown key", (d: any) => (d.records[0].extra = "x")],
    ["numeric title", (d: any) => (d.records[0].title = 23)],
    ["invalid enum", (d: any) => (d.records[0].investor = "guess")],
    ["invalid record type", (d: any) => (d.records[0].recordType = "guess")],
    ["invalid source status", (d: any) => (d.sources[0].status = "guess")],
    ["impossible date", (d: any) => (d.records[0].statusAsOf = "2026-02-30")],
    ["invalid time", (d: any) => (d.generatedAt = "not a timestamp")],
    [
      "invalid source time",
      (d: any) => (d.sources[0].fetchedAt = "2026-02-30T10:00:00Z"),
    ],
    ["negative money", (d: any) => (d.records[0].costs[0].amount = -1)],
    ["string money", (d: any) => (d.records[0].costs[0].amount = "123")],
    ["infinite money", (d: any) => (d.records[0].costs[0].amount = Infinity)],
    ["fractional year", (d: any) => (d.records[0].years = [2020.5])],
    [
      "unsafe URL",
      (d: any) => (d.records[0].sourceUrl = "javascript:alert(1)"),
    ],
    [
      "URL credentials",
      (d: any) => (d.sources[0].url = "https://user:secret@example.org/"),
    ],
    [
      "secret URL",
      (d: any) =>
        (d.records[0].facts[0].sourceUrl = "https://example.org/?token=secret"),
    ],
    ["unknown source", (d: any) => (d.records[0].sourceId = "missing")],
    ["duplicate sources", (d: any) => d.sources.push(d.sources[0])],
    ["wrong total", (d: any) => (d.counts.records = 5)],
    ["wrong mapped count", (d: any) => (d.counts.mapped = 2)],
    ["wrong geometry count", (d: any) => (d.counts.geometries = 2)],
    ["wrong source count", (d: any) => (d.sources[0].recordCount = 1)],
    ["wrong bySource", (d: any) => (d.counts.bySource = { test: 1 })],
    [
      "duplicate geometry within record",
      (d: any) => d.records[0].geometries.push(d.records[0].geometries[0]),
    ],
    [
      "coordinate range",
      (d: any) => (d.records[0].geometries[0].geometry.coordinates = [200, 52]),
    ],
    [
      "coordinate string",
      (d: any) =>
        (d.records[0].geometries[0].geometry.coordinates = ["20", 52]),
    ],
    [
      "unknown geometry",
      (d: any) =>
        (d.records[0].geometries[0].geometry.type = "GeometryCollection"),
    ],
    [
      "wrong accuracy",
      (d: any) => (d.records[0].geometries[0].properties.accuracy = "parcel"),
    ],
    [
      "open ring",
      (d: any) => {
        d.records[0].geometries[0].geometry = {
          type: "Polygon",
          coordinates: [
            [
              [20, 52],
              [21, 52],
              [21, 53],
              [20, 53],
            ],
          ],
        };
        d.records[0].geometries[0].properties.accuracy = "project-footprint";
      },
    ],
    ["unproven relation", (d: any) => (d.records[0].relatedIds = ["missing"])],
    [
      "invalid parcel ID",
      (d: any) => (d.records[0].parcelIds = ["143206_4.001.3"]),
    ],
  ] as [string, (d: any) => void][])(
    "rejects %s without coercion",
    (_name, mutate) => {
      const d = fixture();
      mutate(d);
      expect(() => parseInvestments(d)).toThrow();
    },
  );
  it.each(["https://example.org/x", "http://example.org/x"])(
    "keeps safe %s",
    (url) => expect(investmentUrl(url)).toBe(url),
  );
  it.each([
    "//example.org/x",
    "javascript:alert(1)",
    "https://u:p@example.org",
    "https://example.org/?email=person@example.org",
    "https://example.org/?auth=secret",
    "https://example.org/path%250Asecret",
    "https://example.org/?%2574oken=secret",
    "https://example.org/ghp_TESTONLYNOTAREALTOKEN",
    "https://example.org/?api_key=x",
    "https://example.org/?X-Amz-Signature=x",
    "https://example.org/\nfoo",
  ])("blocks unsafe %s", (url) => expect(investmentUrl(url)).toBeNull());
  it("supports true point, multipoint, polygon, multipolygon, route and multiroute geometry", () => {
    const ring = [
      [20.8, 52.2],
      [20.81, 52.2],
      [20.81, 52.21],
      [20.8, 52.2],
    ];
    for (const [type, coordinates, accuracy] of [
      ["Point", [20.8, 52.2], "source-point"],
      [
        "MultiPoint",
        [
          [20.8, 52.2],
          [20.81, 52.21],
        ],
        "source-point",
      ],
      ["Polygon", [ring], "project-footprint"],
      ["MultiPolygon", [[ring]], "project-footprint"],
      [
        "LineString",
        [
          [20.8, 52.2],
          [20.81, 52.21],
        ],
        "route",
      ],
      [
        "MultiLineString",
        [
          [
            [20.8, 52.2],
            [20.81, 52.21],
          ],
        ],
        "route",
      ],
    ] as any[]) {
      const d = fixture() as any;
      d.records[0].geometries[0].geometry = { type, coordinates };
      d.records[0].geometries[0].properties.accuracy = accuracy;
      expect(parseInvestments(d).counts.geometries).toBe(1);
    }
  });
});
describe("investment loader", () => {
  it("fetches the BASE_URL single file with no-store and cachebuster", async () => {
    const fetcher = vi.fn(async (_url: string, _options: RequestInit) => ({
      ok: true,
      json: async () => fixture(),
    }));
    const result = await loadInvestments(fetcher as any);
    expect(result.error).toBeNull();
    expect(result.dataset?.counts.records).toBe(2);
    expect(fetcher.mock.calls[0][0]).toMatch(/data\/investments\.json\?v=/);
    expect(fetcher.mock.calls[0][1].cache).toBe("no-store");
  });
  it("returns a retryable error, never an empty successful dataset on 503", async () => {
    const result = await loadInvestments(
      vi.fn(async () => ({ ok: false, status: 503 })) as any,
    );
    expect(result.dataset).toBeNull();
    expect(result.error).toContain("503");
  });
  it.each(["abort", "timeout"])(
    "terminates a stuck request on %s",
    async (reason) => {
      vi.useFakeTimers();
      const controller = new AbortController();
      let requestSignal: AbortSignal | undefined;
      const p = loadInvestments(
        ((_url: any, options: any) => {
          requestSignal = options.signal;
          return new Promise(() => {});
        }) as any,
        controller.signal,
        20,
      );
      if (reason === "abort") controller.abort();
      else await vi.advanceTimersByTimeAsync(21);
      const result = await p;
      expect(requestSignal?.aborted).toBe(true);
      expect(result.error).toBeTruthy();
    },
  );
  it("does not start requests after external cancellation", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetcher = vi.fn();
    expect(
      (await loadInvestments(fetcher, controller.signal)).error,
    ).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
  });
});
describe("one investment result set", () => {
  it("defaults to all years and searches facts, address and source case identity", () => {
    const d = parseInvestments(fixture());
    expect(filterInvestments(d.records, investmentDefaults)).toHaveLength(2);
    for (const query of ["TEST-ABC", "test street", "test:1"]) {
      expect(
        filterInvestments(d.records, { ...investmentDefaults, query }).length,
      ).toBeGreaterThan(0);
    }
  });
  it("uses every filter and preserves CSV IDs/order with formula protection", () => {
    const d = parseInvestments(fixture());
    let f = {
      ...investmentDefaults,
      source: "test",
      investor: "municipal",
      category: "Park",
      status: "Plan",
      year: "2020",
      mapping: "mapped" as const,
      sort: "title" as const,
    };
    const records = filterInvestments(d.records, f);
    expect(records.map((r) => r.id)).toEqual(["test:1"]);
    records[0].title = "=TEST formula";
    const csv = investmentsCsv(records);
    expect(csv).toContain('"test:1"');
    expect(csv).not.toContain('\r\n"test:2";');
    expect(csv).toContain("'=TEST formula");
    expect(csv).toContain("multi-municipality");
  });
});
function mockData(fail = false) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: !fail || !url.includes("investments.json"),
      status: 503,
      json: async () =>
        url.includes("investments.json")
          ? fixture()
          : url.includes("permits.json")
            ? dataset
            : url.includes("parcels.geojson")
              ? parcels
              : metadata,
    })),
  );
}
describe("investment Atlas UX without GUNB regression", () => {
  it("brands the retained GIS interface as Radar Ożarów", () => {
    mockData();
    render(<App />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Radar Ożarów" }),
    ).toBeInTheDocument();
  });
  it("keeps permit integrity failures visible outside collapsed source notes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url.includes("permits.json")
            ? dataset
            : url.includes("parcels.geojson")
              ? { ...parcels, generatedAt: "2020-01-01T00:00:00Z" }
              : metadata,
      })),
    );
    render(<App />);
    await waitFor(() =>
      expect(screen.getByTestId("data-status")).toHaveAttribute(
        "data-state",
        "ready",
      ),
    );
    const warning = screen.getByRole("alert");
    expect(warning).toHaveTextContent("Niespójny zestaw plików");
    expect(warning.closest("details")).toBeNull();
  });
  it("switches modes without resetting permit filters or maps and loads investments lazily", async () => {
    mockData();
    const { container } = render(<App />);
    await waitFor(() =>
      expect(screen.getByTestId("data-status")).toHaveAttribute(
        "data-state",
        "ready",
      ),
    );
    expect(
      (fetch as any).mock.calls.some(([url]: [string]) =>
        url.includes("investments.json"),
      ),
    ).toBe(false);
    fireEvent.change(screen.getByLabelText("Okres"), {
      target: { value: "all" },
    });
    const map = screen.getByLabelText("Permit test map");
    fireEvent.click(screen.getByRole("button", { name: "Inwestycje" }));
    await screen.findByText("TEST ONLY park");
    expect(screen.getByLabelText("Rok inwestycji")).toHaveValue("");
    expect(
      container.querySelector(".investment-atlas details.data-disclosure"),
    ).not.toHaveAttribute("open");
    fireEvent.click(screen.getByRole("button", { name: "Pozwolenia" }));
    expect(screen.getByLabelText("Okres")).toHaveValue("all");
    expect(screen.getByLabelText("Permit test map")).toBe(map);
  });
  it("synchronizes map/list/count/CSV with filters and renders typed details safely", async () => {
    mockData();
    const { container } = render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Inwestycje" }));
    await screen.findByText("TEST ONLY park");
    fireEvent.change(screen.getByLabelText("Szukaj inwestycji"), {
      target: { value: "park" },
    });
    expect(screen.getByTestId("investments-status")).toHaveAttribute(
      "data-filtered-count",
      "1",
    );
    expect(screen.getByLabelText("Investment test map")).toHaveAttribute(
      "data-record-ids",
      "test:1",
    );
    fireEvent.click(screen.getByRole("button", { name: /TEST ONLY park/ }));
    expect(
      screen.getByRole("heading", { name: "Szczegóły inwestycji" }),
    ).toBeInTheDocument();
    expect(
      within(
        container.querySelector(
          ".investment-atlas .detail-panel",
        ) as HTMLElement,
      ).getByText(/Cały projekt wielogminny/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Rekord w źródle" }),
    ).toHaveAttribute("rel", "noopener noreferrer");
    expect(
      container.querySelector(".investment-atlas .detail-panel"),
    ).toHaveTextContent("TEST ONLY caveat");
    fireEvent.change(screen.getByLabelText("Szukaj inwestycji"), {
      target: { value: "nonexistent" },
    });
    expect(
      within(
        container.querySelector(".investment-atlas") as HTMLElement,
      ).getByText("Brak wyników dla tych filtrów."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Szczegóły inwestycji" }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Wyczyść filtry inwestycji" }),
    );
    expect(screen.getByTestId("investments-status")).toHaveAttribute(
      "data-filtered-count",
      "2",
    );
  });
  it("isolates investment 503, exposes retry and preserves permit availability", async () => {
    mockData(true);
    render(<App />);
    await waitFor(() =>
      expect(screen.getByTestId("data-status")).toHaveAttribute(
        "data-state",
        "ready",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Inwestycje" }));
    await screen.findByRole("button", {
      name: "Spróbuj ponownie — inwestycje",
    });
    expect(
      screen.queryByText("Brak rekordów w załadowanym zbiorze."),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Eksport CSV inwestycji" }),
    ).toBeDisabled();
    mockData();
    fireEvent.click(
      screen.getByRole("button", { name: "Spróbuj ponownie — inwestycje" }),
    );
    await screen.findByText("TEST ONLY park");
    fireEvent.click(screen.getByRole("button", { name: "Pozwolenia" }));
    expect(screen.getByTestId("data-status")).toHaveAttribute(
      "data-state",
      "ready",
    );
  });
  it("reframes repeat mobile mapped selections, keeps unmapped details on list and restores visible focus", async () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: true })),
    );
    const scroll = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scroll,
    });
    mockData();
    const { container } = render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Inwestycje" }));
    await screen.findByText("TEST ONLY park");
    const map = screen.getByLabelText("Investment test map");
    for (let i = 0; i < 2; i++) {
      fireEvent.click(
        screen.getByRole("button", { name: "Lista inwestycji (2)" }),
      );
      fireEvent.click(screen.getByRole("button", { name: /TEST ONLY park/ }));
      expect(container.querySelector(".investment-workspace")).toHaveClass(
        "view-map",
      );
      expect(
        screen.getByRole("button", { name: "Pokaż wyniki inwestycji" }),
      ).toHaveFocus();
      expect(screen.getByLabelText("Investment test map")).toBe(map);
    }
    fireEvent.click(
      screen.getByRole("button", { name: "TEST choose investment geometry" }),
    );
    expect(
      container.querySelector(".investment-atlas .detail-panel"),
    ).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(
      screen.getByRole("button", { name: "Pokaż wyniki inwestycji" }),
    ).toHaveFocus();
    fireEvent.click(
      screen.getByRole("button", { name: "Lista inwestycji (2)" }),
    );
    const row = screen.getByRole("button", { name: /TEST ONLY unmapped/ });
    fireEvent.click(row);
    expect(container.querySelector(".investment-workspace")).toHaveClass(
      "view-list",
    );
    expect(
      container.querySelector(".investment-atlas .detail-panel"),
    ).toHaveFocus();
    fireEvent.click(
      screen.getByRole("button", { name: "Zamknij szczegóły inwestycji" }),
    );
    expect(row).toHaveFocus();
  });
});
