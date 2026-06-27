import { spawn, execSync, ChildProcess } from "child_process";
import { mkdtempSync } from "fs";
import { tmpdir } from "os";
import { dirname, join, resolve } from "path";
import { fileURLToPath } from "url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const FRONTEND = resolve(HERE, "..");

let backend: ChildProcess | undefined;

async function waitForServer(url: string, timeoutMs = 60_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Backend did not come up at ${url} within ${timeoutMs}ms`);
}

export default async function globalSetup() {
  const port = process.env.PLOTTER_PORT || "7440";

  // Build the SPA so Flask serves the current code (skip with E2E_SKIP_BUILD=1).
  if (!process.env.E2E_SKIP_BUILD) {
    execSync("npm run build", { cwd: FRONTEND, stdio: "inherit" });
  }

  // Isolated HOME so the backend's ~/.plotter_studio, ~/.plotter_settings.json,
  // resume-job and paths-cache files never touch the real user profile.
  const home = mkdtempSync(join(tmpdir(), "plotter-e2e-"));
  const cmd = process.env.E2E_BACKEND_CMD || "uv run python -m web.server";

  backend = spawn(cmd, {
    cwd: REPO,
    shell: true,
    stdio: "inherit",
    env: {
      ...process.env,
      HOME: home,
      USERPROFILE: home, // Path.home() uses USERPROFILE on Windows
      PLOTTER_PORT: port,
      PLOTTER_HOST: "127.0.0.1",
      PLOTTER_FAKE_SERIAL: "1",
      SAM2_AUTO_SETUP: "0",
      PLOTTER_LOG_FILE: "0",
    },
  });

  console.log(`[e2e] backend pid=${backend.pid} home=${home} port=${port}`);
  await waitForServer(`http://127.0.0.1:${port}/`);

  // Returned function runs as global teardown.
  return async () => {
    if (backend && backend.pid) {
      if (process.platform === "win32") {
        try {
          execSync(`taskkill /pid ${backend.pid} /T /F`, { stdio: "ignore" });
        } catch {
          /* already gone */
        }
      } else {
        backend.kill("SIGTERM");
      }
    }
  };
}
