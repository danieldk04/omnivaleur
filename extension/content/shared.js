// Shared, robust form-filling engine for Marktplaats / 2dehands (Adevinta ECG forms).
// Exposes window.CL with reliable helpers. Loaded before each platform script.
window.CL = (() => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const qs = (sel) => document.querySelector(sel);

  // Wachten op een verandering in het formulier, in plaats van klokjes.
  //
  // Chrome zet in een tabblad dat niet zichtbaar is ELKE korte wachttijd op een
  // hele seconde. Onze zoekertjes worden ingevuld in een venster op de
  // achtergrond, dus daar gold dat altijd: een pauze van 150 ms kostte een
  // seconde, en de honderden kleine pauzes in één formulier tikten samen op tot
  // minuten. Het formulier stond dan keurig ingevuld op het scherm terwijl de
  // tijd voor het plaatsen allang op was.
  //
  // Een MutationObserver wordt niet vertraagd: die meldt zich zodra de pagina
  // echt verandert. Vandaar dat elke "wacht tot dit waar is" hier langsgaat en
  // de klok alleen nog de uiterste grens bewaakt.
  function waitUntil(voorwaarde, timeoutMs = 4000) {
    return new Promise((resolve) => {
      let klaar = false;
      const check = () => { try { return !!voorwaarde(); } catch (_) { return false; } };
      if (check()) return resolve(true);
      const stop = (v) => {
        if (klaar) return;
        klaar = true;
        obs.disconnect();
        clearInterval(tik);
        clearTimeout(limiet);
        resolve(v);
      };
      const obs = new MutationObserver(() => { if (check()) stop(true); });
      obs.observe(document.documentElement, {
        childList: true, subtree: true, attributes: true, characterData: true,
      });
      // Vangnet voor veranderingen zonder DOM-mutatie (bv. een waarde die het
      // formulier zelf zet). Eén seconde is precies wat een verborgen tabblad
      // toestaat, dus dit kost niets extra.
      const tik = setInterval(() => { if (check()) stop(true); }, 1000);
      const limiet = setTimeout(() => stop(check()), timeoutMs);
    });
  }

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
  // Alleen Marktplaats heeft de "echte toetsaanslag"-duw nodig; 2dehands werkt
  // zonder en dat laten we met rust.
  let _descriptionNudge = false;
  let _nudgeGedaan = false;

  // THROWS on failure. "Geen advertentietekst ingevuld" is a platform-side
  // rejection the user cannot act on; the causes below can be reported precisely.
  async function fillDescription(selectors, text, opties) {
    const value = (text || "").trim().slice(0, 2000);
    if (!value) throw new Error("This item has no description — add one in Omnivaleur and publish again");
    const selector = selectors.find((s) => document.querySelector(s));
    if (!selector) throw new Error("The description field could not be found on the page (" + selectors.join(", ") + ")");
    _pendingDescription = value;
    _descriptionSelector = selector;
    _descriptionNudge = !!(opties && opties.nudge);
    _nudgeGedaan = false;
    document.querySelector(selector)?.scrollIntoView({ block: "center" });
    const ok = await runInMainWorld("FILL_DESC", { selector, text: value });
    if (!ok) throw new Error("The description could not be placed into the editor");
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

  // De klacht die Marktplaats ("Geen advertentietekst ingevuld") en 2dehands
  // ("Geen zoekertjestekst ingevuld") tonen zodra ze de beschrijving als leeg
  // beschouwen. Dit is de enige harde waarheid die we hebben: het oordeel van
  // het formulier zelf, in plaats van onze eigen inschatting vooraf.
  // Marktplaats/2dehands keuren een prijs met ÉÉN decimaal af met "Ongeldige
  // prijs.": "9,5" en "25,0" mogen niet, "9,50", "25" en "25,00" wel. Een prijs
  // als 9.5 werd letterlijk "9,5" en de advertentie ging dus nooit online — bij
  // kleding viel dat niet op omdat die bijna altijd op ,99 of rond eindigt.
  // Altijd twee decimalen is de vorm die in alle gevallen wordt geaccepteerd.
  function mpPrijs(waarde, el) {
    const n = Number(waarde);
    if (!isFinite(n) || n <= 0) return "";
    if (el && el.type === "number") return String(n);
    return n.toFixed(2).replace(".", ",");
  }

  // Alles wat het formulier zelf zichtbaar als bezwaar toont. Eén lijst, zodat
  // elke mislukte publicatie dezelfde volledige uitleg meekrijgt.
  // "52 of 60 characters used" is geen klacht maar een tellertje onder een
  // tekstveld. Die stonden wél in de foutmelding en het échte rode veld niet,
  // waardoor er vijf regels ruis terugkwamen en nul bruikbare informatie —
  // gemeten op een mislukte publicatie 21-08-2026.
  const _TELLER_RE = /^\d+\s*(of|van)\s*\d+\s*(characters|tekens)/i;

  function formulierklachten() {
    const els = [...document.querySelectorAll(
      '[class*="error"], [class*="Error"], [role="alert"], [aria-invalid="true"]'
    )];
    const teksten = els.map((el) => (el.textContent || "").replace(/\s+/g, " ").trim())
                       .filter((t) => t.length > 0 && t.length < 200 && !_TELLER_RE.test(t));
    return [...new Set(teksten)];
  }

  // WELK VELD IS ROOD?
  //
  // De klachtenlezer hierboven pakt de tekst van foutmeldingen op, maar niet
  // ieder formulier zet er een tekst bij: Marktplaats kleurt soms alleen het
  // kader rood. Dan meldde de extensie "vul de rode velden in" zonder te kunnen
  // zeggen wélke — en daar kan niemand iets mee, ook ik niet.
  //
  // Deze leest de velden zelf: wat is ongeldig, hoe heet het, en wat staat
  // erin. Alleen naam en lengte, nooit de inhoud zelf.
  function roodGemarkeerdeVelden() {
    const uit = [];
    for (const el of document.querySelectorAll("input, textarea, select, [contenteditable='true']")) {
      const ongeldig = el.getAttribute("aria-invalid") === "true"
        || /error|invalid/i.test(el.className || "")
        || /error|invalid/i.test((el.closest("[class]") || {}).className || "");
      if (!ongeldig) continue;
      const naam = el.name || el.id || el.getAttribute("data-testid") || el.tagName.toLowerCase();
      const waarde = (el.value != null ? String(el.value) : (el.innerText || ""));
      uit.push(`${naam}=${waarde.trim() ? waarde.trim().length + " tekens" : "LEEG"}`);
      if (uit.length >= 8) break;
    }
    return uit;
  }

  // Een venster dat het plaatsen BLOKKEERT en dat alleen de verkoper zelf kan
  // wegwerken: Vinted vraagt bij het eerste zoekertje (en na een adreswijziging)
  // "Waar woon je?" en soms om een telefoonbevestiging, in een modaal venster
  // bovenop het formulier.
  //
  // Waarom dit apart wordt herkend: het adresvenster verandert de adresbalk niet
  // en zet geen rode foutmelding op het formulier. De wachtlus liep dus 20
  // seconden leeg, daarna nog drie herstelrondes voor de beschrijving en tot
  // slot anderhalve minuut zoeken in de garderobe — ruim twee minuten, waarna de
  // gebruiker "Not published — complete the fields marked in red" te zien kreeg
  // terwijl er geen enkel rood veld was. Precies de melding die je nergens heen
  // stuurt.
  //
  // Het adres wordt NOOIT automatisch ingevuld. Het is een woonadres; dat raden
  // of ergens vandaan halen is niets voor een machine. Het tabblad blijft open,
  // de verkoper vult het één keer in en klikt zelf op Uploaden — die klik wordt
  // al opgepikt en het zoekertje wordt vanzelf afgemeld.
  const BLOKKADE_PATRONEN = [
    { naam: "adres",    re: /waar woon je|where do you live|où habites-tu|voeg (je|uw) adres|add your address|bezorgadres|verzendadres|shipping address|home address|straatnaam|postcode en plaats/i },
    { naam: "telefoon", re: /verifieer je telefoonnummer|verify your phone|telefoonnummer bevestigen|confirm your phone number/i },
    // Zakelijke verkopers op Vinted (Pro) moeten hun bedrijf laten verifieren
    // voordat er ook maar iets geplaatst mag worden. Zonder deze herkenning
    // strandde elke poging op een algemene mislukking, en zag de verkoper zes
    // advertenties die "niet lukten" zonder te weten waarom. Gemeten geval
    // 20-08-2026: zes Vinted-publicaties, geen enkele geplaatst, account nog in
    // verificatie.
    { naam: "verificatie", re: /verifieer je (account|bedrijf)|verify your (account|business)|bedrijfsverificatie|business verification|identiteitsverificatie|verify your identity|nog niet geverifieerd|not yet verified|upload je (kvk|uittreksel|documenten)|pro.?account.*verificatie/i },
  ];

  // Alleen binnen een écht zichtbaar dialoogvenster kijken. Zoeken in de hele
  // pagina zou op woorden als "postcode" in een voettekst kunnen aanslaan, en
  // een verzonnen blokkade is erger dan geen blokkade: dan stopt het plaatsen
  // van elk zoekertje.
  function plaatsBlokkade() {
    const vensters = [...document.querySelectorAll(
      '[role="dialog"], [role="alertdialog"], [data-testid*="modal" i], [class*="Modal" i]'
    )].filter((el) => el.offsetParent !== null && (el.textContent || "").trim().length > 10);
    for (const venster of vensters) {
      const tekst = (venster.textContent || "").replace(/\s+/g, " ");
      for (const p of BLOKKADE_PATRONEN) {
        if (p.re.test(tekst)) return { naam: p.naam, tekst: tekst.trim().slice(0, 160) };
      }
    }
    return null;
  }

  function beschrijvingKlachtOpPagina() {
    return /geen\s+(advertentietekst|zoekertjestekst)\s+ingevuld/i
      .test(document.body.innerText || "");
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

  // Laatste controle vlak vóór het plaatsen: staat de advertentietekst er nog?
  //
  // De tekst wordt vroeg in het formulier gezet, maar daarna gebeurt er nog van
  // alles: foto's uploaden (tot twee minuten), kenmerken kiezen, het merkvenster.
  // Elke herteken-ronde kan de editor opnieuw opbouwen, en dan is de tekst weg.
  // Niemand keek daar nog naar — de bewaker hield alleen het VERBORGEN veld in de
  // gaten, en dat blijkt niet te zijn waar Marktplaats op controleert (live
  // gemeten: dat veld blijft leeg, ook als een mens zelf typt). Zo ging een
  // advertentie zonder tekst de deur uit en kwam "Geen advertentietekst
  // ingevuld" terug. Nu vullen we hem in dat geval gewoon opnieuw.
  async function ensureDescriptionStillFilled() {
    if (!_pendingDescription || !_descriptionSelector) return true;
    if (!descriptionIsEmpty()) return true;
    console.warn("[Omnivaleur] beschrijving was leeggeraakt — opnieuw invullen vlak voor het plaatsen");
    document.querySelector(_descriptionSelector)?.scrollIntoView({ block: "center" });
    const ok = await runInMainWorld("FILL_DESC", {
      selector: _descriptionSelector, text: _pendingDescription,
    });
    await runInMainWorld("FILL_HIDDEN_DESC", { text: _pendingDescription });
    if (!ok || descriptionIsEmpty()) {
      throw new Error(
        "The description kept disappearing from the form right before publishing, " +
        "so this listing was not submitted (it would have gone out empty). " +
        "The tab is left open — paste the text yourself and click place, or try again."
      );
    }
    return true;
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
  // Alleen de kern: welke keuzevelden staan er, en wat is er gekozen. Bedoeld
  // voor de foutmelding — zonder dit is "hij plaatst niet en er staat niets
  // rood" niet op te lossen, want juist een leeg verplicht veld blijft stil.
  function keuzeveldenKort() {
    try {
      return attrSelects()
        .map((el) => `${el.name.replace(/^singleSelectAttribute\[|\]$/g, "")}=${el.value || "LEEG"}`)
        .join(", ");
    } catch (_) { return "niet te lezen"; }
  }

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

  // Welk instrument iets bij hoort, voor het "Bestemd voor"-veld in de
  // muziekcategorieën. Sleutel = een woord uit de titel of onze eigen categorie,
  // waarde = de optie zoals Marktplaats hem letterlijk spelt. Langste sleutels
  // eerst, zodat "basgitaar" wint van "gitaar".
  const MUZIEK_BESTEMD_VOOR = [
    ["elektrische basgitaar", "Elektrische basgitaar"],
    ["akoestische basgitaar", "Akoestische basgitaar"],
    ["elektrische gitaar", "Elektrische gitaar"], ["gitaren elektrisch", "Elektrische gitaar"],
    ["akoestische gitaar", "Akoestische gitaar"], ["gitaren akoestisch", "Akoestische gitaar"],
    ["basgitaar", "Elektrische basgitaar"], ["gitaren bas", "Elektrische basgitaar"],
    ["dwarsfluit", "Dwarsfluit of Piccolo"], ["piccolo", "Dwarsfluit of Piccolo"],
    ["mondharmonica", "Mondharmonica"], ["klavecimbel", "Klavecimbel"],
    ["altviool", "Viool of Altviool"], ["contrabas", "Contrabas"],
    ["blokfluit", "Blokfluit"], ["accordeon", "Accordeon"], ["banjo", "Banjo"],
    ["mandoline", "Mandoline"], ["draaiorgel", "Draaiorgel"],
    ["drumcomputer", "Drumcomputer"], ["klarinet", "Klarinet"],
    ["saxofoon", "Saxofoon"], ["trombone", "Trombone"], ["trompet", "Trompet"],
    ["tuba", "Tuba"], ["hobo", "Hobo"], ["hoorn", "Hoorn"], ["cello", "Cello"],
    ["viool", "Viool of Altviool"], ["piano", "Piano"], ["orgel", "Orgel"],
    ["synthesizer", "Keyboard of Synthesizer"], ["keyboard", "Keyboard of Synthesizer"],
    ["percussie", "Drums of Percussie"], ["drumstel", "Drums of Percussie"],
    ["drums", "Drums of Percussie"], ["slagwerk", "Drums of Percussie"],
    ["gitaar", "Akoestische gitaar"],
  ];

  // "Bestemd voor" heeft per categorie een heel andere betekenis: bij
  // kinderkleding is het jongen/meisje, bij muziek is het WELK INSTRUMENT. Vullen
  // met "Jongen of Meisje" op een muziekformulier laat het veld leeg staan, en
  // dan weigert verifyMpGroupFields terecht te plaatsen. Daarom kijken we naar
  // de opties die er écht staan in plaats van naar de categorie te gokken.
  function selectIntendedFor(item) {
    const el = intendedForSelect();
    if (!el) return true; // deze categorie kent het veld niet — niets te doen
    const opties = [...el.options].map((o) => o.text.trim());
    const hay = `${item.title || ""} ${item.category || ""} ${item.description || ""}`.toLowerCase();

    if (opties.some((o) => /^Jongen|^Meisje/.test(o))) {
      const boy = /jongen|boys?\b|garçon/.test(hay);
      const girl = /meisje|girls?\b|fille/.test(hay);
      const want = boy && !girl ? "Jongen" : girl && !boy ? "Meisje" : "Jongen of Meisje";
      return fillNativeSelect(el, want);
    }

    // Instrumentenlijst: neem het eerste instrument dat in de tekst voorkomt en
    // dat deze lijst ook echt kent. Vinden we niets, dan "Overige instrumenten" —
    // een bestaande, eerlijke keuze, nooit een verkeerd instrument.
    const heeft = (naam) => opties.find((o) => o.toLowerCase() === naam.toLowerCase());
    for (const [woord, optie] of MUZIEK_BESTEMD_VOOR) {
      if (hay.includes(woord) && heeft(optie)) return fillNativeSelect(el, heeft(optie));
    }
    const rest = heeft("Overige instrumenten");
    if (rest) return fillNativeSelect(el, rest);

    // Onbekende lijst in een categorie die we nog niet kennen: liever leeg laten
    // en de gebruiker laten kiezen dan een willekeurige optie aanvinken.
    return false;
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

    if (item.size && emptyLabel("Maat")) missing.push("size");
    if (item.color && emptyLabel("Kleur")) missing.push("colour");
    const condEl = conditionSelect();
    if (condEl && !condEl.value) missing.push("condition");
    const intendedEl = intendedForSelect();
    if (intendedEl && !intendedEl.value) missing.push("intended for");
    const bf = brandField();
    if (item.brand && bf && !fieldFilled(bf)) missing.push("brand");
    if (emptyInput("textAttribute[manufacturerTradename]")) missing.push("manufacturer trade name");
    if (emptyInput("textAttribute[manufacturerEmail]")) missing.push("manufacturer e-mail");
    if (item.bid_percentage && emptyInput("price.minimumBidPrice")) missing.push("minimum bid");

    if (missing.length) {
      throw new Error(
        `These fields were left empty on the form: ${missing.join(", ")}. ` +
        `The listing was NOT published — fill them in yourself and click publish.`
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

  // MAATVELDEN DIE NIET OP TEKST MATCHEN.
  //
  // Marktplaats zet bij overhemden geen maat maar een halswijdte-groep:
  // "Halswijdte 38 (S) of kleiner", "Halswijdte 39/40 (M)", "41/42 (L)",
  // "43/44 (XL)", "Overige halswijdtes". Onze maat is "16 in | 40 cm" of "39",
  // en die tekst komt in geen van die opties voor — dus bleef het veld leeg.
  //
  // Waarom dat erger is dan het lijkt: het veld is verplicht. Marktplaats zet er
  // geen zichtbare klacht bij en markeert het niet rood, maar de plaatsknop doet
  // dan gewoon niets. Gemeten 21-08-2026: formulier compleet, geen enkele
  // melding, echte muisklik aantoonbaar op de knop — en geen advertentie.
  //
  // Werkt op getallen, niet op tekst: haal het getal uit de maat, reken inches
  // om naar centimeters, en kies de groep waar dat getal in valt.
  function _maatGetal(maat) {
    const t = String(maat || "").toLowerCase();
    // Centimeters eerst: staat er "16 in | 40 cm", dan is 40 wat de verkoper
    // bedoelt. Omrekenen van inches geeft 40,6 en dus 41 — één groep te hoog.
    const cm = t.match(/(\d{2})\s*cm/);
    if (cm) return parseInt(cm[1], 10);
    const inch = t.match(/(\d{2}(?:[.,]5)?)\s*(?:in\b|inch|")/);
    if (inch) return Math.round(parseFloat(inch[1].replace(",", ".")) * 2.54);
    const kaal = t.match(/\b(3[5-9]|4[0-9])\b/);
    return kaal ? parseInt(kaal[1], 10) : null;
  }

  async function vulHalswijdte(item) {
    const select = attrSelects().find((el) =>
      [...el.options].some((o) => /halswijdte/i.test(o.text)));
    if (!select) return false;
    if (select.value && select.value !== "") return true;   // al gevuld
    const n = _maatGetal(item && item.size);
    const opties = [...select.options].map((o) => o.text.trim());
    const kies = (test) => opties.find((t) => test.test(t));
    let wil = null;
    if (n != null) {
      if (n <= 38) wil = kies(/38.*kleiner|38\s*\(S\)/i);
      else if (n <= 40) wil = kies(/39\s*\/\s*40/);
      else if (n <= 42) wil = kies(/41\s*\/\s*42/);
      else if (n <= 44) wil = kies(/43\s*\/\s*44/);
    }
    // Geen bruikbare maat? Dan "Overige", want leeg laten betekent hier: de
    // advertentie gaat er niet op. Een eerlijke "overige" is beter dan niets.
    if (!wil) wil = kies(/overige/i);
    if (!wil) return false;
    const ok = fillNativeSelect(select, wil);
    clog(`halswijdte: maat "${item && item.size}" → ${n ?? "onbekend"} → "${wil}" ${ok ? "gezet" : "MISLUKT"}`);
    return ok;
  }

  // DE BESCHRIJVING ECHT TYPEN.
  //
  // Dit is geen noodgreep meer maar de gewone weg op Marktplaats en 2dehands.
  // Bewezen op 21-08-2026 op een echt formulier: tekst die wij in het veld
  // zetten komt wél in de DOM (449 tekens) maar niet in de staat waarop het
  // formulier zijn oordeel baseert (0 tekens). De plaatsknop doet dan niets —
  // geen klacht, geen rood veld, geen enkel verzoek naar de server. Dezelfde
  // advertentie mét echt getypte tekst (158 tekens in beide) stond meteen online.
  //
  // Daarom typen we hem hier na het invullen alsnog, en controleren we het:
  // blijft de staat leeg, dan weten we dat vóór het plaatsen in plaats van erna.
  async function typBeschrijvingEcht(tekst) {
    if (!tekst) return "geen tekst";
    const uitkomst = await new Promise((res) => {
      try { chrome.runtime.sendMessage({ type: "TYPE_ECHT", text: tekst }, (r) => res(r || "geen antwoord")); }
      catch (_) { res("niet bereikbaar"); }
    });
    const lengte = await new Promise((res) => {
      try { chrome.runtime.sendMessage({ type: "ECHTE_DESC_LENGTE" }, (r) => res(typeof r === "number" ? r : -1)); }
      catch (_) { res(-1); }
    });
    clog(`beschrijving echt getypt: ${uitkomst} — formulier houdt nu ${lengte} tekens vast`);
    _echteBeschrijvingLengte = lengte;
    return uitkomst;
  }

  let _echteBeschrijvingLengte = -1;

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

  // De EU verplicht bij veel categorieen een "verantwoordelijke partij": wie is
  // aansprakelijk voor dit product. Dat hoort de verkoper zelf te zijn.
  //
  // Hier stond Revaleur als standaardwaarde, en omdat een item die velden helemaal
  // niet heeft werd die standaard ALTIJD gebruikt. Elke klant plaatste zijn
  // advertenties dus met Daniels bedrijfsnaam en mailadres als aansprakelijke
  // partij. Gemeld door Jaap van Zilverwebsite op 18-08-2026: "hij vult een
  // emailadres van Revaleur in + handelsnaam is Revaleur".
  //
  // Nu vullen we alleen wat de verkoper zelf heeft opgegeven. Staat er niets, dan
  // laten we het veld met rust: Marktplaats vult die velden voor een zakelijk
  // account meestal zelf voor, en anders vraagt het formulier erom. Een leeg veld
  // is vervelend; een verkeerde aansprakelijke is een juridisch probleem.
  function fillManufacturer(item) {
    const fields = [
      ["textAttribute[manufacturerTradename]", item.manufacturer_name],
      ["textAttribute[manufacturerAddress]", item.manufacturer_address],
      ["textAttribute[manufacturerEmail]", item.manufacturer_email],
    ];
    for (const [name, val] of fields) {
      if (!val || !String(val).trim()) continue;
      const el = qs(`input[name="${name}"]`);
      if (el) { el.scrollIntoView({ block: "center" }); fillInput(el, val); }
    }
  }

  // De verzendwijze die de verkoper in de extensie heeft ingesteld. Dit stond
  // hard op "Ophalen of Verzenden": prima voor wie kleding verkoopt en laat
  // ophalen, fout voor wie alleen verzendt. Gemeten geval: een verkoper van
  // antiek zilver verzendt uitsluitend en moest dit bij elke advertentie
  // terugzetten.
  //
  // De waarden zijn de labels zoals Marktplaats en 2dehands ze zelf op de
  // keuzerondjes zetten; de terugval is de oude vaste keuze, zodat een lege of
  // onleesbare instelling nooit tot een advertentie zonder verzendwijze leidt.
  const LEVERING_LABELS = {
    beide: "Ophalen of Verzenden",
    verzenden: "Verzenden",
    ophalen: "Ophalen",
  };

  async function gekozenLevering() {
    try {
      const s = await chrome.storage.sync.get("deliveryMode");
      return LEVERING_LABELS[s.deliveryMode] || LEVERING_LABELS.beide;
    } catch (_) {
      return LEVERING_LABELS.beide;
    }
  }

  // Kiest de ingestelde verzendwijze, en valt terug op "Ophalen of Verzenden"
  // als dit formulier die optie niet aanbiedt — niet elke categorie heeft alle
  // drie de keuzes.
  // De keuze uit het account (meegestuurd in de opdracht) gaat vóór de oude
  // schakelaar in de extensie-instellingen. Die laatste zit verstopt achter een
  // rechtermuisknop en werd door vrijwel niemand gevonden, waardoor iemand die
  // uitsluitend verzendt bij elke advertentie "Ophalen of Verzenden" kreeg.
  async function selectDelivery(item) {
    const uitOpdracht = LEVERING_LABELS[(item && item.levering) || ""];
    const gewenst = uitOpdracht || (await gekozenLevering());
    if (clickRadioByValue(gewenst)) return true;
    return clickRadioByValue(LEVERING_LABELS.beide);
  }

  // Pakketgrootte op Marktplaats. De keuzerondjes hebben echte waarden
  // (XS = brievenbuspakje, S = klein, M = gemiddeld, L = groot pakket), live
  // afgelezen op het formulier. Op waarde klikken is veel steviger dan op de
  // labeltekst zoeken: die tekst verandert met elke campagne van Marktplaats.
  async function selectPakketWaarde(waarde) {
    if (!waarde) return false;
    for (let i = 0; i < 20; i++) {
      const radio = qs(`input[type="radio"][name="packageSize"][value="${waarde}"]`);
      if (radio) {
        radio.click();
        (radio.closest("label") || radio).click();
        await sleep(150);
        return true;
      }
      await sleep(150);
    }
    return false;
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
    if (!fileInput) throw new Error("The photo upload field could not be found on the page");

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
        `None of the ${urls.length} photo(s) could be downloaded — ` +
        `first URL: ${(failures[0] || "").slice(0, 120)}`
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

  // Zorgt dat de beschrijving er staat waar het formulier hem leest, en geeft
  // pas op na een paar echte pogingen. De volgorde is met opzet:
  // vullen → veld verlaten → dán het verborgen veld zetten. Andersom wist het
  // verlaten van het veld net weer wat we er zojuist in hadden gezet.
  async function ensureDescriptionReady() {
    for (let poging = 1; poging <= 5; poging++) {
      if (descriptionIsEmpty()) {
        await runInMainWorld("FILL_DESC", { selector: _descriptionSelector, text: _pendingDescription });
        await sleep(400);
      }
      await runInMainWorld("BLUR_DESC", { selector: _descriptionSelector });
      await sleep(250);
      await runInMainWorld("FILL_HIDDEN_DESC", { text: _pendingDescription });
      await runInMainWorld("ENFORCE_DESC", { text: _pendingDescription, durationMs: 120000 });
      await sleep(250);

      const zichtbaarLeeg = descriptionIsEmpty();
      // Het verborgen veld is BEWUST geen voorwaarde meer. Live gemeten op
      // marktplaats.nl (aug. 2026): dat veld blijft leeg — ook als een mens de
      // tekst zelf intypt — en tóch keurt het formulier de advertentie goed. Het
      // wordt pas bij het plaatsen door de site zelf gevuld. Er op wachten
      // betekende dus vijf zinloze pogingen van een halve seconde bij ELKE
      // advertentie, en een melding dat de beschrijving leeg was terwijl hij er
      // gewoon stond. De editor is de waarheid; het verborgen veld vullen we
      // alleen nog "voor het geval dat".
      const verborgenOk = await hiddenDescriptionOk();
      if (!zichtbaarLeeg) {
        // Laatste stap vlak vóór Plaatsen: één echte spatie typen. Marktplaats
        // rekende de tekst pas mee ná een toetsaanslag — zonder dit bleef
        // "Geen advertentietekst ingevuld" staan met de tekst gewoon in beeld.
        // Eén keer, anders stapelen de spaties zich op bij een herhaalde poging.
        if (_descriptionNudge && !_nudgeGedaan) {
          _nudgeGedaan = true;
          const geduwd = await runInMainWorld("NUDGE_DESC", { selector: _descriptionSelector });
          clog(`beschrijving: spatie-duw ${geduwd ? "gelukt" : "MISLUKT"}`);
          await sleep(250);
        }
        return true;
      }
      clog(`beschrijving poging ${poging}: editor ${zichtbaarLeeg ? "LEEG" : "ok"}, ` +
           `verborgen veld ${verborgenOk ? "ok" : "LEEG"}`);
      await sleep(600);
    }

    // Staat de tekst zichtbaar in de editor, dan weigeren we NIET meer te
    // plaatsen. Dat oordeel kwam van onze eigen inschatting van een verborgen
    // veld, en die zat er soms naast — dan blokkeerden we een advertentie die
    // prima had gekund. Plaatsen mag het nu proberen; klaagt het formulier
    // daarna alsnog, dan typt submitListing een echte spatie en klikt opnieuw.
    if (!descriptionIsEmpty()) {
      clog("beschrijving: tekst staat zichtbaar in de editor — toch plaatsen, " +
           "met herstel-na-klik als het formulier alsnog klaagt");
      return true;
    }

    clog("plaatsen: geweigerd — de beschrijving bleef leeg");
    throw new Error(
      "The description stayed empty on the form, so nothing was published. " +
      "Paste the text into the description field yourself and click publish."
    );
  }

  let _laatsteEchteKlik = "niet nodig";
  let _laatsteGratisKlik = "niet nodig";

  async function submitListing(idFromUrl) {
    // Brand FIRST — closing the brand modal triggers a React re-render that resets
    // the Lexical EditorState. Description must be filled AFTER brand to survive.
    if (_pendingBrand) {
      await runInMainWorld("FILL_BRAND", { brand: _pendingBrand });
      await sleep(500); // wait for React to settle after modal close
    }

    // Description LAST — fills Lexical EditorState after all React re-renders are done.
    // PRE-FLIGHT. Een formulier plaatsen waarvan we al weten dat het incompleet
    // is levert alleen het nutteloze "Geen zoekertjestekst ingevuld" op. Hier
    // wordt de beschrijving daarom net zolang opnieuw gezet tot zowel de
    // zichtbare editor als het veld waar het formulier écht op valideert gevuld
    // is — en anders weigeren we te plaatsen, met een melding die zegt wat er is.
    if (_pendingDescription && _descriptionSelector) await ensureDescriptionReady();

    // Het formulier houdt de geüploade foto's bij in een verborgen veld. Dat is
    // een hardere waarheid dan miniaturen tellen, die per categorie anders heten.
    const fotoIds = qs('input[name="images.ids"]');
    const fotosVolgensFormulier = fotoIds ? (fotoIds.value || "").trim().length > 0 : null;
    if (_expectPhotos && fotosVolgensFormulier === false && countPhotoThumbs() === 0) {
      clog("plaatsen: geweigerd — geen foto zichtbaar op het formulier");
      throw new Error(
        "Not a single photo was uploaded, so nothing was published. " +
        "Add the photos yourself and click publish."
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
    if (!btn) throw new Error("The publish button could not be found on the page");
    clog(`plaatsen: knop gevonden ("${(btn.textContent || "").trim()}")`);
    btn.scrollIntoView({ block: "center" });
    await sleep(800); // Lexical commit is async — give it time before submit fires

    // Allerlaatste controle, ná alle blur- en herteken-rondes: dit is het moment
    // waarop het formulier de beschrijving beoordeelt. Was dit vroeger alleen
    // een logregel, waarna er tóch geklikt werd — precies de willekeurige
    // afkeuring die de gebruiker zag.
    if (_pendingDescription && _descriptionSelector) await ensureDescriptionReady();

    // Vanaf hier is er geklikt: alles wat daarna in de adresbalk verschijnt is
    // een ECHTE, geplaatste advertentie. Dat moet de achtergrond weten, want
    // Vinted gooit bij het plaatsen de pagina om en dan sterft dit script
    // middenin — de melding "hij staat online" komt dan nooit aan. De
    // achtergrond kijkt zelf mee naar het adres, maar accepteerde alleen het
    // nette adres mét naam erin (/items/123-grijze-short). Vinted landt lang
    // niet altijd op die vorm, en dan bleef het artikel eindeloos op
    // "Publishing…" staan terwijl hij gewoon online stond.
    // DE GRATIS-KEUZE OOK ECHT AANKLIKKEN.
    //
    // "Hoe wil je adverteren?" (Gratis / Plus / Premium) is verplicht, en geldt
    // net als de beschrijving: onze eigen klik zet het bolletje wel aan in de
    // pagina, maar niet in de staat waarop het formulier zijn oordeel baseert.
    // Zonder die keuze doet de plaatsknop niets, zonder klacht en zonder rood
    // veld. Nog een keer echt klikken kan geen kwaad: het is dezelfde keuze.
    const gratisGekozen = await new Promise((res) => {
      try {
        chrome.runtime.sendMessage(
          { type: "KLIK_ECHT", selector: '[data-testid="bundle-option-FREE"]' },
          (r) => res(r || "geen antwoord"));
      } catch (_) { res("niet bereikbaar"); }
    });
    clog(`gratis-keuze: ${gratisGekozen}`);
    _laatsteGratisKlik = gratisGekozen;
    await sleep(400);

    try { chrome.runtime.sendMessage({ type: "SUBMIT_CLICKED" }, () => chrome.runtime.lastError); } catch (_) {}
    btn.click();
    clog("plaatsen: op de knop geklikt, wachten op de advertentie");

    // Wachten op het zoekertje, maar tegelijk kijken of er een venster bovenop
    // is gekomen dat alleen de verkoper zelf kan wegwerken (adres, telefoon).
    // Zonder deze wedloop bleef het plaatsen ruim twee minuten hangen en kwam er
    // een melding uit die naar rode velden verwees die er niet waren.
    const blokkadeWacht = (async () => {
      const einde = Date.now() + 20000;
      while (Date.now() < einde) {
        const b = plaatsBlokkade();
        if (b) return b;
        await sleep(500);
      }
      return null;
    })();
    let id = await Promise.race([
      waitForListingUrl(idFromUrl, 20000).catch(() => null),
      blokkadeWacht.then((b) => (b ? { _blokkade: b } : null)),
    ]);

    // Onze klik genegeerd? Marktplaats doet met de plaatsknop hetzelfde als met
    // het tekstveld: alleen een échte muisklik telt. Gemeten: formulier compleet,
    // geen rood veld, knop aanwezig en niet uitgeschakeld, en na btn.click()
    // gebeurde er niets. Daarom hier nog één keer, maar dan echt.
    //
    // Alleen als we nog steeds op het plaatsformulier staan. Werkte de eerste
    // klik tóch, dan is de pagina veranderd en zou een tweede klik een tweede
    // advertentie kunnen opleveren — precies wat er nooit mag gebeuren.
    if (!id && /\/(plaats|syi)\b/.test(location.pathname) && document.contains(btn)) {
      const echteKlik = await new Promise((res) => {
        try {
          chrome.runtime.sendMessage(
            { type: "KLIK_ECHT", selector: '[data-testid="place-listing-submit-button"]' },
            (r) => res(r || "geen antwoord"));
        } catch (_) { res("niet bereikbaar"); }
      });
      clog(`plaatsen: echte klik — ${echteKlik}`);
      _laatsteEchteKlik = echteKlik;
      id = await waitForListingUrl(idFromUrl, 25000).catch(() => null);
    }
    if (id && id._blokkade) {
      const b = id._blokkade;
      clog(`plaatsen: geblokkeerd door Vinted (${b.naam}) — teruggegeven aan de gebruiker`);
      const fout = new Error(
        (b.naam === "adres"
          ? "Vinted first wants your address before it will publish anything (\"Where do you live?\"). "
          : b.naam === "verificatie"
          ? "Vinted has not verified your account yet, and will not publish anything until it has. For a business account a Chamber of Commerce extract showing your trading name is normally enough — articles of association are not required for a VOF or sole trader. "
          : "Vinted first wants you to confirm your phone number before it will publish anything. ") +
        (b.naam === "verificatie"
          ? "Nothing was published, and nothing was lost — your items stay ready here. Publishing to Vinted works as soon as Vinted approves your account. "
          : "We never fill that in for you. The tab is left open with everything else already filled in: " +
            "complete this one screen and click Upload — the listing is then marked as published automatically, " +
            "and every following listing goes through without this step. ") +
        `Vinted says: \u201c${b.tekst}\u201d`
      );
      // Merkteken voor de opdracht zelf: bij een blokkade heeft doorzoeken van de
      // garderobe geen zin — er is niets geplaatst. Zonder dit merkteken kostte
      // die zoektocht nog eens anderhalve minuut voor niets.
      fout.blokkade = b.naam;
      throw fout;
    }
    if (id) return id;

    // Het formulier zegt zélf wat er mis is. Tot nu toe voorspelden we vooraf of
    // de beschrijving zou meetellen — een gok die er soms naast zat, waarna er
    // tóch geklikt werd en de gebruiker "Geen advertentietekst ingevuld" zag met
    // de tekst gewoon in beeld. Nu lezen we die melding en doen we precies wat de
    // gebruiker met de hand deed: één echte spatie typen en opnieuw plaatsen.
    if (_pendingDescription && _descriptionSelector) {
      let laatsteToets = "niet geprobeerd";
      for (let herstel = 1; herstel <= 3; herstel++) {
        if (!beschrijvingKlachtOpPagina()) break;
        const staat = await runInMainWorld("DESCRIBE_DESC", {});
        clog(`plaatsen: formulier meldt lege beschrijving (herstelpoging ${herstel}) — ${staat}`);

        // Beide kanten opnieuw aanpakken: het verborgen veld waar de validatie op
        // leest, én een echte toetsaanslag in de zichtbare editor. Welke van de
        // twee het formulier gelooft verschilt per platform, dus doen we allebei.
        await runInMainWorld("FILL_HIDDEN_DESC", { text: _pendingDescription });
        const geduwd = await runInMainWorld("NUDGE_DESC", { selector: _descriptionSelector });
        // De nagemaakte spatie hierboven verandert de staat van het Marktplaats-
        // formulier aantoonbaar NIET (zie typEchteToets in background.js). Blijft
        // de klacht staan, dan proberen we een echte toetsaanslag; die werkt wel,
        // maar vraagt eenmalig toestemming van de gebruiker.
        let echt = "niet geprobeerd";
        await sleep(400);
        if (beschrijvingKlachtOpPagina()) {
          echt = await new Promise((res) => {
            // Eerste poging: één echte spatie. Dat bleek in de praktijk genoeg
            // om de klacht te laten verdwijnen. Helpt het niet, dan typt de
            // volgende ronde de hele tekst opnieuw — het formulier telt namelijk
            // alleen mee wat er echt getypt is (zie typEchteToets).
            const teTypen = herstel === 1 ? " " : (_pendingDescription || " ");
            try { chrome.runtime.sendMessage({ type: "TYPE_ECHT", text: teTypen }, (r) => res(r || "geen antwoord")); }
            catch (_) { res("niet bereikbaar"); }
          });
          laatsteToets = echt;
          clog(`herstel ${herstel}: echte toets — ${echt}`);
        }
        await sleep(500 + herstel * 700);

        const klachtWeg = !beschrijvingKlachtOpPagina();
        clog(`herstel ${herstel}: spatie ${geduwd ? "getypt" : "MISLUKT"}, echte toets ${echt}, `
           + `melding ${klachtWeg ? "weg" : "staat er nog"}`);
        // Hier stond alleen btn.click(). Gemeten 21-08-2026: na herstelronde 1
        // was de klacht wég — en toch gebeurde er niets, want Marktplaats
        // negeert een klik die van een script komt. De echte klik landde in
        // dezelfde ronde aantoonbaar op de knop. Dus hier ook echt klikken.
        btn.click();
        let id2 = await waitForListingUrl(idFromUrl, 8000).catch(() => null);
        if (!id2 && /\/(plaats|syi)\b/.test(location.pathname) && document.contains(btn)) {
          _laatsteEchteKlik = await new Promise((res) => {
            try {
              chrome.runtime.sendMessage(
                { type: "KLIK_ECHT", selector: '[data-testid="place-listing-submit-button"]' },
                (r) => res(r || "geen antwoord"));
            } catch (_) { res("niet bereikbaar"); }
          });
          clog(`herstel ${herstel}: echte klik — ${_laatsteEchteKlik}`);
          id2 = await waitForListingUrl(idFromUrl, 20000).catch(() => null);
        }
        if (id2) { clog(`plaatsen: alsnog gelukt na herstelpoging ${herstel}`); return id2; }
      }
      if (beschrijvingKlachtOpPagina()) {
        // De melding in het dashboard vertelt nu zelf wat het formulier had —
        // anders is elke volgende ronde weer gissen. ÉN alle andere klachten die
        // op de pagina staan: één keer bleek de tekst gewoon gevuld (123 tekens
        // aan beide kanten) terwijl deze melding er nog stond, en toen wees hij
        // ons de verkeerde kant op omdat het echte bezwaar ergens anders zat.
        const staat = await runInMainWorld("DESCRIBE_DESC", {});
        const rest = formulierklachten().filter((t) => !/advertentietekst|zoekertjestekst/i.test(t));
        // WIE ZIT ER NOG MEER IN DIT TABBLAD?
        //
        // Chrome laat ons niet aan de toetsen komen zodra er een stukje van een
        // ándere extensie in de pagina hangt. Dat is van buitenaf niet te zien,
        // dus vragen we het de pagina zelf: welke ingesloten kaders komen van
        // een extensie, en van welke. Zonder deze regel blijft het gissen welke
        // extensie in de weg zit.
        const vreemdeKaders = [...document.querySelectorAll("iframe, embed, object")]
          .map((f) => f.src || f.data || "")
          .filter((u) => u.startsWith("chrome-extension://"))
          .map((u) => u.slice(19, 51))
          .filter((id, i, a) => a.indexOf(id) === i);
        const magTypen = await new Promise((res) => {
          try { chrome.runtime.sendMessage({ type: "HEEFT_DEBUGGER" }, (r) => res(!!r)); }
          catch (_) { res(false); }
        });
        throw new Error(
          `The form kept treating the description as empty, even after re-filling it. ` +
          (magTypen ? "" : "Marktplaats only accepts this text after a real keystroke — "
            + "switch on \"Let Omnivaleur type like a keyboard\" in the extension menu and try again. ") +
          `Real keystroke: ${laatsteToets}. ` +
          (vreemdeKaders.length
            ? `Other extensions inside this tab: ${vreemdeKaders.join(", ")}. `
            : "No other extension frames in this tab. ") +
          `What the form actually held — ${staat}` +
          (rest.length ? ` | Other complaints on the page: ${rest.join(" | ")}` : ` | No other complaints on the page.`)
        );
      }
    }

    const uniq = formulierklachten();
    const rood = roodGemarkeerdeVelden();
    // WAT STAAT ER OP HET SCHERM OP HET MOMENT VAN MISLUKKEN?
    //
    // Geen rood veld, geen klacht, en tóch geen advertentie: dan is de vraag
    // niet "wat mist er" maar "waar zijn we beland". Een extra stap voor
    // zakelijke verkopers, een venster over het formulier heen, een knop die
    // ineens uitstaat — dat zie je alleen aan de pagina zelf. Alleen het adres
    // en de eerste regels tekst; nooit iets uit de invoervelden.
    const waar = location.pathname + location.search.slice(0, 40);
    const zichtbaar = (document.body.innerText || "").replace(/\s+/g, " ").trim().slice(0, 220);
    const knopStand = btn
      ? `knop "${(btn.textContent || "").trim().slice(0, 30)}"${btn.disabled ? " (uitgeschakeld)" : ""}`
      : "knop weg";
    clog(`plaatsen: mislukt — ${uniq.join(" | ") || "geen foutmelding op de pagina"}`
       + (rood.length ? ` | rode velden: ${rood.join(", ")}` : ""));
    throw new Error(
      `Not published — complete the fields marked in red and click publish yourself. `
      + (uniq.length ? `${uniq.join(" | ")} ` : "")
      + (rood.length ? `| Fields marked invalid: ${rood.join(", ")} ` : "| No field is marked invalid. ")
      + `| Real click: ${_laatsteEchteKlik} | Still on ${waar}, ${knopStand} `
      + `| Attribute fields: ${keuzeveldenKort()} | Form's own description length: ${_echteBeschrijvingLengte} `
      + `| Free option: ${_laatsteGratisKlik} | Price field: ${(qs('input[name="price.value"]') || {}).value || "LEEG"} | Page says: ${zichtbaar}`
    );
  }

  async function waitForListingUrl(extraMatcher, timeout) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const href = location.href;

      // Detect logout/session expiry redirect — throw so tab stays open for user
      if (/\/(login|inloggen|signin|account\/login)/i.test(href)) {
        throw new Error("You were logged out while publishing — sign in again and click publish yourself");
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
      throw new Error("Minimum bid: the amount field never appeared on the form");
    }

    const val = bidInput.type === "number" ? String(minBid) : String(minBid.toFixed(2)).replace(".", ",");
    await fillInputHuman(bidInput, val);
    await sleep(300);
    // Verify rather than assume: React can reset a value it didn't like.
    if (!(bidInput.value || "").trim()) {
      throw new Error("Minimum bid: the page reset the amount");
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
    sleep, waitUntil, qs, waitForEl, fillInput, fillInputHuman, fillNativeSelect, clickRadioByValue, fillDescription,
    findFieldByLabel, selectDropdown, fillBrand, fillManufacturer, selectBundleFree,
    selectDelivery, gekozenLevering, selectPakketWaarde, vulHalswijdte, keuzeveldenKort, typBeschrijvingEcht,
    selectPackageSize, uploadPhotos, submitListing, step, closePopup, smartTrunc, fillBidding,
    clog, plaatsBlokkade, dutchColor, verifyMpGroupFields, repairMpGroupFields, ensureDescriptionStillFilled, selectCondition, selectIntendedFor, fillBrandField, logMpFields, mpPrijs,
  };
})();
