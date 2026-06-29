#!/bin/sh
set -eu
cd "$(dirname "$0")"

unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_PROMPT_MODIFIER CONDA_PYTHON_EXE CONDA_SHLVL
export SAM2_BUILD_CUDA=0

command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
command -v node >/dev/null || { echo "Node.js is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm is required" >&2; exit 1; }

echo "[1/4] Installing managed Python 3.13..."
uv python install 3.13

echo "[2/4] Syncing locked MPS + SAM2 environment..."
# Two-phase: install build deps (setuptools/torch) before building sam-2,
# which is built without isolation against this environment.
uv sync --locked --extra mps --extra sam2 --no-install-package sam-2
uv sync --locked --extra mps --extra sam2

echo "[3/4] Building frontend..."
(cd frontend && npm ci && npm run build)

echo "[4/4] Verifying GPU and SAM2..."
uv run --locked --no-sync python -m web.env_check --backend mps --download-checkpoint --smoke
