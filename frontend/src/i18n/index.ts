import { createI18n } from 'vue-i18n';

const messages = {
  es: {
    navigation: {
      dashboard: 'Panel',
    },
    layout: {
      openMenu: 'Abrir menú',
      logout: 'Cerrar sesión',
      userFallback: 'Usuario',
      languageLabel: 'Idioma',
    },
    auth: {
      login: {
        emailPlaceholder: 'Correo electrónico',
        passwordPlaceholder: 'Contraseña',
        rememberMe: 'Recordar sesión',
        forgotPassword: '¿Olvidaste tu contraseña?',
        submit: 'Iniciar sesión',
        submitting: 'Iniciando sesión...',
        emailRequired: 'El correo electrónico es obligatorio',
        emailInvalid: 'El correo electrónico no es válido',
        passwordRequired: 'La contraseña es obligatoria',
        passwordLength: 'La contraseña debe tener al menos 6 caracteres',
        tokenError: 'No se pudo guardar el token de autenticación',
        defaultError: 'Error al iniciar sesión. Por favor, verifica tus credenciales.',
        genericError: 'Ocurrió un error al intentar iniciar sesión. Por favor, inténtalo de nuevo.',
      },
    },
    status: {
      completed: 'Completado',
      pending: 'Pendiente',
      error: 'Error',
      noActivities: 'No hay actividades recientes',
    },
  },
  en: {
    navigation: {
      dashboard: 'Dashboard',
    },
    layout: {
      openMenu: 'Open menu',
      logout: 'Log out',
      userFallback: 'User',
      languageLabel: 'Language',
    },
    auth: {
      login: {
        emailPlaceholder: 'Email address',
        passwordPlaceholder: 'Password',
        rememberMe: 'Remember me',
        forgotPassword: 'Forgot your password?',
        submit: 'Sign in',
        submitting: 'Signing in...',
        emailRequired: 'Email address is required',
        emailInvalid: 'Email address is not valid',
        passwordRequired: 'Password is required',
        passwordLength: 'Password must be at least 6 characters',
        tokenError: 'Authentication token could not be stored',
        defaultError: 'Failed to sign in. Please check your credentials.',
        genericError: 'Something went wrong. Please try again.',
      },
    },
    status: {
      completed: 'Completed',
      pending: 'Pending',
      error: 'Error',
      noActivities: 'No recent activity',
    },
  },
};

const parseSupportedLocales = (): string[] => {
  const envLocales = import.meta.env.VITE_SUPPORTED_LANGUAGES;
  if (typeof envLocales === 'string' && envLocales.trim().length > 0) {
    return envLocales
      .split(',')
      .map((locale) => locale.trim())
      .filter(Boolean);
  }
  return ['es', 'en'];
};

const supportedLocales = parseSupportedLocales();

const canAccessStorage = typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';

const resolveDefaultLocale = (): string => {
  if (canAccessStorage) {
    const persistedLocale = window.localStorage.getItem('zeus_locale');
    if (persistedLocale && supportedLocales.includes(persistedLocale)) {
      return persistedLocale;
    }
  }

  const envDefault = import.meta.env.VITE_DEFAULT_LANGUAGE;
  if (typeof envDefault === 'string' && supportedLocales.includes(envDefault)) {
    return envDefault;
  }

  return supportedLocales.includes('es') ? 'es' : supportedLocales[0];
};

const resolveFallbackLocale = (): string => {
  if (supportedLocales.includes('es') && supportedLocales.includes('en')) {
    return 'en';
  }
  return supportedLocales[0];
};

export const i18n = createI18n({
  legacy: false,
  locale: resolveDefaultLocale(),
  fallbackLocale: resolveFallbackLocale(),
  messages,
  warnHtmlMessage: false,
});

export const getSupportedLocales = () => supportedLocales;

export default i18n;

