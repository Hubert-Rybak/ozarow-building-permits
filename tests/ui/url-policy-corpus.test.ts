import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { investmentUrl, parseInvestments } from "../../src/investments";

// Same fake-only corpus exercised by Python validation/publication tests.
const corpus = JSON.parse(
  readFileSync("tests/investments/fixtures/url_policy_corpus.json", "utf8"),
) as {
  baseDataset: Record<string, unknown>;
  cases: { id: string; url: string; accepted: boolean }[];
};
const paths: (string | number)[][] = [
  ["sources", 0, "url"],
  ["records", 0, "sourceUrl"],
  ["records", 0, "costs", 0, "sourceUrl"],
  ["records", 0, "dates", 0, "sourceUrl"],
  ["records", 0, "events", 0, "sourceUrl"],
  ["records", 0, "facts", 0, "sourceUrl"],
  ["records", 0, "geometries", 0, "properties", "sourceUrl"],
];

describe("shared credential URL query/fragment policy", () => {
  for (const entry of corpus.cases) {
    it(`${entry.id}: URL helper and every dataset URL field`, () => {
      expect(investmentUrl(entry.url) !== null).toBe(entry.accepted);
      for (const path of paths) {
        const dataset = JSON.parse(JSON.stringify(corpus.baseDataset));
        let target = dataset;
        for (const key of path.slice(0, -1)) target = target[key];
        target[path.at(-1)!] = entry.url;
        if (entry.accepted) expect(parseInvestments(dataset)).toEqual(dataset);
        else expect(() => parseInvestments(dataset)).toThrow(/kontrakt inwestycji/);
      }
    });
  }
});
