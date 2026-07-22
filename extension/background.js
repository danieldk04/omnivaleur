importScripts("analytics.js");

const POLL_INTERVAL_SECONDS = 15;

// Platforms this extension handles (API platforms like eBay/Etsy are server-side)
// "facebook" = Facebook Marketplace (BETA, best-effort — see content/facebook.js)
const EXTENSION_PLATFORMS = ["marktplaats", "2dehands", "vinted", "facebook"];

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

  // === GAMES (cat1=356 "Spelcomputers en Games") ===
  // Non-clothing. URL form is /plaats/{cat1}/{cat3}?bucketId={bucketId}, where
  // for this branch bucketId = the L2 platform subcategory and cat3 = the L3
  // console-generation "type". Both are mandatory in Marktplaats' sell flow, so
  // every game category is pinned to a specific generation. IDs read straight
  // from the live SYI category picker (verified, not guessed).
  // -- PlayStation games (bucketId 205 = "Games | Sony PlayStation")
  "games playstation 5":    { cat1: 356, cat3: 2952, bucketId: 205 },
  "games playstation 4":    { cat1: 356, cat3: 2889, bucketId: 205 },
  "games playstation 3":    { cat1: 356, cat3: 1735, bucketId: 205 },
  "games playstation 2":    { cat1: 356, cat3: 1734, bucketId: 205 },
  "games playstation 1":    { cat1: 356, cat3: 367,  bucketId: 205 },
  "games psp":              { cat1: 356, cat3: 1660, bucketId: 205 },
  "games ps vita":          { cat1: 356, cat3: 2890, bucketId: 205 },
  // -- Nintendo games (bucketId 204 = "Games | Nintendo")
  "games nintendo switch":  { cat1: 356, cat3: 2942, bucketId: 204 },
  "games nintendo wii u":   { cat1: 356, cat3: 2888, bucketId: 204 },
  "games nintendo wii":     { cat1: 356, cat3: 1630, bucketId: 204 },
  "games nintendo 3ds":     { cat1: 356, cat3: 2887, bucketId: 204 },
  "games nintendo ds":      { cat1: 356, cat3: 1659, bucketId: 204 },
  "games gamecube":         { cat1: 356, cat3: 1730, bucketId: 204 },
  "games nintendo 64":      { cat1: 356, cat3: 1733, bucketId: 204 },
  "games snes":             { cat1: 356, cat3: 1732, bucketId: 204 },
  "games nes":              { cat1: 356, cat3: 1731, bucketId: 204 },
  "games gameboy":          { cat1: 356, cat3: 363,  bucketId: 204 },
  // -- Xbox games (bucketId 206 = "Games | Xbox")
  "games xbox series":      { cat1: 356, cat3: 2953, bucketId: 206 },
  "games xbox one":         { cat1: 356, cat3: 2891, bucketId: 206 },
  "games xbox 360":         { cat1: 356, cat3: 1631, bucketId: 206 },
  "games xbox original":    { cat1: 356, cat3: 368,  bucketId: 206 },
  // -- Other games (bucketId 207 = "Games | Overige")
  "games pc":               { cat1: 356, cat3: 365,  bucketId: 207 },
  "games sega":             { cat1: 356, cat3: 366,  bucketId: 207 },
  "games atari":            { cat1: 356, cat3: 1729, bucketId: 207 },
  "games overige":          { cat1: 356, cat3: 364,  bucketId: 207 },

  // === GAME CONSOLES — hardware (cat1=356, but the "Spelcomputers" L2 buckets
  // 208-211, distinct from the "Games" software buckets 204-207 above). Same
  // URL form /plaats/{cat1}/{cat3}?bucketId={bucketId}. IDs read live from the
  // SYI category picker (verified). These share the "games " non-clothing prefix.
  // -- PlayStation consoles (bucketId 209 = "Spelcomputers | Sony PlayStation")
  "games console playstation 5": { cat1: 356, cat3: 2954, bucketId: 209 },
  "games console playstation 4": { cat1: 356, cat3: 2894, bucketId: 209 },
  "games console playstation 3": { cat1: 356, cat3: 1741, bucketId: 209 },
  "games console playstation 2": { cat1: 356, cat3: 1740, bucketId: 209 },
  "games console playstation 1": { cat1: 356, cat3: 347,  bucketId: 209 },
  "games console ps vita":       { cat1: 356, cat3: 2895, bucketId: 209 },
  "games console psp":           { cat1: 356, cat3: 1656, bucketId: 209 },
  // -- Nintendo consoles (bucketId 208 = "Spelcomputers | Nintendo")
  "games console nintendo switch":      { cat1: 356, cat3: 2943, bucketId: 208 },
  "games console nintendo switch lite": { cat1: 356, cat3: 2946, bucketId: 208 },
  "games console nintendo wii u":       { cat1: 356, cat3: 2893, bucketId: 208 },
  "games console nintendo wii":         { cat1: 356, cat3: 1628, bucketId: 208 },
  "games console nintendo 3ds":         { cat1: 356, cat3: 2892, bucketId: 208 },
  "games console nintendo ds":          { cat1: 356, cat3: 1655, bucketId: 208 },
  "games console gamecube":             { cat1: 356, cat3: 1736, bucketId: 208 },
  "games console nintendo 64":          { cat1: 356, cat3: 1739, bucketId: 208 },
  "games console snes":                 { cat1: 356, cat3: 1738, bucketId: 208 },
  "games console nes":                  { cat1: 356, cat3: 1737, bucketId: 208 },
  "games console gameboy":              { cat1: 356, cat3: 346,  bucketId: 208 },
  // -- Xbox consoles (bucketId 210 = "Spelcomputers | Xbox")
  "games console xbox series":   { cat1: 356, cat3: 2955, bucketId: 210 },
  "games console xbox one":      { cat1: 356, cat3: 2896, bucketId: 210 },
  "games console xbox 360":      { cat1: 356, cat3: 1629, bucketId: 210 },
  "games console xbox original": { cat1: 356, cat3: 349,  bucketId: 210 },
  // -- Other consoles (bucketId 211 = "Spelcomputers | Overige")
  "games console sega":    { cat1: 356, cat3: 348,  bucketId: 211 },
  "games console atari":   { cat1: 356, cat3: 345,  bucketId: 211 },
  "games console overige": { cat1: 356, cat3: 1743, bucketId: 211 },

  // === ELECTRONICS — mobile phones (cat1=820 "Telecommunicatie", L2 bucketId
  // 225 = "Mobiele telefoons", cat3 = phone brand). Same URL form. IDs read live
  // from the SYI picker (verified: /plaats/820/1953?bucketId=225 = Apple iPhone).
  // Recognised as non-clothing by the "electronics " prefix.
  "electronics telefoon apple iphone": { cat1: 820, cat3: 1953, bucketId: 225 },
  "electronics telefoon samsung":      { cat1: 820, cat3: 841,  bucketId: 225 },
  "electronics telefoon huawei":       { cat1: 820, cat3: 2897, bucketId: 225 },
  "electronics telefoon sony":         { cat1: 820, cat3: 843,  bucketId: 225 },
  "electronics telefoon nokia":        { cat1: 820, cat3: 836,  bucketId: 225 },
  "electronics telefoon lg":           { cat1: 820, cat3: 1632, bucketId: 225 },
  "electronics telefoon motorola":     { cat1: 820, cat3: 834,  bucketId: 225 },
  "electronics telefoon htc":          { cat1: 820, cat3: 1685, bucketId: 225 },
  "electronics telefoon blackberry":   { cat1: 820, cat3: 1954, bucketId: 225 },
  "electronics telefoon overige":      { cat1: 820, cat3: 837,  bucketId: 225 },
};
// NOTE: there is deliberately no catch-all default category. There used to be
// one (dames jeans), and it meant any item whose category didn't resolve got
// published as women's jeans — a MyProtein sport short included. Publishing to a
// wrong category is worse than not publishing: it's visible to buyers, hurts
// reach, and the user never learns it happened. Unresolved category now fails
// the job with an actionable message instead (see getMpSyiUrl).

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
  if (platform === "facebook") {
    // Beta: open the exact item page when we captured it at publish time,
    // otherwise the seller's "Your listings" page so the content script can
    // find it by title. FB item pages look like /marketplace/item/{id}.
    if (payload?.platform_listing_url) return payload.platform_listing_url;
    if (payload?.platform_listing_id) return `https://www.facebook.com/marketplace/item/${payload.platform_listing_id}`;
    return "https://www.facebook.com/marketplace/you/selling";
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

// Thrown when an item's category can't be mapped to a real platform category.
// Distinct from a runtime failure: nothing is broken, the item just needs a
// category from the user — so it's reported as a normal job error with a clear
// instruction rather than retried.
class CategoryUnresolvedError extends Error {
  constructor(message) {
    super(message);
    this.name = "CategoryUnresolvedError";
    this.needsUserInput = true;
  }
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

  // Facebook Marketplace (beta): single create-item form, no category-based URL.
  // The content script fills category/condition/etc. inside the form.
  if (platform === "facebook") {
    return "https://www.facebook.com/marketplace/create/item";
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
    // A dames category (cat1=621) for a heren item is a mismatch, not a result.
    if (c && c.cat1 === 621) c = null;
  } else {
    c = MP_CATEGORIES[cat];
  }

  if (!c) {
    throw new CategoryUnresolvedError(
      cat
        ? `Category "${cat}"${gender ? ` (${gender})` : ""} doesn't map to a ${platform} category. Set the category on this item and publish again.`
        : `This item has no category set, so it can't be published to ${platform} without guessing. Set a category on the item and publish again.`
    );
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

chrome.runtime.onInstalled.addListener((details) => {
  gaEvent(details.reason === "install" ? "extension_installed" : "extension_updated", {
    version: chrome.runtime.getManifest().version,
  });
});

async function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ serverUrl: "https://omnivaleur.com" }, (s) => {
      let url = s.serverUrl.replace(/\/$/, "");
      if (url === "https://api.omnivaleur.com") {
        // Stale value from before the domain consolidation — migrate it.
        url = "https://omnivaleur.com";
        chrome.storage.sync.set({ serverUrl: url });
      }
      resolve(url);
    });
  });
}

