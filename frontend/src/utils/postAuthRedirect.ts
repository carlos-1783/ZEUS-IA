/**
 * Tras login/registro: dashboard o configuración inicial (empleados, redes, horario).
 */
export async function resolvePostAuthPath(
  fallback = '/dashboard',
  token?: string | null,
): Promise<string> {
  if (!token) return fallback
  if (fallback.startsWith('/onboarding-setup')) return fallback

  try {
    const api = (await import('@/services/api')).default
    const status = await api.get('/api/v1/auth/onboarding/status', token)
    const questionnaireCompleted = !!status?.questionnaire_completed
    const validationOk = status?.validation?.ok === true
    if (!questionnaireCompleted || !validationOk) {
      return '/onboarding-setup'
    }
  } catch (e) {
    console.warn('postAuthRedirect: no se pudo leer onboarding/status', e)
    if (fallback === '/dashboard') {
      return '/onboarding-setup'
    }
  }
  return fallback
}
