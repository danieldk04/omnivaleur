"""Record real screens of the live CrossList EU app for the marketing video.

Uses the seeded demo account (real items, real UI, real interactions). For screens
that are naturally empty/sparse on a fresh demo account (analytics numbers, eBay/
Shopify connection state, platform icons), we inject richer front-end display data
purely for the recording via page.evaluate — no backend writes, nothing persisted.
"""
import base64
import pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "scripts" / "output" / "real"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS = ROOT / "scripts" / "assets"

EMAIL = "dkresellacademy@gmail.com"
PASSWORD = "95rwPSLgHxncWDV"
BASE = "https://crosslisteu.com"

W, H = 1600, 1000


def data_uri(path, mime):
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


PLATFORM_LOGOS = {
    "marktplaats": data_uri(ASSETS / "marktplaats.png", "image/png"),
    "2dehands": data_uri(ASSETS / "2dehands.png", "image/png"),
    "vinted": data_uri(ASSETS / "vinted.png", "image/png"),
    "ebay": data_uri(ASSETS / "ebay.webp", "image/webp"),
    "shopify": data_uri(ASSETS / "shopify.webp", "image/webp"),
}


def new_ctx(p, name):
    browser = p.chromium.launch()
    ctx = browser.new_context(
        viewport={"width": W, "height": H},
        record_video_dir=str(OUT_DIR),
        record_video_size={"width": W, "height": H},
    )
    page = ctx.new_page()
    return browser, ctx, page


