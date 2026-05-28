/**
 * 聊天 UI 渲染与管理
 */
const Chat = {
  messagesEl: null,
  containerEl: null,
  welcomeEl: null,

  init(messagesEl, containerEl, welcomeEl) {
    this.messagesEl = messagesEl;
    this.containerEl = containerEl;
    this.welcomeEl = welcomeEl;
  },

  hideWelcome() {
    if (this.welcomeEl) this.welcomeEl.style.display = 'none';
  },

  showWelcome() {
    if (this.welcomeEl) this.welcomeEl.style.display = '';
  },

  clear() {
    this.messagesEl.querySelectorAll('.message').forEach((el) => el.remove());
    this.showWelcome();
  },

  scrollToBottom() {
    requestAnimationFrame(() => {
      this.containerEl.scrollTop = this.containerEl.scrollHeight;
    });
  },

  appendUserMessage(content) {
    this.hideWelcome();
    const el = this._createMessage('user', '你', content, false);
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  },

  appendAIMessage(content, isError = false) {
    this.hideWelcome();
    const el = this._createMessage('ai', 'AI', content, isError);
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  },

  appendLoading() {
    this.hideWelcome();
    const el = document.createElement('div');
    el.className = 'message ai loading';
    el.id = 'loadingMessage';
    el.innerHTML = `
      <div class="message-avatar">AI</div>
      <div class="message-body">
        正在思考中...
        <div class="typing-dots"><span></span><span></span><span></span></div>
      </div>`;
    this.messagesEl.appendChild(el);
    this.scrollToBottom();
    return el;
  },

  removeLoading() {
    const el = document.getElementById('loadingMessage');
    if (el) el.remove();
  },

  renderSessionMessages(messages) {
    this.clear();
    if (!messages.length) return;

    messages.forEach((msg) => {
      if (msg.role === 'user') {
        this.appendUserMessage(msg.content);
      } else {
        this.appendAIMessage(msg.content, msg.isError);
      }
    });
  },

  _createMessage(role, avatarLabel, content, isError) {
    const el = document.createElement('div');
    el.className = `message ${role}${isError ? ' error' : ''}`;

    const bodyContent = role === 'ai' && !isError
      ? Markdown.render(content)
      : this._escapeHtml(content).replace(/\n/g, '<br>');

    el.innerHTML = `
      <div class="message-avatar">${avatarLabel}</div>
      <div class="message-body">${bodyContent}</div>`;
    return el;
  },

  _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },
};
