/**
 * 应用主逻辑
 */
const App = {
  currentSession: null,
  settings: null,
  isSending: false,

  init() {
    this.settings = Storage.getSettings();
    this._bindElements();
    this._bindEvents();
    this._loadOrCreateSession();
    this._renderHistory();
  },

  _bindElements() {
    this.el = {
      sidebar: document.getElementById('sidebar'),
      btnMenu: document.getElementById('btnMenu'),
      sidebarClose: document.getElementById('sidebarClose'),
      btnNewChat: document.getElementById('btnNewChat'),
      historyList: document.getElementById('historyList'),
      btnSettings: document.getElementById('btnSettings'),
      settingsModal: document.getElementById('settingsModal'),
      settingsClose: document.getElementById('settingsClose'),
      settingsSave: document.getElementById('settingsSave'),
      apiBase: document.getElementById('apiBase'),
      includeAnalysis: document.getElementById('includeAnalysis'),
      chatTitle: document.getElementById('chatTitle'),
      messagesContainer: document.getElementById('messagesContainer'),
      messages: document.getElementById('messages'),
      welcome: document.getElementById('welcome'),
      messageInput: document.getElementById('messageInput'),
      btnSend: document.getElementById('btnSend'),
    };

    Chat.init(this.el.messages, this.el.messagesContainer, this.el.welcome);
  },

  _bindEvents() {
    this.el.btnNewChat.addEventListener('click', () => this.newChat());
    this.el.btnSend.addEventListener('click', () => this.sendMessage());
    this.el.btnSettings.addEventListener('click', () => this.openSettings());
    this.el.settingsClose.addEventListener('click', () => this.closeSettings());
    this.el.settingsSave.addEventListener('click', () => this.saveSettings());
    this.el.settingsModal.addEventListener('click', (e) => {
      if (e.target === this.el.settingsModal) this.closeSettings();
    });

    this.el.btnMenu.addEventListener('click', () => this.el.sidebar.classList.add('open'));
    this.el.sidebarClose.addEventListener('click', () => this.el.sidebar.classList.remove('open'));

    this.el.messageInput.addEventListener('input', () => {
      this._autoResize();
      this.el.btnSend.disabled = !this.el.messageInput.value.trim() || this.isSending;
    });

    this.el.messageInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!this.el.btnSend.disabled) this.sendMessage();
      }
    });
  },

  _autoResize() {
    const ta = this.el.messageInput;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  },

  _loadOrCreateSession() {
    const sessions = Storage.getSessions();
    if (sessions.length) {
      this._switchSession(sessions[0].id);
    } else {
      this.newChat();
    }
  },

  newChat() {
    this.currentSession = Storage.createSession();
    Storage.upsertSession(this.currentSession);
    this.el.chatTitle.textContent = '新对话';
    Chat.clear();
    this._renderHistory();
    this.el.sidebar.classList.remove('open');
    this.el.messageInput.focus();
  },

  _switchSession(id) {
    const session = Storage.getSession(id);
    if (!session) return;
    this.currentSession = session;
    this.el.chatTitle.textContent = session.title;
    Chat.renderSessionMessages(session.messages);
    this._renderHistory();
    this.el.sidebar.classList.remove('open');
  },

  _renderHistory() {
    const sessions = Storage.getSessions();
    this.el.historyList.innerHTML = '';

    sessions.forEach((s) => {
      const li = document.createElement('li');
      li.className = 'history-item' + (this.currentSession?.id === s.id ? ' active' : '');
      li.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        </svg>
        <span>${this._escapeHtml(s.title)}</span>`;
      li.addEventListener('click', () => this._switchSession(s.id));
      this.el.historyList.appendChild(li);
    });
  },

  async sendMessage() {
    const text = this.el.messageInput.value.trim();
    if (!text || this.isSending) return;

    this.isSending = true;
    this.el.btnSend.disabled = true;
    this.el.messageInput.value = '';
    this._autoResize();

    this.currentSession.messages.push({ role: 'user', content: text });

    if (this.currentSession.title === '新对话') {
      const parsed = API.parseInput(text);
      this.currentSession.title = parsed
        ? parsed.question.slice(0, 30) + (parsed.question.length > 30 ? '…' : '')
        : text.slice(0, 30) + (text.length > 30 ? '…' : '');
      this.el.chatTitle.textContent = this.currentSession.title;
    }

    Chat.appendUserMessage(text);
    Chat.appendLoading();

    try {
      const parsed = API.parseInput(text);
      if (!parsed) {
        throw new Error(
          '请按以下格式输入：\n题目：你的题目\n作答：你的解答'
        );
      }

      const data = await API.diagnose(parsed.question, parsed.studentSolution, this.settings);
      const reply = API.formatDiagnosisResponse(data);

      Chat.removeLoading();
      Chat.appendAIMessage(reply);

      this.currentSession.messages.push({ role: 'ai', content: reply });
    } catch (err) {
      Chat.removeLoading();
      Chat.appendAIMessage(err.message || '请求失败，请稍后重试', true);
      this.currentSession.messages.push({ role: 'ai', content: err.message, isError: true });
    }

    Storage.upsertSession(this.currentSession);
    this._renderHistory();
    this.isSending = false;
    this.el.btnSend.disabled = !this.el.messageInput.value.trim();
  },

  openSettings() {
    this.el.apiBase.value = this.settings.apiBase;
    this.el.includeAnalysis.checked = this.settings.includeAnalysis;
    this.el.settingsModal.hidden = false;
  },

  closeSettings() {
    this.el.settingsModal.hidden = true;
  },

  saveSettings() {
    this.settings = {
      apiBase: this.el.apiBase.value.trim().replace(/\/$/, ''),
      includeAnalysis: this.el.includeAnalysis.checked,
    };
    Storage.saveSettings(this.settings);
    this.closeSettings();
  },

  _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
