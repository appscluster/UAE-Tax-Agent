import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const root = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "roughjs/bin/rough": path.join(root, "node_modules/roughjs/bin/rough.js"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 8420,
    proxy: {
      "/api": "http://127.0.0.1:8421",
      "/health": "http://127.0.0.1:8421",
    },
  },
});
