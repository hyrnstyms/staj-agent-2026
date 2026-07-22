// src/App.tsx
// Asistan — Ana uygulama bileşeni

import { useEffect, useCallback } from "react";
import { useChatStore } from "./store/chatStore";
import { useWebSocket }  from "./hooks/useWebSocket";
import { ChatWindow, AsistanLogo } from "./components/ChatWindow";
import { InputBar }      from "./components/InputBar";
import { ApprovalModal } from "./components/ApprovalModal";
import { SettingsPanel } from "./components/SettingsPanel";

// ─────────────────────────────────────────────────────────────────────────────
// Bağlantı durum göstergesi
// ─────────────────────────────────────────────────────────────────────────────
function ConnectionIndicator() {
  const connected    = useChatStore((s) => s.connected);
  const reconnecting = useChatStore((s) => s.reconnecting);

  const dotClass = connected ? "connected" : reconnecting ? "reconnecting" : "disconnected";
  const label    = connected ? "Bağlı" : reconnecting ? "Yeniden bağlanıyor…" : "Bağlantı yok";

  return (
    <div className="connection-indicator">
      <div className={`connection-dot ${dotClass}`} />
      <span>{label}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Ana uygulama
// ─────────────────────────────────────────────────────────────────────────────
function App() {
  const {
    settings,
    settingsOpen,
    setSettingsOpen,
    loadSettings,
    addMessage,
    updateLastMessage,
    setStreaming,
  } = useChatStore();

  const { sendMessage } = useWebSocket();

  // Uygulama başlangıcında ayarları yükle
  useEffect(() => {
    loadSettings();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Mesaj gönderme akışı ─────────────────────────────────────────────────
  const handleSend = useCallback(
    (text: string) => {
      // Kullanıcı mesajını listeye ekle
      addMessage({
        id:        crypto.randomUUID(),
        role:      "user",
        content:   text,
        status:    "done",
        timestamp: new Date(),
      });

      // Asistan için placeholder mesaj (streaming dolduracak)
      addMessage({
        id:        crypto.randomUUID(),
        role:      "assistant",
        content:   "",
        status:    "streaming",
        timestamp: new Date(),
      });

      setStreaming(true);

      const sent = sendMessage(text);
      if (!sent) {
        updateLastMessage({
          status:  "error",
          content: "WebSocket bağlı değil. Lütfen backend'in çalıştığından emin ol.",
        });
        setStreaming(false);
      }
    },
    [addMessage, sendMessage, setStreaming, updateLastMessage]
  );

  return (
    <div className="app-layout">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="app-header">
        <div className="header-brand">
          <AsistanLogo size={32} />
          <div>
            <div className="header-title">Asistan</div>
            <div className="header-subtitle">{settings.backendUrl}</div>
          </div>
        </div>

        <div className="header-actions">
          <ConnectionIndicator />

          {/* Ayarlar butonu */}
          <button
            id="btn-settings"
            className="btn btn-icon"
            title="Ayarlar"
            onClick={() => setSettingsOpen(!settingsOpen)}
          >
            ⚙️
          </button>
        </div>
      </header>

      {/* ── Chat alanı ─────────────────────────────────────────────────────── */}
      <ChatWindow />

      {/* ── Giriş çubuğu ───────────────────────────────────────────────────── */}
      <InputBar onSend={handleSend} />

      {/* ── Modallar ───────────────────────────────────────────────────────── */}
      <ApprovalModal />

      {/* ── Ayarlar paneli ─────────────────────────────────────────────────── */}
      {settingsOpen && <SettingsPanel />}
    </div>
  );
}

export default App;
