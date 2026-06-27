import { readFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { test, expect, ASSETS, freshProject } from "./fixtures";

const HERE = dirname(fileURLToPath(import.meta.url));

// Story C9 — per-PFM timing matrix (representative 3-PFM subset). Drives the
// synchronous per-layer pathfinding endpoint against the live backend so it
// exercises the real algorithms, records wall-clock to the perf artifact, and
// warns (never fails) when a run exceeds its soft budget.
const SUBSET = ["voronoi_stippling", "grid_halftone", "spiral"];

type Budgets = { default_ms: number; pfm: Record<string, number> };
const budgets: Budgets = JSON.parse(readFileSync(join(HERE, "perf", "budgets.json"), "utf8"));

function countShapes(svg: string): number {
  return (svg.match(/<(circle|path|line|polyline|polygon|rect)\b/g) || []).length;
}

test("C9: per-PFM timing subset records to the perf artifact", async ({ request, baseURL, recordPerf }) => {
  await freshProject(request, baseURL!, "E2E Perf");
  // Ensure an image is loaded for the current project.
  const up = await request.post(`${baseURL}/api/image`, {
    multipart: {
      file: { name: "sample.png", mimeType: "image/png", buffer: readFileSync(join(ASSETS, "sample.png")) },
    },
  });
  expect(up.ok()).toBeTruthy();

  for (const pfm of SUBSET) {
    // Fresh empty path-finding layer to render into.
    const add = await (await request.post(`${baseURL}/api/composition/add-layer`, { data: {} })).json();
    const layerId: string = add.composition.layers.at(-1).id;

    const t0 = Date.now();
    const res = await request.post(`${baseURL}/api/composition/layers/${layerId}/pathfinding/generate`, {
      data: { pfm_id: pfm, params: {} },
    });
    const duration_ms = Date.now() - t0;
    expect(res.ok(), `${pfm} should generate`).toBeTruthy();

    const body = await res.json();
    const layer = body.composition.layers.find((l: { id: string }) => l.id === layerId);
    const shapes = countShapes(layer.svg || "");
    expect(shapes, `${pfm} produced no geometry`).toBeGreaterThan(0);

    recordPerf({ story: "C9", pfm, duration_ms, shapes });
    const budget = budgets.pfm[pfm] ?? budgets.default_ms;
    if (duration_ms > budget) {
      console.warn(`[perf] ${pfm}: ${duration_ms}ms > budget ${budget}ms (soft)`);
    }
    console.log(`[perf] ${pfm}: ${duration_ms}ms, ${shapes} shapes`);
  }
});
