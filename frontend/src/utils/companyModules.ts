/**
 * Segmentación de módulos del menú según company_type (backend: GET /company/config, /auth/me).
 */

export type CompanyType = 'bar_restaurant' | 'office' | string

export type ModuleKey =
  | 'dashboard'
  | 'analytics'
  | 'tpv'
  | 'control_horario'
  | 'crm'
  | 'payroll'
  | 'settings'
  | 'admin'
  | 'agents'

export type ModuleMap = Partial<Record<ModuleKey, boolean>>

const MODULES_BY_TYPE: Record<string, ModuleKey[]> = {
  bar_restaurant: ['tpv', 'control_horario', 'payroll'],
  office: ['crm', 'analytics'],
}

const BASE_MODULES: ModuleKey[] = ['dashboard', 'settings', 'agents']

/** Mapa por defecto si el backend aún no devolvió módulos (compatibilidad). */
export function defaultModulesForType(companyType: CompanyType | null | undefined): ModuleMap {
  const ct = (companyType || 'bar_restaurant').toLowerCase()
  const allowed = new Set(MODULES_BY_TYPE[ct] || MODULES_BY_TYPE.bar_restaurant)
  return {
    dashboard: true,
    analytics: allowed.has('analytics'),
    tpv: allowed.has('tpv'),
    control_horario: allowed.has('control_horario'),
    crm: allowed.has('crm'),
    payroll: allowed.has('payroll'),
    settings: true,
    agents: true,
    admin: false,
  }
}

export function normalizeModulesFromApi(
  modules: ModuleMap | null | undefined,
  companyType?: CompanyType | null
): ModuleMap {
  if (modules && typeof modules === 'object' && Object.keys(modules).length > 0) {
    return {
      dashboard: modules.dashboard !== false,
      analytics: !!modules.analytics,
      tpv: !!modules.tpv,
      control_horario: !!modules.control_horario,
      crm: !!(modules.crm || (modules as any).clients || (modules as any).payments),
      payroll: !!modules.payroll,
      settings: modules.settings !== false,
      agents: modules.agents !== false,
      admin: !!modules.admin,
    }
  }
  return defaultModulesForType(companyType)
}

export function isModuleVisible(
  modules: ModuleMap | null | undefined,
  key: ModuleKey,
  opts?: { isSuperuser?: boolean; isEmployee?: boolean }
): boolean {
  if (opts?.isSuperuser) return true
  if (opts?.isEmployee) {
    if (key === 'payroll' || key === 'admin' || key === 'crm' || key === 'analytics') return false
    if (key === 'tpv' || key === 'control_horario' || key === 'dashboard') {
      return modules?.[key] !== false
    }
    return false
  }
  const m = modules || defaultModulesForType(null)
  if (key === 'dashboard' || key === 'settings' || key === 'agents') {
    return m[key] !== false
  }
  return !!m[key]
}

/** Rutas protegidas → módulo requerido */
export const ROUTE_MODULE_MAP: Record<string, ModuleKey> = {
  TPV: 'tpv',
  ControlHorario: 'control_horario',
  OfficeCrm: 'crm',
  PayrollDrafts: 'payroll',
}

export function routeAllowed(
  routeName: string | undefined | null,
  modules: ModuleMap | null | undefined,
  opts?: { isSuperuser?: boolean; isEmployee?: boolean }
): boolean {
  if (!routeName) return true
  if (opts?.isSuperuser) return true
  const mod = ROUTE_MODULE_MAP[routeName]
  if (!mod) return true
  return isModuleVisible(modules, mod, opts)
}
