#!/usr/bin/env python3
"""Leadbeoordeling via de ingelogde Claude-opdrachtregel in plaats van de API.

Waarom (24-11-2026): op de nieuwe Mac is de sleutel in .env ongeldig (401) en het
API-tegoed is eerder leeggelopen door tokengebruik. De beoordelaar van
leadgen_marktplaats.py (classify) roept per verkoper `client.messages.create`
aan; dit bestand vervangt alleen die ene aanroep door `claude -p --model haiku`.
Prompt, drie-assen-toets, cache en filters blijven die van het origineel.

Gebruik: exact als leadgen_marktplaats.py, bijvoorbeeld
    python3 scripts/leadgen_classify_cli.py classify --only-email
    python3 scripts/leadgen_classify_cli.py classify --site 2dehands
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import leadgen_instagram as ig  # noqa: E402
import leadgen_marktplaats as mp  # noqa: E402


def _claude() -> str:
    pad = sorted(glob(str(Path.home() / "Library/Application Support/Claude/claude-code"
                          "/*/*/claude.app/Contents/MacOS/claude")))
    if not pad:
        sys.exit("Claude-opdrachtregel niet gevonden")
    return pad[-1]


CLAUDE = _claude()


def _judge_cli(client, row: dict, fill=None) -> dict | None:
    prompt = (fill or ig._fill)(row)
    try:
        uit = subprocess.run(
            [CLAUDE, "-p", "--model", "haiku", "--output-format", "text"],
            input=prompt, capture_output=True, text=True, timeout=180, cwd="/tmp")
        if uit.returncode != 0:
            raise RuntimeError(uit.stderr.strip()[:200] or f"exit {uit.returncode}")
        return json.loads(re.search(r"\{.*\}", uit.stdout, re.S).group(0))
    except Exception as e:  # noqa: BLE001
        print(f"  ! {row.get('handle') or row.get('name')}: {e}")
        return None


ig._judge = _judge_cli

if __name__ == "__main__":
    sys.argv[0] = "leadgen_marktplaats.py"
    if "--workers" not in sys.argv:
        sys.argv += ["--workers", "4"]
    mp.main()
