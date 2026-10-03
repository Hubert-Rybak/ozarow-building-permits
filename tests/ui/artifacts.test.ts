import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { loadData, parseParcels, parsePermits } from "../../src/data";
import { summarize } from "../../src/model";

const artifact = (name: string) => JSON.parse(readFileSync(`public/data/${name}`, "utf8"));

describe("the actual public snapshot (counts may change on the next import)", () => {
  it("loads the published contract and joins real geometry without a mixed-snapshot warning", async () => {
    const permits = parsePermits(artifact("permits.json"));
    const parcels = parseParcels(artifact("parcels.geojson"));
    const metadata = artifact("metadata.json");
    expect(parcels.generatedAt).toBe(permits.generatedAt);
    const result = await loadData(vi.fn(async url => {
      const name = String(url).split("/").at(-1)!;
      return {ok:true, json:async () => artifact(name)} as Response;
    }));
    expect(result.error).toBeNull();
    expect(result.warnings.some(w => w.includes("Niespójny"))).toBe(false);
    expect(result.dataset?.records.length).toBe(permits.records.length);
    expect(result.parcels.features.length).toBe(parcels.features.length);
    expect(metadata.generatedAt).toBe(permits.generatedAt);
    expect(metadata.recordCount).toBe(permits.records.length);
    expect(metadata.parcelCount).toBe(parcels.features.length);
    const counts = summarize(permits.records, parcels);
    expect(counts.total).toBe(counts.mapped + counts.unmapped);
    expect(counts.parcelCount).toBe(parcels.features.length);
  });
  it("does not publish investor or designer fields in record payloads", () => {
    for (const record of artifact("permits.json").records)
      expect(Object.keys(record).filter(key => /investor|designer|inwestor|projektant|pesel/i.test(key))).toEqual([]);
  });
  it("builds for the repository subpath by default", () => {
    expect(readFileSync("vite.config.ts", "utf8")).toMatch(/base:\s*"\/ozarow-building-permits\/"/);
  });
});
