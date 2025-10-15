/// <reference types="vite/client" />

// Import Vue file types
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// Environment variables
declare interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_TITLE: string
  // Add other environment variables here
}

declare interface ImportMeta {
  readonly env: ImportMetaEnv
}
