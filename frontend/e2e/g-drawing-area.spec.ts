import { test, expect, freshProject, gotoApp } from "./fixtures";

// G1: selecting a preset from the Drawing Area panel persists width/height.
test("G1: area preset sets width and height via API", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E G1");
  await gotoApp(page);

  // Drawing Area panel is collapsed by default in the pathfinding step.
  await page.getByRole("button", { name: "Drawing Area" }).click();

  // Fetch presets to avoid hard-coding dimensions.
  const { presets } = await (await request.get(`${baseURL}/api/area`)).json();
  const [expectedW, expectedH] = presets["A4"] as [number, number];

  // The preset select is uniquely identified by its A4 option.
  await page.locator('select:has(option[value="A4"])').selectOption("A4");

  await page.waitForTimeout(300);
  const { area } = await (await request.get(`${baseURL}/api/area`)).json();
  expect(area.width).toBeCloseTo(expectedW, 0);
  expect(area.height).toBeCloseTo(expectedH, 0);
});

// G2: padding inputs save to the backend.
test("G2: padding left input saves to area settings", async ({ page, request, baseURL }) => {
  await freshProject(request, baseURL!, "E2E G2");
  await gotoApp(page);

  await page.getByRole("button", { name: "Drawing Area" }).click();

  // The four padding inputs live inside .grid4 (L/R/T/B order).
  const padInputs = page.locator(".grid4 input");
  await padInputs.first().fill("15");
  await padInputs.first().press("Tab"); // triggers onchange → api.saveArea()

  await page.waitForTimeout(300);
  const { area } = await (await request.get(`${baseURL}/api/area`)).json();
  expect(area.pad_left).toBe(15);
});
