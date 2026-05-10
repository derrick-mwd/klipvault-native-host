// ClipVault Background Service Worker
// Handles downloads via chrome.downloads (direct URLs) or native messaging (HLS/yt-dlp)

const downloadQueue = [];
let downloadHistory = [];

// Cross-browser action API wrapper — Chrome MV3 uses chrome.action, Firefox MV2 uses chrome.browserAction
const actionAPI = chrome.action || chrome.browserAction || null;

function setBadge(text, color, tabId) {
  if (!actionAPI) return;
  try {
    const opts = { text };
    if (tabId !== undefined) opts.tabId = tabId;
    actionAPI.setBadgeText(opts);
    if (color) {
      actionAPI.setBadgeBackgroundColor({ color });
    }
  } catch (err) {
    console.warn('Badge API error:', err);
  }
}

// Batch / playlist queue
let batchQueue = [];
let batchProcessing = false;

// Premium / freemium state
const FREE_DAILY_LIMIT = 3;
let premiumState = {
  isPremium: false,
  downloadsToday: 0,
  lastResetDate: null,
};

// Native messaging state
let nativePort = null;
let nativeHostAvailable = false;

// Load premium state from storage
chrome.storage.local.get(['premiumState', 'downloadHistory'], (result) => {
  if (result.premiumState) {
    premiumState = result.premiumState;
    maybeResetDailyCounter();
  }
  if (result.downloadHistory) {
    downloadHistory = result.downloadHistory;
  }
});

function maybeResetDailyCounter() {
  const today = new Date().toISOString().split('T')[0];
  if (premiumState.lastResetDate !== today) {
    premiumState.downloadsToday = 0;
    premiumState.lastResetDate = today;
    savePremiumState();
  }
}

function savePremiumState() {
  chrome.storage.local.set({ premiumState });
}

function canDownload() {
  maybeResetDailyCounter();
  if (premiumState.isPremium) return { allowed: true };
  if (premiumState.downloadsToday < FREE_DAILY_LIMIT) return { allowed: true };
  return {
    allowed: false,
    reason: 'daily_limit',
    limit: FREE_DAILY_LIMIT,
    used: premiumState.downloadsToday,
  };
}

function incrementDownloadCount() {
  maybeResetDailyCounter();
  premiumState.downloadsToday += 1;
  savePremiumState();
}

function saveHistory() {
  chrome.storage.local.set({ downloadHistory: downloadHistory.slice(0, 100) });
}

function addToHistory(item) {
  downloadHistory.unshift({
    ...item,
    id: crypto.randomUUID(),
    timestamp: Date.now(),
  });
  saveHistory();
}

// Native Messaging: connect to the local yt-dlp host
function connectNativeHost() {
  if (nativePort) return nativePort;
  try {
    nativePort = chrome.runtime.connectNative('clipvault_host');
    nativePort.onMessage.addListener((msg) => {
      handleNativeMessage(msg);
    });
    nativePort.onDisconnect.addListener(() => {
      nativeHostAvailable = false;
      nativePort = null;
      const err = chrome.runtime.lastError;
      if (err) {
        console.log('Native host disconnected:', err.message);
      }
    });
    return nativePort;
  } catch (err) {
    console.warn('Failed to connect native host:', err);
    return null;
  }
}

function handleNativeMessage(msg) {
  if (msg.type === 'pong') {
    nativeHostAvailable = msg.ytDlpFound;
    // Broadcast status to popup and content scripts
    try {
      chrome.runtime.sendMessage({
        action: 'nativeHostStatus',
        connected: nativeHostAvailable,
        ytDlpPath: msg.ytDlpPath,
      });
    } catch {}
  } else if (msg.type === 'progress') {
    try {
      chrome.runtime.sendMessage({
        action: 'downloadProgress',
        percent: msg.percent,
        raw: msg.raw,
      });
    } catch {}
  } else if (msg.type === 'log') {
    try {
      chrome.runtime.sendMessage({
        action: 'downloadLog',
        data: msg.data,
      });
    } catch {}
  } else if (msg.type === 'started') {
    try {
      chrome.runtime.sendMessage({
        action: 'downloadStarted',
        message: msg.message,
      });
    } catch {}
  } else if (msg.type === 'complete') {
    try {
      chrome.runtime.sendMessage({
        action: 'downloadComplete',
        message: msg.message,
      });
    } catch {}
  } else if (msg.type === 'error') {
    try {
      chrome.runtime.sendMessage({
        action: 'downloadError',
        error: msg.error,
        message: msg.message,
      });
    } catch {}
  } else if (msg.type === 'done') {
    // Download finished, port will be reused
  }
}

