// src/store/chatStore.ts
// Asistan — Zustand global state yönetimi

import { create } from "zustand";
import { load } from "@tauri-apps/plugin-store";
import {
  type Message,
  type PendingApproval,
  type AppSettings,
  DEFAULT_SETTINGS,
} from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// Store tanımı
// ─────────────────────────────────────────────────────────────────────────────

interface ChatState {
  // Mesajlar
  messages: Message[];
  addMessage: (msg: Message) => void;
  updateLastMessage: (patch: Partial<Message>) => void;
  appendToLastAssistant: (token: string) => void;
  clearMessages: () => void;

  // Session
  sessionId: string | null;
  setSessionId: (id: string) => void;

  // Bağlantı durumu
  connected: boolean;
  reconnecting: boolean;
  setConnected: (v: boolean) => void;
  setReconnecting: (v: boolean) => void;

  // Onay bekleyen işlem
  pendingApproval: PendingApproval | null;
  setPendingApproval: (a: PendingApproval | null) => void;

  // Ayarlar
  settings: AppSettings;
  setSettings: (s: Partial<AppSettings>) => Promise<void>;
  loadSettings: () => Promise<void>;

  // UI durumu
  settingsOpen: boolean;
  setSettingsOpen: (v: boolean) => void;
  isStreaming: boolean;
  setStreaming: (v: boolean) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tauri Store yardımcıları (ayarları diske kaydet/yükle)
// ─────────────────────────────────────────────────────────────────────────────

async function getTauriStore() {
  try {
    return await load("asistan-store.json", { autoSave: true });
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Store oluştur
// ─────────────────────────────────────────────────────────────────────────────

export const useChatStore = create<ChatState>((set, get) => ({
  // ── Mesajlar ───────────────────────────────────────────────────────────────
  messages: [],

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  updateLastMessage: (patch) =>
    set((s) => {
      const msgs = [...s.messages];
      if (msgs.length === 0) return s;
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], ...patch };
      return { messages: msgs };
    }),

  appendToLastAssistant: (token) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (!last || last.role !== "assistant") return s;
      msgs[msgs.length - 1] = {
        ...last,
        content: last.content + token,
        status: "streaming",
      };
      return { messages: msgs };
    }),

  clearMessages: () => set({ messages: [], sessionId: null }),

  // ── Session ────────────────────────────────────────────────────────────────
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),

  // ── Bağlantı ───────────────────────────────────────────────────────────────
  connected: false,
  reconnecting: false,
  setConnected: (v) => set({ connected: v, reconnecting: false }),
  setReconnecting: (v) => set({ reconnecting: v }),

  // ── Onay ───────────────────────────────────────────────────────────────────
  pendingApproval: null,
  setPendingApproval: (a) => set({ pendingApproval: a }),

  // ── Ayarlar ────────────────────────────────────────────────────────────────
  settings: DEFAULT_SETTINGS,

  setSettings: async (patch) => {
    const next = { ...get().settings, ...patch };
    set({ settings: next });
    const store = await getTauriStore();
    if (store) {
      await store.set("settings", next);
    }
  },

  loadSettings: async () => {
    const store = await getTauriStore();
    if (!store) return;
    const saved = await store.get<AppSettings>("settings");
    if (saved) {
      set({ settings: { ...DEFAULT_SETTINGS, ...saved } });
    }
  },

  // ── UI ─────────────────────────────────────────────────────────────────────
  settingsOpen: false,
  setSettingsOpen: (v) => set({ settingsOpen: v }),
  isStreaming: false,
  setStreaming: (v) => set({ isStreaming: v }),
}));
