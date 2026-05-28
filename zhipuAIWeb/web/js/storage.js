/**
 * localStorage 会话管理
 */
const Storage = {
  KEY: 'zhipu_diagnosis_sessions',
  SETTINGS_KEY: 'zhipu_diagnosis_settings',

  getSettings() {
    try {
      const raw = localStorage.getItem(this.SETTINGS_KEY);
      return raw ? JSON.parse(raw) : {
        apiBase: `${window.location.origin}/api/v1`,
        includeAnalysis: false,
      };
    } catch {
      return { apiBase: 'http://127.0.0.1:8000/api/v1', includeAnalysis: false };
    }
  },

  saveSettings(settings) {
    localStorage.setItem(this.SETTINGS_KEY, JSON.stringify(settings));
  },

  getSessions() {
    try {
      const raw = localStorage.getItem(this.KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  },

  saveSessions(sessions) {
    localStorage.setItem(this.KEY, JSON.stringify(sessions));
  },

  createSession(title = '新对话') {
    return {
      id: `session_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      title,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
  },

  upsertSession(session) {
    const sessions = this.getSessions();
    const idx = sessions.findIndex((s) => s.id === session.id);
    session.updatedAt = Date.now();
    if (idx >= 0) {
      sessions[idx] = session;
    } else {
      sessions.unshift(session);
    }
    this.saveSessions(sessions);
    return sessions;
  },

  deleteSession(id) {
    const sessions = this.getSessions().filter((s) => s.id !== id);
    this.saveSessions(sessions);
    return sessions;
  },

  getSession(id) {
    return this.getSessions().find((s) => s.id === id) || null;
  },
};
