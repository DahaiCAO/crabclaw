function qs(id){ return document.getElementById(id); }

// Notification system
function showNotification(message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `notification notification-${type}`;
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    color: white;
    font-weight: 500;
    z-index: 10000;
    animation: slideIn 0.3s ease;
    max-width: 400px;
    word-wrap: break-word;
  `;
  
  // Set background color based on type
  const colors = {
    success: "#10b981",
    error: "#ef4444",
    warning: "#f59e0b",
    info: "#3b82f6"
  };
  notification.style.backgroundColor = colors[type] || colors.info;
  
  document.body.appendChild(notification);
  
  // Auto remove after 5 seconds
  setTimeout(() => {
    notification.style.animation = "slideOut 0.3s ease";
    setTimeout(() => notification.remove(), 300);
  }, 5000);
}

// Friend and Group data
let friends = [];
let groups = [];
let friendBadges = {};
let groupBadges = {};
let currentChat = { type: 'main', id: null };

const connPill = qs("conn-pill");
const wsUrlPill = qs("ws-url-pill");
const portraitContainer = document.querySelector('.portrait-container');
const auditLog = qs("audit-log");

// User authentication variables
let currentUser = null;
let currentSession = null;
const seenMessageEvents = new Map();

function getAccessToken() {
  return localStorage.getItem('access_token') || '';
}

function clearAuthState() {
  currentUser = null;
  currentSession = null;
  localStorage.removeItem('session_id');
  localStorage.removeItem('access_token');
}

function redirectToLogin() {
  window.location.href = '/login.html';
}

function eventKeyForMessage(type, data) {
  const payload = data || {};
  if (payload.event_id) {
    return `${type}:${payload.event_id}`;
  }

  const content = payload.content || payload.response || '';
  return `${type}|${payload.channel || ''}|${payload.chat_id || ''}|${payload.sender_id || ''}|${content}|${payload.timestamp || ''}`;
}

function shouldRenderEvent(type, data) {
  const key = eventKeyForMessage(type, data);
  const now = Date.now();
  const ttl = 120000;
  for (const [k, ts] of seenMessageEvents.entries()) {
    if (now - ts > ttl) seenMessageEvents.delete(k);
  }
  if (seenMessageEvents.has(key)) return false;
  seenMessageEvents.set(key, now);
  return true;
}


const reflLog = qs("refl-log");
const clearAuditBtn = qs("clear-audit");
const autoScroll = qs("auto-scroll");
const showAudit = qs("show-audit");
const showReflection = qs("show-reflection");
const search = qs("search");
const llmStats = qs("llm-stats");
const llmStatsWindow = qs("llm-stats-window");
const peCharts = qs("pe-charts");
const peDeployments = qs("pe-deployments");
const peCandidates = qs("pe-candidates");
const peCandidateCount = qs("pe-candidate-count");
const peDeploymentCount = qs("pe-deployment-count");
const ovAgentAlive = qs("ov-agent-alive");
const ovEnergy = qs("ov-energy");
const ovCredits = qs("ov-credits");
const ovCanary = qs("ov-canary");
const ovCandidates = qs("ov-candidates");
const ovLastDecision = qs("ov-last-decision");
const ovFocus = qs("ov-focus");
const peRefreshBtn = qs("pe-refresh");
const peAutoDecideBtn = qs("pe-auto-decide");
const pePromoteBtn = qs("pe-promote");
const peRollbackBtn = qs("pe-rollback");
const peFactoryResetBtn = qs("pe-factory-reset");
const peCandidateInput = qs("pe-candidate-id");
const peFileInput = qs("pe-file-rel");
const peAlerts = qs("pe-alerts");
const peTimeline = qs("pe-timeline");
const peCompare = qs("pe-compare");
const peCompareTable = qs("pe-compare-table");
const peCompareSort = qs("pe-compare-sort");
const peCompareOrder = qs("pe-compare-order");
const peCompareMinSamples = qs("pe-compare-min-samples");
const peCompareSearch = qs("pe-compare-search");
const peRuleLowSample = qs("pe-rule-low-sample");
const peRuleWarningError = qs("pe-rule-warning-error");
const peRuleCriticalError = qs("pe-rule-critical-error");
const peRuleHighTurns = qs("pe-rule-high-turns");
const peApplyRulesBtn = qs("pe-apply-rules");
const candidateDetailModal = qs("candidate-detail-modal");
const candidateDetailClose = qs("candidate-detail-close");
const candidateDetailTitle = qs("candidate-detail-title");
const candidateDetailSummary = qs("candidate-detail-summary");
const candidateDetailDiff = qs("candidate-detail-diff");
const candidateDetailEvents = qs("candidate-detail-events");
const candidateDetailContent = qs("candidate-detail-content");
const candidateDetailPromote = qs("candidate-detail-promote");
const candidateDetailRollback = qs("candidate-detail-rollback");
const candidateDetailFactoryReset = qs("candidate-detail-factory-reset");
const candidateDetailJumpFile = qs("candidate-detail-jump-file");
const candidateDiffPrevHunk = qs("candidate-diff-prev-hunk");
const candidateDiffNextHunk = qs("candidate-diff-next-hunk");
const candidateDiffHunkSelect = qs("candidate-diff-hunk-select");
const candidateDiffKeyword = qs("candidate-diff-keyword");
const candidateDiffCopyPatch = qs("candidate-diff-copy-patch");
const candidateDiffCopyHunk = qs("candidate-diff-copy-hunk");
const candidateDiffAcceptHunk = qs("candidate-diff-accept-hunk");
const candidateDiffRejectHunk = qs("candidate-diff-reject-hunk");
const candidateDiffApplySelected = qs("candidate-diff-apply-selected");
const candidateDiffAcceptStatus = qs("candidate-diff-accept-status");
const candidateReviewer = qs("candidate-reviewer");
const candidateDraftSave = qs("candidate-draft-save");
const candidateDraftClear = qs("candidate-draft-clear");
let latestInternalState = {};
let latestConfig = null;
let promptEvolutionState = {};
let lastAutoDecisionLabel = "-";
let currentCandidateDetail = null;
let currentDiffHunks = [];
let currentDiffLines = [];
let currentHunkIndex = 0;
let currentHunkDecisions = {};
let channelsRequestTimer = null;

// Chat interface elements
const chatMessages = qs("chat-messages");
const chatInput = qs("chat-input");
const sendButton = qs("send-button");

// Chat functionality
function loadChatHistory(messages) {
  // Clear existing messages
  chatMessages.innerHTML = '';
  
  // Add each message from history
  messages.forEach(msg => {
    const isUser = msg.role === 'user';
    const messageDiv = document.createElement("div");
    messageDiv.className = `chat-message ${isUser ? "user" : "assistant"}`;
    
    const avatarDiv = document.createElement("div");
    avatarDiv.className = "message-avatar";
    avatarDiv.textContent = isUser ? "👤" : "🦀";
    
    const contentContainer = document.createElement("div");
    contentContainer.className = "message-content-container";
    
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    contentDiv.textContent = msg.content;
    
    contentContainer.appendChild(contentDiv);
    
    // Add channel info if available
    if (isUser && msg.channel) {
      const channelLabel = document.createElement('div');
      channelLabel.style.cssText = 'font-size: 10px; color: rgba(255,255,255,0.8); margin-top: 4px; display: flex; align-items: center; gap: 4px;';
      
      // Channel emoji mapping
      const channelEmojis = {
        'feishu': '📱',
        'mochat': '💬',
        'discord': '🎮',
        'matrix': '🟣',
        'dingtalk': '🔔',
        'dashboard': '💻',
      };
      const emoji = channelEmojis[msg.channel.toLowerCase()] || '📨';
      const senderDisplay = msg.sender_id ? ` ${msg.sender_id}` : '';
      channelLabel.textContent = `${emoji} [${msg.channel}]${senderDisplay}`;
      contentContainer.appendChild(channelLabel);
    }
    
    // Add timestamp if available
    if (msg.timestamp) {
      const timestampDiv = document.createElement("div");
      timestampDiv.className = "message-timestamp";
      const date = new Date(msg.timestamp);
      timestampDiv.textContent = date.toLocaleString();
      contentContainer.appendChild(timestampDiv);
    }
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentContainer);
    chatMessages.appendChild(messageDiv);
  });
  
  // Auto scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addChatMessage(content, isUser) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `chat-message ${isUser ? "user" : "assistant"}`;
  
  const avatarDiv = document.createElement("div");
  avatarDiv.className = "message-avatar";
  avatarDiv.textContent = isUser ? "👤" : "🦀";
  
  const contentContainer = document.createElement("div");
  contentContainer.className = "message-content-container";
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  contentDiv.textContent = content;
  
  contentContainer.appendChild(contentDiv);
  
  // Add timestamp
  const timestampDiv = document.createElement("div");
  timestampDiv.className = "message-timestamp";
  timestampDiv.textContent = new Date().toLocaleString();
  contentContainer.appendChild(timestampDiv);
  
  messageDiv.appendChild(avatarDiv);
  messageDiv.appendChild(contentContainer);
  chatMessages.appendChild(messageDiv);
  
  // Auto scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle send button click
sendButton.addEventListener("click", () => {
  const message = chatInput.value.trim();
  if (message) {
    console.log(`[Chat] Sending message: ${message}`);
    addChatMessage(message, true);
    chatInput.value = "";
    
    // Send message to backend via WebSocket
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      const payload = JSON.stringify({
        type: "chat_message",
        data: {
          message: message,
          timestamp: Date.now() / 1000
        }
      });
      console.log(`[Chat] Sending payload: ${payload}`);
      window.ws.send(payload);
      console.log(`[Chat] Message sent successfully`);
    } else {
      console.error(`[Chat] WebSocket not connected. State: ${window.ws ? window.ws.readyState : 'undefined'}`);
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

// Channel Mode Switching
function setChannelMode(mode) {
  document.querySelectorAll('.channel-mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.channelMode === mode);
  });
  // Save to server
  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    window.ws.send(JSON.stringify({
      type: 'update_settings',
      data: { channel_mode: mode }
    }));
  }
  // Save to localStorage
  localStorage.setItem('channel-mode', mode);
}

// Channel mode button click handlers
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('channel-mode-btn')) {
    setChannelMode(e.target.dataset.channelMode);
  }
});

// Initialize channel mode on load
function initChannelMode() {
  const savedMode = localStorage.getItem('channel-mode') || 'multi';
  setChannelMode(savedMode);
}

// Initialize theme on load
  initTheme();
  initChannelMode();

  // Collapsible menu groups
  document.querySelectorAll('.menu-group-header').forEach(header => {
    header.addEventListener('click', () => {
      const content = header.nextElementSibling;
      header.classList.toggle('collapsed');
      content.classList.toggle('collapsed');
    });
  });

  // Render friends list
  function renderFriends() {
    const list = document.getElementById('private-chat-list');
    if (!list) return;
    
    list.innerHTML = '';
    
    if (friends.length === 0) {
      list.innerHTML = '<div class="empty-list">No friends yet</div>';
      return;
    }
    
    friends.forEach(friend => {
      const item = document.createElement('div');
      item.className = 'menu-item friend-item';
      item.dataset.section = 'friend-chat';
      item.dataset.friendId = friend.agent_id;
      
      const name = document.createElement('span');
      name.className = 'friend-name';
      name.textContent = friend.agent_name || friend.agent_id;
      
      const badge = document.createElement('span');
      badge.className = 'badge';
      if (friendBadges[friend.agent_id] > 0) {
        badge.style.display = 'flex';
        badge.textContent = friendBadges[friend.agent_id];
      } else {
        badge.style.display = 'none';
      }
      
      item.appendChild(name);
      item.appendChild(badge);
      
      item.addEventListener('click', () => {
        openFriendChat(friend);
      });
      
      list.appendChild(item);
    });
  }

  // Render groups list
  function renderGroups() {
    const list = document.getElementById('group-chat-list');
    if (!list) return;
    
    list.innerHTML = '';
    
    if (groups.length === 0) {
      list.innerHTML = '<div class="empty-list">No groups yet</div>';
      return;
    }
    
    groups.forEach(group => {
      const item = document.createElement('div');
      item.className = 'menu-item group-item';
      item.dataset.section = 'group-chat';
      item.dataset.groupId = group.group_id;
      
      const name = document.createElement('span');
      name.className = 'group-name';
      name.textContent = group.group_name || group.group_id;
      
      const badge = document.createElement('span');
      badge.className = 'badge';
      if (groupBadges[group.group_id] > 0) {
        badge.style.display = 'flex';
        badge.textContent = groupBadges[group.group_id];
      } else {
        badge.style.display = 'none';
      }
      
      item.appendChild(name);
      item.appendChild(badge);
      
      item.addEventListener('click', () => {
        openGroupChat(group);
      });
      
      list.appendChild(item);
    });
  }

  // Open friend chat
  function openFriendChat(friend) {
    currentChat = { type: 'friend', id: friend.agent_id };
    
    // Clear badge
    friendBadges[friend.agent_id] = 0;
    renderFriends();
    
    // Update UI
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.content-section').forEach(section => section.classList.remove('active'));
    
    // Create or show friend chat section
    let section = document.getElementById('section-friend-chat');
    if (!section) {
      section = document.createElement('section');
      section.className = 'content-section';
      section.id = 'section-friend-chat';
      section.innerHTML = `
        <div class="card">
          <div class="chat-header">
            <span class="chat-header-title" id="friend-chat-title">${friend.agent_name || friend.agent_id}</span>
            <span class="chat-header-status" id="friend-chat-status">Online</span>
          </div>
          <div class="chat-container">
            <div class="chat-messages" id="friend-chat-messages"></div>
            <div class="chat-input">
              <input type="text" id="friend-chat-input" placeholder="Type your message..." />
              <button id="friend-send-button">Send</button>
            </div>
          </div>
        </div>
      `;
      document.querySelector('.content').appendChild(section);
      
      // Add event listeners
      const friendInput = document.getElementById('friend-chat-input');
      const friendSendBtn = document.getElementById('friend-send-button');
      
      friendSendBtn.addEventListener('click', () => {
        const message = friendInput.value.trim();
        if (message) {
          sendFriendMessage(friend.agent_id, message);
          friendInput.value = '';
        }
      });
      
      friendInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          friendSendBtn.click();
        }
      });
    } else {
      document.getElementById('friend-chat-title').textContent = friend.agent_name || friend.agent_id;
    }
    
    section.classList.add('active');
    
    // Request chat history
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({
        type: 'get_friend_chat_history',
        data: { friend_id: friend.agent_id }
      }));
    }
  }

  // Open group chat
  function openGroupChat(group) {
    currentChat = { type: 'group', id: group.group_id };
    
    // Clear badge
    groupBadges[group.group_id] = 0;
    renderGroups();
    
    // Update UI
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.content-section').forEach(section => section.classList.remove('active'));
    
    // Create or show group chat section
    let section = document.getElementById('section-group-chat');
    if (!section) {
      section = document.createElement('section');
      section.className = 'content-section';
      section.id = 'section-group-chat';
      section.innerHTML = `
        <div class="card">
          <div class="chat-header">
            <span class="chat-header-title" id="group-chat-title">${group.group_name || group.group_id}</span>
            <span class="chat-header-status" id="group-chat-status">${group.members?.length || 0} members</span>
          </div>
          <div class="chat-container">
            <div class="chat-messages" id="group-chat-messages"></div>
            <div class="chat-input">
              <input type="text" id="group-chat-input" placeholder="Type your message..." />
              <button id="group-send-button">Send</button>
            </div>
          </div>
        </div>
      `;
      document.querySelector('.content').appendChild(section);
      
      // Add event listeners
      const groupInput = document.getElementById('group-chat-input');
      const groupSendBtn = document.getElementById('group-send-button');
      
      groupSendBtn.addEventListener('click', () => {
        const message = groupInput.value.trim();
        if (message) {
          sendGroupMessage(group.group_id, message);
          groupInput.value = '';
        }
      });
      
      groupInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          groupSendBtn.click();
        }
      });
    } else {
      document.getElementById('group-chat-title').textContent = group.group_name || group.group_id;
      document.getElementById('group-chat-status').textContent = `${group.members?.length || 0} members`;
    }
    
    section.classList.add('active');
    
    // Request chat history
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({
        type: 'get_group_chat_history',
        data: { group_id: group.group_id }
      }));
    }
  }

  // Back to main chat
  window.backToMainChat = function() {
    currentChat = { type: 'main', id: null };
    
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.content-section').forEach(section => section.classList.remove('active'));
    
    document.querySelector('[data-section="chat"]').classList.add('active');
    document.getElementById('section-chat').classList.add('active');
  };

  // Send friend message
  function sendFriendMessage(friendId, message) {
    const messagesContainer = document.getElementById('friend-chat-messages');
    if (messagesContainer) {
      addChatMessageToContainer(messagesContainer, message, true);
    }
    
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({
        type: 'send_friend_message',
        data: {
          friend_id: friendId,
          message: message,
          timestamp: Date.now() / 1000
        }
      }));
    }
  }

  // Send group message
  function sendGroupMessage(groupId, message) {
    const messagesContainer = document.getElementById('group-chat-messages');
    if (messagesContainer) {
      addChatMessageToContainer(messagesContainer, message, true);
    }
    
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({
        type: 'send_group_message',
        data: {
          group_id: groupId,
          message: message,
          timestamp: Date.now() / 1000
        }
      }));
    }
  }

  // Add message to specific container
  function addChatMessageToContainer(container, content, isUser, senderName = null) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `chat-message ${isUser ? "user" : "assistant"}`;
    
    const avatarDiv = document.createElement("div");
    avatarDiv.className = "message-avatar";
    avatarDiv.textContent = isUser ? "👤" : "🦀";
    
    const contentContainer = document.createElement("div");
    contentContainer.className = "message-content-container";
    
    if (senderName && !isUser) {
      const senderDiv = document.createElement("div");
      senderDiv.className = "message-sender";
      senderDiv.textContent = senderName;
      senderDiv.style.cssText = "font-size: 11px; color: var(--accent); margin-bottom: 2px;";
      contentContainer.appendChild(senderDiv);
    }
    
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    contentDiv.textContent = content;
    
    contentContainer.appendChild(contentDiv);
    
    const timestampDiv = document.createElement("div");
    timestampDiv.className = "message-timestamp";
    timestampDiv.textContent = new Date().toLocaleString();
    contentContainer.appendChild(timestampDiv);
    
    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentContainer);
    container.appendChild(messageDiv);
    
    container.scrollTop = container.scrollHeight;
  }

  // Handle incoming friend message notification
  function handleFriendMessageNotification(data) {
    const { from_agent_id, from_agent_name, message } = data;
    
    // Update badge
    if (!friendBadges[from_agent_id]) {
      friendBadges[from_agent_id] = 0;
    }
    friendBadges[from_agent_id]++;
    
    // If currently in this friend's chat, add message directly
    if (currentChat.type === 'friend' && currentChat.id === from_agent_id) {
      const container = document.getElementById('friend-chat-messages');
      if (container) {
        addChatMessageToContainer(container, message, false, from_agent_name);
        friendBadges[from_agent_id] = 0; // Clear badge since we're viewing
      }
    } else {
      showNotification(`New message from ${from_agent_name || from_agent_id}`, "info");
    }
    
    renderFriends();
  }

  // Handle incoming group message notification
  function handleGroupMessageNotification(data) {
    const { group_id, group_name, from_agent_id, from_agent_name, message } = data;
    
    // Update badge
    if (!groupBadges[group_id]) {
      groupBadges[group_id] = 0;
    }
    groupBadges[group_id]++;
    
    // If currently in this group chat, add message directly
    if (currentChat.type === 'group' && currentChat.id === group_id) {
      const container = document.getElementById('group-chat-messages');
      if (container) {
        addChatMessageToContainer(container, message, false, from_agent_name);
        groupBadges[group_id] = 0; // Clear badge since we're viewing
      }
    } else {
      showNotification(`New message in ${group_name || group_id}`, "info");
    }
    
    renderGroups();
  }

  // File operations
  function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function formatTimeAgo(timestamp) {
    const now = Date.now() / 1000;
    const diff = now - timestamp;
    
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString();
  }

  function renderFiles(files) {
    const fileList = document.getElementById('core-files-list');
    fileList.innerHTML = '';

    files.forEach(file => {
      const fileItem = document.createElement('div');
      fileItem.className = 'core-file-item';
      fileItem.dataset.fileName = file.name;

      const fileName = document.createElement('div');
      fileName.className = 'core-file-name';
      fileName.textContent = file.name.split('/').pop(); // Show only filename without prefix

      const fileMeta = document.createElement('div');
      fileMeta.className = 'core-file-meta';
      const sizeStr = formatFileSize(file.size);
      const timeStr = formatTimeAgo(file.mtime);
      fileMeta.textContent = `${sizeStr} · ${timeStr}`;

      fileItem.appendChild(fileName);
      fileItem.appendChild(fileMeta);

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
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({
        type: 'get_file_content',
        data: { file_name: fileName }
      }));
    } else {
      showNotification('WebSocket not connected', 'error');
    }
  }

  function saveFile() {
    const fileName = document.getElementById('current-file-name').textContent;
    const content = document.getElementById('file-content').value;

    if (fileName !== 'Select a file') {
      if (window.ws && window.ws.readyState === WebSocket.OPEN) {
        window.ws.send(JSON.stringify({
          type: 'save_file',
          data: { file_name: fileName, content: content }
        }));
      } else {
        showNotification('WebSocket not connected', 'error');
      }
    }
  }

  // Load files when Core Files section is selected
  document.addEventListener('click', (e) => {
    if (e.target.closest('.menu-item[data-section="core-files"]')) {
      if (window.ws && window.ws.readyState === WebSocket.OPEN) {
        window.ws.send(JSON.stringify({ type: 'get_files' }));
      } else {
        showNotification('WebSocket not connected', 'error');
      }
    }
  });

  // Save button click event
  document.getElementById('save-file-btn').addEventListener('click', saveFile);

// Menu navigation
const menuItems = document.querySelectorAll('.menu-item');

function canAccessMenu(access) {
  if (!access) return true;
  const isAdmin = !!(currentUser && currentUser.is_admin);
  if (access === 'admin') return isAdmin;
  if (access === 'user') return !!currentUser;
  if (access === 'member') return !!currentUser && !isAdmin;
  if (access === 'guest') return !currentUser;
  return true;
}

function activateSection(sectionId) {
  const targetMenu = Array.from(document.querySelectorAll(`.menu-item[data-section="${sectionId}"]`))
    .find((item) => item.style.display !== 'none');
  if (!targetMenu) return;
  menuItems.forEach(menu => menu.classList.remove('active'));
  targetMenu.classList.add('active');
  document.querySelectorAll('.content-section').forEach(section => {
    section.classList.remove('active');
    if (section.id === `section-${sectionId}`) {
      section.classList.add('active');
    }
  });
}

menuItems.forEach(item => {
  item.addEventListener('click', () => {
    const sectionId = item.dataset.section;
    const access = item.getAttribute('data-access');
    if (!canAccessMenu(access)) {
      showNotification('当前账号无权访问该菜单', 'warning');
      return;
    }

    // Update menu items
    menuItems.forEach(menu => menu.classList.remove('active'));
    item.classList.add('active');
    
    // Update content sections - query all sections including dynamically created ones
    document.querySelectorAll('.content-section').forEach(section => {
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
    } else if (sectionId === 'settings') {
      loadConfig();
    } else if (sectionId === 'portrait') {
      // Data will be updated by WebSocket message
    } else if (sectionId === 'prompt-evolution' || sectionId === 'overview') {
      requestPromptEvolutionStatus();
    } else if (sectionId === 'skills') {
      loadSkills();
    } else if (sectionId === 'channels') {
      loadChannels();
    } else if (sectionId === 'users') {
      loadUsers();
    }
  });
});

function loadProviders() {
  const providersList = document.getElementById('providers-list');
  if (!providersList) return;
  
  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    window.ws.send(JSON.stringify({ type: 'get_providers' }));
    window.ws.send(JSON.stringify({ type: 'get_config' }));
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

// Skills management
let allSkills = { built_in: [], workspace: [] };

function loadSkills() {
  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    window.ws.send(JSON.stringify({ type: 'get_skills' }));
  } else {
    const workspaceList = document.getElementById('workspace-skills-list');
    const builtinList = document.getElementById('built-in-skills-list');
    if (workspaceList) workspaceList.innerHTML = '<div class="skill-item"><div class="skill-info"><div class="skill-name">WebSocket not connected</div></div></div>';
    if (builtinList) builtinList.innerHTML = '';
  }
}

function loadChannels() {
  const channelsList = document.getElementById('channels-list');
  if (!channelsList) return;
  
  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    channelsList.innerHTML = '<div class="channel-item"><span class="channel-status loading"></span><span class="channel-name">Loading...</span></div>';
    if (channelsRequestTimer) {
      clearTimeout(channelsRequestTimer);
      channelsRequestTimer = null;
    }
    channelsRequestTimer = setTimeout(() => {
      const current = document.getElementById('channels-list');
      if (!current) return;
      current.innerHTML = '<div class="channel-item"><span class="channel-status error"></span><span class="channel-name">频道数据加载超时，请刷新页面并重启 dashboard 服务</span></div>';
    }, 3000);
    window.ws.send(JSON.stringify({ type: 'get_channels' }));
  } else {
    channelsList.innerHTML = '<div class="channel-item"><span class="channel-status error"></span><span class="channel-name">WebSocket not connected</span></div>';
  }
}

function loadUsers() {
  const usersList = document.getElementById('users-list');
  if (!usersList) return;
  
  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    window.ws.send(JSON.stringify({ type: 'get_users' }));
  } else {
    usersList.innerHTML = '<div class="user-item"><span class="user-status error"></span><span class="user-info">WebSocket not connected</span></div>';
  }
}

function renderSkills(skills) {
  allSkills = skills || { built_in: [], workspace: [] };
  filterSkills();
}

function filterSkills() {
  const filterInput = document.getElementById('skills-filter-input');
  const filterText = filterInput ? filterInput.value.toLowerCase() : '';
  
  const workspaceList = document.getElementById('workspace-skills-list');
  const builtinList = document.getElementById('built-in-skills-list');
  
  if (workspaceList) {
    const filteredWorkspace = allSkills.workspace.filter(skill => 
      skill.name.toLowerCase().includes(filterText) ||
      skill.description.toLowerCase().includes(filterText)
    );
    renderSkillList(workspaceList, filteredWorkspace, 'workspace');
  }
  
  if (builtinList) {
    const filteredBuiltin = allSkills.built_in.filter(skill => 
      skill.name.toLowerCase().includes(filterText) ||
      skill.description.toLowerCase().includes(filterText)
    );
    renderSkillList(builtinList, filteredBuiltin, 'built_in');
  }
}

function renderSkillList(container, skills, source) {
  container.innerHTML = '';
  
  if (skills.length === 0) {
    const noSkillsText = getTranslation('skills.no_skills') || 'No skills found';
    container.innerHTML = `<div class="skill-item empty"><div class="skill-info"><div class="skill-name">${noSkillsText}</div></div></div>`;
    return;
  }
  
  const eligibleText = getTranslation('skills.eligible') || 'eligible';
  
  skills.forEach(skill => {
    const skillItem = document.createElement('div');
    skillItem.className = 'skill-item';
    
    const skillIcon = document.createElement('div');
    skillIcon.className = 'skill-icon';
    skillIcon.textContent = skill.icon || '🛠️';
    
    const skillInfo = document.createElement('div');
    skillInfo.className = 'skill-info';
    
    const skillName = document.createElement('div');
    skillName.className = 'skill-name';
    skillName.textContent = skill.name;
    
    const skillDesc = document.createElement('div');
    skillDesc.className = 'skill-description';
    skillDesc.textContent = skill.description || '';
    
    skillInfo.appendChild(skillName);
    skillInfo.appendChild(skillDesc);
    
    const skillTags = document.createElement('div');
    skillTags.className = 'skill-tags';
    
    const sourceTag = document.createElement('span');
    sourceTag.className = 'skill-tag';
    sourceTag.textContent = source === 'workspace' ? 'opencilaw-workspace' : 'opencilaw-bundled';
    
    const statusTag = document.createElement('span');
    statusTag.className = 'skill-tag status-eligible';
    statusTag.textContent = eligibleText;
    
    skillTags.appendChild(sourceTag);
    skillTags.appendChild(statusTag);
    
    skillItem.appendChild(skillIcon);
    skillItem.appendChild(skillInfo);
    skillItem.appendChild(skillTags);
    
    container.appendChild(skillItem);
  });
}

// Skills filter event listener
document.addEventListener('DOMContentLoaded', () => {
  const skillsFilterInput = document.getElementById('skills-filter-input');
  if (skillsFilterInput) {
    skillsFilterInput.addEventListener('input', filterSkills);
  }
});

function renderProviders(providers) {
  const providersList = document.getElementById('providers-list');
  if (!providersList) return;
  
  providersList.innerHTML = '';
  
  if (!providers || providers.length === 0) {
    providersList.innerHTML = '<div class="provider-item"><span class="provider-status"></span><span class="provider-name">No providers configured</span></div>';
    return;
  }

  const addItem = document.createElement('div');
  addItem.className = 'provider-item detailed';

  const addHeader = document.createElement('div');
  addHeader.className = 'provider-item-header';
  addHeader.innerHTML = `
    <span class="provider-status"></span>
    <span class="provider-name">+ Add Provider</span>
    <span class="provider-info">user provider</span>
  `;

  const addFields = document.createElement('div');
  addFields.className = 'provider-item-fields';

  const idGroup = document.createElement('div');
  idGroup.className = 'form-group';
  const idLabel = document.createElement('label');
  idLabel.textContent = 'provider_id';
  const idInput = document.createElement('input');
  idInput.type = 'text';
  idInput.placeholder = 'my_provider';
  idGroup.appendChild(idLabel);
  idGroup.appendChild(idInput);
  addFields.appendChild(idGroup);

  const baseGroup0 = document.createElement('div');
  baseGroup0.className = 'form-group';
  const baseLabel0 = document.createElement('label');
  baseLabel0.textContent = 'base_url';
  const baseInput0 = document.createElement('input');
  baseInput0.type = 'text';
  baseInput0.placeholder = 'https://api.example.com/v1';
  baseGroup0.appendChild(baseLabel0);
  baseGroup0.appendChild(baseInput0);
  addFields.appendChild(baseGroup0);

  const keyGroup0 = document.createElement('div');
  keyGroup0.className = 'form-group';
  const keyLabel0 = document.createElement('label');
  keyLabel0.textContent = 'api_key';
  const keyInput0 = document.createElement('input');
  keyInput0.type = 'password';
  keyInput0.placeholder = 'sk-...';
  keyGroup0.appendChild(keyLabel0);
  keyGroup0.appendChild(keyInput0);
  addFields.appendChild(keyGroup0);

  const modelGroup0 = document.createElement('div');
  modelGroup0.className = 'form-group';
  const modelLabel0 = document.createElement('label');
  modelLabel0.textContent = 'model_name';
  const modelInput0 = document.createElement('input');
  modelInput0.type = 'text';
  modelInput0.placeholder = 'gpt-4o / deepseek-chat / ...';
  modelGroup0.appendChild(modelLabel0);
  modelGroup0.appendChild(modelInput0);
  addFields.appendChild(modelGroup0);

  const addActions = document.createElement('div');
  addActions.className = 'provider-item-actions';
  const addBtn = document.createElement('button');
  addBtn.textContent = getTranslation('provider.save') || 'Save';
  addBtn.addEventListener('click', () => {
    const rawId = (idInput.value || '').trim();
    const providerId = rawId.replace(/\s+/g, '');
    if (!providerId) {
      showNotification('provider_id 不能为空', 'warning');
      return;
    }
    if (!/^[a-zA-Z0-9_-]+$/.test(providerId)) {
      showNotification('provider_id 仅支持字母/数字/_/-', 'warning');
      return;
    }
    const baseUrl = (baseInput0.value || '').trim();
    const apiKey = (keyInput0.value || '').trim();
    const modelName = (modelInput0.value || '').trim();
    if (!baseUrl || !apiKey || !modelName) {
      showNotification('base_url / api_key / model_name 不能为空', 'warning');
      return;
    }
    
    // 防止连续点击
     addBtn.disabled = true;
     addBtn.textContent = getTranslation('provider.saving') || 'Saving and testing...';
    
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({
        type: 'update_settings',
        data: {
          provider_keys: {
            [`user:${providerId}`]: { api_key: apiKey, api_base: baseUrl, model: modelName }
          }
        }
      }));
      
      // 测试新添加的提供商
      window.ws.send(JSON.stringify({
        type: 'test_provider',
        data: {
          provider_id: `user:${providerId}`,
          api_key: apiKey,
          api_base: baseUrl,
          model: modelName
        }
      }));
      
      // 3秒后恢复按钮状态（防止测试超时）
       setTimeout(() => {
         addBtn.disabled = false;
         addBtn.textContent = getTranslation('provider.save') || 'Save';
       }, 30000);
     } else {
       showNotification('WebSocket not connected', 'error');
       addBtn.disabled = false;
       addBtn.textContent = getTranslation('provider.save') || 'Save';
     }
  });
  addActions.appendChild(addBtn);

  addItem.appendChild(addHeader);
  addItem.appendChild(addFields);
  addItem.appendChild(addActions);
  providersList.appendChild(addItem);

  providers.forEach((provider) => {
    const item = document.createElement('div');
    item.className = 'provider-item detailed';

    const header = document.createElement('div');
    header.className = 'provider-item-header';

    const status = document.createElement('span');
    status.className = `provider-status ${provider.status || 'error'}`;
    header.appendChild(status);

    const name = document.createElement('span');
    name.className = 'provider-name';
    name.textContent = provider.name || provider.config_name || '';
    header.appendChild(name);

    const info = document.createElement('span');
    info.className = 'provider-info';
    info.textContent = provider.config_name || '';
    header.appendChild(info);

    const fields = document.createElement('div');
    fields.className = 'provider-item-fields';

    const baseGroup = document.createElement('div');
    baseGroup.className = 'form-group';
    const baseLabel = document.createElement('label');
    baseLabel.textContent = 'base_url';
    const baseInput = document.createElement('input');
    baseInput.type = 'text';
    baseInput.value = provider.apiBase || provider.api_base || '';
    baseInput.placeholder = provider.default_api_base || 'https://...';
    baseGroup.appendChild(baseLabel);
    baseGroup.appendChild(baseInput);
    fields.appendChild(baseGroup);

    const keyGroup = document.createElement('div');
    keyGroup.className = 'form-group';
    const keyLabel = document.createElement('label');
    keyLabel.textContent = 'api_key';
    const keyInput = document.createElement('input');
    keyInput.type = 'password';
    keyInput.value = provider.apiKey || provider.api_key || '';
    keyInput.placeholder = 'sk-...';
    keyGroup.appendChild(keyLabel);
    keyGroup.appendChild(keyInput);
    fields.appendChild(keyGroup);

    const defBaseGroup = document.createElement('div');
    defBaseGroup.className = 'form-group';
    const defBaseLabel = document.createElement('label');
    defBaseLabel.textContent = 'default_base_url';
    const defBaseInput = document.createElement('input');
    defBaseInput.type = 'text';
    defBaseInput.value = provider.default_api_base || '';
    defBaseInput.readOnly = true;
    defBaseGroup.appendChild(defBaseLabel);
    defBaseGroup.appendChild(defBaseInput);
    fields.appendChild(defBaseGroup);

    const modelGroup2 = document.createElement('div');
    modelGroup2.className = 'form-group';
    const modelLabel2 = document.createElement('label');
    modelLabel2.textContent = 'model_name';
    const modelInput2 = document.createElement('input');
    modelInput2.type = 'text';
    modelInput2.value = provider.model || provider.provider_model || '';
    modelInput2.placeholder = '例如: gpt-4o / deepseek-chat / ...';
    modelGroup2.appendChild(modelLabel2);
    modelGroup2.appendChild(modelInput2);
    fields.appendChild(modelGroup2);

    const actions = document.createElement('div');
    actions.className = 'provider-item-actions';

    const toggleKeyBtn = document.createElement('button');
    toggleKeyBtn.textContent = getTranslation('provider.show_key') || 'Show Key';
    toggleKeyBtn.addEventListener('click', () => {
      if (keyInput.type === 'password') {
        keyInput.type = 'text';
        toggleKeyBtn.textContent = getTranslation('provider.hide_key') || 'Hide Key';
      } else {
        keyInput.type = 'password';
        toggleKeyBtn.textContent = getTranslation('provider.show_key') || 'Show Key';
      }
    });
    actions.appendChild(toggleKeyBtn);

    const saveBtn = document.createElement('button');
    saveBtn.textContent = getTranslation('provider.save') || 'Save';
    saveBtn.addEventListener('click', () => {
      const pName = provider.config_name;
      if (!pName) {
        showNotification('Provider 名称缺失，无法保存', 'error');
        return;
      }
      
      // 防止连续点击
      saveBtn.disabled = true;
      saveBtn.textContent = getTranslation('provider.saving') || 'Saving and testing...';
      
      // 先保存配置
      if (window.ws && window.ws.readyState === WebSocket.OPEN) {
        window.ws.send(JSON.stringify({
          type: 'update_settings',
          data: {
            provider_keys: {
              [pName]: {
                api_key: keyInput.value || '',
                api_base: baseInput.value || '',
                model: (modelInput2.value || '').trim()
              }
            }
          }
        }));
        
        // 然后测试连接
        window.ws.send(JSON.stringify({
          type: 'test_provider',
          data: {
            provider_id: pName,
            api_key: keyInput.value || '',
            api_base: baseInput.value || '',
            model: (modelInput2.value || '').trim()
          }
        }));
        
        // 3秒后恢复按钮状态（防止测试超时）
      setTimeout(() => {
        saveBtn.disabled = false;
        saveBtn.textContent = getTranslation('provider.save') || 'Save';
      }, 30000);
    } else {
      showNotification('WebSocket not connected', 'error');
      saveBtn.disabled = false;
      saveBtn.textContent = getTranslation('provider.save') || 'Save';
    }
    });
    actions.appendChild(saveBtn);

    item.appendChild(header);
    item.appendChild(fields);
    item.appendChild(actions);
    providersList.appendChild(item);
  });
}

function coerceConfigValue(rawValue, typeText) {
  const value = String(rawValue ?? '').trim();
  const type = String(typeText || '').toLowerCase();
  if (!value) return '';
  if (type.includes('bool')) {
    return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase());
  }
  if (type.includes('int')) {
    const num = parseInt(value, 10);
    return Number.isNaN(num) ? value : num;
  }
  if (type.includes('float') || type.includes('double')) {
    const num = parseFloat(value);
    return Number.isNaN(num) ? value : num;
  }
  if (type.includes('dict') || type.includes('list') || type.includes('json')) {
    try {
      return JSON.parse(value);
    } catch (error) {
      return value;
    }
  }
  return value;
}

function renderChannelsLegacy(payload) {
  const container = document.getElementById('channels-list');
  if (!container) return;
  const channels = Array.isArray(payload) ? payload : (payload?.channels || []);
  const userConfigs = Array.isArray(payload) ? {} : (payload?.user_configs || {});
  const identityMappings = Array.isArray(payload) ? [] : (payload?.identity_mappings || []);
  container.innerHTML = '';

  if (!channels.length) {
    container.innerHTML = '<div class="channel-item"><span class="channel-name">No channels available</span></div>';
    return;
  }

  const mappingCard = document.createElement('div');
  mappingCard.className = 'channel-item';
  mappingCard.style.flexBasis = '100%';
  mappingCard.innerHTML = '<div class="channel-item-header"><span class="channel-name">Identity Mapping</span></div><div class="channel-description">将外部通道身份映射到当前登录用户，保证多通道消息归并到同一用户档案。</div>';
  const mappingForm = document.createElement('div');
  mappingForm.className = 'channel-params';
  const channelSelect = document.createElement('select');
  channelSelect.className = 'config-input';
  channels.forEach((ch) => {
    const option = document.createElement('option');
    option.value = ch.name;
    option.textContent = ch.display_name || ch.name;
    channelSelect.appendChild(option);
  });
  const externalInput = document.createElement('input');
  externalInput.className = 'config-input';
  externalInput.placeholder = 'external_id（如邮箱、飞书 open_id）';
  const aliasInput = document.createElement('input');
  aliasInput.className = 'config-input';
  aliasInput.placeholder = '备注（可选）';
  const mapBtn = document.createElement('button');
  mapBtn.className = 'btn small';
  mapBtn.textContent = '添加映射';
  mapBtn.onclick = () => {
    if (!window.ws || window.ws.readyState !== WebSocket.OPEN) {
      showNotification('WebSocket not connected', 'error');
      return;
    }
    const externalId = externalInput.value.trim();
    if (!externalId) {
      showNotification('external_id 不能为空', 'error');
      return;
    }
    window.ws.send(JSON.stringify({
      type: 'map_identity',
      data: {
        channel: channelSelect.value,
        external_id: externalId,
        alias: aliasInput.value.trim(),
      },
    }));
  };
  mappingForm.appendChild(channelSelect);
  mappingForm.appendChild(externalInput);
  mappingForm.appendChild(aliasInput);
  mappingForm.appendChild(mapBtn);
  mappingCard.appendChild(mappingForm);
  const mappingList = document.createElement('div');
  mappingList.className = 'channel-params';
  if (!identityMappings.length) {
    const emptyLine = document.createElement('div');
    emptyLine.className = 'channel-param';
    emptyLine.textContent = '暂无映射';
    mappingList.appendChild(emptyLine);
  } else {
    identityMappings.forEach((mapping) => {
      const row = document.createElement('div');
      row.className = 'channel-param';
      const left = document.createElement('span');
      left.className = 'channel-param-name';
      left.textContent = `${mapping.channel}:${mapping.external_id}${mapping.alias ? ` (${mapping.alias})` : ''}`;
      const delBtn = document.createElement('button');
      delBtn.className = 'btn small';
      delBtn.textContent = '删除';
      delBtn.onclick = () => {
        if (!window.ws || window.ws.readyState !== WebSocket.OPEN) return;
        window.ws.send(JSON.stringify({
          type: 'delete_identity_mapping',
          data: { mapping_id: mapping.mapping_id },
        }));
      };
      row.appendChild(left);
      row.appendChild(delBtn);
      mappingList.appendChild(row);
    });
  }
  mappingCard.appendChild(mappingList);
  container.appendChild(mappingCard);

  channels.forEach((channel) => {
    const item = document.createElement('div');
    item.className = 'channel-item';

    const header = document.createElement('div');
    header.className = 'channel-item-header';
    const status = document.createElement('span');
    status.className = `channel-status ${channel.available ? 'ok' : 'error'}`;
    const name = document.createElement('span');
    name.className = 'channel-name';
    name.textContent = channel.display_name || channel.name;
    header.appendChild(status);
    header.appendChild(name);

    const desc = document.createElement('div');
    desc.className = 'channel-description';
    desc.textContent = channel.description || '';
    item.appendChild(header);
    item.appendChild(desc);

    const paramsWrap = document.createElement('div');
    paramsWrap.className = 'channel-params';
    const fieldInputs = {};
    const parameters = channel.parameters || {};
    Object.entries(parameters).forEach(([paramName, paramInfo]) => {
      const row = document.createElement('div');
      row.className = 'channel-param';
      const title = document.createElement('span');
      title.className = 'channel-param-name';
      title.textContent = `${paramName}${paramInfo.required ? ' *' : ''}`;
      const type = document.createElement('span');
      type.className = 'channel-param-type';
      type.textContent = paramInfo.type || 'str';
      row.appendChild(title);
      row.appendChild(type);
      paramsWrap.appendChild(row);
      if (paramInfo.description) {
        const detail = document.createElement('div');
        detail.className = 'channel-description';
        detail.textContent = paramInfo.description;
        paramsWrap.appendChild(detail);
      }
      const input = document.createElement('input');
      input.className = 'config-input';
      input.placeholder = `请输入 ${paramName}`;
      if (paramInfo.default !== '' && paramInfo.default !== null && paramInfo.default !== undefined) {
        input.value = String(paramInfo.default);
      }
      fieldInputs[paramName] = input;
      paramsWrap.appendChild(input);
    });
    if (!Object.keys(parameters).length) {
      const none = document.createElement('div');
      none.className = 'channel-param';
      none.textContent = 'No parameters required';
      paramsWrap.appendChild(none);
    }
    item.appendChild(paramsWrap);

    const title = document.createElement('div');
    title.className = 'channel-description';
    title.style.marginTop = '10px';
    title.textContent = '我的频道配置';
    item.appendChild(title);

    const existingList = document.createElement('div');
    existingList.className = 'channel-params';
    const records = userConfigs[channel.name] || [];
    if (!records.length) {
      const none = document.createElement('div');
      none.className = 'channel-param';
      none.textContent = '暂无配置';
      existingList.appendChild(none);
    } else {
      records.forEach((cfg) => {
        const row = document.createElement('div');
        row.className = 'channel-param';
        const left = document.createElement('span');
        left.className = 'channel-param-name';
        left.textContent = `${cfg.name}${cfg.is_active ? '' : ' (disabled)'}`;
        const del = document.createElement('button');
        del.className = 'btn small';
        del.textContent = '删除';
        del.onclick = () => {
          if (!window.ws || window.ws.readyState !== WebSocket.OPEN) return;
          window.ws.send(JSON.stringify({
            type: 'delete_channel_config',
            data: { channel_type: channel.name, account_id: cfg.account_id },
          }));
        };
        row.appendChild(left);
        row.appendChild(del);
        existingList.appendChild(row);
      });
    }
    item.appendChild(existingList);

    const editor = document.createElement('div');
    editor.className = 'channel-params';
    const cfgName = document.createElement('input');
    cfgName.className = 'config-input';
    cfgName.placeholder = '配置名称';
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn small';
    saveBtn.textContent = '保存配置';
    saveBtn.onclick = () => {
      if (!window.ws || window.ws.readyState !== WebSocket.OPEN) {
        showNotification('WebSocket not connected', 'error');
        return;
      }
      const configPayload = {};
      for (const [paramName, input] of Object.entries(fieldInputs)) {
        const paramType = (parameters[paramName] || {}).type || '';
        const raw = input.value;
        if (!String(raw || '').trim()) continue;
        configPayload[paramName] = coerceConfigValue(raw, paramType);
      }
      window.ws.send(JSON.stringify({
        type: 'save_channel_config',
        data: {
          channel_type: channel.name,
          name: cfgName.value.trim(),
          config: configPayload,
          is_active: true,
        },
      }));
      cfgName.value = '';
    };
    editor.appendChild(cfgName);
    editor.appendChild(saveBtn);
    item.appendChild(editor);
    container.appendChild(item);
  });
}

function serializeConfigValue(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2);
    } catch (error) {
      return '';
    }
  }
  return String(value);
}

function createChannelFieldControl(paramName, paramInfo, currentValue) {
  const typeText = String(paramInfo?.type || 'str');
  const normalizedType = typeText.toLowerCase();

  const field = document.createElement('div');
  field.className = 'channel-field';

  const label = document.createElement('label');
  label.className = 'channel-field-label';
  label.textContent = `${paramName}${paramInfo?.required ? ' *' : ''}`;
  field.appendChild(label);

  const meta = document.createElement('div');
  meta.className = 'channel-field-meta';
  meta.textContent = typeText;
  field.appendChild(meta);

  let input;
  if (normalizedType.includes('bool')) {
    input = document.createElement('select');
    ['true', 'false'].forEach((value) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      input.appendChild(option);
    });
    const boolValue = typeof currentValue === 'boolean'
      ? currentValue
      : String(currentValue ?? paramInfo?.default ?? '').toLowerCase() === 'true';
    input.value = boolValue ? 'true' : 'false';
  } else if (normalizedType.includes('list') || normalizedType.includes('dict') || normalizedType.includes('json')) {
    input = document.createElement('textarea');
    input.rows = 4;
    input.value = serializeConfigValue(currentValue !== undefined ? currentValue : paramInfo?.default);
    input.placeholder = normalizedType.includes('list') ? '["value1", "value2"]' : '{"key": "value"}';
  } else {
    input = document.createElement('input');
    input.type = normalizedType.includes('int') || normalizedType.includes('float') || normalizedType.includes('double')
      ? 'number'
      : (/(password|secret|token|key)/i.test(paramName) ? 'password' : 'text');
    const sourceValue = currentValue !== undefined ? currentValue : paramInfo?.default;
    if (sourceValue !== undefined && sourceValue !== null && sourceValue !== '') {
      input.value = serializeConfigValue(sourceValue);
    }
    input.placeholder = `请输入 ${paramName}`;
  }

  input.className = 'config-input';
  field.appendChild(input);

  if (paramInfo?.description) {
    const help = document.createElement('div');
    help.className = 'channel-field-help';
    help.textContent = paramInfo.description;
    field.appendChild(help);
  }

  return {
    name: paramName,
    info: paramInfo || {},
    element: field,
    read() {
      if (normalizedType.includes('bool')) {
        return input.value === 'true';
      }
      return coerceConfigValue(input.value, typeText);
    },
  };
}

function buildChannelConfigPayload(controls) {
  const config = {};
  const missing = [];

  controls.forEach((control) => {
    const value = control.read();
    const isEmpty = value === '' || value === null || value === undefined;
    if (isEmpty) {
      if (control.info?.required) missing.push(control.name);
      return;
    }
    config[control.name] = value;
  });

  if (missing.length) {
    showNotification(`请填写必填参数: ${missing.join(', ')}`, 'warning');
    return null;
  }
  return config;
}

function sendChannelConfig(channelName, accountId, name, controls, isActive) {
  if (!window.ws || window.ws.readyState !== WebSocket.OPEN) {
    showNotification('WebSocket not connected', 'error');
    return;
  }

  const config = buildChannelConfigPayload(controls);
  if (!config) return;

  window.ws.send(JSON.stringify({
    type: 'save_channel_config',
    data: {
      channel_type: channelName,
      account_id: accountId || null,
      name: (name || '').trim(),
      config,
      is_active: Boolean(isActive),
    },
  }));
}

function setChannelConfigActive(channelName, accountId, isActive) {
  if (!window.ws || window.ws.readyState !== WebSocket.OPEN) {
    showNotification('WebSocket not connected', 'error');
    return;
  }
  window.ws.send(JSON.stringify({
    type: 'set_channel_config_active',
    data: {
      channel_type: channelName,
      account_id: accountId,
      is_active: Boolean(isActive),
    },
  }));
}

function renderIdentityMappingCard(container, channels, mappings) {
  const mappingCard = document.createElement('div');
  mappingCard.className = 'channel-item channel-item-wide';

  const header = document.createElement('div');
  header.className = 'channel-item-header';
  header.innerHTML = '<span class="channel-name">身份映射</span>';
  mappingCard.appendChild(header);

  const desc = document.createElement('div');
  desc.className = 'channel-description';
  desc.textContent = '把外部频道身份绑定到当前登录用户，保证来自不同频道的消息都能归档到同一用户。';
  mappingCard.appendChild(desc);

  const form = document.createElement('div');
  form.className = 'channel-actions';

  const channelSelect = document.createElement('select');
  channelSelect.className = 'config-input';
  channels.forEach((channel) => {
    const option = document.createElement('option');
    option.value = channel.name;
    option.textContent = channel.display_name || channel.name;
    channelSelect.appendChild(option);
  });

  const externalInput = document.createElement('input');
  externalInput.className = 'config-input';
  externalInput.placeholder = 'external_id，例如 open_id / email / user_id';

  const aliasInput = document.createElement('input');
  aliasInput.className = 'config-input';
  aliasInput.placeholder = '备注，可选';

  const mapBtn = document.createElement('button');
  mapBtn.className = 'btn small';
  mapBtn.textContent = '添加映射';
  mapBtn.onclick = () => {
    if (!window.ws || window.ws.readyState !== WebSocket.OPEN) {
      showNotification('WebSocket not connected', 'error');
      return;
    }
    const externalId = externalInput.value.trim();
    if (!externalId) {
      showNotification('external_id 不能为空', 'warning');
      return;
    }
    window.ws.send(JSON.stringify({
      type: 'map_identity',
      data: {
        channel: channelSelect.value,
        external_id: externalId,
        alias: aliasInput.value.trim(),
      },
    }));
  };

  form.appendChild(channelSelect);
  form.appendChild(externalInput);
  form.appendChild(aliasInput);
  form.appendChild(mapBtn);
  mappingCard.appendChild(form);

  const list = document.createElement('div');
  list.className = 'channel-instance-list';
  if (!mappings.length) {
    const empty = document.createElement('div');
    empty.className = 'channel-empty';
    empty.textContent = '当前还没有身份映射。';
    list.appendChild(empty);
  } else {
    mappings.forEach((mapping) => {
      const row = document.createElement('div');
      row.className = 'channel-instance compact';

      const text = document.createElement('div');
      text.className = 'channel-instance-meta';
      text.textContent = `${mapping.channel}:${mapping.external_id}${mapping.alias ? ` (${mapping.alias})` : ''}`;

      const delBtn = document.createElement('button');
      delBtn.className = 'btn small danger';
      delBtn.textContent = '删除';
      delBtn.onclick = () => {
        if (!window.ws || window.ws.readyState !== WebSocket.OPEN) return;
        window.ws.send(JSON.stringify({
          type: 'delete_identity_mapping',
          data: { mapping_id: mapping.mapping_id },
        }));
      };

      row.appendChild(text);
      row.appendChild(delBtn);
      list.appendChild(row);
    });
  }
  mappingCard.appendChild(list);
  container.appendChild(mappingCard);
}

function renderChannelInstance(channel, cfg, parameters) {
  const instance = document.createElement('div');
  instance.className = 'channel-instance';

  const header = document.createElement('div');
  header.className = 'channel-instance-header';

  const titleWrap = document.createElement('div');
  const title = document.createElement('div');
  title.className = 'channel-instance-title';
  title.textContent = cfg.name || cfg.account_id;
  titleWrap.appendChild(title);

  const meta = document.createElement('div');
  meta.className = 'channel-instance-meta';
  meta.textContent = `ID: ${cfg.account_id} · 更新于 ${cfg.updated_at ? new Date(cfg.updated_at).toLocaleString() : '-'}`;
  titleWrap.appendChild(meta);

  const badges = document.createElement('div');
  badges.className = 'channel-badges';
  const statusBadge = document.createElement('span');
  statusBadge.className = `channel-badge ${cfg.is_active ? 'ok' : 'muted'}`;
  statusBadge.textContent = cfg.is_active ? '运行中' : '已停止';
  badges.appendChild(statusBadge);

  header.appendChild(titleWrap);
  header.appendChild(badges);
  instance.appendChild(header);

  const nameInput = document.createElement('input');
  nameInput.className = 'config-input';
  nameInput.value = cfg.name || '';
  nameInput.placeholder = '实例名称';
  instance.appendChild(nameInput);

  const fieldGrid = document.createElement('div');
  fieldGrid.className = 'channel-grid';
  const controls = [];
  Object.entries(parameters).forEach(([paramName, paramInfo]) => {
    const control = createChannelFieldControl(paramName, paramInfo, cfg.config?.[paramName]);
    controls.push(control);
    fieldGrid.appendChild(control.element);
  });
  if (!controls.length) {
    const empty = document.createElement('div');
    empty.className = 'channel-empty';
    empty.textContent = '该频道没有额外配置参数。';
    fieldGrid.appendChild(empty);
  }
  instance.appendChild(fieldGrid);

  const actions = document.createElement('div');
  actions.className = 'channel-actions';

  const saveBtn = document.createElement('button');
  saveBtn.className = 'btn small';
  saveBtn.textContent = '保存';
  saveBtn.onclick = () => {
    sendChannelConfig(channel.name, cfg.account_id, nameInput.value, controls, cfg.is_active);
  };

  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'btn small secondary';
  toggleBtn.textContent = cfg.is_active ? '停止' : '启动';
  toggleBtn.onclick = () => {
    setChannelConfigActive(channel.name, cfg.account_id, !cfg.is_active);
  };

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn small danger';
  deleteBtn.textContent = '删除';
  deleteBtn.onclick = () => {
    if (!window.ws || window.ws.readyState !== WebSocket.OPEN) return;
    window.ws.send(JSON.stringify({
      type: 'delete_channel_config',
      data: {
        channel_type: channel.name,
        account_id: cfg.account_id,
      },
    }));
  };

  actions.appendChild(saveBtn);
  actions.appendChild(toggleBtn);
  actions.appendChild(deleteBtn);
  instance.appendChild(actions);

  return instance;
}

function renderChannels(payload) {
  const container = document.getElementById('channels-list');
  if (!container) return;
  if (channelsRequestTimer) {
    clearTimeout(channelsRequestTimer);
    channelsRequestTimer = null;
  }

  const channels = Array.isArray(payload?.channels) ? [...payload.channels] : [];
  channels.sort((a, b) => String(a?.name || '').localeCompare(String(b?.name || '')));
  const userConfigs = payload?.user_configs || {};
  const identityMappings = payload?.identity_mappings || [];
  const storagePath = payload?.storage_path || '';
  const availableCount = channels.filter((c) => !!c?.available).length;

  container.innerHTML = '';

  const overview = document.createElement('div');
  overview.className = 'channel-overview';
  overview.textContent = `Loaded channels: ${channels.length} (available: ${availableCount}, unavailable: ${channels.length - availableCount}) | config dir: ${storagePath || '-'}`;
  container.appendChild(overview);

  if (false && storagePath) {
    const overview = document.createElement('div');
    overview.className = 'channel-overview';
    overview.textContent = `实例配置文件保存在: ${storagePath}`;
    container.appendChild(overview);
  }

  if (!channels.length) {
    const empty = document.createElement('div');
    empty.className = 'channel-item channel-item-wide';
    empty.innerHTML = '<span class="channel-name">当前没有可用频道</span>';
    container.appendChild(empty);
    return;
  }

  renderIdentityMappingCard(container, channels, identityMappings);

  channels.forEach((channel) => {
    const card = document.createElement('div');
    card.className = 'channel-item';

    const header = document.createElement('div');
    header.className = 'channel-item-header';

    const titleWrap = document.createElement('div');
    const title = document.createElement('span');
    title.className = 'channel-name';
    title.textContent = channel.display_name || channel.name;
    titleWrap.appendChild(title);

    const desc = document.createElement('div');
    desc.className = 'channel-description';
    desc.textContent = channel.description || '';
    titleWrap.appendChild(desc);

    const badges = document.createElement('div');
    badges.className = 'channel-badges';
    const availableBadge = document.createElement('span');
    availableBadge.className = `channel-badge ${channel.available ? 'ok' : 'warn'}`;
    availableBadge.textContent = channel.available ? '可用' : '未加载';
    badges.appendChild(availableBadge);

    const countBadge = document.createElement('span');
    countBadge.className = 'channel-badge';
    countBadge.textContent = `${channel.instance_count || 0} 个实例`;
    badges.appendChild(countBadge);

    header.appendChild(titleWrap);
    header.appendChild(badges);
    card.appendChild(header);

    const parametersTitle = document.createElement('div');
    parametersTitle.className = 'channel-section-title';
    parametersTitle.textContent = '参数模板';
    card.appendChild(parametersTitle);

    const parametersWrap = document.createElement('div');
    parametersWrap.className = 'channel-params';
    const parameterEntries = Object.entries(channel.parameters || {});
    if (!parameterEntries.length) {
      const empty = document.createElement('div');
      empty.className = 'channel-empty';
      empty.textContent = '该频道没有额外参数。';
      parametersWrap.appendChild(empty);
    } else {
      parameterEntries.forEach(([paramName, paramInfo]) => {
        const row = document.createElement('div');
        row.className = 'channel-param';

        const left = document.createElement('span');
        left.className = 'channel-param-name';
        left.textContent = `${paramName}${paramInfo.required ? ' *' : ''}`;
        row.appendChild(left);

        const right = document.createElement('span');
        right.className = 'channel-param-type';
        right.textContent = paramInfo.type || 'str';
        row.appendChild(right);

        parametersWrap.appendChild(row);
      });
    }
    card.appendChild(parametersWrap);

    const instancesTitle = document.createElement('div');
    instancesTitle.className = 'channel-section-title';
    instancesTitle.textContent = '实例列表';
    card.appendChild(instancesTitle);

    const records = userConfigs[channel.name] || [];
    const instanceList = document.createElement('div');
    instanceList.className = 'channel-instance-list';
    if (!records.length) {
      const empty = document.createElement('div');
      empty.className = 'channel-empty';
      empty.textContent = '当前用户还没有创建该频道实例。';
      instanceList.appendChild(empty);
    } else {
      records.forEach((cfg) => {
        instanceList.appendChild(renderChannelInstance(channel, cfg, channel.parameters || {}));
      });
    }
    card.appendChild(instanceList);

    const createTitle = document.createElement('div');
    createTitle.className = 'channel-section-title';
    createTitle.textContent = '创建新实例';
    card.appendChild(createTitle);

    const createBox = document.createElement('div');
    createBox.className = 'channel-instance new-instance';

    const createName = document.createElement('input');
    createName.className = 'config-input';
    createName.placeholder = '实例名称，例如：我的 Telegram Bot';
    createBox.appendChild(createName);

    const createGrid = document.createElement('div');
    createGrid.className = 'channel-grid';
    const createControls = [];
    Object.entries(channel.parameters || {}).forEach(([paramName, paramInfo]) => {
      const control = createChannelFieldControl(paramName, paramInfo, undefined);
      createControls.push(control);
      createGrid.appendChild(control.element);
    });
    if (!createControls.length) {
      const empty = document.createElement('div');
      empty.className = 'channel-empty';
      empty.textContent = '该频道没有额外配置参数。';
      createGrid.appendChild(empty);
    }
    createBox.appendChild(createGrid);

    const createActions = document.createElement('div');
    createActions.className = 'channel-actions';
    const createBtn = document.createElement('button');
    createBtn.className = 'btn small';
    createBtn.textContent = '保存新实例';
    createBtn.onclick = () => {
      sendChannelConfig(channel.name, null, createName.value, createControls, false);
      createName.value = '';
    };
    createActions.appendChild(createBtn);
    createBox.appendChild(createActions);

    card.appendChild(createBox);
    container.appendChild(card);
  });
}

function renderUsers(users) {
  const container = document.getElementById('users-list');
  if (!container) return;

  container.innerHTML = '';
  
  if (!users || users.length === 0) {
    container.innerHTML = '<div class="user-item"><span class="user-status"></span><span class="user-info">No users found</span></div>';
    return;
  }

  users.forEach((user) => {
    const item = document.createElement('div');
    item.className = 'user-item';

    const status = document.createElement('span');
    status.className = `user-status ${user.is_active ? 'ok' : 'error'}`;
    status.textContent = user.is_admin ? '👑' : (user.is_active ? '👤' : '🚫');
    item.appendChild(status);

    const info = document.createElement('div');
    info.className = 'user-info';

    const name = document.createElement('div');
    name.className = 'user-name';
    name.textContent = `${user.display_name} (${user.username})`;
    info.appendChild(name);

    const details = document.createElement('div');
    details.className = 'user-details';

    const userId = document.createElement('div');
    userId.className = 'user-detail';
    userId.textContent = `ID: ${user.user_id.substring(0, 8)}...`;
    details.appendChild(userId);

    const role = document.createElement('div');
    role.className = 'user-detail';
    role.textContent = user.is_admin ? 'Role: Admin' : 'Role: User';
    details.appendChild(role);

    const created = document.createElement('div');
    created.className = 'user-detail';
    created.textContent = `Created: ${new Date(user.created_at).toLocaleDateString()}`;
    details.appendChild(created);

    const lastLogin = document.createElement('div');
    lastLogin.className = 'user-detail';
    lastLogin.textContent = user.last_login ? `Last Login: ${new Date(user.last_login).toLocaleDateString()}` : 'Last Login: Never';
    details.appendChild(lastLogin);

    info.appendChild(details);
    item.appendChild(info);
    container.appendChild(item);
  });
}

function renderConfig(config) {
  const configPre = document.getElementById('config-pre');
  if (!configPre) return;
  
  // Display the raw config content if available, otherwise the whole object
  if (config && config.raw_config) {
    configPre.textContent = config.raw_config;
  } else {
    configPre.textContent = JSON.stringify(config, null, 2);
  }
}

const _buffer = [];
const _MAX = 800;

function setConn(ok, textKey){
  if (!connPill) return;
  const text = getTranslation(textKey) || textKey;
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
    if (payload.event_type === "llm_call"){
      const d = payload.details || {};
      const usage = d.usage || {};
      const total = (usage.total ?? "");
      const meta = `${ts} · ${d.callpoint || ""} · ${d.provider || ""} · ${d.model || ""} · tokens:${total}`;
      const tagText = "llm";
      appendRow(auditLog, meta, text, tagText, payload.result === "error" ? "bad" : "ok");
      return;
    }

    const meta = `${ts} · ${payload.engine || ""}`;
    const tagText = payload.event_type || "audit";
    appendRow(auditLog, meta, text, tagText, payload.result === "error" ? "bad" : "ok");
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
  renderLlmStats();
}

for (const el of [showAudit, showReflection, search]){
  el.addEventListener("input", () => rerender());
  el.addEventListener("change", () => rerender());
}

if (llmStatsWindow){
  llmStatsWindow.addEventListener("change", () => renderLlmStats());
}

function renderLlmStats(){
  if (!llmStats) return;
  const now = Date.now() / 1000;
  const windowSec = llmStatsWindow ? Number(llmStatsWindow.value || "0") : 0;

  const items = _buffer
    .filter(x => x.kind === "audit" && x.payload && x.payload.event_type === "llm_call")
    .map(x => x.payload)
    .filter(p => {
      const ts = Number(p.timestamp || 0);
      return windowSec > 0 ? ts >= (now - windowSec) : true;
    });

  const by = new Map();
  let totalCalls = 0;
  let totalTokens = 0;
  let totalLatency = 0;

  for (const p of items){
    const d = p.details || {};
    const callpoint = d.callpoint || "unknown";
    const usage = d.usage || {};
    const tokens = Number(usage.total || 0);
    const latency = Number(d.latency_ms || 0);

    totalCalls += 1;
    totalTokens += tokens;
    totalLatency += latency;

    const cur = by.get(callpoint) || {callpoint, calls: 0, tokens: 0, latency: 0};
    cur.calls += 1;
    cur.tokens += tokens;
    cur.latency += latency;
    by.set(callpoint, cur);
  }

  llmStats.innerHTML = "";

  const summary = document.createElement("div");
  summary.className = "llm-stats-summary";
  const avgLatency = totalCalls ? Math.round(totalLatency / totalCalls) : 0;
  const avgTokens = totalCalls ? Math.round(totalTokens / totalCalls) : 0;
  summary.textContent = `calls: ${totalCalls} · tokens: ${totalTokens} · avg tokens: ${avgTokens} · avg latency(ms): ${avgLatency}`;
  llmStats.appendChild(summary);

  if (by.size === 0){
    const empty = document.createElement("div");
    empty.className = "llm-stats-empty";
    empty.textContent = "暂无 LLM 调用统计数据";
    llmStats.appendChild(empty);
    return;
  }

  const table = document.createElement("div");
  table.className = "llm-stats-table";

  const header = document.createElement("div");
  header.className = "llm-stats-row llm-stats-head";
  header.innerHTML = `
    <div class="c1">callpoint</div>
    <div class="c2">calls</div>
    <div class="c3">tokens</div>
    <div class="c4">avg ms</div>
  `;
  table.appendChild(header);

  const rows = Array.from(by.values()).sort((a, b) => (b.tokens - a.tokens) || (b.calls - a.calls));
  for (const r of rows){
    const row = document.createElement("div");
    row.className = "llm-stats-row";
    const avgMs = r.calls ? Math.round(r.latency / r.calls) : 0;
    row.innerHTML = `
      <div class="c1">${escapeHtml(r.callpoint)}</div>
      <div class="c2">${r.calls}</div>
      <div class="c3">${r.tokens}</div>
      <div class="c4">${avgMs}</div>
    `;
    table.appendChild(row);
  }

  llmStats.appendChild(table);
}

function pretty(obj){
  try { return JSON.stringify(obj, null, 2); } catch { return String(obj); }
}

function escapeHtml(text){
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeRegExp(text){
  return String(text || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function copyText(text){
  const t = String(text || "");
  if (!t) return;
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(t).then(() => {
      showNotification("Copied to clipboard", "success");
    }).catch(() => {
      showNotification("Copy failed", "error");
    });
    return;
  }
  showNotification("Clipboard API unavailable", "warning");
}

function parseDiffHunks(lines){
  const hunks = [];
  let current = null;
  lines.forEach((line, idx) => {
    if (line.startsWith("@@")){
      if (current) hunks.push(current);
      current = { header: line, start: idx, end: idx };
      return;
    }
    if (current) current.end = idx;
  });
  if (current) hunks.push(current);
  return hunks;
}

function updateHunkDecisionStatus(){
  if (!candidateDiffAcceptStatus) return;
  const entries = Object.entries(currentHunkDecisions);
  if (entries.length === 0){
    candidateDiffAcceptStatus.innerHTML = '<div class="msg">No hunk decision yet.</div>';
    return;
  }
  const accepted = entries.filter(([, v]) => v === "accepted").map(([k]) => Number(k) + 1);
  const rejected = entries.filter(([, v]) => v === "rejected").map(([k]) => Number(k) + 1);
  candidateDiffAcceptStatus.innerHTML = `<div class="msg">Accepted: [${accepted.join(", ")}] | Rejected: [${rejected.join(", ")}]</div>`;
}

function renderDiffText(diffText, keyword = "", focusHunk = 0){
  currentDiffLines = String(diffText || "").split("\n");
  currentDiffHunks = parseDiffHunks(currentDiffLines);
  if (currentDiffHunks.length === 0){
    currentHunkIndex = 0;
  } else {
    currentHunkIndex = Math.max(0, Math.min(focusHunk, currentDiffHunks.length - 1));
  }
  if (candidateDiffHunkSelect){
    candidateDiffHunkSelect.innerHTML = "";
    const conflicts = currentCandidateDetail?.review_conflicts?.hunks || [];
    currentDiffHunks.forEach((h, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      const hc = conflicts[i] || {};
      const stats = hc.status ? ` [${hc.status} +${(hc.accepted || []).length}/-${(hc.rejected || []).length}]` : "";
      opt.textContent = `#${i + 1} ${h.header}${stats}`;
      candidateDiffHunkSelect.appendChild(opt);
    });
    if (currentDiffHunks.length > 0) candidateDiffHunkSelect.value = String(currentHunkIndex);
  }
  const kw = keyword?.trim() || "";
  const reg = kw ? new RegExp(escapeRegExp(kw), "gi") : null;
  const html = [];
  currentDiffLines.forEach((line, idx) => {
    let cls = "diff-line";
    if (line.startsWith("@@")) cls += " hunk";
    else if (line.startsWith("+") && !line.startsWith("+++")) cls += " add";
    else if (line.startsWith("-") && !line.startsWith("---")) cls += " remove";
    if (currentDiffHunks[currentHunkIndex] && idx >= currentDiffHunks[currentHunkIndex].start && idx <= currentDiffHunks[currentHunkIndex].end){
      cls += " active-hunk";
    }
    currentDiffHunks.forEach((h, hidx) => {
      if (idx < h.start || idx > h.end) return;
      const decision = currentHunkDecisions[hidx];
      if (decision === "accepted") cls += " accepted";
      if (decision === "rejected") cls += " rejected";
    });
    let escaped = escapeHtml(line || " ");
    if (reg){
      escaped = escaped.replace(reg, (m) => `<mark class="diff-hit">${m}</mark>`);
    }
    if (line.startsWith("@@")) {
       const hunkIdx = currentDiffHunks.findIndex(h => h.start === idx);
       if (hunkIdx >= 0) {
         const hc = (currentCandidateDetail?.review_conflicts?.hunks || [])[hunkIdx];
         if (hc) {
           const stats = `<span style="font-size: 0.8em; color: #888; margin-left: 10px;">[${hc.status}] Accept:${(hc.accepted || []).length} Reject:${(hc.rejected || []).length}</span>`;
           escaped += stats;
         }
       }
    }
    html.push(`<span id="diff-line-${idx}" class="${cls}">${escaped}</span>`);
  });
  candidateDetailDiff.innerHTML = html.join("");
  if (currentDiffHunks[currentHunkIndex]){
    const anchor = document.getElementById(`diff-line-${currentDiffHunks[currentHunkIndex].start}`);
    if (anchor) anchor.scrollIntoView({ block: "nearest" });
  }
  updateHunkDecisionStatus();
}

