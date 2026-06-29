@echo off
setlocal
cd /d "%~dp0"

set "CONDA_PREFIX="
set "CONDA_DEFAULT_ENV="
set "CONDA_PROMPT_MODIFIER="
set "CONDA_PYTHON_EXE="
set "CONDA_SHLVL="
set "SAM2_BUILD_CUDA=0"

where uv >nul 2>&1 || (echo uv is required & exit /b 1)
where node >nul 2>&1 || (echo Node.js is required & exit /b 1)
where npm >nul 2>&1 || (echo npm is required & exit /b 1)

echo [1/4] Installing managed Python 3.13...
uv python install 3.13 || exit /b 1

echo [2/4] Syncing locked CUDA + SAM2 environment...
uv sync --locked --extra cuda --extra sam2 || exit /b 1

echo [3/4] Building frontend...
pushd frontend
call npm ci || (popd & exit /b 1)
call npm run build || (popd & exit /b 1)
popd

echo [4/4] Verifying GPU and SAM2...
uv run --locked --no-sync python -m web.env_check --backend cuda --download-checkpoint --smoke
exit /b %errorlevel%
