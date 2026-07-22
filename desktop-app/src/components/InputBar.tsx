// src/components/InputBar.tsx
// Mesaj girişi + mikrofon + dosya/görsel yükleme araç çubuğu

import { useState, useRef, useCallback } from "react";
import { useChatStore } from "../store/chatStore";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import type { UploadResponse, Message } from "../types";

interface Props {
  onSend: (message: string) => void;
}

export function InputBar({ onSend }: Props) {
  const [text, setText]             = useState("");
  const fileInputRef                = useRef<HTMLInputElement>(null);
  const textareaRef                 = useRef<HTMLTextAreaElement>(null);

  const { isStreaming, settings, addMessage } = useChatStore();
  const { recordingState, startRecording, stopRecording, error: recError } = useAudioRecorder();

  const isRecording = recordingState === "recording";
  const isUploading = recordingState === "uploading";
  const canSend     = !isStreaming && !isRecording && !isUploading;

  // ─── Metin gönder ─────────────────────────────────────────────────────────
  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || !canSend) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, canSend, onSend]);

  // Enter = gönder, Shift+Enter = yeni satır
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Textarea auto-resize
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 150)}px`;
  };

  // ─── Mikrofon ─────────────────────────────────────────────────────────────
  const handleMicClick = async () => {
    if (isRecording) {
      const transcript = await stopRecording();
      if (transcript) {
        setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
        textareaRef.current?.focus();
      }
    } else {
      await startRecording();
    }
  };

  // ─── Dosya/Görsel Yükleme ─────────────────────────────────────────────────
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // İstemci boyut kontrolü
    const isImage = file.type.startsWith("image/");
    const maxBytes = isImage ? 5 * 1024 * 1024 : 10 * 1024 * 1024;
    if (file.size > maxBytes) {
      addMessage({
        id:        crypto.randomUUID(),
        role:      "system",
        content:   `❌ Dosya çok büyük (max ${isImage ? "5MB" : "10MB"})`,
        status:    "error",
        timestamp: new Date(),
      });
      return;
    }

    // Yükleme sistemi mesajı
    const uploadingMsg: Message = {
      id:        crypto.randomUUID(),
      role:      "system",
      content:   `📎 "${file.name}" yükleniyor…`,
      status:    "sending",
      timestamp: new Date(),
    };
    addMessage(uploadingMsg);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${settings.backendUrl}/upload`, {
        method:  "POST",
        headers: { "X-API-Key": settings.apiKey },
        body:    form,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: UploadResponse = await res.json();

      if (data.success && data.result) {
        // Upload sonucunu metin alanına ekle
        const prefix = isImage ? "🖼️ Görsel açıklaması: " : "🎙️ Transkript: ";
        setText((prev) => (prev ? `${prev}\n${prefix}${data.result}` : `${prefix}${data.result}`));
        addMessage({
          id:        crypto.randomUUID(),
          role:      "system",
          content:   `✅ ${isImage ? "Görsel analiz edildi" : "Ses transkript edildi"}`,
          status:    "done",
          timestamp: new Date(),
        });
      } else {
        addMessage({
          id:        crypto.randomUUID(),
          role:      "system",
          content:   `❌ ${data.message || "Yükleme başarısız"}`,
          status:    "error",
          timestamp: new Date(),
        });
      }
    } catch (err) {
      addMessage({
        id:        crypto.randomUUID(),
        role:      "system",
        content:   `❌ Yükleme hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
        status:    "error",
        timestamp: new Date(),
      });
    }

    // Input'u sıfırla
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Mikrofon durumuna göre ikon/ipucu
  const micLabel  = isRecording ? "⏹️" : isUploading ? "⏳" : "🎤";
  const micTitle  = isRecording ? "Kaydı Durdur" : "Sesli Giriş";

  return (
    <div className="input-bar">
      {/* Hata bildirimi (kayıt hatası) */}
      {recError && (
        <div style={{ fontSize: 11, color: "var(--danger)", marginBottom: 6, paddingLeft: 4 }}>
          ⚠️ {recError}
        </div>
      )}

      <div className="input-row">
        {/* Gizli dosya input'u */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif,audio/webm,audio/ogg,audio/wav,audio/mpeg"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />

        {/* Dosya/Görsel ekleme */}
        <button
          className="btn btn-icon"
          title="Dosya veya görsel ekle"
          onClick={() => fileInputRef.current?.click()}
          disabled={!canSend}
          style={{ flexShrink: 0 }}
        >
          📎
        </button>

        {/* Metin alanı */}
        <textarea
          ref={textareaRef}
          className="input-textarea"
          rows={1}
          placeholder={
            isRecording  ? "Dinleniyor… kaydı durdurmak için 🎤'ya tıkla" :
            isUploading  ? "Yükleniyor…" :
            isStreaming  ? "Asistan yazıyor…" :
            "Bir şey sor… (Enter = gönder, Shift+Enter = yeni satır)"
          }
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={!canSend}
        />

        <div className="input-actions">
          {/* Mikrofon */}
          <button
            className={`btn btn-icon ${isRecording ? "recording" : ""}`}
            title={micTitle}
            onClick={handleMicClick}
            disabled={isUploading || isStreaming}
            style={isRecording ? { background: "var(--danger)", color: "#fff" } : undefined}
          >
            {micLabel}
          </button>

          {/* Gönder */}
          <button
            className="btn btn-send"
            title="Gönder (Enter)"
            onClick={handleSend}
            disabled={!canSend || !text.trim()}
          >
            ↑
          </button>
        </div>
      </div>

      <div className="input-hint">
        Enter ile gönder · Shift+Enter yeni satır · 📎 ile dosya/görsel ekle · 🎤 sesli giriş
      </div>
    </div>
  );
}
