# Performance profiling

A deterministic profiling suite for the engine, server pipeline, and browser.
It measures CPU, and — when a real accelerator is present — MPS or CUDA, plus
Playwright browser journeys. Reports show median/p90 trends against a named
baseline, but **performance warnings never fail CI**: only correctness errors
and profiling-infrastructure failures do.

## Commands

```bash
# Fast CPU sanity profile (quick-tagged workloads only)
uv run --frozen python tools/profile_suite.py quick

# Every registered workload across available backends
uv run --frozen python tools/profile_suite.py full

# Full run forced onto the GPU (errors if no MPS/CUDA device)
uv run --frozen python tools/profile_suite.py full --backend gpu

# Deep single-workload profile with a CPU .prof + memory phase
uv run --frozen python tools/profile_suite.py diagnose pipeline.svg_dense_circles

# Promote a matching results file to a named baseline (never done by CI)
uv run --frozen python tools/profile_suite.py baseline update \
  --from artifacts/profiling/RUN/results.json --name cpu-ci
```

Common flags: `--backend {cpu,gpu,all,auto}`, `--repeat N`, `--category C`
(repeatable), `--exclude-category C`, `--output DIR`, `--baseline FILE`,
`--playwright FILE`.

Exit codes are truthful about correctness, not speed: `0` clean, `1` when any
sample errored, `2` for argument or infrastructure failures. A run that only
emits performance warnings still exits `0`.

## What each backend reports

- **CPU** — wall-clock timing samples plus a separate diagnostic phase that
  writes a `cProfile` `.prof` (open with `python -m pstats` or snakeviz) and a
  `tracemalloc` Python peak. Timing samples never include the profiler overhead.
- **CUDA** — every timed region is synchronized on both sides; the diagnostic
  phase exports a Chrome trace via `torch.profiler`, and memory metrics come from
  `torch.cuda.*` (allocated/reserved/peak).
- **MPS** — synchronized timing and boundary allocator memory
  (`current_allocated_memory` / `driver_allocated_memory`). MPS has no kernel
  trace export: the diagnostic phase records `os_signpost` intervals, which you
  capture out-of-band with **Instruments → Metal System Trace**. It does not
  claim CUDA-style kernel traces.

A requested GPU run that silently falls back to NumPy is an **error**, not a
slow success — the suite installs process-local wrappers around the accelerated
primitives and rejects any GPU-labeled workload that never dispatched one.

## Python vs GPU memory

The `memory` phase reports the Python allocator peak (`tracemalloc`) and, on an
accelerator, the device allocator snapshot. These are independent numbers:
Python peak covers host-side objects; GPU peak covers device buffers.

## Environment segmentation

Every sample carries an environment key (OS, machine, processor, Python,
backend, device, dtype, problem size). Baseline comparison only ever compares
samples with an **identical** segment key, so CPU, MPS, and CUDA numbers — and
numbers from different hardware — are never compared against each other. A
missing baseline **file** is reported as `incomparable` and does not fail the
run; a missing segment inside an existing baseline is reported as `new`.

## Browser profiling

`full` includes the `browser` category and, unless you pass `--playwright FILE`
with pre-existing rows, runs the Playwright performance stories automatically
and ingests their JSONL. To skip the browser entirely, pass
`--exclude-category browser`.

## Artifacts and hygiene

Runtime artifacts live under `artifacts/profiling/` (git-ignored) and the
browser JSONL under `frontend/e2e/perf/results.jsonl` (git-ignored). Only
explicit named baselines under `profiling/baselines/` are committed.

## Baseline bootstrap (CI segment)

The CI workflow (`.github/workflows/profile.yml`) runs a quick CPU profile plus
the browser stories on `ubuntu-latest`, writes the Markdown table to the job
summary, and uploads `artifacts/profiling/ci/` for 30 days. It never updates a
baseline.

The first CI run has no matching `cpu-ci` segment, so it reports `incomparable`
and still uploads results. To establish the baseline **from real CI data** (never
from a local macOS/MPS measurement):

1. Open the first green `Performance profile` run and download the
   `performance-profile` artifact.
2. From that artifact, promote its `results.json`:

   ```bash
   uv run --frozen python tools/profile_suite.py baseline update \
     --from path/to/ci/results.json --name cpu-ci --output profiling/baselines
   ```

3. Commit `profiling/baselines/cpu-ci.json` on its own. Do **not** create this
   commit from local measurements — the Linux CI segment must hold Linux data.
