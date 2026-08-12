// Content script for marktplaats.nl/plaats/* — uses the shared CL engine.
(async () => {
  const PLATFORM = "marktplaats";
  const { step, clog, qs, sleep, waitForEl, fillInput, fillInputHuman, fillDescription, selectDropdown,
          fillBrand, fillBrandField, fillManufacturer, selectBundleFree, uploadPhotos, submitListing,
          clickRadioByValue, smartTrunc, fillBidding, dutchColor,
          ensureDescriptionStillFilled, verifyMpGroupFields, repairMpGroupFields, selectCondition, selectIntendedFor } = window.CL;

  const job = await getJob();
  if (!job) return;
  const { id: jobId, serverUrl, payload: item } = job;

  try {
    if (job.action === "delete") {
      await deleteListingMp(item.platform_listing_id);
      send("JOB_DONE", {});
    } else {
      await fillForm(item);
      const id = await submitListing(/marktplaats\.nl\/v\/[^/]+\/(m\d+)/);
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: `https://www.marktplaats.nl/v/listing/${id}` });
    }
  } catch (e) {
    send("JOB_ERROR", null, String(e)); // tab stays open (background no longer closes it)
  }

  async function deleteListingMp(listingId) {
    // We land on /v/listing/{id} — the listing detail page.
    // Wait for page to render, then find the delete action.
    await sleep(2500);

    async function findAndClickDelete() {
      return [...document.querySelectorAll('button, a, [role="menuitem"], [role="option"], li')]
        .find(el => /verwijder/i.test(el.textContent?.trim()));
    }

    // 1. Check if delete is directly visible
    let deleteEl = await findAndClickDelete();

    // 2. Try every button that looks like a menu/options trigger
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

    // Confirm dialog if it appears
    const confirmBtn = [...document.querySelectorAll('button')]
      .find(el => /verwijder|bevestig|ok|ja\b/i.test(el.textContent?.trim()));
    if (confirmBtn) { confirmBtn.click(); await sleep(1000); }
  }

  // Marktplaats vraagt bij sportkleding om een "Type", en de keuzelijst verschilt
  // per geslacht. Live afgelezen op het plaatsformulier (aug. 2026):
  //   heren: Algemeen · Fitness · Hardlopen of Fietsen · Racketsport · Vechtsport ·
  //          Voetbal · Wandelen of Outdoor · Overige typen
  //   dames: Fitness of Aerobics · Hardlopen of Fietsen · Racketsport · Yoga ·
  //          Overige typen
  // Zonder dit veld staat elk sportartikel zonder type in de zoekfilters, en
  // filtert een koper op "Hardlopen of Fietsen" de advertentie dus gewoon weg.
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
    await waitForEl('input[name="title_nl-NL"]', 20000);
    await step("title",        () => fillInputHuman(qs('input[name="title_nl-NL"]'), smartTrunc(item.title || "", 60)));
    await step("price",        () => { const el = qs('input[name="price.value"]'); return fillInputHuman(el, el?.type === "number" ? String(item.price || "") : String(item.price || "").replace(".", ",")); });
    // NOT wrapped in step(): description and photos are mandatory on Marktplaats,
    // and step() swallows the error — which is how listings ended up submitted
    // with an empty advertentietekst and no photos, with nothing to explain it.
    // Let these throw so the job reports the real cause and keeps the tab open.
    // nudge: Marktplaats accepteert de tekst pas na een echte toetsaanslag.
    await fillDescription(['[data-testid="text-editor-input_nl-NL"]'], item.description, { nudge: true });
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
    await step("sporttype",    () => mpSportType(item) && selectDropdown("Type", mpSportType(item)));
    await step("size",         () => item.size && selectDropdown(["Maat", "Jeansmaat", "Maat (cm)", "Maat bovenstuk", "Maat onderstuk"], item.size));
    await step("color",        () => item.color && selectDropdown("Kleur", dutchColor(item.color)));
    await step("brand",        () => item.brand && fillBrandField(item.brand));
    await step("manufacturer", () => fillManufacturer(item));
    await step("delivery",     () => { clickRadioByValue("Ophalen of Verzenden"); selectBundleFree(); });
    await step("bidding",      () => item.bid_percentage && fillBidding(item.price, item.bid_percentage));

    await sleep(600);
    await repairMpGroupFields(item);

    // Lees het formulier terug voor we plaatsen — zie verifyMpGroupFields.
    if (photoError) throw photoError;
    // De advertentietekst is als eerste ingevuld, maar daarna zijn er foto's
    // geüpload en kenmerken gekozen — elke herteken-ronde kan de editor
    // opnieuw opbouwen en de tekst wissen. Hier kijken we of hij er nog staat.
    await ensureDescriptionStillFilled();
    verifyMpGroupFields(item);
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
