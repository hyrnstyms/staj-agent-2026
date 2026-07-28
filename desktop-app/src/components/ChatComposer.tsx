import { useState, useRef, KeyboardEvent, useEffect } from "react";
import { Send, Mic, MicOff, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useChatStore } from "../store/chatStore";
import { useWebSocket } from "../hooks/useWebSocket";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";

export function ChatComposer() {
  const { connected, isStreaming, addMessage, setStreaming, clearMessages, messages } = useChatStore();
  const { sendMessage } = useWebSocket();
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { state: speechState, transcript, startListening, stopListening, error: speechError } = useSpeechRecognition();

  // Ses tanıma sırasında canlı olarak input'a yaz
  useEffect(() => {
    if (speechState === "listening" && transcript) {
      setInput(transcript);
    }
  }, [transcript, speechState]);

  useEffect(() => {
    if (speechError) toast.error(speechError);
  }, [speechError]);

  const handleSend = () => {
    if (!input.trim() || !connected || isStreaming) return;
    
    addMessage({
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      status: "done",
      timestamp: new Date()
    });

    addMessage({
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      status: "streaming",
      timestamp: new Date()
    });

    setStreaming(true);
    sendMessage(input.trim());
    setInput("");
    if (inputRef.current) inputRef.current.style.height = 'auto';
  };

  const handleClear = () => {
    if (confirm("Tüm sohbet geçmişini silmek istediğinize emin misiniz?")) {
      clearMessages();
      toast.success("Sohbet temizlendi.");
    }
  };

  const handleMicClick = () => {
    if (speechState === "listening") {
      const text = stopListening();
      if (text.trim()) {
        setInput(text);
        // Otomatik gönder
        setTimeout(() => {
          const trimmed = text.trim();
          if (!trimmed || !connected || isStreaming) return;
          addMessage({ id: crypto.randomUUID(), role: "user", content: trimmed, status: "done", timestamp: new Date() });
          addMessage({ id: crypto.randomUUID(), role: "assistant", content: "", status: "streaming", timestamp: new Date() });
          setStreaming(true);
          sendMessage(trimmed);
          setInput("");
        }, 100);
      }
    } else {
      startListening();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const adjustHeight = () => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`;
    }
  };

  return (
    <div className="glass-panel p-2 flex flex-col gap-2 rounded-2xl">
      {/* Ses tanıma aktifken gösterge */}
      {speechState === "listening" && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 rounded-xl mx-2">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-xs text-red-600 font-medium">Dinleniyor... Konuşmanız bitince mikrofona tekrar basın.</span>
        </div>
      )}

      {/* Input Area */}
      <div className="flex items-end gap-2 px-2 pb-1">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); adjustHeight(); }}
          onKeyDown={handleKeyDown}
          placeholder="PINGO'ya sor veya bir görev ver..."
          className="flex-1 max-h-48 resize-none bg-transparent border-none outline-none text-brand-dark placeholder:text-brand-gray py-2"
          rows={1}
          disabled={!connected || isStreaming}
        />
        
        <div className="flex items-center gap-1 pb-1">
           {/* Mikrofon butonu */}
           <button 
             onClick={handleMicClick}
             className={`p-2.5 rounded-xl transition-all duration-200 ${
               speechState === 'listening'
                 ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-200'
                 : 'text-brand-gray hover:bg-brand-light-gray/50 hover:text-brand-dark'
             }`}
             disabled={!connected || isStreaming}
             title={speechState === 'listening' ? 'Kaydı durdur ve gönder' : 'Sesle söyle'}
           >
              {speechState === 'listening' ? <MicOff size={20} /> : <Mic size={20} />}
           </button>
           
           {messages.length > 0 && (
             <button 
               onClick={handleClear}
               title="Sohbeti Temizle"
               className="p-2.5 text-brand-gray hover:bg-red-50 hover:text-red-500 rounded-xl transition-colors"
             >
                <Trash2 size={20} />
             </button>
           )}

           <button 
             onClick={handleSend}
             disabled={!input.trim() || !connected || isStreaming}
             className="p-2.5 bg-brand-dark text-white rounded-xl hover:bg-brand-indigo disabled:opacity-50 transition-all duration-200 shadow-sm"
           >
              <Send size={20} />
           </button>
        </div>
      </div>
    </div>
  );
}
