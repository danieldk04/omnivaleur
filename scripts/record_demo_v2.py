"""Record the polished, feature-complete vertical (9:16) social demo with real product photos."""
import pathlib
import time
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "scripts" / "social_demo_v2.html"
OUT_DIR = ROOT / "scripts" / "output"
OUT_DIR.mkdir(exist_ok=True)

WIDTH, HEIGHT = 608, 1080
DURATION_S = 24.5

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": WIDTH, "height": HEIGHT},
        record_video_dir=str(OUT_DIR),
        record_video_size={"width": WIDTH, "height": HEIGHT},
    )
    page = context.new_page()
    page.goto(HTML_PATH.as_uri())
    # Let all Unsplash images finish loading before the timeline starts consuming them.
    page.wait_for_timeout(400)
    time.sleep(DURATION_S)
    context.close()
    browser.close()

videos = sorted(OUT_DIR.glob("*.webm"), key=lambda f: f.stat().st_mtime)
final = videos[-1]
target = OUT_DIR / "crosslisteu_social_v2.webm"
final.rename(target)
print(f"Saved: {target}")
