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
      <div className="flex w-full justify-center mb-4">
        <div className="px-3 py-1 bg-brand-light-gray/50 text-brand-gray text-xs rounded-full border border-brand-light-gray/60">
          {content}
        </div>
      </div>
    );
  }

  const isUser = role === "user";

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-4 group`}>
      <div 
        className={`max-w-[85%] px-5 py-3 shadow-sm relative ${
          isUser 
            ? "rounded-2xl rounded-br-sm bg-brand-indigo text-white shadow-soft" 
            : `rounded-2xl rounded-bl-sm bg-white border border-brand-light-gray text-brand-dark-gray ${isError ? 'border-status-red/50 bg-status-red/5' : ''}`
        }`}
      >
        {/* Tool chip (sadece asistan mesajlarında) */}
        {!isUser && tool_call && (
          <div className="mb-2">
            <ToolCallChip toolCall={tool_call} />
          </div>
        )}

        {/* İçerik */}
        {!isUser ? (
          <div className={`prose prose-sm prose-slate max-w-none ${isStreaming ? "animate-pulse" : ""}`}>
            {content ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            ) : (
              // Boş içerik = sadece cursor göster (streaming başlıyor)
              isStreaming ? null : <span className="text-brand-gray">…</span>
            )}
          </div>
        ) : (
          // Kullanıcı mesajı — düz metin (markdown yorumlanmaz)
          <p className="whitespace-pre-wrap leading-relaxed">{content}</p>
        )}

        {/* Zaman damgası */}
        <div className={`text-[10px] mt-2 font-medium ${isUser ? 'text-indigo-100' : 'text-brand-gray'}`}>
          {formatTime(timestamp)}
          {isStreaming && <span className="ml-2 text-brand-accent">● yazıyor…</span>}
          {isError     && <span className="ml-2 text-status-red">✕ hata</span>}
          {status === "pending_approval" && (
            <span className="ml-2 text-status-yellow">⏳ onay bekleniyor</span>
          )}
        </div>
      </div>
    </div>
  );
}
