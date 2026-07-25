import { useState } from "react";
import { useChatStore } from "../store/chatStore";
import { toast } from "sonner";
import { Save, Server, Key, Volume2, ShieldAlert } from "lucide-react";

export function Settings() {
  const { settings, setSettings } = useChatStore();
  const [local, setLocal] = useState({ ...settings });

  const handleSave = async () => {
    await setSettings(local);
    toast.success("Ayarlar başarıyla kaydedildi!");
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-dark">Ayarlar</h1>
        <p className="text-brand-gray mt-2">Sistem bağlantılarını ve uygulama tercihlerini yapılandırın.</p>
      </div>

      <div className="grid gap-6">
        
        {/* Connection Settings */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-4 text-brand-dark-gray">
            <Server size={20} className="text-brand-indigo" />
            <h2 className="text-lg font-bold">Bağlantı Ayarları</h2>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-brand-dark-gray mb-1">Backend URL</label>
              <input
                type="text"
                value={local.backendUrl}
                onChange={(e) => setLocal({ ...local, backendUrl: e.target.value })}
                className="w-full bg-brand-light-gray/50 border border-brand-light-gray rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-indigo/50 transition-shadow"
                placeholder="http://localhost:1420"
              />
              <p className="text-xs text-brand-gray mt-1">Yerel ağdaki FastAPI backend adresi.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-brand-dark-gray mb-1">API Key (Geçici Auth)</label>
              <input
                type="password"
                value={local.apiKey}
                onChange={(e) => setLocal({ ...local, apiKey: e.target.value })}
                className="w-full bg-brand-light-gray/50 border border-brand-light-gray rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-indigo/50 transition-shadow font-mono"
              />
              <div className="flex items-start gap-2 mt-2 text-xs text-brand-gray bg-status-yellow/10 p-2.5 rounded-lg border border-status-yellow/20">
                <ShieldAlert size={14} className="text-status-yellow shrink-0 mt-0.5" />
                <p>
                  Yalnızca backend'e bağlanmak için kullanılan geliştirme anahtarıdır. GitHub veya diğer servislerin gerçek token'ları 
                  <strong>.env</strong> dosyasında barındırılır.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Voice Settings */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-4 text-brand-dark-gray">
            <Volume2 size={20} className="text-brand-indigo" />
            <h2 className="text-lg font-bold">Ses ve Bildirimler</h2>
          </div>

          <div className="flex items-center justify-between p-4 border border-brand-light-gray rounded-xl bg-brand-white/50">
            <div>
              <div className="font-medium text-brand-dark">TTS (Sesli Cevap)</div>
              <div className="text-xs text-brand-gray mt-0.5">Asistanın verdiği cevapları otomatik olarak sesli oku.</div>
            </div>
            
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                className="sr-only peer"
                checked={local.ttsEnabled}
                onChange={(e) => setLocal({ ...local, ttsEnabled: e.target.checked })}
              />
              <div className="w-11 h-6 bg-brand-light-gray peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-brand-gray/20 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-status-green"></div>
            </label>
          </div>
        </div>
        
      </div>

      <div className="flex justify-end pt-4 pb-12">
        <button 
          onClick={handleSave}
          className="bg-brand-indigo hover:bg-brand-indigo/90 text-white px-6 py-2.5 rounded-xl font-medium transition-colors flex items-center gap-2 shadow-soft"
        >
          <Save size={18} />
          Değişiklikleri Kaydet
        </button>
      </div>

    </div>
  );
}
