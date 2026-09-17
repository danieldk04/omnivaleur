/*
 * Omnivaleur: beginnen en uitleg (17-09-2026).
 *
 * WAAROM DIT BESTAND ER IS. Johan Kist (Blackbird Guitars) importeerde op dag één
 * 24 advertenties, klikte bij 23 gitaren elk kanaalicoon aan en dacht dat hij
 * daarmee geplaatst had. Drie dagen later zocht hij zijn advertenties op 2dehands
 * en Facebook en vond niets. In de call bleek wat hij miste: dat je op elk kanaal
 * zelf een account nodig hebt en daar in Chrome ingelogd moet zijn, dat
 * "Auto-detected" niets over zijn account zei, en dat plaatsen via Publish gaat.
 * Die vragen komen bij bijna elke nieuwe klant terug (zie docs/klantenservice-brein.md).
 *
 * Wat hier staat:
 *   - een "Get started"-lijst op het dashboard die afvinkt op wat er ECHT gebeurde
 *     (server: /api/jobs/onboarding), nooit op wat er aangeklikt is;
 *   - de Help-pagina: een schema van hoe het werkt, de iconen uitgelegd, per kanaal
 *     wat je nodig hebt en wat het kost, en de vragen die het vaakst binnenkomen;
 *   - een kleine uitleg van de kanaaliconen naast de kolom "Platforms".
 *
 * Gebruikt de globale `state`, `extState`, `apiFetch`, `API`, `platIcon`, `showView`
 * uit app.html. Alles is er bewust tegen bestand dat die (nog) niet bestaan: een
 * uitlegscherm mag het dashboard nooit breken.
 */