function currentHunkText(){
  const h = currentDiffHunks[currentHunkIndex];
  if (!h) return "";
  return currentDiffLines.slice(h.start, h.end + 1).join("\n");
}

function acceptedHunkIndices(){
  return Object.entries(currentHunkDecisions)
    .filter(([, v]) => v === "accepted")
    .map(([k]) => Number(k) + 1)
    .sort((a, b) => a - b);
}

function decisionsForPayload(){
  const out = {};
  Object.entries(currentHunkDecisions).forEach(([k, v]) => {
    out[String(Number(k) + 1)] = v;
  });
  return out;
}

function loadDraftToLocal(draft){
  currentHunkDecisions = {};
  const decisions = draft?.decisions || {};
  Object.entries(decisions).forEach(([k, v]) => {
    const idx = Number(k) - 1;
    if (idx >= 0 && (v === "accepted" || v === "rejected")){
      currentHunkDecisions[idx] = v;
    }
  });
  if (candidateReviewer) candidateReviewer.value = draft?.reviewer || "";
}

function renderReviewConflicts(conflicts){
  const container = document.getElementById("candidate-review-conflicts");
  if (!container) return;
  
  if (!conflicts || !conflicts.hunks || conflicts.hunks.length === 0){
    container.innerHTML = '<div class="msg">No conflicts data available.</div>';
    return;
  }

  let html = `<div class="review-stats">
    <div>Reviewers: ${conflicts.reviewer_count}</div>
    <div>Conflicts: ${conflicts.conflict_count}</div>
    <div>Consensus: ${conflicts.consensus_count}</div>
  </div>`;

  html += `<div class="review-actions" style="margin-top: 10px;">
    <select id="review-strategy">
      <option value="majority">Majority Vote</option>
    </select>
    <input type="number" id="review-min-votes" value="1" min="1" style="width: 50px;" />
    <label><input type="checkbox" id="review-apply-now" checked /> Apply Now</label>
    <button id="btn-generate-conclusion" class="btn">Auto Resolve & Generate Conclusion</button>
  </div>`;
  
  container.innerHTML = html;
  
  const btn = document.getElementById("btn-generate-conclusion");
  if (btn){
    btn.onclick = () => {
      const strategy = document.getElementById("review-strategy").value;
      const minVotes = document.getElementById("review-min-votes").value;
      const applyNow = document.getElementById("review-apply-now").checked;
      postPromptAction("prompt_generate_review_conclusion", {
        candidate_id: currentCandidateDetail.candidate_id,
        strategy: strategy,
        min_votes: Number(minVotes),
        apply_now: applyNow
      });
    };
  }
}

