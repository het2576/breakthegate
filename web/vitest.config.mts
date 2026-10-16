import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["**/*.test.{ts,tsx}"],
    // e2e/ is reserved for Playwright specs (P5, P6).
    exclude: ["node_modules/**", ".next/**", "e2e/**"],
  },
});
