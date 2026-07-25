// src/components/ApprovalModal.tsx
// Riskli işlem onay / red diyalogu

import { useChatStore } from "../store/chatStore";
import { useApproval } from "../hooks/useApproval";
import { useState } from "react";
import { ShieldAlert, Check, X, Loader2 } from "lucide-react";

interface Props {
  sendMessage?: (message: string, approvalId?: string) => void;
}

export function ApprovalModal({ sendMessage }: Props) {
  const pendingApproval  = useChatStore((s) => s.pendingApproval);
  const [loading, setLoading] = useState(false);
  const { approve, reject }   = useApproval();

  if (!pendingApproval) return null;

  const { approval_id, tool_name, description } = pendingApproval;

  // Geri alınamaz tool'lar için ek uyarı
  const isDestructive = [
    "file_delete", "db_delete", "calendar_delete_event",
    "git_commit_and_push", "mail_send",
  ].some((t) => tool_name.includes(t.split("_")[0]));

  const handleApprove = async () => {
    setLoading(true);
    const result = await approve(approval_id);
    if (result && sendMessage) {
      const msgs = useChatStore.getState().messages;
      const lastUserMsg = [...msgs].reverse().find(m => m.role === "user");
      if (lastUserMsg) {
        useChatStore.getState().addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content: "",
          status: "streaming",
          timestamp: new Date(),
        });
        useChatStore.getState().setStreaming(true);
        sendMessage(lastUserMsg.content, approval_id);
      }
    }
    setLoading(false);
  };

  const handleReject = async () => {
    setLoading(true);
    await reject(approval_id);
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-brand-dark/40 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={(e) => e.stopPropagation()}>
      <div className="bg-white rounded-3xl shadow-soft w-full max-w-md overflow-hidden border border-brand-light-gray animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className={`p-6 border-b flex items-start gap-4 ${isDestructive ? 'bg-status-red/5 border-status-red/10' : 'bg-status-yellow/5 border-status-yellow/10'}`}>
          <div className={`p-3 rounded-2xl ${isDestructive ? 'bg-status-red/10 text-status-red' : 'bg-status-yellow/10 text-status-yellow'}`}>
            <ShieldAlert size={28} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-brand-dark">Onay Gerekiyor</h2>
            <p className="text-sm text-brand-gray mt-1">
              Güvenlik politikası gereği bu işlem izninizi bekliyor.
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
           <div>
              <div className="text-xs font-bold text-brand-gray uppercase tracking-wider mb-1">Araç (Tool)</div>
              <div className="font-mono text-sm bg-brand-light-gray/30 px-3 py-2 rounded-lg text-brand-dark inline-block border border-brand-light-gray/50">
                 {tool_name}
              </div>
           </div>
           
           <div>
              <div className="text-xs font-bold text-brand-gray uppercase tracking-wider mb-1">İşlem Özeti</div>
              <p className="text-sm text-brand-dark-gray leading-relaxed bg-brand-light-gray/10 p-3 rounded-lg border border-brand-light-gray/30">
                 {description}
              </p>
           </div>
        </div>

        {/* Actions */}
        <div className="p-6 pt-2 flex gap-3">
          <button
            onClick={handleReject}
            disabled={loading}
            className="flex-1 px-4 py-3 rounded-xl border border-brand-light-gray text-brand-dark-gray font-semibold hover:bg-brand-light-gray/50 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : <X size={18} />}
            İptal Et
          </button>
          
          <button
            onClick={handleApprove}
            disabled={loading}
            className={`flex-1 px-4 py-3 rounded-xl text-white font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50 shadow-sm ${
              isDestructive 
                ? 'bg-status-red hover:bg-red-600' 
                : 'bg-brand-indigo hover:bg-indigo-600'
            }`}
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : <Check size={18} />}
            Onayla
          </button>
        </div>
      </div>
    </div>
  );
}
