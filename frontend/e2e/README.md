# E2E tests (Playwright)

Browser e2e tests driving the built Svelte app against a live, **isolated** Flask backend.
See `USER_STORIES.md` for the full story library these tests map to.

## Run

```bash
cd frontend
npm install
npx playwright install chromium   # one-time browser download
npm run e2e                       # or: npm run e2e:ui
```

`global-setup.ts` builds the SPA, then spawns the backend with:

- a **temp HOME** (`USERPROFILE`/`HOME`) so `~/.plotter_studio`, `~/.plotter_settings.json`,
  the resume-job and paths-cache files never touch your real profile;
- `PLOTTER_FAKE_SERIAL=1` — an in-memory Grbl stub so plot/manual flows run with no hardware;
- `SAM2_AUTO_SETUP=0` — never downloads the segmentation model in tests.

The backend listens on port **7440** (override `E2E_PORT`). Set `E2E_SKIP_BUILD=1` to reuse the
existing `web/static/app` build, or `E2E_BACKEND_CMD` to change how the server is launched
(default `uv run python -m web.server`).

## Performance

`perf-pfm.spec.ts` appends `{story, pfm, duration_ms, shapes}` rows to `perf/results.jsonl`.
Budgets live in `perf/budgets.json` — over-budget logs a warning, it never fails the run.

## Layout

- `*.spec.ts` — tests (one file per epic as they're filled in; the three shipped specs are
  `smoke`, `plot-estimate`, `perf-pfm`).
- `fixtures.ts` — app helpers (`gotoApp`, `importImage`, `runPathFinding`, `gotoStep`) + the
  `recordPerf` fixture.
- `assets/` — fixture image + svg.
