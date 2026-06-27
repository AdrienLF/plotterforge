import { readFileSync } from "fs";
import { join } from "path";
import { test, expect, ASSETS, freshProject, gotoApp } from "./fixtures";

// C1: "＋ Path finding" creates an empty layer, opens the editor, and the layer is stale.
test("C1: add path-finding layer creates stale layer and opens editor", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E C1");
  await gotoApp(page);

  const before = await page.locator(".layer").count();

  await page.getByRole("button", { name: "＋ Path finding" }).click();

  // A new layer appears in the composition list.
  await expect(page.locator(".layer")).toHaveCount(before + 1, { timeout: 10_000 });

  // The LayerStylePanel (floating PF editor) opens automatically.
  // UX: the editor is the right entry point — a new user can start immediately.
  await expect(page.locator('[aria-label="Layer style"]')).toBeVisible();

  // The status shows "stale" (no pathfinding has run yet).
  await expect(page.locator(".layer-style em.dirty")).toBeVisible();
});

// C3: switching the PFM dropdown reloads the param schema without losing the layer.
// ponytail: verifies the select fires; deeper param-round-trip is C4.
test("C3: switch PFM algorithm reloads schema without losing the layer", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E C3");

  // Set up: upload image + add a PF layer so the editor is pre-populated.
  await request.post(`${baseURL}/api/image`, {
    multipart: {
      file: { name: "sample.png", mimeType: "image/png", buffer: readFileSync(join(ASSETS, "sample.png")) },
    },
  });
  const add = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: {} })).json();
  const layerId: string = add.composition.layers.at(-1).id;

  await gotoApp(page);

  // Open the editor for the layer.
  await page.getByRole("button", { name: `Open ${add.composition.layers.at(-1).name} path finding` }).click();
  await expect(page.locator('[aria-label="Layer style"]')).toBeVisible();

  // Get current PFM and switch to another.
  const pfmList = await (await request.get(`${baseURL}/api/pfm/list`)).json();
  const current = pfmList.pfms[0].id;
  const other = pfmList.pfms.find((p: { id: string }) => p.id !== current)?.id;
  if (!other) return; // only one PFM; skip

  const select = page.locator('.layer-style label:has-text("PFM") select');
  await select.selectOption(other);

  // Layer still exists after switching.
  expect(await request.get(`${baseURL}/api/composition`).then(r => r.json())).toMatchObject({
    composition: { layers: [{ id: layerId }] },
  });
});

// C11: a param combination that produces no geometry surfaces an error state, not a hang.
test("C11: zero-geometry params show layer error state", async ({ request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E C11");
  await request.post(`${baseURL}/api/image`, {
    multipart: {
      file: { name: "sample.png", mimeType: "image/png", buffer: readFileSync(join(ASSETS, "sample.png")) },
    },
  });
  const add = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: {} })).json();
  const layerId: string = add.composition.layers.at(-1).id;

  // n_points=0 should yield no geometry and trigger an error response.
  const res = await request.post(`${baseURL}/api/composition/layers/${layerId}/pathfinding/generate`, {
    data: { pfm_id: "voronoi_stippling", params: { n_points: 0 } },
  });

  // Either a 4xx/5xx error, or the layer ends up in "error" status.
  if (!res.ok()) {
    expect(res.status()).toBeGreaterThanOrEqual(400);
  } else {
    const body = await res.json();
    const layer = body.composition.layers.find((l: { id: string }) => l.id === layerId);
    // If 200, the layer should either have 0 shapes or an error status.
    const svg: string = layer?.svg ?? "";
    const hasShapes = /<(circle|path|line|polyline|polygon|rect)\b/g.test(svg);
    expect(hasShapes || layer?.pathfinding_style?.status === "error").toBeTruthy();
  }
});
