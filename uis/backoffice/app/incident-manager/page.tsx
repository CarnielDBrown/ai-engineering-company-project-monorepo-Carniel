"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { ApiRequestError } from "@/lib/auth";
import {
  createManagedIncident,
  displayIncidentLabel,
  formatIncidentDate,
  getIncidentSummary,
  getManagedIncidents,
  incidentBranches,
  incidentCategories,
  incidentOrigins,
  incidentStatuses,
  IncidentCreate,
  IncidentFilters,
  IncidentStatus,
  IncidentSummary,
  ManagedIncident,
  updateManagedIncidentStatus,
} from "@/lib/incident-manager";
import "../operations.css";
import "./incident-manager.css";

const PAGE_SIZE = 50;
const emptyForm: IncidentCreate = {
  title: "",
  description: "",
  category: "patient_experience",
  branch: "central",
  origin: "branch",
  is_critical: false,
};

const emptySummary: IncidentSummary = {
  total: 0,
  by_status: { open: 0, in_progress: 0, resolved: 0, discarded: 0 },
  by_category: {
    clinical_equipment: 0,
    it_system: 0,
    billing_error: 0,
    compliance_breach: 0,
    patient_experience: 0,
    staff_issue: 0,
    facility_issue: 0,
    referral_issue: 0,
    other: 0,
  },
  by_branch: {
    central: 0,
    austin_north: 0,
    dallas_uptown: 0,
    houston_med_center: 0,
    san_antonio_west: 0,
    miami_brickell: 0,
    miami_doral: 0,
    orlando_east: 0,
    tampa_bay: 0,
    atlanta_midtown: 0,
    savannah: 0,
    london_city: 0,
    london_west: 0,
    manchester_central: 0,
  },
  critical_open_by_country: { US: 0, UK: 0 },
};

function safeError(cause: unknown): string {
  return cause instanceof ApiRequestError
    ? cause.message
    : "Unable to complete the incident request. Check your connection and try again.";
}

