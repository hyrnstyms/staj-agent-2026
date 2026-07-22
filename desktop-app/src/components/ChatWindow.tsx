// src/components/ChatWindow.tsx
// Mesaj listesi — otomatik scroll, boş durum ekranı

import { useEffect, useRef } from "react";
import { useChatStore } from "../store/chatStore";
import { MessageBubble } from "./MessageBubble";

// Asistan SVG logosu
function AsistanLogo({ size = 48, dimmed = false }: { size?: number; dimmed?: boolean }) {
  return (
    <svg
      className={dimmed ? "chat-empty-logo" : "header-logo"}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Beyin / dalga ikonu */}
      <circle cx="24" cy="24" r="22" fill="rgba(0,180,216,0.1)" stroke="#00b4d8" strokeWidth="1.5" />
      {/* Sinyal dalgaları */}
      <path d="M14 24 C14 18 18 14 24 14 C30 14 34 18 34 24" stroke="#00b4d8" strokeWidth="2" strokeLinecap="round" fill="none" />
      <path d="M10 24 C10 15 16 10 24 10 C32 10 38 15 38 24" stroke="#00b4d8" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.5" />
      {/* Merkez nokta */}
      <circle cx="24" cy="24" r="3.5" fill="#00b4d8" />
      {/* Alt yay */}
      <path d="M18 28 C20 32 24 34 24 34 C24 34 28 32 30 28" stroke="#00b4d8" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.7" />
    </svg>
  );
}

export function ChatWindow() {
  const messages     = useChatStore((s) => s.messages);
  const bottomRef    = useRef<HTMLDivElement>(null);

  // Yeni mesajda otomatik scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="chat-window">
        <div className="chat-empty">
          <AsistanLogo size={64} dimmed />
          <h1 className="chat-empty-title">Merhaba, ben Asistan</h1>
          <p className="chat-empty-sub">
            Dosyalar, veritabanı, kod, mail, takvim ve daha fazlası için
            buradayım. Ne yapmamı istersin?
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-window">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} style={{ height: 8 }} />
    </div>
  );
}

export { AsistanLogo };
