@echo off
setlocal
set PORT=7438

echo . Stopping any studio already on port %PORT%...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)

echo . Syncing Python deps with GPU support...
call uv sync --extra gpu
if errorlevel 1 ( echo uv sync failed & exit /b 1 )

echo . Building the UI...
if not exist frontend\node_modules (
    pushd frontend && call npm install && popd
    if errorlevel 1 ( echo npm install failed & exit /b 1 )
)
pushd frontend && call npm run build && popd
if errorlevel 1 ( echo UI build failed & exit /b 1 )

echo.
echo . Starting Plotter Studio (GPU)...
echo     Local:  http://localhost:%PORT%
echo   (Press Ctrl+C to stop.)
echo.

uv run --extra gpu python -m web.server
