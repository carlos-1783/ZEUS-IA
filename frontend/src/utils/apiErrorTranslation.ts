/**
 * Traducción de errores de validación del backend (FastAPI/Pydantic/
 * email-validator) a mensajes en español.
 *
 * Origen: esta lógica vivía duplicada solo dentro de Register.vue. Se
 * extrae aquí para que cualquier flujo que reciba errores crudos del
 * backend (axios o fetch) pueda reutilizarla sin reimplementarla —
 * ver Hallazgo 6 de AUDIT_FRONTEND_CIERRE.md: el mismo bug (mensaje de
 * Pydantic en inglés crudo) se repetía en OnboardingSetup.vue porque
 * usa `services/api.ts` (fetch) y nunca pasaba por esta tabla.
 *
 * Se busca coincidencia parcial (case-insensitive) sobre el mensaje
 * real; si no hay ninguna coincidencia, se usa un fallback genérico
 * por campo — nunca se debe mostrar el texto en inglés tal cual.
 */

export const KNOWN_MESSAGE_TRANSLATIONS: Array<{ match: RegExp; es: string }> = [
  { match: /domain name .* is reserved/i, es: 'no se permite usar un dominio de correo reservado para pruebas' },
  { match: /is not valid.*@-sign|@-sign.*not valid/i, es: 'no tiene un formato válido' },
  { match: /not a valid email address/i, es: 'no es una dirección de correo válida' },
  { match: /field required/i, es: 'es obligatorio' },
  { match: /already registered/i, es: 'ya está registrado' },
  { match: /ensure this value has at least/i, es: 'es demasiado corto' },
  { match: /string does not match/i, es: 'tiene un formato no válido' },
]

/** Heurística simple: ¿el mensaje ya viene redactado en español por el backend? */
export function looksSpanish(text: string): boolean {
  return /[áéíóúñÁÉÍÓÚÑ]/.test(text) || /\b(el|la|los|las|correo|contraseña|cuenta)\b/i.test(text)
}

/** Convierte un nombre de campo en snake_case a una etiqueta legible genérica. */
function humanizeFieldName(field: string): string {
  const words = field.replace(/_/g, ' ').trim()
  return words ? `el campo "${words}"` : 'un campo del formulario'
}

/**
 * Traduce/reformula a español un mensaje de validación crudo del backend
 * para un campo concreto. Nunca devuelve el texto en inglés sin traducir —
 * si no hay traducción específica, cae en un mensaje genérico razonable
 * mencionando el campo afectado.
 *
 * `fieldLabels` permite que cada formulario aporte sus propias etiquetas
 * legibles (ej. { email: 'el correo electrónico' }); si el campo no está
 * en el mapa, se humaniza el nombre técnico del campo.
 */
export function translateFieldMessage(
  field: string,
  rawMsg: unknown,
  fieldLabels: Record<string, string> = {}
): string {
  const label = fieldLabels[field] || (field ? humanizeFieldName(field) : 'un campo del formulario')
  if (field === 'password') {
    return 'La contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula y un número.'
  }
  const known = KNOWN_MESSAGE_TRANSLATIONS.find((entry) => entry.match.test(String(rawMsg || '')))
  if (known) {
    return `Revisa ${label}: ${known.es}.`
  }
  return `Revisa ${label}: el valor introducido no es válido.`
}

/**
 * Traduce el `detail` crudo devuelto por el backend (FastAPI: string,
 * lista de errores de validación de Pydantic, u objeto) a un mensaje en
 * español apto para mostrar al usuario. Devuelve `null` si no hay nada
 * que traducir (el llamador debe aplicar su propio fallback genérico).
 */
export function translateValidationDetail(
  detail: unknown,
  fieldLabels: Record<string, string> = {}
): string | null {
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== 'object') return ''
        const record = item as { loc?: unknown[]; msg?: string; message?: string }
        const field = Array.isArray(record.loc) ? String(record.loc.slice(-1)[0]) : ''
        const msg = record.msg || record.message || ''
        return translateFieldMessage(field, msg, fieldLabels)
      })
      .filter(Boolean)
    return parts.length ? parts.join(' ') : null
  }

  if (typeof detail === 'string' && detail) {
    const known = KNOWN_MESSAGE_TRANSLATIONS.find((entry) => entry.match.test(detail))
    if (known) return `Revisa los datos introducidos: ${known.es}.`
    return looksSpanish(detail) ? detail : null
  }

  return null
}
