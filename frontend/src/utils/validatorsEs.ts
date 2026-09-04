/**
 * Validadores de formato real para CIF/NIF e IBAN (feedback inmediato en el
 * formulario de onboarding). Reflejan exactamente el algoritmo que aplica el
 * backend en backend/app/core/validators_es.py — el backend es la fuente de
 * verdad y revalida siempre, esto es solo UX.
 */

const NIF_CONTROL_LETTERS = 'TRWAGMYFPDXBNJZSQVHLCKE'
const CIF_CONTROL_LETTERS = 'JABCDEFGHI'
const CIF_LETTER_ONLY = new Set(['K', 'P', 'Q', 'S'])
const CIF_DIGIT_ONLY = new Set(['A', 'B', 'E', 'H'])

function clean(value: string): string {
  return String(value || '').replace(/[\s-]/g, '').toUpperCase()
}

export function validarNif(value: string): boolean {
  const v = clean(value)
  const m = /^(\d{8})([A-Z])$/.exec(v)
  if (!m) return false
  const numero = parseInt(m[1], 10)
  const letra = m[2]
  return NIF_CONTROL_LETTERS[numero % 23] === letra
}

export function validarCif(value: string): boolean {
  const v = clean(value)
  const m = /^([A-HJNPQRSUVW])(\d{7})([0-9A-J])$/.exec(v)
  if (!m) return false
  const letraInicial = m[1]
  const numero = m[2]
  const control = m[3]

  let sumaPar = 0
  let sumaImpar = 0
  for (let i = 0; i < numero.length; i += 1) {
    let d = parseInt(numero[i], 10)
    if (i % 2 === 0) {
      d *= 2
      if (d > 9) d -= 9
      sumaImpar += d
    } else {
      sumaPar += d
    }
  }
  const total = sumaPar + sumaImpar
  const digitoControl = (10 - (total % 10)) % 10
  const letraControl = CIF_CONTROL_LETTERS[digitoControl]

  if (CIF_LETTER_ONLY.has(letraInicial)) return control === letraControl
  if (CIF_DIGIT_ONLY.has(letraInicial)) return control === String(digitoControl)
  return control === String(digitoControl) || control === letraControl
}

export function validarNifCif(value: string): boolean {
  const v = clean(value)
  if (/^\d{8}[A-Z]$/.test(v)) return validarNif(v)
  if (/^[A-HJNPQRSUVW]\d{7}[0-9A-J]$/.test(v)) return validarCif(v)
  return false
}

export function validarIban(value: string): boolean {
  const v = clean(value)
  if (!/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(v)) return false
  const rearranged = v.slice(4) + v.slice(0, 4)
  let numeric = ''
  for (const ch of rearranged) {
    if (/\d/.test(ch)) {
      numeric += ch
    } else {
      numeric += String(ch.charCodeAt(0) - 55)
    }
  }
  // mod-97 sobre un número potencialmente muy largo: se procesa por trozos
  let remainder = 0
  for (const digit of numeric) {
    remainder = (remainder * 10 + parseInt(digit, 10)) % 97
  }
  return remainder === 1
}

export function maskIban(value: string): string {
  const v = clean(value)
  if (v.length < 8) return '*'.repeat(v.length)
  const country = v.slice(0, 2)
  const last4 = v.slice(-4)
  const middleLen = v.length - country.length - last4.length
  const masked = `${country}${'*'.repeat(middleLen)}${last4}`
  const groups: string[] = []
  for (let i = 0; i < masked.length; i += 4) {
    groups.push(masked.slice(i, i + 4))
  }
  return groups.join(' ')
}
