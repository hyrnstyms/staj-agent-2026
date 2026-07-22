// src/components/ApprovalModal.tsx
// Riskli işlem onay / red diyalogu

import { useChatStore } from "../store/chatStore";
import { useApproval } from "../hooks/useApproval";
import { useState } from "react";

export function ApprovalModal() {
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
    await approve(approval_id);
    setLoading(false);
  };

  const handleReject = async () => {
    setLoading(true);
    await reject(approval_id);
    setLoading(false);
  };

  return (
    <div className="modal-backdrop" onClick={(e) => e.stopPropagation()}>
      <div className="modal-card">
        {/* Başlık */}
        <div className="modal-header">
          <span className="modal-icon">{isDestructive ? "🚨" : "⚠️"}</span>
          <div>
            <div className="modal-title">Onay Gerekiyor</div>
            <div className="modal-subtitle">
              Bu işlem geri alınamaz olabilir. Devam etmek istiyor musun?
            </div>
          </div>
        </div>

        {/* Tool adı */}
        <div className="modal-tool-badge">
          <span>🔧</span>
          <span>{tool_name}</span>
        </div>

        {/* Açıklama */}
        <div className="modal-description">{description}</div>

        {/* Ek uyarı (silme/gönderme için) */}
        {isDestructive && (
          <div className="modal-warning">
            <span>⚠️</span>
            <span>Bu işlem geri alınamaz. Onaylamadan önce dikkatlice oku.</span>
          </div>
        )}

        {/* Butonlar */}
        <div className="modal-actions">
          <button
            className="btn btn-ghost"
            onClick={handleReject}
            disabled={loading}
          >
            🚫 Reddet
          </button>
          <button
            className="btn btn-danger"
            onClick={handleApprove}
            disabled={loading}
            style={!isDestructive ? { background: "var(--accent)", color: "#000" } : undefined}
          >
            {loading ? "İşleniyor…" : isDestructive ? "🔴 Evet, Onayla" : "✅ Onayla"}
          </button>
        </div>
      </div>
    </div>
  );
}
