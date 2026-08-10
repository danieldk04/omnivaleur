// Reports what the run actually achieved, so the outcome can be read without
// interpreting the log by hand.
(() => {
  const t0 = Date.now();
  const v = document.getElementById("verdict");
  const val = (sel) => (document.querySelector(sel)?.value || "").trim();

  setInterval(() => {
    const s = window.__mock;
    const done = window.__result;
    const sub = window.__submit;
    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    v.textContent = [
      `verstreken:    ${secs}s`,
      `titel:         ${val('[data-testid="title--input"]') || "—"}`,
      `beschrijving:  ${val('[data-testid="description--input"]').length} tekens`,
      `foto's:        ${document.querySelectorAll("#thumbs img").length}`,
      `categorie:     ${s.category || "—"}`,
      `prijs:         ${val('[data-testid="price-input--input"]') || "—"}`,
      `staat:         ${s.condition || "—"}`,
      `maat:          ${s.size || "—"}`,
      `merk:          ${s.brand || "—"}`,
      `KLEUR:         ${s.colours.join(", ") || "— LEEG —"}`,
      `materiaal:     ${s.material.join(", ") || "—"}`,
      "",
      `upload geklikt: ${sub ? "ja" : "nee"}${sub && sub.missing.length ? " (geweigerd: " + sub.missing.join(", ") + ")" : ""}`,
      `uitkomst:      ${done ? (done.ok ? "JOB_DONE " + JSON.stringify(done.result) : "JOB_ERROR " + done.error) : "bezig…"}`,
    ].join("\n");
  }, 250);
})();
