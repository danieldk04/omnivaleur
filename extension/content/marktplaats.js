// Content script for marktplaats.nl/plaats/* — uses the shared CL engine.
(async () => {
  const PLATFORM = "marktplaats";
  const CONDITION_MAP = { new: "Nieuw", good: "Zo goed als nieuw", fair: "Gedragen", poor: "Beschadigd" };
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
    // We land on the direct listing page (seller/view/{id}).
    // Wait for the page to load, then find and click delete.
    await sleep(2000);

    // Try kebab / options menu first (may be inside an action bar)
    const actionsBtn = document.querySelector(
      'button[aria-label*="opties"], button[aria-label*="menu"], button[aria-label*="actions"], ' +
      '[data-testid*="action"], [data-testid*="kebab"], [data-testid*="more"], [aria-label*="Meer"]'
    );
    if (actionsBtn) {
      actionsBtn.click();
      await sleep(600);
    }

    // Find "Verwijder" button/link anywhere on page or in dropdown
    let deleteEl = [...document.querySelectorAll('button, a, [role="menuitem"], [role="option"]')]
      .find(el => /verwijder/i.test(el.textContent));

    // Fallback: look for a "..." / options button if delete not yet visible
    if (!deleteEl) {
      const moreBtn = [...document.querySelectorAll('button')]
        .find(el => /\.\.\.|opties|meer|beheer/i.test(el.textContent) || el.getAttribute('aria-label')?.match(/opties|meer|beheer/i));
      if (moreBtn) { moreBtn.click(); await sleep(600); }
      deleteEl = [...document.querySelectorAll('button, a, [role="menuitem"]')]
        .find(el => /verwijder/i.test(el.textContent));
    }

    if (!deleteEl) throw new Error("Delete button not found for listing " + listingId + " — check if already removed or page layout changed");
    deleteEl.click();
    await sleep(800);

    // Confirm deletion dialog
    const confirmBtn = [...document.querySelectorAll('button')]
      .find(el => /verwijder|bevestig|ok|ja\b/i.test(el.textContent));
    if (confirmBtn) {
      confirmBtn.click();
      await sleep(1000);
    }
  }

  async function fillForm(item) {
    await waitForEl('input[name="title_nl-NL"]', 20000);
    await step("title",        () => fillInputHuman(qs('input[name="title_nl-NL"]'), smartTrunc(item.title || "", 60)));
    await step("price",        () => { const el = qs('input[name="price.value"]'); return fillInputHuman(el, el?.type === "number" ? String(item.price || "") : String(item.price || "").replace(".", ",")); });
    await step("description",  () => fillDescription(['[data-testid="text-editor-input_nl-NL"]'], item.description));
    await step("photos",       () => item.photo_urls?.length && uploadPhotos(item.photo_urls.slice(0, 10)));
    await step("condition",    () => selectDropdown("Conditie", CONDITION_MAP[item.condition] || "Zo goed als nieuw"));
    await sleep(400); // let React re-render kenmerken after condition selection
    await step("size",         () => item.size && selectDropdown(["Maat", "Jeansmaat", "Maat (cm)", "Maat bovenstuk", "Maat onderstuk"], item.size));
    await step("color",        () => item.color && selectDropdown("Kleur", item.color));
    await step("brand",        () => item.brand && fillBrand(item.brand));
    await step("manufacturer", () => fillManufacturer(item));
    await step("delivery",     () => { clickRadioByValue("Ophalen of Verzenden"); selectBundleFree(); });
    await step("bidding",      () => item.bid_percentage && fillBidding(item.price, item.bid_percentage));
  }

  function getJob() {
    return new Promise((r) => chrome.storage.local.get(`job_${PLATFORM}`, (s) => r(s[`job_${PLATFORM}`] || null)));
  }
  function send(type, result, errorMsg) {
    chrome.runtime.sendMessage({ type, platform: PLATFORM, jobId, serverUrl, result, error: errorMsg });
  }
})();