function saveDraft(){
  const candidateId = currentCandidateDetail?.candidate_id;
  if (!candidateId) return;
  postPromptAction("prompt_save_review_draft", {
    candidate_id: candidateId,
    reviewer: candidateReviewer?.value || "",
    decisions: decisionsForPayload(),
  });
}

function makeSparkline(values, color){
  if (!values || values.length === 0) return '<svg class="spark"></svg>';
  const width = 320;
  const height = 72;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(0.0001, max - min);
  const pts = values.map((v, i) => {
    const x = (i / Math.max(1, values.length - 1)) * (width - 6) + 3;
    const y = height - ((v - min) / span) * (height - 8) - 4;
    return `${x},${y}`;
  }).join(" ");
  return `<svg class="spark" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"><polyline points="${pts}" style="stroke:${color};"></polyline></svg>`;
}

function renderPromptEvolution(data){
  promptEvolutionState = data || {};
  const deployments = data.deployments || {};
  const candidates = data.candidates || {};
  const online = data.online_metrics || {};
  const series = data.timeseries || {};
  const alerts = data.alerts || [];
  const timeline = data.timeline || [];
  const comparisons = data.comparisons || {};
  const alertRules = data.alert_rules || {};

  if (peCandidateCount) peCandidateCount.textContent = String(data.candidate_count || 0);
  if (peDeploymentCount) peDeploymentCount.textContent = String(Object.keys(deployments).length);
  if (peDeployments) peDeployments.textContent = pretty(deployments);
  if (peCandidates) peCandidates.textContent = pretty(candidates);
  if (ovCanary){
    const canaryCount = Object.values(deployments).filter(x => x && x.mode === "canary").length;
    ovCanary.textContent = String(canaryCount);
  }
  if (ovCandidates) ovCandidates.textContent = String(data.candidate_count || 0);
  if (timeline.length > 0){
    const latest = timeline[timeline.length - 1];
    lastAutoDecisionLabel = latest.type || "-";
    renderOverviewFromState(latestInternalState);
  }
  if (peAlerts){
    peAlerts.innerHTML = "";
    if (alerts.length === 0){
      peAlerts.innerHTML = '<div class="row"><div class="msg">No active alerts.</div></div>';
    } else {
      for (const item of alerts){
        const div = document.createElement("div");
        div.className = `alert-item ${item.level || "warning"}`;
        div.innerHTML = `<div><strong>${item.title}</strong></div><div>${item.file || "-"} · ${item.candidate_id || "-"}</div><div>${item.detail || ""}</div>`;
        peAlerts.appendChild(div);
      }
    }
  }
  if (peTimeline) peTimeline.textContent = pretty(timeline);
  if (peCompare) peCompare.textContent = pretty(comparisons);
  if (peRuleLowSample) peRuleLowSample.value = alertRules.low_sample_canary ?? "";
  if (peRuleWarningError) peRuleWarningError.value = alertRules.warning_error_rate ?? "";
  if (peRuleCriticalError) peRuleCriticalError.value = alertRules.critical_error_rate ?? "";
  if (peRuleHighTurns) peRuleHighTurns.value = alertRules.high_avg_turns ?? "";
  renderCompareTable(comparisons, alerts);

  if (peCharts){
    peCharts.innerHTML = "";
    for (const [candidateId, metrics] of Object.entries(online)){
      const ts = series[candidateId] || [];
      const succ = ts.map(x => Number(x.tool_success_rate || 0));
      const err = ts.map(x => Number(x.error_rate || 0));
      const turns = ts.map(x => Number(x.avg_turns || 0));
      const score = ts.map(x => Number(x.online_score || 0));
      const wrap = document.createElement("div");
      wrap.className = "chart-card";
      wrap.innerHTML = `
        <div class="chart-title">${candidateId} | samples=${metrics.samples} | status=${(candidates[candidateId] || {}).status || "-"}</div>
        <div>success_rate ${makeSparkline(succ, "#22c55e")}</div>
        <div>error_rate ${makeSparkline(err, "#ef4444")}</div>
        <div>avg_turns ${makeSparkline(turns, "#f59e0b")}</div>
        <div>online_score ${makeSparkline(score, "#60a5fa")}</div>
      `;
      peCharts.appendChild(wrap);
    }
    if (Object.keys(online).length === 0){
      peCharts.innerHTML = '<div class="row"><div class="msg">No candidate metrics yet.</div></div>';
    }
  }
}

