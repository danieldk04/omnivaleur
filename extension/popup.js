const SERVER_URL = "https://omnivaleur.com";

if (typeof gaEvent === "function") gaEvent("popup_opened", {});

async function checkLoginState() {
  // Ook het vernieuwbewijs meewegen: zonder dat kan de extensie na een uur geen
  // vers inlogbewijs meer halen en ligt hij stil, terwijl dit scherm "actief"
  // bleef melden. Precies zo stond hij een uur lang groen zonder iets te doen.
  const { authToken, refreshToken, userEmail } = await chrome.storage.sync.get(["authToken", "refreshToken", "userEmail"]);
  if (authToken && refreshToken) {
    document.getElementById("loggedOut").style.display = "none";
    document.getElementById("loggedIn").style.display = "flex";
    document.getElementById("userInfo").textContent = userEmail || "";
  } else {
    document.getElementById("loggedOut").style.display = "flex";
    document.getElementById("loggedIn").style.display = "none";
  }
}

document.getElementById("loginBtn").addEventListener("click", async () => {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  const statusEl = document.getElementById("authStatus");
  if (!email || !password) {
    statusEl.textContent = "Please enter your email and password.";
    return;
  }
  const btn = document.getElementById("loginBtn");
  btn.textContent = "Logging in…";
  btn.disabled = true;
  try {
    const res = await fetch(`${SERVER_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusEl.textContent = data.detail || "Login failed. Check your credentials.";
      btn.textContent = "Log in";
      btn.disabled = false;
      return;
    }
    // refreshToken ontbrak hier: checkLoginState() (zie boven) telt pas als
    // "ingelogd" wanneer ZOWEL authToken als refreshToken in de opslag staan,
    // dus zonder deze regel bleef het scherm na een geslaagde login gewoon op
    // "niet ingelogd" staan — precies zo gemeld door meerdere verkopers.
    await chrome.storage.sync.set({
      authToken: data.access_token, refreshToken: data.refresh_token, userEmail: data.user.email,
    });
    statusEl.textContent = "";
    btn.textContent = "Log in";
    btn.disabled = false;
    checkLoginState();
  } catch (e) {
    statusEl.textContent = "Could not reach server. Check your internet connection.";
    btn.textContent = "Log in";
    btn.disabled = false;
  }
});

document.getElementById("logoutBtn").addEventListener("click", async () => {
  await chrome.storage.sync.remove(["authToken", "userEmail"]);
  checkLoginState();
});

// Calm mode. Deze schakelaar schoof jarenlang heen en weer zonder dat er ook maar
// iets achter zat: er was geen enkele regel code die hem uitlas of opsloeg. De
// gebruiker dacht rustiger te publiceren en deed dat niet.
const calmToggle = document.getElementById("calmModeToggle");

async function toonCalm() {
  try {
    const s = await chrome.storage.sync.get("calmMode");
    calmToggle.checked = !!s.calmMode;
  } catch (_) { calmToggle.checked = false; }
}

// Verzendwijze. Bewust in storage.sync naast calmMode: het is een voorkeur van
// de verkoper, geen eigenschap van een los item, en hij hoort mee te reizen naar
// zijn andere computer.
const deliverySelect = document.getElementById("deliverySelect");
if (deliverySelect) {
  (async () => {
    try {
      const s = await chrome.storage.sync.get("deliveryMode");
      deliverySelect.value = s.deliveryMode || "beide";
    } catch (_) { deliverySelect.value = "beide"; }
  })();
  deliverySelect.addEventListener("change", async () => {
    try {
      await chrome.storage.sync.set({ deliveryMode: deliverySelect.value });
    } catch (_) { /* niet opgeslagen = onveranderd */ }
  });
}

calmToggle.addEventListener("change", async () => {
  try {
    await chrome.storage.sync.set({ calmMode: calmToggle.checked });
  } catch (_) {
    calmToggle.checked = !calmToggle.checked;   // niet opgeslagen = niet aan
  }
});

toonCalm();

// Toestemming voor Admarkt. De schakelaar toont de ECHTE stand (wat Chrome
// zegt), niet een eigen instelling — anders staat hij aan terwijl de toestemming
// er niet is en snapt niemand waarom de scan nog steeds niets vindt.
const ADMARKT = { origins: ["https://admarkt.marktplaats.nl/*"] };
const admarktToggle = document.getElementById("admarktToggle");

// De schakelaar volgt de VOORKEUR, niet meer de toestemming. Sinds 1.0.258 staat
// de toegang tot admarkt.marktplaats.nl vast in het manifest, dus
// permissions.contains() zegt voortaan altijd "ja" — dat is geen antwoord meer
// op de vraag "wil deze verkoper dat wij in Admarkt kijken".
async function toonAdmarkt() {
  try {
    const o = await chrome.storage.local.get(["admarkt_aan", "admarkt_ooit_aan"]);
    if (typeof o.admarkt_aan === "boolean") { admarktToggle.checked = o.admarkt_aan; return; }
    admarktToggle.checked = !!o.admarkt_ooit_aan || await chrome.permissions.contains(ADMARKT);
  } catch (_) { admarktToggle.checked = false; }
}

// Deze pagina dient twee doelen: het uitklapvenster onder het icoontje, en
// dezelfde pagina in een echt tabblad (?tab=1).
//
// WAAROM DAT NODIG IS. Chrome sluit het uitklapvenster op het moment dat hij
// een toestemmingsvraag toont. Daarmee verdwijnt ook de code die op het antwoord
// wacht, en als je het venster daarna opnieuw opent staat de schakelaar
// onveranderd uit. Voor de gebruiker ziet dat eruit alsof de schakelaar
// klemzit — precies wat er gebeurde. In een gewoon tabblad speelt dat niet.
const inTabblad = new URLSearchParams(location.search).get("tab") === "1";
const admarktUitleg = document.getElementById("admarktUitleg");

if (inTabblad) document.body.classList.add("als-pagina");
if (inTabblad && admarktUitleg) admarktUitleg.style.display = "block";

admarktToggle.addEventListener("change", async () => {
  const aan = admarktToggle.checked;
  // Eerst de voorkeur vastleggen: die overleeft een update van de extensie, een
  // herstart en een ingetrokken toestemming. Dat laatste is bij een klant echt
  // gebeurd, en de Admarkt-kant lag daarna een week stil.
  try {
    await chrome.storage.local.set(aan ? { admarkt_aan: true, admarkt_ooit_aan: true }
                                       : { admarkt_aan: false });
  } catch (_) {}

  // Uitzetten mag overal: dat vraagt Chrome niets en sluit dus niets.
  if (!aan) {
    try { await chrome.permissions.remove(ADMARKT); } catch (_) {}
    admarktToggle.checked = false;
    return;
  }

  // Aanzetten vanuit het uitklapvenster: eerst gewoon proberen. Lukt het (sommige
  // Chrome-versies laten het toe), dan is de gebruiker in één klik klaar.
  try {
    if (await chrome.permissions.contains(ADMARKT)) { admarktToggle.checked = true; return; }
    if (await chrome.permissions.request(ADMARKT)) { admarktToggle.checked = true; return; }
  } catch (_) {}

  if (!inTabblad) {
    // Niet gelukt en we zitten in het venstertje: dezelfde pagina in een tabblad
    // openen, waar de vraag wél blijft staan.
    try { await chrome.storage.local.set({ admarkt_aan: false }); } catch (_) {}
    admarktToggle.checked = false;
    chrome.tabs.create({ url: chrome.runtime.getURL("popup.html?tab=1") });
    window.close();
    return;
  }

  // Toestemming niet gekregen: dan is de voorkeur ook niet waargemaakt.
  try { await chrome.storage.local.set({ admarkt_aan: false }); } catch (_) {}
  admarktToggle.checked = false;
});

toonAdmarkt();
checkLoginState();


// De schakelaar "echt typen". Bewust een gewone voorkeur en geen
// toestemmingsvraag: Chrome laat "debugger" niet als optionele permissie toe, dus
// chrome.permissions.request() deed hier niets en de schakelaar leek stuk.
const toetsToggle = document.getElementById("toetsToggle");

if (toetsToggle) {
  chrome.storage.sync.get("magTypen").then((s) => {
    toetsToggle.checked = s.magTypen !== false;
  }).catch(() => { toetsToggle.checked = true; });

  toetsToggle.addEventListener("change", () => {
    chrome.storage.sync.set({ magTypen: toetsToggle.checked });
  });
}
