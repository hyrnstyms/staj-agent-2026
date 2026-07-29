import { useState, useEffect, useCallback } from "react";
import { useChatStore } from "../store/chatStore";
import { toast } from "sonner";
import {
  Save,
  Server,
  Volume2,
  ShieldAlert,
  GitFork,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ExternalLink,
  GitBranch,
  Lock,
} from "lucide-react";

// ─── Google OAuth status type ──────────────────────────────────────────────
interface GoogleStatus {
  connected: boolean;
  google_email?: string;
  is_valid?: boolean;
  expires_at?: string;
  scopes?: string;
}

// ─── GitHub status type ────────────────────────────────────────────────────
interface GitHubStatus {
  connected: boolean;
  username?: string;
  scopes?: string;
  message: string;
}

interface GitHubRepo {
  full_name: string;
  description?: string;
  private: boolean;
  html_url: string;
  default_branch: string;
}

// ─── Status Badge ──────────────────────────────────────────────────────────
function StatusBadge({
  connected,
  label,
}: {
  connected: boolean | null;
  label: string;
}) {
  if (connected === null) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-600 animate-pulse">
        <RefreshCw size={11} className="animate-spin" />
        Kontrol ediliyor…
      </span>
    );
  }
  if (connected) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-green-50 text-green-700 border border-green-200">
        <CheckCircle2 size={12} />
        {label}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-red-50 text-red-600 border border-red-200">
      <XCircle size={12} />
      Bağlı Değil
    </span>
  );
}

