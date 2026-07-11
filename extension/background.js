const POLL_INTERVAL_SECONDS = 15;

// Platforms this extension handles (API platforms like eBay/Etsy are server-side)
const EXTENSION_PLATFORMS = ["marktplaats", "2dehands", "vinted"];

// Marktplaats category map: item.category → {cat1, cat3, bucketId}
// cat1=621 = Dames Kleding, cat1=385 = Heren Kleding
// Verified Marktplaats SYI category IDs (from actual URLs)
// Dames: cat1=621, bucketId=162 | Heren: cat1=1776, bucketId=169
const MP_CATEGORIES = {
  // === DAMES (verified) ===
  "jeans":                  { cat1: 621,  cat3: 636,  bucketId: 162 },
  "spijkerbroeken":         { cat1: 621,  cat3: 636,  bucketId: 162 },
  "truien / vesten":        { cat1: 621,  cat3: 640,  bucketId: 162 },
  "truien":                 { cat1: 621,  cat3: 640,  bucketId: 162 },
  "vesten":                 { cat1: 621,  cat3: 640,  bucketId: 162 },
  "blouses":                { cat1: 621,  cat3: 628,  bucketId: 162 },
  "blouses en tunieken":    { cat1: 621,  cat3: 628,  bucketId: 162 },
  "jurken":                 { cat1: 621,  cat3: 631,  bucketId: 162 },
  "jassen":                 { cat1: 621,  cat3: 2784, bucketId: 162 },
  "jassen | winter":        { cat1: 621,  cat3: 2784, bucketId: 162 },
  // Dames — fallback to Blouses for tops/polo/shirts
  "t-shirts":               { cat1: 621,  cat3: 628,  bucketId: 162 },
  "tops":                   { cat1: 621,  cat3: 628,  bucketId: 162 },
  "polo's":                 { cat1: 621,  cat3: 628,  bucketId: 162 },
  "polo":                   { cat1: 621,  cat3: 628,  bucketId: 162 },
  // Dames — fallback to Jeans for broeken/rokken
  "rokken":                 { cat1: 621,  cat3: 636,  bucketId: 162 },
  "broeken":                { cat1: 621,  cat3: 636,  bucketId: 162 },
  "shorts":                 { cat1: 621,  cat3: 636,  bucketId: 162 },
  "leggings":               { cat1: 621,  cat3: 636,  bucketId: 162 },
  // Dames — fallback to Jassen for sportkleding/overige
  "sportkleding":           { cat1: 621,  cat3: 2784, bucketId: 162 },
  "ondergoed":              { cat1: 621,  cat3: 631,  bucketId: 162 },
  "badkleding":             { cat1: 621,  cat3: 631,  bucketId: 162 },
  // Dames schoenen (verified)
  "schoenen dames":         { cat1: 621,  cat3: 625,  bucketId: 164 },
  "schoenen":               { cat1: 621,  cat3: 625,  bucketId: 164 },

  // === HEREN (verified) ===
  "heren jeans":            { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren spijkerbroeken":   { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren truien / vesten":  { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren truien":           { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren vesten":           { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren jassen":           { cat1: 1776, cat3: 2788, bucketId: 169 },
  "heren jassen | winter":  { cat1: 1776, cat3: 2788, bucketId: 169 },
  // Heren — fallback to Truien for tops/polo/shirts
  "heren t-shirts / polo":  { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren t-shirts":         { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren polo's":           { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren polo":             { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren overhemden":       { cat1: 1776, cat3: 652,  bucketId: 169 },
  // Heren — fallback to Jeans for broeken/shorts
  "heren broeken":          { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren shorts":           { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren pakken":           { cat1: 1776, cat3: 2788, bucketId: 169 },
  "heren sportkleding":     { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren ondergoed":        { cat1: 1776, cat3: 1497, bucketId: 169 },
  // Heren schoenen (verified)
  "heren schoenen":         { cat1: 1776, cat3: 642,  bucketId: 171 },

  // === NIEUWE DAMES categorieën ===
  "broeken":                { cat1: 621,  cat3: 636,  bucketId: 162 },
  "shorts":                 { cat1: 621,  cat3: 636,  bucketId: 162 },
  "rokken":                 { cat1: 621,  cat3: 636,  bucketId: 162 },
  "jurken casual":          { cat1: 621,  cat3: 631,  bucketId: 162 },
  "jurken feest":           { cat1: 621,  cat3: 631,  bucketId: 162 },
  "tops":                   { cat1: 621,  cat3: 628,  bucketId: 162 },
  "truien":                 { cat1: 621,  cat3: 640,  bucketId: 162 },
  "hoodies":                { cat1: 621,  cat3: 640,  bucketId: 162 },
  "jassen":                 { cat1: 621,  cat3: 2784, bucketId: 162 },
  "sport bh":               { cat1: 621,  cat3: 2784, bucketId: 162 },
  "sportleggings":          { cat1: 621,  cat3: 636,  bucketId: 162 },
  "sportbroeken":           { cat1: 621,  cat3: 2784, bucketId: 162 },
  "sportjassen":            { cat1: 621,  cat3: 2784, bucketId: 162 },
  "yoga kleding":           { cat1: 621,  cat3: 2784, bucketId: 162 },
  "hardloopkleding":        { cat1: 621,  cat3: 2784, bucketId: 162 },
  "gymkleding":             { cat1: 621,  cat3: 2784, bucketId: 162 },
  "zwemkleding":            { cat1: 621,  cat3: 631,  bucketId: 162 },
  "ondergoed":              { cat1: 621,  cat3: 631,  bucketId: 162 },
  "sneakers dames":         { cat1: 621,  cat3: 625,  bucketId: 164 },
  "hakken":                 { cat1: 621,  cat3: 625,  bucketId: 164 },
  "laarzen dames":          { cat1: 621,  cat3: 625,  bucketId: 164 },
  "sandalen":               { cat1: 621,  cat3: 625,  bucketId: 164 },
  "accessoires dames":      { cat1: 621,  cat3: 628,  bucketId: 162 },

  // === NIEUWE HEREN categorieën ===
  "heren chinos":           { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren t-shirts":         { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren hoodies":          { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren sport tops":       { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren sportbroeken":     { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren sportjassen":      { cat1: 1776, cat3: 2788, bucketId: 169 },
  "heren hardloopkleding":  { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren gymkleding":       { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren voetbalkleding":   { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren wielrenkleding":   { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren zwembroeken":      { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren ondergoed":        { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren sneakers":         { cat1: 1776, cat3: 642,  bucketId: 171 },
  "heren formele schoenen": { cat1: 1776, cat3: 642,  bucketId: 171 },
  "heren laarzen":          { cat1: 1776, cat3: 642,  bucketId: 171 },
  "heren accessoires":      { cat1: 1776, cat3: 652,  bucketId: 169 },

  // === KINDEREN (cat1=428 = Kinderkleding, bucketId=127) ===
  "babykleding":            { cat1: 428,  cat3: 429,  bucketId: 127 },
  "peuterkleding":          { cat1: 428,  cat3: 429,  bucketId: 127 },
  "jongens kleding":        { cat1: 428,  cat3: 430,  bucketId: 127 },
  "meisjes kleding":        { cat1: 428,  cat3: 431,  bucketId: 127 },
  "tieners jongens":        { cat1: 428,  cat3: 430,  bucketId: 127 },
  "tieners meisjes":        { cat1: 428,  cat3: 431,  bucketId: 127 },
  "kinderen sportkleding":  { cat1: 428,  cat3: 429,  bucketId: 127 },
  "kinderen schoenen":      { cat1: 428,  cat3: 432,  bucketId: 127 },
  "kinderen accessoires":   { cat1: 428,  cat3: 429,  bucketId: 127 },

  // === UNISEX (fallback naar dames) ===
  "unisex truien":          { cat1: 621,  cat3: 640,  bucketId: 162 },
  "unisex jassen":          { cat1: 621,  cat3: 2784, bucketId: 162 },
  "unisex sportkleding":    { cat1: 621,  cat3: 2784, bucketId: 162 },
  "unisex schoenen":        { cat1: 621,  cat3: 625,  bucketId: 164 },
  "unisex accessoires":     { cat1: 621,  cat3: 628,  bucketId: 162 },
};
const MP_DEFAULT = { cat1: 621, cat3: 636, bucketId: 162 }; // fallback: dames jeans

function getDeleteUrl(platform, payload) {
  if (platform === "marktplaats") {
    if (payload?.platform_listing_id) return `https://www.marktplaats.nl/v/listing/${payload.platform_listing_id}`;
    if (payload?.platform_listing_url) return payload.platform_listing_url;
    return "https://www.marktplaats.nl";
  }
  if (platform === "2dehands") {
    if (payload?.platform_listing_id) return `https://www.2dehands.be/v/listing/${payload.platform_listing_id}`;
    if (payload?.platform_listing_url) return payload.platform_listing_url;
    return "https://www.2dehands.be";
  }
  if (platform === "vinted") {
    // A Vinted account lives on ONE country domain (e.g. vinted.nl) and the
    // item + its /api/v2 endpoints only exist on that same origin. Opening
    // vinted.com for a .nl item shows a page but its API 404s — which the
    // delete-verification would misread as "already deleted". So always use
    // the stored listing URL (which carries the real .nl/.be/… origin).
    if (payload?.platform_listing_url) return payload.platform_listing_url;
    return payload?.platform_listing_id
      ? `https://www.vinted.com/items/${payload.platform_listing_id}`
      : null;
  }
  return null;
}

function getEditUrl(platform, payload) {
  // Content-refresh only supported for Vinted today — light in-place edit
  // (price/photo-order nudge) to refresh the listing's "updated" signal.
  // Derive the edit URL from the stored listing URL's real origin (see the
  // domain note in getDeleteUrl) rather than hardcoding vinted.com.
  if (platform === "vinted") {
    if (!payload?.platform_listing_id) return null;
    let origin = "https://www.vinted.com";
    if (payload.platform_listing_url) {
      try { origin = new URL(payload.platform_listing_url).origin; } catch (e) {}
    }
    return `${origin}/items/${payload.platform_listing_id}/edit`;
  }
  return null;
}

function getMpSyiUrl(platform, item) {
  // Vinted has a simple listing flow — no category-based URLs needed.
  // Open the create form on the account's real country domain when known
  // (a relist carries _create_origin recovered from the old listing URL),
  // otherwise fall back to vinted.com. Opening the wrong domain would create
  // the new listing on the wrong catalog.
  if (platform === "vinted") {
    const origin = item?._create_origin || "https://www.vinted.com";
    return `${origin}/items/new`;
  }

  const base = platform === "marktplaats"
    ? "https://www.marktplaats.nl/plaats"
    : "https://www.2dehands.be/plaats";
  const cat = (item?.category || "").toLowerCase().trim();
  // Imported items often have no gender/category saved at all (only title +
  // 1 photo carry over) — item.gender is then empty and this used to silently
  // fall through to MP_DEFAULT (Dames Jeans), regardless of what the item
  // actually is. Recover gender from the title itself before giving up, since
  // that's usually the one field an imported item does have.
  let gender = (item?.gender || "").toLowerCase().trim();
  if (!gender) {
    const t = (item?.title || "").toLowerCase();
    if (/\bheren\b|\bmen'?s\b|\bmannen\b/.test(t)) gender = "heren";
    else if (/\bdames\b|\bwomen'?s\b|\bvrouwen\b/.test(t)) gender = "dames";
  }

  let c;

  // When gender is heren, always try heren-prefixed first so "truien / vesten" + heren → Heren
  if (gender === "heren") {
    c = MP_CATEGORIES[`heren ${cat}`] || MP_CATEGORIES[cat];
    // If matched category is still Dames (cat1=621), override to Heren default
    if (!c || c.cat1 === 621) {
      c = { cat1: 1776, cat3: 652, bucketId: 169 }; // Heren Truien / Vesten
    }
  } else {
    c = MP_CATEGORIES[cat] || MP_DEFAULT;
  }

  return `${base}/${c.cat1}/${c.cat3}?bucketId=${c.bucketId}&title=`;
}

chrome.alarms.create("poll", { periodInMinutes: POLL_INTERVAL_SECONDS / 60 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "poll") pollJobs();
});

// Also poll immediately on install/startup
chrome.runtime.onInstalled.addListener(pollJobs);
chrome.runtime.onStartup.addListener(pollJobs);

async function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ serverUrl: "https://crosslisteu.com" }, (s) => {
      let url = s.serverUrl.replace(/\/$/, "");
      if (url === "https://api.crosslisteu.com") {
        // Stale value from before the domain consolidation — migrate it.
        url = "https://crosslisteu.com";
        chrome.storage.sync.set({ serverUrl: url });
      }
      resolve(url);
    });
  });
}

async function getAuthHeaders() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(["authToken"], (s) => {
      const headers = { "Content-Type": "application/json" };
      if (s.authToken) headers["Authorization"] = `Bearer ${s.authToken}`;
      resolve(headers);
    });
  });
}

// Post a small live-progress update for a running job so the dashboard can show
// the user exactly what's happening. Fire-and-forget: never let a progress ping
// (or its failure) slow down or break the actual scan.
async function reportProgress(serverUrl, jobId, progress) {
  try {
    const headers = await getAuthHeaders();
    await fetch(`${serverUrl}/api/jobs/${jobId}/progress`, {
      method: "POST", headers, body: JSON.stringify(progress),
    });
  } catch (e) { /* progress is best-effort */ }
}

async function pollJobs() {
  const serverUrl = await getServerUrl();
  const headers = await getAuthHeaders();
  for (const platform of EXTENSION_PLATFORMS) {
    try {
      const res = await fetch(`${serverUrl}/api/jobs/pending?platform=${platform}`, { headers });
      if (!res.ok) continue;
      const jobs = await res.json();
      for (const job of jobs) {
        await processJob(job, serverUrl);
      }
    } catch (e) {
      console.error(`ListHub poll error (${platform}):`, e);
    }
  }
}

async function processJob(job, serverUrl) {
  const headers = await getAuthHeaders();
  // Claim job first
  const claimRes = await fetch(`${serverUrl}/api/jobs/${job.id}/claim`, { method: "POST", headers });
  if (!claimRes.ok) return;

  // MP/2dh delete: fully background-driven, no content script needed
  if (job.action === "delete" && (job.platform === "marktplaats" || job.platform === "2dehands")) {
    try {
      await bgDeleteMp2dh(job, serverUrl);
    } catch (e) {
      await reportError(job.id, serverUrl, String(e));
    }
    return;
  }

  // Vinted delete: also background-driven. Vinted redirects the seller away
  // from the item page right after confirming delete, which destroys any
  // content-script mid-verification (leaving the job stuck "claimed" and the
  // paired relist recreate blocked forever). The background worker survives
  // that navigation, so verification + /complete happen reliably here.
  if (job.action === "delete" && job.platform === "vinted") {
    try {
      await bgDeleteVinted(job, serverUrl);
    } catch (e) {
      await reportError(job.id, serverUrl, String(e));
    }
    return;
  }

  // Scan: read the user's own "my listings" page, report candidates for manual review
  if (job.action === "scan") {
    try {
      if (job.platform === "vinted") await bgScanVinted(job, serverUrl);
      else await bgScanMp2dh(job, serverUrl);
    } catch (e) {
      await reportError(job.id, serverUrl, String(e));
    }
    return;
  }

  // Store job for content script to pick up
  await chrome.storage.local.set({ [`job_${job.platform}`]: { ...job, serverUrl } });

  const url = job.action === "delete" ? getDeleteUrl(job.platform, job.payload)
    : job.action === "content_refresh" ? getEditUrl(job.platform, job.payload)
    : getMpSyiUrl(job.platform, job.payload);
  if (!url) {
    await reportError(job.id, serverUrl, "No URL configured for " + job.platform + " action=" + job.action);
    return;
  }

  console.log(`[ListHub] Opening tab for ${job.platform} job ${job.id}: ${url}`);
  chrome.tabs.create({ url, active: true }, (tab) => {
    if (chrome.runtime.lastError) {
      reportError(job.id, serverUrl, "tabs.create failed: " + chrome.runtime.lastError.message);
    } else {
      if (job.action === "create") {
        chrome.storage.local.set({ [`jobtab_${tab.id}`]: { jobId: job.id, platform: job.platform, serverUrl } });
      }
    }
  });
}

// ── Background-driven delete for Marktplaats / 2dehands ───────────────────
// Navigates: homepage → clicks "Mijn [platform]" nav link → finds listing by
// title on the overview → clicks options → clicks Verwijder → confirms.
// No content script needed — all via executeScript from background.

function execInTab(tabId, func, args = []) {
  return new Promise((resolve, reject) => {
    chrome.scripting.executeScript(
      { target: { tabId }, world: "MAIN", func, args },
      results => chrome.runtime.lastError
        ? reject(new Error(chrome.runtime.lastError.message))
        : resolve(results?.[0]?.result)
    );
  });
}

function waitForTabLoad(tabId, timeoutMs = 20000) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(fn);
      resolve(); // resolve on timeout so execution continues
    }, timeoutMs);
    function fn(id, info) {
      if (id !== tabId || info.status !== "complete") return;
      chrome.tabs.onUpdated.removeListener(fn);
      clearTimeout(timer);
      resolve();
    }
    chrome.tabs.onUpdated.addListener(fn);
    // Also check if already complete
    chrome.tabs.get(tabId, t => {
      if (t && t.status === "complete") {
        chrome.tabs.onUpdated.removeListener(fn);
        clearTimeout(timer);
        resolve();
      }
    });
  });
}

async function bgDeleteMp2dh(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const platform = job.platform;
  const payload = job.payload || {};
  const title = (payload.title || "").substring(0, 35);
  const listingId = payload.platform_listing_id || "";

  // Navigate directly to the seller's listings overview
  const overviewUrl = platform === "marktplaats"
    ? "https://www.marktplaats.nl/my-account/sell/index.html"
    : "https://www.2dehands.be/my-account/sell/index.html";

  const tabId = await new Promise((res, rej) =>
    chrome.tabs.create({ url: overviewUrl, active: true }, t =>
      chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res(t.id)
    )
  );

  try {
    await waitForTabLoad(tabId);
    await sleep(3000); // let React fully render listings

    // Find listing card by title or ID and click its options button
    const findResult = await execInTab(tabId, (title, listingId) => {
      const allEls = [...document.querySelectorAll("*")];

      // Find element containing the title text (prefer smaller, more specific elements)
      let titleEl = allEls.find(el =>
        el.children.length === 0 && // leaf node
        el.textContent.trim().startsWith(title.substring(0, 20)) &&
        el.textContent.trim().length < title.length + 20
      );
      if (!titleEl && listingId) {
        titleEl = [...document.querySelectorAll(`a[href*="${listingId}"]`)][0];
      }
      if (!titleEl) {
        // Broader: any element whose text contains the first 15 chars of title
        titleEl = allEls.find(el => el.textContent.includes(title.substring(0, 15)) && el.tagName !== "BODY" && el.tagName !== "HTML");
      }
      if (!titleEl) return { found: false };

      // Walk up to find a card-like ancestor
      let card = titleEl;
      for (let i = 0; i < 8; i++) {
        if (!card.parentElement) break;
        card = card.parentElement;
        if (/article|li/i.test(card.tagName) ||
            (card.querySelectorAll("button").length > 0 && card.querySelectorAll("a").length > 0)) {
          break;
        }
      }

      // Find an options/kebab/more button inside the card
      const btns = [...card.querySelectorAll("button")];
      const optBtn = btns.find(b =>
        /opties|meer|menu|\.\.\./i.test(b.textContent + (b.getAttribute("aria-label") || "")) ||
        b.querySelector("svg")
      ) || btns[btns.length - 1]; // last button is often the options button

      if (optBtn) { optBtn.click(); return { found: true, btn: optBtn.textContent || "svg-btn" }; }
      return { found: true, btn: null };
    }, [title, listingId]);

    if (!findResult?.found) {
      throw new Error(`Listing "${title}" not found on ${overviewUrl}. Is the item actually listed on ${platform}?`);
    }

    await sleep(700);

    // Click Verwijder (in dropdown or directly visible)
    const clickedDelete = await execInTab(tabId, () => {
      const el = [...document.querySelectorAll("button, a, [role='menuitem'], li")]
        .find(e => /verwijder/i.test(e.textContent));
      if (el) { el.click(); return true; }
      return false;
    });

    if (!clickedDelete) throw new Error("Verwijder button not found — options menu may not have opened");

    await sleep(800);

    // Confirm dialog if it appears — must actually find and click a confirm
    // button, otherwise we'd mark the job "done" while the listing is still live.
    const clickedConfirm = await execInTab(tabId, () => {
      const btn = [...document.querySelectorAll("button")]
        .find(e => /verwijder|bevestig|ok|ja\b/i.test(e.textContent));
      if (btn) { btn.click(); return true; }
      return false;
    });

    if (!clickedConfirm) throw new Error("Confirm button not found — delete may not have gone through, listing was not verified as removed");

    await sleep(1500);

    // Verify the listing card is actually gone before reporting success —
    // without this check the delete job was marked "done" (and the DB set to
    // "delisted") even when nothing was actually removed on the platform.
    const stillPresent = await execInTab(tabId, (title, listingId) => {
      const allEls = [...document.querySelectorAll("*")];
      let titleEl = allEls.find(el =>
        el.children.length === 0 &&
        el.textContent.trim().startsWith(title.substring(0, 20)) &&
        el.textContent.trim().length < title.length + 20
      );
      if (!titleEl && listingId) {
        titleEl = [...document.querySelectorAll(`a[href*="${listingId}"]`)][0];
      }
      return !!titleEl;
    }, [title, listingId]);

    if (stillPresent) throw new Error(`Listing "${title}" still visible on ${overviewUrl} after confirming delete — removal was not verified`);

    const completeHeaders = await getAuthHeaders();
    await fetch(`${serverUrl}/api/jobs/${job.id}/complete`, {
      method: "POST", headers: completeHeaders,
      body: JSON.stringify({}),
    });
    console.log(`[ListHub] bgDelete success: ${platform} listing "${title}"`);

  } finally {
    setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2500);
  }
}

