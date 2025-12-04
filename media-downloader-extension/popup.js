// For production: 'https://pyd.snpsujon.me'
// For local development: 'http://127.0.0.1:5000' (or 'http://127.0.0.1:5020' if using Docker)
const BASE_URL = 'http://127.0.0.1:5000';
const downloadsContainer = document.getElementById('downloads');
const submitBtn = document.getElementById('submit');
const urlInput = document.getElementById('url');
const emptyState = document.getElementById('empty-state');

const activeDownloads = new Map();

// Auto-fill URL from current tab
document.addEventListener('DOMContentLoaded', () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs.length > 0) {
      urlInput.value = tabs[0].url || '';
    }
  });
  updateEmptyState();
});

function updateEmptyState() {
  if (downloadsContainer.children.length === 0) {
    emptyState.style.display = 'block';
  } else {
    emptyState.style.display = 'none';
  }
}

function getStatusIcon(status) {
  if (status === 'Completed') return '✅';
  if (status.startsWith('Error')) return '❌';
  if (status === 'Downloading') return '⬇️';
  if (status === 'Processing...') return '⚙️';
  return '🔄';
}

function createDownloadCard(downloadId) {
  const card = document.createElement('div');
  card.className = 'download-item';
  card.id = `download-${downloadId}`;
  
  card.innerHTML = `
    <div class="download-header">
      <div class="download-status">
        <span class="status-icon" id="icon-${downloadId}">🔄</span>
        <span id="status-${downloadId}">Starting...</span>
      </div>
      <button class="cancel-btn" id="cancel-${downloadId}">✕ Cancel</button>
    </div>
    <div class="progress-container">
      <div class="progress-bar">
        <div class="progress-fill" id="progress-${downloadId}"></div>
      </div>
      <div class="progress-text" id="progress-text-${downloadId}">0%</div>
    </div>
    <a href="#" class="download-link hidden" id="link-${downloadId}" target="_blank" rel="noopener noreferrer">
      📥 Download File
    </a>
  `;
  
  downloadsContainer.prepend(card);
  updateEmptyState();

  document.getElementById(`cancel-${downloadId}`).addEventListener('click', () => {
    if (activeDownloads.has(downloadId)) {
      clearInterval(activeDownloads.get(downloadId).intervalId);
      activeDownloads.delete(downloadId);
    }
    card.remove();
    updateEmptyState();
  });
}

submitBtn.addEventListener('click', async () => {
  const url = urlInput.value.trim();
  if (!url) {
    alert('⚠️ Please enter a URL');
    return;
  }
  
  const format = document.getElementById('format').value;
  const quality = document.getElementById('quality').value;
  const playlist = document.getElementById('playlist')?.checked || false;

  submitBtn.disabled = true;
  submitBtn.textContent = '⏳ Starting...';

  try {
    const formData = new URLSearchParams();
    formData.append('url', url);
    formData.append('format', format);
    formData.append('quality', quality);
    if (playlist) formData.append('playlist', 'on');

    // Get extension version and browser info
    let extensionVersion = '1.0';
    try {
      const manifest = chrome.runtime.getManifest();
      extensionVersion = manifest.version || '1.0';
    } catch (e) {
      console.log('Could not get extension version:', e);
    }
    
    // Get browser info
    const browserInfo = navigator.userAgent;
    const platform = navigator.platform;
    const language = navigator.language;

    const response = await fetch(`${BASE_URL}/api/download`, {
      method: 'POST',
      headers: {
        'X-Extension-Request': 'true',
        'X-Extension-Version': extensionVersion,
        'X-Platform': platform,
        'X-Language': language,
        'User-Agent': browserInfo
      },
      body: formData
    });

    const data = await response.json();

    if (data.success && data.session_id) {
      const downloadId = data.session_id;

      // Clear URL input after starting download
      urlInput.value = '';

      createDownloadCard(downloadId);

      const statusEl = document.getElementById(`status-${downloadId}`);
      const iconEl = document.getElementById(`icon-${downloadId}`);
      const progressFillEl = document.getElementById(`progress-${downloadId}`);
      const progressTextEl = document.getElementById(`progress-text-${downloadId}`);
      const linkEl = document.getElementById(`link-${downloadId}`);
      const cardEl = document.getElementById(`download-${downloadId}`);

      const intervalId = setInterval(async () => {
        try {
          const progressRes = await fetch(`${BASE_URL}/api/progress`, {
            method: 'GET',
            headers: {
              'X-Session-ID': downloadId
            }
          });
          const progress = await progressRes.json();

          const status = progress.status || 'Unknown';
          const percent = progress.percent || '0%';
          const percentNum = parseFloat(percent) || 0;

          // Update status and icon
          statusEl.textContent = `${status} ${percent !== '0%' ? `(${percent})` : ''}`;
          iconEl.textContent = getStatusIcon(status);
          
          // Update progress bar
          progressFillEl.style.width = `${percentNum}%`;
          progressTextEl.textContent = percent;

          if (status === 'Completed' && progress.filename) {
            clearInterval(intervalId);
            activeDownloads.delete(downloadId);
            
            linkEl.href = `${BASE_URL}/downloads/${progress.filename}`;
            linkEl.classList.remove('hidden');
            statusEl.textContent = '✅ Download completed';
            iconEl.textContent = '✅';
            cardEl.classList.add('success-state');
            progressFillEl.style.width = '100%';
            progressTextEl.textContent = '100%';
          }

          if (status.startsWith('Error')) {
            clearInterval(intervalId);
            activeDownloads.delete(downloadId);
            statusEl.textContent = `❌ ${status}`;
            iconEl.textContent = '❌';
            cardEl.classList.add('error-state');
            progressFillEl.style.width = '100%';
            progressTextEl.textContent = 'Error';
          }
        } catch (e) {
          clearInterval(intervalId);
          activeDownloads.delete(downloadId);
          statusEl.textContent = '❌ Error fetching progress';
          iconEl.textContent = '❌';
          cardEl.classList.add('error-state');
          progressFillEl.style.background = 'linear-gradient(90deg, #ff6b6b 0%, #ee5a6f 100%)';
        }
      }, 2000);

      activeDownloads.set(downloadId, { intervalId });

    } else {
      alert('❌ Failed to start download. Please check the URL and try again.');
    }
  } catch (err) {
    const errorMsg = err.message || 'Unknown error';
    console.error('Download error:', err);
    alert(`❌ Network error: ${errorMsg}\n\nMake sure the server is running on ${BASE_URL}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = '🚀 Start Download';
  }
});

// Allow Enter key to submit
urlInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    submitBtn.click();
  }
});
