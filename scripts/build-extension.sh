#!/usr/bin/env bash
#
# build-extension.sh — package the browser extension for the Chrome Web Store.
#
# Always zips the CURRENT extension/ folder and names the archive after the
# manifest version, so you never accidentally upload a stale build (the cause
# of "version must be higher than the published package" rejections).
#
# Usage:
#   ./scripts/build-extension.sh            # zips ./extension
#   git pull origin main && ./scripts/build-extension.sh   # ensure it's latest
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT_DIR="$ROOT/extension"
DIST_DIR="$ROOT/dist"

version="$(python3 -c "import json;print(json.load(open('$EXT_DIR/manifest.json'))['version'])")"
out="$DIST_DIR/omnivaleur-extension-$version.zip"

mkdir -p "$DIST_DIR"
rm -f "$out"

# Zip only the real extension files — exclude dev/tooling cruft that must never
# ship in the store package.
( cd "$EXT_DIR" && zip -rq "$out" . \
    -x "*.DS_Store" \
    -x ".claude-flow/*" -x "*/.claude-flow/*" \
    -x "*.map" \
    -x "__MACOSX/*" )

echo "Built $out"
echo "manifest version: $version"
echo
echo "Upload this file at: Chrome Web Store Developer Dashboard → your item → Package → Upload new package"
