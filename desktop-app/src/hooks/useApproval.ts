// src/hooks/useApproval.ts
// Onay/red akışı hook'u

import { useCallback } from "react";
import { useChatStore } from "../store/chatStore";
import type { ApprovalResponse } from "../types";

export function useApproval() {
  const { settings, setPendingApproval, addMessage } = useChatStore();

  /** Bekleyen işlemi onayla — POST /approve/{id} */
  const approve = useCallback(
    async (approvalId: string): Promise<ApprovalResponse | null> => {
      try {
        const res = await fetch(
          `${settings.backendUrl}/approve/${approvalId}`,
          {
            method: "POST",
            headers: { "X-API-Key": settings.apiKey },
          }
        );

        if (!res.ok) {
          const detail = await res.text();
          throw new Error(`Onay hatası (${res.status}): ${detail}`);
        }

        const data: ApprovalResponse = await res.json();
        setPendingApproval(null);

        addMessage({
          id:        crypto.randomUUID(),
          role:      "system",
          content:   `✅ "${data.tool_name}" işlemi onaylandı. ${data.message}`,
          status:    "done",
          timestamp: new Date(),
        });

        return data;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Onay başarısız";
        addMessage({
          id:        crypto.randomUUID(),
          role:      "system",
          content:   `❌ Onay gönderilemedi: ${msg}`,
          status:    "error",
          timestamp: new Date(),
        });
        return null;
      }
    },
    [settings, setPendingApproval, addMessage]
  );

  /** Bekleyen işlemi reddet — POST /reject/{id} */
  const reject = useCallback(
    async (approvalId: string): Promise<ApprovalResponse | null> => {
      try {
        const res = await fetch(
          `${settings.backendUrl}/reject/${approvalId}`,
          {
            method: "POST",
            headers: { "X-API-Key": settings.apiKey },
          }
        );

        if (!res.ok) {
          const detail = await res.text();
          throw new Error(`Red hatası (${res.status}): ${detail}`);
        }

        const data: ApprovalResponse = await res.json();
        setPendingApproval(null);

        addMessage({
          id:        crypto.randomUUID(),
          role:      "system",
          content:   `🚫 "${data.tool_name}" işlemi iptal edildi.`,
          status:    "done",
          timestamp: new Date(),
        });

        return data;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Red başarısız";
        addMessage({
          id:        crypto.randomUUID(),
          role:      "system",
          content:   `❌ Red gönderilemedi: ${msg}`,
          status:    "error",
          timestamp: new Date(),
        });
        return null;
      }
    },
    [settings, setPendingApproval, addMessage]
  );

  return { approve, reject };
}
