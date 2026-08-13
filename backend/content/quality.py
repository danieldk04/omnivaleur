"""
De publicatienorm voor een blogartikel, in code.

Dit bestand is de "lock" op het format: alles wat een artikel in juli 2026 goed
maakte — eigen hero, relevante screenshots, inhoudsopgave-waardige koppen, een
citeerbaar antwoordblok, genoeg interne links, echte bronnen, geen
markdown-restanten — staat hier als controleerbare eis. De pijplijn draait deze
check bij elke publicatie en bij elke herschrijving, en het backfill-script
gebruikt 'm om bestaande pagina's te toetsen.

Bewust WAARSCHUWINGEN, geen harde blokkade: een artikel dat op één punt zakt is
nog altijd beter dan geen artikel, en een blokkade zou de dagelijkse cron stil
laten vallen zonder dat iemand het merkt. De waarschuwingen gaan mee in de
publicatie-mail en `scripts/check_blog_quality.py` zet ze op een rij voor de
hele site — dáár zie je of het niveau zakt.

Wil je de lat hoger leggen (en dat is de bedoeling: elk kwartaal een eis erbij),
verhoog dan een drempel hieronder of voeg een check toe. Alles wat je hier
toevoegt geldt automatisch voor nieuwe én bestaande artikelen.
"""
from __future__ import annotations

import re

# Ondergrenzen. Deze getallen zijn geen theorie: ze komen uit wat de artikelen
# die het goed doen feitelijk halen (gemeten juli 2026, 24 artikelen).
MIN_WORDS = 1200
MIN_H2 = 5                  # genoeg secties voor een zinnige inhoudsopgave
MIN_INTERNAL_LINKS = 4
MIN_AUTHORITY_LINKS = 2
MIN_FAQ_ITEMS = 4
MIN_TAKEAWAYS = 3
MIN_IMAGES = 2
MAX_TITLE = 60
MAX_META = 160
QUICK_ANSWER_RANGE = (35, 75)   # woorden — kort genoeg om letterlijk geciteerd te worden

# Merknaam mag nooit als werkwoord. Zelfde patroon als in generator.py, hier als
# controle achteraf zodat een handmatige bewerking het ook niet stiekem invoert.
# Alleen woorden die er een handeling van maken — "the Omnivaleur item list" is
# een zelfstandig naamwoord en moet geen alarm geven.
_BRAND_AS_VERB = re.compile(
    r"\bOmnivaleur\b(?=\s+(?:from|to|your|their|our|it|between|across|everything|anything)\b)",
    re.IGNORECASE,
)
_MD_LEFTOVER = re.compile(r"\*\*\S|\S\*\*")
_INTERNAL_LINK = re.compile(r'href="(?:https?://(?:www\.)?omnivaleur\.com)?(/[^"#][^"]*)"')
_EXTERNAL_LINK = re.compile(r'href="https?://(?!(?:www\.)?omnivaleur\.com)([^/"]+)')


# Een compleet artikel eindigt op een afgesloten blok. Loopt het af midden in een
# zin, dan is het model gestopt voordat hij klaar was.
_SLUIT_NETJES = re.compile(
    r"(</p>|</ul>|</ol>|</h[1-6]>|</table>|</div>|</blockquote>|</figure>)\s*$", re.I)
MIN_FAQ_ANTWOORD = 40      # tekens; "It" en "Het" stonden er echt
MIN_TAKEAWAY_TEKENS = 25


def _text(html: str) -> str:
    stripped = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", html or "", flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", stripped)


