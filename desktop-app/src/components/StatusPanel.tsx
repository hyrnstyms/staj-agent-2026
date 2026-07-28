import { useState, useEffect } from "react";
import { Server, Activity, Database, Box, Zap } from "lucide-react";
import { useChatStore } from "../store/chatStore";

export function StatusPanel() {
  const [metrics, setMetrics] = useState<any>(null);
  const { connected, reconnecting, settings } = useChatStore();

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/system/metrics`);
        const data = await res.json();
        setMetrics(data);
      } catch (err) {
        console.error(err);
      }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="w-64 bg-white border-l border-brand-light-gray shadow-sm shrink-0 flex flex-col z-20">
      <div className="p-6 border-b border-brand-light-gray">
        <h2 className="font-bold text-sm text-brand-dark flex items-center gap-2">
          <Activity size={16} className="text-brand-indigo" />
          Sistem Durumu
        </h2>
      </div>

      <div className="p-4 space-y-4">
        
        {/* Core Process */}
        <div className="bg-brand-white rounded-xl p-3 border border-brand-light-gray">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Server size={14} className="text-brand-gray" />
              <span className="text-xs font-semibold text-brand-dark-gray">FastAPI Core</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-status-green animate-pulse" />
              <span className="text-[10px] text-brand-gray uppercase font-bold">Online</span>
            </div>
          </div>
          <div className="flex justify-between text-xs mt-3">
            <span className="text-brand-gray">CPU</span>
            <span className="font-medium">{metrics?.cpu_usage_percent || 0}%</span>
          </div>
          <div className="flex justify-between text-xs mt-1">
            <span className="text-brand-gray">RAM</span>
            <span className="font-medium">{metrics ? Math.round(metrics.ram_usage_mb) : 0} MB</span>
          </div>
        </div>

        {/* Ollama / Model */}
        <div className="bg-brand-white rounded-xl p-3 border border-brand-light-gray">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Box size={14} className="text-brand-gray" />
              <span className="text-xs font-semibold text-brand-dark-gray">LLM Engine</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-status-green" />
            </div>
          </div>
          <div className="text-[10px] bg-brand-light-gray/50 px-2 py-1 rounded text-center text-brand-dark font-medium mb-2 truncate">
            {metrics?.active_model || "qwen2.5:3b-instruct"}
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-brand-gray">Yanıt Süresi</span>
            <span className="font-medium">{metrics?.response_time_ms || 0}ms</span>
          </div>
        </div>

        {/* Database */}
        <div className="bg-brand-white rounded-xl p-3 border border-brand-light-gray">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Database size={14} className="text-brand-gray" />
              <span className="text-xs font-semibold text-brand-dark-gray">SQLite Store</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-status-green" />
            </div>
          </div>
          <div className="flex justify-between text-xs text-brand-gray">
            <span>Bağlantı</span>
            <span className="font-medium text-brand-dark-gray">Hazır</span>
          </div>
        </div>

        {/* WebSocket */}
        <div className="bg-brand-white rounded-xl p-3 border border-brand-light-gray">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-brand-gray" />
              <span className="text-xs font-semibold text-brand-dark-gray">Canlı Akış</span>
            </div>
            <div className="flex items-center gap-1">
              {connected ? (
                <div className="w-2 h-2 rounded-full bg-status-green" title="Bağlı" />
              ) : reconnecting ? (
                <div className="w-2 h-2 rounded-full bg-status-yellow animate-pulse" title="Yeniden Bağlanıyor" />
              ) : (
                <div className="w-2 h-2 rounded-full bg-status-red" title="Koptu" />
              )}
            </div>
          </div>
          <div className="flex justify-between text-xs text-brand-gray">
            <span>Bağlantı Durumu</span>
            <span className={`font-medium ${connected ? "text-status-green" : reconnecting ? "text-status-yellow" : "text-status-red"}`}>
              {connected ? "Bağlı 🟢" : reconnecting ? "Yeniden Bağlanıyor 🟡" : "Koptu 🔴"}
            </span>
          </div>
        </div>
        
      </div>
    </aside>
  );
}
