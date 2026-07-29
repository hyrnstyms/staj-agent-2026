import { useState, useEffect, useCallback } from "react";
import {
  Wrench,
  Terminal,
  FileCode2,
  Database,
  Mail,
  Calendar,
  GitFork,
  GitBranch,
  GitCommit,
  Code2,
  Monitor,
  Mic,
  Volume2,
  Eye,
  Image,
  Users,
  ChevronDown,
  ChevronUp,
  Search,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Info,
  RefreshCw,
  Folder,
} from "lucide-react";
import { useChatStore } from "../store/chatStore";

// ─── Tool tanımlamaları ────────────────────────────────────────────────────
type ApprovalLevel = "none" | "requires" | "destructive";

interface ToolDef {
  name: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  server: string;
  approval: ApprovalLevel;
  example?: string;
}

interface ServerGroup {
  key: string;
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  headerBg: string;
  tools: ToolDef[];
}

const SERVER_GROUPS: ServerGroup[] = [
  {
    key: "filesystem",
    label: "Dosya Sistemi",
    description: "Sandbox korumalı dosya okuma, yazma, silme, listeleme işlemleri",
    icon: Folder,
    color: "text-orange-600",
    headerBg: "bg-orange-50 border-orange-200",
    tools: [
      {
        name: "file_read",
        description: "Belirtilen dosyanın içeriğini okur.",
        icon: FileCode2,
        color: "text-orange-600",
        bg: "bg-orange-50",
        server: "filesystem",
        approval: "none",
        example: "README.md dosyasını oku",
      },
      {
        name: "file_write",
        description: "Dosya oluşturur veya üzerine yazar.",
        icon: FileCode2,
        color: "text-orange-500",
        bg: "bg-orange-50",
        server: "filesystem",
        approval: "requires",
        example: "notlar.txt dosyasına 'Toplantı notları' yaz",
      },
      {
        name: "file_delete",
        description: "Belirtilen dosyayı kalıcı olarak siler.",
        icon: FileCode2,
        color: "text-red-500",
        bg: "bg-red-50",
        server: "filesystem",
        approval: "destructive",
        example: "eski_dosya.txt'yi sil",
      },
      {
        name: "file_list",
        description: "Dizindeki dosya ve klasörleri listeler.",
        icon: Folder,
        color: "text-orange-400",
        bg: "bg-orange-50",
        server: "filesystem",
        approval: "none",
        example: "Sandbox klasöründeki dosyaları listele",
      },
      {
        name: "file_move",
        description: "Dosyayı taşır veya yeniden adlandırır.",
        icon: FileCode2,
        color: "text-orange-500",
        bg: "bg-orange-50",
        server: "filesystem",
        approval: "requires",
        example: "notlar.txt'yi arsiv/notlar.txt'ye taşı",
      },
    ],
  },
  {
    key: "database",
    label: "Veritabanı",
    description: "SQLite veritabanı sorgulama ve yönetimi",
    icon: Database,
    color: "text-purple-600",
    headerBg: "bg-purple-50 border-purple-200",
    tools: [
      {
        name: "db_list_tables",
        description: "Erişilebilir tabloları listeler.",
        icon: Database,
        color: "text-purple-500",
        bg: "bg-purple-50",
        server: "database",
        approval: "none",
        example: "Veritabanındaki tabloları göster",
      },
      {
        name: "db_get_schema",
        description: "Tablonun sütun şemasını döner.",
        icon: Database,
        color: "text-purple-500",
        bg: "bg-purple-50",
        server: "database",
        approval: "none",
        example: "employees tablosunun yapısını göster",
      },
      {
        name: "db_query",
        description: "Tabloda filtre uygulayarak veri sorgular.",
        icon: Database,
        color: "text-purple-500",
        bg: "bg-purple-50",
        server: "database",
        approval: "none",
        example: "employees tablosundan mühendisleri getir",
      },
      {
        name: "db_insert",
        description: "Tabloya yeni kayıt ekler.",
        icon: Database,
        color: "text-purple-400",
        bg: "bg-purple-50",
        server: "database",
        approval: "requires",
        example: "employees tablosuna yeni çalışan ekle",
      },
      {
        name: "db_update",
        description: "Tabloda belirli bir kaydı günceller.",
        icon: Database,
        color: "text-purple-400",
        bg: "bg-purple-50",
        server: "database",
        approval: "requires",
        example: "ID=5 çalışanın departmanını güncelle",
      },
      {
        name: "db_delete",
        description: "Tablodan belirli bir kaydı kalıcı siler.",
        icon: Database,
        color: "text-red-500",
        bg: "bg-red-50",
        server: "database",
        approval: "destructive",
        example: "ID=3 kaydını sil",
      },
    ],
  },
  {
    key: "mail_calendar",
    label: "Mail & Takvim",
    description: "Gmail gönderme/okuma ve Google Takvim yönetimi (n8n + OAuth)",
    icon: Mail,
    color: "text-blue-600",
    headerBg: "bg-blue-50 border-blue-200",
    tools: [
      {
        name: "mail_read_inbox",
        description: "Gelen kutusundaki son e-postaları okur.",
        icon: Mail,
        color: "text-blue-500",
        bg: "bg-blue-50",
        server: "mail_calendar",
        approval: "none",
        example: "Son 5 e-postamı göster",
      },
      {
        name: "mail_send",
        description: "Gmail üzerinden e-posta gönderir.",
        icon: Mail,
        color: "text-blue-400",
        bg: "bg-blue-50",
        server: "mail_calendar",
        approval: "requires",
        example: "ali@ornek.com'a 'Toplantı saati' konuluyla mail at",
      },
      {
        name: "mail_extract_meeting",
        description: "E-postadan toplantı linki ve tarih çıkarır.",
        icon: Mail,
        color: "text-blue-500",
        bg: "bg-blue-50",
        server: "mail_calendar",
        approval: "none",
        example: "Son maildeki toplantı bilgilerini çıkar",
      },
      {
        name: "calendar_list_events",
        description: "Google Takvim etkinliklerini listeler.",
        icon: Calendar,
        color: "text-indigo-500",
        bg: "bg-indigo-50",
        server: "mail_calendar",
        approval: "none",
        example: "Bu haftaki takvim etkinliklerimi göster",
      },
      {
        name: "calendar_add_event",
        description: "Google Takvim'e yeni etkinlik ekler.",
        icon: Calendar,
        color: "text-indigo-400",
        bg: "bg-indigo-50",
        server: "mail_calendar",
        approval: "requires",
        example: "Yarın saat 14:00'de 1 saatlik toplantı ekle",
      },
      {
        name: "calendar_delete_event",
        description: "Takvim etkinliğini siler.",
        icon: Calendar,
        color: "text-red-500",
        bg: "bg-red-50",
        server: "mail_calendar",
        approval: "destructive",
        example: "Toplantı etkinliğini sil",
      },
    ],
  },
  {
    key: "code_git",
    label: "Kod & Git/GitHub",
    description: "Docker sandbox'ta kod çalıştırma, lint ve Git/GitHub işlemleri",
    icon: GitFork,
    color: "text-gray-800",
    headerBg: "bg-gray-50 border-gray-200",
    tools: [
      {
        name: "code_run",
        description: "Kodu Docker sandbox içinde güvenle çalıştırır (Python/JS/Bash).",
        icon: Terminal,
        color: "text-green-600",
        bg: "bg-green-50",
        server: "code_git",
        approval: "none",
        example: "sandbox/hesap.py dosyasını çalıştır",
      },
      {
        name: "code_lint",
        description: "Dosyadaki sözdizim ve kalite hatalarını kontrol eder.",
        icon: Code2,
        color: "text-green-500",
        bg: "bg-green-50",
        server: "code_git",
        approval: "none",
        example: "sandbox/script.py'daki lint hatalarını göster",
      },
      {
        name: "git_status",
        description: "Git reposunun değişiklik durumunu gösterir.",
        icon: GitBranch,
        color: "text-gray-700",
        bg: "bg-gray-100",
        server: "code_git",
        approval: "none",
        example: "Repo değişikliklerini göster",
      },
      {
        name: "git_diff_preview",
        description: "Bekleyen değişikliklerin diff özetini gösterir.",
        icon: GitBranch,
        color: "text-gray-600",
        bg: "bg-gray-100",
        server: "code_git",
        approval: "none",
        example: "Son değişikliklerin diffini göster",
      },
      {
        name: "git_create_branch",
        description: "Yeni bir git branch'i oluşturur ve geçiş yapar.",
        icon: GitBranch,
        color: "text-gray-700",
        bg: "bg-gray-100",
        server: "code_git",
        approval: "none",
        example: "feature/yeni-özellik branch'i oluştur",
      },
      {
        name: "git_commit_and_push",
        description: "Commit oluşturur ve uzak repoya push eder.",
        icon: GitCommit,
        color: "text-amber-600",
        bg: "bg-amber-50",
        server: "code_git",
        approval: "requires",
        example: "Tüm değişiklikleri 'Hata düzeltmesi' mesajıyla commit et ve push et",
      },
      {
        name: "github_create_pull_request",
        description: "GitHub'da Pull Request açar.",
        icon: GitFork,
        color: "text-gray-800",
        bg: "bg-gray-100",
        server: "code_git",
        approval: "requires",
        example: "owner/repo reposunda PR aç: 'Yeni özellik'",
      },
    ],
  },
  {
    key: "hr",
    label: "İnsan Kaynakları",
    description: "Personel bilgileri, izin bakiyesi ve izin yönetimi",
    icon: Users,
    color: "text-rose-600",
    headerBg: "bg-rose-50 border-rose-200",
    tools: [
      {
        name: "get_employee_leave_balance",
        description: "Çalışanın izin bakiyesini sorgular.",
        icon: Users,
        color: "text-rose-500",
        bg: "bg-rose-50",
        server: "hr",
        approval: "none",
        example: "Ahmet Yılmaz'ın izin bakiyesini göster",
      },
      {
        name: "get_employees_on_leave",
        description: "Belirli bir tarihte izinli olan çalışanları listeler.",
        icon: Users,
        color: "text-rose-500",
        bg: "bg-rose-50",
        server: "hr",
        approval: "none",
        example: "Bugün izinli çalışanları göster",
      },
      {
        name: "request_leave",
        description: "İzin talebi oluşturur.",
        icon: Users,
        color: "text-rose-400",
        bg: "bg-rose-50",
        server: "hr",
        approval: "requires",
        example: "Ahmet için 3-5 Ağustos arası yıllık izin talebi oluştur",
      },
      {
        name: "approve_leave",
        description: "Bekleyen izin talebini onaylar. (Sadece HR/Admin)",
        icon: Users,
        color: "text-rose-400",
        bg: "bg-rose-50",
        server: "hr",
        approval: "requires",
        example: "İzin talebi #5'i onayla",
      },
    ],
  },
  {
    key: "app",
    label: "Uygulama Kontrolü",
    description: "Masaüstü uygulama açma, kapatma ve listeleme",
    icon: Monitor,
    color: "text-teal-600",
    headerBg: "bg-teal-50 border-teal-200",
    tools: [
      {
        name: "app_open",
        description: "Bir masaüstü uygulamasını açar.",
        icon: Monitor,
        color: "text-teal-500",
        bg: "bg-teal-50",
        server: "app",
        approval: "none",
        example: "Notepad'i aç",
      },
      {
        name: "app_close",
        description: "Çalışan bir uygulamayı kapatır.",
        icon: Monitor,
        color: "text-teal-400",
        bg: "bg-teal-50",
        server: "app",
        approval: "none",
        example: "Notepad'i kapat",
      },
      {
        name: "app_list_running",
        description: "Şu anda çalışan uygulamaları listeler.",
        icon: Monitor,
        color: "text-teal-500",
        bg: "bg-teal-50",
        server: "app",
        approval: "none",
        example: "Çalışan uygulamaları listele",
      },
    ],
  },
  {
    key: "multimodal",
    label: "Ses & Görsel (Faz 6)",
    description: "Whisper STT, Piper TTS, Vision ve Stable Diffusion - yakında aktif",
    icon: Mic,
    color: "text-violet-600",
    headerBg: "bg-violet-50 border-violet-200",
    tools: [
      {
        name: "stt_transcribe",
        description: "Ses dosyasını metne çevirir (Whisper STT).",
        icon: Mic,
        color: "text-violet-500",
        bg: "bg-violet-50",
        server: "multimodal",
        approval: "none",
        example: "ses.wav dosyasını metne çevir",
      },
      {
        name: "tts_speak",
        description: "Metni sese çevirir (Piper TTS).",
        icon: Volume2,
        color: "text-violet-500",
        bg: "bg-violet-50",
        server: "multimodal",
        approval: "none",
        example: "Bu metni sesli oku",
      },
      {
        name: "vision_describe",
        description: "Görsel dosyasını açıklar (qwen2-vl Vision).",
        icon: Eye,
        color: "text-violet-400",
        bg: "bg-violet-50",
        server: "multimodal",
        approval: "none",
        example: "ekran_goruntüsü.png'yi açıkla",
      },
      {
        name: "image_generate",
        description: "Metin açıklamasından görsel üretir (Stable Diffusion).",
        icon: Image,
        color: "text-violet-400",
        bg: "bg-violet-50",
        server: "multimodal",
        approval: "requires",
        example: "Gün batımı manzarasının görselini oluştur",
      },
    ],
  },
];

