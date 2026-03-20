// AI chat widget — injected into header by map.html directly
// This file just exports the sendAiMessage logic used by the inline button
window.aiChat = (() => {
  const API = 'https://dybar52ziekaj.cloudfront.net/api/chat';
  let sessionId = crypto.randomUUID();
  let isOpen = false;

  function getToken() { return localStorage.getItem('id_token') || ''; }

  function toggle() {
    isOpen = !isOpen;
    document.getElementById('ai-chat-box').classList.toggle('open', isOpen);
  }

  async function send() {
    const input = document.getElementById('ai-chat-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    appendMsg(text, 'user');
    const thinking = appendMsg('...', 'bot');
    try {
      const res = await fetch(API, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getToken()}` },
        body: JSON.stringify({ message: text, session_id: sessionId })
      });
      const data = await res.json();
      sessionId = data.session_id || sessionId;
      thinking.textContent = data.reply || 'No response.';
    } catch {
      thinking.textContent = 'Something went wrong. Try again.';
    }
  }

  function appendMsg(text, role) {
    const messages = document.getElementById('ai-chat-messages');
    const div = document.createElement('div');
    div.className = `ai-msg ${role}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  return { toggle, send };
})();
