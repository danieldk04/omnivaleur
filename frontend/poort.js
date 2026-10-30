/*
 * De startpoort (Daniel, 30-10-2026).
 *
 * WAAROM. Een nieuwe klant zei dat het "niet werkt", terwijl hij de extensie niet
 * had, niet op Marktplaats was ingelogd of nog niets had ingelezen. Het
 * afvinklijstje op het dashboard (onboarding.js) is een advies: je kunt het
 * wegklikken, en het installatievenster had een "Not now"-knop. Dit bestand maakt er
 * een poort van. Zolang de voorbereiding niet klaar is, kom je niet in het
 * dashboard, en wijst een pijl naar de volgende handeling.
 *
 * Vier fasen, puur uit feiten (nooit uit een klik, behalve de keuze van kanalen):
 *   extensie  Chrome-extensie aanwezig en ingelogd   dicht: alles behalve Help en Account
 *   kanalen   gekozen waar hij verkoopt, en daar niet bewezen uitgelogd  dicht: idem
 *   items     minstens één item (importeren of nieuw)   alleen Import, Items, Platforms open
 *   plaatsen  eerste plaatsing: alleen een pijl, niets dicht
 *
 * Wie al bewezen werkt (een gelukte plaatsing, een eBay/Shopify/Woo-koppeling) komt
 * er nooit in. Weten we de feiten niet (server geeft geen antwoord), dan blijft de
 * poort open: een storing van ons mag een klant nooit buitensluiten.
 *
 * Gebruikt OB.feiten (onboarding.js) en de globalen showView, extState, showToast.
 */
