import React, { useState, lazy, Suspense } from 'react';
import { Joyride } from 'react-joyride';
import useKeyboardShortcuts from './hooks/useKeyboardShortcuts';
import { ThemeProvider } from './hooks/useTheme.jsx';
import useGuidedTour from './hooks/useGuidedTour.jsx';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import StatusBar from './components/layout/StatusBar';
import EISPanel from './components/simulation/EISPanel';
import CVPanel from './components/simulation/CVPanel';
import BatteryPanel from './components/simulation/BatteryPanel';
import GCDPanel from './components/simulation/GCDPanel';
import DRTPanel from './components/simulation/DRTPanel';
import CircuitFittingPanel from './components/simulation/CircuitFittingPanel';
import ToolkitPanel from './components/simulation/ToolkitPanel';
import DataImportPanel from './components/data/DataImportPanel';
import MaterialsExplorer from './components/materials/MaterialsExplorer';
import AlchemistCanvas from './components/materials/AlchemistCanvas';
import BiosensorPanel from './components/simulation/BiosensorPanel';
import DashboardPanel from './components/simulation/DashboardPanel';
import AlchemiPanel from './components/ai/AlchemiPanel';
import LiteratureMiningPanel from './components/research/LiteratureMiningPanel';
import ValidationPanel from './components/research/ValidationPanel';
import UserProfilePanel from './components/user/UserProfilePanel';
import WorkspacePanel from './components/workspace/WorkspacePanel';
import ReportsPanel from './components/reports/ReportsPanel';

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
  validation: { label: 'Paper Validation',    component: ValidationPanel },
  workspace:  { label: 'Workspace',           component: WorkspacePanel },
  reports:    { label: 'Reports',             component: ReportsPanel },
  profile:    { label: 'User Profile',        component: UserProfilePanel },
};

function AppContent() {
  const [activePanel, setActivePanel] = useState('alchemi');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [backendStatus, setBackendStatus] = useState('connecting');
  const { runTour, handleTourCallback, tourSteps, tourStyles } = useGuidedTour();

  useKeyboardShortcuts(setActivePanel, () => setSidebarCollapsed(c => !c));

  const ActiveComponent = PANELS[activePanel]?.component || DashboardPanel;

  React.useEffect(() => {
    const nav = (e) => setActivePanel(e.detail);
    window.addEventListener('NAVIGATE_PANEL', nav);
    
    const check = async () => {
      try {
        const api = window.raman?.api;
        if (api) {
          await api.get('/api/health');
          setBackendStatus('connected');
        } else {
          const res = await fetch(`${BACKEND_URL}/api/health`);
          if (res.ok) setBackendStatus('connected');
        }
      } catch {
        setBackendStatus('disconnected');
      }
    };
    check();
    const interval = setInterval(check, 15000);
    return () => {
      clearInterval(interval);
      window.removeEventListener('NAVIGATE_PANEL', nav);
    };
  }, []);

  return (
    <div className="app-shell">
      <Joyride
        steps={tourSteps}
        run={runTour}
        callback={handleTourCallback}
        continuous
        showSkipButton
        showProgress
        disableOverlayClose
        styles={tourStyles}
      />
      <Sidebar
        panels={PANELS}
        active={activePanel}
        onSelect={setActivePanel}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div className="app-main scanline-container">
        <TopBar
          title={PANELS[activePanel]?.label || 'RAMAN Studio'}
          backendStatus={backendStatus}
        />
        <div className="app-content animate-in">
          <ActiveComponent />
        </div>
        <StatusBar
          backendStatus={backendStatus}
          activePanel={activePanel}
        />
      </div>
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
