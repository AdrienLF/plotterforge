import { defineConfig, devices } from "@playwright/test";

// Isolated test port (dev server uses 7438). Override with E2E_PORT if taken.
const PORT = process.env.E2E_PORT || "7440";
process.env.PLOTTER_PORT = PORT; // global-setup spawns the backend on this port

export default defineConfig({
  testDir: "./e2e",
  // The Flask backend keeps global state (one current project), so tests must
  // not run concurrently. ponytail: serial run, revisit only if it gets slow.
  workers: 1,
  fullyParallel: false,
  globalSetup: "./e2e/global-setup.ts",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    ["json", { outputFile: "e2e/perf/playwright-report.json" }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
