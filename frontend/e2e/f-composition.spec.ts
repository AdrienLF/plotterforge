import { readFileSync } from "fs";
import { join } from "path";
import { test, expect, ASSETS, freshProject, gotoApp } from "./fixtures";

/** Set up a project with one generated PF layer; returns the layer id. */
async function setupOneLayer(request: any, baseURL: string, name: string): Promise<string> {
  await freshProject(request, baseURL, name);
  await request.post(`${baseURL}/api/image`, {
    multipart: {
      file: { name: "sample.png", mimeType: "image/png", buffer: readFileSync(join(ASSETS, "sample.png")) },
    },
  });
  const add = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: {} })).json();
  const id: string = add.composition.layers.at(-1).id;
  await request.post(`${baseURL}/api/composition/layers/${id}/pathfinding/generate`, {
    data: { pfm_id: "spiral", params: {} },
  });
  return id;
}

// F1: reordering layers with ↑/↓ changes z-order in the composition.
test("F1: layer ↑/↓ buttons reorder the layer list", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E F1");
  await request.post(`${baseURL}/api/image`, {
    multipart: {
      file: { name: "sample.png", mimeType: "image/png", buffer: readFileSync(join(ASSETS, "sample.png")) },
    },
  });
  // Add two layers: A then B (B ends up on top visually / higher index).
  const addA = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: { name: "Layer A" } })).json();
  await request.post(`${baseURL}/api/composition/add-layer`, { data: { name: "Layer B" } });

  await gotoApp(page);

  // Composition panel renders layers top-first (reversed), so B is shown first.
  const layers = page.locator(".layer");
  await expect(layers.first()).toContainText("Layer B");
  await expect(layers.nth(1)).toContainText("Layer A");

  // Click ↓ on Layer B (top slot) to move it below A.
  await page.locator(".layer", { hasText: "Layer B" }).getByRole("button", { name: "Move down" }).click();

  // Order should now be A on top, B below.
  await expect(layers.first()).toContainText("Layer A", { timeout: 10_000 });
  await expect(layers.nth(1)).toContainText("Layer B");
});

// F2: unchecking a layer's visibility disables Export and Plot when no layers remain visible.
test("F2: hiding the only layer disables Export and Plot", async ({ page, request, baseURL }) => {
  const id = await setupOneLayer(request, baseURL!, "E2E F2");
  await gotoApp(page);

  // Layer is visible by default → Export SVG is enabled.
  await page.getByRole("button", { name: "File" }).click();
  await expect(page.getByRole("button", { name: "Export SVG" })).toBeEnabled();
  // Close the menu.
  await page.keyboard.press("Escape");

  // Uncheck the layer's visibility checkbox.
  await page.locator(".layer input[type='checkbox']").first().uncheck();

  // All layers hidden → Export and Plot are now disabled.
  await expect(page.locator('button[title="Plot"]')).toBeDisabled({ timeout: 5_000 });
  await page.getByRole("button", { name: "File" }).click();
  await expect(page.getByRole("button", { name: "Export SVG" })).toBeDisabled();
});

// F7: duplicate creates a copy; delete removes it.
test("F7: duplicate and delete layer", async ({ page, request, baseURL }) => {
  const id = await setupOneLayer(request, baseURL!, "E2E F7");
  await gotoApp(page);

  const before = await page.locator(".layer").count();

  // Duplicate the layer.
  await page.locator(".layer").first().getByRole("button", { name: "Duplicate" }).click();
  await expect(page.locator(".layer")).toHaveCount(before + 1, { timeout: 10_000 });
  // The copy's name ends with " copy".
  await expect(page.locator(".layer").first()).toContainText("copy");

  // Delete the copy.
  await page.locator(".layer").first().getByRole("button", { name: "Delete" }).click();
  await expect(page.locator(".layer")).toHaveCount(before, { timeout: 10_000 });
  await expect(page.locator(".layer").first()).not.toContainText("copy");
});
