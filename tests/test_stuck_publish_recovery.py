"""Een vastgelopen publicatie mag de hele wachtrij niet blokkeren.

De extensie geeft één opdracht tegelijk uit. Blijft er één "claimed" staan omdat
het tabblad weg is, dan gebeurt er niets meer — precies het beeld van "hij doet
niks". Deze tests dekken de twee ontsnappingsroutes af: opnieuw op publiceren
drukken (backend) en het tabblad dat verdwijnt (extensie).
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.services.crosslist import STALE_CLAIM_SECONDS, _republish_job_update

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 11, 20, 0, tzinfo=timezone.utc)


def _iso(seconds_ago: int) -> str:
    return (NOW - timedelta(seconds=seconds_ago)).isoformat()


def test_fresh_claim_is_left_alone():
    """De extensie is écht bezig — niet opnieuw in de wachtrij zetten."""
    upd = _republish_job_update({"status": "claimed", "claimed_at": _iso(5)}, {"x": 1}, now=NOW)
    assert upd == {"payload": {"x": 1}}


def test_stale_claim_is_requeued():
    upd = _republish_job_update(
        {"status": "claimed", "claimed_at": _iso(STALE_CLAIM_SECONDS + 30)}, {"x": 1}, now=NOW
    )
    assert upd["status"] == "pending" and upd["claimed_at"] is None


def test_claim_without_timestamp_is_requeued():
    upd = _republish_job_update({"status": "claimed", "claimed_at": None}, {"x": 1}, now=NOW)
    assert upd["status"] == "pending"


def test_pending_job_is_only_updated():
    upd = _republish_job_update({"status": "pending", "claimed_at": None}, {"x": 1}, now=NOW)
    assert upd == {"payload": {"x": 1}}


def _background_js() -> str:
    return (ROOT / "extension/background.js").read_text(encoding="utf-8")


def test_closing_the_tab_reports_the_job():
    """tabs.onRemoved moet de opdracht afmelden, niet stil weggooien."""
    src = _background_js()
    handler = src.split("chrome.tabs.onRemoved.addListener((tabId) => {")[1].split("\n});")[0]
    assert "finaliseJob" in handler
    assert "awaitingManualFinish" in handler  # handmatige afronding niet kapotmaken


def test_orphan_job_tabs_are_reconciled_before_polling():
    src = _background_js()
    assert "async function reconcileOrphanJobTabs()" in src
    poll = src.split("async function pollJobs() {")[1].split("\n}")[0]
    assert "reconcileOrphanJobTabs()" in poll


@pytest.mark.parametrize("needle", [
    # De oranje "publishing…" stip moet klikbaar zijn om alsnog listed te zetten.
    "markPlatformListed('${itemId}','${p}','${PLATFORM_LABELS[p]}',${isBusy})",
])
def test_busy_platform_dot_can_be_marked_listed(needle):
    src = (ROOT / "frontend/app.html").read_text(encoding="utf-8")
    assert needle in src
    block = src.split("const canMark =")[1][:400]
    assert not re.search(r"canMark[^\n]*'pending'", block), "pending mag niet meer uitgesloten zijn"
