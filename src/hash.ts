/** Shareable state in the URL hash: #budowy, #inwestycje, #wpis=<id>, #inwestycja=<id>. */
export type Mode = "permits" | "investments";
export interface HashState { mode: Mode; permitId: string | null; investmentId: string | null }
export function readHash(hash: string): HashState {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const permitId = params.get("wpis");
  const investmentId = params.get("inwestycja");
  const mode: Mode = investmentId || params.has("inwestycje") ? "investments" : "permits";
  return { mode, permitId: mode === "permits" ? permitId : null, investmentId };
}
export function writeHash(state: { mode: Mode; id: string | null }): string {
  if (state.mode === "permits") return state.id ? `#wpis=${encodeURIComponent(state.id)}` : "#budowy";
  return state.id ? `#inwestycja=${encodeURIComponent(state.id)}` : "#inwestycje";
}
export function shareUrl(state: { mode: Mode; id: string | null }): string {
  return `${window.location.origin}${window.location.pathname}${writeHash(state)}`;
}
