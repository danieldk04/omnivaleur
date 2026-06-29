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
  if (platform === "marktplaats") return "https://www.marktplaats.nl/mijn-marktplaats/advertenties/actief";
  if (platform === "2dehands")   return "https://www.2dehands.be/mijn-2dehands/advertenties/actief";
  if (platform === "vinted")     return payload?.platform_listing_id
    ? `https://www.vinted.com/items/${payload.platform_listing_id}`
    : null;
  return null;
}

function getMpSyiUrl(platform, item) {
  // Vinted has a simple listing flow — no category-based URLs needed
  if (platform === "vinted") {
    return "https://www.vinted.com/items/new";
  }

  const base = platform === "marktplaats"
    ? "https://www.marktplaats.nl/plaats"
    : "https://www.2dehands.be/plaats";
  const cat = (item?.category || "").toLowerCase().trim();
  const gender = (item?.gender || "").toLowerCase().trim();

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
    chrome.storage.sync.get({ serverUrl: "http://localhost:8001" }, (s) =>
      resolve(s.serverUrl.replace(/\/$/, ""))
    );
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
      console.error(`CrossList poll error (${platform}):`, e);
    }
  }
}

async function processJob(job, serverUrl) {
  const headers = await getAuthHeaders();
  // Claim job first
  const claimRes = await fetch(`${serverUrl}/api/jobs/${job.id}/claim`, { method: "POST", headers });
  if (!claimRes.ok) return; // Already claimed by another instance

  // Store job for content script to pick up
  await chrome.storage.local.set({ [`job_${job.platform}`]: { ...job, serverUrl } });

  // Open tab to the right page
  const url = job.action === "delete"
    ? getDeleteUrl(job.platform, job.payload)
    : getMpSyiUrl(job.platform, job.payload);
  if (!url) {
    await reportError(job.id, serverUrl, "No URL configured for " + job.platform + " action=" + job.action);
    return;
  }

  console.log(`[CrossList] Opening tab for ${job.platform} job ${job.id}: ${url}`);
  chrome.tabs.create({ url, active: true }, (tab) => {
    if (chrome.runtime.lastError) {
      console.error("[CrossList] tabs.create failed:", chrome.runtime.lastError.message);
      reportError(job.id, serverUrl, "tabs.create failed: " + chrome.runtime.lastError.message);
    } else {
      console.log(`[CrossList] Tab created: id=${tab.id} url=${tab.url || url}`);
      // Track this tab so we can auto-complete if user publishes manually
      if (job.action === "create") {
        chrome.storage.local.set({ [`jobtab_${tab.id}`]: { jobId: job.id, platform: job.platform, serverUrl } });
      }
    }
  });
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
  const m = url.match(/\/seller\/view\/(m\d+)/) ||
             url.match(/\/v\/[^/]+\/(m\d+)/) ||
             url.match(/[?&](m\d{6,})/) ||
             url.match(/(m\d{8,})/);
  if (!m) return;

  const listingId = m[1];
  console.log(`[CrossList] Auto-detected listing after manual publish: ${listingId} (${meta.platform})`);

  // Clear stored job
  chrome.storage.local.remove([key, `job_${meta.platform}`]);

  const listingUrl = meta.platform === "marktplaats"
    ? `https://www.marktplaats.nl/v/listing/${listingId}`
    : meta.platform === "2dehands"
    ? `https://www.2dehands.be/v/listing/${listingId}`
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
    marktplaats: "https://www.marktplaats.nl/mijn-marktplaats/advertenties/verkocht",
    "2dehands":  "https://www.2dehands.be/mijn-2dehands/advertenties/verkocht",
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
          console.log(`[CrossList] Sold detected: ${listing.platform_listing_id} on ${platform}, triggering delist`);
          await fetch(`${serverUrl}/api/listings/sold?item_id=${listing.item_id}&platform=${platform}`, {
            method: "POST",
            headers: authHeaders,
          }).catch(e => console.error("[CrossList] sold trigger failed:", e));
        }
      }
    } catch (e) {
      console.error(`[CrossList] sold-check error (${platform}):`, e);
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
          console.log(`[CrossList] Sold listings scraped from ${platform}:`, ids);
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
  if (msg.type === "FILL_DESC") {
    console.log("[CrossList] FILL_DESC received, tab:", sender.tab?.id, "text len:", msg.text?.length);
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwFillDescription,
      args: [msg.selector, msg.text],
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error("[CrossList] FILL_DESC failed:", chrome.runtime.lastError.message);
        sendResponse(false);
      } else {
        console.log("[CrossList] FILL_DESC result:", results?.[0]?.result);
        sendResponse(results?.[0]?.result ?? false);
      }
    });
    return true;
  }

  if (msg.type === "FILL_BRAND") {
    console.log("[CrossList] FILL_BRAND received, brand:", msg.brand);
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwFillBrand,
      args: [msg.brand],
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error("[CrossList] FILL_BRAND failed:", chrome.runtime.lastError.message);
        sendResponse(false);
      } else {
        console.log("[CrossList] FILL_BRAND result:", results?.[0]?.result);
        sendResponse(results?.[0]?.result ?? false);
      }
    });
    return true;
  }

  if (msg.type === "JOB_DONE") {
    const { platform, jobId, serverUrl, result } = msg;
    fetch(`${serverUrl}/api/jobs/${jobId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(result),
    }).then(() => {
      chrome.storage.local.remove(`job_${platform}`);
      // Keep tab open 2s so user can see the listing was created
      setTimeout(() => chrome.tabs.remove(sender.tab.id), 2000);
    });
    sendResponse({ ok: true });
  }

  if (msg.type === "JOB_ERROR") {
    const { platform, jobId, serverUrl, error } = msg;
    fetch(`${serverUrl}/api/jobs/${jobId}/error`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error }),
    }).then(() => {
      chrome.storage.local.remove(`job_${platform}`);
      // Keep the tab OPEN so the user can review the filled form and finish
      // manually. Closing it here loses all the work that was filled in.
    });
    sendResponse({ ok: true });
  }
  return true;
});

async function reportError(jobId, serverUrl, error) {
  await fetch(`${serverUrl}/api/jobs/${jobId}/error`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ error }),
  });
}