// Without a token every request goes out unauthenticated, gets a 401 and no job
// is ever picked up — silently. The popup shows this, but only if you think to
// open it, so surface it on the toolbar icon itself instead.
function refreshAuthBadge() {
  chrome.storage.sync.get(["authToken"], (s) => {
    if (s.authToken) {
      chrome.action.setBadgeText({ text: "" });
      chrome.action.setTitle({ title: "Omnivaleur" });
    } else {
      chrome.action.setBadgeText({ text: "!" });
      chrome.action.setBadgeBackgroundColor({ color: "#dc2626" });
      chrome.action.setTitle({
        title: "Omnivaleur — not logged in. Nothing will be published until you log in.",
      });
    }
  });
}

refreshAuthBadge();
chrome.runtime.onStartup.addListener(refreshAuthBadge);
chrome.runtime.onInstalled.addListener(refreshAuthBadge);

// Content scripts are only injected into pages loaded AFTER install, so someone
// who installs the extension with their dashboard already open would sit there
// signed out, with the dashboard telling them to install what they just
// installed — until they happened to reload. Inject the bridge into any open
// Omnivaleur tab so it syncs the token and announces itself immediately.
chrome.runtime.onInstalled.addListener(() => {
  chrome.tabs.query({ url: ["https://omnivaleur.com/*", "https://www.omnivaleur.com/*"] }, (tabs) => {
    for (const t of tabs || []) {
      chrome.scripting.executeScript(
        { target: { tabId: t.id }, files: ["content/webapp_sync.js"] },
        () => { void chrome.runtime.lastError; }  // tab may have navigated away
      );
    }
  });
});
// Covers the popup's own login/logout, which writes the token directly.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "sync" && changes.authToken) refreshAuthBadge();
});

async function getAuthHeaders() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(["authToken"], (s) => {
      const headers = { "Content-Type": "application/json" };
      if (s.authToken) headers["Authorization"] = `Bearer ${s.authToken}`;
      resolve(headers);
    });
  });
}

