#!/usr/bin/env bash
#
# check-railway-env.sh — verify required backend env vars are set in Railway.
#
# Prints PASS/FAIL per variable WITHOUT ever revealing the secret values, so
# it is safe to run in logs and CI. Exits non-zero if any required var is
# missing.
#
# Requirements:
#   - Railway CLI (auto-installed via npm if missing)
#   - RAILWAY_TOKEN in the environment (a Railway *Project Token*), OR an
#     interactive `railway login` session.
#   - Outbound network access to railway.com / backboard.railway.app. In a
#     Claude Code Cloud session this needs a network policy that allows egress
#     to Railway — the default restricted policy blocks it.
#
# Usage:
#   RAILWAY_TOKEN=xxxx: ./scripts/check-railway-env.sh
#   ./scripts/check-railway-env.sh            # if already `railway link`-ed
#
set -euo pipefail

# Vars the backend needs for the eBay category-suggest feature to work live.
REQUIRED_VARS=(EBAY_APP_ID EBAY_CERT_ID)
OPTIONAL_VARS=(ANTHROPIC_API_KEY EBAY_MARKETPLACE_ID EBAY_DEFAULT_CATEGORY_ID)

command -v railway >/dev/null 2>&1 || {
  echo "Railway CLI not found — installing (@railway/cli)…"
  npm install -g @railway/cli >/dev/null 2>&1
}

# Fail fast with a clear message if Railway can't be reached (blocked network
# policy or missing auth), instead of a confusing CLI stack trace.
if ! railway whoami >/dev/null 2>&1 && [ -z "${RAILWAY_TOKEN:-}" ]; then
  echo "✗ Not authenticated to Railway."
  echo "  Set RAILWAY_TOKEN (Railway → project → Settings → Tokens → Project Token)"
  echo "  or run 'railway link' interactively, then re-run this script."
  exit 2
fi

# Pull the variables once as key=value pairs; keep only the keys we care about.
if ! vars_output="$(railway variables --kv 2>/tmp/railway-err)"; then
  echo "✗ Could not read Railway variables:"
  sed 's/^/    /' /tmp/railway-err
  echo "  (In a Claude Code Cloud session, check the environment's network"
  echo "   policy allows egress to railway.com / backboard.railway.app.)"
  exit 3
fi

# Return 0 if KEY is present and non-empty, without printing its value.
has_var() {
  awk -F= -v k="$1" '$1==k && length($2)>0 {found=1} END {exit found?0:1}' <<<"$vars_output"
}

status=0
echo "Railway environment check"
echo "========================="
echo "Required:"
for v in "${REQUIRED_VARS[@]}"; do
  if has_var "$v"; then echo "  ✓ $v is set"; else echo "  ✗ $v is MISSING"; status=1; fi
done
echo "Optional:"
for v in "${OPTIONAL_VARS[@]}"; do
  if has_var "$v"; then echo "  ✓ $v is set"; else echo "  – $v not set"; fi
done

echo
if [ "$status" -eq 0 ]; then
  echo "All required variables present — eBay category suggestions should work live."
else
  echo "Missing required variable(s) — the eBay category dropdown will return"
  echo "\"eBay is not configured yet\" until they are set in Railway."
fi
exit "$status"
