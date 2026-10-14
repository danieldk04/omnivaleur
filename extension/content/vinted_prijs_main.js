// DE PRIJS IN DE PAGINA ZETTEN (MAIN world).
//
// Dit bestand doet twee dingen:
//   1. In de achtergrond (importScripts in background.js) levert het de functie
//      _mwSetVintedPrice voor SET_PRICE_MAIN, de route via executeScript.
//   2. Op het Vinted-formulier staat het vanaf het laden klaar in de pagina zelf
//      (content_scripts met "world": "MAIN") en luistert het naar een vraag van
//      vinted.js. Waarom (13-10-2026, Janneke): op Chrome 128 kreeg een tabblad
//      op de achtergrond een ingespoten functie soms helemaal niet aan de beurt.
//      Gemeten: 44 s geen antwoord, ook met de nieuwe pauzes. Een gebeurtenis op
//      de pagina komt direct binnen bij wie er al staat, dus dit hoeft niet op
//      Chrome te wachten. Vraag en antwoord gaan als tekst (JSON), want een
//      object uit de ene wereld is in de andere niet leesbaar.

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
  // GEEN PAGINAKLOK (13-10-2026, Janneke). Deze functie draait IN de pagina en
  // had zes pauzes via setTimeout. Zet Chrome het tabblad stil (één tik per
  // minuut), dan duurde de prijs zes minuten en liep de klus na drie minuten af,
  // elf keer op rij net na de rubriek. Een berichtje via MessageChannel wordt
  // niet afgeknepen; daarmee kijken we telkens of de tijd om is. setTimeout
  // loopt ernaast voor als dat ooit anders wordt.
  const sleep = (ms) => new Promise((r) => {
    const tot = Date.now() + ms;
    let klaar = false;
    const af = () => { if (!klaar) { klaar = true; r(); } };
    setTimeout(af, ms);
    const kanaal = new MessageChannel();
    kanaal.port1.onmessage = () => {
      if (klaar || Date.now() >= tot) { kanaal.port1.close(); af(); return; }
      kanaal.port2.postMessage(0);
    };
    kanaal.port2.postMessage(0);
  });
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

if (typeof document !== "undefined" && typeof window !== "undefined" && !window.__ovPrijsMain) {
  window.__ovPrijsMain = true;
  document.addEventListener("ov-prijs-vraag", async (e) => {
    let v;
    try { v = JSON.parse(e.detail); } catch (_) { return; }
    let r;
    try { r = await _mwSetVintedPrice(v.selector, v.values); }
    catch (err) { r = { ok: false, reason: String((err && err.message) || err).slice(0, 120) }; }
    document.dispatchEvent(new CustomEvent("ov-prijs-antwoord", { detail: JSON.stringify({ id: v.id, r }) }));
  });
  document.documentElement.setAttribute("data-ov-prijs-main", "1");
}
