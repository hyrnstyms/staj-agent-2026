// src/types/index.ts
// Asistan frontend için merkezi TypeScript tip tanımlamaları

// ─────────────────────────────────────────────────────────────────────────────
// Mesaj tipleri
// ─────────────────────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "system";

export type MessageStatus =
  | "sending"        // Kullanıcı mesajı gönderildi, cevap bekleniyor
  | "streaming"      // LLM token'ları akıyor
  | "done"           // Tamamlandı
  | "error"          // Hata oluştu
  | "pending_approval"; // Onay bekleniyor

export interface ToolCall {
  tool_name: string;
  category: string;
  /** Tool çalışma süresi ms cinsinden (backend'den gelirse) */
  duration_ms?: number;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  timestamp: Date;
  tool_call?: ToolCall;
  approval_id?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Backend API yanıt tipleri
// ─────────────────────────────────────────────────────────────────────────────

export interface ChatResponse {
  message: string;
  status: string;
  session_id: string;
  tool_name?: string;
  approval_id?: string;
  category?: string;
  phase1_success: boolean;
  phase2_success: boolean;
  tool_result?: unknown;
}

export interface ApprovalResponse {
  approval_id: string;
  decision: "approved" | "rejected";
  tool_name: string;
  message: string;
}

export interface UploadResponse {
  success: boolean;
  upload_type: "audio" | "image";
  result: string;
  mime_type: string;
  size_bytes: number;
  message?: string;
}

export interface HealthResponse {
  status: string;
  model: string;
  ollama_url: string;
  sandbox_root: string;
  active_sessions: number;
  pending_approvals: number;
  worker_warning: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket event tipleri (server → client)
// ─────────────────────────────────────────────────────────────────────────────

export interface WsConnectedEvent {
  type: "connected";
  session_id: string;
  message: string;
}

export interface WsTokenEvent {
  type: "token";
  content: string;
}

export interface WsDoneEvent {
  type: "done";
  status: string;
  session_id: string;
  full_response: string;
}

export interface WsApprovalEvent {
  type: "approval";
  approval_id: string;
  tool_name: string;
  description: string;
}

export interface WsErrorEvent {
  type: "error";
  message: string;
}

export type WsEvent =
  | WsConnectedEvent
  | WsTokenEvent
  | WsDoneEvent
  | WsApprovalEvent
  | WsErrorEvent;

// ─────────────────────────────────────────────────────────────────────────────
// Onay talebi (approval)
// ─────────────────────────────────────────────────────────────────────────────

export interface PendingApproval {
  approval_id: string;
  tool_name: string;
  description: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Uygulama ayarları (tauri-plugin-store'a kaydedilir)
// ─────────────────────────────────────────────────────────────────────────────

export interface AppSettings {
  /** Backend'e bağlanmak için kullanılan Faz 1 auth anahtarı.
   *  NOT: GitHub/Gmail gibi hassas token'lar ASLA burada tutulmaz;
   *  bunlar backend .env dosyasında kalır. */
  apiKey: string;
  /** Backend URL — varsayılan: http://localhost:8000 */
  backendUrl: string;
  /** TTS sesli cevap açık mı */
  ttsEnabled: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  apiKey: "dev-api-key-change-in-production",
  backendUrl: "http://localhost:8000",
  ttsEnabled: false,
};

// ─────────────────────────────────────────────────────────────────────────────
// Kategori → renk eşlemesi (tool chip renklendirmesi)
// ─────────────────────────────────────────────────────────────────────────────

export const CATEGORY_COLORS: Record<string, string> = {
  dosya:          "var(--chip-dosya)",
  veritabani:     "var(--chip-veritabani)",
  kod_git:        "var(--chip-kod-git)",
  mail_takvim:    "var(--chip-mail)",
  uygulama:       "var(--chip-uygulama)",
  gorsel_ses:     "var(--chip-gorsel)",
  genel_sohbet:   "var(--chip-genel)",
};

export const CATEGORY_ICONS: Record<string, string> = {
  dosya:          "📁",
  veritabani:     "🗄️",
  kod_git:        "💻",
  mail_takvim:    "📧",
  uygulama:       "🖥️",
  gorsel_ses:     "🎙️",
  genel_sohbet:   "💬",
};