// ── Background-driven delete for Vinted ───────────────────────────────────
// Opens the listing on its real country origin, verifies it's in the user's
// wardrobe (ground truth), clicks Delete + confirm, then verifies it's gone
// from the wardrobe — all from the background worker so Vinted's post-delete
// redirect can't kill the flow mid-verification.
async function bgDeleteVinted(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const payload = job.payload || {};
  const listingId = payload.platform_listing_id;
  if (!listingId) throw new Error("Vinted delete: no platform_listing_id in payload");
  const url = payload.platform_listing_url || `https://www.vinted.com/items/${listingId}`;

  const tabId = await new Promise((res, rej) =>
    chrome.tabs.create({ url, active: true }, t =>
      chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res(t.id)
    )
  );

  try {
    await waitForTabLoad(tabId);
    await sleep(2500);

    // 1) Ground truth BEFORE: find member id and confirm the item is live in
    //    the user's own wardrobe on this origin.
    const before = await execInTab(tabId, async (lid) => {
      async function findUserId() {
        let id = null;
        for (const a of document.querySelectorAll('a[href*="/member/"]')) {
          const m = (a.getAttribute("href") || "").match(/\/member\/(\d+)/);
          if (m) { id = m[1]; break; }
        }
        if (id) return id;
        document.querySelector('#user-menu-button, [data-testid="user-menu-button"]')?.click();
        await new Promise(r => setTimeout(r, 600));
        for (const a of document.querySelectorAll('a[href*="/member/"]')) {
          const m = (a.getAttribute("href") || "").match(/\/member\/(\d+)/);
          if (m) { id = m[1]; break; }
        }
        return id;
      }
      const userId = await findUserId();
      if (!userId) return { userId: null };
      try {
        const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=1&per_page=200`, { headers: { Accept: "application/json" } });
        if (!res.ok) return { userId, present: null };
        const data = await res.json();
        if (data.code && data.code !== 0) return { userId, present: null };
        return { userId, present: (data.items || []).some(it => String(it.id) === String(lid)) };
      } catch (e) { return { userId, present: null }; }
    }, [listingId]);

    if (!before?.userId) throw new Error(`Could not determine your Vinted member id on the item page — make sure you're logged into this Vinted account.`);
    if (before.present === null) throw new Error(`Could not read your Vinted wardrobe to verify item ${listingId} — aborting to avoid an unverified delete.`);
    if (before.present === false) throw new Error(`Vinted item ${listingId} is not in your wardrobe — it may already be gone or belong to a different account; nothing to delete.`);

    // 1b) Snapshot the FULL live listing BEFORE deleting. Imported items carry
    //     almost no data in the dashboard, so we recover everything (all photos,
    //     description, brand, size, condition, colour, material, category) from
    //     Vinted itself and feed it into the paired recreate job. Combine the
    //     wardrobe item object (photos, brand, size, catalog) with DOM scraping
    //     (description, attribute rows, category breadcrumb) — best-effort per
    //     field. If this is a relist, complete_job merges it into the create job.
    const snapshot = await execInTab(tabId, async (userId, lid) => {
      const out = { photo_urls: [], description: "", brand: "", size: "", condition: "", color: "", material: "", category: "", gender: "", price: null, _raw: null };
      // Wardrobe object for this item — the ONLY reliable structured source.
      // Whole-page DOM scraping is avoided for brand/size/description because
      // the item page also renders "Member's items" and a stats line, which
      // produced junk ("Menu", "17 views 0 favourites") in the first attempt.
      let it = null;
      try {
        const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=1&per_page=200`, { headers: { Accept: "application/json" } });
        if (res.ok) {
          const data = await res.json();
          it = (data.items || []).find(x => String(x.id) === String(lid)) || null;
        }
      } catch (e) {}
      if (it) {
        // Keep the raw object (trimmed) so we can map any field names precisely.
        try {
          const clone = JSON.parse(JSON.stringify(it));
          if (clone.photos) clone.photos = `[${clone.photos.length} photos]`;
          out._raw = clone;
        } catch (e) {}
        const photos = (it.photos || []).map(p => p.full_size_url || p.url).filter(Boolean);
        if (photos.length) out.photo_urls = photos;
        else if (it.photo?.url) out.photo_urls = [it.photo.url];
        out.brand = it.brand_title || it.brand_dto?.title || it.brand || "";
        out.size = it.size_title || it.size || "";
        out.condition = it.status || it.status_title || "";
        out.description = it.description || "";
        const pr = it.price?.amount ?? it.price ?? it.total_item_price?.amount;
        if (pr != null && !isNaN(Number(pr))) out.price = Number(pr);
        // Colours: Vinted returns color names on the wardrobe object under
        // varying keys.
        out.color = it.color1 || it.color1_title || it.colour || "";
      }
      // Description: if the wardrobe object didn't carry it, scrape the DOM but
      // reject the stats line / anything that isn't a real description.
      if (!out.description) {
        const cand = document.querySelector('[itemprop="description"]')
          || [...document.querySelectorAll('div, p, span')].find(el =>
              el.children.length === 0 &&
              el.textContent.trim().length > 25 &&
              !/views|favourites|favorieten|weergaven|€|\bcm\b/i.test(el.textContent));
        if (cand && cand.textContent.trim()) out.description = cand.textContent.trim().slice(0, 1000);
      }
      // Colour + material: the wardrobe object often omits these, but scraping
      // the item's OWN attribute rows worked. Scope to the details container
      // that holds "Condition"/"Material" so we never pick up "Member's items".
      const scopeRow = (labels) => {
        // Find the attribute table/list: the ancestor that contains a leaf
        // element whose text is exactly "Material" or "Condition".
        let container = null;
        for (const el of document.querySelectorAll('*')) {
          if (el.children.length === 0 && /^(material|condition|colour|color)$/i.test(el.textContent.trim())) {
            container = el.closest('dl, ul, table, [class*="Details" i], [data-testid*="attributes" i]') || el.parentElement?.parentElement;
            if (container) break;
          }
        }
        const root = container || document;
        for (const lab of labels) {
          for (const el of root.querySelectorAll('*')) {
            if (el.children.length === 0 && new RegExp("^\\s*" + lab + "\\s*$", "i").test(el.textContent)) {
              const sib = el.nextElementSibling || el.parentElement?.nextElementSibling;
              const v = (sib?.textContent || "").trim();
              if (v && v.length < 40 && !/^(menu|home|catalog)$/i.test(v)) return v;
            }
          }
        }
        return "";
      };
      // Broader row scrape (the original approach that reliably found Grey/Wool)
      // — used only as a fallback for colour/material, which are single-word
      // values easy to sanity-check, so junk like "Menu" is filtered out.
      const rowValue = (labels) => {
        const rows = [...document.querySelectorAll('[data-testid*="item-attributes"] *, dl div, div[class*="Cell"], li, tr')];
        for (const lab of labels) {
          const re = new RegExp("^\\s*" + lab + "\\s*[:\\-]?\\s*(.+)$", "i");
          for (const el of rows) {
            const m = (el.textContent || "").trim().match(re);
            const v = m && m[1] ? m[1].trim() : "";
            if (v && v.length < 30 && !/menu|home|catalog|view|favourite|€|\d{2,}|\bcm\b/i.test(v)) return v;
          }
        }
        return "";
      };
      if (!out.color) out.color = scopeRow(["Colour", "Color", "Kleur"]) || rowValue(["Colour", "Color", "Kleur"]);
      out.material = scopeRow(["Material", "Materiaal"]) || rowValue(["Material", "Materiaal"]);
      // Category + gender from the breadcrumb (e.g. Women / Clothing / Jumpers & sweaters / ...).
      const crumbs = [...document.querySelectorAll('nav a, [class*="breadcrumb" i] a, [data-testid*="breadcrumb"] a')]
        .map(a => a.textContent.trim()).filter(Boolean);
      if (crumbs.length) {
        const g = crumbs[0].toLowerCase();
        if (/women|dames/.test(g)) out.gender = "dames";
        else if (/men|heren/.test(g)) out.gender = "heren";
        // The most specific meaningful crumb (skip Home/Catalog and the item title itself).
        const meaningful = crumbs.filter(c => !/^(home|catalog|vinted)$/i.test(c));
        if (meaningful.length >= 2) out.category = meaningful[meaningful.length - 1];
      }
      return out;
    }, [before.userId, listingId]);

    // 2) Click Delete, then confirm. "Confirm and delete" is multi-word, so
    //    match on containing confirm/delete and never the Cancel button.
    const clicked = await execInTab(tabId, async () => {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      // Direct visible Delete button/link, else open a kebab/actions dropdown.
      let del = [...document.querySelectorAll('button, a, [role="menuitem"], [role="button"]')]
        .find(e => e.offsetParent !== null && (/^\s*delete\s*$/i.test(e.textContent) || e.dataset.testid?.includes("delete")));
      if (!del) {
        const actions = document.querySelector(
          '[data-testid="item-actions-button"], [data-testid="item-menu-button"], ' +
          '[data-testid="item-page-actions-dropdown-button"], [data-testid*="kebab"], ' +
          'button[aria-label*="more" i], button[aria-label*="actions" i], button[aria-label*="options" i]'
        );
        if (actions) {
          actions.click();
          await sleep(600);
          const menu = document.querySelector('[role="menu"], [role="listbox"], [data-testid*="dropdown"], [data-testid*="modal"]') || document;
          del = [...menu.querySelectorAll('button, a, [role="menuitem"]')]
            .find(e => /^\s*delete\s*$/i.test(e.textContent) || e.dataset.testid?.includes("delete"))
            || [...document.querySelectorAll('button, a, [role="menuitem"], [data-testid*="delete"]')]
              .find(e => /delete/i.test(e.textContent) || e.dataset.testid?.includes("delete"));
        }
      }
      if (!del) return { clickedDelete: false };
      del.click();
      await sleep(900);
      const scope = document.querySelector('[role="dialog"], [role="alertdialog"], [data-testid*="modal"], .ReactModal__Content') || document;
      const confirm = [...scope.querySelectorAll('button, a[role="button"]')]
        .find(el => {
          const t = el.textContent.trim();
          if (/annuleer|cancel|terug|back/i.test(t)) return false;
          return /confirm|delete|verwijder|remove|\byes\b|\bja\b/i.test(t) || el.dataset.testid?.includes("delete");
        });
      if (!confirm) return { clickedDelete: true, clickedConfirm: false };
      confirm.click();
      return { clickedDelete: true, clickedConfirm: true };
    });

    if (!clicked?.clickedDelete) throw new Error(`Delete control not found on Vinted item page for ID ${listingId} — Vinted may have changed its layout.`);
    if (!clicked.clickedConfirm) throw new Error(`Confirm-delete button not found on Vinted for ID ${listingId} — deletion was not confirmed.`);

    // 3) Give Vinted a moment to process + redirect, then verify the item is
    //    gone from the wardrobe. The tab is now on some page of the SAME
    //    origin, so the wardrobe fetch still works. Poll a few times.
    await sleep(2500);
    let goneAfter = false;
    for (let i = 0; i < 5; i++) {
      const present = await execInTab(tabId, async (userId, lid) => {
        try {
          const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=1&per_page=200`, { headers: { Accept: "application/json" } });
          if (!res.ok) return null;
          const data = await res.json();
          if (data.code && data.code !== 0) return null;
          return (data.items || []).some(it => String(it.id) === String(lid));
        } catch (e) { return null; }
      }, [before.userId, listingId]);
      if (present === false) { goneAfter = true; break; }
      await sleep(1800);
    }
    if (!goneAfter) throw new Error(`Vinted listing ${listingId} still in your wardrobe after confirming delete — removal was not verified.`);

    const completeHeaders = await getAuthHeaders();
    await fetch(`${serverUrl}/api/jobs/${job.id}/complete`, {
      method: "POST", headers: completeHeaders,
      // Hand the captured listing snapshot to the backend so it can enrich the
      // paired relist recreate job (imported items otherwise lack this data).
      body: JSON.stringify({ captured_listing: snapshot }),
    });
    console.log(`[ListHub] bgDeleteVinted success: listing ${listingId}`, snapshot);
  } finally {
    setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2500);
  }
}

