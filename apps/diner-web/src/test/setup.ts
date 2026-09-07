import '@testing-library/jest-dom/vitest';

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
