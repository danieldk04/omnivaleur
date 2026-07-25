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

  function syncToken() {
    const token = sessionStorage.getItem("cl_token");
    const email = sessionStorage.getItem("cl_email") || "";
    // The refresh token lets the extension mint fresh access tokens on its own,
    // so background jobs don't die on "Sessie verlopen" once the ~1h access
    // token expires with no dashboard tab open to re-push one.
    const refresh = sessionStorage.getItem("cl_refresh") || "";
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
  });

  announce();
})();