export default function IncidentManagerPage() {
  const [incidents, setIncidents] = useState<ManagedIncident[]>([]);
  const [summary, setSummary] = useState<IncidentSummary>(emptySummary);
  const [form, setForm] = useState(emptyForm);
  const [filterDraft, setFilterDraft] = useState({ category: "", branch: "", status: "", date_from: "", date_to: "" });
  const [filters, setFilters] = useState<IncidentFilters>({});
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [correctiveActions, setCorrectiveActions] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextIncidents, nextSummary] = await Promise.all([
        getManagedIncidents(filters, offset, PAGE_SIZE + 1),
        getIncidentSummary({ date_from: filters.date_from, date_to: filters.date_to }),
      ]);
      setIncidents(nextIncidents.slice(0, PAGE_SIZE));
      setHasMore(nextIncidents.length > PAGE_SIZE);
      setSummary(nextSummary);
    } catch (cause) {
      setError(safeError(cause));
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadData(), 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const activeFilters = Object.fromEntries(
      Object.entries(filterDraft).filter(([, value]) => value),
    ) as IncidentFilters;
    setOffset(0);
    setFilters(activeFilters);
  }

  async function submitIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = form.title.trim();
    if (!title || !form.description.trim()) {
      setFormError("Enter a title and incident description.");
      return;
    }
    setSaving(true);
    setFormError("");
    setSuccess("");
    try {
      await createManagedIncident({ ...form, title });
      setForm(emptyForm);
      setSuccess("Incident recorded.");
      await loadData();
    } catch (cause) {
      setFormError(safeError(cause));
    } finally {
      setSaving(false);
    }
  }

  async function transitionIncident(incident: ManagedIncident, nextStatus: IncidentStatus) {
    const correctiveAction = correctiveActions[incident.id]?.trim();
    if (nextStatus === "resolved" && !correctiveAction) {
      setError("Document the corrective action before resolving this incident.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await updateManagedIncidentStatus(incident.id, nextStatus, correctiveAction);
      setCorrectiveActions((current) => ({ ...current, [incident.id]: "" }));
      setSuccess(`Incident moved to ${displayIncidentLabel(nextStatus)}.`);
      await loadData();
    } catch (cause) {
      setError(safeError(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content incident-manager-page">
        <header className="topbar">
          <div className="breadcrumb"><Link href="/">HealthCore Digital</Link><span aria-hidden="true">/</span><strong>Incident manager</strong></div>
          <div className="topbar-actions"><span className="status-dot"><i></i>Authenticated incident register</span></div>
        </header>

        <section className="welcome-section incident-manager-welcome">
          <div>
            <p className="eyebrow">Clinical operations · Compliance · Technology</p>
            <h1>Incident manager.</h1>
            <p className="welcome-copy">A traceable network register for operational, clinical, compliance, and patient-experience incidents.</p>
          </div>
        </section>

        <section className="incident-critical-summary" aria-label="Critical open incidents by country">
          <div><span>Critical incidents open</span><strong>{summary.critical_open_by_country.US + summary.critical_open_by_country.UK}</strong></div>
          <div><span>United States</span><strong>{summary.critical_open_by_country.US}</strong></div>
          <div><span>United Kingdom</span><strong>{summary.critical_open_by_country.UK}</strong></div>
          <small>Critical status is staff-entered; classification criteria have not been specified.</small>
        </section>

        <section className="incident-summary-grid" aria-label="Incident totals">
          <div className="incident-summary-tile total"><span>Total in date range</span><strong>{summary.total}</strong></div>
          {incidentStatuses.map((status) => (
            <div className={`incident-summary-tile ${status}`} key={status}>
              <span>{displayIncidentLabel(status)}</span><strong>{summary.by_status[status]}</strong>
            </div>
          ))}
        </section>

        <section className="panel incident-manager-panel" aria-labelledby="incident-create-title">
          <div className="panel-heading"><div><p className="eyebrow">New record</p><h2 id="incident-create-title">Register an incident</h2></div></div>
          <form className="supplier-form incident-manager-form" onSubmit={submitIncident}>
            {formError && <p className="incident-manager-error" role="alert">{formError}</p>}
            <label>Title<input required maxLength={120} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
            <label>Category<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value as IncidentCreate["category"] })}>{incidentCategories.map((category) => <option key={category} value={category}>{displayIncidentLabel(category)}</option>)}</select></label>
            <label>Branch<select value={form.branch} onChange={(event) => setForm({ ...form, branch: event.target.value as IncidentCreate["branch"] })}>{incidentBranches.map((branch) => <option key={branch} value={branch}>{displayIncidentLabel(branch)}</option>)}</select></label>
            <label>Origin<select value={form.origin} onChange={(event) => setForm({ ...form, origin: event.target.value as IncidentCreate["origin"] })}>{incidentOrigins.map((origin) => <option key={origin} value={origin}>{displayIncidentLabel(origin)}</option>)}</select></label>
            <label className="incident-critical-toggle"><input type="checkbox" checked={form.is_critical} onChange={(event) => setForm({ ...form, is_critical: event.target.checked })} /><span>Mark as critical</span></label>
            <div className="incident-phi-warning" role="note"><strong>Do not enter identifying patient data.</strong> Never include a patient name, date of birth, medical record number, or contact details in this description. Use only an approved opaque reference if needed.</div>
            <label className="incident-description-field">Incident description<textarea required rows={4} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
            <button className="button supplier-submit" type="submit" disabled={saving}>{saving ? "Recording…" : "Record incident"}<span aria-hidden="true">→</span></button>
          </form>
          {success && <p className="incident-manager-success" role="status">{success}</p>}
        </section>

        <section className="panel incident-manager-panel" aria-labelledby="incident-list-title">
          <div className="panel-heading"><div><p className="eyebrow">Audit register</p><h2 id="incident-list-title">Incidents</h2></div><span className="panel-count">{incidents.length} shown</span></div>
          <form className="incident-filter-form" onSubmit={applyFilters}>
            <label>Category<select value={filterDraft.category} onChange={(event) => setFilterDraft({ ...filterDraft, category: event.target.value })}><option value="">All categories</option>{incidentCategories.map((category) => <option key={category} value={category}>{displayIncidentLabel(category)}</option>)}</select></label>
            <label>Branch<select value={filterDraft.branch} onChange={(event) => setFilterDraft({ ...filterDraft, branch: event.target.value })}><option value="">All branches</option>{incidentBranches.map((branch) => <option key={branch} value={branch}>{displayIncidentLabel(branch)}</option>)}</select></label>
            <label>Status<select value={filterDraft.status} onChange={(event) => setFilterDraft({ ...filterDraft, status: event.target.value })}><option value="">All statuses</option>{incidentStatuses.map((status) => <option key={status} value={status}>{displayIncidentLabel(status)}</option>)}</select></label>
            <label>From<input type="date" value={filterDraft.date_from} onChange={(event) => setFilterDraft({ ...filterDraft, date_from: event.target.value })} /></label>
            <label>To<input type="date" value={filterDraft.date_to} onChange={(event) => setFilterDraft({ ...filterDraft, date_to: event.target.value })} /></label>
            <button className="supplier-small-button" type="submit">Apply filters</button>
          </form>
          {error && <div className="incident-manager-error" role="alert">{error}<button className="supplier-small-button" type="button" onClick={() => void loadData()}>Try again</button></div>}
          {loading ? <p className="supplier-empty" role="status">Loading incidents…</p> : incidents.length === 0 ? <p className="supplier-empty">No incidents match the selected filters.</p> : (
            <div className="supplier-table-wrap">
              <table className="supplier-table incident-manager-table">
                <thead><tr><th>Incident</th><th>Category / branch</th><th>Status</th><th>Origin</th><th>Reported</th><th>Audit / action</th></tr></thead>
                <tbody>{incidents.map((incident) => (
                  <tr key={incident.id}>
                    <td><strong>{incident.title}</strong>{incident.is_critical && <span className="incident-critical-tag">Critical</span>}<p className="incident-description">{incident.description}</p>{incident.corrective_action && <small className="incident-corrective-action"><strong>Corrective action:</strong> {incident.corrective_action}</small>}</td>
                    <td>{displayIncidentLabel(incident.category)}<small>{displayIncidentLabel(incident.branch)}</small></td>
                    <td><span className={`incident-status-tag ${incident.status}`}>{displayIncidentLabel(incident.status)}</span></td>
                    <td>{displayIncidentLabel(incident.origin)}</td>
                    <td>{formatIncidentDate(incident.created_at)}</td>
                    <td>
                      <details className="incident-audit-details"><summary>{incident.audit_events.length} audit events</summary>{incident.audit_events.map((event) => <small key={event.id}>{displayIncidentLabel(event.action)} · {event.from_status ? `${displayIncidentLabel(event.from_status)} → ` : ""}{displayIncidentLabel(event.to_status)} · {formatIncidentDate(event.created_at)}{event.actor_uuid ? ` · ${event.actor_uuid}` : " · System import"}</small>)}</details>
                      {incident.status === "open" && <div className="incident-row-actions"><button className="supplier-small-button" type="button" disabled={saving} onClick={() => void transitionIncident(incident, "in_progress")}>Start work</button><button className="incident-discard-button" type="button" disabled={saving} onClick={() => void transitionIncident(incident, "discarded")}>Discard</button></div>}
                      {incident.status === "in_progress" && <div className="incident-row-actions"><label className="incident-action-input">Corrective action<input value={correctiveActions[incident.id] ?? ""} onChange={(event) => setCorrectiveActions({ ...correctiveActions, [incident.id]: event.target.value })} /></label><button className="supplier-small-button" type="button" disabled={saving} onClick={() => void transitionIncident(incident, "resolved")}>Resolve</button><button className="incident-discard-button" type="button" disabled={saving} onClick={() => void transitionIncident(incident, "discarded")}>Discard</button></div>}
                    </td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {!loading && (offset > 0 || incidents.length === PAGE_SIZE) && <div className="incident-pagination"><button className="supplier-small-button" type="button" disabled={offset === 0} onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}>Previous</button><span>Showing {offset + 1}–{offset + incidents.length}</span><button className="supplier-small-button" type="button" disabled={!hasMore} onClick={() => setOffset((current) => current + PAGE_SIZE)}>Next</button></div>}
        </section>
        <footer className="main-footer"><span>HealthCore Digital · Incident manager</span><span>Authenticated access · HIPAA / UK GDPR safeguards</span></footer>
      </main>
    </div>
  );
}