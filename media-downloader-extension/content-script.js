(function () {
  if (document.getElementById('umd-download-btn')) return;

  const videos = document.querySelectorAll('video');
  if (videos.length === 0) return;

  const video = videos[0];

  // Create button container with better styling
  const btnContainer = document.createElement('div');
  btnContainer.id = 'umd-download-container';
  
  const btn = document.createElement('button');
  btn.id = 'umd-download-btn';
  
  // Create icon and text elements
  const icon = document.createElement('span');
  icon.id = 'umd-download-icon';
  icon.textContent = '⬇️';
  icon.style.cssText = 'font-size: 18px; margin-right: 8px; display: inline-block; transition: transform 0.3s ease;';
  
  const text = document.createElement('span');
  text.id = 'umd-download-text';
  text.textContent = 'Download Video';
  
  btn.appendChild(icon);
  btn.appendChild(text);
  
  // Modern button styling
  Object.assign(btn.style, {
    position: 'absolute',
    zIndex: '999999',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
    color: 'white',
    border: 'none',
    padding: '12px 20px',
    borderRadius: '12px',
    cursor: 'pointer',
    fontSize: '15px',
    fontWeight: '600',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4), 0 2px 8px rgba(0, 0, 0, 0.1)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    outline: 'none',
    userSelect: 'none',
    backdropFilter: 'blur(10px)',
    WebkitBackdropFilter: 'blur(10px)',
    border: '2px solid rgba(255, 255, 255, 0.2)'
  });

  // Hover effects
  btn.addEventListener('mouseenter', () => {
    if (!btn.disabled) {
      btn.style.transform = 'translateY(-2px) scale(1.05)';
      btn.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.5), 0 4px 12px rgba(0, 0, 0, 0.15)';
      icon.style.transform = 'rotate(360deg)';
    }
  });

  btn.addEventListener('mouseleave', () => {
    if (!btn.disabled) {
      btn.style.transform = 'translateY(0) scale(1)';
      btn.style.boxShadow = '0 4px 15px rgba(102, 126, 234, 0.4), 0 2px 8px rgba(0, 0, 0, 0.1)';
      icon.style.transform = 'rotate(0deg)';
    }
  });

  btn.addEventListener('mousedown', () => {
    if (!btn.disabled) {
      btn.style.transform = 'translateY(0) scale(0.98)';
    }
  });

  btn.addEventListener('mouseup', () => {
    if (!btn.disabled) {
      btn.style.transform = 'translateY(-2px) scale(1.05)';
    }
  });

  // Progress bar element
  const progressBar = document.createElement('div');
  progressBar.id = 'umd-progress-bar';
  progressBar.style.cssText = `
    position: absolute;
    bottom: 0;
    left: 0;
    height: 3px;
    background: rgba(255, 255, 255, 0.3);
    border-radius: 0 0 12px 12px;
    width: 0%;
    transition: width 0.3s ease;
    overflow: hidden;
  `;
  
  const progressFill = document.createElement('div');
  progressFill.style.cssText = `
    height: 100%;
    width: 100%;
    background: linear-gradient(90deg, rgba(255, 255, 255, 0.6), rgba(255, 255, 255, 0.9));
    animation: shimmer 2s infinite;
  `;
  
  // Add shimmer animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes shimmer {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.7; }
    }
  `;
  document.head.appendChild(style);
  
  progressBar.appendChild(progressFill);
  btn.appendChild(progressBar);

  const setPosition = () => {
    const rect = video.getBoundingClientRect();
    btn.style.top = `${rect.top + window.scrollY + 15}px`;
    btn.style.left = `${rect.left + window.scrollX + 15}px`;
  };
  setPosition();

  document.body.appendChild(btn);
  window.addEventListener('scroll', setPosition);
  window.addEventListener('resize', setPosition);

  // For production: 'https://pyd.snpsujon.me'
  // For local development: 'http://127.0.0.1:5000' (or 'http://127.0.0.1:5020' if using Docker)
  const BASE_URL = 'http://127.0.0.1:5000';

  function updateButtonState(state, progress = 0) {
    const states = {
      idle: {
        icon: '⬇️',
        text: 'Download Video',
        bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
        disabled: false
      },
      preparing: {
        icon: '⏳',
        text: 'Preparing...',
        bg: 'linear-gradient(135deg, #f093fb 0%, #764ba2 50%, #667eea 100%)',
        disabled: true
      },
      downloading: {
        icon: '⬇️',
        text: 'Downloading...',
        bg: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        disabled: true
      },
      ready: {
        icon: '✅',
        text: 'Ready!',
        bg: 'linear-gradient(135deg, #51cf66 0%, #40c057 100%)',
        disabled: false
      },
      complete: {
        icon: '🎉',
        text: 'Complete!',
        bg: 'linear-gradient(135deg, #51cf66 0%, #40c057 100%)',
        disabled: false
      },
      error: {
        icon: '❌',
        text: 'Error',
        bg: 'linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%)',
        disabled: false
      }
    };

    const currentState = states[state] || states.idle;
    icon.textContent = currentState.icon;
    text.textContent = currentState.text;
    btn.style.background = currentState.bg;
    btn.disabled = currentState.disabled;
    btn.style.opacity = currentState.disabled ? '0.8' : '1';
    progressBar.style.width = `${progress}%`;
    
    if (state === 'downloading' && progress > 0) {
      text.textContent = `Downloading ${progress}%`;
    }
  }

  async function startDownload(videoUrl) {
    updateButtonState('preparing', 0);

    const formData = new URLSearchParams();
    formData.append('url', videoUrl);
    formData.append('format', 'video');
    formData.append('quality', 'best');
    formData.append('playlist', 'off');

    // Get extension version
    let extensionVersion = '1.0';
    try {
      extensionVersion = chrome.runtime.getManifest().version || '1.0';
    } catch (e) {
      console.log('Could not get extension version:', e);
    }
    const browserInfo = navigator.userAgent;
    const platform = navigator.platform;
    const language = navigator.language;

    try {
      const res = await fetch(`${BASE_URL}/api/download`, {
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
      const data = await res.json();

      if (!data.success || !data.session_id) {
        updateButtonState('error', 0);
        setTimeout(() => {
          updateButtonState('idle', 0);
        }, 3000);
        return;
      }

      const sessionId = data.session_id;
      updateButtonState('downloading', 0);

      const poll = setInterval(async () => {
        try {
          const progressRes = await fetch(`${BASE_URL}/api/progress`, {
            method: 'GET',
            headers: {
              'X-Session-ID': sessionId
            }
          });
          const progress = await progressRes.json();

          const percent = parseFloat(progress.percent) || 0;

          if (progress.status === 'Completed' && progress.filename) {
            clearInterval(poll);
            updateButtonState('ready', 100);

            const downloadUrl = `${BASE_URL}/downloads/${progress.filename}`;
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = progress.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();

            updateButtonState('complete', 100);
            setTimeout(() => {
              updateButtonState('idle', 0);
            }, 3000);
          } else if (progress.status.startsWith('Error')) {
            clearInterval(poll);
            updateButtonState('error', 0);
            setTimeout(() => {
              updateButtonState('idle', 0);
            }, 3000);
          } else {
            updateButtonState('downloading', percent);
          }
        } catch (e) {
          clearInterval(poll);
          updateButtonState('error', 0);
          setTimeout(() => {
            updateButtonState('idle', 0);
          }, 3000);
        }
      }, 2000);
    } catch (error) {
      console.error('Download error:', error);
      updateButtonState('error', 0);
      alert(`❌ Network error: ${error.message || 'Unknown error'}\n\nMake sure the server is running on ${BASE_URL}`);
      setTimeout(() => {
        updateButtonState('idle', 0);
      }, 3000);
    }
  }

  btn.addEventListener('click', () => {
    if (!btn.disabled) {
      const videoUrl = window.location.href;
      startDownload(videoUrl);
    }
  });
})();
