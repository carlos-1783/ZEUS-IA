/** @type {import('tailwindcss').Config} */
module.exports = {
  // Only scan files that might contain Tailwind classes
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  
  // Enable dark mode via class strategy
  darkMode: 'class',
  
  // Core plugins configuration
  corePlugins: {
    // Disable unused core plugins to reduce CSS bundle size
    float: false,
    clear: false,
    skew: false,
    // Enable modern features
    backdropBlur: true,
    backdropFilter: true,
    filter: true,
    ringWidth: true,
    ringOffsetWidth: true,
    ringColor: true,
    ringOffsetColor: true,
    ringOpacity: true,
    ringOffset: true,
  },
  
  // Theme customization
  theme: {
    extend: {
      // Custom colors with modern color spaces
      colors: {
        primary: {
          DEFAULT: 'hsl(199, 89%, 48%)',
          50: 'hsl(195, 100%, 95%)',
          100: 'hsl(196, 100%, 89%)',
          200: 'hsl(197, 97%, 78%)',
          300: 'hsl(199, 96%, 68%)',
          400: 'hsl(200, 94%, 60%)',
          500: 'hsl(199, 89%, 48%)',
          600: 'hsl(200, 98%, 39%)',
          700: 'hsl(200, 96%, 32%)',
          800: 'hsl(201, 90%, 27%)',
          900: 'hsl(201, 80%, 23%)',
        },
        // Semantic colors with modern color spaces
        success: 'hsl(160, 84%, 39%)',
        warning: 'hsl(38, 92%, 50%)',
        danger: 'hsl(0, 84%, 60%)',
        info: 'hsl(221, 91%, 60%)',
      },
      // Custom spacing scale
      spacing: {
        '128': '32rem',
        '144': '36rem',
      },
      // Modern breakpoints
      screens: {
        '3xl': '1600px',
        '4xl': '1920px',
      },
      // Custom typography
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
    },
  },
  
  // Variants configuration
  variants: {
    extend: {
      opacity: ['disabled'],
      backgroundColor: ['active', 'disabled'],
      textColor: ['active', 'disabled'],
      borderColor: ['focus-visible', 'first'],
    },
  },
  
  // Plugins
  plugins: [
    // Add useful plugins only if they exist
    // require('@tailwindcss/forms'),
    // require('@tailwindcss/typography'),
  ],
  
  // Purge configuration for production
  future: {
    removeDeprecatedGapUtilities: true,
    purgeLayersByDefault: true,
  },
  
  // Important: true adds !important to all utilities
  important: false,
}
