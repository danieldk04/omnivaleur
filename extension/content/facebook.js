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
    await sleep(700);

    // If a search box appeared (category), type the first candidate to filter.
    const search = [...document.querySelectorAll('input[type="text"], input[type="search"], [role="combobox"] input')]
      .find((el) => isVisible(el) && el !== trigger && document.activeElement === el);
    if (search) { await typeInto(search, candidates[0]); await sleep(700); }

    const deadline = Date.now() + 4000;
    let opt = null;
    while (Date.now() < deadline && !opt) {
      const opts = [...document.querySelectorAll('[role="option"], [role="menuitem"], [role="menuitemradio"], li')]
        .filter(isVisible)
        .map((o) => ({ o, t: (o.textContent || "").trim().toLowerCase() }))
        .filter((x) => x.t);
      for (const w of wants) {
        opt = (opts.find((x) => x.t === w)               // exact match wins
            || opts.find((x) => x.t.includes(w)))?.o;     // then substring
        if (opt) break;
      }
      if (!opt) await sleep(250);
    }
    if (!opt) return false;
    opt.click();
    await sleep(400);
    return true;
  }

  async function fillForm(item) {
    // Photos first — FB's create form opens straight on the photo step.
    await waitForEl('input[type="file"]', 20000);
    if (item.photo_urls?.length) await uploadPhotos(item.photo_urls.slice(0, 20));
    await sleep(800);

    // FB localises the whole form (verified NL: "Titel"/"Prijs"/"Categorie"/
    // "Staat"), so every label match accepts both the Dutch and English term.
    await typeInto(findField(/^(titel|title)$/i), smartTrunc(item.title || "", 100));
    await typeInto(findField(/^(prijs|price)$/i), String(item.price || ""));

    // Category is required on Marketplace — type the item's category so FB's
    // picker surfaces a matching option, then pick the closest one.
    await selectCombo(/categorie|category/i, [item.category]);
    await selectCombo(/staat|conditie|condition/i, CONDITION_MAP[item.condition] || CONDITION_MAP.good);

    // Description ("Beschrijving") is optional and sometimes behind a details
    // expander — fill it if present, skip otherwise (happy path).
    const desc = findField(/beschrijving|description|details/i);
    if (desc) await typeInto(desc, item.description || "");
    await sleep(400);
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
