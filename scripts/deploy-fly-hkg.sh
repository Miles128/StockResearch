#!/usr/bin/env bash
# 首次 Fly 香港部署：需先 flyctl auth login
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP="${FLY_APP:-stockresearch-api}"

flyctl auth whoami

if ! flyctl apps list 2>/dev/null | grep -q "^${APP}[[:space:]]"; then
  flyctl apps create "$APP"
fi

if ! flyctl volumes list -a "$APP" 2>/dev/null | grep -q stockresearch_data; then
  flyctl volumes create stockresearch_data --region hkg --size 1 --app "$APP"
fi

if ! flyctl secrets list -a "$APP" 2>/dev/null | grep -q SECRET_KEY; then
  flyctl secrets set SECRET_KEY="$(openssl rand -hex 32)" --app "$APP"
fi

flyctl deploy --remote-only
echo "API: https://${APP}.fly.dev"
curl -fsS "https://${APP}.fly.dev/health" && echo
