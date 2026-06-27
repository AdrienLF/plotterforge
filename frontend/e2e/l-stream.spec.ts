import { join } from "path";
import { test, expect, ASSETS, freshProject, gotoApp, importImage } from "./fixtures";

// L1: SSE progress bar appears during a PF run and disappears on completion.
test("L1: progress bar visible during path-finding, gone when idle", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E L1");
  await gotoApp(page);
  await importImage(page, join(ASSETS, "sample.png"));

  // Start path finding without waiting for completion.
  await page.locator('button[title="Run path finding"]').click();

  // The progress bar should appear while studio.processing is true.
  await expect(page.locator(".status .bar")).toBeVisible({ timeout: 10_000 });

  // Wait for completion.
  await expect(page.locator(".status .state")).toHaveText("Ready", { timeout: 60_000 });

  // Progress bar is hidden once processing ends.
  await expect(page.locator(".status .bar")).not.toBeVisible();
});

// L2: badge text correctly reflects GPU vs CPU backend from /api/pfm/list.
test("L2: status badge reflects GPU/CPU backend", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E L2");
  await gotoApp(page);

  const { backend } = await (await request.get(`${baseURL}/api/pfm/list`)).json();
  const expectedPrefix = backend.startsWith("torch") ? "GPU" : "CPU";

  const badgeText = await page.locator(".badge").textContent();
  expect(badgeText).toContain(expectedPrefix);
  expect(badgeText).toContain(backend);
});
