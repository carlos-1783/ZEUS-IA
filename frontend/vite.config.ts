import { defineConfig, loadEnv, type ConfigEnv, type UserConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath } from 'node:url';
import { visualizer } from 'rollup-plugin-visualizer';
import { compression } from 'vite-plugin-compression2';
import type { PluginOption } from 'vite';

export default defineConfig(({ command, mode }: ConfigEnv): UserConfig => {
  const isDev = mode === 'development';
  const env = loadEnv(mode, process.cwd(), '');
  
  // Base configuration
  const base = '/';
  
  // CSS configuration
  const cssConfig = {
    preprocessorOptions: {
      scss: {
        sourceMap: isDev
      }
    },
    devSourcemap: isDev,
    modules: {
      generateScopedName: isDev 
        ? '[name]__[local]__[hash:base64:5]' 
        : '[hash:base64:8]'
    }
  };

  // PWA Configuration - SOLO PARA PRODUCCIÓN (comentado para desarrollo)
  // const pwaOptions = !isDev ? { ... } : null;

  // Plugins configuration
  const plugins: PluginOption[] = [
    vue({
      script: {
        defineModel: true,
        propsDestructure: true
      },
      template: {
        compilerOptions: {
          isCustomElement: (tag: string) => tag.startsWith('ion-')
        }
      }
    })
  ];

  // NO AGREGAR PWA EN DESARROLLO - Solo en producción
  // En desarrollo, NO agregar ningún plugin PWA para evitar conflictos de rutas

  // Add development plugins
  if (!isDev) {
    plugins.push(
      visualizer({
        open: false,
        gzipSize: true,
        brotliSize: true,
        filename: 'dist/stats.html'
      }) as PluginOption,
      compression({
        algorithm: 'gzip',
        deleteOriginalAssets: false,
        filename: '[path][base].gz',
        threshold: 1024,
        include: /\.(js|mjs|json|css|html|svg)$/i
      }),
      compression({
        algorithm: 'brotliCompress',
        deleteOriginalAssets: false,
        filename: '[path][base].br',
        threshold: 1024,
        include: /\.(js|mjs|json|css|html|svg)$/i
      })
    );
  }

  // Development server configuration
  const server = isDev ? {
    port: 5173,
    strictPort: true, // FORZAR puerto 5173 - NO permitir alternativos
    host: 'localhost', // Usar localhost para consistencia con CSP
    open: false,
    cors: true,
    hmr: {
      port: 5173, // Usar el mismo puerto para HMR
      host: 'localhost'
    },
    watch: {
      usePolling: false,
      interval: 1000,
      ignored: [
        '**/node_modules/**',
        '**/dist/**',
        '**/.git/**',
        '**/vite.config.ts.timestamp-*',
        '**/*.timestamp-*'
      ]
    },
    // DESHABILITAR PROXY EN PRODUCCIÓN PARA EVITAR VIOLACIONES
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
        timeout: 120000, // Permitir respuestas largas (OpenAI, render, etc.)
        configure: (proxy: any, options: any) => {
          proxy.on('error', (err: any, req: any, res: any) => {
            console.log('Proxy error:', err);
          });
        }
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
        timeout: 120000 // Mantener sockets abiertos
      }
    }, // <-- Coma añadida aquí
    fs: {
      strict: false,
      allow: ['..']
    }
  } : undefined;

  // Build configuration - OPTIMIZADA PARA PRODUCCIÓN
  const build = {
    sourcemap: false, // Sin sourcemaps en producción para seguridad
    assetsDir: 'assets',
    cssTarget: 'esnext',
    modulePreload: {
      polyfill: false
    },
    commonjsOptions: {
      include: [/node_modules/],
      extensions: ['.js', '.cjs'],
      strictRequires: true,
      transformMixedEsModules: true
    },
    rollupOptions: {
      onwarn: (warning: any, warn: any) => {
        if (warning.code === 'DEPRECATED_FEATURE') return;
        warn(warning);
      },
      output: {
        manualChunks: (id: string): string | undefined => {
          if (id.includes('node_modules')) {
            if (id.includes('@vue/') || id.includes('vue-router') || id.includes('pinia')) {
              return 'vendor';
            }
            if (id.includes('three') || id.includes('@react-three')) {
              return 'three';
            }
            if (id.includes('vue3-toastify')) {
              return 'toastify';
            }
            return 'vendor';
          }
        },
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: (assetInfo: { name?: string }): string => {
          const fileName = assetInfo.name || 'asset';
          const info = fileName.split('.');
          const ext = info[info.length - 1].toLowerCase();
          
          if (ext === 'css') {
            return 'assets/css/[name]-[hash][extname]';
          } 
          if (/(png|jpe?g|gif|svg|webp|avif)$/i.test(fileName)) {
            return 'assets/images/[name]-[hash][extname]';
          } 
          if (/(woff|woff2|eot|ttf|otf)$/i.test(fileName)) {
            return 'assets/fonts/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        }
      },
      external: []
    },
    target: 'esnext',
    minify: !isDev ? 'esbuild' as const : false,
    cssCodeSplit: true,
    reportCompressedSize: false,
    chunkSizeWarningLimit: 1600,
    emptyOutDir: true // Limpiar directorio de salida antes de cada build
  };

  return {
    base,
    mode,
    css: cssConfig,
    define: {
      __APP_ENV__: JSON.stringify(env.APP_ENV || ''),
      'import.meta.env.MODE': JSON.stringify(mode),
      'import.meta.env.DEV': isDev,
      'import.meta.env.PROD': !isDev,
      'import.meta.env.SSR': false,
    },
    plugins,
    server,
    build,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        '~bootstrap': 'bootstrap',
        '~@fontsource': '@fontsource',
      },
      extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue']
    },
    esbuild: {
      drop: isDev ? [] : ['console', 'debugger'],
      define: {
        global: 'globalThis'
      },
      treeShaking: true,
      keepNames: isDev
    },
    optimizeDeps: {
      include: ['vue', 'vue-router', 'pinia', 'axios', 'socket.io-client']
    },
    clearScreen: false,
    logLevel: 'info',
    root: '.',
    publicDir: 'public',
    appType: 'spa',
    envPrefix: 'VITE_',
    assetsInclude: ['**/*.png', '**/*.jpg', '**/*.jpeg', '**/*.gif', '**/*.svg', '**/*.ico', '**/*.webp'],
    cacheDir: 'node_modules/.vite'
  };
});