// ── Reliable job finalisation ─────────────────────────────────────────────
// A /complete that silently fails is worse than a job that never ran: the work
// IS done on the platform, but the backend still sees the job as claimed and
// _recover_stale_claims resets it to pending — so the dashboard shows it queued
// forever, and a create job gets flagged as a possible duplicate. These calls
// used to be `await fetch(...)` with no .ok check, so a 401/5xx/offline blip was
// invisible. Now: verify the response, retry with backoff, and persist anything
// still unsent so an MV3 worker kill can't drop it.
const FINALISE_QUEUE_KEY = "pendingFinalisations";
const FINALISE_MAX_ATTEMPTS = 4;

async function _postFinalise(serverUrl, jobId, kind, body) {
  const headers = await getAuthHeaders();
  const res = await fetch(`${serverUrl}/api/jobs/${jobId}/${kind}`, {
    method: "POST", headers, body: JSON.stringify(body || {}),
  });
  // 404 = job is already gone/finalised server-side; treat as settled, not a
  // failure, so we don't retry forever on a job the backend has moved past.
  if (!res.ok && res.status !== 404) {
    throw new Error(`${kind} returned HTTP ${res.status}`);
  }
  return true;
}

function _queueGet() {
  return new Promise(r => chrome.storage.local.get([FINALISE_QUEUE_KEY], s => r(s[FINALISE_QUEUE_KEY] || [])));
}
function _queueSet(list) {
  return new Promise(r => chrome.storage.local.set({ [FINALISE_QUEUE_KEY]: list }, r));
}

async function _queueAdd(entry) {
  const list = await _queueGet();
  if (list.some(e => e.jobId === entry.jobId && e.kind === entry.kind)) return;
  list.push(entry);
  await _queueSet(list);
}
async function _queueRemove(jobId, kind) {
  await _queueSet((await _queueGet()).filter(e => !(e.jobId === jobId && e.kind === kind)));
}

// Finalise a job (complete/error), retrying transient failures. Resolves true if
// the backend confirmed it; false if it was handed to the persistent queue.
async function finaliseJob(serverUrl, jobId, kind, body) {
  for (let attempt = 1; attempt <= FINALISE_MAX_ATTEMPTS; attempt++) {
    try {
      await _postFinalise(serverUrl, jobId, kind, body);
      await _queueRemove(jobId, kind);
      return true;
    } catch (e) {
      if (attempt === FINALISE_MAX_ATTEMPTS) {
        console.warn(`[Omnivaleur] ${kind} for job ${jobId} failed after ${attempt} attempts (${e.message}) — queued for retry`);
        await _queueAdd({ jobId, kind, body: body || {}, serverUrl, queuedAt: Date.now() });
        return false;
      }
      await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt - 1)));
    }
  }
  return false;
}

// Drain anything the retries above couldn't deliver. Runs on every poll tick and
// on startup, so a completion survives Chrome restarting or the token being
// refreshed after it expired mid-run.
async function flushFinaliseQueue() {
  const list = await _queueGet();
  if (!list.length) return;
  for (const e of list) {
    try {
      await _postFinalise(e.serverUrl, e.jobId, e.kind, e.body);
      await _queueRemove(e.jobId, e.kind);
      console.log(`[Omnivaleur] flushed queued ${e.kind} for job ${e.jobId}`);
    } catch (err) { /* stays queued for the next tick */ }
  }
}
chrome.runtime.onStartup.addListener(flushFinaliseQueue);

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
  // Deliver any completions a previous run couldn't confirm BEFORE asking for
  // pending work — otherwise the backend hands us back a job we already did.
  await flushFinaliseQueue();
  const headers = await getAuthHeaders();
  for (const platform of EXTENSION_PLATFORMS) {
    try {
      const res = await fetch(`${serverUrl}/api/jobs/pending?platform=${platform}`, { headers });
      if (!res.ok) continue;
      const jobs = await res.json();
      for (const job of jobs) {
        try {
          await processJob(job, serverUrl);
        } catch (e) {
          // Last line of defence. processJob claims the job BEFORE doing any
          // work, and the backend refuses to dispatch anything at all while a
          // job sits claimed (strict global serialisation). So an unhandled
          // throw here used to freeze the entire queue — every platform — until
          // the 5-minute stale sweep, which then killed the job as "interrupted"
          // rather than telling the user what actually went wrong. Report it
          // against this job and keep going.
          console.error(`Omnivaleur job ${job.id} (${job.action}/${platform}) threw:`, e);
          try {
            await reportError(job.id, serverUrl, `Extension error: ${e?.message || e}`);
          } catch (e2) {
            console.error("Omnivaleur: failed to report job error:", e2);
          }
        }
      }
    } catch (e) {
      console.error(`Omnivaleur poll error (${platform}):`, e);
    }
  }
}

