import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createManagedIncident,
  getIncidentSummary,
  getManagedIncidents,
  updateManagedIncidentStatus,
} from "./incident-manager";

vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return { ...actual, authFetch: vi.fn() };
});

import { authFetch } from "@/lib/auth";

const mockedAuthFetch = vi.mocked(authFetch);

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => mockedAuthFetch.mockReset());

describe("incident manager API client", () => {
  it("requests filtered incidents and date-scoped summary through the auth proxy", async () => {
    mockedAuthFetch.mockResolvedValueOnce(jsonResponse([])).mockResolvedValueOnce(jsonResponse({}));

    await getManagedIncidents({ category: "compliance_breach", branch: "london_city", status: "open" });
    await getIncidentSummary({ date_from: "2026-01-01", date_to: "2026-01-31" });

    expect(mockedAuthFetch.mock.calls[0][0]).toBe(
      "/incident-manager/incidents?category=compliance_breach&branch=london_city&status=open&limit=50&offset=0",
    );
    expect(mockedAuthFetch.mock.calls[1][0]).toBe(
      "/incident-manager/summary?date_from=2026-01-01&date_to=2026-01-31",
    );
  });

  it("posts incident creation and lifecycle changes as JSON", async () => {
    mockedAuthFetch.mockResolvedValueOnce(jsonResponse({})).mockResolvedValueOnce(jsonResponse({}));

    await createManagedIncident({
      title: "Portal outage",
      description: "Synthetic operational incident",
      category: "it_system",
      branch: "central",
      origin: "internal",
      is_critical: false,
    });
    await updateManagedIncidentStatus(5, "resolved", "Service restored.");

    expect(mockedAuthFetch.mock.calls[0][1]).toMatchObject({ method: "POST" });
    expect(JSON.parse(String(mockedAuthFetch.mock.calls[0][1]?.body))).toMatchObject({ category: "it_system" });
    expect(mockedAuthFetch.mock.calls[1][0]).toBe("/incident-manager/incidents/5/status");
    expect(JSON.parse(String(mockedAuthFetch.mock.calls[1][1]?.body))).toEqual({
      status: "resolved",
      corrective_action: "Service restored.",
    });
  });
});