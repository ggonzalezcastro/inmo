import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'   // SWC: ~20x más rápido que Babel
import path from 'path'

export default defineConfig({
  plugins: [react()],
  base: '/',

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  // ── Dep pre-bundling ────────────────────────────────────────────────────────
  // noDiscovery: true → Vite NO escanea source files en busca de deps.
  // Solo pre-bundlea lo listado en `include`. Esto acelera el cold start
  // porque evita el análisis estático de todo el proyecto al arrancar.
  //
  // Incluimos SOLO las deps que aparecen en la ruta de renderizado inicial
  // (router + AppShell + LoginPage + AuthGuard). Las deps de páginas lazy
  // se descubren cuando esa página se carga por primera vez (una sola vez,
  // el resultado queda cacheado en node_modules/.vite).
  optimizeDeps: {
    include: [
      // Core runtime
      'react',
      'react-dom',
      'react-dom/client',
      'react-router-dom',
      'zustand',
      'axios',
      'sonner',
      // Shared UI components usados en el layout y login
      'clsx',
      'tailwind-merge',
      'class-variance-authority',
      'lucide-react',
      // Radix primitives usados en LoginPage (Card, Input, Button, Label)
      '@radix-ui/react-slot',
      '@radix-ui/react-label',
      // Lazy pages se pre-bundlean de forma diferida (sin noDiscovery),
      // así Vite sólo hace el trabajo pesado para lo que realmente se necesita.
    ],
  },

  server: {
    port: 5173,
    strictPort: true,
    host: '127.0.0.1',

    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },

    // Pre-transforma los archivos core al arrancar, no en la primera petición.
    warmup: {
      clientFiles: [
        './src/main.tsx',
        './src/app/App.tsx',
        './src/app/router.tsx',
        './src/shared/components/layout/AppShell.tsx',
        './src/shared/components/layout/Sidebar.tsx',
        './src/features/auth/components/LoginPage.tsx',
        './src/features/dashboard/components/DashboardPage.tsx',
      ],
    },
  },

  // ── Build (producción) ──────────────────────────────────────────────────────
  build: {
    target: 'esnext',
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-ui': [
            '@radix-ui/react-avatar',
            '@radix-ui/react-checkbox',
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-label',
            '@radix-ui/react-popover',
            '@radix-ui/react-progress',
            '@radix-ui/react-select',
            '@radix-ui/react-separator',
            '@radix-ui/react-slot',
            '@radix-ui/react-switch',
            '@radix-ui/react-tabs',
            '@radix-ui/react-tooltip',
          ],
          'vendor-charts': ['recharts', 'react-is'],
          'vendor-table': ['@tanstack/react-table'],
          'vendor-dnd': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
          'vendor-utils': [
            'axios',
            'zustand',
            'sonner',
            'lucide-react',
            'clsx',
            'tailwind-merge',
            'class-variance-authority',
          ],
        },
      },
    },
  },
})
