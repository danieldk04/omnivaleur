// Taal van het uitklapvenster. Standaard de taal van de browser; de EN/NL-knop
// bovenin onthoudt een eigen keuze. Elk element met data-t heeft de Engelse tekst
// als sleutel, tests/test_extensie_popup_taal.py bewaakt dat er een vertaling is.
const NL_TEKST = {
 "Automatic cross-listing extension": "Automatisch crosslisten",
 "Chrome won't let us see the selling sites": "Chrome laat ons de verkoopsites niet zien",
 "Every tab Omnivaleur opens stays empty because of this, and you have to stay with it. One click and that's over.": "Daardoor blijft elk tabblad dat Omnivaleur opent leeg en moet je er zelf bij blijven. Eén klik en dat is voorbij.",
 "Give access to all selling sites": "Toegang geven tot alle verkoopsites",
 "Not logged in, extension inactive": "Niet ingelogd, extensie staat uit",
 "Log in to activate the extension. Without login, jobs won't be picked up and nothing will be published.": "Log in om de extensie aan te zetten. Zonder inloggen worden opdrachten niet opgepakt en wordt er niets geplaatst.",
 "Email": "E-mailadres",
 "Password": "Wachtwoord",
 "Log in": "Inloggen",
 "Log out": "Uitloggen",
 "Extension active, ready to publish": "Extensie actief, klaar om te plaatsen",
 "Polls every": "Kijkt elke",
 "15 seconds": "15 seconden",
 "Calm mode": "Calm mode",
 "Spaces publishes 3 to 8 minutes apart and checks for sold items hourly instead of every 10 minutes: a lighter footprint that's less likely to trigger a platform's \"commercial activity\" review.": "Plaatst met 3 tot 8 minuten ertussen en kijkt elk uur naar verkochte artikelen in plaats van elke 10 minuten: rustiger, en minder kans op een controle op \"commerciële activiteit\" door een platform.",
 "Delivery &amp; parcel size": "Bezorging en pakketformaat",
 "Set once in the app under <strong>Preferences</strong>, together with your responsible party and relist rhythm. It applies to every listing we publish. <a href=\"https://omnivaleur.com/app\" target=\"_blank\">Open Preferences</a>": "Stel je één keer in de app in onder <strong>Voorkeuren</strong>, samen met je verantwoordelijke partij en herplaatsritme. Het geldt voor elke advertentie die we plaatsen. <a href=\"https://omnivaleur.com/app\" target=\"_blank\">Open Voorkeuren</a>",
 "Click the switch below. Chrome will now ask whether Omnivaleur may read your Admarkt page: choose <strong>Allow</strong>. You can close this tab afterwards.": "Klik op de schakelaar hieronder. Chrome vraagt nu of Omnivaleur je Admarkt-pagina mag lezen: kies <strong>Toestaan</strong>. Daarna kun je dit tabblad sluiten.",
 "Business account (Admarkt)": "Zakelijk account (Admarkt)",
 "Switch this on if your Marktplaats adverts are managed in Admarkt, the business side of Marktplaats. A scan then also reads that overview; without it, a business account looks empty. Chrome will ask your permission once.": "Zet dit aan als je Marktplaats-advertenties in Admarkt staan, het zakelijke deel van Marktplaats. Een scan leest dan ook dat overzicht; zonder dit lijkt een zakelijk account leeg. Chrome vraagt één keer om toestemming.",
 "Let Omnivaleur type like a keyboard": "Laat Omnivaleur typen als een toetsenbord",
 "Marktplaats sometimes says \"no advert text\" while your description is clearly there, and only accepts it after a real keystroke; nothing a script fires by itself counts. With this on, Omnivaleur presses that one key for you. Chrome shows a yellow \"debugging\" bar on the tab for those few seconds; that is Chrome's own notice, and it disappears straight after. Only used when the form actually complains. Switch it off and those listings stay open for you to finish by hand.": "Marktplaats zegt soms \"geen advertentietekst\" terwijl je omschrijving er gewoon staat, en accepteert hem pas na een echte toetsaanslag; wat een script zelf doet telt niet. Met deze schakelaar aan drukt Omnivaleur die ene toets voor je in. Chrome toont die paar seconden een gele \"foutopsporing\"-balk op het tabblad; dat is Chrome's eigen melding en die verdwijnt meteen weer. Alleen gebruikt als het formulier echt klaagt. Zet je hem uit, dan blijven die advertenties open staan zodat je ze zelf afmaakt.",
 " (just now)": " (net)",
 " (for {0} hour)": " (al {0} uur)",
 " (for {0} hours)": " (al {0} uur)",
 " (for {0} day)": " (al {0} dag)",
 " (for {0} days)": " (al {0} dagen)",
 "Not signed in to {0} in this browser{1}": "Niet ingelogd op {0} in deze browser{1}",
 "Nothing is published to {0} until you sign in there. Marktplaats and 2dehands have separate logins. Your queue stays as it is and starts again on its own once you are back in.": "Er wordt niets op {0} geplaatst tot je daar inlogt. Marktplaats en 2dehands hebben aparte inlogs. Je wachtrij blijft staan en loopt vanzelf door zodra je weer bent ingelogd.",
 "Sign in to {0}": "Inloggen op {0}",
 "Please enter your email and password.": "Vul je e-mailadres en wachtwoord in.",
 "Logging in…": "Bezig met inloggen…",
 "Login failed. Check your credentials.": "Inloggen mislukt. Controleer je gegevens.",
 "Could not reach server. Check your internet connection.": "Kan de server niet bereiken. Controleer je internetverbinding."
};

function kiesPopupTaal() {
  try {
    const eigen = localStorage.getItem("omni_popup_taal");
    if (eigen === "nl" || eigen === "en") return eigen;
  } catch (_) {}
  return (navigator.language || "").toLowerCase().startsWith("nl") ? "nl" : "en";
}
const POPUP_TAAL = kiesPopupTaal();

function t(tekst, ...waarden) {
  const uit = (POPUP_TAAL === "nl" && NL_TEKST[tekst]) || tekst;
  return uit.replace(/\{(\d)\}/g, (_, i) => waarden[+i] ?? "");
}

document.documentElement.lang = POPUP_TAAL;
if (POPUP_TAAL === "nl") {
  document.querySelectorAll("[data-t]").forEach((el) => {
    const sleutel = el.innerHTML.trim();
    if (NL_TEKST[sleutel]) el.innerHTML = NL_TEKST[sleutel];
  });
}
document.querySelectorAll("[data-taal]").forEach((knop) => {
  knop.setAttribute("aria-pressed", knop.dataset.taal === POPUP_TAAL ? "true" : "false");
  knop.addEventListener("click", () => {
    try { localStorage.setItem("omni_popup_taal", knop.dataset.taal); } catch (_) {}
    location.reload();
  });
});
