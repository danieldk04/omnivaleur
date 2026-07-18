// Content script for Facebook Marketplace — facebook.com/marketplace/*
//
// ⚠️ BETA / HAPPY-PATH. Facebook does not expose stable selectors (class names are
// obfuscated and rotate) and actively detects automation. This script therefore
// leans on aria-labels, roles and visible label text, and is best-effort only.
// It can break whenever Facebook reworks the Marketplace form, and using it
// carries a real risk of the seller's account being flagged. The dashboard warns
// the user about this before they select Facebook as a target.
(async () => {
  const PLATFORM = "facebook";
  // Facebook Marketplace "Staat"/"Condition" options. Verified live against the
  // real form (2026-07, NL account): "Nieuw" / "Gebruikt - zo goed als nieuw" /
  // "Gebruikt - in goede staat" / "Gebruikt - in redelijke staat". FB localises
  // the whole form, so each dashboard condition maps to a list of candidate option
  // texts (Dutch first, English fallback) — selectCombo tries them in order.
  const CONDITION_MAP = {
    new_with_tags: ["Nieuw", "New"],
    new: ["Nieuw", "New"],
    good: ["Gebruikt - in goede staat", "Used - good", "Used – good"],
    fair: ["Gebruikt - in redelijke staat", "Used - fair", "Used – fair"],
    poor: ["Gebruikt - in redelijke staat", "Used - fair", "Used – fair"],
  };
  const { qs, sleep, waitForEl, uploadPhotos, smartTrunc } = window.CL;

  const job = await getJob();
  if (!job) return;
  const { id: jobId, serverUrl, payload: item } = job;

  // Facebook redirects the create form to a one-time DMA/GDPR consent gate
  // (/privacy/consent?flow=fb_dma_marketplace) and to security checkpoints. Our
  // content script can't fill those, so without this guard the job tab would sit
  // there and the publish job would silently hang. Fail loudly with a fixable
  // instruction instead — the user grants the consent once, by hand, then retries.
  if (/\/privacy\/consent|\/checkpoint/.test(location.href)) {
    send("JOB_ERROR", null,
      "Facebook wants a one-time Marketplace consent (or a security check) before " +
      "it lets anything list. Open Facebook Marketplace once, click ‘Aan de slag’ / " +
      "complete the check, then publish this item again.");
    return;
  }

  try {
    if (job.action === "delete") {
      await deleteListingFb(item);
      send("JOB_DONE", {});
    } else {
      await fillForm(item);
      const { id, url } = await publishAndCapture();
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: url });
    }
  } catch (e) {
    send("JOB_ERROR", null, String(e)); // tab stays open for manual recovery
  }

  // ── Field helpers (aria-label / label-text based, FB has no stable testids) ──

  // Find a text input / textarea by its accessible label. FB labels the field via
  // aria-label on the control itself, or via a <label> whose text precedes it.
  function findField(labelRe) {
    const controls = [...document.querySelectorAll(
      'input[type="text"], input:not([type]), textarea, [contenteditable="true"], [role="textbox"]'
    )];
    return controls.find((el) => {
      if (!isVisible(el)) return false;
      // Test each accessible-name source on its own (trimmed) so an anchored
      // regex like /^titel$/ still matches. VERIFIED on the live FB form: the
      // Titel/Prijs inputs have NO aria-label/placeholder — their name comes from
      // the WRAPPING <label> (e.g. <label><span>Titel</span><input></label>), so
      // el.closest('label').textContent is the source that actually works.
      const names = [
        el.getAttribute("aria-label"),
        el.getAttribute("placeholder"),
        el.closest("label")?.textContent,
      ];
      const labelledby = el.getAttribute("aria-labelledby");
      if (labelledby) names.push(document.getElementById(labelledby)?.textContent);
      return names.some((n) => n && labelRe.test(n.trim()));
    });
  }

  function isVisible(el) {
    return !!el && (el.offsetParent !== null || el.getClientRects().length > 0);
  }

  // Type into a React-controlled input the way FB expects (native setter + input
  // event), so React registers the value rather than discarding it on re-render.
  async function typeInto(el, value) {
    if (!el || value == null) return false;
    el.focus();
    const proto = el.tagName === "TEXTAREA"
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter && el.value !== undefined) {
      setter.call(el, "");
      el.dispatchEvent(new Event("input", { bubbles: true }));
      setter.call(el, String(value));
    } else {
      // contenteditable / role=textbox path
      el.textContent = String(value);
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(250);
    return true;
  }

  // Open a FB combobox (Categorie/Staat) identified by its aria-label, then pick
  // the option matching one of `candidates` (tried in order). FB is a role=combobox
  // that opens a role=listbox of role=option rows; the category picker also exposes
  // a search box we can type into to filter a long taxonomy.
  async function selectCombo(labelRe, candidates) {
    const wants = (Array.isArray(candidates) ? candidates : [candidates])
      .filter(Boolean).map((c) => String(c).toLowerCase().trim());
    if (!wants.length) return false;

    // VERIFIED live: the Categorie/Staat comboboxes also have NO aria-label —
    // their name comes from the wrapping <label>. Match aria-label OR the closest
    // <label> text, then fall back to the element's own text.
    const comboName = (el) =>
      el.getAttribute("aria-label") || el.closest("label")?.textContent || "";
    const combos = [...document.querySelectorAll('[role="combobox"], [aria-haspopup="listbox"], [role="button"]')]
      .filter(isVisible);
    const trigger = combos.find((el) => labelRe.test((comboName(el) || "").trim()))
      || combos.find((el) => labelRe.test((el.textContent || "").slice(0, 60)));
    if (!trigger) return false;
    trigger.click();
    await sleep(800);

    // Options render two ways (both VERIFIED live): "Staat" opens role=option rows,
    // but "Categorie" opens a tree of plain clickable <div>s (role=null) — so we
    // can't rely on role=option. Match any visible node whose EXACT text is one of
    // the candidates, preferring the innermost node (fewest children), then click.
    const sel = '[role="option"], [role="menuitem"], [role="menuitemradio"], li, div, span, a';
    const deadline = Date.now() + 4000;
    let opt = null;
    while (Date.now() < deadline && !opt) {
      const nodes = [...document.querySelectorAll(sel)]
        .filter((el) => isVisible(el) && el.childElementCount <= 3)
        .map((el) => ({ el, t: (el.textContent || "").trim().toLowerCase() }))
        .filter((x) => x.t && x.t.length < 60);
      const innermost = (list) => list.sort((a, b) => a.el.childElementCount - b.el.childElementCount)[0]?.el;
      for (const w of wants) {
        opt = innermost(nodes.filter((x) => x.t === w))          // exact match wins
           || innermost(nodes.filter((x) => x.t.includes(w)));   // then substring
        if (opt) break;
      }
      if (!opt) await sleep(250);
    }
    if (!opt) return false;
    opt.click();
    await sleep(500);
    return true;
  }

  // Map the item to Facebook's flat clothing categories (VERIFIED leaves:
  // "Herenkleding en -schoenen" / "Dameskleding en -schoenen"), which are directly
  // selectable. This is a clothing-first tool, so gender drives the pick; the
  // generic "Kleding en accessoires" is the fallback when gender is unknown.
  // Format a price for FB's price input. VERIFIED live: FB Marketplace's price
  // field is INTEGER-ONLY — it rounds whatever you type (29,50 → €30, 19,95 → €20)
  // and, worse, reads a "." as a thousands separator ("29.99" → 2999). So we skip
  // separators entirely and type the rounded whole-euro amount, which is exactly
  // what FB would store anyway. `field` is unused but kept for signature stability.
  function formatPrice(price, field) {
    const num = Number(price);
    if (!Number.isFinite(num)) return String(price || "");
    return String(Math.round(num));
  }

  function fbCategoryCandidates(item) {
    const g = (item.gender || "").toLowerCase();
    const cat = (item.category || "").toLowerCase();
    const isMen = /heren|\bmen\b|man/.test(g) || /heren|\bmen\b/.test(cat);
    const isWomen = /dames|women|vrouw/.test(g) || /dames|women/.test(cat);
    if (isMen) return ["Herenkleding en -schoenen", "Men’s clothing & shoes", "Kleding en accessoires"];
    if (isWomen) return ["Dameskleding en -schoenen", "Women’s clothing & shoes", "Kleding en accessoires"];
    return ["Kleding en accessoires", "Clothing & accessories"];
  }

  async function fillForm(item) {
    // Photos first — FB's create form opens straight on the photo step.
    await waitForEl('input[type="file"]', 20000);
    if (item.photo_urls?.length) {
      await uploadPhotos(item.photo_urls.slice(0, 20));
      // FB renders a blob:/scontent preview thumbnail once it accepts the files.
      // If none shows up the upload silently failed (usually a cross-origin fetch
      // block on the image host) — fail loudly rather than publish without photos.
      const ok = await waitForPhotoPreview(6000);
      if (!ok) throw new Error(
        "Photos could not be added to Facebook (the image files were rejected or " +
        "blocked). Nothing was published. Try again, or add the photos by hand.");
    }
    await sleep(800);

    // FB localises the whole form (verified NL: "Titel"/"Prijs"/"Categorie"/
    // "Staat"), so every label match accepts both the Dutch and English term.
    await typeInto(findField(/^(titel|title)$/i), smartTrunc(item.title || "", 100));

    // Price is locale-sensitive. On the Dutch form the number input reads "." as a
    // THOUSANDS separator, so typing "29.99" is stored as 2999. Detect the field's
    // language from its own label and type the matching decimal separator ("29,99"
    // on NL, "29.99" on EN). Whole amounts are typed without decimals.
    const priceField = findField(/^(prijs|price)$/i);
    if (priceField) await typeInto(priceField, formatPrice(item.price, priceField));

    // Category is required. FB uses its own flat taxonomy (no free-text search),
    // so we map the item to a verified selectable leaf rather than typing.
    await selectCombo(/categorie|category/i, fbCategoryCandidates(item));
    await selectCombo(/staat|conditie|condition/i, CONDITION_MAP[item.condition] || CONDITION_MAP.good);

    // Description ("Beschrijving") is a <textarea> that only mounts AFTER a category
    // is picked (it's a clothing-specific field), so it can render a beat late.
    // Poll for it instead of a single lookup — that late mount is why the field
    // stayed empty before while title/price/category/condition all filled.
    const desc = await waitForField(/^(beschrijving|description)$/i, 5000);
    if (desc) await typeInto(desc, item.description || "");
    await sleep(400);
  }

  // Poll findField until the control mounts (or timeout). Used for fields FB adds
  // asynchronously after another choice (e.g. Beschrijving appears post-category).
  async function waitForField(labelRe, timeout) {
    const deadline = Date.now() + (timeout || 4000);
    while (Date.now() < deadline) {
      const el = findField(labelRe);
      if (el) return el;
      await sleep(250);
    }
    return null;
  }

  // Has Facebook shown a photo preview thumbnail yet? Picked files render as
  // blob: <img>s — verified live. (We deliberately do NOT look at scontent URLs:
  // FB's own profile/chrome images use those, so they'd give a false positive.)
  async function waitForPhotoPreview(timeout) {
    const deadline = Date.now() + (timeout || 6000);
    while (Date.now() < deadline) {
      const has = [...document.querySelectorAll("img")].some((i) => /^blob:/.test(i.src));
      if (has) return true;
      await sleep(300);
    }
    return false;
  }

  // Click through FB's "Next" → "Publish" and capture the resulting item URL.
  async function publishAndCapture() {
    const clickByText = (re) => {
      const btn = [...document.querySelectorAll('[role="button"], button, [aria-label]')]
        .find((b) => isVisible(b) && re.test(
          (b.textContent || "").trim() + " " + (b.getAttribute("aria-label") || "")
        ));
      if (btn) { btn.click(); return true; }
      return false;
    };

    // FB Marketplace has a "Next"/"Volgende" step before "Publish"/"Publiceren".
    if (clickByText(/^(volgende|next)$/i)) await sleep(1800);
    if (!clickByText(/^(publiceren|publish)$/i)) throw new Error("Publish/Volgende button not found (Facebook layout changed?)");

    // After publishing FB navigates to the new item page: /marketplace/item/{id}.
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      const m = location.href.match(/\/marketplace\/item\/(\d+)/);
      if (m) return { id: m[1], url: `https://www.facebook.com/marketplace/item/${m[1]}` };
      await sleep(500);
    }
    // Couldn't read the id — still count it published (happy path), just without a URL.
    return { id: null, url: null };
  }

  // Best-effort delete: on the item page (or "Your listings"), open the item's
  // menu and choose Delete → Confirm. Beta — layout-dependent.
  async function deleteListingFb(item) {
    await sleep(2500);
    const openMenu = [...document.querySelectorAll('[aria-label], [role="button"]')]
      .find((el) => isVisible(el) && /more|options|menu|acties|meer/i.test(
        (el.getAttribute("aria-label") || "") + (el.textContent || "")
      ));
    if (openMenu) { openMenu.click(); await sleep(800); }

    const del = [...document.querySelectorAll('[role="menuitem"], [role="button"], div, span')]
      .find((el) => isVisible(el) && /^(delete listing|delete|verwijder)/i.test((el.textContent || "").trim()));
    if (!del) throw new Error("Delete control not found on Facebook listing (beta)");
    del.click();
    await sleep(1000);

    const confirm = [...document.querySelectorAll('[role="button"], button')]
      .find((el) => isVisible(el) && /^(delete|confirm|verwijder|ok)/i.test((el.textContent || "").trim()));
    if (confirm) { confirm.click(); await sleep(1200); }
  }

  // ── Job plumbing (identical pattern to the other platform scripts) ──────────
  function getJob() {
    return new Promise((resolve) => {
      let tries = 0;
      const ask = () => {
        chrome.runtime.sendMessage({ type: "GET_JOB" }, (resp) => {
          if (chrome.runtime.lastError) { /* background not ready yet */ }
          if (resp && resp.job) return resolve(resp.job);
          if (++tries < 20) return setTimeout(ask, 150);
          resolve(null);
        });
      };
      ask();
    });
  }
  function send(type, result, errorMsg) {
    chrome.runtime.sendMessage({ type, platform: PLATFORM, jobId, serverUrl, result, error: errorMsg });
  }
})();
