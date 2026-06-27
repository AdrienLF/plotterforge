import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { appendFileSync, mkdirSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const ASSETS = join(HERE, "assets");
const PERF_FILE = join(HERE, "perf", "results.jsonl");

// ── App-level helpers ───────────────────────────────────────────────────────

/**
 * Make a fresh, empty backend project the current one. The backend keeps a
 * single global "current project", so tests must isolate themselves or they
 * inherit each other's image + layers.
 */
export async function freshProject(request: APIRequestContext, baseURL: string, name: string) {
  const r = await request.post(`${baseURL}/api/projects`, { data: { name } });
  expect(r.ok(), "create project").toBeTruthy();
}

/** Load the app and wait for boot() to populate the backend badge. */
export async function gotoApp(page: Page) {
  await page.goto("/");
  await expect(page.locator(".badge")).not.toHaveText("… · …", { timeout: 20_000 });
}

/** Wait for the boot() sequence (its trailing GET /api/versions) to settle. */
export async function waitForBoot(page: Page) {
  await page.waitForResponse(
    (r) => r.url().includes("/api/versions") && r.request().method() === "GET",
    { timeout: 20_000 },
  );
}

/** Import a raster/SVG via the hidden file input (same input the menu/rail use). */
export async function importImage(page: Page, file: string) {
  await page.locator('input[type="file"]').setInputFiles(file);
  // Run-path-finding enables once studio.imageUrl is set.
  await expect(page.locator('button[title="Run path finding"]')).toBeEnabled({ timeout: 15_000 });
}

/** Run the single-PFM "Run path finding" flow and wait for the SSE result. */
export async function runPathFinding(page: Page) {
  await page.locator('button[title="Run path finding"]').click();
  await waitForReady(page);
}

/** Wait for the StatusBar to report a finished run. */
export async function waitForReady(page: Page) {
  await expect(page.locator(".status .state")).toHaveText("Ready", { timeout: 60_000 });
}

/** Click a workflow step tab by its label (Path Finding / Generate / Composition / Plot). */
export async function gotoStep(page: Page, label: string) {
  await page.getByRole("tab", { name: label }).click();
}

// ── Perf recorder fixture ────────────────────────────────────────────────────

export type PerfRecord = { story: string; pfm?: string; duration_ms: number; shapes?: number };
export type RecordPerf = (rec: PerfRecord) => void;

export const test = base.extend<{ recordPerf: RecordPerf }>({
  recordPerf: async ({}, use) => {
    mkdirSync(dirname(PERF_FILE), { recursive: true });
    await use((rec) => appendFileSync(PERF_FILE, JSON.stringify({ ts: Date.now(), ...rec }) + "\n"));
  },
});

export { expect };