async function processJob(job, serverUrl) {
  const headers = await getAuthHeaders();
  // Claim job first
  const claimRes = await fetch(`${serverUrl}/api/jobs/${job.id}/claim`, { method: "POST", headers });
  if (!claimRes.ok) return;

  gaEvent("job_started", { action: job.action, platform: job.platform });

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

  let url;
  try {
    url = job.action === "delete" ? getDeleteUrl(job.platform, job.payload)
      : job.action === "content_refresh" ? getEditUrl(job.platform, job.payload)
      : getMpSyiUrl(job.platform, job.payload);
  } catch (e) {
    // An unresolved category lands here. Report it against this job only — an
    // uncaught throw would escape processJob and silently abandon every other
    // job in this poll round.
    await reportError(job.id, serverUrl, e.message || String(e));
    return;
  }
  if (!url) {
    await reportError(job.id, serverUrl, "No URL configured for " + job.platform + " action=" + job.action);
    return;
  }

  console.log(`[Omnivaleur] Opening tab for ${job.platform} job ${job.id}: ${url}`);
  chrome.tabs.create({ url, active: true }, (tab) => {
    if (chrome.runtime.lastError) {
      reportError(job.id, serverUrl, "tabs.create failed: " + chrome.runtime.lastError.message);
      return;
    }
    // PER-TAB job storage — the whole job, keyed by THIS tab's id. The content
    // script asks the background for its own tab's job (GET_JOB). This replaces
    // the old single job_<platform> slot, where a second same-platform tab
    // overwrote the first tab's job data, so two listings published with each
    // other's photos, prices, titles and descriptions. Per-tab keying makes that
    // impossible even if two tabs ever run at once.
    chrome.storage.local.set({ [`jobtab_${tab.id}`]: { ...job, jobId: job.id, serverUrl } });
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

    await finaliseJob(serverUrl, job.id, "complete", {});
    console.log(`[Omnivaleur] bgDelete success: ${platform} listing "${title}"`);

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
      // Page through the WHOLE wardrobe. Vinted caps per_page at 96 server-side
      // and silently ignores anything larger, so the old single "per_page=200"
      // call only ever proved the 96 NEWEST listings. Any older listing looked
      // absent, which aborted its delete with "not in your wardrobe" while the
      // listing was in fact live — verified live 2026-07: item 8557510561 sits
      // on page 2 of a 536-item wardrobe. Only a full walk may return false.
      try {
        for (let page = 1; page <= 60; page++) {
          const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=96`, { headers: { Accept: "application/json" } });
          if (!res.ok) return { userId, present: null };
          const data = await res.json();
          if (data.code && data.code !== 0) return { userId, present: null };
          const items = data.items || [];
          if (items.some(it => String(it.id) === String(lid))) return { userId, present: true };
          const pg = data.pagination || {};
          if (items.length === 0) return { userId, present: false };
          if (pg.total_pages && page >= pg.total_pages) return { userId, present: false };
          if (!pg.total_pages && items.length < 96) return { userId, present: false };
        }
        return { userId, present: null };  // never saw the end — don't claim absent
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
      // Paged for the same reason as the presence check above (per_page caps at
      // 96): without this an older listing's snapshot came back empty and the
      // paired recreate would republish it stripped of photos/description.
      let it = null;
      try {
        for (let page = 1; page <= 60 && !it; page++) {
          const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=96`, { headers: { Accept: "application/json" } });
          if (!res.ok) break;
          const data = await res.json();
          const items = data.items || [];
          it = items.find(x => String(x.id) === String(lid)) || null;
          if (it) break;
          const pg = data.pagination || {};
          if (items.length === 0) break;
          if (pg.total_pages && page >= pg.total_pages) break;
          if (!pg.total_pages && items.length < 96) break;
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
        // Field names verified live 2026-07 against a real wardrobe object:
        // brand:"Ralph Lauren", size:"L", status:"Very good",
        // price:{amount,currency_code}, photos:[{url,full_size_url}].
        // The verified name comes FIRST; the alternates behind it are legacy
        // guesses kept only as a cushion if Vinted renames a field.
        out.brand = it.brand || it.brand_title || it.brand_dto?.title || "";
        out.size = it.size || it.size_title || "";
        out.condition = it.status || it.status_title || "";
        out.description = it.description || "";
        const pr = it.price?.amount ?? it.price ?? it.total_item_price?.amount;
        if (pr != null && !isNaN(Number(pr))) out.price = Number(pr);
        // Colour + material are NOT on the wardrobe object at all (confirmed
        // live) — they only exist in the page's attribute rows, scraped below.
        out.color = it.color1 || it.color1_title || it.colour || "";
      }
      // Description: never on the wardrobe object, so it comes from the DOM.
      // [itemprop="description"] is THIS item's description — the loose
      // "any leaf element with >25 chars" fallback is dangerous here because the
      // page also renders other_user_items-*--description blocks for the
      // seller's OTHER listings, and could republish a different item's text.
      // Collapsed descriptions append a "... more" expander to innerText but do
      // NOT truncate it (verified live: 540 chars collapsed = 531 + "\n... more",
      // identical text after expanding), so stripping the suffix is lossless.
      if (!out.description) {
        const dEl = document.querySelector('[itemprop="description"]');
        const raw = (dEl?.innerText || "").trim();
        if (raw) out.description = raw.replace(/\s*\n?\.{3}\s*(more|meer|minder|less)\s*$/i, "").trim().slice(0, 1000);
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
      // Vinted gives every attribute row an exact testid (verified live 2026-07):
      //   item-attributes-color    -> "Colour\nNavy"
      //   item-attributes-material -> "Material\nCotton"
      //   item-attributes-status   -> "Condition\nVery good"
      // Read those directly — the label/sibling walking below only ever ran on
      // guessed label text and returned nothing for colour and material, so both
      // were silently lost on every relist. Each row renders "Label\nValue", so
      // drop the first line and keep the rest.
      const attrValue = (testid) => {
        const el = document.querySelector(`[data-testid="item-attributes-${testid}"]`);
        const lines = (el?.innerText || "").split("\n").map(s => s.trim()).filter(Boolean);
        return lines.length > 1 ? lines.slice(1).join(" ") : "";
      };
      if (!out.color) out.color = attrValue("color") || scopeRow(["Colour", "Color", "Kleur"]) || rowValue(["Colour", "Color", "Kleur"]);
      out.material = attrValue("material") || scopeRow(["Material", "Materiaal"]) || rowValue(["Material", "Materiaal"]);
      if (!out.condition) out.condition = attrValue("status");
      if (!out.size) out.size = attrValue("size");
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
      // Paged — and this one matters most: with the old single-page fetch an
      // older listing was ALWAYS absent from page 1, so a delete that never
      // happened verified as "gone" and the recreate then duplicated the still
      // live listing. A false "gone" is worse than a failed relist.
      const present = await execInTab(tabId, async (userId, lid) => {
        try {
          for (let page = 1; page <= 60; page++) {
            const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=96`, { headers: { Accept: "application/json" } });
            if (!res.ok) return null;
            const data = await res.json();
            if (data.code && data.code !== 0) return null;
            const items = data.items || [];
            if (items.some(it => String(it.id) === String(lid))) return true;
            const pg = data.pagination || {};
            if (items.length === 0) return false;
            if (pg.total_pages && page >= pg.total_pages) return false;
            if (!pg.total_pages && items.length < 96) return false;
          }
          return null;
        } catch (e) { return null; }
      }, [before.userId, listingId]);
      if (present === false) { goneAfter = true; break; }
      await sleep(1800);
    }
    if (!goneAfter) throw new Error(`Vinted listing ${listingId} still in your wardrobe after confirming delete — removal was not verified.`);

    // The captured listing snapshot lets the backend enrich the paired relist
    // recreate job (imported items otherwise lack this data).
    await finaliseJob(serverUrl, job.id, "complete", { captured_listing: snapshot });
    console.log(`[Omnivaleur] bgDeleteVinted success: listing ${listingId}`, snapshot);
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
          console.log("[Omnivaleur] detail-debug", { status: d._status, err: d._err, tries: d._tries, descLen: (d.description || "").length, src: d._src || "api" });
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
        console.log("[Omnivaleur] no-desc items:", noDesc.join(" "));
        await reportProgress(serverUrl, job.id, {
          stage: "enriching", message: `${enriched}/${total} enriched — ${noDesc.length} without description`,
          current: total, total,
          debug: `no desc (${noDesc.length}): ${noDesc.slice(0, 12).join(" ")}`,
        });
        await sleep(1200); // give the panel a beat to poll this before "saving" overwrites it
      }
    } catch (e) {
      console.warn("[Omnivaleur] Vinted enrichment aborted, sending list data only:", e);
    }

    await reportProgress(serverUrl, job.id, {
      stage: "saving", message: "Saving to your dashboard…", current: total, total,
    });
    await finaliseJob(serverUrl, job.id, "complete", { listings: result.items });
    console.log(`[Omnivaleur] Vinted scan found ${result.items.length} listings (enriched ${enriched})`);
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

    await finaliseJob(serverUrl, job.id, "complete", { listings: result.items });
    console.log(`[Omnivaleur] ${platform} scan found ${result.items.length} listings (enriched ${Object.keys(enrichments || {}).length})`);
  } finally {
    setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2500);
  }
}

// Closing a job tab means that job's meta is dead. Without this, jobtab_ keys
// pile up forever — and because Chrome reuses tab ids after a restart, a brand
// new tab could inherit a stale entry and complete the wrong job.
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.remove(`jobtab_${tabId}`);
});

// ── Auto-detect manual publish ─────────────────────────────────────────────
// When the user manually clicks "Plaatsen" after an error, the tab URL changes
// to the listing URL. We detect this and auto-complete the job.
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
  if (!changeInfo.url) return;
  const key = `jobtab_${tabId}`;
  const stored = await chrome.storage.local.get(key);
  const meta = stored[key];
  if (!meta) return;
  // This auto-detect is a safety net for a manual publish — only meaningful for
  // a create. A content_refresh (which now also has a jobtab entry) is completed
  // by its own content script, so never auto-complete it here.
  if (meta.action && meta.action !== "create") return;

  const url = changeInfo.url;
  // Vinted listing ids are plain digits (/items/9331465721), so the m-prefixed
  // Marktplaats/2dehands patterns never match them. Without a Vinted-specific
  // pattern the create job stays stuck "claimed" after publish, because Vinted's
  // post-Upload navigation tears down the content script before it can send
  // JOB_DONE.
  //
  // BUT: while the content script is still filling the form, Vinted assigns the
  // in-progress listing a DRAFT url — /items/{id}/edit or a bare /items/{id} —
  // long before it's actually published. A loose /items/{digits} match fired on
  // that draft url, marked the create job "complete" with the draft id, and
  // closed the tab before anything was really done. A genuinely PUBLISHED Vinted
  // item always redirects to its slugged canonical url (/items/{id}-{slug}), so
  // require that hyphen-slug shape: it never matches /items/new, /items/{id}/edit
  // or a bare draft /items/{id}, only the real post-publish page.
  let m;
  if (meta.platform === "vinted") {
    m = url.match(/\/items\/(\d+)-[a-z0-9]/i);
  } else {
    m = url.match(/\/seller\/view\/(m\d+)/) ||
         url.match(/\/v\/[^/]+\/(m\d+)/) ||
         url.match(/[?&](m\d{6,})/) ||
         url.match(/(m\d{8,})/);
  }
  if (!m) return;

  const listingId = m[1];
  console.log(`[Omnivaleur] Auto-detected listing after publish: ${listingId} (${meta.platform})`);

  // Clear stored job
  chrome.storage.local.remove([key, `job_${meta.platform}`]);

  const listingUrl = meta.platform === "marktplaats"
    ? `https://www.marktplaats.nl/v/listing/${listingId}`
    : meta.platform === "2dehands"
    ? `https://www.2dehands.be/v/listing/${listingId}`
    : meta.platform === "vinted"
    ? `${new URL(url).origin}/items/${listingId}`
    : null;

  // Critical path: this is the ONLY completion signal for a create job, and a
  // create is not retry-safe server-side — a lost completion gets surfaced to
  // the user as a possible duplicate. Retry hard, and queue if still unsent.
  await finaliseJob(meta.serverUrl, meta.jobId, "complete", {
    platform_listing_id: listingId, platform_listing_url: listingUrl,
  });

  setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2000);
});

// ── Autonomous sold detection + cross-platform delist ─────────────────────
// Every poll cycle also checks for sold items and triggers auto-delist.
chrome.alarms.create("sold-check", { periodInMinutes: 10 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "sold-check") { checkSoldListings(); checkVintedOrders(); }
});

// Vinted has no webhook and no server-side polling (a stale session once let
// server-side Vinted polling mass-delist live listings by mistake, so that
// path stays permanently disabled). The only reliable, safe signal for "this
// Vinted item sold" is the extension's own wardrobe scan, run from the
// user's real logged-in session. Without a recurring trigger, that scan only
// ever ran when the user manually clicked "scan" — so a Vinted sale could sit
// undetected (and the item still listed elsewhere) indefinitely. This queues
// a scan job every hour; the existing 15s job poller picks it up and runs it
// like any other job, and the backend reconciles sold items once it completes.
chrome.alarms.create("vinted-auto-scan", { periodInMinutes: 60 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "vinted-auto-scan") triggerVintedAutoScan();
});
chrome.runtime.onInstalled.addListener(triggerVintedAutoScan);
chrome.runtime.onStartup.addListener(triggerVintedAutoScan);
// Alarms only fire after their first period, so kick a sold-check once on
// startup too (delayed a little so auth/session is ready).
function kickSoldCheck() { setTimeout(() => { checkSoldListings(); checkVintedOrders(); }, 8000); }
chrome.runtime.onInstalled.addListener(kickSoldCheck);
chrome.runtime.onStartup.addListener(kickSoldCheck);

async function triggerVintedAutoScan() {
  try {
    const serverUrl = await getServerUrl();
    const headers = await getAuthHeaders();
    if (!headers.Authorization) return; // not logged into the extension yet
    await fetch(`${serverUrl}/api/scan/vinted`, { method: "POST", headers });
    // Job is now pending — the regular 15s pollJobs() loop dispatches it.
  } catch (e) {
    console.error("[Omnivaleur] vinted-auto-scan trigger failed:", e);
  }
}

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

      // Scrape the ads overview and read each ad's SOLD marker. We only act on a
      // POSITIVE "verkocht/gereserveerd" label — never on a listing merely being
      // absent, which on Marktplaats also means "expired" (auto-relisted later)
      // and would wrongly delist a still-live item everywhere. Fail-safe: if no
      // ad shows a sold label, nothing happens.
      const ads = await scrapeMarktplaatsAds(soldUrl, platform);
      const soldIds = new Set(ads.filter(a => a.sold).map(a => a.id));
      if (!soldIds.size) continue;

      for (const listing of active) {
        if (soldIds.has(listing.platform_listing_id)) {
          console.log(`[Omnivaleur] Sold detected (verkocht label): ${listing.platform_listing_id} on ${platform}, triggering delist`);
          await fetch(`${serverUrl}/api/listings/sold?item_id=${listing.item_id}&platform=${platform}`, {
            method: "POST",
            headers: authHeaders,
          }).catch(e => console.error("[Omnivaleur] sold trigger failed:", e));
        }
      }
    } catch (e) {
      console.error(`[Omnivaleur] sold-check error (${platform}):`, e);
    }
  }
}