function renderCompareTable(comparisons, alerts){
  if (!peCompareTable) return;
  const sortBy = peCompareSort?.value || "online_score";
  const order = peCompareOrder?.value || "desc";
  const minSamples = Number(peCompareMinSamples?.value || 0);
  const query = (peCompareSearch?.value || "").trim().toLowerCase();
  const alertMap = new Map();
  for (const item of alerts || []){
    const key = `${item.file}|${item.candidate_id}`;
    alertMap.set(key, item.level);
  }
  const rows = [];
  for (const [fileRel, candidates] of Object.entries(comparisons || {})){
    for (const item of candidates){
      const online = item.online || {};
      const candidateId = item.candidate_id || "";
      const samples = Number(online.samples || 0);
      if (samples < minSamples) continue;
      if (query && !(fileRel.toLowerCase().includes(query) || candidateId.toLowerCase().includes(query))) continue;
      rows.push({
        file: fileRel,
        candidate_id: candidateId,
        status: item.status || "-",
        online_score: Number(online.online_score || 0),
        tool_success_rate: Number(online.tool_success_rate || 0),
        error_rate: Number(online.error_rate || 0),
        avg_turns: Number(online.avg_turns || 0),
        samples,
      });
    }
  }
  rows.sort((a, b) => {
    const va = a[sortBy] ?? 0;
    const vb = b[sortBy] ?? 0;
    return order === "asc" ? va - vb : vb - va;
  });
  const html = [];
  html.push('<table class="compare-table"><thead><tr><th>file</th><th>candidate</th><th>status</th><th>score</th><th>success</th><th>error</th><th>avg_turns</th><th>samples</th></tr></thead><tbody>');
  for (const row of rows){
    const key = `${row.file}|${row.candidate_id}`;
    const level = alertMap.get(key) || "";
    html.push(
      `<tr class="compare-row ${level}" data-candidate-id="${row.candidate_id}"><td>${row.file}</td><td>${row.candidate_id}</td><td>${row.status}</td><td>${row.online_score.toFixed(3)}</td><td>${row.tool_success_rate.toFixed(3)}</td><td>${row.error_rate.toFixed(3)}</td><td>${row.avg_turns.toFixed(3)}</td><td>${row.samples}</td></tr>`
    );
  }
  html.push("</tbody></table>");
  peCompareTable.innerHTML = rows.length ? html.join("") : '<div class="row"><div class="msg">No comparison rows.</div></div>';
  peCompareTable.querySelectorAll("tr[data-candidate-id]").forEach((tr) => {
    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => requestCandidateDetail(tr.dataset.candidateId));
  });
}