def check_article(page: dict) -> list[str]:
    """
    Toetst één artikel aan de norm. `page` is de gegenereerde/opgeslagen rij:
    title, meta_description, h1, quick_answer, takeaways, body_html, faq,
    featured_image_url.

    Geeft een lijst met wat er niet klopt — leeg betekent: voldoet aan de norm.
    """
    problems: list[str] = []
    body = page.get("body_html") or ""
    words = len(_text(body).split())

    if words < MIN_WORDS:
        problems.append(f"te kort: {words} woorden (norm {MIN_WORDS}+)")

    h2_count = len(re.findall(r"<h2", body, re.I))
    if h2_count < MIN_H2:
        problems.append(f"{h2_count} H2-secties (norm {MIN_H2}+, anders geen bruikbare inhoudsopgave)")

    internal = len(set(_INTERNAL_LINK.findall(body)))
    if internal < MIN_INTERNAL_LINKS:
        problems.append(f"{internal} interne links (norm {MIN_INTERNAL_LINKS}+)")

    external = len({host.lower() for host in _EXTERNAL_LINK.findall(body)})
    if external < MIN_AUTHORITY_LINKS:
        problems.append(f"{external} externe bronnen (norm {MIN_AUTHORITY_LINKS}+)")

    images = len(re.findall(r"<img\b", body, re.I))
    if images < MIN_IMAGES:
        problems.append(f"{images} afbeeldingen in de tekst (norm {MIN_IMAGES}+)")

    if not page.get("featured_image_url"):
        problems.append("geen hero-/deelafbeelding — deelbare links tonen een leeg blok")

    quick = len((page.get("quick_answer") or "").split())
    low, high = QUICK_ANSWER_RANGE
    if not low <= quick <= high:
        problems.append(f"quick answer is {quick} woorden (norm {low}-{high}, anders slecht citeerbaar)")

    if len(page.get("takeaways") or []) < MIN_TAKEAWAYS:
        problems.append(f"{len(page.get('takeaways') or [])} key takeaways (norm {MIN_TAKEAWAYS}+)")

    if len(page.get("faq") or []) < MIN_FAQ_ITEMS:
        problems.append(f"{len(page.get('faq') or [])} FAQ-vragen (norm {MIN_FAQ_ITEMS}+, voedt het FAQ-schema)")

    title = page.get("title") or ""
    if not title or len(title) > MAX_TITLE:
        problems.append(f"meta title ontbreekt of is {len(title)} tekens (max {MAX_TITLE})")

    meta = page.get("meta_description") or ""
    if not meta or len(meta) > MAX_META:
        problems.append(f"meta description ontbreekt of is {len(meta)} tekens (max {MAX_META})")

    if not page.get("h1"):
        problems.append("H1 ontbreekt")

    # Tekstuele fouten die eerder live hebben gestaan. Alleen op de ZICHTBARE
    # tekst: alt-teksten van onze eigen screenshots beginnen met "Omnivaleur …"
    # en dat is correct Engels, geen werkwoordgebruik.
    joined = " ".join(
        [title, meta, page.get("h1") or "", page.get("quick_answer") or "", _text(body)]
        + list(page.get("takeaways") or [])
    )
    # Afgekapte tekst. Dit is geen smaakkwestie maar kapotte content: eind 2026
    # stonden er vijf artikelen live die middenin een zin ophielden omdat het
    # model tegen zijn tokenlimiet aanliep. Deze drie signalen vingen ze alle vijf.
    if body.strip() and not _SLUIT_NETJES.search(body.strip()):
        problems.append("AFGEKAPT: de tekst eindigt niet op een afgesloten alinea of kop")
    if body.count("<p>") != body.count("</p>"):
        problems.append(
            f"AFGEKAPT: {body.count('<p>')} keer <p> tegen {body.count('</p>')} keer </p>")
    for f in page.get("faq") or []:
        if len((f.get("answer") or "").strip()) < MIN_FAQ_ANTWOORD:
            problems.append(
                f"AFGEKAPT: FAQ-antwoord op '{(f.get('question') or '?')[:40]}' is "
                f"maar {len((f.get('answer') or '').strip())} tekens")
    for t in page.get("takeaways") or []:
        if len(str(t).strip()) < MIN_TAKEAWAY_TEKENS:
            problems.append(f"AFGEKAPT: key takeaway '{str(t)[:40]}' is te kort")

    if _MD_LEFTOVER.search(joined):
        problems.append("markdown-restanten (**vet**) staan als letterlijke tekens in de tekst")
    if _BRAND_AS_VERB.search(joined):
        problems.append("merknaam 'Omnivaleur' wordt als werkwoord gebruikt")

    return problems
