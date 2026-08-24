"""Dry-run verificatie van de support-mailagent classificatie/grounding-logica,
zonder de echte Zoho-mailbox of Supabase aan te raken.

Fixtures zijn versimpelde, gesynthetiseerde versies van de drie threads uit de
sessie van 24-08-2026 (Twan de Haas/kenmerken, Robert/relist, Egbert/Admarkt) —
geen echte klantdata, alleen de vorm van de vraag.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import support_mail_agent as sma  # noqa: E402


def test_topic_classification_kenmerken():
    body = "Hoi, worden de kenmerken/attributen van een advertentie ook overgenomen?"
    assert sma._classificeer_topic(body) == "kenmerken-support"


def test_topic_classification_relist():
    body = "Mijn advertentie is verlopen, wordt die automatisch opnieuw geplaatst (relist)?"
    assert sma._classificeer_topic(body) == "relist-vs-crosslist"


def test_topic_classification_admarkt():
    body = "Ik heb een zakelijk Admarkt-account, wordt dat ook gescand?"
    assert sma._classificeer_topic(body) == "admarkt-scan-batching"


def test_topic_classification_billing_never_promises():
    body = "Kun je mijn betaling deze maand uitstellen?"
    assert sma._classificeer_topic(body) == "billing-verzoek"


def test_topic_classification_fallback():
    body = "Ik wil graag een keer langskomen op kantoor."
    assert sma._classificeer_topic(body) == "wil-langskomen"


def test_grep_grondslag_finds_real_file_for_kenmerken():
    grondslag = sma._grep_grondslag("vraag over kenmerken van een advertentie")
    assert "extension/content/marktplaats.js" in grondslag
    assert "geen relevante broncode" not in grondslag


def test_grep_grondslag_finds_real_file_for_admarkt():
    grondslag = sma._grep_grondslag("hoe werkt de admarkt scan precies")
    assert "backend/api/imports.py" in grondslag or "extension/background.js" in grondslag


def test_grep_grondslag_no_match_is_explicit_not_fabricated():
    grondslag = sma._grep_grondslag("kun je een keer langskomen bij mij in de winkel")
    assert grondslag.startswith("(geen relevante broncode")


def test_thread_dataclass_roundtrip():
    draad = sma.Thread(
        message_id="abc123@zoho.eu",
        van_adres="twan@example.com",
        van_naam="Twan de Haas",
        onderwerp="Vraag over kenmerken",
        body="Worden kenmerken overgenomen bij het plaatsen?",
        references="<abc123@zoho.eu>",
    )
    assert draad.van_naam.split()[0] == "Twan"


def test_draft_without_llm_key_is_neutral_placeholder(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    draad = sma.Thread("id1", "robert@example.com", "Robert", "Vraag",
                        "Doet dit ook echte crosslisting of alleen relist?", "<id1>")
    tekst, topic = sma._draft_met_llm(draad, "geen grondslag nodig voor deze test")
    assert "Robert" in tekst
    assert "Groetjes" in tekst
    assert topic == "relist-vs-crosslist"
    # geen technische bewering zonder LLM/grondslag
    assert "werkt wel" not in tekst.lower()


# ---------------------------------------------------------------- Module B: auto-fix classifier
def test_classify_fix_simple_isolated_text_change():
    fix = sma.classificeer_fix("prijs-vraag", "typo in prijstekst", "frontend/pricing.html", 2)
    assert fix.is_simple


def test_classify_fix_rejects_billing_code():
    fix = sma.classificeer_fix("billing-verzoek", "trial-lengte aanpassen",
                                "backend/services/billing.py", 1)
    assert not fix.is_simple
    assert "auth" in fix.reden or "betaal" in fix.reden or "datamodel" in fix.reden


def test_classify_fix_rejects_large_change():
    fix = sma.classificeer_fix("login-bug", "meerdere functies aangepast",
                                "backend/api/imports.py", 40)
    assert not fix.is_simple


def test_classify_fix_rejects_missing_file():
    fix = sma.classificeer_fix("overig", "onduidelijk waar", None, 1)
    assert not fix.is_simple


def test_auto_fix_not_actually_executed_yet():
    """Documenteert bewust de huidige staat: Module B classificeert, maar voert
    nog geen patch uit (zie voer_simpele_fix_uit docstring)."""
    fix = sma.classificeer_fix("prijs-vraag", "typo", "frontend/pricing.html", 1)
    assert sma.voer_simpele_fix_uit(fix) is None