// Scrape each ad card on the Marktplaats/2dehands "my ads" overview and report
// whether it carries an explicit SOLD/RESERVED label. Returns [{id, sold}].
function scrapeMarktplaatsAds(url, platform) {
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
            const byId = {};
            document.querySelectorAll('a[href]').forEach(a => {
              const m = a.href.match(/\/(m\d{6,})/);
              if (!m) return;
              const id = m[1];
              const card = a.closest('article, li, [class*="listing" i], [class*="ad" i]') || a.parentElement || a;
              const text = (card.innerText || "").toLowerCase();
              const sold = /\bverkocht\b|\bgereserveerd\b|\bsold\b|\breserved\b/.test(text);
              byId[id] = byId[id] || sold;
              if (sold) byId[id] = true;
            });
            return Object.entries(byId).map(([id, sold]) => ({ id, sold }));
          },
        }, (results) => {
          chrome.tabs.remove(tabId).catch(() => {});
          const ads = results?.[0]?.result || [];
          console.log(`[Omnivaleur] ${platform} ads scraped: ${ads.length} (sold: ${ads.filter(a => a.sold).length})`);
          resolve(ads);
        });
      };

      chrome.tabs.onUpdated.addListener(onUpdated);
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(onUpdated);
        chrome.tabs.remove(tabId).catch(() => {});
        resolve([]);
      }, 30000);
    });
  });
}

