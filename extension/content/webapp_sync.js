// Runs on omnivaleur.com — bridges the web app and the extension.
//
// Two jobs:
//  1. Sync the web app's auth token into the extension, so the user never has to
//     type their Omnivaleur credentials a second time.
//  2. Announce that the extension exists, and whether it's signed in. The
//     dashboard has no other way to know: it used to just claim "Extension
//     active" unconditionally and ask the user to self-declare that they'd
//     installed it. Now it can tell the difference between missing, signed out,
//     and working.
(function () {
  const EXT = "omnivaleur-extension";
  const PAGE = "omnivaleur-page";

  // Het dashboard bewaart dit inlogbewijs sinds 08-09-2026 in localStorage (dan
  // overleeft het het sluiten van een tabblad). Oudere pagina's zetten het in
  // sessionStorage. Lees allebei, localStorage eerst, zodat het niet uitmaakt
  // welke kant van die wijziging draait — anders vindt de extensie geen token
  // meer, kan ze haar sessie niet verversen en valt ze na een uur stil.
  function leesSessie(sleutel) {
    try { const v = localStorage.getItem(sleutel); if (v !== null) return v; } catch (e) {}
    try { return sessionStorage.getItem(sleutel); } catch (e) { return null; }
  }

  function syncToken() {
    const token = leesSessie("cl_token");
    const email = leesSessie("cl_email") || "";
    // The refresh token lets the extension mint fresh access tokens on its own,
    // so background jobs don't die on "Sessie verlopen" once the ~1h access
    // token expires with no dashboard tab open to re-push one.
    const refresh = leesSessie("cl_refresh") || "";
    if (!token) return Promise.resolve(false);
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "SYNC_TOKEN", token, email, refresh }, () => {
        // lastError = extension reloading/gone. Never throw into the page.
        resolve(!chrome.runtime.lastError);
      });
    });
  }

  function authState() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "GET_AUTH_STATE" }, (res) => {
        resolve(chrome.runtime.lastError ? null : res);
      });
    });
  }

  async function announce() {
    // Push the token first: if the user is logged in to the dashboard, the
    // extension should be signed in by the time we report state.
    await syncToken();
    const state = await authState();
    let version = "";
    try { version = chrome.runtime.getManifest().version; } catch (e) { /* worker gone */ }
    window.postMessage({
      source: EXT,
      type: "EXT_HELLO",
      version,
      signedIn: !!(state && state.signedIn),
      email: (state && state.email) || "",
    }, window.location.origin);
  }

  // The dashboard pings on load and after login; answering is what makes
  // detection work without the page having to guess.
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const d = event.data;
    if (!d || d.source !== PAGE) return;
    if (d.type === "EXT_PING") announce();
    // "Er staat werk klaar." Zonder dit wachtte de extensie tot haar eigen ronde
    // (die Chrome niet vaker dan elke halve minuut laat lopen) voordat ze ook
    // maar keek — pure stiltetijd na elke publicatie. Het token gaat mee, want
    // een net gewekte service worker kan een verlopen sessie hebben.
    // Het dashboard heeft de vernieuwsleutel doorgedraaid. Die van ons is
    // daarmee dood; zonder dit valt de extensie een uur later stil met "sign in
    // again to keep publishing" terwijl de verkoper gewoon ingelogd is.
    if (d.type === "EXT_SYNC_TOKEN") syncToken().catch(() => {});
    if (d.type === "EXT_POLL_NOW") {
      syncToken()
        .then(() => chrome.runtime.sendMessage({ type: "POLL_NOW" }, () => chrome.runtime.lastError))
        .catch(() => { /* extensie herlaadt — de gewone ronde pakt het op */ });
    }
  });

  // De service worker heeft de vernieuwsleutel doorgedraaid. Die van deze pagina
  // is daarmee dood, en zonder dit zou de verkoper bij zijn volgende bezoek
  // worden uitgelogd terwijl er niets aan de hand is. Zie de uitleg bij
  // stuurTokenNaarDashboard in background.js.
  function schrijfSessie(sleutel, waarde) {
    try { localStorage.setItem(sleutel, waarde); } catch (e) {}
    try { sessionStorage.setItem(sleutel, waarde); } catch (e) {}
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.type !== "TOKEN_VERNIEUWD" || !msg.token) return;
    schrijfSessie("cl_token", msg.token);
    if (msg.refresh) schrijfSessie("cl_refresh", msg.refresh);
    // Ook meteen aan de draaiende pagina vertellen, zodat die niet eerst een
    // mislukt verzoek hoeft te doen om erachter te komen.
    window.postMessage({ source: EXT, type: "EXT_TOKEN", token: msg.token },
                       window.location.origin);
  });

  announce();
})();
