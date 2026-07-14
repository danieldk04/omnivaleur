# Checking Railway backend env vars

`check-railway-env.sh` verifies the backend has the environment variables it
needs (currently the eBay keys for category suggestions), reporting PASS/FAIL
per variable **without ever printing the secret values**.

## Run it locally

```bash
railway link                       # pick the project + environment once
./scripts/check-railway-env.sh
```

## Run it non-interactively (CI / automation)

```bash
RAILWAY_TOKEN=<project-token> ./scripts/check-railway-env.sh
```

Create the token in **Railway → your project → Settings → Tokens → Project
Token**.

## Letting Claude Code run it autonomously

For a Claude Code Cloud session to run this check itself, two things are needed
on the **environment** (set at claude.com/code when creating/editing it):

1. **Network policy** that allows outbound egress to `railway.com` /
   `backboard.railway.app`. The default restricted policy blocks all outbound
   traffic, so the Railway API is unreachable and the script exits with a clear
   network error.
2. **`RAILWAY_TOKEN`** added as an environment variable.

With both in place, the agent can run `./scripts/check-railway-env.sh` and read
the result directly.

## Variables checked

| Variable | Required | Used for |
| --- | --- | --- |
| `EBAY_APP_ID` | yes | eBay API auth (category suggestions, publishing) |
| `EBAY_CERT_ID` | yes | eBay API auth |
| `ANTHROPIC_API_KEY` | no | Translating eBay category names to English |
| `EBAY_MARKETPLACE_ID` | no | Target eBay marketplace (defaults apply) |
| `EBAY_DEFAULT_CATEGORY_ID` | no | Fallback category when none is set on an item |

Edit `REQUIRED_VARS` / `OPTIONAL_VARS` at the top of the script to extend the
check as the backend grows.
