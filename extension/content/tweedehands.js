// Content script for 2dehands.be/plaats/* — uses the shared CL engine.
(async () => {
  const PLATFORM = "2dehands";
  const CONDITION_MAP = { new: "Nieuw", good: "Zo goed als nieuw", fair: "Gedragen", poor: "Beschadigd" };
  const { step, qs, sleep, waitForEl, fillInput, fillInputHuman, fillDescription, selectDropdown,
          fillBrand, fillManufacturer, selectBundleFree, selectPackageSize,
          uploadPhotos, submitListing, clickRadioByValue, smartTrunc, fillBidding } = window.CL;

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
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: `https://www.2dehands.be/seller/view/${id}` });
    }
  } catch (e) {
    send("JOB_ERROR", null, String(e)); // tab stays open
  }

  async function deleteListing2dh(listingId) {
    await waitForEl('[data-testid="my-listings-item"], .listing-card, article', 15000);
    await sleep(1000);

    const allLinks = [...document.querySelectorAll('a[href*="' + listingId + '"]')];
    if (!allLinks.length) throw new Error("Listing " + listingId + " not found on page — may already be deleted");

    const card = allLinks[0].closest('article, [data-testid*="listing"], li, .listing-card, tr') || allLinks[0].parentElement.parentElement;

    const actionsBtn = card.querySelector(
      'button[aria-label*="opties"], button[aria-label*="menu"], button[aria-label*="actions"], ' +
      '[data-testid*="action"], [data-testid*="kebab"], [data-testid*="more"]'
    );
    if (actionsBtn) {
      actionsBtn.click();
      await sleep(600);
    }

    const deleteEl = [...document.querySelectorAll('button, a, [role="menuitem"]')]
      .find(el => /verwijder/i.test(el.textContent));
    if (!deleteEl) throw new Error("Delete button not found for listing " + listingId);
    deleteEl.click();
    await sleep(800);

    const confirmBtn = [...document.querySelectorAll('button')]
      .find(el => /verwijder|bevestig|ok|ja\b/i.test(el.textContent));
    if (confirmBtn) {
      confirmBtn.click();
      await sleep(1000);
    }
  }

  // 2dehands only renders these 7 tags; anything else crashes the editor.
  function sanitize2dh(html) {
    if (!html) return "";
    const ALLOWED = new Set(["u", "em", "ul", "li", "p", "strong", "br"]);
    return html.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)[^>]*>/g, (match, tag) =>
      ALLOWED.has(tag.toLowerCase()) ? match : ""
    );
  }

  async function fillForm(item) {
    await waitForEl('input[name="title_nl-BE"], input[name="title_nl-NL"]', 20000);
    await step("title",        () => fillInput(titleInput(), smartTrunc(item.title || "", 60)));
    await step("price",        () => { const el = qs('input[name="price.value"]'); fillInput(el, el?.type === "number" ? String(item.price || "") : String(item.price || "").replace(".", ",")); });
    await step("description",  () => fillDescription(['[data-testid="text-editor-input_nl-BE"]', '[data-testid="text-editor-input_nl-NL"]'], sanitize2dh(item.description)));
    await step("photos",       () => item.photo_urls?.length && uploadPhotos(item.photo_urls.slice(0, 10)));
    await step("condition",    () => selectDropdown("Conditie", CONDITION_MAP[item.condition] || "Zo goed als nieuw"));
    await sleep(400); // let React re-render kenmerken after condition selection
    await step("package",      () => selectPackageSize());
    await step("size",         () => item.size && selectDropdown(["Maat", "Maat (cm)"], item.size));
    await step("color",        () => item.color && selectDropdown("Kleur", item.color));
    await step("brand",        () => item.brand && fillBrand(item.brand));
    await step("manufacturer", () => fillManufacturer(item));
    await step("delivery",     () => { clickRadioByValue("Ophalen of Verzenden"); selectBundleFree(); });
    await step("bidding",      () => item.bid_percentage && fillBidding(item.price, item.bid_percentage));
  }

  function titleInput() {
    return qs('input[name="title_nl-BE"]') || qs('input[name="title_nl-NL"]');
  }
  function getJob() {
    return new Promise((r) => chrome.storage.local.get(`job_${PLATFORM}`, (s) => r(s[`job_${PLATFORM}`] || null)));
  }
  function send(type, result, errorMsg) {
    chrome.runtime.sendMessage({ type, platform: PLATFORM, jobId, serverUrl, result, error: errorMsg });
  }
})();
