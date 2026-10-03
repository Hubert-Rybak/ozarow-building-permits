import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/ozarow-building-permits/",
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/ui/setup.ts"],
    include: ["tests/ui/**/*.test.{ts,tsx}"],
    clearMocks: true,
  },
});