// ── Scan: read existing listings the user already has on a platform ───────
// Read-only — only reports candidates to /api/imports for manual review,
// never touches items/listings directly.

async function bgScanVinted(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const tabId = await new Promise((res, rej) =>
    chrome.tabs.create({ url: "https://www.vinted.nl/", active: true }, t =>
      chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res(t.id)
    )
  );
  try {
    await reportProgress(serverUrl, job.id, { stage: "opening", message: "Opening Vinted…", current: 0, total: 0 });
    await waitForTabLoad(tabId);
    await sleep(2500);

    await reportProgress(serverUrl, job.id, { stage: "account", message: "Finding your Vinted account…", current: 0, total: 0 });
    // The account/avatar menu only exposes your numeric member id (/member/{id})
    // once its dropdown is opened — nothing on the page reveals it beforehand.
    await execInTab(tabId, () => {
      document.querySelector('#user-menu-button, [data-testid="user-menu-button"]')?.click();
    });
    await sleep(600);

    // Find the numeric member id AND the real country origin (Vinted links to
    // your home country domain, e.g. vinted.nl, even from the .com entry page —
    // the items API only exists on that same origin, not on vinted.com).
    const idInfo = await execInTab(tabId, () => {
      let userId = null, origin = null;
      const links = [...document.querySelectorAll('a[href*="/member/"]')];
      for (const link of links) {
        const href = link.getAttribute("href") || "";
        const m = href.match(/\/member\/(\d+)(?:[/?]|$)/);
        if (m) {
          userId = m[1];
          try { origin = new URL(href, location.href).origin; } catch (e) { origin = location.origin; }
          break;
        }
      }
      return { userId, origin };
    });

    if (!idInfo?.userId) throw new Error("Could not find your logged-in Vinted account (member id) — make sure you're logged into Vinted in this browser tab.");

    // If the member link points at a different country domain, navigate there
    // so the items fetch is same-origin (and actually has the right catalog).
    const currentTab = await new Promise(res => chrome.tabs.get(tabId, res));
    if (idInfo.origin && currentTab?.url && new URL(currentTab.url).origin !== idInfo.origin) {
      await new Promise((res, rej) =>
        chrome.tabs.update(tabId, { url: idInfo.origin + "/" }, () =>
          chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res()
        )
      );
      await waitForTabLoad(tabId);
      await sleep(1500);
    }

    const userId = idInfo.userId;
    await reportProgress(serverUrl, job.id, { stage: "listing", message: "Reading your listings…", current: 0, total: 0 });
    const result = await execInTab(tabId, async (userId) => {
      const nap = ms => new Promise(r => setTimeout(r, ms));
      // Page through the WHOLE wardrobe — one page of 200 is not enough for a
      // seller with a big closet, and stopping at page 1 silently drops the rest.
      // Loop until a page comes back short (fewer than per_page) or empty; a hard
      // page cap only guards against a pathological infinite loop.
      const PER_PAGE = 200;
      const MAX_PAGES = 50; // 10,000 listings — far beyond any real wardrobe
      const rawItems = [];
      for (let page = 1; page <= MAX_PAGES; page++) {
        let res, data;
        // Retry each page a couple of times so one transient hiccup mid-paging
        // doesn't truncate the scan.
        for (let attempt = 0; attempt < 3; attempt++) {
          res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=${PER_PAGE}`, {
            headers: { Accept: "application/json" },
          });
          if (res.ok) break;
          if (res.status !== 429 && res.status < 500) break; // real client error — don't retry
          await nap(1000 * Math.pow(2, attempt));
        }
        if (!res.ok) {
          // First page failing is fatal; a later page failing after we already
          // have items just ends paging with what we collected so far.
          if (page === 1) return { error: `Vinted returned HTTP ${res.status} while listing your items (user id ${userId}, ${location.origin}).` };
          break;
        }
        data = await res.json();
        if (data.code && data.code !== 0) {
          if (page === 1) return { error: `Vinted API error: ${data.message_code || data.code}` };
          break;
        }
        const pageItems = data.items || [];
        rawItems.push(...pageItems);
        if (pageItems.length < PER_PAGE) break; // last page reached
        await nap(300); // gentle pacing between pages
      }

      const items = rawItems.map(it => {
        const priceObj = it.price || it.total_item_price;
        const price = priceObj && priceObj.amount != null ? Number(priceObj.amount)
          : (typeof it.price === "number" ? it.price : null);
        // Full ordered photo list — the whole point of a rich import. Keep the
        // single photo_url too for the old thumbnail path.
        const photoUrls = (it.photos || []).map(p => p.full_size_url || p.url).filter(Boolean);
        const photo = it.photo?.url || photoUrls[0] || null;
        if (!photoUrls.length && photo) photoUrls.push(photo);
        // Vinted returns the original upload time as a unix-seconds timestamp
        // (field name has varied across API versions) — best-effort pick.
        const listedTs = it.created_at_ts || it.photo?.high_resolution?.timestamp || it.photos?.[0]?.high_resolution?.timestamp || null;
        // Everything the wardrobe object carries for free — mirrors the field
        // mapping used by the pre-delete snapshot so imports land fully populated.
        return {
          platform_listing_id: String(it.id),
          title: it.title || "",
          price,
          photo_url: photo,
          photo_urls: photoUrls,
          description: it.description || "",
          brand: it.brand_title || it.brand_dto?.title || it.brand || "",
          size: it.size_title || it.size || "",
          condition: it.status || it.status_title || "",
          color: it.color1 || it.color1_title || it.colour || "",
          platform_listing_url: it.url || `${location.origin}/items/${it.id}`,
          platform_listed_at: listedTs ? new Date(listedTs * 1000).toISOString() : null,
        };
      });
      return { items };
    }, [userId]);

    if (!result) throw new Error("Vinted scan returned nothing — page may not have loaded correctly.");
    if (result.error) throw new Error(result.error);

    // The wardrobe LIST endpoint omits description + colour/material and
    // sometimes the photos array. Fetch each item's detail (same-origin, cheap)
    // to fill those in, so an import lands fully populated.
    //
    // CRITICAL: do this as one short executeScript PER ITEM, driven from the
    // service worker — not a single 50s executeScript. An MV3 service worker
    // that sits idle awaiting one long call gets terminated by Chrome before it
    // returns, which would abort the whole scan (no /complete, no candidates).
    // A quick call every ~200ms keeps the worker alive. The whole enrichment is
    // wrapped so ANY failure just ships the list-only data — the scan always
    // completes.
    const total = result.items.length;
    await reportProgress(serverUrl, job.id, {
      stage: "enriching", message: `Found ${total} listings — fetching full details…`,
      current: 0, total,
    });
    let enriched = 0;
    try {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      const startedAt = Date.now();
      const noDesc = [];
      let idx = 0;
      for (const it of result.items) {
        let d = null;
        try {
          d = await execInTab(tabId, async (id) => {
            const nap = ms => new Promise(r => setTimeout(r, ms));
            const out = { _status: null, _err: null, _tries: 0, description: "", color: "", material: "", brand: "", size: "", condition: "", photo_urls: [] };
            // Try the JSON detail endpoint (same-origin, carries the full
            // description that the wardrobe list omits). We try the DEFAULT
            // (localized) endpoint first — that's exactly what Vinted's item
            // page uses and what the seller sees, so it always carries the
            // visible description. `?localize=false` is only a fallback: for
            // some items it returns a null description, which was the bug.
            const urls = [`/api/v2/items/${id}`, `/api/v2/items/${id}?localize=false`];
            for (const url of urls) {
              // Retry each variant with exponential backoff on rate-limits
              // (429/5xx) or an empty body — throttling is transient.
              for (let attempt = 0; attempt < 3; attempt++) {
                out._tries = (out._tries || 0) + 1;
                try {
                  const res = await fetch(url, {
                    headers: { Accept: "application/json" }, credentials: "include",
                  });
                  out._status = res.status;
                  if (res.ok) {
                    const data = await res.json();
                    const item = data.item || data || {};
                    // Only overwrite fields we don't have yet, so a good value
                    // from the first URL isn't wiped by an empty one from the second.
                    if (!out.description) out.description = item.description || item.description_text || "";
                    if (!out.color) out.color = item.color1 || item.color1_title || item.colour || "";
                    if (!out.material) out.material = item.material || item.material_title || "";
                    if (!out.brand) out.brand = item.brand_title || item.brand_dto?.title || item.brand || "";
                    if (!out.size) out.size = item.size_title || item.size || "";
                    if (!out.condition) out.condition = item.status || item.status_title || "";
                    if (!out.photo_urls.length) out.photo_urls = (item.photos || []).map(p => p.full_size_url || p.url).filter(Boolean);
                    out._err = null;
                    break; // this variant answered; move to next URL only if still no desc
                  } else if (res.status !== 429 && res.status < 500) {
                    break; // a real client error (404/403) won't fix itself
                  }
                  out._err = null;
                } catch (e) { out._err = String(e && e.message || e); }
                if (attempt < 2) {
                  const retryAfter = out._status === 429 ? 1500 : 400;
                  await nap(retryAfter * Math.pow(2, attempt)); // 400/800 or 1500/3000
                }
              }
              if (out.description) break; // got the description — no need for the other variant
            }
            // Fallback: if the API gave us no description, scrape it from the
            // public item page. Vinted renders the description into the page's
            // meta description / embedded JSON, which is reliable even when the
            // JSON API misbehaves. Retry this too — it hits the same limiter.
            if (!out.description) {
              for (let attempt = 0; attempt < 3; attempt++) {
                try {
                  const pageRes = await fetch(`/items/${id}`, { credentials: "include" });
                  out._pageStatus = pageRes.status;
                  if (pageRes.ok) {
                    const html = await pageRes.text();
                    const decode = s => { try { return JSON.parse('"' + s.replace(/"/g, '\\"') + '"'); } catch (e2) { return s; } };
                    // The embedded JSON often contains SEVERAL "description":"…"
                    // fields — the first is frequently an empty SEO/catalog stub.
                    // Collect them all and keep the longest non-empty one, so an
                    // early `"description":""` no longer makes us give up.
                    let best = "";
                    for (const mm of html.matchAll(/"description":"((?:[^"\\]|\\.)*)"/g)) {
                      const val = decode(mm[1]);
                      if (val && val.length > best.length) best = val;
                    }
                    // og:description as a secondary source (usually a shorter
                    // teaser, so only use it if the JSON gave us nothing).
                    if (!best) {
                      const og = html.match(/<meta[^>]+(?:property|name)=["'](?:og:description|description)["'][^>]+content=["']([^"']+)["']/i);
                      if (og && og[1]) best = decode(og[1]);
                    }
                    out._pageDescLen = best.length;
                    if (best) { out.description = best; out._src = "page"; break; }
                    break; // page loaded but genuinely no description text found
                  } else if (pageRes.status !== 429 && pageRes.status < 500) {
                    break;
                  }
                } catch (e) { /* fallback best-effort */ }
                if (attempt < 2) await nap(1000 * Math.pow(2, attempt));
              }
            }
            return out;
          }, [it.platform_listing_id]);
        } catch (e) { d = null; }
        // One-time diagnostic on the first item so we can see exactly what Vinted
        // returned (visible in the service-worker console AND surfaced to the UI).
        if (idx === 0 && d) {
          console.log("[ListHub] detail-debug", { status: d._status, err: d._err, tries: d._tries, descLen: (d.description || "").length, src: d._src || "api" });
          await reportProgress(serverUrl, job.id, {
            stage: "enriching", message: `Found ${total} listings — fetching full details…`,
            current: 0, total,
            debug: `detail HTTP ${d._status ?? "?"}${d._err ? " err:" + d._err : ""} · ${d._tries || 1} tr · desc ${(d.description || "").length} chars (${d._src || "api"})`,
          });
        }
        // Collect a compact record for every item that ended up with no
        // description, so we can see exactly what Vinted returned for the
        // stubborn ones (deterministic failures, not throttling).
        if (d && !d.description) {
          noDesc.push(`${it.platform_listing_id}(api${d._status ?? "?"}/pg${d._pageStatus ?? "-"}${d._pageDescLen != null ? ":" + d._pageDescLen : ""})`);
        }
        if (d) {
          enriched++;
          if (d.description) it.description = d.description;
          if (d.color) it.color = d.color;
          if (d.material) it.material = d.material;
          if (d.brand && !it.brand) it.brand = d.brand;
          if (d.size && !it.size) it.size = d.size;
          if (d.condition && !it.condition) it.condition = d.condition;
          if (d.photo_urls && d.photo_urls.length) {
            it.photo_urls = d.photo_urls;
            it.photo_url = it.photo_url || d.photo_urls[0];
          }
        }
        idx++;
        // Estimate remaining time from the average per-item pace so the user
        // sees a real "~N sec left", updated live as it goes.
        const elapsed = (Date.now() - startedAt) / 1000;
        const perItem = elapsed / idx;
        const etaSeconds = Math.max(0, Math.round(perItem * (total - idx)));
        await reportProgress(serverUrl, job.id, {
          stage: "enriching",
          message: `Fetching details ${idx}/${total}…`,
          current: idx, total, eta_seconds: etaSeconds,
        });
        // Adaptive pacing: if this item came back throttled (429) or empty
        // despite retries, Vinted is rate-limiting us — back off harder for the
        // next item so we don't drag a whole cluster down. Otherwise stay gentle.
        const throttled = d && (d._status === 429 || (!d.description && d._status));
        await sleep(throttled ? 1200 : 200); // keeps the SW warm either way
      }
      // Surface which listings still lack a description and what Vinted returned
      // for them (api<status>/pg<status>:<pageDescLen>) — visible in the panel.
      if (noDesc.length) {
        console.log("[ListHub] no-desc items:", noDesc.join(" "));
        await reportProgress(serverUrl, job.id, {
          stage: "enriching", message: `${enriched}/${total} enriched — ${noDesc.length} without description`,
          current: total, total,
          debug: `no desc (${noDesc.length}): ${noDesc.slice(0, 12).join(" ")}`,
        });
        await sleep(1200); // give the panel a beat to poll this before "saving" overwrites it
      }
    } catch (e) {
      console.warn("[ListHub] Vinted enrichment aborted, sending list data only:", e);
    }

    await reportProgress(serverUrl, job.id, {
      stage: "saving", message: "Saving to your dashboard…", current: total, total,
    });
    const completeHeaders = await getAuthHeaders();
    await fetch(`${serverUrl}/api/jobs/${job.id}/complete`, {
      method: "POST", headers: completeHeaders,
      body: JSON.stringify({ listings: result.items }),
    });
    console.log(`[ListHub] Vinted scan found ${result.items.length} listings (enriched ${enriched})`);
  } finally {
    setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2500);
  }
}

async function bgScanMp2dh(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const platform = job.platform;
  const overviewUrl = platform === "marktplaats"
    ? "https://www.marktplaats.nl/my-account/sell/index.html"
    : "https://www.2dehands.be/my-account/sell/index.html";

  const tabId = await new Promise((res, rej) =>
    chrome.tabs.create({ url: overviewUrl, active: true }, t =>
      chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res(t.id)
    )
  );

  try {
    await waitForTabLoad(tabId);
    await sleep(3000); // let React fully render listings

    const result = await execInTab(tabId, () => {
      const cards = [...document.querySelectorAll("li, article")].filter(el => {
        const link = el.querySelector('a[href*="/v/"]');
        const priceText = el.textContent.match(/€\s?\d/);
        return link && priceText;
      });

      const seen = new Set();
      const items = [];
      for (const card of cards) {
        const link = card.querySelector('a[href*="/v/"]');
        if (!link) continue;
        const href = link.getAttribute("href") || "";
        const idMatch = href.match(/(m\d{6,})/);
        const id = idMatch ? idMatch[1] : href;
        if (!id || seen.has(id)) continue;
        seen.add(id);

        const titleEl = [...card.querySelectorAll("*")].find(el =>
          el.children.length === 0 && el.textContent.trim().length > 5 && el.textContent.trim().length < 120
        );
        const priceMatch = card.textContent.match(/€\s?([\d.,]+)/);
        const img = card.querySelector("img");

        items.push({
          platform_listing_id: id,
          title: (titleEl?.textContent || "").trim(),
          price: priceMatch ? Number(priceMatch[1].replace(/\./g, "").replace(",", ".")) : null,
          photo_url: img?.src || null,
          platform_listing_url: href.startsWith("http") ? href : `https://www.${location.hostname}${href}`,
        });
      }
      return { items };
    });

    if (!result || !result.items) throw new Error("Could not read your listings overview — page structure may have changed.");

    // The overview cards only expose title/price/thumbnail. Enrich each listing
    // by fetching its own page (same-origin) and reading the JSON-LD Product +
    // description block, so the import carries the full description and every
    // photo — not just the first one. Best-effort per listing: any failure just
    // leaves that candidate with the basic card data.
    const urls = result.items.map(it => it.platform_listing_url).slice(0, 100);
    const enrichments = await execInTab(tabId, async (urls) => {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      const out = {};
      for (const url of urls) {
        try {
          const res = await fetch(url, { headers: { Accept: "text/html" } });
          if (!res.ok) continue;
          const html = await res.text();
          const doc = new DOMParser().parseFromString(html, "text/html");
          let description = "", photos = [];
          // JSON-LD Product — the most stable source for description + images.
          for (const s of doc.querySelectorAll('script[type="application/ld+json"]')) {
            try {
              let data = JSON.parse(s.textContent);
              const arr = Array.isArray(data) ? data : (data["@graph"] || [data]);
              const prod = arr.find(x => x && /product/i.test(x["@type"] || ""));
              if (prod) {
                if (prod.description && !description) description = String(prod.description).trim();
                const imgs = prod.image ? (Array.isArray(prod.image) ? prod.image : [prod.image]) : [];
                for (const im of imgs) { const u = typeof im === "string" ? im : im?.url; if (u) photos.push(u); }
              }
            } catch (e) {}
          }
          // DOM fallback for the description if JSON-LD didn't carry it.
          if (!description) {
            const el = doc.querySelector('[data-collapsable="description"], .Description-description, [class*="Description" i]');
            if (el && el.textContent.trim().length > 20) description = el.textContent.trim().slice(0, 4000);
          }
          out[url] = { description: description.slice(0, 4000), photo_urls: [...new Set(photos)] };
        } catch (e) {}
        await sleep(150);
      }
      return out;
    }, [urls]);

    for (const it of result.items) {
      const e = enrichments && enrichments[it.platform_listing_url];
      if (!e) continue;
      if (e.description) it.description = e.description;
      if (e.photo_urls && e.photo_urls.length) {
        it.photo_urls = e.photo_urls;
        it.photo_url = it.photo_url || e.photo_urls[0];
      }
    }

    const completeHeaders = await getAuthHeaders();
    await fetch(`${serverUrl}/api/jobs/${job.id}/complete`, {
      method: "POST", headers: completeHeaders,
      body: JSON.stringify({ listings: result.items }),
    });
    console.log(`[ListHub] ${platform} scan found ${result.items.length} listings (enriched ${Object.keys(enrichments || {}).length})`);
  } finally {
    setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2500);
  }
}

