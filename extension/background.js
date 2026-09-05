importScripts("analytics.js");

// Terugvalklok. Chrome staat geen kortere wekker toe dan een halve minuut, dus
// deze 15 wordt in de praktijk 30 — daarom is dit alleen het vangnet. Het echte
// startsein komt van het dashboard (POLL_NOW), meteen nadat er werk is
// klaargezet, en van de ronde zelf zolang die werk blijft vinden.
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
  // === KLEDING | DAMES (cat1 621) ===
  // Alle cat3-waarden hieronder zijn de echte Marktplaats-type-ID's, opgehaald
  // uit de categorieboom van Marktplaats zelf (searchCategoryOptions onder
  // l1CategoryId=621), niet gegokt. Waar eerder geen exacte match bestond stond
  // een noodgreep die inhoudelijk fout was: rokken, broeken en shorts gingen
  // allemaal als Spijkerbroeken en Jeans de deur uit, sportkleding als
  // Winterjas, en t-shirts als Blouse.
  // bucketId 162 = de groep "Kleding", 164 = "Schoenen en Sokken".
  "jeans":                  { cat1: 621,  cat3: 636,  bucketId: 162 },  // Spijkerbroeken en Jeans
  "spijkerbroeken":         { cat1: 621,  cat3: 636,  bucketId: 162 },
  "broeken":                { cat1: 621,  cat3: 629,  bucketId: 162 },  // Broeken en Pantalons
  "shorts":                 { cat1: 621,  cat3: 629,  bucketId: 162 },
  "leggings":               { cat1: 621,  cat3: 629,  bucketId: 162 },
  "rokken":                 { cat1: 621,  cat3: 635,  bucketId: 162 },  // Rokken
  "jurken":                 { cat1: 621,  cat3: 631,  bucketId: 162 },  // Jurken
  "jurken casual":          { cat1: 621,  cat3: 631,  bucketId: 162 },
  "jurken feest":           { cat1: 621,  cat3: 631,  bucketId: 162 },
  "blouses":                { cat1: 621,  cat3: 628,  bucketId: 162 },  // Blouses en Tunieken
  "blouses en tunieken":    { cat1: 621,  cat3: 628,  bucketId: 162 },
  "t-shirts":               { cat1: 621,  cat3: 637,  bucketId: 162 },  // T-shirts
  "tops":                   { cat1: 621,  cat3: 638,  bucketId: 162 },  // Tops
  "polo's":                 { cat1: 621,  cat3: 638,  bucketId: 162 },  // Dames kennen geen Polo's-type
  "polo":                   { cat1: 621,  cat3: 638,  bucketId: 162 },
  "truien":                 { cat1: 621,  cat3: 640,  bucketId: 162 },  // Truien en Vesten
  "truien / vesten":        { cat1: 621,  cat3: 640,  bucketId: 162 },
  "vesten":                 { cat1: 621,  cat3: 640,  bucketId: 162 },
  "hoodies":                { cat1: 621,  cat3: 640,  bucketId: 162 },
  "unisex truien":          { cat1: 621,  cat3: 640,  bucketId: 162 },
  "jassen":                 { cat1: 621,  cat3: 2784, bucketId: 162 },  // Jassen | Winter
  "jassen | winter":        { cat1: 621,  cat3: 2784, bucketId: 162 },
  "unisex jassen":          { cat1: 621,  cat3: 2784, bucketId: 162 },
  // Sportkleding heeft een eigen type (798). Alles wat sport is hoort daar, niet
  // bij de winterjassen waar het eerder belandde.
  "sportkleding":           { cat1: 621,  cat3: 798,  bucketId: 162 },
  "sportbroeken":           { cat1: 621,  cat3: 798,  bucketId: 162 },
  "sportleggings":          { cat1: 621,  cat3: 798,  bucketId: 162 },
  "sport bh":               { cat1: 621,  cat3: 798,  bucketId: 162 },
  "sportjassen":            { cat1: 621,  cat3: 798,  bucketId: 162 },
  "yoga kleding":           { cat1: 621,  cat3: 798,  bucketId: 162 },
  "hardloopkleding":        { cat1: 621,  cat3: 798,  bucketId: 162 },
  "gymkleding":             { cat1: 621,  cat3: 798,  bucketId: 162 },
  "yogakleding":            { cat1: 621,  cat3: 798,  bucketId: 162 },
  "sport tops":             { cat1: 621,  cat3: 798,  bucketId: 162 },
  "trainingspakken":        { cat1: 621,  cat3: 798,  bucketId: 162 },
  "wielrenkleding":         { cat1: 621,  cat3: 798,  bucketId: 162 },
  "voetbalkleding":         { cat1: 621,  cat3: 798,  bucketId: 162 },
  "skikleding":             { cat1: 621,  cat3: 798,  bucketId: 162 },
  "unisex sportkleding":    { cat1: 621,  cat3: 798,  bucketId: 162 },
  "unisex wielrenkleding":  { cat1: 621,  cat3: 798,  bucketId: 162 },
  "unisex trainingspakken": { cat1: 621,  cat3: 798,  bucketId: 162 },
  "unisex hardloopkleding": { cat1: 621,  cat3: 798,  bucketId: 162 },
  // Badmode en ondergoed hebben op Marktplaats hun eigen groep náást "Kleding",
  // en die groeps-id (bucketId) is niet uit de openbare boom te lezen. Tot die
  // geverifieerd is blijven deze staan waar ze stonden; fout, maar wél een
  // categorie die het formulier accepteert. Zie het openstaande punt hierover.
  "zwemkleding":            { cat1: 621,  cat3: 631,  bucketId: 162 },
  "badkleding":             { cat1: 621,  cat3: 631,  bucketId: 162 },
  "ondergoed":              { cat1: 621,  cat3: 631,  bucketId: 162 },
  // Carnaval, verkleedkleding en klederdracht. Zonder deze regel viel een dirndl
  // of lederhose terug op broeken en jeans.
  //
  // GEVERIFIEERD in een ingelogde browser op 30-08-2026, niet gegokt en niet op
  // een HTTP 200 afgegaan: /plaats/621/623?bucketId=162 toont in het
  // plaatsformulier "Kleding | Dames > Kleding > Carnavalskleding en
  // Feestkleding", en /plaats/1776/2031?bucketId=169 hetzelfde onder Heren.
  "verkleedkleding":        { cat1: 621,  cat3: 623,  bucketId: 162 },  // Carnavalskleding en Feestkleding
  "unisex verkleedkleding": { cat1: 621,  cat3: 623,  bucketId: 162 },
  "accessoires dames":      { cat1: 621,  cat3: 628,  bucketId: 162 },
  "unisex accessoires":     { cat1: 621,  cat3: 628,  bucketId: 162 },
  // Schoenen: één type (625) voor alle soorten, Marktplaats splitst niet verder.
  "schoenen":               { cat1: 621,  cat3: 625,  bucketId: 164 },
  "schoenen dames":         { cat1: 621,  cat3: 625,  bucketId: 164 },
  "sneakers dames":         { cat1: 621,  cat3: 625,  bucketId: 164 },
  "hakken":                 { cat1: 621,  cat3: 625,  bucketId: 164 },
  "laarzen dames":          { cat1: 621,  cat3: 625,  bucketId: 164 },
  "sandalen":               { cat1: 621,  cat3: 625,  bucketId: 164 },
  "unisex schoenen":        { cat1: 621,  cat3: 625,  bucketId: 164 },

  // === KLEDING | HEREN (cat1 1776) ===
  // Idem: echte type-ID's uit de boom onder l1CategoryId=1776. Overhemden,
  // Polo's, T-shirts, Sportkleding, Broeken en Kostuums bestaan allemaal als
  // eigen type — ze werden alleen niet gebruikt, waardoor elk overhemd als
  // "Truien en Vesten" en elke chino als "Spijkerbroeken en Jeans" werd geplaatst.
  // bucketId 169 = groep "Kleding", 171 = "Schoenen en Sokken".
  "heren jeans":            { cat1: 1776, cat3: 1497, bucketId: 169 },  // Spijkerbroeken en Jeans
  "heren spijkerbroeken":   { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren broeken":          { cat1: 1776, cat3: 646,  bucketId: 169 },  // Broeken en Pantalons
  "heren chinos":           { cat1: 1776, cat3: 646,  bucketId: 169 },
  "heren shorts":           { cat1: 1776, cat3: 646,  bucketId: 169 },
  "heren overhemden":       { cat1: 1776, cat3: 649,  bucketId: 169 },  // Overhemden
  "heren polo's":           { cat1: 1776, cat3: 2790, bucketId: 169 },  // Polo's
  "heren polo":             { cat1: 1776, cat3: 2790, bucketId: 169 },
  "heren verkleedkleding":  { cat1: 1776, cat3: 2031, bucketId: 169 },  // Carnavalskleding en Feestkleding
  "heren t-shirts":         { cat1: 1776, cat3: 651,  bucketId: 169 },  // T-shirts
  "heren t-shirts / polo":  { cat1: 1776, cat3: 651,  bucketId: 169 },
  "heren truien":           { cat1: 1776, cat3: 652,  bucketId: 169 },  // Truien en Vesten
  "heren truien / vesten":  { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren vesten":           { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren hoodies":          { cat1: 1776, cat3: 652,  bucketId: 169 },
  "heren jassen":           { cat1: 1776, cat3: 2788, bucketId: 169 },  // Jassen | Winter
  "heren jassen | winter":  { cat1: 1776, cat3: 2788, bucketId: 169 },
  "heren pakken":           { cat1: 1776, cat3: 648,  bucketId: 169 },  // Kostuums en Colberts
  "heren sportkleding":     { cat1: 1776, cat3: 1779, bucketId: 169 },  // Sportkleding
  "heren sportbroeken":     { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren sportjassen":      { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren sport tops":       { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren hardloopkleding":  { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren gymkleding":       { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren voetbalkleding":   { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren wielrenkleding":   { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren trainingspakken":  { cat1: 1776, cat3: 1779, bucketId: 169 },
  "heren skikleding":       { cat1: 1776, cat3: 1779, bucketId: 169 },
  // Zie de opmerking bij dames: badmode, ondergoed en accessoires zitten in een
  // andere groep, waarvan de id nog niet geverifieerd is.
  "heren zwembroeken":      { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren ondergoed":        { cat1: 1776, cat3: 1497, bucketId: 169 },
  "heren accessoires":      { cat1: 1776, cat3: 652,  bucketId: 169 },
  // Schoenen: één type (642) voor alle soorten.
  "heren schoenen":         { cat1: 1776, cat3: 642,  bucketId: 171 },
  "heren sneakers":         { cat1: 1776, cat3: 642,  bucketId: 171 },
  "heren formele schoenen": { cat1: 1776, cat3: 642,  bucketId: 171 },
  "heren laarzen":          { cat1: 1776, cat3: 642,  bucketId: 171 },

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
  "kinderen wielrenkleding":{ cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  "kinderen voetbalkleding":{ cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  "kinderen zwemkleding":   { cat1: 565, bucketId: 153, cat3: 597, sizeMap: MP_KIDS_SIZES },
  // Schoenen en Sokken is its own type, so no size lookup.
  "kinderen schoenen":      { cat1: 565, bucketId: 153, cat3: 598 },
  // Mode-accessoires (bucketId 427) has exactly two types: baby and kind.
  "kinderen accessoires":   { cat1: 565, bucketId: 427, cat3: 3136 },

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

  // === AUDIO, TV EN FOTO (cat1 31) ===
  // Herkenbaar aan het "audio "-voorvoegsel. TWEE niveaus, net als muziek en
  // antiek: dus GEEN bucketId — met een bucketId erbij antwoordt Marktplaats
  // met HTTP 400. Elke cat3 hieronder komt uit searchCategoryOptions van
  // /l/audio-tv-en-foto/ (l1=31), waar id en naam in hetzelfde record staan;
  // een id kan dus niet bij de verkeerde naam belanden.
  //
  // Daarbovenop op 27-08-2026 alle 68 langs een TWEEDE, onafhankelijke bron
  // gelegd: /lrp/api/search met l2CategoryId={cat3} gaf voor elk id echte
  // advertenties terug die zelf datzelfde categoryId dragen, met titels die bij
  // de naam horen (38 = luidsprekers, 37 = koptelefoons, 33 = buizenversterkers).
  // 68 van 68, geen enkele leeg of afwijkend.
  //
  // Op 27-08-2026 in een INGELOGDE browser bevestigd, en niet steekproefsgewijs:
  // alle 68 opgehaald via /plaats/31/{cat3} en de "categoryName" uit het
  // antwoord vergeleken met de naam die Marktplaats zelf aan dat id hangt.
  // 68 van 68 gelijk. Zonder bucketId, zoals bij muziek en antiek.
  //
  // Wat daarbij opviel: deze tak heeft wél kenmerkvelden (bij Luidsprekers Type,
  // Wattage, Merk, Handelsnaam fabrikant). Alleen titel, beschrijving en foto's
  // zijn verplicht — de kenmerken zijn een kwaliteitsduwtje ("1 / 8 ingevuld").
  // Merk en conditie vullen we al (fillBrandField/selectCondition zijn algemeen,
  // niet kleding-only). Type en Wattage blijven leeg; net als destijds bij
  // sportkleding betekent dat: wie op zo'n filter zoekt, ziet de advertentie niet.
  // Wil je dat oplossen, dan is mpSportType() het model om na te volgen.
  // Let op: /plaats/ geeft zonder login HTTP 401 vóór enige controle van de URL —
  // ook /plaats/99999/38 geeft exact hetzelfde 401. Uit een statuscode valt hier
  // dus niets af te leiden; alleen de gerenderde categorienaam telt.
  // 2dehands gebruikt dezelfde ids.
  "audio luidsprekers":                  { cat1: 31, cat3: 38 },
  "audio soundbars":                     { cat1: 31, cat3: 3053 },
  "audio koptelefoons":                  { cat1: 31, cat3: 37 },
  "audio versterkers en receivers":      { cat1: 31, cat3: 46 },
  "audio buizenversterkers":             { cat1: 31, cat3: 33 },
  "audio tuners":                        { cat1: 31, cat3: 45 },
  "audio stereo sets":                   { cat1: 31, cat3: 36 },
  "audio home cinema sets":              { cat1: 31, cat3: 1116 },
  "audio platenspelers":                 { cat1: 31, cat3: 42 },
  "audio cd spelers":                    { cat1: 31, cat3: 35 },
  "audio blu ray spelers":               { cat1: 31, cat3: 2665 },
  "audio dvd spelers":                   { cat1: 31, cat3: 1114 },
  "audio videospelers":                  { cat1: 31, cat3: 1133 },
  "audio cassettedecks":                 { cat1: 31, cat3: 2036 },
  "audio bandrecorders":                 { cat1: 31, cat3: 32 },
  "audio radio s":                       { cat1: 31, cat3: 43 },
  "audio walkmans en discmans":          { cat1: 31, cat3: 47 },
  "audio mp3 spelers ipod":              { cat1: 31, cat3: 40 },
  "audio mp3 spelers overige":           { cat1: 31, cat3: 1649 },
  "audio mp4 spelers":                   { cat1: 31, cat3: 2615 },
  "audio mp3 accessoires ipod":          { cat1: 31, cat3: 1723 },
  "audio mp3 accessoires overige":       { cat1: 31, cat3: 1452 },
  "audio mediaspelers":                  { cat1: 31, cat3: 2668 },
  "audio karaoke apparatuur":            { cat1: 31, cat3: 2833 },
  "audio professionele audio en video":  { cat1: 31, cat3: 1117 },
  "audio televisies":                    { cat1: 31, cat3: 1120 },
  "audio vintage televisies":            { cat1: 31, cat3: 1121 },
  "audio televisiebeugels":              { cat1: 31, cat3: 1453 },
  "audio televisie accessoires":         { cat1: 31, cat3: 3058 },
  "audio afstandsbedieningen":           { cat1: 31, cat3: 2617 },
  "audio decoders en harddiskrecorders": { cat1: 31, cat3: 1722 },
  "audio schotelantennes":               { cat1: 31, cat3: 1118 },
  "audio audio en tv kabels":            { cat1: 31, cat3: 1106 },
  "audio converters":                    { cat1: 31, cat3: 3052 },
  "audio opladers":                      { cat1: 31, cat3: 1724 },
  "audio accu s en batterijen":          { cat1: 31, cat3: 2035 },
  "audio beamers":                       { cat1: 31, cat3: 1132 },
  "audio beamer accessoires":            { cat1: 31, cat3: 3056 },
  "audio projectieschermen":             { cat1: 31, cat3: 3055 },
  "audio diaprojectors":                 { cat1: 31, cat3: 2666 },
  "audio videobewaking":                 { cat1: 31, cat3: 1129 },
  "audio drones":                        { cat1: 31, cat3: 3057 },
  "audio actiecamera s":                 { cat1: 31, cat3: 2834 },
  "audio fotocamera s digitaal":         { cat1: 31, cat3: 487 },
  "audio fotocamera s analoog":          { cat1: 31, cat3: 480 },
  "audio onderwatercamera s":            { cat1: 31, cat3: 497 },
  "audio videocamera s digitaal":        { cat1: 31, cat3: 1131 },
  "audio videocamera s analoog":         { cat1: 31, cat3: 1130 },
  "audio lenzen en objectieven":         { cat1: 31, cat3: 495 },
  "audio filters":                       { cat1: 31, cat3: 1720 },
  "audio flitsers":                      { cat1: 31, cat3: 489 },
  "audio statieven en balhoofden":       { cat1: 31, cat3: 500 },
  "audio fototassen":                    { cat1: 31, cat3: 1484 },
  "audio geheugenkaarten":               { cat1: 31, cat3: 493 },
  "audio fotografie accu s":             { cat1: 31, cat3: 1360 },
  "audio fotostudio en toebehoren":      { cat1: 31, cat3: 1400 },
  "audio professionele fotoapparatuur":  { cat1: 31, cat3: 501 },
  "audio doka toebehoren":               { cat1: 31, cat3: 488 },
  "audio filmrollen":                    { cat1: 31, cat3: 1115 },
  "audio fotopapier":                    { cat1: 31, cat3: 1721 },
  "audio fotolijsten":                   { cat1: 31, cat3: 1483 },
  "audio digitale fotolijsten":          { cat1: 31, cat3: 2667 },
  "audio fotoalbums en accessoires":     { cat1: 31, cat3: 3059 },
  "audio verrekijkers":                  { cat1: 31, cat3: 503 },
  "audio telescopen":                    { cat1: 31, cat3: 502 },
  "audio microscopen":                   { cat1: 31, cat3: 496 },
  "audio weerstations en barometers":    { cat1: 31, cat3: 1725 },
  "audio overige audio tv en foto":      { cat1: 31, cat3: 41 },

  // === MUZIEK EN INSTRUMENTEN (cat1 728) ===
  // Herkenbaar aan het "muziek "-voorvoegsel, net als de electronics-tak.
  // LET OP: deze tak is maar TWEE niveaus diep, kleding is er drie. Daarom
  // staat hier geen bucketId: /plaats/728/{cat3} is de juiste vorm en met een
  // bucketId erbij antwoordt Marktplaats met HTTP 400. Alle 52 ids zijn op
  // 13-08-2026 in een ingelogde browser nagelopen tegen de categorienaam die
  // Marktplaats zelf rendert — niet tegen een HTTP-status. 2dehands gebruikt
  // exact dezelfde ids.
  // Antiek en Kunst: twee niveaus, geen bucketId (net als muziek). Geverifieerd
  // in een ingelogde browser op 18-08-2026 — /plaats/1/2614 toont
  // "Antiek en Kunst > Goud en Zilver", /plaats/1/2 toont "Bestek".
  "antiek curiosa en brocante": { cat1: 1, cat3: 15 },
  "antiek glas en kristal": { cat1: 1, cat3: 1648 },
  "kunst schilderijen klassiek": { cat1: 1, cat3: 25 },
  "antiek vazen": { cat1: 1, cat3: 14 },
  "antiek keramiek en aardewerk": { cat1: 1, cat3: 1502 },
  "antiek overige antiek": { cat1: 1, cat3: 9 },
  "antiek woonaccessoires": { cat1: 1, cat3: 1500 },
  "antiek porselein": { cat1: 1, cat3: 10 },
  "antiek servies los": { cat1: 1, cat3: 12 },
  "kunst beelden en houtsnijwerken": { cat1: 1, cat3: 23 },
  "antiek meubels stoelen en banken": { cat1: 1, cat3: 1505 },
  "antiek lampen": { cat1: 1, cat3: 7 },
  "kunst schilderijen modern": { cat1: 1, cat3: 1845 },
  "antiek wandborden en tegels": { cat1: 1, cat3: 1104 },
  "kunst etsen en gravures": { cat1: 1, cat3: 1105 },
  "antiek koper en brons": { cat1: 1, cat3: 1647 },
  "antiek bestek": { cat1: 1, cat3: 2 },
  "antiek boeken en bijbels": { cat1: 1, cat3: 3 },
  "antiek klokken": { cat1: 1, cat3: 6 },
  "antiek meubels kasten": { cat1: 1, cat3: 5 },
  "antiek speelgoed": { cat1: 1, cat3: 1507 },
  "kunst niet westerse kunst": { cat1: 1, cat3: 1844 },
  "antiek schalen": { cat1: 1, cat3: 1103 },
  "antiek meubels tafels": { cat1: 1, cat3: 1506 },
  "antiek gereedschap en instrumenten": { cat1: 1, cat3: 1501 },
  "kunst schilderijen abstract": { cat1: 1, cat3: 1846 },
  "antiek religie": { cat1: 1, cat3: 1102 },
  "kunst designobjecten": { cat1: 1, cat3: 1508 },
  "antiek emaille": { cat1: 1, cat3: 1100 },
  "antiek goud en zilver": { cat1: 1, cat3: 2614 },
  "kunst litho s en zeefdrukken": { cat1: 1, cat3: 27 },
  "kunst tekeningen en foto s": { cat1: 1, cat3: 26 },
  "antiek keukenbenodigdheden": { cat1: 1, cat3: 1842 },
  "antiek servies compleet": { cat1: 1, cat3: 1843 },
  "antiek kandelaars": { cat1: 1, cat3: 2661 },
  "antiek spiegels": { cat1: 1, cat3: 2663 },
  "antiek tin": { cat1: 1, cat3: 2664 },
  "antiek kleden en textiel": { cat1: 1, cat3: 2118 },
  "kunst overige kunst": { cat1: 1, cat3: 24 },
  "antiek kantoor en zakelijk": { cat1: 1, cat3: 1841 },
  "antiek schoolplaten": { cat1: 1, cat3: 2662 },
  "antiek kleding en accessoires": { cat1: 1, cat3: 1503 },
  "antiek naaimachines": { cat1: 1, cat3: 1101 },
  "antiek tv s en audio": { cat1: 1, cat3: 11 },
  "antiek meubels bedden": { cat1: 1, cat3: 1504 },

  "muziek accordeons":                                  { cat1: 728, cat3: 729 },   // Accordeons
  "muziek behuizingen en koffers":                      { cat1: 728, cat3: 730 },   // Behuizingen en Koffers
  "muziek blaasinstrumenten blokfluiten":               { cat1: 728, cat3: 1713 },   // Blaasinstrumenten | Blokfluiten
  "muziek blaasinstrumenten didgeridoos":               { cat1: 728, cat3: 2885 },   // Blaasinstrumenten | Didgeridoos
  "muziek blaasinstrumenten dwarsfluiten en piccolo's": { cat1: 728, cat3: 743 },   // Blaasinstrumenten | Dwarsfluiten en Piccolo's
  "muziek blaasinstrumenten hobo's":                    { cat1: 728, cat3: 1764 },   // Blaasinstrumenten | Hobo's
  "muziek blaasinstrumenten hoorns":                    { cat1: 728, cat3: 1765 },   // Blaasinstrumenten | Hoorns
  "muziek blaasinstrumenten klarinetten":               { cat1: 728, cat3: 771 },   // Blaasinstrumenten | Klarinetten
  "muziek blaasinstrumenten mondharmonica's":           { cat1: 728, cat3: 1714 },   // Blaasinstrumenten | Mondharmonica's
  "muziek blaasinstrumenten overige":                   { cat1: 728, cat3: 763 },   // Blaasinstrumenten | Overige
  "muziek blaasinstrumenten saxofoons":                 { cat1: 728, cat3: 1766 },   // Blaasinstrumenten | Saxofoons
  "muziek blaasinstrumenten trombones":                 { cat1: 728, cat3: 1767 },   // Blaasinstrumenten | Trombones
  "muziek blaasinstrumenten trompetten":                { cat1: 728, cat3: 779 },   // Blaasinstrumenten | Trompetten
  "muziek blaasinstrumenten tuba's":                    { cat1: 728, cat3: 1768 },   // Blaasinstrumenten | Tuba's
  "muziek bladmuziek":                                  { cat1: 728, cat3: 731 },   // Bladmuziek
  "muziek dj-sets en draaitafels":                      { cat1: 728, cat3: 738 },   // Dj-sets en Draaitafels
  "muziek draaiorgels":                                 { cat1: 728, cat3: 1769 },   // Draaiorgels
  "muziek drumcomputers":                               { cat1: 728, cat3: 1402 },   // Drumcomputers
  "muziek drumstellen en slagwerk":                     { cat1: 728, cat3: 742 },   // Drumstellen en Slagwerk
  "muziek effecten":                                    { cat1: 728, cat3: 744 },   // Effecten
  "muziek instrumenten onderdelen":                     { cat1: 728, cat3: 1716 },   // Instrumenten | Onderdelen
  "muziek instrumenten toebehoren":                     { cat1: 728, cat3: 1717 },   // Instrumenten | Toebehoren
  "muziek kabels en stekkers":                          { cat1: 728, cat3: 2135 },   // Kabels en Stekkers
  "muziek keyboards":                                   { cat1: 728, cat3: 751 },   // Keyboards
  "muziek licht en laser":                              { cat1: 728, cat3: 754 },   // Licht en Laser
  "muziek mengpanelen":                                 { cat1: 728, cat3: 756 },   // Mengpanelen
  "muziek microfoons":                                  { cat1: 728, cat3: 757 },   // Microfoons
  "muziek midi-apparatuur":                             { cat1: 728, cat3: 758 },   // Midi-apparatuur
  "muziek orgels":                                      { cat1: 728, cat3: 761 },   // Orgels
  "muziek orkestbanden":                                { cat1: 728, cat3: 762 },   // Orkestbanden
  "muziek overige muziek en instrumenten":              { cat1: 728, cat3: 764 },   // Overige Muziek en Instrumenten
  "muziek percussie":                                   { cat1: 728, cat3: 739 },   // Percussie
  "muziek piano's":                                     { cat1: 728, cat3: 765 },   // Piano's
  "muziek samplers":                                    { cat1: 728, cat3: 770 },   // Samplers
  "muziek snaarinstrumenten banjo's":                   { cat1: 728, cat3: 1770 },   // Snaarinstrumenten | Banjo's
  "muziek snaarinstrumenten gitaren akoestisch":        { cat1: 728, cat3: 746 },   // Snaarinstrumenten | Gitaren | Akoestisch
  "muziek snaarinstrumenten gitaren bas":               { cat1: 728, cat3: 747 },   // Snaarinstrumenten | Gitaren | Bas
  "muziek snaarinstrumenten gitaren elektrisch":        { cat1: 728, cat3: 748 },   // Snaarinstrumenten | Gitaren | Elektrisch
  "muziek snaarinstrumenten harpen":                    { cat1: 728, cat3: 2886 },   // Snaarinstrumenten | Harpen
  "muziek snaarinstrumenten klavecimbels":              { cat1: 728, cat3: 1771 },   // Snaarinstrumenten | Klavecimbels
  "muziek snaarinstrumenten mandolines":                { cat1: 728, cat3: 1772 },   // Snaarinstrumenten | Mandolines
  "muziek snaarinstrumenten overige":                   { cat1: 728, cat3: 1370 },   // Snaarinstrumenten | Overige
  "muziek soundmodules":                                { cat1: 728, cat3: 772 },   // Soundmodules
  "muziek standaards":                                  { cat1: 728, cat3: 774 },   // Standaards
  "muziek strijkinstrumenten cello's":                  { cat1: 728, cat3: 1773 },   // Strijkinstrumenten | Cello's
  "muziek strijkinstrumenten contrabassen":             { cat1: 728, cat3: 1774 },   // Strijkinstrumenten | Contrabassen
  "muziek strijkinstrumenten overige":                  { cat1: 728, cat3: 1775 },   // Strijkinstrumenten | Overige
  "muziek strijkinstrumenten violen en altviolen":      { cat1: 728, cat3: 1371 },   // Strijkinstrumenten | Violen en Altviolen
  "muziek synthesizers":                                { cat1: 728, cat3: 777 },   // Synthesizers
  "muziek theaterbelichting":                           { cat1: 728, cat3: 2631 },   // Theaterbelichting
  "muziek versterkers bas en gitaar":                   { cat1: 728, cat3: 745 },   // Versterkers | Bas en Gitaar
  "muziek versterkers keyboard, monitor en pa":         { cat1: 728, cat3: 768 },   // Versterkers | Keyboard, Monitor en PA

  // ── HUIS, TUIN EN KERST ────────────────────────────────────────────────
  // Herkenbaar aan het "wonen "-voorvoegsel. Drie takken van Marktplaats onder
  // één noemer: Tuin en Terras (1847), Huis en Inrichting (504) en Kerst, dat
  // bij Marktplaats onder Diversen (428) hangt en niet bij wonen.
  //
  // Alle 40 ids zijn op 21-08-2026 opgehaald uit de categorieboom van
  // Marktplaats zelf (searchCategoryOptions per l1CategoryId) en stuk voor stuk
  // vergeleken met de naam die Marktplaats teruggeeft — niet geraden en niet op
  // een HTTP-status afgegaan, want een fout pad geeft daar gewoon 200.
  //
  // Twee niveaus, dus GEEN bucketId (zoals muziek en antiek). Met een bucketId
  // erbij antwoordt /plaats/{cat1}/{cat3} met HTTP 400.
  "wonen tuinmeubel accessoires":                { cat1: 1847, cat3: 1864 },   // Tuinmeubel-accessoires
  "wonen parasols":                              { cat1: 1847, cat3: 3009 },   // Parasols
  "wonen tuinstoelen":                           { cat1: 1847, cat3: 3001 },   // Tuinstoelen
  "wonen tuintafels":                            { cat1: 1847, cat3: 3002 },   // Tuintafels
  "wonen tuinsets en loungesets":                { cat1: 1847, cat3: 278 },   // Tuinsets en Loungesets
  "wonen tuinbanken":                            { cat1: 1847, cat3: 3004 },   // Tuinbanken
  "wonen ligbedden":                             { cat1: 1847, cat3: 3005 },   // Ligbedden
  "wonen bloembakken en plantenbakken":          { cat1: 1847, cat3: 1852 },   // Bloembakken en Plantenbakken
  "wonen bloempotten":                           { cat1: 1847, cat3: 1442 },   // Bloempotten
  "wonen buitenverlichting":                     { cat1: 1847, cat3: 281 },   // Buitenverlichting
  "wonen vuurkorven":                            { cat1: 1847, cat3: 2964 },   // Vuurkorven
  "wonen terrasverwarmers":                      { cat1: 1847, cat3: 2811 },   // Terrasverwarmers
  "wonen partytenten":                           { cat1: 1847, cat3: 1858 },   // Partytenten
  "wonen overkappingen":                         { cat1: 1847, cat3: 2901 },   // Overkappingen
  "wonen schaduwdoeken":                         { cat1: 1847, cat3: 3008 },   // Schaduwdoeken
  "wonen zonneschermen":                         { cat1: 1847, cat3: 288 },   // Zonneschermen
  "wonen hangmatten":                            { cat1: 1847, cat3: 3006 },   // Hangmatten
  "wonen picknicktafels":                        { cat1: 1847, cat3: 3003 },   // Picknicktafels
  "wonen gordijnen en lamellen":                 { cat1: 504, cat3: 512 },   // Gordijnen en Lamellen
  "wonen barkrukken":                            { cat1: 504, cat3: 2128 },   // Barkrukken
  "wonen stoelen":                               { cat1: 504, cat3: 530 },   // Stoelen
  "wonen krukjes":                               { cat1: 504, cat3: 3203 },   // Krukjes
  "wonen fauteuils":                             { cat1: 504, cat3: 1940 },   // Fauteuils
  "wonen eettafels":                             { cat1: 504, cat3: 1949 },   // Eettafels
  "wonen salontafels":                           { cat1: 504, cat3: 527 },   // Salontafels
  "wonen bijzettafels":                          { cat1: 504, cat3: 2758 },   // Bijzettafels
  "wonen tapijten en kleden":                    { cat1: 504, cat3: 533 },   // Tapijten en Kleden
  "wonen kussens":                               { cat1: 504, cat3: 2768 },   // Kussens
  "wonen plaids en woondekens":                  { cat1: 504, cat3: 2870 },   // Plaids en Woondekens
  // Marktplaats heeft geen eigen rubriek voor schapen-, rendier- of koeienvachten;
  // verkopers zetten ze zelf onder Woonaccessoires | Overige (536). Spreien horen
  // onder Slaapkamer | Beddengoed (525). Beide id's en hun ouder (504) zijn
  // 28-08-2026 nagekeken in de openbare categorieboom van Marktplaats zelf,
  // niet geraden. Zonder deze twee bleef woontextiel deels onplaatsbaar.
  "wonen vachten":                               { cat1: 504, cat3: 536 },   // Woonaccessoires | Overige
  "wonen beddengoed":                            { cat1: 504, cat3: 525 },   // Slaapkamer | Beddengoed
  "wonen vazen":                                 { cat1: 504, cat3: 1516 },   // Vazen
  "wonen spiegels":                              { cat1: 504, cat3: 529 },   // Spiegels
  "wonen wanddecoraties":                        { cat1: 504, cat3: 2875 },   // Wanddecoraties
  "wonen kunstplanten":                          { cat1: 504, cat3: 3121 },   // Kunstplanten en Kunstbloemen
  "wonen tafellampen":                           { cat1: 504, cat3: 1260 },   // Tafellampen
  "wonen vloerlampen":                           { cat1: 504, cat3: 1259 },   // Vloerlampen
  "wonen hanglampen":                            { cat1: 504, cat3: 1258 },   // Hanglampen
  "wonen kandelaars en kaarsen":                 { cat1: 504, cat3: 1510 },   // Kandelaars en Kaarsen
  "wonen tafelkleden":                           { cat1: 504, cat3: 3120 },   // Tafelkleden
  "wonen overige huis en inrichting":            { cat1: 504, cat3: 526 },   // Overige Huis en Inrichting
  "wonen kerst":                                 { cat1: 428, cat3: 436 },   // Kerst
};
// NOTE: there is deliberately no catch-all default category. There used to be
// one (dames jeans), and it meant any item whose category didn't resolve got
// published as women's jeans — a MyProtein sport short included. Publishing to a
// wrong category is worse than not publishing: it's visible to buyers, hurts
// reach, and the user never learns it happened. Unresolved category now fails
// the job with an actionable message instead (see getMpSyiUrl).

function getDeleteUrl(platform, payload) {
  // /v/listing/{id} bestaat NIET bij Marktplaats/2dehands — die geeft altijd
  // 404, ook voor een levende advertentie. De verwijderklus opende dus een
  // foutpagina, vond daar geen Verwijder-knop en moest terugvallen op zoeken in
  // het overzicht. /seller/view/{id} is de pagina die het wél doet, met de knop
  // erop.
  if (platform === "marktplaats") {
    if (payload?.platform_listing_id) return `https://www.marktplaats.nl/seller/view/${payload.platform_listing_id}`;
    if (payload?.platform_listing_url) return payload.platform_listing_url;
    return "https://www.marktplaats.nl";
  }
  if (platform === "2dehands") {
    if (payload?.platform_listing_id) return `https://www.2dehands.be/seller/view/${payload.platform_listing_id}`;
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
    // Zet de extensieversie in de melding. Zonder dat is een categorie die de
    // server wél kent en de extensie niet, niet te onderscheiden van een oude
    // extensie die nog draait — en dat kostte precies één misdiagnose.
    let v = "";
    try { v = ` [extensie ${chrome.runtime.getManifest().version}]`; } catch (_) {}
    super(message + v);
    this.name = "CategoryUnresolvedError";
    this.needsUserInput = true;
  }
}

// De omgekeerde weg door MP_CATEGORIES: van de twee nummers die Marktplaats
// zelf op een advertentie zet terug naar onze eigen regel.
//
// Waarom dat nodig is: aan onze regel hangt het bucketId (de groep in het
// plaatsformulier) en bij kinderkleding een maat-afhankelijke onderverdeling.
// Kennen we het paar, dan bouwen we het adres dus op de bewezen manier; kennen
// we het niet — munten, postzegels, boeken, alles buiten onze lijst — dan gaan
// we rechtstreeks op de twee nummers af.
//
// Eén keer opbouwen en bewaren: deze functie draait bij elke plaatsing.
let _mpOpNummer = null;
function mpCategorieOpNummer(l1, l2) {
  if (!_mpOpNummer) {
    _mpOpNummer = new Map();
    for (const regel of Object.values(MP_CATEGORIES)) {
      if (!regel || regel.cat1 == null || regel.cat3 == null) continue;
      const sleutel = `${regel.cat1}/${regel.cat3}`;
      // De eerste die we tegenkomen wint. Meerdere sleutels wijzen naar dezelfde
      // Marktplaats-categorie ("jeans" en "spijkerbroeken"), en die leveren
      // hetzelfde adres op — welke het wordt maakt dus niet uit.
      if (!_mpOpNummer.has(sleutel)) _mpOpNummer.set(sleutel, regel);
    }
  }
  return _mpOpNummer.get(`${l1}/${l2}`) || null;
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

  // DE ECHTE CATEGORIE VAN DE OUDE ADVERTENTIE GAAT VOOR.
  //
  // Bij een verversing haalt de server vlak vóór het verwijderen op in welke
  // categorie de advertentie stond (l1/l2, letterlijk van de advertentiepagina
  // van Marktplaats). Die is per definitie beter dan wat wij uit de titel
  // kunnen afleiden: onze eigen lijst dekt kleding, wonen, antiek, muziek en
  // sieraden, en Amanda verkoopt daarnaast munten, bankbiljetten en boeken.
  // Voor die takken bestond er geen goede doos en werd het altijd de verkeerde.
  //
  // Kennen we het paar zelf ook (dan hoort er een bucketId bij, en bij
  // kinderkleding een maat-afhankelijk type), dan gebruiken we onze eigen regel
  // — dat adres is bewezen. Kennen we het niet, dan gaan we op de twee nummers
  // van Marktplaats af, zonder bucketId; precies de vorm die de tweeniveau-
  // takken (muziek) al gebruiken.
  const mpCat = item?.mp_category;
  const eigenPaar = (mpCat && mpCat.l1 && mpCat.l2)
    ? mpCategorieOpNummer(mpCat.l1, mpCat.l2) : null;
  if (mpCat && mpCat.l1 && mpCat.l2 && !eigenPaar) {
    return `${base}/${mpCat.l1}/${mpCat.l2}?title=`;
  }

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

  // Kennen we het paar van Marktplaats zelf ook? Dan die regel, want daar hangt
  // het bucketId aan (en bij kinderkleding de maat-afhankelijke onderverdeling).
  let c = eigenPaar;

  // When gender is heren, always try heren-prefixed first so "truien / vesten" + heren → Heren
  if (c) { /* de advertentie zelf heeft het al gezegd */ }
  else if (gender === "heren") {
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

  // A three-level branch (all clothing) needs its bucketId; a two-level branch
  // (music) has none, and sending one anyway makes Marktplaats answer HTTP 400.
  return c.bucketId == null
    ? `${base}/${c.cat1}/${cat3}?title=`
    : `${base}/${c.cat1}/${cat3}?bucketId=${c.bucketId}&title=`;
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

// ── Calm mode ──────────────────────────────────────────────────────────────
// Wat een geautomatiseerd account verraadt is RITME, niet aantal. Twintig
// advertenties die in twee minuten achter elkaar verschijnen zien er anders uit
// dan twintig advertenties verspreid over een middag — terwijl het eindresultaat
// hetzelfde is. Calm mode koopt die rust: publicaties komen 3 tot 8 minuten uit
// elkaar (willekeurig, want een vaste tussenpoos is óók een patroon) en de
// verkocht-controle gaat van elke tien minuten naar één keer per uur.
//
// Alleen SCHRIJVENDE opdrachten worden vertraagd. Een scan leest alleen en is
// niet zichtbaar voor het platform; die tegenhouden zou de gebruiker laten
// wachten zonder dat het iets veiliger maakt.
const CALM_MIN_MS = 3 * 60 * 1000;
const CALM_MAX_MS = 8 * 60 * 1000;
const CALM_SLEUTEL = "calmVolgendeNa";
const SCHRIJVENDE_ACTIES = new Set(["create", "delete", "content_refresh"]);
// Zonder Calm mode stond hier helemaal geen rem: een grote stapel te herplaatsen
// advertenties liep in één ronde achter elkaar door, en dan wisselt het werkvenster
// tientallen keren per minuut van tabblad. Dat venster is wel unfocused, maar niet
// elk Windows/Chrome-versie respecteert dat bij elke update — de gebruiker zag zijn
// scherm dan continu wegflitsen. Deze korte pauze geldt ALTIJD, Calm mode of niet,
// en kost bij een normale klus niets: een herplaatsing duurt zelf al seconden.
const MIN_GAP_MS = 4000;

async function calmAan() {
  try {
    const s = await chrome.storage.sync.get("calmMode");
    return !!s.calmMode;
  } catch (_) { return false; }
}

// Mag er nu een schrijvende opdracht draaien? In de opslag, niet in het geheugen:
// een service worker wordt door Chrome doodgemaakt zodra hij even niets doet, en
// dan zou de wachttijd elke keer opnieuw op nul beginnen.
async function calmMagNu() {
  if (!await calmAan()) return true;
  try {
    const s = await chrome.storage.local.get(CALM_SLEUTEL);
    const na = s[CALM_SLEUTEL] || 0;
    return Date.now() >= na;
  } catch (_) { return true; }
}

async function calmVolgendeInplannen() {
  if (!await calmAan()) return;
  const wacht = CALM_MIN_MS + Math.floor(Math.random() * (CALM_MAX_MS - CALM_MIN_MS));
  try {
    await chrome.storage.local.set({ [CALM_SLEUTEL]: Date.now() + wacht });
    console.log(`[Omnivaleur] Calm mode: volgende publicatie over ${Math.round(wacht / 60000)} min`);
  } catch (_) {}
}

// De verkocht-controle draait op een alarm, en dat moet opnieuw gezet worden
// zodra de schakelaar omgaat — een alarm verandert niet vanzelf van tempo.
async function calmAlarmBijwerken() {
  const minuten = await calmAan() ? 60 : 10;
  try { await chrome.alarms.create("sold-check", { periodInMinutes: minuten }); } catch (_) {}
}

chrome.storage.onChanged.addListener((wijzigingen, gebied) => {
  if (gebied === "sync" && wijzigingen.calmMode) {
    calmAlarmBijwerken();
    // Uitzetten mag meteen effect hebben: geen reden iemand te laten wachten op
    // een rem die hij zojuist heeft losgelaten.
    if (!wijzigingen.calmMode.newValue) chrome.storage.local.remove(CALM_SLEUTEL);
  }
});

chrome.alarms.create("poll", { periodInMinutes: POLL_INTERVAL_SECONDS / 60 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "poll") pollJobs();
});

// Also poll immediately on install/startup
chrome.runtime.onInstalled.addListener(pollJobs);


// Meteen bij het opstarten of bijwerken: restanten van eerdere versies opruimen.
// Dat zijn de lege vensters die zich onderin de balk opstapelden.
chrome.runtime.onInstalled.addListener(() => { opruimenBijStart(); });
chrome.runtime.onStartup.addListener(() => { opruimenBijStart(); });

async function opruimenBijStart() {
  try {
    const houden = await vindEnOpruimenWerkvensters();
    if (houden != null) await setWorkerWindowId(houden);
  } catch (_) { /* niet erg — de eerstvolgende klus ruimt ook op */ }
}

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
        // 401 = dit inlogbewijs is definitief ongeldig; opnieuw proberen heeft
        // geen zin. Het bewijs moet dan weg, anders blijft het menu vrolijk
        // "Extension active" melden terwijl er niets meer gebeurt. Gemeten geval
        // (21-08-2026): de extensie stond groen, meldde zich al een uur niet meer
        // bij de server en liet elke opdracht liggen — van buitenaf niet te zien.
        if (res.status === 401 || res.status === 403) {
          await new Promise((r) => chrome.storage.sync.remove(["authToken", "refreshToken"], r));
          try {
            await chrome.action.setBadgeText({ text: "!" });
            await chrome.action.setBadgeBackgroundColor({ color: "#dc2626" });
            await chrome.action.setTitle({ title: "Omnivaleur — sign in again to keep publishing" });
          } catch (_) {}
        }
        return null;
      }
      const data = await res.json();
      if (!data.access_token) return null;
      const patch = { authToken: data.access_token };
      if (data.refresh_token) patch.refreshToken = data.refresh_token; // rotation
      await new Promise((r) => chrome.storage.sync.set(patch, r));
      try { await chrome.action.setBadgeText({ text: "" }); } catch (_) {}
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
  // Vertel de server bij ELK verzoek wie we zijn. Zonder dit kon een kopie van
  // maanden oud gewoon werk blijven ophalen en half afleveren; de server had
  // geen enkele manier om dat te zien, want een oude kopie stempelt haar versie
  // alleen in foutmeldingen — en juist deze gevallen liepen vast zonder fout.
  try { headers["X-Omnivaleur-Ext"] = chrome.runtime.getManifest().version; } catch (_) {}
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

// De klussen lopen bewust één voor één (één tabblad tegelijk — twee tegelijk
// haalde de gegevens van twee advertenties door elkaar). Maar zodra er één klaar
// was, wachtte de volgende tot de eerstvolgende ronde: bij drie platforms waren
// dat drie stiltes van maximaal een halve minuut bovenop het echte werk. Daarom
// gaat er direct nóg een ronde overheen zolang er in de vorige ronde werk is
// verzet. De klussen blijven strikt achter elkaar lopen; alleen het wachten
// ertussen is weg.
//
// `_pollLoopt` voorkomt dat het dashboard-porren en de klok tegelijk gaan
// pollen — twee rondes door elkaar zouden dezelfde klus twee keer kunnen
// oppakken. Wie tegen een lopende ronde aanloopt, vraagt gewoon om nog een ronde
// erna.
let _pollLoopt = false;
let _pollNogmaals = false;
// Welke platforms op dit moment een scan draaien. Zonder deze rem zou elke
// pollronde er nóg één starten, want een scan blokkeert de wachtrij niet meer.
const _lopendeScans = new Set();

// Tabbladen die er niet meer zijn, maar wél nog een lopende opdracht in de
// administratie hebben staan. Bij netjes sluiten vangt tabs.onRemoved dat af,
// maar bij een crash van Chrome of een herstart van de extensie draait die
// listener niet — en dan blijft de opdracht "bezig" en ligt de wachtrij stil.
// Deze controle draait vóór elke pollronde en meldt zulke wezen alsnog af.
async function reconcileOrphanJobTabs() {
  let all;
  try {
    all = await chrome.storage.local.get(null);
  } catch { return; }
  for (const [key, meta] of Object.entries(all)) {
    if (!key.startsWith("jobtab_") || !meta || !meta.jobId) continue;
    if (meta.awaitingManualFinish) continue;  // bewust opengelaten voor de gebruiker
    const tabId = Number(key.slice("jobtab_".length));
    let leeft = true;
    try { await chrome.tabs.get(tabId); } catch { leeft = false; }
    if (leeft) continue;
    console.warn(`[Omnivaleur] Job ${meta.jobId} (${meta.platform}) has no tab any more — reporting it so the queue keeps moving.`);
    await chrome.storage.local.remove(key);
    clearJobWatchdog(tabId);
    await finaliseJob(meta.serverUrl, meta.jobId, "error", {
      error: `The tab this ${meta.platform} job was working in disappeared (closed, or Chrome restarted) before it finished. `
        + `Check the platform, then publish again — or click the platform icon in the dashboard to mark it as listed.`,
    }).catch(() => {});
  }
}

async function pollJobs() {
  if (_pollLoopt) { _pollNogmaals = true; return; }
  _pollLoopt = true;
  try {
    await reconcileOrphanJobTabs();
    // Bovengrens puur als noodrem: blijft de server werk aanbieden dat nooit
    // afrondt, dan valt hij terug op de gewone klok in plaats van rond te tollen.
    for (let ronde = 0; ronde < 25; ronde++) {
      _pollNogmaals = false;
      const verzet = await pollJobsEenRonde();
      if (!verzet && !_pollNogmaals) break;
    }
  } finally {
    _pollLoopt = false;
  }
}

// Eén ronde langs alle platforms. Geeft terug of er werk is verzet.
async function pollJobsEenRonde() {
  let verzet = false;
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
        // Een scan leest je hele garderobe uit en duurt minuten. Zolang de ronde
        // dáárop stond te wachten, werd er in die tijd niets gepubliceerd: je
        // klikte op publiceren en er ging niet eens een tabblad open. Een scan
        // loopt nu naast de rest door — hij schrijft niets, en elk tabblad heeft
        // zijn eigen opdracht, dus ze kunnen elkaar niet in de weg zitten.
        if (job.action === "scan") {
          // Hooguit één scan tegelijk, ongeacht het platform: meer tabbladen
          // tegelijk maakt Chrome alleen maar trager.
          if (_lopendeScans.size > 0) continue;
          _lopendeScans.add(job.platform);
          processJob(job, serverUrl)
            .catch((e) => {
              console.error(`Omnivaleur scan ${job.id} (${job.platform}) threw:`, e);
              return reportError(job.id, serverUrl, `Extension error: ${e?.message || e}`).catch(() => {});
            })
            .finally(() => _lopendeScans.delete(job.platform));
          continue;
        }
        // Calm mode: de opdracht blijft gewoon klaarstaan, hij begint alleen
        // later. Niets gaat verloren; de gebruiker ziet hem in het dashboard
        // in de wachtrij staan.
        if (SCHRIJVENDE_ACTIES.has(job.action) && !(await calmMagNu())) continue;

        verzet = true;
        try {
          await processJob(job, serverUrl);
          if (SCHRIJVENDE_ACTIES.has(job.action)) {
            await calmVolgendeInplannen();
            await new Promise(r => setTimeout(r, MIN_GAP_MS));
          }
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
  return verzet;
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

// Eén vast, leeg "anker"-tabblad in het werkvenster.
//
// Zonder dit tabblad verdween het hele venster zodra het laatste job-tabblad
// dichtging, en werd er bij de volgende klus (of bij de volgende controle op
// verkopen/berichten, elke 10 tot 15 minuten) opnieuw een venster geopend. Dat
// is wat de gebruiker als "steeds weer die tabbladen" ziet. Met het anker
// blijft er precies één venster bestaan zolang de browser open is: het wordt
// hooguit uit- en weer ingeklapt.
//
// Meegenomen effect: het venster kan nu niet meer halverwege een klus
// omvallen doordat het vorige tabblad net iets te laat dichtging.
// Het anker is een eigen paginaatje van de extensie in plaats van een lege
// pagina. Daarmee is het venster ONMISKENBAAR van ons: we kunnen het altijd
// terugvinden, ook nadat de extensie is bijgewerkt of opnieuw is gestart.
//
// Dat was precies het lek. Het venster-nummer werd alleen in het werkgeheugen
// van de extensie bewaard, en dat wordt bij elke update gewist. Het oude venster
// bleef dan gewoon staan terwijl de extensie dacht dat ze er geen had — en maakte
// er een nieuwe bij. Na een dag bijwerken stonden er zeven, acht vensters.
const KEEPER_URL = chrome.runtime.getURL("keeper.html");

async function ensureKeeperTab(winId) {
  try {
    const tabs = await chrome.tabs.query({ windowId: winId });
    if (tabs.some(t => t.pinned && (t.url === KEEPER_URL || t.pendingUrl === KEEPER_URL))) return;
    await chrome.tabs.create({ url: KEEPER_URL, windowId: winId, pinned: true, active: false });
  } catch (_) { /* venster net weg — volgende klus maakt een nieuw venster */ }
}

// Zoek ons werkvenster terug aan het anker-tabblad, zonder op het geheugen te
// vertrouwen. Staan er meerdere (restanten van eerdere versies), dan houden we er
// één over en ruimen we de rest op — maar alleen als daar niets anders in staat
// dan het anker zelf, zodat er nooit werk van de gebruiker verloren gaat.
async function vindEnOpruimenWerkvensters() {
  let ankers = [];
  try { ankers = await chrome.tabs.query({ url: KEEPER_URL }); } catch (_) { return null; }
  // Vensters van vóór deze versie hadden een gewone lege pagina als anker. Die
  // staan nu verweesd op de balk; ze horen ook opgeruimd te worden. Alleen als
  // ALLES in dat venster leeg is — dan kan het niets van de gebruiker zijn.
  let oud = [];
  try {
    const blanco = await chrome.tabs.query({ url: "about:blank" });
    for (const winId of [...new Set(blanco.map(t => t.windowId))]) {
      const tabs = await chrome.tabs.query({ windowId: winId }).catch(() => []);
      if (tabs.length && tabs.every(t => t.url === "about:blank" || !t.url)) oud.push(winId);
    }
  } catch (_) { /* niet erg */ }
  for (const winId of oud) {
    console.log(`[Omnivaleur] leeg werkvenster van een vorige versie (${winId}) opgeruimd`);
    await chrome.windows.remove(winId).catch(() => {});
  }
  if (!ankers.length) return null;
  const vensters = [...new Set(ankers.map(t => t.windowId))];
  if (vensters.length === 1) return vensters[0];

  // Voorkeur voor het venster waar op dit moment nog werk in staat.
  let houden = vensters[0];
  for (const winId of vensters) {
    const tabs = await chrome.tabs.query({ windowId: winId }).catch(() => []);
    if (tabs.some(t => t.url !== KEEPER_URL && !t.pinned)) { houden = winId; break; }
  }
  for (const winId of vensters) {
    if (winId === houden) continue;
    const tabs = await chrome.tabs.query({ windowId: winId }).catch(() => []);
    const alleenAnker = tabs.length > 0 && tabs.every(t => t.url === KEEPER_URL || t.pendingUrl === KEEPER_URL);
    if (alleenAnker) {
      console.log(`[Omnivaleur] leeg werkvenster ${winId} opgeruimd (er was er al één)`);
      await chrome.windows.remove(winId).catch(() => {});
    }
  }
  return houden;
}

// Klapt het werkvenster vanzelf weer in zodra er geen klus meer in draait, zodat
// het na het plaatsen niet over het werk van de gebruiker blijft staan.
let _minimiseTimer = null;

function scheduleWorkerWindowMinimise() {
  if (_minimiseTimer) clearTimeout(_minimiseTimer);
  _minimiseTimer = setTimeout(async () => {
    _minimiseTimer = null;
    try {
      const id = await getWorkerWindowId();
      if (id == null) return;
      const tabs = await chrome.tabs.query({ windowId: id });
      // Alleen als er echt niets meer draait: alleen het anker-tabblad over.
      if (tabs.some(t => !t.pinned || t.url !== KEEPER_URL)) return;
      const win = await chrome.windows.get(id);
      if (win.state === "minimized") return;
      await chrome.windows.update(id, { state: "minimized" }).catch(() => {});
    } catch (_) { /* niets aan de hand */ }
  }, 4000);
}

chrome.tabs.onRemoved.addListener((_tabId, info) => {
  getWorkerWindowId().then((id) => {
    if (id != null && id === info.windowId && !info.isWindowClosing) scheduleWorkerWindowMinimise();
  }).catch(() => {});
});

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

// opts.silent → run MINIMISED, fully out of sight.
//
// Only safe for the recurring housekeeping scans (sold-check, notifications,
// Vinted wardrobe), because a minimised window's tabs count as hidden and Chrome
// then clamps their timers to >=1s (and to 1/min past five minutes). Those scans
// do their real work in one page-side fetch to the site's own JSON API, so slower
// timers cost nothing. The publish/delete flows are the opposite — long chains of
// short waits while filling a form — so they run in a normal (still unfocused)
// window, and un-minimise it if a scan left it minimised. Jobs are dispatched
// strictly one at a time, so the two modes can never fight over the window.
// Automatische achtergrondscans openen hun venster ALTIJD geminimaliseerd.
//
// De verkoop-controle en het tellen van berichten draaien uit zichzelf, elk uur,
// zonder dat de verkoper er iets voor doet. Die openden een gewoon venster, en
// dat is precies wat een verkoper beschreef: "als ik internet open, dan flitst
// die drie of vier keer weg en dan opent hij tweedehands.be, en dan kom ik er
// niet meer tussen". Werk dat jij niet gevraagd hebt mag je scherm niet afpakken.
function openStilWerkTabblad(url, callback) {
  return openWorkerTab(url, callback, { silent: true });
}

// STIL WERK OPENT NOOIT MEER EEN EIGEN VENSTER.
//
// Een geminimaliseerd venster is niet onzichtbaar. Chrome tekent het eerst en
// klapt het daarna in, en op een Mac zie je dat als een flits. Eén keer is
// vervelend, elk kwartier is onwerkbaar — gemeten klacht: "mijn scherm flitst
// nog steeds 4 a 5 keer weg, om de ca. 15 minuten". Bovendien sluit de verkoper
// dat venstertje, waarna de volgende ronde er weer een maakt: een flits die
// zichzelf in stand houdt.
//
// Een achtergrond-tabblad in het venster waar hij tóch al werkt flitst niet, pakt
// de aandacht niet en verdwijnt weer zodra de scan klaar is. Alleen als er geen
// enkel gewoon venster is (Chrome draait dan op de achtergrond) valt het terug
// op het oude gedrag.

// Een werk-tabblad openen dat we mógen aansturen.
//
// Eerst leeg openen, dan koppelen, dan pas navigeren. Andersom is te laat:
// zodra Marktplaats geladen is weigert Chrome de koppeling (zie koppelVroeg).
async function maakWerkTabblad(opties, url) {
  const tab = await chrome.tabs.create({ ...opties, url: "about:blank" });
  await koppelVroeg(tab.id, url);
  await chrome.tabs.update(tab.id, { url });
  // Een nieuw tabblad haalt het venster op macOS terug in beeld.
  await houdWerkvensterGeminimaliseerd();
  return tab;
}

async function openAchtergrondTabblad(url) {
  try {
    const vensters = await chrome.windows.getAll({ windowTypes: ["normal"] });
    const bruikbaar = vensters.find(w => w.state !== "minimized") || vensters[0];
    if (bruikbaar) {
      return await maakWerkTabblad({ windowId: bruikbaar.id, active: false }, url);
    }
  } catch (_) { /* val terug op het werkvenster */ }
  return null;
}

// Achtergrondwerk hoort te wachten tot de verkoper even niet aan het werk is.
// Er is geen enkele reden om precies tijdens het typen een tabblad te openen:
// deze scans hebben nergens haast mee. Na drie overgeslagen rondes gaat het toch
// door, anders zouden de cijfers bij iemand die de hele dag doorwerkt nooit meer
// bijwerken.
// RUSTIG OPSTARTEN.
//
// Bij het starten van Chrome vuurde alles tegelijk: de verkoopcontrole, het
// tellen van berichten, de garderobescan en de wachtrij met publicaties. Vier
// dingen die alle vier een tabblad willen, binnen een paar seconden. Dat is wat
// je ziet als "meerdere vensters tegelijk" zodra je je profiel opent, en het is
// ook precies het moment waarop de verkoper zijn browser wil gebruiken.
// Niets hiervan heeft haast; alles wordt uitgesmeerd over de eerste minuten.
const STARTTIJD_SLEUTEL = "browserStartOp";

async function markeerStart() {
  await chrome.storage.session.set({ [STARTTIJD_SLEUTEL]: Date.now() }).catch(() => {});
}
chrome.runtime.onStartup.addListener(() => { markeerStart().then(planStartWerk); });
chrome.runtime.onInstalled.addListener(() => { markeerStart().then(planStartWerk); });

// Hoe lang geleden Chrome startte. Onbekend (bijvoorbeeld na het herladen van
// de service worker) telt als "lang geleden": dan houden we niets tegen.
async function msSindsStart() {
  try {
    const { [STARTTIJD_SLEUTEL]: t } = await chrome.storage.session.get(STARTTIJD_SLEUTEL);
    return t ? Date.now() - t : Infinity;
  } catch { return Infinity; }
}

// Wachten doen we met een wekker, niet met setTimeout: een service worker in
// Manifest V3 wordt na een halve minuut stilte afgeschoten, dus een pauze van
// vijf minuten met setTimeout haalt het eind nooit.
const START_WEKKERS = {
  "start-sold": 3,
  "start-notif": 5,
  "start-vinted": 7,
};

function planStartWerk() {
  for (const [naam, minuten] of Object.entries(START_WEKKERS)) {
    chrome.alarms.create(naam, { delayInMinutes: minuten });
  }
}

// Draait dit werk te kort na het opstarten? Dan slaan we deze ronde over; de
// wekker hierboven pakt het straks alsnog op.
async function teVroegNaStart(minuten) {
  return (await msSindsStart()) < minuten * 60000;
}

chrome.alarms.onAlarm.addListener((alarm) => {
  switch (alarm.name) {
    case "start-sold":
      magStilScannenNu().then((mag) => { if (mag) { checkSoldListings(); checkVintedOrders(); } });
      break;
    case "start-notif":
      magStilScannenNu().then((mag) => { if (mag) scanNotifications(); });
      break;
    case "start-vinted": triggerVintedAutoScan(); break;
  }
});

const DRUK_SLEUTEL = "scanUitgesteld";
const MAX_UITGESTELD = 3;

async function magStilScannenNu() {
  let staat = "idle";
  try { staat = await chrome.idle.queryState(60); } catch (_) { return true; }
  if (staat !== "active") {
    await chrome.storage.session.set({ [DRUK_SLEUTEL]: 0 }).catch(() => {});
    return true;
  }
  const { [DRUK_SLEUTEL]: n = 0 } = await chrome.storage.session.get(DRUK_SLEUTEL).catch(() => ({}));
  if (n >= MAX_UITGESTELD) {
    await chrome.storage.session.set({ [DRUK_SLEUTEL]: 0 }).catch(() => {});
    return true;
  }
  await chrome.storage.session.set({ [DRUK_SLEUTEL]: n + 1 }).catch(() => {});
  return false;
}

// Eerst een achtergrond-tabblad in een bestaand venster; lukt dat niet, dan pas
// het oude, geminimaliseerde werkvenster.
function stilTabblad(url, callback) {
  openAchtergrondTabblad(url).then((tab) => {
    if (tab) { callback(tab); return; }
    openStilWerkTabblad(url, callback);
  }).catch(() => openStilWerkTabblad(url, callback));
}


// "SITE VERLATEN?" MAG NOOIT MEER IN BEELD KOMEN.
//
// Marktplaats en 2dehands hangen aan hun plaatsformulier een bevestigingsvraag
// bij het weggaan. Sluiten wij zo'n tabblad — na een geplaatste advertentie, of
// nadat een opdracht is afgerond — dan stelt Chrome die vraag aan de verkoper.
// Zolang hij niet klikt staat álles stil, ook het tabblad waarin op dat moment
// het volgende formulier wordt ingevuld: twee tabbladen van dezelfde site delen
// één proces. Dat is exact de melding "ik moet elke keer zelf op Verlaten
// drukken, en dan publiceert hij meteen".
//
// content/unload_guard.js draait in elke marktplaats/2dehands/vinted-pagina en
// onthoudt die meldingen zonder ze te blokkeren. Hier, vlak voor wij zelf het
// tabblad sluiten of wegsturen, zetten we ze uit. Doet de verkoper het zelf,
// dan krijgt hij zijn waarschuwing gewoon.
async function ontwapenAfsluitvraag(tabId) {
  if (tabId == null) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId }, world: "MAIN",
      func: () => {
        try { if (window.__ovDisarmUnload) return window.__ovDisarmUnload(); } catch (_) {}
        try { window.onbeforeunload = null; } catch (_) {}
        return 0;
      },
    });
  } catch (_) { /* tabblad al weg, of geen toegang: dan gewoon sluiten */ }
}

// Een werk-tabblad sluiten zonder dat de verkoper er iets van merkt.
// HET WERKVENSTER MOET GEMINIMALISEERD BLIJVEN.
//
// Eén keer minimaliseren is niet genoeg gebleken. Op macOS zet Chrome het venster
// terug zodra er een tabblad in wordt geopend of het laatste tabblad sluit —
// precies de twee momenten waarop de verkoper het scherm zag opklappen ("hij
// opent nog steeds een venster, op het einde"). Deze functie kost niets als het
// venster al klein staat en wordt daarom na elk van die momenten aangeroepen.
async function houdWerkvensterGeminimaliseerd() {
  try {
    const id = await getWorkerWindowId();
    if (id == null) return;
    const win = await chrome.windows.get(id).catch(() => null);
    if (!win || win.state === "minimized") return;
    await chrome.windows.update(id, { state: "minimized", focused: false }).catch(() => {});
  } catch (_) { /* nooit een klus laten vallen om een venster */ }
}

function sluitWerkTabblad(tabId, vertragingMs = 0) {
  if (tabId == null) return;
  const sluit = () => {
    ontwapenAfsluitvraag(tabId).finally(() => chrome.tabs.remove(tabId).catch(() => {}))
      .finally(() => houdWerkvensterGeminimaliseerd());
  };
  if (vertragingMs > 0) setTimeout(sluit, vertragingMs);
  else sluit();
}

// Een werk-tabblad naar een ander adres sturen. Ook een navigatie laat het
// formulier "wil je echt weg?" vragen, dus dezelfde ontwapening vooraf.
async function stuurWerkTabbladNaar(tabId, url) {
  await ontwapenAfsluitvraag(tabId);
  return new Promise((res, rej) => chrome.tabs.update(tabId, { url }, () =>
    chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res()));
}

// Tabbladen waar we al aan gekoppeld zijn (zie koppelVroeg).
const _vroegGekoppeld = new Set();

// KOPPELEN TERWIJL HET TABBLAD NOG LEEG IS.
//
// Chrome weigert een debugger-koppeling zodra er ergens in het tabblad een
// stukje van een ándere extensie zit: "Cannot access a chrome-extension:// URL
// of different extension". Op een volle Marktplaats-pagina met advertenties en
// meeleesextensies is dat kennelijk het geval — gemeten op 21-08-2026, twee
// koppelwegen, allebei geweigerd, op een doodgewone marktplaats.nl-pagina.
//
// Een leeg tabblad (about:blank) mag Chrome wél, en de koppeling blijft daarna
// gewoon staan als het tabblad naar Marktplaats navigeert. Dus koppelen we
// meteen bij het openen, vóór er iets geladen is.
// Alleen het plaatsformulier van Marktplaats/2dehands heeft de echte
// toetsaanslag nodig (het verborgen omschrijvingsveld — zie typEchteToets).
// Overal elders is de koppeling puur schade: Chrome zet dan de gele balk
// "'Omnivaleur' is begonnen met foutopsporing voor deze browser" boven het
// venster van de verkoper.
// Het inlogadres van Marktplaats en 2dehands. Waargenomen op 05-09-2026:
// /plaats/728/748 zonder sessie kwam uit op
// https://www.2dehands.be/identity/v2/login?target=%2Fplaats%2F728%2F748
const MP_LOGINPAGINA = /\/identity\/v\d+\/login|\/identity\/login|\/account\/login\b/i;

const HEEFT_TOETSEN_NODIG = /^https:\/\/(?:www\.)?(?:marktplaats\.nl|2dehands\.be)\/plaats\b/i;

async function koppelVroeg(tabId, url) {
  try {
    // GEEN GELE BALK WAAR HIJ NIETS OPLOST (30-08-2026).
    //
    // Deze koppeling stond bij ELK werk-tabblad aan: scannen, Vinted, eBay,
    // verwijderen. Chrome zet daar een balk voor neer die eruitziet als een
    // storing, mét een knop "Annuleren" die de koppeling verbreekt. Amanda
    // stuurde er een foto van als "een foutmelding wat betreft de browser" —
    // terwijl er niets aan de hand was. Nu koppelen we alleen nog waar het
    // écht nodig is: het plaatsformulier van Marktplaats en 2dehands.
    if (url && !HEEFT_TOETSEN_NODIG.test(String(url))) return false;
    if (_vroegGekoppeld.has(tabId)) return true;
    if (!(await heeftDebugger())) return false;
    await new Promise((res, rej) => chrome.debugger.attach({ tabId }, "1.3", () => {
      chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res();
    }));
    _vroegGekoppeld.add(tabId);
    return true;
  } catch (e) {
    console.warn("[Omnivaleur] vroeg koppelen mislukt:", e.message);
    return false;
  }
}

function ontkoppelVroeg(tabId) {
  if (!_vroegGekoppeld.has(tabId)) return;
  _vroegGekoppeld.delete(tabId);
  try { chrome.debugger.detach({ tabId }); } catch (_) {}
}

chrome.tabs.onRemoved.addListener((tabId) => _vroegGekoppeld.delete(tabId));

// DE KNOP "ANNULEREN" IN DE GELE BALK (04-09-2026).
//
// Chrome zet boven het venster een balk "'Omnivaleur' is begonnen met
// foutopsporing voor deze browser", mét een knop Annuleren. Egbert Brouwer
// stuurde er een foto van met een pijl naar precies die knop. Wie hem indrukt
// verbreekt de koppeling — en daar hing tot nu toe niets aan vast: onze lijst
// dacht nog dat we vastzaten, dus klikEcht stuurde zijn muisklik het niets in
// en typEchteToets sloeg het opnieuw koppelen over. Gevolg: het formulier staat
// volledig ingevuld op het scherm en er wordt nooit op Plaatsen gedrukt.
//
// Nu houden we het bij, zodat de volgende klik gewoon opnieuw koppelt.
chrome.debugger.onDetach.addListener((bron) => {
  if (bron && bron.tabId != null && _vroegGekoppeld.delete(bron.tabId)) {
    console.warn("[Omnivaleur] debugger-koppeling verbroken op tab", bron.tabId);
  }
});

function openWorkerTab(url, callback, opts = {}) {
  _workerWindowChain = _workerWindowChain
    .then(() => openWorkerTabInner(url, opts))
    .then(
      tab => callback(tab),
      err => { console.error("[Omnivaleur] openWorkerTab failed:", err); callback(null); }
    );
}

async function openWorkerTabInner(url, opts = {}) {
  // HET WERKVENSTER KOMT NOOIT MEER IN BEELD.
  //
  // Hier stond: scans ingeklapt, publiceren in een gewoon venster. Gevolg: bij
  // elke advertentie klapte het venster weer open over het werk van de verkoper
  // heen — "elke keer komt het scherm in beeld waar hij aan het listen is".
  // Publiceren hoort net zo onzichtbaar te zijn als de scans.
  //
  // De prijs is bekend en aanvaard: Chrome vertraagt korte pauzes in een
  // verborgen tabblad tot een seconde, dus invullen duurt wat langer. In de
  // praktijk gebeurde dat toch al — een venster dat achter de vensters van de
  // verkoper ligt, telt op een Mac ook als verborgen. Elke logregel uit het
  // formulier zet de bewaker opnieuw op scherp, dus trager werk wordt niet
  // afgebroken.
  const wantState = "minimized";
  let existing = await getWorkerWindowId();
  if (existing == null) {
    // Geen nummer in het geheugen (bijvoorbeeld na een update): kijk of ons
    // venster er nog staat vóór we er een nieuwe bij maken.
    existing = await vindEnOpruimenWerkvensters();
    if (existing != null) await setWorkerWindowId(existing);
  }
  if (existing != null) {
    try {
      const win = await chrome.windows.get(existing);
      if (win.state !== wantState) {
        // focused:false keeps this from ever pulling the user out of their work.
        await chrome.windows.update(existing, { state: wantState, focused: false }).catch(() => {});
      }
      // active:true is scoped to THAT window, so it never steals focus from the
      // user's foreground window — and does not un-minimise it either.
      await ensureKeeperTab(existing);
      const tab = await maakWerkTabblad({ windowId: existing, active: true }, url);
      // Het vorige job-tabblad wordt pas 2 seconden NA afronding gesloten. Valt
      // dat samen met het openen van het volgende, dan sluit Chrome het venster
      // (laatste tabblad weg) en neemt het nieuwe tabblad meteen mee — het
      // content-script sterft dan halverwege het invullen. Dat is precies waarom
      // twee platforms achter elkaar misging en één platform alleen wel lukte.
      // Controleer of het tabblad de tearing-down overleefde; anders een vers
      // venster.
      await new Promise(r => setTimeout(r, 150));
      const alive = await chrome.tabs.get(tab.id).catch(() => null);
      if (alive) return tab;
      await chrome.storage.session.remove(WORKER_WIN_KEY).catch(() => {});
    } catch {
      await chrome.storage.session.remove(WORKER_WIN_KEY).catch(() => {});
    }
  }
  try {
    // Chrome rejects state:"minimized" combined with an explicit size (and, on
    // some versions, with focused), so the minimised window is created bare and
    // degrades to a normal unfocused window rather than failing the whole job.
    // Leeg openen en pas daarna navigeren: alleen op een leeg tabblad laat
    // Chrome ons aan de toetsen komen (zie koppelVroeg).
    const leeg = "about:blank";
    const w = await chrome.windows.create({ url: leeg, focused: false, state: "minimized" })
      .catch(() => chrome.windows.create({ url: leeg, state: "minimized" }))
      .catch(() => chrome.windows.create({ url: leeg, focused: false, ...WORKER_WIN_SIZE }));
    if (!w || !w.tabs || !w.tabs[0]) throw new Error("no tab in new window");
    // NOG EEN KEER MINIMALISEREN, EXPLICIET.
    //
    // Op macOS weigert Chrome windows.create met state:"minimized" regelmatig;
    // dan valt hij hierboven terug op een gewoon venster en pópt er elke ronde
    // een Marktplaats-scherm open over het werk van de verkoper heen — ook als
    // hij het net zelf had geminimaliseerd. windows.update accepteert die stand
    // wél, ook direct na het aanmaken.
    await chrome.windows.update(w.id, { state: "minimized", focused: false }).catch(() => {});
    await setWorkerWindowId(w.id);
    // Anker erbij: vanaf nu blijft dit ene venster bestaan in plaats van bij
    // elke klus opnieuw op te poppen.
    await ensureKeeperTab(w.id);
    await koppelVroeg(w.tabs[0].id, url);
    await chrome.tabs.update(w.tabs[0].id, { url });
    // Navigeren kan het venster terugzetten; nog één keer wegduwen kost niets.
    await chrome.windows.update(w.id, { state: "minimized", focused: false }).catch(() => {});
    return w.tabs[0];
  } catch {
    // Window creation blocked (rare) — fall back to a plain background tab so
    // the job still runs rather than failing outright.
    return await maakWerkTabblad({ active: false }, url);
  }
}

// WAT ALS CHROME ONS DE SITE NIET LAAT ZIEN? (05-09-2026, Amanda Haas)
//
// In Chrome kun je per extensie instellen wanneer hij een site mag lezen: "Op
// alle sites", "Op specifieke sites" of "Als je erop klikt". Staat hij op dat
// laatste, dan moet de verkoper bij ELKE nieuwe pagina eerst op het icoontje
// rechts van de adresbalk klikken. Onze werk-tabbladen openen zichzelf, dus dan
// gebeurt er domweg niets: geen invulstap, geen foutmelding, en na drie minuten
// "Extension timed out waiting for this job to finish". Amanda beschreef precies
// dat: "moet er dan wel voor achter de pc blijven hangen".
//
// Chrome geeft dit gewoon eerlijk terug via permissions.contains(). Weten we het
// zeker, dan stoppen we meteen met een leesbare uitleg in plaats van de verkoper
// drie minuten te laten wachten op niets. Bij twijfel (een uitzondering, een
// onbekend kanaal) gaat de opdracht gewoon door — deze rem mag nooit werk
// tegenhouden dat het wél zou doen.
const SITE_ORIGINS = {
  marktplaats: ["https://www.marktplaats.nl/*"],
  "2dehands":  ["https://www.2dehands.be/*"],
  vinted:      ["https://www.vinted.nl/*", "https://www.vinted.be/*",
                "https://www.vinted.com/*", "https://www.vinted.de/*",
                "https://www.vinted.fr/*"],
  facebook:    ["https://www.facebook.com/*"],
};

const GEEN_SITETOEGANG =
  "Chrome laat Omnivaleur deze site alleen zien als je zelf op het icoontje "
  + "klikt, dus het werk-tabblad bleef leeg. Er is niets geplaatst of verwijderd. "
  + "Zet het eenmalig goed: klik rechts van de adresbalk op het puzzelstukje, dan "
  + "op de drie puntjes naast Omnivaleur, \"Deze extensie kan lezen en wijzigen\" "
  + "→ \"Op alle sites\". Daarna loopt de wachtrij vanzelf door.";

async function siteToegangOntbreekt(platform, payload) {
  let origins = SITE_ORIGINS[platform];
  if (!origins) return false;              // onbekend kanaal: nooit tegenhouden
  // Vinted leeft op één landdomein per account. Weten we welk, dan is dat het
  // enige dat telt; anders is één van de landen genoeg.
  const eigen = (payload || {})._create_origin;
  if (platform === "vinted" && eigen) {
    try { origins = [`${new URL(eigen).origin}/*`]; } catch (_) { /* laat staan */ }
  }
  try {
    for (const o of origins) {
      if (await chrome.permissions.contains({ origins: [o] })) return false;
    }
    return true;                            // Chrome zegt met zoveel woorden nee
  } catch (_) {
    return false;                           // niet kunnen vragen is geen bewijs
  }
}

async function processJob(job, serverUrl) {
  const headers = await getAuthHeaders();
  // Claim job first
  const claimRes = await fetch(`${serverUrl}/api/jobs/${job.id}/claim`, { method: "POST", headers });
  if (!claimRes.ok) return;

  // Eerst: mág deze kopie de site van dit kanaal überhaupt lezen? Zo niet, dan
  // heeft doorgaan geen enkele zin en kost het de verkoper drie minuten stilte.
  if (await siteToegangOntbreekt(job.platform, job.payload)) {
    await reportError(job.id, serverUrl, GEEN_SITETOEGANG);
    return;
  }

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

  // ── IS HIJ WEL INGELOGD OP VINTED? ────────────────────────────────────────
  //
  // Budgetheld, 01-09-2026: het dashboard zette een groen vinkje bij een
  // advertentie die helemaal niet op hun Vinted-profiel stond. De klant was op
  // dat moment niet ingelogd op Vinted.
  //
  // Uitgelogd levert Vinted op /items/new gewoon een pagina op — geen 401, geen
  // doorverwijzing die wij herkennen. Het invulscript loopt dan over een
  // formulier dat er niet is: elke stap mislukt stil (step() logt en gaat door),
  // de eindcontrole vindt geen veld en klaagt dus ook niet (een veld dat niet
  // bestaat is niet leeg), en daarna is elk /items/{cijfers} in de adresbalk
  // genoeg om de opdracht af te melden als geplaatst. Vandaar het vinkje bij
  // niets.
  //
  // Deze controle is het enige eerlijke antwoord op "ben je ingelogd": het
  // gaat langs Vinted's eigen endpoint, met de cookies van de browser. Komt daar
  // geen gebruiker uit, dan openen we geen tabblad en melden we de opdracht af
  // als mislukt, met wat de verkoper moet doen. Kunnen we het niet vaststellen
  // (netwerk, endpoint veranderd), dan gaat het gewoon door — een onzekere
  // controle mag geen werk tegenhouden.
  if (job.platform === "vinted" && job.action !== "scan") {
    const klaar = await vintedOriginKlaarzetten(job);
    if (!klaar.ok) { await reportError(job.id, serverUrl, klaar.melding); return; }
  }

  // Hetzelfde voor Marktplaats en 2dehands, en om dezelfde reden: zonder sessie
  // stuurt de site het plaatsadres door naar haar inlogpagina, waar ons
  // invulscript niet draait. Zie mpSessie voor de meting.
  if ((job.platform === "marktplaats" || job.platform === "2dehands")
      && (job.action === "create" || job.action === "content_refresh")) {
    const klaar = await mpPlaatsenKlaarzetten(job, serverUrl);
    if (!klaar.ok) { await reportError(job.id, serverUrl, klaar.melding); return; }
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

  console.log(`[Omnivaleur v${chrome.runtime.getManifest().version}] Opening tab for ${job.platform} job ${job.id}: ${url}`);
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
    chrome.storage.local.set({
      [`jobtab_${tab.id}`]: { ...job, jobId: job.id, serverUrl, startedAt: Date.now() },
    });
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

// ── "Het formulier is nooit opengegaan" ────────────────────────────────────
//
// GEMETEN, NIET GEGOKT (03-09-2026, Egbert Brouwer / papas-plectrums).
// Van zijn 305 opdrachten voor 2dehands is er nooit één geslaagd: 26 werden er
// door de bewaker hieronder afgebroken na exact drie minuten, telkens zonder
// één teken van leven uit het tabblad, en 279 stonden er nog achter. Zijn
// Marktplaats-opdrachten uit diezelfde ronde liepen wél door (15 scans, geen
// plaatsingen: naar Marktplaats is er nooit één opdracht aangemaakt), en
// bij andere verkopers slaagde 2dehands in dezelfde periode 97 keer. Het
// verschil zit dus niet in onze code en niet in de categorie, maar in de site:
// www.2dehands.be antwoordt op het plaatsadres met HTTP 401 zolang je daar niet
// bent ingelogd (nagemeten op 03-09-2026: twaalf bytes platte tekst, geen
// formulier). Op zo'n pagina draait ons invulscript helemaal niet, dus meldt
// niemand iets terug en loopt de bewaker af.
//
// Marktplaats.nl en 2dehands.be zijn twee aparte sites met twee aparte
// inlogsessies. Wie op de een is ingelogd, is dat op de ander niet vanzelf.
//
// Dat verschil is nu zichtbaar: heeft het invulscript zich gemeld, dan is het
// formulier echt opengegaan en is er iets ánders misgegaan. Heeft het zich niet
// gemeld, dan is de pagina nooit het formulier geweest — en dan is elke
// volgende opdracht op dat kanaal net zo kansloos.
const NIET_GESTART_PREFIX = "nietgestart_";
const NIET_GESTART_GRENS = 2;   // pas na twee op rij: één keer kan pech zijn

const SITE_NAAM = {
  marktplaats: "Marktplaats (marktplaats.nl)",
  "2dehands": "2dehands (2dehands.be)",
  vinted: "Vinted",
  facebook: "Facebook Marketplace",
};

// Neem in één keer alles terug wat nog voor dit kanaal in de wachtrij staat.
// Zonder dit bleef de rij hem 279 keer hetzelfde vertellen, drie en een halve
// minuut per keer: zestien uur waarin hij niets anders kon publiceren, want de
// extensie doet met opzet één opdracht tegelijk.
async function stopPlatformWachtrij(serverUrl, platform, reden) {
  try {
    const headers = await getAuthHeaders();
    const res = await fetch(`${serverUrl}/api/jobs/stop-platform`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ platform, reason: reden }),
    });
    const data = await res.json().catch(() => ({}));
    console.warn(`[Omnivaleur] ${platform}: wachtrij gestopt, ${data.cancelled ?? "?"} opdrachten teruggenomen.`);
  } catch (e) {
    console.error("[Omnivaleur] Wachtrij stoppen mislukt:", e);
  }
}

// Wat er op dat tabblad te zien was, gemeten in plaats van aangenomen.
//
// HIER STOND EEN CONCLUSIE, EN DIE WAS FOUT (03-09-2026). De vorige versie zei
// zonder voorbehoud "dat is hoe het eruitziet als je niet bent ingelogd".
// Egbert Brouwer kreeg die tekst dertig keer en was gewoon ingelogd. Wat we
// hadden was: het tabblad ging open en er kwam nooit iets terug. Dat is een
// waarneming van niets, en daar hoort geen oorzaak bij.
//
// Deze functie kijkt daarom eerst in het tabblad zelf. Dat kan: scannen doet
// hetzelfde en dat werkt bij hem wél. Het beslissende gegeven is het stempel
// dat content/shared.js achterlaat. Staat het er, dan is ons invulscript
// geladen en ligt het aan ons. Staat het er niet en zegt de pagina
// "Unauthorized" of vraagt ze om een wachtwoord, dan is het de inlog. Staat er
// iets anders, dan schrijven we op wat er stond in plaats van te gokken.
async function bekijkVastgelopenTabblad(tabId) {
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const tekst = (document.body?.innerText || "").trim();
        return {
          url: String(location.href).split("?")[0],
          titel: (document.title || "").slice(0, 120),
          begin: tekst.slice(0, 200),
          stempel: document.documentElement?.getAttribute("data-omnivaleur-cs") || null,
          velden: document.querySelectorAll("input, textarea, [contenteditable=true]").length,
          wachtwoordveld: !!document.querySelector('input[type="password"]'),
        };
      },
    });
    return res?.result || null;
  } catch (e) {
    console.warn("[Omnivaleur] Kon het vastgelopen tabblad niet bekijken:", e);
    return null;
  }
}

async function meldNooitBegonnen(tabId, meta) {
  const site = SITE_NAAM[meta.platform] || meta.platform;
  const f = await bekijkVastgelopenTabblad(tabId);

  const feiten = f
    ? ` [pagina: ${f.url}, titel ${JSON.stringify(f.titel)}, ${f.velden} invulveld(en), `
      + `invulscript geladen: ${f.stempel ? f.stempel : "nee"}${f.begin ? `, begint met ${JSON.stringify(f.begin.slice(0, 80))}` : ""}]`
    : " [het tabblad was al weg voordat we konden kijken]";

  let tekst;
  if (f && f.stempel) {
    // Ons eigen script stond er wel degelijk. Dan is het onze fout, en dat mag
    // een verkoper gewoon horen in plaats van naar zijn login gestuurd worden.
    tekst =
      `The ${site} listing form opened and our filling script did load, but it never got as far as `
      + `filling anything in. That is a fault on our side, not with your account or your login. `
      + `Nothing was published and nothing was changed on ${site}.` + feiten;
  } else if (f && (f.wachtwoordveld || /unauthorized|inloggen|log in|sign in/i.test(f.begin || ""))) {
    tekst =
      `The ${site} listing form never opened: that browser tab showed a login page instead. `
      + `Marktplaats and 2dehands are separate sites with separate logins, so being signed in to `
      + `one does not sign you in to the other. Open ${site}, sign in, and publish again.` + feiten;
  } else {
    tekst =
      `The ${site} listing form never opened: the page never reported back, so nothing was filled `
      + `in and nothing was published. We could not tell from here whether that page was a login `
      + `screen or something else, so the details we did see are below. Please send them to us.`
      + feiten;
  }

  await reportError(meta.jobId, meta.serverUrl, tekst).catch(() => {});
  // Er valt hier niets met de hand af te maken — er staat geen formulier. Het
  // tabblad openhouden levert alleen een stapel foutpagina's op.
  await chrome.storage.local.remove(`jobtab_${tabId}`);
  sluitWerkTabblad(tabId);

  const sleutel = `${NIET_GESTART_PREFIX}${meta.platform}`;
  const opgeslagen = await chrome.storage.local.get(sleutel);
  const opRij = (Number(opgeslagen[sleutel]) || 0) + 1;
  await chrome.storage.local.set({ [sleutel]: opRij });
  if (opRij >= NIET_GESTART_GRENS) {
    await chrome.storage.local.remove(sleutel);
    await stopPlatformWachtrij(meta.serverUrl, meta.platform, tekst);
  }
}

// Hoe lang een opdracht in totaal mag doen over zijn tab. Ruim onder de vijf
// minuten waarop de server een niet-afgemelde opdracht terugneemt.
const JOB_MAX_LIFETIME_MS = 4.5 * 60 * 1000;

// Teken van leven vanuit de tab: bewaker opnieuw opspannen, tenzij de opdracht
// al te lang loopt of al aan de gebruiker is teruggegeven.
function keepJobAlive(tabId) {
  if (tabId == null) return;
  chrome.storage.local.get(`jobtab_${tabId}`, (s) => {
    const meta = s[`jobtab_${tabId}`];
    if (!meta || meta.awaitingManualFinish) return;
    if (meta.startedAt && Date.now() - meta.startedAt > JOB_MAX_LIFETIME_MS) return;
    armJobWatchdog(tabId);
  });
}

function clearJobWatchdog(tabId) {
  if (tabId == null) return;
  chrome.alarms.clear(`${JOB_WATCHDOG_PREFIX}${tabId}`);
}

// Staat deze advertentie inmiddels gewoon op Vinted?
//
// De bevestiging "hij staat online" komt normaal uit het tabblad zelf, maar
// Vinted gooit bij het plaatsen de pagina om — en dan is het script dat de
// melding moest sturen al weg. Daarom kijkt de achtergrond hier zelf in de
// garderobe van de gebruiker, met dezelfde inlog als de browser. Vinden we de
// titel terug, dan is de advertentie geplaatst en melden we hem gewoon af, in
// plaats van een fout te tonen bij iets dat gelukt is.
// Titel vergelijkbaar maken: kleine letters, alleen letters en cijfers.
function _vintedTitelSleutel(t) {
  return String(t || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}
// Hetzelfde, maar zonder een voorloopnummer als "(1327) ". Dat nummer staat wel
// in het dashboard en niet altijd op het platform (of andersom), en op dat
// verschil liep de exacte vergelijking stuk.
function _vintedTitelZonderSku(t) {
  return _vintedTitelSleutel(String(t || "").replace(/^\s*\([^)]{1,24}\)\s*/, ""));
}

// OP WELK VINTED-DOMEIN IS DEZE VERKOPER INGELOGD? (04-09-2026, gemeten)
//
// Een Vinted-account leeft op één landdomein, en cookies reizen niet mee:
// vinted.nl en vinted.com zijn losse domeinen met losse sessies. Gemeten op
// 04-09-2026: https://www.vinted.com/api/v2/users/current geeft 401 zonder
// enige doorverwijzing naar het landdomein. Wie dus op vinted.nl is ingelogd,
// is voor vinted.com een vreemde.
//
// Daar liep de inlogcontrole op stuk. Een eerste plaatsing draagt geen
// _create_origin — dat zet alleen een herplaatsing, afgeleid uit het oude
// advertentieadres (backend/services/relist.py) — dus viel de controle terug op
// vinted.com, kreeg netjes 401 en meldde "je bent niet ingelogd op Vinted" aan
// iemand die zichtbaar was ingelogd op vinted.nl. Er werd niets geplaatst.
//
// Dezelfde aanname zat in het adres van het plaatsformulier zelf: vinted.com
// /items/new stuurt een uitgelogde bezoeker door naar
// /member/register/select_type (gemeten: HTTP 200 op dat registratieadres), dus
// ook zonder de controle viel daar niets in te vullen.
//
// Daarom zoeken we het domein op in plaats van het te gokken, en geven we dat
// door aan de rest van de opdracht.
const VINTED_ORIGINS = [
  "https://www.vinted.nl", "https://www.vinted.be", "https://www.vinted.de",
  "https://www.vinted.fr", "https://www.vinted.com",
];
const vintedKaalDomein = (o) => String(o || "").replace(/^https:\/\/(www\.)?/, "");

// Onthouden wat we vonden. Vijf vragen per opdracht is zonde als het antwoord
// een kwartier lang hetzelfde is; de gevonden waarde wordt hoe dan ook opnieuw
// nagelopen voordat hij gebruikt wordt.
let _vintedOriginCache = null;                 // { origin, at }
const VINTED_ORIGIN_TTL_MS = 15 * 60 * 1000;

// Geeft het origin waar een sessie leeft, `false` als élk domein hardop zegt dat
// er niemand is ingelogd, en `null` als we het niet konden vaststellen (netwerk,
// onderhoud). Bij `null` gaat het werk gewoon door: een onzekere controle mag
// nooit werk tegenhouden.
async function vintedIngelogdOrigin(voorkeur) {
  const kandidaten = [];
  const zet = (o) => { if (o && !kandidaten.includes(o)) kandidaten.push(o); };
  zet(voorkeur);
  if (_vintedOriginCache && Date.now() - _vintedOriginCache.at < VINTED_ORIGIN_TTL_MS) {
    zet(_vintedOriginCache.origin);
  }
  for (const o of VINTED_ORIGINS) zet(o);

  let ergensOnzeker = false;
  for (const origin of kandidaten) {
    const uitslag = await vintedIngelogd(origin);
    if (uitslag === true) { _vintedOriginCache = { origin, at: Date.now() }; return origin; }
    if (uitslag === null) ergensOnzeker = true;
  }
  _vintedOriginCache = null;
  return ergensOnzeker ? null : false;
}

// Zet de opdracht klaar op het domein waar de verkoper echt is ingelogd, en
// zeg het alleen dan af als geen enkel domein een sessie kent. Het gevonden
// origin gaat in _create_origin, want daar leest getMpSyiUrl het uit: zo opent
// het plaatsformulier op vinted.nl in plaats van op vinted.com.
async function vintedOriginKlaarzetten(job) {
  let voorkeur = job.payload && job.payload._create_origin;
  if (!voorkeur && job.payload && job.payload.platform_listing_url) {
    try { voorkeur = new URL(job.payload.platform_listing_url).origin; } catch (_) {}
  }
  const gevonden = await vintedIngelogdOrigin(voorkeur);
  if (gevonden === false) {
    return { ok: false, melding:
      "You are not signed in to Vinted in this browser, so nothing was published. " +
      "We checked " + VINTED_ORIGINS.map(vintedKaalDomein).join(", ") + ". " +
      "Open Vinted, log in there, and publish again." };
  }
  if (typeof gevonden === "string") {
    if (!job.payload) job.payload = {};
    job.payload._create_origin = gevonden;
  }
  return { ok: true, origin: typeof gevonden === "string" ? gevonden : null };
}

// Ingelogd op Vinted, ja/nee/onbekend. `null` = niet vast te stellen.
//
// credentials:"include" is hier geen sierlijkheid maar de kern: we willen exact
// weten wat de browser van de verkoper te zien krijgt, met zijn eigen cookies.
async function vintedIngelogd(origin) {
  try {
    const res = await fetch(`${origin}/api/v2/users/current`, {
      headers: { Accept: "application/json" }, credentials: "include",
    });
    if (res.status === 401 || res.status === 403) return false;
    if (!res.ok) return null;                       // 5xx, onderhoud: niet ons oordeel
    const data = await res.json().catch(() => null);
    if (!data) return null;
    return data.user && data.user.id ? true : false;
  } catch (_) {
    return null;                                    // geen netwerk: laat het werk door
  }
}

// ── Ingelogd op Marktplaats / 2dehands? ────────────────────────────────────
//
// GEMETEN OP 05-09-2026, IN EEN ECHTE BROWSER (Egbert Brouwer, papas-plectrums).
//
// Zijn 305 opdrachten voor 2dehands zijn alle 305 mislukt, en steeds op dezelfde
// manier: het tabblad ging open, er kwam nooit een teken van leven uit, en na
// exact drie minuten sloeg de bewaker toe. Nul voortgangsberichten, altijd
// 195 tot 230 seconden. Bij andere verkopers duurt een geslaagde plaatsing op
// 2dehands 10 tot 50 seconden. Het lag dus niet aan traagheid en niet aan de
// categorie: zijn categorienummers (728/748, muziek) bestaan op 2dehands.be
// precies zoals op marktplaats.nl, nagemeten via de openbare zoek-API.
//
// WAT ER WEL GEBEURT. Vraag je https://www.2dehands.be/plaats/728/748 op zonder
// sessie, dan krijg je in een browser GEEN foutpagina maar een doorverwijzing
// naar https://www.2dehands.be/identity/v2/login?target=... Ons invulscript
// luistert alleen op /plaats/*, dus op die inlogpagina draait het niet, meldt
// niemand iets terug, en wacht de bewaker drie minuten op stilte.
//
// De vorige verklaring ("het plaatsadres geeft 401") klopte alleen voor een
// kale aanvraag zonder cookies, en verklaarde niets: www.marktplaats.nl doet op
// hetzelfde adres exact hetzelfde.
//
// DE CONTROLE ZELF. /my-account/sell/api/listings is afgeschermd en verwijst
// NIET door: zonder sessie is het 401 met twaalf bytes "Unauthorized" (drie keer
// nagemeten: kale curl, een uitgelogde echte browser, en de scan van Egbert
// zelf), met sessie 200. Dat is dus een eerlijk ja of nee, en het is precies
// dezelfde aanpak als de Vinted-controle hierboven.
//
// Weten we het niet zeker (netwerkfout, 5xx, onderhoud), dan gaat het werk
// gewoon door. Een onzekere controle mag nooit een publicatie tegenhouden.
const MP_SESSIE_URL = {
  marktplaats: "https://www.marktplaats.nl/my-account/sell/api/listings?batchNumber=1&batchSize=1",
  "2dehands": "https://www.2dehands.be/my-account/sell/api/listings?batchNumber=1&batchSize=1",
};
const MP_INLOG_URL = {
  marktplaats: "https://www.marktplaats.nl",
  "2dehands": "https://www.2dehands.be",
};

async function mpSessie(platform) {
  const url = MP_SESSIE_URL[platform];
  if (!url) return { ingelogd: null, status: null };
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/json" }, credentials: "include",
    });
    if (res.status === 401 || res.status === 403) return { ingelogd: false, status: res.status };
    if (!res.ok) return { ingelogd: null, status: res.status };
    return { ingelogd: true, status: res.status };
  } catch (_) {
    return { ingelogd: null, status: null };   // geen netwerk: laat het werk door
  }
}

