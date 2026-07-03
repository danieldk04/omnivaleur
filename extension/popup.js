const SERVER_URL = "https://crosslisteu.com";

async function checkLoginState() {
  const { authToken, userEmail } = await chrome.storage.sync.get(["authToken", "userEmail"]);
  if (authToken) {
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
    await chrome.storage.sync.set({ authToken: data.access_token, userEmail: data.user.email });
    statusEl.textContent = "";
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

checkLoginState();
