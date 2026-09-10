"""Een opdracht die er niet meer is hoort "bestaat niet" te zijn, geen storing.

Gemeten in het foutenlogboek op 10-09-2026: POST /api/jobs/{id}/complete viel
331 keer om, allemaal voor dezelfde opdracht
(9ac23805-4549-4d09-811d-1dc922a80015), voor het laatst die ochtend om 06:32
UTC. Die opdracht staat niet in de tabel: hij is meeverwijderd toen het artikel
in het dashboard werd weggegooid (backend/api/items.py wist de opdrachten van
een artikel mee).

De keten:

1. `.single()` geeft bij nul rijen geen leeg antwoord terug maar gooit een
   APIError (PGRST116, "Cannot coerce the result to a single JSON object").
   Nagemeten tegen de echte database, en de foutmelding uit productie wijst
   precies deze regel aan.
2. Daardoor werd `if not job: raise HTTPException(404)` nooit bereikt: dode
   code. De extensie kreeg een kale 500.
3. En een 500 is voor de extensie iets heel anders dan een 404. Zie
   `_postFinalise` in extension/background.js: een 404 geldt als afgehandeld,
   al het andere als een hik. Vier pogingen, dan de bewaarrij
   (`pendingFinalisations`), en `flushFinaliseQueue()` biedt die bij ELKE poll
   opnieuw aan. Op een opdracht die nooit meer terugkomt is dat oneindig.

Deze proef draait de echte eindpunten met een database die zich net zo gedraagt
als de echte: `.single()` gooit, `.limit(1)` geeft een lege lijst.
"""
import asyncio
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from postgrest.exceptions import APIError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as jobs_api  # noqa: E402

# Een vast commitnummer, geen HEAD: zodra deze reparatie gecommit is vergelijkt
# HEAD de nieuwe code met zichzelf en bewijst de voor-en-na-proef niets meer.
VOOR_DE_REPARATIE = "f64b30a1"
JOB_ID = "9ac23805-4549-4d09-811d-1dc922a80015"
USER_ID = "96e30080-ab81-47ac-8626-e8637f1e2a9e"


class _LegeVraag:
    """Bootst PostgREST na voor een zoekopdracht die niets vindt."""

    def __init__(self):
        self._enkel = False

    def single(self):
        self._enkel = True
        return self

    def __getattr__(self, _naam):
        def bouw(*_a, **_kw):
            return self
        return bouw

    def execute(self):
        if self._enkel:
            raise APIError({
                "code": "PGRST116",
                "details": "The result contains 0 rows",
                "hint": None,
                "message": "Cannot coerce the result to a single JSON object",
            })

        class Antwoord:
            data = []
        return Antwoord()


class _LegeDB:
    def table(self, _naam):
        return _LegeVraag()


def _ontwapen(module, monkeypatch):
    monkeypatch.setattr(module, "get_db", lambda: _LegeDB())
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *_a, **_kw: None)
    monkeypatch.setattr(module, "execute_with_retry", lambda *_a, **_kw: None)


def test_completen_van_een_verdwenen_opdracht_is_404(monkeypatch):
    """Het geval uit het logboek zelf."""
    _ontwapen(jobs_api, monkeypatch)

    with pytest.raises(HTTPException) as val:
        asyncio.run(jobs_api.complete_job(JOB_ID, {"platform_listing_id": "m123"}, USER_ID))

    assert val.value.status_code == 404


def test_de_vorige_versie_gaf_hier_een_storing(monkeypatch):
    """Voor-en-na. Zonder dit weten we alleen dat de nieuwe code werkt.

    De oude complete_job wordt letterlijk uit de geschiedenis gehaald en onder
    exact dezelfde omstandigheden gedraaid. Hij hoort NIET met een nette 404 te
    komen maar met de APIError die de extensie tot in het oneindige liet
    herhalen.
    """
    bron = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert ".single().execute()" in bron, "verkeerd commitnummer gepind"

    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)

    _ontwapen(oud, monkeypatch)

    with pytest.raises(APIError) as val:
        asyncio.run(oud.complete_job(JOB_ID, {"platform_listing_id": "m123"}, USER_ID))

    assert val.value.code == "PGRST116"


def test_de_andere_opdracht_eindpunten_ook(monkeypatch):
    """Dezelfde dode 404-controle stond op /cancel en /status/{id}."""
    _ontwapen(jobs_api, monkeypatch)

    for aanroep in (lambda: jobs_api.cancel_job(JOB_ID, USER_ID),
                    lambda: jobs_api.get_job_status(JOB_ID, USER_ID)):
        with pytest.raises(HTTPException) as val:
            aanroep()
        assert val.value.status_code == 404


def test_een_foutmelding_over_een_verdwenen_opdracht_loopt_door(monkeypatch):
    """/error mag hier niet omvallen.

    Hij hoeft geen 404 te geven: alles wat niet-fout is geldt voor de extensie
    als afgehandeld, dus de bewaarrij loopt leeg. Wat NIET mag is de PGRST116
    die de hele lus voedde.
    """
    _ontwapen(jobs_api, monkeypatch)
    monkeypatch.setattr(jobs_api, "_stop_wachtrij", lambda *_a, **_kw: 0)

    try:
        jobs_api.fail_job(JOB_ID, {"error": "tab closed"}, USER_ID)
    except APIError as e:  # pragma: no cover - dit is precies de fout van 10-09
        pytest.fail(f"/error viel om op een verdwenen opdracht: {e}")
    except HTTPException as e:
        assert e.status_code == 404