function pingNativeHost() {
  return new Promise((resolve) => {
    const port = connectNativeHost();
    if (!port) {
      nativeHostAvailable = false;
      resolve({ available: false, error: 'Native messaging not supported or host not installed' });
      return;
    }
    // Wait a moment for pong response
    const timeout = setTimeout(() => {
      resolve({ available: false, error: 'Native host did not respond' });
    }, 5000);

    const handler = (msg) => {
      if (msg.type === 'pong') {
        clearTimeout(timeout);
        nativePort.onMessage.removeListener(handler);
        resolve({ available: msg.ytDlpFound, ytDlpPath: msg.ytDlpPath, searchLog: msg.searchLog });
      }
    };
    nativePort.onMessage.addListener(handler);
    port.postMessage({ action: 'ping' });
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'download') {
    const check = canDownload();
    if (!check.allowed) {
      sendResponse({ success: false, error: check.reason, limit: check.limit, used: check.used });
      return true;
    }
    const { payload } = message;
    handleDownload(payload)
      .then(() => sendResponse({ success: true }))
      .catch((err) => sendResponse({ success: false, error: err.message || String(err) }));
    return true;
  }

  if (message.action === 'getPremiumState') {
    maybeResetDailyCounter();
    sendResponse({
      isPremium: premiumState.isPremium,
      downloadsToday: premiumState.downloadsToday,
      limit: FREE_DAILY_LIMIT,
    });
  }

  if (message.action === 'setPremium') {
    premiumState.isPremium = !!message.isPremium;
    if (message.token) {
      premiumState.token = message.token;
    }
    savePremiumState();
    sendResponse({ success: true, isPremium: premiumState.isPremium });
  }

  if (message.action === 'getHistory') {
    sendResponse({ history: downloadHistory });
  }

  if (message.action === 'clearHistory') {
    downloadHistory = [];
    saveHistory();
    sendResponse({ success: true, downloadsToday: premiumState.downloadsToday });
  }

  if (message.action === 'removeHistoryItem') {
    downloadHistory = downloadHistory.filter((h) => h.id !== message.id);
    saveHistory();
    sendResponse({ success: true });
  }

  if (message.action === 'getNativeHostStatus') {
    pingNativeHost().then((status) => {
      sendResponse({
        available: status.available,
        ytDlpPath: status.ytDlpPath,
        searchLog: status.searchLog,
        error: status.error,
      });
    });
    return true;
  }

  if (message.action === 'pageDetected') {
    setBadge('✓', '#10b981', sender.tab?.id);
  }

  if (message.action === 'playlistDetected') {
    setBadge(String(message.count || '◎'), '#8b5cf6', sender.tab?.id);
    sendResponse({ success: true });
  }

  if (message.action === 'addToBatch') {
    const items = Array.isArray(message.items) ? message.items : [message.items];
    const check = canDownload();
    if (!check.allowed && !premiumState.isPremium) {
      sendResponse({ success: false, error: check.reason, limit: check.limit, used: check.used });
      return true;
    }
    batchQueue.push(...items.map((item) => ({ ...item, status: 'queued', id: crypto.randomUUID() })));
    sendResponse({ success: true, queued: batchQueue.length });
  }

  if (message.action === 'getBatchQueue') {
    sendResponse({ queue: batchQueue, processing: batchProcessing });
  }

  if (message.action === 'clearBatchQueue') {
    batchQueue = [];
    batchProcessing = false;
    sendResponse({ success: true });
  }

  if (message.action === 'startBatch') {
    processBatchQueue();
    sendResponse({ success: true });
  }

  return true;
});

async function handleDownload(payload) {
  const { url, directUrl, title, ext, quality, isHls, httpHeaders, cookies } = payload;

  // HLS or complex streams → use native messaging (yt-dlp)
  const needsNative = isHls || (directUrl && directUrl.includes('.m3u8'));

  if (needsNative) {
    return await handleNativeDownload(payload);
  }

  // Direct URLs → use chrome.downloads (fast path)
  return await handleDirectDownload(payload);
}