// ── Auto-detect manual publish ─────────────────────────────────────────────
// When the user manually clicks "Plaatsen" after an error, the tab URL changes
// to the listing URL. We detect this and auto-complete the job.
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
  if (!changeInfo.url) return;
  const key = `jobtab_${tabId}`;
  const stored = await chrome.storage.local.get(key);
  const meta = stored[key];
  if (!meta) return;

  const url = changeInfo.url;
  // Vinted listing ids are plain digits (/items/9331465721), so the m-prefixed
  // Marktplaats/2dehands patterns never match them. Without a Vinted-specific
  // pattern the create job stays stuck "claimed" after publish, because Vinted's
  // post-Upload navigation tears down the content script before it can send
  // JOB_DONE. Match /items/{digits} for Vinted (never /items/new).
  let m;
  if (meta.platform === "vinted") {
    m = url.match(/\/items\/(\d+)(?:[-/?#]|$)/);
  } else {
    m = url.match(/\/seller\/view\/(m\d+)/) ||
         url.match(/\/v\/[^/]+\/(m\d+)/) ||
         url.match(/[?&](m\d{6,})/) ||
         url.match(/(m\d{8,})/);
  }
  if (!m) return;

  const listingId = m[1];
  console.log(`[ListHub] Auto-detected listing after publish: ${listingId} (${meta.platform})`);

  // Clear stored job
  chrome.storage.local.remove([key, `job_${meta.platform}`]);

  const listingUrl = meta.platform === "marktplaats"
    ? `https://www.marktplaats.nl/v/listing/${listingId}`
    : meta.platform === "2dehands"
    ? `https://www.2dehands.be/v/listing/${listingId}`
    : meta.platform === "vinted"
    ? `${new URL(url).origin}/items/${listingId}`
    : null;

  const completeHeaders = await getAuthHeaders();
  await fetch(`${meta.serverUrl}/api/jobs/${meta.jobId}/complete`, {
    method: "POST",
    headers: completeHeaders,
    body: JSON.stringify({ platform_listing_id: listingId, platform_listing_url: listingUrl }),
  });

  setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2000);
});

