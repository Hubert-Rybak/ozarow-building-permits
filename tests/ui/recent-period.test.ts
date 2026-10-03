import { describe, expect, it } from "vitest";
import { defaultFilters, filterRecords, exportCsv, summarize } from "../../src/model";
import { parcels, records } from "./fixtures";
import type { Permit } from "../../src/types";

const dated = (date: string | null, id = date || "missing"): Permit => ({
  ...records[0], id, applicationDate: date, decisionDate: null,
});
const recent = (rows: Permit[], now: string) => filterRecords(rows, defaultFilters, parcels, new Date(now));

describe("rolling three calendar months in Europe/Warsaw", () => {
  it("defaults to recent dates", () => {
    expect(defaultFilters).toHaveProperty("period", "3months");
  });
  it("includes both boundary days, excludes older, future and missing dates", () => {
    expect(recent([
      dated("2026-07-02"), dated("2026-07-03"), dated("2026-10-03"),
      dated("2026-10-04"), dated(null),
    ], "2026-10-03T10:00:00Z").map(r => r.id)).toEqual(["2026-10-03", "2026-07-03"]);
  });
  it.each([
    ["2026-05-31T10:00:00Z", "2026-02-28", "2026-02-27"],
    ["2024-05-31T10:00:00Z", "2024-02-29", "2024-02-28"],
    ["2026-01-31T10:00:00Z", "2025-10-31", "2025-10-30"],
    ["2026-12-31T10:00:00Z", "2026-09-30", "2026-09-29"],
  ])("clamps month-end without treating months as 90 days: %s", (now, cutoff, older) => {
    expect(recent([dated(cutoff), dated(older)], now).map(r => r.id)).toEqual([cutoff]);
  });
  it("uses Warsaw today across UTC midnight, not the import timestamp", () => {
    const rows = [dated("2026-07-02"), dated("2026-07-03"), dated("2026-10-03")];
    expect(recent(rows, "2026-10-02T21:59:59Z").map(r => r.id)).toEqual(["2026-07-03", "2026-07-02"]);
    expect(recent(rows, "2026-10-02T22:00:00Z").map(r => r.id)).toEqual(["2026-10-03", "2026-07-03"]);
  });
  it("uses decision date first, then application date, preserving filters and order", () => {
    const rows = [
      {...dated("2020-01-01", "decision"), decisionDate: "2026-07-03"},
      dated("2026-09-01", "application"),
      {...dated("2026-09-01", "old-decision"), decisionDate: "2020-01-01"},
    ];
    expect(recent(rows, "2026-10-03T10:00:00Z").map(r => r.id)).toEqual(["application", "decision"]);
    expect(filterRecords(rows, {...defaultFilters, sort: "oldest", query: "poznanska", mapping: "mapped"}, parcels, new Date("2026-10-03T10:00:00Z")).map(r => r.id)).toEqual(["decision", "application"]);
  });
  it("keeps historical and unknown dates available with all dates", () => {
    const rows = [dated("2000-01-01"), dated(null), dated("2027-01-01")];
    expect(filterRecords(rows, {...defaultFilters, period: "all"}, parcels, new Date("2026-10-03T10:00:00Z")).map(r => r.id)).toEqual(["2027-01-01", "2000-01-01", "missing"]);
  });
  it("applies the same recent results to geometry counts and CSV", () => {
    const rows = [dated("2026-07-03", "test-application"), {...dated("2020-01-01", "old"), parcelIds: []}];
    const filtered = recent(rows, "2026-10-03T10:00:00Z");
    expect(summarize(filtered, parcels)).toEqual({total: 1, mapped: 1, unmapped: 0, parcelCount: 1});
    expect(exportCsv(filtered, parcels)).toContain('"test-application"');
    expect(exportCsv(filtered, parcels)).not.toContain('"old"');
  });
});
