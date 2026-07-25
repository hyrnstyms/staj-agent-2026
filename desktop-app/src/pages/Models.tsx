import { useState, useEffect } from "react";
import { useChatStore } from "../store/chatStore";
import { Box, Cpu, HardDrive, Zap, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export function Models() {
  const { settings } = useChatStore();
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${settings.backendUrl}/system/metrics`);
      if (!res.ok) throw new Error("Metrics fetch failed");
      const data = await res.json();
      setMetrics(data);
    } catch (err) {
      toast.error("Metrikler alınırken bir hata oluştu.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, [settings.backendUrl]);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-dark flex items-center gap-2">
            <Box size={28} className="text-brand-indigo" />
            Modeller ve Kaynaklar
          </h1>
          <p className="text-brand-gray mt-2">
            Aktif dil modeli (LLM) ve anlık donanım tüketimi istatistikleri.
          </p>
        </div>
        <button 
          onClick={fetchMetrics} 
          className="p-2 text-brand-gray hover:text-brand-indigo bg-white border border-brand-light-gray rounded-lg hover:shadow-sm transition-all"
          title="Yenile"
        >
          <RefreshCw size={20} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Active Model Card */}
        <div className="glass-panel p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-4 text-brand-dark-gray">
              <Zap size={20} className="text-brand-indigo" />
              <h2 className="text-lg font-bold">Aktif LLM Modeli</h2>
            </div>
            
            <div className="bg-brand-indigo/5 border border-brand-indigo/10 rounded-xl p-4 flex flex-col items-center justify-center min-h-[120px]">
              {loading && !metrics ? (
                <span className="text-brand-gray animate-pulse">Yükleniyor...</span>
              ) : (
                <>
                  <span className="text-2xl font-bold text-brand-indigo mb-1 text-center">
                    {metrics?.active_model || "qwen2.5:3b-instruct"}
                  </span>
                  <span className="text-xs text-brand-gray font-medium uppercase tracking-wider">Ollama Engine</span>
                </>
              )}
            </div>
          </div>
          
          <div className="mt-6 flex justify-between text-sm text-brand-gray border-t border-brand-light-gray pt-4">
            <span>Ortalama Yanıt Süresi</span>
            <span className="font-bold text-brand-dark">{metrics?.response_time_ms || 0} ms</span>
          </div>
        </div>

        {/* Resources Card */}
        <div className="glass-panel p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-4 text-brand-dark-gray">
              <Cpu size={20} className="text-status-green" />
              <h2 className="text-lg font-bold">Sistem Kaynakları</h2>
            </div>
            
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-brand-gray flex items-center gap-1"><Cpu size={14}/> CPU Kullanımı</span>
                  <span className="font-bold text-brand-dark">{metrics?.cpu_usage_percent || 0}%</span>
                </div>
                <div className="w-full bg-brand-light-gray rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-brand-indigo h-2 rounded-full transition-all duration-1000" 
                    style={{ width: `${metrics?.cpu_usage_percent || 0}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-brand-gray flex items-center gap-1"><HardDrive size={14}/> RAM Tüketimi</span>
                  <span className="font-bold text-brand-dark">{metrics ? Math.round(metrics.ram_usage_mb) : 0} MB</span>
                </div>
                <div className="w-full bg-brand-light-gray rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-status-green h-2 rounded-full transition-all duration-1000" 
                    style={{ width: `${Math.min((metrics?.ram_usage_mb || 0) / 1024 * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
          
          <div className="mt-6 flex justify-between text-xs text-brand-gray border-t border-brand-light-gray pt-4">
            <span>Platform: <span className="font-mono">{metrics?.platform || 'Bilinmiyor'}</span></span>
            <span>Çalışma Süresi: <span className="font-mono">{metrics?.uptime_seconds ? Math.round(metrics.uptime_seconds) : 0}s</span></span>
          </div>
        </div>

      </div>
    </div>
  );
}
