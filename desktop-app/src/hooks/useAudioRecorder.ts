// src/hooks/useAudioRecorder.ts
// Mikrofon kaydı — MediaRecorder API (WebM/Opus) + backend /upload

import { useState, useRef, useCallback } from "react";
import { useChatStore } from "../store/chatStore";
import type { UploadResponse } from "../types";

// ─────────────────────────────────────────────────────────────────────────────

export type RecordingState = "idle" | "recording" | "uploading" | "error";

interface UseAudioRecorderReturn {
  recordingState: RecordingState;
  /** Kaydı başlat */
  startRecording: () => Promise<void>;
  /** Kaydı durdur ve /upload'a gönder; transkripti döner */
  stopRecording: () => Promise<string | null>;
  error: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [error, setError]                   = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef        = useRef<Blob[]>([]);
  const { settings }     = useChatStore();

  // ─── Kaydı başlat ─────────────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Tarayıcının desteklediği WebM/Opus formatını seç
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/ogg;codecs=opus";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start(250); // Her 250ms'de chunk al
      setRecordingState("recording");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Mikrofona erişilemiyor";
      setError(msg);
      setRecordingState("error");
    }
  }, []);

  // ─── Kaydı durdur ve yükle ────────────────────────────────────────────────
  const stopRecording = useCallback((): Promise<string | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(null);
        return;
      }

      recorder.onstop = async () => {
        // Ses stream'ini durdur
        recorder.stream.getTracks().forEach((t) => t.stop());

        const mimeType = recorder.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });

        // Boyut kontrolü — istemci tarafında ön kontrol (10MB)
        const MAX_AUDIO_BYTES = 10 * 1024 * 1024;
        if (blob.size > MAX_AUDIO_BYTES) {
          setError("Ses kaydı 10MB sınırını aştı. Lütfen daha kısa bir kayıt yapın.");
          setRecordingState("error");
          resolve(null);
          return;
        }

        setRecordingState("uploading");

        // FormData ile /upload endpoint'ine gönder
        const form = new FormData();
        const ext  = mimeType.includes("ogg") ? ".ogg" : ".webm";
        form.append("file", blob, `recording${ext}`);

        try {
          const res = await fetch(
            `${settings.backendUrl}/upload`,
            {
              method: "POST",
              headers: { "X-API-Key": settings.apiKey },
              body: form,
            }
          );

          if (!res.ok) {
            const detail = await res.text();
            throw new Error(`Upload hatası (${res.status}): ${detail}`);
          }

          const data: UploadResponse = await res.json();

          if (data.success && data.result) {
            setRecordingState("idle");
            resolve(data.result); // STT transkripti
          } else {
            setError(data.message || "STT başarısız");
            setRecordingState("error");
            resolve(null);
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Upload başarısız";
          setError(msg);
          setRecordingState("error");
          resolve(null);
        }
      };

      recorder.stop();
    });
  }, [settings]);

  return { recordingState, startRecording, stopRecording, error };
}
