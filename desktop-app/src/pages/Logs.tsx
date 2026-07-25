import { useState, useEffect } from "react";
import { useChatStore } from "../store/chatStore";
import { Activity, Clock, AlertTriangle, CheckCircle, Search, Terminal } from "lucide-react";
import { toast } from "sonner";

export function Logs() {
  const { settings } = useChatStore();
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/logs`);
        if (!res.ok) throw new Error("Log fetch failed");
        const data = await res.json();
        setLogs(data);
      } catch (err) {
        toast.error("Loglar alınırken bir hata oluştu.");
      } finally {
        setLoading(false);
      }
    };
    fetchLogs();
  }, [settings.backendUrl]);

  const filteredLogs = logs.filter(log => 
    JSON.stringify(log).toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-dark flex items-center gap-2">
            <Terminal size={28} className="text-brand-indigo" />
            Sistem Logları
          </h1>
          <p className="text-brand-gray mt-2">Agent tool kullanımları ve sistem içi detaylı kayıtlar.</p>
        </div>
        
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-brand-gray" />
          <input
            type="text"
            placeholder="Loglarda ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 bg-white border border-brand-light-gray rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-indigo/50 w-full md:w-64"
          />
        </div>
      </div>

      <div className="glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-brand-light-gray/50 text-brand-dark-gray border-b border-brand-light-gray">
              <tr>
                <th className="px-6 py-4 font-semibold rounded-tl-2xl">Zaman</th>
                <th className="px-6 py-4 font-semibold">İşlem (Tool)</th>
                <th className="px-6 py-4 font-semibold">Durum</th>
                <th className="px-6 py-4 font-semibold">Sonuç</th>
                <th className="px-6 py-4 font-semibold text-right rounded-tr-2xl">Süre</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-light-gray/50">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-brand-gray">
                    <Activity size={24} className="animate-spin mx-auto mb-2 text-brand-indigo" />
                    Loglar yükleniyor...
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-brand-gray">
                    Herhangi bir log bulunamadı.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log, i) => (
                  <tr key={i} className="hover:bg-brand-white transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-brand-gray font-mono text-xs">
                      {new Date(log.created_at).toLocaleString('tr-TR')}
                    </td>
                    <td className="px-6 py-4 font-medium text-brand-dark">
                      <div className="bg-brand-indigo/10 text-brand-indigo px-2 py-1 rounded inline-block text-xs">
                        {log.tool_name}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {log.error ? (
                        <span className="flex items-center gap-1 text-status-red text-xs font-medium">
                          <AlertTriangle size={14} /> Hatalı
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-status-green text-xs font-medium">
                          <CheckCircle size={14} /> Başarılı
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-brand-gray max-w-xs truncate" title={log.error || "Başarılı"}>
                      {log.error || "İşlem başarıyla tamamlandı."}
                    </td>
                    <td className="px-6 py-4 text-right whitespace-nowrap text-brand-gray flex justify-end items-center gap-1">
                      <Clock size={12} /> {log.execution_time_ms ? `${Math.round(log.execution_time_ms)}ms` : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