async function handleNativeDownload(payload) {
  const { url, title, ext, quality, formatId, isHls, cookies } = payload;

  // Ensure native host is connected
  const port = connectNativeHost();
  if (!port) {
    throw new Error('Native host not connected. Install yt-dlp and the ClipVault native host. See the setup guide on the website.');
  }

  // Verify yt-dlp is available
  const status = await pingNativeHost();
  if (!status.available) {
    const log = status.searchLog ? status.searchLog.join('\n') : 'No search log available';
    throw new Error(`yt-dlp not found. Install it with: pip install yt-dlp\n\nSearch log:\n${log}`);
  }

  incrementDownloadCount();

  addToHistory({
    title,
    url: url || directUrl,
    filename: sanitizeFilename(`${title} [${quality}].${ext}`),
    quality,
    ext,
    status: 'downloading',
  });

  // Send download command to native host
  port.postMessage({
    action: 'download',
    payload: {
      url: url || directUrl,
      title,
      formatId: formatId || quality,
      isHls: !!isHls,
      cookies: cookies || '',
    },
  });
}

async function handleDirectDownload(payload) {
  const { directUrl, title, ext, quality, httpHeaders } = payload;

  const filename = sanitizeFilename(`${title} [${quality}].${ext}`);

  incrementDownloadCount();

  // Build headers array for chrome.downloads.download()
  // Chrome blocks "unsafe" request headers that it controls internally
  const BLOCKED_HEADERS = new Set([
    'cookie', 'origin', 'host', 'connection', 'keep-alive', 'proxy-authentication',
    'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade',
    'via', 'user-agent', 'referer', 'sec-ch-ua', 'sec-ch-ua-mobile',
    'sec-ch-ua-platform', 'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site',
    'sec-fetch-user', 'accept-encoding', 'accept-language', 'cache-control',
    'content-length', 'if-match', 'if-none-match', 'if-modified-since',
    'if-unmodified-since', 'if-range', 'range', 'expect', 'max-forwards',
    'pragma', 'dnt', 'access-control-request-headers', 'access-control-request-method',
  ]);

  const downloadHeaders = [];
  if (httpHeaders && typeof httpHeaders === 'object') {
    for (const [name, value] of Object.entries(httpHeaders)) {
      if (!BLOCKED_HEADERS.has(name.toLowerCase())) {
        downloadHeaders.push({ name, value });
      }
    }
  }

  const downloadId = await new Promise((resolve, reject) => {
    const opts = {
      url: directUrl,
      filename: `ClipVault/${filename}`,
      saveAs: false,
    };
    if (downloadHeaders.length > 0) {
      opts.headers = downloadHeaders;
    }
    chrome.downloads.download(opts, (id) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(id);
      }
    });
  });

  addToHistory({
    title,
    url: directUrl,
    filename,
    quality,
    ext,
    downloadId,
    status: 'downloading',
  });

  // Monitor download completion
  chrome.downloads.onChanged.addListener(function onChanged(delta) {
    if (delta.id !== downloadId) return;

    if (delta.state?.current === 'complete') {
      updateDownloadStatus(downloadId, 'complete');
      chrome.downloads.onChanged.removeListener(onChanged);
    }

    if (delta.error?.current) {
      updateDownloadStatus(downloadId, 'error', delta.error.current);
      chrome.downloads.onChanged.removeListener(onChanged);
    }
  });
}

function updateDownloadStatus(downloadId, status, error) {
  const item = downloadHistory.find((h) => h.downloadId === downloadId);
  if (item) {
    item.status = status;
    if (error) item.error = error;
    saveHistory();
  }
}

function sanitizeFilename(name) {
  return name.replace(/[<>:"/\\|?*]/g, '').substring(0, 100) || 'download';
}

async function processBatchQueue() {
  if (batchProcessing || batchQueue.length === 0) return;
  batchProcessing = true;

  while (batchQueue.length > 0) {
    const check = canDownload();
    if (!check.allowed) {
      batchQueue.forEach((item) => { item.status = 'blocked'; });
      break;
    }

    const item = batchQueue[0];
    item.status = 'downloading';
    try {
      await handleDownload(item);
      item.status = 'complete';
    } catch (err) {
      item.status = 'error';
      console.error('Batch item failed:', err);
    }
    batchQueue.shift();
  }

  batchProcessing = false;
  setBadge('', null);
}
