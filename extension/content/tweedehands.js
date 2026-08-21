// Content script for 2dehands.be/plaats/* — uses the shared CL engine.
(async () => {
  const PLATFORM = "2dehands";
  const { step, clog, qs, sleep, waitForEl, fillInput, fillInputHuman, fillDescription, selectDropdown,
          fillBrand, fillBrandField, fillManufacturer, selectBundleFree, selectDelivery, selectPackageSize, typBeschrijvingEcht,
          uploadPhotos, submitListing, clickRadioByValue, smartTrunc, fillBidding,
          dutchColor, ensureDescriptionStillFilled, verifyMpGroupFields, repairMpGroupFields, selectCondition, selectIntendedFor, mpPrijs } = window.CL;

  const job = await getJob();
  if (!job) return;
  const { id: jobId, serverUrl, payload: item } = job;

  try {
    if (job.action === "delete") {
      await deleteListing2dh(item.platform_listing_id);
      send("JOB_DONE", {});
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
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: echteUrl });
    }
  } catch (e) {
    send("JOB_ERROR", null, String(e)); // tab stays open
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
    await step("title",        () => fillInputHuman(titleInput(), smartTrunc(item.title || "", 60)));
    await step("price",        () => { const el = qs('input[name="price.value"]'); return fillInputHuman(el, mpPrijs(item.price, el)); });
    // Mandatory fields — deliberately NOT inside step(), see marktplaats.js.
    // nudge: ook 2dehands rekent de tekst pas mee na een echte toetsaanslag.
    await fillDescription(['[data-testid="text-editor-input_nl-BE"]', '[data-testid="text-editor-input_nl-NL"]'], sanitize2dh(item.description), { nudge: true });
    // Nu pas echt typen: alleen wat er echt getypt is telt mee bij het plaatsen.
    await step("echte tekst", () => typBeschrijvingEcht(sanitize2dh(item.description)));
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
    await step("delivery",     async () => { await selectDelivery(item); selectBundleFree(); });
    await step("bidding",      () => item.bid_percentage && fillBidding(item.price, item.bid_percentage));

    await sleep(600);
    await repairMpGroupFields(item);

    // Zelfde controle als op Marktplaats: 2dehands draait hetzelfde formulier,
    // maar plaatste tot nu toe zonder terug te lezen — dus met stille gaten.
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
