"""
Structured-data sanity-check vóór publicatie. Google's Rich Results Test heeft geen
publiek batch/automation-API (de oude Structured Data Testing Tool API is uitgefaseerd) —
dus dit is een lokale validatie van de verplichte velden per schema.org-type die Google's
Rich Results eist, in plaats van Claude's JSON-LD blind te vertrouwen. Geen harde blokkade:
geeft een lijst waarschuwingen terug die worden meegestuurd in de publicatie-melding.
"""


def validate_article_json_ld(article: dict) -> list[str]:
    warnings = []
    required = ["headline", "image", "author", "publisher", "datePublished"]
    for field in required:
        if not article.get(field):
            warnings.append(f"Article JSON-LD mist verplicht veld: {field}")
    if article.get("headline") and len(article["headline"]) > 110:
        warnings.append("Article headline > 110 tekens — Google kan 'm afkappen in Rich Results")
    return warnings


def validate_faq_json_ld(faq_items: list[dict]) -> list[str]:
    warnings = []
    if not faq_items:
        warnings.append("Geen FAQ-items — FAQPage-schema wordt niet gegenereerd")
        return warnings
    for i, item in enumerate(faq_items):
        if not item.get("question") or not item.get("answer"):
            warnings.append(f"FAQ-item {i + 1} mist vraag of antwoord")
    return warnings


def validate_page(generated: dict) -> list[str]:
    """Voert alle checks uit op een net gegenereerde pagina (voor het opslaan)."""
    warnings = []
    if not generated.get("title") or len(generated["title"]) > 60:
        warnings.append("Meta title ontbreekt of is langer dan 60 tekens")
    if not generated.get("meta_description") or len(generated["meta_description"]) > 160:
        warnings.append("Meta description ontbreekt of is langer dan 160 tekens")
    if not generated.get("h1"):
        warnings.append("H1 ontbreekt")
    warnings.extend(validate_faq_json_ld(generated.get("faq") or []))
    return warnings