function mpNietIngelogdMelding(platform, status) {
  const site = SITE_NAAM[platform] || platform;
  return (
    `You are not signed in to ${site} in this browser, so nothing was published and no tab `
    + `was opened. We asked ${site} itself and it refused (HTTP ${status}). Marktplaats and `
    + `2dehands are separate sites with separate logins, so being signed in to one does not `
    + `sign you in to the other. Open ${MP_INLOG_URL[platform]}, sign in there, and publish again.`
  );
}

// Mag deze plaatsopdracht een tabblad openen?
//
// Nee betekent: geen tabblad, geen drie minuten wachten, en de rest van de
// wachtrij voor dit kanaal meteen stilgezet. Zonder dat laatste blijft hij
// honderden keren hetzelfde proberen: bij Egbert stonden er 274 opdrachten
// achter die stuk voor stuk kansloos waren.
async function mpPlaatsenKlaarzetten(job, serverUrl) {
  const { ingelogd, status } = await mpSessie(job.platform);
  if (ingelogd !== false) return { ok: true };
  const melding = mpNietIngelogdMelding(job.platform, status);
  await stopPlatformWachtrij(serverUrl, job.platform, melding).catch(() => {});
  return { ok: false, melding };
}

// Is advertentie {listingId} er een van deze verkoper zelf?
// true / false / null (niet vast te stellen).
//
// WAAROM DIT ER IS (01-09-2026, gemeten). De automatische herkenning hieronder
// (chrome.tabs.onUpdated) neemt ELK advertentie-adres dat in het werk-tabblad
// verschijnt voor "onze zojuist geplaatste advertentie". Zolang de extensie het
// tabblad bestuurt klopt dat. Maar is de verkoper niet ingelogd op Vinted, dan
// stuurt Vinted /items/new door naar /member/register/select_type (nagemeten op
// 01-09-2026: HTTP 200, geen foutmelding, geen plaatsformulier). Er valt daar
// niets in te vullen, dus gaat hij zelf klikken — en het tabblad blijft drie
// minuten open. Eén klik op een willekeurige advertentie levert
// /items/12345-een-slug op, en dát adres werd afgemeld als "geplaatst". Groen
// vinkje bij de advertentie van een vreemde, en bij een latere verwijdering
// wijst dat nummer naar diens advertentie. Precies wat Budgetheld zag.
//
// DE GRENS LIGT BEWUST BIJ "INGELOGD", NIET BIJ "STAAT IN DE KAST".
//
// Vinted laat een net geplaatste advertentie eerst door een controle lopen; hij
// verschijnt pas een minuut of twee later in de kast (daarom polst
// resolveCreatedVintedItem 90 seconden). "Nog niet in de kast" mag dus nooit
// "niet van jou" betekenen — dan zouden we een échte publicatie weggooien, en
// dat komt bij de verkoper terug als een mogelijk dubbele advertentie.
// Uitgelogd is wél beslissend: wie niet is ingelogd, kan onmogelijk zojuist iets
// geplaatst hebben. Dat is precies het geval dat we moeten tegenhouden, en het
// is met één vraag vast te stellen.
async function bgVintedEigenAdvertentie(origin, listingId, item) {
  const want = String(listingId);
  const ingelogd = await vintedIngelogd(origin);
  if (ingelogd === false) return false;   // uitgelogd: nooit van hem
  if (ingelogd !== true) return null;     // niet vast te stellen: laat het door

  // Wel ingelogd. Staat hij in de kast, dan is het een advertentie van hemzelf —
  // maar dat is niet genoeg. Nagemeten op 01-09-2026 in de echte database:
  // artikel (1353) Dark Green Suitsupply Cardigan droeg het nummer van (1352)
  // Navy Suitsupply Zip Vest. Beide van dezelfde verkoper, dus een eigendoms-
  // controle alleen had dit doorgelaten. Daarom vergelijken we ook de titel: die
  // van de kast hoort bij het artikel dat we zojuist plaatsten. Klopt dat niet,
  // dan is dit de verkeerde advertentie en melden we niets af.
  //
  // Staat hij nog niet in de kast (Vinted's controle duurt een minuut of twee),
  // dan zegt dat niets en geven we 'onbekend' terug — een echte publicatie mag
  // hier nooit sneuvelen.
  try {
    const me = await fetch(`${origin}/api/v2/users/current`, {
      headers: { Accept: "application/json" }, credentials: "include",
    });
    if (!me.ok) return null;
    const userId = (await me.json())?.user?.id;
    if (!userId) return null;
    const res = await fetch(
      `${origin}/api/v2/wardrobe/${userId}/items?order=newest_first&page=1&per_page=50`,
      { headers: { Accept: "application/json" }, credentials: "include" });
    if (!res.ok) return null;
    const items = (await res.json())?.items || [];
    const gevonden = items.find((it) => String(it.id) === want);
    if (!gevonden) return null;                 // nog niet geregistreerd: laat door
    if (!item) return true;                     // niets om mee te vergelijken
    return vintedTitelHoortBij(gevonden.title, item) ? true : false;
  } catch (_) {
    return null;
  }
}

