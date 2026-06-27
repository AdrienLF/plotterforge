import { readFileSync } from "fs";
import { join } from "path";
import { test, expect, ASSETS, freshProject, gotoApp } from "./fixtures";

/** Create a project with a generated spiral layer and return composition data. */
async function setupLayerProject(request: any, baseURL: string, name: string) {
  await freshProject(request, baseURL, name);
  await request.post(`${baseURL}/api/image`, {
    multipart: {
      file: { name: "sample.png", mimeType: "image/png", buffer: readFileSync(join(ASSETS, "sample.png")) },
    },
  });
  const add = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: {} })).json();
  const layerId: string = add.composition.layers.at(-1).id;
  await request.post(`${baseURL}/api/composition/layers/${layerId}/pathfinding/generate`, {
    data: { pfm_id: "spiral", params: {} },
  });
  return { layerId, composition: add.composition };
}

// J1: export SVG downloads a valid SVG document.
test("J1: export SVG returns valid SVG content", async ({ request, baseURL }) => {
  await setupLayerProject(request, baseURL!, "E2E J1");

  const r = await request.get(`${baseURL}/api/export`);
  expect(r.ok(), "export should succeed").toBeTruthy();
  expect(r.headers()["content-type"]).toMatch(/svg/i);

  const body = await r.text();
  expect(body).toMatch(/^<svg\s/);
  expect(body).toContain("</svg>");
});

// J2: export with split=1 downloads a zip containing per-layer SVG files.
test("J2: export layers (zip) returns application/zip", async ({ request, baseURL }) => {
  await setupLayerProject(request, baseURL!, "E2E J2");

  const r = await request.get(`${baseURL}/api/export?split=1`);
  expect(r.ok(), "zip export should succeed").toBeTruthy();
  expect(r.headers()["content-type"]).toMatch(/zip/i);

  // Zip files start with PK (0x50 0x4B).
  const body = await r.body();
  expect(body[0]).toBe(0x50);
  expect(body[1]).toBe(0x4b);
});

// J3: exported SVG dimensions match the composition page (default A3: 297x420mm).
test("J3: exported SVG width/height match the composition page", async ({ request, baseURL }) => {
  await setupLayerProject(request, baseURL!, "E2E J3");

  // Read the current composition page so the assertion doesn't hard-code a preset.
  const { composition } = await (await request.get(`${baseURL}/api/composition`)).json();
  const w: number = composition.page.width;
  const h: number = composition.page.height;

  const r = await request.get(`${baseURL}/api/export`);
  const svg = await r.text();

  // _fmt(297.0) → "297"; check the SVG header carries the page dimensions in mm.
  expect(svg).toContain(`width="${w}mm"`);
  expect(svg).toContain(`height="${h}mm"`);
});

// J4: hidden layers are excluded — when all layers are hidden, Export is disabled in the UI.
// (The API would fall back to _drawing; the UI gate is the user-visible protection.)
test("J4: hidden-only composition disables Export SVG in the UI", async ({ page, request, baseURL }) => {
  await setupLayerProject(request, baseURL!, "E2E J4");
  await gotoApp(page);

  // Layer is visible by default.
  await page.getByRole("button", { name: "File" }).click();
  await expect(page.getByRole("button", { name: "Export SVG" })).toBeEnabled();
  await page.keyboard.press("Escape");

  // Hide the layer.
  await page.locator(".layer input[type='checkbox']").first().uncheck();

  // Export should now be disabled (hasVisibleLayers = false).
  await expect(page.locator('button[title="Plot"]')).toBeDisabled({ timeout: 5_000 });
  await page.getByRole("button", { name: "File" }).click();
  await expect(page.getByRole("button", { name: "Export SVG" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Export layers (zip)" })).toBeDisabled();
});