// ── Autonomous sold detection + cross-platform delist ─────────────────────
// Every poll cycle also checks for sold items and triggers auto-delist.
chrome.alarms.create("sold-check", { periodInMinutes: 10 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "sold-check") checkSoldListings();
});

async function checkSoldListings() {
  const serverUrl = await getServerUrl();
  const soldUrls = {
    marktplaats: "https://www.marktplaats.nl/mijn-marktplaats/advertenties",
    "2dehands":  "https://www.2dehands.be/mijn-2dehands/advertenties",
  };

  for (const [platform, soldUrl] of Object.entries(soldUrls)) {
    try {
      // Fetch active listings for this platform from backend
      const authHeaders = await getAuthHeaders();
      const resp = await fetch(`${serverUrl}/api/listings/?platform=${platform}&status=active`, { headers: authHeaders }).catch(() => null);
      if (!resp?.ok) continue;
      const allListings = await resp.json();
      const active = allListings.filter(l => l.platform === platform && l.status === "active" && l.platform_listing_id);
      if (!active.length) continue;

      // Open a background tab to the sold page and scrape it
      const soldIds = await scrapeSoldListings(soldUrl, platform);
      if (!soldIds.length) continue;

      for (const listing of active) {
        if (soldIds.includes(listing.platform_listing_id)) {
          console.log(`[ListHub] Sold detected: ${listing.platform_listing_id} on ${platform}, triggering delist`);
          await fetch(`${serverUrl}/api/listings/sold?item_id=${listing.item_id}&platform=${platform}`, {
            method: "POST",
            headers: authHeaders,
          }).catch(e => console.error("[ListHub] sold trigger failed:", e));
        }
      }
    } catch (e) {
      console.error(`[ListHub] sold-check error (${platform}):`, e);
    }
  }
}