// Hoort deze Vinted-titel bij dit dashboarditem? Ruimhartig, want Vinted toont de
// VERTAALDE titel en kapt lange titels af: het volstaat dat een van onze titels
// (met of zonder het SKU-nummer vooraan) erin voorkomt of ermee begint. Alleen
// als geen enkele vorm past, noemen we het een andere advertentie.
function vintedTitelHoortBij(vintedTitel, item) {
  const kaal = (t) => String(t || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  const zonderSku = (t) => kaal(String(t || "").replace(/^\s*\([^)]{1,24}\)\s*/, ""));
  const hun = kaal(vintedTitel);
  if (!hun) return true;                        // geen titel gekregen: niet ons oordeel
  const onze = [item.title, item.title_en, item.title_nl].filter(Boolean);
  if (!onze.length) return true;
  for (const t of onze) {
    for (const vorm of [kaal(t), zonderSku(t)]) {
      if (!vorm) continue;
      if (hun.includes(vorm) || vorm.includes(hun)) return true;
      const kop = vorm.slice(0, Math.max(12, Math.floor(vorm.length / 2)));
      if (kop && hun.startsWith(kop)) return true;
    }
  }
  // Het SKU-nummer is het hardste bewijs dat er is: dat vertaalt niet mee.
  const onsSku = (String(item.title || "").match(/^\s*\((\d{1,6})\)/) || [])[1];
  const hunSku = (String(vintedTitel || "").match(/^\s*\(?(\d{1,6})\)?\b/) || [])[1];
  if (onsSku && hunSku) return onsSku === hunSku;
  return false;
}

async function bgVindVintedAdvertentie(item) {
  const titel = _vintedTitelSleutel(item?.title);
  if (!titel) return null;
  const titelKaal = _vintedTitelZonderSku(item?.title);
  const origins = [item?._create_origin, ...VINTED_ORIGINS].filter(Boolean);
  for (const origin of [...new Set(origins)]) {
    try {
      const me = await fetch(`${origin}/api/v2/users/current`, {
        headers: { Accept: "application/json" }, credentials: "include",
      });
      if (!me.ok) continue;
      const userId = (await me.json())?.user?.id;
      if (!userId) continue;
      const res = await fetch(
        `${origin}/api/v2/wardrobe/${userId}/items?order=newest_first&page=1&per_page=50`,
        { headers: { Accept: "application/json" }, credentials: "include" });
      if (!res.ok) continue;
      const items = (await res.json())?.items || [];
      const levend = items.filter((it) => !it.is_closed && !it.is_draft);
      // Streng naar soepel, en elke stap moet PRECIES EEN kandidaat opleveren.
      // Bij twijfel liever niets koppelen dan de verkeerde advertentie: een
      // verkeerde koppeling betekent later de verkeerde advertentie weghalen.
      const uniek = (lijst) => (lijst.length === 1 ? lijst[0] : null);
      const hit =
        uniek(levend.filter((it) => _vintedTitelSleutel(it.title) === titel)) ||
        uniek(levend.filter((it) => _vintedTitelZonderSku(it.title) === titelKaal)) ||
        // Vinted kapt lange titels af; dan is de zijne een begin van de onze.
        (titelKaal.length >= 20
          ? uniek(levend.filter((it) => {
              const k = _vintedTitelZonderSku(it.title);
              return k.length >= 20 && (titelKaal.startsWith(k) || k.startsWith(titelKaal));
            }))
          : null);
      if (hit) return { id: String(hit.id), url: hit.url || `${origin}/items/${hit.id}` };
    } catch (_) { /* volgende domein */ }
  }
  return null;
}

async function fireJobWatchdog(tabId) {
  const key = `jobtab_${tabId}`;
  const stored = await chrome.storage.local.get(key);
  const meta = stored[key];
  if (!meta) return; // already resolved (JOB_DONE/JOB_ERROR cleared it)
  // A job deliberately handed back to the user to finish by hand is already
  // reported as an error and its tab is kept open on purpose — force-failing it
  // again would close the very tab they're still typing in.
  //
  // MAAR: hier stond alleen `return`, en daarmee keek er daarna NOOIT meer
  // iemand of de verkoper het zelf had afgemaakt. Maakte hij de advertentie
  // vervolgens met de hand af op Vinted, dan bleef het kaartje voor altijd
  // oranje "nog niet geplaatst" staan terwijl de advertentie gewoon online
  // stond. Gemeld op 26-08-2026, en het is precies het geval waarvoor deze
  // overdracht bedoeld is — dus juist hier hoort de controle thuis.
  if (meta.awaitingManualFinish) {
    if (meta.platform === "vinted" && (meta.action || "create") === "create") {
      const zelfGedaan = await bgVindVintedAdvertentie(meta.payload || meta).catch(() => null);
      if (zelfGedaan) {
        console.log(`[Omnivaleur] "${(meta.payload || meta).title}" is door de verkoper zelf afgemaakt op Vinted (${zelfGedaan.id}) — alsnog als geplaatst afgemeld.`);
        await finaliseJob(meta.serverUrl, meta.jobId, "complete", {
          platform_listing_id: zelfGedaan.id, platform_listing_url: zelfGedaan.url,
        });
        await chrome.storage.local.remove(`jobtab_${tabId}`);
      }
    }
    return;  // nooit force-failen: hij is misschien nog aan het typen
  }
  // Nooit een teken van leven uit het tabblad: dan is het formulier niet
  // opengegaan. Zie de toelichting bij meldNooitBegonnen — dit is een andere
  // storing dan "het formulier liep vast", en hij vraagt om een ander antwoord.
  if (!meta.scriptSeen) {
    console.warn(`[Omnivaleur] Watchdog: job ${meta.jobId} (${meta.platform}) — het invulscript heeft zich nooit gemeld; het formulier is niet opengegaan.`);
    await meldNooitBegonnen(tabId, meta);
    return;
  }
  console.warn(`[Omnivaleur] Watchdog: job ${meta.jobId} (${meta.platform}) on tab ${tabId} did not finish in time — force-failing.`);
  // Eerst kijken of het misschien gewoon gelukt is. Niets is verwarrender dan een
  // rode melding bij een advertentie die gewoon online staat.
  if (meta.platform === "vinted" && (meta.action || "create") === "create") {
    const gevonden = await bgVindVintedAdvertentie(meta.payload || meta).catch(() => null);
    if (gevonden) {
      console.log(`[Omnivaleur] Watchdog: "${(meta.payload || meta).title}" staat wél op Vinted (${gevonden.id}) — als geplaatst afgemeld.`);
      await finaliseJob(meta.serverUrl, meta.jobId, "complete", {
        platform_listing_id: gevonden.id, platform_listing_url: gevonden.url,
      }).catch(() => {});
      await chrome.storage.local.remove(key);
      sluitWerkTabblad(tabId);
      return;
    }
  }
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
  sluitWerkTabblad(tabId);
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (!alarm.name.startsWith(JOB_WATCHDOG_PREFIX)) return;
  fireJobWatchdog(Number(alarm.name.slice(JOB_WATCHDOG_PREFIX.length)));
});

// ── Background-driven delete for Marktplaats / 2dehands ───────────────────
// Navigates: homepage → clicks "Mijn [platform]" nav link → finds listing by
// title on the overview → clicks options → clicks Verwijder → confirms.
// No content script needed — all via executeScript from background.

