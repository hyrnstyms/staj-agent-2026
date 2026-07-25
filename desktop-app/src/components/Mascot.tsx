import mascotImg from '../assets/maskot.png';

interface MascotProps {
  className?: string;
  status?: 'idle' | 'thinking' | 'working' | 'listening' | 'success' | 'warning';
}

export function Mascot({ className = "", status = 'idle' }: MascotProps) {
  const opacity = status === 'listening' ? 'opacity-75' : 'opacity-100';
  return (
    <div className={`flex items-center justify-center rounded-xl overflow-hidden shadow-sm border border-brand-indigo/10 ${opacity} ${className} bg-brand-indigo/5`}>
      <img src={mascotImg} alt="Pingo AI Mascot" className="w-full h-full object-cover" />
    </div>
  );
}
