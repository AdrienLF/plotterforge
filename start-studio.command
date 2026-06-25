#!/bin/sh
# Plotter Studio — one-click launch (GPU / Metal-MPS).
# Double-click in Finder, or run: ./start-studio.command
#
# Stops any already-running studio, ensures the GPU dependency (torch) is
# installed, rebuilds the UI, then serves everything from one Flask process on
# port 7438 (reachable at localhost and over Tailscale).

cd "$(dirname "$0")" || exit 1
PORT=7438

echo "▸ Stopping any studio already on port $PORT…"
PIDS=$(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null)
if [ -n "$PIDS" ]; then
  kill $PIDS 2>/dev/null
  sleep 1
  # force-kill anything that ignored the polite request
  PIDS=$(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null)
  [ -n "$PIDS" ] && kill -9 $PIDS 2>/dev/null && sleep 1
fi

echo "▸ Syncing Python deps with GPU support…"
uv sync --extra gpu || { echo "uv sync failed"; exit 1; }

echo "▸ Building the UI…"
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install) || { echo "npm install failed"; exit 1; }
fi
(cd frontend && npm run build) || { echo "UI build failed"; exit 1; }

echo ""
echo "▸ Starting Plotter Studio (GPU) …"
echo "    Local:    http://localhost:$PORT"
echo "    Tailnet:  http://<this-mac-tailscale-ip>:$PORT"
echo "  (Press Ctrl+C in this window to stop.)"
echo ""

exec uv run --extra gpu python -c "import web.server as s; s.app.run(host='0.0.0.0', port=$PORT, threaded=True)"