// ─────────────────────────────────────────────────────────────────────────────
// VINTED: DE ADVERTENTIE WEGHALEN
//
// WAAROM DIT EEN APARTE FUNCTIE MET VASTE TEKSTEN IS (30-08-2026)
// Bij één verkoper mislukten acht verversingen op rij met "still in your
// wardrobe after confirming delete". Haar advertenties stonden aantoonbaar nog
// online, dus er was echt niets weggehaald. De oorzaak zat in twee aannames:
//
//   1. De knop werd alleen als /^delete$/ gezocht. Op vinted.nl heet hij
//      "Verwijderen", op .fr/.be "Supprimer", op .de "Löschen".
//   2. Werd het bevestigingsvenster niet herkend, dan zocht de bevestiging in
//      de HELE pagina en pakte hij het EERSTE element dat op "verwijderen"
//      leek — en dat is de knop op de pagina zelf. Die werd dus twee keer
//      aangeklikt, het venster ging open en weer dicht, en er gebeurde niets.
//      Op .fr en .de is dat gegarandeerd mis: daar heet de bevestigknop
//      LETTERLIJK hetzelfde als de knop op de pagina ("Supprimer", "Löschen").
//
// De teksten hieronder zijn geen gok. Ze komen uit Vinted's eigen tekstenboek,
// dat in elke artikelpagina meegestuurd wordt, opgehaald op 30-08-2026 voor
// vinted.nl, .be, .fr, .de en .com:
//
//   item.actions.delete                    → de knop op de pagina
//   item.deletion_modal.actions.delete     → "Bevestigen en verwijderen"
//   item.deletion_modal.actions.delete_v2  → "Ja, verwijderen"  (tweede variant)
//   item.deletion_modal.actions.cancel     → "Annuleren"
//   item.deletion_modal.title(_v2)         → de titel van het venster
//
// Er is GEEN stap waarin Vinted om een reden vraagt; het is één venster.
async function _mwVintedVerwijderen() {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const WEG = ["verwijderen", "supprimer", "löschen", "loschen", "delete",
               "eliminar", "elimina", "usuń", "usun", "ištrinti", "smazat"];
  const BEVESTIG = [
    "bevestigen en verwijderen", "ja, verwijderen",
    "confirmer et supprimer", "supprimer",
    "bestätigen und löschen", "bestatigen und loschen", "löschen", "loschen",
    "confirm and delete", "delete", "verwijderen",
    "confirmar y eliminar", "eliminar", "conferma ed elimina", "elimina",
    "ja", "yes", "oui",
  ];
  const ANNULEER = ["annuleren", "annuler", "abbrechen", "cancel", "cancelar",
                    "annulla", "terug", "back", "sluiten", "close", "nee", "no", "non"];
  const TITELS = ["artikel verwijderen", "advertentie verwijderen",
                  "supprimer l'article", "artikel löschen", "artikel loschen",
                  "delete item", "eliminar artículo", "elimina l'oggetto"];

  // ALLES WAT DEZE FUNCTIE GEBRUIKT MOET HIERBINNEN STAAN.
  //
  // Chrome injecteert alleen déze functie in de pagina; de rest van
  // background.js bestaat daar niet. Stond de hulpfunctie hieronder los, dan
  // gooide de pagina meteen een ReferenceError en kreeg de verkoper altijd
  // "Delete control not found" te zien, ongeacht wat er op het scherm stond.
  // Dat is op 30-08-2026 precies zo misgegaan. tests/test_vinted_verwijderknop.py
  // bewaakt dat er niets van buiten wordt aangeroepen.
  const tekst = e => (e.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
  const kaal = t => t.replace(/[?!.]+$/, "").trim();
  const zichtbaar = e => e.offsetParent !== null || e.getClientRects().length > 0;
  const knoppen = w => [...w.querySelectorAll('button, a, [role="menuitem"], [role="button"]')];
  const isWeg = e => WEG.includes(kaal(tekst(e))) || (e.dataset && e.dataset.testid || "").includes("delete");
  const schermbeeld = () => {
    const w = document.querySelector('[role="dialog"], [role="alertdialog"], [aria-modal="true"], '
                                     + '[data-testid*="modal"], .ReactModal__Content') || document;
    return knoppen(w).filter(zichtbaar).slice(0, 25)
      .map(e => tekst(e).slice(0, 30) + (e.dataset && e.dataset.testid ? `#${e.dataset.testid}` : ""))
      .filter(Boolean).join(" | ").slice(0, 400);
  };

  // 0) WACHTEN TOT DE PAGINA ER ECHT STAAT.
  //
  // Vinted bouwt de artikelpagina met JavaScript op. Kijken we te vroeg, dan is
  // er nog geen enkele knop en heet dat ten onrechte "Delete control not found".
  // Wachten tot er iets staat kost hooguit een paar seconden en scheelt een
  // mislukte verversing.
  for (let i = 0; i < 20; i++) {
    if (knoppen(document).some(zichtbaar)) break;
    await sleep(250);
  }

  // 1) De knop op de pagina zelf, eventueel achter het menu met de drie puntjes.
  let del = knoppen(document).find(e => zichtbaar(e) && isWeg(e));
  if (!del) {
    const menuknop = document.querySelector(
      '[data-testid="item-actions-button"], [data-testid="item-menu-button"], ' +
      '[data-testid="item-page-actions-dropdown-button"], [data-testid*="kebab"], ' +
      'button[aria-label*="more" i], button[aria-label*="actions" i], button[aria-label*="options" i]'
    );
    if (menuknop) {
      menuknop.click();
      await sleep(700);
      const menu = document.querySelector('[role="menu"], [role="listbox"], [data-testid*="dropdown"]') || document;
      del = knoppen(menu).find(isWeg) || knoppen(document).find(e => zichtbaar(e) && isWeg(e));
    }
  }
  if (!del) return { clickedDelete: false, opScherm: schermbeeld() };
  del.click();

  // 2) Wachten tot het bevestigingsvenster er echt staat. Herkenning op drie
  //    manieren, want Vinted wisselt van opmaak: de rol, of de titel uit hun
  //    eigen tekstenboek.
  let venster = null;
  for (let i = 0; i < 10 && !venster; i++) {
    await sleep(300);
    venster = document.querySelector('[role="dialog"], [role="alertdialog"], [aria-modal="true"], '
                                     + '[data-testid*="modal"], [data-testid*="dialog"], .ReactModal__Content');
    if (!venster) {
      const kop = [...document.querySelectorAll("h1,h2,h3,h4,[class*='title' i]")]
        .find(e => zichtbaar(e) && TITELS.includes(kaal(tekst(e))));
      if (kop) venster = kop.closest("div[class],section,form") || kop.parentElement;
    }
  }

  // 3) Bevestigen. NOOIT hetzelfde element nog een keer, en nooit "Annuleren".
  //    Zonder venster zoeken we in de hele pagina, maar dan van ACHTEREN naar
  //    voren: een venster wordt onderaan de body gehangen, de knop van de
  //    pagina staat erboven.
  const kandidaten = knoppen(venster || document)
    .filter(e => e !== del && zichtbaar(e) && !e.disabled)
    .filter(e => { const t = kaal(tekst(e)); return t && !ANNULEER.includes(t) && BEVESTIG.includes(t); });
  const bevestig = venster ? kandidaten[0] : kandidaten[kandidaten.length - 1];
  if (!bevestig) return { clickedDelete: true, clickedConfirm: false, venster: !!venster,
                          opScherm: schermbeeld() };
  bevestig.click();
  await sleep(1200);
  return { clickedDelete: true, clickedConfirm: true, venster: !!venster,
           bevestigd: kaal(tekst(bevestig)) };
}

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
      // lastError MOET gelezen worden, ook als we niets met de fout doen: anders
      // schreeuwt Chrome "Unchecked runtime.lastError: No tab with id" in de
      // console zodra het tabblad al weg is, wat als losse fout overkomt terwijl
      // het hier gewoon betekent dat we niets meer hoeven te wachten.
      if (chrome.runtime.lastError) {
        chrome.tabs.onUpdated.removeListener(fn);
        clearTimeout(timer);
        resolve();
        return;
      }
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

// Een advertentie verwijderen vanaf haar EIGEN pagina (/seller/view/{id}).
//
// Nodig voor verkopers van wie de advertenties niet op de gewone "Mijn
// advertenties"-pagina staan — zakelijke accounts bijvoorbeeld. Die pagina
// vinden we op advertentienummer, dus hier is geen titelvergelijking nodig en
// kan er per definitie geen verkeerde advertentie geraakt worden.
//
// Geeft true terug als er aantoonbaar iets is verwijderd. Bij twijfel false:
// "waarschijnlijk weg" melden als succes is de gevaarlijkste uitkomst, want dan
// wordt er een tweede advertentie naast de eerste geplaatst.
// Wat er op de advertentiepagina stond toen het verwijderen niet lukte. Reist
// mee in de foutmelding, want zonder dat is elke mislukking dezelfde ene zin.
let _laatsteVerwijderpagina = "niet gekeken";

async function verwijderViaAdvertentiepagina(tabId, adUrl, platform) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  try {
    await stuurWerkTabbladNaar(tabId, adUrl);
    await waitForTabLoad(tabId);
    await sleep(2500);

    const geklikt = await execInTab(tabId, async () => {
      const zichtbaar = el => el && el.offsetParent !== null && !el.disabled;
      const tekst = el => (el.textContent || "").replace(/\s+/g, " ").trim();
      // Alleen een knop die letterlijk verwijderen zegt. "Verkocht", "Bewerken"
      // en "Omhoog bellen" staan er vlak naast en mogen nooit geraakt worden.
      const WEG = /^(verwijder(en)?|advertentie verwijderen|delete|remove)( \(\d+\))?$/i;
      const knoppen = [...document.querySelectorAll('button, a[role="button"], [role="button"]')];
      const knop = knoppen.filter(zichtbaar).find(b => WEG.test(tekst(b)));
      if (!knop) return { ok: false, gezien: knoppen.filter(zichtbaar).map(tekst).slice(0, 12) };
      knop.click();
      return { ok: true };
    });
    if (!geklikt || !geklikt.ok) {
      // WELKE KNOPPEN STONDEN ER DAN WEL?
      //
      // Dit stond alleen in de console van de verkoper, en daar kijkt niemand.
      // Gevolg: 360 mislukte verwijderopdrachten in een week met exact dezelfde
      // zin "de verwijderknop kon niet worden gebruikt", en geen enkele manier
      // om te zien of de knop anders heet, achter een menu zit, of er helemaal
      // niet is. Nu reist die lijst mee naar het dashboard.
      const gezien = (geklikt && geklikt.gezien || []).join(" / ") || "geen enkele knop";
      console.log("[Omnivaleur] geen verwijderknop op de advertentiepagina:", gezien);
      _laatsteVerwijderpagina = gezien;
      return false;
    }

    // Bevestigen. Twee verschillende vensters mogelijk: een simpel "weet je het
    // zeker"-venstertje, ÓF (zoals ook bij de gewone lijst-verwijderroute
    // ontdekt) "Heb je '<titel>' verkocht via Marktplaats?" met precies twee
    // knoppen — "Niet verkocht via Marktplaats" en "Verkocht via Marktplaats".
    // Die laatste tekst matcht geen van de oude JA-woorden (geen "verwijder",
    // "ja", "bevestig", "delete", "confirm"), dus die knop werd nooit gevonden
    // en het venster bleef gewoon openstaan — de advertentie werd nooit
    // verwijderd. Zelfde oorzaak, zelfde oplossing als daar: eerst "niet
    // verkocht" beantwoorden (verkeerd antwoord boekt een valse verkoop), dan
    // een eventueel vervolgscherm afhandelen.
    await sleep(1200);
    const CONFIRM_STEPS = 3;
    for (let stap = 0; stap < CONFIRM_STEPS; stap++) {
      const res = await execInTab(tabId, async () => {
        const zichtbaar = el => el && el.offsetParent !== null && !el.disabled;
        const tekst = el => (el.textContent || "").replace(/\s+/g, " ").trim();
        const modal = [...document.querySelectorAll('.ReactModalPortal, [role="dialog"], [aria-modal="true"]')]
          .find(el => el.getClientRects().length > 0 && (el.innerText || "").trim());
        const scope = modal || document;
        const knoppen = [...scope.querySelectorAll('button, a[role="button"], [role="button"]')]
          .filter(zichtbaar);
        const knop =
          knoppen.find(b => /niet\s+verkocht/i.test(tekst(b))) ||
          knoppen.find(b => /^(verwijder(en)?|ja,? verwijder(en)?|bevestig(en)?|yes,? delete|delete|confirm|doorgaan|ok)\b/i.test(tekst(b)));
        if (!knop) return { open: !!modal, clicked: false };
        knop.click();
        return { open: true, clicked: true };
      });
      if (!res || !res.open) break;
      if (!res.clicked) break; // geen herkenbare knop meer — niets forceren
      await sleep(1500);
    }
    await sleep(1500);

    // Nakijken, niet aannemen. Pas als de advertentie aantoonbaar weg is melden
    // we succes.
    for (let poging = 0; poging < 3; poging++) {
      const weg = await execInTab(tabId, async (u) => {
        try {
          const r = await fetch(u, { credentials: "include", redirect: "follow" });
          if (r.status === 404 || r.status === 410) return true;
          if (!r.ok) return null;
          const html = (await r.text()).toLowerCase();
          return /niet meer beschikbaar|is verwijderd|verlopen advertentie|no longer available/.test(html);
        } catch (e) { return null; }
      }, [adUrl]).catch(() => null);
      if (weg === true) return true;
      await sleep(2000);
    }
    return false;
  } catch (e) {
    console.error("[Omnivaleur] verwijderen via advertentiepagina mislukt:", e);
    return false;
  }
}

// ── De advertentie vastleggen VOORDAT hij weggehaald wordt ────────────────
//
// WAAROM DIT ER MOET ZIJN.
//
// Herplaatsen is: weghalen en opnieuw plaatsen. De nieuwe advertentie wordt
// gebouwd uit wat er in Omnivaleur over het item bekend is — en van een
// geïmporteerde advertentie is dat maar ÉÉN foto. Marktplaats geeft in zijn
// zoeklijst namelijk alleen het omslagplaatje mee, niet de hele reeks. Gevolg:
// een advertentie met negen foto's kwam met één foto terug. Precies de melding
// "bij het herplaatsen neemt hij elke keer maar één foto mee".
//
// De volledige reeks staat wél op de advertentiepagina zelf, en die pagina
// hebben we op dit moment gewoon voor ons — vlak voor het verwijderen. We lezen
// de miniaturen uit de galerij (dat is meteen de juiste volgorde, dus de
// omslagfoto blijft de omslagfoto) en vragen van elke foto de grootste versie
// op. De server zet ze in de al klaarstaande plaatsingsopdracht.
const MP_FOTO_REGEL = "ecg_mp_eps$_86";   // grootste versie; live nagemeten

async function mpAdvertentieSnapshot(tabId) {
  try {
    const snap = await execInTab(tabId, async (regel) => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const uitUrl = (waarde) => {
        const m = /url\(\s*["']?([^"')]+)/i.exec(waarde || "");
        return m ? m[1] : null;
      };
      // Miniaturen dragen "Foto 3 van 9", dus de pagina zegt zelf hoeveel het er
      // zijn. Zolang we er minder zien blijven we even wachten: de galerij wordt
      // pas na het laden opgebouwd.
      const lees = () => {
        const knoppen = [...document.querySelectorAll('[class*="Thumbnails-module-item"]')];
        const urls = [];
        for (const k of knoppen) {
          const u = uitUrl(k.style && k.style.backgroundImage) ||
                    uitUrl(getComputedStyle(k).backgroundImage) ||
                    (k.querySelector("img") || {}).src;
          if (u) urls.push(u);
        }
        if (!urls.length) {
          // Advertentie met één foto: dan tekent Marktplaats geen miniatuurrij.
          const hoofd = [...document.querySelectorAll("img")]
            .map((i) => i.src || "")
            .filter((u) => /images\.(?:marktplaats|2dehands)\.com\/api\/v1\/[^/]+\/images\//.test(u));
          urls.push(...hoofd);
        }
        return urls;
      };
      let totaal = 0;
      const label = [...document.querySelectorAll('[aria-label*="van"]')]
        .map((e) => /(\d+)\s+van\s+(\d+)/.exec(e.getAttribute("aria-label") || ""))
        .find(Boolean);
      if (label) totaal = parseInt(label[2], 10) || 0;

      let beste = [];
      for (let poging = 0; poging < 10; poging++) {
        const nu = lees();
        if (nu.length > beste.length) beste = nu;
        if (totaal && beste.length >= totaal) break;
        if (!totaal && beste.length) break;
        // Miniaturen verderop in de rij worden pas geladen als ze in beeld
        // komen. Even langsscrollen dus, anders houden we er vijf van negen.
        const rij = document.querySelectorAll('[class*="Thumbnails-module-item"]');
        if (rij.length) {
          try { rij[rij.length - 1].scrollIntoView({ block: "nearest" }); } catch (_) {}
        }
        await sleep(500);
      }

      // Grootste versie opvragen en dubbele eruit: dezelfde foto staat vaak in
      // meerdere maten in de pagina.
      const gezien = new Set();
      const fotos = [];
      for (let u of beste) {
        if (!u) continue;
        if (u.startsWith("//")) u = "https:" + u;
        if (!/^https?:\/\//.test(u)) continue;
        const m = /\/images\/([0-9a-f-]{16,})/i.exec(u);
        const sleutel = m ? m[1] : u;
        if (gezien.has(sleutel)) continue;
        gezien.add(sleutel);
        fotos.push(u.split("?")[0] + "?rule=" + regel);
      }

      // "Kenmerken" van de advertentie zelf. Precies de velden waar het
      // dashboard om vraagt bij een geïmporteerde advertentie ("Vul merk en maat
      // aan voor Marktplaats & 2dehands") — ze stonden altijd al op de
      // advertentie, alleen niet in de zoeklijst waaruit geïmporteerd wordt.
      const kenmerk = {};
      for (const rij of document.querySelectorAll('[class*="Attributes-module-item"]')) {
        const label = (rij.querySelector('[class*="Attributes-module-label"]') || {}).innerText;
        const waarde = (rij.querySelector('[class*="Attributes-module-value"]') || {}).innerText;
        if (label && waarde) kenmerk[label.trim().toLowerCase()] = waarde.trim();
      }
      const conditieNaarOns = (w) => {
        const t = (w || "").toLowerCase();
        if (!t) return "";
        if (t.includes("nieuw met")) return "new_with_tags";
        if (t.includes("zo goed als nieuw")) return "good";
        if (t.includes("nieuw")) return "new";
        if (t.includes("beschadigd") || t.includes("defect")) return "poor";
        if (t.includes("gebruikt") || t.includes("gedragen")) return "fair";
        return "";
      };
      // Marktplaats zet maten soms in emmertjes ("Maat 46/48 (XL) of groter",
      // "Overige maten"). Alleen een maat die ook op een ander platform een maat
      // ís nemen we over; een emmertje zou daar onzin worden.
      const maatUit = (w) => {
        const t = (w || "").trim();
        if (!t) return "";
        const m = /\b(XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|XXXXL)\b/i.exec(t);
        if (m) return m[1].toUpperCase();
        const n = /^\s*(\d{2,3})\s*$/.exec(t);
        return n ? n[1] : "";
      };

      // DE CATEGORIE WAAR DEZE ADVERTENTIE ECHT IN STAAT.
      //
      // Marktplaats zet hem gewoon in de pagina:
      //   "l1CategoryId":1784,"l1CategoryName":"Postzegels en Munten",
      //   "l2CategoryId":1789,"l2CategoryName":"Bankbiljetten | Afrika"
      // Bij een verversing plaatsen we hem daarmee terug waar hij stond, in
      // plaats van in de categorie die wij uit de titel hebben geraden. Amanda
      // meldde precies dat: "hij zet deze dan in de verkeerde categorie. Dit
      // kun je bij MP niet aanpassen."
      const mp_category = (() => {
        try {
          const bron = document.documentElement.innerHTML;
          const nr = (naam) => {
            const m = new RegExp('"' + naam + '"\\s*:\\s*"?(\\d+)"?').exec(bron);
            return m ? parseInt(m[1], 10) : null;
          };
          const tekst = (naam) => {
            const m = new RegExp('"' + naam + '"\\s*:\\s*"([^"]{1,120})"').exec(bron);
            return m ? m[1] : "";
          };
          const l1 = nr("l1CategoryId"), l2 = nr("l2CategoryId");
          if (!l1 || !l2) return null;
          return { l1, l2, l1_naam: tekst("l1CategoryName"), l2_naam: tekst("l2CategoryName") };
        } catch (e) { return null; }
      })();

      const blok = document.querySelector('[class*="Description-module-description"]');
      return {
        photo_urls: fotos,
        foto_totaal: totaal || fotos.length,
        description: blok ? (blok.innerText || "").trim().slice(0, 20000) : "",
        brand: kenmerk["merk"] || "",
        size: maatUit(kenmerk["maat"] || kenmerk["kledingmaat"] || ""),
        color: kenmerk["kleur"] || "",
        condition: conditieNaarOns(kenmerk["conditie"] || kenmerk["staat"] || ""),
        mp_category,
      };
    }, [MP_FOTO_REGEL]);
    if (!snap) return {};
    if (!Array.isArray(snap.photo_urls) || !snap.photo_urls.length) {
      console.log("[Omnivaleur] snapshot: geen foto's gevonden op de advertentiepagina");
      snap.photo_urls = [];
    }
    console.log(`[Omnivaleur] snapshot: ${snap.photo_urls.length} van ${snap.foto_totaal} foto('s) vastgelegd`);
    return snap;
  } catch (e) {
    console.warn("[Omnivaleur] snapshot mislukt:", e && e.message);
    return {};
  }
}

async function bgDeleteMp2dh(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const platform = job.platform;
  const payload = job.payload || {};
  // De VOLLEDIGE titel — hij werd hier op 35 tekens afgekapt, en dan kan een
  // 1-op-1 vergelijking met de titel op de pagina per definitie nooit kloppen.
  const title = (payload.title || "").trim();
  const listingId = payload.platform_listing_id || "";
  // Het nummer waarmee elke advertentie begint: uit het SKU-veld, of anders uit
  // de "(1337)"-prefix die de verkoper zelf in de titel zet.
  const sku = String(payload.sku || (/^\s*\(([^)]{1,24})\)/.exec(payload.title || "") || [])[1] || "").trim();

  // Navigate directly to the seller's listings overview
  const overviewUrl = platform === "marktplaats"
    ? "https://www.marktplaats.nl/my-account/sell/index.html"
    : "https://www.2dehands.be/my-account/sell/index.html";

  // De echte advertentiepagina, als we die hebben. Daar staan alle foto's; op
  // het overzicht staat alleen het omslagplaatje.
  const adUrl = String(payload.platform_listing_url || "").trim();
  const startUrl = /^https:\/\/(?:www\.)?(?:marktplaats\.nl|2dehands\.be)\/v\//.test(adUrl)
    ? adUrl : overviewUrl;

  const tabId = await new Promise((res, rej) =>
    openWorkerTab(startUrl, t =>
      t ? res(t.id) : rej(new Error("could not open worker tab")), { silent: true }
    )
  );

  let snapshot = {};
  try {
    await waitForTabLoad(tabId);
    if (startUrl !== overviewUrl) {
      await sleep(1500);
      snapshot = await mpAdvertentieSnapshot(tabId);
      await stuurWerkTabbladNaar(tabId, overviewUrl);
      await waitForTabLoad(tabId);
    }
    await sleep(3000); // let React fully render listings
    await expandMp2dhOverview(tabId); // load ALL ads, not just the first 50

    // Find the listing's row and SELECT its checkbox. The "Mijn zoekertjes"
    // overview has NO per-card kebab/options menu — deletion is bulk-style:
    // tick the row's checkbox, then click the single red "Verwijder" button at
    // the top of the list, then confirm. (The old code hunted for an options
    // button that doesn't exist, clicked the last card button — "Omhoog
    // bellen"/"Sneller verkopen" — and removed nothing.)
    const findResult = await execInTab(tabId, (rawTitle, listingId, wantSku) => {
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

      const leaves = () => [...document.querySelectorAll("a, h1, h2, h3, span, p, div")]
        .filter(el => el.children.length === 0 && el.textContent.trim());

      // Zonder advertentienummer: 1-op-1 op de titel. Hoofdletters, accenten,
      // leestekens, dubbele spaties en een eventuele "(1337)"-prefix doen niet
      // mee; de rest moet exact kloppen. De oude vergelijking keek naar de eerste
      // 18 tekens met "bevat" — die vond óf niets (de titel op de pagina is
      // vertaald) óf de verkeerde advertentie.
      const norm = s => (s || "")
        .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/^\s*\([^)]{1,24}\)\s*/, "")
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
      const want = norm(rawTitle);
      let matchedBy = listingId && checkbox ? "id" : null;
      let ambiguous = false;

      if (!checkbox && wantSku) {
        const needle = `(${String(wantSku).trim().toLowerCase()})`;
        const hits = leaves().filter(e =>
          e.textContent.replace(/\s+/g, " ").trim().toLowerCase().startsWith(needle));
        const boxes = [...new Set(hits.map(rowFor).filter(Boolean))];
        if (boxes.length === 1) { checkbox = boxes[0]; matchedBy = "sku"; }
        else if (boxes.length > 1) ambiguous = true;
      }

      if (!checkbox && !ambiguous && want) {
        const boxes = [...new Set(
          leaves().filter(el => norm(el.textContent) === want).map(rowFor).filter(Boolean)
        )];
        if (boxes.length === 1) { checkbox = boxes[0]; matchedBy = "title"; }
        else if (boxes.length > 1) ambiguous = true;
      }

      // Laatste kans: de pagina kapt lange titels af met "…". Dan telt een begin
      // dat exact op onze titel past, mits het er maar één is.
      if (!checkbox && !ambiguous && want.length >= 12) {
        const boxes = [...new Set(
          leaves()
            .map(el => ({ el, t: norm(el.textContent) }))
            .filter(x => x.t.length >= 12 && want.startsWith(x.t))
            .map(x => rowFor(x.el)).filter(Boolean)
        )];
        if (boxes.length === 1) { checkbox = boxes[0]; matchedBy = "title-truncated"; }
        else if (boxes.length > 1) ambiguous = true;
      }

      if (ambiguous && !checkbox) return { found: false, ambiguous: true, rendered };
      if (!checkbox) return { found: false, rendered };

      // Draagt juist DEZE rij een verkocht-label? Dan is verwijderen het
      // verkeerde antwoord: de advertentie is via dit platform verkocht en dat
      // moet geboekt worden. Bewust streng: alleen een los labeltje dat exact
      // "verkocht"/"gereserveerd" is telt, zodat knoppen als "Verkocht? Meld
      // het" nooit voor een valse verkoop kunnen zorgen.
      let soldOnPlatform = false;
      const rowScope = checkbox.closest('article, li, tr') || checkbox.parentElement;
      if (rowScope) {
        soldOnPlatform = [...rowScope.querySelectorAll("span, div, p, strong, b, em")]
          .filter(el => el.children.length === 0)
          .some(el => /^(verkocht|gereserveerd|sold|reserved)$/i.test(el.textContent.replace(/\s+/g, " ").trim()));
      }
      if (soldOnPlatform) return { found: true, rendered, matchedBy, soldOnPlatform: true };

      if (!checkbox.checked) {
        checkbox.click();
        // Some React lists ignore a bare .click() — nudge with events too.
        checkbox.dispatchEvent(new Event("input", { bubbles: true }));
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return { found: true, rendered, matchedBy, selected: !!checkbox.checked };
    }, [title, listingId, sku]);

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
      if (findResult.ambiguous) {
        // Twee advertenties met exact dezelfde titel: gokken zou de verkeerde
        // verwijderen. Liever eerlijk stoppen.
        throw new Error(
          `There are several ${platform} listings with the title "${title}". ` +
          `Nothing was removed, to avoid deleting the wrong one — ` +
          `delete it by hand, or link the right listing via its URL.`
        );
      }
      // Niet gevonden tussen de advertenties die wél renderden. Dat betekende
      // tot nu toe meteen "hij is al weg" — en dus meldde het dashboard hem als
      // verwijderd terwijl hij gewoon nog online stond (bijvoorbeeld omdat de
      // advertentie onder een ander tabblad/filter van het overzicht valt).
      // Daarom eerst de advertentiepagina zelf opvragen: geeft die nog een
      // levende advertentie, dan is dit een echte fout, geen succes.
      // De verkoperspagina is de enige vorm die op een id alléén betrouwbaar
      // antwoordt. /v/listing/{id} en /v/a/{id} geven ALTIJD 404 — ook voor een
      // advertentie die gewoon online staat — en precies dat las deze controle
      // als bewijs dat hij weg was. Resultaat: het dashboard zette hem op
      // "verwijderd" terwijl hij bij Marktplaats nog gewoon te koop stond.
      const origin = new URL(overviewUrl).origin;
      const opgeslagen = payload.platform_listing_url || "";
      const adUrl = listingId ? `${origin}/seller/view/${listingId}`
                  : (/\/v\//.test(opgeslagen) ? opgeslagen : "");
      const live = adUrl ? await execInTab(tabId, async (u) => {
        try {
          const r = await fetch(u, { credentials: "include", redirect: "follow" });
          if (r.status === 404 || r.status === 410) return false;
          if (!r.ok) return null; // niets bewezen
          const html = (await r.text()).toLowerCase();
          if (/niet meer beschikbaar|is verwijderd|verlopen advertentie|not available|no longer available/.test(html)) return false;
          return true;
        } catch (e) { return null; }
      }, [adUrl]).catch(() => null) : null;

      if (live === true) {
        // NIET IN HET OVERZICHT, MAAR WEL ONLINE: VERWIJDER HEM DAN OP ZIJN
        // EIGEN PAGINA.
        //
        // Dit gaf tot nu toe een foutmelding en verder niets, en daarmee stond
        // de hele herplaatsing stil: de verwijderstap faalde, dus de opnieuw-
        // plaatsen-stap werd overgeslagen ("de oude staat nog live, een nieuwe
        // zou dubbelen"). Gemeten bij een verkoper met een zakelijk account:
        // zijn 1.221 advertenties staan gewoon online, maar niet op de gewone
        // "Mijn advertenties"-pagina, waardoor elke herplaatsing hierop strandde.
        //
        // De advertentiepagina zelf heeft wél een verwijderknop, en die pagina
        // vinden we op nummer — dus zonder titelvergelijking en zonder overzicht.
        console.log(`[Omnivaleur] bgDelete: "${title}" niet in het overzicht maar wel online — via ${adUrl}`);
        const gelukt = await verwijderViaAdvertentiepagina(tabId, adUrl, platform);
        if (gelukt) {
          await finaliseJob(serverUrl, job.id, "complete", { note: "deleted_via_ad_page" });
          return;
        }
        throw new Error(
          `"${title}" cannot be found in your ${platform} listings overview, and the delete button on its ` +
          `own page (${adUrl}) could not be used either. Nothing was removed — delete it by hand, or check ` +
          `that you are signed in to the right account. | Buttons on that page: ${_laatsteVerwijderpagina}`
        );
      }
      if (live !== false) {
        // Onbewezen is géén succes. "Waarschijnlijk weg" melden als verwijderd is
        // de gevaarlijkste uitkomst van de drie: de verkoper denkt dat hij eraf
        // staat, en hij staat er nog.
        throw new Error(
          `"${title}" cannot be found in your ${platform} listings overview, and we could not verify ` +
          `whether it is still online. Nothing was removed — check it by hand on ${platform}.`
        );
      }
      // Aantoonbaar weg = doel bereikt.
      console.log(`[Omnivaleur] bgDelete: "${title}" not among ${findResult.rendered} ${platform} ads and confirmed gone — marking done`);
      await finaliseJob(serverUrl, job.id, "complete", { note: "already_absent" });
      return;
    }
    if (findResult.soldOnPlatform) {
      console.log(`[Omnivaleur] bgDelete: "${title}" carries a sold label on ${platform} — reporting the sale instead of deleting`);
      await finaliseJob(serverUrl, job.id, "complete", { sold_on_platform: true, note: "sold_label_on_overview" });
      return;
    }
    if (!findResult.selected) {
      throw new Error(`Found "${title}" but couldn't tick its checkbox to delete it.`);
    }
    console.log(`[Omnivaleur] bgDelete: matched "${title}" on ${platform} by ${findResult.matchedBy || "unknown"}`);

    await sleep(600);

    // Click the top "Verwijder" (trash) button — now enabled by the selection.
    // The label carries a count once something is selected ("Verwijder (1)"), so
    // an exact-text match found nothing and the delete silently never started.
    const clickedDelete = await execInTab(tabId, () => {
      // ALLEEN DE KNOP DIE ÉCHT VERWIJDERT.
      //
      // Hier stond "de eerste knop waarvan de tekst met verwijder begint". Dat
      // is één woord te ruim: alles wat "Verwijder <iets>" heet — een opgeslagen
      // zoekopdracht, een filter, een bericht — staat vaak hoger op de pagina en
      // won dus altijd. Er werd dan netjes geklikt, er kwam geen venster, en de
      // verversing eindigde met "de advertentie staat er nog" zonder dat iemand
      // kon zien dat de verkeerde knop was geraakt.
      //
      // De echte knop is de bulk-knop boven de lijst, en die is te herkennen:
      // zijn tekst is precies "Verwijder"/"Verwijderen", eventueel met de
      // telling die Marktplaats erbij zet zodra er iets is aangevinkt
      // ("Verwijder (1)"). Een knop mét telling wint altijd van een knop zonder.
      const zichtbaar = e => !e.disabled && e.getAttribute("aria-disabled") !== "true"
        && e.getClientRects().length > 0;
      const tekst = e => (e.textContent || "").replace(/\s+/g, " ").trim();
      const PRECIES = /^(🗑\s*)?verwijder(en)?(\s*\(\d+\))?$/i;
      const knoppen = [...document.querySelectorAll('button, a, [role="button"]')].filter(zichtbaar);
      const passend = knoppen.filter(e => PRECIES.test(tekst(e)));
      const el = passend.find(e => /\(\d+\)/.test(tekst(e))) || passend[0];
      if (el) { el.click(); return { ok: true, geklikt: tekst(el) }; }
      return { ok: false, gezien: knoppen.map(tekst).filter(Boolean).slice(0, 15) };
    });

    if (!clickedDelete || !clickedDelete.ok) {
      // Welke knoppen stonden er dan wél? Zonder die lijst is elke mislukking
      // dezelfde ene zin en valt er niets aan te repareren. Zelfde les als bij
      // de verwijderknop op de advertentiepagina zelf.
      const gezien = (clickedDelete && clickedDelete.gezien || []).join(" / ") || "geen enkele knop";
      throw new Error(
        `The ${platform} "Verwijder" button above the list could not be used — the selection may not have ` +
        `registered, or the button was renamed. Nothing was deleted. | Buttons on that page: ${gezien}`
      );
    }
    console.log(`[Omnivaleur] bgDelete: klikte "${clickedDelete.geklikt}"`);

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

    // NAKIJKEN OP DE ADVERTENTIE ZELF, ALS WE HAAR NUMMER HEBBEN.
    //
    // Het overzicht is een wankele getuige bij een grote verkoper: het rendert
    // vijftig advertenties per keer en wij klikken maximaal veertig keer door.
    // Boven de tweeduizend advertenties staat de onze dus gewoon niet in beeld,
    // en "ik zie hem niet meer" betekent daar niets. Bij Egbert (5.540
    // advertenties) en Jaap (1.284) is dat de dagelijkse werkelijkheid.
    //
    // De advertentiepagina zelf antwoordt wél eenduidig, en die vinden we op
    // nummer. Geeft die aantoonbaar "weg", dan zijn we klaar; zegt hij dat de
    // advertentie nog leeft, dan is er niets verwijderd. Alleen als hij géén
    // uitsluitsel geeft vallen we terug op het overzicht hieronder.
    if (listingId) {
      const origin = new URL(overviewUrl).origin;
      const eigenUrl = `${origin}/seller/view/${listingId}`;
      for (let poging = 0; poging < 3; poging++) {
        const weg = await execInTab(tabId, async (u) => {
          try {
            const r = await fetch(u, { credentials: "include", redirect: "follow" });
            if (r.status === 404 || r.status === 410) return true;
            if (!r.ok) return null;
            const html = (await r.text()).toLowerCase();
            if (/niet meer beschikbaar|is verwijderd|verlopen advertentie|not available|no longer available/.test(html)) return true;
            return false;
          } catch (e) { return null; }
        }, [eigenUrl]).catch(() => null);
        if (weg === true) {
          const iets0 = snapshot && ((snapshot.photo_urls || []).length || snapshot.brand ||
                                     snapshot.size || snapshot.description);
          await finaliseJob(serverUrl, job.id, "complete", iets0 ? { captured_listing: snapshot } : {});
          console.log(`[Omnivaleur] bgDelete success (op de advertentiepagina bevestigd): ${platform} "${title}"`);
          return;
        }
        if (weg === false && poging === 2) {
          throw new Error(
            `"${title}" is still online on ${platform} (${eigenUrl}) after confirming the delete — ` +
            `nothing was removed, so no new listing was created. Check it by hand.`
          );
        }
        if (weg === false) { await sleep(2000); continue; }
        break; // geen uitsluitsel: het overzicht hieronder beslist
      }
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

    const naControle = await execInTab(tabId, (rawTitle, listingId, wantSku) => {
      // HOEVEEL ADVERTENTIES RENDERDE DEZE PAGINA?
      //
      // Precies dezelfde telling als bij het zoeken hierboven, en om precies
      // dezelfde reden — maar die stond hier niet, en dát is het gat waar de
      // dubbele advertenties uit kwamen. Na het bevestigen wordt het overzicht
      // herladen; valt de sessie daar weg, laadt de pagina te traag, of geeft
      // Marktplaats een foutpagina, dan staat er geen enkele advertentie op het
      // scherm. "Onze advertentie staat er niet meer" werd dan gelezen als
      // "verwijderd", de opdracht werd als geslaagd gemeld, en de tweede helft
      // van de verversing plaatste er een nieuwe naast — terwijl de oude gewoon
      // online stond. Vandaar: "aantal op Marktplaats is gegroeid".
      const rendered = new Set(
        [...document.querySelectorAll('a[href*="/v/"], a[href*="/seller/view/"]')]
          .map(a => ((a.getAttribute("href") || "").match(/(m\d{6,})/) || [])[1])
          .filter(Boolean)
      ).size;
      const norm = s => (s || "")
        .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/^\s*\([^)]{1,24}\)\s*/, "")
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
      const leaves = [...document.querySelectorAll("a, h1, h2, h3, span, p, div")]
        .filter(el => el.children.length === 0 && el.textContent.trim());
      // Dezelfde sleutels als bij het zoeken, zodat "weg" ook echt weg betekent
      // en niet "onder een net iets andere titel niet teruggevonden".
      const aanwezig = (() => {
        if (listingId && document.querySelector(`a[href*="${listingId}"]`)) return true;
        if (wantSku) {
          const needle = `(${String(wantSku).trim().toLowerCase()})`;
          if (leaves.some(e => e.textContent.replace(/\s+/g, " ").trim().toLowerCase().startsWith(needle))) return true;
        }
        const want = norm(rawTitle);
        if (!want) return false;
        return leaves.some(el => {
          const t = norm(el.textContent);
          return t && (t === want || (t.length >= 12 && want.startsWith(t)));
        });
      })();
      return { aanwezig, rendered };
    }, [title, listingId, sku]);

    if (naControle && naControle.aanwezig) {
      throw new Error(`Listing "${title}" still visible on ${overviewUrl} after confirming delete — removal was not verified`);
    }
    if ((!naControle || !naControle.rendered) && (findResult.rendered || 0) > 1) {
      // Geen enkele advertentie op het scherm bewijst niets. Dit als succes
      // melden is de duurste fout die dit bestand kan maken: de server zet de
      // advertentie op "verwijderd" en plaatst er daarna een tweede naast.
      //
      // We vergelijken met het aantal van VÓÓR het verwijderen, want nul kan ook
      // eerlijk zijn: wie zijn laatste advertentie ververst houdt een leeg
      // overzicht over. Stonden er eerst meer, dan hoort er nu ook nog wat te
      // staan — en is leeg dus een weggevallen sessie of een pagina die niet
      // laadde, niet een geslaagde verwijdering.
      throw new Error(
        `Couldn't confirm the removal: your ${platform} listings overview came back empty right after ` +
        `deleting, while it showed ${findResult.rendered} ads a moment earlier. That usually means the page ` +
        `didn't load or you were signed out — so we can't tell whether "${title}" is really gone. ` +
        `Check it by hand on ${platform}; no new listing was created.`
      );
    }

    // De vastgelegde advertentie gaat mee: de server zet de volledige fotoreeks
    // in de plaatsingsopdracht die hierna volgt (het tweede deel van een
    // herplaatsing). Zonder dit komt een geïmporteerde advertentie met één foto
    // terug.
    const iets = snapshot && ((snapshot.photo_urls || []).length || snapshot.brand ||
                             snapshot.size || snapshot.description);
    await finaliseJob(serverUrl, job.id, "complete", iets ? { captured_listing: snapshot } : {});
    console.log(`[Omnivaleur] bgDelete success: ${platform} listing "${title}"`);

  } finally {
    sluitWerkTabblad(tabId, 2500);
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
async function resolveVintedIdByTitle(title, sku) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const tabId = await new Promise((res, rej) =>
    openWorkerTab("https://www.vinted.nl/", t =>
      t ? res(t.id) : rej(new Error("could not open worker tab")), { silent: true }
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
      await stuurWerkTabbladNaar(tabId, idInfo.origin + "/");
      await waitForTabLoad(tabId);
      await sleep(1500);
    }

    const found = await execInTab(tabId, async (userId, wantTitle, wantSku) => {
      // 1-op-1 op de titel: hoofdletters, accenten, leestekens, dubbele spaties
      // en een eventuele "(1337)"-prefix doen niet mee, de rest moet exact gelijk
      // zijn. Dat werkt ook voor verkopers die geen nummer in hun titel zetten.
      // (Vroeger werd op de eerste 20 tekens vergeleken met "bevat", waardoor
      // twee "Beige Profuomo …"-advertenties door elkaar liepen.)
      const norm = s => (s || "")
        .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/^\s*\([^)]{1,24}\)\s*/, "")
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
      const want = norm(wantTitle);
      const sku = String(wantSku || "").trim().toLowerCase();
      const skuOf = t => {
        const m = /^\s*\(([^)]{1,24})\)/.exec(t || "");
        return m ? m[1].trim().toLowerCase() : "";
      };
      // Alles verzamelen en pas aan het eind beslissen: twee advertenties met
      // dezelfde titel betekent geen match, geen gok.
      const byTitle = [], bySku = [];
      try {
        for (let page = 1; page <= 60; page++) {
          const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=96`, { headers: { Accept: "application/json" } });
          if (!res.ok) return null;
          const data = await res.json();
          if (data.code && data.code !== 0) return null;
          const items = data.items || [];
          for (const it of items) {
            const entry = { id: String(it.id), closed: !!it.is_closed };
            if (want && norm(it.title) === want) byTitle.push(entry);
            if (sku && skuOf(it.title) === sku) bySku.push(entry);
          }
          const pg = data.pagination || {};
          if (items.length === 0) break;
          if (pg.total_pages && page >= pg.total_pages) break;
          if (!pg.total_pages && items.length < 96) break;
        }
        // Het nummer wint als het er is (exacter dan een titel), daarna de titel.
        if (bySku.length === 1) return bySku[0];
        if (byTitle.length === 1) return byTitle[0];
        if (bySku.length > 1 || byTitle.length > 1) return { ambiguous: true };
        return null;
      } catch (e) { return null; }
    }, [idInfo.userId, title, sku || ""]);

    if (found?.ambiguous) return { id: null, ambiguous: true, origin: idInfo.origin };
    return { id: found?.id || null, closed: !!found?.closed, origin: idInfo.origin };
  } finally {
    sluitWerkTabblad(tabId, 2500);
  }
}

// Draait IN het tabblad: wie ben ik op deze Vinted, en wat zegt mijn kast over
// deze advertentie? Alles wat deze functie gebruikt staat hierbinnen — Chrome
// injecteert alleen deze functie, de rest van background.js bestaat daar niet.
// Terug: { userId, present, closed }. present === null betekent "niet kunnen
// lezen" en is nooit hetzelfde als "niet aanwezig".
async function _mwVintedKast(lid) {
  const slaap = ms => new Promise(r => setTimeout(r, ms));
  let userId = null;
  // Eerst Vinted's eigen antwoord op "wie ben ik". Dat is één vraag, hij hangt
  // niet aan de opmaak van de pagina en niet aan een uitklapmenu dat in een
  // verborgen tabblad soms niet opengaat. Op 05-09-2026 liep het daar mis: de
  // startpagina gaf geen /member/-link, en de verkoper kreeg te horen dat hij
  // niet ingelogd was terwijl hij dat wel was.
  try {
    const res = await fetch("/api/v2/users/current", { headers: { Accept: "application/json" }, credentials: "include" });
    if (res.ok) {
      const data = await res.json().catch(() => null);
      if (data && data.user && data.user.id) userId = String(data.user.id);
    }
  } catch (e) {}
  const zoek = () => {
    for (const a of document.querySelectorAll('a[href*="/member/"]')) {
      const m = (a.getAttribute("href") || "").match(/\/member\/(\d+)/);
      if (m) return m[1];
    }
    return null;
  };
  if (!userId) userId = zoek();
  if (!userId) {
    document.querySelector('#user-menu-button, [data-testid="user-menu-button"]')?.click();
    await slaap(700);
    userId = zoek();
  }
  if (!userId) return { userId: null, present: null };
  try {
    for (let page = 1; page <= 60; page++) {
      const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=${page}&per_page=96`, { headers: { Accept: "application/json" } });
      if (!res.ok) return { userId, present: null };
      const data = await res.json();
      if (data.code && data.code !== 0) return { userId, present: null };
      const items = data.items || [];
      const mijn = items.find(it => String(it.id) === String(lid));
      if (mijn) return { userId, present: true, closed: !!mijn.is_closed };
      const pg = data.pagination || {};
      if (items.length === 0) return { userId, present: false };
      if (pg.total_pages && page >= pg.total_pages) return { userId, present: false };
      if (!pg.total_pages && items.length < 96) return { userId, present: false };
    }
    return { userId, present: null };
  } catch (e) { return { userId, present: null }; }
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
    const vintedSku = payload.sku || (/^\s*\(([^)]{1,24})\)/.exec(title) || [])[1] || "";
    const resolved = await resolveVintedIdByTitle(title, vintedSku);
    if (resolved?.ambiguous) {
      throw new Error(
        `You have several Vinted listings with the title "${title}". Nothing was removed, ` +
        `to avoid deleting the wrong one — link the right listing via its URL.`
      );
    }
    if (!resolved?.id) {
      throw new Error(`Could not locate "${title}" on Vinted to delist it. Open the listing on Vinted and use "mark as published" (paste its link) so it can be delisted.`);
    }
    // Al verkocht op Vinted: niet verwijderen, maar de verkoop melden. De server
    // boekt hem dan als verkocht en ruimt juist de ándere platforms op.
    if (resolved.closed) {
      console.log(`[Omnivaleur] bgDeleteVinted: "${title}" is closed (sold/ended) on Vinted — reporting the sale instead of deleting`);
      await finaliseJob(serverUrl, job.id, "complete", { sold_on_platform: true, note: "vinted_is_closed" });
      return;
    }
    listingId = resolved.id;
    resolvedOrigin = resolved.origin || "";
  }
  const url = payload.platform_listing_url
    || (resolvedOrigin ? `${resolvedOrigin}/items/${listingId}` : `https://www.vinted.com/items/${listingId}`);

  const tabId = await new Promise((res, rej) =>
    openWorkerTab(url, t =>
      t ? res(t.id) : rej(new Error("could not open worker tab")), { silent: true }
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
        // Vinted's eigen antwoord op "wie ben ik" gaat voor: dat hangt niet aan
        // de opmaak van de pagina en niet aan een uitklapmenu dat in een
        // verborgen tabblad soms niet opengaat. Zelfde reden als in
        // _mwVintedKast; zie tests/vinted-lidnummer-test.js.
        try {
          const res = await fetch("/api/v2/users/current", { headers: { Accept: "application/json" }, credentials: "include" });
          if (res.ok) {
            const data = await res.json().catch(() => null);
            if (data && data.user && data.user.id) return String(data.user.id);
          }
        } catch (e) {}
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
      if (!userId) {
        // Geen lidnummer op de pagina heeft twee heel verschillende oorzaken:
        // uitgelogd, of de advertentie bestaat niet meer (Vinted serveert dan
        // een 404-pagina zonder menu). Die twee zijn niet uit elkaar te houden
        // aan de DOM, en "je bent niet ingelogd" tegen iemand die wél ingelogd
        // is stuurt hem een uur de verkeerde kant op. De statuscode van de
        // pagina zelf is wel eenduidig en taalonafhankelijk.
        let httpStatus = 0;
        try {
          const r = await fetch(location.href, { headers: { Accept: "text/html" }, redirect: "follow" });
          httpStatus = r.status;
        } catch (e) { httpStatus = 0; }
        return { userId: null, httpStatus };
      }
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
          const mine = items.find(it => String(it.id) === String(lid));
          // is_closed = Vinted's own "sold or ended" flag. A sold listing stays
          // in the wardrobe, so this is the only way to tell it apart from one
          // that's still for sale — and it must never be deleted.
          if (mine) return { userId, present: true, closed: !!mine.is_closed };
          const pg = data.pagination || {};
          if (items.length === 0) return { userId, present: false };
          if (pg.total_pages && page >= pg.total_pages) return { userId, present: false };
          if (!pg.total_pages && items.length < 96) return { userId, present: false };
        }
        return { userId, present: null };  // never saw the end — don't claim absent
      } catch (e) { return { userId, present: null }; }
    }, [listingId]);

    if (!before?.userId && before?.httpStatus === 404) {
      // De advertentiepagina bestaat niet meer. Dat is nog geen antwoord op de
      // vraag wát er gebeurd is, en het verschil is groot: verkocht hoort als
      // verkoop geboekt te worden, weggehaald mag gewoon opnieuw geplaatst.
      // Vinted's eigen kast weet het, maar die is alleen te lezen vanaf een
      // pagina die wél bestaat — dus eerst naar de startpagina van hetzelfde
      // land. Zonder deze stap is een 404 niet te onderscheiden van uitgelogd,
      // en liep de herplaatsing dood op een melding over inloggen (Daniel,
      // 05-09-2026, twee artikelen op rij).
      const itemOrigin = new URL(url).origin;
      await stuurWerkTabbladNaar(tabId, itemOrigin + "/");
      await waitForTabLoad(tabId);
      await sleep(2000);
      let kast = await execInTab(tabId, _mwVintedKast, [listingId]);
      // Geen sessie op dít domein hoeft niet te betekenen dat hij uitgelogd is:
      // een sessie op vinted.nl weet niets van vinted.com en omgekeerd. Dus het
      // domein zoeken waar hij wél is ingelogd, en daar nog één keer kijken.
      if (!kast?.userId) {
        const ander = await vintedIngelogdOrigin(itemOrigin).catch(() => null);
        if (ander && ander !== itemOrigin) {
          await stuurWerkTabbladNaar(tabId, ander + "/");
          await waitForTabLoad(tabId);
          await sleep(2000);
          kast = await execInTab(tabId, _mwVintedKast, [listingId]);
        }
      }
      if (!kast?.userId) {
        throw new Error(`Could not determine your Vinted member id — make sure you're logged into this Vinted account.`);
      }
      if (kast.present === null) {
        throw new Error(`Could not read your Vinted wardrobe to check item ${listingId} — aborting to avoid an unverified delete.`);
      }
      if (kast.present && kast.closed) {
        console.log(`[Omnivaleur] bgDeleteVinted: item ${listingId} page is gone but the wardrobe says sold/ended — reporting the sale`);
        await finaliseJob(serverUrl, job.id, "complete", { sold_on_platform: true, note: "vinted_is_closed" });
        return;
      }
      if (kast.present) {
        throw new Error(`Vinted listing ${listingId} gives "Page not found" but is still in your wardrobe — nothing was removed. Try again later.`);
      }
      // Weg is weg: het doel van deze stap is bereikt. Als geslaagd afmelden,
      // zodat de herplaatsing gewoon doorloopt in plaats van dood te lopen.
      console.log(`[Omnivaleur] bgDeleteVinted: item ${listingId} bestaat niet meer op Vinted en staat niet in de kast — als al weg afgemeld`);
      await finaliseJob(serverUrl, job.id, "complete", { note: "already_absent" });
      return;
    }
    if (!before?.userId) throw new Error(`Could not determine your Vinted member id on the item page — make sure you're logged into this Vinted account.`);
    if (before.present === null) throw new Error(`Could not read your Vinted wardrobe to verify item ${listingId} — aborting to avoid an unverified delete.`);
    if (before.present === false) throw new Error(`Vinted item ${listingId} is not in your wardrobe — it may already be gone or belong to a different account; nothing to delete.`);
    if (before.closed) {
      // Verkocht (of beëindigd) op Vinted zelf: weghalen is fout — de verkoop
      // hoort erbij. Melden, dan boekt de server hem als verkocht.
      console.log(`[Omnivaleur] bgDeleteVinted: item ${listingId} is closed (sold/ended) on Vinted — reporting the sale instead of deleting`);
      await finaliseJob(serverUrl, job.id, "complete", { sold_on_platform: true, note: "vinted_is_closed" });
      return;
    }

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
    const clicked = await execInTab(tabId, _mwVintedVerwijderen);

    // De knoppen die er wél stonden gaan mee in de melding. Anders is dit
    // achteraf niet na te lopen zonder toegang tot het account van de verkoper.
    const opScherm = clicked?.opScherm ? ` Zichtbaar op het scherm: ${clicked.opScherm}` : "";
    // De knop is een aanwijzing, de kast is het bewijs. Op 05-09-2026 meldde
    // een herplaatsing "Delete control not found" terwijl advertentie
    // 7606902151 daarna aantoonbaar weg was (404 op vinted.nl én .com), en aan
    // het begin van diezelfde ronde stond hij nog gewoon in de kast — anders
    // was de melding "not in your wardrobe" geweest. Wie hier op de knop
    // afgaat, zegt "er is niets weggehaald, je advertentie staat nog online"
    // tegen iemand van wie de advertentie net weg is, en breekt de
    // herplaatsing af: het artikel blijft dan van álle kanten af. Dus: eerst
    // nameten, en pas klagen over de knop als hij er echt nog staat.
    const knopMislukt = !clicked?.clickedDelete
      ? `Delete control not found on Vinted item page for ID ${listingId} — Vinted may have changed its layout.${opScherm}`
      : !clicked.clickedConfirm
        ? `Confirm-delete button not found on Vinted for ID ${listingId} — deletion was not confirmed.${opScherm}`
        : "";

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
    if (!goneAfter && knopMislukt) throw new Error(knopMislukt);
    if (!goneAfter) {
      const rest = await execInTab(tabId, async () => {
        const v = document.querySelector('[role="dialog"], [role="alertdialog"], [data-testid*="modal"], .ReactModal__Content');
        if (!v) return "";
        return [...v.querySelectorAll('button, a, [role="button"], [role="radio"], input[type="radio"]')]
          .map(e => (e.textContent || e.value || "").trim().slice(0, 30) + (e.dataset.testid ? `#${e.dataset.testid}` : ""))
          .filter(Boolean).join(" | ").slice(0, 400);
      });
      // Staat er nog een venster open, dan is de bevestiging niet afgerond en
      // zegt dít precies welke knop er nog wachtte.
      throw new Error(`Vinted listing ${listingId} still in your wardrobe after confirming delete — removal was not verified.`
        + (rest ? ` Er stond nog een venster open met: ${rest}` : ""));
    }

    // The captured listing snapshot lets the backend enrich the paired relist
    // recreate job (imported items otherwise lack this data).
    if (knopMislukt) console.warn(`[Omnivaleur] bgDeleteVinted: ${knopMislukt} — maar ${listingId} is wél uit de kast verdwenen; als geslaagd afgemeld.`);
    await finaliseJob(serverUrl, job.id, "complete", { captured_listing: snapshot });
    console.log(`[Omnivaleur] bgDeleteVinted success: listing ${listingId}`, snapshot);
  } finally {
    sluitWerkTabblad(tabId, 2500);
  }
}

