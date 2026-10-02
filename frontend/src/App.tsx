import { useState, useEffect } from 'react';
import { AppShell, type PageId } from '@/components/AppShell';
import { DashboardPage } from '@/pages/DashboardPage';
import { TransactionsPage } from '@/pages/TransactionsPage';
import { CopilotPage } from '@/pages/CopilotPage';
import { AutomationPage } from '@/pages/AutomationPage';
import { CasesPage } from '@/pages/CasesPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { SimulationPage } from '@/pages/SimulationPage';

const VALID_PAGES: PageId[] = [
  'dashboard',
  'transactions',
  'copilot',
  'automation',
  'cases',
  'reports',
  'simulation',
];

function getInitialPage(): PageId {
  const hash = window.location.hash.replace(/^#\/?/, '') as PageId;
  if (VALID_PAGES.includes(hash)) {
    return hash;
  }
  const stored = localStorage.getItem('rails_active_page') as PageId;
  if (VALID_PAGES.includes(stored)) {
    return stored;
  }
  return 'dashboard';
}

function App() {
  const [page, setPageState] = useState<PageId>(getInitialPage);

  const setPage = (newPage: PageId) => {
    setPageState(newPage);
    window.location.hash = `#/${newPage}`;
    localStorage.setItem('rails_active_page', newPage);
  };

  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.replace(/^#\/?/, '') as PageId;
      if (VALID_PAGES.includes(hash) && hash !== page) {
        setPageState(hash);
        localStorage.setItem('rails_active_page', hash);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [page]);

  return (
    <AppShell current={page} onNavigate={setPage}>
      {page === 'dashboard' && <DashboardPage onNavigate={setPage} />}
      {page === 'transactions' && <TransactionsPage />}
      {page === 'copilot' && <CopilotPage />}
      {page === 'automation' && <AutomationPage />}
      {page === 'cases' && <CasesPage />}
      {page === 'reports' && <ReportsPage />}
      {page === 'simulation' && <SimulationPage />}
    </AppShell>
  );
}

export default App;
