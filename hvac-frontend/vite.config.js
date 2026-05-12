import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],

  server: {
    port: 5173,
    strictPort: true,
    historyApiFallback: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE_URL || "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },
      "/ws": {
        target: process.env.VITE_API_BASE_URL || "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        ws: true,
      },
    },
  },

  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: mode === "development",
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query"],
          charts: ["recharts", "react-plotly.js"],
          leaflet: ["leaflet", "react-leaflet"],
          http: ["axios"],
        },
      },
    },
  },

  css: {
    devSourcemap: mode === "development",
  },
}));