// ── Scan: read existing listings the user already has on a platform ───────
// Read-only — only reports candidates to /api/imports for manual review,
// never touches items/listings directly.

async function bgScanVinted(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const tabId = await new Promise((res, rej) =>
    openWorkerTab("https://www.vinted.nl/", t =>
      t ? res(t.id) : rej(new Error("could not open worker tab")), { silent: true }
    )
  );
  try {
    await reportProgress(serverUrl, job.id, { stage: "opening", message: "Opening Vinted…", current: 0, total: 0 });
    await waitForTabLoad(tabId);
    await sleep(2500);

    await reportProgress(serverUrl, job.id, { stage: "account", message: "Finding your Vinted account…", current: 0, total: 0 });
    // Find the numeric member id AND the real country origin (Vinted links to
    // your home country domain, e.g. vinted.nl, even from the .com entry page —
    // the items API only exists on that same origin, not on vinted.com).
    //
    // The member id used to be scraped from a /member/{id} link that only appears
    // after the avatar dropdown opens — a single 600ms wait that missed often
    // (this was the "Could not find member id" error that silently killed
    // sold-detection). Now we retry with growing waits and several sources:
    // open the menu, read anchor links, and — as a fallback — dig the id out of
    // the page's embedded JSON (Vinted ships it in the bootstrap data), which
    // doesn't depend on the dropdown rendering in time.
    let idInfo = { userId: null, origin: null };
    for (let attempt = 0; attempt < 4 && !idInfo.userId; attempt++) {
      await execInTab(tabId, () => {
        document.querySelector('#user-menu-button, [data-testid="user-menu-button"], header [aria-haspopup="true"]')?.click();
      });
      await sleep(500 + attempt * 700); // 500 / 1200 / 1900 / 2600ms
      idInfo = await execInTab(tabId, () => {
        // 1) The /member/{id} link (present once the dropdown is open).
        for (const link of document.querySelectorAll('a[href*="/member/"]')) {
          const href = link.getAttribute("href") || "";
          const m = href.match(/\/member\/(\d+)(?:[/?]|$)/);
          if (m) {
            let origin;
            try { origin = new URL(href, location.href).origin; } catch (e) { origin = location.origin; }
            return { userId: m[1], origin };
          }
        }
        // 2) Fallback: Vinted embeds the logged-in user's id in the page's
        //    bootstrap JSON — independent of any dropdown rendering.
        const html = document.documentElement.innerHTML;
        let m = html.match(/"user"\s*:\s*\{[^}]*?"id"\s*:\s*(\d+)/)
             || html.match(/"user_id"\s*:\s*(\d+)/)
             || html.match(/\\?"current_user_id\\?"\s*:\s*(\d+)/)
             || html.match(/\/member\/(\d+)/);
        if (m) return { userId: m[1], origin: location.origin };
        return { userId: null, origin: null };
      });
    }

    if (!idInfo?.userId) throw new Error("Could not find your logged-in Vinted account (member id) — make sure you're logged into Vinted in this browser tab.");

    // If the member link points at a different country domain, navigate there
    // so the items fetch is same-origin (and actually has the right catalog).
    const currentTab = await new Promise(res => chrome.tabs.get(tabId, res));
    if (idInfo.origin && currentTab?.url && new URL(currentTab.url).origin !== idInfo.origin) {
      await stuurWerkTabbladNaar(tabId, idInfo.origin + "/");
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
    // WAT WE AL HEBBEN, SLAAN WE OVER.
    //
    // Toon (dejuistetoon), 02-09-2026. Vinted heeft een budget: gemeten geeft
    // hij na een bui verzoeken 429 en laat daarna nog maar een handvol per
    // halve minuut door. Deze lus haalde élke scan alle ruim duizend
    // advertentiepagina's opnieuw op, ook die waarvan de tekst allang in het
    // dashboard stond — dus was het budget op vóór de advertenties die het
    // echt nodig hadden aan de beurt waren. Zijn drie scans van dezelfde kast
    // gaven 52, 776 en 507 advertenties zonder tekst.
    //
    // De server stuurt nu mee van welke nummers hij de tekst al heeft
    // (payload.tekst_bekend). Bij Toon zakt dat van 1.017 naar 52 pagina's.
    // Ontbreekt de lijst (oudere server), dan doen we gewoon wat we altijd deden.
    const alBekend = new Set((job.payload?.tekst_bekend || []).map(String));
    const openStaand = result.items.filter(it => !it.is_closed && !it.is_draft);
    const toEnrich = openStaand.filter(it => !alBekend.has(String(it.platform_listing_id)));
    const total = toEnrich.length;
    const skipped = result.items.length - total;
    const overgeslagen = openStaand.length - toEnrich.length;
    await reportProgress(serverUrl, job.id, {
      stage: "enriching",
      message: overgeslagen
        ? `Found ${result.items.length} listings — ${overgeslagen} already have their text, fetching ${total}…`
        : `Found ${result.items.length} listings (${total} still for sale) — fetching full details…`,
      current: 0, total,
    });
    let enriched = 0;
    try {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      const startedAt = Date.now();
      const noDesc = [];
      let idx = 0;
      let apiDood = false;   // /api/v2/items/{id} bleek 404 — niet meer proberen
      let knepen = 0;        // 429's op rij; MAX_KNEPEN keer = stoppen voor nu
      const MAX_KNEPEN = 3;
      for (const it of toEnrich) {
        let d = null;
        try {
          d = await execInTab(tabId, async (id, apiDood) => {
            const nap = ms => new Promise(r => setTimeout(r, ms));
            const out = { _status: null, _err: null, _tries: 0, description: "", color: "", material: "", brand: "", size: "", condition: "", photo_urls: [] };
            // Try the JSON detail endpoint (same-origin, carries the full
            // description that the wardrobe list omits). We try the DEFAULT
            // (localized) endpoint first — that's exactly what Vinted's item
            // page uses and what the seller sees, so it always carries the
            // visible description. `?localize=false` is only a fallback: for
            // some items it returns a null description, which was the bug.
            // GEEN VERZOEKEN VERSPILLEN AAN EEN DOOD ADRES.
            //
            // Gemeten 02-09-2026: /api/v2/items/{id} geeft 404, allebei de
            // varianten, ook zonder inloggen. Vinted heeft dit endpoint eruit
            // gehaald. Toch werden er per advertentie eerst twee verzoeken aan
            // besteed — en die tellen gewoon mee in Vinted's budget, dus was
            // twee derde van het budget op vóór de pagina aan de beurt was
            // waar de tekst wél op staat. In Toons eigen scanlogboek is dat
            // letterlijk terug te zien: "9739740557(api404/pg429)".
            //
            // Blijkt het bij de eerste advertentie 404, dan slaat de rest van
            // deze scan de API over en gaat meteen naar de pagina. Komt hij ooit
            // terug, dan pakken we hem vanzelf weer op.
            const urls = apiDood ? [] : [`/api/v2/items/${id}`, `/api/v2/items/${id}?localize=false`];
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
          }, [it.platform_listing_id, apiDood]);
        } catch (e) { d = null; }
        // Geeft de API 404, dan is dat geen pech bij déze advertentie maar een
        // adres dat Vinted heeft weggehaald. Vanaf nu overslaan, zodat het
        // budget naar de pagina gaat die de tekst wél draagt.
        if (!apiDood && d && d._status === 404) {
          apiDood = true;
          console.log("[Omnivaleur] Vinted item-API geeft 404 — rest van deze scan direct via de pagina");
        }
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
        // TEMPO, GEMETEN IN PLAATS VAN GESCHAT (02-09-2026).
        //
        // Vinted's advertentiepagina laat een bui van zo'n twintig verzoeken
        // toe en geeft daarna 429. Na een pauze van een halve minuut komen er
        // maar twee doorheen voordat hij weer dichtgaat. Hier stond 1.200 ms
        // als "harder terugtrekken" — dat is voor deze rem niets, dus liep een
        // grote scan na de eerste 429 gewoon leeg door te vragen: honderden
        // advertenties zonder tekst, en dat werden vroeger de lege waarden die
        // over de goede heen gingen.
        //
        // Nu: bij een 429 dertig seconden wachten. Blijft hij dichtzitten, dan
        // stoppen we met verrijken en leveren we op wat we wél hebben. De
        // volgende scan pakt precies de rest op, want de server stuurt mee wat
        // hij al heeft (tekst_bekend) — zo komt het in een paar rondes rond in
        // plaats van elke keer opnieuw op dezelfde muur te lopen.
        const geknepen = d && (d._status === 429 || d._pageStatus === 429);
        if (geknepen) {
          knepen++;
          if (knepen >= MAX_KNEPEN) {
            console.warn(`[Omnivaleur] Vinted blijft afknijpen na ${idx}/${total} — rest volgende scan`);
            await reportProgress(serverUrl, job.id, {
              stage: "enriching",
              message: `Vinted is rate-limiting — got ${enriched} of ${total}, the rest follows on the next scan`,
              current: idx, total,
            });
            break;
          }
          await sleep(30000);
        } else {
          knepen = 0;
          await sleep(200); // keeps the SW warm either way
        }
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
    sluitWerkTabblad(tabId, 2500);
  }
}

// Why a Marktplaats/2dehands scan came back with nothing.
//
// The old message ("are you logged in on this account?") was a guess, and it
// sent a business seller looking for a login problem he didn't have: a Pro /
// zakelijk account manages its adverts in the separate Admarkt console, so the
// personal "my listings" overview this scan reads is genuinely empty for him.
// Say which of the three it is, because the fix is different every time.
function mpEmptyScanReason(meta, platform) {
  const site = platform === "marktplaats" ? "Marktplaats" : "2dehands";
  // ALTIJD de waargenomen feiten erbij. Zonder dit was elke mislukte scan
  // dezelfde ene zin, en stond er in het opdrachtenlogboek van de server
  // twintig keer exact dezelfde tekst — waaruit niet valt op te maken of de
  // overzichtspagina 401 gaf, of hij gewoon leeg was, of de Admarkt-schakelaar
  // uitstond. Dat kostte bij Egbert Brouwer een week aan gokwerk.
  const feiten =
    ` [overzicht: API ${meta.api_status ?? "geen antwoord"}, ` +
    `${meta.fetched ?? 0} advertenties, ingelogd op ${site}: ${meta.signed_in ? "ja" : "nee"}` +
    (platform === "marktplaats"
      ? `, Admarkt-schakelaar: ${meta.admarkt_toegestaan ? "aan" : "uit"}` : "") + `]`;

  // DE BELANGRIJKSTE AFSLAG, EN HIJ STOND VROEGER ONDERAAN.
  //
  // Voor een zakelijke verkoper is het persoonlijke "Mijn advertenties"-
  // overzicht van www.marktplaats.nl per definitie leeg: zijn advertenties
  // staan in Admarkt, met een EIGEN inlog. Zo iemand is dus tegelijk "niet
  // ingelogd op www" én volkomen in orde. Staat de Admarkt-schakelaar dan uit,
  // dan kan Omnivaleur nergens kijken — en dat is het enige wat hij kan
  // oplossen. De oude volgorde zette "je bent niet ingelogd" er als eerste
  // overheen, waardoor die ene bruikbare aanwijzing nooit in beeld kwam.
  if (platform === "marktplaats" && !meta.admarkt_toegestaan) {
    return (meta.admarkt_ooit_aan
      ? `De Admarkt-schakelaar staat uit — eerder stond hij aan. Chrome zet zo'n `
        + `toestemming soms terug na een update van de extensie of een herstart. `
      : `Je persoonlijke advertentieoverzicht op ${site} is leeg. Dat is precies `
        + `hoe een zakelijk account eruitziet: die advertenties staan in Admarkt. `)
      + `Klik op het Omnivaleur-icoon in je browserbalk en zet "Business account `
      + `(Admarkt)" aan, en start de scan opnieuw. Heb je een gewoon particulier `
      + `account, controleer dan of je op ${site} zelf bent ingelogd.` + feiten;
  }

  // Pas hier mag "je bent niet ingelogd" klinken: Admarkt staat aan (of het is
  // 2dehands, dat geen Admarkt heeft) én ${site} weigerde ons echt.
  if (meta.api_status === 401 || meta.api_status === 403) {
    return `${site} weigert je advertentieoverzicht (foutcode ${meta.api_status}). `
      + `Open ${site}, log opnieuw in en start de scan nog een keer.` + feiten;
  }
  // EEN 200 IS HET BEWIJS DAT DE INLOG WERD GEACCEPTEERD (03-09-2026).
  //
  // Dit is de belangrijkste afslag van deze functie, en hij ontbrak. Het
  // advertentie-overzicht (/my-account/sell/api/listings) is afgeschermd:
  // zonder geldige sessie antwoordt het met HTTP 401, twaalf bytes "Unauthorized".
  // Nagemeten met een kale aanvraag zonder cookies, op 2dehands.be én op
  // marktplaats.nl — allebei 401. Krijgen wij dus een 200, dan heeft de site
  // die verkoper herkend en is hij per definitie ingelogd.
  //
  // Egbert Brouwer kreeg "You don't appear to be signed in to 2dehands" terwijl
  // in diezelfde melding "API 200" stond. Hij was ingelogd; hij had daar alleen
  // nog nooit een advertentie geplaatst, dus was de lijst leeg. Die ene zin
  // stuurde hem, en ons, een week de verkeerde kant op.
  if (meta.api_status === 200) {
    if (meta.total_entries) {
      return `${site} says your account has ${meta.total_entries} advert(s), but we could not read `
        + `a single one of them. That is a problem on our side, not with your login — `
        + `please report it so we can fix it.` + feiten;
    }
    return `You are signed in to ${site} — it recognised your account and answered us — but there `
      + `are no adverts on it, so there is nothing to import. If you do have adverts running on `
      + `${site}, they belong to a different account than the one you are signed in with in this `
      + `browser.` + feiten;
  }
  if (meta.signed_in === false) {
    return `You don't appear to be signed in to ${site} in this browser. `
      + `Open ${site}, sign in, and run the scan again.` + feiten;
  }
  return `Signed in fine, but ${site} shows no adverts on your personal "my listings" page. `
    + `If you do have adverts running, they are almost certainly managed through Admarkt — `
    + `${site}' separate platform for business sellers.` + feiten;
}

// ── Admarkt ────────────────────────────────────────────────────────────────
// De zakelijke kant van Marktplaats. Een verkoper met een zakelijk account
// beheert zijn advertenties op admarkt.marktplaats.nl en zijn persoonlijke
// "Mijn advertenties"-pagina is dan leeg — gemeten geval: 5.540 advertenties in
// Admarkt tegenover nul in het gewone overzicht.
//
// WAAROM WE HET ADRES NIET INTIKKEN. Ik heb geen zakelijk account en kan die
// pagina dus niet zelf bekijken; een geraden API-adres was een gok geweest die
// bij de eerste de beste wijziging omvalt. In plaats daarvan laat deze code de
// pagina gewoon zichzelf laden en kijkt daarna in `performance` welke verzoeken
// hij daarbij heeft gedaan. Dat is geen gok maar een waarneming: we halen
// precies dezelfde gegevens op als de pagina zelf. Wat hij gebruikt heeft komt
// mee terug in `meta`, zodat we het daarna hard kunnen vastleggen.
// `optional_host_permissions` in het manifest staat er om twee redenen, en beide
// zijn belangrijk genoeg om hier vast te leggen (in het manifest zelf kan geen
// commentaar staan — een zelfverzonnen "//"-sleutel is een onbekende sleutel en
// dat is precies het soort ding waar een winkelcontrole op afknapt):
//   1. Een update die een nieuwe VASTE host-toestemming toevoegt, zet Chrome bij
//      iedere bestaande gebruiker de extensie stil tot hij hem accepteert.
//   2. Alleen zakelijke verkopers hebben Admarkt nodig.
const ADMARKT_ORIGIN = "https://admarkt.marktplaats.nl";
// Exact de vorm die een zakelijk account zelf gebruikt (waargenomen bij Egbert
// Brouwer, 15-08-2026). De datumgrenzen staan er BEWUST in: zonder start- en
// einddatum weet ik niet welke standaardperiode de pagina kiest, en een lijst
// die stilletjes maar één maand beslaat lijkt op "bijna niks gevonden".
function admarktUrl() {
  const eind = new Date();
  const start = new Date(eind.getTime() - 365 * 86400000);
  const d = x => x.toISOString().slice(0, 10);
  return `${ADMARKT_ORIGIN}/advertisements?startDate=${d(start)}&endDate=${d(eind)}`
       + `&dateOption=last-365-days`;
}

// Hoeveel advertenties we in één keer meenemen. Een zakelijk account kan er
// tienduizenden hebben; alles in één ronde ophalen levert een scan op die lijkt
// te hangen. Elke volgende scan begint waar de vorige ophield (zie scan_offset),
// dus dit is een lading per keer en niet een plafond.
const ADMARKT_MAX = 2000;

async function admarktToegestaan() {
  try {
    const mag = await chrome.permissions.contains({ origins: [`${ADMARKT_ORIGIN}/*`] });
    // Onthouden DAT hij ooit aan stond. Een optionele toestemming kan in Chrome
    // stilletjes verdwijnen (update van de extensie, ander profiel, tweede
    // kopie). Zonder dit geheugen is "uit" niet te onderscheiden van "nooit
    // aangezet", en dat verschil bepaalt wat de verkoper moet doen.
    if (mag) { try { await chrome.storage.local.set({ admarkt_ooit_aan: true }); } catch (_) {} }
    return mag;
  } catch (_) { return false; }
}

async function admarktOoitAan() {
  try { return !!(await chrome.storage.local.get("admarkt_ooit_aan")).admarkt_ooit_aan; }
  catch (_) { return false; }
}

// WANNEER KIJKEN WE IN ADMARKT?
//
// Vroeger hing dat aan één ding: de optionele toestemming voor
// admarkt.marktplaats.nl. Dat is te wankel gebleken. Zo'n toestemming kan in
// Chrome verdwijnen zonder dat de verkoper er iets voor doet — een update, een
// tweede kopie van de extensie, een ander profiel — en dan valt de hele
// Admarkt-kant stil. Bij Egbert Brouwer gebeurde dat tussen 27-08 11:09 (2.000
// nieuwe advertenties binnengehaald) en 27-08 20:35 (vanaf dan twintig keer
// "je bent niet ingelogd"). Hij heeft niets aangeraakt.
//
// Twee dingen zijn daarom veranderd. De toestemming staat sinds 1.0.258 vast in
// het manifest (via https://*.marktplaats.nl/*), dus hij kan niet meer
// wegvallen. En de keuze om in Admarkt te kijken is nu een gewone voorkeur MET
// een vangnet: staat het persoonlijke overzicht leeg, dan kijken we sowieso in
// Admarkt. Precies het geval van een zakelijke verkoper — en het kost een
// particuliere verkoper niets, want die scan liep daar toch al op een fout uit.
async function admarktVoorkeurAan() {
  try {
    const opgeslagen = await chrome.storage.local.get(["admarkt_aan", "admarkt_ooit_aan"]);
    if (typeof opgeslagen.admarkt_aan === "boolean") return opgeslagen.admarkt_aan;
    return !!opgeslagen.admarkt_ooit_aan;   // wie hem ooit aanzette, houdt hem aan
  } catch (_) { return false; }
}

async function admarktMeenemen(persoonlijkGevonden) {
  if (!await admarktToegestaan()) return false;
  if (persoonlijkGevonden === 0) return true;
  return await admarktVoorkeurAan();
}

// De meekijker moet vóór de pagina-code draaien, en dat kan alleen met een
// aangemeld script — executeScript komt altijd te laat, want dan heeft de app
// haar gegevens al binnen. Aanmelden kan pas als de toestemming er is, dus dit
// gebeurt bij het opstarten en meteen nadat de gebruiker de schakelaar omzet.
const ADMARKT_SCRIPT_ID = "omnivaleur-admarkt";

async function zorgVoorAdmarktMeekijker() {
  if (!await admarktToegestaan()) return false;
  try {
    const al = await chrome.scripting.getRegisteredContentScripts({ ids: [ADMARKT_SCRIPT_ID] });
    if (al && al.length) return true;
  } catch (_) {}
  try {
    await chrome.scripting.registerContentScripts([{
      id: ADMARKT_SCRIPT_ID,
      matches: [`${ADMARKT_ORIGIN}/*`],
      js: ["content/admarkt_sniffer.js"],
      runAt: "document_start",
      world: "MAIN",
      persistAcrossSessions: true,
    }]);
    return true;
  } catch (e) {
    console.warn("[Omnivaleur] Admarkt-meekijker niet aangemeld:", e);
    return false;
  }
}

chrome.runtime.onStartup.addListener(() => { zorgVoorAdmarktMeekijker(); });
chrome.runtime.onInstalled.addListener(() => { zorgVoorAdmarktMeekijker(); });
// De schakelaar in de popup vraagt de toestemming; dit vangt het moment daarna.
if (chrome.permissions && chrome.permissions.onAdded) {
  chrome.permissions.onAdded.addListener(() => { zorgVoorAdmarktMeekijker(); });
}
if (chrome.permissions && chrome.permissions.onRemoved) {
  chrome.permissions.onRemoved.addListener(async () => {
    try { await chrome.scripting.unregisterContentScripts({ ids: [ADMARKT_SCRIPT_ID] }); } catch (_) {}
  });
}

async function bgScanAdmarkt(job, serverUrl) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // Zeker weten dat de meekijker klaarstaat vóór het tabblad opengaat; anders
  // heeft de pagina haar gegevens al binnen tegen de tijd dat wij kijken.
  await zorgVoorAdmarktMeekijker();

  const tabId = await new Promise((res, rej) =>
    openWorkerTab(admarktUrl(), t =>
      t ? res(t.id) : rej(new Error("could not open worker tab")), { silent: true }
    )
  );

  try {
    await waitForTabLoad(tabId);
    await sleep(6000);   // Admarkt rendert traag; de lijst komt na de pagina

    // Waar de vorige scan ophield. Zonder dit begon elke scan weer bij
    // advertentie 1 en kwam er niets nieuws bij, terwijl hij wel "klaar" meldde.
    const OVERSLAAN = Math.max(0, Number((job.payload || {}).scan_offset) || 0);
    // De nummers die de server al kent. Betrouwbaarder dan tellen: Admarkt geeft
    // zijn advertenties niet elke keer in dezelfde volgorde terug, dus "sla de
    // eerste 250 over" leverde drie scans lang exact dezelfde 250 op.
    const BEKEND = Array.isArray((job.payload || {}).bekende_ids)
      ? (job.payload || {}).bekende_ids.map(String) : [];

    const result = await execInTab(tabId, async (MAX, OVERSLAAN, BEKEND) => {
      const alBekend = new Set(BEKEND || []);
      // Admarkt praat tRPC: /api/trpc/<procedure>?batch=1&input=<json>, GET, op
      // de sessiecookie van de ingelogde verkoper. Waargenomen en uitgeprobeerd
      // op een echt zakelijk account (16-08-2026), niet geraden — raden kan hier
      // ook niet: élk onbekend PAD geeft HTTP 200 met de gewone pagina terug.
      // Een onbekende PROCEDURE geeft wél netjes 404, en dat is precies hoe
      // ad.getAds gevonden is.
      const roep = async (procedure, invoer) => {
        const url = `/api/trpc/${procedure}?batch=1&input=`
          + encodeURIComponent(JSON.stringify({ "0": invoer }));
        const res = await fetch(url, { headers: { Accept: "application/json" },
                                       credentials: "include" });
        const type = res.headers.get("content-type") || "";
        if (!res.ok || !/json/i.test(type)) {
          throw new Error(`${procedure} → HTTP ${res.status} ${type.split(";")[0]}`);
        }
        const body = await res.json();
        if (body && body[0] && body[0].error) {
          throw new Error(`${procedure} → ${String(body[0].error.message).slice(0, 200)}`);
        }
        return body[0].result.data;
      };

      const stappen = [];
      const items = [];
      let totaal = 0;
      let gezien = 0;   // hoeveel live advertenties we al voorbij hebben laten gaan

      // Advertenties hangen altijd onder een campagne; er is er minstens één,
      // ook bij wie er nooit een heeft aangemaakt ("Campagne zonder titel").
      const campagnes = (await roep("campaign.getAllCampaigns", {})).campaigns || [];
      stappen.push(`campagnes: ${campagnes.length}`);

      for (const c of campagnes) {
        let token = null;
        for (let pagina = 0; pagina < 250; pagina++) {
          const invoer = { campaignId: c.id };
          if (token) invoer.pageToken = token;
          const data = await roep("ad.getAds", invoer);
          const ads = data.ads || [];
          // Alleen op de EERSTE pagina meetellen. data.count is het totaal van
          // de hele campagne, niet van deze pagina — bij elke volgende pagina
          // er nog eens bij optellen maakte van 5.534 advertenties er 16.602.
          if (pagina === 0 && typeof data.count === "number") totaal += data.count;

          for (const ad of ads) {
            // Alleen wat live staat; gepauzeerd of verwijderd hoort niet als
            // bestaande advertentie geïmporteerd te worden.
            if (ad.status && ad.status !== "ACTIVE") continue;
            // Alles wat een eerdere scan al heeft opgehaald overslaan, zodat deze
            // ronde echt de vólgende lading oplevert.
            gezien++;
            // Kennen we hem al? Dan overslaan, waar hij ook in de rij stond.
            // Alleen als de server geen lijst meestuurde vallen we terug op de
            // oude telling (oudere server, of de lijst kon niet opgehaald worden).
            if (alBekend.size) {
              if (alBekend.has(String(ad.id))) continue;
            } else if (gezien <= OVERSLAAN) {
              continue;
            }
            const fotos = (ad.images || [])
              .filter(i => i && i.status !== "ERROR")
              .map(i => {
                const l = i.links || {};
                const beste = l["1024x1024"] || l["726x726"] || l["498x498"] || i.src;
                return !beste ? null
                  : beste.startsWith("//") ? `https:${beste}` : beste;
              })
              .filter(Boolean);

            items.push({
              platform_listing_id: String(ad.id),
              title: ad.title || "",
              // Admarkt kent GEEN prijs en GEEN omschrijving: het zijn advertenties
              // die naar de eigen webwinkel van de verkoper wijzen, niet naar een
              // Marktplaats-advertentie. Hier iets verzinnen zou erger zijn dan
              // leeg laten — de verkoper vult dit zelf aan bij het bevestigen.
              price: null,
              photo_url: fotos[0] || null,
              photo_urls: fotos,
              category_name: "",
              category_id: ad.categoryId != null ? String(ad.categoryId) : "",
              status: ad.status || "",
              // Bewust GEEN platform_listing_url: het enige adres dat Admarkt
              // geeft is de webwinkel van de verkoper. Dat als advertentielink
              // opslaan zou later een verkeerde pagina openen of verwijderen.
            });
            if (items.length >= MAX) break;
          }

          stappen.push(`campagne ${c.id} pagina ${pagina + 1}: ${ads.length} adv`);
          token = data.nextPageToken || null;
          if (!token || !ads.length || items.length >= MAX) break;
          await new Promise(r => setTimeout(r, 200));
        }
        if (items.length >= MAX) break;
      }

      return {
        items,
        meta: {
          bron: "trpc ad.getAds",
          totaal,
          gevonden: items.length,
          overgeslagen: alBekend.size || OVERSLAAN,
          rest: Math.max(0, totaal - (alBekend.size || 0) - items.length),
          stappen: stappen.slice(0, 25),
          zonder_prijs: items.length,
          pagina_titel: (document.title || "").slice(0, 120),
        },
      };
    }, [ADMARKT_MAX, OVERSLAAN, BEKEND]);

    console.log("[Omnivaleur] Admarkt:", JSON.stringify(result?.meta || {}));

    if (!result || !result.items || !result.items.length) {
      const m = (result && result.meta) || {};
      // Niets nieuws terwijl we al een deel binnen hadden: dan zijn we gewoon
      // aan het eind. Dat is klaar, geen fout.
      if ((OVERSLAAN > 0 || BEKEND.length) && m.totaal) return { items: [], meta: { ...m, klaar: true } };
      throw new Error(
        `Admarkt returned no live adverts. page="${m.pagina_titel || "?"}" ` +
        `steps=[${(m.stappen || []).join(" | ") || "none"}]`
      );
    }
    return result;
  } finally {
    sluitWerkTabblad(tabId, 2500);
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
      t ? res(t.id) : rej(new Error("could not open worker tab")), { silent: true }
    )
  );

  try {
    await waitForTabLoad(tabId);
    await sleep(3000); // let React fully render listings

    const result = await execInTab(tabId, async () => {
      const nap = ms => new Promise(r => setTimeout(r, ms));
      // Marktplaats returns its image urls PROTOCOL-relative ("//images.markt…").
      // Treating those as a site-relative path produced
      // "https://www.marktplaats.nl//images.marktplaats.com/…" — a 404, so every
      // imported thumbnail was blank.
      const abs = u => !u ? null
        : u.startsWith("http") ? u
        : u.startsWith("//") ? `https:${u}`
        : `${location.origin}${u.startsWith("/") ? "" : "/"}${u}`;

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
      let apiStatus = null;      // the HTTP status the overview API actually gave us

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
          if (res) apiStatus = res.status;
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
          api_status: apiStatus,
          // Alleen of we überhaupt ingelogd zijn. Of dit een zakelijk account
          // is, valt hier niet betrouwbaar aan de paginatekst af te lezen — dat
          // is geprobeerd en het gaf een verkeerd antwoord.
          // GEMETEN OP 03-09-2026, EN HET WAS FOUT.
          //
          // Deze zin stond er met alleen Marktplaats-woorden in, maar hij draait
          // óók op 2dehands. Een verkoper die daar keurig was ingelogd kreeg
          // daardoor "je bent niet ingelogd op 2dehands" te horen — Egbert
          // Brouwer, en hij mailde terug dat hij wél was ingelogd. Hij had
          // gelijk. Zie mpEmptyScanReason: wat de site ANTWOORDT weegt vanaf nu
          // zwaarder dan welk woord er toevallig op de pagina staat.
          signed_in: /uitloggen|log ?uit|afmelden|mijn marktplaats|mijn 2dehands|my account/i
            .test(document.body.innerText || ""),
        },
      };
    });

    if (!result || !result.items) throw new Error("Could not read your listings overview — page structure may have changed.");

    // Niets op het persoonlijke overzicht? Dan kijken we in Admarkt.
    //
    // HIER STOND EERST "en wel ingelogd", en dat maakte deze hele stap
    // onbereikbaar voor precies de mensen voor wie hij gebouwd is. Admarkt heeft
    // een ÉÉGEN inlog: een zakelijke verkoper kan prima in Admarkt zitten en
    // tegelijk uitgelogd zijn op www.marktplaats.nl. Die kreeg dan "je bent niet
    // ingelogd" te zien terwijl er niets mis was met zijn inlog — Egbert
    // Brouwer, 16-08-2026. Of we op www ingelogd zijn zegt niets over Admarkt,
    // dus dat mag deze stap niet tegenhouden.
    // ALTIJD ook Admarkt meenemen als de gebruiker dat aanheeft, niet alleen
    // wanneer het persoonlijke overzicht helemaal niets vindt.
    //
    // Egbert Brouwer (26-08-2026): zijn persoonlijke overzicht vindt wél iets
    // (~1000 advertenties) — dus deze stap sloeg vroeger altijd over, terwijl
    // de overige duizenden van zijn 5.534 advertenties uitsluitend via Admarkt
    // te vinden zijn. "Niets nieuws" op het persoonlijke overzicht werd dan
    // gemeld als "klaar, niets meer te doen" terwijl er nog duizenden open
    // stonden. Persoonlijke advertenties en Admarkt-advertenties zitten in
    // een andere nummerreeks (zie backend/services/mp_enrich.py), dus
    // samenvoegen op advertentienummer kan hier geen dubbele opleveren.
    let admarktFout = null;
    let admarktKlaar = false;
    if (platform === "marktplaats" && await admarktMeenemen(result.items.length)) {
      await reportProgress(serverUrl, job.id, {
        stage: "scanning",
        message: result.items.length
          ? `${result.items.length} op je persoonlijke overzicht — nu ook Admarkt erbij…`
          : "Nothing on your personal overview — checking Admarkt…",
        current: 0, total: 0,
      });
      try {
        const via = await bgScanAdmarkt(job, serverUrl);
        const bekend = new Set(result.items.map(it => it.platform_listing_id));
        for (const it of via.items) {
          if (!bekend.has(it.platform_listing_id)) result.items.push(it);
        }
        result.meta = {
          ...result.meta, ...via.meta,
          source: result.items.length && via.items.length ? "personal+admarkt" : (via.items.length ? "admarkt" : result.meta?.source),
        };
        // Admarkt heeft alles al gehad wat wij kennen. Dat is KLAAR, geen fout —
        // en zeker geen inlogprobleem. Voor een zakelijk account is het
        // persoonlijke overzicht altijd leeg, dus zonder deze afslag viel deze
        // ronde hieronder door naar "You don't appear to be signed in to
        // Marktplaats", terwijl er niets aan de hand was. Egbert Brouwer kreeg
        // die melding 18 keer en ging telkens zijn login controleren.
        admarktKlaar = !!via.meta?.klaar;
      } catch (e) {
        // Admarkt zelf gaf niets. Die melding is specifieker dan "geen
        // advertenties gevonden", dus die willen we terugzien — maar alleen
        // als het persoonlijke overzicht OOK niets had; anders verdringt een
        // Admarkt-foutmelding een prima geslaagde persoonlijke scan.
        if (!result.items.length) admarktFout = String(e && e.message ? e.message : e);
        else console.warn("[Omnivaleur] Admarkt-scan naast persoonlijk overzicht mislukt:", e);
      }
    }

    if (!result.items.length && admarktKlaar) {
      // Netjes afronden met nul nieuwe advertenties: het scherm meldt dan
      // "alles is al binnen" in plaats van een verzonnen fout.
      await finaliseJob(serverUrl, job.id, "complete", {
        listings: [], scan_meta: { ...(result.meta || {}), klaar: true },
      });
      console.log("[Omnivaleur] Admarkt: niets nieuws meer — scan afgerond.");
      return;
    }
    if (!result.items.length) {
      if (admarktFout) throw new Error(`Admarkt: ${admarktFout}`);
      const admarktAan = await admarktMeenemen(0);
      // EEN LEEG ACCOUNT IS GEEN STORING (03-09-2026).
      //
      // Wie op 2dehands nog nooit iets heeft geplaatst, hééft daar geen
      // advertenties. Dat meldden we als rode fout met de tekst "je bent niet
      // ingelogd" erbij, en dat is twee keer onwaar. Voorwaarde om het rustig
      // af te ronden: de site gaf een 200 (dus de inlog werd geaccepteerd) én
      // zegt zelf dat er niets staat. Zegt hij een aantal en lezen wij er nul,
      // dan is er wél iets stuk en blijft het een fout — zie mpEmptyScanReason.
      const echtLeeg = result.meta?.api_status === 200 && !result.meta?.total_entries;
      const admarktKanNogWat = platform === "marktplaats" && !admarktAan;
      if (echtLeeg && !admarktKanNogWat) {
        await finaliseJob(serverUrl, job.id, "complete", {
          listings: [], scan_meta: { ...(result.meta || {}), klaar: true, leeg_account: true },
        });
        console.log(`[Omnivaleur] ${platform}: ingelogd, maar dit account heeft daar geen advertenties — scan netjes afgerond.`);
        return;
      }
      throw new Error(mpEmptyScanReason({
        ...(result.meta || {}),
        admarkt_toegestaan: admarktAan,
        admarkt_ooit_aan: await admarktOoitAan(),
      }, platform));
    }
    // De verrijking hieronder haalt elke advertentiepagina op VANUIT dit tabblad,
    // en dat tabblad staat op www.marktplaats.nl. Voor een advertentie waarvan de
    // link op een ander domein staat (admarkt.marktplaats.nl) is dat een
    // cross-origin verzoek: die wordt geweigerd en levert stilzwijgend niets op.
    // Bij een Admarkt-scan zou daardoor ELKE advertentie zonder prijs en zonder
    // omschrijving binnenkomen — een import die er compleet uitziet maar leeg is.
    // Dat is erger dan een eerlijke melding, dus we controleren het vooraf.
    const tabOrigin = platform === "marktplaats"
      ? "https://www.marktplaats.nl" : "https://www.2dehands.be";
    const teVerrijken = result.items.filter(it => {
      if (!it.platform_listing_url) return false;
      try { return new URL(it.platform_listing_url).origin === tabOrigin; }
      catch (_) { return false; }
    });
    const buitenBereik = result.items.length - teVerrijken.length;
    if (buitenBereik) {
      console.warn(`[Omnivaleur] ${buitenBereik}/${result.items.length} listings sit on `
        + `another domain than ${tabOrigin} — cannot fetch their details from here.`);
      result.meta = { ...(result.meta || {}), enrichment_skipped: buitenBereik };
    }

    await reportProgress(serverUrl, job.id, {
      stage: "enriching",
      message: `Found ${result.items.length} listings — fetching full details…`,
      current: 0, total: teVerrijken.length,
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
    const total = teVerrijken.length;
    let enriched = 0;
    const startedAt = Date.now();
    // HARDE TIJDGRENS OP HET VERRIJKEN.
    //
    // Hier stond niets, en dat was de laatste val voor een grote winkel. Elke
    // advertentie kost een eigen aanvraag; gemeten bij Egbert Brouwer
    // (26-08-2026): 95 advertenties duurden "meerdere minuten", dus ~2-3
    // seconden per stuk. Bij zijn ~1000 persoonlijke advertenties is dat een
    // half uur tot een uur onafgebroken doorwerken in een achtergrondtabblad.
    // Wat er dan misging is erger dan traag: brak er onderweg iets af (Chrome
    // die de service worker opruimt, een hangende aanvraag, de gebruiker die
    // het tabblad sluit), dan werd er NIETS teruggestuurd en was al het werk
    // weg — "na 95 items krijg ik weer een timeout", en daarna begon alles
    // opnieuw bij nul.
    //
    // Nu kappen we op tijd af en sturen we op wat er wél klaar is. De rest
    // houdt gewoon zijn titel/prijs/foto uit het overzicht en wordt bij een
    // volgende scan alsnog verrijkt. Onvolledig binnen is oneindig veel beter
    // dan compleet kwijt.
    const VERRIJK_BUDGET_MS = 4 * 60 * 1000;
    let afgekaptOpTijd = 0;
    try {
      for (let i = 0; i < teVerrijken.length; i++) {
        if (Date.now() - startedAt > VERRIJK_BUDGET_MS) {
          afgekaptOpTijd = teVerrijken.length - i;
          console.warn(`[Omnivaleur] verrijken afgekapt op tijd: ${enriched} gedaan, `
            + `${afgekaptOpTijd} blijven staan voor een volgende scan.`);
          break;
        }
        const it = teVerrijken[i];
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
                return { description: description.trim().slice(0, 20000), photo_urls: [...new Set(photos)] };
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
        // Voortgang melden is versiering, geen werk. Toch stond deze aanroep
        // KAAL in de lus: één mislukte melding — een hik op de server, een 500
        // — vloog naar de vangst hieronder en gooide de verrijking van ALLE
        // resterende advertenties weg. De scan meldde zich daarna gewoon als
        // geslaagd. Bij een verkoper met 1.245 advertenties kwamen zo de laatste
        // 304 binnen met één foto en zonder tekst, zonder dat iemand iets zag.
        //
        // En niet meer bij elke advertentie: dat waren 1.245 schrijfacties naar
        // de server voor een voortgangsbalk. Elke tiende is genoeg, en dat is
        // meteen tien keer minder kans dat het misgaat.
        if (i % 10 === 0 || i === teVerrijken.length - 1) {
          const perItem = ((Date.now() - startedAt) / 1000) / (i + 1);
          try {
            await reportProgress(serverUrl, job.id, {
              stage: "enriching",
              message: `Fetching details ${i + 1}/${total}…`,
              current: i + 1, total,
              eta_seconds: Math.max(0, Math.round(perItem * (total - i - 1))),
            });
          } catch (e3) {
            console.warn("[Omnivaleur] voortgang niet gemeld (gaat gewoon door):", e3);
          }
        }
        await sleep(150); // gentle, and keeps the worker warm
      }
    } catch (e) {
      // Komt er hier tóch iets doorheen, leg dan vast hoe ver we kwamen. Anders
      // ziet een halve oogst er precies zo uit als een hele.
      console.warn(`[Omnivaleur] ${platform} enrichment aborted at ${enriched}/${total}:`, e);
      result.meta = { ...(result.meta || {}), enrichment_aborted_at: enriched,
                      enrichment_error: String(e && e.message || e).slice(0, 200) };
    }
    // Op tijd afgekapt is geen fout, maar het scherm hoort het wel te weten:
    // "compleet" mag dit niet heten zolang er nog advertenties op hun tekst en
    // prijs wachten.
    if (afgekaptOpTijd) {
      result.meta = {
        ...(result.meta || {}),
        complete: false,
        enrichment_remaining: afgekaptOpTijd,
        truncated_reason: `${enriched} van ${total} advertenties verrijkt binnen de tijd; `
          + `${afgekaptOpTijd} volgen bij een volgende scan`,
      };
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
    sluitWerkTabblad(tabId, 2500);
  }
}

// Closing a job tab means that job's meta is dead. Without this, jobtab_ keys
// pile up forever — and because Chrome reuses tab ids after a restart, a brand
// new tab could inherit a stale entry and complete the wrong job.
//
// Sluit de gebruiker (of Chrome) dat tabblad terwijl de opdracht nog loopt, dan
// meldde niemand dat af: de opdracht bleef server-side "claimed" staan, en omdat
// er bewust maar één opdracht tegelijk draait lag ALLES stil tot de server hem na
// vijf minuten opruimde. Vandaar dat het dashboard "publishing…" bleef tonen en
// opnieuw crosslisten niets deed. Nu melden we het sluiten meteen, zodat de
// wachtrij binnen seconden weer loopt en de gebruiker ziet wat er gebeurde.
chrome.tabs.onRemoved.addListener((tabId) => {
  const key = `jobtab_${tabId}`;
  chrome.storage.local.get(key, (s) => {
    const meta = s[key];
    chrome.storage.local.remove(key);
    clearJobWatchdog(tabId);
    // awaitingManualFinish = al als fout gemeld en bewust opengelaten voor een
    // handmatige afronding; die opdracht nog eens afmelden heeft geen zin.
    if (!meta || !meta.jobId || meta.awaitingManualFinish) return;
    console.warn(`[Omnivaleur] Tab ${tabId} closed while job ${meta.jobId} (${meta.platform}) was running — checking the platform before reporting.`);
    // Sloot het tabblad omdat Vinted na het plaatsen doornavigeerde? Kijk dan
    // eerst of de advertentie er gewoon staat, vóór we een fout melden.
    (async () => {
      if (meta.platform === "vinted" && (meta.action || "create") === "create") {
        const gevonden = await bgVindVintedAdvertentie(meta.payload || meta).catch(() => null);
        if (gevonden) {
          console.log(`[Omnivaleur] Tabblad weg, maar de advertentie staat op Vinted (${gevonden.id}) — als geplaatst afgemeld.`);
          await finaliseJob(meta.serverUrl, meta.jobId, "complete", {
            platform_listing_id: gevonden.id, platform_listing_url: gevonden.url,
          }).catch(() => {});
          return;
        }
      }
      await meldTabblad(meta);
    })();
  });
});

function meldTabblad(meta) {
    return finaliseJob(meta.serverUrl, meta.jobId, "error", {
      error: `The tab this ${meta.platform} job was working in was closed before it finished. `
        + `Nothing was published (or it wasn't confirmed) — check the platform, then publish again, `
        + `or click the platform icon in the dashboard to mark it as listed.`,
    }).catch(() => {});
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
  // OP DE INLOGPAGINA BELAND IN PLAATS VAN OP HET FORMULIER.
  //
  // Dan is er niets meer te wachten: ons invulscript luistert alleen op
  // /plaats/*, dus daar meldt zich nooit iemand en loopt de bewaker drie
  // minuten leeg. Dat is precies wat Egbert Brouwer 305 keer overkwam. Zeg het
  // meteen, mét het adres waar het tabblad werkelijk terechtkwam, in plaats van
  // stilte en daarna een gok.
  if (!meta.scriptSeen && MP_LOGINPAGINA.test(changeInfo.url)
      && (meta.platform === "marktplaats" || meta.platform === "2dehands")) {
    const site = SITE_NAAM[meta.platform] || meta.platform;
    clearJobWatchdog(tabId);
    await chrome.storage.local.remove(key);
    const melding =
      `The ${site} listing form never opened: that tab was sent straight to the ${site} login `
      + `page, so nothing was filled in and nothing was published. Sign in to ${site} in this `
      + `browser and publish again. [tabblad kwam uit op ${String(changeInfo.url).split("?")[0]}]`;
    await stopPlatformWachtrij(meta.serverUrl, meta.platform, melding).catch(() => {});
    await reportError(meta.jobId, meta.serverUrl, melding).catch(() => {});
    sluitWerkTabblad(tabId);
    return;
  }

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
  //
  // Die strenge eis geldt alleen zolang de extensie zélf nog bezig is. Zodra een
  // job aan de gebruiker is teruggegeven (awaitingManualFinish), vult niemand
  // meer automatisch iets in, en dan is er geen draft-url meer die per ongeluk
  // kan matchen. Vinted landt na een handmatige "Upload" lang niet altijd op de
  // slug-url — vaak op een kale /items/{id} — en dan bleef de advertentie in het
  // dashboard staan als mislukt terwijl hij gewoon online stond. Daarom in die
  // situatie ook de kale vorm accepteren, maar nooit /items/new of .../edit.
  // NA EEN HANDMATIGE UPLOAD LANDT VINTED OP DE KAST, NIET OP DE ADVERTENTIE
  // (31-08-2026, waargenomen: https://www.vinted.com/member/35817973).
  //
  // Alle patronen hieronder zoeken een advertentie-id in het adres. Dat adres
  // krijgt de verkoper na een handmatige "Upload" helemaal niet te zien: hij
  // wordt naar zijn eigen kastpagina gestuurd. Er viel dus niets te matchen, en
  // de advertentie bleef in het dashboard staan als niet-geplaatst terwijl hij
  // gewoon online stond.
  //
  // Op die kastpagina weten we het antwoord wél: de garderobe zelf. Die zoeker
  // koppelt alleen bij PRECIES één kandidaat (zie bgVindVintedAdvertentie), dus
  // bij twijfel gebeurt er niets — een verkeerde koppeling zou later de
  // verkeerde advertentie weghalen.
  if (meta.platform === "vinted" && meta.awaitingManualFinish
      && /\/member\/\d+/.test(url)) {
    const zelfGedaan = await bgVindVintedAdvertentie(meta.payload || meta).catch(() => null);
    if (!zelfGedaan) return;   // niets gevonden: laat de opdracht met rust
    console.log(`[Omnivaleur] Handmatig geplaatst op Vinted (${zelfGedaan.id}) — alsnog als geplaatst afgemeld.`);
    clearJobWatchdog(tabId);
    chrome.storage.local.remove([key, `job_${meta.platform}`]);
    await finaliseJob(meta.serverUrl, meta.jobId, "complete", {
      platform_listing_id: zelfGedaan.id, platform_listing_url: zelfGedaan.url,
    });
    return;
  }

  let m;
  if (meta.platform === "vinted") {
    m = url.match(/\/items\/(\d+)-[a-z0-9]/i);
    if (!m && (meta.awaitingManualFinish || meta.submitClicked)) {
      m = url.match(/\/items\/(\d+)(?:[/?#]|$)/);
      if (m && /\/items\/\d+\/(edit|new)\b/i.test(url)) m = null;
    }
  } else {
    m = url.match(/\/seller\/view\/(m\d+)/) ||
         url.match(/\/v\/[^/]+\/(m\d+)/) ||
         url.match(/[?&](m\d{6,})/) ||
         url.match(/(m\d{8,})/);
  }
  if (!m) return;

  const listingId = m[1];

  // Alleen afmelden als deze advertentie aantoonbaar van deze verkoper is.
  // Zie de toelichting bij bgVintedEigenAdvertentie: zonder dit werd een
  // willekeurige advertentie waar de verkoper op klikte afgemeld als de zijne.
  if (meta.platform === "vinted") {
    const vanHem = await bgVintedEigenAdvertentie(new URL(url).origin, listingId, meta.payload || meta);
    if (vanHem === false) {
      console.log(`[Omnivaleur] /items/${listingId} staat niet in de kast van deze verkoper — niet afgemeld.`);
      return;
    }
  }

  console.log(`[Omnivaleur] Auto-detected listing after publish: ${listingId} (${meta.platform})`);

  // Clear stored job
  clearJobWatchdog(tabId);
  chrome.storage.local.remove([key, `job_${meta.platform}`]);

  // Zelfde reden als in getDeleteUrl: /v/listing/{id} is een dode link. Liever
  // de echte pagina waar we na het plaatsen op staan; kunnen we die niet lezen,
  // dan de verkoperspagina, want die werkt altijd.
  const gelandeUrl = /\/v\//.test(url) ? url.split("?")[0] : null;
  const listingUrl = meta.platform === "marktplaats"
    ? (gelandeUrl || `https://www.marktplaats.nl/seller/view/${listingId}`)
    : meta.platform === "2dehands"
    ? (gelandeUrl || `https://www.2dehands.be/seller/view/${listingId}`)
    : meta.platform === "vinted"
    ? `${new URL(url).origin}/items/${listingId}`
    : null;

  // Critical path: this is the ONLY completion signal for a create job, and a
  // create is not retry-safe server-side — a lost completion gets surfaced to
  // the user as a possible duplicate. Retry hard, and queue if still unsent.
  await finaliseJob(meta.serverUrl, meta.jobId, "complete", {
    platform_listing_id: listingId, platform_listing_url: listingUrl,
  });

  sluitWerkTabblad(tabId, 2000);
});

// ── Autonomous sold detection + cross-platform delist ─────────────────────
// Every poll cycle also checks for sold items and triggers auto-delist.
chrome.alarms.create("sold-check", { periodInMinutes: 10 });
// En meteen op de juiste stand zetten als Calm mode aan staat.
calmAlarmBijwerken();
chrome.runtime.onStartup.addListener(() => { calmAlarmBijwerken(); });
chrome.runtime.onInstalled.addListener(() => { calmAlarmBijwerken(); });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "sold-check") {
    // Niet vlak na het opstarten (dan doet de wekker start-sold het) en niet
    // tijdens het werken van de verkoper — zie magStilScannenNu.
    teVroegNaStart(3).then((vroeg) => (vroeg ? false : magStilScannenNu()))
      .then((mag) => { if (mag) { checkSoldListings(); checkVintedOrders(); } });
  }
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


// Alarms only fire after their first period, so kick a sold-check once on
// startup too (delayed a little so auth/session is ready).
function kickSoldCheck() { /* zie START_WEKKERS: gebeurt via de wekker start-sold */ }
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
      const resp = await fetch(`${serverUrl}/api/listings/?platform=${platform}`, { headers: authHeaders }).catch(() => null);
      if (!resp?.ok) {
        console.warn(`[Omnivaleur][sold] ${platform}: could not fetch active listings (HTTP ${resp?.status || "no response"}) — skipping`);
        continue;
      }
      const allListings = await resp.json();
      // Ook 'hidden' en 'relisting': ook zo'n advertentie kan gewoon verkocht
      // zijn, en die verkoop werd tot nu toe nooit opgemerkt.
      const active = allListings.filter(l =>
        l.platform === platform && ["active", "hidden", "relisting"].includes(l.status));
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
      // Titels van verkochte advertenties, genormaliseerd voor een 1-op-1
      // vergelijking (voor advertenties zonder opgeslagen nummer). Komt een titel
      // twee keer voor, dan is hij als sleutel onbruikbaar — dan liever niets
      // boeken dan het verkeerde item verkocht melden.
      const normTitle = s => (s || "")
        .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/^\s*\([^)]{1,24}\)\s*/, "")
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
      const soldTitleCount = new Map();
      for (const a of soldAds) {
        const t = normTitle(a.title);
        if (t) soldTitleCount.set(t, (soldTitleCount.get(t) || 0) + 1);
      }
      const soldTitles = soldAds.map(a => (a.title || "").toLowerCase().trim()).filter(Boolean);
      console.log(`[Omnivaleur][sold] ${platform}: ${ads.length} ad cards scraped, ${soldAds.length} carry a sold/reserved label`);

      // ADVERTENTIES DIE HELEMAAL NIET IN HET OVERZICHT STAAN.
      //
      // Bij een zakelijk account staan de advertenties niet op de gewone "Mijn
      // advertenties"-pagina. Gemeten bij een verkoper met 1.221 advertenties:
      // geen enkele stond in dat overzicht, dus werd er ook nooit een verkoop
      // opgemerkt en bleef het item op alle andere kanalen gewoon te koop staan.
      //
      // Voor die advertenties kijken we op hun eigen pagina. Alleen een expliciet
      // "verkocht" of "gereserveerd" telt; enkel verdwenen zijn telt niet, want
      // dat betekent op Marktplaats ook "verlopen" en dan zou een nog levend item
      // overal worden weggehaald.
      const gezien = new Set(ads.map(a => a.id).filter(Boolean));
      // HARDE VOORWAARDE. Leverde het overzicht geen enkele advertentie op, dan
      // weten we niet of er advertenties ontbreken of dat de pagina niet geladen
      // is (uitgelogd, opmaak gewijzigd, trage verbinding). Dan lijkt ALLES
      // verdwenen en zouden we de verkoper honderden verkoopvragen sturen.
      // Absentie zegt alleen iets als we echt gekeken hebben.
      if (!ads.length) {
        console.warn(`[Omnivaleur][sold] ${platform}: het overzicht gaf 0 advertenties — deze ronde wordt niets als verdwenen geteld.`);
      } else {
        const gemist = withId.filter(l => !gezien.has(l.platform_listing_id));
        const staat = await verdenkingen();
        // Advertenties die we WEL terugzagen: elke verdenking daarop vervalt.
        for (const l of withId) {
          if (gezien.has(l.platform_listing_id)) delete staat[`${platform}:${l.platform_listing_id}`];
        }
        if (gemist.length) {
          console.log(`[Omnivaleur][sold] ${platform}: ${gemist.length} advertentie(s) niet in het overzicht — eigen pagina nakijken`);
          // Niet het hele bestand per beurt: dat zijn duizenden aanvragen. Een
          // vaste hap per ronde houdt het rustig. Wél elke ronde een STUK
          // VERDEROP, anders werden bij een groot account eeuwig dezelfde
          // veertig nagekeken en kwam de rest nooit aan de beurt.
          const HAP = 40;
          const startSleutel = `mogelijk_verkocht_start_${platform}`;
          let start = 0;
          try { start = (await chrome.storage.local.get(startSleutel))?.[startSleutel] || 0; } catch (_) {}
          if (start >= gemist.length) start = 0;
          const beurt = gemist.slice(start, start + HAP);
          try { await chrome.storage.local.set({ [startSleutel]: start + beurt.length }); } catch (_) {}

          const teBevestigen = [];
          const tellers = { verkocht: 0, weg: 0, leeft: 0, onbekend: 0 };
          let nagekeken = 0;
          for (const l of beurt) {
            // Rustig aan: veertig aanvragen achter elkaar op volle snelheid is
            // precies waar Marktplaats met een 403 op reageert.
            if (nagekeken) await new Promise(r => setTimeout(r, 250));
            const sleutel = `${platform}:${l.platform_listing_id}`;
            const oordeel = await bekijkEigenPagina(platform, l.platform_listing_id);
            nagekeken++;
            tellers[oordeel] = (tellers[oordeel] || 0) + 1;
            const regel = { item_id: l.item_id, platform,
                            platform_listing_id: l.platform_listing_id,
                            title: l.title };
            if (oordeel === "verkocht") {
              // Bewijs op de pagina zelf. Geen tweede ronde nodig.
              delete staat[sleutel];
              teBevestigen.push({ ...regel, reden: "label" });
            } else if (oordeel === "weg") {
              const eerder = staat[sleutel];
              const nu = Date.now();
              if (eerder && nu - eerder.eerst >= VERDENKING_MIN_MINUTEN * 60000) {
                delete staat[sleutel];
                teBevestigen.push({ ...regel, reden: "weg" });
              } else if (!eerder) {
                staat[sleutel] = { eerst: nu, n: 1 };
              }
            } else {
              // "leeft" of "onbekend": niets bewezen, dus geen verdenking laten
              // staan die op een storing of op een nog levende advertentie berust.
              delete staat[sleutel];
            }
            // Vijf keer achter elkaar niets kunnen vaststellen betekent dat er
            // iets mis is met de sessie of de verbinding, niet dat er advertenties
            // verdwenen zijn. Dan deze ronde stoppen in plaats van doorbeuken.
            if (nagekeken >= 5 && tellers.onbekend === nagekeken) {
              console.warn(`[Omnivaleur][sold] ${platform}: eerste ${nagekeken} pagina's gaven geen uitsluitsel (uitgelogd of geblokkeerd) — ronde afgebroken.`);
              break;
            }
          }
          await verdenkingenOpslaan(staat);
          console.log(`[Omnivaleur][sold] ${platform}: ${beurt.length} eigen pagina(s) nagekeken vanaf ${start} →`, tellers);
          if (teBevestigen.length) {
            // Melden, niet afmelden. De verkoper bevestigt het zelf in het
            // dashboard; pas dan gaat het item van de andere kanalen af.
            console.log(`[Omnivaleur][sold] ${platform}: ${teBevestigen.length} advertentie(s) ter bevestiging doorgegeven`);
            await meldMogelijkeVerkopen(serverUrl, teBevestigen);
          }
        } else {
          await verdenkingenOpslaan(staat);
        }
      }

      if (!soldAds.length) continue;

      let triggered = 0;
      for (const listing of active) {
        // Match a sold ad either by exact platform id, or — for listings without
        // an id — by a resilient title match against a POSITIVELY sold ad. We
        // NEVER infer a sale from absence; only a positive sold label acts.
        let isSold = listing.platform_listing_id && soldIds.has(listing.platform_listing_id);
        // Zonder platform-id: eerst de SKU-prefix "(1337)" waarmee elke door deze
        // app geplaatste advertentie begint — exact en uniek. Pas daarna de
        // titelvergelijking, die op vertaalde of afgekapte titels kan missen.
        const listingSku = listing.sku
          || (/^\s*\(([^)]{1,24})\)/.exec(listing.title || "") || [])[1] || "";
        if (!isSold && !listing.platform_listing_id && listingSku) {
          const needle = `(${String(listingSku).trim().toLowerCase()})`;
          isSold = soldTitles.some(st => st.startsWith(needle));
          if (isSold) console.log(`[Omnivaleur][sold] ${platform}: matched sold ad by SKU ${listingSku} for "${listing.title}" (no platform id)`);
        }
        if (!isSold && !listing.platform_listing_id && listing.title) {
          // 1-op-1 op de titel, en alleen als die titel bij precies één verkochte
          // advertentie hoort. (Vroeger: eerste 20 tekens met "bevat" — dat kon
          // het verkeerde item als verkocht boeken.)
          const key = normTitle(listing.title);
          isSold = !!key && soldTitleCount.get(key) === 1;
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
// Staat DEZE advertentie als verkocht of gereserveerd op haar eigen pagina?
//
// Voor verkopers van wie de advertenties niet in het gewone overzicht staan —
// zakelijke accounts. Alleen de pagina ophalen, geen tabblad en geen klikken.
//
// BEWUST GEEN AUTOMATISCHE AFMELDING OP DEZE UITKOMST.
// Een verkeerde "verkocht" haalt het item van alle andere kanalen af, en dat is
// onherstelbaar werk voor de verkoper. De opmaak van een verkochte advertentie
// op deze pagina is niet nagekeken: zonder ingelogde zakelijke sessie geeft hij
// 401, dus er is geen enkel echt voorbeeld om tegen te toetsen. Tot dat er is
// wordt de uitkomst alleen gemeld, zodat de verkoper het zelf bevestigt.
// Raden op een pagina die je nooit gezien hebt is precies hoe je iemands
// voorraad sloopt.
async function meldMogelijkeVerkopen(serverUrl, regels) {
  try {
    const headers = await getAuthHeaders();
    if (!headers.Authorization) return;
    await fetch(`${serverUrl}/api/listings/possibly-sold`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ listings: regels }),
    });
  } catch (e) {
    console.warn("[Omnivaleur][sold] mogelijke verkopen niet doorgegeven:", e);
  }
}