// ── Vinted sales from the seller's own "My orders → Sold" page ─────────────
// Authoritative (Vinted itself says the order sold) and carries the amount
// actually received — far better than inferring a sale from a wardrobe
// disappearance. Each order's title embeds our "(1234)" SKU, which the backend
// matches EXACTLY + uniquely, so a bad scrape can't touch the wrong item.
async function checkVintedOrders() {
  try {
    const serverUrl = await getServerUrl();
    const authHeaders = await getAuthHeaders();
    if (!authHeaders.Authorization) return; // not logged into the extension yet
    const orders = await scrapeVintedOrders("https://www.vinted.nl/my_orders");
    if (!orders.length) return;
    await fetch(`${serverUrl}/api/listings/reconcile-vinted-orders`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ orders }),
    }).catch(e => console.error("[Omnivaleur] vinted-orders reconcile failed:", e));
  } catch (e) {
    console.error("[Omnivaleur] checkVintedOrders error:", e);
  }
}

function scrapeVintedOrders(url) {
  return new Promise((resolve) => {
    chrome.tabs.create({ url, active: false }, (tab) => {
      if (chrome.runtime.lastError) { resolve([]); return; }
      const tabId = tab.id;

      const onUpdated = (id, info) => {
        if (id !== tabId || info.status !== "complete") return;
        chrome.tabs.onUpdated.removeListener(onUpdated);

        // Give the SPA a moment to render the orders list, then scrape.
        setTimeout(() => {
          chrome.scripting.executeScript({
            target: { tabId },
            world: "MAIN",
            func: () => {
              // Each order row links to its conversation (/inbox/…). Walk up to the
              // row and read title (with the "(1234)" SKU), price, and status text.
              const rows = {};
              document.querySelectorAll('a[href*="/inbox/"]').forEach(a => {
                const row = a.closest('div, li, article') || a;
                const text = (row.innerText || a.innerText || "").replace(/\s+/g, " ").trim();
                const skuM = text.match(/\((\d{3,6})\)/);
                if (!skuM) return;
                const sku = skuM[1];
                const priceM = text.match(/€\s?(\d+(?:[.,]\d{2})?)/);
                const cancelled = /cancel|refund|geannuleerd|terugbetaal|retour/i.test(text);
                const prev = rows[sku];
                const sold = !cancelled;
                // Keep the sold entry (with price) over a cancelled one for the same SKU.
                if (!prev || (sold && !prev.sold)) {
                  rows[sku] = { sku, price: priceM ? priceM[1] : null, sold };
                } else if (sold && prev.sold && !prev.price && priceM) {
                  prev.price = priceM[1];
                }
              });
              return Object.values(rows);
            },
          }, (results) => {
            chrome.tabs.remove(tabId).catch(() => {});
            const orders = results?.[0]?.result || [];
            console.log(`[Omnivaleur] Vinted orders scraped: ${orders.length} (sold: ${orders.filter(o => o.sold).length})`);
            resolve(orders);
          });
        }, 2500);
      };

      chrome.tabs.onUpdated.addListener(onUpdated);
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(onUpdated);
        chrome.tabs.remove(tabId).catch(() => {});
        resolve([]);
      }, 30000);
    });
  });
}

