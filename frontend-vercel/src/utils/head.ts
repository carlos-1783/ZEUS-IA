import { createHead, useHead as useVueHead, type HeadObject } from '@vueuse/head'

export const head = createHead()

// Export the head instance for use in the app
export const useHead = useVueHead

// Default head configuration
const defaultHead: HeadObject = {
  title: 'ZEUS-IA - Sistema de Gestión',
  htmlAttrs: {
    lang: 'es',
    dir: 'ltr' as const
  },
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1.0, viewport-fit=cover' },
    { 'http-equiv': 'X-UA-Compatible', content: 'IE=edge' },
    { name: 'description', content: 'Sistema de gestión ZEUS-IA' },
    { name: 'theme-color', content: '#1f2937' },
    { name: 'format-detection', content: 'telephone=no' },
    { name: 'mobile-web-app-capable', content: 'yes' },
    { name: 'apple-mobile-web-app-title', content: 'ZEUS-IA' },
    { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
    { name: 'msapplication-TileColor', content: '#1f2937' }
  ],
  link: [
    { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
    { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' },
    { rel: 'manifest', href: '/site.webmanifest' }
  ]
}

// Setup function to be called in the app
export function setupHead() {
  // Apply default head configuration
  useHead(defaultHead)
  
  // Return the head instance for further use
  return head
}

// Vue plugin for head management
export const HeadPlugin = {
  install(app: any) {
    app.use(head)
  }
}

export default HeadPlugin
