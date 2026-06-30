/**
 * ZEUS safe lock v1 — frontend truth rules (no fallback REAL).
 */

export type SafeExecutionState = 'REAL' | 'SIMULATED' | 'UNKNOWN' | 'ERROR'

export interface ZeusTruthSlice {
  execution_mode?: string | null
  writes_enabled?: boolean | null
}

const REAL_ALIASES = new Set([
  'REAL',
  'REAL_SAFE',
  'REAL_ACTIVE',
  'REAL_WITH_OUTPUT',
  'REAL_CONDITIONAL',
])

const SIM_ALIASES = new Set(['SIMULATED', 'SIMULATION', 'SIMULADO', 'READ_ONLY', 'PARTIAL'])

/** Map backend badge / classification → safe UI state. Unknown is never REAL. */
export function resolveModuleBadge(backendValue?: string | null): SafeExecutionState {
  if (backendValue == null || String(backendValue).trim() === '') return 'UNKNOWN'
  const upper = String(backendValue).trim().toUpperCase()
  if (upper === 'ERROR') return 'ERROR'
  if (REAL_ALIASES.has(upper)) return 'REAL'
  if (SIM_ALIASES.has(upper) || upper.includes('SIMUL')) return 'SIMULATED'
  if (upper === 'PARTIAL_REAL' || upper === 'EMPTY_REAL') return 'SIMULATED'
  return 'UNKNOWN'
}

/** REAL badge only when backend confirms execution_mode REAL + writes_enabled. */
export function isVerifiedReal(zeus: ZeusTruthSlice | null | undefined): boolean {
  if (!zeus) return false
  return zeus.execution_mode === 'REAL' && zeus.writes_enabled === true
}

export function resolveThalosModuleBadge(
  module: string,
  status: {
    module_classification?: Record<string, string>
    thalos_control?: { ui_badge?: string }
  } | null | undefined,
): SafeExecutionState {
  if (!status) return 'UNKNOWN'
  const cls = status.module_classification?.[module]
  if (cls === 'REAL_SAFE' || cls === 'REAL_CONDITIONAL') return 'REAL'
  if (cls && (cls.includes('SIMUL') || cls === 'READ_ONLY')) return 'SIMULATED'
  return resolveModuleBadge(status.thalos_control?.ui_badge)
}

export function resolveJusticiaModuleBadge(
  key: string,
  status: {
    module_badges?: Record<string, string>
    JUSTICE_REAL_AUDIT_ENABLED?: boolean
  } | null | undefined,
): SafeExecutionState {
  if (!status) return 'UNKNOWN'
  const fromBackend = status.module_badges?.[key]
  if (fromBackend) return resolveModuleBadge(fromBackend)
  if (key === 'system_audit') {
    return status.JUSTICE_REAL_AUDIT_ENABLED ? 'REAL' : 'SIMULATED'
  }
  return 'UNKNOWN'
}
