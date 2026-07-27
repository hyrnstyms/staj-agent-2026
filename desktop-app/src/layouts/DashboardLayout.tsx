import { ReactNode } from "react";
import { Link, useLocation } from "wouter";
import { 
  Home, MessageSquare, Mic, FolderKanban, Box, 
  Wrench, Database, Settings, Activity, ShieldAlert,
  Mic2, Radio
} from "lucide-react";
import { ChatComposer } from "../components/ChatComposer";
import { Mascot } from "../components/Mascot";
import { StatusPanel } from "../components/StatusPanel";
import { useWakeWord } from "../hooks/useWakeWord";

interface Props {
  children: ReactNode;
}

export function DashboardLayout({ children }: Props) {
  const [location] = useLocation();
  const { enabled: isListening, state, toggle: toggleListening } = useWakeWord();

const NAV_ITEMS = [
  { icon: Home, label: "Ana Sayfa", href: "/" },
  { icon: MessageSquare, label: "Sohbet", href: "/chat" },
  { icon: Mic, label: "Sesli Komutlar", href: "/voice" },
  { icon: FolderKanban, label: "Projeler", href: "/projects" },
  { icon: Box, label: "Modeller", href: "/models" },
  { icon: Wrench, label: "Araçlar", href: "/tools" },
  { icon: Database, label: "Veri", href: "/data" },
  { icon: ShieldAlert, label: "Yetkiler", href: "/permissions" },
  { icon: Activity, label: "Loglar", href: "/logs" },
  { icon: Settings, label: "Ayarlar", href: "/settings" },
];

  return (
    <div className="flex h-screen bg-brand-white text-brand-dark-gray overflow-hidden">
      
      {/* Sidebar */}
      <aside className="w-64 flex flex-col bg-white border-r border-brand-light-gray shadow-soft z-20 shrink-0">
        <div className="p-6 flex items-center gap-3 border-b border-brand-light-gray">
          <Mascot className="w-10 h-10" />
          <div>
            <h1 className="font-bold text-lg text-brand-dark leading-tight">PINGO AI</h1>
            <span className="text-[10px] text-brand-gray font-bold bg-brand-light-gray px-2 py-0.5 rounded-full uppercase tracking-wider">v1.0.0</span>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            const isActive = location === item.href;
            return (
              <Link key={item.href} href={item.href}>
                <a className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors duration-200 ${
                  isActive 
                  ? 'bg-brand-indigo/10 text-brand-indigo font-semibold' 
                  : 'text-brand-dark-gray hover:bg-brand-light-gray/50 hover:text-brand-dark'
                }`}>
                  <Icon size={18} className={isActive ? 'text-brand-indigo' : 'text-brand-gray'} />
                  {item.label}
                </a>
              </Link>
            )
          })}
        </nav>

        {/* Microphone Panel */}
        <div className="p-4 border-t border-brand-light-gray">
          <div 
            className="bg-brand-dark text-white rounded-xl p-4 relative overflow-hidden shadow-soft cursor-pointer hover:bg-brand-dark/90 transition-colors"
            onClick={toggleListening}
          >
            <div className="absolute top-0 right-0 p-2 opacity-10">
              <Mic2 size={48} />
            </div>
            <div className="flex items-center gap-2 mb-2">
              <Radio size={14} className={isListening ? "text-status-green animate-pulse" : "text-brand-gray"} />
              <span className={`text-[10px] font-bold tracking-widest uppercase ${isListening ? "text-status-green" : "text-brand-gray"}`}>
                {state === 'idle' ? 'Kapalı' : state === 'listening' ? 'Dinleniyor' : state === 'wake_detected' ? 'Algılandı!' : state === 'command_listening' ? 'Komut Dinleniyor' : 'Hata'}
              </span>
            </div>
            <div className="text-sm font-medium mb-1">Hey Asistan</div>
            <div className="flex items-end gap-[3px] h-3 mt-2">
               {[...Array(6)].map((_, i) => (
                 <div 
                   key={i} 
                   className={`w-1 rounded-full ${isListening ? "bg-brand-indigo animate-pulse" : "bg-brand-gray/30"}`} 
                   style={isListening ? { height: `${20 + Math.random() * 80}%`, animationDelay: `${i*150}ms` } : { height: '20%' }} 
                 />
               ))}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-brand-white/50">
        <div className="flex-1 overflow-y-auto p-8 pb-32">
          <div className="max-w-6xl mx-auto w-full">
            {children}
          </div>
        </div>
        
        {/* Fixed Bottom Chat Composer */}
        <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-brand-white via-brand-white to-transparent pointer-events-none z-10">
           <div className="pointer-events-auto max-w-4xl mx-auto w-full">
              <ChatComposer />
           </div>
        </div>
      </main>

      {/* Right Status Panel */}
      <StatusPanel />

    </div>
  );
}
