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
  Cpu,
} from 'lucide-react';
import { api } from '@/lib/api';

export type PageId =
  | 'dashboard'
  | 'transactions'
  | 'copilot'
  | 'cases'
  | 'reports'
  | 'simulation'
  | 'automation';

interface Props {
  current: PageId;
  onNavigate: (page: PageId) => void;
  children: React.ReactNode;
}

const navDefinitions: { id: PageId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
  { id: 'transactions', label: 'Transactions', icon: ArrowLeftRight },
  { id: 'copilot', label: 'Risk Copilot', icon: Bot },
  { id: 'automation', label: 'Automation', icon: Cpu },
  { id: 'cases', label: 'Cases', icon: FolderOpen },
  { id: 'reports', label: 'Regulatory Reports', icon: FileText },
  { id: 'simulation', label: 'Simulation Lab', icon: FlaskConical },
];


export function AppShell({ current, onNavigate, children }: Props) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [time, setTime] = useState(new Date());
  const [caseCount, setCaseCount] = useState<number>(() => {
    return Number(localStorage.getItem('rails_cached_case_count')) || 0;
  });
  const [reportCount, setReportCount] = useState<number>(() => {
    return Number(localStorage.getItem('rails_cached_report_count')) || 0;
  });
  const [totalTx, setTotalTx] = useState<number>(() => {
    return Number(localStorage.getItem('rails_cached_total_tx')) || 0;
  });

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const refreshCounts = () => {
    api.getOverview()
      .then((data) => {
        const cases = data.count_cases || data.open_cases || 0;
        const reports = data.count_reports || 0;
        setCaseCount(cases);
        setReportCount(reports);
        localStorage.setItem('rails_cached_case_count', String(cases));
        localStorage.setItem('rails_cached_report_count', String(reports));
        if (data.total_transactions) {
          setTotalTx(data.total_transactions);
          localStorage.setItem('rails_cached_total_tx', String(data.total_transactions));
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    refreshCounts();
  }, []);


  const handleNav = (page: PageId) => {
    onNavigate(page);
    setMobileOpen(false);
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex">
      
      <aside className="hidden lg:flex w-64 flex-col border-r border-neutral-800 bg-neutral-950 fixed h-screen z-30">
        <SidebarContent
          current={current}
          onNavigate={handleNav}
          caseCount={caseCount}
          reportCount={reportCount}
          totalTx={totalTx}
        />
      </aside>

      
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
            <SidebarContent
              current={current}
              onNavigate={handleNav}
              caseCount={caseCount}
              reportCount={reportCount}
              totalTx={totalTx}
            />
          </aside>
        </>
      )}

      
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        
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
  caseCount,
  reportCount,
  totalTx,
}: {
  current: PageId;
  onNavigate: (page: PageId) => void;
  caseCount: number;
  reportCount: number;
  totalTx: number;
}) {
  const formattedTx = totalTx >= 1000000
    ? `${(totalTx / 1000000).toFixed(1)}M`
    : totalTx.toLocaleString();

  return (
    <>
      
      <div className="flex items-center gap-3 px-5 h-14 border-b border-neutral-800">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white">
          <ShieldCheck className="h-5 w-5 text-black" />
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-white">Risk Analysis</div>
        </div>
      </div>

      
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navDefinitions.map((item) => {
          const Icon = item.icon;
          const active = current === item.id;
          let badge: string | null = null;
          if (item.id === 'cases' && caseCount > 0) {
            badge = String(caseCount);
          } else if (item.id === 'reports' && reportCount > 0) {
            badge = String(reportCount);
          }

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
              {badge && (
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    active ? 'bg-black text-white' : 'bg-yellow-500/20 text-yellow-400'
                  }`}
                >
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      
      <div className="border-t border-neutral-800 px-5 py-3">
        <div className="text-[10px] text-neutral-600">
          <div>ML Models: 5 active</div>
          <div className="mt-0.5">DB: {totalTx > 0 ? formattedTx : '...'} transactions</div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
            <span className="text-green-500">All systems operational</span>
          </div>
        </div>
      </div>
    </>
  );
}
