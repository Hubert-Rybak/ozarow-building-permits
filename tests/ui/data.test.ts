import { afterEach, describe, expect, it, vi } from "vitest";
afterEach(() => vi.unstubAllEnvs());
import { loadData, parsePermits, parseParcels } from "../../src/data";
import { dataset, metadata, parcels, records } from "./fixtures";
const response = (body: unknown, ok = true) =>
  ({ ok, status: ok ? 200 : 503, json: async () => body }) as Response;

describe("validated live-data boundary", () => {
  it("uses the deployment BASE_URL rather than the current relative route", async () => {
    vi.stubEnv("BASE_URL", "/ozarow-building-permits/");
    const fetcher = vi.fn(async (url: string | URL | Request) => response(
      String(url).includes("permits.json") ? dataset : String(url).includes("parcels.geojson") ? parcels : metadata,
    ));
    await loadData(fetcher);
    expect(fetcher.mock.calls.map(c => c[0])).toEqual([
      "/ozarow-building-permits/data/permits.json",
      "/ozarow-building-permits/data/parcels.geojson",
      "/ozarow-building-permits/data/metadata.json",
    ]);
  });
  it("requests a fresh snapshot rather than a cached daily import", async () => {
    const fetcher = vi.fn<typeof fetch>(async (url) => response(
      String(url).includes("permits.json") ? dataset : String(url).includes("parcels.geojson") ? parcels : metadata,
    ));
    await loadData(fetcher);
    expect(fetcher.mock.calls.every(([, options]) => options?.cache === "no-store")).toBe(true);
  });
  it("retries a mixed generation once before accepting a consistent snapshot", async () => {
    let metaReads = 0;
    const result = await loadData(vi.fn(async (url) => {
      const path = String(url);
      if (path.includes("metadata.json")) return response({generatedAt: ++metaReads === 1 ? "2024-01-01T00:00:00Z" : dataset.generatedAt});
      return response(path.includes("permits.json") ? dataset : parcels);
    }));
    expect(metaReads).toBe(2);
    expect(result.parcels.features).toHaveLength(1);
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(false);
  });
  it("keeps records but disables untrustworthy geometry after a persistent mixed snapshot", async () => {
    const result = await loadData(vi.fn(async (url) => response(
      String(url).includes("permits.json") ? dataset : String(url).includes("parcels.geojson") ? parcels : {generatedAt: "2024-01-01T00:00:00Z", warnings:["STALE WARNING"]},
    )));
    expect(result.dataset?.records).toHaveLength(3);
    expect(result.parcels.features).toHaveLength(0);
    expect(result.metadata).toBe(null);
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(true);
    expect(result.warnings).not.toContain("STALE WARNING");
  });
  it("does not map geometry whose reciprocal references disagree with records", async () => {
    const differentParcels = {...parcels, features: [{...parcels.features[0], properties: {...parcels.features[0].properties, permitIds:["foreign-record"]}}]};
    const result = await loadData(vi.fn(async url => response(
      String(url).includes("permits.json") ? dataset : String(url).includes("parcels.geojson") ? differentParcels : metadata,
    )));
    expect(result.parcels.features).toHaveLength(0);
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(true);
  });
  it.each([
    { field: "kind", value: ["decision"] },
    { field: "geometryStatus", value: ["matched"] },
  ])("rejects array values masquerading as the $field enum", ({ field, value }) => {
    const row = { ...records[1], [field]: value };
    expect(() => parsePermits({ ...dataset, records: [row] })).toThrow();
  });
  it.each([true, false])("hides persistently stale coordinates with unchanged identifiers (metadata available: %s)", async (metadataAvailable) => {
    const staleParcels = {
      ...parcels,
      generatedAt: "2024-01-01T00:00:00Z",
      features: [{
        ...parcels.features[0],
        geometry: { type: "Polygon", coordinates: [[[20.7, 52.1], [20.71, 52.1], [20.71, 52.11], [20.7, 52.1]]] },
      }],
    };
    const fetcher = vi.fn<typeof fetch>(async url => {
      const path = String(url);
      if (path.includes("metadata.json"))
        return response({ generatedAt: dataset.generatedAt, warnings: ["UNTRUSTED WARNING"] }, metadataAvailable);
      return response(path.includes("permits.json") ? dataset : staleParcels);
    });
    const result = await loadData(fetcher);
    expect(fetcher).toHaveBeenCalledTimes(6);
    expect(result.dataset).toEqual(dataset);
    expect(result.error).toBeNull();
    expect(result.parcels.features).toEqual([]);
    expect(result.metadata).toBeNull();
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(true);
    expect(result.warnings).not.toContain("UNTRUSTED WARNING");
  });
  it("retries stale GeoJSON and accepts the fresh matching generation", async () => {
    let parcelReads = 0;
    const result = await loadData(vi.fn(async url => {
      const path = String(url);
      if (path.includes("parcels.geojson"))
        return response({ ...parcels, generatedAt: ++parcelReads === 1 ? "2024-01-01T00:00:00Z" : dataset.generatedAt });
      return response(path.includes("permits.json") ? dataset : { generatedAt: dataset.generatedAt });
    }));
    expect(parcelReads).toBe(2);
    expect(result.parcels).toEqual(parcels);
    expect(result.metadata?.generatedAt).toBe(dataset.generatedAt);
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(false);
  });
  it("retries legacy GeoJSON without generation then hides geometry and metadata", async () => {
    const { generatedAt: _generation, ...legacyParcels } = parcels;
    const fetcher = vi.fn<typeof fetch>(async url => response(
      String(url).includes("permits.json") ? dataset : String(url).includes("parcels.geojson") ? legacyParcels : { generatedAt: dataset.generatedAt },
    ));
    const result = await loadData(fetcher);
    expect(fetcher).toHaveBeenCalledTimes(6);
    expect(result.dataset).toEqual(dataset);
    expect(result.parcels.features).toEqual([]);
    expect(result.metadata).toBeNull();
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(true);
  });
  it("does not trust metadata with a missing generation", async () => {
    const fetcher = vi.fn<typeof fetch>(async url => response(
      String(url).includes("permits.json") ? dataset : String(url).includes("parcels.geojson") ? parcels : {},
    ));
    const result = await loadData(fetcher);
    expect(fetcher).toHaveBeenCalledTimes(6);
    expect(result.dataset).toEqual(dataset);
    expect(result.parcels.features).toEqual([]);
    expect(result.metadata).toBeNull();
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(true);
  });
  it("warns when source metadata is unavailable", async () => {
    const result = await loadData(vi.fn(async url => String(url).includes("metadata.json") ? response({}, false) : response(String(url).includes("permits.json") ? dataset : parcels)));
    expect(result.parcels).toEqual(parcels);
    expect(result.warnings.some(w => w.includes("metadata.json"))).toBe(true);
  });
  it("accepts empty sources without injecting placeholder records or polygons", () => {
    expect(parsePermits({ ...dataset, records: [] }).records).toEqual([]);
    expect(
      parseParcels({ type: "FeatureCollection", features: [] }).features,
    ).toEqual([]);
  });
  it("rejects malformed schemas, duplicate records, non-polygon geometry and invalid coordinates", () => {
    expect(() => parsePermits({ records })).toThrow();
    expect(() =>
      parsePermits({ ...dataset, records: [records[0], records[0]] }),
    ).toThrow();
    expect(() =>
      parseParcels({
        type: "FeatureCollection",
        features: [
          {
            ...parcels.features[0],
            geometry: { type: "Point", coordinates: [20, 52] },
          },
        ],
      }),
    ).toThrow();
    expect(() =>
      parseParcels({
        type: "FeatureCollection",
        features: [
          {
            ...parcels.features[0],
            geometry: {
              type: "Polygon",
              coordinates: [
                [
                  [999, 52],
                  [20, 52],
                  [20, 53],
                  [999, 52],
                ],
              ],
            },
          },
        ],
      }),
    ).toThrow();
  });
  it("loads both contract paths and optional metadata without depending on metadata counts", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request) =>
      response(
        String(url).includes("permits.json")
          ? dataset
          : String(url).includes("parcels.geojson")
            ? parcels
            : { ...metadata, recordCount: 999, warnings: ["TEST warning"] },
      ),
    );
    const result = await loadData(fetcher);
    expect(fetcher.mock.calls.map((c) => c[0])).toEqual([
      `${import.meta.env.BASE_URL}data/permits.json`,
      `${import.meta.env.BASE_URL}data/parcels.geojson`,
      `${import.meta.env.BASE_URL}data/metadata.json`,
    ]);
    expect(result.dataset?.records).toHaveLength(3);
    expect(result.parcels.features).toHaveLength(1);
    expect(result.warnings).toContain("TEST warning");
  });
  it("reports an actionable records error and never creates fake records after a failed fetch", async () => {
    const result = await loadData(vi.fn(async () => response({}, false)));
    expect(result.dataset).toBe(null);
    expect(result.error).toContain("permits.json");
    expect(result.parcels.features).toEqual([]);
  });
  it("retains browsable records if geometry fails and optional metadata is unavailable", async () => {
    const result = await loadData(
      vi.fn(async (url: string | URL | Request) =>
        String(url).includes("permits.json")
          ? response(dataset)
          : response({}, false),
      ),
    );
    expect(result.dataset?.records).toHaveLength(3);
    expect(result.error).toBe(null);
    expect(result.warnings.some((w) => w.includes("parcels.geojson"))).toBe(
      true,
    );
  });
});