(function () {
  "use strict";

  const P = {};
  window.OBPoort = P;

  const KANALEN_SLEUTEL = "ob-poort-kanalen";
  const OK_SLEUTEL = "ob-poort-kanalen-ok";
  const KANALEN = [
    ["marktplaats", "Marktplaats", "https://www.marktplaats.nl"],
    ["2dehands", "2dehands", "https://www.2dehands.be"],
    ["vinted", "Vinted", "https://www.vinted.nl"],
    ["facebook", "Facebook", "https://www.facebook.com/marketplace"],
  ];
  const STORE_URL = "https://chrome.google.com/webstore/detail/gfaogapbhaacfbpdppdcmnkjndlphleh";
  const STAP_NAMEN = ["Chrome extension", "Your marketplaces", "Your items", "First advert"];
  const OPEN = { extensie: ["help", "prijs"], kanalen: ["help", "prijs"], items: ["import", "items", "help", "prijs", "platforms"] };

  const opslag = {
    lees(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    zet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* privé venster */ } },
  };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const g = (naam) => { try { return window[naam] !== undefined ? window[naam] : (0, eval)(naam); } catch (e) { return undefined; } };

  // ── Wat moet er nog? Puur uit feiten, los te testen ─────────────────────────
  /**
   * f = { bekend, server:{extensie,kanaal,gepubliceerd,items}, extStatus, items,
   *       gekoppeld[], nietIngelogd[], gekozen[], kanalenOk, telefoon, andereBrowser }
   */
  P.fase = function (f) {
    f = f || {};
    const s = f.server || {};
    if (!f.bekend) return { fase: "vrij" };
    if (s.gepubliceerd || s.kanaal) return { fase: "vrij" };
    if ((f.gekoppeld || []).some((p) => ["ebay", "shopify", "woocommerce"].includes(p))) return { fase: "vrij" };
    if (!(s.extensie || f.extStatus === "ready")) {
      let sub = "zoeken";
      if (f.telefoon) sub = "telefoon";
      else if (f.andereBrowser) sub = "andere";
      else if (f.extStatus === "signed-out") sub = "inloggen";
      else if (f.extStatus === "missing") sub = "installeren";
      return { nr: 1, fase: "extensie", sub };
    }
    const gekozen = f.gekozen || [];
    const ontbreekt = (f.nietIngelogd || []).filter((p) => gekozen.includes(p));
    if (!gekozen.length || ontbreekt.length || !f.kanalenOk) {
      return { nr: 2, fase: "kanalen", sub: !gekozen.length ? "kiezen" : ontbreekt.length ? "inloggen" : "bevestigen", ontbreekt };
    }
    if (!(s.items || f.items > 0)) return { nr: 3, fase: "items" };
    return { nr: 4, fase: "plaatsen" };
  };

  P.toegestaan = function (fase, view) {
    const lijst = OPEN[fase];
    return !lijst || lijst.includes(view);
  };
  // Waar je terechtkomt als je ergens heen wilt waar je nog niet mag.
  P.terugval = (fase) => (fase === "items" ? "import" : "dashboard");

  // ── Toestand ────────────────────────────────────────────────────────────────
  let huidig = { fase: "vrij" };
  let laatsteFeiten = null, laatsteServer = 0, bezig = false, sindsKanalen = 0;

  P.actief = () => huidig.fase !== "vrij" && huidig.fase !== "plaatsen";
  P.guard = function (view) {
    if (P.toegestaan(huidig.fase, view)) return view;
    const f = P.terugval(huidig.fase);
    if (view === f) return f;
    try { const t = g("showToast"); if (typeof t === "function") t("Finish the setup first: this screen opens right after."); } catch (e) { /* geen toast */ }
    return f;
  };
  // Een selector op id, opgebouwd uit stukjes zodat de vertaallaag er geen tekst in ziet.
  const ID = (id, rest) => "#" + id + " " + rest;
  const actieveView = () => {
    const el = document.querySelector(".view.active");
    return el ? el.id.replace(/^view-/, "") : "";
  };

  // ── Stijl ───────────────────────────────────────────────────────────────────
  const CSS = `
    #ob-poort{position:fixed;top:0;right:0;bottom:0;left:232px;z-index:90;background:var(--bg,#f1f5f9);overflow:auto;display:none;padding:32px 28px 60px}
    @media(max-width:768px){#ob-poort{left:0;padding:20px 16px 60px}}
    .pt-wrap{max-width:980px;margin:0 auto}
    .pt-kop{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:6px}
    .pt-kop h1{font-size:22px;font-weight:800;letter-spacing:-.3px;margin:0}
    .pt-belofte{font-size:14px;color:var(--muted,#64748b);margin:0 0 20px}
    .pt-lijn{display:flex;gap:8px;margin-bottom:22px;flex-wrap:wrap}
    .pt-pas{display:flex;align-items:center;gap:8px;padding:8px 14px;border-radius:100px;background:#fff;border:1.5px solid var(--border,#e2e8f0);font-size:13px;font-weight:650;color:#94a3b8}
    .pt-pas b{width:22px;height:22px;border-radius:50%;background:#e2e8f0;color:#64748b;display:flex;align-items:center;justify-content:center;font-size:12px}
    .pt-pas.nu{border-color:#2563eb;color:#0f172a;box-shadow:0 0 0 4px rgba(37,99,235,.12)}
    .pt-pas.nu b{background:#2563eb;color:#fff}
    .pt-pas.klaar{color:#15803d;border-color:#bbf7d0;background:#f0fdf4}
    .pt-pas.klaar b{background:#16a34a;color:#fff}
    .pt-kaart{background:#fff;border:1px solid var(--border,#e2e8f0);border-radius:18px;padding:28px;display:grid;grid-template-columns:1.1fr 1fr;gap:28px;box-shadow:0 10px 40px rgba(15,23,42,.07)}
    @media(max-width:860px){.pt-kaart{grid-template-columns:1fr;padding:20px}}
    .pt-kaart h2{font-size:21px;font-weight:800;letter-spacing:-.3px;margin:0 0 10px}
    .pt-kaart p{font-size:14px;line-height:1.65;color:#475569;margin:0 0 16px}
    .pt-groot{display:inline-block;padding:14px 26px;background:linear-gradient(135deg,#2563eb,#34d399);color:#fff!important;border-radius:100px;font-size:15px;font-weight:750;text-decoration:none;border:0;cursor:pointer;box-shadow:0 4px 16px rgba(37,99,235,.3)}
    .pt-groot[disabled]{opacity:.45;cursor:not-allowed;box-shadow:none}
    .pt-licht{display:inline-block;padding:11px 18px;background:#fff;border:1.5px solid var(--border,#e2e8f0);border-radius:100px;font-size:13px;font-weight:650;color:#334155;text-decoration:none;cursor:pointer}
    .pt-lijst{margin:0 0 18px;padding:0;list-style:none;display:flex;flex-direction:column;gap:9px}
    .pt-lijst li{display:flex;gap:11px;align-items:flex-start;font-size:13.5px;line-height:1.5;color:#334155}
    .pt-lijst li i{flex:0 0 24px;height:24px;border-radius:50%;background:#eff6ff;color:#2563eb;font-style:normal;font-weight:800;font-size:12px;display:flex;align-items:center;justify-content:center}
    .pt-wacht{display:flex;align-items:center;gap:9px;font-size:13px;color:#64748b;margin-top:16px}
    .pt-puls{width:10px;height:10px;border-radius:50%;background:#2563eb;animation:pt-puls 1.2s infinite}
    @keyframes pt-puls{0%{box-shadow:0 0 0 0 rgba(37,99,235,.5)}100%{box-shadow:0 0 0 12px rgba(37,99,235,0)}}
    .pt-beeld{background:linear-gradient(160deg,#eff6ff,#ecfdf5);border-radius:14px;padding:18px;display:flex;align-items:center;justify-content:center;min-height:240px;position:relative;overflow:hidden}
    .pt-chrome{width:100%;max-width:380px;background:#fff;border-radius:10px;box-shadow:0 8px 28px rgba(15,23,42,.14);overflow:hidden;position:relative}
    .pt-balk{display:flex;align-items:center;gap:6px;padding:9px 10px;background:#e2e8f0}
    .pt-balk i{width:9px;height:9px;border-radius:50%;background:#94a3b8}
    .pt-url{flex:1;background:#fff;border-radius:100px;font-size:10px;color:#64748b;padding:4px 10px;margin:0 6px}
    .pt-puzzel{width:24px;height:24px;border-radius:6px;background:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;outline:3px solid #2563eb;animation:pt-glow 1.4s infinite}
    @keyframes pt-glow{0%,100%{outline-color:rgba(37,99,235,.9)}50%{outline-color:rgba(37,99,235,.2)}}
    .pt-pagina{padding:18px 14px;font-size:11px;color:#64748b;line-height:1.7}
    .pt-pijl-mock{position:absolute;top:44px;right:8px;display:flex;flex-direction:column;align-items:flex-end;animation:pt-op 1s ease-in-out infinite;color:#2563eb;font-size:11px;font-weight:750}
    @keyframes pt-op{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
    .pt-pijl-mock span{background:#2563eb;color:#fff;border-radius:8px;padding:5px 9px;margin-top:2px;white-space:nowrap}
    .pt-chips{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:16px}
    .pt-chip{display:flex;align-items:center;gap:8px;padding:11px 16px;border-radius:12px;border:2px solid var(--border,#e2e8f0);background:#fff;font-size:14px;font-weight:650;cursor:pointer;color:#334155}
    .pt-chip.aan{border-color:#2563eb;background:#eff6ff;color:#0f172a}
    .pt-rij{display:flex;align-items:center;gap:10px;padding:11px 12px;border-radius:12px;border:1px solid var(--border,#e2e8f0);background:#fff;margin-bottom:9px;font-size:13.5px;flex-wrap:wrap}
    .pt-rij.slecht{border-color:#fecaca;background:#fef2f2}
    .pt-rij b{flex:1;min-width:110px}
    .pt-stat{font-size:12px;font-weight:700;padding:3px 10px;border-radius:100px;background:#f1f5f9;color:#64748b}
    .pt-stat.slecht{background:#fee2e2;color:#b91c1c}
    .pt-stat.goed{background:#dcfce7;color:#15803d}
    .pt-hier{color:#dc2626;font-weight:800;display:inline-block;animation:pt-zij .9s ease-in-out infinite}
    @keyframes pt-zij{0%,100%{transform:translateX(0)}50%{transform:translateX(-7px)}}
    .pt-voet{margin-top:18px;font-size:12.5px;color:#64748b;text-align:center}
    .pt-voet a{color:#2563eb;font-weight:650;cursor:pointer;text-decoration:none}
    #ob-coach{position:fixed;bottom:18px;left:calc(232px + 18px);right:18px;max-width:600px;z-index:80;background:#fff;border:2px solid #2563eb;border-radius:16px;padding:14px 18px;box-shadow:0 14px 40px rgba(15,23,42,.22);display:none}
    @media(max-width:768px){#ob-coach{left:12px;right:12px}}
    #ob-coach .pt-cs{font-size:11px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:#2563eb;margin-bottom:3px}
    #ob-coach b.pt-ct{display:block;font-size:15px;margin-bottom:3px}
    #ob-coach p{margin:0;font-size:13px;line-height:1.55;color:#475569}
    #ob-coach .pt-cb{margin-top:10px}
    #ob-pijl{position:fixed;z-index:85;display:none;pointer-events:none;align-items:center;gap:6px;color:#fff;font-weight:750;font-size:13px}
    #ob-pijl span{background:#2563eb;border-radius:10px;padding:7px 12px;box-shadow:0 6px 20px rgba(37,99,235,.4);white-space:nowrap}
    #ob-pijl svg{color:#2563eb;filter:drop-shadow(0 3px 5px rgba(37,99,235,.35))}
    #ob-pijl.zij{animation:pt-zij2 .9s ease-in-out infinite}
    #ob-pijl.links{animation:pt-zij3 .9s ease-in-out infinite}
    @keyframes pt-zij3{0%,100%{transform:translateX(0)}50%{transform:translateX(9px)}}
    #ob-pijl.onder{flex-direction:column;animation:pt-op 1s ease-in-out infinite}
    @keyframes pt-zij2{0%,100%{transform:translateX(0)}50%{transform:translateX(-9px)}}
    .pt-wijs{outline:3px solid #2563eb!important;outline-offset:3px;border-radius:8px;animation:pt-glow 1.4s infinite}
    .nav-item.pt-slot{opacity:.45}
    .nav-item.pt-slot::after{content:"\\1F512";margin-left:auto;font-size:11px}
  `;
  function stijl() {
    if (document.getElementById("pt-stijl")) return;
    const s = document.createElement("style");
    s.id = "pt-stijl"; s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ── Het scherm ──────────────────────────────────────────────────────────────
  function beeldChrome(label) {
    return `<div class="pt-beeld"><div class="pt-chrome">
        <div class="pt-balk"><i></i><i></i><i></i><span class="pt-url">omnivaleur.com/app</span><span class="pt-puzzel">🧩</span></div>
        <div class="pt-pagina">Omnivaleur<br>Your items, on every marketplace.<br>One click to publish.</div>
        <div class="pt-pijl-mock"><svg width="26" height="30" viewBox="0 0 24 28" fill="currentColor"><path d="M12 0l11 14h-7v14H8V14H1z"/></svg><span>${label}</span></div>
      </div></div>`;
  }
  const naam = (p) => (KANALEN.find((k) => k[0] === p) || [p, p])[1];
  const logo = (p) => { try { const f = g("platIcon"); return typeof f === "function" ? f(p, 18) : ""; } catch (e) { return ""; } };

  function inhoudExtensie(r) {
    const link = "https://omnivaleur.com/app";
    if (r.sub === "telefoon" || r.sub === "andere") {
      const tel = r.sub === "telefoon";
      const mail = opslag.lees("cl_email") || "";
      return `<div>
          <h2>${tel ? "Continue on your computer" : "Open this page in Chrome"}</h2>
          <p>${tel
            ? "Omnivaleur places your adverts through the Chrome browser on a computer, in your own marketplace accounts. A phone can't do that, so the setup happens there. You can use your phone for everything else afterwards."
            : "Omnivaleur needs Google Chrome on a computer to place your adverts. Safari and Firefox can't run the extension."}</p>
          <ul class="pt-lijst"><li><i>1</i><span>Open <b>omnivaleur.com/app</b> in Chrome on your computer.</span></li><li><i>2</i><span>Sign in with the same account. This page continues from there.</span></li></ul>
          <div style="display:flex;gap:10px;flex-wrap:wrap">
            ${tel && mail ? `<a class="pt-groot" href="mailto:${esc(mail)}?subject=${encodeURIComponent("Omnivaleur link")}&body=${encodeURIComponent(link)}">Email me the link</a>` : ""}
            <button class="pt-licht" onclick="OBPoort.kopieer()">Copy link</button>
          </div></div>${beeldChrome("Chrome on your computer")}`;
    }
    const inloggen = r.sub === "inloggen";
    return `<div>
        <h2>${inloggen ? "Sign in to the extension" : "Install the Chrome extension"}</h2>
        <p>${inloggen
          ? "The extension is installed, but it isn't signed in yet. Nothing can be published until it is."
          : "Omnivaleur places your adverts through a small Chrome extension, in your own browser, as you. Without it nothing can be published."}</p>
        <ul class="pt-lijst">
          ${inloggen
            ? `<li><i>1</i><span>Click the <b>puzzle piece</b> at the top right of Chrome (see the arrow).</span></li>
               <li><i>2</i><span>Click <b>Omnivaleur</b>, then <b>Sign in</b>. Can't see it? Pin it with the pin icon.</span></li>`
            : `<li><i>1</i><span>Press <b>Add to Chrome</b> and confirm <b>Add extension</b>.</span></li>
               <li><i>2</i><span>Come back to this tab. It continues by itself.</span></li>`}
        </ul>
        ${inloggen ? "" : `<a class="pt-groot" href="${STORE_URL}" target="_blank" rel="noopener">Add to Chrome</a>`}
        <div class="pt-wacht"><span class="pt-puls"></span>${r.sub === "zoeken" ? "Looking for the extension in this browser…" : "Waiting for the extension. This page continues by itself."}</div>
      </div>${beeldChrome(inloggen ? "Click here, then Sign in" : "It appears here")}`;
  }

  function inhoudKanalen(r, f) {
    const gekozen = f.gekozen || [];
    const kanalen = f.kanalen || {};
    const chips = KANALEN.map(([p, n]) => `<button class="pt-chip ${gekozen.includes(p) ? "aan" : ""}" onclick="OBPoort.kies('${p}')">${logo(p)} ${n}${gekozen.includes(p) ? " ✓" : ""}</button>`).join("");
    const rijen = gekozen.map((p) => {
      const uit = r.ontbreekt && r.ontbreekt.includes(p);
      const gemeten = kanalen[p] && kanalen[p].ingelogd !== undefined;
      const url = (KANALEN.find((k) => k[0] === p) || [])[2];
      return `<div class="pt-rij ${uit ? "slecht" : ""}">${logo(p)}<b>${naam(p)}</b>
          <span class="pt-stat ${uit ? "slecht" : gemeten ? "goed" : ""}">${uit ? "Not signed in" : gemeten ? "No problem found" : "Checking…"}</span>
          ${uit ? '<span class="pt-hier">←</span>' : ""}
          <a class="${uit ? "pt-groot" : "pt-licht"}" href="${url}" target="_blank" rel="noopener" style="${uit ? "padding:9px 18px;font-size:13px" : ""}">${uit ? "Sign in here" : "Open"} <span translate="no">${naam(p)}</span></a>
        </div>`;
    }).join("");
    const geblokkeerd = !gekozen.length || (r.ontbreekt || []).length;
    return `<div style="grid-column:1/-1">
        <h2>Which marketplaces do you sell on?</h2>
        <p>Omnivaleur publishes <b>as you</b>, so you need to be signed in to each marketplace in <b>this same Chrome</b>. Marktplaats and 2dehands are separate sites with separate logins. Tick yours, open each one, sign in, and come back: the status updates by itself.</p>
        <div class="pt-chips">${chips}</div>
        ${rijen}
        ${(r.ontbreekt || []).length ? `<p style="color:#b91c1c;font-weight:650;margin-top:6px"><span>You are not signed in to ${r.ontbreekt.map(naam).join(" and ")} in this browser.</span> <span>Sign in there, then come back.</span></p>` : ""}
        <button class="pt-groot" ${geblokkeerd ? "disabled" : ""} onclick="OBPoort.bevestig()">${gekozen.length ? "I am signed in, continue" : "Tick at least one marketplace"}</button>
      </div>`;
  }

  function overlayHtml(r, f) {
    const pas = STAP_NAMEN.map((t, i) => {
      const nr = i + 1;
      const klas = nr < r.nr ? "klaar" : nr === r.nr ? "nu" : "";
      return `<div class="pt-pas ${klas}"><b>${nr < r.nr ? "✓" : nr}</b>${t}</div>`;
    }).join("");
    return `<div class="pt-wrap">
        <div class="pt-kop"><h1>Welcome to Omnivaleur</h1></div>
        <p class="pt-belofte">Four short steps and your first advert is on another marketplace. The dashboard opens as soon as the first two are done.</p>
        <div class="pt-lijn">${pas}</div>
        <div class="pt-kaart">${r.fase === "extensie" ? inhoudExtensie(r) : inhoudKanalen(r, f)}</div>
        <div class="pt-voet">Stuck? <a onclick="OBPoort.helpOpen()">Open Help</a> or <a href="mailto:info@omnivaleur.com">email us</a>. We reply within one business day.</div>
      </div>`;
  }

  // ── Pijl en coachkaart ──────────────────────────────────────────────────────
  let wijsDoel = null;
  function pijl(selector, tekst) {
    let el = document.getElementById("ob-pijl");
    if (!el) { el = document.createElement("div"); el.id = "ob-pijl"; document.body.appendChild(el); }
    let doel = null;
    try { doel = selector ? document.querySelector(selector) : null; } catch (e) { doel = null; }
    // Staat het doel buiten beeld (op het dashboard zit de tabel onder de startkaart),
    // schuif er dan één keer naartoe, anders wijst de pijl naar niets.
    if (doel && wijsDoel !== doel) {
      const b = doel.getBoundingClientRect();
      if (b.width >= 4 && (b.top > innerHeight - 90 || b.bottom < 60)) doel.scrollIntoView({ block: "center" });
    }
    const r = doel ? doel.getBoundingClientRect() : null;
    if (!doel || r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight || r.right <= 0 || r.left >= innerWidth) {
      el.style.display = "none";
      if (wijsDoel) { wijsDoel.classList.remove("pt-wijs"); wijsDoel = null; }
      return;
    }
    if (wijsDoel !== doel) { if (wijsDoel) wijsDoel.classList.remove("pt-wijs"); doel.classList.add("pt-wijs"); wijsDoel = doel; }
    const zij = r.right + 250 < innerWidth;
    const links = !zij && r.left > 280;
    el.className = zij ? "zij" : links ? "links" : "onder";
    const naar = zij ? '<svg width="30" height="26" viewBox="0 0 28 24" fill="currentColor"><path d="M0 12L14 1v7h14v8H14v7z"/></svg>'
      : links ? '<svg width="30" height="26" viewBox="0 0 28 24" fill="currentColor"><path d="M28 12L14 1v7H0v8h14v7z"/></svg>'
      : '<svg width="26" height="30" viewBox="0 0 24 28" fill="currentColor"><path d="M12 0l11 14h-7v14H8V14H1z"/></svg>';
    el.innerHTML = links ? `<span>${esc(tekst)}</span>${naar}` : `${naar}<span>${esc(tekst)}</span>`;
    el.style.display = "flex";
    const w = el.offsetWidth, h = el.offsetHeight;
    el.style.left = Math.max(8, Math.min(innerWidth - w - 8, zij ? r.right + 8 : links ? r.left - w - 8 : r.left + r.width / 2 - w / 2)) + "px";
    el.style.top = Math.max(8, Math.min(innerHeight - h - 8, zij || links ? r.top + r.height / 2 - h / 2 : r.bottom + 8)) + "px";
  }
  function wisPijl() {
    const el = document.getElementById("ob-pijl");
    if (el) el.style.display = "none";
    if (wijsDoel) { wijsDoel.classList.remove("pt-wijs"); wijsDoel = null; }
  }
  function coach(html) {
    let el = document.getElementById("ob-coach");
    if (!html) { if (el) el.style.display = "none"; return; }
    if (!el) { el = document.createElement("div"); el.id = "ob-coach"; document.body.appendChild(el); }
    if (el._h !== html) { el._h = html; el.innerHTML = html; }
    el.style.display = "block";
  }

  function tekenCoach(r) {
    const view = actieveView();
    if (r.fase === "items") {
      const opImport = view === "import";
      coach(`<div class="pt-cs">Step 3 of 4</div><b class="pt-ct">Add your items</b>
        <p>Import the adverts you already have on Marktplaats, 2dehands or Vinted, or create one with <b>New item</b>. The next step opens as soon as there is one item.</p>
        ${opImport ? "" : `<div class="pt-cb"><button class="pt-groot" style="padding:10px 20px;font-size:13px" onclick="showView('import')">Go to Import</button></div>`}`);
      pijl(opImport ? ID("view-import", ".imp-chip") : ".nav-item[data-view='import']", opImport ? "Tick where you sell" : "Open Import");
      return;
    }
    // plaatsen
    const sel = view === "dashboard" ? ID("dashboard-items-body", ".btn-primary")
      : view === "items" ? ID("items-body", ".btn-primary") : ".nav-item[data-view='items']";
    coach(`<div class="pt-cs">Step 4 of 4</div><b class="pt-ct">Publish your first item</b>
      <p>Press <b>Publish</b> on an item, tick a marketplace and confirm. The icon turns orange while the extension works and <b>green once the advert is really online</b>.</p>`);
    pijl(sel, view === "dashboard" || view === "items" ? "Press Publish" : "Go to your items");
  }

  // ── Eén ronde ───────────────────────────────────────────────────────────────
  function lokaleFeiten() {
    const OBr = window.OB;
    if (!OBr || typeof OBr.feiten !== "function") return null;
    return OBr.feiten;
  }
  async function verzamel() {
    const feiten = lokaleFeiten();
    if (!feiten) return null;
    const vers = Date.now() - laatsteServer > 15000 && huidig.fase !== "vrij";
    const uit = await feiten(vers);
    if (vers) laatsteServer = Date.now();
    const ext = g("extState") || {};
    const gek = (() => { try { return JSON.parse(opslag.lees(KANALEN_SLEUTEL) || "[]"); } catch (e) { return []; } })();
    const kanalen = ext.kanalen || {};
    let telefoon = false, andere = false;
    try { const t = g("_opTelefoon"); telefoon = typeof t === "function" && !!t(); } catch (e) { /* onbekend */ }
    try { const a = g("_andereBrowser"); andere = typeof a === "function" && !!a(); } catch (e) { /* onbekend */ }
    return {
      bekend: !!uit.bekend, server: uit.server || {}, extStatus: ext.status,
      items: uit.lokaal ? uit.lokaal.items : 0, gekoppeld: uit.lokaal ? uit.lokaal.gekoppeld : [],
      nietIngelogd: Object.entries(kanalen).filter(([, v]) => v && v.ingelogd === false).map(([p]) => p),
      kanalen, gekozen: gek, kanalenOk: opslag.lees(OK_SLEUTEL) === "1", telefoon, andereBrowser: andere,
    };
  }

  P.tik = async function () {
    if (bezig || document.hidden) return;
    bezig = true;
    try {
      stijl();
      const f = await verzamel();
      if (!f) return;
      laatsteFeiten = f;
      const r = P.fase(f);
      huidig = r;
      const view = actieveView();
      // Mag hij hier nog zijn? Zo niet: naar waar het wel mag.
      if (view && !P.toegestaan(r.fase, view) && view !== P.terugval(r.fase)) { const sv = g("showView"); if (typeof sv === "function") sv(P.terugval(r.fase)); }
      let ov = document.getElementById("ob-poort");
      if (!ov) { ov = document.createElement("div"); ov.id = "ob-poort"; document.body.appendChild(ov); }
      const dicht = (r.fase === "extensie" || r.fase === "kanalen") && !P.toegestaan(r.fase, actieveView());
      if (dicht) {
        const h = overlayHtml(r, f);
        if (ov._h !== h) { ov._h = h; ov.innerHTML = h; }
        ov.style.display = "block";
        coach(null); wisPijl();
      } else {
        ov.style.display = "none";
        if (r.fase === "items" || r.fase === "plaatsen") tekenCoach(r); else { coach(null); wisPijl(); }
      }
      // Slotjes in het menu bij wat nog dicht is.
      document.querySelectorAll(".sidebar .nav-item[data-view]").forEach((n) =>
        n.classList.toggle("pt-slot", !P.toegestaan(r.fase, n.dataset.view) && r.fase !== "vrij"));
      // De extensie meet kanalen pas als we haar vragen: tijdens stap 2 vaker vragen.
      if (r.fase === "kanalen" && Date.now() - sindsKanalen > 5000) {
        sindsKanalen = Date.now();
        try { const p = g("_extPingEenmaal"); if (typeof p === "function") p(); } catch (e) { /* volgende ronde */ }
      }
    } catch (e) { /* een uitlegscherm mag het dashboard nooit breken */ }
    bezig = false;
  };

  // ── Handelingen uit het scherm ──────────────────────────────────────────────
  P.kies = function (p) {
    let l = []; try { l = JSON.parse(opslag.lees(KANALEN_SLEUTEL) || "[]"); } catch (e) { l = []; }
    l = l.includes(p) ? l.filter((x) => x !== p) : [...l, p];
    opslag.zet(KANALEN_SLEUTEL, JSON.stringify(l));
    P.tik();
  };
  P.bevestig = function () { opslag.zet(OK_SLEUTEL, "1"); P.tik(); };
  P.helpOpen = function () { const sv = g("showView"); if (typeof sv === "function") sv("help"); P.tik(); };
  P.kopieer = function () {
    try { navigator.clipboard.writeText("https://omnivaleur.com/app"); const t = g("showToast"); if (typeof t === "function") t("Link copied"); } catch (e) { /* geen klembord */ }
  };

  // Elke twee seconden: goedkoop, de server wordt hooguit elke 15 seconden gevraagd.
  setInterval(P.tik, 2000);
  setTimeout(P.tik, 800);
  addEventListener("focus", () => setTimeout(P.tik, 300));
  addEventListener("resize", () => { if (huidig.fase === "items" || huidig.fase === "plaatsen") P.tik(); });
})();
