// Shared, robust form-filling engine for Marktplaats / 2dehands (Adevinta ECG forms).
// Exposes window.CL with reliable helpers. Loaded before each platform script.
window.CL = (() => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const qs = (sel) => document.querySelector(sel);

  function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  function waitForEl(sel, timeout = 10000) {
    return new Promise((resolve, reject) => {
      const el = document.querySelector(sel);
      if (el) return resolve(el);
      const obs = new MutationObserver(() => {
        const f = document.querySelector(sel);
        if (f) { obs.disconnect(); resolve(f); }
      });
      obs.observe(document.body, { childList: true, subtree: true });
      setTimeout(() => { obs.disconnect(); reject(new Error("Timeout: " + sel)); }, timeout);
    });
  }

  function fillInput(el, value) {
    if (!el) return false;
    const proto = el instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    el.dispatchEvent(new Event("focus", { bubbles: true }));
    try {
      setter.call(el, value);
    } catch (e) {
      el.value = value;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));
    return true;
  }

  // Human-like typing: sets the full value at once but adds random pre/post delays
  // so the browser sees natural timing gaps instead of instant programmatic fills.
  async function fillInputHuman(el, value) {
    if (!el) return false;
    await sleep(60 + Math.random() * 120);
    el.dispatchEvent(new Event("focus", { bubbles: true }));
    await sleep(40 + Math.random() * 80);
    const proto = el instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    try { setter.call(el, value); } catch (e) { el.value = value; }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    await sleep(30 + Math.random() * 60);
    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(50 + Math.random() * 100);
    el.dispatchEvent(new Event("blur", { bubbles: true }));
    return true;
  }

  // Fill a native <select> element by finding the best-matching option text.
  function fillNativeSelect(selectEl, value) {
    if (!selectEl || !value) return false;
    const opts = [...selectEl.options].filter((o) => o.value !== "" && !o.disabled);
    let best = null, bestScore = 0;
    for (const o of opts) {
      const s = matchScore(o.text, value);
      if (s > bestScore) { best = o; bestScore = s; }
    }
    if (!best) return false;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set;
    setter.call(selectEl, best.value);
    selectEl.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function clickRadioByValue(value) {
    const radio = [...document.querySelectorAll('input[type="radio"]')].find((r) => r.value === value);
    if (radio) { radio.click(); return true; }
    return false;
  }

  // ---- Main-world execution via background worker ----
  // Content scripts run in an isolated JS world where page properties like __lexicalEditor
  // are invisible. chrome.scripting.executeScript (called from background) runs in the
  // page's main world and bypasses the page's CSP. We message the background to do it.
  function runInMainWorld(type, data) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        console.error("[CrossList] runInMainWorld timeout:", type);
        resolve(false);
      }, 8000);
      chrome.runtime.sendMessage({ type, ...data }, (result) => {
        clearTimeout(timer);
        if (chrome.runtime.lastError) {
          console.error("[CrossList] sendMessage error:", type, chrome.runtime.lastError.message);
        }
        resolve(result ?? false);
      });
    });
  }

  // ---- Lexical / contenteditable description ----
  let _pendingDescription = null;
  let _descriptionSelector = null;

  async function fillDescription(selectors, text) {
    const selector = selectors.find((s) => document.querySelector(s));
    if (!selector) return false;
    const value = (text || "").slice(0, 2000);
    _pendingDescription = value;
    _descriptionSelector = selector;
    document.querySelector(selector)?.scrollIntoView({ block: "center" });
    const ok = await runInMainWorld("FILL_DESC", { selector, text: value });
    return !!ok;
  }

  // ---- find the control (input/select/button) that belongs to a field label ----
  function findFieldByLabel(labelText) {
    const want = labelText.toLowerCase();
    const candidates = [...document.querySelectorAll('label, span, h3, h4, h5, legend, dt, p, div')];
    const labelEl = candidates.find((el) => {
      const own = [...el.childNodes].filter((n) => n.nodeType === 3)
        .map((n) => n.textContent.trim()).join(" ").trim().toLowerCase().replace(/\s*\*$/, "");
      if (own === want) return true;
      // Fallback: full textContent for <label><span>Maat</span></label> patterns
      const full = el.textContent.trim().toLowerCase().replace(/\s*\*$/, "");
      return full === want && el.children.length <= 2 && !el.querySelector('input, button, select, textarea');
    });
    if (!labelEl) return null;

    const forId = labelEl.getAttribute && labelEl.getAttribute("for");
    if (forId) { const t = document.getElementById(forId); if (t) return t; }

    let node = labelEl.parentElement;
    for (let depth = 0; depth < 4 && node; depth++) {
      const ctl = node.querySelector?.(
        'input:not([type="hidden"]):not([readonly]), select, button, [role="combobox"], [role="button"], [tabindex="0"]'
      );
      if (ctl && !labelEl.contains(ctl)) return ctl;
      node = node.parentElement;
    }
    return labelEl.nextElementSibling?.querySelector?.('input, select, button, [role="combobox"]')
        || labelEl.nextElementSibling;
  }

  // score how well an option's text matches a target value (token-aware)
  function matchScore(elText, value) {
    const a = elText.trim().toLowerCase();
    const b = value.trim().toLowerCase();
    if (!a || !b) return 0;
    if (a === b) return 3;
    const tokenRe = new RegExp(`(^|[\\s(/-])${escapeRegex(b)}([\\s)/-]|$)`, "i");
    if (tokenRe.test(a)) return 2;
    if (b.length >= 3 && a.includes(b)) return 1;
    return 0;
  }

  // poll for the best-matching visible option (for custom dropdowns / autocomplete)
  async function waitForOption(value, timeout = 3500) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const opts = [...document.querySelectorAll(
        '[role="option"], [role="listbox"] li, [role="menuitem"], ul[class*="list"] li, ul[class*="List"] li, [class*="option"], [class*="Option"], li[data-value], [data-testid*="option"]'
      )].filter((el) => el.offsetParent !== null);
      let best = null, bestScore = 0;
      for (const el of opts) {
        const s = matchScore(el.textContent, value);
        if (s > bestScore) { best = el; bestScore = s; }
      }
      if (best && bestScore > 0) return best;
      await sleep(70);
    }
    return null;
  }

  function closePopup() {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    document.body.click();
  }

  function stillPlaceholder(trigger) {
    if (trigger.tagName === "SELECT") return trigger.value === "" || trigger.options[trigger.selectedIndex]?.disabled;
    return /kies/i.test((trigger.textContent || trigger.value || "").trim());
  }

  // Robust dropdown/select selection. Handles native <select> and custom dropdowns.
  async function selectDropdown(labels, value) {
    if (!value) return false;
    const labelArr = Array.isArray(labels) ? labels : [labels];
    for (const label of labelArr) {
      const trigger = findFieldByLabel(label);
      if (!trigger) continue;

      // Native <select>: set value directly — no clicking/waiting needed
      if (trigger.tagName === "SELECT") {
        const ok = fillNativeSelect(trigger, value);
        if (ok) return true;
        continue;
      }

      // Plain text input (typeahead): fill directly
      if (trigger.tagName === "INPUT" && trigger.type !== "radio" && trigger.type !== "checkbox") {
        fillInput(trigger, value);
        return true;
      }

      // Custom dropdown (button / combobox): click and wait for rendered options
      for (let attempt = 0; attempt < 3; attempt++) {
        const t = trigger.isConnected ? trigger : findFieldByLabel(label);
        if (!t) break;
        closePopup();
        await sleep(150);
        t.scrollIntoView({ block: "center" });
        await sleep(80);
        t.click();
        const opt = await waitForOption(value, 3500);
        if (opt) {
          opt.click();
          await sleep(400);
          if (!stillPlaceholder(t)) return true;
        }
        closePopup();
        await sleep(200);
      }
    }
    return false;
  }

  // Brand fill: runs in main world via background worker.
  // Sets value via prototype setter without events — React won't re-render and reset it.
  // Re-applied right before submit in case an earlier re-render cleared it.
  let _pendingBrand = null;

  async function fillBrand(brand) {
    // Native <select> for Merk (some categories) — works from isolated world
    const trigger = findFieldByLabel("Merk");
    if (trigger?.tagName === "SELECT") {
      return fillNativeSelect(trigger, brand);
    }

    _pendingBrand = brand;
    return runInMainWorld("FILL_BRAND", { brand });
  }

  function fillManufacturer(item) {
    const fields = [
      ["textAttribute[manufacturerTradename]", item.manufacturer_name || "Revaleur"],
      ["textAttribute[manufacturerAddress]", item.manufacturer_address || " "],
      ["textAttribute[manufacturerEmail]", item.manufacturer_email || "info@revaleur.com"],
    ];
    for (const [name, val] of fields) {
      const el = qs(`input[name="${name}"]`);
      if (el) { el.scrollIntoView({ block: "center" }); fillInput(el, val); }
    }
  }

  function selectBundleFree() {
    const bundleEl = qs('[data-testid="bundle-option-FREE"] input');
    if (bundleEl) { bundleEl.click(); return; }
    clickRadioByValue("FREE");
  }

  // Pakketgrootte (2dehands): pick the row containing the wanted weight band.
  async function selectPackageSize(bandRegex = /0\s*-\s*2\s*kg/i) {
    for (let i = 0; i < 20; i++) {
      const rows = [...document.querySelectorAll('label, li, [role="radio"], [class*="radio"], [class*="Radio"]')]
        .filter((el) => el.offsetParent !== null && el.textContent.length < 80 && bandRegex.test(el.textContent));
      if (rows.length) {
        const row = rows[0];
        const radio = row.querySelector?.('input[type="radio"]') || row.closest('label, li')?.querySelector('input[type="radio"]');
        if (radio) radio.click();
        row.click();
        await sleep(150);
        const close = [...document.querySelectorAll('button[aria-label*="luit"], button[aria-label*="lose"], [data-testid*="close"]')]
          .find((b) => b.offsetParent !== null);
        if (close) close.click();
        return true;
      }
      await sleep(100);
    }
    const vis = [...document.querySelectorAll('input[type="radio"]')].filter((r) => r.offsetParent !== null);
    if (vis[0]) { vis[0].click(); return true; }
    return false;
  }

  async function uploadPhotos(urls, opts = {}) {
    const fileInput = qs('input[type="file"]');
    if (!fileInput) return false;
    const files = (await Promise.all(urls.map((u) => fetchFile(u, opts)))).filter(Boolean);
    if (!files.length) return false;
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    await waitForEl('[class*="hz-Listing"] img, [class*="photo"] img, [class*="thumbnail"] img, [data-testid*="image"] img', 8000)
      .catch(() => sleep(1500));
    return true;
  }

  async function fetchFile(url, opts = {}) {
    try {
      const resp = await fetch(url);
      const blob = await resp.blob();
      const name = url.split("/").pop()?.split("?")[0] || "photo.jpg";
      const finalBlob = opts.jitter ? await jitterImage(blob) : blob;
      return new File([finalBlob], name, { type: "image/jpeg" });
    } catch (e) { console.warn("CrossList photo fetch failed", url, e); return null; }
  }

  // Apply random 1-3px crop per side + a sub-perceptual brightness/contrast/
  // saturation nudge + canvas re-render (strips EXIF), then re-encode at a
  // slightly randomised JPEG quality. Changes both the byte hash AND the
  // perceptual hash without any visible difference — makes Vinted treat these
  // as genuinely new images on a relist, not a re-upload of the same photos.
  function jitterImage(blob) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        URL.revokeObjectURL(url);
        const rand = () => Math.floor(Math.random() * 3) + 1; // 1-3px
        const cx = rand(), cy = rand(), cw = rand(), ch = rand();
        const canvas = document.createElement("canvas");
        canvas.width  = img.naturalWidth  - cx - cw;
        canvas.height = img.naturalHeight - cy - ch;
        const ctx = canvas.getContext("2d");
        // Imperceptible tone shift (±1.5% brightness, ±1.5% contrast, ±2% sat).
        const jit = (spread) => 1 + (Math.random() * 2 - 1) * spread;
        try {
          ctx.filter = `brightness(${jit(0.015).toFixed(4)}) contrast(${jit(0.015).toFixed(4)}) saturate(${jit(0.02).toFixed(4)})`;
        } catch (e) { /* filter unsupported → crop+re-encode still changes the hash */ }
        ctx.drawImage(img, -cx, -cy);
        // Slightly randomise quality too (0.90–0.93) so the encoder output differs.
        const q = 0.90 + Math.random() * 0.03;
        canvas.toBlob((b) => resolve(b || blob), "image/jpeg", q);
      };
      img.onerror = () => { URL.revokeObjectURL(url); resolve(blob); };
      img.src = url;
    });
  }

  async function submitListing(idFromUrl) {
    // Brand FIRST — closing the brand modal triggers a React re-render that resets
    // the Lexical EditorState. Description must be filled AFTER brand to survive.
    if (_pendingBrand) {
      await runInMainWorld("FILL_BRAND", { brand: _pendingBrand });
      await sleep(500); // wait for React to settle after modal close
    }

    // Description LAST — fills Lexical EditorState after all React re-renders are done.
    if (_pendingDescription && _descriptionSelector) {
      await runInMainWorld("FILL_DESC", { selector: _descriptionSelector, text: _pendingDescription });
    }

    const submitContainer = qs('[data-testid="place-listing-submit-button"]');
    const btn = submitContainer?.querySelector("button") || qs('button[type="submit"]');
    if (!btn) throw new Error("Plaats-knop niet gevonden");
    btn.scrollIntoView({ block: "center" });
    await sleep(800); // Lexical commit is async — give it time before submit fires
    btn.click();

    const id = await waitForListingUrl(idFromUrl, 20000).catch(() => null);
    if (id) return id;

    const errs = [...document.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"], [aria-invalid="true"]')]
      .map((el) => el.textContent.trim()).filter((t) => t.length > 0 && t.length < 200);
    const uniq = [...new Set(errs)];
    throw new Error(`Niet geplaatst — vul de rode velden aan en klik zelf op Plaatsen. ${uniq.join(" | ")}`.trim());
  }

  async function waitForListingUrl(extraMatcher, timeout) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const href = location.href;

      // Detect logout/session expiry redirect — throw so tab stays open for user
      if (/\/(login|inloggen|signin|account\/login)/i.test(href)) {
        throw new Error("Uitgelogd tijdens publiceren — log opnieuw in en klik zelf op Plaatsen");
      }

      const m = href.match(/\/seller\/view\/(m\d+)/) || href.match(/\/(m\d{8,})/) || (extraMatcher && href.match(extraMatcher));
      if (m) return m[1];
      if (href.includes("placeAdSuccess")) return (href.match(/(m\d{6,})/) || [])[1] || `posted_${Date.now()}`;
      // Left the /plaats/ flow with a listing ID in the URL → success
      if (!href.includes("/plaats/")) {
        const id = (href.match(/(m\d{6,})/) || [])[1];
        if (id) return id;
        // No recognisable ID and not a login page — something unexpected, wait a bit more
      }
      await sleep(250);
    }
    throw new Error("timeout");
  }

  // run a named step so a single failure never aborts the whole flow
  async function step(name, fn) {
    try { await fn(); } catch (e) { console.warn(`CrossList step "${name}" failed:`, e); }
  }

  // Enable "Bieden vanaf" and fill the minimum bid as a percentage of the asking price.
  async function fillBidding(price, percentage) {
    const minBid = Math.round(price * percentage / 100 * 100) / 100;

    // Step 1: activate bidding mode — try radio values first, then label clicks
    const bidValues = ["BIDDING_FROM", "BIDDING", "BID_FROM", "bieden", "bid"];
    let activated = false;
    for (const val of bidValues) {
      const r = [...document.querySelectorAll('input[type="radio"], input[type="checkbox"]')]
        .find(el => el.value?.toLowerCase() === val.toLowerCase());
      if (r) { r.click(); activated = true; break; }
    }

    if (!activated) {
      // Try clicking any element whose text matches "bieden" pricing options
      const clickTargets = [...document.querySelectorAll(
        'label, [role="radio"], [role="button"], button, span, div[tabindex]'
      )].filter(el => {
        const txt = el.textContent.trim().toLowerCase();
        return (txt === "bieden" || txt === "bieden vanaf" || txt === "bieden of kopen") && txt.length < 30;
      });
      for (const t of clickTargets) { t.click(); activated = true; break; }
    }

    if (!activated) {
      // Last resort: use selectDropdown with common label names for the pricing type
      await selectDropdown(["Prijstype", "Type", "Biedmogelijkheid"], "Bieden");
    }

    // Wait for React to reveal the minimum bid input after toggle activation
    // Poll up to 3s for the field to appear (it only exists after toggle is ON)
    const BID_SELECTORS = [
      'input[name="price.minimumBidPrice"]',
      'input[name="minimalBid"]',
      'input[name="minimumBid"]',
      'input[name="bid.value"]',
      'input[name="bid.minimumBid"]',
      'input[name="lowestBid"]',
      'input[placeholder*="minimumbod"]',
      'input[placeholder*="minimale"]',
      'input[placeholder*="bod"]',
    ].join(", ");

    let bidInput = null;
    for (let i = 0; i < 15; i++) {
      await sleep(200);
      bidInput = qs(BID_SELECTORS)
        || findFieldByLabel("Bieden vanaf")
        || findFieldByLabel("Minimumbod");
      if (bidInput) break;
    }

    if (bidInput && bidInput.tagName === "INPUT") {
      const val = bidInput.type === "number"
        ? String(minBid)
        : String(minBid).replace(".", ",");
      fillInput(bidInput, val);
    }
  }

  // Truncate to maxLen chars without cutting mid-word. Trims at last space before limit.
  function smartTrunc(str, maxLen) {
    if (str.length <= maxLen) return str;
    const cut = str.lastIndexOf(" ", maxLen);
    return cut > 0 ? str.slice(0, cut) : str.slice(0, maxLen);
  }

  return {
    sleep, qs, waitForEl, fillInput, fillInputHuman, fillNativeSelect, clickRadioByValue, fillDescription,
    findFieldByLabel, selectDropdown, fillBrand, fillManufacturer, selectBundleFree,
    selectPackageSize, uploadPhotos, submitListing, step, closePopup, smartTrunc, fillBidding,
  };
})();
