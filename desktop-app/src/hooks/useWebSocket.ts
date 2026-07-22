// src/hooks/useWebSocket.ts
// WebSocket bağlantı yönetimi — exponential backoff ile otomatik yeniden bağlanma

import { useEffect, useRef, useCallback } from "react";
import { useChatStore } from "../store/chatStore";
import type { WsEvent, PendingApproval } from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// Sabitler
// ─────────────────────────────────────────────────────────────────────────────

const RECONNECT_BASE_MS  = 1000;  // İlk bekleme süresi
const RECONNECT_MAX_MS   = 30000; // Maksimum bekleme süresi
const RECONNECT_FACTOR   = 2;     // Her denemede 2x artar

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export function useWebSocket() {
  const wsRef        = useRef<WebSocket | null>(null);
  const retryRef     = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef   = useRef(0);
  const mountedRef   = useRef(true);

  const {
    settings,
    sessionId,
    setSessionId,
    setConnected,
    setReconnecting,
    appendToLastAssistant,
    updateLastMessage,
    setPendingApproval,
    setStreaming,
  } = useChatStore();

  // ─── WebSocket bağlantısını aç ────────────────────────────────────────────
  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = settings.backendUrl
      .replace(/^http/, "ws")
      .replace(/\/$/, "");

    const sid = sessionId || crypto.randomUUID();
    const url = `${wsUrl}/ws/chat?session_id=${sid}&api_key=${encodeURIComponent(settings.apiKey)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      attemptRef.current = 0;
      setConnected(true);
    };

    ws.onmessage = (ev) => {
      if (!mountedRef.current) return;
      let data: WsEvent;
      try {
        data = JSON.parse(ev.data as string);
      } catch {
        return;
      }
      handleEvent(data, sid);
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnected(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [settings, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Exponential backoff reconnect ────────────────────────────────────────
  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    setReconnecting(true);

    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(RECONNECT_FACTOR, attemptRef.current),
      RECONNECT_MAX_MS
    );
    attemptRef.current += 1;

    retryRef.current = setTimeout(() => {
      if (mountedRef.current) connect();
    }, delay);
  }, [connect, setReconnecting]);

  // ─── WebSocket event işleyici ─────────────────────────────────────────────
  const handleEvent = useCallback(
    (data: WsEvent, sid: string) => {
      switch (data.type) {
        case "connected":
          setSessionId(data.session_id || sid);
          break;

        case "token":
          appendToLastAssistant(data.content);
          break;

        case "done":
          updateLastMessage({ status: "done" });
          setStreaming(false);
          break;

        case "approval": {
          const approval: PendingApproval = {
            approval_id: data.approval_id,
            tool_name:   data.tool_name,
            description: data.description,
          };
          setPendingApproval(approval);
          updateLastMessage({ status: "pending_approval", approval_id: data.approval_id });
          setStreaming(false);
          break;
        }

        case "error":
          updateLastMessage({ status: "error", content: `Hata: ${data.message}` });
          setStreaming(false);
          break;
      }
    },
    [appendToLastAssistant, setPendingApproval, setSessionId, setStreaming, updateLastMessage]
  );

  // ─── Mesaj gönder ─────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    (message: string, approvalId?: string) => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket bağlı değil");
        return false;
      }
      const payload: Record<string, string> = { message };
      if (approvalId) payload.approval_id = approvalId;
      wsRef.current.send(JSON.stringify(payload));
      return true;
    },
    []
  );

  // ─── Mount / unmount ───────────────────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { sendMessage };
}
