import { useState, useEffect, useRef, useCallback } from "react";
import { useChatStore } from "../store/chatStore";

export type WakeWordState = "idle" | "listening" | "wake_detected" | "command_listening" | "error";

// Singleton state — tüm bileşenler aynı state'i paylaşır
let _globalEnabled = false;
let _globalState: WakeWordState = "idle";
let _globalWs: WebSocket | null = null;
let _listeners: Set<() => void> = new Set();

function notifyAll() {
  _listeners.forEach(fn => fn());
}

export function useWakeWord() {
  const { settings } = useChatStore();
  const [, forceUpdate] = useState(0);

  // Register this component to re-render on global state changes
  useEffect(() => {
    const listener = () => forceUpdate(n => n + 1);
    _listeners.add(listener);
    return () => { _listeners.delete(listener); };
  }, []);

  // WebSocket bağlantısı — sadece bir kez oluşturulur
  useEffect(() => {
    if (_globalWs && _globalWs.readyState <= 1) return; // Zaten bağlı

    // İlk durumu çek
    fetch(`${settings.backendUrl}/voice/status`, { headers: { "X-API-Key": settings.apiKey } })
      .then(r => r.json())
      .then(d => {
         _globalEnabled = d.running;
         _globalState = d.state;
         notifyAll();
      }).catch(() => {});

    // WebSocket
    let wsUrl = settings.backendUrl.replace("http://", "ws://").replace("https://", "wss://");
    if (wsUrl.endsWith("/")) wsUrl = wsUrl.slice(0, -1);

    const ws = new WebSocket(`${wsUrl}/voice/ws`);
    _globalWs = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const { addMessage } = useChatStore.getState();

        if (data.type === "state_change") {
          _globalState = data.state;
        } else if (data.type === "wake_detected") {
          _globalState = "wake_detected";
        } else if (data.type === "connected") {
          _globalEnabled = data.status?.running ?? false;
          _globalState = data.status?.state ?? "idle";
        } else if (data.type === "stopped") {
          _globalEnabled = false;
          _globalState = "idle";
        } else if (data.type === "command") {
          addMessage({
            id: crypto.randomUUID(),
            role: "user",
            content: data.text,
            status: "done",
            timestamp: new Date()
          });
        } else if (data.type === "response") {
          addMessage({
            id: crypto.randomUUID(),
            role: "assistant",
            content: data.text,
            status: "done",
            timestamp: new Date(),
          });
        }
        notifyAll();
      } catch (err) {
        console.error("Voice WS error", err);
      }
    };

    ws.onerror = () => {
      console.warn("Voice WebSocket bağlantı hatası (backend /voice/ws erişilemez olabilir)");
    };

    ws.onclose = () => {
      _globalWs = null;
    };

    return () => {
      // Cleanup sadece son component unmount olduğunda
      if (_listeners.size <= 1) {
        ws.close();
        _globalWs = null;
      }
    };
  }, [settings.backendUrl, settings.apiKey]);

  const start = useCallback(async () => {
    try {
      const res = await fetch(`${settings.backendUrl}/voice/start`, {
        method: "POST",
        headers: { "X-API-Key": settings.apiKey }
      });
      const data = await res.json();
      if (data.success) {
        _globalEnabled = true;
        _globalState = data.state || "listening";
        notifyAll();
      }
    } catch (e) {
      console.error("Voice start error:", e);
    }
  }, [settings]);

  const stop = useCallback(async () => {
    try {
      await fetch(`${settings.backendUrl}/voice/stop`, {
        method: "POST",
        headers: { "X-API-Key": settings.apiKey }
      });
      _globalEnabled = false;
      _globalState = "idle";
      notifyAll();
    } catch (e) {
      console.error("Voice stop error:", e);
    }
  }, [settings]);

  const toggle = useCallback(() => {
    if (_globalEnabled) stop();
    else start();
  }, [start, stop]);

  return { 
    enabled: _globalEnabled, 
    state: _globalState, 
    toggle 
  };
}