let currentLang = localStorage.getItem('language') || 'en';
let translations = {};

async function loadTranslations(lang) {
  try {
    // We could fetch from server if exposed, but for now we'll use a local object
    // or request via WebSocket. Let's request via WebSocket.
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({ type: 'get_translations', data: { lang } }));
    }
  } catch (e) {
    console.error("Failed to load translations", e);
  }
}

function getTranslation(key) {
  // Try current language first, then fallback to 'zh' if current is 'en', or 'en' if current is 'zh'
  const langs = [currentLang, currentLang === 'zh' ? 'en' : 'zh'];
  
  for (const lang of langs) {
    const t = translations[lang] || {};
    const parts = key.split('.');
    let text = t;
    for (const part of parts) {
      text = text ? text[part] : null;
    }
    if (typeof text === 'string') {
      return text;
    }
  }
  return null;
}

function updateUIStrings() {
  const t = translations[currentLang] || {};
  console.log("Updating UI for language:", currentLang, t);
  
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const text = getTranslation(key);
    if (text) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = text;
      } else {
        el.textContent = text;
      }
    }
  });

  // Also update connection pill if it's currently showing a known state
  if (window.ws) {
    if (window.ws.readyState === WebSocket.OPEN) setConn(true, "menu.ws_connected");
    else if (window.ws.readyState === WebSocket.CONNECTING) setConn(false, "menu.ws_connecting");
    else setConn(false, "menu.ws_disconnected");
  }
}

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('language', lang);
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  
  // Update radio buttons
  document.querySelectorAll('input[name="language"]').forEach(radio => {
    radio.checked = radio.value === lang;
  });
  
  // Load and apply
  loadTranslations(lang);
}

