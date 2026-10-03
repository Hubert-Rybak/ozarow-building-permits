/** "New since your last visit": per-browser convenience only, never required for the app to work. */
export interface SeenState { newIds: Set<string>; lastVisit: string | null }
export function readAndRemember(key: string, ids: string[], now = new Date()): SeenState {
  const storageKey = `radar-ozarow:seen:${key}`;
  let previous: { ids: string[]; at: string } | null = null;
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && Array.isArray(parsed.ids) && typeof parsed.at === "string") previous = parsed;
  } catch { previous = null; }
  try {
    window.localStorage.setItem(storageKey, JSON.stringify({ ids, at: now.toISOString() }));
  } catch { /* private mode or blocked storage */ }
  if (!previous) return { newIds: new Set(), lastVisit: null };
  const known = new Set(previous.ids);
  return { newIds: new Set(ids.filter(id => !known.has(id))), lastVisit: previous.at };
}
