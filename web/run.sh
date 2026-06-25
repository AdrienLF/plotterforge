#!/bin/sh
# Run from the repo root so the `engine` package and `web` package both import cleanly.
# Launch with the GPU extra by default; accel.py falls back to numpy/scipy if
# Torch or a Metal/CUDA device is unavailable.
cd "$(dirname "$0")/.."
exec uv run --extra gpu python -m web.server
