/**
 * Paneles holograma del orbe: «enséñame la facturación / las tareas / el marketing / la actividad».
 *
 * Es solo LECTURA de pantallas que ya existen en la app, con los mismos endpoints (tenant por sesión):
 *   facturación -> GET /api/v1/invoices/            (facturas de las empresas del usuario)
 *   tareas      -> GET /api/v1/analytics/events     (lo mismo que el KPI «Tareas 24h»)
 *   marketing   -> GET /api/v1/marketing/integrations/metrics
 *   actividad   -> GET /api/v1/activities/{AGENTE}
 * Nunca se inventan cifras: sin filas -> «Sin datos …»; si el servidor dice que algo no está
 * conectado o implementado, se muestra su motivo tal cual. Cualquier otra frase va al agente.
 */

export type HoloKey = 'billing' | 'tasks' | 'marketing' | 'activity';

export interface HoloFigure {
  label: string;
  value: string;
}

export interface HoloPanel {
  key: HoloKey;
  title: string;
  source: string;
  state: 'ok' | 'empty' | 'error';
  message: string;
  figures: HoloFigure[];
  columns: string[];
  rows: string[][];
}

export const HOLO_TITLES: Record<HoloKey, string> = {
  billing: 'Facturación',
  tasks: 'Tareas · últimas 24 h',
  marketing: 'Marketing',
  activity: 'Actividad',
};

