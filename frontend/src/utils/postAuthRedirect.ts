/**
 * Tras login/registro: dashboard o configuración inicial (empleados, redes, horario).
 * La fuente de verdad es la API /onboarding/status (BD), no sessionStorage.
 */

const ONBOARDING_DONE_KEY = 'zeus_onboarding_setup_done'

export function markOnboardingSetupDone(): void {
  try {
    sessionStorage.setItem(ONBOARDING_DONE_KEY, '1')
  } catch {
    /* ignore */
  }
}

export function clearOnboardingSetupDone(): void {
  try {
    sessionStorage.removeItem(ONBOARDING_DONE_KEY)
  } catch {
    /* ignore */
  }
}

export function isOnboardingSetupComplete(status: Record<string, unknown> | null | undefined): boolean {
  if (!status || typeof status !== 'object') return false
  if (status.setup_completed === true) return true
  if (status.questionnaire_completed === true) return true
  if (status.operational_profile_completed === true) return true
  if (status.user_onboarding_backup === true) return true
  return false
}

export async function resolvePostAuthPath(
  fallback = '/dashboard',
  token?: string | null,
): Promise<string> {
  if (!token) return fallback
  if (fallback.startsWith('/onboarding-setup')) return fallback

  try {
    const api = (await import('@/services/api')).default
    const status = await api.get('/api/v1/auth/onboarding/status', token)
    if (isOnboardingSetupComplete(status)) {
      markOnboardingSetupDone()
      return fallback
    }
    return '/onboarding-setup'
  } catch (e) {
    console.warn('postAuthRedirect: no se pudo leer onboarding/status', e)
    try {
      if (sessionStorage.getItem(ONBOARDING_DONE_KEY) === '1') {
        return fallback
      }
    } catch {
      /* ignore */
    }
    if (fallback === '/dashboard') {
      return '/onboarding-setup'
    }
  }
  return fallback
}
