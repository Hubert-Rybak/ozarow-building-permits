/** Synthetic warning/availability fixtures: never served by the application. */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "../../src/App";
import type { InvestmentDataset } from "../../src/investments";
import corpus from "../investments/fixtures/url_policy_corpus.json";
import { dataset, metadata, parcels } from "./fixtures";

vi.mock("../../src/ParcelMap", () => ({ default: () => <div /> }));
vi.mock("../../src/InvestmentsMap", () => ({ default: () => <div /> }));
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

type Availability = "fresh" | "retained" | "unavailable";
function warningsFixture(status: Availability = "fresh") {
  const data = structuredClone(corpus.baseDataset) as InvestmentDataset;
  data.warnings = ["TEST ONLY full dataset limitation"];
  data.sources[0].warnings = ["TEST ONLY full source limitation"];
  data.sources[0].status = status;
  if (status === "unavailable") {
    data.records = [];
    data.sources[0].recordCount = 0;
    data.counts = { records: 0, mapped: 0, geometries: 0, bySource: { official: 0 } };
  }
  return data;
}

async function showInvestments(status: Availability = "fresh", fail = false) {
  const investments = warningsFixture(status);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: !(fail && url.includes("investments.json")), status: 503,
    json: async () => url.includes("investments.json") ? investments
      : url.includes("permits.json") ? dataset
        : url.includes("parcels.geojson") ? parcels : metadata,
  })));
  const view = render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Inwestycje" }));
  await waitFor(() => expect(screen.getByTestId("investments-status"))
    .toHaveAttribute("data-state", fail ? "error" : "ready"));
  return view.container.querySelector(".investment-atlas") as HTMLElement;
}

describe("compact investment limitations disclosure", () => {
  it("keeps full routine warning text inside closed O danych, not in an alert above the map", async () => {
    const atlas = await showInvestments();
    const disclosure = atlas.querySelector("#investment-provenance")!;
    expect(disclosure).not.toHaveAttribute("open");
    for (const text of ["TEST ONLY full dataset limitation", "TEST ONLY source: TEST ONLY full source limitation"]) {
      const warning = within(atlas).getByText(text);
      expect(warning.closest("details")).toBe(disclosure);
      expect(warning).not.toBeVisible();
    }
    expect(within(atlas).queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: /O danych/ }));
    expect(disclosure).toHaveAttribute("open");
    expect(within(atlas).getByText("TEST ONLY full dataset limitation")).toBeVisible();
    expect(within(atlas).getByText("TEST ONLY source: TEST ONLY full source limitation")).toBeVisible();
  });

  it.each(["retained", "unavailable"] as const)("keeps a compact %s source failure visible outside the closed disclosure", async (status) => {
    const atlas = await showInvestments(status);
    const alert = within(atlas).getByRole("alert", { name: "Problemy z pobraniem źródeł" });
    expect(alert).toBeVisible();
    expect(alert.closest("details")).toBeNull();
    expect(alert).toHaveTextContent("TEST ONLY source");
    expect(alert).toHaveTextContent(status === "retained" ? "Zachowany poprzedni odczyt" : "Źródło niedostępne");
    expect(alert).not.toHaveTextContent("TEST ONLY full source limitation");
    expect(atlas.querySelector("#investment-provenance")).not.toHaveAttribute("open");
    expect(within(atlas).getByText("TEST ONLY full dataset limitation")).not.toBeVisible();
    fireEvent.click(within(alert).getByRole("link", { name: "Szczegóły w „O danych”" }));
    expect(atlas.querySelector("#investment-provenance")).toHaveAttribute("open");
    expect(within(atlas).getByText("TEST ONLY full dataset limitation")).toBeVisible();
  });

  it("never collapses a fatal investment loading error or its retry button", async () => {
    const atlas = await showInvestments("fresh", true);
    const alert = within(atlas).getByRole("alert");
    expect(alert).toBeVisible();
    expect(alert.closest("details")).toBeNull();
    expect(within(alert).getByRole("button", { name: "Spróbuj ponownie — inwestycje" })).toBeVisible();
  });
});
