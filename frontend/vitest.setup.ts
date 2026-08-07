import "@testing-library/jest-dom/vitest";

// Node 26 ships an experimental Web Storage global (on by default) that defines
// `globalThis.localStorage` as a getter resolving to `undefined` unless
// `--localstorage-file` is passed. jsdom's own environment setup treats the
// property as already present and skips installing its real implementation, so
// `localStorage` ends up undefined in tests on this Node version even though
// jsdom itself supports it. We install a minimal, spec-shaped Storage
// implementation unconditionally so tests don't depend on this interaction
// varying across Node versions.
function createStorageMock(): Storage {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => (key in store ? store[key] : null),
    setItem: (key: string, value: string) => {
      store[key] = String(value);
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
    get length() {
      return Object.keys(store).length;
    },
  } as Storage;
}

Object.defineProperty(globalThis, "localStorage", {
  value: createStorageMock(),
  writable: true,
  configurable: true,
});
