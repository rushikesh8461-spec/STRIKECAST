import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  optimizeDeps: { exclude: ["maplibre-gl"] },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/testSetup.ts"],
    restoreMocks: true,
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
