import { join } from "path";
import { test, expect, ASSETS, freshProject, gotoApp, importImage, runPathFinding } from "./fixtures";

// H1: selecting a library from the dropdown populates the pen list.
test("H1: load pen library populates the pen list", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E H1");
  await gotoApp(page);

  // The Pens panel is open by default in the pathfinding step.
  // Fetch available library names so the test isn't hard-coded to one brand.
  const { libraries } = await (await request.get(`${baseURL}/api/pens`)).json();
  const lib: string = libraries[0];

  await page.locator('select[title="Load a pen library"]').selectOption(lib);

  // The pen list should now match the chosen library's count.
  const { pens } = await (await request.get(`${baseURL}/api/pens/library/${encodeURIComponent(lib)}`)).json();
  await expect(page.locator(".pen")).toHaveCount(pens.length, { timeout: 10_000 });
});

// H2: the + button adds a pen; the ✕ button removes it.
test("H2: add pen then delete it", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E H2");
  await gotoApp(page);

  const before = await page.locator(".pen").count();

  await page.locator('button[title="Add pen"]').click();
  await expect(page.locator(".pen")).toHaveCount(before + 1, { timeout: 10_000 });

  await page.locator(".pen .del").last().click();
  await expect(page.locator(".pen")).toHaveCount(before, { timeout: 10_000 });
});

// H3: changing the distribution type is saved (POST /api/pens) on change.
// UX: "Distribution" label is clear; option labels like "Even weighted" vs "Random weighted"
//     could be shorter but are unambiguous.
test("H3: distribution type select is saved on change", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E H3");
  await gotoApp(page);

  // The distribution select is uniquely identified by its "luminance" option.
  await page.locator('select:has(option[value="luminance"])').selectOption("even");

  // Verify the value persisted to the backend.
  const { drawing_set } = await (await request.get(`${baseURL}/api/pens`)).json();
  expect(drawing_set.distribution_type).toBe("even");
});

// H4: distribution order select persists.
test("H4: distribution order select saves to backend", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E H4");
  await gotoApp(page);

  // The order select has options darkest/lightest/displayed/reversed.
  await page.locator('select:has(option[value="darkest"])').selectOption("lightest");

  const { drawing_set } = await (await request.get(`${baseURL}/api/pens`)).json();
  expect(drawing_set.distribution_order).toBe("lightest");
});

// H5: usage % on each pen reflects geometry from the last run.
// After a run with studio.stats set, at least one pen shows > 0 % usage.
test("H5: pen usage % is non-zero after a pathfinding run", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E H5");
  await gotoApp(page);
  await importImage(page, join(ASSETS, "sample.png"));
  await runPathFinding(page);

  // After runPathFinding the SSE done event sets studio.stats including per_pen counts.
  // The single default pen should have 100 % of the shapes.
  const firstPct = page.locator(".pen .pct").first();
  const pctText = await firstPct.textContent();
  const pct = parseInt(pctText ?? "0", 10);
  expect(pct, "usage % should be > 0 after a run").toBeGreaterThan(0);
});
