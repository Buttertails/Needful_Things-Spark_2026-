(() => {
  const API = 'https://dybar52ziekaj.cloudfront.net/api/chat';
  let sessionId = crypto.randomUUID();

  function getToken() {
    return localStorage.getItem('id_token') || '';
  }

  const styles = `
    #ai-chat-btn { position: fixed; bottom: 1.5rem; right: 1.5rem; width: 52px; height: 52px; border-radius: 50%; background: #7c3aed; color: white; border: none; font-size: 1.5rem; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 1000; }
    #ai-chat-box { display: none; position: fixed; bottom: 5rem; right: 1.5rem; width: 320px; max-height: 460px; background: white; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.15); z-index: 1000; flex-direction: column; overflow: hidden; }
    #ai-chat-box.open { display: flex; }
    #ai-chat-header { background: #7c3aed; color: white; padding: 0.75rem 1rem; font-weight: 600; font-size: 0.95rem; }
    #ai-chat-messages { flex: 1; overflow-y: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.5rem; }
    .ai-msg { padding: 0.5rem 0.75rem; border-radius: 8px; max-width: 85%; font-size: 0.9rem; line-height: 1.4; }
    .ai-msg.user { background: #7c3aed; color: white; align-self: flex-end; }
    .ai-msg.bot { background: #f1f5f9; color: #1e293b; align-self: flex-start; }
    #ai-chat-input-row { display: flex; border-top: 1px solid #e2e8f0; }
    #ai-chat-input { flex: 1; padding: 0.65rem; border: none; outline: none; font-size: 0.9rem; }
    #ai-chat-send { padding: 0.65rem 1rem; background: #7c3aed; color: white; border: none; cursor: pointer; font-size: 0.9rem; }
  `;

  const html = `
    <style>${styles}</style>
    <button id="ai-chat-btn" title="Chat with AI">🤖</button>
    <div id="ai-chat-box">
      <div id="ai-chat-header">AI Assistant</div>
      <div id="ai-chat-messages"></div>
      <div id="ai-chat-input-row">
        <input id="ai-chat-input" type="text" placeholder="Ask something..." />
        <button id="ai-chat-send">Send</button>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', html);

  const btn = document.getElementById('ai-chat-btn');
  const box = document.getElementById('ai-chat-box');
  const messages = document.getElementById('ai-chat-messages');
  const input = document.getElementById('ai-chat-input');
  const send = document.getElementById('ai-chat-send');

  btn.addEventListener('click', () => box.classList.toggle('open'));

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    appendMsg(text, 'user');

    const thinking = appendMsg('...', 'bot');
    try {
      const res = await fetch(API, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getToken()}` },
        body: JSON.stringify({ message: text, session_id: sessionId })
      });
      const data = await res.json();
      sessionId = data.session_id;
      thinking.textContent = data.reply || 'No response.';
    } catch {
      thinking.textContent = 'Something went wrong. Try again.';
    }
  }

  function appendMsg(text, role) {
    const div = document.createElement('div');
    div.className = `ai-msg ${role}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  send.addEventListener('click', sendMessage);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });
})();
