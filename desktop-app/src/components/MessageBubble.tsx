// src/components/MessageBubble.tsx
// Tek mesaj balonu — markdown render + tool chip + durum göstergesi

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../types";
import { ToolCallChip } from "./ToolCallChip";

interface Props {
  message: Message;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ message }: Props) {
  const { role, content, status, timestamp, tool_call } = message;

  const isStreaming = status === "streaming";
  const isError     = status === "error";

  // Sistem mesajları — kompakt pill
  if (role === "system") {
    return (
      <div className="message-row system">
        <div className="message-bubble system">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className={`message-row ${role}`}>
      <div className={`message-bubble ${role} ${isError ? "error" : ""}`}>
        {/* Tool chip (sadece asistan mesajlarında) */}
        {role === "assistant" && tool_call && (
          <ToolCallChip toolCall={tool_call} />
        )}

        {/* İçerik */}
        {role === "assistant" ? (
          <div className={`md-content ${isStreaming ? "streaming-cursor" : ""}`}>
            {content ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            ) : (
              // Boş içerik = sadece cursor göster (streaming başlıyor)
              isStreaming ? null : <span style={{ color: "var(--text-dim)" }}>…</span>
            )}
          </div>
        ) : (
          // Kullanıcı mesajı — düz metin (markdown yorumlanmaz)
          <p style={{ whiteSpace: "pre-wrap" }}>{content}</p>
        )}

        {/* Zaman damgası */}
        <div className="message-meta">
          <span>{formatTime(timestamp)}</span>
          {isStreaming && <span style={{ color: "var(--accent)", fontSize: 10 }}>● yazıyor…</span>}
          {isError     && <span style={{ color: "var(--danger)", fontSize: 10 }}>✕ hata</span>}
          {status === "pending_approval" && (
            <span style={{ color: "var(--warning)", fontSize: 10 }}>⏳ onay bekleniyor</span>
          )}
        </div>
      </div>
    </div>
  );
}
