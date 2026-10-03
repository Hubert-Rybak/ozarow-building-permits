import { afterEach, describe, expect, it, vi } from "vitest";
import {
  parseInvestments,
  loadInvestments,
  filterInvestments,
  investmentDefaults,
  investmentsCsv,
  investmentUrl,
} from "../../src/investments";

import { fixture } from "./investment-fixtures";
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
