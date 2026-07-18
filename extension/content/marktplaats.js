// Content script for marktplaats.nl/plaats/* — uses the shared CL engine.
(async () => {
  const PLATFORM = "marktplaats";
  const CONDITION_MAP = { new_with_tags: "Nieuw", new: "Nieuw", good: "Zo goed als nieuw", fair: "Gedragen", poor: "Beschadigd" };
  const { step, qs, sleep, waitForEl, fillInput, fillInputHuman, fillDescription, selectDropdown,
          fillBrand, fillManufacturer, selectBundleFree, uploadPhotos, submitListing,
          clickRadioByValue, smartTrunc, fillBidding } = window.CL;

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

    if (!deleteEl) throw new Error("Verwijder button not found on listing " + listingId);
    deleteEl.click();
    await sleep(800);

    // Confirm dialog if it appears
    const confirmBtn = [...document.querySelectorAll('button')]
      .find(el => /verwijder|bevestig|ok|ja\b/i.test(el.textContent?.trim()));
    if (confirmBtn) { confirmBtn.click(); await sleep(1000); }
  }

  async function fillForm(item) {
    await waitForEl('input[name="title_nl-NL"]', 20000);
    await step("title",        () => fillInputHuman(qs('input[name="title_nl-NL"]'), smartTrunc(item.title || "", 60)));
    await step("price",        () => { const el = qs('input[name="price.value"]'); return fillInputHuman(el, el?.type === "number" ? String(item.price || "") : String(item.price || "").replace(".", ",")); });
    await step("description",  () => fillDescription(['[data-testid="text-editor-input_nl-NL"]'], item.description));
    await step("photos",       () => item.photo_urls?.length && uploadPhotos(item.photo_urls.slice(0, 20)));
    await step("condition",    () => selectDropdown("Conditie", CONDITION_MAP[item.condition] || "Zo goed als nieuw"));
    await sleep(400); // let React re-render kenmerken after condition selection
    await step("size",         () => item.size && selectDropdown(["Maat", "Jeansmaat", "Maat (cm)", "Maat bovenstuk", "Maat onderstuk"], item.size));
    await step("color",        () => item.color && selectDropdown("Kleur", item.color));
    await step("brand",        () => item.brand && fillBrand(item.brand));
    await step("manufacturer", () => fillManufacturer(item));
    await step("delivery",     () => { clickRadioByValue("Ophalen of Verzenden"); selectBundleFree(); });
    await step("bidding",      () => item.bid_percentage && fillBidding(item.price, item.bid_percentage));
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
