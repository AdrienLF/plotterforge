import { join } from "path";
import { test, expect, ASSETS, freshProject, gotoApp, importImage, runPathFinding } from "./fixtures";

/** Run path finding so studio.stats is set (required for the Save button). */
async function withStats(page: any, request: any, baseURL: string, name: string) {
  await freshProject(request, baseURL, name);
  await gotoApp(page);
  await importImage(page, join(ASSETS, "sample.png"));
  await runPathFinding(page);
}

// I1: saving a named version makes it appear in the Versions panel list.
test("I1: save version appears in the list", async ({ page, request, baseURL }) => {
  await withStats(page, request, baseURL!, "E2E I1");

  await page.locator('input[placeholder="Version name…"]').fill("My snapshot");
  await page.getByRole("button", { name: "＋ Save" }).click();

  await expect(page.locator(".ver .name", { hasText: "My snapshot" })).toBeVisible({ timeout: 10_000 });
});

// I2: loading a saved version restores the drawing and triggers a re-run (status → Ready).
test("I2: load version restores drawing and re-runs path finding", async ({ page, request, baseURL }) => {
  await withStats(page, request, baseURL!, "E2E I2");

  // Save a version.
  await page.locator('input[placeholder="Version name…"]').fill("Restore Me");
  await page.getByRole("button", { name: "＋ Save" }).click();
  await expect(page.locator(".ver .name", { hasText: "Restore Me" })).toBeVisible({ timeout: 10_000 });

  // Load it via the 👁 button — this re-runs path finding.
  await page.locator(".ver", { hasText: "Restore Me" }).getByRole("button", { name: "Load" }).click();
  // Re-run must complete before the test ends.
  await expect(page.locator(".status .state")).toHaveText("Ready", { timeout: 60_000 });
  // The log should mention "Loaded version".
  await expect(page.locator(".status .log")).toContainText("Loaded version");
});

// I3: star rating, move (▲/▼), and delete all work.
test("I3: rate, reorder, and delete versions", async ({ page, request, baseURL }) => {
  await withStats(page, request, baseURL!, "E2E I3");

  // Save two versions.
  await page.locator('input[placeholder="Version name…"]').fill("V1");
  await page.getByRole("button", { name: "＋ Save" }).click();
  await expect(page.locator(".ver .name", { hasText: "V1" })).toBeVisible({ timeout: 10_000 });

  await page.locator('input[placeholder="Version name…"]').fill("V2");
  await page.getByRole("button", { name: "＋ Save" }).click();
  await expect(page.locator(".ver .name", { hasText: "V2" })).toBeVisible({ timeout: 10_000 });

  // Rate V1 with 3 stars (V1 is now 2nd in list; V2 was saved last and appears first).
  const v1Row = page.locator(".ver", { hasText: "V1" });
  await v1Row.locator(".star").nth(2).click(); // 0-indexed → 3rd star
  // Stars 1–3 should be "on"; 4–5 should not.
  await expect(v1Row.locator(".star.on")).toHaveCount(3, { timeout: 5_000 });

  // Move V2 (top) down so V1 moves to top.
  const v2Row = page.locator(".ver", { hasText: "V2" });
  await v2Row.getByRole("button", { name: "Down" }).click();
  // V1 should now be first.
  await expect(page.locator(".ver").first()).toContainText("V1", { timeout: 5_000 });

  // Delete V2.
  await v2Row.getByRole("button", { name: "Delete" }).click();
  await expect(page.locator(".ver", { hasText: "V2" })).not.toBeVisible({ timeout: 5_000 });
  await expect(page.locator(".ver", { hasText: "V1" })).toBeVisible();
});

// I4: version thumbnails load (the img src returns a non-empty image).
test("I4: version thumbnail is served without error", async ({ page, request, baseURL }) => {
  await withStats(page, request, baseURL!, "E2E I4");

  await page.locator('input[placeholder="Version name…"]').fill("With Thumb");
  await page.getByRole("button", { name: "＋ Save" }).click();
  await expect(page.locator(".ver .name", { hasText: "With Thumb" })).toBeVisible({ timeout: 10_000 });

  // Extract the thumbnail URL and verify it returns a valid PNG.
  const thumbSrc = await page.locator(".ver .thumb").getAttribute("src");
  expect(thumbSrc).toMatch(/\/api\/version-thumb\//);

  const r = await request.get(`${baseURL}${thumbSrc}`);
  expect(r.ok()).toBeTruthy();
  expect(r.headers()["content-type"]).toMatch(/image\/png/i);
});
