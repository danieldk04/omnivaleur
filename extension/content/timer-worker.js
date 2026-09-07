// Draait de pauzes voor de content-scripts (zie sleep() in shared.js).
//
// Een setTimeout hier, in een Worker, valt niet onder Chrome's "intensive
// throttling" van een verborgen tabblad. Op de pagina zelf zakt setTimeout na
// 5 minuten verborgen terug naar één keer per minuut, waardoor lange
// Vinted-klussen stilvielen zodra de verkoper naar een ander tabblad ging.
self.onmessage = (e) => {
  const data = e.data || {};
  setTimeout(() => self.postMessage(data.id), data.ms);
};
