"""
Featured-image generatie voor content_pages, zelfde patroon als in de
AXONGEAR/Revaleur blog-automations: Gemini image-modellen eerst, gratis
Pollinations.ai (Flux) als fallback zodat een ontbrekende GOOGLE_API_KEY
nooit een publicatie blokkeert.
"""
import logging

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

GEMINI_MODELS = ["gemini-2.5-flash-image", "gemini-3.1-flash-image"]

TOPIC_PROMPTS = {
    "vinted": "a real person photographing a folded clothing item on a bed with natural window light, ready to list it online, candid lifestyle moment, photorealistic",
    "marktplaats": "a real person packing a used item into a cardboard box at home, preparing it for a local buyer pickup, warm natural light, photorealistic",
    "ebay": "a small home-based reseller wrapping a parcel at a desk covered in shipping labels and bubble wrap, candid editorial photography, photorealistic",
    "kleding": "a real person steaming and folding secondhand clothing on a clothing rack, soft natural daylight, editorial lifestyle photography, photorealistic",
    "verzendlabel": "close-up of real hands printing and applying a shipping label to a parcel, warm desk lighting, shallow depth of field, photorealistic",
    "default": "a real natural-looking reseller working at a laptop surrounded by neatly organized secondhand items ready to ship, warm home office light, candid editorial photography, photorealistic",
}


def _prompt_for_keyword(keyword: str) -> str:
    kw = keyword.lower()
    for topic, prompt in TOPIC_PROMPTS.items():
        if topic in kw:
            return prompt
    return TOPIC_PROMPTS["default"]


def _generate_with_gemini(keyword: str) -> str | None:
    if not settings.google_api_key:
        return None

    base = _prompt_for_keyword(keyword)
    prompt = (
        f'Hyperrealistic editorial photograph for a reselling/e-commerce blog. Topic: "{keyword}". '
        f"{base}. Real, natural-looking human, candid unposed moment, authentic editorial lighting, "
        "shallow depth of field, warm natural tones, photorealistic skin and fabric texture. "
        "3:2 landscape orientation. No text, no watermarks, no logos."
    )

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

    base = _prompt_for_keyword(keyword)
    full_prompt = (
        f"{base}, real natural-looking human, candid unposed moment, hyperrealistic editorial photography, "
        "DSLR quality, warm natural tones, sharp focus, no text, no logos, no watermarks"
    )
    seed = random.randint(0, 999999)
    url = f"https://image.pollinations.ai/prompt/{httpx.QueryParams({'p': full_prompt})['p']}"
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
