import tailwindcss from "@tailwindcss/vite"

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  css: ["./app/assets/css/main.css"],
  build: {
    transpile: ["vue", "cally"],
  },
  modules: ['@pinia/nuxt'],
  ssr: false,
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000'
    }
  },
  vite: {
    plugins: [tailwindcss()],
    server: {
      hmr: {
        overlay: false
      }
    }
  },
  nitro: {
    devServer: {
      fork: false
    }
  }
})
