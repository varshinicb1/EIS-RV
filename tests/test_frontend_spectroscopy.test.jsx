/**
 * Frontend Tests for Unified Spectroscopy Panel
 * ==============================================
 * 
 * Tests:
 * - Component rendering
 * - File upload and analysis
 * - Theme-aware plotting
 * - Analysis options (cosmic ray, Fourier, Voigt)
 * - Display options (peaks, baseline, fit)
 * - Material identification display
 * - AI analysis integration
 * - PNG export functionality
 * 
 * Author: VidyuthLabs
 * Date: May 5, 2026
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import UnifiedSpectroscopyPanel from '../src/frontend/src/components/simulation/UnifiedSpectroscopyPanel';
import { ThemeProvider } from '../src/frontend/src/hooks/useTheme';

// Mock fetch
global.fetch = jest.fn();

// Mock canvas
HTMLCanvasElement.prototype.getContext = jest.fn(() => ({
  fillStyle: '',
  strokeStyle: '',
  lineWidth: 0,
  fillRect: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  stroke: jest.fn(),
  fill: jest.fn(),
  arc: jest.fn(),
  closePath: jest.fn(),
  fillText: jest.fn(),
  save: jest.fn(),
  restore: jest.fn(),
  translate: jest.fn(),
  rotate: jest.fn(),
  scale: jest.fn(),
  setLineDash: jest.fn(),
  createLinearGradient: jest.fn(() => ({
    addColorStop: jest.fn(),
  })),
}));

HTMLCanvasElement.prototype.toDataURL = jest.fn(() => 'data:image/png;base64,mock');

// Helper to wrap component with theme
const renderWithTheme = (component, theme = 'light') => {
  return render(
    <ThemeProvider initialTheme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('UnifiedSpectroscopyPanel', () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // RENDERING TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('renders without crashing', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />);
    expect(screen.getByText(/Unified Spectroscopy/i)).toBeInTheDocument();
  });

  test('displays file upload input', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />);
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);
    expect(fileInput).toBeInTheDocument();
    expect(fileInput).toHaveAttribute('type', 'file');
    expect(fileInput).toHaveAttribute('accept', '.txt,.csv');
  });

  test('displays analysis options', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />);
    
    expect(screen.getByText(/Cosmic ray removal/i)).toBeInTheDocument();
    expect(screen.getByText(/Fourier filtering/i)).toBeInTheDocument();
    expect(screen.getByText(/Voigt peak fitting/i)).toBeInTheDocument();
  });

  test('displays empty state message', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />);
    expect(screen.getByText(/UPLOAD_SPECTRUM_FILE_TO_BEGIN/i)).toBeInTheDocument();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // FILE UPLOAD TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('handles file upload and triggers analysis', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300, 400, 500],
      intensity: [0.1, 0.3, 0.5, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.45, 0.25, 0.05],
      baseline: [0.05, 0.05, 0.05, 0.05, 0.05],
      peaks: [
        { position_cm: 300, intensity: 0.45, prominence: 0.4, fwhm_cm: 20 }
      ],
      n_points: 5,
      wavenumber_range: [100, 500],
      material_matches: [],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1\n200\t0.3\n300\t0.5'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/unified-spectroscopy/analyze'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  test('displays error message on upload failure', async () => {
    fetch.mockRejectedValueOnce(new Error('Network error'));

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['invalid data'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // ANALYSIS OPTIONS TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('cosmic ray removal checkbox toggles state', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />);
    
    const checkbox = screen.getByLabelText(/Cosmic ray removal/i);
    expect(checkbox).not.toBeChecked();
    
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  test('fourier filtering checkbox toggles state', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />);
    
    const checkbox = screen.getByLabelText(/Fourier filtering/i);
    expect(checkbox).not.toBeChecked();
    
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  test('voigt fitting checkbox toggles state', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />);
    
    const checkbox = screen.getByLabelText(/Voigt peak fitting/i);
    expect(checkbox).not.toBeChecked();
    
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  test('reanalyze button appears after file upload', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [],
      n_points: 3,
      wavenumber_range: [100, 300],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Reanalyze/i)).toBeInTheDocument();
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // DISPLAY OPTIONS TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('display options appear after analysis', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [{ position_cm: 200, intensity: 0.25 }],
      n_points: 3,
      wavenumber_range: [100, 300],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Show peak markers/i)).toBeInTheDocument();
      expect(screen.getByText(/Show baseline correction/i)).toBeInTheDocument();
      expect(screen.getByText(/Show fitted peaks/i)).toBeInTheDocument();
    });
  });

  test('peak markers checkbox is checked by default', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [{ position_cm: 200, intensity: 0.25 }],
      n_points: 3,
      wavenumber_range: [100, 300],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      const checkbox = screen.getByLabelText(/Show peak markers/i);
      expect(checkbox).toBeChecked();
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // THEME TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('renders with light theme', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />, 'light');
    // Component should render without errors
    expect(screen.getByText(/Unified Spectroscopy/i)).toBeInTheDocument();
  });

  test('renders with dark theme', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />, 'dark');
    expect(screen.getByText(/Unified Spectroscopy/i)).toBeInTheDocument();
  });

  test('renders with high contrast theme', () => {
    renderWithTheme(<UnifiedSpectroscopyPanel />, 'hc');
    expect(screen.getByText(/Unified Spectroscopy/i)).toBeInTheDocument();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // MATERIAL IDENTIFICATION TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('displays material matches', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [{ position_cm: 520, intensity: 0.8 }],
      n_points: 3,
      wavenumber_range: [100, 300],
      material_matches: [
        {
          material: 'silicon',
          description: 'Crystalline silicon',
          confidence: 0.95,
          matched_peaks: 1,
          total_peaks: 1,
        },
      ],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Material Identification/i)).toBeInTheDocument();
      expect(screen.getByText(/Crystalline silicon/i)).toBeInTheDocument();
      expect(screen.getByText(/95%/i)).toBeInTheDocument();
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // EXPORT TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('export button appears after analysis', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [],
      n_points: 3,
      wavenumber_range: [100, 300],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Download PNG/i)).toBeInTheDocument();
    });
  });

  test('export button triggers PNG download', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [],
      n_points: 3,
      wavenumber_range: [100, 300],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // Mock document.createElement
    const mockLink = {
      click: jest.fn(),
      download: '',
      href: '',
    };
    jest.spyOn(document, 'createElement').mockReturnValue(mockLink);

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      const exportButton = screen.getByText(/Download PNG/i);
      fireEvent.click(exportButton);
      expect(mockLink.click).toHaveBeenCalled();
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // AI ANALYSIS TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('AI analysis section appears after analysis', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [{ position_cm: 200, intensity: 0.25 }],
      n_points: 3,
      wavenumber_range: [100, 300],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    // Mock API key status
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ configured: true }),
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/AI Peak Analysis & Reasoning/i)).toBeInTheDocument();
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // STATISTICS TESTS
  // ═══════════════════════════════════════════════════════════════════════

  test('displays statistics after analysis', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300, 400, 500],
      intensity: [0.1, 0.3, 0.5, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.45, 0.25, 0.05],
      peaks: [
        { position_cm: 300, intensity: 0.45 },
        { position_cm: 200, intensity: 0.25 },
      ],
      n_points: 5,
      wavenumber_range: [100, 500],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/PEAKS_DETECTED/i)).toBeInTheDocument();
      expect(screen.getByText(/DATA_POINTS/i)).toBeInTheDocument();
      expect(screen.getByText(/WAVENUMBER_MIN/i)).toBeInTheDocument();
      expect(screen.getByText(/WAVENUMBER_MAX/i)).toBeInTheDocument();
    });
  });

  test('displays peaks table', async () => {
    const mockResponse = {
      wavenumber: [100, 200, 300],
      intensity: [0.1, 0.3, 0.1],
      corrected_intensity: [0.05, 0.25, 0.05],
      peaks: [
        { position_cm: 200.5, intensity: 0.25, prominence: 0.2, fwhm_cm: 15.3 },
      ],
      n_points: 3,
      wavenumber_range: [100, 300],
    };

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    renderWithTheme(<UnifiedSpectroscopyPanel />);

    const file = new File(['100\t0.1'], 'test.txt', { type: 'text/plain' });
    const fileInput = screen.getByLabelText(/Raman spectrum file/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Detected Peaks/i)).toBeInTheDocument();
      expect(screen.getByText(/200.50/i)).toBeInTheDocument();
      expect(screen.getByText(/0.250/i)).toBeInTheDocument();
    });
  });
});
