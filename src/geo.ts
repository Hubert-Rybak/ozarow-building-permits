import type { Geometry, Position } from "geojson";

export type LatLng = [number, number];
export interface Box { south: number; west: number; north: number; east: number }

function positions(geometry: Geometry): Position[] {
  switch (geometry.type) {
    case "Point": return [geometry.coordinates];
    case "MultiPoint":
    case "LineString": return geometry.coordinates;
    case "MultiLineString":
    case "Polygon": return geometry.coordinates.flat();
    case "MultiPolygon": return geometry.coordinates.flat(2);
    default: return [];
  }
}
export function boxOf(geometries: Geometry[]): Box | null {
  let box: Box | null = null;
  for (const geometry of geometries)
    for (const [lon, lat] of positions(geometry)) {
      if (!box) box = { south: lat, west: lon, north: lat, east: lon };
      else {
        box.south = Math.min(box.south, lat); box.north = Math.max(box.north, lat);
        box.west = Math.min(box.west, lon); box.east = Math.max(box.east, lon);
      }
    }
  return box;
}
export function centerOf(geometries: Geometry[]): LatLng | null {
  const box = boxOf(geometries);
  return box ? [(box.south + box.north) / 2, (box.west + box.east) / 2] : null;
}
export function distanceMeters(a: LatLng, b: LatLng): number {
  const rad = Math.PI / 180, r = 6_371_000;
  const dLat = (b[0] - a[0]) * rad, dLon = (b[1] - a[1]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}
export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.max(10, Math.round(meters / 10) * 10)} m`;
  return `${(meters / 1000).toLocaleString("pl-PL", { maximumFractionDigits: 1 })} km`;
}
export function nearest<T>(origin: LatLng, items: { item: T; at: LatLng }[], maxMeters: number, limit: number) {
  return items
    .map(entry => ({ item: entry.item, meters: distanceMeters(origin, entry.at) }))
    .filter(entry => entry.meters <= maxMeters)
    .sort((a, b) => a.meters - b.meters)
    .slice(0, limit);
}
