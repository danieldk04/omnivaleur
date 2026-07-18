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
  // Facebook Marketplace condition values (as shown in the "Condition" dropdown).
  const CONDITION_MAP = {
    new_with_tags: "New",
    new: "New",
    good: "Used – good",
    fair: "Used – fair",
    poor: "Used – fair",
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
      const aria = (el.getAttribute("aria-label") || "") + " " + (el.getAttribute("placeholder") || "");
      if (labelRe.test(aria)) return true;
      // Fallback: a labelling element sitting just above the control.
      const labelledby = el.getAttribute("aria-labelledby");
      if (labelledby) {
        const lbl = document.getElementById(labelledby);
        if (lbl && labelRe.test(lbl.textContent || "")) return true;
      }
      return false;
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

  // Open a FB dropdown/combobox identified by its label, then pick the option
  // whose text best matches `wanted`. Used for Category and Condition.
  async function selectCombo(labelRe, wanted) {
    if (!wanted) return false;
    const trigger = [...document.querySelectorAll('[role="combobox"], [role="button"], label, div[aria-haspopup="listbox"]')]
      .find((el) => isVisible(el) && labelRe.test(
        (el.getAttribute("aria-label") || "") + " " + (el.textContent || "").slice(0, 60)
      ));
    if (!trigger) return false;
    trigger.click();
    await sleep(600);
    // Options render into a popup listbox.
    const deadline = Date.now() + 4000;
    let opt = null;
    const want = wanted.toLowerCase();
    while (Date.now() < deadline && !opt) {
      const opts = [...document.querySelectorAll('[role="option"], [role="menuitem"], li')]
        .filter(isVisible);
      // Exact-ish match first, then a looser "starts with the first word" match.
      opt = opts.find((o) => (o.textContent || "").trim().toLowerCase() === want)
         || opts.find((o) => (o.textContent || "").trim().toLowerCase().includes(want))
         || opts.find((o) => (o.textContent || "").trim().toLowerCase().startsWith(want.split(" ")[0]));
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

    await typeInto(findField(/title/i), smartTrunc(item.title || "", 100));
    await typeInto(findField(/price/i), String(item.price || ""));

    // Category is required on Marketplace — type the item's category so FB's
    // picker surfaces a matching option, then pick the closest one.
    await selectCombo(/categor/i, item.category || "");
    await selectCombo(/condition/i, CONDITION_MAP[item.condition] || "Used – good");

    await typeInto(findField(/description|details/i), item.description || "");
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

    // FB Marketplace has a "Next" step before "Publish" on some layouts.
    if (clickByText(/^next$/i)) await sleep(1500);
    if (!clickByText(/^publish$/i)) throw new Error("Publish button not found (Facebook layout changed?)");

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