// Settings real-time save
function initSettingsSync() {
  const syncElements = [
    // Fields moved to Portrait
    { id: 'pt-name', key: 'agent_name', type: 'input' },
    { id: 'pt-nickname', key: 'nickname', type: 'input' },
    { id: 'pt-gender', key: 'gender', type: 'change' },
    { id: 'pt-age', key: 'age', type: 'input' },
    { id: 'pt-height', key: 'height', type: 'input' },
    { id: 'pt-weight', key: 'weight', type: 'input' },
    { id: 'pt-hobbies', key: 'hobbies', type: 'input' },
    // Psychology sliders
    { id: 'pt-curiosity', key: 'psychology.curiosity', type: 'input' },
    { id: 'pt-confidence', key: 'psychology.confidence', type: 'input' },
    { id: 'pt-risk-aversion', key: 'psychology.risk_aversion', type: 'input' },
    { id: 'pt-social-trust', key: 'psychology.social_trust', type: 'input' },
    // Remaining fields in Settings
    { id: 'set-save-interval', key: 'save_interval', type: 'input' },
    { id: 'set-push-interval', key: 'push_interval', type: 'input' },
    { id: 'set-audit-enabled', key: 'audit_enabled', type: 'change', isCheck: true }
  ];

  syncElements.forEach(item => {
    const el = qs(item.id);
    if (!el) return;

    el.addEventListener(item.type, () => {
      const val = item.isCheck ? el.checked : el.value;
      if (window.ws && window.ws.readyState === WebSocket.OPEN) {
        window.ws.send(JSON.stringify({
          type: 'update_settings',
          data: { [item.key]: val }
        }));
      }
    });
  });

  // Language radio sync
  document.querySelectorAll('input[name="language"]').forEach(radio => {
    radio.addEventListener('change', () => {
      if (radio.checked) {
        const newLang = radio.value;
        setLanguage(newLang);
        if (window.ws && window.ws.readyState === WebSocket.OPEN) {
          window.ws.send(JSON.stringify({
            type: 'update_settings',
            data: { language: newLang }
          }));
        }
      }
    });
  });
}

// Initial setup
document.addEventListener('DOMContentLoaded', () => {
  const savedLang = localStorage.getItem('language') || 'en';
  setLanguage(savedLang);
  initSettingsSync();
});

function safeUpdate(id, val, field = 'value') {
  const el = qs(id);
  if (!el) return;
  // Don't overwrite if the user is currently interacting with the field
  if (document.activeElement === el) return;
  
  if (field === 'value') el.value = val;
  else if (field === 'checked') el.checked = !!val;
  else if (field === 'textContent') el.textContent = val;
}

function renderSettings(config) {
  if (!config) return;
  
  // Note: agent_name, gender, hobbies are now primarily in Portrait
  // but we still sync them if the Portrait section is loaded via internal_state.
  // We can update them here too if needed for consistency.
  safeUpdate('pt-name', config.agent_name || '');
  safeUpdate('pt-nickname', config.nickname || '');
  safeUpdate('pt-gender', config.gender || 'non-binary');
  safeUpdate('pt-hobbies', (config.hobbies || []).join(', '));

  safeUpdate('set-save-interval', config.save_interval || 60);
  safeUpdate('set-push-interval', config.state_push_interval || 1.0);
  safeUpdate('set-audit-enabled', !!config.audit_enabled, 'checked');

  if (config.language) {
    const lang = config.language;
    currentLang = lang;
    localStorage.setItem('language', lang);
    document.querySelectorAll('input[name="language"]').forEach(radio => {
      radio.checked = radio.value === lang;
    });
    // If translations already loaded for this language, update UI immediately
    if (translations[lang]) {
      updateUIStrings();
      // Re-render skills if loaded
      if (allSkills.built_in.length > 0 || allSkills.workspace.length > 0) {
        filterSkills();
      }
    } else {
      // Otherwise load translations
      loadTranslations(lang);
    }
  }

  const routingList = qs("llm-routing-list");
  console.log("Rendering LLM callpoints:", {
    routingList: !!routingList,
    llm_callpoints: config.llm_callpoints,
    providers_catalog: config.providers_catalog,
    isCallpointsArray: Array.isArray(config.llm_callpoints),
    isProvidersArray: Array.isArray(config.providers_catalog)
  });
  if (routingList && Array.isArray(config.llm_callpoints) && Array.isArray(config.providers_catalog)) {
    const routes = config.llm_routes || {};
    const providers = config.providers_catalog || [];

    const findProvider = (name) => {
      return providers.find(p => p.config_name === name) || null;
    };
    const describeProvider = (p) => {
      if (!p) return { base_url: "", model_name: "", api_key: "" };
      return {
        base_url: p.base_url || "",
        model_name: p.model_name || "",
        api_key: p.api_key ? "已配置" : "",
      };
    };

    routingList.innerHTML = "";

    const availableProviders = providers.filter(p => !!p.ready);

    config.llm_callpoints.forEach((cp) => {
      const key = cp.key;
      const selected = routes[key] || "";

      const item = document.createElement("div");
      item.className = "provider-item detailed";

      const isSelectedAndAvailable = selected && availableProviders.some(p => p.config_name === selected);
      const callpointStatus = isSelectedAndAvailable ? "ok" : "error";

      const header = document.createElement("div");
      header.className = "provider-item-header";
      header.innerHTML = `
        <span class="provider-status ${callpointStatus}"></span>
        <span class="provider-name">${cp.label || key}</span>
        <span class="provider-info">${key}</span>
      `;

      const desc = document.createElement("div");
      desc.className = "provider-item-desc";
      desc.textContent = cp.description || "";

      const descRow = document.createElement("div");
      descRow.className = "provider-item-desc-row";
      const descGroup = document.createElement("div");
      descGroup.className = "form-group";
      const saveGroup = document.createElement("div");
      saveGroup.className = "form-group";

      const fields = document.createElement("div");
      fields.className = "provider-item-fields";

      const selectGroup = document.createElement("div");
      selectGroup.className = "form-group";
      const selectLabel = document.createElement("label");
      selectLabel.textContent = "选择服务提供商";
      const select = document.createElement("select");

      const emptyOpt = document.createElement("option");
      emptyOpt.value = "";
      emptyOpt.textContent = "未选择（请先在 Providers 配置服务商）";
      select.appendChild(emptyOpt);

      if (selected && !availableProviders.some(p => p.config_name === selected)) {
        const cur = findProvider(selected);
        const curLabel = cur ? (cur.label || cur.config_name) : selected;
        const curModelMark = cur?.model_name ? ` · ${cur.model_name}` : "";
        const curOpt = document.createElement("option");
        curOpt.value = selected;
        curOpt.textContent = `${curLabel} (${selected})${curModelMark}（不可用）`;
        select.appendChild(curOpt);
      }

      availableProviders.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.config_name;
        const modelMark = p.model_name ? ` · ${p.model_name}` : "";
        opt.textContent = `${p.label} (${p.config_name})${modelMark}（可用）`;
        select.appendChild(opt);
      });

      select.value = selected;
      selectGroup.appendChild(selectLabel);
      selectGroup.appendChild(select);
      fields.appendChild(selectGroup);

      const baseGroup = document.createElement("div");
      baseGroup.className = "form-group";
      const baseLabel = document.createElement("label");
      baseLabel.textContent = "base_url";
      const baseInput = document.createElement("input");
      baseInput.type = "text";
      baseInput.readOnly = true;
      baseGroup.appendChild(baseLabel);
      baseGroup.appendChild(baseInput);
      fields.appendChild(baseGroup);

      const modelGroup = document.createElement("div");
      modelGroup.className = "form-group";
      const modelLabel = document.createElement("label");
      modelLabel.textContent = "model_name";
      const modelInput = document.createElement("input");
      modelInput.type = "text";
      modelInput.readOnly = true;
      modelGroup.appendChild(modelLabel);
      modelGroup.appendChild(modelInput);
      fields.appendChild(modelGroup);

      const keyGroup = document.createElement("div");
      keyGroup.className = "form-group";
      const keyLabel = document.createElement("label");
      keyLabel.textContent = "api_key";
      const keyInput = document.createElement("input");
      keyInput.type = "text";
      keyInput.readOnly = true;
      keyGroup.appendChild(keyLabel);
      keyGroup.appendChild(keyInput);
      fields.appendChild(keyGroup);

      const refreshSummary = () => {
        const v = select.value || "";
        const p = v ? findProvider(v) : null;
        const d = describeProvider(p);
        baseInput.value = d.base_url;
        modelInput.value = d.model_name;
        keyInput.value = d.api_key;
      };
      refreshSummary();
      select.addEventListener("change", refreshSummary);

      const saveBtn = document.createElement("button");
      saveBtn.textContent = getTranslation('provider.save') || 'Save';
      saveBtn.addEventListener("click", () => {
        const v = select.value || "";
        if (!v) {
          // 如果当前有不可用的路由设置，可以删除它
          if (selected && !availableProviders.some(p => p.config_name === selected)) {
            if (window.ws && window.ws.readyState === WebSocket.OPEN) {
              // 发送删除请求（将路由设为空）
              window.ws.send(JSON.stringify({
                type: "update_settings",
                data: { llm_routes: { [key]: "" } }
              }));
              showNotification("已删除不可用的路由", "success");
            } else {
              showNotification("WebSocket not connected", "error");
            }
          } else {
            showNotification("请先选择一个可用的服务提供商", "warning");
          }
          return;
        }
        if (window.ws && window.ws.readyState === WebSocket.OPEN) {
          window.ws.send(JSON.stringify({
            type: "update_settings",
            data: { llm_routes: { [key]: v } }
          }));
        } else {
          showNotification("WebSocket not connected", "error");
        }
      });

      descGroup.appendChild(desc);
      saveGroup.appendChild(saveBtn);
      descRow.appendChild(descGroup);
      descRow.appendChild(saveGroup);

      item.appendChild(header);
      item.appendChild(descRow);
      item.appendChild(fields);
      routingList.appendChild(item);
    });
  }
}

function renderPortrait(state) {
  if (!state) return;
  latestInternalState = state;

  // Helper function for progress bars
  const updateProgress = (id, val) => {
    const el = qs(id);
    if (el) el.style.width = (val * 100) + "%";
    const valEl = qs(id + "-val");
    if (valEl) valEl.textContent = val.toFixed(2);
  };

  // 1. Basic Profile
  safeUpdate("pt-id", state.agent_id || "");
  const displayName = state.agent_name || "Crabclaw";
  safeUpdate("pt-name", displayName);
  safeUpdate("pt-nickname", state.nickname || "");
  safeUpdate("pt-age", (state.age || 0).toFixed(1));
  
  if (qs("pt-gender") && document.activeElement !== qs("pt-gender")) {
    qs("pt-gender").value = state.gender || "non-binary";
  }
  
  safeUpdate("pt-height", state.height || 175);
  safeUpdate("pt-weight", state.weight || 70);
  safeUpdate("pt-hobbies", (state.hobbies || []).join(", "));

  // 2. Psychology & Emotion
  const emotion = state.psychology?.emotion || {};
  console.log("[renderPortrait] emotion data:", emotion);
  updateProgress("pt-curiosity", emotion.curiosity || 0);
  updateProgress("pt-confidence", emotion.confidence || 0);
  updateProgress("pt-risk-aversion", emotion.risk_aversion || 0);
  updateProgress("pt-social-trust", emotion.social_trust || 0);

  // 3. Needs & Motivation
  const needs = state.needs || {};
  console.log("[renderPortrait] needs data:", needs);
  updateProgress("pt-need-energy", needs.energy || 0);
  updateProgress("pt-need-social", needs.social || 0);
  updateProgress("pt-need-achievement", needs.achievement || 0);
  updateProgress("pt-need-curiosity", needs.curiosity || 0);
  updateProgress("pt-need-safety", needs.safety || 0);

  // 4. Sociology & Mind
  safeUpdate("pt-social-ticks", state.sociology?.ticks_since_last_interaction || 0);
  safeUpdate("pt-credits", (state.sociology?.economy?.credits || 0).toFixed(2));
  safeUpdate("pt-partners-count", state.sociology?.partners_count || 0);

  // 5. Self Model & Skills
  const selfModel = state.self_model || {};
  const skillsContainer = qs("pt-skills");
  if (skillsContainer) {
    skillsContainer.innerHTML = "";
    const skills = selfModel.skills || {};
    Object.entries(skills).forEach(([name, level]) => {
      const item = document.createElement("div");
      item.className = "skill-item";
      item.innerHTML = `<span class="skill-name">${name}</span><span class="skill-level">${(level * 100).toFixed(0)}%</span>`;
      skillsContainer.appendChild(item);
    });
    if (Object.keys(skills).length === 0) {
      skillsContainer.innerHTML = '<div class="skill-item"><span class="skill-name">No skills yet</span></div>';
    }
  }

  // 6. Physiology
  const metabolism = state.physiology?.metabolism || {};
  if (qs("pt-phys-health")) qs("pt-phys-health").textContent = (metabolism.health || 0).toFixed(0) + "%";
  if (qs("pt-phys-satiety")) qs("pt-phys-satiety").textContent = (metabolism.satiety || 0).toFixed(0) + "%";
  if (qs("pt-phys-plasticity")) qs("pt-phys-plasticity").textContent = ((state.physiology?.plasticity || 0) * 100).toFixed(0) + "%";

  // Also update overview metrics
  renderOverviewFromState(state);
}

