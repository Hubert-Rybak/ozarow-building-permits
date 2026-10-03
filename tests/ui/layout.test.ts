import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
it("keeps the map legend collapsed until requested", () => {
  const source = readFileSync("src/ParcelMap.tsx", "utf8");
  expect(source).toMatch(/<details className="map-legend">/);
});
it("gives the source gap notice a distinct readable surface", () => {
  const css = readFileSync("src/styles.css", "utf8");
  expect(css).toMatch(/\.coverage-note\s*\{[^}]*background:/);
});
it("declares a bundled favicon without a root-relative request on Pages", () => {
  const html = readFileSync("index.html", "utf8");
  expect(html).toMatch(/rel="icon"[^>]*href="data:image\/svg\+xml/);
});
// Regression caught on real mobile data: a long status must not widen grid tracks.
it("allows filter labels to shrink within mobile grid tracks", () => {
  const css = readFileSync("src/styles.css", "utf8");
  expect(css).toMatch(/\.filter-grid label\s*\{[^}]*min-width:\s*0/);
});
