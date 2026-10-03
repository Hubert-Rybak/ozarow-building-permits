import { describe, expect, it } from "vitest";
import {
  defaultFilters,
  filterRecords,
  recordDate,
  semanticStatus,
  summarize,
  csvCell,
  exportCsv,
  safeUrl,
  getRecordParcels,
} from "../../src/model";
import { parcels, records } from "./fixtures";
const allFilters = {...defaultFilters, period: "all" as const};

describe("test fixtures only: searching, filtering and honest counts", () => {
  it("searches place, street, parcel and title without Polish accent sensitivity", () => {
    for (const query of ["poznanska", "12/3", "budowa domu"])
      expect(
        filterRecords(records, { ...allFilters, query }, parcels).map(
          (r) => r.id,
        ),
      ).toEqual(["test-application"]);
    expect(
      filterRecords(records, { ...allFilters, query: "ozarow" }, parcels),
    ).toHaveLength(2);
  });
  it("combines locality, type, year, raw status and mapped filters", () => {
    expect(
      filterRecords(
        records,
        {
          ...allFilters,
          locality: "Duchnice",
          kind: "decision",
          year: "2025",
          status: "odmowa",
          mapping: "unmapped",
        },
        parcels,
      ).map((r) => r.id),
    ).toEqual(["test-decision"]);
    expect(
      filterRecords(records, { ...allFilters, mapping: "mapped" }, parcels),
    ).toHaveLength(1);
  });
  it("sorts by decision date then application date, keeping missing dates last", () => {
    expect(
      filterRecords(records, allFilters, parcels).map((r) => r.id),
    ).toEqual(["test-decision", "test-application", "test-unknown"]);
    expect(
      filterRecords(records, { ...allFilters, sort: "oldest" }, parcels)[0]
        .id,
    ).toBe("test-unknown");
    expect(recordDate({ ...records[0], applicationDate: null })).toBe(null);
    expect(
      filterRecords(
        [...records, { ...records[0], id: "no-date", applicationDate: null }],
        { ...allFilters, sort: "oldest" },
        parcels,
      ).at(-1)?.id,
    ).toBe("no-date");
  });
  it("derives displayed counts from the filtered rows and actual loaded geometry", () => {
    expect(summarize(records, parcels)).toEqual({
      total: 3,
      mapped: 1,
      unmapped: 2,
      parcelCount: 1,
    });
    expect(
      summarize(
        filterRecords(records, { ...allFilters, query: "hala" }, parcels),
        parcels,
      ),
    ).toEqual({ total: 1, mapped: 0, unmapped: 1, parcelCount: 0 });
    expect(
      summarize(records, { type: "FeatureCollection", features: [] }).mapped,
    ).toBe(0);
  });
  it("keeps applications distinct from granted permits", () => {
    expect(semanticStatus({ ...records[0], status: "pozytywna" })).toBe(
      "pending",
    );
    expect(semanticStatus(records[1])).toBe("refused");
    expect(semanticStatus(records[2])).toBe("unknown");
    expect(semanticStatus({ ...records[1], status: "pozytywna" })).toBe(
      "approved",
    );
    expect(semanticStatus({ ...records[1], status: "decyzja wydana" })).toBe(
      "unknown",
    );
  });
  it.each([
    "Nie wydano decyzji pozytywnej",
    "Nie ma pozytywnej decyzji",
    "Brak decyzji pozytywnej",
  ])("does not infer approval from the negated source status: %s", (status) => {
    expect(semanticStatus({ ...records[1], status })).toBe("unknown");
  });
  it("does not infer approval from an unrecognized phrase mentioning a positive decision", () => {
    expect(semanticStatus({ ...records[1], status: "Oczekiwanie na decyzję pozytywną" })).toBe("unknown");
  });
  it.each(["pozytywna", " Decyzja POZYTYWNA ", "Udzielono pozwolenia"])(
    "recognizes the explicit positive decision status: %s",
    (status) => expect(semanticStatus({ ...records[1], status })).toBe("approved"),
  );
  it("preserves an explicit notification opposition as refused", () => {
    expect(semanticStatus({ ...records[0], kind: "notification", status: "Sprzeciw" })).toBe("refused");
  });
  it("keeps notifications without opposition separate from approved permit decisions", () => {
    expect(semanticStatus({...records[0], kind:"notification", status:"Brak sprzeciwu"})).toBe("pending");
    expect(semanticStatus({...records[0], kind:"notification", status:"pozytywna"})).toBe("pending");
  });
  it("does not classify absent opposition or negated approval as a refusal or approval", () => {
    expect(semanticStatus({ ...records[1], status: "Brak sprzeciwu" })).toBe(
      "unknown",
    );
    expect(
      semanticStatus({ ...records[1], status: "Nie zatwierdzono projektu" }),
    ).toBe("unknown");
    expect(
      semanticStatus({
        ...records[1],
        status: "Decyzja odnotowana — wynik nieudostępniony w CSV",
      }),
    ).toBe("unknown");
  });
  it("filters partial mapping without hiding unresolved entries in the default view", () => {
    const partial = {...records[0], geometryStatus:"partial" as const};
    expect(filterRecords([partial, ...records.slice(1)], {...allFilters,mapping:"partial"}, parcels)).toEqual([partial]);
  });
  it("joins confirmed parcel identifiers without guessing from parcel number", () => {
    expect(getRecordParcels(records[0], parcels)).toHaveLength(1);
    expect(
      getRecordParcels({ ...records[2], parcelNumbers: ["12/3"] }, parcels),
    ).toHaveLength(0);
  });
});

describe("safe provenance and CSV export", () => {
  it("carries source incompleteness and geometry status into exported rows", () => {
    const csv = exportCsv([records[1]], parcels);
    expect(csv).toContain("Ograniczenia zbioru");
    expect(csv).toContain("nierozpatrzonych wniosków");
    expect(csv).toContain("Status geometrii");
    expect(csv).toContain("unresolved");
    expect(csv).toContain("nie oznacza pozwolenia");
  });
  it("allows only absolute HTTP(S) source URLs", () => {
    expect(safeUrl("javascript:alert(1)")).toBe(null);
    expect(safeUrl("/fake")).toBe(null);
    expect(safeUrl("https://example.org/source")).toBe(
      "https://example.org/source",
    );
  });
  it("quotes CSV and neutralizes formulas including leading whitespace/control characters", () => {
    expect(csvCell("=SUM(1;2)")).toBe(`"'=SUM(1;2)"`);
    expect(csvCell(" \t+123")).toBe(`"' \t+123"`);
    expect(csvCell("@x")).toBe(`"'@x"`);
    expect(csvCell('a"b;c')).toBe('"a""b;c"');
    expect(csvCell(" zwykły tekst")).toBe('" zwykły tekst"');
  });
  it("exports only requested rows, preserves kind and original status", () => {
    const csv = exportCsv([records[1]], parcels);
    expect(csv).toContain("Rodzaj");
    expect(csv).toContain("Decyzja");
    expect(csv).toContain("odmowa");
    expect(csv).not.toContain("test-application");
    expect(csv.split("\r\n")).toHaveLength(2);
  });
});
