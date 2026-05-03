import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import AlchemistCanvas from '../src/components/materials/AlchemistCanvas';

/**
 * Minimal contract test: the panel hits the two backend endpoints when the
 * user clicks "INITIALIZE GENERATION", and surfaces a license-required error
 * when the backend returns 403 (the most likely state for an unactivated
 * researcher).
 */
describe('AlchemistCanvas', () => {
  it('renders the formula input and run button', () => {
    render(<AlchemistCanvas />);
    expect(screen.getByPlaceholderText(/Target formula/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /INITIALIZE GENERATION/i })).toBeInTheDocument();
  });

  it('surfaces an error when /properties fails', async () => {
    // Reject with a real-looking 403; the panel catches anything and writes
    // it into the error banner. We don't pin the exact message — we just
    // verify the user sees a visible "● ..." banner with "DISMISS" button.
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 403,
      text: async () => '{"detail":{"code":"license_invalid","message":"License required"}}',
      json: async () => ({ detail: { code: 'license_invalid', message: 'License required' } }),
    });

    render(<AlchemistCanvas />);
    const button = screen.getByRole('button', { name: /INITIALIZE GENERATION/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /DISMISS/i })).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('hits both alchemi endpoints on success', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({   // /api/v2/alchemi/properties
        ok: true, status: 200,
        json: async () => ({
          formula: 'MnO2',
          band_gap_ev: 0.3,
          specific_capacitance_f_g: 250,
          source: 'curated',
        }),
      })
      .mockResolvedValueOnce({   // /api/v2/alchemi/chat
        ok: true, status: 200,
        json: async () => ({
          answer: '{"steps":["Step A","Step B","Step C","Step D"],"rationale":"Standard protocol."}',
        }),
      });
    globalThis.fetch = fetchMock;

    render(<AlchemistCanvas />);
    const button = screen.getByRole('button', { name: /INITIALIZE GENERATION/i });
    await act(async () => {
      fireEvent.click(button);
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v2/alchemi/properties');
    expect(fetchMock.mock.calls[1][0]).toContain('/api/v2/alchemi/chat');
  });
});
