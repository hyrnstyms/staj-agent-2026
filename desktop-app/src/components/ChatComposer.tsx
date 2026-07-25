import { useState, useRef, KeyboardEvent } from "react";
import { Send, Paperclip, Mic, Image as ImageIcon, Folder, Code, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useChatStore } from "../store/chatStore";
import { useWebSocket } from "../hooks/useWebSocket";

export function ChatComposer() {
  const { connected, isStreaming, addMessage, setStreaming, clearMessages, messages } = useChatStore();
  const { sendMessage } = useWebSocket();
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || !connected || isStreaming) return;
    
    // Add user message to store
    addMessage({
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      status: "done",
      timestamp: new Date()
    });

    // Add empty assistant placeholder
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
    if (inputRef.current) {
       inputRef.current.style.height = 'auto';
    }
  };

  const handleClear = () => {
    if (confirm("Tüm sohbet geçmişini silmek istediğinize emin misiniz?")) {
      clearMessages();
      toast.success("Sohbet temizlendi.");
    }
  };

  const notifyNotImplemented = (feature: string) => {
    toast.info(`${feature} özelliği yakında eklenecek.`);
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
      <div className="flex items-end gap-3">
        <div className="flex items-center gap-1 pb-1">
           <button 
             onClick={() => notifyNotImplemented("Dosya ekleme")}
             className="p-2.5 text-brand-gray hover:bg-brand-light-gray/50 hover:text-brand-dark rounded-xl transition-colors tooltip-trigger" title="Dosya Ekle"
           >
              <Paperclip size={20} />
           </button>
           <button 
             onClick={() => notifyNotImplemented("Görsel yükleme")}
             className="p-2.5 text-brand-gray hover:bg-brand-light-gray/50 hover:text-brand-dark rounded-xl transition-colors tooltip-trigger" title="Görsel Analizi"
           >
              <ImageIcon size={20} />
           </button>
           <button 
             onClick={() => notifyNotImplemented("Klasör seçme")}
             className="p-2.5 text-brand-gray hover:bg-brand-light-gray/50 hover:text-brand-dark rounded-xl transition-colors tooltip-trigger" title="Klasör Seç"
           >
              <Folder size={20} />
           </button>
           <div className="w-px h-4 bg-brand-light-gray mx-1" />
           <button 
             onClick={() => notifyNotImplemented("Kod bloğu ekleme")}
             className="p-2.5 text-brand-gray hover:bg-brand-light-gray/50 hover:text-brand-dark rounded-xl transition-colors tooltip-trigger" title="Kod Bloğu Ekle"
           >
              <Code size={20} />
           </button>
        </div>
      </div>

      {/* Input Area */}
      <div className="flex items-end gap-2 px-2 pb-1">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          placeholder="PINGO'ya sor veya bir görev ver..."
          className="flex-1 max-h-48 resize-none bg-transparent border-none outline-none text-brand-dark placeholder:text-brand-gray py-2"
          rows={1}
          disabled={!connected || isStreaming}
        />
        
        <div className="flex items-center gap-1 pb-1">
           <button 
             onClick={() => notifyNotImplemented("Ses kaydı")}
             className="p-2.5 text-brand-gray hover:bg-brand-light-gray/50 hover:text-brand-dark rounded-xl transition-colors"
             disabled={!connected}
           >
              <Mic size={20} />
           </button>
           
           {messages.length > 0 && (
             <button 
               onClick={handleClear}
               title="Sohbeti Temizle"
               className="p-2.5 text-brand-gray hover:bg-status-red/10 hover:text-status-red rounded-xl transition-colors ml-1 mr-1"
             >
                <Trash2 size={20} />
             </button>
           )}

           <button 
             onClick={handleSend}
             disabled={!input.trim() || !connected || isStreaming}
             className="p-2.5 bg-brand-dark text-white rounded-xl hover:bg-brand-indigo disabled:opacity-50 disabled:hover:bg-brand-dark transition-all duration-200 shadow-sm"
           >
              <Send size={20} />
           </button>
        </div>
      </div>
    </div>
  );
}