def rename_last_video(prefix):
    videos = sorted(OUT_DIR.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    final = videos[-1]
    target = OUT_DIR / f"{prefix}.webm"
    final.rename(target)
    print("Saved", target)


def login(page):
    page.goto(f"{BASE}/login")
    page.fill("#email", EMAIL)
    page.fill("#password", PASSWORD)
    page.click("form button")
    page.wait_for_url(f"{BASE}/app", timeout=15000)
    # Wait for real data to actually be loaded (not just a fixed timer).
    page.wait_for_function(
        "document.getElementById('stat-items') && document.getElementById('stat-items').textContent.trim() !== '' && document.getElementById('stat-items').textContent.trim() !== '—'",
        timeout=15000,
    )
    try:
        page.click("text=I already have the extension installed", timeout=2000)
    except Exception:
        pass
    page.wait_for_timeout(300)


def smooth_scroll(page, target_y, duration_ms=1200, steps=40):
    start = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        y = start + (target_y - start) * (i / steps)
        page.evaluate(f"window.scrollTo(0,{y})")
        page.wait_for_timeout(duration_ms // steps)


def move_mouse_smooth(page, x1, y1, x2, y2, steps=25, delay=12):
    for i in range(steps + 1):
        t = i / steps
        t = 1 - (1 - t) ** 3  # ease-out
        page.mouse.move(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        page.wait_for_timeout(delay)


def swap_platform_logos(page):
    """Real Platforms page: swap the emoji glyphs for actual brand logo images."""
    page.evaluate(
        """(logos) => {
            const order = ['marktplaats','2dehands','vinted','ebay','etsy','shopify'];
            const spans = [...document.querySelectorAll('#platforms-body span')]
              .filter(s => s.style.fontSize === '22px');
            spans.forEach((span, i) => {
              const key = order[i];
              const src = logos[key];
              if (!src) return;
              span.innerHTML = '';
              const img = document.createElement('img');
              img.src = src;
              img.style.width = '30px';
              img.style.height = '30px';
              img.style.objectFit = 'contain';
              img.style.borderRadius = '6px';
              span.appendChild(img);
            });
        }""",
        PLATFORM_LOGOS,
    )


with sync_playwright() as p:
    # ---- Segment 1: Dashboard (stats + real item photos) ----
    browser, ctx, page = new_ctx(p, "dashboard")
    login(page)
    page.wait_for_timeout(600)
    move_mouse_smooth(page, 200, 200, 400, 130, steps=15)
    page.wait_for_timeout(300)
    smooth_scroll(page, 280, duration_ms=1400)
    page.wait_for_timeout(400)
    move_mouse_smooth(page, 400, 400, 700, 620, steps=20)
    page.wait_for_timeout(1200)
    ctx.close(); browser.close()
    rename_last_video("01_dashboard")

    # ---- Segment 2: Items list close-up ----
    browser, ctx, page = new_ctx(p, "items")
    login(page)
    page.evaluate("showView('items')")
    page.wait_for_selector("table tbody tr, .item-row", timeout=8000)
    page.wait_for_timeout(200)
    move_mouse_smooth(page, 300, 200, 500, 500, steps=20)
    page.wait_for_timeout(1800)
    ctx.close(); browser.close()
    rename_last_video("02_items")

    # ---- Segment 3: Platforms page with real logos + all connected ----
    browser, ctx, page = new_ctx(p, "platforms")
    login(page)
    page.evaluate("showView('platforms')")
    page.wait_for_selector("#platforms-body div", timeout=8000)
    page.evaluate("""() => {
        if (window.state && !state.connected.includes('ebay')) state.connected.push('ebay');
        if (window.state && !state.connected.includes('shopify')) state.connected.push('shopify');
        if (typeof renderPlatforms === 'function') renderPlatforms();
    }""")
    page.wait_for_timeout(150)
    swap_platform_logos(page)
    page.wait_for_timeout(200)
    move_mouse_smooth(page, 300, 200, 500, 550, steps=25)
    page.wait_for_timeout(1800)
    ctx.close(); browser.close()
    rename_last_video("03_platforms")

    # ---- Segment 4: Analytics with injected rich chart data ----
    browser, ctx, page = new_ctx(p, "analytics")
    login(page)
    page.evaluate("showView('analytics')")
    page.wait_for_function(
        "typeof Chart !== 'undefined' && Chart.getChart('an-chart-revenue') && Chart.getChart('an-chart-sales')",
        timeout=8000,
    )
    page.evaluate("""() => {
      const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
      setTxt('an-revenue', '€1,840.00');
      setTxt('an-profit', '€1,120.00');
      setTxt('an-sales', '38');
      setTxt('an-avg-profit', '€29.50');
      const labels = ['3 Apr','15 Apr','27 Apr','9 May','21 May','2 Jun','14 Jun','26 Jun'];
      const rev = [120,180,140,260,210,340,290,380];
      const profit = [70,110,90,160,130,210,180,240];
      const sales = [2,4,3,6,5,8,6,9];
      const _anChartRevenue = Chart.getChart('an-chart-revenue');
      if (_anChartRevenue) {
        _anChartRevenue.data.labels = labels;
        _anChartRevenue.data.datasets[0].data = rev;
        _anChartRevenue.data.datasets[1].data = profit;
        _anChartRevenue.update();
      }
      const _anChartSales = Chart.getChart('an-chart-sales');
      if (_anChartSales) {
        _anChartSales.data.labels = labels;
        _anChartSales.data.datasets[0].data = sales;
        _anChartSales.update();
      }
      const platList = document.getElementById('an-platform-list');
      if (platList) platList.innerHTML = `
        <li style="display:flex;align-items:center;gap:10px;padding:6px 0">
          <span style="font-weight:600;font-size:12px;min-width:90px">Marktplaats</span>
          <div style="flex:1;background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden"><div style="width:85%;height:100%;background:#2563eb"></div></div>
          <span style="font-size:12px;font-weight:700">€780</span>
        </li>
        <li style="display:flex;align-items:center;gap:10px;padding:6px 0">
          <span style="font-weight:600;font-size:12px;min-width:90px">Vinted</span>
          <div style="flex:1;background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden"><div style="width:60%;height:100%;background:#34d399"></div></div>
          <span style="font-size:12px;font-weight:700">€540</span>
        </li>
        <li style="display:flex;align-items:center;gap:10px;padding:6px 0">
          <span style="font-weight:600;font-size:12px;min-width:90px">eBay</span>
          <div style="flex:1;background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden"><div style="width:35%;height:100%;background:#f59e0b"></div></div>
          <span style="font-size:12px;font-weight:700">€320</span>
        </li>
      `;
    }""")
    page.wait_for_timeout(1000)  # let Chart.js finish its update animation
    move_mouse_smooth(page, 300, 300, 700, 450, steps=25)
    page.wait_for_timeout(1600)
    ctx.close(); browser.close()
    rename_last_video("04_analytics")

    # ---- Segment 5: Margin calculator, live typing ----
    browser, ctx, page = new_ctx(p, "calculator")
    login(page)
    page.evaluate("showView('calculator')")
    page.wait_for_selector("input", timeout=8000)
    page.wait_for_timeout(200)
    inputs = page.query_selector_all("input")
    purchase_input = None
    profit_input = None
    for inp in inputs:
        ph = inp.get_attribute("placeholder") or ""
        if "0.00" in ph:
            purchase_input = inp
        if "10.00" in ph:
            profit_input = inp
    if purchase_input:
        purchase_input.click()
        page.wait_for_timeout(200)
        purchase_input.type("18", delay=110)
    page.wait_for_timeout(500)
    if profit_input:
        profit_input.click()
        page.wait_for_timeout(200)
        profit_input.fill("")
        profit_input.type("22", delay=110)
    page.wait_for_timeout(2000)
    ctx.close(); browser.close()
    rename_last_video("05_calculator")

print("Done. Segments in", OUT_DIR)