function scrapeSoldListings(url, platform) {
  return new Promise((resolve) => {
    chrome.tabs.create({ url, active: false }, (tab) => {
      if (chrome.runtime.lastError) { resolve([]); return; }
      const tabId = tab.id;

      const onUpdated = (id, info) => {
        if (id !== tabId || info.status !== "complete") return;
        chrome.tabs.onUpdated.removeListener(onUpdated);

        chrome.scripting.executeScript({
          target: { tabId },
          world: "MAIN",
          func: () => {
            // Scrape listing IDs from the sold listings page
            const ids = [];
            document.querySelectorAll('a[href]').forEach(a => {
              const m = a.href.match(/\/(m\d{6,})/);
              if (m) ids.push(m[1]);
            });
            return [...new Set(ids)];
          },
        }, (results) => {
          chrome.tabs.remove(tabId).catch(() => {});
          const ids = results?.[0]?.result || [];
          console.log(`[ListHub] Sold listings scraped from ${platform}:`, ids);
          resolve(ids);
        });
      };

      chrome.tabs.onUpdated.addListener(onUpdated);
      // Timeout fallback
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(onUpdated);
        chrome.tabs.remove(tabId).catch(() => {});
        resolve([]);
      }, 30000);
    });
  });
}

// ---- Main-world helpers (injected via chrome.scripting, bypasses page CSP) ----

