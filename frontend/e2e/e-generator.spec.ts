import { test, expect, freshProject, gotoApp } from "./fixtures";

// E1: "＋ Generator" button navigates to the Generate step.
test("E1: ＋ Generator button navigates to the Generate step", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E E1");
  await gotoApp(page);

  await page.getByRole("button", { name: "＋ Generator" }).click();

  // The "Generate" step tab should become active.
  await expect(page.getByRole("tab", { name: "Generate" })).toHaveAttribute("aria-selected", "true");
  // The GeneratePanel mounts — the generator select is the entry point.
  await expect(page.locator(".gen-select")).toBeVisible({ timeout: 5_000 });
});

// E2: default generator (spokes_and_circles) auto-generates when Auto is on.
test("E2: Auto-redraw generates on Generate step entry", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E E2");
  await gotoApp(page);

  await page.getByRole("button", { name: "＋ Generator" }).click();
  await expect(page.locator(".gen-select")).toBeVisible({ timeout: 5_000 });

  // Auto is true by default; debounce fires after 350ms.
  await expect(page.locator(".status .state")).toHaveText("Ready", { timeout: 60_000 });

  // The layer should now have SVG geometry.
  const { composition } = await (await request.get(`${baseURL}/api/composition`)).json();
  expect(composition.layers[0]?.svg).toMatch(/<(path|line|polyline|circle)\b/);
});

// E3: unchecking Auto suppresses auto-redraw; explicit Generate still works.
test("E3: Auto off suppresses auto-redraw; explicit Generate triggers generation", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E E3");
  await gotoApp(page);

  await page.getByRole("button", { name: "＋ Generator" }).click();
  await expect(page.locator(".gen-select")).toBeVisible({ timeout: 5_000 });

  // Uncheck Auto before the 350ms debounce fires.
  const autoCheck = page.locator("label.auto input[type='checkbox']");
  await expect(autoCheck).toBeChecked();
  await autoCheck.uncheck();

  // Wait longer than the debounce; status should remain Idle.
  await page.waitForTimeout(600);
  await expect(page.locator(".status .state")).toHaveText("Idle");

  // Explicit click → generation completes.
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.locator(".status .state")).toHaveText("Ready", { timeout: 60_000 });
});
