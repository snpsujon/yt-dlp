chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'download' && message.url) {
    // For demo: just alert or send response back
    console.log('Download requested for:', message.url);
    sendResponse({ message: 'Download started for: ' + message.url });
    // You can programmatically open popup or send message to popup here
  }
});
