import { useState, useEffect } from "react";
import { useChatStore } from "../store/chatStore";
import { Shield, ShieldCheck, ShieldAlert, FileText, Check, X, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export function Permissions() {
  const { settings } = useChatStore();
  const [permissions, setPermissions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPerms = async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/permissions`);
        if (!res.ok) throw new Error("Permissions fetch failed");
        const data = await res.json();
        setPermissions(data);
      } catch (err) {
        toast.error("Yetkiler alınırken bir hata oluştu.");
      } finally {
        setLoading(false);
      }
    };
    fetchPerms();
  }, [settings.backendUrl]);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-dark flex items-center gap-2">
          <Shield size={28} className="text-brand-indigo" />
          Rol ve Yetki Yönetimi (RBAC)
        </h1>
        <p className="text-brand-gray mt-2">
          Agent'ın sistem üzerindeki dosya, komut ve erişim yetkilerinin güncel listesi.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          [...Array(6)].map((_, i) => (
            <div key={i} className="glass-card p-6 h-32 animate-pulse bg-brand-light-gray/20 border-transparent" />
          ))
        ) : permissions.length === 0 ? (
          <div className="col-span-full glass-panel p-12 text-center text-brand-gray flex flex-col items-center">
            <Shield size={48} className="mb-4 opacity-50" />
            <p>Herhangi bir özel yetki tanımlanmamış. Varsayılan kısıtlamalar geçerli.</p>
          </div>
        ) : (
          permissions.map((perm, i) => (
            <div key={i} className="glass-card p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div className="bg-brand-indigo/10 text-brand-indigo px-2.5 py-1 rounded-md text-xs font-bold tracking-wide uppercase">
                    {perm.action}
                  </div>
                  {perm.status === "allowed" ? (
                     <ShieldCheck size={20} className="text-status-green" />
                  ) : perm.status === "denied" ? (
                     <ShieldAlert size={20} className="text-status-red" />
                  ) : (
                     <AlertTriangle size={20} className="text-status-yellow" />
                  )}
                </div>
                
                <h3 className="text-brand-dark font-medium font-mono text-sm break-all leading-tight mb-2">
                  {perm.target}
                </h3>
                {perm.reason && (
                  <p className="text-xs text-brand-gray leading-relaxed flex items-start gap-1">
                    <FileText size={12} className="shrink-0 mt-0.5 opacity-70" />
                    {perm.reason}
                  </p>
                )}
              </div>
              
              <div className="mt-4 pt-3 border-t border-brand-light-gray/50 flex justify-between items-center">
                <span className="text-[10px] text-brand-gray uppercase font-bold tracking-wider">Durum</span>
                <span className={`text-xs font-semibold flex items-center gap-1 ${
                  perm.status === "allowed" ? "text-status-green" : 
                  perm.status === "denied" ? "text-status-red" : "text-status-yellow"
                }`}>
                  {perm.status === "allowed" && <><Check size={12}/> İzin Verildi</>}
                  {perm.status === "denied" && <><X size={12}/> Reddedildi</>}
                  {perm.status === "ask" && <><AlertTriangle size={12}/> Onay Bekleniyor</>}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
