async function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ serverUrl: "http://localhost:8001" }, (s) =>
      resolve(s.serverUrl.replace(/\/$/, ""))
    );
  });
}

async function checkLoginState() {
  const { authToken, userEmail } = await chrome.storage.sync.get(["authToken", "userEmail"]);
  if (authToken) {
    document.getElementById("loggedOut").style.display = "none";
    document.getElementById("loggedIn").style.display = "block";
    document.getElementById("userInfo").textContent = `Ingelogd als: ${userEmail || "onbekend"}`;
  } else {
    document.getElementById("loggedOut").style.display = "block";
    document.getElementById("loggedIn").style.display = "none";
  }
  const { serverUrl } = await chrome.storage.sync.get({ serverUrl: "http://localhost:8001" });
  document.getElementById("serverUrl").value = serverUrl;
  document.getElementById("serverUrl2").value = serverUrl;
}

document.getElementById("loginBtn").addEventListener("click", async () => {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  const statusEl = document.getElementById("authStatus");
  if (!email || !password) {
    statusEl.textContent = "Vul e-mail en wachtwoord in.";
    statusEl.className = "status error";
    return;
  }
  const serverUrl = await getServerUrl();
  try {
    const res = await fetch(`${serverUrl}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusEl.textContent = data.detail || "Inloggen mislukt.";
      statusEl.className = "status error";
      return;
    }
    await chrome.storage.sync.set({ authToken: data.access_token, userEmail: data.user.email });
    statusEl.textContent = "";
    checkLoginState();
  } catch (e) {
    statusEl.textContent = "Server niet bereikbaar.";
    statusEl.className = "status error";
  }
});

document.getElementById("registerBtn").addEventListener("click", async () => {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  const statusEl = document.getElementById("authStatus");
  if (!email || !password) {
    statusEl.textContent = "Vul e-mail en wachtwoord in.";
    statusEl.className = "status error";
    return;
  }
  const serverUrl = await getServerUrl();
  try {
    const res = await fetch(`${serverUrl}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusEl.textContent = data.detail || "Registratie mislukt.";
      statusEl.className = "status error";
      return;
    }
    statusEl.textContent = "Account aangemaakt! Bevestig je e-mail en log daarna in.";
    statusEl.className = "status success";
  } catch (e) {
    statusEl.textContent = "Server niet bereikbaar.";
    statusEl.className = "status error";
  }
});

document.getElementById("logoutBtn").addEventListener("click", async () => {
  await chrome.storage.sync.remove(["authToken", "userEmail"]);
  checkLoginState();
});

function saveUrl(inputId, statusId) {
  const url = document.getElementById(inputId).value.trim();
  chrome.storage.sync.set({ serverUrl: url }, () => {
    const el = document.getElementById(statusId);
    el.textContent = "Opgeslagen ✓";
    el.className = "status success";
    setTimeout(() => (el.textContent = ""), 2000);
  });
}

document.getElementById("saveUrl").addEventListener("click", () => saveUrl("serverUrl", "authStatus"));
document.getElementById("saveUrl2").addEventListener("click", () => saveUrl("serverUrl2", "status"));

checkLoginState();
