"""Contentpagina's: korte cache en kopie per aanroep (Ahrefs-crawl gaf 502's, 26-11-2026)."""
import inspect

from backend.api import content


def test_cache_laadt_een_keer_en_geeft_kopieen():
    content.wis_pagina_cache()
    n = {"x": 0}

    def laad():
        n["x"] += 1
        return {"body": "a"}

    a = content._gecached(("t", 1), laad)
    a["body"] = "veranderd"
    b = content._gecached(("t", 1), laad)
    assert n["x"] == 1 and b == {"body": "a"}


def test_publieke_paginaroutes_blokkeren_de_lus_niet():
    for naam in ["niche_page_en", "combo_page_en", "comparison_page_en", "niche_page_lang", "blog_index_default"]:
        assert not inspect.iscoroutinefunction(getattr(content, naam)), naam