async function _mwFillDescription(selector, descText) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const el = document.querySelector(selector);
  if (!el) return false;

  el.scrollIntoView({ block: "center" });
  el.focus();
  await sleep(150);

  // Verify via Lexical EditorState, not DOM textContent.
  // DOM can have stale content from earlier fills; EditorState is what validation reads.
  function lexHasText() {
    const lex = el.__lexicalEditor;
    if (!lex) return el.textContent.trim().length > 0;
    try {
      for (const [, node] of (lex._editorState?._nodeMap || new Map())) {
        if (typeof node.__text === "string" && node.__text.trim().length > 0) return true;
      }
      return false;
    } catch (_) {
      return el.textContent.trim().length > 0;
    }
  }

  // ── Approach 1: execCommand (most reliable) ───────────────────────────────
  // execCommand fires a REAL native beforeinput event that Chrome and Lexical
  // both handle natively. InputEvent.dataTransfer is always null for synthetic
  // events in Chrome — execCommand bypasses that problem entirely.
  try {
    el.focus();
    document.execCommand("selectAll", false, null);
    document.execCommand("insertText", false, descText);
    await sleep(300);
    if (lexHasText()) return true;
  } catch (_) {}

  // ── Approach 2: Lexical internal update API ───────────────────────────────
  // Directly writes into EditorState using Lexical's own update() mechanism.
  const lex = el.__lexicalEditor;
  if (lex && typeof lex.update === "function") {
    const PClass = lex._nodes?.get("paragraph")?.klass;
    const TClass = lex._nodes?.get("text")?.klass;
    if (PClass && TClass) {
      try {
        await new Promise((resolve) => {
          lex.update(() => {
            const root = lex._editorState?._nodeMap?.get("root");
            if (!root) return;
            // Clear existing content
            let c = root.getFirstChild?.();
            while (c) { const n = c.getNextSibling?.(); try { c.remove?.(); } catch (_) {} c = n; }
            for (const line of descText.split("\n")) {
              const p = new PClass();
              if (line.length > 0) p.append(new TClass(line));
              root.append(p);
            }
          }, { discrete: true, onUpdate: resolve });
          setTimeout(resolve, 600);
        });
        await sleep(200);
        if (lexHasText()) return true;
      } catch (_) {}
    }
  }

  // ── Approach 3: line-by-line insertText beforeinput ──────────────────────
  // Synthetic InputEvent with insertText — Lexical handles this type correctly
  // because 'data' is a plain string property (unlike dataTransfer which Chrome
  // always nulls out on synthetic events).
  try {
    el.focus();
    document.execCommand("selectAll", false, null);
    el.dispatchEvent(new InputEvent("beforeinput", {
      inputType: "deleteContentBackward", bubbles: true, cancelable: true,
    }));
    await sleep(80);
    for (const [i, line] of descText.split("\n").entries()) {
      if (i > 0) {
        el.dispatchEvent(new InputEvent("beforeinput", {
          inputType: "insertParagraph", bubbles: true, cancelable: true,
        }));
        await sleep(15);
      }
      if (line.length > 0) {
        el.dispatchEvent(new InputEvent("beforeinput", {
          inputType: "insertText", data: line, bubbles: true, cancelable: true,
        }));
        await sleep(15);
      }
    }
    await sleep(300);
    if (lexHasText()) return true;
  } catch (_) {}

  // ── Approach 4: ClipboardEvent paste ─────────────────────────────────────
  try {
    const dt = new DataTransfer();
    dt.setData("text/plain", descText);
    el.focus();
    document.execCommand("selectAll", false, null);
    el.dispatchEvent(new ClipboardEvent("paste", {
      clipboardData: dt, bubbles: true, cancelable: true,
    }));
    await sleep(400);
    if (lexHasText()) return true;
  } catch (_) {}

  return false;
}

