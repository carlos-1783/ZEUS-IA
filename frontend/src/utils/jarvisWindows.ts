/**
 * Fase 2 JARVIS: convierte la respuesta REAL de POST /chat/{agente}/chat en "ventanas" del orbe.
 *
 * No inventa nada: cada cifra, fila o tabla sale de los campos que devuelve el backend
 * (`execution.metrics` / `execution.data` del resultado ZeusExecutionResult, `execution.steps[].data`,
 * `steps` del plan J9b y `evidence` J10). Si el backend no devuelve datos estructurados, la ventana
 * muestra solo el texto de la respuesta.
 */
import type { ChatEvidence } from './chatApi';

export interface WinFigure {
  label: string;
  value: string;
}
export interface WinRow {
  label: string;
  value: string;
}
export interface WinTable {
  title: string;
  columns: string[];
  columnLabels: string[];
  rows: string[][];
  more: number;
}
export type WinKind = 'answer' | 'blocked' | 'error' | 'info';

export interface JarvisWindow {
  id: string;
  kind: WinKind;
  title: string;
  source: string;
  text: string;
  figures: WinFigure[];
  rows: WinRow[];
  tables: WinTable[];
  evidence: ChatEvidence[];
  nextStep: string;
  needsConfirmation: boolean;
}

const LABELS: Record<string, string> = {
  open_leads: 'Leads abiertos',
  high_priority: 'Prioridad alta',
  with_meeting: 'Con reunión',
  events_total: 'Eventos',
  denied_total: 'Rechazados',
  critical_total: 'Críticos',
  window_days: 'Días analizados',
  total_skus: 'Referencias',
  total_units: 'Unidades',
  low_stock_count: 'Con stock bajo',
  low_stock_items: 'Stock bajo',
  legal_documents: 'Documentos legales',
  compliance_events: 'Eventos de cumplimiento',
  pending: 'Pendientes',
  recent_denials: 'Últimos rechazos',
  name: 'Nombre',
  sku: 'SKU',
  stock: 'Stock',
  rule: 'Regla',
  severity: 'Gravedad',
  event_type: 'Tipo',
  status: 'Estado',
  agent: 'Agente',
  summary: 'Resumen',
  detail: 'Detalle',
  step: 'Paso',
  type: 'Tipo',
  title: 'Título',
  email: 'Email',
  created_at: 'Fecha',
  total: 'Total',
  amount: 'Importe',
};

// Identificadores internos que no aportan nada al usuario en una ventana.
const HIDDEN_KEYS = new Set(['company_id', 'user_id', 'tenant_id', 'request_id', 'correlation_id']);

const MAX_FIGURES = 4;
const MAX_TABLE_ROWS = 8;
const MAX_TABLE_COLS = 5;

export function humanizeKey(key: string): string {
  if (LABELS[key]) return LABELS[key];
  const s = String(key).replace(/[_-]+/g, ' ').trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : key;
}

export function formatScalar(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'boolean') return v ? 'Sí' : 'No';
  if (typeof v === 'number') {
    return Number.isFinite(v) ? v.toLocaleString('es-ES', { maximumFractionDigits: 2 }) : '—';
  }
  if (typeof v === 'string') {
    // Fechas ISO -> formato local legible
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v)) {
      const d = new Date(v);
      if (!Number.isNaN(d.getTime())) {
        return d.toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
      }
    }
    return v;
  }
  if (Array.isArray(v)) return v.map(formatScalar).join(', ');
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === 'object' && !Array.isArray(v);
}

function tableFrom(title: string, list: Record<string, unknown>[]): WinTable {
  const cols: string[] = [];
  for (const row of list.slice(0, MAX_TABLE_ROWS)) {
    for (const k of Object.keys(row)) {
      if (!HIDDEN_KEYS.has(k) && !cols.includes(k) && !isPlainObject(row[k])) cols.push(k);
      if (cols.length >= MAX_TABLE_COLS) break;
    }
    if (cols.length >= MAX_TABLE_COLS) break;
  }
  return {
    title,
    columns: cols,
    columnLabels: cols.map(humanizeKey),
    rows: list.slice(0, MAX_TABLE_ROWS).map((r) => cols.map((c) => formatScalar(r[c]))),
    more: Math.max(0, list.length - MAX_TABLE_ROWS),
  };
}

/** Reparte un objeto de datos del backend en cifras, filas clave/valor y tablas. */
export function shapeData(
  data: Record<string, unknown>,
  out: { figures: WinFigure[]; rows: WinRow[]; tables: WinTable[] },
  prefix = '',
): void {
  for (const [key, value] of Object.entries(data)) {
    if (HIDDEN_KEYS.has(key)) continue;
    const label = prefix ? `${prefix} · ${humanizeKey(key)}` : humanizeKey(key);
    if (typeof value === 'number' && Number.isFinite(value) && !prefix && out.figures.length < MAX_FIGURES) {
      out.figures.push({ label, value: formatScalar(value) });
    } else if (Array.isArray(value)) {
      if (!value.length) {
        out.rows.push({ label, value: 'Ninguno' });
      } else if (value.every(isPlainObject)) {
        const t = tableFrom(label, value as Record<string, unknown>[]);
        if (t.columns.length) out.tables.push(t);
      } else {
        out.rows.push({ label, value: formatScalar(value) });
      }
    } else if (isPlainObject(value)) {
      if (!prefix) shapeData(value, out, label);
      else out.rows.push({ label, value: formatScalar(value) });
    } else {
      out.rows.push({ label, value: formatScalar(value) });
    }
  }
}

