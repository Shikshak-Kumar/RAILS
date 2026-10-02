import { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  ArrowLeftRight,
  Bot,
  FolderOpen,
  FileText,
  FlaskConical,
  ShieldCheck,
  Menu,
  X,
  Activity,
} from 'lucide-react';

export type PageId =
  | 'dashboard'
  | 'transactions'
  | 'copilot'
  | 'cases'
  | 'reports'
  | 'simulation';

interface Props {
  current: PageId;
  onNavigate: (page: PageId) => void;
  children: React.ReactNode;
}

const navItems: { id: PageId; label: string; icon: React.ComponentType<{ className?: string }>; badge?: string }[] = [
  { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
  { id: 'transactions', label: 'Transactions', icon: ArrowLeftRight },
  { id: 'copilot', label: 'Risk Copilot', icon: Bot },
  { id: 'cases', label: 'Cases', icon: FolderOpen, badge: '34' },
  { id: 'reports', label: 'Regulatory Reports', icon: FileText, badge: '12' },
  { id: 'simulation', label: 'Simulation Lab', icon: FlaskConical },
];

export function AppShell({ current, onNavigate, children }: Props) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const handleNav = (page: PageId) => {
    onNavigate(page);
    setMobileOpen(false);
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex">
      {/* Sidebar - Desktop */}
      <aside className="hidden lg:flex w-64 flex-col border-r border-neutral-800 bg-neutral-950 fixed h-screen z-30">
        <SidebarContent current={current} onNavigate={handleNav} />
      </aside>

      {/* Sidebar - Mobile */}
      {mobileOpen && (
        <>
          <div className="fixed inset-0 bg-black/60 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
          <aside className="fixed left-0 top-0 h-screen w-64 bg-neutral-950 border-r border-neutral-800 z-50 lg:hidden">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute top-4 right-4 text-neutral-400 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent current={current} onNavigate={handleNav} />
          </aside>
        </>
      )}

      {/* Main content */}
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-neutral-800 bg-neutral-950/95 backdrop-blur-sm px-4 lg:px-6 h-14">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden text-neutral-400 hover:text-white"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-green-500 animate-pulse" />
              <span className="text-xs text-neutral-400 hidden sm:inline">Live monitoring</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-xs text-neutral-500 tabular-nums hidden sm:inline">
              {time.toLocaleTimeString('en-US', { hour12: false })}
            </span>
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-full bg-neutral-700 flex items-center justify-center text-xs font-bold text-neutral-200">
                RS
              </div>
              <span className="text-sm font-medium hidden sm:inline">Risk Analyst</span>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-6 overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
}

function SidebarContent({
  current,
  onNavigate,
}: {
  current: PageId;
  onNavigate: (page: PageId) => void;
}) {
  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 h-14 border-b border-neutral-800">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white">
          <ShieldCheck className="h-5 w-5 text-black" />
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-white">RAILS</div>
          <div className="text-[10px] text-neutral-500 -mt-0.5">Risk Sentinel</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = current === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active
                  ? 'bg-white text-black'
                  : 'text-neutral-400 hover:text-white hover:bg-neutral-900'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && (
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    active ? 'bg-black text-white' : 'bg-yellow-500/20 text-yellow-400'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-neutral-800 px-5 py-3">
        <div className="text-[10px] text-neutral-600">
          <div>ML Models: 5 active</div>
          <div className="mt-0.5">DB: 3.1M transactions</div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
            <span className="text-green-500">All systems operational</span>
          </div>
        </div>
      </div>
    </>
  );
}
