importScripts("analytics.js");

const POLL_INTERVAL_SECONDS = 15;

// Platforms this extension handles (API platforms like eBay/Etsy are server-side)
// "facebook" = Facebook Marketplace (BETA, best-effort — see content/facebook.js)
const EXTENSION_PLATFORMS = ["marktplaats", "2dehands", "vinted", "facebook"];

// Marktplaats files children's clothing by SIZE: the L3 "type" under Babykleding
// and Kinderkleding literally IS the size (Maat 50 … Maat 176), with no boy/girl
// split at all. So for those two buckets cat3 has to be resolved from the item's
// own size instead of being a constant. IDs read from the live SYI picker.
const MP_BABY_SIZES = {   // Kinderen en Baby's > Babykleding (bucketId 150)
  50: 568, 56: 569, 62: 570, 68: 571, 74: 572, 80: 573, 86: 574,
};
const MP_KIDS_SIZES = {   // Kinderen en Baby's > Kinderkleding (bucketId 153)
  92: 582, 98: 583, 104: 584, 110: 585, 116: 586, 122: 587, 128: 588,
  134: 589, 140: 590, 146: 591, 152: 592, 158: 593, 164: 594, 170: 595, 176: 596,
};

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

  // === KINDEREN EN BABY'S (cat1=565) ===
  // These were all pointing at cat1=428 with bucketId=127. 428 is "Diversen"
  // (Feesten, Levensmiddelen, Zorg, …) — NOT Kinderkleding, and bucketId 127
  // doesn't exist under it. Verified live 2026-07: /plaats/428/429?bucketId=127,
  // /430 and /432 all return HTTP 400 ("deze pagina kan niet getoond worden"),
  // and /431 ("meisjes kleding") silently resolved to
  // Diversen > Modeltreinen > Brommobielen en Scootmobielen — a PAID category.
  // So every children's listing either failed outright or was posted as a
  // mobility scooter.
  //
  // The real tree is cat1=565 "Kinderen en Baby's", and Marktplaats files
  // children's clothing by SIZE, not by boy/girl — the L3 "type" IS the size
  // (Maat 50…Maat 176). Hence sizeMap below: cat3 is resolved from item.size at
  // publish time (see mpCategoryUrl), with cat3 as the fallback when the item has
  // no size or an unrecognised one.
  // -- Babykleding (bucketId 150): maten 50-86
  "babykleding":            { cat1: 565, bucketId: 150, cat3: 575, sizeMap: MP_BABY_SIZES },
  // -- Kinderkleding (bucketId 153): maten 92-176
  "peuterkleding":          { cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  "jongens kleding":        { cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  "meisjes kleding":        { cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  "tieners jongens":        { cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  "tieners meisjes":        { cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  "kinderen sportkleding":  { cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  // Schoenen en Sokken is its own type, so no size lookup.
  "kinderen schoenen":      { cat1: 565, bucketId: 153, cat3: 598 },
  // Mode-accessoires (bucketId 427) has exactly two types: baby and kind.
  "kinderen accessoires":   { cat1: 565, bucketId: 427, cat3: 3136 },

  // === UNISEX (fallback naar dames) ===
  "unisex truien":          { cat1: 621,  cat3: 640,  bucketId: 162 },
  "unisex jassen":          { cat1: 621,  cat3: 2784, bucketId: 162 },
  "unisex sportkleding":    { cat1: 621,  cat3: 2784, bucketId: 162 },
  "unisex schoenen":        { cat1: 621,  cat3: 625,  bucketId: 164 },
  "unisex accessoires":     { cat1: 621,  cat3: 628,  bucketId: 162 },

  // === SIERADEN, TASSEN EN UITERLIJK (cat1=1826) ===
  // Non-clothing, same prefix scheme as "games "/"electronics ". Exists because a
  // watch has no home in the clothing taxonomy: it could only be filed under an
  // "accessoires" key, which maps to Kleding | Dames (cat1 621) — so every watch,
  // ring and handbag landed in women's clothing accessories.
  // IDs read straight from the live SYI category picker on marktplaats.nl
  // (verified 2026-07, not guessed): cat1 1826, bucketId = the L2 subcategory,
  // cat3 = the L3 "type". Confirmed loading as "Horloges | Dames" for 1826/16?bucketId=199.
  // -- Horloges (bucketId 199)
  "sieraden horloges dames":    { cat1: 1826, cat3: 16,   bucketId: 199 },
  "sieraden horloges heren":    { cat1: 1826, cat3: 1831, bucketId: 199 },
  "sieraden horloges kinderen": { cat1: 1826, cat3: 2797, bucketId: 199 },
  "sieraden horloges antiek":   { cat1: 1826, cat3: 4,    bucketId: 199 },
  "sieraden smartwatch":        { cat1: 1826, cat3: 3041, bucketId: 199 },
  "sieraden sporthorloge":      { cat1: 1826, cat3: 3045, bucketId: 199 },
  "sieraden activity tracker":  { cat1: 1826, cat3: 3042, bucketId: 199 },
  // -- Sieraden (bucketId 200)
  "sieraden kettingen":         { cat1: 1826, cat3: 18,   bucketId: 200 },
  "sieraden kettinghangers":    { cat1: 1826, cat3: 2136, bucketId: 200 },
  "sieraden armbanden":         { cat1: 1826, cat3: 1827, bucketId: 200 },
  "sieraden ringen":            { cat1: 1826, cat3: 22,   bucketId: 200 },
  "sieraden oorbellen":         { cat1: 1826, cat3: 19,   bucketId: 200 },
  "sieraden bedels":            { cat1: 1826, cat3: 17,   bucketId: 200 },
  "sieraden broches":           { cat1: 1826, cat3: 1829, bucketId: 200 },
  "sieraden enkelbandjes":      { cat1: 1826, cat3: 2137, bucketId: 200 },
  "sieraden kindersieraden":    { cat1: 1826, cat3: 2138, bucketId: 200 },
  "sieraden antiek":            { cat1: 1826, cat3: 13,   bucketId: 200 },
  // -- Tassen en Koffers (bucketId 201)
  "sieraden damestassen":       { cat1: 1826, cat3: 626,  bucketId: 201 },
  "sieraden schoudertassen":    { cat1: 1826, cat3: 1840, bucketId: 201 },
  "sieraden rugtassen":         { cat1: 1826, cat3: 1838, bucketId: 201 },
  "sieraden reistassen":        { cat1: 1826, cat3: 1837, bucketId: 201 },
  "sieraden sporttassen":       { cat1: 1826, cat3: 3151, bucketId: 201 },
  "sieraden koffers":           { cat1: 1826, cat3: 1348, bucketId: 201 },
  // -- Accessoires (bucketId 197) en Zonnebrillen (bucketId 203)
  "sieraden portemonnees":      { cat1: 1826, cat3: 1836, bucketId: 197 },
  "sieraden zonnebril dames":   { cat1: 1826, cat3: 627,  bucketId: 203 },
  "sieraden zonnebril heren":   { cat1: 1826, cat3: 645,  bucketId: 203 },

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

  // Children's clothing: the L3 type is the size (see MP_BABY_SIZES). Read the
  // size off the item; fall back to the bucket's "Overige" type when the item has
  // no size or a non-numeric one (e.g. "4-5 jaar"), which is a real, valid
  // category — never a wrong one.
  let cat3 = c.cat3;
  if (c.sizeMap) {
    const resolved = mpKidsSizeCat3(item?.size, c.sizeMap);
    if (resolved) cat3 = resolved;
  }

  return `${base}/${c.cat1}/${cat3}?bucketId=${c.bucketId}&title=`;
}

// Map a stored size onto a Marktplaats children's size type id.
// Handles "104", "maat 104", "104/110" and "3-4 jaar" (years → cm, the standard
// EU sizing: 92 = 2 yrs, then +6cm per year). Returns null when nothing matches,
// so the caller can use the bucket's "Overige" type rather than guess.
function mpKidsSizeCat3(size, sizeMap) {
  const raw = String(size || "").toLowerCase().trim();
  if (!raw) return null;

  const known = Object.keys(sizeMap).map(Number).sort((a, b) => a - b);
  const nearest = (cm) => {
    // Marktplaats only has discrete sizes; snap to the nearest one, but never
    // across a gap bigger than one step (so a 200cm "size" isn't forced to 176).
    let best = null;
    for (const k of known) {
      if (best === null || Math.abs(k - cm) < Math.abs(best - cm)) best = k;
    }
    return best !== null && Math.abs(best - cm) <= 6 ? sizeMap[best] : null;
  };

  // "3 jaar" / "3-4 jaar" / "3y" → cm. Take the LOWER bound so a 3-4 lands on 98,
  // matching how these garments are actually labelled.
  const years = raw.match(/(\d{1,2})\s*(?:-\s*\d{1,2}\s*)?(?:jaar|jr|y|yrs|years)\b/);
  if (years) return nearest(92 + (parseInt(years[1], 10) - 2) * 6);

  // First number in the string: "104", "maat 104", "104/110", "110 cm".
  const num = raw.match(/\d{2,3}/);
  if (num) return nearest(parseInt(num[0], 10));

  return null;
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

// Seconds before a JWT's own expiry at which we proactively refresh. A slow
// background job (e.g. the Vinted sold scan) can run for many seconds, so we
// refresh with margin rather than let a call start on a token about to die.
const TOKEN_REFRESH_MARGIN_S = 120;
let _refreshInFlight = null;

function _sget(keys) {
  return new Promise((resolve) => chrome.storage.sync.get(keys, resolve));
}

// Decode a JWT's `exp` (seconds since epoch) without verifying — we only need to
// know whether it's about to expire, not to trust it.
function _jwtExp(token) {
  try {
    const p = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof p.exp === "number" ? p.exp : null;
  } catch (e) { return null; }
}

// Exchange the stored refresh token for a fresh access token via the backend.
// Deduped so a burst of parallel calls triggers a single refresh. Returns the
// new access token, or null if we can't refresh (no refresh token / rejected).
async function refreshAccessToken() {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = (async () => {
    const { refreshToken } = await _sget(["refreshToken"]);
    if (!refreshToken) return null;
    try {
      const serverUrl = await getServerUrl();
      const res = await fetch(`${serverUrl}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) {
        console.warn(`[Omnivaleur] token refresh failed HTTP ${res.status}`);
        return null;
      }
      const data = await res.json();
      if (!data.access_token) return null;
      const patch = { authToken: data.access_token };
      if (data.refresh_token) patch.refreshToken = data.refresh_token; // rotation
      await new Promise((r) => chrome.storage.sync.set(patch, r));
      console.log("[Omnivaleur] access token refreshed");
      return data.access_token;
    } catch (e) {
      console.warn("[Omnivaleur] token refresh error:", e);
      return null;
    }
  })().finally(() => { _refreshInFlight = null; });
  return _refreshInFlight;
}

async function getAuthHeaders() {
  const { authToken, refreshToken } = await _sget(["authToken", "refreshToken"]);
  let token = authToken;
  // Proactively refresh if the token is missing/expired/about-to-expire and we
  // have a refresh token. This is what keeps long background jobs from failing
  // with "Sessie verlopen" mid-run.
  const exp = token ? _jwtExp(token) : null;
  const soon = exp != null && exp - Date.now() / 1000 < TOKEN_REFRESH_MARGIN_S;
  if (refreshToken && (!token || soon)) {
    const fresh = await refreshAccessToken();
    if (fresh) token = fresh;
  }
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
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

// ── Dedicated worker window ────────────────────────────────────────────────
// Every automation tab used to spawn into — and yank focus from — whatever the
// user was doing, so a single publish threw several tabs in their face. Instead
// we keep ONE reused, UNFOCUSED worker window and open all automation tabs there:
// the window never comes to the front (no focus theft, no interleaving with the
// user's own tabs), yet each tab is still the ACTIVE tab of that window, so it
// stays visible and Chrome doesn't throttle its form-filling timers the way it
// would a truly hidden background tab. Closing the window just makes the next job
// open a fresh one.
//
// The window id MUST live in chrome.storage.session, not in a module variable.
// An MV3 service worker is evicted after ~30s idle, and every automation trigger
// here (15s job poll, 10-min sold-check, 15-min notification scan, hourly Vinted
// scan) wakes a FRESH worker with all module state reset. With the id in memory
// each of those woke up believing no worker window existed and created another
// one — which is why users ended up with a pile of Marktplaats/2dehands/Vinted
// windows. storage.session survives worker eviction (and is cleared on browser
// restart, exactly the lifetime we want), so all scans now share one window.
const WORKER_WIN_KEY = "workerWindowId";
// Small and out of the way: the user minimises it once and it STAYS minimised,
// because we never focus it and never call windows.update on it.
const WORKER_WIN_SIZE = { width: 1000, height: 800 };

async function getWorkerWindowId() {
  try {
    const { [WORKER_WIN_KEY]: id } = await chrome.storage.session.get(WORKER_WIN_KEY);
    if (id == null) return null;
    // Verify it still exists — the user may have closed it while the worker slept.
    await chrome.windows.get(id);
    return id;
  } catch {
    return null;
  }
}

function setWorkerWindowId(id) {
  return chrome.storage.session.set({ [WORKER_WIN_KEY]: id }).catch(() => {});
}

chrome.windows.onRemoved.addListener((winId) => {
  chrome.storage.session.get(WORKER_WIN_KEY).then(({ [WORKER_WIN_KEY]: id }) => {
    if (id === winId) chrome.storage.session.remove(WORKER_WIN_KEY);
  }).catch(() => {});
});

// Two triggers can fire in the same worker (e.g. sold-check and notif-scan land
// together, each opening a tab per platform). Without this chain they would all
// see "no window yet" and race to create one — the same multi-window bug, only
// within a single wake-up. Serialising means the first call creates the window
// and the rest reuse it.
let _workerWindowChain = Promise.resolve();

function openWorkerTab(url, callback) {
  _workerWindowChain = _workerWindowChain
    .then(() => openWorkerTabInner(url))
    .then(
      tab => callback(tab),
      err => { console.error("[Omnivaleur] openWorkerTab failed:", err); callback(null); }
    );
}

async function openWorkerTabInner(url) {
  const existing = await getWorkerWindowId();
  if (existing != null) {
    try {
      // active:true is scoped to THAT window, so it never steals focus from the
      // user's foreground window — and does not un-minimise it either.
      return await chrome.tabs.create({ url, windowId: existing, active: true });
    } catch {
      await chrome.storage.session.remove(WORKER_WIN_KEY).catch(() => {});
    }
  }
  try {
    const w = await chrome.windows.create({ url, focused: false, ...WORKER_WIN_SIZE });
    if (!w || !w.tabs || !w.tabs[0]) throw new Error("no tab in new window");
    await setWorkerWindowId(w.id);
    return w.tabs[0];
  } catch {
    // Window creation blocked (rare) — fall back to a plain background tab so
    // the job still runs rather than failing outright.
    return await chrome.tabs.create({ url, active: false });
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
  openWorkerTab(url, (tab) => {
    if (!tab) {
      reportError(job.id, serverUrl, "tabs.create failed: could not open a tab");
      return;
    }
    // PER-TAB job storage — the whole job, keyed by THIS tab's id. The content
    // script asks the background for its own tab's job (GET_JOB). This replaces
    // the old single job_<platform> slot, where a second same-platform tab
    // overwrote the first tab's job data, so two listings published with each
    // other's photos, prices, titles and descriptions. Per-tab keying makes that
    // impossible even if two tabs ever run at once.
    chrome.storage.local.set({ [`jobtab_${tab.id}`]: { ...job, jobId: job.id, serverUrl } });
    armJobWatchdog(tab.id);
  });
}

// ── Per-tab watchdog for content-script-driven jobs ────────────────────────
// Facebook (beta, unstable selectors) and any other tab-based job can hang
// without ever calling JOB_DONE/JOB_ERROR — e.g. getJob() never resolves, or
// fillForm() gets stuck in a wait loop on a form Facebook changed. Because the
// extension dispatches strictly ONE job at a time, a single silently-hung tab
// used to freeze the ENTIRE queue (every platform) until the server's 5-minute
// stale-claim sweep finally reset it — with no visible error in the meantime.
// This watchdog force-fails the job itself after a shorter timeout so the
// queue keeps moving and the user gets an actionable error immediately.
const JOB_TAB_TIMEOUT_MIN = 3; // minutes — generous for slow forms, short vs. the 5-min server sweep
const JOB_WATCHDOG_PREFIX = "jobwd_";

// Backed by chrome.alarms, NOT setTimeout: an MV3 service worker is evicted when
// idle, which silently cancelled the old timer — precisely in the situations that
// strand a job (content script hung, Chrome idle, worker killed). An alarm wakes
// the worker back up, so the timeout actually fires.
function armJobWatchdog(tabId) {
  chrome.alarms.create(`${JOB_WATCHDOG_PREFIX}${tabId}`, { delayInMinutes: JOB_TAB_TIMEOUT_MIN });
}

function clearJobWatchdog(tabId) {
  if (tabId == null) return;
  chrome.alarms.clear(`${JOB_WATCHDOG_PREFIX}${tabId}`);
}

async function fireJobWatchdog(tabId) {
  const key = `jobtab_${tabId}`;
  const stored = await chrome.storage.local.get(key);
  const meta = stored[key];
  if (!meta) return; // already resolved (JOB_DONE/JOB_ERROR cleared it)
  // A job deliberately handed back to the user to finish by hand is already
  // reported as an error and its tab is kept open on purpose — force-failing it
  // again would close the very tab they're still typing in.
  if (meta.awaitingManualFinish) return;
  console.warn(`[Omnivaleur] Watchdog: job ${meta.jobId} (${meta.platform}) on tab ${tabId} did not finish in time — force-failing.`);
  try {
    await reportError(meta.jobId, meta.serverUrl,
      `Extension timed out waiting for this ${meta.platform} job to finish (no response after ${JOB_TAB_TIMEOUT_MIN} minutes). ` +
      `The page may have changed, needs a manual step, or the extension lost track of the tab. ` +
      `Check the tab if it's still open, then publish again.`);
  } catch (e) {
    console.error("[Omnivaleur] Watchdog: failed to report timeout error:", e);
  }
  // A timed-out CREATE is usually half-filled and finishable by hand, so keep its
  // tab open and keep the meta alive: closing it would throw away the user's work
  // and, worse, leave the manual-publish auto-detect with nothing to match on — so
  // a listing they finished themselves would stay "not posted" in the dashboard.
  if ((meta.action || "create") === "create") {
    chrome.storage.local.set({ [key]: { ...meta, awaitingManualFinish: true } });
    return;
  }
  chrome.storage.local.remove(key);
  chrome.tabs.remove(tabId).catch(() => {});
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (!alarm.name.startsWith(JOB_WATCHDOG_PREFIX)) return;
  fireJobWatchdog(Number(alarm.name.slice(JOB_WATCHDOG_PREFIX.length)));
});

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

// The MP/2dehands seller overview renders only the FIRST 50 ads and hides the
// rest behind a "Toon 50 volgende advertenties." button. Anything past #50 is
// simply not in the DOM — and both the delete and the scan below read a missing
// row as "this listing is already gone", so a delete silently completed while
// the ad stayed live (verified live 2026-07: 129 ads on the account, 50
// rendered). Click through until the button is gone so the whole shop is loaded.
async function expandMp2dhOverview(tabId) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 40; i++) { // 40 x 50 = 2000 ads — far beyond any real shop
    const clicked = await execInTab(tabId, () => {
      const btn = [...document.querySelectorAll("button")]
        .find(b => /toon\s+\d+\s+volgende/i.test(b.textContent || "") && !b.disabled);
      if (!btn) return false;
      btn.click();
      return true;
    });
    if (!clicked) return;
    await sleep(1200); // let the next batch render before looking again
  }
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
    openWorkerTab(overviewUrl, t =>
      t ? res(t.id) : rej(new Error("could not open worker tab"))
    )
  );

  try {
    await waitForTabLoad(tabId);
    await sleep(3000); // let React fully render listings
    await expandMp2dhOverview(tabId); // load ALL ads, not just the first 50

    // Find the listing's row and SELECT its checkbox. The "Mijn zoekertjes"
    // overview has NO per-card kebab/options menu — deletion is bulk-style:
    // tick the row's checkbox, then click the single red "Verwijder" button at
    // the top of the list, then confirm. (The old code hunted for an options
    // button that doesn't exist, clicked the last card button — "Omhoog
    // bellen"/"Sneller verkopen" — and removed nothing.)
    const findResult = await execInTab(tabId, (rawTitle, listingId) => {
      // How many ads the page actually rendered. This is what separates "this
      // listing is genuinely gone" from "the page never loaded / we're logged
      // out / the markup changed" — the two used to be indistinguishable, and
      // the second was silently reported as a successful delete.
      const rendered = new Set(
        [...document.querySelectorAll('a[href*="/v/"], a[href*="/seller/view/"]')]
          .map(a => ((a.getAttribute("href") || "").match(/(m\d{6,})/) || [])[1])
          .filter(Boolean)
      ).size;

      const rowFor = el => {
        // Walk up until we reach an ancestor row that holds the row's OWN
        // selection checkbox. Every row also contains hidden feature checkboxes
        // ("Bel omhoog" = input#up-call-select-<adId>), so match the selection
        // one explicitly instead of taking whichever checkbox comes first.
        let n = el;
        for (let i = 0; i < 12 && n; i++) {
          const cb = n.querySelector('input.verkopen-select, input[data-testid="select-ad-checkbox"]');
          if (cb) return cb;
          n = n.parentElement;
        }
        return null;
      };

      // Anchor on the listing ID first. Every row's own links carry it
      // (/v/kleding-heren/schoenen/m2423718603-1333-grijze-…), so it identifies
      // exactly one ad — unlike the title text, which is translated per
      // platform, SKU-prefixed and truncated on the page, and which matched on
      // its first 18 characters only (two "Grijze Profuomo …" ads collide).
      let checkbox = null;
      if (listingId) {
        // The selection checkbox carries the ad id itself (data-ad-id="m2423718603"),
        // so go straight to it — no DOM walking, no ambiguity.
        checkbox = document.querySelector(`input.verkopen-select[data-ad-id="${listingId}"]`);
        if (!checkbox) {
          for (const a of document.querySelectorAll(`a[href*="${listingId}"]`)) {
            checkbox = rowFor(a);
            if (checkbox) break;
          }
        }
      }

      // Fallback: match on title text, for ads listed before an id was recorded.
      // Titles on the overview are prefixed with the SKU, e.g. "(1323) Grijze
      // Suitsupply Cardigan …", so both sides drop a leading "(digits)" first.
      if (!checkbox) {
        const strip = s => (s || "").replace(/^\s*\(\d+\)\s*/, "").replace(/\s+/g, " ").trim().toLowerCase();
        const shortWant = strip(rawTitle).substring(0, 18);
        if (shortWant) {
          const titleEl = [...document.querySelectorAll("a, h1, h2, h3, span, p, div")]
            .filter(el => el.children.length === 0 && el.textContent.trim())
            .find(el => {
              const t = strip(el.textContent);
              return t && (t.startsWith(shortWant) || t.includes(shortWant));
            });
          if (titleEl) checkbox = rowFor(titleEl);
        }
      }

      if (!checkbox) return { found: false, rendered };
      if (!checkbox.checked) {
        checkbox.click();
        // Some React lists ignore a bare .click() — nudge with events too.
        checkbox.dispatchEvent(new Event("input", { bubbles: true }));
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return { found: true, rendered, selected: !!checkbox.checked };
    }, [title, listingId]);

    if (!findResult?.found) {
      // An empty overview proves nothing — we can't tell "already sold/removed"
      // from "not logged in" or "markup changed", and guessing "gone" here is
      // what marked listings delisted in the dashboard while they stayed live.
      if (!findResult?.rendered) {
        throw new Error(
          `Couldn't read your ${platform} listings overview — no ads rendered on ${overviewUrl}. ` +
          `Make sure you're still logged in on ${platform}. Nothing was deleted.`
        );
      }
      // Genuinely not among the ads that ARE listed = already gone. For a
      // delete/sold that IS the goal, so complete cleanly instead of erroring.
      console.log(`[Omnivaleur] bgDelete: "${title}" not among ${findResult.rendered} ${platform} ads — already gone, marking done`);
      await finaliseJob(serverUrl, job.id, "complete", { note: "already_absent" });
      return;
    }
    if (!findResult.selected) {
      throw new Error(`Found "${title}" but couldn't tick its checkbox to delete it.`);
    }

    await sleep(600);

    // Click the top "Verwijder" (trash) button — now enabled by the selection.
    const clickedDelete = await execInTab(tabId, () => {
      const el = [...document.querySelectorAll("button, a")]
        .find(e => /^\s*(🗑\s*)?verwijder(en)?\s*$/i.test(e.textContent.trim()) && !e.disabled);
      if (el) { el.click(); return true; }
      return false;
    });

    if (!clickedDelete) throw new Error("Top 'Verwijder' button not found or disabled — selection may not have registered");

    await sleep(900);

    // Confirm dialog. Verified live 2026-07 on marktplaats.nl: clicking the top
    // Verwijder opens a ReactModal asking "Heb je "<titel>" verkocht via
    // Marktplaats?" with exactly two buttons — "Niet verkocht via Marktplaats"
    // and "Verkocht via Marktplaats". NEITHER contains "verwijderen", so the old
    // regex matched nothing inside the dialog. On top of that the old scope
    // selector's [class*="odal"] matched <body class="ReactModal__Body--open">
    // first, so "scope" became the whole page and the search fell back to the
    // toolbar's own Verwijder button. The modal simply stayed open and NOTHING
    // was ever deleted — the same silent failure for the delist AND for the
    // relist ("hard refresh"), whose first step is this delete.
    //
    // We always answer "Niet verkocht via <platform>": every delete we drive is
    // either a sold-elsewhere delist or a relist, so the ad was not sold through
    // this platform. Clicking the other button would file a false sale on the
    // user's account.
    const CONFIRM_STEPS = 3; // MP has added follow-up screens before; handle a short chain
    for (let step = 0; step < CONFIRM_STEPS; step++) {
      const res = await execInTab(tabId, () => {
        // .ReactModalPortal is the real dialog root. Never match on <body>.
        const modal = [...document.querySelectorAll('.ReactModalPortal, [role="dialog"], [aria-modal="true"]')]
          .find(el => el.getClientRects().length > 0 && (el.innerText || "").trim());
        if (!modal) return { open: false };
        const buttons = [...modal.querySelectorAll('button, a[role="button"]')]
          .filter(b => !b.disabled && (b.textContent || "").trim());
        const labels = buttons.map(b => b.textContent.trim().replace(/\s+/g, " "));
        const pick =
          // Step 1: the "sold via this platform?" question — decline it.
          buttons.find(b => /niet\s+verkocht/i.test(b.textContent)) ||
          // Any follow-up screen: a plain confirm. "annuleren"/"terug" excluded.
          buttons.find(b => /^(ja|verwijder(en)?|bevestig(en)?|doorgaan|ok)\b/i.test(b.textContent.trim()));
        if (!pick) return { open: true, clicked: false, labels };
        pick.click();
        return { open: true, clicked: true, picked: pick.textContent.trim(), labels };
      });

      if (!res || !res.open) break; // dialog gone — either answered, or none appeared
      if (!res.clicked) {
        throw new Error(
          `The ${platform} delete dialog had no button this extension recognises ` +
          `(saw: ${(res.labels || []).join(" | ") || "no buttons"}). Nothing was deleted — ` +
          `${platform} likely changed this screen.`
        );
      }
      console.log(`[Omnivaleur] bgDelete: confirm step ${step + 1} → clicked "${res.picked}"`);
      await sleep(1500);
    }

    // Verify the listing is actually gone before reporting success — without
    // this the job was marked "done" (DB set to "delisted") even when nothing
    // was removed. Reload the overview to be sure it's not a stale DOM.
    await new Promise(res => chrome.tabs.reload(tabId, {}, res));
    await waitForTabLoad(tabId);
    await sleep(2500);
    // Expand here too: only the first 50 ads render, so on a shop with more than
    // that an ad sitting at #51+ is simply absent from the DOM — which this check
    // would read as "successfully deleted" and report a false success.
    await expandMp2dhOverview(tabId);

    const stillPresent = await execInTab(tabId, (rawTitle, listingId) => {
      const strip = s => (s || "").replace(/^\s*\(\d+\)\s*/, "").replace(/\s+/g, " ").trim().toLowerCase();
      const want = strip(rawTitle);
      const shortWant = want.substring(0, 18);
      if (!shortWant) return false;
      const leaves = [...document.querySelectorAll("a, h1, h2, h3, span, p, div")]
        .filter(el => el.children.length === 0 && el.textContent.trim());
      let titleEl = leaves.find(el => {
        const t = strip(el.textContent);
        return t && (t.startsWith(shortWant) || t.includes(shortWant));
      });
      if (!titleEl && listingId) {
        titleEl = document.querySelector(`a[href*="${listingId}"]`);
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
// Resolve a Vinted numeric item id from a listing TITLE when no
// platform_listing_id is known (e.g. items the user marked "published" by hand).
// Mirrors bgScanVinted: open the wardrobe on the real country origin, find the
// member id, page the whole wardrobe and match the title with a resilient
// first-N-chars startsWith/includes compare (titles may be truncated/decorated).
// Returns { id, origin } or { id: null }.
async function resolveVintedIdByTitle(title) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const tabId = await new Promise((res, rej) =>
    openWorkerTab("https://www.vinted.nl/", t =>
      t ? res(t.id) : rej(new Error("could not open worker tab"))
    )
  );
  try {
    await waitForTabLoad(tabId);
    await sleep(2500);

    // Open the account menu — the numeric member id (/member/{id}) and the real
    // country origin are only exposed once the avatar dropdown is opened.
    await execInTab(tabId, () => {
      document.querySelector('#user-menu-button, [data-testid="user-menu-button"]')?.click();
    });
    await sleep(600);

    const idInfo = await execInTab(tabId, () => {
      let userId = null, origin = null;
      for (const link of document.querySelectorAll('a[href*="/member/"]')) {
        const m = (link.getAttribute("href") || "").match(/\/member\/(\d+)(?:[/?]|$)/);
        if (m) {
          userId = m[1];
          try { origin = new URL(link.getAttribute("href"), location.href).origin; } catch (e) { origin = location.origin; }
          break;
        }
      }
      return { userId, origin };
    });

    if (!idInfo?.userId) return { id: null };

    // Navigate to the home-country origin so the wardrobe fetch is same-origin.
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

    const found = await execInTab(tabId, async (userId, wantTitle) => {
      const norm = s => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
      const want = norm(wantTitle);
      const short = want.substring(0, 20);
      const matches = t => {
        const c = norm(t);
        if (!c || !short) return false;
        return c.startsWith(short) || c.includes(short) || want.includes(c.substring(0, 20));
      };
      try {
        for (let page = 1; page <= 60; page++) {
          const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=96`, { headers: { Accept: "application/json" } });
          if (!res.ok) return null;
          const data = await res.json();
          if (data.code && data.code !== 0) return null;
          const items = data.items || [];
          const hit = items.find(it => matches(it.title));
          if (hit) return String(hit.id);
          const pg = data.pagination || {};
          if (items.length === 0) return null;
          if (pg.total_pages && page >= pg.total_pages) return null;
          if (!pg.total_pages && items.length < 96) return null;
        }
        return null;
      } catch (e) { return null; }
    }, [idInfo.userId, title]);

    return { id: found || null, origin: idInfo.origin };
  } finally {
    setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2500);
  }
}

async function bgDeleteVinted(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const payload = job.payload || {};
  let listingId = payload.platform_listing_id;
  let resolvedOrigin = "";
  // Fallback: no id (e.g. a listing the user marked "published" by hand) — locate
  // it in the wardrobe by title, then run the existing delete-by-id flow verbatim.
  if (!listingId) {
    const title = (payload.title || "").trim();
    if (!title) throw new Error("Vinted delete: no platform_listing_id and no title in payload");
    const resolved = await resolveVintedIdByTitle(title);
    if (!resolved?.id) {
      throw new Error(`Could not locate "${title}" on Vinted to delist it. Open the listing on Vinted and use "mark as published" (paste its link) so it can be delisted.`);
    }
    listingId = resolved.id;
    resolvedOrigin = resolved.origin || "";
  }
  const url = payload.platform_listing_url
    || (resolvedOrigin ? `${resolvedOrigin}/items/${listingId}` : `https://www.vinted.com/items/${listingId}`);

  const tabId = await new Promise((res, rej) =>
    openWorkerTab(url, t =>
      t ? res(t.id) : rej(new Error("could not open worker tab"))
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
    openWorkerTab("https://www.vinted.nl/", t =>
      t ? res(t.id) : rej(new Error("could not open worker tab"))
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
      // Page through the WHOLE wardrobe.
      //
      // Vinted CAPS per_page at 96 and silently ignores anything larger. The old
      // code asked for 200 and then stopped as soon as a page came back "short"
      // (< 200) — which page 1 always is. So every scan read exactly the newest
      // 96 listings and quietly dropped the rest; a 518-item wardrobe imported
      // 96. Never infer the last page from the size we ASKED for: use the size
      // the server actually used, plus its own pagination metadata.
      const PER_PAGE = 96;          // Vinted's real maximum
      const MAX_PAGES = 200;        // safety net only (≈19k listings)
      const rawItems = [];
      const seenIds = new Set();    // newest_first can shift under us between pages
      let totalEntries = null;      // what Vinted says the wardrobe holds
      let totalPages = null;
      let pagesRead = 0;
      let truncatedReason = null;   // non-null ⇒ the snapshot is INCOMPLETE

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
          // First page failing is fatal; a later page failing means we have a
          // PARTIAL wardrobe — record that, because a partial snapshot must
          // never be treated as "everything that's still live".
          if (page === 1) return { error: `Vinted returned HTTP ${res.status} while listing your items (user id ${userId}, ${location.origin}).` };
          truncatedReason = `page ${page} returned HTTP ${res.status}`;
          break;
        }
        data = await res.json();
        if (data.code && data.code !== 0) {
          if (page === 1) return { error: `Vinted API error: ${data.message_code || data.code}` };
          truncatedReason = `page ${page} returned API code ${data.message_code || data.code}`;
          break;
        }
        const pag = data.pagination || null;
        if (pag) {
          if (pag.total_entries != null) totalEntries = pag.total_entries;
          if (pag.total_pages != null) totalPages = pag.total_pages;
        }
        const pageItems = data.items || [];
        for (const it of pageItems) {
          if (it && it.id != null && !seenIds.has(it.id)) { seenIds.add(it.id); rawItems.push(it); }
        }
        pagesRead = page;

        if (!pageItems.length) break;                       // ran off the end
        if (totalPages != null && page >= totalPages) break; // server says we're done
        // No metadata to go on: fall back to the size the SERVER used for this
        // page, not the size we requested.
        if (totalPages == null && pageItems.length < (pag?.per_page || PER_PAGE)) break;
        if (page === MAX_PAGES) truncatedReason = `hit the ${MAX_PAGES}-page safety cap`;
        await nap(300); // gentle pacing between pages
      }

      // Cross-check against Vinted's own count. If they disagree, the snapshot
      // is not authoritative and the server must not use it to decide what sold.
      if (!truncatedReason && totalEntries != null && rawItems.length < totalEntries) {
        truncatedReason = `fetched ${rawItems.length} of ${totalEntries} listings`;
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
          // Vinted's own state flags. Sold/ended listings STAY in the wardrobe
          // as is_closed — they don't vanish — so these are what tells us a
          // listing is really gone, instead of inferring it from absence.
          is_closed: !!it.is_closed,
          is_hidden: !!it.is_hidden,
          is_draft: !!it.is_draft,
        };
      });
      return {
        items,
        // Everything the server needs to judge how much to trust this snapshot.
        meta: {
          complete: !truncatedReason,
          truncated_reason: truncatedReason,
          total_entries: totalEntries,
          fetched: rawItems.length,
          pages_read: pagesRead,
        },
      };
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
    // Only enrich listings that are actually still for sale. Sold/ended ones are
    // still in the wardrobe (is_closed) and are shipped to the server for the
    // sale reconcile, but nobody is going to import them — fetching a detail
    // page for each would triple the scan time for data no one reads.
    const toEnrich = result.items.filter(it => !it.is_closed && !it.is_draft);
    const total = toEnrich.length;
    const skipped = result.items.length - total;
    await reportProgress(serverUrl, job.id, {
      stage: "enriching",
      message: `Found ${result.items.length} listings (${total} still for sale) — fetching full details…`,
      current: 0, total,
    });
    let enriched = 0;
    try {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      const startedAt = Date.now();
      const noDesc = [];
      let idx = 0;
      for (const it of toEnrich) {
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
    // scan_meta travels with the results: the server uses `complete` to decide
    // whether this snapshot may be trusted to mark listings as sold.
    await finaliseJob(serverUrl, job.id, "complete", {
      listings: result.items,
      scan_meta: result.meta || null,
    });
    console.log(
      `[Omnivaleur] Vinted scan: ${result.items.length} listings ` +
      `(${total} for sale, ${skipped} closed/draft, enriched ${enriched}) ` +
      `complete=${result.meta?.complete} ${result.meta?.truncated_reason || ""}`
    );
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
    openWorkerTab(overviewUrl, t =>
      t ? res(t.id) : rej(new Error("could not open worker tab"))
    )
  );

  try {
    await waitForTabLoad(tabId);
    await sleep(3000); // let React fully render listings

    const result = await execInTab(tabId, async () => {
      const nap = ms => new Promise(r => setTimeout(r, ms));
      const abs = u => !u ? null : (u.startsWith("http") ? u : `${location.origin}${u.startsWith("/") ? "" : "/"}${u}`);

      // ── Primary: the page's own JSON API ──────────────────────────────
      // The overview is React-rendered and only ever paints ~50 rows, so
      // scraping the DOM could never see a bigger account (127 listings here).
      // It feeds from /my-account/sell/api/listings, which returns
      // { ads: [...], totalNumberOfResults: N } and pages via
      // batchNumber (1-BASED — batch 0 and 1 both return the first page)
      // and batchSize. Verified live: batchSize is honoured up to at least 200.
      const API = "/my-account/sell/api/listings";
      const BATCH = 100;
      const MAX_BATCHES = 200;
      const byId = new Map();
      let totalExpected = null;
      let truncatedReason = null;

      try {
        for (let batch = 1; batch <= MAX_BATCHES; batch++) {
          let res = null;
          for (let attempt = 0; attempt < 3; attempt++) {
            res = await fetch(`${API}?batchNumber=${batch}&batchSize=${BATCH}`, {
              headers: { Accept: "application/json" }, credentials: "include",
            });
            if (res.ok) break;
            if (res.status !== 429 && res.status < 500) break;
            await nap(1000 * Math.pow(2, attempt));
          }
          if (!res || !res.ok) {
            if (batch === 1) { truncatedReason = `API HTTP ${res ? res.status : "?"}`; break; }
            truncatedReason = `batch ${batch} returned HTTP ${res.status}`;
            break;
          }
          const data = await res.json();
          if (data.totalNumberOfResults != null) totalExpected = data.totalNumberOfResults;
          const ads = data.ads || [];
          let added = 0;
          for (const ad of ads) {
            const id = ad.itemId;
            if (!id || byId.has(id)) continue;
            byId.set(id, {
              platform_listing_id: String(id),
              title: ad.title || "",
              // priceCents is an integer in cents — /100, never parsed from text.
              price: ad.priceCents != null ? Number(ad.priceCents) / 100 : null,
              photo_url: abs(ad.primaryImageUrl),
              platform_listing_url: abs(ad.vipUrl || ad.sVipUrl),
              category_name: ad.categoryName || "",
              is_reserved: !!ad.reserved,
              status: ad.status || "",
            });
            added++;
          }
          if (!ads.length) break;                                   // ran off the end
          if (totalExpected != null && byId.size >= totalExpected) break;  // got them all
          if (!added) break;                                        // no new ids — stop rather than loop
          if (batch === MAX_BATCHES) truncatedReason = `hit the ${MAX_BATCHES}-batch safety cap`;
          await nap(250);
        }
      } catch (e) {
        truncatedReason = `API error: ${String(e && e.message || e)}`;
      }

      // ── Fallback: read whatever the page rendered ─────────────────────
      // Only if the API gave us nothing (different market, endpoint moved).
      // NOTE the container is div.row.ad-listing — the old code looked for
      // "li, article", which this page simply has none of, so it found zero.
      let usedFallback = false;
      if (!byId.size) {
        usedFallback = true;
        const rows = document.querySelectorAll("div.row.ad-listing");
        const cards = rows.length ? [...rows] : [...document.querySelectorAll("li, article, div")].filter(el =>
          el.querySelectorAll('a[href*="/v/"]').length === 1 && /€\s?\d/.test(el.textContent));
        for (const card of cards) {
          const link = card.querySelector('a[href*="/v/"]');
          if (!link) continue;
          const href = link.getAttribute("href") || "";
          const id = (href.match(/(m\d{6,})/) || [])[1];
          if (!id || byId.has(id)) continue;
          const titleEl = [...card.querySelectorAll("*")].find(el =>
            el.children.length === 0 && el.textContent.trim().length > 5 && el.textContent.trim().length < 120);
          const priceMatch = card.textContent.match(/€\s?([\d.,]+)/);
          const img = card.querySelector("img");
          byId.set(id, {
            platform_listing_id: id,
            title: (titleEl?.textContent || "").trim(),
            price: priceMatch ? Number(priceMatch[1].replace(/\./g, "").replace(",", ".")) : null,
            photo_url: img?.src || null,
            platform_listing_url: abs(href),
          });
        }
        // The DOM only ever holds the rendered page, so this is never complete
        // unless it happens to match the total the page advertises.
        const shown = (document.body.innerText.match(/advertenties\s*\((\d+)\)/i) || [])[1];
        if (shown != null) totalExpected = Number(shown);
        if (!truncatedReason) truncatedReason = "read from the page instead of the API";
      }

      const items = [...byId.values()];
      if (!truncatedReason && totalExpected != null && items.length < totalExpected) {
        truncatedReason = `found ${items.length} of ${totalExpected} listings`;
      }
      return {
        items,
        meta: {
          complete: !truncatedReason,
          truncated_reason: truncatedReason,
          total_entries: totalExpected,
          fetched: items.length,
          source: usedFallback ? "dom" : "api",
        },
      };
    });

    if (!result || !result.items) throw new Error("Could not read your listings overview — page structure may have changed.");
    if (!result.items.length) throw new Error("No listings found on your overview — are you logged in on this account?");
    await reportProgress(serverUrl, job.id, {
      stage: "enriching",
      message: `Found ${result.items.length} listings — fetching full details…`,
      current: 0, total: result.items.length,
    });

    // The overview cards only expose title/price/thumbnail. Enrich each listing
    // by fetching its own page (same-origin) and reading the JSON-LD Product +
    // description block, so the import carries the full description and every
    // photo — not just the first one. Best-effort per listing: any failure just
    // leaves that candidate with the basic card data.
    // One SHORT executeScript per listing, driven from here — never a single
    // long one. An MV3 service worker awaiting one multi-minute call gets
    // terminated by Chrome, which would kill the whole scan before it reports
    // anything. (The old code did all of them in one call, capped at 100, so a
    // bigger account was silently cut off AND at risk of being killed.)
    const total = result.items.length;
    let enriched = 0;
    const startedAt = Date.now();
    try {
      for (let i = 0; i < result.items.length; i++) {
        const it = result.items[i];
        let e = null;
        try {
          e = await execInTab(tabId, async (url) => {
            const nap = ms => new Promise(r => setTimeout(r, ms));
            for (let attempt = 0; attempt < 3; attempt++) {
              try {
                const res = await fetch(url, { headers: { Accept: "text/html" }, credentials: "include" });
                if (!res.ok) {
                  if (res.status !== 429 && res.status < 500) return null;
                  await nap(800 * Math.pow(2, attempt));
                  continue;
                }
                const html = await res.text();
                const decode = s => { try { return JSON.parse('"' + s.replace(/"/g, '\\"') + '"'); } catch (e2) { return s; } };
                const unesc = s => s.replace(/\\u002F/gi, "/").replace(/\\\//g, "/");

                // The listing page is client-rendered: there is NO JSON-LD and no
                // description element in the fetched HTML (the old code looked for
                // both and always came back empty). The text IS there, inside the
                // embedded __CONFIG__ state. Several "description" keys exist — UI
                // chrome like menu entries and shipping options — so take the
                // LONGEST, which is reliably the advert itself.
                let description = "";
                for (const m of html.matchAll(/"description"\s*:\s*"((?:[^"\\]|\\.)*)"/g)) {
                  const v = decode(m[1]);
                  if (v && v.length > description.length) description = v;
                }

                // Photos live in an "imageUrls" array as protocol-relative,
                // /-escaped URLs with a "$_" size-rule placeholder.
                const photos = [];
                const im = html.match(/"imageUrls"\s*:\s*\[([^\]]*)\]/);
                if (im) {
                  for (const m of im[1].matchAll(/"((?:[^"\\]|\\.)*)"/g)) {
                    let u = unesc(decode(m[1]));
                    if (!u) continue;
                    if (u.startsWith("//")) u = "https:" + u;
                    u = u.replace(/\$_/, "85"); // large variant
                    if (/^https?:\/\//.test(u)) photos.push(u);
                  }
                }
                return { description: description.trim().slice(0, 4000), photo_urls: [...new Set(photos)] };
              } catch (e3) {
                await nap(500 * Math.pow(2, attempt));
              }
            }
            return null;
          }, [it.platform_listing_url]);
        } catch (e4) { e = null; }

        if (e) {
          enriched++;
          if (e.description) it.description = e.description;
          if (e.photo_urls && e.photo_urls.length) {
            it.photo_urls = e.photo_urls;
            it.photo_url = it.photo_url || e.photo_urls[0];
          }
        }
        const perItem = ((Date.now() - startedAt) / 1000) / (i + 1);
        await reportProgress(serverUrl, job.id, {
          stage: "enriching",
          message: `Fetching details ${i + 1}/${total}…`,
          current: i + 1, total,
          eta_seconds: Math.max(0, Math.round(perItem * (total - i - 1))),
        });
        await sleep(150); // gentle, and keeps the worker warm
      }
    } catch (e) {
      console.warn(`[Omnivaleur] ${platform} enrichment aborted, sending list data only:`, e);
    }

    await reportProgress(serverUrl, job.id, {
      stage: "saving", message: "Saving to your dashboard…", current: total, total,
    });
    await finaliseJob(serverUrl, job.id, "complete", {
      listings: result.items,
      scan_meta: result.meta || null,
    });
    console.log(
      `[Omnivaleur] ${platform} scan: ${total} listings (enriched ${enriched}) ` +
      `via ${result.meta?.source} complete=${result.meta?.complete} ${result.meta?.truncated_reason || ""}`
    );
  } finally {
    setTimeout(() => chrome.tabs.remove(tabId).catch(() => {}), 2500);
  }
}

// Closing a job tab means that job's meta is dead. Without this, jobtab_ keys
// pile up forever — and because Chrome reuses tab ids after a restart, a brand
// new tab could inherit a stale entry and complete the wrong job.
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.remove(`jobtab_${tabId}`);
  clearJobWatchdog(tabId);
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
  clearJobWatchdog(tabId);
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
      if (!resp?.ok) {
        console.warn(`[Omnivaleur][sold] ${platform}: could not fetch active listings (HTTP ${resp?.status || "no response"}) — skipping`);
        continue;
      }
      const allListings = await resp.json();
      const active = allListings.filter(l => l.platform === platform && l.status === "active");
      const withId = active.filter(l => l.platform_listing_id);
      const withoutId = active.filter(l => !l.platform_listing_id);
      console.log(`[Omnivaleur][sold] ${platform}: ${active.length} active listings (${withId.length} with a platform id, ${withoutId.length} without an id → matched by title)`);
      if (!active.length) continue;

      // Scrape the ads overview and read each ad's SOLD marker. We only act on a
      // POSITIVE "verkocht/gereserveerd" label — never on a listing merely being
      // absent, which on Marktplaats also means "expired" (auto-relisted later)
      // and would wrongly delist a still-live item everywhere. Fail-safe: if no
      // ad shows a sold label, nothing happens.
      console.log(`[Omnivaleur][sold] ${platform}: opening sold-overview ${soldUrl}`);
      const ads = await scrapeMarktplaatsAds(soldUrl, platform);
      const soldAds = ads.filter(a => a.sold);
      const soldIds = new Set(soldAds.map(a => a.id).filter(Boolean));
      // Normalised sold-ad titles for title-based matching (listings without an id).
      const soldTitles = soldAds.map(a => (a.title || "").toLowerCase().trim()).filter(Boolean);
      console.log(`[Omnivaleur][sold] ${platform}: ${ads.length} ad cards scraped, ${soldAds.length} carry a sold/reserved label`);
      if (!soldAds.length) continue;

      let triggered = 0;
      for (const listing of active) {
        // Match a sold ad either by exact platform id, or — for listings without
        // an id — by a resilient title match against a POSITIVELY sold ad. We
        // NEVER infer a sale from absence; only a positive sold label acts.
        let isSold = listing.platform_listing_id && soldIds.has(listing.platform_listing_id);
        if (!isSold && !listing.platform_listing_id && listing.title) {
          const lt = listing.title.toLowerCase().trim();
          const key = lt.substring(0, 20);
          isSold = key.length >= 8 && soldTitles.some(st => st.startsWith(key) || st.includes(key));
          if (isSold) console.log(`[Omnivaleur][sold] ${platform}: matched sold ad by TITLE for "${listing.title}" (no platform id)`);
        }
        if (isSold) {
          triggered++;
          console.log(`[Omnivaleur][sold] ${platform}: SOLD confirmed (positive label) item_id=${listing.item_id} id=${listing.platform_listing_id || "—"} → triggering cross-platform delist`);
          const r = await fetch(`${serverUrl}/api/listings/sold?item_id=${listing.item_id}&platform=${platform}`, {
            method: "POST",
            headers: authHeaders,
          }).catch(e => { console.error("[Omnivaleur][sold] sold POST failed:", e); return null; });
          console.log(`[Omnivaleur][sold] ${platform}: POST /api/listings/sold → HTTP ${r?.status ?? "no response"}`);
        }
      }
      console.log(`[Omnivaleur][sold] ${platform}: ${triggered} listing(s) triggered delist this cycle`);
    } catch (e) {
      console.error(`[Omnivaleur][sold] sold-check error (${platform}):`, e);
    }
  }
}

// Scrape each ad card on the Marktplaats/2dehands "my ads" overview and report
// whether it carries an explicit SOLD/RESERVED label. Returns [{id, title, sold}].
// The title lets us match sold ads to listings that have no platform id.
function scrapeMarktplaatsAds(url, platform) {
  return new Promise((resolve) => {
    openWorkerTab(url, (tab) => {
      if (!tab) { resolve([]); return; }
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
              const raw = card.innerText || "";
              const text = raw.toLowerCase();
              const sold = /\bverkocht\b|\bgereserveerd\b|\bsold\b|\breserved\b/.test(text);
              // Prefer the link's own text as the title, fall back to the card's first line.
              const title = (a.innerText || raw.split("\n")[0] || "").trim();
              const prev = byId[id];
              if (!prev) byId[id] = { id, title, sold };
              else { if (sold) prev.sold = true; if (!prev.title && title) prev.title = title; }
            });
            const ads = Object.values(byId);
            // Diagnostic: if NOTHING shows a sold label, capture what the page
            // structure / section labels actually look like so we can confirm
            // whether sold ads even live on this view (they may sit behind a
            // separate status filter/tab). Also dump a couple of raw card texts.
            let diag = null;
            if (!ads.some(x => x.sold)) {
              const labels = [...document.querySelectorAll('nav a, [role="tab"], button, [class*="tab" i], [class*="filter" i]')]
                .map(el => (el.innerText || "").replace(/\s+/g, " ").trim())
                .filter(t => t && t.length < 40).slice(0, 25);
              const sampleCards = [...document.querySelectorAll('article, li[class*="listing" i], [class*="ad" i]')]
                .map(el => (el.innerText || "").replace(/\s+/g, " ").trim()).filter(Boolean).slice(0, 3);
              diag = { pageTitle: document.title, tabOrFilterLabels: labels, sampleCards };
            }
            return { ads, diag };
          },
        }, (results) => {
          chrome.tabs.remove(tabId).catch(() => {});
          const out = results?.[0]?.result || { ads: [], diag: null };
          const ads = out.ads || [];
          console.log(`[Omnivaleur][sold] ${platform}: scraper found ${ads.length} ad cards (sold-labelled: ${ads.filter(a => a.sold).length})`);
          if (out.diag) {
            console.warn(`[Omnivaleur][sold] ${platform}: ZERO sold labels on this page. This is the PRIME SUSPECT — sold ads may live behind a separate status filter/tab, so this default overview never shows them. Page structure follows so we can find the right view:`);
            console.warn(`[Omnivaleur][sold] ${platform}: tab/filter labels on page:`, out.diag.tabOrFilterLabels);
            console.warn(`[Omnivaleur][sold] ${platform}: sample raw card text:`, out.diag.sampleCards);
          }
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
    const ordersUrl = "https://www.vinted.nl/my_orders";
    console.log(`[Omnivaleur][sold] Vinted: opening orders page ${ordersUrl}`);
    const orders = await scrapeVintedOrders(ordersUrl);
    console.log(`[Omnivaleur][sold] Vinted: ${orders.length} order(s) with a parseable (SKU) scraped:`, orders);
    if (!orders.length) {
      console.warn("[Omnivaleur][sold] Vinted: no orders scraped — either no sales, not logged in, or the orders-page selectors no longer match (see scraper logs above)");
      return;
    }
    // Re-fetch headers here (not the ones captured before the multi-second
    // scrape): getAuthHeaders proactively refreshes, so the POST always goes out
    // with a token that isn't about to expire — this is what fixed the
    // "reconcile → 401 Sessie verlopen" the scan kept hitting.
    const postHeaders = await getAuthHeaders();
    const r = await fetch(`${serverUrl}/api/listings/reconcile-vinted-orders`, {
      method: "POST",
      headers: postHeaders,
      body: JSON.stringify({ orders }),
    }).catch(e => { console.error("[Omnivaleur][sold] Vinted reconcile POST failed:", e); return null; });
    let bodyText = "";
    try { bodyText = r ? await r.text() : ""; } catch (_) {}
    console.log(`[Omnivaleur][sold] Vinted: POST /api/listings/reconcile-vinted-orders → HTTP ${r?.status ?? "no response"} body=${bodyText}`);
  } catch (e) {
    console.error("[Omnivaleur][sold] checkVintedOrders error:", e);
  }
}

function scrapeVintedOrders(url) {
  return new Promise((resolve) => {
    openWorkerTab(url, (tab) => {
      if (!tab) { resolve([]); return; }
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
              // Each order row links to its conversation (/inbox/…). Vinted has,
              // however, changed this markup before, so we look for order rows via
              // several selectors and de-duplicate. A row only ever counts as a
              // sale when it has a parseable "(1234)" SKU AND is not cancelled/
              // refunded — so a broader net can't create a false positive.
              const selectors = [
                'a[href*="/inbox/"]',
                'a[href*="/order"]',
                'a[href*="/transaction"]',
                '[class*="order" i]',
                '[data-testid*="order" i]',
              ];
              const anchors = new Set();
              const selectorHits = {};
              selectors.forEach(sel => {
                const found = document.querySelectorAll(sel);
                selectorHits[sel] = found.length;
                found.forEach(el => anchors.add(el));
              });

              const rows = {};
              anchors.forEach(el => {
                const row = el.closest('div, li, article') || el;
                const text = (row.innerText || el.innerText || "").replace(/\s+/g, " ").trim();
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
              return { orders: Object.values(rows), selectorHits, rowCandidates: anchors.size };
            },
          }, (results) => {
            chrome.tabs.remove(tabId).catch(() => {});
            const out = results?.[0]?.result || { orders: [], selectorHits: {}, rowCandidates: 0 };
            const orders = out.orders || [];
            console.log(`[Omnivaleur][sold] Vinted: selector hits`, out.selectorHits, `→ ${out.rowCandidates} candidate row(s), ${orders.length} with a (SKU) (sold: ${orders.filter(o => o.sold).length})`);
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
    openWorkerTab(url, (tab) => {
      if (!tab) { resolve(null); return; }
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

  // Verifying only that SOME text landed is not enough: Marktplaats's editor
  // silently ignores execCommand("insertParagraph"), so every line got
  // concatenated into one glued paragraph ("…kopen!Dit item…") while lexHasText()
  // still reported success — which is exactly how descriptions shipped as one
  // solid block. Require the line structure to survive too, otherwise fall
  // through to the strategies/approaches below that build real paragraphs.
  const _wantLines = _lines.filter((l) => l.trim().length > 0).length;
  function structureOk() {
    if (!lexHasText()) return false;
    if (_wantLines <= 1) return true;
    const got = (el.innerText || "").split("\n").filter((l) => l.trim().length > 0).length;
    return got >= _wantLines;
  }

  // ── Approach 1: execCommand (most reliable) ───────────────────────────────
  // execCommand fires a REAL native beforeinput event that Chrome and Lexical
  // both handle natively. InputEvent.dataTransfer is always null for synthetic
  // events in Chrome — execCommand bypasses that problem entirely.
  //
  // CRITICAL: insert LINE BY LINE. Passing the whole multi-line string to a
  // single insertText makes Lexical collapse every "\n", gluing all sentences
  // together. We insert each line and separate them with a real line break so
  // paragraph breaks survive exactly as written. Editors disagree on which
  // break command they honour, so try each and keep the one that actually works.
  try {
    const breakStrategies = [
      () => document.execCommand("insertParagraph", false, null),
      () => document.execCommand("insertText", false, "\n"),
      () => document.execCommand("insertLineBreak", false, null),
      () => document.execCommand("insertHTML", false, "<br>"),
    ];
    for (const insertBreak of breakStrategies) {
      el.focus();
      document.execCommand("selectAll", false, null);
      document.execCommand("delete", false, null);
      for (let i = 0; i < _lines.length; i++) {
        if (i > 0) { try { insertBreak(); } catch (_) {} }
        if (_lines[i].length > 0) document.execCommand("insertText", false, _lines[i]);
      }
      await sleep(300);
      if (structureOk()) return true;
      if (_wantLines <= 1) break; // single-line text — nothing structural to recover
    }
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
        if (structureOk()) return true;
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
    for (const [i, line] of _lines.entries()) {
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
    if (structureOk()) return true;
  } catch (_) {}

  // ── Approach 4: ClipboardEvent paste ─────────────────────────────────────
  // A real paste carries the newlines in text/plain, so editors that ignore
  // every explicit break command usually still reproduce the paragraphs here.
  try {
    const dt = new DataTransfer();
    dt.setData("text/plain", descText);
    el.focus();
    document.execCommand("selectAll", false, null);
    el.dispatchEvent(new ClipboardEvent("paste", {
      clipboardData: dt, bubbles: true, cancelable: true,
    }));
    await sleep(400);
    if (structureOk()) return true;
  } catch (_) {}

  // Every strategy failed to keep the paragraph structure. Text that landed at
  // all still beats an empty description, so report on content as a last resort.
  return lexHasText();
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
    const patch = { authToken: msg.token, userEmail: msg.email || "" };
    // Only overwrite the stored refresh token when the page actually sent one —
    // an older dashboard build syncs just the access token, and we must not wipe
    // a good refresh token we already have.
    if (msg.refresh) patch.refreshToken = msg.refresh;
    chrome.storage.sync.set(patch, () => {
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
      clearJobWatchdog(sender.tab?.id);
      chrome.storage.local.remove([`job_${platform}`, `jobtab_${sender.tab?.id}`]);
      // Keep tab open 2s so user can see the listing was created
      if (sender.tab?.id) setTimeout(() => chrome.tabs.remove(sender.tab.id).catch(() => {}), 2000);
    });
    sendResponse({ ok: true });
  }

  if (msg.type === "JOB_ERROR") {
    const { platform, jobId, serverUrl, error } = msg;
    finaliseJob(serverUrl, jobId, "error", { error }).finally(() => {
      // The tab is intentionally left open for a manual finish, so stand the
      // watchdog down — otherwise it would close that tab mid-edit.
      clearJobWatchdog(sender.tab?.id);
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
