import { defaultExclude, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    // Exclude macOS AppleDouble shadow files (`._*`) — this repo lives on an
    // exFAT volume, which makes macOS write one alongside every new file.
    exclude: [...defaultExclude, "**/._*"],
    passWithNoTests: true,
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
