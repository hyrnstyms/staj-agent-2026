import { useState, useEffect } from "react";
import { Search, Bell, Sparkles, TerminalSquare, Mail, Calendar, Settings, ChevronRight, Activity } from "lucide-react";
import { Mascot } from "../components/Mascot";

export function Home() {
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    fetch("http://localhost:1420/logs")
      .then(r => r.json())
      .then(data => setLogs(data))
      .catch(console.error);
  }, []);

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="relative w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-brand-gray" size={18} />
          <input 
            type="text" 
            placeholder="Ne yapmak istersin?" 
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-brand-light-gray rounded-2xl focus:outline-none focus:ring-2 focus:ring-brand-indigo/20 shadow-sm"
          />
        </div>
        <button className="p-2.5 bg-white border border-brand-light-gray rounded-xl text-brand-gray hover:text-brand-dark shadow-sm transition-colors relative">
          <Bell size={20} />
          <span className="absolute top-2 right-2 w-2 h-2 bg-status-red rounded-full" />
        </button>
      </div>

      {/* Hero Section */}
      <div className="glass-card bg-gradient-to-br from-brand-indigo/5 to-brand-purple/5 border border-brand-indigo/10 p-8 flex items-center justify-between overflow-hidden relative">
        <div className="z-10 max-w-xl">
           <h2 className="text-3xl font-bold text-brand-dark mb-2 flex items-center gap-2">
             Merhaba, ben PINGO <Sparkles className="text-status-yellow" size={24} />
           </h2>
           <p className="text-brand-gray mb-6 text-lg">Sana nasıl yardımcı olabilirim? Dosyalarını analiz edebilir, e-postalarını okuyabilir veya terminal üzerinden otomasyonlar çalıştırabilirim.</p>
           
           <div className="flex gap-4">
              <button className="bg-brand-dark text-white px-5 py-2.5 rounded-xl font-medium shadow-soft hover:bg-brand-indigo transition-colors flex items-center gap-2">
                 Yeni Görev Başlat <ChevronRight size={18} />
              </button>
           </div>
        </div>
        <div className="absolute right-10 -bottom-10 opacity-90 scale-125 origin-bottom-right">
           <Mascot className="w-48 h-48 border-none bg-transparent text-[8rem]" />
        </div>
      </div>

      {/* Quick Actions */}
      <div>
         <h3 className="text-lg font-bold text-brand-dark mb-4">Hızlı İşlemler</h3>
         <div className="grid grid-cols-4 gap-4">
            {[
              { icon: TerminalSquare, label: "Terminalde Çalıştır", color: "text-brand-blue", bg: "bg-brand-blue/10" },
              { icon: Mail, label: "E-postaları Oku", color: "text-status-red", bg: "bg-status-red/10" },
              { icon: Calendar, label: "Takvimi Düzenle", color: "text-status-yellow", bg: "bg-status-yellow/10" },
              { icon: Settings, label: "Sistem Ayarları", color: "text-brand-gray", bg: "bg-brand-gray/10" },
            ].map((action, i) => (
              <button key={i} className="glass-card p-4 flex flex-col items-start gap-3 hover:-translate-y-1 transition-transform text-left">
                 <div className={`p-3 rounded-xl ${action.bg} ${action.color}`}>
                   <action.icon size={24} />
                 </div>
                 <span className="font-semibold text-brand-dark-gray">{action.label}</span>
              </button>
            ))}
         </div>
      </div>

      {/* Recent Activities */}
      <div>
         <h3 className="text-lg font-bold text-brand-dark mb-4 flex items-center gap-2">
            <Activity size={20} className="text-brand-gray" />
            Son Aktiviteler (Tool Logları)
         </h3>
         <div className="glass-card bg-white overflow-hidden">
            <table className="w-full text-sm text-left">
              <thead className="bg-brand-light-gray/30 text-brand-gray uppercase text-[11px] font-bold">
                <tr>
                  <th className="px-6 py-4">Araç (Tool)</th>
                  <th className="px-6 py-4">Kategori</th>
                  <th className="px-6 py-4">Zaman</th>
                  <th className="px-6 py-4">Durum</th>
                  <th className="px-6 py-4 text-right">Süre</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-light-gray/50">
                {logs.slice(0, 5).map(log => (
                  <tr key={log.id} className="hover:bg-brand-light-gray/20 transition-colors">
                    <td className="px-6 py-4 font-medium text-brand-dark-gray">{log.tool_name}</td>
                    <td className="px-6 py-4">
                      <span className="bg-brand-light-gray text-brand-dark-gray px-2.5 py-1 rounded-md text-xs font-semibold">
                         {log.category || 'general'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-brand-gray">{new Date(log.timestamp).toLocaleTimeString()}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] uppercase font-bold tracking-wider ${
                        log.status === 'success' ? 'bg-status-green/10 text-status-green' :
                        log.status === 'error' ? 'bg-status-red/10 text-status-red' :
                        'bg-status-yellow/10 text-status-yellow'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right text-brand-gray">{log.duration_ms}ms</td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-brand-gray">Henüz aktivite bulunmuyor.</td>
                  </tr>
                )}
              </tbody>
            </table>
         </div>
      </div>
    </div>
  );
}
