"""One-off: log into the live app and screenshot the main screens for demo planning."""
from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path(__file__).parent / "output" / "explore"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("https://crosslisteu.com/login")
    page.fill("#email", "dkresellacademy@gmail.com")
    page.fill("#password", "95rwPSLgHxncWDV")
    page.click("button[type=submit], form button")
    page.wait_for_timeout(3000)

    # Dismiss the extension-install overlay if present.
    try:
        page.click("text=I already have the extension installed", timeout=2000)
    except Exception:
        pass
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "01_dashboard.png"))

    for view in ["items", "analytics", "calculator", "platforms", "protections", "prijs"]:
        page.evaluate(f"showView('{view}')")
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / f"02_{view}.png"))

    browser.close()
