// Minimal stand-in for the extension APIs the content script uses. Everything it
// asks the background worker to do is answered by the real background functions
// (see mw-functions.js, sliced out of background.js at build time).
window.__log = [];
window.__result = null;

const JOB = {
  id: "test-job-1",
  serverUrl: "https://example.invalid",
  action: "create",
  payload: {
    title: "(1339) Khaki Profuomo Zip Vest - Men S - Very Good",
    description: "Mooi khaki vest van Profuomo.\n\nMaat S, merino wol.\nIn zeer goede staat.",
    price: 29.99,
    condition: "goed",
    size: "S",
    brand: "Profuomo",
    color: "Beige",
    material: "merino",
    category: "vesten",
    gender: "heren",
    photo_urls: ["https://example.invalid/a.jpg", "https://example.invalid/b.jpg"],
  },
};

const PIXEL = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

const __t0 = Date.now();
function logLine(text) {
  text = `[${((Date.now() - __t0) / 1000).toFixed(1)}s] ${text}`;
  window.__log.push(text);
  const el = document.getElementById("log");
  if (el) {
    el.insertAdjacentHTML("beforeend", `<div>${String(text).replace(/</g, "&lt;")}</div>`);
    el.scrollTop = el.scrollHeight;
  }
}

window.chrome = {
  runtime: {
    lastError: undefined,
    async sendMessage(msg, cb) {
      const done = (v) => cb && cb(v);
      try {
        switch (msg.type) {
          case "GET_JOB":            return done({ job: JOB });
          case "LOG":                logLine(msg.text); return done(true);
          case "FILL_DESC":          return done(await _mwFillDescription(msg.selector, msg.text));
          case "FILL_HIDDEN_DESC":   return done(_mwFillHiddenDescription(msg.text));
          case "READ_HIDDEN_DESC":   return done(_mwHiddenDescriptionValue());
          case "BLUR_DESC":          return done(_mwBlurDescription(msg.selector));
          case "ENFORCE_DESC":       return done(_mwEnforceDescription(msg.text, msg.durationMs));
          case "NUDGE_DESC":         return done(_mwNudgeDescription(msg.selector));
          case "DESCRIBE_DESC":      return done(_mwDescribeDescriptionFields());
          case "FILL_BRAND":         return done(await _mwFillBrand(msg.brand));
          case "FETCH_PHOTO":        return done({ ok: true, dataUrl: PIXEL });
          case "JOB_DONE":
            window.__result = { ok: true, ...msg };
            logLine("→ JOB_DONE " + JSON.stringify(msg.result));
            return done({ ok: true });
          case "JOB_ERROR":
            window.__result = { ok: false, ...msg };
            logLine("→ JOB_ERROR " + msg.error);
            return done({ ok: true });
          default:
            logLine("(shim) onbekend bericht: " + msg.type);
            return done(false);
        }
      } catch (e) {
        logLine("(shim) FOUT in " + msg.type + ": " + e.message);
        return done(false);
      }
    },
  },
};
