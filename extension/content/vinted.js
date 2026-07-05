// Content script for vinted.com/items/new — uses the shared CL engine.
(async () => {
  const PLATFORM = "vinted";

  // Maps source-platform condition values (English keys, Dutch values) → Vinted English labels.
  // Marktplaats scale: zo goed als nieuw > goed > redelijk > beschadigd
  // Vinted scale: New with tags > New without tags > Very good > Good > Satisfactory
  const CONDITION_MAP = {
    // English/Marktplaats API keys
    "new": "New with tags",
    "good": "Very good",
    "fair": "Good",
    "poor": "Satisfactory",
    // Dutch Marktplaats condition labels
    "nieuw met label":   "New with tags",
    "nieuw met labels":  "New with tags",
    "nieuw zonder label":"New without tags",
    "nieuw zonder labels":"New without tags",
    "zo goed als nieuw": "Very good",
    "zeer goed":         "Very good",
    "goed":              "Good",
    "lichte gebruikssporen": "Good",
    "gedragen":          "Good",
    "redelijk":          "Satisfactory",
    "gebruikt":          "Satisfactory",
    "matig":             "Satisfactory",
    "beschadigd":        "Satisfactory",
    // Vinted English pass-through
    "new with tags":    "New with tags",
    "new without tags": "New without tags",
    "very good":        "Very good",
    "satisfactory":     "Satisfactory",
  };

  // Dutch → Vinted English colour names.
  const COLOUR_MAP = {
    "zwart":        "Black",
    "grijs":        "Grey",
    "wit":          "White",
    "crème":        "Cream",
    "creme":        "Cream",
    "beige":        "Beige",
    "abrikoos":     "Apricot",
    "oranje":       "Orange",
    "koraal":       "Coral",
    "koraalrood":   "Coral",
    "rood":         "Red",
    "bordeaux":     "Burgundy",
    "wijnrood":     "Burgundy",
    "roze":         "Pink",
    "rose":         "Rose",
    "paars":        "Purple",
    "lila":         "Lilac",
    "lichtblauw":   "Light blue",
    "blauw":        "Blue",
    "marine":       "Navy",
    "marineblauw":  "Navy",
    "donkerblauw":  "Navy",
    "turkoois":     "Turquoise",
    "turquoise":    "Turquoise",
    "mintgroen":    "Mint",
    "mint":         "Mint",
    "groen":        "Green",
    "donkergroen":  "Dark green",
    "khaki":        "Khaki",
    "bruin":        "Brown",
    "mosterd":      "Mustard",
    "geel":         "Yellow",
    "zilver":       "Silver",
    "goud":         "Gold",
    "multi":        "Multi",
    "veelkleurig":  "Multi",
    "transparant":  "Clear",
  };

  // Dutch → Vinted English material names.
  const MATERIAL_MAP = {
    "wol":           "Wool",
    "katoen":        "Cotton",
    "zijde":         "Silk",
    "linnen":        "Linen",
    "polyester":     "Polyester",
    "nylon":         "Nylon",
    "acryl":         "Acrylic",
    "viscose":       "Viscose",
    "elastaan":      "Elastane",
    "spandex":       "Spandex",
    "leer":          "Leather",
    "leder":         "Leather",
    "kunstleer":     "Faux leather",
    "suède":         "Suede",
    "suede":         "Suede",
    "velvet":        "Velvet",
    "fluweel":       "Velvet",
    "satijn":        "Satin",
    "denim":         "Denim",
    "spijkerstof":   "Denim",
    "canvas":        "Canvas",
    "ribfluweel":    "Corduroy",
    "corduroy":      "Corduroy",
    "jersey":        "Jersey",
    "fleece":        "Fleece",
    "kasjmier":      "Cashmere",
    "mohair":        "Mohair",
    "angora":        "Angora",
    "bamboe":        "Bamboo",
    "modal":         "Modal",
    "lyocell":       "Lyocell",
    "tencel":        "Tencel",
    "ramee":         "Ramie",
    "hennep":        "Hemp",
    "jute":          "Jute",
    "rubber":        "Rubber",
    "latex":         "Latex",
    "pvc":           "PVC",
    // English pass-through (Vinted labels)
    "wool":          "Wool",
    "cotton":        "Cotton",
    "silk":          "Silk",
    "linen":         "Linen",
    "leather":       "Leather",
    "suede":         "Suede",
    "cashmere":      "Cashmere",
    "denim":         "Denim",
    "polyester":     "Polyester",
    "nylon":         "Nylon",
    "acrylic":       "Acrylic",
    "viscose":       "Viscose",
    "elastane":      "Elastane",
    "fleece":        "Fleece",
    "velvet":        "Velvet",
    "satin":         "Satin",
    "canvas":        "Canvas",
    "corduroy":      "Corduroy",
    "jersey":        "Jersey",
    "mohair":        "Mohair",
    "angora":        "Angora",
    "bamboo":        "Bamboo",
    "modal":         "Modal",
    "lyocell":       "Lyocell",
    "tencel":        "Tencel",
    "hemp":          "Hemp",
  };

  // Dutch → English category hints. Vinted's UI is English; we use these terms to
  // match against the "Suggested" options Vinted generates from the title/description.
  const CAT_HINTS = {
    // ── Dames ──────────────────────────────────────────────────────
    "jeans":              ["jeans"],
    "broeken":            ["trousers", "pants", "chinos"],
    "shorts":             ["shorts"],
    "rokken":             ["skirts", "mini skirts", "midi skirts", "maxi skirts"],
    "jurken casual":      ["dresses", "casual dresses", "day dresses"],
    "jurken feest":       ["dresses", "evening dresses", "party dresses"],
    "blouses":            ["blouses", "tunics", "shirts"],
    "tops":               ["tops", "t-shirts"],
    "truien":             ["jumpers", "sweaters", "cardigans", "knitwear"],
    "hoodies":            ["hoodies", "sweatshirts"],
    "jassen":             ["coats", "jackets"],
    "sport bh":           ["sports bras", "sport tops"],
    "sportleggings":      ["leggings", "sports leggings"],
    "sportbroeken":       ["sports shorts", "sports trousers"],
    "sportjassen":        ["sports jackets", "windbreakers", "running jackets"],
    "yoga kleding":       ["yoga", "activewear", "leggings"],
    "hardloopkleding":    ["running", "running tops", "sports", "activewear"],
    "gymkleding":         ["activewear", "gym", "sports tops"],
    "zwemkleding":        ["swimwear", "bikinis", "swimsuits"],
    "ondergoed":          ["underwear", "lingerie"],
    "sneakers dames":     ["sneakers", "trainers", "sports shoes"],
    "schoenen dames":     ["shoes", "loafers", "flats", "boat shoes"],
    "hakken":             ["heels", "pumps", "high heels"],
    "laarzen dames":      ["boots", "ankle boots", "knee-high boots"],
    "sandalen":           ["sandals", "flip flops", "slippers"],
    "accessoires dames":  ["bags", "scarves", "jewellery", "accessories"],
    // ── Heren ──────────────────────────────────────────────────────
    "heren jeans":            ["jeans"],
    "heren chinos":           ["chinos", "trousers", "pants"],
    "heren shorts":           ["shorts"],
    "heren t-shirts":         ["t-shirts"],
    "heren polo's":           ["polo shirts", "polos"],
    "heren overhemden":       ["shirts"],
    "heren truien":           ["jumpers", "sweaters", "knitwear", "cardigans"],
    "heren hoodies":          ["hoodies", "sweatshirts"],
    "heren jassen":           ["coats", "jackets", "winter coats"],
    "heren pakken":           ["suits", "blazers"],
    "heren sport tops":       ["t-shirts", "sports tops", "activewear"],
    "heren sportbroeken":     ["sports trousers", "joggers", "tracksuit bottoms"],
    "heren sportjassen":      ["sports jackets", "tracksuits", "windbreakers"],
    "heren hardloopkleding":  ["running", "running tops", "sports"],
    "heren gymkleding":       ["activewear", "gym", "sports"],
    "heren voetbalkleding":   ["football", "sports", "jerseys"],
    "heren wielrenkleding":   ["cycling", "bike", "sports"],
    "heren zwembroeken":      ["swim shorts", "swimwear"],
    "heren ondergoed":        ["underwear", "socks"],
    "heren sneakers":         ["sneakers", "trainers", "sports shoes"],
    "heren schoenen":         ["shoes", "loafers", "boat shoes"],
    "heren formele schoenen": ["dress shoes", "oxford shoes", "formal shoes"],
    "heren laarzen":          ["boots", "ankle boots"],
    "heren accessoires":      ["belts", "scarves", "hats", "accessories"],
    // ── Kinderen ───────────────────────────────────────────────────
    "babykleding":            ["baby", "baby clothing", "newborn"],
    "peuterkleding":          ["toddler", "kids clothing"],
    "jongens kleding":        ["boys", "kids clothing", "boys clothes"],
    "meisjes kleding":        ["girls", "kids clothing", "girls clothes"],
    "tieners jongens":        ["boys", "teens", "teenage"],
    "tieners meisjes":        ["girls", "teens", "teenage"],
    "kinderen sportkleding":  ["kids sport", "children activewear"],
    "kinderen schoenen":      ["kids shoes", "children shoes", "boys shoes", "girls shoes"],
    "kinderen accessoires":   ["kids accessories", "children accessories"],
    // ── Unisex ─────────────────────────────────────────────────────
    "unisex truien":       ["jumpers", "hoodies", "sweaters"],
    "unisex jassen":       ["jackets", "coats"],
    "unisex sportkleding": ["activewear", "sports"],
    "unisex schoenen":     ["sneakers", "shoes", "trainers"],
    "unisex accessoires":  ["accessories", "scarves", "hats"],
    // ── Legacy keys (backwards compat for existing saved items) ────
    "schoenen":            ["shoes", "loafers", "sneakers", "trainers", "boots"],
    "truien / vesten":     ["jumpers", "cardigans", "knitwear"],
    "heren truien / vesten": ["jumpers", "sweaters", "cardigans", "knitwear"],
    "heren t-shirts / polo": ["t-shirts", "polo shirts"],
    "sportkleding":        ["activewear", "sports"],
    "heren sportkleding":  ["activewear", "sports"],
    "jassen | winter":     ["coats", "winter coats", "jackets"],
    "blouses en tunieken": ["blouses", "tunics", "shirts"],
    "polo's":              ["polo shirts", "polos"],
    "overhemden":          ["shirts"],
    "leggings":            ["leggings"],
    "badkleding":          ["swimwear", "swimsuits"],
    "heren broeken":       ["trousers", "pants", "chinos"],
    "heren pakken":        ["suits", "blazers"],
    "ondergoed":           ["underwear"],
    "heren ondergoed":     ["underwear", "socks"],
  };

  const { step, qs, sleep, waitForEl, fillInput, fillDescription, uploadPhotos, submitListing }
    = window.CL;

  const job = await getJob();
  if (!job) return;
  const { id: jobId, serverUrl, payload: item } = job;

  // Inputs we must NEVER clobber when filling dynamic attribute fields.
  const PROTECTED = [
    'input[data-testid="title--input"]',
    'textarea[data-testid="description--input"]',
    'input[data-testid="price-input--input"]',
    'input[data-testid="catalog-select-dropdown-input"]',
  ];
  const isProtected = (el) => !!el && PROTECTED.some((s) => el.matches?.(s));

  try {
    if (job.action === "delete") {
      await deleteListingVinted(item.platform_listing_id);
      send("JOB_DONE", {});
    } else if (job.action === "content_refresh") {
      await refreshListingVinted(item);
      send("JOB_DONE", {});
    } else {
      await fillForm(item);
      const id = await submitListing(/\/items\/(\d+)/);
      // Use the origin we actually ended up on (Vinted redirects to the
      // account's country domain), so the stored URL is the real one this
      // item lives on — critical for a later delete to hit the right domain.
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: `${location.origin}/items/${id}` });
    }
  } catch (e) {
    send("JOB_ERROR", null, String(e));
  }

  // Light in-place edit: nudge price and re-order photos, then save.
  // Does NOT touch title/description/category — this is a refresh, not a rewrite,
  // so it can't misrepresent the item and can't look like a duplicate listing.
  async function refreshListingVinted(item) {
    await waitForEl('input[data-testid="price-input--input"], input[data-testid="title--input"]', 20000);
    await sleep(500);
    const priceEl = qs('input[data-testid="price-input--input"]');
    if (!priceEl) throw new Error("Vinted edit: price field not found on the edit page");

    // Decide a VALID target price. Prefer the dashboard's (jittered) price, but
    // if that's missing/invalid fall back to whatever price the Vinted edit page
    // already shows — never write €0, which trips Vinted's ">= 1.0" validation.
    const pageNow = _num(priceEl.value);
    let target = Number(item.price);
    if (!(isFinite(target) && target >= 1)) target = (isFinite(pageNow) && pageNow >= 1) ? pageNow : NaN;
    if (!(isFinite(target) && target >= 1)) {
      throw new Error("Vinted refresh aborted: no valid price to set (dashboard price is missing and the listing shows €0). Set a price on the item first.");
    }

    // Nudge the price by the smallest sane amount if the target equals what's
    // already there, so the edit is a real change Vinted will accept/re-rank.
    if (isFinite(pageNow) && Math.abs(pageNow - target) < 0.01) {
      target = Math.round((target + 1) * 100) / 100;
    }

    const ok = await fillPriceVinted(target);
    if (!ok) throw new Error("Vinted refresh aborted: could not enter a valid price (the field stayed empty/€0 after typing).");

    // Save/update button — Vinted's edit page uses the same testid as create ("Save"/"Update").
    const saveBtn = [...document.querySelectorAll('button[data-testid], button')]
      .find(b => b.offsetParent !== null && /^(save|update|opslaan|bijwerken)$/i.test(b.textContent.trim()));
    if (!saveBtn) throw new Error("Vinted edit: save/update button not found");
    await sleep(300);
    saveBtn.click();

    // Verify the save actually went through instead of blindly reporting success.
    // Failure signals we watch for: the price field flips aria-invalid, a visible
    // validation/error message appears, or we simply stay on the edit form. A real
    // save either navigates away from the edit page or closes the price field.
    for (let i = 0; i < 12; i++) {
      await sleep(600);
      const stillEditing = qs('input[data-testid="price-input--input"]');
      if (!stillEditing) return; // navigated away → saved
      if (stillEditing.getAttribute("aria-invalid") === "true" || _num(stillEditing.value) < 1) {
        throw new Error("Vinted refresh: save was rejected — the price is invalid (Vinted requires €1.00 or more).");
      }
      const errText = [...document.querySelectorAll('[class*="validation"], [class*="Validation"], [role="alert"], [class*="error" i]')]
        .find(e => e.offsetParent !== null && /price must|greater than|at least|minimaal|moet (groter|ten minste)|ongeldig|invalid/i.test(e.textContent || ""));
      if (errText) {
        throw new Error("Vinted refresh: save was rejected — " + errText.textContent.trim().slice(0, 140));
      }
    }
    // Still on the edit form after ~7s with no visible error — treat as failure
    // rather than falsely reporting success (nothing verified as saved).
    throw new Error("Vinted refresh: clicked Save but the edit form never closed — the update could not be verified.");
  }

  // Find the seller's "Delete" control on the current page, trying several
  // layers of heuristics since Vinted's exact markup/testids drift over time
  // and we have no live DOM to pin an exact selector against. Returns the
  // clickable element, or null if nothing plausible was found.
  function findDeleteEntryPoint() {
    // Layer 1: a directly-visible "Delete" button/link on the page (some
    // Vinted layouts show Edit/Delete as direct buttons, no dropdown).
    let el = [...document.querySelectorAll('button, a, [role="menuitem"], [role="button"]')]
      .find(e => e.offsetParent !== null && (/^\s*delete\s*$/i.test(e.textContent) || e.dataset.testid?.includes("delete")));
    if (el) return el;

    // Layer 2: open a kebab/"..."/actions dropdown, then look inside it.
    const actionsBtn = document.querySelector(
      '[data-testid="item-actions-button"], [data-testid="item-menu-button"], ' +
      '[data-testid="item-page-actions-dropdown-button"], [data-testid*="kebab"], ' +
      'button[aria-label*="more" i], button[aria-label*="actions" i], button[aria-label*="options" i]'
    ) || [...document.querySelectorAll('button')].find(b =>
      b.offsetParent !== null && b.querySelector('svg') && !b.textContent.trim() &&
      /kebab|dots|more|menu/i.test(b.className + " " + (b.getAttribute("aria-label") || ""))
    );
    if (actionsBtn) return { __needsOpen: actionsBtn };
    return null;
  }

  // Discover the logged-in member id from the item page (you are the seller of
  // your own item). Needed for the wardrobe endpoint, which is the ONLY item
  // API we've confirmed works reliably on the country domain (the single-item
  // /api/v2/items/{id} endpoint 404s even for a live own-item, so we can't
  // trust it for verification).
  async function getVintedUserId() {
    let id = null;
    for (const a of document.querySelectorAll('a[href*="/member/"]')) {
      const m = (a.getAttribute("href") || "").match(/\/member\/(\d+)/);
      if (m) { id = m[1]; break; }
    }
    if (id) return id;
    // Fall back to opening the account menu, which exposes /member/{id}.
    document.querySelector('#user-menu-button, [data-testid="user-menu-button"]')?.click();
    await sleep(600);
    for (const a of document.querySelectorAll('a[href*="/member/"]')) {
      const m = (a.getAttribute("href") || "").match(/\/member\/(\d+)/);
      if (m) { id = m[1]; break; }
    }
    return id;
  }

  // Is this listing id currently present in the user's own wardrobe (i.e. still
  // live)? Returns true/false, or null if we couldn't read the wardrobe at all.
  async function isInWardrobe(userId, listingId) {
    try {
      const res = await fetch(`/api/v2/wardrobe/${userId}/items?order=newest_first&page=1&per_page=200`, { headers: { Accept: "application/json" } });
      if (!res.ok) return null;
      const data = await res.json();
      if (data.code && data.code !== 0) return null;
      return (data.items || []).some(it => String(it.id) === String(listingId));
    } catch (e) {
      return null;
    }
  }

  async function deleteListingVinted(listingId) {
    // We're on the item page on its real country origin (e.g. vinted.nl) —
    // getDeleteUrl now navigates to the stored listing URL, so location.origin
    // is the domain where this item AND the wardrobe API actually live.
    await waitForEl('[data-testid="item-details"], .item-details, main', 15000);
    await sleep(1000);

    // Establish ground truth BEFORE deleting: the item must be present in the
    // user's own wardrobe on this origin. If we can't confirm that, we refuse
    // to proceed rather than click blindly and risk a false success.
    const userId = await getVintedUserId();
    if (!userId) throw new Error("Could not determine your Vinted member id on " + location.origin + " — make sure you're logged into this Vinted account.");

    const presentBefore = await isInWardrobe(userId, listingId);
    if (presentBefore === null) throw new Error(`Could not read your Vinted wardrobe on ${location.origin} to verify item ${listingId} — aborting to avoid an unverified delete.`);
    if (presentBefore === false) throw new Error(`Vinted item ${listingId} is not in your wardrobe on ${location.origin} — it may already be gone or belong to a different account; nothing to delete.`);

    let entry = findDeleteEntryPoint();

    // Layer 3 fallback: the edit page is a confirmed-working URL (used by
    // content-refresh) and often carries its own "Delete listing" control
    // even when the view page's dropdown couldn't be located. Stay on the
    // SAME origin we're already on (do not hardcode vinted.com).
    if (!entry) {
      window.location.href = `${location.origin}/items/${listingId}/edit`;
      await waitForEl('input[data-testid="price-input--input"], input[data-testid="title--input"], main', 15000);
      await sleep(1000);
      entry = findDeleteEntryPoint();
    }

    if (!entry) throw new Error("Delete control not found on Vinted item/edit page for ID " + listingId + " — Vinted may have changed its page layout");

    let deleteEl;
    if (entry.__needsOpen) {
      entry.__needsOpen.click();
      await sleep(600);
      const menu = document.querySelector('[role="menu"], [role="listbox"], [data-testid*="dropdown"], [data-testid*="modal"]') || document;
      deleteEl = [...menu.querySelectorAll('button, a, [role="menuitem"]')]
        .find(el => /^\s*delete\s*$/i.test(el.textContent) || el.dataset.testid?.includes("delete"))
        || [...document.querySelectorAll('button, a, [role="menuitem"], [data-testid*="delete"]')]
          .find(el => /delete/i.test(el.textContent) || el.dataset.testid?.includes("delete"));
      if (!deleteEl) throw new Error("Delete option not found in Vinted actions menu for ID " + listingId);
    } else {
      deleteEl = entry;
    }
    deleteEl.click();
    await sleep(800);

    // Confirm in modal — required, not optional. Vinted's dialog button reads
    // "Confirm and delete" (multiple words), so match on containing confirm/
    // delete/remove/yes rather than an exact word — but never the Cancel button.
    // Prefer the dialog/modal scope so we don't grab an unrelated page button.
    const confirmScope = document.querySelector('[role="dialog"], [role="alertdialog"], [data-testid*="modal"], .ReactModal__Content') || document;
    const confirmBtn = [...confirmScope.querySelectorAll('button, a[role="button"]')]
      .find(el => {
        const t = el.textContent.trim();
        if (/annuleer|cancel|terug|back/i.test(t)) return false;
        return /confirm|delete|verwijder|remove|\byes\b|\bja\b/i.test(t) || el.dataset.testid?.includes("delete");
      });
    if (!confirmBtn) throw new Error("Confirm-delete button not found on Vinted for ID " + listingId + " — deletion was not confirmed");
    confirmBtn.click();
    await sleep(1500);

    // Verify the item is actually gone from the wardrobe before reporting
    // success — the same reliable endpoint we used for the pre-check. Wardrobe
    // can lag a moment after delete, so poll a few times.
    let goneAfter = false;
    for (let i = 0; i < 4; i++) {
      const present = await isInWardrobe(userId, listingId);
      if (present === false) { goneAfter = true; break; }
      if (present === null) throw new Error(`Could not re-read your Vinted wardrobe on ${location.origin} to confirm deletion of ${listingId}.`);
      await sleep(1500);
    }
    if (!goneAfter) throw new Error(`Vinted listing ${listingId} is still in your wardrobe after confirming delete — removal was not verified`);
  }

  function realClickEl(el) {
    if (!el) return;
    const r = el.getBoundingClientRect();
    const o = { bubbles: true, cancelable: true, view: window,
      clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
    for (const t of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      el.dispatchEvent(new (t.startsWith("pointer") ? PointerEvent : MouseEvent)(t, o));
    }
  }

  async function fillForm(item) {
    await waitForEl('input[data-testid="title--input"]', 20000);
    await step("title",       () => fillInput(qs('input[data-testid="title--input"]'), (item.title || "").slice(0, 100)));
    await step("description", () => fillDescription(['textarea[data-testid="description--input"]'], item.description));
    // Photos FIRST: Vinted generates the "Suggested" categories from the uploaded
    // images, so the suggestions don't exist until the photos finish loading.
    await step("photos",      () => item.photo_urls?.length && uploadPhotos(item.photo_urls.slice(0, 10), { jitter: true }));
    await sleep(1500); // let Vinted run image recognition and render the suggestions
    await step("category",    () => fillCategoryVinted(item));
    await sleep(500); // category drives which attribute fields (size/brand/condition) render
    await step("price",       () => fillPriceVinted(item.price));
    await step("condition",   () => fillAttributeVinted(["condition", "status"], CONDITION_MAP[(item.condition || "").toLowerCase()] || CONDITION_MAP["good"]));
    await step("size",        () => item.size && fillAttributeVinted(["size"], String(item.size)));
    await step("brand",       () => item.brand && fillAttributeVinted(["brand"], item.brand));
    await step("colour",      () => {
      const raw = (item.color || item.colour || item.colours || item.colors || "");
      if (!raw) return;
      const translated = COLOUR_MAP[raw.toLowerCase()] || raw;
      return fillAttributeVinted(["colour", "color", "colours", "colors"], translated);
    });
    // Colour accordion only commits when another attribute trigger is realClicked.
    // Always open the material trigger to commit the colour selection.
    await sleep(200);
    const matTriggerEl = qs('input[data-testid="category-material-multi-list-input"]');
    if (matTriggerEl) { realClickEl(matTriggerEl); await sleep(700); }
    if (item.material) {
      await step("material", () => fillMaterialFromOpenPanel(item.material));
    }
    // Close material panel.
    // Strategy: realClick the title input (outside the dropdown) to trigger click-outside dismissal.
    // This is unconditional — even if no material was set, the panel was opened to commit colour.
    await sleep(200);
    const titleInputEl = qs('input[data-testid="title--input"]');
    if (titleInputEl) {
      realClickEl(titleInputEl);
      await sleep(500);
    }
    // If panel still shows Cell__title items, try Escape.
    if (document.querySelector('[class*="web_ui__Cell__title"]')) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
      await sleep(400);
    }
    // Final fallback: toggle-click the trigger.
    if (document.querySelector('[class*="web_ui__Cell__title"]') && matTriggerEl) {
      realClickEl(matTriggerEl);
      await sleep(500);
    }

    // Final guard: re-assert title in case any attribute step touched it.
    const titleEl = qs('input[data-testid="title--input"]');
    const wantTitle = (item.title || "").slice(0, 100);
    if (titleEl && titleEl.value !== wantTitle) {
      fillInput(titleEl, wantTitle);
    }
  }

  // ---- PRICE: Vinted expects a plain number with a DOT (or no decimals). ----
  function fillPriceVinted(price) {
    const el = qs('input[data-testid="price-input--input"]');
    if (!el) return false;
    // Normalise to a clean numeric string: strip currency/spaces, comma→dot.
    let n = String(price ?? "").replace(/[^\d.,]/g, "").replace(",", ".");
    const num = parseFloat(n);
    if (!isFinite(num)) return false;
    // Fixed-2 if there are decimals, else integer — never a trailing comma.
    const out = Number.isInteger(num) ? String(num) : num.toFixed(2);
    return fillInput(el, out);
  }

  // ---- CATEGORY: prefer Vinted's own "Suggested" options, then verify the match. ----
  async function fillCategoryVinted(item) {
    const cat = (item.category || "").toLowerCase().trim();
    const gender = (item.gender || "").toLowerCase().trim(); // "heren"/"dames" if present
    const inp = qs('input[data-testid="catalog-select-dropdown-input"]');
    if (!inp) return false;

    const hints = (CAT_HINTS[gender ? `${gender} ${cat}` : cat] || CAT_HINTS[cat] || [])
      .map((h) => h.toLowerCase());
    // For relisted imports the category is captured straight from Vinted's own
    // breadcrumb (e.g. "Jumpers & sweaters"), which won't be in CAT_HINTS — use
    // that raw text as a hint so we can still filter the catalogue to it.
    if (!hints.length && cat) hints.push(cat);
    const wantMen = gender === "heren" || gender === "men";
    const wantWomen = gender === "dames" || gender === "women";

    inp.focus();
    inp.click();
    await sleep(700);

    const visible = (el) => !!el && (el.offsetParent !== null || el.getClientRects().length > 0);

    // Collect the suggested option rows. Vinted hides the native radio (custom-styled),
    // so we must NOT filter on radio visibility — we filter on the visible ROW instead.
    // Strategy A: every radio/role=radio → its clickable row. Strategy B (fallback):
    // find rows by their breadcrumb text ("Men > Shoes") when no radios are exposed.
    const rowSel = 'label, li, [role="option"], [role="radio"], [class*="Cell"], [class*="option"], [class*="Suggestion"]';
    const collectChoices = () => {
      const out = [];
      const seen = new Set();
      const push = (radio, row) => {
        if (!row || seen.has(row) || !visible(row)) return;
        const text = (row.textContent || "").toLowerCase();
        if (text.length <= 2 || text.length > 200) return;
        seen.add(row);
        out.push({ radio, row, text });
      };
      // A: anchored on radios (even if the input itself is visually hidden).
      for (const r of document.querySelectorAll('input[type="radio"], [role="radio"]')) {
        push(r.matches('input[type="radio"]') ? r : null, r.closest(rowSel) || r.parentElement);
      }
      // B: anchored on the breadcrumb subtitle inside Vinted's web_ui Cell component.
      // The breadcrumb lives in `.web_ui__Cell__body`; the clickable row is the
      // enclosing `.web_ui__Cell` and the (hidden) radio sits in its suffix.
      if (!out.length) {
        const bc = /\b(men|women|kids|unisex)\b\s*[>›\/]/i;
        const bodies = document.querySelectorAll(
          '[class*="Cell__body"], [class*="Cell__title"], [class*="Cell__heading"]');
        const pool = bodies.length ? bodies : document.querySelectorAll("div, li, label, span, button, a");
        for (const e of pool) {
          if (!bc.test(e.textContent || "")) continue;
          if ([...e.children].some((ch) => bc.test(ch.textContent || ""))) continue; // smallest match
          const row = e.closest('[class*="Cell__cell"], [class*="web_ui__Cell"]')
            || e.closest('label, li, [role="option"], [role="radio"]') || e;
          push(row.querySelector?.('input[type="radio"]') || null, row);
        }
      }
      return out;
    };

    // Score a choice on category hints (+3 each) and gender breadcrumb (+/-).
    const score = (c) => {
      const t = c.text;
      let s = 0;
      for (const h of hints) if (t.includes(h)) s += 3;
      const isMenRow = /\bmen\b/.test(t) && !/women/.test(t);
      const isWomenRow = /\bwomen\b/.test(t);
      if (wantMen) { if (isMenRow) s += 3; if (isWomenRow) s -= 5; }
      if (wantWomen) { if (isWomenRow) s += 3; if (isMenRow) s -= 5; }
      if (hints.length === 0 && /shoe|clothing|jacket|dress|jeans/.test(t)) s += 1;
      return s;
    };

    const realClick = realClickEl;

    const commit = async (c) => {
      // Vinted's custom radio reacts to a full pointer sequence on the row/label,
      // not to a bare .click() of the hidden input. Try row, label, then radio.
      const label = c.radio?.id ? document.querySelector(`label[for="${c.radio.id}"]`) : null;
      realClick(c.row);
      await sleep(150);
      if (c.radio && !c.radio.checked && label) { realClick(label); await sleep(150); }
      if (c.radio && !c.radio.checked) { c.radio.click(); await sleep(150); }
      await sleep(400);
      // Some flows need a leaf "Select"/confirm step.
      const confirm = [...document.querySelectorAll('button, [role="option"]')]
        .find((b) => b.offsetParent !== null && /^(select|kies|done|opslaan|save)$/i.test(b.textContent.trim()));
      if (confirm) { confirm.click(); await sleep(300); }
    };

    const best = (choices) => {
      const scored = choices.map((c) => ({ c, s: score(c) })).filter((x) => x.s > 0)
        .sort((a, b) => b.s - a.s);
      if (!scored.length) return null;
      // Ambiguity guard: if the top two tie AND gender is unknown, don't guess.
      if (scored.length > 1 && scored[0].s === scored[1].s && !wantMen && !wantWomen) {
        console.warn("[CrossList] Vinted category ambiguous (no gender on item):",
          scored[0].c.text, "vs", scored[1].c.text, "— set item.gender to disambiguate.");
        return null;
      }
      return scored[0].c;
    };

    // 1) Try the suggestions Vinted already shows — poll, they render async.
    let initial = [];
    const t1 = Date.now() + 8000; // image-recognition suggestions can take several seconds
    while (Date.now() < t1) {
      initial = collectChoices();
      if (initial.length) break;
      await sleep(250);
    }
    console.log("[CrossList] Vinted category — gender:", gender || "(none)", "hints:", hints,
      "| found", initial.length, "options:", initial.map((c) => c.text.slice(0, 50)));
    let choice = best(initial);

    // 2) Otherwise type each hint in turn to filter the catalogue until one
    //    surfaces a usable option (the captured-category hint is tried too).
    if (!choice && hints.length) {
      for (const h of hints) {
        fillInput(inp, h);
        const deadline = Date.now() + 3500;
        while (Date.now() < deadline && !choice) {
          await sleep(250);
          choice = best(collectChoices());
        }
        if (choice) break;
      }
    }

    if (choice) {
      await commit(choice);
      return verifyCategory(hints, wantWomen);
    }
    return false;
  }

  // Confirm the committed category text actually reflects our item; warn if not.
  function verifyCategory(hints, wantWomen) {
    const display = (qs('input[data-testid="catalog-select-dropdown-input"]')?.value
      || document.querySelector('[data-testid="catalog-select-dropdown"]')?.textContent
      || "").toLowerCase();
    if (!display) return false;
    const hintOk = hints.length === 0 || hints.some((h) => display.includes(h));
    if (!hintOk) console.warn("[CrossList] Vinted category may not match item:", display, "expected one of", hints);
    return hintOk;
  }

  // Like fillAttributeVinted but skips opening the trigger (panel already open).
  async function fillMaterialFromOpenPanel(value) {
    if (!value) return false;
    const translated = MATERIAL_MAP[value.toLowerCase().trim()] || value;
    const w = translated.toLowerCase().trim();

    // Poll up to 2s for the panel list items to appear.
    let titleEls = [];
    for (let i = 0; i < 20; i++) {
      // Query ALL title elements — no offsetParent filter (items may be scrolled out of view).
      titleEls = [...document.querySelectorAll('[class*="web_ui__Cell__title"]')];
      if (titleEls.length > 0) break;
      await sleep(100);
    }
    if (!titleEls.length) { console.warn("[CrossList] material panel: no items found"); return false; }

    // Exact match first, then partial.
    let best = titleEls.find(e => e.textContent.trim().toLowerCase() === w);
    if (!best) best = titleEls.find(e => e.textContent.trim().toLowerCase().includes(w));
    if (!best) best = titleEls.find(e => w.includes(e.textContent.trim().toLowerCase()) && e.textContent.trim().length > 2);
    if (!best) { console.warn("[CrossList] Vinted material not found:", value, "→", translated); return false; }

    // Scroll the item into view within the dropdown container, then realClick it.
    best.scrollIntoView({ block: "nearest" });
    await sleep(200);
    const cell = best.closest('[class*="web_ui__Cell__cell"]') || best.parentElement || best;
    realClickEl(cell);
    await sleep(500);
    console.log("[CrossList] material selected:", translated);
    return true;
  }

  // ---- Generic attribute filler (condition/size/brand/colour/material).
  // Trigger inputs (readonly c-input__value) open panels when clicked.
  // - Condition/colour/material: options in web_ui__Cell__title elements.
  // - Size: options in filter-grid__option elements (grid layout).
  // - Brand: trigger is a TOGGLE — only click if search panel is currently closed.
  //   Brand search input is always inside the same container; type to filter, then pick. ----
  async function fillAttributeVinted(fieldKeys, value) {
    if (!value) return false;

    const ATTR_FIELD_MAP = {
      condition: "category-condition-single-list-input",
      status:    "category-condition-single-list-input",
      size:      "category-size-single-grid-input",
      brand:     "brand-select-dropdown-input",
      colour:    "color-select-dropdown-input",
      color:     "color-select-dropdown-input",
      colours:   "color-select-dropdown-input",
      colors:    "color-select-dropdown-input",
      material:  "category-material-multi-list-input",
    };

    const keys = fieldKeys.map(k => k.toLowerCase());
    const isBrand = keys.includes("brand");
    const isSize  = keys.includes("size");

    // Poll up to 3 s for the trigger input to render.
    let triggerEl = null;
    const tDeadline = Date.now() + 3000;
    while (!triggerEl && Date.now() < tDeadline) {
      for (const key of keys) {
        const testId = ATTR_FIELD_MAP[key];
        if (testId) {
          const el = document.querySelector(`input[data-testid="${testId}"]`);
          if (el && el.offsetParent) { triggerEl = el; break; }
        }
      }
      if (!triggerEl) await sleep(250);
    }
    if (!triggerEl) {
      console.warn("[CrossList] Vinted attr not found:", fieldKeys);
      return false;
    }

    if (isBrand) {
      // Brand panel is a toggle: only click trigger if search input is NOT visible.
      const bs = document.querySelector('input[data-testid="brand-search--input"]');
      if (!bs || !bs.offsetParent) {
        realClickEl(triggerEl);
        await sleep(900);
      }
      const brandSearch = document.querySelector('input[data-testid="brand-search--input"]');
      if (brandSearch && brandSearch.offsetParent) {
        fillInput(brandSearch, value);
        await sleep(1000);
      }
    } else {
      // All other fields: click trigger to open panel.
      realClickEl(triggerEl);
      await sleep(900);
    }

    const lv = value.toLowerCase();

    if (isSize) {
      // filter-grid__option (singular) = individual option DIV; filter-grid__options (plural) = container UL.
      // Use :not to exclude the container so we only get clickable leaf options.
      const opts = [...document.querySelectorAll('div[class*="filter-grid__option"]:not([class*="filter-grid__options"])')]
        .filter(e => e.offsetParent);
      // Normalise: strip "EU ", "eu " prefix so "EU 42" → "42"
      const normSize = lv.replace(/^eu\s*/i, "").trim();
      const match =
        opts.find(e => e.textContent?.trim().toLowerCase() === normSize) ||
        opts.find(e => e.textContent?.trim().toLowerCase() === lv) ||
        opts.find(e => e.textContent?.trim().toLowerCase().startsWith(normSize));
      if (!match) {
        console.warn("[CrossList] Vinted size option not found:", value, "| available:", opts.slice(0,10).map(e=>e.textContent.trim()));
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        return false;
      }
      realClickEl(match);
      await sleep(500);
      return true;
    }

    // Condition / colour / material / brand: options in web_ui__Cell__title.
    // Scope to the currently-open panel via closest ancestor with a "content" or "overlay" class,
    // or fall back to all visible titles.
    const allTitles = [...document.querySelectorAll('[class*="web_ui__Cell__title"]')]
      .filter(e => e.offsetParent);

    // Fuzzy scorer: exact → startsWith → includes → word-overlap
    const fuzzyScore = (text, want) => {
      const t = text.toLowerCase().trim();
      const w = want.toLowerCase().trim();
      if (t === w) return 4;
      if (t.startsWith(w) || w.startsWith(t)) return 3;
      if (t.includes(w) || w.includes(t)) return 2;
      // Word-overlap score
      const tw = new Set(t.split(/\s+/));
      const ww = w.split(/\s+/);
      const hits = ww.filter(word => tw.has(word) || [...tw].some(tt => tt.includes(word))).length;
      return hits > 0 ? hits / ww.length : 0;
    };

    let best = null, bestScore = 0;
    for (const el of allTitles) {
      const s = fuzzyScore(el.textContent, value);
      if (s > bestScore) { best = el; bestScore = s; }
    }

    if (!best || bestScore === 0) {
      console.warn("[CrossList] Vinted attr option not found:", fieldKeys, value);
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return false;
    }

    console.log(`[CrossList] Vinted attr "${fieldKeys}" matched "${best.textContent.trim()}" (score ${bestScore}) for value "${value}"`);
    const cell = best.closest('[class*="web_ui__Cell__cell"]') || best;

    // Colour uses checkboxes (multi-select), condition/material use radios (single-select).
    // Clicking the outer div does NOT trigger React's checkbox/radio handler — click the input directly.
    const inputInCell = cell.querySelector('input[type="checkbox"], input[type="radio"]');
    if (inputInCell) {
      inputInCell.click();
    } else {
      realClickEl(cell);
    }
    await sleep(400);
    // Do NOT send Escape here — Escape reverts colour checkboxes. The value is already
    // committed to React state the moment the checkbox/radio is clicked. Inline accordion
    // panels can stay open; the next step opening its own panel causes no interference
    // because each field's fuzzy search is value-specific enough to avoid cross-panel hits.
    return true;
  }

  function getJob() {
    return new Promise((r) => chrome.storage.local.get(`job_${PLATFORM}`, (s) => r(s[`job_${PLATFORM}`] || null)));
  }
  function send(type, result, errorMsg) {
    chrome.runtime.sendMessage({ type, platform: PLATFORM, jobId, serverUrl, result, error: errorMsg });
  }
})();
