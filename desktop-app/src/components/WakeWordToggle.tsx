// src/components/WakeWordToggle.tsx
// Wake word toggle — sidebar ve diğer yerlerde kullanılabilir

import { Mic, MicOff } from "lucide-react";
import { useWakeWord } from "../hooks/useWakeWord";

export function WakeWordToggle() {
  const { enabled, state, toggle } = useWakeWord();

  return (
    <button
      onClick={toggle}
      className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-all duration-200 text-sm font-medium ${
        enabled
          ? "bg-green-100 text-green-700 hover:bg-green-200"
          : "bg-gray-100 text-gray-500 hover:bg-gray-200"
      }`}
      title={enabled ? "Sesli Asistanı Kapat" : "Sesli Asistanı Aç"}
    >
      {enabled ? <Mic size={16} className="animate-pulse" /> : <MicOff size={16} />}
      <span>Hey Asistan</span>
      {enabled && (
        <span className="text-[10px] uppercase tracking-wider font-bold text-green-600">
          {state === "listening" ? "Dinliyor" : state === "wake_detected" ? "Algılandı!" : "Açık"}
        </span>
      )}
    </button>
  );
}
