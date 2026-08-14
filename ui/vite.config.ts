/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Il backend non ha CORS, ed e' giusto cosi': in produzione l'API e la UI stanno
// dietro la stessa origine, e aprirla a chiunque per comodita' di sviluppo
// sarebbe una decisione di sicurezza presa per sbaglio. In sviluppo ci pensa
// questo proxy: `/api/...` esce da Vite e arriva al backend come `/...`.
//
// `X-Accel-Buffering: no` viaggia dal backend, ma il proxy va comunque tenuto in
// streaming (`selfHandleResponse: false`, che e' il default): un proxy che
// bufferizza non rompe niente e annulla lo streaming in silenzio, che e'
// esattamente il guasto che /query/stream esiste per evitare.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: env.VITE_API_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    },
  };
});
