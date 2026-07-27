import { useState } from "react";
import { useChatStore } from "../store/chatStore";
import { toast } from "sonner";
import { Save, Server, Volume2, ShieldAlert } from "lucide-react";

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

        {/* Google OAuth Settings (Phase 4) */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-4 text-brand-dark-gray">
            <svg viewBox="0 0 24 24" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            <h2 className="text-lg font-bold">Google Entegrasyonu</h2>
          </div>
          
          <div className="space-y-4">
            <p className="text-sm text-brand-gray">
              Google hesabı bağlayarak asistanın sizin adınıza e-posta okumasına, göndermesine ve takvim etkinlikleri yönetmesine izin verin.
            </p>

            <div className="flex items-center gap-4">
              <button
                onClick={() => {
                  const url = `${local.backendUrl}/auth/google/connect?user_id=1&api_key=${local.apiKey}`;
                  window.open(url, '_blank');
                }}
                className="bg-brand-white border border-brand-light-gray hover:bg-brand-light-gray/50 text-brand-dark px-4 py-2 rounded-xl font-medium transition-colors shadow-soft"
              >
                Google ile Bağlan
              </button>
              
              <button
                onClick={async () => {
                  try {
                    const res = await fetch(`${local.backendUrl}/auth/google/status?user_id=1`, {
                      headers: { "X-API-Key": local.apiKey }
                    });
                    const data = await res.json();
                    if (data.connected) {
                      toast.success(`Bağlı: ${data.google_email}`);
                    } else {
                      toast.info("Google hesabı bağlı değil.");
                    }
                  } catch (e) {
                    toast.error("Bağlantı durumu alınamadı.");
                  }
                }}
                className="bg-brand-white border border-brand-light-gray hover:bg-brand-light-gray/50 text-brand-dark px-4 py-2 rounded-xl font-medium transition-colors shadow-soft"
              >
                Durumu Kontrol Et
              </button>

              <button
                onClick={async () => {
                  try {
                    const res = await fetch(`${local.backendUrl}/auth/google/disconnect?user_id=1`, {
                      method: 'DELETE',
                      headers: { "X-API-Key": local.apiKey }
                    });
                    if (res.ok) {
                      toast.success("Google hesabı bağlantısı kesildi.");
                    } else {
                      toast.error("Bağlantı kesilemedi.");
                    }
                  } catch (e) {
                    toast.error("Bağlantı kesilemedi.");
                  }
                }}
                className="text-status-red hover:bg-status-red/10 px-4 py-2 rounded-xl font-medium transition-colors"
              >
                Bağlantıyı Kes
              </button>
            </div>
            <div className="flex items-start gap-2 mt-2 text-xs text-brand-gray bg-brand-light-gray/20 p-2.5 rounded-lg border border-brand-light-gray/50">
                <ShieldAlert size={14} className="text-brand-gray shrink-0 mt-0.5" />
                <p>
                  Bağlantı işleminden sonra (veya hata alırsanız) 'Durumu Kontrol Et' butonuna tıklayarak bağlantı durumunuzu teyit edebilirsiniz.
                </p>
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
