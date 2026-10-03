import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";
import { defaultFilters, filterRecords, geoportalParcelUrl, gunbNumber, searchStem, sourceFileLabel, formatDateTime } from "../../src/model";
import { categoryGroup, filterInvestments, investmentDefaults, investmentStage, mapStage, similarRecords, type InvestmentRecord } from "../../src/investments";
import { centerOf, distanceMeters, formatDistance, nearest } from "../../src/geo";
import { readAndRemember } from "../../src/seen";
import { readHash, writeHash } from "../../src/hash";
import { parcels, records } from "./fixtures";

const all = { ...defaultFilters, period: "all" as const };
afterEach(() => window.localStorage.clear());

describe("search tolerates Polish inflection", () => {
  it("finds inflected forms but keeps short words and numbers exact", () => {
    expect(searchStem("boisko")).toBe("boisk");
    expect(searchStem("domu")).toBe("domu");
    expect(searchStem("12/3")).toBe("12/3");
    const rows = [{ ...records[0], title: "Budowa boiska przy szkole" }];
    expect(filterRecords(rows, { ...all, query: "boisko szkoła" }, parcels)).toHaveLength(1);
    expect(filterRecords(rows, { ...all, query: "basen" }, parcels)).toHaveLength(0);
  });
});

describe("verification links never pretend a ZIP archive is a single record", () => {
  it("labels voivodeship and national archives and builds a Geoportal parcel link", () => {
    expect(sourceFileLabel("https://wyszukiwarka.gunb.gov.pl/pliki_pobranie/wynik_mazowieckie.zip")).toMatch(/archiwum ZIP całego województwa/);
    expect(sourceFileLabel("https://wyszukiwarka.gunb.gov.pl/pliki_pobranie/wynik_zgloszenia_2022_up.zip")).toMatch(/zgłoszeń z całego kraju/);
    expect(gunbNumber({ ...records[0], id: "permit:ST-MZ-OZ/WNIOSEK/1/2026" })).toBe("ST-MZ-OZ/WNIOSEK/1/2026");
    expect(geoportalParcelUrl("143206_5.0023.78/7")).toBe("https://mapy.geoportal.gov.pl/imapnext/imap/?identifyParcel=143206_5.0023.78/7");
    expect(formatDateTime("2026-10-03T16:26:00Z")).toBe("03.10.2026, 18:26");
  });
});

describe("investment stages and groups (display only)", () => {
  it.each([
    ["Ukończone", "done"], ["Realizowane", "progress"], ["Plan przyjęty — nie potwierdzenie wykonania", "plan"],
    ["Wybrany do realizacji", "plan"], ["Postępowanie wszczęte", "tender"], ["Etap zawarcia umowy — nie potwierdzenie zakończenia budowy", "tender"],
    ["Umowa/decyzja ujęta w wykazie FE — nie potwierdza rozpoczęcia budowy", "preparation"],
    ["Wydano decyzję środowiskową — status robót niepotwierdzony", "preparation"],
    ["Postępowanie zawieszone — status robót niepotwierdzony", "other"], ["Status postępowania: Invalidated", "other"],
    ["Komunikat źródłowy — etap robót do odczytu w źródle", "other"], ["coś nowego", "other"],
  ])("%s → %s", (status, stage) => expect(investmentStage(status)).toBe(stage));
  it("maps every real status and category without inventing values", () => {
    const data = JSON.parse(readFileSync("public/data/investments.json", "utf8"));
    const groups = new Set(data.records.map((r: InvestmentRecord) => categoryGroup(r.category)));
    expect(groups.size).toBeLessThanOrEqual(11);
    expect(categoryGroup("wod-kan")).toBe("Woda i kanalizacja");
    expect(categoryGroup("Infrastruktura drogowa")).toBe("Drogi i transport");
    expect(categoryGroup("")).toBe("Inne");
    const stages = new Set(data.records.map((r: InvestmentRecord) => mapStage(investmentStage(r.status))));
    for (const stage of stages) expect(["upcoming", "progress", "done", "other"]).toContain(stage);
  });
  it("hides completed records by default but keeps them one chip away", () => {
    const row = (id: string, status: string) => ({ id, status, title: id, address: "", locality: "", summary: "", sourceRecordId: id, parcelIds: [], facts: [], years: [], geometries: [], category: "", sourceId: "s", investor: "municipal", statusAsOf: null, sourceUpdatedAt: null }) as unknown as InvestmentRecord;
    const rows = [row("a", "Ukończone"), row("b", "Realizowane")];
    expect(filterInvestments(rows, investmentDefaults).map(r => r.id)).toEqual(["b"]);
    expect(filterInvestments(rows, { ...investmentDefaults, stages: ["done"] }).map(r => r.id)).toEqual(["a"]);
    expect(filterInvestments(rows, { ...investmentDefaults, locality: "-" })).toHaveLength(1);
  });
  it("finds records with similar names without merging them", () => {
    const row = (id: string, title: string) => ({ id, title }) as InvestmentRecord;
    const rows = [row("1", "Projekt i budowa boiska przy SP Umiastów"), row("2", "Budowa boiska przy Szkole Podstawowej w Umiastowie"),
      row("3", "Modernizacja boiska przy Szkole Podstawowej nr 1 w Ożarowie Mazowieckim"), row("4", "Budowa ulicy Polnej")];
    expect(similarRecords(rows[0], rows).map(r => r.id)).toEqual(["2"]);
  });
});

describe("geometry helpers", () => {
  it("measures distances and finds nearby items", () => {
    expect(Math.round(distanceMeters([52.2, 20.8], [52.209, 20.8]))).toBe(1001);
    expect(formatDistance(57)).toBe("60 m");
    expect(formatDistance(1234)).toBe("1,2 km");
    const center = centerOf([{ type: "Point", coordinates: [20.8, 52.2] }, { type: "Point", coordinates: [20.82, 52.22] }])!;
    expect(center[0]).toBeCloseTo(52.21);
    expect(center[1]).toBeCloseTo(20.81);
    expect(nearest([52.2, 20.8], [{ item: "far", at: [52.3, 20.8] }, { item: "near", at: [52.2001, 20.8] }], 300, 4).map(x => x.item)).toEqual(["near"]);
  });
});

describe("new since last visit (browser storage only)", () => {
  it("marks nothing on the first visit, then only unseen IDs", () => {
    expect(readAndRemember("t", ["a", "b"]).newIds.size).toBe(0);
    const second = readAndRemember("t", ["a", "b", "c"]);
    expect([...second.newIds]).toEqual(["c"]);
    expect(second.lastVisit).toBeTruthy();
  });
  it("survives unavailable storage", () => {
    const original = Object.getOwnPropertyDescriptor(window, "localStorage")!;
    Object.defineProperty(window, "localStorage", { configurable: true, get() { throw new Error("blocked"); } });
    try { expect(readAndRemember("t", ["a"]).newIds.size).toBe(0); }
    finally { Object.defineProperty(window, "localStorage", original); }
  });
});

describe("shareable URL hash", () => {
  it("round-trips modes and record IDs with slashes", () => {
    const id = "permit:ST-MZ-OZ/WNIOSEK/24879/2026";
    expect(readHash(writeHash({ mode: "permits", id }))).toEqual({ mode: "permits", permitId: id, investmentId: null });
    expect(readHash(writeHash({ mode: "investments", id: "a:b" }))).toEqual({ mode: "investments", permitId: null, investmentId: "a:b" });
    expect(readHash("#inwestycje").mode).toBe("investments");
    expect(readHash("").mode).toBe("permits");
  });
});