// Wat zegt de advertentie zelf? Vier uitkomsten, bewust uit elkaar gehouden —
// ze leiden tot heel verschillende conclusies:
//
//   "verkocht"  De pagina draagt zelf het label verkocht/gereserveerd. Het
//               sterkste bewijs dat er is; hier hoeft niets bevestigd te worden
//               met een tweede ronde.
//   "weg"       De advertentie bestaat niet meer (404, of doorgestuurd naar iets
//               anders dan deze advertentie). Dat kan verkocht zijn, maar op
//               Marktplaats óók gewoon verlopen — dus nooit alleen hierop
//               afgaan.
//   "leeft"     Staat er nog gewoon. Elke verdenking vervalt.
//   "onbekend"  401/403 (zakelijk account zonder sessie), serverfout, of geen
//               verbinding. Niets bewezen, dus niets doen — en vooral geen
//               verdenking laten staan die op een storing berust.
const NIET_MEER_BESCHIKBAAR = /(deze\s+)?advertentie\s+(is\s+)?(niet\s+meer\s+beschikbaar|niet\s+gevonden|verwijderd|bestaat niet)|pagina niet gevonden|no longer available|not found/;

async function bekijkEigenPagina(platform, advertentieId) {
  if (!advertentieId) return "onbekend";
  const basis = platform === "marktplaats" ? "https://www.marktplaats.nl" : "https://www.2dehands.be";
  const url = `${basis}/seller/view/${advertentieId}`;
  try {
    const r = await fetch(url, { credentials: "include", redirect: "follow" });
    if (r.status === 404 || r.status === 410) return "weg";
    if (!r.ok) return "onbekend";                  // 401/403/5xx: niets bewezen
    // Doorgestuurd naar iets anders dan deze advertentie (meestal de homepage of
    // een zoekpagina) betekent bij Marktplaats: deze advertentie bestaat niet meer.
    if (r.redirected && !String(r.url || "").includes(String(advertentieId))) return "weg";
    const html = (await r.text()).toLowerCase();
    // Het label eerst: dat is bewijs, de rest is gevolgtrekking.
    if (/(^|[^a-z])(verkocht|gereserveerd)([^a-z]|$)/.test(html)
        && !/verkochte\s+artikelen|verkocht\?|meld het/.test(html)) return "verkocht";
    if (NIET_MEER_BESCHIKBAAR.test(html)) return "weg";
    // Een echte advertentiepagina noemt het advertentienummer. Staat dat er niet
    // in, dan kijken we niet naar deze advertentie en concluderen we niets.
    return html.includes(String(advertentieId).toLowerCase()) ? "leeft" : "onbekend";
  } catch (e) {
    return "onbekend";                             // niets bewezen is geen verkoop
  }
}