function renderOverviewFromState(state){
  if (!state || typeof state !== "object") return;
  latestInternalState = state;
  if (ovAgentAlive) ovAgentAlive.textContent = String(state.is_alive ?? "unknown");
  if (ovEnergy) ovEnergy.textContent = state.physiology?.metabolism?.energy?.toFixed?.(2) ?? "-";
  if (ovCredits) ovCredits.textContent = state.sociology?.economy?.credits?.toFixed?.(2) ?? "-";
  if (ovFocus) ovFocus.textContent = pretty(state.current_focus || []);
  if (ovLastDecision) ovLastDecision.textContent = lastAutoDecisionLabel;
}

function requestPromptEvolutionStatus(){
  if (!window.ws || window.ws.readyState !== WebSocket.OPEN) return;
  window.ws.send(JSON.stringify({ type: "get_prompt_evolution_status" }));
}

function postPromptAction(type, data){
  if (!window.ws || window.ws.readyState !== WebSocket.OPEN){
    showNotification("WebSocket not connected", "error");
    return;
  }
  window.ws.send(JSON.stringify({ type, data }));
}

function openCoreFileEditor(fileRel){
  if (!fileRel) return;
  const menuItem = document.querySelector('.menu-item[data-section="core-files"]');
  if (menuItem) menuItem.click();
  const currentFileName = document.getElementById("current-file-name");
  if (currentFileName) currentFileName.textContent = fileRel;
  if (window.ws && window.ws.readyState === WebSocket.OPEN){
    window.ws.send(JSON.stringify({ type: "get_files" }));
    window.ws.send(JSON.stringify({
      type: "get_file_content",
      data: { file_name: fileRel },
    }));
  }
}

function openCandidateDetail(detail){
  if (!candidateDetailModal) return;
  currentCandidateDetail = detail || null;
  loadDraftToLocal(detail.review_draft || {});
  
  // Ensure conflict container exists
  let conflictContainer = document.getElementById("candidate-review-conflicts");
  if (!conflictContainer && candidateDetailDiff) {
    conflictContainer = document.createElement("div");
    conflictContainer.id = "candidate-review-conflicts";
    conflictContainer.className = "review-conflicts-panel";
    // Insert before diff container
    candidateDetailDiff.parentNode.insertBefore(conflictContainer, candidateDetailDiff);
  }
  renderReviewConflicts(detail.review_conflicts || {});

  candidateDetailTitle.textContent = `${detail.candidate_id} · ${detail.file}`;
  candidateDetailSummary.textContent = pretty({
    status: detail.status,
    created_at: detail.created_at,
    online: detail.online,
    base_score: detail.base_score,
    candidate_score: detail.candidate_score,
    latest_version_meta: detail.latest_version_meta,
  });
  renderDiffText(detail.diff?.diff_text || "", candidateDiffKeyword?.value || "", 0);
  candidateDetailEvents.textContent = pretty(detail.events || []);
  candidateDetailContent.textContent = detail.content || "";
  if (peCandidateInput) peCandidateInput.value = detail.candidate_id || "";
  if (peFileInput) peFileInput.value = detail.file || "";
  candidateDetailModal.classList.remove("hidden");
}

function requestCandidateDetail(candidateId){
  if (!candidateId) return;
  postPromptAction("prompt_candidate_detail", { candidate_id: candidateId });
}

if (peRefreshBtn){
  peRefreshBtn.addEventListener("click", () => requestPromptEvolutionStatus());
}
if (peAutoDecideBtn){
  peAutoDecideBtn.addEventListener("click", () => postPromptAction("prompt_auto_decide", {}));
}
if (pePromoteBtn){
  pePromoteBtn.addEventListener("click", () => {
    const candidate = (peCandidateInput?.value || "").trim();
    postPromptAction("prompt_promote", { candidate_id: candidate });
  });
}
if (peRollbackBtn){
  peRollbackBtn.addEventListener("click", () => {
    const file = (peFileInput?.value || "").trim();
    postPromptAction("prompt_rollback", { file });
  });
}
if (peFactoryResetBtn){
  peFactoryResetBtn.addEventListener("click", () => {
    const file = (peFileInput?.value || "").trim();
    postPromptAction("prompt_factory_reset", { file });
  });
}
if (peApplyRulesBtn){
  peApplyRulesBtn.addEventListener("click", () => {
    postPromptAction("prompt_set_alert_rules", {
      low_sample_canary: Number(peRuleLowSample?.value || 5),
      warning_error_rate: Number(peRuleWarningError?.value || 0.25),
      critical_error_rate: Number(peRuleCriticalError?.value || 0.45),
      high_avg_turns: Number(peRuleHighTurns?.value || 4.5),
    });
  });
}
for (const el of [peCompareSort, peCompareOrder, peCompareMinSamples, peCompareSearch]){
  if (!el) continue;
  el.addEventListener("input", () => renderCompareTable(promptEvolutionState.comparisons || {}, promptEvolutionState.alerts || []));
  el.addEventListener("change", () => renderCompareTable(promptEvolutionState.comparisons || {}, promptEvolutionState.alerts || []));
}
if (candidateDetailClose){
  candidateDetailClose.addEventListener("click", () => candidateDetailModal?.classList.add("hidden"));
}
if (candidateDetailModal){
  candidateDetailModal.addEventListener("click", (e) => {
    if (e.target === candidateDetailModal) candidateDetailModal.classList.add("hidden");
  });
}
if (candidateDetailPromote){
  candidateDetailPromote.addEventListener("click", () => {
    const candidateId = currentCandidateDetail?.candidate_id;
    if (!candidateId) return;
    postPromptAction("prompt_promote", { candidate_id: candidateId });
  });
}
if (candidateDetailRollback){
  candidateDetailRollback.addEventListener("click", () => {
    const fileRel = currentCandidateDetail?.file;
    if (!fileRel) return;
    postPromptAction("prompt_rollback", { file: fileRel });
  });
}
if (candidateDetailFactoryReset){
  candidateDetailFactoryReset.addEventListener("click", () => {
    const fileRel = currentCandidateDetail?.file;
    if (!fileRel) return;
    postPromptAction("prompt_factory_reset", { file: fileRel });
  });
}
if (candidateDetailJumpFile){
  candidateDetailJumpFile.addEventListener("click", () => {
    const fileRel = currentCandidateDetail?.file;
    if (!fileRel) return;
    candidateDetailModal?.classList.add("hidden");
    openCoreFileEditor(fileRel);
  });
}
if (candidateDiffPrevHunk){
  candidateDiffPrevHunk.addEventListener("click", () => {
    if (currentDiffHunks.length === 0) return;
    currentHunkIndex = Math.max(0, currentHunkIndex - 1);
    renderDiffText((currentCandidateDetail?.diff?.diff_text || ""), candidateDiffKeyword?.value || "", currentHunkIndex);
  });
}
if (candidateDiffNextHunk){
  candidateDiffNextHunk.addEventListener("click", () => {
    if (currentDiffHunks.length === 0) return;
    currentHunkIndex = Math.min(currentDiffHunks.length - 1, currentHunkIndex + 1);
    renderDiffText((currentCandidateDetail?.diff?.diff_text || ""), candidateDiffKeyword?.value || "", currentHunkIndex);
  });
}
if (candidateDiffHunkSelect){
  candidateDiffHunkSelect.addEventListener("change", () => {
    currentHunkIndex = Number(candidateDiffHunkSelect.value || 0);
    renderDiffText((currentCandidateDetail?.diff?.diff_text || ""), candidateDiffKeyword?.value || "", currentHunkIndex);
  });
}
if (candidateDiffKeyword){
  candidateDiffKeyword.addEventListener("input", () => {
    renderDiffText((currentCandidateDetail?.diff?.diff_text || ""), candidateDiffKeyword.value || "", currentHunkIndex);
  });
}
if (candidateDiffCopyPatch){
  candidateDiffCopyPatch.addEventListener("click", () => {
    copyText(currentCandidateDetail?.diff?.diff_text || "");
  });
}
if (candidateDiffCopyHunk){
  candidateDiffCopyHunk.addEventListener("click", () => {
    copyText(currentHunkText());
  });
}
if (candidateDiffAcceptHunk){
  candidateDiffAcceptHunk.addEventListener("click", () => {
    currentHunkDecisions[currentHunkIndex] = "accepted";
    renderDiffText((currentCandidateDetail?.diff?.diff_text || ""), candidateDiffKeyword?.value || "", currentHunkIndex);
    saveDraft();
  });
}
if (candidateDiffRejectHunk){
  candidateDiffRejectHunk.addEventListener("click", () => {
    currentHunkDecisions[currentHunkIndex] = "rejected";
    renderDiffText((currentCandidateDetail?.diff?.diff_text || ""), candidateDiffKeyword?.value || "", currentHunkIndex);
    saveDraft();
  });
}
if (candidateDiffApplySelected){
  candidateDiffApplySelected.addEventListener("click", () => {
    const candidateId = currentCandidateDetail?.candidate_id;
    if (!candidateId) return;
    const accepted = acceptedHunkIndices();
    postPromptAction("prompt_apply_selected_hunks", {
      candidate_id: candidateId,
      accepted_indices: accepted,
    });
  });
}
if (candidateDraftSave){
  candidateDraftSave.addEventListener("click", () => saveDraft());
}
if (candidateDraftClear){
  candidateDraftClear.addEventListener("click", () => {
    const candidateId = currentCandidateDetail?.candidate_id;
    if (!candidateId) return;
    postPromptAction("prompt_clear_review_draft", { candidate_id: candidateId });
  });
}

