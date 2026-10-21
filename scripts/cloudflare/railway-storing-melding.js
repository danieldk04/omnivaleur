// Cloudflare Worker: rode melding in het dashboard tijdens de Railway-storing (21-10-2026).
//
// Waarom hier en niet in frontend/app.html: het dashboard komt van Railway, en
// Railway rolt sinds 20-10 22:40 niets meer uit (status.railway.com: "builds
// paused"). Een wijziging in app.html komt dus pas live als de storing voorbij is,
// en dan hoort de melding juist weg te zijn. Cloudflare staat vóór de site en kan
// de melding wel in de pagina zetten.
//
// Vanzelf weg: zolang /health nog de commit van vóór de storing noemt, staat de
// melding erin. Noemt /health een andere commit, dan rolt Railway weer uit en gaat
// de pagina onveranderd door. Een open tabblad kijkt elke vijf minuten zelf ook.
// Daarna kan deze Worker (en zijn route omnivaleur.com/app*) weg.
//
// Route: omnivaleur.com/app* , bij een fout "fail open" (dan gewoon de pagina).

const OUDE_COMMIT = "01d19123";
const HEALTH_GELDIG_MS = 60 * 1000;

let health = { commit: null, ts: 0 };

async function serverDraaitNogOud(origin) {
  if (Date.now() - health.ts < HEALTH_GELDIG_MS) return health.commit === OUDE_COMMIT;
  try {
    const r = await fetch(origin + "/health", { cf: { cacheTtl: 0 } });
    const j = await r.json();
    health = { commit: String(j.commit || ""), ts: Date.now() };
  } catch (e) {
    // Niet te zeggen: dan niets veranderen. Liever een keer geen melding dan een
    // melding die blijft staan terwijl alles weer loopt.
    health = { commit: null, ts: Date.now() };
  }
  return health.commit === OUDE_COMMIT;
}

export const MELDING = `
<div id="railway-storing" role="alert" translate="no" style="display:flex;gap:12px;align-items:flex-start;background:#fee2e2;border:1px solid #fca5a5;border-left:4px solid #dc2626;color:#7f1d1d;border-radius:10px;padding:14px 18px;margin:0 0 20px;font-size:13px;line-height:1.55">
  <svg width="18" height="18" viewBox="0 0 20 20" fill="#dc2626" aria-hidden="true" style="flex-shrink:0;margin-top:1px"><path fill-rule="evenodd" d="M8.26 3.1c.77-1.33 2.7-1.33 3.47 0l6.02 10.42c.77 1.33-.19 3-1.73 3H3.97c-1.54 0-2.5-1.67-1.73-3L8.26 3.1zM10 7a1 1 0 00-1 1v3a1 1 0 102 0V8a1 1 0 00-1-1zm0 8a1.1 1.1 0 100-2.2 1.1 1.1 0 000 2.2z" clip-rule="evenodd"/></svg>
  <div>
    <div data-taal="en"><strong style="color:#991b1b">Updates are on hold because of an outage at our hosting provider.</strong><br>Railway, where Omnivaleur runs, has a major outage, so the improvements and fixes we made today can't go live yet. Your inventory and listings are safe and the dashboard keeps working. This notice disappears by itself as soon as updates go through again.</div>
    <div data-taal="nl" style="display:none"><strong style="color:#991b1b">Updates staan tijdelijk stil door een storing bij onze hostingpartij.</strong><br>Railway, waar Omnivaleur op draait, heeft een grote storing. Daardoor kunnen de verbeteringen en reparaties van vandaag nog niet live. Je voorraad en advertenties zijn veilig en het dashboard werkt gewoon. Deze melding verdwijnt vanzelf zodra updates weer doorkomen.</div>
  </div>
</div>
<script>
(function () {
  var oud = ${JSON.stringify(OUDE_COMMIT)};
  function taal() {
    var el = document.getElementById("railway-storing");
    if (!el) return;
    var nl = (document.documentElement.lang || "").toLowerCase().indexOf("nl") === 0;
    el.querySelector('[data-taal="en"]').style.display = nl ? "none" : "";
    el.querySelector('[data-taal="nl"]').style.display = nl ? "" : "none";
  }
  taal();
  new MutationObserver(taal).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
  document.addEventListener("DOMContentLoaded", taal);
  function kijk() {
    fetch("/health", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.commit && String(j.commit) !== oud) {
        var el = document.getElementById("railway-storing");
        if (el) el.remove();
        clearInterval(klok);
      }
    }).catch(function () {});
  }
  var klok = setInterval(kijk, 5 * 60 * 1000);
})();
</script>
`;

export default {
  async fetch(request) {
    const antwoord = await fetch(request);
    const url = new URL(request.url);
    const pad = url.pathname.replace(/\/+$/, "");
    const html = (antwoord.headers.get("content-type") || "").includes("text/html");
    if (request.method !== "GET" || pad !== "/app" || !html || antwoord.status !== 200) return antwoord;
    if (!(await serverDraaitNogOud(url.origin))) return antwoord;
    return new HTMLRewriter()
      .on("div.content", { element(el) { el.prepend(MELDING, { html: true }); } })
      .transform(antwoord);
  },
};
