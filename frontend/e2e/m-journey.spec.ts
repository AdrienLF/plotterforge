import { readFileSync } from "fs";
import { join } from "path";
import { test, expect, ASSETS, freshProject, gotoApp } from "./fixtures";

// M1 [R+P]: Import → 2 PF layers (different algorithms) → load pens → export SVG.
// Skips the SAM2 region step (D-epic, gated on model availability).
test("M1: multi-layer artwork — import, 2 PF layers, pens, export SVG", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E M1");

  // Upload image and add two layers with different PFMs via API (fast path).
  await request.post(`${baseURL}/api/image`, {
    multipart: {
      file: { name: "sample.png", mimeType: "image/png", buffer: readFileSync(join(ASSETS, "sample.png")) },
    },
  });
  const addA = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: { name: "Spiral" } })).json();
  const idA: string = addA.composition.layers.at(-1).id;
  await request.post(`${baseURL}/api/composition/layers/${idA}/pathfinding/generate`, {
    data: { pfm_id: "spiral", params: {} },
  });

  const addB = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: { name: "Stipple" } })).json();
  const idB: string = addB.composition.layers.at(-1).id;
  await request.post(`${baseURL}/api/composition/layers/${idB}/pathfinding/generate`, {
    data: { pfm_id: "voronoi_stippling", params: { n_points: 20 } },
  });

  await gotoApp(page);

  // Both layers visible in the Composition panel.
  await expect(page.locator(".layer")).toHaveCount(2, { timeout: 10_000 });

  // Load a pen library via UI.
  const { libraries } = await (await request.get(`${baseURL}/api/pens`)).json();
  await page.locator('select[title="Load a pen library"]').selectOption(libraries[0]);
  await expect(page.locator(".pen")).toHaveCount(
    (await (await request.get(`${baseURL}/api/pens/library/${encodeURIComponent(libraries[0])}`)).json()).pens.length,
    { timeout: 10_000 },
  );

  // Export SVG via API — should include geometry from both layers.
  const r = await request.get(`${baseURL}/api/export`);
  expect(r.ok()).toBeTruthy();
  const svg = await r.text();
  expect(svg).toMatch(/^<svg\s/);
  // Combined export must contain at least one drawn shape from the layers.
  expect(svg).toMatch(/<(path|line|polyline|circle)\b/);
});

// M2 [R]: Generator-only artwork — generate → save version → export SVG.
test("M2: generator-only artwork — generate, version, export", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E M2");
  await gotoApp(page);

  // Jump to Generate step and auto-generate spokes_and_circles.
  await page.getByRole("button", { name: "＋ Generator" }).click();
  await expect(page.locator(".gen-select")).toBeVisible({ timeout: 5_000 });
  await expect(page.locator(".status .state")).toHaveText("Ready", { timeout: 60_000 });

  // Versions panel is collapsed by default in the Generate step — open it.
  await page.getByRole("button", { name: "Versions" }).click();

  // Save a named version (＋ Save is enabled once studio.stats is set by the done event).
  await page.locator('input[placeholder="Version name…"]').fill("M2 snapshot");
  await page.getByRole("button", { name: "＋ Save" }).click();
  await expect(page.locator(".ver .name", { hasText: "M2 snapshot" })).toBeVisible({ timeout: 10_000 });

  // Export — the generated SVG should be a valid document.
  const r = await request.get(`${baseURL}/api/export`);
  expect(r.ok(), "export should succeed").toBeTruthy();
  const svg = await r.text();
  expect(svg).toMatch(/^<svg\s/);
  expect(svg).toContain("</svg>");
});
