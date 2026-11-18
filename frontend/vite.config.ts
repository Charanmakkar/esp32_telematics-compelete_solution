import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { SW_VERSION, SW_BUILD_ID } from "./src/sw_version";

export default defineConfig({
  plugins: [react(), {
    name: "software-version",
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "sw-version.json",
        source: JSON.stringify({ sw_version: SW_VERSION, sw_build: SW_BUILD_ID }) });
    },
  }],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ["recharts"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.BACKEND_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.BACKEND_URL || "http://127.0.0.1:8000",
        ws: true,
      },
      "/docs": {
        target: process.env.BACKEND_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/redoc": {
        target: process.env.BACKEND_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/openapi.json": {
        target: process.env.BACKEND_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
