import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IncidentManagerPage from "./page";

vi.mock("next/link", () => ({ default: ({ children, href, ...props }: React.ComponentProps<"a">) => <a href={href} {...props}>{children}</a> }));
vi.mock("@/components/sidebar", () => ({ Sidebar: () => <nav aria-label="Main navigation">Incident manager</nav> }));
vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return { ...actual, authFetch: vi.fn() };
});

import { authFetch } from "@/lib/auth";

const mockedAuthFetch = vi.mocked(authFetch);
const incident = {
  id: 8,
  title: "Portal availability",
  description: "Synthetic operational description for testing.",
  category: "it_system" as const,
  branch: "central" as const,
  status: "open" as const,
  origin: "internal" as const,
  is_critical: true,
  corrective_action: null,
  created_at: "2026-01-02T12:00:00Z",
  updated_at: "2026-01-02T12:00:00Z",
  created_by_uuid: "synthetic-actor",
  updated_by_uuid: "synthetic-actor",
  audit_events: [{ id: 1, action: "created" as const, from_status: null, to_status: "open" as const, actor_uuid: "synthetic-actor", created_at: "2026-01-02T12:00:00Z" }],
};
const summary = {
  total: 1,
  by_status: { open: 1, in_progress: 0, resolved: 0, discarded: 0 },
  by_category: { clinical_equipment: 0, it_system: 1, billing_error: 0, compliance_breach: 0, patient_experience: 0, staff_issue: 0, facility_issue: 0, referral_issue: 0, other: 0 },
  by_branch: { central: 1, austin_north: 0, dallas_uptown: 0, houston_med_center: 0, san_antonio_west: 0, miami_brickell: 0, miami_doral: 0, orlando_east: 0, tampa_bay: 0, atlanta_midtown: 0, savannah: 0, london_city: 0, london_west: 0, manchester_central: 0 },
  critical_open_by_country: { US: 1, UK: 0 },
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function queueInitialLoad(rows: unknown[] = [incident]) {
  mockedAuthFetch.mockResolvedValueOnce(jsonResponse(rows)).mockResolvedValueOnce(jsonResponse(summary));
}

async function waitForPage() {
  await screen.findByText("Portal availability");
}

beforeEach(() => mockedAuthFetch.mockReset());

describe("incident manager page", () => {
  it("shows the patient-data warning, critical summary, and loads through authenticated API helpers", async () => {
    queueInitialLoad();
    render(<IncidentManagerPage />);

    await waitForPage();
    expect(screen.getByRole("note").textContent).toContain("Do not enter identifying patient data");
    expect(screen.getByRole("note").textContent).toContain("medical record number");
    expect(screen.getByLabelText("Incident description")).toBeTruthy();
    expect(screen.getByText("Critical incidents open")).toBeTruthy();
    expect(screen.getByText("Synthetic operational description for testing.")).toBeTruthy();
    expect(mockedAuthFetch.mock.calls.slice(0, 2).map(([path]) => path)).toEqual([
      "/incident-manager/incidents?limit=51&offset=0",
      "/incident-manager/summary",
    ]);
  });

  it("applies category, branch, status, and date filters to the list request", async () => {
    queueInitialLoad();
    render(<IncidentManagerPage />);
    await waitForPage();
    mockedAuthFetch.mockResolvedValueOnce(jsonResponse([])).mockResolvedValueOnce(jsonResponse(summary));

    const filterForm = screen.getByRole("button", { name: "Apply filters" }).closest("form")!;
    await userEvent.selectOptions(within(filterForm).getByLabelText("Category"), "compliance_breach");
    await userEvent.selectOptions(within(filterForm).getByLabelText("Branch"), "london_city");
    await userEvent.selectOptions(within(filterForm).getByLabelText("Status"), "open");
    fireEvent.change(within(filterForm).getByLabelText("From"), { target: { value: "2026-01-01" } });
    fireEvent.change(within(filterForm).getByLabelText("To"), { target: { value: "2026-01-31" } });
    await userEvent.click(within(filterForm).getByRole("button", { name: "Apply filters" }));

    await waitFor(() => expect(mockedAuthFetch.mock.calls.length).toBe(4));
    expect(mockedAuthFetch.mock.calls[2][0]).toBe(
      "/incident-manager/incidents?category=compliance_breach&branch=london_city&status=open&date_from=2026-01-01&date_to=2026-01-31&limit=51&offset=0",
    );
    expect(mockedAuthFetch.mock.calls[3][0]).toBe(
      "/incident-manager/summary?date_from=2026-01-01&date_to=2026-01-31",
    );
  });

  it("shows a safe retry state and an empty result after a failed load", async () => {
    mockedAuthFetch
      .mockRejectedValueOnce(new Error("internal database connection details"))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(summary));
    render(<IncidentManagerPage />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Unable to complete the incident request");
    expect(alert.textContent).not.toContain("database connection details");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No incidents match the selected filters.")).toBeTruthy();
  });

  it("loads the next bounded page of incidents", async () => {
    const firstPage = Array.from({ length: 51 }, (_, index) => ({
      ...incident,
      id: index + 1,
      title: `Synthetic incident ${index + 1}`,
    }));
    queueInitialLoad(firstPage);
    render(<IncidentManagerPage />);
    await screen.findByText("Synthetic incident 50");
    mockedAuthFetch.mockResolvedValueOnce(jsonResponse([incident])).mockResolvedValueOnce(jsonResponse(summary));

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Showing 51–51")).toBeTruthy();
    expect(mockedAuthFetch.mock.calls[2][0]).toBe("/incident-manager/incidents?limit=51&offset=50");
    expect(screen.getByRole("button", { name: "Next" })).toHaveProperty("disabled", true);
  });

  it("disables next when the first page contains exactly fifty incidents", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) => ({
      ...incident,
      id: index + 1,
      title: `Synthetic incident ${index + 1}`,
    }));
    queueInitialLoad(firstPage);
    render(<IncidentManagerPage />);

    await screen.findByText("Synthetic incident 50");
    expect(screen.getByRole("button", { name: "Next" })).toHaveProperty("disabled", true);
  });

  it("records an incident without introducing patient identifier fields", async () => {
    queueInitialLoad([]);
    render(<IncidentManagerPage />);
    await screen.findByText("No incidents match the selected filters.");
    mockedAuthFetch.mockResolvedValueOnce(jsonResponse(incident, 201)).mockResolvedValueOnce(jsonResponse([incident])).mockResolvedValueOnce(jsonResponse(summary));

    const form = screen.getByRole("heading", { name: "Register an incident" }).closest("section")!.querySelector("form")!;
    fireEvent.change(within(form).getByLabelText("Title"), { target: { value: "Portal availability" } });
    fireEvent.change(within(form).getByLabelText("Incident description"), { target: { value: "Synthetic operational description." } });
    await userEvent.click(within(form).getByRole("button", { name: /Record incident/ }));

    await screen.findByRole("status");
    const request = mockedAuthFetch.mock.calls[2];
    expect(request[0]).toBe("/incident-manager/incidents");
    expect(request[1]?.method).toBe("POST");
    const submitted = JSON.parse(String(request[1]?.body));
    expect(submitted).toMatchObject({ title: "Portal availability", category: "patient_experience", origin: "branch" });
    expect(submitted).not.toHaveProperty("patient_id");
    expect(submitted).not.toHaveProperty("date_of_birth");
  });

  it("requires corrective action before resolving and sends it with the transition", async () => {
    const inProgress = { ...incident, status: "in_progress" as const };
    queueInitialLoad([inProgress]);
    render(<IncidentManagerPage />);
    await waitForPage();

    await userEvent.click(screen.getByRole("button", { name: "Resolve" }));
    expect(screen.getByRole("alert").textContent).toContain("Document the corrective action");
    expect(mockedAuthFetch).toHaveBeenCalledTimes(2);

    mockedAuthFetch.mockResolvedValueOnce(jsonResponse({ ...inProgress, status: "resolved" })).mockResolvedValueOnce(jsonResponse([])).mockResolvedValueOnce(jsonResponse(summary));
    fireEvent.change(screen.getByLabelText("Corrective action"), { target: { value: "Service restored and monitored." } });
    await userEvent.click(screen.getByRole("button", { name: "Resolve" }));

    await waitFor(() => expect(mockedAuthFetch.mock.calls.length).toBe(5));
    expect(mockedAuthFetch.mock.calls[2][0]).toBe("/incident-manager/incidents/8/status");
    expect(JSON.parse(String(mockedAuthFetch.mock.calls[2][1]?.body))).toEqual({
      status: "resolved",
      corrective_action: "Service restored and monitored.",
    });
  });
});