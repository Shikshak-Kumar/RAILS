import { useState } from 'react';
import { AppShell, type PageId } from '@/components/AppShell';
import { DashboardPage } from '@/pages/DashboardPage';
import { TransactionsPage } from '@/pages/TransactionsPage';
import { CopilotPage } from '@/pages/CopilotPage';
import { CasesPage } from '@/pages/CasesPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { SimulationPage } from '@/pages/SimulationPage';

function App() {
  const [page, setPage] = useState<PageId>('dashboard');

  return (
    <AppShell current={page} onNavigate={setPage}>
      {page === 'dashboard' && <DashboardPage onNavigate={setPage} />}
      {page === 'transactions' && <TransactionsPage />}
      {page === 'copilot' && <CopilotPage />}
      {page === 'cases' && <CasesPage />}
      {page === 'reports' && <ReportsPage />}
      {page === 'simulation' && <SimulationPage />}
    </AppShell>
  );
}

export default App;
