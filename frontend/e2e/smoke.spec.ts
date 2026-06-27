import { join } from "path";
import { test, expect, ASSETS, gotoApp, importImage, runPathFinding, waitForBoot } from "./fixtures";

// Stories A1 (new project) + B1 (import raster) + C2 (run path finding).
test("A1+B1+C2: new project, import image, run path finding", async ({ page }) => {
  // window.prompt for the project name — answer it before it opens.
  page.on("dialog", (d) => d.accept("E2E Smoke"));

  await gotoApp(page);

  // A1 — create a project via the Project menu. Creating it re-runs boot();
  // wait for that to settle before importing, or boot's applyProject() races
  // the upload and resets imageUrl back to null.
  await page.getByRole("button", { name: "Project" }).click();
  const booted = waitForBoot(page);
  await page.getByRole("button", { name: "New project…" }).click();
  await expect(page.locator(".menubar")).toContainText("E2E Smoke");
  await booted;

  // B1 — import the sample raster.
  await importImage(page, join(ASSETS, "sample.png"));
  await expect(page.locator(".menubar")).toContainText("sample.png");

  // C2 — run path finding; StatusBar reports shapes and the SVG renders.
  await runPathFinding(page);
  await expect(page.locator(".status")).toContainText("shapes");
  await expect(page.locator(".area-viewport svg").first()).toBeVisible();
});
