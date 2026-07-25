import { Wrench, Terminal, FileCode2, Globe, Database, Network } from "lucide-react";

const AVAILABLE_TOOLS = [
  {
    name: "bash",
    description: "Sistemde komut çalıştırmak için kullanılır. (Örn: ls, npm install)",
    icon: Terminal,
    color: "text-blue-500",
    bg: "bg-blue-500/10"
  },
  {
    name: "file_read",
    description: "Belirtilen dosyanın içeriğini okur ve analiz eder.",
    icon: FileCode2,
    color: "text-orange-500",
    bg: "bg-orange-500/10"
  },
  {
    name: "file_write",
    description: "Yeni bir dosya oluşturur veya var olan dosyayı değiştirir.",
    icon: FileCode2,
    color: "text-green-500",
    bg: "bg-green-500/10"
  },
  {
    name: "web_search",
    description: "İnternette bilgi arar ve güncel sonuçları döndürür.",
    icon: Globe,
    color: "text-indigo-500",
    bg: "bg-indigo-500/10"
  },
  {
    name: "sqlite_query",
    description: "Veritabanı üzerinde SQL sorguları çalıştırır.",
    icon: Database,
    color: "text-purple-500",
    bg: "bg-purple-500/10"
  },
  {
    name: "api_fetch",
    description: "Harici API'lara HTTP istekleri gönderir (GET/POST).",
    icon: Network,
    color: "text-pink-500",
    bg: "bg-pink-500/10"
  }
];

export function Tools() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-dark flex items-center gap-2">
          <Wrench size={28} className="text-brand-indigo" />
          MCP Araç Gezgini (Tools)
        </h1>
        <p className="text-brand-gray mt-2">
          Agent'ın kullanabildiği araçlar (Model Context Protocol). Sisteminizdeki yetenekleri genişletmek için yeni araçlar entegre edebilirsiniz.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {AVAILABLE_TOOLS.map((tool, idx) => {
          const Icon = tool.icon;
          return (
            <div key={idx} className="glass-panel p-6 flex gap-4 hover:-translate-y-1 transition-transform cursor-default">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${tool.bg} ${tool.color}`}>
                <Icon size={24} />
              </div>
              <div>
                <h3 className="font-bold text-brand-dark mb-1">{tool.name}</h3>
                <p className="text-sm text-brand-gray leading-relaxed">{tool.description}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  );
}
