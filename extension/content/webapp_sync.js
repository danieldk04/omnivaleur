// Runs on crosslisteu.com — syncs the web app's auth token to the extension
(function () {
  const token = sessionStorage.getItem('cl_token');
  const email = sessionStorage.getItem('cl_email') || '';
  if (!token) return;

  chrome.runtime.sendMessage({ type: 'SYNC_TOKEN', token, email }, () => {
    if (chrome.runtime.lastError) {
      // Extension not installed or not responding — silently ignore
    }
  });
})();
