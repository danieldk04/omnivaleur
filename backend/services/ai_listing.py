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
You are an expert second-hand clothing reseller.
Analyse the photo(s) of the clothing item and return a JSON response.

Return ONLY valid JSON, no markdown code blocks, no explanation.

Required fields:
{
  "brand": "brand name from the label, or null",
  "item_type": "e.g. blazer, polo, jacket, trousers",
  "size": "size from the label, e.g. M, L, 50, 32/34",
  "color": "primary colour in English",
  "condition": "new or good or fair or poor (based on visible wear)",
  "material": "material if visible on label, otherwise null",
  "title_vinted": "max 60 chars, casual English, hashtag-friendly",
  "description_vinted": "max 2000 chars, casual English, mention size/brand/condition",
  "title_marktplaats": "max 60 chars, professional Dutch",
  "description_marktplaats": "max 2000 chars, professional Dutch, all details",
  "title_ebay": "max 80 chars, English, SEO-friendly with brand + type + size",
  "description_ebay": "max 4000 chars, English, all details for international buyer"
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
    content.append({"type": "text", "text": "Analyse this clothing item and return the JSON response."})

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
