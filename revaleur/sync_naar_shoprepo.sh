#!/bin/bash
# Spiegelt revaleur/ naar de private repo danieldk04/revaleur-shop (de Cloudflare Pages-bouw leest die repo, omdat
# omnivaleur al aan een ander Cloudflare-account hangt). Draai na elke wijziging in revaleur/ die live moet.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"
git clone -q https://github.com/danieldk04/revaleur-shop.git "$T"
rm -rf "$T/revaleur"; mkdir "$T/revaleur"
(cd "$ROOT" && git archive HEAD revaleur) | tar -x -C "$T"
cd "$T"; git add -A
if git diff --cached --quiet; then echo "niets te syncen"; else git commit -qm "Mirror van omnivaleur/revaleur $(git -C "$ROOT" rev-parse --short HEAD)" && git push -q origin main && echo "gesynct"; fi
rm -rf "$T"
