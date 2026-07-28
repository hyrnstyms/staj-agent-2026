import { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Volume2, VolumeX, ArrowLeft } from "lucide-react";
import { useSpeechRecognition, speakText } from "../hooks/useSpeechRecognition";
import { useChatStore } from "../store/chatStore";
import { Link } from "wouter";

interface VoiceMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

export function VoicePage() {
  const { settings } = useChatStore();
  const { state: speechState, transcript, startListening, stopListening, error } = useSpeechRecognition();
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [liveText, setLiveText] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Canlı transkript göster
  useEffect(() => {
    if (speechState === "listening") {
      setLiveText(transcript);
    }
  }, [transcript, speechState]);

  // Otomatik scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveText]);

  const handleMicClick = async () => {
    if (speechState === "listening") {
      const text = stopListening();
      setLiveText("");

      if (!text.trim()) return;

      // Kullanıcı mesajını ekle
      const userMsg: VoiceMessage = { id: crypto.randomUUID(), role: "user", text: text.trim() };
      setMessages(prev => [...prev, userMsg]);

      // Agent'a gönder
      setIsThinking(true);
      try {
        const res = await fetch(`${settings.backendUrl}/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": settings.apiKey,
          },
          body: JSON.stringify({ message: text.trim() }),
        });

        const data = await res.json();
        const reply = data.message || "Yanıt alınamadı.";

        const assistantMsg: VoiceMessage = { id: crypto.randomUUID(), role: "assistant", text: reply };
        setMessages(prev => [...prev, assistantMsg]);

        // TTS ile yanıtı oku
        if (ttsEnabled) {
          setIsSpeaking(true);
          await speakText(reply);
          setIsSpeaking(false);
        }
      } catch (err) {
        const errMsg: VoiceMessage = { id: crypto.randomUUID(), role: "assistant", text: "Bağlantı hatası. Backend çalışıyor mu?" };
        setMessages(prev => [...prev, errMsg]);
      } finally {
        setIsThinking(false);
      }
    } else {
      // Konuşma başlat
      if (isSpeaking) window.speechSynthesis.cancel();
      setIsSpeaking(false);
      startListening();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] animate-in fade-in duration-300">
      
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-brand-dark">Sesli Diyalog</h2>
          <p className="text-sm text-brand-gray">Mikrofona bas, konuş, bırak. Asistan sesli yanıt verir.</p>
        </div>
        <button
          onClick={() => setTtsEnabled(!ttsEnabled)}
          className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
            ttsEnabled ? "bg-brand-indigo/10 text-brand-indigo" : "bg-gray-100 text-gray-400"
          }`}
        >
          {ttsEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          {ttsEnabled ? "Sesli Yanıt Açık" : "Sesli Yanıt Kapalı"}
        </button>
      </div>

      {/* Mesaj listesi */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && !liveText && (
          <div className="flex flex-col items-center justify-center h-full text-brand-gray">
            <Mic size={48} className="mb-4 opacity-30" />
            <p className="text-lg font-medium text-brand-dark-gray">Konuşmaya Hazır</p>
            <p className="text-sm mt-1">Aşağıdaki mikrofon butonuna basarak başlayın</p>
          </div>
        )}

        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-brand-dark text-white rounded-br-md"
                  : "bg-white border border-brand-light-gray text-brand-dark rounded-bl-md shadow-sm"
              }`}
            >
              {msg.role === "assistant" && (
                <div className="text-[10px] text-brand-gray font-bold uppercase mb-1">Asistan</div>
              )}
              {msg.text}
            </div>
          </div>
        ))}

        {/* Canlı transkript */}
        {speechState === "listening" && liveText && (
          <div className="flex justify-end">
            <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-br-md bg-brand-dark/70 text-white/80 text-sm italic">
              {liveText}
              <span className="animate-pulse">|</span>
            </div>
          </div>
        )}

        {/* Düşünüyor göstergesi */}
        {isThinking && (
          <div className="flex justify-start">
            <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-white border border-brand-light-gray shadow-sm">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-brand-indigo animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 rounded-full bg-brand-indigo animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 rounded-full bg-brand-indigo animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-xs text-brand-gray">Düşünüyor...</span>
              </div>
            </div>
          </div>
        )}

        {/* Konuşuyor göstergesi */}
        {isSpeaking && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-brand-indigo/10 text-brand-indigo text-xs font-medium">
              <Volume2 size={14} className="animate-pulse" />
              Konuşuyor...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Hata mesajı */}
      {error && (
        <div className="mx-auto mb-2 px-4 py-2 bg-red-50 text-red-600 text-xs rounded-xl">
          {error}
        </div>
      )}

      {/* Büyük mikrofon butonu */}
      <div className="flex flex-col items-center gap-3 py-6">
        {/* Ses dalgası animasyonu */}
        {speechState === "listening" && (
          <div className="flex items-end gap-[3px] h-8 mb-2">
            {[...Array(16)].map((_, i) => (
              <div
                key={i}
                className="w-1 rounded-full bg-red-400"
                style={{
                  height: `${20 + Math.random() * 80}%`,
                  animation: `pulse ${0.5 + Math.random() * 0.5}s ease-in-out infinite`,
                  animationDelay: `${i * 50}ms`,
                }}
              />
            ))}
          </div>
        )}

        <button
          onClick={handleMicClick}
          disabled={isThinking}
          className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl ${
            speechState === "listening"
              ? "bg-red-500 text-white scale-110 shadow-red-300 animate-pulse"
              : isThinking
              ? "bg-gray-300 text-gray-500 cursor-wait"
              : "bg-brand-dark text-white hover:bg-brand-indigo hover:scale-105 shadow-brand-dark/30"
          }`}
        >
          {speechState === "listening" ? <MicOff size={32} /> : <Mic size={32} />}
        </button>

        <span className="text-xs text-brand-gray font-medium">
          {speechState === "listening"
            ? "Konuşun... Bitince butona basın"
            : isThinking
            ? "Yanıt bekleniyor..."
            : "Konuşmak için basın"}
        </span>
      </div>
    </div>
  );
}
