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
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: `https://www.2dehands.be/v/listing/${id}` });
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

    if (!deleteEl) throw new Error("Verwijder button not found on listing " + listingId);
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

  async function fillForm(item) {
    await waitForEl('input[name="title_nl-BE"], input[name="title_nl-NL"]', 20000);
    await step("title",        () => fillInputHuman(titleInput(), smartTrunc(item.title || "", 60)));
    await step("price",        () => { const el = qs('input[name="price.value"]'); return fillInputHuman(el, el?.type === "number" ? String(item.price || "") : String(item.price || "").replace(".", ",")); });
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
