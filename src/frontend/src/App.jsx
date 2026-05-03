import React, { useState, useEffect, lazy, Suspense } from 'react';
import useKeyboardShortcuts from './hooks/useKeyboardShortcuts';
import { ThemeProvider } from './hooks/useTheme.jsx';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import StatusBar from './components/layout/StatusBar';
import OfflineBanner from './components/layout/OfflineBanner';
import Toaster from './components/layout/Toaster';
// Eager: dashboard + alchemi (default landing) + lightweight panels
import DashboardPanel from './components/simulation/DashboardPanel';
import AlchemiPanel from './components/ai/AlchemiPanel';

// Lazy: every other panel — keeps initial bundle small (Electron cold-start)
const EISPanel              = lazy(() => import('./components/simulation/EISPanel'));
const CVPanel               = lazy(() => import('./components/simulation/CVPanel'));
const BatteryPanel          = lazy(() => import('./components/simulation/BatteryPanel'));
const GCDPanel              = lazy(() => import('./components/simulation/GCDPanel'));
const DRTPanel              = lazy(() => import('./components/simulation/DRTPanel'));
const CircuitFittingPanel   = lazy(() => import('./components/simulation/CircuitFittingPanel'));
const ToolkitPanel          = lazy(() => import('./components/simulation/ToolkitPanel'));
const DataImportPanel       = lazy(() => import('./components/data/DataImportPanel'));
const MaterialsExplorer     = lazy(() => import('./components/materials/MaterialsExplorer'));
const AlchemistCanvas       = lazy(() => import('./components/materials/AlchemistCanvas'));
const BiosensorPanel        = lazy(() => import('./components/simulation/BiosensorPanel'));
const LiteratureMiningPanel = lazy(() => import('./components/research/LiteratureMiningPanel'));
const ValidationPanel       = lazy(() => import('./components/research/ValidationPanel'));
const UserProfilePanel      = lazy(() => import('./components/user/UserProfilePanel'));
const WorkspacePanel        = lazy(() => import('./components/workspace/WorkspacePanel'));
const ReportsPanel          = lazy(() => import('./components/reports/ReportsPanel'));
const LabDataPanel          = lazy(() => import('./components/lab/LabDataPanel'));

// Backend URL — uses Electron preload bridge or fallback
const BACKEND_URL = window.raman ? null : 'http://127.0.0.1:8000';

const PANELS = {
  dashboard:  { label: 'Dashboard',          component: DashboardPanel },
  alchemi:    { label: 'Materials AI',        component: AlchemiPanel },
  alchemist_canvas: { label: 'Alchemist Canvas', component: AlchemistCanvas },
  biosensor:  { label: 'Biosensor Fab',       component: BiosensorPanel },
  literature: { label: 'Literature Mining',   component: LiteratureMiningPanel },
  eis:        { label: 'EIS',                 component: EISPanel },
  cv:         { label: 'Cyclic Voltammetry',  component: CVPanel },
  battery:    { label: 'Battery',             component: BatteryPanel },
  gcd:        { label: 'GCD',                 component: GCDPanel },
  drt:        { label: 'DRT Analysis',        component: DRTPanel },
  circuit:    { label: 'Circuit Fitting',     component: CircuitFittingPanel },
  toolkit:    { label: 'Toolkit',             component: ToolkitPanel },
  materials:  { label: 'Materials Database',  component: MaterialsExplorer },
  data:       { label: 'Data Import',         component: DataImportPanel },
  lab:        { label: 'Lab Data',             component: LabDataPanel },
  validation: { label: 'Paper Validation',    component: ValidationPanel },
  workspace:  { label: 'Workspace',           component: WorkspacePanel },
  reports:    { label: 'Reports',             component: ReportsPanel },
  profile:    { label: 'User Profile',        component: UserProfilePanel },
};

function AppContent() {
  const [activePanel, setActivePanel] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [backendStatus, setBackendStatus] = useState('connecting');
  const [licenseInfo, setLicenseInfo] = useState(null);
  const [nimConfigured, setNimConfigured] = useState(null);

  useKeyboardShortcuts(setActivePanel, () => setSidebarCollapsed(c => !c));

  const ActiveComponent = PANELS[activePanel]?.component || DashboardPanel;

  useEffect(() => {
    const nav = (e) => setActivePanel(e.detail);
    window.addEventListener('NAVIGATE_PANEL', nav);

    let aborted = false;
    const probe = async () => {
      try {
        const api = window.raman?.api;
        const get = (p) => api ? api.get(p) : fetch(`${BACKEND_URL}${p}`).then(r => r.ok ? r.json() : Promise.reject(r));
        await get('/api/health');
        if (aborted) return;
        setBackendStatus('connected');
        // Pull license + NIM status (these are lightweight; no auth needed).
        try { setLicenseInfo(await get('/api/v2/auth/license')); } catch { /* ignore */ }
        try { const s = await get('/api/v2/alchemi/status'); setNimConfigured(!!s?.configured); }
          catch { setNimConfigured(false); }
      } catch {
        if (!aborted) setBackendStatus('disconnected');
      }
    };
    probe();
    const interval = setInterval(probe, 5000);
    return () => {
      aborted = true;
      clearInterval(interval);
      window.removeEventListener('NAVIGATE_PANEL', nav);
    };
  }, []);

  return (
    <div className="app-shell">
      <Toaster />
      <Sidebar
        panels={PANELS}
        active={activePanel}
        onSelect={setActivePanel}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        backendStatus={backendStatus}
      />
      <div className="app-main">
        <OfflineBanner backendStatus={backendStatus} />
        <TopBar
          title={PANELS[activePanel]?.label || 'RĀMAN Studio'}
          backendStatus={backendStatus}
          licenseInfo={licenseInfo}
        />
        <div className="app-content animate-in">
          <Suspense fallback={<PanelLoading />}>
            <ActiveComponent />
          </Suspense>
        </div>
        <StatusBar
          backendStatus={backendStatus}
          licenseInfo={licenseInfo}
          nimConfigured={nimConfigured}
          activePanel={activePanel}
        />
      </div>
    </div>
  );
}

function PanelLoading() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100%', color: 'var(--text-tertiary)',
      fontSize: 12, fontWeight: 400,
    }}>
      Loading…
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
