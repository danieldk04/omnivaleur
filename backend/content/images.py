"""
Featured-image generatie voor content_pages, zelfde patroon als in de
Revaleur blog-automation: Gemini image-modellen eerst, gratis
Pollinations.ai (Flux) als fallback zodat een ontbrekende GOOGLE_API_KEY
nooit een publicatie blokkeert.

Prompt-stijl is bewust concreet en actie-gericht (fotograferen, inpakken,
verzendlabel printen) in plaats van vage "candid lifestyle moment"-taal —
die laatste liet het model te vrij en leverde irrelevante scenes op
(bijv. iemand die in bed lag i.p.v. een reselling-actie).
"""
import logging

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

GEMINI_MODELS = ["gemini-2.5-flash-image", "gemini-3.1-flash-image"]

# Bewust CLOSE-UP op handen + product, geen volledige personen/gezichten —
# AI image-modellen renderen volledige lichamen/gezichten onbetrouwbaar
# (vervormde anatomie, "uitgerekte" proporties). Handen + object is het
# meest betrouwbare shot-type en oogt nog steeds als echte productfotografie.
TOPIC_PROMPTS = [
    ("verzendlabel", "close-up of hands applying a printed shipping label to a cardboard box, desk covered with bubble wrap, soft daylight, shallow depth of field, photorealistic"),
    ("kleding", "close-up of hands smoothing a folded sweater flat on a wooden table, soft natural light from the side, shallow depth of field, photorealistic"),
    ("marktplaats naar vinted", "close-up of hands holding a smartphone photographing a folded jacket laid flat on a table, small ring light glow visible at the edge of frame, shallow depth of field, photorealistic"),
    ("vinted naar ebay", "close-up of hands folding a shirt into a poly mailer shipping bag on a desk, a printed shipping label beside it, shallow depth of field, photorealistic"),
    ("2dehands naar vinted", "close-up of hands holding a smartphone photographing a folded clothing item laid flat on a table, small ring light glow visible, shallow depth of field, photorealistic"),
    ("marktplaats", "close-up of hands taping shut a labeled cardboard box on a car trunk, driveway setting, daylight, shallow depth of field, photorealistic"),
    ("ebay", "close-up of hands applying a printed shipping label to a cardboard box, desk covered with bubble wrap, soft daylight, shallow depth of field, photorealistic"),
    ("vinted", "close-up of hands holding a smartphone photographing a folded jacket laid flat on a table, small ring light glow visible at the edge of frame, shallow depth of field, photorealistic"),
]
DEFAULT_PROMPT = "close-up of hands holding a smartphone photographing a folded clothing item laid flat on a table for an online listing, small ring light glow, shallow depth of field, photorealistic"


def _prompt_for_keyword(keyword: str) -> str:
    kw = keyword.lower()
    for topic, prompt in TOPIC_PROMPTS:
        if topic in kw:
            return prompt
    return DEFAULT_PROMPT


def _full_prompt(keyword: str) -> str:
    base = _prompt_for_keyword(keyword)
    return (
        f'Hyperrealistic editorial product photograph for a reselling/e-commerce blog. Topic: "{keyword}". '
        f"{base}. No face or full body visible — hands and product only, editorial lighting, "
        "warm neutral tones, photorealistic skin and fabric texture, sharp focus on the product. "
        "3:2 landscape orientation. No text, no watermarks, no logos, no brand names visible."
    )


def _generate_with_gemini(keyword: str) -> str | None:
    if not settings.google_api_key:
        return None

    prompt = _full_prompt(keyword)
    for model_id in GEMINI_MODELS:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={settings.google_api_key}"
            resp = httpx.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=60,
            )
            if resp.status_code != 200:
                logger.warning(f"Gemini {model_id}: HTTP {resp.status_code}")
                continue
            data = resp.json()
            parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                inline = part.get("inlineData")
                if inline and inline.get("data"):
                    return inline["data"]
        except Exception as e:
            logger.warning(f"Gemini {model_id} fout: {e}")
    return None


def _generate_with_pollinations(keyword: str) -> str | None:
    import base64
    import random

    full_prompt = _full_prompt(keyword) + ", DSLR quality, sharp focus"
    seed = random.randint(0, 999999)
    try:
        resp = httpx.get(
            "https://image.pollinations.ai/prompt/" + full_prompt.replace(" ", "%20"),
            params={"width": 1200, "height": 800, "model": "flux", "seed": seed, "nologo": "true"},
            timeout=90,
        )
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        logger.warning(f"Pollinations fallback mislukt: {e}")
        return None


def generate_featured_image_base64(keyword: str) -> str | None:
    """Retourneert base64 JPEG data, of None als beide providers falen (publicatie gaat dan zonder image door)."""
    image = _generate_with_gemini(keyword)
    if image:
        logger.info(f"Featured image via Gemini voor '{keyword}'")
        return image

    image = _generate_with_pollinations(keyword)
    if image:
        logger.info(f"Featured image via Pollinations voor '{keyword}'")
        return image

    logger.warning(f"Geen featured image kunnen genereren voor '{keyword}' — publiceer zonder")
    return None
