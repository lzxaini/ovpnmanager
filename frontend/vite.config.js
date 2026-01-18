import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/ovpnmanager/",
  server: {
    host: "0.0.0.0",
    port: 8010,
  },
  build: {
    target: "es2018",
    outDir: "ovpnmanager",
    assetsDir: "assets",
    sourcemap: false,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["vue", "vue-router", "axios", "element-plus"],
        },
      },
    },
  },
});