// ─── Google Integration Card ───────────────────────────────────────────────
function GoogleIntegrationCard({
  backendUrl,
  apiKey,
}: {
  backendUrl: string;
  apiKey: string;
}) {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const checkStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/auth/google/status?user_id=1`, {
        headers: { "X-API-Key": apiKey },
      });
      const data = await res.json();
      setStatus(data);
    } catch {
      setStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  }, [backendUrl, apiKey]);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const handleConnect = () => {
    const url = `${backendUrl}/auth/google/connect?user_id=1&api_key=${apiKey}`;
    window.open(url, "_blank");
    // Bağlantı sonrası durumu otomatik yenile
    setTimeout(checkStatus, 3000);
  };

  const handleDisconnect = async () => {
    try {
      const res = await fetch(
        `${backendUrl}/auth/google/disconnect?user_id=1`,
        {
          method: "DELETE",
          headers: { "X-API-Key": apiKey },
        }
      );
      if (res.ok) {
        toast.success("Google hesabı bağlantısı kesildi.");
        setStatus({ connected: false });
      } else {
        toast.error("Bağlantı kesilemedi.");
      }
    } catch {
      toast.error("Bağlantı kesilemedi.");
    }
  };

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-brand-dark-gray">
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              fill="#EA4335"
            />
          </svg>
          <h2 className="text-lg font-bold">Google Entegrasyonu</h2>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            connected={status === null ? null : status.connected}
            label={status?.google_email ?? "Bağlı"}
          />
          <button
            onClick={checkStatus}
            disabled={loading}
            className="p-1.5 rounded-lg hover:bg-brand-light-gray/50 text-brand-gray transition-colors"
            title="Yenile"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      <p className="text-sm text-brand-gray mb-4">
        Google hesabı bağlayarak asistanın sizin adınıza e-posta göndermesine
        ve takvim etkinliklerini yönetmesine izin verin.
      </p>

      {status?.connected && (
        <div className="mb-4 p-3 rounded-xl bg-green-50 border border-green-100 text-sm text-green-800 space-y-1">
          <div className="font-medium">✓ Bağlı Hesap: {status.google_email}</div>
          {status.expires_at && (
            <div className="text-xs text-green-600">
              Token geçerlilik: {new Date(status.expires_at).toLocaleString("tr-TR")}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleConnect}
          className="bg-brand-white border border-brand-light-gray hover:bg-brand-light-gray/50 text-brand-dark px-4 py-2 rounded-xl font-medium transition-colors shadow-soft flex items-center gap-2"
        >
          <ExternalLink size={14} />
          {status?.connected ? "Yeniden Bağlan" : "Google ile Bağlan"}
        </button>

        {status?.connected && (
          <button
            onClick={handleDisconnect}
            className="text-red-600 hover:bg-red-50 px-4 py-2 rounded-xl font-medium transition-colors border border-red-200"
          >
            Bağlantıyı Kes
          </button>
        )}
      </div>

      <div className="flex items-start gap-2 mt-3 text-xs text-brand-gray bg-brand-light-gray/20 p-2.5 rounded-lg border border-brand-light-gray/50">
        <ShieldAlert size={14} className="text-brand-gray shrink-0 mt-0.5" />
        <p>
          Bağlantıdan sonra "yenile" butonuna tıklayarak durumu teyit edin.
          Token, backend tarafından otomatik yenilenir.
        </p>
      </div>
    </div>
  );
}

// ─── GitHub Integration Card ───────────────────────────────────────────────
function GitHubIntegrationCard({
  backendUrl,
  apiKey,
}: {
  backendUrl: string;
  apiKey: string;
}) {
  const [status, setStatus] = useState<GitHubStatus | null>(null);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [allowedRepos, setAllowedRepos] = useState<string[]>([]);
  const [showRepos, setShowRepos] = useState(false);
  const [loading, setLoading] = useState(false);

  const checkStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${backendUrl}/integrations/github/status`, {
        headers: { "X-API-Key": apiKey },
      });
      const data = await res.json();
      setStatus(data);
    } catch {
      setStatus({ connected: false, message: "Backend'e ulaşılamadı." });
    } finally {
      setLoading(false);
    }
  }, [backendUrl, apiKey]);

  const loadRepos = async () => {
    if (repos.length > 0) {
      setShowRepos(!showRepos);
      return;
    }
    try {
      const [repoRes, allowedRes] = await Promise.all([
        fetch(`${backendUrl}/integrations/github/repos`, {
          headers: { "X-API-Key": apiKey },
        }),
        fetch(`${backendUrl}/integrations/github/allowed-repos`, {
          headers: { "X-API-Key": apiKey },
        }),
      ]);
      if (repoRes.ok) {
        const data = await repoRes.json();
        setRepos(data.repos ?? []);
      }
      if (allowedRes.ok) {
        const data = await allowedRes.json();
        setAllowedRepos(data.allowed_repos ?? []);
      }
      setShowRepos(true);
    } catch {
      toast.error("Repolar yüklenemedi.");
    }
  };

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-brand-dark-gray">
          <GitFork size={20} className="text-brand-dark" />
          <h2 className="text-lg font-bold">GitHub Entegrasyonu</h2>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            connected={status === null ? null : status.connected}
            label={status?.username ? `@${status.username}` : "Bağlı"}
          />
          <button
            onClick={checkStatus}
            disabled={loading}
            className="p-1.5 rounded-lg hover:bg-brand-light-gray/50 text-brand-gray transition-colors"
            title="Yenile"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      <p className="text-sm text-brand-gray mb-4">
        GitHub Personal Access Token (PAT) ile bağlanarak git commit, push ve
        Pull Request işlemleri yapabilirsiniz. Token, backend{" "}
        <code className="font-mono bg-brand-light-gray/50 px-1 rounded">.env</code>{" "}
        dosyasındaki{" "}
        <code className="font-mono bg-brand-light-gray/50 px-1 rounded">GITHUB_TOKEN</code>{" "}
        değişkeninde saklanır.
      </p>

      {status?.connected ? (
        <div className="mb-4 p-3 rounded-xl bg-green-50 border border-green-100 text-sm text-green-800 space-y-1">
          <div className="font-medium">✓ Kullanıcı: @{status.username}</div>
          {status.scopes && (
            <div className="text-xs text-green-600">
              Yetkiler: {status.scopes}
            </div>
          )}
        </div>
      ) : (
        status && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-100 text-sm text-red-700">
            {status.message}
          </div>
        )
      )}

      <div className="flex flex-wrap gap-3 mb-4">
        {status?.connected && (
          <button
            onClick={loadRepos}
            className="bg-brand-white border border-brand-light-gray hover:bg-brand-light-gray/50 text-brand-dark px-4 py-2 rounded-xl font-medium transition-colors shadow-soft flex items-center gap-2"
          >
            <GitBranch size={14} />
            {showRepos ? "Repoları Gizle" : "Repoları Listele"}
          </button>
        )}
      </div>

      {/* Repo listesi */}
      {showRepos && repos.length > 0 && (
        <div className="mt-2 space-y-2 max-h-64 overflow-y-auto pr-1">
          <div className="text-xs font-medium text-brand-gray mb-2 flex items-center gap-1">
            <GitBranch size={11} />
            {repos.length} repo bulundu
          </div>
          {repos.map((repo) => (
            <a
              key={repo.full_name}
              href={repo.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between p-3 rounded-xl border border-brand-light-gray bg-brand-white/50 hover:bg-brand-light-gray/30 transition-colors group"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  {repo.private && <Lock size={11} className="text-brand-gray shrink-0" />}
                  <span className="font-medium text-sm text-brand-dark truncate">
                    {repo.full_name}
                  </span>
                </div>
                {repo.description && (
                  <p className="text-xs text-brand-gray mt-0.5 truncate">
                    {repo.description}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0 ml-2">
                <span className="text-xs text-brand-gray bg-brand-light-gray/50 px-2 py-0.5 rounded-full">
                  {repo.default_branch}
                </span>
                <ExternalLink
                  size={12}
                  className="text-brand-gray opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </div>
            </a>
          ))}
        </div>
      )}

      {/* İzin verilen repolar */}
      {allowedRepos.length > 0 && showRepos && (
        <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-100">
          <div className="text-xs font-medium text-amber-800 mb-1.5">
            Sistemde İzin Verilen Repolar (ALLOWED_REPOS)
          </div>
          {allowedRepos.map((r) => (
            <div
              key={r}
              className="font-mono text-xs text-amber-700 bg-amber-100/60 px-2 py-1 rounded mt-1"
            >
              {r}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-start gap-2 mt-4 text-xs text-brand-gray bg-brand-light-gray/20 p-2.5 rounded-lg border border-brand-light-gray/50">
        <ShieldAlert size={14} className="text-status-yellow shrink-0 mt-0.5" />
        <p>
          Token'ı değiştirmek için backend{" "}
          <strong>.env</strong> dosyasındaki{" "}
          <code className="font-mono">GITHUB_TOKEN</code> değerini güncelleyin
          ve backend'i yeniden başlatın. Aynı şekilde{" "}
          <code className="font-mono">ALLOWED_REPOS</code> ile hangi
          repo dizinlerine izin verildiğini belirleyin.
        </p>
      </div>
    </div>
  );
}

// ─── Ana Settings sayfası ─────────────────────────────────────────────────
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
        <p className="text-brand-gray mt-2">
          Sistem bağlantılarını ve uygulama tercihlerini yapılandırın.
        </p>
      </div>

      <div className="grid gap-6">
        {/* Bağlantı Ayarları */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-4 text-brand-dark-gray">
            <Server size={20} className="text-brand-indigo" />
            <h2 className="text-lg font-bold">Bağlantı Ayarları</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-brand-dark-gray mb-1">
                Backend URL
              </label>
              <input
                type="text"
                value={local.backendUrl}
                onChange={(e) =>
                  setLocal({ ...local, backendUrl: e.target.value })
                }
                className="w-full bg-brand-light-gray/50 border border-brand-light-gray rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-indigo/50 transition-shadow"
                placeholder="http://localhost:8000"
              />
              <p className="text-xs text-brand-gray mt-1">
                Yerel ağdaki FastAPI backend adresi.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-brand-dark-gray mb-1">
                API Key (Geçici Auth)
              </label>
              <input
                type="password"
                value={local.apiKey}
                onChange={(e) => setLocal({ ...local, apiKey: e.target.value })}
                className="w-full bg-brand-light-gray/50 border border-brand-light-gray rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-indigo/50 transition-shadow font-mono"
              />
              <div className="flex items-start gap-2 mt-2 text-xs text-brand-gray bg-status-yellow/10 p-2.5 rounded-lg border border-status-yellow/20">
                <ShieldAlert
                  size={14}
                  className="text-status-yellow shrink-0 mt-0.5"
                />
                <p>
                  Yalnızca backend'e bağlanmak için kullanılan geliştirme
                  anahtarıdır. GitHub veya diğer servislerin gerçek token'ları{" "}
                  <strong>.env</strong> dosyasında barındırılır.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Google Entegrasyonu */}
        <GoogleIntegrationCard
          backendUrl={local.backendUrl}
          apiKey={local.apiKey}
        />

        {/* GitHub Entegrasyonu */}
        <GitHubIntegrationCard
          backendUrl={local.backendUrl}
          apiKey={local.apiKey}
        />

        {/* Ses ve Bildirimler */}
        <div className="glass-panel p-6">
          <div className="flex items-center gap-2 mb-4 text-brand-dark-gray">
            <Volume2 size={20} className="text-brand-indigo" />
            <h2 className="text-lg font-bold">Ses ve Bildirimler</h2>
          </div>

          <div className="flex items-center justify-between p-4 border border-brand-light-gray rounded-xl bg-brand-white/50">
            <div>
              <div className="font-medium text-brand-dark">TTS (Sesli Cevap)</div>
              <div className="text-xs text-brand-gray mt-0.5">
                Asistanın verdiği cevapları otomatik olarak sesli oku.
              </div>
            </div>

            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={local.ttsEnabled}
                onChange={(e) =>
                  setLocal({ ...local, ttsEnabled: e.target.checked })
                }
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
