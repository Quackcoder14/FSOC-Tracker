import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  root: fileURLToPath(new URL(".", import.meta.url)),
  server: {
    port: 3000,
    strictPort: true,
  },
  build: {
    target: "esnext",
  },
});