// ── Verdenkingen die twee rondes moeten standhouden ────────────────────────
// "Weg" is het zwakke signaal: een hik in het ophalen, een uitgelogde sessie of
// een trage pagina mag nooit tot een verkoopvraag leiden. Daarom telt een
// advertentie pas als "mogelijk verkocht" wanneer hij in TWEE aparte rondes,
// minstens een half uur uit elkaar, verdwenen was. Ziet een ronde hem weer
// staan, dan vervalt de telling meteen.
const VERDENKING_SLEUTEL = "mogelijk_verkocht_verdenkingen";
const VERDENKING_MIN_MINUTEN = 30;
const VERDENKING_VERVALT_DAGEN = 14;

async function verdenkingen() {
  try {
    const o = await chrome.storage.local.get(VERDENKING_SLEUTEL);
    return o?.[VERDENKING_SLEUTEL] && typeof o[VERDENKING_SLEUTEL] === "object" ? o[VERDENKING_SLEUTEL] : {};
  } catch (_) { return {}; }
}

async function verdenkingenOpslaan(staat) {
  const grens = Date.now() - VERDENKING_VERVALT_DAGEN * 86400000;
  for (const [k, v] of Object.entries(staat)) {
    if (!v || !v.eerst || v.eerst < grens) delete staat[k];
  }
  try { await chrome.storage.local.set({ [VERDENKING_SLEUTEL]: staat }); } catch (_) {}
}

function scrapeMarktplaatsAds(url, platform) {
  return new Promise((resolve) => {
    stilTabblad(url, (tab) => {
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
          sluitWerkTabblad(tabId);
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
        sluitWerkTabblad(tabId);
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
    stilTabblad(url, (tab) => {
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

              // De datum die Vinted bij de bestelling toont. ZONDER deze datum
              // krijgt elke bestelling die wij voor het eerst zien de klok van
              // dit moment — en dan landt na een stille periode de omzet van
              // weken op één dag (gemeten 30-08-2026: twaalf verkopen binnen
              // twaalf seconden). Meerdere kandidaten, van hard naar zacht: het
              // datetime-attribuut is machineleesbaar, een title-attribuut komt
              // daarna, dan de tekst van een datumveld. De server neemt de eerste
              // die hij met zekerheid kan lezen en gokt nooit.
              const datumKandidaten = (row) => {
                const uit = [];
                row.querySelectorAll('time[datetime]').forEach(t => uit.push(t.getAttribute('datetime')));
                row.querySelectorAll('time, [datetime], [title], [data-testid*="date" i], [class*="date" i], [class*="time" i]').forEach(el => {
                  const attr = el.getAttribute('datetime') || el.getAttribute('title');
                  if (attr) uit.push(attr);
                  const txt = (el.innerText || "").replace(/\s+/g, " ").trim();
                  if (txt && txt.length <= 40) uit.push(txt);
                });
                return [...new Set(uit.filter(Boolean))].slice(0, 8);
              };

              const rows = {};
              anchors.forEach(el => {
                const row = el.closest('div, li, article') || el;
                const text = (row.innerText || el.innerText || "").replace(/\s+/g, " ").trim();
                if (!text) return;
                const skuM = text.match(/\((\d{3,6})\)/);
                // Zonder "(1234)" in de tekst was deze rij tot nu toe waardeloos:
                // verkopers die geen nummer in hun titel zetten hadden hier dus
                // nooit iets aan. Nu gaat de hele rijtekst mee en zoekt de server
                // er de bijbehorende titel bij (alleen als die uniek is).
                const priceM = text.match(/€\s?(\d+(?:[.,]\d{2})?)/);
                const cancelled = /cancel|refund|geannuleerd|terugbetaal|retour/i.test(text);
                const sold = !cancelled;
                const key = skuM ? `sku:${skuM[1]}` : `txt:${text.slice(0, 160)}`;
                const entry = {
                  sku: skuM ? skuM[1] : null,
                  text: text.slice(0, 300),
                  price: priceM ? priceM[1] : null,
                  date: datumKandidaten(row),
                  sold,
                };
                const prev = rows[key];
                // Keep the sold entry (with price) over a cancelled one for the same row.
                if (!prev || (sold && !prev.sold)) {
                  rows[key] = entry;
                } else if (sold && prev.sold) {
                  if (!prev.price && priceM) prev.price = priceM[1];
                  if (!prev.date?.length && entry.date.length) prev.date = entry.date;
                }
              });
              return { orders: Object.values(rows), selectorHits, rowCandidates: anchors.size };
            },
          }, (results) => {
            sluitWerkTabblad(tabId);
            const out = results?.[0]?.result || { orders: [], selectorHits: {}, rowCandidates: 0 };
            const orders = out.orders || [];
            console.log(`[Omnivaleur][sold] Vinted: selector hits`, out.selectorHits, `→ ${out.rowCandidates} candidate row(s), ${orders.length} order row(s) (${orders.filter(o => o.sku).length} with a (SKU), sold: ${orders.filter(o => o.sold).length}, met datum: ${orders.filter(o => o.date?.length).length})`);
            if (orders.length && !orders.some(o => o.date?.length)) {
              console.warn("[Omnivaleur][sold] Vinted: GEEN datumveld gevonden op de bestellingenpagina. Nieuwe verkopen krijgen dan de datum van vandaag; de opmaak van de pagina is waarschijnlijk gewijzigd.");
            }
            resolve(orders);
          });
        }, 2500);
      };

      chrome.tabs.onUpdated.addListener(onUpdated);
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(onUpdated);
        sluitWerkTabblad(tabId);
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
const NOTIF_SCAN_MINUTES = 10;

// Where to open the messages/bids view per platform, and the deep link we hand
// the dashboard so the user can jump straight there. (Vinted's inbox lives at
// /inbox — /member/messages 404s.)
const NOTIF_SOURCES = {
  marktplaats: "https://www.marktplaats.nl/messages",
  "2dehands": "https://www.2dehands.be/messages",
};

chrome.alarms.create("notif-scan", { periodInMinutes: NOTIF_SCAN_MINUTES });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "notif-scan") {
    teVroegNaStart(5).then((vroeg) => vroeg ? false : magStilScannenNu())
      .then((mag) => { if (mag) scanNotifications(); });
  }
});



async function scanNotifications() {
  const serverUrl = await getServerUrl();
  const headers = await getAuthHeaders();
  if (!headers.Authorization) return; // not logged into the extension yet

  const melden = async (platform, counts, deepLink) => {
    if (!counts) return; // niet ingelogd / niet gelezen — vorige stand laten staan
    await fetch(`${serverUrl}/api/notifications/report`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        platform,
        messages: counts.messages,
        offers: counts.offers,
        deep_link: deepLink,
      }),
    }).catch((e) => console.error(`[Omnivaleur] notif report failed (${platform}):`, e));
  };

  // Vinted heeft er geen tabblad voor nodig: de inbox is een gewone JSON-oproep
  // met dezelfde inlog als de browser. Dat scheelt niet alleen een tabblad elk
  // kwartier — het lost ook een echte fout op. De scan opende altijd vinted.nl,
  // terwijl een Belgische verkoper op vinted.be zit. Daar was hij niet ingelogd,
  // dus kwam er nooit een getal binnen en bleef "Berichten" leeg terwijl er wél
  // berichten stonden.
  try {
    const v = await bgVintedInbox();
    if (v) await melden("vinted", v.counts, `${v.origin}/inbox`);
  } catch (e) {
    console.error("[Omnivaleur] notif-scan error (vinted):", e);
  }

  for (const [platform, url] of Object.entries(NOTIF_SOURCES)) {
    try {
      const counts = await scrapeNotificationCounts(url, platform);
      await melden(platform, counts, url);
      await meldVerkochtUitBerichten(serverUrl, headers, platform, counts?.sold);
    } catch (e) {
      console.error(`[Omnivaleur] notif-scan error (${platform}):`, e);
    }
  }
}

// De verkocht-badges uit de berichtenlijst doorgeven. Dit is de enige plek waar
// Marktplaats een handmatige verkoop wél hardop zegt: op de advertentie zelf
// komt nooit een label te staan, want die haal je gewoon weg.
//
// Alleen doorgeven, niet beslissen. De server kijkt of het artikel nog ergens te
// koop staat en boekt alleen dan — een gesprek van maanden geleden houdt zijn
// badge voor eeuwig, dus zonder die controle zou elke ronde dezelfde oude
// verkopen opnieuw melden.
async function meldVerkochtUitBerichten(serverUrl, headers, platform, sold) {
  if (!Array.isArray(sold) || !sold.length) return;
  console.log(`[Omnivaleur][sold] ${platform}: ${sold.length} gesprek(ken) met een verkocht-badge`, sold.map(s => s.sku));
  const r = await fetch(`${serverUrl}/api/listings/sold-from-messages`, {
    method: "POST",
    headers,
    body: JSON.stringify({ platform, sold }),
  }).catch((e) => { console.error("[Omnivaleur][sold] sold-from-messages POST failed:", e); return null; });
  if (r?.ok) {
    const uit = await r.json().catch(() => ({}));
    console.log(`[Omnivaleur][sold] ${platform}: ${uit.booked ?? 0} verkoop/verkopen geboekt, ${uit.skipped ?? 0} overgeslagen`);
  }
}

// Leest de Vinted-inbox rechtstreeks, op het domein waar deze verkoper echt is
// ingelogd. Geeft null als we nergens een geldige sessie vinden — dan blijft de
// vorige stand staan in plaats van dat er een nul wordt gemeld.
async function bgVintedInbox() {
  for (const origin of VINTED_ORIGINS) {
    try {
      const me = await fetch(`${origin}/api/v2/users/current`, {
        headers: { Accept: "application/json" }, credentials: "include",
      });
      if (!me.ok) continue;
      const r = await fetch(`${origin}/api/v2/inbox?page=1&per_page=50`, {
        headers: { Accept: "application/json" }, credentials: "include",
      });
      if (!r.ok) continue;
      const j = await r.json();
      const convos = Array.isArray(j.conversations) ? j.conversations : [];
      const ongelezen = convos.filter((c) => c && c.unread);
      return {
        origin,
        counts: { messages: ongelezen.length, offers: ongelezen.filter(vintedLijktBod).length },
      };
    } catch (_) { /* volgend domein proberen */ }
  }
  return null;
}

// Wat telt als een bod op Vinted.
//
// Dit stond eerder op /would you (sell|take)|sell (it|this)|prijsvoorstel|€\s?\d/ —
// en dat laatste stuk sloeg aan op ELK bedrag. De omschrijving van een gesprek
// op Vinted is de titel plus de prijs van het artikel, dus vrijwel elk ongelezen
// gesprek werd als bod geteld. Zelfde soort fout als "aangeboden" op
// Marktplaats: verzonnen getallen maken alle andere cijfers verdacht. Alleen
// nog echte bod-bewoordingen. Liever een bod missen dan er een verzinnen — het
// aantal berichten klopt hoe dan ook, en daar klikt hij toch op door.
const VINTED_BOD_RE = /\bbod\b|\bbieding\b|prijsvoorstel|\bofferte\b|\boffer\b|would you (sell|take)|make an offer|\bproposition\b/i;
function vintedLijktBod(c) {
  return VINTED_BOD_RE.test(String((c && c.description) || ""));
}

// Opens the messages page in a background tab and reads counts from the DOM.
// Returns {messages, offers} or null if we couldn't read a logged-in page.
// NOTE: the selectors below are best-effort against the platforms' current
// markup and MUST be re-verified against a live logged-in session when a
// platform changes its layout — a miss degrades to null (no update), never a
// wrong number.
function scrapeNotificationCounts(url, platform) {
  return new Promise((resolve) => {
    stilTabblad(url, (tab) => {
      if (!tab) { resolve(null); return; }
      const tabId = tab.id;
      let settled = false;
      const finish = (val) => {
        if (settled) return;
        settled = true;
        chrome.tabs.onUpdated.removeListener(onUpdated);
        sluitWerkTabblad(tabId);
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
  // Woordgrenzen aan BEIDE kanten. Zonder de grens ervoor matchte "geboden"
  // binnen "aangeboden" en "bieding" binnen "aanbieding" — twee woorden die in
  // vrijwel elke advertentietekst staan. Gemeten geval 18-08-2026: een verkoper
  // met bieden UIT zag vijf biedingen op zijn dashboard staan die niet bestonden.
  // Verzonnen getallen zijn erger dan geen getallen: ze maken alle andere
  // cijfers verdacht.
  const MP_OFFER_RE = /\bbod\b|\bgeboden\b|\bbieding\b|\bbiedingen\b/i;
  let messages = 0;
  let offers = 0;
  // DE VERKOCHT-BADGE IN DE BERICHTENLIJST.
  //
  // Waarom dit hier staat (01-09-2026, Daniel): "de enige manier dat ik zelf kan
  // controleren of iets op Marktplaats echt verkocht is, is via de verkocht
  // badge". Die badge staat op het gesprek, niet op de advertentie — dat is
  // precies waarom wij hem nooit zagen. Wij keken naar het advertentie-overzicht,
  // en daar verdwijnt een handmatig verkocht artikel gewoon zonder label.
  //
  // Even streng als bij het verwijderen: alleen een LOS labeltje dat exact
  // "verkocht" is telt. Het woord in een berichtvoorbeeld ("Is deze nog te koop?
  // Verkocht?") mag nooit een verkoop boeken. En de sleutel is het nummer
  // waarmee elke door deze app geplaatste titel begint — "(1308)" — want de
  // titel zelf staat afgekapt in de lijst.
  const sold = [];
  const gezien = new Set();
  // Een bod telt alleen mee als het gesprek ONGELEZEN is. Eerder werd elke rij
  // geteld, ook gesprekken van maanden geleden die allang afgehandeld waren.
  // Daardoor stonden er structureel meer "biedingen" dan "berichten" op het
  // dashboard — een getal waar niets meer achter zat om te doen.
  rows.forEach((r) => {
    // Verkocht-badge: los labeltje, exacte tekst, geen kindelementen.
    const verkocht = [...r.querySelectorAll("span, div, p, strong, b, em")]
      .filter((el) => el.children.length === 0)
      .some((el) => /^verkocht!?$/i.test((el.textContent || "").replace(/\s+/g, " ").trim()));
    if (verkocht) {
      // Het nummer waar de advertentietitel mee begint. Alleen aan het BEGIN van
      // een regel, zodat een nummer uit een berichttekst ("ik bied 1300") of een
      // jaartal er niet voor door kan gaan.
      const m = /(?:^|\n)\s*\((\d{1,6})\)\s*(.{0,80})/.exec(r.innerText || r.textContent || "");
      if (m && !gezien.has(m[1])) {
        gezien.add(m[1]);
        sold.push({ sku: m[1], title: `(${m[1]}) ${(m[2] || "").trim()}` });
      }
    }
    const ongelezen = !!r.querySelector('[class*="u-textStyleBodySmallStrong"]');
    if (!ongelezen) return;
    messages++;
    if (MP_OFFER_RE.test(r.textContent || "")) offers++;
  });
  return { messages, offers, sold };
}

// ---- Main-world helpers (injected via chrome.scripting, bypasses page CSP) ----

// Het formulier valideert NIET op de zichtbare editor maar op een verborgen
// veld (description_nl-BE / description_nl-NL). Live gemeten: de Lexical-editor
// vullen laat dat veld leeg achter, en dan blijft "Geen zoekertjestekst
// ingevuld" staan hoeveel tekst er ook zichtbaar is. Dit veld staat onder
// React-beheer, dus zetten via de eigen setter plus een input-gebeurtenis —
// precies zoals React zelf een toetsaanslag verwerkt.
// Er staat niet altijd één zo'n veld op het formulier: op 2dehands komen
// description_nl-BE en description_nl-NL naast elkaar voor, en welke van de twee
// de validatie leest verschilt per categorie. Alleen de eerste vullen liet de
// andere leeg — precies het willekeurige "geen zoekertjestekst ingevuld".
// Daarom vullen we ze allemaal.
//
// Let op: chrome.scripting.executeScript injecteert alléén de functie zelf —
// hulpfuncties uit dit bestand bestaan niet in de pagina. Alles staat daarom
// opzettelijk binnenin.
function _mwFillHiddenDescription(descText) {
  // Breed op naam zoeken. De oude, strakke lijst eiste letterlijk
  // "description_nl-…" of "description". Heette het veld op dit formulier iets
  // anders (description_fr-BE, listing.description, Description), dan vonden we
  // NIETS — en dan meldde de controle "prima, dit platform heeft dat veld niet"
  // terwijl er in werkelijkheid nooit iets was ingevuld. Precies zo kon 2dehands
  // blijven zeggen "Geen zoekertjestekst ingevuld".
  const SEL = 'input[name*="escription" i], textarea[name*="escription" i], '
            + 'input[id*="escription" i], textarea[id*="escription" i]';
  // Alleen echte tekstvelden. De brede naamzoektocht hierboven mag nooit een
  // keuzerondje, een aantal of een knop met de advertentietekst volschrijven.
  const _bruikbaar = (v) => {
    if (v.disabled || v.readOnly) return false;
    const t = (v.type || "text").toLowerCase();
    if (!(v instanceof HTMLTextAreaElement || t === "text" || t === "hidden")) return false;
    // "description" moet een heel woord zijn. Zo vangen we description_nl-BE,
    // description_fr-BE en listing.description, maar schrijven we nooit per
    // ongeluk in een veld als descriptionType of descriptionCount.
    return /(^|[^a-z])description([^a-z]|$)/i.test(v.name || v.id || "");
  };
  const velden = [...document.querySelectorAll(SEL)].filter(_bruikbaar);
  if (!velden.length) return false;
  const zet = (veld) => {
    const proto = veld instanceof HTMLTextAreaElement
      ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(veld, descText);
    veld.dispatchEvent(new Event("input", { bubbles: true }));
    veld.dispatchEvent(new Event("change", { bubbles: true }));
  };
  velden.forEach(zet);
  return velden.every((v) => (v.value || "").trim().length > 0);
}


// ── ECHT TYPEN, ALS LAATSTE REDMIDDEL ─────────────────────────────────────
//
// WAAROM DIT BESTAAT — live gemeten op het Marktplaats-plaatsformulier
// (21-08-2026, ingelogd account, categorie sieraden):
//   * de tekst staat zichtbaar in de editor en óók in Lexical's eigen
//     editorstaat, en tóch meldt het formulier "Geen advertentietekst
//     ingevuld";
//   * het verborgen veld description_nl-NL wordt door React bestuurd en heeft
//     geen onChange — wat wij erin zetten wordt bij de volgende hertekening
//     gewoon overschreven;
//   * execCommand, een nagemaakte beforeinput/input, een nagemaakt plakken en
//     blur() veranderen de staat van het formulier NIET;
//   * één echte toetsaanslag in het veld werkt wel, en neemt dan meteen alles
//     mee wat er al stond. Precies wat de verkoper doet als hij een spatie
//     typt en de melding ziet verdwijnen.
//
// Het verschil is `isTrusted`: alles wat een script zelf afvuurt draagt dat
// stempel niet, en Marktplaats kijkt ernaar. De énige manier om vanuit een
// extensie een echte toetsaanslag te maken is de debugger-API van Chrome.
// Daarom staat die permissie NIET standaard aan: hij wordt pas gevraagd als
// het formulier daadwerkelijk blijft klagen, en hij wordt meteen na gebruik
// weer losgelaten.
// Chrome staat "debugger" NIET toe als optionele permissie: chrome.permissions
// .request() doet er domweg niets mee en de schakelaar in het menu bleef dus
// dood. Hij staat daarom in de vaste permissies, en de schakelaar hieronder is
// een gewone voorkeur: staat hij uit, dan raken we de debugger niet aan.
async function heeftDebugger() {
  try {
    const s = await chrome.storage.sync.get("magTypen");
    return s.magTypen !== false;   // standaard aan: zonder dit plaatst Marktplaats niet
  } catch (_) {
    return true;
  }
}

async function typEchteToets(tabId, tekst) {
  if (!(await heeftDebugger())) return "geen-toestemming";
  const doel = { tabId };
  const stuur = (methode, params) => new Promise((res, rej) => {
    chrome.debugger.sendCommand(doel, methode, params, (r) => {
      chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res(r);
    });
  });
  // Waar koppelen we eigenlijk aan? Een verkeerd tabblad geeft een melding die
  // nergens op slaat ("Cannot access a chrome-extension:// URL of different
  // extension") en dan zoek je in de verkeerde hoek. Eerst kijken wat het ís.
  const tab = await chrome.tabs.get(tabId).catch(() => null);
  const adres = (tab && tab.url) || "";
  if (!/^https?:/i.test(adres)) {
    return `verkeerd tabblad (${adres ? adres.slice(0, 60) : "geen adres"})`;
  }
  const koppel = (waar) => new Promise((res, rej) => chrome.debugger.attach(waar, "1.3", () => {
    chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res();
  }));
  // Al gekoppeld bij het openen van het tabblad? Dan hoeft het niet nog eens —
  // en dat is precies de koppeling die wél lukt.
  const alGekoppeld = _vroegGekoppeld.has(tabId);
  try {
    if (!alGekoppeld) await koppel(doel);
  } catch (eerste) {
    // Tweede weg: koppelen op het doel-ID in plaats van op het tabblad-nummer.
    // Chrome geeft bij een tabblad soms een melding over een extensie-adres die
    // niets met dit tabblad te maken heeft; via het doel-ID speelt dat niet.
    try {
      const doelen = await new Promise((r) => chrome.debugger.getTargets(r));
      const t = (doelen || []).find((d) => d.tabId === tabId && d.type === "page");
      if (!t) throw eerste;
      await koppel({ targetId: t.id });
      doel.targetId = t.id;
      delete doel.tabId;
    } catch (e) {
    // Zit er al een ander opsporingsprogramma op dit tabblad — de DevTools van
    // de verkoper, of een andere extensie die hetzelfde doet — dan weigert
    // Chrome een tweede. Melden mét het adres, anders is het niet te plaatsen.
    let bezet = "";
    try {
      const doelen = await new Promise((r) => chrome.debugger.getTargets(r));
      const t = (doelen || []).find((d) => d.tabId === tabId);
      if (t && t.attached) bezet = " (er zit al een opsporingsprogramma op dit tabblad)";
    } catch (_) {}
      return `niet gekoppeld: ${eerste.message} / ${e.message}${bezet} — tab ${adres.slice(0, 50)}`;
    }
  }
  try {
    // Chrome schuift de pagina omlaag zodra hij de gele "wordt opgespoord"-balk
    // toont. Meten we de plek van het veld daarvóór, dan klikken we ernaast en
    // komt de toetsaanslag nergens terecht. Even wachten dus.
    await new Promise((r) => setTimeout(r, 700));
    // Eerst een echte klik in het veld: zonder cursor in de editor komt een
    // toetsaanslag nergens terecht. De plek komt uit de pagina zelf.
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId }, world: "MAIN",
      func: (sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const e = el.isContentEditable ? el : (el.querySelector('[contenteditable="true"]') || el);
        e.scrollIntoView({ block: "center" });
        const r = e.getBoundingClientRect();
        return { x: Math.round(r.left + Math.min(r.width - 8, 40)), y: Math.round(r.top + r.height - 12) };
      },
      args: ['[data-testid="text-editor-input_nl-NL"], [data-testid="text-editor-input_nl-BE"], [contenteditable="true"]'],
    });
    if (!result) return "veld niet gevonden";
    for (const type of ["mousePressed", "mouseReleased"]) {
      await stuur("Input.dispatchMouseEvent", {
        type, x: result.x, y: result.y, button: "left", clickCount: 1,
      });
    }
    // Eén spatie, echt getypt. Meer is niet nodig: het formulier neemt hierna
    // de hele tekst over die er al stond. Drie vormen achter elkaar, want welke
    // een site accepteert verschilt: rawKeyDown+char is hoe Chrome zelf een
    // tekstaanslag doorgeeft, insertText is de kortste weg.
    await stuur("Input.dispatchKeyEvent", { type: "rawKeyDown", key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 });
    await stuur("Input.dispatchKeyEvent", { type: "char", key: " ", text: " ", unmodifiedText: " " });
    await stuur("Input.dispatchKeyEvent", { type: "keyUp", key: " ", code: "Space", windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 });
    await new Promise((r) => setTimeout(r, 250));
    await stuur("Input.insertText", { text: " " });
    return `getypt op ${result.x},${result.y}`;
  } catch (e) {
    return `mislukt: ${e.message}`;
  } finally {
    // De koppeling van bij het openen laten we staan; die is voor het hele
    // tabblad en wordt opgeruimd als het tabblad sluit.
    if (!alGekoppeld) { try { chrome.debugger.detach(doel); } catch (_) {} }
  }
}


// ECHT KLIKKEN, met dezelfde koppeling als het echte typen.
//
// Marktplaats negeert een klik die van een script komt, net zoals het een
// getypte letter negeert. Gemeten 21-08-2026: formulier volledig ingevuld, geen
// enkel veld rood, knop "Plaats je advertentie" gewoon aanwezig en niet
// uitgeschakeld — en na onze klik gebeurde er niets. Met een echte muisklik op
// dezelfde plek wél.
async function klikEcht(tabId, selector) {
  if (!(await heeftDebugger())) return "geen-toestemming";
  // HET VENSTER MOET ZICHTBAAR ZIJN.
  //
  // Het werkvenster staat geminimaliseerd, zodat de verkoper er geen last van
  // heeft. Een pagina in zo'n venster is voor de browser "verborgen"
  // (document.hidden), en dat is precies het soort ding waar een formulier op
  // kan besluiten dat er geen echte gebruiker aan het werk is. Typen kwam er wél
  // doorheen, de plaatsknop niet — dus dit moet uitgesloten worden. Even
  // terugzetten, klikken, en daarna weer weg: de verkoper ziet hooguit een flits.
  let hersteld = null;
  try {
    const tab = await chrome.tabs.get(tabId);
    const win = await chrome.windows.get(tab.windowId);
    if (win.state === "minimized") {
      hersteld = { id: win.id, state: win.state };
      await chrome.windows.update(win.id, { state: "normal", focused: false });
      await new Promise((r) => setTimeout(r, 600));
    }
  } catch (_) {}
  if (!_vroegGekoppeld.has(tabId)) {
    // Koppeling weg: de verkoper drukte op Annuleren in de gele balk, of het
    // tabblad navigeerde ertussenuit. Nog één poging, want anders blijft het
    // zoekertje ingevuld-maar-ongeplaatst staan.
    const tab = await chrome.tabs.get(tabId).catch(() => null);
    if (!(await koppelVroeg(tabId, tab && tab.url))) return "niet gekoppeld";
  }
  const doel = { tabId };
  const stuur = (methode, params) => new Promise((res, rej) => {
    chrome.debugger.sendCommand(doel, methode, params, (r) => {
      chrome.runtime.lastError ? rej(new Error(chrome.runtime.lastError.message)) : res(r);
    });
  });
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId }, world: "MAIN",
      func: (sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const knop = el.tagName === "BUTTON" ? el : (el.querySelector("button") || el);
        knop.scrollIntoView({ block: "center" });
        const r = knop.getBoundingClientRect();
        if (!r.width || !r.height) return null;
        const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
        // Wat zit er op die plek? Een klik op de juiste coördinaten is nog geen
        // klik op de juiste knop: een balk onderaan of een reclamelaag ligt er
        // zo overheen, en dan klikken we op niets. Zonder deze controle blijft
        // "geklikt, maar er gebeurde niets" onverklaarbaar.
        const opDiePlek = document.elementFromPoint(x, y);
        const raakt = opDiePlek && (opDiePlek === knop || knop.contains(opDiePlek) || opDiePlek.contains(knop));
        return {
          x, y, raakt,
          binnenBeeld: y > 0 && y < innerHeight && x > 0 && x < innerWidth,
          hoogte: innerHeight, breedte: innerWidth,
          erop: opDiePlek ? (opDiePlek.tagName + "." + String(opDiePlek.className || "").split(" ")[0]).slice(0, 40) : "niets",
          zichtbaar: document.visibilityState + (document.hasFocus() ? "+focus" : "-focus"),
        };
      },
      args: [selector],
    });
    if (!result) return "knop niet gevonden";
    if (!result.binnenBeeld) {
      return `knop buiten beeld (${result.x},${result.y} in venster ${result.breedte}x${result.hoogte})`;
    }
    await new Promise((r) => setTimeout(r, 300));
    await stuur("Input.dispatchMouseEvent", { type: "mouseMoved", x: result.x, y: result.y, buttons: 0 });
    await stuur("Input.dispatchMouseEvent", { type: "mousePressed", x: result.x, y: result.y, button: "left", buttons: 1, clickCount: 1 });
    await stuur("Input.dispatchMouseEvent", { type: "mouseReleased", x: result.x, y: result.y, button: "left", buttons: 0, clickCount: 1 });
    return `geklikt op ${result.x},${result.y} (venster ${result.breedte}x${result.hoogte}`
         + `, zichtbaarheid ${result.zichtbaar}${hersteld ? ", venster teruggezet" : ""}`
         + `, daar ligt ${result.erop}${result.raakt ? " = de knop" : " — NIET de knop"})`;
  } catch (e) {
    return `mislukt: ${e.message}`;
  } finally {
    // Het venster weer wegzetten zoals het stond.
    if (hersteld) {
      setTimeout(() => {
        chrome.windows.update(hersteld.id, { state: "minimized" }).catch(() => {});
      }, 25000);
    }
  }
}


// WAT MARKTPLAATS ZÉLF ALS BESCHRIJVING HEEFT.
//
// Het verborgen veld description_nl-NL heeft twee waarden: die in de DOM (wat
// wij erin zetten) en die in de eigen staat van de pagina (wat React vasthoudt).
// Alleen die tweede telt bij het plaatsen. Live gemeten op 21-08-2026: tekst
// erin zetten geeft DOM 449 en staat 0 — en dan doet de plaatsknop niets, zonder
// klacht en zonder rood veld. Echt typen geeft beide 158, en dan plaatst hij.
function _mwEchteBeschrijvingLengte() {
  const el = document.querySelector('input[name*="escription" i], textarea[name*="escription" i]');
  if (!el) return -1;
  const sleutel = Object.keys(el).find((k) => k.startsWith("__reactProps"));
  const staat = sleutel ? (el[sleutel] || {}).value : null;
  return typeof staat === "string" ? staat.length : -1;
}

// Leest terug wat het formulier zélf als beschrijving beschouwt. Eén leeg veld
// is genoeg om afgekeurd te worden, dus dan melden we leeg.
function _mwHiddenDescriptionValue() {
  // Breed op naam zoeken. De oude, strakke lijst eiste letterlijk
  // "description_nl-…" of "description". Heette het veld op dit formulier iets
  // anders (description_fr-BE, listing.description, Description), dan vonden we
  // NIETS — en dan meldde de controle "prima, dit platform heeft dat veld niet"
  // terwijl er in werkelijkheid nooit iets was ingevuld. Precies zo kon 2dehands
  // blijven zeggen "Geen zoekertjestekst ingevuld".
  const SEL = 'input[name*="escription" i], textarea[name*="escription" i], '
            + 'input[id*="escription" i], textarea[id*="escription" i]';
  // Alleen echte tekstvelden. De brede naamzoektocht hierboven mag nooit een
  // keuzerondje, een aantal of een knop met de advertentietekst volschrijven.
  const _bruikbaar = (v) => {
    if (v.disabled || v.readOnly) return false;
    const t = (v.type || "text").toLowerCase();
    if (!(v instanceof HTMLTextAreaElement || t === "text" || t === "hidden")) return false;
    // "description" moet een heel woord zijn. Zo vangen we description_nl-BE,
    // description_fr-BE en listing.description, maar schrijven we nooit per
    // ongeluk in een veld als descriptionType of descriptionCount.
    return /(^|[^a-z])description([^a-z]|$)/i.test(v.name || v.id || "");
  };
  const velden = [...document.querySelectorAll(SEL)].filter(_bruikbaar);
  if (!velden.length) return null;
  if (velden.some((v) => (v.value || "").trim().length === 0)) return "";
  return velden[0].value || "";
}

// Vertelt wat er op DIT formulier daadwerkelijk staat. Zonder dit blijft elke
// afkeuring giswerk: we weten dan niet of het veld ontbreekt, leeg is, of anders
// heet. De uitkomst gaat mee in de foutmelding, zodat die in het dashboard staat
// in plaats van in een console die niemand opent.
function _mwDescribeDescriptionFields() {
  const SEL = 'input[name*="escription" i], textarea[name*="escription" i], '
            + 'input[id*="escription" i], textarea[id*="escription" i]';
  const velden = [...document.querySelectorAll(SEL)].map((v) => {
    const naam = v.name || v.id || "(naamloos)";
    const t = (v.type || "text").toLowerCase();
    return `${naam}[${t}]=${(v.value || "").trim().length}`;
  });
  const editors = [...document.querySelectorAll('[contenteditable="true"]')]
    .map((e) => (e.innerText || "").trim().length);
  return `velden: ${velden.join(", ") || "GEEN"} | editors: ${editors.join(", ") || "GEEN"}`;
}

// Het verborgen veld raakt niet één keer leeg maar telkens opnieuw: elke
// hertekening van het formulier (foto klaar, kenmerk gekozen, merk-venster
// dicht, veld verlaten) kan het wissen. Eenmalig vullen was daarom altijd een
// gok — vandaar dat het "heel random" misging. Deze bewaker zet het veld terug
// zodra het leeg raakt, tot en met het plaatsen. Hij schrijft uitsluitend als
// het veld leeg is, dus tekst die het formulier er zelf in zet blijft staan.
function _mwEnforceDescription(descText, durationMs) {
  // Breed op naam zoeken. De oude, strakke lijst eiste letterlijk
  // "description_nl-…" of "description". Heette het veld op dit formulier iets
  // anders (description_fr-BE, listing.description, Description), dan vonden we
  // NIETS — en dan meldde de controle "prima, dit platform heeft dat veld niet"
  // terwijl er in werkelijkheid nooit iets was ingevuld. Precies zo kon 2dehands
  // blijven zeggen "Geen zoekertjestekst ingevuld".
  const SEL = 'input[name*="escription" i], textarea[name*="escription" i], '
            + 'input[id*="escription" i], textarea[id*="escription" i]';
  // Alleen echte tekstvelden. De brede naamzoektocht hierboven mag nooit een
  // keuzerondje, een aantal of een knop met de advertentietekst volschrijven.
  const _bruikbaar = (v) => {
    if (v.disabled || v.readOnly) return false;
    const t = (v.type || "text").toLowerCase();
    if (!(v instanceof HTMLTextAreaElement || t === "text" || t === "hidden")) return false;
    // "description" moet een heel woord zijn. Zo vangen we description_nl-BE,
    // description_fr-BE en listing.description, maar schrijven we nooit per
    // ongeluk in een veld als descriptionType of descriptionCount.
    return /(^|[^a-z])description([^a-z]|$)/i.test(v.name || v.id || "");
  };
  try { clearInterval(window.__ovDescKeeper); } catch (_) {}
  const einde = Date.now() + (durationMs || 300000);
  const herstel = () => {
    if (Date.now() > einde) { try { clearInterval(window.__ovDescKeeper); } catch (_) {} return; }
    for (const veld of document.querySelectorAll(SEL)) {
      if (!_bruikbaar(veld) || (veld.value || "").trim().length > 0) continue;
      const proto = veld instanceof HTMLTextAreaElement
        ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(veld, descText);
      veld.dispatchEvent(new Event("input", { bubbles: true }));
      veld.dispatchEvent(new Event("change", { bubbles: true }));
    }
  };
  herstel();
  window.__ovDescKeeper = setInterval(herstel, 250);
  return true;
}

