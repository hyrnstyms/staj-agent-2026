// src/components/SettingsPanel.tsx
// Ayarlar paneli — API Key (sadece Faz 1 backend auth), backend URL, TTS toggle

import { useState } from "react";
import { useChatStore } from "../store/chatStore";
import { WakeWordToggle } from "./WakeWordToggle";

export function SettingsPanel() {
  const { settings, setSettings, setSettingsOpen } = useChatStore();
  const [local, setLocal] = useState({ ...settings });
  const [saved, setSaved]  = useState(false);

  const handleSave = async () => {
    await setSettings(local);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="settings-panel">
      {/* Başlık */}
      <div className="settings-header">
        <span className="settings-title">⚙️ Ayarlar</span>
        <button
          className="btn btn-icon"
          onClick={() => setSettingsOpen(false)}
          title="Kapat"
        >
          ✕
        </button>
      </div>

      {/* Gövde */}
      <div className="settings-body">

        {/* Bağlantı ayarları */}
        <div className="settings-section">
          <div className="settings-section-title">Bağlantı</div>

          <div className="form-group">
            <label className="form-label">Backend URL</label>
            <input
              id="setting-backend-url"
              className="form-input"
              type="text"
              value={local.backendUrl}
              onChange={(e) => setLocal({ ...local, backendUrl: e.target.value })}
              placeholder="http://localhost:8000"
            />
            <span className="form-hint">FastAPI backend adresi</span>
          </div>

          <div className="form-group">
            <label className="form-label">API Key</label>
            <input
              id="setting-api-key"
              className="form-input monospace"
              type="password"
              value={local.apiKey}
              onChange={(e) => setLocal({ ...local, apiKey: e.target.value })}
              placeholder="dev-api-key-change-in-production"
            />
            <span className="form-hint">
              ℹ️ Yalnızca backend'e bağlanmak için kullanılan kimlik doğrulama
              anahtarı (Faz 1 geçici auth). GitHub/Gmail gibi hassas token'lar
              backend <code>.env</code> dosyasında tutulur, buraya girilmez.
            </span>
          </div>
        </div>

        {/* Ses ayarları */}
        <div className="settings-section">
          <div className="settings-section-title">Ses</div>

          <div className="toggle-row">
            <div className="form-group" style={{ gap: 3 }}>
              <label className="form-label">TTS (Sesli Cevap)</label>
              <span className="form-hint">Asistanın cevaplarını sesli oku</span>
            </div>
            <label className="toggle">
              <input
                id="setting-tts-enabled"
                type="checkbox"
                checked={local.ttsEnabled}
                onChange={(e) => setLocal({ ...local, ttsEnabled: e.target.checked })}
              />
              <span className="toggle-track" />
            </label>
          </div>

          <div style={{ marginTop: 8 }}>
            <WakeWordToggle />
          </div>
        </div>

        {/* Tehlikeli bölge */}
        <div className="settings-section">
          <div className="settings-section-title">Oturum</div>
          <button
            className="btn btn-ghost"
            style={{ alignSelf: "flex-start", fontSize: 12 }}
            onClick={() => {
              useChatStore.getState().clearMessages();
              setSettingsOpen(false);
            }}
          >
            🗑️ Konuşmayı Temizle
          </button>
        </div>

      </div>

      {/* Footer — kaydet */}
      <div className="settings-footer">
        <button
          className="btn btn-primary"
          style={{ width: "100%" }}
          onClick={handleSave}
        >
          {saved ? "✓ Kaydedildi" : "Kaydet"}
        </button>
        <div className="settings-version">Asistan v0.7.0 — Faz 7</div>
      </div>
    </div>
  );
}
