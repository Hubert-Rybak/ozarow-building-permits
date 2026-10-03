import type {
  Feature,
  FeatureCollection,
  MultiPolygon,
  Polygon,
} from "geojson";
export type RecordKind = "application" | "decision" | "notification";
export interface Permit {
  id: string;
  kind: RecordKind;
  title: string;
  description: string;
  applicationDate: string | null;
  decisionDate: string | null;
  decisionNumber: string | null;
  status: string;
  locality: string;
  street: string;
  municipality: string;
  cadastralRegion: string;
  parcelNumbers: string[];
  parcelIds: string[];
  category: string;
  sourceUrl: string;
  geometryStatus: "matched" | "partial" | "unresolved";
  geometryNote: string;
}
export interface DataSource {
  name: string;
  url: string;
  downloadedAt: string;
  coverage: string;
}
export interface PermitDataset {
  schemaVersion: 1;
  generatedAt: string;
  source: DataSource;
  records: Permit[];
}
export interface ParcelProperties {
  id: string;
  parcelNumber: string;
  region: string;
  permitIds: string[];
  sourceUrl: string;
}
export type ParcelFeature = Feature<Polygon | MultiPolygon, ParcelProperties>;
export type ParcelCollection = FeatureCollection<
  Polygon | MultiPolygon,
  ParcelProperties
> & {
  // Legacy GeoJSON and the empty fallback omit this; the loader must not map them.
  generatedAt?: string;
};
export interface Metadata {
  generatedAt?: string;
  coverage?: string;
  warnings?: string[];
  sources?: { name: string; url: string }[];
}
export interface LoadedData {
  dataset: PermitDataset | null;
  parcels: ParcelCollection;
  metadata: Metadata | null;
  warnings: string[];
  error: string | null;
}
export type SemanticStatus =
  "approved" | "refused" | "pending" | "withdrawn" | "unknown";
export interface Filters {
  period: "3months" | "all";
  query: string;
  kind: string;
  year: string;
  status: string;
  locality: string;
  mapping: "all" | "mapped" | "unmapped" | "partial";
  sort: "newest" | "oldest";
}
