import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import Toaster from '../src/components/layout/Toaster';

describe('Toaster', () => {
  it('renders nothing when no toasts are dispatched', () => {
    render(<Toaster />);
    expect(screen.queryByText(/●/)).not.toBeInTheDocument();
  });

  it('renders a toast when RAMAN_TOAST is dispatched', () => {
    render(<Toaster />);
    act(() => {
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'ok', text: 'Hello world' },
      }));
    });
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('uses the right color accent per kind', () => {
    render(<Toaster />);
    act(() => {
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'err', text: 'Boom' },
      }));
    });
    const text = screen.getByText('Boom');
    // Walk up to the toast container — checks border-color is the err red.
    const container = text.parentElement;
    // Error toasts use Apple-style red (255, 69, 58) at 0.35 alpha.
    expect(container.style.border).toMatch(/255, *69, *58/);
  });

  it('dismisses on click', async () => {
    render(<Toaster />);
    act(() => {
      window.dispatchEvent(new CustomEvent('RAMAN_TOAST', {
        detail: { kind: 'info', text: 'Tap me', durationMs: 60_000 },
      }));
    });
    const toast = screen.getByText('Tap me').parentElement;
    act(() => { toast.click(); });
    expect(screen.queryByText('Tap me')).not.toBeInTheDocument();
  });
});