function connect(){
  const url = new URL(window.location.href);
  const host = url.hostname || "127.0.0.1";
  const httpPort = url.port || "18791";
  const wsPort = parseInt(httpPort) + 1 || "18792";
  const wsUrl = `ws://${host}:${wsPort}/ws`;
  const token = localStorage.getItem('access_token');
  const finalWsUrl = token ? `${wsUrl}?token=${encodeURIComponent(token)}` : wsUrl;
  if (wsUrlPill) wsUrlPill.textContent = finalWsUrl;

  const ws = new WebSocket(finalWsUrl);
  window.ws = ws; // Make ws available globally
  setConn(false, "menu.ws_connecting");

  ws.onopen = () => {
    setConn(true, "menu.ws_connected");
    // Request chat history when connected
    ws.send(JSON.stringify({ type: "get_chat_history" }));
    // Request friends and groups list
    ws.send(JSON.stringify({ type: "get_friends" }));
    ws.send(JSON.stringify({ type: "get_groups" }));
    // Request translations for the current language
    loadTranslations(currentLang);
  };
  ws.onclose = (event) => {
    console.log(`WebSocket closed. Code: ${event.code}, Reason: ${event.reason}, Was clean: ${event.wasClean}`);
    console.trace("WebSocket close stack trace");
    setConn(false, "menu.ws_disconnected");
  };
  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
    setConn(false, "menu.ws_error");
  };

  ws.onmessage = (ev) => {
    let payload = null;
    try { payload = JSON.parse(ev.data); } catch { return; }

    const type = payload.type || "event";
    const data = Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload;
    
    // Debug log for all message types
    if (type === "inbound_message" || type === "outbound_message") {
      console.log(`[Dashboard] Received ${type}:`, data);
    }

    if (type === "hello"){
      requestPromptEvolutionStatus();
      // Also request translations for current language immediately
      loadTranslations(currentLang);
      const channelsSection = document.getElementById('section-channels');
      if (channelsSection && channelsSection.classList.contains('active')) {
        loadChannels();
      }
      return;
    }

    if (type === "internal_state"){
      console.log("[Dashboard] Received internal_state:", data);
      try {
        renderPortrait(data);
      } catch (error) {
        console.error("[Dashboard] renderPortrait failed:", error);
      }
      return;
    }

    if (type === "prompt_evolution_status"){
      renderPromptEvolution(data);
      return;
    }

    if (type === "prompt_auto_decide_result"){
      if (data.success){
        const decisions = data.decisions || [];
        lastAutoDecisionLabel = decisions.length ? `${decisions.length} decisions` : "no decision";
        renderOverviewFromState(latestInternalState);
        showNotification(`Auto decide finished: ${decisions.length} decision(s)`, "success");
      } else {
        showNotification(`Auto decide failed: ${data.error || "unknown"}`, "error");
      }
      requestPromptEvolutionStatus();
      return;
    }

    if (type === "prompt_metrics_result" || type === "prompt_promote_result" || type === "prompt_rollback_result" || type === "prompt_factory_reset_result" || type === "prompt_set_alert_rules_result"){
      if (data.success){
        showNotification(`${type} success`, "success");
      } else {
        showNotification(`${type} failed: ${data.error || "unknown"}`, "error");
      }
      requestPromptEvolutionStatus();
      if (currentCandidateDetail?.candidate_id){
        requestCandidateDetail(currentCandidateDetail.candidate_id);
      }
      return;
    }

    if (type === "prompt_apply_selected_hunks_result"){
      if (data.success){
        showNotification("Selected hunks applied", "success");
      } else {
        showNotification(`prompt_apply_selected_hunks failed: ${data.error || "unknown"}`, "error");
      }
      requestPromptEvolutionStatus();
      if (currentCandidateDetail?.candidate_id){
        requestCandidateDetail(currentCandidateDetail.candidate_id);
      }
      return;
    }

    if (type === "prompt_save_review_draft_result"){
      if (data.success){
        showNotification("Review draft saved", "success");
      } else {
        showNotification(`prompt_save_review_draft failed: ${data.error || "unknown"}`, "error");
      }
      if (currentCandidateDetail?.candidate_id){
        requestCandidateDetail(currentCandidateDetail.candidate_id);
      }
      return;
    }

    if (type === "prompt_clear_review_draft_result"){
      if (data.success){
        showNotification("Review draft cleared", "success");
        currentHunkDecisions = {};
        if (candidateReviewer) candidateReviewer.value = "";
        renderDiffText((currentCandidateDetail?.diff?.diff_text || ""), candidateDiffKeyword?.value || "", currentHunkIndex);
      } else {
        showNotification(`prompt_clear_review_draft failed: ${data.error || "unknown"}`, "error");
      }
      if (currentCandidateDetail?.candidate_id){
        requestCandidateDetail(currentCandidateDetail.candidate_id);
      }
      return;
    }

    if (type === "test_provider_result"){
      if (data.success){
        showNotification('Provider connection test successful!', 'success');
        // 刷新提供商列表，显示新添加的提供商
        if (window.ws && window.ws.readyState === WebSocket.OPEN) {
          window.ws.send(JSON.stringify({ type: 'get_providers' }));
        }
        // 更新状态为ok
        const providerItems = document.querySelectorAll('.provider-item');
        providerItems.forEach(item => {
          const info = item.querySelector('.provider-info');
          if (info && info.textContent === data.provider_id) {
            const status = item.querySelector('.provider-status');
            if (status) {
              status.className = 'provider-status ok';
            }
            // 恢复保存按钮状态
            const actions = item.querySelector('.provider-item-actions');
            const buttons = actions ? actions.querySelectorAll('button') : null;
            const saveBtn = buttons && buttons.length ? buttons[buttons.length - 1] : null;
            if (saveBtn) {
              saveBtn.disabled = false;
              saveBtn.textContent = getTranslation('provider.save') || 'Save';
            }
          }
        });
      } else {
        showNotification(`Provider connection test failed: ${data.error || 'Unknown error'}`, 'error');
        // 更新状态为error
        const providerItems = document.querySelectorAll('.provider-item');
        providerItems.forEach(item => {
          const info = item.querySelector('.provider-info');
          if (info && info.textContent === data.provider_id) {
            const status = item.querySelector('.provider-status');
            if (status) {
              status.className = 'provider-status error';
            }
            // 恢复保存按钮状态
            const actions = item.querySelector('.provider-item-actions');
            const buttons = actions ? actions.querySelectorAll('button') : null;
            const saveBtn = buttons && buttons.length ? buttons[buttons.length - 1] : null;
            if (saveBtn) {
              saveBtn.disabled = false;
              saveBtn.textContent = getTranslation('provider.save') || 'Save';
            }
          }
        });
      }
      return;
    }

    if (type === "settings_updated") {
      if (data.ok) {
        // Settings updated successfully
        console.log('Settings updated successfully');
        // Refresh providers list to show newly added providers
        // Refresh config to update LLM routes and callpoint status
        if (window.ws && window.ws.readyState === WebSocket.OPEN) {
          window.ws.send(JSON.stringify({ type: 'get_providers' }));
          window.ws.send(JSON.stringify({ type: 'get_config' }));
        }
      } else {
        showNotification('Failed to update settings: ' + data.message, 'error');
        // 恢复保存按钮状态
        const saveBtns = document.querySelectorAll('.provider-item button');
        saveBtns.forEach(btn => {
          if (btn.textContent.includes('Saving')) {
            btn.disabled = false;
            btn.textContent = getTranslation('provider.save') || 'Save';
          }
        });
      }
      return;
    }

    if (type === "prompt_candidate_detail_result"){
      if (data.success){
        openCandidateDetail(data.detail || {});
      } else {
        showNotification(`prompt_candidate_detail failed: ${data.error || "unknown"}`, "error");
      }
      return;
    }

    if (type === "audit"){
      _buffer.push({kind: "audit", payload: data});
      if (_buffer.length > _MAX) _buffer.shift();
      renderEvent("audit", data);
      renderLlmStats();
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

    if (type === "channels"){
      try {
        if (data && data.error) {
          showNotification(`channels payload error: ${data.error}`, "error");
        }
        renderChannels(data || {});
      } catch (error) {
        console.error("[Dashboard] renderChannels failed:", error);
        showNotification("频道面板渲染失败，请刷新页面", "error");
      }
      return;
    }

    if (type === "channel_config_result"){
      showNotification(data.ok ? "频道配置已保存" : (data.error || "频道配置保存失败"), data.ok ? "success" : "error");
      return;
    }

    if (type === "channel_config_delete_result"){
      showNotification(data.ok ? "频道配置已删除" : "频道配置删除失败", data.ok ? "success" : "error");
      return;
    }

    if (type === "channel_config_state_result"){
      showNotification(data.ok ? "频道实例状态已更新" : "频道实例状态更新失败", data.ok ? "success" : "error");
      return;
    }

    if (type === "identity_map_result"){
      showNotification(data.ok ? "身份映射已保存" : "身份映射保存失败", data.ok ? "success" : "error");
      return;
    }

    if (type === "identity_delete_result"){
      showNotification(data.ok ? "身份映射已删除" : "身份映射删除失败", data.ok ? "success" : "error");
      return;
    }

    if (type === "users"){
      if (data.ok === false) {
        showNotification(data.error || "Failed to load users", "error");
      return;
      }
      renderUsers(data.users || []);
      return;
    }

    if (type === "config"){
      console.log("Received config data:", data);
      latestConfig = data;
      renderConfig(data);
      renderSettings(data);
      return;
    }

    if (type === "update_settings_result"){
      if (data.success){
        showNotification("已保存", "success");
        if (window.ws && window.ws.readyState === WebSocket.OPEN) {
          window.ws.send(JSON.stringify({ type: "get_providers" }));
          window.ws.send(JSON.stringify({ type: "get_config" }));
        }
      } else {
        showNotification(`保存失败: ${data.error || "unknown"}`, "error");
      }
      return;
    }

    if (type === "translations"){
      console.log("Received translations for", data.lang, ":", data.translations);
      translations[data.lang] = data.translations;
      // Ensure we apply strings immediately
      updateUIStrings();
      // Re-render components that might have changed
      if (latestInternalState) {
        renderPortrait(latestInternalState);
      }
      if (latestConfig) {
        renderSettings(latestConfig);
      }
      if (latestConfig && latestConfig.providers) {
        if (Array.isArray(latestConfig.providers)) {
          renderProviders(latestConfig.providers);
        } else if (latestConfig.providers) {
          // Convert object to array if needed
          const providersArray = Object.values(latestConfig.providers);
          renderProviders(providersArray);
        }
      }
      // Re-render skills if loaded
      if (allSkills.built_in.length > 0 || allSkills.workspace.length > 0) {
        filterSkills();
      }
      return;
    }

    if (type === "chat_response"){
      addChatMessage(data.response, false);
      return;
    }

    if (type === "agent_reply"){
      addChatMessage(payload.content, false);
      return;
    }

    if (type === "user_message"){
      // Ignore user messages (they're already added to the chat by addChatMessage)
      return;
    }

    if (type === "files"){
      renderFiles(data.files);
      return;
    }

    if (type === "file_content"){
      const fileContentEl = document.getElementById("file-content");
      if (fileContentEl) fileContentEl.value = data.content;
      const fileNameEl = document.getElementById("current-file-name");
      const filePathEl = document.getElementById("current-file-path");
      if (fileNameEl) {
        // Show only filename without prefix
        fileNameEl.textContent = data.file_name.split('/').pop();
      }
      if (filePathEl) {
        // Show full path with workspace
        const workspacePath = latestConfig?.workspace_path || '';
        filePathEl.textContent = workspacePath ? `${workspacePath}/${data.file_name}` : data.file_name;
      }
      return;
    }

    if (type === "file_saved"){
      if (data.success) {
        showNotification("已保存", "success");
      } else {
        showNotification("保存失败", "error");
      }
      return;
    }

    if (type === "skills"){
      renderSkills(data);
      return;
    }

    if (type === "template_reloaded"){
      showNotification(data.message || `Template '${data.file_name}' has been hot-reloaded`, "success");
      return;
    }

    if (type === "chat_history"){
      loadChatHistory(data.messages || []);
      return;
    }

    // User authentication
    if (type === "register_response"){
      if (data.ok){
        currentUser = data.user;
        // Store the access token, not the session_id
        if (data.access_token) {
            localStorage.setItem('access_token', data.access_token);
        }
        updateUserUI();
        closeRegisterModal();
        showNotification('Registration successful', 'success');
        // Reconnect WebSocket with the new token
        if(window.ws) window.ws.close();
        connect();
      } else {
        document.getElementById('register-error').textContent = data.error;
      }
      return;
    }

    if (type === "login_response"){
      if (data.ok){
        currentUser = data.user;
        // Store the access token, not the session_id
        if (data.access_token) {
            localStorage.setItem('access_token', data.access_token);
        }
        updateUserUI();
        closeLoginModal();
        showNotification('Login successful', 'success');
        // Reconnect WebSocket with the new token
        if(window.ws) window.ws.close();
        connect();
      } else {
        document.getElementById('login-error').textContent = data.error;
      }
      return;
    }

    if (type === "logout_response"){
      if (data.ok){
        currentUser = null;
        currentSession = null;
        localStorage.removeItem('session_id');
        updateUserUI();
        showNotification('Logged out successfully', 'success');
      }
      return;
    }

    if (type === "session_response"){
      if (data.ok){
        currentUser = data.user;
        currentSession = data.session;
        updateUserUI();
      }
      return;
    }

    if (type === "prompt_evolution"){
      showNotification(
        `Prompt '${data.template_name}' evolved: ${data.rationale}`,
        "info"
      );
      requestPromptEvolutionStatus();
      return;
    }

    if (type === "friends"){
      friends = data.friends || [];
      renderFriends();
      return;
    }

    if (type === "groups"){
      groups = data.groups || [];
      renderGroups();
      return;
    }

    if (type === "friend_message"){
      handleFriendMessageNotification(data);
      return;
    }

    if (type === "group_message"){
      handleGroupMessageNotification(data);
      return;
    }

    if (type === "friend_chat_history"){
      const container = document.getElementById('friend-chat-messages');
      if (container && data.messages) {
        container.innerHTML = '';
        data.messages.forEach(msg => {
          addChatMessageToContainer(container, msg.content, msg.is_user, msg.sender_name);
        });
      }
      return;
    }

    if (type === "group_chat_history"){
      const container = document.getElementById('group-chat-messages');
      if (container && data.messages) {
        container.innerHTML = '';
        data.messages.forEach(msg => {
          addChatMessageToContainer(container, msg.content, msg.is_user, msg.sender_name);
        });
      }
      return;
    }

    if (type === "friend_chat_response"){
      const container = document.getElementById('friend-chat-messages');
      if (container && data.response) {
        addChatMessageToContainer(container, data.response, false, data.from_agent_name);
      }
      return;
    }

    if (type === "group_chat_response"){
      const container = document.getElementById('group-chat-messages');
      if (container && data.response) {
        addChatMessageToContainer(container, data.response, false, data.from_agent_name);
      }
      return;
    }

    // Handle inbound messages from external channels (e.g., Feishu)
    if (type === "inbound_message"){
      if (!shouldRenderEvent(type, data)) return;
      // Show message in the main chat
      const chatMessages = document.getElementById('chat-messages');
      if (chatMessages && data.content) {
        // Create message element for user message
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message user';
        
        const avatarDiv = document.createElement("div");
        avatarDiv.className = "message-avatar";
        avatarDiv.textContent = "👤";
        
        const contentContainer = document.createElement("div");
        contentContainer.className = "message-content-container";
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = data.content;
        
        contentContainer.appendChild(contentDiv);
        
        // Add channel info if available - use emoji for different channels
        if (data.channel) {
          const channelLabel = document.createElement('div');
          channelLabel.style.cssText = 'font-size: 10px; color: rgba(255,255,255,0.8); margin-top: 4px; display: flex; align-items: center; gap: 4px;';
          
          // Channel emoji mapping
          const channelEmojis = {
            'feishu': '📱',
            'mochat': '💬',
            'discord': '🎮',
            'matrix': '🟣',
            'dingtalk': '🔔',
            'dashboard': '💻',
          };
          const emoji = channelEmojis[data.channel.toLowerCase()] || '📨';
          const senderDisplay = data.sender_id ? ` ${data.sender_id}` : '';
          channelLabel.textContent = `${emoji} [${data.channel}]${senderDisplay}`;
          contentContainer.appendChild(channelLabel);
        }
        
        // Add timestamp
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-timestamp';
        timeDiv.textContent = data.timestamp ? new Date(data.timestamp * 1000).toLocaleString() : new Date().toLocaleString();
        contentContainer.appendChild(timeDiv);
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentContainer);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
      return;
    }

    // Handle outbound messages (AI responses to external channels) - skip rendering to avoid duplicates
    if (type === "outbound_message"){
      // Outbound messages are already handled by agent_reply to avoid duplicates
      return;
    }

    _buffer.push({kind: "audit", payload});
    if (_buffer.length > _MAX) _buffer.shift();
    renderEvent("audit", payload);
    renderLlmStats();
  };

  ws.addEventListener("close", () => {
    setTimeout(connect, 1200);
  });
}

// User authentication functions
function updateUserUI() {
  const userMenuButton = document.getElementById('user-menu-button');
  const userMenuLabel = document.getElementById('user-menu-label');
  const userDisplayName = document.getElementById('user-display-name');
  const userUsername = document.getElementById('user-username');
  
  if (currentUser) {
    userMenuLabel.textContent = currentUser.display_name;
    if (userDisplayName) userDisplayName.textContent = currentUser.display_name;
    if (userUsername) userUsername.textContent = currentUser.username;
  } else {
    userMenuLabel.textContent = 'Login';
    if (userDisplayName) userDisplayName.textContent = 'Guest';
    if (userUsername) userUsername.textContent = 'Not logged in';
  }
  
  // Update menu visibility based on user role
  updateMenuVisibility();
}

function updateMenuVisibility() {
  // Get all menu items with data-access attribute
  const menuItems = document.querySelectorAll('.menu-item[data-access]');

  menuItems.forEach(item => {
    const access = item.getAttribute('data-access');
    item.style.display = canAccessMenu(access) ? '' : 'none';
  });

  const activeMenu = document.querySelector('.menu-item.active');
  if (!activeMenu || !canAccessMenu(activeMenu.getAttribute('data-access'))) {
    if (currentUser) {
      activateSection('chat');
    } else {
      const loginMenu = document.querySelector('.menu-item[data-section="chat"]');
      if (loginMenu) loginMenu.classList.remove('active');
    }
  }
}

async function fetchCurrentUser() {
  const token = getAccessToken();
  if (!token) {
    clearAuthState();
    return false;
  }
  try {
    const response = await fetch('/api/me', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!data.ok) {
      clearAuthState();
      return false;
    }
    currentUser = data.user;
    updateUserUI();
    return true;
  } catch (error) {
    console.error('Fetch current user failed:', error);
    clearAuthState();
    return false;
  }
}

function openLoginModal() {
  redirectToLogin();
}

function closeLoginModal() {
  const loginModal = document.getElementById('login-modal');
  if (loginModal) loginModal.classList.add('hidden');
}

function openRegisterModal() {
  document.getElementById('register-modal').classList.remove('hidden');
  document.getElementById('register-error').textContent = '';
}

function closeRegisterModal() {
  document.getElementById('register-modal').classList.add('hidden');
}

function openUserMenu() {
  document.getElementById('user-menu').classList.remove('hidden');
}

function closeUserMenu() {
  document.getElementById('user-menu').classList.add('hidden');
}

// Event listeners for authentication
document.addEventListener('DOMContentLoaded', () => {
  // User menu button
  const userMenuButton = document.getElementById('user-menu-button');
  if (userMenuButton) {
    userMenuButton.addEventListener('click', () => {
      if (currentUser) {
        openUserMenu();
      } else {
        redirectToLogin();
      }
    });
  }
  
  // User menu close
  const userMenuClose = document.getElementById('user-menu-close');
  if (userMenuClose) {
    userMenuClose.addEventListener('click', closeUserMenu);
  }
  
  // Switch to register
  const switchToRegister = document.getElementById('switch-to-register');
  if (switchToRegister) {
    switchToRegister.addEventListener('click', () => {
      redirectToLogin();
    });
  }
  
  // Switch to login
  const switchToLogin = document.getElementById('switch-to-login');
  if (switchToLogin) {
    switchToLogin.addEventListener('click', () => {
      redirectToLogin();
    });
  }
  
  // Login modal close
  const loginClose = document.getElementById('login-close');
  if (loginClose) {
    loginClose.addEventListener('click', closeLoginModal);
  }
  
  // Register modal close
  const registerClose = document.getElementById('register-close');
  if (registerClose) {
    registerClose.addEventListener('click', closeRegisterModal);
  }
  
  // Logout
  const logoutButton = document.getElementById('user-menu-logout');
  if (logoutButton) {
    logoutButton.addEventListener('click', async () => {
      const token = getAccessToken();
      try {
        await fetch('/api/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: token ? `Bearer ${token}` : '',
          }
        });
      } catch (error) {
        console.error('Logout error:', error);
      } finally {
        clearAuthState();
        updateUserUI();
        closeUserMenu();
        redirectToLogin();
      }
    });
  }

  const switchButton = document.getElementById('user-menu-switch-account');
  if (switchButton) {
    switchButton.addEventListener('click', () => {
      clearAuthState();
      updateUserUI();
      closeUserMenu();
      redirectToLogin();
    });
  }

  const deleteButton = document.getElementById('user-menu-delete-account');
  if (deleteButton) {
    deleteButton.addEventListener('click', async () => {
      if (!currentUser) return;
      if (currentUser.is_admin) {
        showNotification('管理员账号不能注销', 'warning');
        return;
      }
      const confirmed = window.confirm('确认注销账号并删除该账号所有 Profile 吗？该操作不可恢复。');
      if (!confirmed) return;
      const token = getAccessToken();
      try {
        const response = await fetch('/api/delete-account', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: token ? `Bearer ${token}` : '',
          },
          body: JSON.stringify({}),
        });
        const data = await response.json();
        if (!data.ok) {
          showNotification(data.error || '注销失败', 'error');
          return;
        }
        clearAuthState();
        updateUserUI();
        closeUserMenu();
        redirectToLogin();
      } catch (error) {
        console.error('Delete account error:', error);
        showNotification('注销失败', 'error');
      }
    });
  }

  const profileButton = document.getElementById('user-menu-profile');
  if (profileButton) {
    profileButton.addEventListener('click', () => {
      activateSection('portrait');
      closeUserMenu();
    });
  }

  window.addEventListener('click', (e) => {
    const userMenu = document.getElementById('user-menu');
    if (userMenu && e.target === userMenu) {
      closeUserMenu();
    }
  });
});

async function bootstrapDashboard() {
  const ok = await fetchCurrentUser();
  if (!ok) {
    redirectToLogin();
    return;
  }
  connect();
}

bootstrapDashboard();
