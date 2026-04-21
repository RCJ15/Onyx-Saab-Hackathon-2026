/**
 * In-memory + localStorage cache for cross-page and cross-reload data persistence.
 *
 * - In-memory Map survives client-side navigation.
 * - localStorage mirror survives full page reloads, so returning to a
 *   previously-visited page paints from cache instantly.
 *
 * Usage:
 *   const cached = getCached<T>("kb:bundle", 60_000);   // sync read
 *   if (cached) hydrateUI(cached);                      // paint first
 *   const fresh = await cachedFetch("kb:bundle", ...); // then revalidate
 */

type Entry = { data: unknown; ts: number };

const PREFIX = "bpcache:";
const cache = new Map<string, Entry>();

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readLS(key: string): Entry | null {
  const ls = storage();
  if (!ls) return null;
  try {
    const raw = ls.getItem(PREFIX + key);
    if (!raw) return null;
    return JSON.parse(raw) as Entry;
  } catch {
    return null;
  }
}

function writeLS(key: string, entry: Entry): void {
  const ls = storage();
  if (!ls) return;
  try {
    ls.setItem(PREFIX + key, JSON.stringify(entry));
  } catch {
    // quota exceeded — ignore, in-memory cache still works
  }
}

function removeLS(key: string): void {
  const ls = storage();
  if (!ls) return;
  try {
    ls.removeItem(PREFIX + key);
  } catch {
    // ignore
  }
}

export function getCached<T>(key: string, maxAgeMs: number): T | null {
  let entry = cache.get(key);
  if (!entry) {
    const fromLS = readLS(key);
    if (fromLS) {
      entry = fromLS;
      cache.set(key, fromLS);
    }
  }
  if (!entry) return null;
  if (Date.now() - entry.ts > maxAgeMs) return null;
  return entry.data as T;
}

export function setCached(key: string, data: unknown): void {
  const entry: Entry = { data, ts: Date.now() };
  cache.set(key, entry);
  writeLS(key, entry);
}

export function invalidate(keyOrPrefix: string): void {
  for (const k of Array.from(cache.keys())) {
    if (k === keyOrPrefix || k.startsWith(keyOrPrefix + ":")) {
      cache.delete(k);
      removeLS(k);
    }
  }
  // Also sweep localStorage for keys that were never hydrated into memory.
  const ls = storage();
  if (!ls) return;
  try {
    const toRemove: string[] = [];
    for (let i = 0; i < ls.length; i++) {
      const k = ls.key(i);
      if (!k || !k.startsWith(PREFIX)) continue;
      const bare = k.slice(PREFIX.length);
      if (bare === keyOrPrefix || bare.startsWith(keyOrPrefix + ":")) {
        toRemove.push(k);
      }
    }
    for (const k of toRemove) ls.removeItem(k);
  } catch {
    // ignore
  }
}

export function clearCache(): void {
  cache.clear();
  const ls = storage();
  if (!ls) return;
  try {
    const toRemove: string[] = [];
    for (let i = 0; i < ls.length; i++) {
      const k = ls.key(i);
      if (k && k.startsWith(PREFIX)) toRemove.push(k);
    }
    for (const k of toRemove) ls.removeItem(k);
  } catch {
    // ignore
  }
}

/**
 * Fetches `fetcher()` or returns cached value if fresh.
 * Use this to wrap any API call where stale-while-revalidate is OK.
 */
export async function cachedFetch<T>(
  key: string,
  maxAgeMs: number,
  fetcher: () => Promise<T>,
): Promise<T> {
  const cached = getCached<T>(key, maxAgeMs);
  if (cached !== null) return cached;
  const fresh = await fetcher();
  setCached(key, fresh);
  return fresh;
}
