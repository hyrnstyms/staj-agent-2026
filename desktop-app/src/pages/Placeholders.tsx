import { Construction } from "lucide-react";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-brand-gray animate-in fade-in duration-500">
       <Construction size={48} className="mb-4 opacity-50" />
       <h2 className="text-xl font-bold text-brand-dark-gray">{title}</h2>
       <p className="text-sm mt-2">Bu sayfa yapım aşamasındadır.</p>
    </div>
  );
}

// Re-export for specific routes
export const Projects = () => <PlaceholderPage title="Proje Yönetimi" />;
export const Data = () => <PlaceholderPage title="Veri Yönetimi" />;
