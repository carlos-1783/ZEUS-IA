/** Safe GET — never throws; returns null on error (dashboard stability). */

export async function safeGet<T = unknown>(
  url: string,
  init?: RequestInit,
): Promise<T | null> {
  try {
    const res = await fetch(url, init)
    if (!res.ok) {
      console.warn('[safeGet] HTTP', res.status, url)
      return null
    }
    return (await res.json()) as T
  } catch (e) {
    console.warn('[safeGet] failed', url, e)
    return null
  }
}