// ── WAAR HET FORMULIER DE BESCHRIJVING ÉCHT BEWAART ───────────────────────
//
// Live gemeten op 04-09-2026, ingelogd, op zowel www.2dehands.be/plaats/… als
// www.marktplaats.nl/plaats/… (categorie Heren > Truien en Vesten):
//
//   * het plaatsformulier is een react-hook-form; de waarde waarop het
//     valideert staat in `control._formValues.description`;
//   * de zichtbare Lexical-editor vullen (onze FILL_DESC) zet 48 tekens in
//     beeld en laat `_formValues.description` op 0 staan;
//   * het verborgen veld `description_nl-BE` erin zetten helpt niet: React
//     kent die waarde niet (`__reactProps.value` blijft leeg) en het formulier
//     leest hem niet;
//   * `document.execCommand("insertText")` doet in deze editor helemaal niets
//     (de tekst wordt niet langer), en Lexical's eigen insertText maakt de
//     editor wél langer maar `_formValues` niet;
//   * het formulier zelf laten valideren (handleSubmit met eigen callbacks, dus
//     zonder te plaatsen) gaf met een gevulde editor en lege `_formValues` de
//     fout op `description` — precies "Geen zoekertjestekst ingevuld" — en na
//     alléén `_formValues.description` te vullen viel `description` uit de
//     foutenlijst weg. Dat is de voor-en-na-proef op de plek waar de klacht
//     vandaan komt.
//
// Daarom schrijven we hier rechtstreeks in de staat van het formulier. Dat is
// wat een echte toetsaanslag indirect ook bereikt, maar zonder debugger-koppeling,
// zonder gele balk en zonder muiscoördinaten die ernaast kunnen zitten.
//
// Let op: chrome.scripting.executeScript injecteert alléén de functie zelf, dus
// de zoeker staat opzettelijk in elke functie opnieuw.
function _mwZetFormulierBeschrijving(descText) {
  const _vind = () => {
    const starts = [
      document.querySelector('[data-testid^="text-editor-input"]'),
      document.querySelector('input[name^="title_"]'),
      document.querySelector("form"),
    ].filter(Boolean);
    for (const start of starts) {
      const fk = Object.keys(start).find((k) => k.startsWith("__reactFiber"));
      if (!fk) continue;
      let f = start[fk], d = 0;
      while (f && d < 40) {
        let ms = f.memoizedState, i = 0;
        while (ms && i < 40) {
          const s = ms.memoizedState;
          const k = (s && s.current && typeof s.current === "object") ? s.current : s;
          if (k && typeof k === "object" && k._formValues && k._fields) return k;
          ms = ms.next; i++;
        }
        f = f.return; d++;
      }
    }
    return null;
  };
  const c = _vind();
  if (!c) return -1;                       // geen react-hook-form: niets te doen
  if (!("description" in c._formValues) && !(c._fields || {}).description) return -1;
  try {
    c._formValues.description = descText;
    const veld = (c._fields || {}).description;
    if (veld && veld._f) veld._f.value = descText;
    return String(c._formValues.description || "").length;
  } catch (_) {
    return -1;
  }
}

// Leest terug wat het formulier zélf als beschrijving vasthoudt. Dit is de enige
// harde waarheid: de zichtbare editor en het verborgen veld zeggen allebei niets
// over wat er bij het plaatsen wordt gecontroleerd.
function _mwLeesFormulierBeschrijving() {
  const _vind = () => {
    const starts = [
      document.querySelector('[data-testid^="text-editor-input"]'),
      document.querySelector('input[name^="title_"]'),
      document.querySelector("form"),
    ].filter(Boolean);
    for (const start of starts) {
      const fk = Object.keys(start).find((k) => k.startsWith("__reactFiber"));
      if (!fk) continue;
      let f = start[fk], d = 0;
      while (f && d < 40) {
        let ms = f.memoizedState, i = 0;
        while (ms && i < 40) {
          const s = ms.memoizedState;
          const k = (s && s.current && typeof s.current === "object") ? s.current : s;
          if (k && typeof k === "object" && k._formValues && k._fields) return k;
          ms = ms.next; i++;
        }
        f = f.return; d++;
      }
    }
    return null;
  };
  const c = _vind();
  if (!c) return -1;
  try { return String(c._formValues.description || "").length; } catch (_) { return -1; }
}

// De staat van het formulier raakt niet één keer leeg maar telkens opnieuw: elke
// hertekening (foto klaar, kenmerk gekozen, merk-venster dicht) kan de
// beschrijving terugzetten op leeg. Deze bewaker zet hem terug zodra hij leeg is,
// tot en met het plaatsen. Hij schrijft uitsluitend als de waarde leeg is, dus
// tekst die het formulier er zelf in zet blijft staan.
function _mwBewaakFormulierBeschrijving(descText, durationMs) {
  const _vind = () => {
    const starts = [
      document.querySelector('[data-testid^="text-editor-input"]'),
      document.querySelector('input[name^="title_"]'),
      document.querySelector("form"),
    ].filter(Boolean);
    for (const start of starts) {
      const fk = Object.keys(start).find((k) => k.startsWith("__reactFiber"));
      if (!fk) continue;
      let f = start[fk], d = 0;
      while (f && d < 40) {
        let ms = f.memoizedState, i = 0;
        while (ms && i < 40) {
          const s = ms.memoizedState;
          const k = (s && s.current && typeof s.current === "object") ? s.current : s;
          if (k && typeof k === "object" && k._formValues && k._fields) return k;
          ms = ms.next; i++;
        }
        f = f.return; d++;
      }
    }
    return null;
  };
  try { clearInterval(window.__ovFormDescKeeper); } catch (_) {}
  const einde = Date.now() + (durationMs || 300000);
  const herstel = () => {
    if (Date.now() > einde) { try { clearInterval(window.__ovFormDescKeeper); } catch (_) {} return; }
    const c = _vind();
    if (!c) return;
    try {
      if (String(c._formValues.description || "").trim().length > 0) return;
      c._formValues.description = descText;
      const veld = (c._fields || {}).description;
      if (veld && veld._f) veld._f.value = descText;
    } catch (_) {}
  };
  herstel();
  window.__ovFormDescKeeper = setInterval(herstel, 250);
  return true;
}


// Marktplaats beschouwde de advertentietekst als leeg terwijl hij zichtbaar in de
// editor stond — en één zelf getypte spatie liet de melding meteen verdwijnen.
// Dat is het bewijs dat het formulier niet naar de inhoud kijkt maar naar een
// échte toetsaanslag: pas dan merkt het formulier het veld als "aangeraakt" aan
// en loopt zijn eigen controle opnieuw. Alles wat wij tot nu toe deden zet de
// tekst neer zonder ooit zo'n aanslag te veroorzaken.
//
// execCommand("insertText") is de enige manier om dat vanuit een script wél te
// doen: Chrome vuurt daarbij dezelfde native beforeinput/input af als een echte
// toets. We typen precies wat de gebruiker met de hand deed — één spatie aan het
// eind — en laten hem staan, want juist dat bleek te werken.
function _mwNudgeDescription(selector) {
  const found = document.querySelector(selector);
  if (!found) return false;
  const el = found.isContentEditable ? found
    : (found.querySelector('[contenteditable="true"]') || found);
  const voor = (el.innerText || el.value || "").length;
  el.scrollIntoView({ block: "center" });
  el.focus();
  try {
    // Cursor helemaal achteraan, anders landt de spatie middenin de tekst.
    const r = document.createRange();
    r.selectNodeContents(el);
    r.collapse(false);
    const s = getSelection();
    s.removeAllRanges();
    s.addRange(r);
  } catch (_) {}
  let ok = false;
  try { ok = document.execCommand("insertText", false, " "); } catch (_) {}
  const na = (el.innerText || el.value || "").length;
  return ok && na > voor;
}

// Prijs zetten in de ECHTE paginacontext (MAIN world).
//
// Vinted's prijsveld is een React-veld met een masker. Een content script leeft
// in een eigen wereld en kan React's `_valueTracker` op dat veld niet zien; die
// tracker onthoudt de laatst bekende waarde en zorgt dat React een input-signaal
// negeert als hij denkt dat er niets veranderd is. Gevolg: het veld tóónde
// €14.99, maar het formulier hield vast aan zijn lege interne waarde en bleef
// "Price must be greater than or equal to 1.0" roepen — precies de melding die
// het plaatsen blokkeerde. Hier zetten we de waarde vanuit de pagina zelf, met
// de tracker gereset, zodat React de nieuwe prijs echt overneemt.
async function _mwSetVintedPrice(selector, values) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const el = document.querySelector(selector);
  if (!el) return { ok: false, reason: "field-not-found" };
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  const num = (v) => {
    const n = parseFloat(String(v ?? "").replace(/[^\d.,]/g, "").replace(",", "."));
    return isFinite(n) ? n : NaN;
  };
  const want = num(values[0]);

  // Vinted zet zijn klacht ("Price must be greater than or equal to 1.0") pas
  // een halve seconde na het verlaten van het veld neer, en zet geen
  // aria-invalid. Wie alleen naar de waarde kijkt, keurt dus een prijs goed die
  // Vinted een tel later weigert. Daarom lezen we hier de melding zelf, in
  // dezelfde wereld als het formulier.
  const FOUT = /price must|must be greater|greater than or equal|at least|minimaal|moet (groter|ten minste)|ongeldig|invalid/i;
  const klacht = () => {
    const kandidaten = [];
    for (const id of (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean)) {
      const e = document.getElementById(id);
      if (e) kandidaten.push(e);
    }
    let n = el.parentElement;
    for (let i = 0; i < 4 && n; i++, n = n.parentElement) kandidaten.push(...n.querySelectorAll("*"));
    return kandidaten.some((e) => e && e.offsetParent !== null && FOUT.test((e.textContent || "").trim()));
  };

  // De waarde die het FORMULIER zelf vasthoudt. Dat is de enige harde waarheid:
  // het zichtbare veld kan een prijs tonen die het formulier nooit heeft
  // overgenomen, en andersom kan een rode regel blijven staan terwijl het
  // formulier de prijs allang heeft.
  const formWaarde = () => {
    try {
      for (const k in el) {
        if (k.startsWith("__reactProps$") && el[k] && el[k].value != null) return num(el[k].value);
      }
      for (const k in el) {
        if (!k.startsWith("__reactFiber$")) continue;
        let f = el[k];
        for (let i = 0; i < 8 && f; i++, f = f.return) {
          if (f.memoizedProps && f.memoizedProps.value != null) return num(f.memoizedProps.value);
        }
      }
    } catch (_) {}
    return NaN;
  };

  // HET VELD ECHT VERLATEN.
  // Gemeten in Chrome (04-09-2026): `dispatchEvent(new Event("blur"))` levert
  // GEEN focusout op, en React luistert nu juist op focusout. Alles wat wij tot
  // nu toe deden liet het veld dus gefocust achter en het formulier heeft zijn
  // controle nooit opnieuw gedraaid: de rode regel bleef staan terwijl de prijs
  // er gewoon in stond. Een echte el.blur() doet het wel, maar niet in een
  // venster zonder toetsenbordfocus, en het werk draait ingeklapt op de
  // achtergrond. Daarom allebei: de echte blur, plus een focusout die bubbelt.
  const verlaatVeld = () => {
    try { el.blur(); } catch (_) {}
    el.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  };

  const betreedVeld = () => {
    try { el.focus(); } catch (_) {}
    el.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
  };

  // DE WAARDE ZETTEN ZONDER HET VELD EERST LEEG TE MAKEN.
  // Hier stond eerst: waarde op "" zetten, een input-gebeurtenis sturen, en dan
  // pas de prijs. Dat gaf het formulier zwart op wit een LEGE prijs te zien, en
  // dat is precies de invoer waar "Price must be greater than or equal to 1.0"
  // op slaat. We maakten de klacht dus zelf. Nu gaat de prijs er in een keer in,
  // over de oude waarde heen.
  const zetWaarde = (out) => {
    betreedVeld();
    try { el.setSelectionRange(0, String(el.value || "").length); } catch (_) {}
    try { el._valueTracker && el._valueTracker.setValue(" "); } catch (_) {}
    setter.call(el, out);
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: out }));
  };

  // DE HANDELING VAN DE VERKOPER ZELF.
  // Daniel: "als ik dan zelf een 9 typ of iets weghaal, verdwijnt die melding."
  // Een teken over zichzelf heen typen dus, zonder de prijs te veranderen.
  // execCommand("insertText") is de enige route uit een script die daarbij een
  // ECHTE (isTrusted) invoergebeurtenis oplevert, gemeten in Chrome op
  // 04-09-2026; alles wat we met dispatchEvent sturen is isTrusted=false.
  const hertyp = async () => {
    const huidig = String(el.value || "");
    if (!huidig) return false;
    const laatsteTeken = huidig.slice(-1);
    betreedVeld();
    let gelukt = false;
    try { el.setSelectionRange(huidig.length - 1, huidig.length); } catch (_) {}
    try { gelukt = document.execCommand("insertText", false, laatsteTeken); } catch (_) { gelukt = false; }
    if (!gelukt || String(el.value || "") !== huidig) {
      try { el.setSelectionRange(huidig.length, huidig.length); } catch (_) {}
      try { document.execCommand("delete", false, null); } catch (_) {}
      await sleep(80);
      try { document.execCommand("insertText", false, laatsteTeken); } catch (_) {}
    }
    await sleep(150);
    verlaatVeld();
    await sleep(300);
    return Math.abs((num(el.value) || -1) - want) < 0.01;
  };

  const zet = async (out) => {
    el.scrollIntoView({ block: "center" });
    zetWaarde(out);
    await sleep(200);
    verlaatVeld();

    // Even de tijd geven om alsnog te klagen: te vroeg kijken is precies hoe een
    // afgekeurde prijs er goed uitzag.
    let klaagt = false;
    for (let i = 0; i < 5; i++) {
      await sleep(200);
      if (klacht()) { klaagt = true; break; }
    }
    const waardeKlopt = Math.abs((num(el.value) || -1) - want) < 0.01;
    if (!waardeKlopt) return null;

    // Blijft de klacht staan terwijl de prijs er goed in staat? Dan doen we na
    // wat de verkoper met de hand doet, in plaats van de prijs nog een keer te
    // zetten. Dat laatste hielp aantoonbaar niet: hij stond er al goed in.
    if (klaagt) {
      for (let poging = 0; poging < 2 && klacht(); poging++) await hertyp();
      klaagt = klacht();
    }

    // HIER STOND: `if (klaagt && aria-invalid === "true") return false;` en dat
    // sprak zichzelf tegen met de uitleg hierboven, die juist vaststelt dat
    // Vinted GEEN aria-invalid zet.
    //
    // Niet gokken op meldingen dus. Vinted is een React-formulier en houdt zijn
    // eigen waarde bij; die lezen we hier rechtstreeks uit. Houdt het formulier
    // de juiste prijs vast, dan is de prijs in orde, ook als de rode regel blijft
    // hangen. Een blijven hangende melding mag een aantoonbaar goede prijs niet
    // weggooien, want dan wordt er helemaal niets geplaatst.
    const intern = formWaarde();
    if (isFinite(intern)) {
      if (Math.abs(intern - want) >= 0.01) return null;
      return { used: out, value: el.value, form: intern, klacht: klaagt };
    }
    // Lukt dat niet, dan is een zichtbare klacht het enige signaal dat we
    // hebben, en dan proberen we eerst de volgende schrijfwijze.
    return klaagt ? null : { used: out, value: el.value, form: null, klacht: false };
  };

  // Alle schrijfwijzen proberen en de eerste houden waar Vinted NIET over klaagt.
  // Welke dat is verschilt per taalinstelling van het account, en dat viel niet
  // betrouwbaar aan de pagina af te lezen, dus laten we het formulier het zeggen.
  for (const out of values) {
    const uit = await zet(out);
    if (uit) return { ok: true, ...uit };
  }
  return { ok: false, reason: "rejected", value: el.value, klacht: klacht() };
}

// Wat houdt het FORMULIER zelf op dit moment als prijs vast? Dit is de vraag
// waarop de eindcontrole voor het plaatsen afgaat. Alleen naar de rode regel
// kijken was fout: die bleef staan bij een prijs die er gewoon in stond, en dan
// werd er helemaal niets geplaatst.
function _mwLeesVintedPrijs(selector) {
  const el = document.querySelector(selector);
  if (!el) return { gevonden: false };
  const num = (v) => {
    const n = parseFloat(String(v ?? "").replace(/[^\d.,]/g, "").replace(",", "."));
    return isFinite(n) ? n : NaN;
  };
  let form = NaN;
  try {
    for (const k in el) {
      if (k.startsWith("__reactProps$") && el[k] && el[k].value != null) { form = num(el[k].value); break; }
    }
    if (!isFinite(form)) {
      for (const k in el) {
        if (!k.startsWith("__reactFiber$")) continue;
        let f = el[k];
        for (let i = 0; i < 8 && f; i++, f = f.return) {
          if (f.memoizedProps && f.memoizedProps.value != null) { form = num(f.memoizedProps.value); break; }
        }
        if (isFinite(form)) break;
      }
    }
  } catch (_) {}
  return { gevonden: true, dom: num(el.value), form: isFinite(form) ? form : null };
}

async function _mwFillDescription(selector, descText) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const found = document.querySelector(selector);
  if (!found) return false;
  // Wijst de selector naar een omhulsel in plaats van het bewerkbare veld zelf,
  // dan gaan focus en execCommand naar het verkeerde element en landt er niets.
  const el = found.isContentEditable ? found
    : (found.querySelector('[contenteditable="true"]') || found);

  el.scrollIntoView({ block: "center" });
  el.focus();
  await sleep(150);

  // Een écht <textarea>/<input> (Vinted) is geen rich-text editor. Alle routes
  // hieronder meten of het gelukt is via innerText/textContent — en dat geeft bij
  // een textarea de ORIGINELE opmaak terug, niet de getypte waarde. Daardoor zag
  // elke poging "leeg", vielen we door tot de laatste return en meldde de
  // beschrijvingstap "kon niet in de editor worden gezet" terwijl het veld gewoon
  // te vullen is. Vandaar: form-velden krijgen hun eigen, korte route.
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
    const want = descText;
    const proto = el instanceof HTMLTextAreaElement
      ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    const gevuld = () => (el.value || "").trim() === want.trim();

    // 1. React's eigen value-setter + input/change: dit is de manier waarop een
    //    React-gecontroleerd veld een externe waarde accepteert.
    try {
      setter.call(el, want);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      await sleep(150);
      if (gevuld()) return true;
    } catch (_) {}

    // 2. Echt "typen": selecteer alles en laat Chrome zelf de native
    //    beforeinput/input afvuren. Velden die stap 1 terugdraaien nemen dit wel.
    try {
      el.focus();
      el.select?.();
      document.execCommand("insertText", false, want);
      await sleep(200);
      if (gevuld()) return true;
    } catch (_) {}

    // 3. Plakken, met een echte DataTransfer.
    try {
      el.focus();
      el.select?.();
      const dt = new DataTransfer();
      dt.setData("text/plain", want);
      el.dispatchEvent(new ClipboardEvent("paste", {
        clipboardData: dt, bubbles: true, cancelable: true,
      }));
      await sleep(250);
      if (gevuld()) return true;
    } catch (_) {}

    // Iets is beter dan niets: alleen als er écht tekst staat melden we succes.
    return (el.value || "").trim().length > 0;
  }

  // Lexical hangt __lexicalEditor niet altijd op het element dat we selecteren.
  // Op 2dehands zit hij op een ouder of een kind, waardoor we hem niet vonden en
  // terugvielen op textContent — die "ja, er staat tekst" zei terwijl de editor
  // zelf leeg was. Het zoekertje ging dan de deur uit en 2dehands weigerde met
  // "Geen zoekertjestekst ingevuld", met een zichtbaar gevulde beschrijving.
  function findLexical() {
    for (let n = el; n; n = n.parentElement) {
      if (n.__lexicalEditor) return n.__lexicalEditor;
    }
    for (const n of el.querySelectorAll("*")) {
      if (n.__lexicalEditor) return n.__lexicalEditor;
    }
    return null;
  }

  // Verify via Lexical EditorState, not DOM textContent.
  // DOM can have stale content from earlier fills; EditorState is what validation reads.
  function lexHasText() {
    const lex = findLexical();
    // Geen Lexical gevonden? Dan is dit geen Lexical-editor en is de DOM wél de
    // waarheid. Alleen dán mag textContent tellen.
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

  // Zet de cursor IN het veld. Zonder eigen selectie doet execCommand op
  // 2dehands helemaal niets (live gemeten: leeg veld, lege editorstaat) en werkt
  // ook "selectAll" + "delete" niet — tekst stapelde zich dan op in plaats van
  // vervangen te worden.
  function placeCaret(collapse) {
    el.focus();
    const r = document.createRange();
    r.selectNodeContents(el);
    if (collapse) r.collapse(false);
    const s = getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }

  // ── Aanpak 1: Lexical's eigen update-API ──────────────────────────────────
  // Live gemeten op 2dehands: dit is de enige manier die het veld schoon
  // leegmaakt én echte alinea's oplevert in de editorstaat waar de site zijn
  // validatie op baseert. execCommand stond hier eerst voorop en liet daar zowel
  // een lege editorstaat ("Geen zoekertjestekst ingevuld") als aan elkaar
  // geplakte zinnen achter.
  {
    const lexApi = findLexical();
    const PClass = lexApi?._nodes?.get("paragraph")?.klass;
    const TClass = lexApi?._nodes?.get("text")?.klass;
    if (lexApi && typeof lexApi.update === "function" && PClass && TClass) {
      try {
        await new Promise((resolve) => {
          lexApi.update(() => {
            const root = lexApi._editorState?._nodeMap?.get("root");
            if (!root) return;
            let c = root.getFirstChild?.();
            while (c) { const n = c.getNextSibling?.(); try { c.remove?.(); } catch (_) {} c = n; }
            for (const line of _lines) {
              const p = new PClass();
              if (line.length > 0) p.append(new TClass(line));
              root.append(p);
            }
          }, { discrete: true, onUpdate: resolve });
          setTimeout(resolve, 800);
        });
        await sleep(250);
        if (structureOk()) return true;
      } catch (_) {}
    }
  }

  // ── Aanpak 2: ClipboardEvent paste ────────────────────────────────────────
  // Een echte plakactie draagt de regeleindes mee in text/plain. Live gemeten
  // als enige execCommand-vrije route die alinea's overhoudt.
  try {
    const dt = new DataTransfer();
    dt.setData("text/plain", descText);
    placeCaret(false); // hele inhoud geselecteerd: de plak vervangt hem
    el.dispatchEvent(new ClipboardEvent("paste", {
      clipboardData: dt, bubbles: true, cancelable: true,
    }));
    await sleep(400);
    if (structureOk()) return true;
  } catch (_) {}

  // ── Aanpak 3: execCommand ─────────────────────────────────────────────────
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
      placeCaret(false);
      document.execCommand("delete", false, null);
      placeCaret(true);
      for (let i = 0; i < _lines.length; i++) {
        if (i > 0) { try { insertBreak(); } catch (_) {} }
        if (_lines[i].length > 0) document.execCommand("insertText", false, _lines[i]);
      }
      await sleep(300);
      if (structureOk()) return true;
      if (_wantLines <= 1) break; // single-line text — nothing structural to recover
    }
  } catch (_) {}

  // ── Aanpak 4: line-by-line insertText beforeinput ────────────────────────
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

  // Every strategy failed to keep the paragraph structure. Text that landed at
  // all still beats an empty description, so report on content as a last resort.
  return lexHasText();
}

// Het formulier achter de editor pikt de tekst pas op als het veld verlaten
// wordt. Wij vulden en klikten meteen op Plaatsen, waardoor 2dehands bleef
// zeggen "Geen zoekertjestekst ingevuld" terwijl de tekst zichtbaar in de
// editor stond. Marktplaats leest wél direct mee, dus daar viel het niet op.
function _mwBlurDescription(selector) {
  const found = document.querySelector(selector);
  if (!found) return false;
  const el = found.isContentEditable ? found
    : (found.querySelector('[contenteditable="true"]') || found);
  for (const type of ["input", "change"]) {
    el.dispatchEvent(new Event(type, { bubbles: true }));
  }
  el.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
  el.blur();
  document.body.click();
  return true;
}

async function _mwFillBrand(brand) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Defined INSIDE this function on purpose: chrome.scripting.executeScript
  // serialises `func` on its own, so anything it calls must live in the same
  // function body — a top-level helper would be undefined in the page.
  async function _mwCloseBrandModal() {
    const getModal = () =>
      document.querySelector(".ReactModal__Content") || document.querySelector('[role="dialog"]');
    for (let attempt = 0; attempt < 3; attempt++) {
      const modal = getModal();
      if (!modal) return true;
      const closeBtn = [...modal.querySelectorAll("button")].find((b) => {
        const label = (b.getAttribute("aria-label") || "").toLowerCase();
        return b.offsetParent !== null && (label.includes("close") || label.includes("sluit"));
      });
      if (closeBtn) closeBtn.click();
      else {
        modal.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        document.querySelector(".ReactModal__Overlay")?.click();
      }
      await sleep(400);
    }
    return !getModal();
  }
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
    if ((trigger.value || "").trim().length > 0) {
      await _mwCloseBrandModal();
      return true;
    }
  }

  // Nothing matched (or the click didn't commit). Closing the modal is NOT
  // optional: ReactModal marks the rest of the page inert while it's open, so a
  // modal left behind silently swallowed every field after Merk — manufacturer,
  // delivery and the bid price all stayed empty with no error anywhere. A bare
  // Escape on `document` is not enough; ReactModal listens on its own node.
  await _mwCloseBrandModal();
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

  // Het dashboard heeft zojuist werk klaargezet — nu kijken in plaats van tot de
  // volgende ronde wachten. Dat scheelt per klus tot een halve minuut waarin er
  // zichtbaar niets gebeurde. Loopt er al een klus, dan verandert dit niets: de
  // server geeft niets vrij zolang er iets geclaimd is.
  if (msg.type === "POLL_NOW") {
    pollJobs();
    sendResponse({ ok: true });
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
    chrome.storage.local.get(key, (s) => {
      const meta = s[key] || null;
      // HET ENIGE HARDE BEWIJS DAT HET FORMULIER ECHT OPENGING.
      // Dit script staat in de manifest alleen op het plaatsformulier zelf. Op
      // een foutpagina of een inlogscherm draait het niet en komt deze vraag
      // dus nooit. De bewaker gebruikt dat verschil, zie meldNooitBegonnen.
      if (meta && !meta.scriptSeen) {
        chrome.storage.local.set({ [key]: { ...meta, scriptSeen: true } });
        if (meta.platform) chrome.storage.local.remove(`${NIET_GESTART_PREFIX}${meta.platform}`);
      }
      sendResponse({ job: meta });
    });
    return true;
  }

  // "Er is op Plaatsen/Upload geklikt." Vanaf dat moment is elk advertentie-adres
  // in dit tabblad een echte, geplaatste advertentie — ook zonder de nette naam
  // in de URL. Zie de toelichting bij de klik zelf in shared.js.
  if (msg.type === "SUBMIT_CLICKED") {
    const key = `jobtab_${sender.tab?.id}`;
    chrome.storage.local.get(key, (s) => {
      const meta = s[key];
      if (meta) chrome.storage.local.set({ [key]: { ...meta, submitClicked: true } });
      sendResponse(true);
    });
    return true;
  }

  // ONTWAPEN VLAK VOOR DE PLAATSKLIK.
  //
  // De plaatsknop stuurt de pagina weg, en het formulier van Marktplaats hangt
  // aan dat wegnavigeren een "Site verlaten? Wijzigingen die je hebt aangebracht
  // worden mogelijk niet opgeslagen". Chrome toont die vraag aan de verkoper en
  // zet ALLES stil tot hij klikt — ook het volgende tabblad, want twee tabbladen
  // van dezelfde site delen één proces. Jaap (Zilverwebsite) meldde het exact zo:
  // "als ik hier handmatig op leave klik, wordt de advertentie geplaatst".
  //
  // De wacht in content/unload_guard.js werd tot nu toe alleen aangeroepen als
  // WIJ een tabblad sloten of wegstuurden. De navigatie die de plaatsknop zelf
  // veroorzaakt viel daar buiten. Dat gat is dit.
  if (msg.type === "ONTWAPEN_AFSLUITVRAAG") {
    ontwapenAfsluitvraag(sender.tab?.id).finally(() => sendResponse(true));
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

  // Prijs zetten vanuit de pagina zelf (zie _mwSetVintedPrice).
  if (msg.type === "SET_PRICE_MAIN") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwSetVintedPrice,
      args: [msg.selector, msg.values],
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error("[Omnivaleur] SET_PRICE_MAIN failed:", chrome.runtime.lastError.message);
        sendResponse({ ok: false, reason: chrome.runtime.lastError.message });
      } else {
        console.log("[Omnivaleur] SET_PRICE_MAIN result:", results?.[0]?.result);
        sendResponse(results?.[0]?.result ?? { ok: false, reason: "no-result" });
      }
    });
    return true;
  }

  // Leest terug welke prijs het formulier zelf vasthoudt. De eindcontrole voor
  // het plaatsen gaat hierop af in plaats van op de rode regel onder het veld.
  if (msg.type === "READ_PRICE_MAIN") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwLeesVintedPrijs,
      args: [msg.selector],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(null);
      else sendResponse(results?.[0]?.result ?? null);
    });
    return true;
  }

  // Het formulier praat mee in dit log: de console van de tab zelf is weg zodra
  // de tab dichtgaat, deze niet.
  //
  // Elke logregel is meteen een teken van leven. De bewaker sloeg namelijk toe
  // terwijl het formulier gewoon nog aan het werk was: het invullen kostte net
  // te lang, de opdracht werd afgebroken vlak vóór het plaatsen en het zoekertje
  // bleef ingevuld-maar-ongeplaatst staan. Zolang er gewerkt wordt schuiven we
  // de bewaker dus op — maar nooit voorbij de grens waarop de server de opdracht
  // zelf terugneemt, want dan zou hij een tweede keer uitgezet worden.
  if (msg.type === "LOG") {
    console.log(`[Omnivaleur][formulier] ${msg.text}`);
    keepJobAlive(sender.tab?.id);
    sendResponse(true);
    return true;
  }

  // Vult het verborgen veld waar de validatie op afgaat.
  if (msg.type === "FILL_HIDDEN_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwFillHiddenDescription, args: [msg.text],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(false);
      else sendResponse(results?.[0]?.result ?? false);
    });
    return true;
  }

  // Houdt het verborgen beschrijvingsveld gevuld zolang het formulier openstaat.
  if (msg.type === "ENFORCE_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwEnforceDescription, args: [msg.text, msg.durationMs || 300000],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(false);
      else sendResponse(results?.[0]?.result ?? false);
    });
    return true;
  }

  // Laatste redmiddel: een echte toetsaanslag via de debugger-API.
  if (msg.type === "ECHTE_DESC_LENGTE") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN", func: _mwEchteBeschrijvingLengte,
    }, (r) => {
      if (chrome.runtime.lastError) sendResponse(-1);
      else sendResponse(r?.[0]?.result ?? -1);
    });
    return true;
  }

  if (msg.type === "KLIK_ECHT") {
    klikEcht(sender.tab.id, msg.selector).then((uit) => sendResponse(uit));
    return true;
  }

  if (msg.type === "TYPE_ECHT") {
    typEchteToets(sender.tab.id, msg.text || " ").then((uitkomst) => sendResponse(uitkomst));
    return true;
  }

  // Heeft de gebruiker het echte-toetsenbord-recht al gegeven?
  if (msg.type === "HEEFT_DEBUGGER") {
    heeftDebugger().then((ja) => sendResponse(ja));
    return true;
  }

  if (msg.type === "READ_HIDDEN_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwHiddenDescriptionValue, args: [],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(null);
      else sendResponse(results?.[0]?.result ?? null);
    });
    return true;
  }

  // Zet de beschrijving in de staat van het formulier zelf — zie
  // _mwZetFormulierBeschrijving. Dit is de plek waar de validatie op afgaat.
  if (msg.type === "FILL_FORM_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwZetFormulierBeschrijving, args: [msg.text],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(-1);
      else sendResponse(results?.[0]?.result ?? -1);
    });
    return true;
  }

  // Leest terug hoeveel tekens het formulier zelf als beschrijving vasthoudt.
  if (msg.type === "READ_FORM_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwLeesFormulierBeschrijving, args: [],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(-1);
      else sendResponse(results?.[0]?.result ?? -1);
    });
    return true;
  }

  // Houdt die staat gevuld zolang het formulier openstaat.
  if (msg.type === "ENFORCE_FORM_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwBewaakFormulierBeschrijving, args: [msg.text, msg.durationMs || 300000],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(false);
      else sendResponse(results?.[0]?.result ?? false);
    });
    return true;
  }

  // Leest terug wat er echt op het formulier staat — zie _mwDescribeDescriptionFields.
  if (msg.type === "DESCRIBE_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwDescribeDescriptionFields, args: [],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse("(niet leesbaar)");
      else sendResponse(results?.[0]?.result ?? "(leeg)");
    });
    return true;
  }

  // Typt één echte spatie in de editor — zie _mwNudgeDescription.
  if (msg.type === "NUDGE_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id }, world: "MAIN",
      func: _mwNudgeDescription, args: [msg.selector],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(false);
      else sendResponse(results?.[0]?.result ?? false);
    });
    return true;
  }

  if (msg.type === "BLUR_DESC") {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: "MAIN",
      func: _mwBlurDescription,
      args: [msg.selector],
    }, (results) => {
      if (chrome.runtime.lastError) sendResponse(false);
      else sendResponse(results?.[0]?.result ?? false);
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

  // Photo download of last resort. A content script's fetch carries the PAGE's
  // origin (marktplaats.nl), so a photo host that doesn't allow that origin fails
  // in the page no matter what — and the photo silently never made it onto the
  // listing. The service worker fetches under the extension's own origin, which
  // is not bound by the marketplace's CORS relationship with the photo host.
  if (msg.type === "FETCH_PHOTO") {
    (async () => {
      try {
        const resp = await fetch(msg.url);
        if (!resp.ok) { sendResponse({ ok: false, error: `HTTP ${resp.status}` }); return; }
        const buf = new Uint8Array(await resp.arrayBuffer());
        // Blobs can't cross the message boundary — hand over a data: URL, which
        // the content script turns straight back into a File. Encoded in chunks
        // because String.fromCharCode(...buf) blows the argument limit on any
        // real photo.
        let bin = "";
        for (let i = 0; i < buf.length; i += 0x8000) {
          bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
        }
        const mime = resp.headers.get("content-type") || "image/jpeg";
        sendResponse({ ok: true, dataUrl: `data:${mime};base64,${btoa(bin)}` });
      } catch (e) {
        console.error("[Omnivaleur] FETCH_PHOTO failed:", msg.url, e);
        sendResponse({ ok: false, error: String(e?.message || e) });
      }
    })();
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
      if (sender.tab?.id) sluitWerkTabblad(sender.tab.id, 2000);
    });
    sendResponse({ ok: true });
  }

  if (msg.type === "JOB_ERROR") {
    const { platform, jobId, serverUrl, error } = msg;
    finaliseJob(serverUrl, jobId, "error", { error }).finally(() => {
      // De bewaker stond hier helemaal uit, zodat hij het tabblad niet zou
      // sluiten waar de verkoper nog in typt. Bijeffect: de controle "heeft hij
      // het zelf afgemaakt?" in fireJobWatchdog liep daardoor NOOIT meer — die
      // zit juist achter awaitingManualFinish en kan niets force-failen. Hem
      // opnieuw opwinden is dus veilig én nodig; sluiten doet hij daar niet.
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
            }, () => {
              // Zie hierboven: vanaf hier mag de bewaker alleen nog kijken of de
              // verkoper het zelf heeft afgemaakt.
              if ((meta.action || "create") === "create") armJobWatchdog(sender.tab.id);
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
  // Zet de extensieversie in ÉLKE foutmelding, niet alleen bij een onbekende
  // categorie. Een keer draaide er stilletjes een oudere versie terug en toen
  // leek een allang opgeloste fout weer terug te zijn — we hebben een ronde
  // verloren aan het uitzoeken welke versie er nu eigenlijk draaide.
  let tekst = String(error && error.message ? error.message : error);
  if (!/\[extensie /.test(tekst)) {
    try { tekst += ` [extensie ${chrome.runtime.getManifest().version}]`; } catch (_) {}
  }
  // Same reliability need as /complete: a dropped error report leaves the job
  // claimed until the stale-claim sweep guesses at what happened.
  await finaliseJob(serverUrl, jobId, "error", { error: tekst });
}