// ── Activity notifications: unread messages + open bids/offers ────────────
// The marketplaces we automate have no seller API for messages/bids, so the
// only reliable read is the user's own logged-in session. Every 15 min we open
// each platform's messages page in a background tab, read the unread badge and
// bid indicators from the DOM, and report the counts to the backend so the
// dashboard can surface "3 new offers on Marktplaats" in one place. We never
// read message CONTENTS — only counts. Reply/accept still happens on-platform.
const NOTIF_SCAN_MINUTES = 15;

// Where to open the messages/bids view per platform, and the deep link we hand
// the dashboard so the user can jump straight there. (Vinted's inbox lives at
// /inbox — /member/messages 404s.)
const NOTIF_SOURCES = {
  marktplaats: "https://www.marktplaats.nl/messages",
  "2dehands": "https://www.2dehands.be/messages",
  vinted: "https://www.vinted.nl/inbox",
};

chrome.alarms.create("notif-scan", { periodInMinutes: NOTIF_SCAN_MINUTES });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "notif-scan") scanNotifications();
});
chrome.runtime.onInstalled.addListener(scanNotifications);
chrome.runtime.onStartup.addListener(scanNotifications);

async function scanNotifications() {
  const serverUrl = await getServerUrl();
  const headers = await getAuthHeaders();
  if (!headers.Authorization) return; // not logged into the extension yet

  for (const [platform, url] of Object.entries(NOTIF_SOURCES)) {
    try {
      const counts = await scrapeNotificationCounts(url, platform);
      if (!counts) continue; // not logged in / page didn't load — leave prior snapshot
      await fetch(`${serverUrl}/api/notifications/report`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          platform,
          messages: counts.messages,
          offers: counts.offers,
          deep_link: url,
        }),
      }).catch((e) => console.error(`[Omnivaleur] notif report failed (${platform}):`, e));
    } catch (e) {
      console.error(`[Omnivaleur] notif-scan error (${platform}):`, e);
    }
  }
}

// Opens the messages page in a background tab and reads counts from the DOM.
// Returns {messages, offers} or null if we couldn't read a logged-in page.
// NOTE: the selectors below are best-effort against the platforms' current
// markup and MUST be re-verified against a live logged-in session when a
// platform changes its layout — a miss degrades to null (no update), never a
// wrong number.
function scrapeNotificationCounts(url, platform) {
  return new Promise((resolve) => {
    chrome.tabs.create({ url, active: false }, (tab) => {
      if (chrome.runtime.lastError || !tab) { resolve(null); return; }
      const tabId = tab.id;
      let settled = false;
      const finish = (val) => {
        if (settled) return;
        settled = true;
        chrome.tabs.onUpdated.removeListener(onUpdated);
        chrome.tabs.remove(tabId).catch(() => {});
        resolve(val);
      };

      const onUpdated = (id, info) => {
        if (id !== tabId || info.status !== "complete") return;
        chrome.tabs.onUpdated.removeListener(onUpdated);
        // Give the SPA a moment to render its message list after load.
        setTimeout(() => {
          chrome.scripting.executeScript(
            { target: { tabId }, world: "MAIN", args: [platform], func: _mwReadNotifCounts },
            (results) => {
              const val = results?.[0]?.result;
              finish(val && typeof val.messages === "number" ? val : null);
            }
          );
        }, 3000);
      };

      chrome.tabs.onUpdated.addListener(onUpdated);
      setTimeout(() => finish(null), 30000); // hard timeout
    });
  });
}

