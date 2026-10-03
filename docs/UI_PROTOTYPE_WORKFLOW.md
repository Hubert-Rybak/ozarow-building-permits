# UI/UX prototype tournament — round 1

Baseline: `20ed307465800256fb1a144e55e154668e202841`. Product: Polish, real-data parcel/building-record explorer for Ożarów Mazowiecki. Primary surface **Explore**, secondary **Inspect**; not a marketing landing page.

## Roles and isolated ownership

Five distinct designer/implementer subagents each own one detached worktree under `/opt/data/cache/scratch/ozarow-ui-round1/prototype-0N`. No designer may edit production worktree, other candidates, source datasets/importers, GitHub settings or workflows. No child commits/pushes. A separate three-person jury evaluates all five candidates. None judges its own work. A fresh, sixth implementer ports the winner into the production branch after the jury selection. Parent owns integration, verification, commits and deployment.

## Five proposals (different composition/interaction, not color swaps)

1. **P1 Atlas GIS** — persistent map canvas, compact tools/results rail, contextual inspector; native CSS.
2. **P2 Civic daisyUI** — accessible light civic UI, progressively disclosed filter drawer, clear map/list tabs and clean detail drawer; locally built Tailwind + daisyUI.
3. **P3 Tailwind Workspace** — compact search toolbar and dual-pane workspace, precise information density, focused inline inspection; locally built Tailwind.
4. **P4 Register** — readable list-first evidence explorer, aligned record rows and contextual map, warm restrained typography; native CSS.
5. **P5 Pocket Map** — mobile-first map canvas, bottom navigation and compact selection/peek cards with reversible inspection; native CSS.

Tailwind/daisyUI are genuine compiled dependencies when used, not decorative class names or CDN scripts. Registry-resolved exact versions for experiments: tailwindcss/@tailwindcss/vite 4.3.3, daisyui 5.7.47; preserve each lockfile. Official install references: tailwindcss.com/docs/installation/using-vite and daisyui.com/docs/install/react/.

## Common task/semantic contract (hard gates)

- Actual baseline records/ULDK polygons only; no invented stats/geometries, fake forecasts or fake permits. Counts derived from filters. Decision is not automatically approval; notifications remain distinct.
- Default last three calendar months in Europe/Warsaw, inclusive/clamped; explicit all-dates option and reset. Shared filtering drives list/map/counts/CSV.
- On phones, tapping a mapped list row switches to map, highlights/framing all available associated polygons and shows map in viewport. Same-ID selection must work repeatedly. Unmapped rows stay accessible with honest no-geometry details.
- Polygon selection opens inspection; close restores a usable map without remounting Leaflet or discarding filters/camera. Keyboard/accessible alternatives exist.
- Retain search, all current filter dimensions, sorting, CSV, source links, provenance, missing/partial geometry indicators, retries/loading/empty/no-results/errors and consistency warnings. Lengthy explanations collapsed by default.
- At 390x844 and 320x700 phones: useful map/navigation near first screen, >=44px primary touch targets, no page-level horizontal overflow measured against documentElement.clientWidth, clear focus, sensible hierarchy. Desktop 1440x1000 remains useful.
- `npm test`, production build/TypeScript and dist contract pass; no secrets/source archives enter build. Browser console/runtime clean. Scope source/UI tests/config/dependencies only.

## Deliverables per candidate

Runnable React/Vite prototype; source diff and changed files; `.cache/design-output/SPEC.md` (composition, tokens, UX flows, dependency/runtime costs, risks); `verification.json` with actual executed checks and caveats; `desktop.png`, `mobile.png`, `mobile-selected.png` and optionally narrow screenshot. All artifacts use real data. Screenshots are not substitutes for working interactions.

Parent independently rebuilds/tests/opens every candidate, verifies artifact handles and counts all five programmatically. A comparison gallery/contact sheet and portable source patches are retained for the user/repo separately from production assets.

## Jury workflow and frozen rubric

Three new reviewer subagents: **mobile UX/accessibility**, **visual/information design**, **frontend reliability/performance**. Each evaluates **all 5** candidates from screenshots plus actual source/demo/verification artifacts, not authors' persuasive self-reports. Each provides hard-gate findings and criterion scores 0–10 with concrete reasoning:

- Mobile map/list/detail task completion: **35%**.
- Information hierarchy and reduced text/clutter: **20%**.
- Accessibility/readability/touch/keyboard: **20%**.
- Visual coherence, polish and desktop usability: **15%**.
- Implementation robustness, dependency/bundle cost: **10%**.

Compute each candidate's weighted score, then mean across three jurors in Python. Any confirmed unmet hard gate makes a candidate ineligible until revised/rechecked. Tie within 0.05/10: higher aggregate mobile score, then lower implementation risk. No selection based solely on framework or visual novelty. Publish raw jury ballots, aggregate score and rationale. This selects the design direction; implementation review remains mandatory.

## Gates / execution sequence

1. **Pre-flight:** baseline clean/current, isolated directories, contracts/rubric frozen.
2. Five designers run in parallel; production untouched while prototypes are compared.
3. **Revision:** parent verification; fix concrete blockers (max 3 cycles, escalate if not converging). Never present fake output as a substitute for a failed prototype.
4. Freeze exact candidate manifest; three jury members evaluate independently in parallel; parent programmatically validates all5x3 ballots, calculates ranking and picks eligible winner.
5. New implementation subagent ports winner in TDD (RED→GREEN), preserving data/selection/filter semantics and meeting jury fixes. No self-review or child publishing.
6. Independent **SPEC** review first, then **QUALITY/security** review; revise/recheck blockers, fingerprints bind reviews.
7. Parent tests all suites/build/dist plus actual mobile/desktop interactions and visual inspection. PR, green CI, merge and Pages deploy.
8. Read back remote refs/blobs, live JS/CSS/data bytes and test the deployed app. Only then report production complete, provide five-option comparison and winner rationale.

If credentials/network/tool failures block publication, preserve all verified artifacts and report the real blocker; do not say deployed. If user steers, newer requirements win and remaining work adjusts.
