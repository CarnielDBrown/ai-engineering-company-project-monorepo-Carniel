import { authFetch, readApiResponse } from "@/lib/auth";

export const incidentCategories = [
  "clinical_equipment",
  "it_system",
  "billing_error",
  "compliance_breach",
  "patient_experience",
  "staff_issue",
  "facility_issue",
  "referral_issue",
  "other",
] as const;

export const incidentBranches = [
  "central",
  "austin_north",
  "dallas_uptown",
  "houston_med_center",
  "san_antonio_west",
  "miami_brickell",
  "miami_doral",
  "orlando_east",
  "tampa_bay",
  "atlanta_midtown",
  "savannah",
  "london_city",
  "london_west",
  "manchester_central",
] as const;

export const incidentStatuses = ["open", "in_progress", "resolved", "discarded"] as const;
export const incidentOrigins = ["customer", "branch", "internal"] as const;

export type IncidentCategory = (typeof incidentCategories)[number];
export type IncidentBranch = (typeof incidentBranches)[number];
export type IncidentStatus = (typeof incidentStatuses)[number];
export type IncidentOrigin = (typeof incidentOrigins)[number];

export type ManagedIncident = {
  id: number;
  title: string;
  description: string;
  category: IncidentCategory;
  branch: IncidentBranch;
  status: IncidentStatus;
  origin: IncidentOrigin;
  is_critical: boolean;
  corrective_action: string | null;
  created_at: string;
  updated_at: string;
  created_by_uuid: string | null;
  updated_by_uuid: string | null;
  audit_events: {
    id: number;
    action: "created" | "legacy_import" | "status_transition";
    from_status: IncidentStatus | null;
    to_status: IncidentStatus;
    actor_uuid: string | null;
    created_at: string;
  }[];
};

export type IncidentSummary = {
  total: number;
  by_status: Record<IncidentStatus, number>;
  by_category: Record<IncidentCategory, number>;
  by_branch: Record<IncidentBranch, number>;
  critical_open_by_country: { US: number; UK: number };
};

export type IncidentFilters = {
  category?: IncidentCategory;
  branch?: IncidentBranch;
  status?: IncidentStatus;
  date_from?: string;
  date_to?: string;
};

export type IncidentCreate = {
  title: string;
  description: string;
  category: IncidentCategory;
  branch: IncidentBranch;
  origin: IncidentOrigin;
  is_critical: boolean;
};

const genericError = "Unable to complete the incident request. Check your connection and try again.";

async function incidentRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await authFetch(path, options);
  return readApiResponse<T>(response, genericError);
}

export function getManagedIncidents(filters: IncidentFilters = {}, offset = 0, limit = 50): Promise<ManagedIncident[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  const query = params.size ? `?${params.toString()}` : "";
  return incidentRequest(`/incident-manager/incidents${query}`);
}

export function getIncidentSummary(filters: Pick<IncidentFilters, "date_from" | "date_to"> = {}): Promise<IncidentSummary> {
  const params = new URLSearchParams();
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  const query = params.size ? `?${params.toString()}` : "";
  return incidentRequest(`/incident-manager/summary${query}`);
}

export function createManagedIncident(payload: IncidentCreate): Promise<ManagedIncident> {
  return incidentRequest("/incident-manager/incidents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateManagedIncidentStatus(
  incidentId: number,
  status: IncidentStatus,
  corrective_action?: string,
): Promise<ManagedIncident> {
  return incidentRequest(`/incident-manager/incidents/${incidentId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, ...(corrective_action ? { corrective_action } : {}) }),
  });
}

export function formatIncidentDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function displayIncidentLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}