async function _mwFillBrand(brand) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const brandLower = brand.toLowerCase().trim();

  // The "Merk" field is an input that does NOT accept typed text (React resets its
  // value to ""). Clicking it opens a ReactModal containing brand "pills"
  // (button.hz-Pill). The value is only committed by clicking a pill — that's why
  // typing + dispatching events never worked. Verified live on marktplaats.nl.
  const trigger =
    document.querySelector('input[data-testid^="attribute-autocomplete-"]') ||
    document.querySelector('input[name^="textAttribute[brand"]') ||
    document.querySelector('input[name="textAttribute[clothingBrand]"]');
  if (!trigger) return false;

  // Idempotent: if the brand is already selected, do NOT reopen the picker.
  // Clicking the already-selected pill toggles it OFF (verified live), which is
  // exactly what wiped the brand when submitListing re-applied it before submit.
  const current = (trigger.value || "").trim().toLowerCase();
  if (current && (current === brandLower || current.includes(brandLower) || brandLower.includes(current))) {
    return true;
  }

  const getModal = () =>
    document.querySelector(".ReactModal__Content") ||
    document.querySelector('[role="dialog"]');

  // Open the brand modal (retry once if it doesn't appear)
  trigger.scrollIntoView({ block: "center" });
  trigger.focus();
  trigger.click();
  await sleep(700);
  let modal = getModal();
  if (!modal) { trigger.click(); await sleep(700); modal = getModal(); }
  if (!modal) return false;

  const findPill = (root) => {
    const items = [...root.querySelectorAll('button, [role="option"], li')]
      .filter((e) => e.offsetParent !== null && e.textContent.trim());
    return (
      items.find((e) => e.textContent.trim().toLowerCase() === brandLower) ||
      items.find((e) => e.textContent.trim().toLowerCase().includes(brandLower))
    );
  };

  // Try a direct match among the initially shown popular brands
  let pill = findPill(modal);

  // Otherwise type into the modal search to filter (execCommand goes through the
  // native input pipeline that this search field reads — verified live)
  if (!pill) {
    const search =
      modal.querySelector('input[data-testid="autocomplete-Merk"]') ||
      modal.querySelector('input[type="text"]') ||
      modal.querySelector("input");
    if (search) {
      search.focus();
      await sleep(60);
      document.execCommand("selectAll", false, null);
      document.execCommand("insertText", false, brand);
      const deadline = Date.now() + 3000;
      while (Date.now() < deadline && !pill) {
        await sleep(150);
        pill = findPill(modal);
      }
    }
  }

  if (pill) {
    pill.scrollIntoView({ block: "nearest" });
    pill.click();
    await sleep(400);
    return (trigger.value || "").trim().length > 0;
  }

  // Nothing matched — close the modal so it doesn't block the rest of the form
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  return false;
}

// Content scripts call this when done

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "SYNC_TOKEN" && msg.token) {
    chrome.storage.sync.set({ authToken: msg.token, userEmail: msg.email || "" }, () => {
      sendResponse({ ok: true });
      pollJobs();
    });
    return true;
  }

  if (msg.type === "FILL_DESC") {
    console.log("[ListHub] FILL_DESC received, tab:", sender.tab?.id, "text len:", msg.text?.length);
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwFillDescription,
      args: [msg.selector, msg.text],
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error("[ListHub] FILL_DESC failed:", chrome.runtime.lastError.message);
        sendResponse(false);
      } else {
        console.log("[ListHub] FILL_DESC result:", results?.[0]?.result);
        sendResponse(results?.[0]?.result ?? false);
      }
    });
    return true;
  }

  if (msg.type === "FILL_BRAND") {
    console.log("[ListHub] FILL_BRAND received, brand:", msg.brand);
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwFillBrand,
      args: [msg.brand],
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error("[ListHub] FILL_BRAND failed:", chrome.runtime.lastError.message);
        sendResponse(false);
      } else {
        console.log("[ListHub] FILL_BRAND result:", results?.[0]?.result);
        sendResponse(results?.[0]?.result ?? false);
      }
    });
    return true;
  }

  if (msg.type === "JOB_DONE") {
    const { platform, jobId, serverUrl, result } = msg;
    getAuthHeaders().then(headers => fetch(`${serverUrl}/api/jobs/${jobId}/complete`, {
      method: "POST",
      headers,
      body: JSON.stringify(result),
    })).then(() => {
      chrome.storage.local.remove(`job_${platform}`);
      // Keep tab open 2s so user can see the listing was created
      setTimeout(() => chrome.tabs.remove(sender.tab.id), 2000);
    });
    sendResponse({ ok: true });
  }

  if (msg.type === "JOB_ERROR") {
    const { platform, jobId, serverUrl, error } = msg;
    getAuthHeaders().then(headers => fetch(`${serverUrl}/api/jobs/${jobId}/error`, {
      method: "POST",
      headers,
      body: JSON.stringify({ error }),
    })).then(() => {
      chrome.storage.local.remove(`job_${platform}`);
      // Keep the tab OPEN so the user can review the filled form and finish
      // manually. Closing it here loses all the work that was filled in.
    });
    sendResponse({ ok: true });
  }
  return true;
});

async function reportError(jobId, serverUrl, error) {
  const headers = await getAuthHeaders();
  await fetch(`${serverUrl}/api/jobs/${jobId}/error`, {
    method: "POST",
    headers,
    body: JSON.stringify({ error }),
  });
}
