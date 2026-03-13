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
  
  const avatarDiv = document.createElement("div");
  avatarDiv.className = "message-avatar";
  avatarDiv.textContent = isUser ? "👤" : "🦀";
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  contentDiv.textContent = content;
  
  messageDiv.appendChild(avatarDiv);
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

// Theme toggle
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  setTheme(savedTheme);
}

function setTheme(theme) {
  document.body.setAttribute('data-theme', theme);
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  
  // Update theme buttons
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === theme);
  });
}

// Theme button click handlers
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('theme-btn')) {
    setTheme(e.target.dataset.theme);
  }
});

// Initialize theme on load
  initTheme();

  // File operations
  function renderFiles(files) {
    const fileList = document.getElementById('core-files-list');
    fileList.innerHTML = '';

    files.forEach(file => {
      const fileItem = document.createElement('div');
      fileItem.className = 'core-file-item';
      fileItem.textContent = file.name;
      fileItem.dataset.fileName = file.name;

      fileItem.addEventListener('click', () => {
        // Remove active class from all items
        document.querySelectorAll('.core-file-item').forEach(item => {
          item.classList.remove('active');
        });
        // Add active class to clicked item
        fileItem.classList.add('active');
        // Load file content
        loadFileContent(file.name);
      });

      fileList.appendChild(fileItem);
    });
  }

  function loadFileContent(fileName) {
    ws.send(JSON.stringify({
      type: 'get_file_content',
      data: { file_name: fileName }
    }));
  }

  function saveFile() {
    const fileName = document.getElementById('current-file-name').textContent;
    const content = document.getElementById('file-content').value;

    if (fileName !== 'Select a file') {
      ws.send(JSON.stringify({
        type: 'save_file',
        data: { file_name: fileName, content: content }
      }));
    }
  }

  // Load files when Core Files section is selected
  document.addEventListener('click', (e) => {
    if (e.target.closest('.menu-item[data-section="core-files"]')) {
      ws.send(JSON.stringify({ type: 'get_files' }));
    }
  });

  // Save button click event
  document.getElementById('save-file-btn').addEventListener('click', saveFile);

// Menu navigation
const menuItems = document.querySelectorAll('.menu-item');
const contentSections = document.querySelectorAll('.content-section');

menuItems.forEach(item => {
  item.addEventListener('click', () => {
    const sectionId = item.dataset.section;
    
    // Update menu items
    menuItems.forEach(menu => menu.classList.remove('active'));
    item.classList.add('active');
    
    // Update content sections
    contentSections.forEach(section => {
      section.classList.remove('active');
      if (section.id === `section-${sectionId}`) {
        section.classList.add('active');
      }
    });
    
    // Load data for specific sections
    if (sectionId === 'providers') {
      loadProviders();
    } else if (sectionId === 'config') {
      loadConfig();
    }
  });
});

function loadProviders() {
  const providersList = document.getElementById('providers-list');
  if (!providersList) return;
  
  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    window.ws.send(JSON.stringify({ type: 'get_providers' }));
  } else {
    providersList.innerHTML = '<div class="provider-item"><span class="provider-status error"></span><span class="provider-name">WebSocket not connected</span></div>';
  }
}

function loadConfig() {
  const configPre = document.getElementById('config-pre');
  if (!configPre) return;
  
  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    window.ws.send(JSON.stringify({ type: 'get_config' }));
  } else {
    configPre.textContent = 'WebSocket not connected';
  }
}

function renderProviders(providers) {
  const providersList = document.getElementById('providers-list');
  if (!providersList) return;
  
  providersList.innerHTML = '';
  
  if (!providers || providers.length === 0) {
    providersList.innerHTML = '<div class="provider-item"><span class="provider-status"></span><span class="provider-name">No providers configured</span></div>';
    return;
  }
  
  providers.forEach(provider => {
    const item = document.createElement('div');
    item.className = 'provider-item';
    item.innerHTML = `
      <span class="provider-status ${provider.status || ''}"></span>
      <span class="provider-name">${provider.name}</span>
      <span class="provider-info">${provider.model || ''}</span>
    `;
    providersList.appendChild(item);
  });
}

function renderConfig(config) {
  const configPre = document.getElementById('config-pre');
  if (!configPre) return;
  
  configPre.textContent = JSON.stringify(config, null, 2);
}

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

    if (type === "providers"){
      renderProviders(data.providers || []);
      return;
    }

    if (type === "config"){
      renderConfig(data);
      return;
    }

    if (type === "chat_response"){
      addChatMessage(data.response, false);
      return;
    }

    if (type === "files"){
      renderFiles(data.files);
      return;
    }

    if (type === "file_content"){
      document.getElementById("file-content").value = data.content;
      document.getElementById("current-file-name").textContent = data.file_name;
      return;
    }

    if (type === "file_saved"){
      alert(data.success ? "File saved successfully!" : "Failed to save file.");
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

