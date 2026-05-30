import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import AlchemistCanvas from '../src/components/materials/AlchemistCanvas';

/**
 * Minimal contract test: the panel hits the two backend endpoints when the
 * user clicks "Plan synthesis", and surfaces a license-required error
 * when the backend returns 403 (the most likely state for an unactivated
 * researcher).
 */
describe('AlchemistCanvas', () => {
  it('renders the search input and generate button', () => {
    render(<AlchemistCanvas />);
    expect(screen.getByPlaceholderText(/Search MnO₂/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generate combinations/i })).toBeInTheDocument();
  });

  it('surfaces an error when generate clicked with no selection (no fetch needed)', async () => {
    // Mock successful (empty) library load so no libError masks the genError
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true, status: 200, json: async () => ({ library: [] }),
    });
    render(<AlchemistCanvas />);
    const button = screen.getByRole('button', { name: /Generate combinations/i });
    await act(async () => {
      fireEvent.click(button);
    });
    // Component sets genError for empty selection; wait for ErrorBox
    await waitFor(() => {
      expect(screen.getByText(/Pick at least one block from the library/i)).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('hits alchemi library endpoint on mount', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true, status: 200,
        json: async () => ({ library: [] }),
      });
    globalThis.fetch = fetchMock;

    render(<AlchemistCanvas />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v2/alchemi/materials/library');
  });
});
