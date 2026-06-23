#!/bin/sh
# Run from the repo root so the `engine` package and `web` package both import cleanly.
cd "$(dirname "$0")/.."
exec uv run python -m web.server