(function () {
  "use strict";

  const OB = {};
  window.OB = OB;

  const STORE_URL = "https://chrome.google.com/webstore/detail/gfaogapbhaacfbpdppdcmnkjndlphleh";
  const VERBORGEN_SLEUTEL = "ob-get-started-hidden";
  const KLAAR_GEZIEN_SLEUTEL = "ob-get-started-done-seen";

  const opslag = {
    lees(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    zet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* privé venster */ } },
    weg(k) { try { localStorage.removeItem(k); } catch (e) { /* privé venster */ } },
  };
  // De globale namen uit app.html (let/const op scriptniveau, dus niet op window).
  const GLOBAAL = {
    state: () => (typeof state !== "undefined" ? state : undefined),
    extState: () => (typeof extState !== "undefined" ? extState : undefined),
    apiFetch: () => (typeof apiFetch !== "undefined" ? apiFetch : undefined),
    API: () => (typeof API !== "undefined" ? API : undefined),
    platIcon: () => (typeof platIcon !== "undefined" ? platIcon : undefined),
    showView: () => (typeof showView !== "undefined" ? showView : undefined),
  };
  const g = (naam) => { try { return GLOBAAL[naam](); } catch (e) { return undefined; } };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const EMOJI = { marktplaats: "🟧", "2dehands": "🟦", vinted: "🟩", facebook: "📘", ebay: "🛒", shopify: "🛍️" };
  function logo(p, size) {
    const f = g("platIcon");
    return typeof f === "function" ? f(p, size || 16) : (EMOJI[p] || "🏪");
  }
  function ga(view) {
    const f = g("showView");
    if (typeof f === "function") f(view);
  }
  OB.ga = ga;

  // ── Stijl ──────────────────────────────────────────────────────────────────
  const CSS = `
  .ob-card{background:var(--surface,#fff);border:1px solid var(--border,#e2e8f0);border-radius:var(--radius,10px);box-shadow:var(--shadow-sm,0 1px 3px rgba(0,0,0,.06));margin-bottom:20px;overflow:hidden}
  .ob-kop{display:flex;align-items:center;gap:16px;padding:16px 20px;flex-wrap:wrap}
  .ob-kop-tekst{flex:1;min-width:200px}
  .ob-titel{font-weight:800;font-size:15px;color:var(--text,#0f172a);letter-spacing:-.2px}
  .ob-sub{font-size:12.5px;color:var(--muted,#64748b);margin-top:2px}
  .ob-voortgang{display:flex;align-items:center;gap:10px;font-size:12px;font-weight:700;color:var(--muted,#64748b)}
  .ob-balk{width:120px;height:6px;border-radius:99px;background:#e2e8f0;overflow:hidden}
  .ob-balk i{display:block;height:100%;background:var(--grad,linear-gradient(135deg,#2563eb,#34d399));border-radius:99px;transition:width .4s}
  .ob-link{background:none;border:0;color:var(--muted,#64748b);font-size:12px;font-weight:600;cursor:pointer;padding:4px 6px;border-radius:6px}
  .ob-link:hover{color:var(--text,#0f172a);background:#f1f5f9}
  .ob-stappen{list-style:none;margin:0;padding:0 8px 8px}
  .ob-stap{border-top:1px solid var(--border,#e2e8f0)}
  .ob-stap-kop{display:flex;align-items:center;gap:12px;width:100%;background:none;border:0;padding:12px;cursor:pointer;text-align:left;font:inherit;color:var(--text,#0f172a);border-radius:8px}
  .ob-stap-kop:hover{background:#f8fafc}
  .ob-nr{width:24px;height:24px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;border:1.5px solid #cbd5e1;color:#64748b;background:#fff}
  .ob-stap.actief .ob-nr{border-color:var(--blue,#2563eb);color:var(--blue,#2563eb);box-shadow:0 0 0 4px #dbeafe}
  .ob-stap.klaar .ob-nr{background:#059669;border-color:#059669;color:#fff}
  .ob-stap-titel{flex:1;font-size:13.5px;font-weight:650}
  .ob-stap.klaar .ob-stap-titel{color:var(--muted,#64748b);text-decoration:line-through;text-decoration-color:#cbd5e1}
  .ob-tag{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#64748b;background:#f1f5f9;border-radius:99px;padding:2px 8px}
  .ob-tag.let-op{color:#9a3412;background:#ffedd5}
  .ob-pijl{color:#94a3b8;transition:transform .2s;flex-shrink:0}
  .ob-stap.open .ob-pijl{transform:rotate(180deg)}
  .ob-stap-inhoud{display:none;padding:0 12px 16px 48px}
  .ob-stap.open .ob-stap-inhoud{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,260px);gap:18px;align-items:center}
  .ob-stap-inhoud p{margin:0 0 10px;font-size:13px;line-height:1.6;color:var(--muted,#64748b)}
  .ob-stap-inhoud p b{color:var(--text,#0f172a)}
  .ob-acties{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .ob-waarschuwing{font-size:12.5px;color:#9a3412;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:8px 10px;margin:0 0 10px;line-height:1.5}
  .ob-mini{background:#f8fafc;border:1px solid var(--border,#e2e8f0);border-radius:10px;padding:12px;font-size:11px;color:#475569}
  .ob-klaar-rij{display:flex;align-items:center;gap:10px;padding:14px 20px;font-size:13px;color:#065f46;background:#ecfdf5}
  @media(max-width:720px){.ob-stap.open .ob-stap-inhoud{grid-template-columns:1fr;padding-left:12px}.ob-balk{width:80px}}

  /* mini-schermpjes */
  .ob-m-browser{border:1px solid #cbd5e1;border-radius:8px;background:#fff;overflow:hidden}
  .ob-m-balk{display:flex;align-items:center;gap:6px;padding:6px 8px;background:#f1f5f9;border-bottom:1px solid #e2e8f0}
  .ob-m-dot{width:7px;height:7px;border-radius:50%;background:#cbd5e1}
  .ob-m-url{flex:1;height:14px;border-radius:99px;background:#fff;border:1px solid #e2e8f0}
  .ob-m-puzzel{width:18px;height:18px;border-radius:5px;background:var(--grad,linear-gradient(135deg,#2563eb,#34d399));position:relative}
  .ob-m-bubbel{margin:8px;border:1px solid #bbf7d0;background:#f0fdf4;color:#065f46;border-radius:8px;padding:6px 8px;font-weight:700;display:flex;align-items:center;gap:6px}
  .ob-m-rij{display:flex;align-items:center;gap:6px;padding:5px 0}
  .ob-m-pil{display:flex;align-items:center;gap:5px;background:#fff;border:1px solid #e2e8f0;border-radius:99px;padding:3px 8px;font-weight:600;color:#334155}
  .ob-m-ok{color:#059669;font-weight:800}
  .ob-m-knop{display:inline-block;background:var(--grad,linear-gradient(135deg,#2563eb,#34d399));color:#fff;border-radius:6px;padding:4px 10px;font-weight:700}
  .ob-m-vak{width:11px;height:11px;border-radius:3px;border:1.5px solid #94a3b8;display:inline-block;vertical-align:-2px;margin-right:5px}
  .ob-m-vak.aan{background:var(--blue,#2563eb);border-color:var(--blue,#2563eb);box-shadow:inset 0 0 0 2px #fff}
  .ob-m-icoon{width:22px;height:22px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;border:1.5px solid #e2e8f0;background:#f1f5f9;position:relative;font-size:11px}
  .ob-m-icoon.groen{background:#d1fae5;border-color:#6ee7b7}
  .ob-m-icoon.oranje{background:#fef3c7;border-color:#fcd34d}
  .ob-m-icoon.rood{background:#fff7ed;border-color:#fbbf24}
  .ob-m-icoon.paars{background:#ede9fe;border-color:#c4b5fd}
  .ob-m-icoon.grijs{opacity:.5}
  .ob-m-icoon i{position:absolute;right:-4px;bottom:-4px;width:12px;height:12px;border-radius:50%;border:1.5px solid #fff;font-size:8px;font-style:normal;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800}
  .ob-m-icoon.groen i{background:#059669}.ob-m-icoon.oranje i{background:#d97706}.ob-m-icoon.rood i{background:#dc2626}.ob-m-icoon.paars i{background:#7c3aed}

  /* Help */
  .ob-help{max-width:900px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
  .ob-help-kop{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
  .ob-help-kop h1{margin:0;font-size:22px;letter-spacing:-.4px}
  .ob-help-kop p{margin:4px 0 0;color:var(--muted,#64748b);font-size:13.5px}
  .ob-zoek{position:relative;min-width:240px;flex:0 1 320px}
  .ob-zoek input{width:100%;box-sizing:border-box;padding:9px 12px 9px 34px;border:1px solid var(--border,#e2e8f0);border-radius:10px;font:inherit;font-size:13px;background:#fff}
  .ob-zoek input:focus{outline:2px solid #bfdbfe;border-color:var(--blue,#2563eb)}
  .ob-zoek svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:#94a3b8}
  .ob-chips{display:flex;gap:6px;flex-wrap:wrap}
  .ob-chip{font-size:12px;font-weight:600;color:#334155;background:#fff;border:1px solid var(--border,#e2e8f0);border-radius:99px;padding:5px 11px;cursor:pointer;text-decoration:none}
  .ob-chip:hover{border-color:#93c5fd;color:var(--blue,#2563eb)}
  .ob-sectie{scroll-margin-top:80px}
  .ob-sectie > .ob-card{margin-bottom:0}
  .ob-sectie-kop{padding:16px 22px;border-bottom:1px solid var(--border,#e2e8f0)}
  .ob-sectie-kop h2{margin:0;font-size:15px}
  .ob-sectie-kop p{margin:3px 0 0;font-size:12.5px;color:var(--muted,#64748b)}
  .ob-sectie-lijf{padding:18px 22px 22px}

  .ob-flow{display:grid;grid-template-columns:1fr 28px 1fr 28px 1fr 28px 1fr;align-items:stretch}
  .ob-fase{background:#f8fafc;border:1px solid var(--border,#e2e8f0);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:8px}
  .ob-fase-nr{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--blue,#2563eb)}
  .ob-fase-titel{font-size:13.5px;font-weight:750;color:var(--text,#0f172a)}
  .ob-fase-tekst{font-size:12px;line-height:1.55;color:var(--muted,#64748b)}
  .ob-fase .ob-mini{padding:8px;background:#fff}
  .ob-flow-pijl{display:flex;align-items:center;justify-content:center;color:#94a3b8}
  .ob-onder{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}
  .ob-weg{border:1px dashed #cbd5e1;border-radius:10px;padding:10px 12px;font-size:12px;line-height:1.55;color:var(--muted,#64748b)}
  .ob-weg b{color:var(--text,#0f172a)}
  @media(max-width:820px){.ob-flow{grid-template-columns:1fr}.ob-flow-pijl{height:26px}.ob-flow-pijl svg{transform:rotate(90deg)}.ob-onder{grid-template-columns:1fr}}

  .ob-uitleg-rij{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid var(--border,#e2e8f0);border-radius:10px;padding:10px 12px;flex-wrap:wrap}
  .ob-uitleg-duim{width:38px;height:38px;border-radius:8px;background:linear-gradient(135deg,#fde68a,#f59e0b)}
  .ob-uitleg-icons{display:flex;gap:12px;margin-left:auto;padding:6px 4px 0}
  .ob-pin{position:relative}
  .ob-pin b{position:absolute;top:-14px;left:50%;transform:translateX(-50%);width:15px;height:15px;border-radius:50%;background:#0f172a;color:#fff;font-size:9px;display:flex;align-items:center;justify-content:center}
  .ob-legenda{display:grid;grid-template-columns:1fr 1fr;gap:8px 18px;margin-top:14px}
  .ob-legenda div{display:flex;gap:10px;align-items:flex-start;font-size:12.5px;line-height:1.5;color:var(--muted,#64748b)}
  .ob-legenda div b{color:var(--text,#0f172a)}
  .ob-legenda .ob-m-icoon{flex-shrink:0;margin-top:1px}
  @media(max-width:640px){.ob-legenda{grid-template-columns:1fr}.ob-uitleg-icons{margin-left:0}}

  .ob-kanalen{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
  .ob-kanaal{border:1px solid var(--border,#e2e8f0);border-radius:10px;padding:12px 14px;background:#fff}
  .ob-kanaal-kop{display:flex;align-items:center;gap:8px;font-weight:750;font-size:13.5px;margin-bottom:6px}
  .ob-kanaal-via{margin-left:auto;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:#64748b;background:#f1f5f9;border-radius:99px;padding:2px 7px}
  .ob-kanaal ul{margin:0;padding-left:16px;font-size:12.5px;line-height:1.6;color:var(--muted,#64748b)}
  .ob-kanaal li b{color:var(--text,#0f172a)}

  .ob-faq-groep{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:#94a3b8;margin:16px 0 4px}
  .ob-faq-groep:first-child{margin-top:0}
  .ob-faq{border-bottom:1px solid var(--border,#e2e8f0)}
  .ob-faq summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:13px 0;font-size:13.5px;font-weight:620;color:var(--text,#0f172a)}
  .ob-faq summary::-webkit-details-marker{display:none}
  .ob-faq[open] summary .ob-pijl{transform:rotate(180deg)}
  .ob-faq-antwoord{font-size:13px;line-height:1.65;color:var(--muted,#64748b);padding:0 0 14px}
  .ob-faq-antwoord b{color:var(--text,#0f172a)}
  .ob-geen{display:none;font-size:13px;color:var(--muted,#64748b);padding:6px 0}

  .ob-popover{position:absolute;z-index:300;width:320px;max-width:calc(100vw - 32px);background:#fff;border:1px solid var(--border,#e2e8f0);border-radius:12px;box-shadow:0 12px 40px rgba(15,23,42,.18);padding:14px}
  .ob-popover .ob-legenda{grid-template-columns:1fr;margin-top:0}
  .ob-vraagje{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;border:1px solid #cbd5e1;background:#fff;color:#64748b;font-size:10px;font-weight:800;cursor:pointer;margin-left:6px;vertical-align:1px;padding:0}
  .ob-vraagje:hover{border-color:var(--blue,#2563eb);color:var(--blue,#2563eb)}
  `;
  function zorgVoorStijl() {
    if (document.getElementById("ob-stijl")) return;
    const s = document.createElement("style");
    s.id = "ob-stijl";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  const PIJL_OMLAAG = `<svg class="ob-pijl" width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.3 7.3a1 1 0 011.4 0L10 10.6l3.3-3.3a1 1 0 111.4 1.4l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 010-1.4z"/></svg>`;
  const PIJL_RECHTS = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15M13 6l6 6-6 6"/></svg>`;

  // ── Mini-schermpjes ────────────────────────────────────────────────────────
  const MINI = {
    extensie: () => `<div class="ob-m-browser">
        <div class="ob-m-balk"><span class="ob-m-dot"></span><span class="ob-m-dot"></span><span class="ob-m-url"></span><span class="ob-m-puzzel" title="Omnivaleur"></span></div>
        <div class="ob-m-bubbel"><span class="ob-m-ok">✓</span> Extension active, ready to publish</div>
      </div>`,
    inloggen: () => `<div>
        ${["marktplaats", "2dehands", "vinted"].map((p) => `<div class="ob-m-rij"><span class="ob-m-pil">${logo(p, 13)} ${{ marktplaats: "marktplaats.nl", "2dehands": "2dehands.be", vinted: "vinted.nl" }[p]}</span><span class="ob-m-ok">✓ signed in</span></div>`).join("")}
        <div style="margin-top:4px">In the <b>same Chrome</b> as the extension</div>
      </div>`,
    items: () => `<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
        <div class="ob-m-browser" style="padding:8px"><b>Import</b><div style="margin-top:3px">Your adverts from ${logo("marktplaats", 11)} ${logo("2dehands", 11)} ${logo("vinted", 11)}</div></div>
        <div class="ob-m-browser" style="padding:8px"><b>+ New item</b><div style="margin-top:3px">Photos, title, price, once</div></div>
      </div>`,
    publiceren: () => `<div class="ob-m-browser" style="padding:9px">
        <div style="font-weight:700;margin-bottom:5px">Publish item</div>
        <div><span class="ob-m-vak aan"></span>2dehands</div>
        <div><span class="ob-m-vak aan"></span>Vinted</div>
        <div style="margin-bottom:7px"><span class="ob-m-vak"></span>Facebook</div>
        <span class="ob-m-knop">Publish</span>
        <div style="margin-top:8px;display:flex;align-items:center;gap:6px">
          <span class="ob-m-icoon grijs">${logo("2dehands", 12)}</span>${PIJL_RECHTS.replace('width="22" height="22"', 'width="14" height="14"')}<span class="ob-m-icoon oranje">${logo("2dehands", 12)}<i>…</i></span>${PIJL_RECHTS.replace('width="22" height="22"', 'width="14" height="14"')}<span class="ob-m-icoon groen">${logo("2dehands", 12)}<i>✓</i></span>
        </div>
      </div>`,
    api: () => `<div>
        <div class="ob-m-rij"><span class="ob-m-pil">${logo("ebay", 13)} eBay</span><span class="ob-m-knop">Connect</span></div>
        <div class="ob-m-rij"><span class="ob-m-pil">${logo("shopify", 13)} Shopify</span><span class="ob-m-knop">Connect</span></div>
      </div>`,
  };

  // ── Wat er echt gebeurd is ────────────────────────────────────────────────
  /**
   * De stappen, puur uit feiten. Los te testen: zie tests/onboarding-stappen-test.js.
   * feiten = { extensie, kanaal, gepubliceerd, items, gekoppeld[], nietIngelogd[] }
   */
  OB.stappen = function (feiten) {
    const f = feiten || {};
    const nietIn = f.nietIngelogd || [];
    const gekoppeld = f.gekoppeld || [];
    return [
      {
        id: "extensie", klaar: !!f.extensie,
        titel: "Install the Chrome extension",
        tekst: "The extension does the work: it opens Marktplaats, 2dehands, Vinted and Facebook in your own Chrome and fills in the forms for you. Install it in the Chrome you want to publish from, then open Omnivaleur once in that same Chrome so the extension signs in with your account.",
        acties: `<a class="btn btn-primary btn-sm" href="${STORE_URL}" target="_blank" rel="noopener" style="text-decoration:none">Install extension</a>
                 <button class="btn btn-outline btn-sm" onclick="OB.verversLijst(true)">I've installed it</button>`,
      },
      {
        id: "inloggen", klaar: !!f.kanaal && !nietIn.length,
        let_op: nietIn.length > 0,
        titel: "Sign in to your marketplaces in that Chrome",
        tekst: "Omnivaleur publishes <b>as you</b>, so you need your own account on every marketplace you want to use, and you need to be signed in to it in the same Chrome as the extension. Marktplaats and 2dehands are separate sites with separate logins.",
        waarschuwing: nietIn.length
          ? `You are not signed in to <b>${nietIn.map((p) => ({ marktplaats: "Marktplaats", "2dehands": "2dehands", vinted: "Vinted", facebook: "Facebook" }[p] || p)).join(" and ")}</b> in this browser. Nothing goes out there until you are.`
          : "",
        acties: `<a class="btn btn-outline btn-sm" href="https://www.marktplaats.nl" target="_blank" rel="noopener" style="text-decoration:none">${logo("marktplaats", 13)} Marktplaats</a>
                 <a class="btn btn-outline btn-sm" href="https://www.2dehands.be" target="_blank" rel="noopener" style="text-decoration:none">${logo("2dehands", 13)} 2dehands</a>
                 <a class="btn btn-outline btn-sm" href="https://www.vinted.nl" target="_blank" rel="noopener" style="text-decoration:none">${logo("vinted", 13)} Vinted</a>`,
      },
      {
        id: "items", klaar: (f.items || 0) > 0,
        titel: "Add your items",
        tekst: "Already selling on Marktplaats, 2dehands or Vinted? <b>Import</b> those adverts and they become items here, photos and prices included. Something new? Create it once with <b>New item</b>. Dutch or English both work: Omnivaleur translates for each marketplace.",
        acties: `<button class="btn btn-primary btn-sm" onclick="OB.ga('import')">Import my adverts</button>
                 <button class="btn btn-outline btn-sm" onclick="typeof openAddItem==='function'&&openAddItem()">New item</button>`,
      },
      {
        id: "publiceren", klaar: !!f.gepubliceerd,
        titel: "Publish an item to another marketplace",
        tekst: "Press <b>Publish</b> on an item (or select several and use <b>Publish to…</b>), tick the marketplaces and confirm. The icon turns orange while the extension works and <b>green once the advert is really online</b>. Only this places adverts: nothing goes live on its own.",
        acties: `<button class="btn btn-primary btn-sm" onclick="OB.ga('items')">Go to my items</button>
                 <button class="ob-link" onclick="OB.naarHelp('iconen')">What do the icons mean?</button>`,
      },
      {
        id: "api", optioneel: true, klaar: gekoppeld.includes("ebay") || gekoppeld.includes("shopify"),
        titel: "Connect eBay or Shopify",
        tekst: "eBay and Shopify don't use the extension: you connect them once under Platforms. eBay first checks your identity and bank account before you can list. Shopify only applies if your webshop runs on Shopify.",
        acties: `<button class="btn btn-outline btn-sm" onclick="OB.ga('platforms')">Open Platforms</button>`,
      },
    ];
  };

  let _server = null, _serverTijd = 0, _bezig = null;
  async function serverFeiten(vers) {
    if (_server && !vers && Date.now() - _serverTijd < 60000) return _server;
    if (_bezig) return _bezig;
    const apiFetch = g("apiFetch"), API = g("API");
    if (typeof apiFetch !== "function") return _server || {};
    _bezig = (async () => {
      try {
        const r = await apiFetch(`${API || ""}/api/jobs/onboarding`);
        if (r.ok) { _server = await r.json(); _serverTijd = Date.now(); }
      } catch (e) { /* dan laten we zien wat we lokaal weten */ }
      _bezig = null;
      return _server || {};
    })();
    return _bezig;
  }

  function lokaleFeiten() {
    const st = g("state") || {};
    const ext = g("extState") || {};
    const kanalen = ext.kanalen || {};
    const status = st.extStatus || {};
    return {
      extensieHier: ["ready", "signed-out", "waking"].includes(ext.status) || !!status.online || !!status.last_seen,
      items: (st.items || []).length,
      gekoppeld: st.connected || [],
      nietIngelogd: Object.entries(kanalen).filter(([, v]) => v && v.ingelogd === false).map(([p]) => p),
    };
  }

  // ── Get started op het dashboard ───────────────────────────────────────────
  // Het dashboard ververst elke paar seconden; alleen tekenen als er iets
  // veranderde, anders springt een open stap of een knop onder je muis weg.
  function zet(el, html) {
    if (el._obHtml === html) return;
    el._obHtml = html;
    el.innerHTML = html;
  }

  OB.opDashboard = async function (vers) {
    const doel = document.getElementById("ob-checklist");
    if (!doel) return;
    zorgVoorStijl();
    if (opslag.lees(VERBORGEN_SLEUTEL) === "1") { zet(doel, ""); return; }
    const lokaal = lokaleFeiten();
    const server = await serverFeiten(vers);
    const stappen = OB.stappen({
      extensie: server.extensie || lokaal.extensieHier,
      kanaal: server.kanaal, gepubliceerd: server.gepubliceerd,
      items: lokaal.items, gekoppeld: lokaal.gekoppeld, nietIngelogd: lokaal.nietIngelogd,
    });
    const kern = stappen.filter((s) => !s.optioneel);
    const klaar = kern.filter((s) => s.klaar).length;
    if (klaar === kern.length) {
      if (opslag.lees(KLAAR_GEZIEN_SLEUTEL) === "1") { zet(doel, ""); return; }
      zet(doel, `<div class="ob-card"><div class="ob-klaar-rij">
          <span style="font-size:18px">🎉</span>
          <div style="flex:1"><b>You're set up.</b> Your items are going out to other marketplaces. Questions later on? Everything is under Help.</div>
          <button class="ob-link" onclick="OB.klaarGezien()">Close</button>
        </div></div>`);
      return;
    }
    const open = OB._open || (stappen.find((s) => !s.klaar && !s.optioneel) || {}).id;
    const eerste = (stappen.find((s) => !s.klaar && !s.optioneel) || {}).id;
    zet(doel, `<div class="ob-card" role="region" aria-label="Get started">
      <div class="ob-kop">
        <div class="ob-kop-tekst">
          <div class="ob-titel">Get started with Omnivaleur</div>
          <div class="ob-sub">A few steps to your first advert on another marketplace. Each step ticks itself off when it has really happened.</div>
        </div>
        <div class="ob-voortgang"><span>${klaar} of ${kern.length} done</span><div class="ob-balk"><i style="width:${Math.round(100 * klaar / kern.length)}%"></i></div></div>
        <button class="ob-link" onclick="OB.naarHelp('werking')">How it works</button>
        <button class="ob-link" onclick="OB.verberg()" title="You can bring this back under Help">Hide</button>
      </div>
      <ol class="ob-stappen">
        ${stappen.map((s, i) => `<li class="ob-stap ${s.klaar ? "klaar" : ""} ${s.id === eerste ? "actief" : ""} ${s.id === open ? "open" : ""}" data-stap="${s.id}">
          <button class="ob-stap-kop" onclick="OB.klap('${s.id}')" aria-expanded="${s.id === open}">
            <span class="ob-nr">${s.klaar ? "✓" : i + 1}</span>
            <span class="ob-stap-titel">${esc(s.titel)}</span>
            ${s.let_op ? `<span class="ob-tag let-op">Action needed</span>` : ""}
            ${s.optioneel ? `<span class="ob-tag">Optional</span>` : ""}
            ${PIJL_OMLAAG}
          </button>
          <div class="ob-stap-inhoud">
            <div>
              ${s.waarschuwing ? `<div class="ob-waarschuwing">${s.waarschuwing}</div>` : ""}
              <p>${s.tekst}</p>
              <div class="ob-acties">${s.acties}</div>
            </div>
            <div class="ob-mini" aria-hidden="true">${MINI[s.id] ? MINI[s.id]() : ""}</div>
          </div>
        </li>`).join("")}
      </ol>
    </div>`);
  };

  OB.klap = function (id) {
    OB._open = OB._open === id ? "__geen__" : id;
    document.querySelectorAll("#ob-checklist .ob-stap").forEach((li) => {
      const aan = li.dataset.stap === OB._open;
      li.classList.toggle("open", aan);
      const knop = li.querySelector(".ob-stap-kop");
      if (knop) knop.setAttribute("aria-expanded", String(aan));
    });
  };
  OB.verberg = function () { opslag.zet(VERBORGEN_SLEUTEL, "1"); OB.opDashboard(); };
  OB.toonWeer = function () { opslag.weg(VERBORGEN_SLEUTEL); opslag.weg(KLAAR_GEZIEN_SLEUTEL); ga("dashboard"); OB.opDashboard(true); };
  OB.klaarGezien = function () { opslag.zet(KLAAR_GEZIEN_SLEUTEL, "1"); OB.opDashboard(); };
  OB.verversLijst = function () { OB._open = null; OB.opDashboard(true); };

  // ── Iconen ──────────────────────────────────────────────────────────────────
  const ICOON_UITLEG = [
    ["grijs", "", "Not on this marketplace", "Click it to publish there, or to paste the link if the advert is already there. A click never marks anything live by itself."],
    ["oranje", "…", "Being published", "The extension is working on it. Leave the tab it opens alone; it closes by itself."],
    ["groen", "✓", "Live", "The advert is really online on that marketplace."],
    ["rood", "!", "Didn't work", "Hover over it (or click) to read why. Fix that, then publish again."],
    ["paars", "⧉", "Live under a copy", "The same item exists twice in your dashboard and the other copy is live. Don't publish again: merge the copies."],
  ];
  function legendaHtml() {
    return `<div class="ob-legenda">${ICOON_UITLEG.map(([kleur, badge, titel, tekst]) =>
      `<div><span class="ob-m-icoon ${kleur}">${logo("marktplaats", 12)}${badge ? `<i>${badge}</i>` : ""}</span><span><b>${titel}.</b> ${tekst}</span></div>`).join("")}</div>`;
  }
  OB.legenda = function (knop, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    zorgVoorStijl();
    const oud = document.getElementById("ob-popover");
    if (oud) { oud.remove(); if (oud._knop === knop) return; }
    const p = document.createElement("div");
    p.id = "ob-popover";
    p.className = "ob-popover";
    p._knop = knop;
    p.innerHTML = `<div style="font-weight:750;font-size:13px;margin-bottom:10px">What the marketplace icons mean</div>${legendaHtml()}
      <div style="margin-top:10px;font-size:12px"><a href="#" onclick="document.getElementById('ob-popover').remove();OB.naarHelp('iconen');return false" style="color:var(--blue,#2563eb);font-weight:650">More in Help →</a></div>`;
    document.body.appendChild(p);
    const r = knop.getBoundingClientRect();
    const links = Math.max(16, Math.min(window.scrollX + r.left - 150, window.scrollX + document.documentElement.clientWidth - p.offsetWidth - 16));
    p.style.left = `${links}px`;
    p.style.top = `${window.scrollY + r.bottom + 8}px`;
    const weg = (e) => { if (!p.contains(e.target) && e.target !== knop) { p.remove(); document.removeEventListener("click", weg, true); } };
    setTimeout(() => document.addEventListener("click", weg, true), 0);
  };

  // ── Platforms: eerlijke status per kanaal ─────────────────────────────────
  /**
   * Hier stond "✓ Auto-detected" bij elk extensiekanaal, altijd, wat er ook aan de
   * hand was. Johan las dat als "mijn account is gekoppeld". Alleen een bewezen
   * "niet ingelogd" meten we echt (zie KANAAL_SESSIE_SLEUTEL in background.js);
   * een "wel ingelogd" kunnen we niet bewijzen, dus beweren we het ook niet.
   */
  OB.kanaalStatus = function (platform, actief) {
    zorgVoorStijl();
    const ext = g("extState") || {};
    const meting = (ext.kanalen || {})[platform];
    const site = { marktplaats: "marktplaats.nl", "2dehands": "2dehands.be", vinted: "vinted.nl", facebook: "facebook.com/marketplace" }[platform];
    let badge = `<span class="badge" style="background:#f1f5f9;color:#475569">Uses your Chrome login</span>`;
    let regel = `Sign in to <b>${site}</b> in the Chrome where the extension runs. Omnivaleur publishes as you.`;
    if (meting && meting.ingelogd === false) {
      badge = `<span class="badge" style="background:#fff7ed;color:#9a3412">Not signed in</span>`;
      regel = `You're not signed in to <b>${site}</b> in this browser. <a href="https://${site}" target="_blank" rel="noopener" style="color:var(--blue,#2563eb);font-weight:650">Open and sign in →</a>`;
    }
    const tel = actief > 0 ? "" : ` <span style="color:#94a3b8">No adverts placed or imported here yet: use <b>Publish</b> on an item.</span>`;
    return { badge, regel: `<div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border,#e2e8f0);font-size:12px;color:var(--muted,#64748b);line-height:1.55">${regel}${tel}</div>` };
  };

  // ── Help ────────────────────────────────────────────────────────────────────
  const KANALEN = [
    ["marktplaats", "Marktplaats", "Chrome", [
      "<b>You need:</b> a Marktplaats account, signed in to in the Chrome with the extension.",
      "<b>Business account (Pro/Admarkt)?</b> Turn on <b>Business account (Admarkt)</b> in the extension popup to import. Omnivaleur can't take adverts offline or replace them on a business account: do that on Marktplaats itself.",
      "<b>Costs:</b> Marktplaats' own rules. A web address in the text turns an advert into a paid one, so Omnivaleur leaves links out.",
    ]],
    ["2dehands", "2dehands", "Chrome", [
      "<b>You need:</b> a 2dehands account. It's a separate site with a separate login, even if you're signed in to Marktplaats.",
      "<b>Living in the Netherlands?</b> Set your country and town under Preferences so the address fits.",
      "<b>Costs:</b> some categories cost money after a few free adverts (guitars: two free per category). Omnivaleur stops at the payment screen and never pays for you.",
    ]],
    ["vinted", "Vinted", "Chrome", [
      "<b>You need:</b> a Vinted account, signed in to in the same Chrome. Listing is free.",
      "<b>Text:</b> Vinted takes 2,000 characters at most. Longer descriptions are shortened for Vinted only, after a full sentence.",
      "Choose which of your categories may go to Vinted under Preferences. Some items Vinted doesn't allow at all (coins, stamps, banknotes).",
    ]],
    ["facebook", "Facebook Marketplace", "Beta", [
      "<b>You need:</b> a personal Facebook profile (a Page can't use Marketplace), signed in to in the same Chrome.",
      "<b>Beta:</b> Facebook doesn't allow automated listing and may flag accounts. Use it deliberately, preferably with a separate account.",
      "A new advert sits in review for a while. Check <b>Marketplace › Your listings</b> to see it.",
    ]],
    ["ebay", "eBay", "Connect", [
      "<b>You need:</b> an eBay account that is set up to sell. eBay checks your identity and bank account before your first listing.",
      "Connect once under Platforms, then fill in shipping and your ship-from address there. Each item needs an eBay category.",
      "Adverts go on ebay.nl, in Dutch.",
    ]],
    ["shopify", "Shopify", "Connect", [
      "<b>Only if your webshop runs on Shopify.</b> Other webshops can't be connected or imported.",
      "Connect under Platforms: the screen walks you through creating a small app in your Shopify admin.",
      "A paid order in your shop takes the item off your other marketplaces automatically.",
    ]],
  ];

  const FAQ = [
    ["Getting started", "Do I need an account on every marketplace?",
      "Yes. Omnivaleur doesn't create adverts under its own name: it publishes <b>as you</b>, on your own accounts. For Marktplaats, 2dehands, Vinted and Facebook you sign in once in the Chrome where the extension runs. eBay and Shopify you connect once under <b>Platforms</b>."],
    ["Getting started", "What does “Uses your Chrome login” on Platforms mean?",
      "That this marketplace works through your own login in Chrome, not through a separate link with Omnivaleur. It does not mean you're signed in. If Omnivaleur notices you're not, the card says <b>Not signed in</b>, and a bar on the dashboard tells you too."],
    ["Getting started", "I clicked the marketplace icons: is my item published now?",
      "No. Only <b>Publish</b> places adverts. Clicking a grey icon opens a choice: publish there, or paste the link if the advert is already there. Before 17 September a click only marked an item as live; if icons turned green without adverts behind them, let us know and we'll clean it up."],
    ["Getting started", "Which language should I write in?",
      "Dutch or English, whichever you prefer. Omnivaleur translates for each marketplace: Dutch for Marktplaats, 2dehands and eBay, English for Vinted and Shopify."],
    ["Getting started", "Can I import from my own website?",
      "Not at the moment. You can import the adverts you already have on <b>Marktplaats, 2dehands and Vinted</b> under Import. If your website runs on Shopify, connect it under Platforms."],
    ["Publishing", "I pressed Publish, but nothing happens",
      "Look at the top of your dashboard: a bar tells you what's holding things up. The usual reasons: the computer with the extension is off or asleep, the extension isn't signed in, or you're not signed in to that marketplace in Chrome. Once that's fixed the queue starts again by itself; you don't need to press Publish again."],
    ["Publishing", "Why does it take a while?",
      "Each advert takes about a minute or two, because the marketplace's own form needs that time, and Omnivaleur deliberately leaves a little room between adverts. With a big stock it's best to let it run overnight. Keep the computer on and awake with Chrome running; Omnivaleur keeps it awake by itself while work is waiting."],
    ["Publishing", "It says I'm not signed in, but I am",
      "Check two things. Marktplaats and 2dehands have separate logins, so you may be signed in to one and not the other. And if your account was turned into a <b>business account</b>, your personal “My adverts” page is empty, which can look like being signed out. Turn on <b>Business account (Admarkt)</b> in the extension popup; your queue stays where it is."],
    ["Publishing", "2dehands asks for payment",
      "Some 2dehands categories are paid after a few free adverts. Omnivaleur stops at that screen and never pays for you; the item shows a red icon with the reason. Decide per item whether you want to pay on 2dehands, or leave 2dehands off for those items."],
    ["Publishing", "Facebook says done, but I can't find my advert",
      "Look under <b>Marketplace › Your listings</b>: a new advert sits in review there for a while. Is it there? Click the Facebook icon on the item and choose <b>It is online</b>. Not there? Publish again. From extension 1.0.338 Omnivaleur only says done when Facebook confirms it."],
    ["Publishing", "Vinted keeps asking for the condition, or says the text is too long",
      "Both are handled for you: the condition is filled in again if Vinted draws the field late (extension 1.0.338), and texts over 2,000 characters are shortened for Vinted. Still seeing it? Your extension may be older; Chrome updates it by itself within a few hours."],
    ["Publishing", "The extension opens a tab but the advert isn't submitted",
      "Usually you're not signed in to that marketplace in this Chrome. Open the site, sign in, and publish again. If the tab shows a form with red fields, the icon on the item tells you what was missing."],
    ["Selling", "What happens when an item sells?",
      "Press <b>Sold</b> on the item and pick where it sold: Omnivaleur takes it off your other marketplaces. A sale on Vinted, or a paid order on eBay or Shopify, is picked up automatically. When an advert simply disappears from Vinted, Marktplaats or 2dehands you get a <b>Did this item sell?</b> question first, so nothing is taken down on a guess."],
    ["Selling", "I sold something, but it's still on my business account",
      "On a business (Pro/Admarkt) account on Marktplaats or 2dehands, Omnivaleur can't take adverts offline. Remove the advert there yourself."],
    ["Selling", "Sold on Vinted, but still on Marktplaats",
      "Vinted doesn't tell anyone about a sale; Omnivaleur notices it by reading your Vinted wardrobe. If you remove a sold item from Vinted yourself, you'll see a <b>Did this item sell?</b> question on your dashboard. Answer it and the item comes off your other marketplaces."],
    ["Account", "Are my marketplace passwords stored?",
      "No. Omnivaleur never sees or stores them. The extension uses the login you already have in Chrome."],
    ["Account", "Can I use Omnivaleur on my phone?",
      "Yes, the dashboard works in any browser. Add it to your home screen: on iPhone via <b>Share › Add to Home Screen</b>, on Android via <b>⋮ › Install app</b>. Publishing itself runs through the extension on your computer."],
    ["Account", "Does my computer need to stay on?",
      "While adverts are being placed, yes: the work runs in your own Chrome. Once everything is out you can switch it off. If your computer is off while work is waiting, you'll get an email."],
  ];

  function kanaalKaart([p, naam, via, regels]) {
    const label = { Chrome: "Via Chrome", Beta: "Beta", Connect: "Connect once" }[via];
    return `<div class="ob-kanaal"><div class="ob-kanaal-kop">${logo(p, 18)} ${naam}<span class="ob-kanaal-via" ${via === "Beta" ? 'style="background:#fef3c7;color:#92400e"' : ""}>${label}</span></div>
      <ul>${regels.map((r) => `<li>${r}</li>`).join("")}</ul></div>`;
  }

  function flowHtml() {
    const fase = (nr, titel, tekst, mini) => `<div class="ob-fase"><div class="ob-fase-nr">Step ${nr}</div><div class="ob-fase-titel">${titel}</div><div class="ob-fase-tekst">${tekst}</div><div class="ob-mini" aria-hidden="true">${mini}</div></div>`;
    const pijl = `<div class="ob-flow-pijl" aria-hidden="true">${PIJL_RECHTS}</div>`;
    return `<div class="ob-flow">
        ${fase(1, "Your items", "Import the adverts you already have, or create a new item. One item, one set of photos and one price for every marketplace.", `<div class="ob-m-rij"><span class="ob-m-pil">⤓ Import</span></div><div class="ob-m-rij"><span class="ob-m-pil">+ New item</span></div>`)}
        ${pijl}
        ${fase(2, "Publish", "Press Publish, tick the marketplaces, confirm. Nothing goes live until you do this.", `<span class="ob-m-vak aan"></span>2dehands<br><span class="ob-m-vak aan"></span>Vinted<br><span class="ob-m-knop" style="margin-top:6px">Publish</span>`)}
        ${pijl}
        ${fase(3, "Placed for you", "The advert is created on each marketplace, as you. About a minute or two per advert.", `<div style="display:flex;align-items:center;gap:6px"><span class="ob-m-icoon oranje">${logo("vinted", 12)}<i>…</i></span>${PIJL_RECHTS.replace('width="22" height="22"', 'width="14" height="14"')}<span class="ob-m-icoon groen">${logo("vinted", 12)}<i>✓</i></span><span>live</span></div>`)}
        ${pijl}
        ${fase(4, "Sold once, gone everywhere", "Sold somewhere? The item comes off your other marketplaces, so you never sell it twice.", `<div style="display:flex;align-items:center;gap:6px"><span class="ob-m-icoon groen">${logo("vinted", 12)}<i>✓</i></span><b style="color:#059669">Sold</b></div><div style="margin-top:6px;display:flex;gap:6px"><span class="ob-m-icoon grijs">${logo("marktplaats", 12)}</span><span class="ob-m-icoon grijs">${logo("2dehands", 12)}</span><span>removed</span></div>`)}
      </div>
      <div class="ob-onder">
        <div class="ob-weg">${logo("marktplaats", 14)} ${logo("2dehands", 14)} ${logo("vinted", 14)} ${logo("facebook", 14)} <b>Through your Chrome.</b> The extension opens the site in your own Chrome, where you are signed in, and fills in the form. Keep that computer on while it works.</div>
        <div class="ob-weg">${logo("ebay", 14)} ${logo("shopify", 14)} <b>Through an official connection.</b> Connect once under Platforms. No Chrome needed for these.</div>
      </div>`;
  }

  function iconenHtml() {
    return `<div class="ob-uitleg-rij" aria-hidden="true">
        <span class="ob-uitleg-duim"></span>
        <div><div style="font-weight:700;font-size:13px">Martin D-28 Custom Ambertone</div><div style="font-size:12px;color:#64748b">€ 3.300</div></div>
        <div class="ob-uitleg-icons">
          ${[["marktplaats", "grijs", "", 1], ["2dehands", "oranje", "…", 2], ["vinted", "groen", "✓", 3], ["facebook", "rood", "!", 4], ["ebay", "paars", "⧉", 5]]
            .map(([p, kleur, badge, nr]) => `<span class="ob-pin"><b>${nr}</b><span class="ob-m-icoon ${kleur}">${logo(p, 12)}${badge ? `<i>${badge}</i>` : ""}</span></span>`).join("")}
        </div>
      </div>
      <div class="ob-legenda">${ICOON_UITLEG.map(([kleur, badge, titel, tekst], i) =>
        `<div><span class="ob-m-icoon ${kleur}">${logo("marktplaats", 12)}${badge ? `<i>${badge}</i>` : ""}</span><span><b>${i + 1}. ${titel}.</b> ${tekst}</span></div>`).join("")}</div>`;
  }

  function faqHtml() {
    let groep = "";
    return FAQ.map(([gr, vraag, antwoord]) => {
      const kop = gr !== groep ? `<div class="ob-faq-groep" data-groep="${esc(gr)}">${esc(gr)}</div>` : "";
      groep = gr;
      return `${kop}<details class="ob-faq" data-groep="${esc(gr)}"><summary>${esc(vraag)}${PIJL_OMLAAG}</summary><div class="ob-faq-antwoord">${antwoord}</div></details>`;
    }).join("");
  }

  function sectie(id, titel, sub, lijf) {
    return `<section class="ob-sectie" id="ob-${id}"><div class="ob-card">
      <div class="ob-sectie-kop"><h2>${titel}</h2>${sub ? `<p>${sub}</p>` : ""}</div>
      <div class="ob-sectie-lijf">${lijf}</div></div></section>`;
  }

  OB.renderHelp = function () {
    const doel = document.getElementById("view-help");
    if (!doel) return;
    zorgVoorStijl();
    if (doel.dataset.ob === "1") return;
    doel.dataset.ob = "1";
    doel.innerHTML = `<div class="ob-help">
      <div class="ob-help-kop">
        <div><h1>Help</h1><p>How Omnivaleur works, what you need per marketplace, and answers to the questions we get most.</p></div>
        <label class="ob-zoek"><svg width="15" height="15" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.9 3.5l4.3 4.3a1 1 0 01-1.4 1.4l-4.3-4.3A6 6 0 012 8z"/></svg>
          <input type="search" placeholder="Search help, e.g. “not signed in”" oninput="OB.zoek(this.value)" aria-label="Search help"></label>
      </div>
      <nav class="ob-chips" aria-label="Help sections">
        <a class="ob-chip" href="#" onclick="OB.naarHelp('werking');return false">How it works</a>
        <a class="ob-chip" href="#" onclick="OB.naarHelp('starten');return false">Getting started</a>
        <a class="ob-chip" href="#" onclick="OB.naarHelp('iconen');return false">The icons</a>
        <a class="ob-chip" href="#" onclick="OB.naarHelp('kanalen');return false">Marketplaces & costs</a>
        <a class="ob-chip" href="#" onclick="OB.naarHelp('vragen');return false">Questions</a>
        <a class="ob-chip" href="#" onclick="OB.naarHelp('contact');return false">Contact</a>
      </nav>
      ${sectie("werking", "How Omnivaleur works", "From item to advert to sale, in four steps.", flowHtml())}
      ${sectie("starten", "Getting started", "The same steps as on your dashboard. Hidden them there? <a href='#' onclick='OB.toonWeer();return false' style='color:var(--blue,#2563eb);font-weight:650'>Show them again</a>.",
        `<ol style="margin:0;padding-left:18px;font-size:13px;line-height:1.7;color:var(--muted,#64748b)">${OB.stappen({}).map((s) =>
          `<li style="margin-bottom:8px"><b style="color:var(--text,#0f172a)">${esc(s.titel)}${s.optioneel ? " (optional)" : ""}.</b> ${s.tekst}</li>`).join("")}</ol>`)}
      ${sectie("iconen", "The icons on each item", "Every item shows one icon per marketplace. Its colour tells you where the item really is.", iconenHtml())}
      ${sectie("kanalen", "What you need per marketplace", "And what the marketplaces themselves may charge. Those costs are between you and the marketplace; Omnivaleur never pays anything on your behalf.", `<div class="ob-kanalen">${KANALEN.map(kanaalKaart).join("")}</div>`)}
      ${sectie("vragen", "Questions", "", `<div id="ob-faq-lijst">${faqHtml()}</div><div class="ob-geen" id="ob-geen">Nothing found. Ask us directly below: we reply within one business day.</div>`)}
      <section class="ob-sectie" id="ob-contact"><div class="ob-card"><div style="padding:20px 22px;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap">
        <div><div style="font-weight:750;font-size:14px;margin-bottom:4px">Still stuck?</div>
          <div style="font-size:13px;color:var(--muted,#64748b)">Book a free video call with the founder, or email us: we reply within one business day.</div>
          <div style="font-size:11px;color:var(--muted,#64748b);margin-top:6px">Revaleur · KVK 86792423 · Kleine Melanen 5, 4614RG Bergen op Zoom</div></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <button onclick="typeof openFounderCall==='function'&&openFounderCall()" class="btn btn-primary btn-sm" style="white-space:nowrap">Talk to the founder</button>
          <a href="mailto:info@revaleur.com" class="btn btn-outline btn-sm" style="text-decoration:none;white-space:nowrap">Email support →</a>
        </div></div></div></section>
    </div>`;
  };

  OB.naarHelp = function (sectieId) {
    ga("help");
    OB.renderHelp();
    const el = document.getElementById(`ob-${sectieId}`);
    if (el) setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 30);
  };

  // De stijl meteen, niet pas als het dashboard tekent: het vraagteken naast
  // "Platforms" staat ook op Items en Stale.
  if (document.head) zorgVoorStijl();

  OB.zoek = function (tekst) {
    const q = String(tekst || "").trim().toLowerCase();
    const lijst = document.getElementById("ob-faq-lijst");
    if (!lijst) return;
    let gevonden = 0;
    lijst.querySelectorAll(".ob-faq").forEach((d) => {
      const raak = !q || d.textContent.toLowerCase().includes(q);
      d.style.display = raak ? "" : "none";
      if (q && raak) { d.open = true; gevonden++; } else if (!q) d.open = false;
    });
    lijst.querySelectorAll(".ob-faq-groep").forEach((kop) => {
      const zichtbaar = [...lijst.querySelectorAll(`.ob-faq[data-groep="${kop.dataset.groep}"]`)].some((d) => d.style.display !== "none");
      kop.style.display = zichtbaar ? "" : "none";
    });
    document.getElementById("ob-geen").style.display = q && !gevonden ? "block" : "none";
    ["werking", "starten", "iconen", "kanalen", "contact"].forEach((id) => {
      const s = document.getElementById(`ob-${id}`);
      if (!s) return;
      s.style.display = !q || s.textContent.toLowerCase().includes(q) || id === "contact" ? "" : "none";
    });
    if (q && gevonden) document.getElementById("ob-vragen").scrollIntoView({ block: "start" });
  };
})();
