from backend.platforms.vinted import VintedPlatform
from backend.platforms.marktplaats import MarktplaatsPlatform, TweedehandsPlatform
from backend.platforms.ebay import EbayPlatform
from backend.platforms.etsy import EtsyPlatform
from backend.platforms.shopify import ShopifyPlatform
from backend.platforms.woocommerce import WooCommercePlatform

PLATFORM_REGISTRY = {
    "vinted": VintedPlatform(),
    "marktplaats": MarktplaatsPlatform(),
    "2dehands": TweedehandsPlatform(),
    "ebay": EbayPlatform(),
    "etsy": EtsyPlatform(),
    "shopify": ShopifyPlatform(),
    "woocommerce": WooCommercePlatform(),
}


def get_platform(name: str):
    platform = PLATFORM_REGISTRY.get(name)
    if not platform:
        raise ValueError(f"Unknown platform: {name}")
    return platform
