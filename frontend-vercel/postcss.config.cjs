/**
 * PostCSS Configuration (CommonJS version for Vite compatibility)
 * Optimized for Vite + Vue 3 + Tailwind CSS
 * Clean configuration without deprecated features
 */

// Configuración optimizada y limpia
const config = {
  plugins: [
    // Importar estilos primero
    require('postcss-import'),
    
    // Tailwind CSS - usando el nuevo paquete PostCSS
    require('@tailwindcss/postcss'),
    
    // Autoprefixer optimizado
    require('autoprefixer')({
      grid: 'autoplace',
      flexbox: 'no-2009',
      overrideBrowserslist: [
        'last 2 versions',
        '> 0.5%',
        'not dead',
        'not op_mini all',
        'not ie > 0',
        'not ie_mob > 0',
        'not baidu > 0'
      ]
    })
  ]
};

// Solo agregar cssnano en producción para optimización
if (process.env.NODE_ENV === 'production') {
  config.plugins.push(
    require('cssnano')({
      preset: ['default', {
        discardComments: {
          removeAll: true
        },
        minifySelectors: false,
        normalizeWhitespace: false,
        discardUnused: false,
        reduceIdents: false
      }]
    })
  );
}

// Exportar configuración
module.exports = config;