// ─── Approval badge ────────────────────────────────────────────────────────
function ApprovalBadge({ level }: { level: ApprovalLevel }) {
  if (level === "none") return null;
  if (level === "requires") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
        <Shield size={9} />
        Onay Gerektirir
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200">
      <AlertTriangle size={9} />
      Geri Alınamaz
    </span>
  );
}

// ─── Server status from MCP ────────────────────────────────────────────────
function ServerStatus({ backendUrl, apiKey }: { backendUrl: string; apiKey: string }) {
  const [tools, setTools] = useState<{ name: string; _server: string }[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/mcp/tools`, {
        headers: { "X-API-Key": apiKey },
      });
      if (res.ok) {
        const data = await res.json();
        setTools(data.tools ?? []);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [backendUrl, apiKey]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-brand-gray animate-pulse">
        <RefreshCw size={14} className="animate-spin" />
        MCP durumu yükleniyor…
      </div>
    );
  }

  if (tools.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-red-500">
        <AlertTriangle size={14} />
        Backend'e ulaşılamadı — MCP araçları yüklenemedi
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm text-green-600">
      <CheckCircle2 size={14} />
      {tools.length} araç aktif (MCP bağlantısı sağlıklı)
      <button
        onClick={load}
        className="ml-1 p-0.5 hover:bg-brand-light-gray/50 rounded"
        title="Yenile"
      >
        <RefreshCw size={12} />
      </button>
    </div>
  );
}

// ─── Tool card ────────────────────────────────────────────────────────────
function ToolCard({ tool }: { tool: ToolDef }) {
  const [showExample, setShowExample] = useState(false);
  const Icon = tool.icon;

  return (
    <div className="flex flex-col gap-2 p-4 rounded-xl border border-brand-light-gray bg-brand-white/60 hover:bg-brand-white hover:shadow-soft transition-all group">
      <div className="flex items-start gap-3">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${tool.bg} ${tool.color}`}
        >
          <Icon size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap mb-1">
            <span className="font-mono font-semibold text-sm text-brand-dark">
              {tool.name}
            </span>
            <ApprovalBadge level={tool.approval} />
          </div>
          <p className="text-xs text-brand-gray leading-relaxed">
            {tool.description}
          </p>
        </div>
      </div>

      {tool.example && (
        <div className="mt-1">
          <button
            onClick={() => setShowExample(!showExample)}
            className="flex items-center gap-1 text-xs text-brand-indigo/70 hover:text-brand-indigo transition-colors"
          >
            <Info size={11} />
            {showExample ? "Örneği gizle" : "Örnek göster"}
          </button>
          {showExample && (
            <div className="mt-1.5 p-2.5 rounded-lg bg-brand-indigo/5 border border-brand-indigo/10 text-xs text-brand-dark">
              💬 &ldquo;<em>{tool.example}</em>&rdquo;
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Server group ─────────────────────────────────────────────────────────
function ServerGroupCard({ group }: { group: ServerGroup }) {
  const [expanded, setExpanded] = useState(true);
  const Icon = group.icon;

  return (
    <div className="glass-panel overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full flex items-center justify-between p-4 border-b ${group.headerBg} transition-colors`}
      >
        <div className="flex items-center gap-3">
          <Icon size={18} className={group.color} />
          <div className="text-left">
            <div className="font-bold text-brand-dark text-sm">{group.label}</div>
            <div className="text-xs text-brand-gray">{group.description}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-brand-gray bg-white/80 px-2 py-0.5 rounded-full border border-brand-light-gray">
            {group.tools.length} araç
          </span>
          {expanded ? (
            <ChevronUp size={16} className="text-brand-gray" />
          ) : (
            <ChevronDown size={16} className="text-brand-gray" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {group.tools.map((tool) => (
            <ToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Ana Tools sayfası ────────────────────────────────────────────────────
export function Tools() {
  const { settings } = useChatStore();
  const [search, setSearch] = useState("");

  const filteredGroups = SERVER_GROUPS.map((group) => ({
    ...group,
    tools: group.tools.filter(
      (t) =>
        t.name.toLowerCase().includes(search.toLowerCase()) ||
        t.description.toLowerCase().includes(search.toLowerCase())
    ),
  })).filter((g) => g.tools.length > 0);

  const totalTools = SERVER_GROUPS.reduce((s, g) => s + g.tools.length, 0);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Başlık */}
      <div className="mb-4">
        <h1 className="text-3xl font-bold text-brand-dark flex items-center gap-2">
          <Wrench size={28} className="text-brand-indigo" />
          MCP Araç Gezgini
        </h1>
        <p className="text-brand-gray mt-2">
          Agent'ın kullanabildiği {totalTools} araç, {SERVER_GROUPS.length} MCP server
          üzerinde çalışıyor. Her araç için kullanım örneği görebilirsiniz.
        </p>
      </div>

      {/* MCP Durum + Arama */}
      <div className="glass-panel p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <ServerStatus
          backendUrl={settings.backendUrl}
          apiKey={settings.apiKey}
        />
        <div className="relative w-full sm:w-72">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-brand-gray"
          />
          <input
            type="text"
            placeholder="Araç ara…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-4 py-2 text-sm bg-brand-light-gray/50 border border-brand-light-gray rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-indigo/50 transition-shadow"
          />
        </div>
      </div>

      {/* Onay seviyesi açıklaması */}
      <div className="flex flex-wrap gap-3 text-xs text-brand-gray">
        <span className="flex items-center gap-1.5">
          <CheckCircle2 size={12} className="text-green-500" />
          Onay gerektirmez
        </span>
        <span className="flex items-center gap-1.5">
          <Shield size={12} className="text-amber-500" />
          Kullanıcı onayı gerektirir
        </span>
        <span className="flex items-center gap-1.5">
          <AlertTriangle size={12} className="text-red-500" />
          Geri alınamaz işlem — onay zorunlu
        </span>
      </div>

      {/* Server grupları */}
      <div className="space-y-4">
        {filteredGroups.length > 0 ? (
          filteredGroups.map((group) => (
            <ServerGroupCard key={group.key} group={group} />
          ))
        ) : (
          <div className="glass-panel p-12 text-center text-brand-gray">
            <Search size={32} className="mx-auto mb-3 opacity-30" />
            <p>"{search}" için araç bulunamadı.</p>
          </div>
        )}
      </div>
    </div>
  );
}
