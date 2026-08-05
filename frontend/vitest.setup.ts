import "@testing-library/jest-dom/vitest";

// Provide localStorage since jsdom's localStorage may not always be available in Node.js environments
if (typeof globalThis.localStorage === "undefined") {
  const createStorageMock = () => {
    let store: Record<string, string> = {};

    return {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => {
        store[key] = String(value);
      },
      removeItem: (key: string) => {
        delete store[key];
      },
      clear: () => {
        store = {};
      },
      key: (index: number) => {
        const keys = Object.keys(store);
        return keys[index] ?? null;
      },
      get length() {
        return Object.keys(store).length;
      },
    } as Storage;
  };

  Object.defineProperty(globalThis, "localStorage", {
    value: createStorageMock(),
    writable: true,
    configurable: true,
  });
}
