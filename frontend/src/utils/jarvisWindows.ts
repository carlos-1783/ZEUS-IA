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
  // PERSEO · get_sales_performance
  current: 'Periodo actual',
  previous: 'Periodo anterior',
  change_pct: 'Variación (%)',
  tpv_count: 'Tickets del TPV',
  tpv_total: 'Ventas del TPV',
  invoice_count: 'Facturas',
  invoice_total: 'Importe facturado',
  top_products: 'Lo más vendido',
  quantity: 'Cantidad',
  revenue: 'Ingresos',
  // RAFAEL · get_daily_close / get_pending_invoices
  date: 'Fecha',
  tickets: 'Tickets',
  subtotal: 'Base imponible',
  tax_total: 'IVA',
  average_ticket: 'Ticket medio',
  by_payment_method: 'Por forma de pago',
  count: 'Número',
  cash_closures: 'Cierres de caja',
  cash_count_recorded: 'Arqueo de caja hecho',
  counted_cash: 'Efectivo contado',
  expected_cash: 'Efectivo esperado',
  difference: 'Descuadre',
  terminal: 'Caja',
  note: 'Nota',
  top: 'Destacados',
  pending_count: 'Facturas pendientes de cobro',
  pending_amount: 'Importe pendiente',
  overdue: 'Vencida',
  overdue_count: 'Facturas vencidas',
  overdue_amount: 'Importe vencido',
  drafts_count: 'Borradores sin emitir',
  invoice_number: 'Nº de factura',
  amount_due: 'Pendiente de cobro',
  due_date: 'Vencimiento',
  // THALOS · get_security_status
  by_action: 'Por decisión',
  by_severity: 'Por gravedad',
  at: 'Fecha',
  // AFRODITA · get_attendance_status / get_today_agenda
  checkins_today: 'Entradas de hoy',
  currently_in: 'Dentro ahora',
  employees_today: 'Empleados que han fichado hoy',
  late_today: 'Entradas con retraso',
  with_irregularities_today: 'Fichajes con incidencias',
  hours_closed_today: 'Horas cerradas hoy',
  biometric_data_used: 'Usa datos biométricos',
  reservations: 'Reservas',
  meetings: 'Reuniones',
  guests: 'Comensales',
  items: 'Agenda de hoy',
  kind: 'Tipo',
  time: 'Hora',
  // JUSTICIA · review_contracts
  by_status: 'Por estado',
  pending_review: 'Pendientes de revisión',
  latest: 'Últimos documentos',
  version: 'Versión',
  integrity_sealed: 'Sellado de integridad',
  updated_at: 'Actualizado',
  // ZEUS · get_coordination_report
  activities_total: 'Actividades',
  activities_by_agent: 'Actividad por agente',
  problems: 'Tareas fallidas o bloqueadas',
  pending_approvals: 'Aprobaciones pendientes',
  generated_at: 'Generado',
  action_type: 'Acción',
  description: 'Descripción',
  error: 'Error',
};

// Valores (y claves dinámicas: decisiones THALOS, gravedades, formas de pago, estados) que el
// backend devuelve como identificadores en inglés o internos. Solo se traducen coincidencias exactas.
const VALUE_LABELS: Record<string, string> = {
  allow: 'Permitido',
  deny: 'Denegado',
  block: 'Bloqueado',
  blocked: 'Bloqueado',
  audit_pass: 'Auditoría superada',
  audit_fail: 'Auditoría fallida',
  alert: 'Aviso',
  marked_failed: 'Marcado como fallido',
  status_corrected: 'Estado corregido',
  info: 'Informativo',
  low: 'Baja',
  medium: 'Media',
  warn: 'Aviso',
  warning: 'Aviso',
  high: 'Alta',
  critical: 'Crítica',
  efectivo: 'Efectivo',
  tarjeta: 'Tarjeta',
  bizum: 'Bizum',
  transferencia: 'Transferencia',
  cash: 'Efectivo',
  card: 'Tarjeta',
  credit_card: 'Tarjeta',
  bank_transfer: 'Transferencia',
  qr: 'Pago QR',
  reservation: 'Reserva',
  meeting: 'Reunión',
  draft: 'Borrador',
  signed: 'Firmado',
  sent: 'Enviada',
  partially_paid: 'Cobrada en parte',
  paid: 'Cobrada',
  completed: 'Completada',
  failed: 'Fallida',
  pending: 'Pendiente',
  approved: 'Aprobada',
  rejected: 'Rechazada',
  checked_in: 'Dentro',
  checked_out: 'Fuera',
  not_available: 'No disponible',
  blocked_module: 'Bloqueado: módulo no activo',
  blocked_by_guard: 'Bloqueado por THALOS',
  blocked_by_safeguard: 'Bloqueado por seguridad',
  blocked_no_company: 'Bloqueado: sin empresa',
  blocked_requires_approval: 'Pendiente de aprobación',
  blocked_missing_handler: 'Bloqueado: acción no disponible',
  blocked_client_origin: 'Bloqueado: origen no permitido',
};

// Identificadores internos que no aportan nada al usuario en una ventana.
const HIDDEN_KEYS = new Set([
  'company_id', 'user_id', 'tenant_id', 'request_id', 'correlation_id',
  'id', 'document_id', 'source', 'timezone',
]);

const MAX_FIGURES = 4;
const MAX_TABLE_ROWS = 8;
const MAX_TABLE_COLS = 5;

