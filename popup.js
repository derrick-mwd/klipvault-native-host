// Cross-browser sendMessage wrapper — Firefox MV2 uses callbacks, Chrome MV3 uses Promises
function sendMessage(msg) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage(msg, (response) => {
        if (chrome.runtime.lastError) {
          console.warn('KlipVault message error:', chrome.runtime.lastError.message);
          resolve(null);
        } else {
          resolve(response);
        }
      });
    } catch (err) {
      console.warn('KlipVault sendMessage failed:', err);
      resolve(null);
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const listEl = document.getElementById('downloads-list');
  const totalEl = document.getElementById('total-count');
  const activeEl = document.getElementById('active-count');
  const clearBtn = document.getElementById('clear-btn');
  const premiumBanner = document.getElementById('premium-banner');
  const freeBanner = document.getElementById('free-banner');
  const usageFill = document.getElementById('usage-fill');
  const usageText = document.getElementById('usage-text');
  const batchSection = document.getElementById('batch-section');
  const batchCount = document.getElementById('batch-count');
  const batchList = document.getElementById('batch-list');
  const startBatchBtn = document.getElementById('start-batch-btn');
  const clearBatchBtn = document.getElementById('clear-batch-btn');

  function renderHistory(history) {
    if (!history || history.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          <p>No downloads yet</p>
          <span>Go to klipvault.xyz to start downloading</span>
        </div>
      `;
      totalEl.textContent = '0';
      activeEl.textContent = '0';
      return;
    }

    totalEl.textContent = history.length.toString();
    const active = history.filter((h) => h.status === 'downloading').length;
    activeEl.textContent = active.toString();

    listEl.innerHTML = history
      .slice(0, 20)
      .map((item) => {
        const date = new Date(item.timestamp).toLocaleDateString();
        const statusClass = item.status || 'downloading';
        const showFolderBtn = item.downloadId
          ? `<button class="folder-btn" data-id="${item.downloadId}" title="Open containing folder">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
            </button>`
          : '';
        const errorTooltip = item.error ? `title="${escapeHtml(item.error)}"` : '';
        return `
          <div class="download-item ${statusClass}">
            <div class="download-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            </div>
            <div class="download-info">
              <div class="download-title">${escapeHtml(item.title)}</div>
              <div class="download-meta">${item.quality} · ${item.ext.toUpperCase()} · ${date}</div>
            </div>
            <div class="download-actions">
              ${showFolderBtn}
              <div class="download-status ${statusClass}" ${errorTooltip}>${statusClass}</div>
            </div>
          </div>
        `;
      })
      .join('');

    // Attach folder-open handlers
    listEl.querySelectorAll('.folder-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const downloadId = parseInt(btn.dataset.id, 10);
        if (!isNaN(downloadId)) {
          try {
            chrome.downloads.show(downloadId);
          } catch (err) {
            console.warn('Could not open folder:', err);
          }
        }
      });
    });
  }

  function renderBatch(queue) {
    if (!queue || queue.length === 0) {
      batchSection.style.display = 'none';
      return;
    }
    batchSection.style.display = 'block';
    batchCount.textContent = queue.length.toString();
    batchList.innerHTML = queue
      .slice(0, 10)
      .map((item) => `
        <div class="batch-item">
          <div class="batch-status ${item.status || 'queued'}"></div>
          <div class="batch-title">${escapeHtml(item.title || 'Unknown')}</div>
          <div class="batch-meta">${item.quality || ''} · ${(item.ext || '').toUpperCase()}</div>
        </div>
      `)
      .join('');
    if (queue.length > 10) {
      batchList.innerHTML += `<div class="batch-item"><div class="batch-title" style="color:#64748b">+${queue.length - 10} more items...</div></div>`;
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  async function loadHistory() {
    const response = await sendMessage({ action: 'getHistory' });
    renderHistory(response?.history || []);
  }

  async function loadPremiumState() {
    const state = await sendMessage({ action: 'getPremiumState' });
    if (!state) {
      // Fallback: show free banner with zero usage if messaging fails
      if (premiumBanner) premiumBanner.style.display = 'none';
      if (freeBanner) {
        freeBanner.style.display = 'block';
        if (usageFill) usageFill.style.width = '0%';
        if (usageText) usageText.textContent = '0 / 3 free downloads today';
      }
      return;
    }

    if (state.isPremium) {
      if (premiumBanner) premiumBanner.style.display = 'block';
      if (freeBanner) freeBanner.style.display = 'none';
    } else {
      if (premiumBanner) premiumBanner.style.display = 'none';
      if (freeBanner) freeBanner.style.display = 'block';
      const pct = Math.min((state.downloadsToday / state.limit) * 100, 100);
      if (usageFill) {
        usageFill.style.width = pct + '%';
        usageFill.classList.toggle('full', pct >= 100);
      }
      if (usageText) {
        usageText.textContent = `${state.downloadsToday} / ${state.limit} free downloads today`;
      }
    }
  }

  async function loadBatchQueue() {
    const response = await sendMessage({ action: 'getBatchQueue' });
    renderBatch(response?.queue || []);
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
      await sendMessage({ action: 'clearHistory' });
      loadHistory();
      loadPremiumState(); // keep counter in sync
    });
  }

  if (startBatchBtn) {
    startBatchBtn.addEventListener('click', async () => {
      await sendMessage({ action: 'startBatch' });
      loadBatchQueue();
    });
  }

  if (clearBatchBtn) {
    clearBatchBtn.addEventListener('click', async () => {
      await sendMessage({ action: 'clearBatchQueue' });
      loadBatchQueue();
    });
  }

  // Live refresh while popup is open
  let refreshInterval;
  function startRefresh() {
    refreshInterval = setInterval(() => {
      loadHistory();
      loadPremiumState();
      loadBatchQueue();
    }, 2000);
  }
  function stopRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopRefresh();
    else startRefresh();
  });
  startRefresh();

  // Load everything
  loadHistory();
  loadPremiumState();
  loadBatchQueue();
});
