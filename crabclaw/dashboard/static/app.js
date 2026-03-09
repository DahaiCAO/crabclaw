function qs(id){ return document.getElementById(id); }

const connPill = qs("conn-pill");
const wsUrlPill = qs("ws-url-pill");
const statePre = qs("state-pre");
const auditLog = qs("audit-log");
const reflLog = qs("refl-log");
const clearAuditBtn = qs("clear-audit");
const autoScroll = qs("auto-scroll");
const showAudit = qs("show-audit");
const showReflection = qs("show-reflection");
const search = qs("search");

// Chat interface elements
const chatMessages = qs("chat-messages");
const chatInput = qs("chat-input");
const sendButton = qs("send-button");

// Chat functionality
function addChatMessage(content, isUser) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `chat-message ${isUser ? "user" : "assistant"}`;
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  contentDiv.textContent = content;
  
  messageDiv.appendChild(contentDiv);
  chatMessages.appendChild(messageDiv);
  
  // Auto scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle send button click
sendButton.addEventListener("click", () => {
  const message = chatInput.value.trim();
  if (message) {
    addChatMessage(message, true);
    chatInput.value = "";
    
    // Send message to backend via WebSocket
    if (window.ws) {
      const payload = JSON.stringify({
        type: "chat_message",
        data: {
          message: message,
          timestamp: Date.now() / 1000
        }
      });
      window.ws.send(payload);
    } else {
      // Fallback to simulated response
      setTimeout(() => {
        addChatMessage("WebSocket not connected. Using simulated response.", false);
      }, 1000);
    }
  }
});

// Handle Enter key press in input
chatInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    sendButton.click();
  }
});

const _buffer = [];
const _MAX = 800;

function setConn(ok, text){
  connPill.textContent = text;
  connPill.style.borderColor = ok ? "rgba(34,197,94,.45)" : "rgba(239,68,68,.45)";
  connPill.style.color = ok ? "rgba(34,197,94,.95)" : "rgba(239,68,68,.95)";
}

function appendRow(container, meta, msg, tagText, tagClass){
  const row = document.createElement("div");
  row.className = "row";
  const m = document.createElement("div");
  m.className = "meta";

  const tag = document.createElement("span");
  tag.className = "tag " + (tagClass || "");
  tag.textContent = tagText || "";
  m.appendChild(tag);
  const metaText = document.createElement("span");
  metaText.textContent = meta || "";
  m.appendChild(metaText);

  const body = document.createElement("div");
  body.className = "msg";
  body.textContent = msg || "";

  row.appendChild(m);
  row.appendChild(body);
  container.appendChild(row);

  if (autoScroll.checked){
    container.scrollTop = container.scrollHeight;
  }
}

clearAuditBtn.addEventListener("click", () => {
  auditLog.innerHTML = "";
  reflLog.innerHTML = "";
  _buffer.length = 0;
});

function passesFilter(kind, text){
  if (kind === "audit" && !showAudit.checked) return false;
  if (kind === "reflection" && !showReflection.checked) return false;
  const q = (search.value || "").trim().toLowerCase();
  if (!q) return true;
  return (text || "").toLowerCase().includes(q);
}

function renderEvent(kind, payload){
  const text = pretty(payload);
  if (!passesFilter(kind, text)) return;

  if (kind === "audit"){
    const ts = payload.timestamp ? new Date(payload.timestamp * 1000).toISOString() : "";
    const meta = `${ts} · ${payload.engine || ""}`;
    const tagText = payload.event_type || "audit";
    appendRow(auditLog, meta, text, tagText, "ok");
    return;
  }

  if (kind === "reflection"){
    const ts = payload.timestamp ? new Date(payload.timestamp * 1000).toISOString() : "";
    const stage = payload.stage || "reflection";
    appendRow(reflLog, ts, text, stage, "");
    return;
  }
}

function rerender(){
  auditLog.innerHTML = "";
  reflLog.innerHTML = "";
  for (const item of _buffer){
    renderEvent(item.kind, item.payload);
  }
}

for (const el of [showAudit, showReflection, search]){
  el.addEventListener("input", () => rerender());
  el.addEventListener("change", () => rerender());
}

function pretty(obj){
  try { return JSON.stringify(obj, null, 2); } catch { return String(obj); }
}

function connect(){
  const url = new URL(window.location.href);
  const host = url.hostname || "127.0.0.1";
  const wsPort = url.searchParams.get("ws_port") || "18792";
  const wsUrl = `ws://${host}:${wsPort}/ws`;
  wsUrlPill.textContent = wsUrl;

  const ws = new WebSocket(wsUrl);
  window.ws = ws; // Make ws available globally
  setConn(false, "WS: connecting…");

  ws.onopen = () => setConn(true, "WS: connected");
  ws.onclose = () => setConn(false, "WS: disconnected (retrying)");
  ws.onerror = () => setConn(false, "WS: error (retrying)");

  ws.onmessage = (ev) => {
    let payload = null;
    try { payload = JSON.parse(ev.data); } catch { return; }

    const type = payload.type || "event";
    const data = payload.data || {};

    if (type === "hello"){
      return;
    }

    if (type === "internal_state"){
      statePre.textContent = pretty(data);
      return;
    }

    if (type === "audit"){
      _buffer.push({kind: "audit", payload: data});
      if (_buffer.length > _MAX) _buffer.shift();
      renderEvent("audit", data);
      return;
    }

    if (type === "reflection"){
      _buffer.push({kind: "reflection", payload: data});
      if (_buffer.length > _MAX) _buffer.shift();
      renderEvent("reflection", data);
      return;
    }

    _buffer.push({kind: "audit", payload});
    if (_buffer.length > _MAX) _buffer.shift();
    renderEvent("audit", payload);
  };

  ws.addEventListener("close", () => {
    setTimeout(connect, 1200);
  });
}

connect();

