#!/usr/bin/env bash
# Start the API (:8000) and the web app (:3000). Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT
.venv/bin/uvicorn marketentry.api:app --host 127.0.0.1 --port 8000 --reload &
(cd web && pnpm dev --port 3000) &
wait
