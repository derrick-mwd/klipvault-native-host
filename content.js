// KlipVault Content Script
// Bridges the website and the extension via postMessage

// Signal to the website that the extension is installed
const marker = document.createElement('div');
marker.id = 'klipvault-extension-marker';
marker.style.display = 'none';
document.documentElement.appendChild(marker);
document.documentElement.setAttribute('data-klipvault-ext', 'installed');
(window).klipvaultExtension = true;

// Listen for messages from the website
window.addEventListener('message', (event) => {
  if (event.source !== window) return;
  if (!event.data || event.data.source !== 'klipvault-web') return;

  const { action, payload } = event.data;

  if (action === 'download') {
    chrome.runtime.sendMessage({
      action: 'download',
      payload,
    }, (response) => {
      if (chrome.runtime.lastError) {
        window.postMessage(
          { source: 'klipvault-ext', action: 'downloadError', error: chrome.runtime.lastError.message },
          '*'
        );
        return;
      }
      if (response && !response.success) {
        window.postMessage(
          { source: 'klipvault-ext', action: 'downloadError', error: response.error, limit: response.limit, used: response.used },
          '*'
        );
      } else if (response && response.success) {
        window.postMessage(
          { source: 'klipvault-ext', action: 'downloadStarted' },
          '*'
        );
      }
    });
  }

  if (action === 'extensionDownload') {
    chrome.runtime.sendMessage({
      action: 'extensionDownload',
      payload,
    }, (response) => {
      if (chrome.runtime.lastError) {
        window.postMessage(
          { source: 'klipvault-ext', action: 'downloadError', error: chrome.runtime.lastError.message },
          '*'
        );
        return;
      }
      if (response && !response.success) {
        window.postMessage(
          { source: 'klipvault-ext', action: 'downloadError', error: response.error, limit: response.limit, used: response.used },
          '*'
        );
      } else if (response && response.success) {
        window.postMessage(
          { source: 'klipvault-ext', action: 'downloadStarted' },
          '*'
        );
      }
    });
  }

  if (action === 'setPremium') {
    chrome.runtime.sendMessage({
      action: 'setPremium',
      isPremium: true,
      token: payload?.token || null,
    }, (response) => {
      if (!chrome.runtime.lastError && response?.success) {
        window.postMessage(
          { source: 'klipvault-ext', action: 'premiumSet' },
          '*'
        );
      }
    });
  }

  if (action === 'ping') {
    window.postMessage(
      { source: 'klipvault-ext', action: 'pong' },
      '*'
    );
  }
});

// Auto-detect video pages and show download button
const PLATFORM_PATTERNS = [
  { host: 'youtube.com', name: 'YouTube' },
  { host: 'youtu.be', name: 'YouTube' },
  { host: 'vimeo.com', name: 'Vimeo' },
  { host: 'dailymotion.com', name: 'Dailymotion' },
];

const currentPlatform = PLATFORM_PATTERNS.find((p) =>
  location.hostname.includes(p.host)
);

if (currentPlatform) {
  // Notify background that we're on a video page
  try {
    chrome.runtime.sendMessage({
      action: 'pageDetected',
      platform: currentPlatform.name,
      url: location.href,
    });
  } catch (err) {
    // Background not ready — ignore
  }
}

// Detect YouTube playlists
if (location.hostname.includes('youtube.com') && location.search.includes('list=')) {
  const listMatch = location.search.match(/[?&]list=([^&]+)/);
  if (listMatch) {
    try {
      chrome.runtime.sendMessage({
        action: 'playlistDetected',
        listId: listMatch[1],
        url: location.href,
      });
    } catch (err) {
      // Background not ready — ignore
    }
  }
}
