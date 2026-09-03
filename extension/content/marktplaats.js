// Content script for marktplaats.nl/plaats/* — uses the shared CL engine.
(async () => {
  const PLATFORM = "marktplaats";
  const { step, clog, qs, sleep, waitForEl, fillInput, fillInputHuman, fillDescription, selectDropdown,
          fillBrand, fillBrandField, fillManufacturer, selectBundleFree, selectDelivery, selectPakketWaarde, typBeschrijvingEcht, vulHalswijdte, uploadPhotos, submitListing,
          clickRadioByValue, smartTrunc, fillBidding, dutchColor,
          ensureDescriptionStillFilled, verifyMpGroupFields, repairMpGroupFields, selectCondition, selectIntendedFor, mpPrijs,
          mpPrijsvorm, kiesPrijsvorm, MP_ZONDER_BEDRAG } = window.CL;

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
      // Marktplaats/2dehands hebben GEEN werkende /v/listing/{id}-vorm: die geeft
      // 404, ook voor een advertentie die gewoon online staat. Een verzonnen link
      // is niet alleen een dode knop in het dashboard — de verwijderroute
      // gebruikte hem om te controleren of iets nog leeft, kreeg 404, en
      // concludeerde "al weg" terwijl de advertentie er nog stond. Neem daarom de
      // echte pagina waar we na het plaatsen op belanden.
      const echteUrl = /\/v\//.test(location.href) ? location.href.split("?")[0] : `https://www.marktplaats.nl/seller/view/${id}`;
      send("JOB_DONE", { platform_listing_id: id, platform_listing_url: echteUrl });
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

  // ── Audio, tv en foto: "Type" en "Wattage" ────────────────────────────────
  //
  // Waarom dit bestaat: dezelfde reden als mpSportType hierboven. Deze velden
  // zijn NIET verplicht — een advertentie komt zonder ook gewoon online — maar
  // wie in de zoekfilters op "Type" of "Wattage" filtert, krijgt een advertentie
  // zonder die waarde simpelweg niet te zien. Dat is stille onzichtbaarheid.
  //
  // De keuzelijsten hieronder zijn niet bedacht maar OPGEHAALD, op 27-08-2026,
  // uit de facetten van Marktplaats' eigen zoek-API:
  //   /lrp/api/search?l1CategoryId=31&l2CategoryId={cat3}  →  facets[key=type|power]
  // Dat is dezelfde lijst die een koper in de filterbalk ziet. Ze staan hier
  // WOORDELIJK; een zelfbedachte waarde wordt door het formulier genegeerd en is
  // dan niet van "niet ingevuld" te onderscheiden.
  //
  // 39 van de 68 audio-categorieën hebben een Type, en maar twee een Wattage.
  // De indeling van Wattage verschilt per categorie — luidsprekers kent
  // "120 tot 150 watt", versterkers niet — dus die grenzen staan apart.
  //
  // Alleen Marktplaats. Voor 2dehands is niet nagemeten of dezelfde labels daar
  // bestaan, en een gok zou hier precies het probleem zijn dat we oplossen.
  const MP_AUDIO_TYPE = {
    "luidsprekers": ["Boekenplank luidspreker", "Center speaker", "Draagbare speaker", "Party speaker", "Slimme speaker", "Speakerset", "Stereo speakers", "Studiomonitor", "Subwoofer", "Surroundset", "Vloerstaande luidspreker", "Overige typen"],
    "koptelefoons": ["Bone conduction", "Gaming", "Gehoorbeschermer", "In-ear", "On-ear", "Open-ear", "Over-ear", "Studio / DJ", "Overige typen"],
    "buizenversterkers": ["Versterker", "Buis of Buizen", "Overige onderdelen", "Toebehoren"],
    "platenspelers": ["Platenspeler", "Platenspeler-onderdeel"],
    "dvd spelers": ["Dvd-speler", "Dvd-recorder"],
    "videospelers": ["VHS-speler of -recorder", "Video 2000-speler of -recorder", "Betamax-speler of -recorder", "Videoband", "Overige typen"],
    "cassettedecks": ["Enkel", "Dubbel"],
    "bandrecorders": ["Bandrecorder", "Defecte bandrecorder", "Onderdeel"],
    "radio s": ["Radio", "Bouwradio", "Transistorradio", "Wereldontvanger", "Overige typen"],
    "walkmans en discmans": ["Walkman", "Discman", "Minidisc-speler", "Minidisc-recorder", "Overige typen"],
    "mp3 spelers ipod": ["Classic", "Mini", "Nano", "Photo", "Shuffle", "Touch", "Overige types"],
    "mp3 accessoires ipod": ["Dock of Kabel", "Carkit of Auto-accessoire", "Opberg- of Beschermhoesje", "Koptelefoon", "Speaker", "Voeding", "Overige typen"],
    "mp3 accessoires overige": ["Dock of Kabel", "Carkit of Auto-accessoire", "Opberg- of Beschermhoesje", "Koptelefoon", "Speaker", "Voeding", "Overige typen"],
    "karaoke apparatuur": ["Complete set", "Luidspreker(s)", "Microfoon(s)", "Mixer", "Speler", "Versterker of Tuner", "Overige typen"],
    "professionele audio en video": ["Audio", "Tv en Weergevers", "Video"],
    "televisies": ["LCD", "LED", "OLED", "QLED"],
    "afstandsbedieningen": ["Origineel", "Universeel"],
    "decoders en harddiskrecorders": ["Decoder", "Harddiskrecorder"],
    "schotelantennes": ["(Schotel)antenne", "(Schotel)antenne-accessoires"],
    "audio en tv kabels": ["Scartkabel", "Luidsprekerkabel", "Tv-kabel", "Coaxiale kabel", "Optische kabel", "HDMI-kabel", "Componentkabel", "Interlink-kabel", "Overige kabels"],
    "videobewaking": ["Binnencamera", "Buitencamera"],
    "fotocamera s digitaal": ["Bridgecamera", "Cinemacamera", "Compactcamera", "Instant camera", "Kindercamera", "Spiegelreflex", "Systeemcamera", "Vlogcamera", "Wildcamera", "Overige typen"],
    "fotocamera s analoog": ["Compact", "Spiegelreflex", "Polaroid"],
    "onderwatercamera s": ["Accessoires", "Camera", "Complete set", "Dome port", "Onderwaterflitser", "Onderwaterhuis", "Smartphonebehuizing", "Overige typen"],
    "videocamera s digitaal": ["Camera", "Band, Disc of Geheugen", "Overige typen"],
    "videocamera s analoog": ["Camera", "(Video)band", "Overige typen"],
    "lenzen en objectieven": ["Fisheye-lens", "Groothoeklens", "Macrolens", "Standaardlens", "Telelens", "Toebehoren", "Voorzetlens/converter", "Overige typen"],
    "filters": ["Beschermfilter", "Effectfilter", "Filterset", "Kleurfilter", "Macro-filter", "ND-filter", "Polarisatiefilter", "Skylightfilter", "Softfilter", "UV-filter", "Overige typen"],
    "statieven en balhoofden": ["Balhoofd", "Driepoot", "Eenpoot", "Gimbal", "L-bracket", "Ministatief", "Selfiestick", "Slider", "Statiefkop", "Overige typen"],
    "fototassen": ["Heuptas", "Hoes", "Koffer", "Lenstas", "Pouch", "Rolkoffer", "Rugtas", "Schoudertas", "Slingtas", "Overige typen"],
    "geheugenkaarten": ["CFexpress Type B", "Compact Flash (CF)", "CompactFlash", "Memory stick", "MicroSD", "MicroSDHC", "MicroSDXC", "SD", "SDHC", "SDXC", "XD", "XQD", "Overige typen"],
    "fotostudio en toebehoren": ["Achtergrond", "Complete fotostudio", "Lamp of Flitsset", "Mini fotostudio", "Statief", "Studioflitser", "Studiolamp", "Overige typen"],
    "doka toebehoren": ["Belichtingsmeter", "Complete dokaset", "Dokalamp", "Focushulp", "Fotodroger", "Kleurenaccessoire", "Ontwikkeltank", "Overig typen", "Snijder", "Timer", "Vergroter", "Vergrotingsaccessoire"],
    "filmrollen": ["8mm film", "16mm film", "35mm film", "Accessoire"],
    "fotoalbums en accessoires": ["Bewaarbox", "Dia-accessoire", "Fotoalbum-accessoire", "Fotomap", "Insteekalbum", "Losbladig album", "Plakboek", "Spiraalalbum", "Thema-album", "Overige typen"],
    "verrekijkers": ["Dakkant (recht)", "Porro (met knik)", "Overige typen"],
    "telescopen": ["Lenzentelescoop (refractor)", "Spiegeltelescoop (reflector)", "Onderdelen of Toebehoren"],
    "microscopen": ["Biologische microscoop", "Stereomicroscoop", "Onderdelen of Toebehoren"],
    "weerstations en barometers": ["Weerstation", "Barometer"],
  };

  const MP_AUDIO_WATT = {
    "luidsprekers": [[0, 60, "Minder dan 60 watt"], [60, 120, "60 tot 120 watt"], [120, 150, "120 tot 150 watt"], [150, null, "150 watt of meer"]],
    "versterkers en receivers": [[0, 60, "Minder dan 60 watt"], [60, 120, "60 tot 120 watt"], [120, null, "120 watt of meer"]],
  };

  // Woorden die hetzelfde betekenen als een optie maar er niet in staan. Klein
  // en handmatig gehouden: het label zelf wordt altijd eerst geprobeerd, dit is
  // alleen de brug van het Engels (en van hoe verkopers het echt opschrijven)
  // naar het Nederlandse label.
  const MP_AUDIO_SYNONIEMEN = {
    "Boekenplank luidspreker": ["bookshelf"],
    "Vloerstaande luidspreker": ["floorstanding", "vloerstaand", "zuilspeaker"],
    "Draagbare speaker": ["portable speaker", "bluetooth speaker"],
    "Studiomonitor": ["studio monitor", "monitorspeaker"],
    "Subwoofer": ["sub woofer"],
    "In-ear": ["earbuds", "oordopjes", "oortjes"],
    "Over-ear": ["overear"],
    "On-ear": ["onear"],
    "Spiegelreflex": ["dslr", "slr"],
    "Systeemcamera": ["mirrorless", "systeem camera"],
    "Compactcamera": ["compact camera", "point and shoot"],
    "Groothoeklens": ["groothoek", "wide angle", "wideangle"],
    "Telelens": ["telephoto", "tele lens"],
    "Macrolens": ["macro lens"],
    "Fisheye-lens": ["fisheye", "vissenoog"],
    "Rugtas": ["rugzak", "backpack"],
    "Schoudertas": ["shoulder bag"],
    "MicroSD": ["micro sd"],
    "Polarisatiefilter": ["polarisatie", "cpl filter", "circular polarizer"],
  };

  // Marktplaats schrijft zijn vangnet-optie op drie manieren ("Overige typen",
  // "Overige types", "Overig typen"). Nooit zelf een variant verzinnen: pak de
  // vorm die in DEZE lijst staat, of vul niets in.
  function mpAudioRest(opties) {
    return opties.find(o => /^overige?\s+type/i.test(o)) || null;
  }

  function mpAudioPlat(tekst) {
    return ` ${String(tekst || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()} `;
  }

  // Zoeken op de kale tekst is niet genoeg: een verkoper schrijft "vloerstaande
  // luidsprekers" en het label is "Vloerstaande luidspreker". Zonder buiging
  // viel dat terug op "Overige typen" — precies de zichtbaarheid die we hier
  // juist willen winnen. Daarom mag het LAATSTE woord een Nederlandse uitgang
  // dragen (-e, -en, -s, -es). Alleen het laatste: alles vrijgeven zou van
  // "Enkel" ook "enkele kabels" maken.
  function mpAudioRegex(zin) {
    const woorden = mpAudioPlat(zin).trim().split(" ").filter(Boolean);
    if (!woorden.length) return null;
    const esc = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const kop = woorden.slice(0, -1).map(esc);

    // Het laatste woord in al zijn Nederlandse meervouds- en verbogen vormen.
    // De gewone uitgangen dekken "luidspreker(s)" en "vloerstaand(e)", maar niet
    // de klankwisseling: het meervoud van "lens" is "lenzen" en van "brief"
    // "brieven". Zonder die twee regels viel "Canon telelenzen" terug op
    // "Overige typen".
    const laatste = woorden[woorden.length - 1];
    const vormen = [esc(laatste) + "(?:e|en|s|es)?"];
    if (/s$/.test(laatste)) vormen.push(esc(laatste.slice(0, -1)) + "zen");
    if (/f$/.test(laatste)) vormen.push(esc(laatste.slice(0, -1)) + "ven");
    const staart = `(?:${vormen.join("|")})`;

    return new RegExp(`(?:^| )${[...kop, staart].join(" ")}(?= |$)`);
  }

  // Geeft de Type-waarde voor dit artikel, of null. Null betekent "niets
  // invullen" en is altijd beter dan een verkeerd type: op een verkeerd type
  // filtert een koper de advertentie juist wég.
  function mpAudioType(item) {
    const cat = String(item?.category || "").toLowerCase().trim();
    if (!cat.startsWith("audio ")) return null;
    const opties = MP_AUDIO_TYPE[cat.slice(6)];
    if (!opties) return null;

    const hooi = mpAudioPlat(`${item?.title || ""} ${item?.description || ""}`);
    const rest = mpAudioRest(opties);
    // Langste eerst, anders wint "SD" van "MicroSDXC" en "Camera" van
    // "Cinemacamera". Het vangnet doet niet mee aan het zoeken zelf, anders
    // zou het woord "overige" in een advertentietekst het al triggeren.
    const kandidaten = opties.filter(o => o !== rest)
      .slice().sort((a, b) => b.length - a.length);

    for (const optie of kandidaten) {
      const woorden = [optie, ...(MP_AUDIO_SYNONIEMEN[optie] || [])];
      for (const w of woorden) {
        const re = mpAudioRegex(w);
        if (re && re.test(hooi)) return optie;
      }
    }
    return rest;
  }

  // Wattage alleen als er ECHT een getal met watt in de tekst staat. Geen getal
  // is geen wattage — raden zou hier hetzelfde kwaad doen als een fout type.
  function mpAudioWattage(item) {
    const cat = String(item?.category || "").toLowerCase().trim();
    if (!cat.startsWith("audio ")) return null;
    const vakken = MP_AUDIO_WATT[cat.slice(6)];
    if (!vakken) return null;

    const tekst = `${item?.title || ""} ${item?.description || ""}`;
    const m = tekst.match(/(\d{1,5})\s*(?:watt\b|w\b|wrms\b)/i);
    if (!m) return null;
    const watt = parseInt(m[1], 10);
    if (!Number.isFinite(watt) || watt <= 0 || watt > 20000) return null;

    for (const [onder, boven, label] of vakken) {
      if (watt >= onder && (boven === null || watt < boven)) return label;
    }
    return null;
  }

  async function fillForm(item) {
    await waitForEl('input[name="title_nl-NL"]', 20000);
    await step("title",        () => fillInputHuman(qs('input[name="title_nl-NL"]'), smartTrunc(item.title || "", 60)));
    // EERST DE ADVERTENTIEVORM, DAN PAS DE PRIJS (03-09-2026, Amanda Haas).
    //
    // Een artikel zonder vraagprijs is op Marktplaats geen fout maar een keuze:
    // "Bieden". Stond de lijst op "Vraagprijs" en het prijsveld leeg, dan
    // weigerde het formulier en bleef het tabblad open staan wachten op de
    // verkoper — met de oude advertentie al weg. Zie mpPrijsvorm in shared.js.
    //
    // De volgorde is niet vrij: bij "Bieden" verdwijnt het prijsveld, dus een
    // eerst ingevulde prijs is daarna weg.
    let vormError = null;
    const vorm = mpPrijsvorm(item);
    if (vorm) {
      try { await kiesPrijsvorm(vorm); }
      catch (e) { vormError = e; clog(`advertentievorm: FOUT — ${e && e.message ? e.message : e}`); }
    }
    if (!(vorm && MP_ZONDER_BEDRAG.has(vorm))) {
      await step("price",      () => { const el = qs('input[name="price.value"]'); return fillInputHuman(el, mpPrijs(item.price, el)); });
    }
    // NOT wrapped in step(): description and photos are mandatory on Marktplaats,
    // and step() swallows the error — which is how listings ended up submitted
    // with an empty advertentietekst and no photos, with nothing to explain it.
    // Let these throw so the job reports the real cause and keeps the tab open.
    // nudge: Marktplaats accepteert de tekst pas na een echte toetsaanslag.
    let descError = null;
    try {
      await fillDescription(['[data-testid="text-editor-input_nl-NL"]'], item.description, { nudge: true });
      // Nu pas echt typen: alleen dan telt de tekst mee bij het plaatsen.
      await step("echte tekst", () => typBeschrijvingEcht(item.description));
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
    await step("sporttype",    () => mpSportType(item) && selectDropdown("Type", mpSportType(item)));
    await step("audiotype",    () => { const t = mpAudioType(item);    return t && selectDropdown("Type", t); });
    await step("wattage",      () => { const w = mpAudioWattage(item); return w && selectDropdown("Wattage", w); });
    await step("size",         () => item.size && selectDropdown(["Maat", "Jeansmaat", "Maat (cm)", "Maat bovenstuk", "Maat onderstuk"], item.size));
    // Halswijdte werkt op getallen in plaats van op tekst; zie vulHalswijdte.
    await step("halswijdte",   () => vulHalswijdte(item));
    await step("color",        () => item.color && selectDropdown("Kleur", dutchColor(item.color)));
    await step("brand",        () => item.brand && fillBrandField(item.brand));
    await step("manufacturer", () => fillManufacturer(item));
    await step("delivery",     async () => { await selectDelivery(item); selectBundleFree(); });
    // Pakketgrootte hoorde hier helemaal niet: alleen 2dehands koos er een, dus
    // op Marktplaats bleef het leeg en moest de verkoper het per advertentie
    // zelf aanklikken. item.pakket komt uit zijn eigen instelling (onder de
    // prijsgrens brievenbuspakje, daarboven groot pakket).
    await step("package",      () => item.pakket && selectPakketWaarde(item.pakket));
    // "Bieden vanaf" hoort bij een vraagprijs. Zonder prijs is het minimumbod 0,
    // en dat is geen bod maar een leeg veld dat de advertentie tegenhoudt.
    await step("bidding",      () => item.bid_percentage && Number(item.price) > 0 && fillBidding(item.price, item.bid_percentage));

    await sleep(600);
    await repairMpGroupFields(item);

    // Lees het formulier terug voor we plaatsen — zie verifyMpGroupFields.
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
