// Vitest setup — runs once before all tests.
// - Adds @testing-library/jest-dom matchers (toBeInTheDocument, etc.)
// - Stubs fetch by default so panels that call backend APIs at mount don't hang.
//   Individual tests can override with `globalThis.fetch = vi.fn(...)`.
// - Ensures jsdom resizes match what panels expect (no zero-height ResizeObserver).

import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom doesn't ship ResizeObserver by default
class _ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || _ResizeObserver;

// IntersectionObserver — same story
class _IntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() { return []; }
}
globalThis.IntersectionObserver = globalThis.IntersectionObserver || _IntersectionObserver;

// matchMedia — for components that adapt to dark/light mode
if (!globalThis.matchMedia) {
  globalThis.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

// Default-deny network: every test should opt in by mocking explicitly.
beforeEach(() => {
  globalThis.fetch = vi.fn(() => Promise.reject(new Error('fetch not mocked')));
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
