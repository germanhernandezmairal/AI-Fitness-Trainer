import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Exclude macOS AppleDouble shadow files (`._*`) — this repo lives on an
    // exFAT volume, which makes macOS write one alongside every new file.
    // Same fix as vitest.config.ts and playwright.config.ts.
    "**/._*",
  ]),
]);

export default eslintConfig;
