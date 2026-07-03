"""Record a ~20s screen capture of the demo-dashboard.html landing animation."""
import pathlib
import time
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "frontend" / "demo-dashboard.html"
OUT_DIR = ROOT / "scripts" / "output"
OUT_DIR.mkdir(exist_ok=True)

WIDTH, HEIGHT = 1280, 800
DURATION_S = 21

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": WIDTH, "height": HEIGHT},
        record_video_dir=str(OUT_DIR),
        record_video_size={"width": WIDTH, "height": HEIGHT},
    )
    page = context.new_page()
    page.goto(HTML_PATH.as_uri())
    time.sleep(DURATION_S)
    context.close()
    browser.close()

# Playwright names the file with a random hash; find and rename it.
videos = sorted(OUT_DIR.glob("*.webm"), key=lambda f: f.stat().st_mtime)
final = videos[-1]
target = OUT_DIR / "crosslisteu_demo.webm"
final.rename(target)
print(f"Saved: {target}")
