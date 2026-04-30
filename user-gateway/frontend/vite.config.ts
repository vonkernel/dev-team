import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 로컬 dev 시 Vite 개발 서버 (기본 포트 5173) 가 /api/* 를 UG backend(8000) 로 proxy.
// 프로덕션: `vite build` → dist/ 가 UG backend 의 StaticFiles 로 서빙됨.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
