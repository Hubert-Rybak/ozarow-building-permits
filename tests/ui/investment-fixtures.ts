/** Synthetic investment fixtures: TESTS ONLY, never served by the application. */
// Invented records below are strictly test fixtures, never production data.
export function fixture() {
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
