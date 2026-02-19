import '@testing-library/jest-dom'

// Polyfill ResizeObserver for jsdom (used by Radix Select, etc.)
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
