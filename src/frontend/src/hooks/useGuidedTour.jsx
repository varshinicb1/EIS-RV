import { useState, useCallback, useEffect } from 'react';

/**
 * RĀMAN Studio Guided Tour System
 * =================================
 * Beginner-friendly onboarding using react-joyride.
 * Steps are panel-aware and context-sensitive.
 */

const TOUR_STEPS = [
  {
    target: '.sidebar-logo',
    content: 'Welcome to RĀMAN Studio — the world\'s most advanced electrochemical research platform. Let\'s take a quick tour!',
    disableBeacon: true,
    placement: 'right',
  },
  {
    target: '.sidebar-nav',
    content: 'Navigate between simulation engines, AI tools, and research modules from this sidebar. Use Ctrl+1-9 for quick access.',
    placement: 'right',
  },
  {
    target: '.topbar',
    content: 'The top bar shows your current module and backend connection status. Green means the physics engine is online.',
    placement: 'bottom',
  },
  {
    target: '.statusbar',
    content: 'The status bar provides real-time system information — engine type (C++ or Python), backend connectivity, and active module.',
    placement: 'top',
  },
  {
    target: '[data-tour="ai-research"]',
    content: 'AI & Research modules include NVIDIA Alchemi for quantum materials simulation, Biosensor fabrication, and Literature Mining.',
    placement: 'right',
  },
  {
    target: '[data-tour="simulation"]',
    content: 'Simulation engines cover EIS, CV, Battery, GCD, DRT, and Circuit Fitting — all powered by a C++/Python hybrid solver.',
    placement: 'right',
  },
  {
    target: '[data-tour="management"]',
    content: 'Manage your projects, generate reports, and configure your profile and license from here.',
    placement: 'right',
  },
];

const TOUR_STYLES = {
  options: {
    arrowColor: '#1a1c22',
    backgroundColor: '#1a1c22',
    overlayColor: 'rgba(0, 0, 0, 0.75)',
    primaryColor: '#4a9eff',
    textColor: '#e8eaed',
    spotlightShadow: '0 0 30px rgba(74, 158, 255, 0.3)',
    zIndex: 10000,
  },
  tooltip: {
    borderRadius: 8,
    padding: 16,
    fontSize: 13,
    border: '1px solid #2d3036',
  },
  tooltipTitle: {
    fontSize: 14,
    fontWeight: 600,
  },
  buttonNext: {
    backgroundColor: '#4a9eff',
    borderRadius: 4,
    color: '#000',
    fontSize: 12,
    fontWeight: 600,
    padding: '6px 16px',
  },
  buttonBack: {
    color: '#9aa0a6',
    fontSize: 12,
  },
  buttonSkip: {
    color: '#6b7280',
    fontSize: 11,
  },
  buttonClose: {
    color: '#9aa0a6',
  },
};

export default function useGuidedTour() {
  const [runTour, setRunTour] = useState(false);
  const [tourCompleted, setTourCompleted] = useState(() => {
    try {
      return localStorage.getItem('raman-tour-completed') === 'true';
    } catch { return false; }
  });

  const startTour = useCallback(() => {
    setRunTour(true);
  }, []);

  const handleTourCallback = useCallback((data) => {
    const { status } = data;
    if (status === 'finished' || status === 'skipped') {
      setRunTour(false);
      setTourCompleted(true);
      try { localStorage.setItem('raman-tour-completed', 'true'); } catch {}
    }
  }, []);

  // Auto-start for first-time users
  useEffect(() => {
    if (!tourCompleted) {
      const timer = setTimeout(() => setRunTour(true), 1500);
      return () => clearTimeout(timer);
    }
  }, [tourCompleted]);

  return {
    runTour,
    startTour,
    tourCompleted,
    handleTourCallback,
    tourSteps: TOUR_STEPS,
    tourStyles: TOUR_STYLES,
  };
}