export function humanizeKey(key: string): string {
  if (LABELS[key]) return LABELS[key];
  if (VALUE_LABELS[key]) return VALUE_LABELS[key];
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
    return VALUE_LABELS[v] || v;
  }
  if (Array.isArray(v)) return v.map(formatScalar).join(', ');
  if (isPlainObject(v)) {
    // p. ej. una forma de pago {total, count} -> "Total: 12,5 · Número: 3", nunca JSON crudo.
    return Object.entries(v)
      .filter(([k]) => !HIDDEN_KEYS.has(k))
      .map(([k, x]) => `${humanizeKey(k)}: ${formatScalar(x)}`)
      .join(' · ');
  }
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

// Estados de bloqueo honesto del backend (ChatResponse.status / execution.status):
// blocked_* (modulo, guard THALOS) y not_available (falta modelo/integracion real).
function isBlockedStatus(s: unknown): boolean {
  return typeof s === 'string' && (/^blocked/i.test(s) || s === 'not_available');
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

  const failed = data?.success === false;
  // Bloqueo de TODA la petición: status blocked_* de primer nivel (o una ejecución bloqueada en una
  // respuesta fallida). Sale UNA sola ventana ámbar con el motivo, no "error" + "bloqueo parcial".
  const wholeBlocked = isBlockedStatus(data?.status) || (failed && !!exec && isBlockedStatus(exec.status));

  if (!wholeBlocked && exec && isBlockedStatus(exec.status)) {
    blockedReasons.push(String(exec.message || exec.status));
  }

  const title = wholeBlocked
    ? /thalos|guard|safeguard/i.test(String(data?.status || exec?.status || ''))
      ? 'Acción bloqueada · Thalos'
      : 'Acción bloqueada'
    : failed
      ? 'No se pudo completar'
      : data?.needs_confirmation
        ? 'Pendiente de tu confirmación'
        : data?.needs_clarification
          ? 'Necesito un dato'
          : 'Respuesta';
  const kind: WinKind = wholeBlocked ? 'blocked' : failed ? 'error' : 'answer';
  const blockedText = String(message || exec?.message || '').trim();
  const main = emptyWindow(
    kind,
    title,
    src,
    wholeBlocked
      ? blockedText || 'El servidor ha bloqueado la petición; no se ha ejecutado nada.'
      : message || 'El agente no devolvió texto.',
  );
  if (wholeBlocked && exec?.message && String(exec.message).trim() !== blockedText) {
    main.rows.push({ label: 'Motivo', value: String(exec.message).trim() });
  }

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

  if (wholeBlocked) {
    // Los pasos bloqueados de un plan totalmente bloqueado van como motivos en la MISMA ventana.
    blockedReasons.forEach((r, i) => main.rows.push({ label: `Paso bloqueado ${i + 1}`, value: r }));
  } else if (blockedReasons.length) {
    // Solo cuando de verdad fue parcial: la respuesta principal se ejecutó y una parte no.
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

// ---------------------------------------------------------------------------------------------
// 📷 Bandeja de ZEUS (POST /api/v1/zeus/inbox): ventana con lo que el modelo leyó DE VERDAD.
// Lo que no se leyó llega a null y se muestra "no leído"; nunca se rellena ni se corrige.
// ---------------------------------------------------------------------------------------------
const INBOX_DOC_LABELS: Record<string, string> = {
  factura_proveedor: 'Factura de proveedor',
  ticket: 'Ticket',
  nomina: 'Nómina',
  albaran: 'Albarán',
  pedido: 'Pedido',
  contrato: 'Contrato',
  otro: 'Otro documento',
};
const INBOX_FIELD_LABELS: Array<[string, string]> = [
  ['proveedor', 'Proveedor'],
  ['nif', 'NIF'],
  ['fecha', 'Fecha'],
  ['numero', 'Número'],
  ['base', 'Base imponible'],
  ['iva', 'IVA'],
  ['total', 'Total'],
];

function inboxMoney(v: unknown): string {
  if (v === null || v === undefined || v === '') return 'no leído';
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString('es-ES', { style: 'currency', currency: 'EUR' })
    : String(v);
}

function agentName(a: unknown): string {
  const s = String(a || '');
  return s ? s.charAt(0) + s.slice(1).toLowerCase() : 'ZEUS';
}

export function windowForInboxItem(item: any, detail?: string): JarvisWindow {
  const src = sourceLabel('ZEUS');
  if (!item || item.status !== 'clasificado') {
    const w = emptyWindow(
      'blocked',
      'Documento guardado · sin clasificar',
      src,
      String(detail || item?.classification_error || 'La clasificación no está disponible ahora mismo.') +
        ' El documento queda en la bandeja de ZEUS como pendiente; no se ha leído ni repartido.',
    );
    return w;
  }
  const doc = INBOX_DOC_LABELS[item.doc_type] || 'Documento';
  const to = agentName(item.assigned_agent);
  const w = emptyWindow(
    'answer',
    `${doc} recibido · vía ZEUS`,
    `ZEUS → ${to}`,
    `ZEUS ha recibido tu foto y la ha dirigido a ${to} para revisión. ${String(item.notice || '')}`.trim(),
  );
  const f = item.fields || {};
  for (const [key, label] of INBOX_FIELD_LABELS) {
    const raw = f[key];
    const value = ['base', 'iva', 'total'].includes(key)
      ? inboxMoney(raw)
      : raw === null || raw === undefined || raw === ''
        ? 'no leído'
        : String(raw);
    w.rows.push({ label, value });
  }
  if (item.confidence) w.rows.push({ label: 'Confianza de la lectura', value: String(item.confidence) });
  const issues: string[] = Array.isArray(item.validation?.issues) ? item.validation.issues : [];
  issues.forEach((t, i) => w.rows.push({ label: `Aviso ${i + 1}`, value: String(t) }));
  return w;
}