function fold(text: string): string {
  return String(text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[¿?¡!.,;:]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const SHOW_VERB =
  '(?:ensename|ensenamelo|muestrame|muestra|abre|abreme|ver|veo|pon|ponme|despliega|saca|sacame|quiero ver|dejame ver|vamos a ver|ir a|llevame a)';
const TOPICS: Array<[HoloKey, string]> = [
  ['billing', '(?:facturacion|facturas?)'],
  ['tasks', '(?:tareas?)'],
  ['marketing', '(?:marketing|campanas?)'],
  ['activity', '(?:actividad|registro de actividad)'],
];

/**
 * Coletillas que cada panel ACEPTA porque de verdad muestra eso. Un panel nunca acepta un periodo que
 * no aplica: «enséñame las facturas de hoy» no abre «Facturación» (que lista las últimas, sin filtrar
 * por fecha) sino que va al chat del agente, que sí filtra por hoy. Cualquier otra coletilla (de hoy,
 * de ayer, de la semana, del mes, del trimestre, una fecha…) => no hay panel => va al agente.
 *   facturación: últimas facturas (sin periodo)      -> solo «recientes»
 *   tareas:      eventos de las últimas 24 h           -> «recientes», «de las últimas 24 horas»
 *   marketing:   métricas de las integraciones          -> ninguna
 *   actividad:   del agente, últimos 7 días             -> «recientes», «del agente», «de los últimos 7 días»
 */
const SUFFIXES: Record<HoloKey, string[]> = {
  billing: ['reciente', 'recientes'],
  tasks: ['reciente', 'recientes', 'de las ultimas 24 horas', 'de las ultimas 24 h', 'de las ultimas veinticuatro horas'],
  marketing: [],
  activity: ['reciente', 'recientes', 'del agente', 'de los ultimos 7 dias', 'de los ultimos siete dias'],
};

/**
 * Detecta la petición de una PANTALLA (verbo de mostrar + tema, o el tema a secas). Conservador a
 * propósito: «crea una factura» o «lanza una campaña» NO abren panel; van al agente. Tampoco una
 * petición acotada a un periodo que el panel no aplica (ver SUFFIXES).
 */
export function detectHoloRequest(message: string): HoloKey | null {
  const m = fold(message).replace(/^(?:oye |hey |ok )?(?:jarvis|zeus)\s*/, '');
  if (!m || m.split(' ').length > 9) return null;
  for (const [key, topic] of TOPICS) {
    const sfx = SUFFIXES[key].length ? `(?:\\s+(?:${SUFFIXES[key].join('|')}))?` : '';
    const withVerb = new RegExp(
      `^(?:${SHOW_VERB})\\s+(?:me\\s+)?(?:la |las |el |los |mi |mis |toda la |todas las )?(?:pantalla de |panel de )?${topic}${sfx}$`,
    );
    const bare = new RegExp(`^(?:la |las |el |los |mi |mis )?(?:pantalla de |panel de )?${topic}$`);
    if (withVerb.test(m) || bare.test(m)) return key;
  }
  return null;
}

const eur = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' });
function money(v: unknown): string {
  // null/undefined/'' = sin dato: '—'. Number(null) daría 0 y pintaría «0,00 €», una cifra inventada.
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  return Number.isFinite(n) ? eur.format(n) : '—';
}
function shortDate(iso: unknown): string {
  if (!iso) return '—';
  const d = new Date(String(iso));
  return Number.isNaN(d.getTime())
    ? String(iso)
    : d.toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

const STATUS_ES: Record<string, string> = {
  draft: 'Borrador',
  sent: 'Enviada',
  paid: 'Pagada',
  partially_paid: 'Pago parcial',
  overdue: 'Vencida',
  cancelled: 'Anulada',
  void: 'Anulada',
  completed: 'Completado',
  success: 'Completado',
  executed: 'Ejecutado',
  failed: 'Fallido',
  error: 'Error',
  pending: 'Pendiente',
  needs_confirmation: 'Pendiente de confirmar',
  rejected: 'Rechazado',
};
function statusEs(s: unknown): string {
  const k = String(s || '').toLowerCase();
  return STATUS_ES[k] || (k ? k.replace(/_/g, ' ') : '—');
}

function base(key: HoloKey, source: string): HoloPanel {
  return { key, title: HOLO_TITLES[key], source, state: 'ok', message: '', figures: [], columns: [], rows: [] };
}

type Getter = (endpoint: string) => Promise<any>;

async function loadBilling(get: Getter): Promise<HoloPanel> {
  const p = base('billing', 'RAFAEL · facturas de tu empresa');
  const data = await get('/api/v1/invoices/?limit=8');
  const list: any[] = Array.isArray(data?.data) ? data.data : [];
  if (!list.length) {
    p.state = 'empty';
    p.message = 'Sin datos: todavía no hay facturas registradas.';
    return p;
  }
  // Solo se suman las facturas con importe pendiente conocido; las que lo tienen a null (filas
  // antiguas) no cuentan como 0: se indica cuántas tienen dato y, si ninguna, '—'.
  const withDue = list.filter((i) => i?.amount_due !== null && i?.amount_due !== undefined && Number.isFinite(Number(i.amount_due)));
  const due = withDue.length ? withDue.reduce((acc, i) => acc + Number(i.amount_due), 0) : null;
  const dueLabel = withDue.length === list.length
    ? `Pendiente de cobro (últimas ${list.length})`
    : `Pendiente de cobro (${withDue.length} de las últimas ${list.length} con dato)`;
  p.figures = [
    { label: 'Facturas en total', value: String(data?.total ?? list.length) },
    { label: dueLabel, value: money(due) },
  ];
  p.columns = ['Nº', 'Fecha', 'Total', 'Estado'];
  p.rows = list.map((i) => [String(i?.invoice_number || i?.id || '—'), shortDate(i?.issue_date), money(i?.total), statusEs(i?.status)]);
  return p;
}

async function loadTasks(get: Getter): Promise<HoloPanel> {
  const p = base('tasks', 'ZEUS · eventos reales de los agentes');
  const data = await get('/api/v1/analytics/events?hours=24');
  const events: any[] = Array.isArray(data?.events) ? data.events : [];
  if (!events.length) {
    p.state = 'empty';
    p.message = 'Sin datos: ningún agente ha registrado tareas en las últimas 24 horas.';
    return p;
  }
  const failed = events.filter((e) => /fail|error/i.test(String(e?.status || ''))).length;
  p.figures = [
    { label: 'Tareas 24 h', value: String(data?.total ?? events.length) },
    { label: 'Con error', value: String(failed) },
  ];
  p.columns = ['Tarea', 'Agente', 'Estado', 'Cuándo'];
  p.rows = events.slice(0, 10).map((e) => [String(e?.type || '—'), String(e?.agent || '—'), statusEs(e?.status), shortDate(e?.created_at)]);
  return p;
}

async function loadMarketing(get: Getter): Promise<HoloPanel> {
  const p = base('marketing', 'PERSEO · integraciones de marketing');
  const data = await get('/api/v1/marketing/integrations/metrics');
  const m = data?.data || {};
  if (!m.enabled) {
    p.state = 'empty';
    p.message = `Sin datos de marketing: ${m.reason || 'no hay métricas disponibles.'}`;
    return p;
  }
  const LABELS: Record<string, string> = { ad_spend: 'Inversión', leads: 'Leads', cpl: 'Coste por lead', engagement: 'Interacción' };
  p.figures = Object.entries(LABELS)
    .filter(([k]) => m[k] !== undefined && m[k] !== null)
    .map(([k, label]) => ({ label, value: k === 'ad_spend' || k === 'cpl' ? money(m[k]) : String(m[k]) }));
  if (!p.figures.length) {
    p.state = 'empty';
    p.message = 'Sin datos: las plataformas conectadas aún no han devuelto métricas.';
  }
  return p;
}

async function loadActivity(get: Getter, agent: string): Promise<HoloPanel> {
  const name = (agent || 'ZEUS').split(' ')[0].toUpperCase();
  const p = base('activity', `${name} · últimos 7 días`);
  const data = await get(`/api/v1/activities/${encodeURIComponent(name)}?days=7`);
  const list: any[] = Array.isArray(data?.activities) ? data.activities : [];
  if (!list.length) {
    p.state = 'empty';
    p.message = `Sin datos: ${name} no tiene actividad registrada esta semana.`;
    return p;
  }
  const ok = list.filter((a) => /complet|success|execut/i.test(String(a?.status || ''))).length;
  p.figures = [
    { label: 'Acciones', value: String(list.length) },
    { label: 'Completadas', value: String(ok) },
  ];
  p.columns = ['Qué', 'Estado', 'Cuándo'];
  p.rows = list.slice(0, 10).map((a) => [String(a?.description || a?.action_type || '—'), statusEs(a?.status), shortDate(a?.created_at)]);
  return p;
}

/** Carga el panel; un fallo de red/permiso se muestra como error honesto, nunca como datos. */
export async function loadHoloPanel(key: HoloKey, get: Getter, agentName: string): Promise<HoloPanel> {
  try {
    if (key === 'billing') return await loadBilling(get);
    if (key === 'tasks') return await loadTasks(get);
    if (key === 'marketing') return await loadMarketing(get);
    return await loadActivity(get, agentName);
  } catch (err: any) {
    const p = base(key, 'No disponible');
    p.state = 'error';
    const status = Number(err?.status || err?.response?.status || 0);
    p.message =
      status === 401 || status === 403
        ? 'No tienes permiso para ver esta pantalla con tu sesión actual.'
        : `No se pudieron cargar los datos: ${String(err?.message || 'error desconocido')}.`;
    return p;
  }
}
