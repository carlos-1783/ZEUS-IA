/** Remove duplicate top-level values (anti-duplication for merged API payloads). */
export function deduplicateDoc<T extends Record<string, unknown>>(doc: T): T {
  const seen = new Set<string>()
  const clean = {} as T

  for (const key of Object.keys(doc)) {
    const value = doc[key]
    const fingerprint =
      typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)
    if (seen.has(fingerprint)) continue
    seen.add(fingerprint)
    clean[key as keyof T] = value
  }

  return clean
}
