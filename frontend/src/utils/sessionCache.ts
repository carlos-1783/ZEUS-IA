/**
 * Limpia caché de datos de sesión anterior (TPV, CRM local, onboarding)
 * sin borrar token ni preferencias globales de idioma/tema.
 */
export function clearSessionCaches(): void {
  const keepExact = new Set(['auth_token', 'refresh_token', 'zeus_locale', 'zeus_theme', 'zeus-pwa-installed'])
  const keepPrefixes = ['zeus_locale', 'zeus_theme']

  try {
    const remove: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (!key || keepExact.has(key)) continue
      if (keepPrefixes.some((p) => key.startsWith(p))) continue
      if (
        key.startsWith('zeus_tpv_') ||
        key.startsWith('tpv_') ||
        key.includes('comanda') ||
        key.startsWith('zeus_notification_') ||
        key.startsWith('zeus_admin_') ||
        key.startsWith('zeus_session_') ||
        key.startsWith('ble_printer_')
      ) {
        remove.push(key)
      }
    }
    remove.forEach((k) => localStorage.removeItem(k))
  } catch {
    /* ignore */
  }

  try {
    sessionStorage.removeItem('zeus_onboarding_setup_done')
  } catch {
    /* ignore */
  }
}
