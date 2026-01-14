import { createI18n } from 'vue-i18n';
import esMessages from './locales/es.json';
import enMessages from './locales/en.json';

const messages = {
  es: esMessages,
  en: enMessages,
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

