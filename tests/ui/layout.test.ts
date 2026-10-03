import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
const css = readFileSync("src/styles.css", "utf8");
it("keeps text readable: nothing below 11px, 16px inputs on phones (no iOS zoom), 44px targets", () => {
  const sizes = Array.from(css.matchAll(/font-size:\s*(\d+)px/g), match => Number(match[1]));
  expect(sizes.filter(size => size < 11)).toEqual([]);
  expect(css).toMatch(/\.search-box input\s*\{[^}]*font-size:\s*16px/);
  expect(css).toMatch(/\.search-box input\s*\{[^}]*min-height:\s*44px/);
  expect(css).toMatch(/:root\s*\{[^}]*font-size:\s*15px/);
});
it("gives the source gap notice a distinct readable surface", () => {
  expect(css).toMatch(/\.coverage-note\s*\{[^}]*background:/);
});
it("declares a bundled favicon without a root-relative request on Pages", () => {
  const html = readFileSync("index.html", "utf8");
  expect(html).toMatch(/rel="icon"[^>]*href="data:image\/svg\+xml/);
});
// Regression caught on real mobile data: a long status must not widen grid tracks.
it("allows filter labels to shrink within grid tracks", () => {
  expect(css).toMatch(/\.filter-grid label\s*\{[^}]*min-width:\s*0/);
});
it("self-hosts the interface font instead of loading it from a remote CDN", () => {
  expect(readFileSync("src/main.tsx", "utf8")).toMatch(/@fontsource\/ibm-plex-sans\/latin-ext-400\.css/);
  expect(css).not.toMatch(/fonts\.googleapis/);
});
