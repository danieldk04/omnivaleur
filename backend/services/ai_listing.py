"""
Claude Vision — analyse clothing photos and generate platform-specific listings.
Returns structured JSON with brand, type, size, colour, condition and copy.
"""
import json
import logging
import anthropic
from backend.config import settings

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """
Je bent een expert tweedehands kledingverkoper in Nederland.
Analyseer de foto('s) van het kledingstuk en geef een JSON response.

Geef ALLEEN valid JSON terug, geen markdown code blocks, geen uitleg.

Vereiste velden:
{
  "brand": "merknaam van het label, of null",
  "item_type": "bijv. blazer, polo, jas, broek",
  "size": "maat van het label, bijv. M, L, 50, 32/34",
  "color": "primaire kleur in het Nederlands",
  "condition": "new of good of fair of poor (op basis van zichtbare slijtage)",
  "material": "materiaal indien zichtbaar op label, anders null",
  "title_vinted": "max 60 tekens, informeel NL, hashtag-vriendelijk",
  "description_vinted": "max 2000 tekens, informeel NL, vermeld maat/merk/staat",
  "title_marktplaats": "max 60 tekens, zakelijk NL",
  "description_marktplaats": "max 2000 tekens, zakelijk NL, alle details",
  "title_ebay": "max 80 tekens, Engels, SEO-vriendelijk met merk + type + maat",
  "description_ebay": "max 4000 tekens, Engels, alle details voor internationale koper"
}
"""


async def generate_listing_from_photos(photo_urls: list[str], platforms: list[str] = None) -> dict:
    """
    Send photos to Claude Vision and get a structured listing back.
    Returns dict with brand, size, condition, titles and descriptions per platform.
    """
    if platforms is None:
        platforms = ["vinted", "marktplaats", "ebay"]

    content = []
    for url in photo_urls[:5]:  # max 5 photos to control token cost
        content.append({
            "type": "image",
            "source": {"type": "url", "url": url},
        })
    content.append({"type": "text", "text": "Analyseer dit kledingstuk en geef de JSON response."})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if model adds them despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
