import { useState, useEffect, useRef } from "react";
import { useChatStore } from "../store/chatStore";

export type WakeWordState = "idle" | "listening" | "wake_detected" | "command_listening" | "error";

export function useWakeWord() {
  const [state, setState] = useState<WakeWordState>("idle");
  const [enabled, setEnabled] = useState(false);
  const { settings } = useChatStore();
  const wsRef = useRef<WebSocket | null>(null);

  const start = async () => {
    try {
      const res = await fetch(`${settings.backendUrl}/voice/start`, {
        method: "POST",
        headers: { "X-API-Key": settings.apiKey }
      });
      if (res.ok) {
        setEnabled(true);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const stop = async () => {
    try {
      await fetch(`${settings.backendUrl}/voice/stop`, {
        method: "POST",
        headers: { "X-API-Key": settings.apiKey }
      });
      setEnabled(false);
      setState("idle");
    } catch (e) {
      console.error(e);
    }
  };

  const toggle = () => {
    if (enabled) stop();
    else start();
  };

  useEffect(() => {
    // İlk durumu çek
    fetch(`${settings.backendUrl}/voice/status`, { headers: { "X-API-Key": settings.apiKey } })
      .then(r => r.json())
      .then(d => {
         setEnabled(d.running);
         setState(d.state);
      }).catch(() => {});

    // WebSocket ile canlı state takibi
    let wsUrl = settings.backendUrl.replace("http://", "ws://").replace("https://", "wss://");
    if (wsUrl.endsWith("/")) wsUrl = wsUrl.slice(0, -1);
    
    const ws = new WebSocket(`${wsUrl}/voice/ws`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const { addMessage } = useChatStore.getState();

        if (data.type === "state_change") {
          setState(data.state);
        } else if (data.type === "wake_detected") {
          setState("wake_detected");
        } else if (data.type === "connected") {
          setEnabled(data.status.running);
          setState(data.status.state);
        } else if (data.type === "stopped") {
          setEnabled(false);
          setState("idle");
        } else if (data.type === "command") {
          // Komut alındığında kullanıcı mesajı olarak ekle
          addMessage({
            id: crypto.randomUUID(),
            role: "user",
            content: data.text,
            status: "done",
            timestamp: new Date()
          });
        } else if (data.type === "response") {
          // Asistan yanıtını ekle
          addMessage({
            id: crypto.randomUUID(),
            role: "assistant",
            content: data.text,
            status: "done",
            timestamp: new Date(),
            audioFile: data.audio_file, // Frontend bunu destekliyorsa
            toolName: data.tool_name
          });
          
          if (data.audio_file) {
            // TODO: İsterseniz doğrudan HTML5 audio ile çalabilirsiniz
            // Örnek: new Audio(file_url).play(); ama yerel dosya yolu dönebilir, 
            // static file serve ayarlamak gerekebilir.
          }
        }
      } catch (err) {
        console.error("WS Parse error", err);
      }
    };

    return () => {
      ws.close();
    };
  }, [settings.backendUrl, settings.apiKey]);

  return { enabled, state, toggle };
}
