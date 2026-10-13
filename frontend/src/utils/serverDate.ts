/**
 * El backend serializa muchas fechas como ISO "naive" en UTC (datetime.utcnow().isoformat(),
 * sin "Z" ni desfase). `new Date("2026-10-13T08:05:00")` las interpreta como hora LOCAL y la
 * pantalla mostraba la hora UTC. Aquí, si la cadena ISO no trae zona, se trata como UTC.
 */
const ISO_NO_TZ = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

export function parseServerDate(value: unknown): Date | null {
  if (value === null || value === undefined || value === '') return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const s = String(value).trim();
  const d = new Date(ISO_NO_TZ.test(s) ? `${s.replace(' ', 'T')}Z` : s);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Hora local del navegador en formato es-ES (HH:MM). */
export function formatServerTime(value: unknown): string {
  const d = parseServerDate(value);
  return d ? d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }) : '';
}

/** Fecha y hora local del navegador en formato es-ES. */
export function formatServerDateTime(value: unknown): string {
  const d = parseServerDate(value);
  return d
    ? d.toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '';
}
