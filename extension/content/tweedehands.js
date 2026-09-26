// Content script for 2dehands.be/plaats/* — uses the shared CL engine.
(async () => {
  const PLATFORM = "2dehands";
  const { step, clog, qs, sleep, waitForEl, fillInput, fillInputHuman, fillDescription, selectDropdown,
          fillBrand, fillBrandField, fillManufacturer, vulLocatie, selectBundleFree, selectDelivery, selectPackageSize, zetVerzendkosten, centenUitTekst, waitUntil, typBeschrijvingEcht,
          uploadPhotos, submitListing, clickRadioByValue, smartTrunc, fillBidding, zetBieden,
          dutchColor, ensureDescriptionStillFilled, verifyMpGroupFields, repairMpGroupFields, selectCondition, selectIntendedFor, mpPrijs,
          mpPrijsvorm, kiesPrijsvorm, MP_ZONDER_BEDRAG, zetPrijs } = window.CL;

  const job = await getJob();
  if (!job) return;
  let verzendingGezet = false;   // zie de stap "verzendkosten" in fillForm
  const { id: jobId, serverUrl, payload: item } = job;
  // EERSTE LEVENSTEKEN, VÓÓR HET EERSTE WACHTEN.
  // Zonder dit was "de opdracht is opgehaald" en "het formulier stond er niet"
  // van buitenaf niet te onderscheiden: allebei leverden ze drie minuten stilte
  // op. Zie meldStapAanServer in background.js.
  clog(`start ${job.action || "create"} — formulierpagina geladen`);

  try {
    if (job.action === "delete") {
      await deleteListing2dh(item.platform_listing_id);
      send("JOB_DONE", {});
    } else if (job.action === "content_refresh") {
      // Een bestaand zoekertje bijwerken. NOOIT doorvallen naar het
      // plaatsformulier hieronder: dat zou titel, tekst en foto's opnieuw
      // invullen op een advertentie die al online staat.
      send("JOB_DONE", await verzendingBijwerken(item));
    } else {
      await fillForm(item);
      const id = await submitListing(/2dehands\.be\/v\/[^/]+\/(m\d+)/);
      // Marktplaats/2dehands hebben GEEN werkende /v/listing/{id}-vorm: die geeft
      // 404, ook voor een advertentie die gewoon online staat. Een verzonnen link
      // is niet alleen een dode knop in het dashboard — de verwijderroute
      // gebruikte hem om te controleren of iets nog leeft, kreeg 404, en
      // concludeerde "al weg" terwijl de advertentie er nog stond. Neem daarom de
      // echte pagina waar we na het plaatsen op belanden.
      const echteUrl = /\/v\//.test(location.href) ? location.href.split("?")[0] : `https://www.2dehands.be/seller/view/${id}`;
      // verzending_gezet: kreeg dit zoekertje het eigen verzendbedrag? Zo niet,
      // dan zet de server vanzelf een bijwerking klaar (zie jobs.py).
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: echteUrl,
                         verzending_gezet: verzendingGezet });
    }
  } catch (e) {
    send("JOB_ERROR", null, String(e)); // tab stays open
  }

  // DE VERZENDKOSTEN VAN EEN ZOEKERTJE DAT AL ONLINE STAAT (26-09-2026).
  //
  // Egbert Brouwer had 116 patches op 2dehands met Bpost EUR 7,10, terwijl hij ze
  // op Marktplaats zelf verstuurt voor zijn eigen bedrag. Het wijzigformulier
  // (/plaats/m{id}/edit) is hetzelfde formulier als het plaatsformulier, al
  // ingevuld. Live nagemeten op een eigen zoekertje: "Zelf versturen" plus bedrag
  // zetten en op Opslaan klikken landt op /seller/view/m{id} met "Je zoekertje is
  // aangepast", en de openbare pagina toont het nieuwe bedrag. Een klik vanuit het
  // script (button.click()) doet op Opslaan NIETS; alleen een echte muisklik telt.
  //
  // Alleen de verzendkosten: niets anders op het formulier wordt aangeraakt. Lukt
  // het niet om het bedrag te zetten, dan wordt er niet opgeslagen.
  async function verzendingBijwerken(item) {
    const v = (item && item.verzending) || {};
    if (!item || !item._verzending_bijwerken || v.soort !== "zelf" || !Number.isInteger(v.cents)) {
      throw new Error("This 2dehands update carries no shipping cost to set, so nothing was changed.");
    }
    const formulier = await waitUntil(() => qs('input[name="shippingMethod"]'), 20000);
    if (!formulier) {
      throw new Error("The 2dehands edit form did not show a shipping choice, so nothing was changed. "
        + "Check that the listing is still online and offers shipping.");
    }
    const bedragGoed = () => {
      const gekozen = qs('input[name="shippingMethod"]:checked');
      const veld = qs('input[name="othersPrice"]');
      return !!(gekozen && gekozen.value === "diy" && veld && centenUitTekst(veld.value) === v.cents);
    };
    if (bedragGoed()) {
      clog("verzendkosten: stonden al goed, niets opgeslagen");
      return { verzending_bijgewerkt: false, al_goed: true };
    }
    const detail = await zetVerzendkosten(item);
    clog(`verzendkosten: ${detail}`);
    if (!bedragGoed()) {
      throw new Error(`The shipping cost could not be set on 2dehands (${detail}), so nothing was saved.`);
    }
    const achtergrond = (bericht) => new Promise((res) => {
      try { chrome.runtime.sendMessage(bericht, (r) => { void chrome.runtime.lastError; res(r); }); }
      catch (_) { res(null); }
    });
    // Zelfde volgorde als bij plaatsen (submitListing): de vraag "Site verlaten?"
    // uitzetten, laten weten dat er geklikt wordt, en dan een echte klik.
    await achtergrond({ type: "ONTWAPEN_AFSLUITVRAAG" });
    await achtergrond({ type: "SUBMIT_CLICKED" });
    const clickResult = await achtergrond({ type: "KLIK_ECHT", selector: '[data-testid="update-listing-submit-button"]' });
    clog(`opslaan: echte klik — ${typeof clickResult === "string" ? clickResult : JSON.stringify(clickResult)}`);
    // Na het opslaan verlaat 2dehands het wijzigformulier. Gebeurt dat met een
    // volledige paginawissel, dan sterft dit script hier en meldt de achtergrond
    // het af (zie bewerkingOpgeslagen2dh in background.js).
    const weg = await waitUntil(() => !/\/edit\b/.test(location.pathname), 20000);
    if (!weg) {
      throw new Error(`2dehands did not save the new shipping cost (click: ${clickResult}). Nothing was changed.`);
    }
    return { verzending_bijgewerkt: true };
  }

  async function deleteListing2dh(listingId) {
    // We land on /v/listing/{id} — the listing detail page.
    await sleep(2500);

    async function findAndClickDelete() {
      return [...document.querySelectorAll('button, a, [role="menuitem"], [role="option"], li')]
        .find(el => /verwijder/i.test(el.textContent?.trim()));
    }

    let deleteEl = await findAndClickDelete();

    if (!deleteEl) {
      const triggers = [...document.querySelectorAll('button, [role="button"]')].filter(el => {
        const label = (el.textContent + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
        return /opties|meer|beheer|\.\.\.|menu|actions/i.test(label) || el.querySelector('svg');
      });
      for (const btn of triggers) {
        btn.click();
        await sleep(500);
        deleteEl = await findAndClickDelete();
        if (deleteEl) break;
      }
    }

    if (!deleteEl) throw new Error("The delete button could not be found on listing " + listingId);
    deleteEl.click();
    await sleep(800);

    const confirmBtn = [...document.querySelectorAll('button')]
      .find(el => /verwijder|bevestig|ok|ja\b/i.test(el.textContent?.trim()));
    if (confirmBtn) { confirmBtn.click(); await sleep(1000); }
  }

  // 2dehands only renders these 7 tags; anything else crashes the editor.
  function sanitize2dh(html) {
    if (!html) return "";
    const ALLOWED = new Set(["u", "em", "ul", "li", "p", "strong", "br"]);
    return html.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)[^>]*>/g, (match, tag) =>
      ALLOWED.has(tag.toLowerCase()) ? match : ""
    );
  }

  // 2dehands gebruikt dezelfde categorieboom als Marktplaats en vraagt bij
  // sportkleding ook om een "Type". Zie de toelichting in marktplaats.js.
  function mpSportType(item) {
    const cat = String(item?.category || "").toLowerCase();
    const dames = !/^heren\b/.test(cat) && String(item?.gender || "").toLowerCase() === "dames";
    if (/wielren|hardloop/.test(cat)) return "Hardlopen of Fietsen";
    if (/voetbal/.test(cat)) return dames ? "Overige typen" : "Voetbal";
    if (/gym/.test(cat)) return dames ? "Fitness of Aerobics" : "Fitness";
    if (/yoga/.test(cat)) return dames ? "Yoga" : "Algemeen";
    if (/ski/.test(cat)) return dames ? "Overige typen" : "Wandelen of Outdoor";
    if (/sport|trainingspak/.test(cat)) return dames ? "Overige typen" : "Algemeen";
    return null;
  }

  async function fillForm(item) {
    await waitForEl('input[name="title_nl-BE"], input[name="title_nl-NL"]', 20000);
    clog("titelveld staat er");
    await step("title",        () => fillInputHuman(titleInput(), smartTrunc(item.title || "", 60)));
    // 2dehands draait hetzelfde formulier als Marktplaats: eerst de
    // advertentievorm, dan de prijs, dan nakijken of hij er echt staat. Alle
    // drie zitten in zetPrijs (shared.js).
    const vormError = await zetPrijs(item);
    // Mandatory fields — deliberately NOT inside step(), see marktplaats.js.
    // nudge: ook 2dehands rekent de tekst pas mee na een echte toetsaanslag.
    let descError = null;
    try {
      await fillDescription(['[data-testid="text-editor-input_nl-BE"]', '[data-testid="text-editor-input_nl-NL"]'], sanitize2dh(item.description), { nudge: true });
      // Nu pas echt typen: alleen wat er echt getypt is telt mee bij het plaatsen.
      await step("echte tekst", () => typBeschrijvingEcht(sanitize2dh(item.description)));
    } catch (e) { descError = e; clog(`beschrijving: FOUT — ${e && e.message ? e.message : e}`); }
    // Foto's zijn verplicht, maar een mislukte upload mag niet de rest van het
    // formulier overslaan: dan blijft alles daarna leeg zonder dat iemand ziet
    // waarom. We onthouden de fout en melden hem pas aan het eind.
    let photoError = null;
    if (item.photo_urls?.length) {
      // Harde bovengrens: als het uploaden om welke reden dan ook blijft hangen,
      // gaan we door met de rest van het formulier in plaats van stil te blijven staan.
      try {
        const done = await Promise.race([
          uploadPhotos(item.photo_urls.slice(0, 20)).then(() => "ok"),
          sleep(120000).then(() => "timeout"),
        ]);
        if (done === "timeout") throw new Error("Uploading the photos took too long");
      }
      catch (e) { photoError = e; clog(`foto's: FOUT — ${e && e.message ? e.message : e}`); }
    }
    await step("condition",    () => selectCondition(item.condition));
    await step("intendedFor",  () => selectIntendedFor(item));
    await sleep(400); // let React re-render kenmerken after condition selection
    await step("package",      () => selectPackageSize());
    await step("sporttype",    () => mpSportType(item) && selectDropdown("Type", mpSportType(item)));
    await step("size",         () => item.size && selectDropdown(["Maat", "Maat (cm)"], item.size));
    await step("color",        () => item.color && selectDropdown("Kleur", dutchColor(item.color)));
    await step("brand",        () => item.brand && fillBrandField(item.brand));
    await step("manufacturer", () => fillManufacturer(item));
    // Waar de verkoper staat. Zonder deze stap neemt het formulier het
    // contactblok uit zijn account op deze site, en dat kan een Nederlandse
    // verkoper op 2dehands.be niet goed zetten. Zie vulLocatie in shared.js.
    await step("locatie", async () => clog(`locatie: ${await vulLocatie(item)}`));
    await step("delivery",     async () => { await selectDelivery(item); selectBundleFree(); });
    // Na de verzendwijze, want pas dan staat de keuze Bpost / Zelf versturen er.
    // Zijn eigen bedrag van Marktplaats in plaats van Bpost 0-2 kg (zie shared.js).
    await step("verzendkosten", async () => {
      const melding = await zetVerzendkosten(item);
      verzendingGezet = /^zelf versturen voor/.test(melding);
      clog(`verzendkosten: ${melding}`);
    });
    // "Bieden vanaf" hoort bij een vraagprijs; zonder prijs is het minimumbod 0.
    // Altijd zetten, ook als de verkoper GEEN bieden wil: de schakelaar
    // "Bieden toestaan" staat op het formulier standaard aan. Zie zetBieden.
    await step("bidding",      () => zetBieden(item));

    await sleep(600);
    await repairMpGroupFields(item);

    // Zelfde controle als op Marktplaats: 2dehands draait hetzelfde formulier,
    // maar plaatste tot nu toe zonder terug te lezen — dus met stille gaten.
    // EERST HET FORMULIER AFMAKEN, DAN PAS KLAGEN.
    //
    // De beschrijving werd hier als eerste ingevuld en gooide bij een probleem
    // meteen de hele invulbeurt weg. Gevolg voor de verkoper: een tabblad met
    // alleen een titel en een prijs, geen foto's, geen kenmerken — en een
    // melding die niet uitlegde waarom de rest ontbrak. Nu wordt alles
    // ingevuld en komt het bezwaar er pas achteraan, mét de echte reden.
    if (vormError) throw vormError;
    if (descError) throw descError;
    if (photoError) throw photoError;
    // De advertentietekst is als eerste ingevuld, maar daarna zijn er foto's
    // geüpload en kenmerken gekozen — elke herteken-ronde kan de editor
    // opnieuw opbouwen en de tekst wissen. Hier kijken we of hij er nog staat.
    await ensureDescriptionStillFilled();
    verifyMpGroupFields(item);
  }

  function titleInput() {
    return qs('input[name="title_nl-BE"]') || qs('input[name="title_nl-NL"]');
  }
  // Ask the background for THIS tab's own job (keyed by tab id), so two tabs can
  // never read each other's data. Retry briefly to cover the tab-open race.
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