// Injected into the platform page (MAIN world). Counts unread conversations and
// open bids/offers. Selectors/endpoints verified against the live logged-in
// sites (2026-07). Defensive: on a login wall / failed read it returns null so
// we never overwrite the stored snapshot with a bogus 0. Async: Vinted is read
// from its own JSON API (runs in the vinted.nl context, so cookies are sent).
async function _mwReadNotifCounts(platform) {
  if (platform === "vinted") {
    // Vinted offers arrive as a message whose text is a price question or a
    // bare amount ("€25.00"). Marktplaats prices everything, so this pattern is
    // Vinted-only — on MP it would match every item price (verified).
    const OFFER_RE = /would you (sell|take)|sell (it|this)|prijsvoorstel|€\s?\d/i;
    // Vinted's inbox API returns each conversation with an `unread` flag. Far
    // more reliable than scraping the SPA. Unread threads sort to the top, so
    // page 1 (50 rows) captures the actionable ones.
    try {
      const r = await fetch("/api/v2/inbox?page=1&per_page=50", {
        headers: { Accept: "application/json" },
        credentials: "include",
      });
      if (!r.ok) return null; // 401 = not logged into Vinted → don't report
      const j = await r.json();
      const convos = Array.isArray(j.conversations) ? j.conversations : [];
      const unread = convos.filter((c) => c && c.unread);
      const offers = unread.filter((c) => OFFER_RE.test(c.description || "")).length;
      return { messages: unread.length, offers };
    } catch (_) {
      return null;
    }
  }

  // Marktplaats / 2dehands share one codebase (hashed CSS-module class names).
  // A conversation row is `ConversationItem-module-root-*`; an UNREAD row shows
  // its latest-message preview in the strong/bold body style; a bid surfaces as
  // "Bod" in the preview text.
  const rows = document.querySelectorAll('[class*="ConversationItem-module-root"]');
  if (!rows.length) {
    // No rows AND a visible login prompt → not signed in; else just empty inbox.
    const txt = (document.body.innerText || "").toLowerCase();
    if (/inloggen|log ?in|aanmelden/.test(txt) && !/bericht/.test(txt)) return null;
    return { messages: 0, offers: 0 };
  }
  // On MP/2dehands a bid shows up literally as "bod" in the preview; the strict
  // word match avoids counting ordinary item prices as offers (verified).
  const MP_OFFER_RE = /\bbod\b|geboden|bieding/i;
  let messages = 0;
  let offers = 0;
  rows.forEach((r) => {
    if (r.querySelector('[class*="u-textStyleBodySmallStrong"]')) messages++;
    if (MP_OFFER_RE.test(r.textContent || "")) offers++;
  });
  return { messages, offers };
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

  // Normalise newlines so line-splitting is consistent across platforms/sources.
  const _lines = descText.replace(/\r\n?/g, "\n").split("\n");

  // ── Approach 1: execCommand (most reliable) ───────────────────────────────
  // execCommand fires a REAL native beforeinput event that Chrome and Lexical
  // both handle natively. InputEvent.dataTransfer is always null for synthetic
  // events in Chrome — execCommand bypasses that problem entirely.
  //
  // CRITICAL: insert LINE BY LINE. Passing the whole multi-line string to a
  // single insertText makes Lexical collapse every "\n", gluing all sentences
  // together. We insert each line and fire a real insertParagraph between them
  // so paragraph/line breaks survive exactly as written.
  try {
    el.focus();
    document.execCommand("selectAll", false, null);
    document.execCommand("delete", false, null);
    for (let i = 0; i < _lines.length; i++) {
      if (i > 0) document.execCommand("insertParagraph", false, null);
      if (_lines[i].length > 0) document.execCommand("insertText", false, _lines[i]);
    }
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
            for (const line of _lines) {
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

  // Lets the dashboard show what's actually wrong (not installed vs. signed out)
  // instead of assuming everything is fine. Deliberately reports only whether a
  // token exists and which account it belongs to — never the token itself.
  if (msg.type === "GET_AUTH_STATE") {
    chrome.storage.sync.get(["authToken", "userEmail"], (s) => {
      sendResponse({ signedIn: !!s.authToken, email: s.userEmail || "" });
    });
    return true;
  }

  // A content script asks for ITS OWN tab's job (keyed by tab id), so two tabs
  // can never read each other's data. Returns null if not ready yet — the
  // content script retries briefly to cover the tab-open race.
  if (msg.type === "GET_JOB") {
    const key = `jobtab_${sender.tab?.id}`;
    chrome.storage.local.get(key, (s) => sendResponse({ job: s[key] || null }));
    return true;
  }

  if (msg.type === "FILL_DESC") {
    console.log("[Omnivaleur] FILL_DESC received, tab:", sender.tab?.id, "text len:", msg.text?.length);
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwFillDescription,
      args: [msg.selector, msg.text],
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error("[Omnivaleur] FILL_DESC failed:", chrome.runtime.lastError.message);
        sendResponse(false);
      } else {
        console.log("[Omnivaleur] FILL_DESC result:", results?.[0]?.result);
        sendResponse(results?.[0]?.result ?? false);
      }
    });
    return true;
  }

  if (msg.type === "FILL_BRAND") {
    console.log("[Omnivaleur] FILL_BRAND received, brand:", msg.brand);
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwFillBrand,
      args: [msg.brand],
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error("[Omnivaleur] FILL_BRAND failed:", chrome.runtime.lastError.message);
        sendResponse(false);
      } else {
        console.log("[Omnivaleur] FILL_BRAND result:", results?.[0]?.result);
        sendResponse(results?.[0]?.result ?? false);
      }
    });
    return true;
  }

  if (msg.type === "JOB_DONE") {
    const { platform, jobId, serverUrl, result } = msg;
    // Clean up and close regardless of whether the completion landed on the
    // first try — finaliseJob queues it if not. Previously both of these hung
    // off .then(), so a failed fetch also stranded the tab open forever.
    finaliseJob(serverUrl, jobId, "complete", result).finally(() => {
      chrome.storage.local.remove([`job_${platform}`, `jobtab_${sender.tab?.id}`]);
      // Keep tab open 2s so user can see the listing was created
      if (sender.tab?.id) setTimeout(() => chrome.tabs.remove(sender.tab.id).catch(() => {}), 2000);
    });
    sendResponse({ ok: true });
  }

  if (msg.type === "JOB_ERROR") {
    const { platform, jobId, serverUrl, error } = msg;
    finaliseJob(serverUrl, jobId, "error", { error }).finally(() => {
      // Keep the tab OPEN so the user can review the filled form and finish
      // manually. Closing it here loses all the work that was filled in.
      //
      // Crucially, KEEP jobtab_${tabId} too. The onUpdated auto-detect listener
      // exists precisely to catch that manual "Plaatsen" click and complete the
      // job — but it bails when the meta is gone. Deleting it here meant a
      // manually-finished listing went live on the platform while Omnivaleur
      // still had it as failed: published, but invisible in the dashboard.
      // /complete has no status guard, so a later completion cleanly overrides
      // this error. Orphaned keys are cleaned up by the tabs.onRemoved listener.
      chrome.storage.local.remove([`job_${platform}`]);
      if (sender.tab?.id) {
        chrome.storage.local.get(`jobtab_${sender.tab.id}`, (s) => {
          const meta = s[`jobtab_${sender.tab.id}`];
          if (meta) {
            chrome.storage.local.set({
              [`jobtab_${sender.tab.id}`]: { ...meta, awaitingManualFinish: true },
            });
          }
        });
      }
    });
    sendResponse({ ok: true });
  }
  return true;
});

async function reportError(jobId, serverUrl, error) {
  gaEvent("job_error", {});
  // Same reliability need as /complete: a dropped error report leaves the job
  // claimed until the stale-claim sweep guesses at what happened.
  await finaliseJob(serverUrl, jobId, "error", { error });
}
