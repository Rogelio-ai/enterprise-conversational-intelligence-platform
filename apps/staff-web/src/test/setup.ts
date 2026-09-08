import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

class MatchMediaMock {
  matches = false;
  media = '';
  onchange = null;
  addListener() {}
  removeListener() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
}

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: () => new MatchMediaMock(),
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});