function isBlockedStatus(s: unknown): boolean {
  return typeof s === 'string' && /^blocked/i.test(s);
}

let seq = 0;
function newId(): string {
  seq += 1;
  return `w${Date.now().toString(36)}${seq}`;
}

function emptyWindow(kind: WinKind, title: string, source: string, text: string): JarvisWindow {
  return {
    id: newId(),
    kind,
    title,
    source,
    text,
    figures: [],
    rows: [],
    tables: [],
    evidence: [],
    nextStep: '',
    needsConfirmation: false,
  };
}

export function sourceLabel(agent: string, at: Date = new Date()): string {
  const hhmm = at.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  const name = String(agent || 'Agente').trim().split(/\s+/)[0] || 'Agente';
  return `${name.charAt(0).toUpperCase()}${name.slice(1).toLowerCase()} · ${hhmm}`;
}

function detailText(body: any, status: number): string {
  const d = body?.detail ?? body?.message ?? body?.error;
  if (typeof d === 'string' && d.trim()) return d.trim();
  if (isPlainObject(d)) {
    const msg = (d as any).message || (d as any).error || (d as any).reason;
    if (typeof msg === 'string' && msg.trim()) return msg.trim();
    try {
      return JSON.stringify(d);
    } catch {
      /* nada */
    }
  }
  return `El servidor respondió ${status}.`;
}

/**
 * Respuesta HTTP no satisfactoria -> ventana honesta.
 * 403 = THALOS rechazó la petición; 501/503 = función no disponible (p. ej. AEAT/Verifactu sin
 * credenciales, integración sin configurar): ambas son BLOQUEOS (borde ámbar), nunca se fingen.
 */
export function windowForHttpError(status: number, body: any, agent: string): JarvisWindow {
  const text = detailText(body, status);
  const src = sourceLabel(agent);
  if (status === 403) return emptyWindow('blocked', 'Acción bloqueada · Thalos', src, text);
  if (status === 501 || status === 503) {
    return emptyWindow('blocked', 'Acción bloqueada · no disponible', src, text);
  }
  if (status === 401) return emptyWindow('error', 'Sesión caducada', src, 'Vuelve a iniciar sesión para seguir hablando con el agente.');
  if (status === 429) return emptyWindow('error', 'Demasiadas peticiones', src, text);
  return emptyWindow('error', 'No se pudo completar', src, text);
}

/** Respuesta 200 del chat -> una ventana de respuesta y, si procede, una de bloqueo. */
export function windowsForChatResponse(data: any, agentFallback: string): JarvisWindow[] {
  const agent = String(data?.agent || agentFallback || 'Agente');
  const src = sourceLabel(agent);
  const message = String(data?.message || data?.error || '').trim();
  const exec = isPlainObject(data?.execution) ? (data.execution as Record<string, any>) : null;

  const wins: JarvisWindow[] = [];
  const blockedReasons: string[] = [];

  if (exec && isBlockedStatus(exec.status)) blockedReasons.push(String(exec.message || exec.status));
  if (isBlockedStatus(data?.status)) blockedReasons.push(String(data?.message || data.status));

  const failed = data?.success === false;
  const title = failed
    ? 'No se pudo completar'
    : data?.needs_confirmation
      ? 'Pendiente de tu confirmación'
      : data?.needs_clarification
        ? 'Necesito un dato'
        : 'Respuesta';
  const main = emptyWindow(failed ? 'error' : 'answer', title, src, message || 'El agente no devolvió texto.');

  if (exec) {
    const shaped = { figures: main.figures, rows: main.rows, tables: main.tables };
    if (isPlainObject(exec.metrics) && Object.keys(exec.metrics).length) shapeData(exec.metrics, shaped);
    if (isPlainObject(exec.data) && Object.keys(exec.data).length) shapeData(exec.data, shaped);
    if (Array.isArray(exec.steps)) {
      for (const st of exec.steps) {
        if (isPlainObject(st) && isPlainObject(st.data) && Object.keys(st.data).length) {
          shapeData(st.data, shaped);
        }
      }
    }
  }

  // J9b: pasos del plan multiagente (agente, estado y resumen por paso), tal cual del servidor.
  if (Array.isArray(data?.steps) && data.steps.length) {
    const plan = data.steps.filter(isPlainObject) as Record<string, unknown>[];
    for (const st of plan) {
      if (isBlockedStatus(st.status)) {
        blockedReasons.push(`${st.agent || 'Agente'}: ${String(st.summary || st.detail || st.status)}`);
      }
    }
    const t = tableFrom('Pasos del plan', plan);
    if (t.columns.length) main.tables.push(t);
  }

  main.evidence = Array.isArray(data?.evidence) ? data.evidence.filter((e: any) => e && e.url) : [];
  main.nextStep = data?.next_step ? String(data.next_step) : '';
  main.needsConfirmation = Boolean(data?.needs_confirmation && data?.approval_id);
  wins.push(main);

  if (blockedReasons.length) {
    const b = emptyWindow('blocked', 'Acción bloqueada', src, 'El servidor ha bloqueado parte de la petición: esa parte no se ha ejecutado.');
    b.rows = blockedReasons.map((r, i) => ({ label: `Motivo ${i + 1}`, value: r }));
    wins.push(b);
  }
  return wins;
}

export function infoWindow(title: string, source: string, text: string): JarvisWindow {
  return emptyWindow('info', title, source, text);
}

export function errorWindow(title: string, source: string, text: string): JarvisWindow {
  return emptyWindow('error', title, source, text);
}
