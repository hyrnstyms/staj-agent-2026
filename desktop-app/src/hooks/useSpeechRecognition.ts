// src/hooks/useSpeechRecognition.ts
// Tarayıcı yerleşik Web Speech API ile anında ses tanıma
// Chrome, Edge, Safari destekler — ek paket gerektirmez

import { useState, useRef, useCallback } from "react";

export type SpeechState = "idle" | "listening" | "error";

interface UseSpeechReturn {
  state: SpeechState;
  transcript: string;
  startListening: () => void;
  stopListening: () => string;
  error: string | null;
}

// Web Speech API tip tanımları
interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

export function useSpeechRecognition(): UseSpeechReturn {
  const [state, setState] = useState<SpeechState>("idle");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);
  const transcriptRef = useRef("");

  const startListening = useCallback(() => {
    setError(null);
    setTranscript("");
    transcriptRef.current = "";

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError("Bu tarayıcı ses tanımayı desteklemiyor. Chrome veya Edge kullanın.");
      setState("error");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "tr-TR";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
      setState("listening");
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalText = "";
      let interimText = "";

      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }

      const full = finalText || interimText;
      transcriptRef.current = full;
      setTranscript(full);
    };

    recognition.onerror = (event: any) => {
      if (event.error === "not-allowed") {
        setError("Mikrofon izni verilmedi. Tarayıcı ayarlarından izin verin.");
      } else if (event.error !== "aborted") {
        setError(`Ses tanıma hatası: ${event.error}`);
      }
      setState("error");
    };

    recognition.onend = () => {
      setState("idle");
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, []);

  const stopListening = useCallback((): string => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setState("idle");
    return transcriptRef.current;
  }, []);

  return { state, transcript, startListening, stopListening, error };
}

// TTS — Tarayıcı yerleşik metin okuma
export function speakText(text: string, lang: string = "tr-TR"): Promise<void> {
  return new Promise((resolve) => {
    if (!window.speechSynthesis) {
      resolve();
      return;
    }

    // Önceki konuşmayı durdur
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();

    window.speechSynthesis.speak(utterance);
  });
}
