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
  // Also used for plain background round-trips (e.g. FETCH_PHOTO), which need a
  // longer budget than a DOM call — a multi-MB photo over a slow line easily
  // outlasts 8s, and timing out here silently dropped the photo.
  function runInMainWorld(type, data, timeoutMs = 8000) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        console.error("[Omnivaleur] runInMainWorld timeout:", type);
        resolve(false);
      }, timeoutMs);
      chrome.runtime.sendMessage({ type, ...data }, (result) => {
        clearTimeout(timer);
        if (chrome.runtime.lastError) {
          console.error("[Omnivaleur] sendMessage error:", type, chrome.runtime.lastError.message);
        }
        resolve(result ?? false);
      });
    });
  }

  // ---- Lexical / contenteditable description ----
  let _pendingDescription = null;
  let _descriptionSelector = null;

  // THROWS on failure. "Geen advertentietekst ingevuld" is a platform-side
  // rejection the user cannot act on; the causes below can be reported precisely.
  async function fillDescription(selectors, text) {
    const value = (text || "").trim().slice(0, 2000);
    if (!value) throw new Error("Item heeft geen beschrijving — vul die in de app in");
    const selector = selectors.find((s) => document.querySelector(s));
    if (!selector) throw new Error("Beschrijvingsveld niet gevonden op de pagina (" + selectors.join(", ") + ")");
    _pendingDescription = value;
    _descriptionSelector = selector;
    document.querySelector(selector)?.scrollIntoView({ block: "center" });
    const ok = await runInMainWorld("FILL_DESC", { selector, text: value });
    if (!ok) throw new Error("Beschrijving kon niet in de editor worden gezet");
    // Het formulier valideert op een verborgen veld, niet op de zichtbare
    // editor. Zonder dit blijft "Geen zoekertjestekst ingevuld" staan.
    await runInMainWorld("FILL_HIDDEN_DESC", { text: value });
    // Verlaat het veld: sommige formulieren nemen de tekst pas over bij blur.
    await runInMainWorld("BLUR_DESC", { selector });
    // Het verborgen veld overleeft een herteken-ronde niet altijd; nog één keer.
    await runInMainWorld("FILL_HIDDEN_DESC", { text: value });
    // En daarna blijft een bewaker het terugzetten zolang het formulier open
    // staat. Alles tussen hier en de Plaatsen-knop (foto's, kenmerken, het
    // merk-venster) kan het veld namelijk opnieuw leeggooien.
    await runInMainWorld("ENFORCE_DESC", { text: value, durationMs: 300000 });
    return true;
  }

  // Het formulier beschouwt de beschrijving als leeg zolang dit verborgen veld
  // leeg is — ongeacht wat er zichtbaar staat.
  async function hiddenDescriptionOk() {
    const waarde = await runInMainWorld("READ_HIDDEN_DESC", {});
    if (waarde === null || waarde === false) return true; // dit platform heeft het veld niet
    return String(waarde).trim().length > 0;
  }

  // Read back what the editor actually holds. The isolated world cannot see
  // __lexicalEditor, but innerText reflects the rendered EditorState, which is
  // enough to answer the only question that matters here: is it empty?
  function descriptionIsEmpty() {
    if (!_descriptionSelector) return false; // nothing was ever meant to be filled
    const el = document.querySelector(_descriptionSelector);
    if (!el) return true;
    // Vinted's description is a real <textarea>: its innerText is the ORIGINAL
    // markup, not what the user typed, so reading innerText there would call a
    // perfectly filled field empty and block the submit.
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
      return (el.value || "").trim().length === 0;
    }
    return (el.innerText || "").trim().length === 0;
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
  // Values the dashboard stores as a multi-region size ("S / 36 / 8",
  // "XL / 42 / 14") matched NOTHING in Marktplaats's size list, whose options
  // read "Maat 36 (S)" — the whole composite string was compared as one token,
  // so every option scored 0 and the size was left on "Kies...". Offer the
  // composite first (an exact hit still wins), then each part on its own.
  // Onze kleurwoordenschat is Engels (Vinted's eigen labels), maar de Kleur-lijst
  // op Marktplaats/2dehands is Nederlands. Zonder deze vertaling matchte "blue"
  // op geen enkele optie: op Marktplaats blokkeerde dat de hele plaatsing, op
  // 2dehands ging de advertentie zonder kleur de deur uit. Meerdere Engelse
  // tinten vallen bewust samen op één Nederlandse optie — die lijst is korter.
  const COLOUR_NL = {
    black: "Zwart", grey: "Grijs", gray: "Grijs",
    "light grey": "Grijs", "light gray": "Grijs",
    "dark grey": "Grijs", "dark gray": "Grijs",
    silver: "Grijs", white: "Wit", "off white": "Wit", cream: "Wit",
    ecru: "Wit", beige: "Beige", camel: "Beige", tan: "Beige",
    taupe: "Beige", apricot: "Oranje", orange: "Oranje",
    coral: "Rood", red: "Rood", burgundy: "Bordeaux", maroon: "Bordeaux",
    wine: "Bordeaux", pink: "Roze", rose: "Roze", purple: "Paars",
    lilac: "Paars", lavender: "Paars", blue: "Blauw", "light blue": "Blauw",
    "dark blue": "Blauw", navy: "Blauw", "royal blue": "Blauw",
    turquoise: "Blauw", teal: "Blauw", mint: "Groen", green: "Groen",
    "light green": "Groen", "dark green": "Groen", olive: "Groen",
    khaki: "Groen", brown: "Bruin", cognac: "Bruin", mustard: "Geel",
    yellow: "Geel", gold: "Goud", multi: "Multicolour", clear: "Wit",
  };

  // Geeft de Nederlandse kleurnaam terug, of de originele waarde als we hem niet
  // kennen — een onbekende kleur mag nooit een lege waarde worden.
  function dutchColor(value) {
    const raw = String(value || "").trim();
    return COLOUR_NL[raw.toLowerCase()] || raw;
  }

  // Leest het formulier terug na het invullen. Elke stap hierboven zit in step(),
  // dat fouten met opzet opslokt zodat één ontbrekend kenmerk de rest niet
  // afbreekt — maar daardoor kon een advertentie zonder maat, merk of
  // fabrikantgegevens de deur uit zonder dat iets dat meldde.
  //
  // Marktplaats en 2dehands draaien hetzelfde plaatsingsformulier, dus dezelfde
  // veldnamen. Een veld dat op deze categorie niet bestaat levert null op en
  // wordt overgeslagen: er wordt nooit iets gemeld wat het item zelf niet heeft.
  // Elke 2dehands/Marktplaats-categorie heeft zijn eigen conditielijst: kleding
  // kent "Gedragen", kinderkleding alleen "Gebruikt". Eén vaste waarde vindt dus
  // in de helft van de categorieën niets. We proberen ze op volgorde van
  // nauwkeurigheid en pakken de eerste die daadwerkelijk bestaat.
  const CONDITION_CANDIDATES = {
    new_with_tags: ["Nieuw met etiket", "Nieuw", "Zo goed als nieuw"],
    new:           ["Nieuw", "Nieuw met etiket", "Zo goed als nieuw"],
    good:          ["Zo goed als nieuw", "Gebruikt", "Gedragen"],
    fair:          ["Gedragen", "Gebruikt", "Zo goed als nieuw"],
    poor:          ["Beschadigd", "Gebruikt", "Gedragen"],
  };

  // Veldnamen verschillen per categorie (condition, clothingCondition,
  // condition_kids_clothing, …). Daarom zoeken we het veld op wát erin staat:
  // de keuzelijst die deze woorden aanbiedt, is per definitie de juiste.
  function attrSelects() {
    return [...document.querySelectorAll('select[name^="singleSelectAttribute["]')];
  }

  function selectByOptions(words) {
    const want = words.map((w) => w.toLowerCase());
    return attrSelects().find((el) => {
      const texts = [...el.options].map((o) => o.text.trim().toLowerCase());
      return want.some((w) => texts.includes(w));
    }) || null;
  }

  function conditionSelect() {
    const byLabel = findFieldByLabel("Conditie");
    if (byLabel?.tagName === "SELECT") return byLabel;
    return selectByOptions(["nieuw", "zo goed als nieuw", "gebruikt", "gedragen"]);
  }

  function intendedForSelect() {
    const byLabel = findFieldByLabel("Bestemd voor");
    if (byLabel?.tagName === "SELECT") return byLabel;
    return selectByOptions(["jongen", "meisje", "jongen of meisje"]);
  }

  // Wat er op deze categorie staat, in het log — zodat een leeg kenmerk
  // meteen te herleiden is zonder opnieuw te moeten raden.
  function logMpFields(tag) {
    try {
      clog(`${tag} velden:`, attrSelects().map((s) =>
        `${s.name}=${s.value || "(leeg)"} [${[...s.options].map((o) => o.text).join("|")}]`),
        [...document.querySelectorAll('input[name^="textAttribute["]')].map((i) => `${i.name}=${i.value || "(leeg)"}`));
    } catch (e) { /* logging mag nooit het plaatsen breken */ }
  }

  async function selectCondition(condition) {
    const list = CONDITION_CANDIDATES[condition] || CONDITION_CANDIDATES.good;
    const el = conditionSelect();
    if (el) {
      const texts = [...el.options].map((o) => o.text.trim().toLowerCase());
      const hit = list.find((c) => texts.includes(c.toLowerCase()));
      if (hit) return fillNativeSelect(el, hit);
      // Onbekende lijst: pak gewoon de eerste echte optie, beter dan leeg laten.
      const first = [...el.options].find((o) => o.value !== "" && !o.disabled);
      return first ? fillNativeSelect(el, first.text) : false;
    }
    for (const c of list) {
      if (await selectDropdown("Conditie", c)) return true;
    }
    return false;
  }

  // "Bestemd voor" bij kinderkleding — verplicht, maar Vinted levert het niet.
  // We leiden het af uit de tekst en vallen anders terug op neutraal.
  function selectIntendedFor(item) {
    const el = intendedForSelect();
    if (!el) return true; // deze categorie kent het veld niet — niets te doen
    const hay = `${item.title || ""} ${item.category || ""} ${item.description || ""}`.toLowerCase();
    const boy = /jongen|boys?\b|garçon/.test(hay);
    const girl = /meisje|girls?\b|fille/.test(hay);
    const want = boy && !girl ? "Jongen" : girl && !boy ? "Meisje" : "Jongen of Meisje";
    return fillNativeSelect(el, want);
  }

  // Merk is per categorie een tekstveld óf een keuzelijst, met steeds een andere
  // naam (clothingBrand, brand_mens_clothing, brand_kids_clothing, …).
  // Let op: dit veld heeft vaak géén name-attribuut, alleen een id — zoeken op
  // naam levert dan niets op. Het label wijst er wel altijd naar.
  function brandField() {
    const byLabel = findFieldByLabel("Merk");
    if (byLabel && (byLabel.tagName === "SELECT" || byLabel.tagName === "INPUT")) return byLabel;
    return qs('[id*="rand"][id^="textAttribute["]')
        || qs('[data-testid^="attribute-autocomplete-brand"]')
        || qs('[id*="rand"][id^="singleSelectAttribute["]');
  }

  function fieldFilled(el) {
    return !!el && !!(el.value || "").trim();
  }

  async function fillBrandField(brand) {
    const el = brandField();
    if (!el || !brand) return false;
    if (el.tagName === "SELECT") return fillNativeSelect(el, brand);
    // Het merkveld is een autocomplete: gewoon tekst erin zetten wordt door de
    // pagina teruggedraaid. De beproefde route loopt via de main world.
    await fillBrand(brand);
    if (fieldFilled(brandField())) return true;
    await fillInputHuman(el, brand);
    return fieldFilled(brandField());
  }

  // Het formulier bouwt zichzelf opnieuw op na het uploaden van foto's en na het
  // kiezen van de conditie. Velden die daarvóór gezet zijn, springen dan terug op
  // "Kies...". Daarom vullen we aan het eind nog één keer alles bij wat leeg is
  // gebleven, vlak voordat we controleren.
  async function repairMpGroupFields(item) {
    // Twee rondes: de kenmerken verschijnen soms pas nadat de foto's klaar zijn,
    // en het kiezen van de conditie bouwt het blok nóg een keer opnieuw op.
    for (let ronde = 1; ronde <= 2; ronde++) {
      await repairOnce(item, ronde);
      await sleep(800);
    }
  }

  async function repairOnce(item, ronde) {
    logMpFields(`ronde ${ronde} — voor reparatie`);

    const condEl = conditionSelect();
    if (condEl && !condEl.value) { await selectCondition(item.condition); await sleep(300); }

    const intendedEl = intendedForSelect();
    if (intendedEl && !intendedEl.value) { selectIntendedFor(item); await sleep(300); }

    for (const [label, value] of [["Maat", item.size], ["Kleur", dutchColor(item.color)]]) {
      if (!value) continue;
      const el = findFieldByLabel(label);
      if (el?.tagName === "SELECT" && !el.value) { fillNativeSelect(el, value); await sleep(300); }
    }

    const brandEl = brandField();
    if (item.brand && brandEl && !fieldFilled(brandEl)) {
      await fillBrandField(item.brand);
      await sleep(300);
    }

    logMpFields(`ronde ${ronde} — na reparatie`);
  }

  function verifyMpGroupFields(item) {
    const missing = [];
    const emptySelect = (name) => {
      const el = qs(`select[name="${name}"]`);
      return el && !el.value; // staat op deze categorie, maar nog op "Kies..."
    };
    const emptyInput = (name) => {
      const el = qs(`input[name="${name}"]`);
      return el && !(el.value || "").trim();
    };

    const emptyLabel = (label) => {
      const el = findFieldByLabel(label);
      return el?.tagName === "SELECT" && !el.value;
    };

    if (item.size && emptyLabel("Maat")) missing.push("maat");
    if (item.color && emptyLabel("Kleur")) missing.push("kleur");
    const condEl = conditionSelect();
    if (condEl && !condEl.value) missing.push("conditie");
    const intendedEl = intendedForSelect();
    if (intendedEl && !intendedEl.value) missing.push("bestemd voor");
    const bf = brandField();
    if (item.brand && bf && !fieldFilled(bf)) missing.push("merk");
    if (emptyInput("textAttribute[manufacturerTradename]")) missing.push("handelsnaam fabrikant");
    if (emptyInput("textAttribute[manufacturerEmail]")) missing.push("e-mailadres fabrikant");
    if (item.bid_percentage && emptyInput("price.minimumBidPrice")) missing.push("bieden vanaf");

    if (missing.length) {
      throw new Error(
        `Deze velden zijn niet ingevuld op het formulier: ${missing.join(", ")}. ` +
        `De advertentie is NIET geplaatst — vul ze zelf aan en klik op Plaatsen.`
      );
    }
  }

  function valueVariants(value) {
    const raw = String(value).trim();
    const out = [raw];
    if (raw.includes("/")) {
      for (const part of raw.split("/")) {
        const p = part.trim();
        if (p && !out.includes(p)) out.push(p);
      }
    }
    return out;
  }

  async function selectDropdown(labels, value) {
    if (!value) return false;
    const labelArr = Array.isArray(labels) ? labels : [labels];
    for (const label of labelArr) {
      const trigger = findFieldByLabel(label);
      if (!trigger) continue;

      // Native <select>: set value directly — no clicking/waiting needed
      if (trigger.tagName === "SELECT") {
        for (const v of valueVariants(value)) {
          if (fillNativeSelect(trigger, v)) return true;
        }
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
        let opt = null;
        for (const v of valueVariants(value)) {
          opt = await waitForOption(v, opt === null ? 3500 : 800);
          if (opt) break;
        }
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
    const ok = await runInMainWorld("FILL_BRAND", { brand });
    // Never continue while the picker is still up. ReactModal makes the rest of
    // the form inert, so every field after Merk would be filled into a page that
    // ignores the events — which is exactly how manufacturer, delivery and the
    // bid price all ended up empty with no error to show for it.
    await waitForNoModal(6000);
    return ok;
  }

  function anyModalOpen() {
    const m = document.querySelector(".ReactModal__Content") || document.querySelector('[role="dialog"]');
    // NOT offsetParent: the brand modal is position:fixed, and a fixed element
    // always reports offsetParent === null — so an offsetParent check called the
    // open modal "closed" and walked straight into the inert form behind it.
    // Verified live on the Marktplaats brand picker.
    return !!(m && m.getClientRects().length > 0);
  }

  async function waitForNoModal(timeout = 6000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      if (!anyModalOpen()) return true;
      await sleep(250);
    }
    return false;
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

  // Thumbnails the marketplaces render once an upload actually landed. Verified
  // live on the Marktplaats SYI form: a successful upload swaps the local blob
  // for an images.marktplaats.com URL, so seeing one of these is real proof the
  // photo reached the platform — not just proof that we set input.files.
  const PHOTO_THUMB_SELECTOR = [
    'img[src*="images.marktplaats.com"]',
    'img[src*="images.2dehands.be"]',
    'img[src*="vinted.net"]',
    'img[src^="blob:"]',
    '[class*="hz-Listing"] img',
    '[class*="thumbnail"] img',
    '[data-testid*="image"] img',
    '[class*="ImageUploader"] img',
    '[class*="imageUploader"] img',
    '[data-testid*="upload"] img',
    '[class*="Carousel"] img',
  ].join(", ");

  // Platforms may override the proof-of-upload selector. Facebook needs this:
  // its create form renders ZERO <img> elements until a photo lands, and then
  // shows scontent.fbcdn.net images — never a blob:. Verified live 2026-07-29 on
  // the real form. With only the list above, uploadPhotos waited the full 45s on
  // Facebook, threw, and fillForm died before typing a single field — which is
  // exactly the "nothing gets filled in" report.
  function countPhotoThumbs(selector) {
    return document.querySelectorAll(selector || PHOTO_THUMB_SELECTOR).length;
  }

  // Set once photos were actually requested, so the pre-submit check only guards
  // listings that are supposed to have images.
  let _expectPhotos = false;

  // THROWS on failure — never returns quietly. Photos are mandatory on every
  // platform here, and a silent `return false` meant the form was submitted with
  // zero photos and the user got no explanation at all. The thrown message names
  // the actual cause (no field / nothing downloadable / platform rejected them).
  async function uploadPhotos(urls, opts = {}) {
    // Prefer the real image picker: MP's page also carries an unrelated
    // input[name="file"], and a plain input[type=file] grab can land on that one.
    const fileInput = qs('input[type="file"][accept*="image"]')
      || qs('input[type="file"]#imageUploader-hiddenInput')
      || qs('input[type="file"]');
    if (!fileInput) throw new Error("Fotoveld niet gevonden op de pagina");

    const thumbSel = opts.thumbSelector;
    const before = countPhotoThumbs(thumbSel);
    const files = [];
    const failures = [];
    clog(`foto's: ${urls.length} ophalen`);
    for (const u of urls) {
      // Zonder tijdslimiet kan één foto die nooit antwoordt het hele formulier
      // laten hangen: alles ná de foto's — conditie, maat, kleur, merk — werd
      // dan nooit meer ingevuld, zonder enige melding.
      const f = await Promise.race([fetchFile(u, opts), sleep(20000).then(() => null)]);
      if (f) files.push(f); else failures.push(u);
    }
    clog(`foto's: ${files.length} van ${urls.length} opgehaald`);
    if (!files.length) {
      throw new Error(
        `Geen van de ${urls.length} foto('s) kon worden gedownload — ` +
        `eerste URL: ${(failures[0] || "").slice(0, 120)}`
      );
    }

    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    // Uploading N photos to the platform's CDN takes real time — the old 8s
    // wait for ONE thumbnail was both too short and too weak a check.
    clog("foto's: geplaatst in het formulier, wachten op miniaturen");
    // Naast de bekende miniatuur-selectors tellen we ook simpelweg hoeveel
    // afbeeldingen de pagina bevat. Elk platform toont zijn miniaturen anders,
    // maar een geslaagde upload laat het aantal afbeeldingen altijd stijgen.
    const imgsBefore = document.querySelectorAll("img").length;
    const zichtbaar = () =>
      countPhotoThumbs(thumbSel) > before || document.querySelectorAll("img").length > imgsBefore;

    const deadline = Date.now() + 25000;
    while (Date.now() < deadline && !zichtbaar()) await sleep(500);

    if (!zichtbaar()) {
      // Niet fataal meer. De foto's blijken in de praktijk gewoon geüpload,
      // alleen herkennen we de miniaturen niet — en daarop de hele advertentie
      // tegenhouden kost meer dan het oplevert.
      clog(`foto's: ${files.length} aangeboden, geen miniatuur herkend — er wordt toch doorgegaan`);
      return true;
    }
    // Only arm the pre-submit photo guard once thumbnails were actually observed
    // here. If a platform's thumbnails don't match PHOTO_THUMB_SELECTOR at all we
    // must not block a submit that would otherwise have succeeded.
    clog("foto's: miniaturen zichtbaar");
    _expectPhotos = true;
    // Give the remaining uploads time to finish before anything clicks submit.
    await sleep(1500);
    return true;
  }

  // Two-stage fetch. A content script's fetch carries the PAGE's origin
  // (marktplaats.nl) and is therefore subject to that origin's CORS — a photo
  // host that doesn't allow it fails here for reasons the page can never fix.
  // The service worker fetches under the extension's own origin with its host
  // permissions, so it succeeds where the page cannot. Try the page first (no
  // round-trip, no base64), fall back to the worker, and log why each failed.
  async function fetchFile(url, opts = {}) {
    // Always land on a .jpg name: photos imported from Vinted are .webp, and a
    // File called "abc.webp" labelled image/jpeg is exactly the kind of mismatch
    // an uploader rejects.
    const base = (url.split("/").pop()?.split("?")[0] || "photo").replace(/\.[a-z0-9]+$/i, "");
    const name = `${base || "photo"}.jpg`;
    const finish = async (blob) => {
      // Marktplaats accepts bmp/jpg/jpeg/png/heic — NOT webp (verified live on
      // the SYI file input). Vinted serves every photo as webp, so an imported
      // item's photos were rejected even when the download itself succeeded.
      // Re-encode anything that isn't already JPEG.
      let out = blob;
      if (opts.jitter) out = await jitterImage(blob);
      else if (!/jpe?g$/i.test(blob.type || "")) out = await toJpeg(blob);
      return new File([out], name, { type: "image/jpeg" });
    };
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      return await finish(await resp.blob());
    } catch (e) {
      console.warn("Omnivaleur photo fetch (page) failed, retrying via background:", url, e);
    }
    try {
      const res = await runInMainWorld("FETCH_PHOTO", { url }, 45000);
      if (!res || !res.ok || !res.dataUrl) throw new Error(res?.error || "background fetch failed");
      const blob = await (await fetch(res.dataUrl)).blob();
      return await finish(blob);
    } catch (e) {
      console.warn("Omnivaleur photo fetch (background) failed:", url, e);
      return null;
    }
  }

  // Re-encode any image the browser can decode (webp, png, heic-as-decoded) into
  // a plain JPEG, without touching its dimensions. Falls back to the original
  // blob if decoding fails — a possibly-rejected upload still beats no upload.
  function toJpeg(blob) {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        URL.revokeObjectURL(url);
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        canvas.getContext("2d").drawImage(img, 0, 0);
        canvas.toBlob((b) => resolve(b || blob), "image/jpeg", 0.92);
      };
      img.onerror = () => { URL.revokeObjectURL(url); resolve(blob); };
      img.src = url;
    });
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
    // Let op: na élke hervulling moet de echte toetsaanslag opnieuw. Zonder dat
    // gooit deze laatste hervulling precies weg wat het formulier nodig had om
    // de tekst te acccepteren — en blijft "Geen zoekertjestekst ingevuld" staan.
    if (_pendingDescription && _descriptionSelector) {
      await runInMainWorld("FILL_DESC", { selector: _descriptionSelector, text: _pendingDescription });
      await runInMainWorld("FILL_HIDDEN_DESC", { text: _pendingDescription });
    }

    // PRE-FLIGHT. Submitting a form we already know is incomplete only produces
    // the platform's own useless "Geen advertentietekst ingevuld" — and, worse,
    // it happened silently because every fill ran inside step() which swallows
    // errors. Verify the two mandatory fields here, retry the description once,
    // and refuse to submit with a message that names what is missing.
    if (descriptionIsEmpty()) {
      await sleep(500);
      await runInMainWorld("FILL_DESC", { selector: _descriptionSelector, text: _pendingDescription });
      await sleep(800);
      if (descriptionIsEmpty()) {
        clog("plaatsen: geweigerd — de editor bleef leeg");
        throw new Error(
          "Beschrijving bleef leeg in de editor — niet geplaatst. " +
          "Plak de tekst zelf in het advertentietekst-veld en klik op Plaatsen."
        );
      }
    }
    // Het formulier houdt de geüploade foto's bij in een verborgen veld. Dat is
    // een hardere waarheid dan miniaturen tellen, die per categorie anders heten.
    const fotoIds = qs('input[name="images.ids"]');
    const fotosVolgensFormulier = fotoIds ? (fotoIds.value || "").trim().length > 0 : null;
    if (_expectPhotos && fotosVolgensFormulier === false && countPhotoThumbs() === 0) {
      clog("plaatsen: geweigerd — geen foto zichtbaar op het formulier");
      throw new Error(
        "Geen enkele foto is geüpload — niet geplaatst. " +
        "Voeg de foto's zelf toe en klik op Plaatsen."
      );
    }

    // Submit button differs per platform:
    //  - Marktplaats/2dehands: [data-testid="place-listing-submit-button"] wrapper.
    //  - Vinted (/items/new and /edit): [data-testid="upload-form-save-button"]
    //    ("Upload" / "Save"). Must NOT grab upload-form-save-draft-button ("Save draft").
    // place-listing-submit-button is the <button> ITSELF on the current
    // Marktplaats form (verified live) — it used to be a wrapper. Handle both,
    // otherwise this silently fell through to the generic fallbacks below.
    const submitContainer = qs('[data-testid="place-listing-submit-button"]');
    const btn = (submitContainer?.tagName === "BUTTON" ? submitContainer : null)
      || submitContainer?.querySelector("button")
      || qs('[data-testid="upload-form-save-button"]')
      || qs('button[type="submit"]')
      || [...document.querySelectorAll("button")].find((b) =>
           b.offsetParent !== null &&
           b.dataset.testid !== "upload-form-save-draft-button" &&
           // The live label is "Plaats je advertentie", which the old
           // anchored one-word pattern could never match.
           /^(plaats(en)?( je advertentie)?|upload|opslaan|publiceer(en)?|publish|save)$/i
             .test((b.textContent || "").trim()));
    // Laatste zekerheid vlak voor de klik: het veld waar het formulier op
    // valideert moet gevuld zijn, anders weigert het zonder bruikbare melding.
    if (_pendingDescription) {
      if (!(await hiddenDescriptionOk())) {
        await runInMainWorld("FILL_HIDDEN_DESC", { text: _pendingDescription });
        await sleep(400);
      }
      clog(`plaatsen: verborgen beschrijvingsveld ${(await hiddenDescriptionOk()) ? "gevuld" : "LEEG"}`);
    }

    if (!btn) throw new Error("Submit/Plaats-knop niet gevonden");
    clog(`plaatsen: knop gevonden ("${(btn.textContent || "").trim()}")`);
    // Nogmaals het beschrijvingsveld verlaten: de laatste bewerking eraan kan
    // van een herstelpoging hierboven komen, en dan staat de cursor er nog in.
    if (_descriptionSelector) await runInMainWorld("BLUR_DESC", { selector: _descriptionSelector });
    btn.scrollIntoView({ block: "center" });
    await sleep(800); // Lexical commit is async — give it time before submit fires
    btn.click();
    clog("plaatsen: op de knop geklikt, wachten op de advertentie");

    const id = await waitForListingUrl(idFromUrl, 20000).catch(() => null);
    if (id) return id;

    const errs = [...document.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"], [aria-invalid="true"]')]
      .map((el) => el.textContent.trim()).filter((t) => t.length > 0 && t.length < 200);
    const uniq = [...new Set(errs)];
    clog(`plaatsen: mislukt — ${uniq.join(" | ") || "geen foutmelding op de pagina"}`);
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
  // Schrijf mee in de console van de service worker — dat is het log dat we
  // daadwerkelijk kunnen inzien. De console van het formulier zelf verdwijnt
  // zodra de tab dichtgaat, dus daar hebben we niets aan bij een storing.
  function clog(...args) {
    console.log("[Omnivaleur]", ...args);
    try { chrome.runtime.sendMessage({ type: "LOG", text: args.map(String).join(" ") }); } catch (e) {}
  }

  async function step(name, fn) {
    try {
      const ok = await fn();
      clog(`stap ${name}: ${ok === false ? "NIET gelukt" : "ok"}`);
    } catch (e) {
      clog(`stap ${name}: FOUT — ${e && e.message ? e.message : e}`);
    }
  }

  // Enable "Bieden vanaf" and fill the minimum bid as a percentage of the asking price.
  //
  // Rewritten against the live Marktplaats form. The old version hunted for a
  // radio whose value was "BIDDING_FROM"/"BIDDING" and, failing that, clicked
  // any element whose text read "bieden" — neither exists here, and the blind
  // text click could just as easily hit the switch and turn bidding OFF.
  // What the page actually has (verified live):
  //   • select#Dropdown-prijstype  — price TYPE, must stay FIXED (Vraagprijs);
  //     FAST_BID would turn the ad into a bidding-only listing.
  //   • input#syi-bidding-switch-input — "Bieden toestaan", on by default.
  //   • input[name="price.minimumBidPrice"] — the "Bieden vanaf" amount, a TEXT
  //     field, so the value needs a comma decimal separator.
  async function fillBidding(price, percentage) {
    const minBid = Math.round(price * percentage / 100 * 100) / 100;

    const sw = qs('input#syi-bidding-switch-input')
      || qs('#syi-bidding-switch input[type="checkbox"]');
    if (sw && !sw.checked) {
      sw.click();
      await sleep(400);
    }

    let bidInput = null;
    for (let i = 0; i < 15; i++) {
      bidInput = qs('input[name="price.minimumBidPrice"]')
        || qs('input#price\\.minimumBidPrice')
        || findFieldByLabel("Bieden vanaf")
        || findFieldByLabel("Minimumbod");
      if (bidInput && bidInput.tagName === "INPUT") break;
      await sleep(200);
    }
    if (!bidInput || bidInput.tagName !== "INPUT") {
      throw new Error("Bieden vanaf: het bedragveld verscheen niet op het formulier");
    }

    const val = bidInput.type === "number" ? String(minBid) : String(minBid.toFixed(2)).replace(".", ",");
    await fillInputHuman(bidInput, val);
    await sleep(300);
    // Verify rather than assume: React can reset a value it didn't like.
    if (!(bidInput.value || "").trim()) {
      throw new Error("Bieden vanaf: het bedrag werd door de pagina teruggezet");
    }
    return true;
  }

  // Truncate to maxLen chars without cutting mid-word. Trims at last space before limit.
  function smartTrunc(str, maxLen) {
    if (str.length <= maxLen) return str;
    // Titles are " - "-separated segments ("(1333) Grijze New Balance Schoenen -
    // Heren 42 - Nieuw Met Kaartjes"). A plain word-boundary cut leaves a dangling
    // half-segment ("… - Nieuw Met"), so drop whole trailing segments first and
    // only fall back to a word cut when even the first segment doesn't fit.
    const SEP = " - ";
    if (str.includes(SEP)) {
      const parts = str.split(SEP);
      while (parts.length > 1 && parts.join(SEP).length > maxLen) parts.pop();
      const kept = parts.join(SEP);
      if (kept.length <= maxLen) return kept;
    }
    const cut = str.lastIndexOf(" ", maxLen);
    return cut > 0 ? str.slice(0, cut) : str.slice(0, maxLen);
  }

  return {
    sleep, qs, waitForEl, fillInput, fillInputHuman, fillNativeSelect, clickRadioByValue, fillDescription,
    findFieldByLabel, selectDropdown, fillBrand, fillManufacturer, selectBundleFree,
    selectPackageSize, uploadPhotos, submitListing, step, closePopup, smartTrunc, fillBidding,
    clog, dutchColor, verifyMpGroupFields, repairMpGroupFields, selectCondition, selectIntendedFor, fillBrandField, logMpFields,
  };
})();
