// GA4 analytics for the Omnivaleur extension.
//
// Manifest V3 blocks gtag.js (it loads a remote script, which the extension
// CSP forbids), so events are sent through the GA4 Measurement Protocol with a
// plain fetch — usable from both the service worker (via importScripts) and the
// popup (via a <script> tag).

const GA_MEASUREMENT_ID = "G-VJ5BVD3GCH";

// Measurement Protocol API secret. Create it in:
//   GA → Admin → Data streams → (Omnivaleur web stream) → Measurement Protocol
//   API secrets → Create.
// Safe to ship in the extension: the secret can only WRITE events, never read
// data. While empty, analytics is a no-op so the extension keeps working.
const GA_API_SECRET = "AHRl1iMJSx2ttoi4v7IPMQ";

// A stable per-install pseudonymous id (not tied to any user account).
async function gaClientId() {
  const { ga_client_id } = await chrome.storage.local.get("ga_client_id");
  if (ga_client_id) return ga_client_id;
  const id =
    (self.crypto && crypto.randomUUID && crypto.randomUUID()) ||
    `${Date.now()}.${Math.random().toString(36).slice(2)}`;
  await chrome.storage.local.set({ ga_client_id: id });
  return id;
}

// Fire a GA4 event. Never throws — analytics must not break the extension.
async function gaEvent(name, params = {}) {
  try {
    if (!GA_API_SECRET) return; // not configured yet
    const clientId = await gaClientId();
    await fetch(
      `https://www.google-analytics.com/mp/collect?measurement_id=${GA_MEASUREMENT_ID}&api_secret=${GA_API_SECRET}`,
      {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId,
          // engagement_time_msec keeps the event out of GA's "(not set)"
          // engagement bucket so it shows up in standard reports.
          //
          // De drie regels daaronder houden dit telemetrieverkeer uit de
          // marketingrapporten. Zonder die regels stond de extensie op
          // 29-08-2026 als "(not set)" in Verkeersacquisitie: 33 sessies met
          // 1.511 gebeurtenissen — bijna de helft van alles in de property —
          // met 0% betrokkenheid, want deze meldingen komen niet van een
          // pagina en Google kan ze dus nergens plaatsen. Daarmee zat er een
          // "kanaal" in de lijst dat geen kanaal is, precies in het rapport
          // waarin je wilt zien wat je kanalen opleveren.
          //
          //   traffic_type: het haakje waar GA's ingebouwde filter voor intern
          //     verkeer op aangrijpt. Staat dat filter aan, dan komen deze
          //     meldingen de property niet eens meer in.
          //   campaign_source/medium: het vangnet als dat filter uit staat.
          //     Dan staat er tenminste een leesbare naam in plaats van
          //     "(not set)".
          //
          // Dit kan het verkeer van een échte bezoeker niet vervuilen: de
          // client_id hierboven is een eigen id per installatie en heeft niets
          // te maken met de cookie van de website.
          events: [
            {
              name,
              params: {
                engagement_time_msec: 1,
                traffic_type: "internal",
                campaign_source: "omnivaleur-extensie",
                campaign_medium: "app",
                ...params,
              },
            },
          ],
        }),
      }
    );
  } catch (e) {
    console.debug("[Omnivaleur] analytics failed:", e);
  }
}

// Expose globally for the popup (module-free) and importScripts contexts.
if (typeof self !== "undefined") {
  self.gaEvent = gaEvent;
  self.gaClientId = gaClientId;
}
