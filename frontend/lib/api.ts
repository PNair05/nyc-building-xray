import type { Building, BuildingModel, Explanation, Report } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, cache: "no-store" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "The request could not be completed.");
  }
  return response.json();
}

export const api = {
  search: (query: string, borough?: string) =>
    request<Building[]>(`/api/search?q=${encodeURIComponent(query)}${borough ? `&borough=${encodeURIComponent(borough)}` : ""}`),
  report: (id: string) => request<Report>(`/api/buildings/${encodeURIComponent(id)}/report?months=12`),
  model: (id: string) => request<BuildingModel>(`/api/buildings/${encodeURIComponent(id)}/model`),
  explain: (id: string) => request<Explanation>(`/api/buildings/${encodeURIComponent(id)}/explanation?months=12`, { method: "POST" }),
};
