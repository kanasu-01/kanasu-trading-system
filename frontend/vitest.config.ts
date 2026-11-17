import path from "path";

import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      "@": path.resolve(
        __dirname,
        "./src",
      ),
    },
  },

  test: {
    environment: "jsdom",
    setupFiles: [
      "./tests/setup.ts",
    ],
    // Browser E2E cases are executed only by Playwright, not by Vitest.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
