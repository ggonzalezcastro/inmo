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
  // Dejamos que Vite descubra deps automáticamente (scan de imports).
  // Solo forzamos `include` para paquetes CJS/mixtos que Vite no detecta
  // bien o que causan "new dependency found → full reload" en runtime.
  optimizeDeps: {
    include: [
      'recharts',
      'react-is',
      'es-toolkit',
      'es-toolkit/compat',
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
    sourcemap: false,
    chunkSizeWarningLimit: 600,
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
