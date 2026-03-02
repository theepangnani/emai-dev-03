import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'masked-icon.svg'],
      manifest: {
        name: 'ClassBridge — AI Education Platform',
        short_name: 'ClassBridge',
        description: 'AI-powered education management for parents, students, and teachers',
        theme_color: '#4f46e5',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\/api\/study\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'study-guides-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 7 * 24 * 60 * 60 }
            }
          },
          {
            urlPattern: /^https:\/\/.*\/api\/flashcards\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'flashcards-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 7 * 24 * 60 * 60 }
            }
          },
          {
            urlPattern: /^https:\/\/.*\/api\/assignments\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'assignments-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 24 * 60 * 60 }
            }
          },
          {
            urlPattern: /^https:\/\/.*\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 }
            }
          }
        ]
      }
    })
  ],
  base: '/',
})
