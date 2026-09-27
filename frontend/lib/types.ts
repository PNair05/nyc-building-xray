export type Building = {
  id: string;
  address: string;
  borough: string;
  latitude: number | null;
  longitude: number | null;
  bin: string | null;
  bbl: string | null;
  source_ids: Record<string, string>;
  match_method: string;
  confidence: number;
  ambiguity: string | null;
  demo: boolean;
};

export type BuildingModel =
  | { status: "unavailable"; message: string; reason?: string; required_district?: string; required_file?: string; available_districts?: string[] }
  | { status: "ready"; match: "demo" | "coordinate"; url: string; download_url: string; message: string; object_count: number; triangle_count: number };

export type Coverage = {
  key: string;
  name: string;
  dataset_url: string;
  status: "complete" | "incomplete" | "unavailable";
  retrieved_at: string;
  dataset_updated_at: string | null;
  period_start: string | null;
  period_end: string | null;
  match_method: string;
  warnings: string[];
  record_count: number | null;
  cached: boolean;
};

export type Evidence = {
  id: string;
  source: "311" | "HPD" | "DOB";
  source_record_id: string;
  occurred_at: string;
  category: string;
  original_category: string;
  description: string;
  status: string;
  status_group: "open" | "closed" | "unknown" | "not_applicable";
  classification: string | null;
  source_url: string;
  address: string | null;
  floor: number | null;
  location_detail: string | null;
};

export type Finding = {
  id: string;
  title: string;
  detail: string;
  evidence_ids: string[];
  category: string | null;
};

export type Report = {
  id: string;
  mode: "demo" | "live";
  reference_date: string;
  building: Building;
  period: { months: number; start: string; end_exclusive: string; label: string };
  coverage: Coverage[];
  summary: {
    complaints_311: number | null;
    open_hpd_violations: number | null;
    hpd_by_class: Record<string, number> | null;
    dob_complaints: number | null;
  };
  category_totals: Record<string, number>;
  monthly: Array<{ month: string; counts: Record<string, number>; total: number }>;
  findings: Finding[];
  records: Evidence[];
  limitations: string[];
};

export type Explanation = {
  label: "Summary" | "AI-generated";
  overview: string;
  findings: Array<{ text: string; evidence_ids: string[] }>;
  landlord_questions: string[];
  limitations: string[];
};
