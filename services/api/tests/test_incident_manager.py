from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import database
from conftest import auth_headers, login, register
from main import app
from models import ManagedIncident


@pytest.fixture
def incident_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def manager_client(client: TestClient, incident_engine):
    engine = incident_engine

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database.get_db] = override_db
    yield client
    app.dependency_overrides.pop(database.get_db, None)


def _headers(client: TestClient) -> dict[str, str]:
    register(client)
    return auth_headers(login(client))


def _payload(**overrides) -> dict:
    return {
        "title": "Portal access disruption",
        "description": "The appointment portal was unavailable for a short period.",
        "category": "it_system",
        "branch": "central",
        "origin": "internal",
        "is_critical": True,
        **overrides,
    }


def _synthetic_legacy_csv() -> str:
    branches = [
        ("central", "US-TX-01", "US", 7),
        ("austin_north", "US-TX-02", "US", 9),
        ("houston_med_center", "US-TX-03", "US", 4),
        ("miami_brickell", "US-FL-01", "US", 8),
        ("orlando_east", "US-FL-02", "US", 4),
        ("tampa_bay", "US-FL-03", "US", 7),
        ("atlanta_midtown", "US-GA-01", "US", 12),
        ("savannah", "US-GA-03", "US", 10),
        ("london_city", "UK-LON-01", "UK", 9),
        ("london_west", "UK-LON-02", "UK", 9),
        ("manchester_central", "UK-MAN-01", "UK", 15),
    ]
    clinic_rows = [entry for _branch, clinic, country, count in branches for entry in [(clinic, country)] * count]
    categories = [
        category
        for category, count in (
            ("APPOINTMENT", 30),
            ("BILLING", 20),
            ("CLINICAL_CARE", 14),
            ("ACCESSIBILITY", 17),
            ("ADMINISTRATIVE", 13),
        )
        for _ in range(count)
    ]
    statuses = ["OPEN"] * 28 + ["CLOSED"] * 52 + ["DISCARDED"] * 14
    rows = []
    for index, ((clinic_id, country), category, status) in enumerate(zip(clinic_rows, categories, statuses), start=1):
        rows.append(
            {
                "incident_id": f"HC-{index:06d}",
                "date": "2026-01-15",
                "clinic_id": clinic_id,
                "country": country,
                "category": category,
                "description": f"Synthetic incident description {index}",
                "status": status,
                "patient_id": f"PAT-{index:06d}",
                "satisfaction_score": "4" if status == "CLOSED" else "",
            }
        )
    invalid_rows = [
        {**rows[0], "incident_id": "HC-000095", "clinic_id": "INVALID"},
        {**rows[0], "incident_id": "HC-000096", "country": "UK"},
        {**rows[0], "incident_id": "HC-000097", "category": "INVALID"},
        {**rows[0], "incident_id": "HC-000098", "description": "bad"},
        {**rows[0], "incident_id": "HC-000099", "patient_id": ""},
        {
            **rows[0],
            "incident_id": "HC-000100",
            "status": "CLOSED",
            "satisfaction_score": "",
        },
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows([*rows, *invalid_rows])
    return output.getvalue()


def test_incident_manager_requires_authentication(manager_client):
    response = manager_client.get("/api/incident-manager/incidents")

    assert response.status_code == 401


def test_create_and_list_incident_with_filters_and_audit(manager_client):
    headers = _headers(manager_client)
    created = manager_client.post(
        "/api/incident-manager/incidents", json=_payload(), headers=headers
    )

    assert created.status_code == 201, created.text
    incident = created.json()
    assert incident["status"] == "open"
    assert incident["created_by_uuid"]
    assert incident["audit_events"][0]["action"] == "created"
    assert incident["audit_events"][0]["actor_uuid"] == incident["created_by_uuid"]
    assert "source_key" not in incident

    filtered = manager_client.get(
        "/api/incident-manager/incidents?category=it_system&branch=central&status=open",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()] == [incident["id"]]
    assert manager_client.get(
        "/api/incident-manager/incidents?category=billing_error", headers=headers
    ).json() == []


def test_patient_identifiers_are_not_accepted_as_incident_fields(manager_client):
    response = manager_client.post(
        "/api/incident-manager/incidents",
        json=_payload(patient_id="PAT-123456"),
        headers=_headers(manager_client),
    )

    assert response.status_code == 422
    assert "PAT-123456" not in response.text


def test_lifecycle_enforces_transitions_and_resolution_action(manager_client):
    headers = _headers(manager_client)
    created = manager_client.post(
        "/api/incident-manager/incidents", json=_payload(), headers=headers
    )
    incident_id = created.json()["id"]
    base = f"/api/incident-manager/incidents/{incident_id}/status"

    assert manager_client.patch(base, json={"status": "resolved"}, headers=headers).status_code == 409
    assert manager_client.patch(base, json={"status": "in_progress"}, headers=headers).status_code == 200
    assert manager_client.patch(base, json={"status": "resolved"}, headers=headers).status_code == 422

    resolved = manager_client.patch(
        base,
        json={"status": "resolved", "corrective_action": "Portal service restored and monitored."},
        headers=headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["corrective_action"] == "Portal service restored and monitored."
    assert [event["to_status"] for event in resolved.json()["audit_events"]] == [
        "open",
        "in_progress",
        "resolved",
    ]
    assert manager_client.patch(base, json={"status": "discarded"}, headers=headers).status_code == 409


def test_summary_returns_complete_zero_filled_groups_and_country_counts(manager_client):
    headers = _headers(manager_client)
    manager_client.post(
        "/api/incident-manager/incidents", json=_payload(branch="london_city"), headers=headers
    )
    manager_client.post(
        "/api/incident-manager/incidents",
        json=_payload(category="billing_error", branch="miami_doral", is_critical=False),
        headers=headers,
    )

    response = manager_client.get("/api/incident-manager/summary", headers=headers)

    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["total"] == 2
    assert summary["by_status"]["open"] == 2
    assert summary["by_status"]["resolved"] == 0
    assert summary["by_category"]["it_system"] == 1
    assert summary["by_branch"]["london_city"] == 1
    assert summary["critical_open_by_country"] == {"US": 0, "UK": 1}


def test_invalid_date_range_is_rejected_without_database_details(manager_client):
    response = manager_client.get(
        "/api/incident-manager/incidents?date_from=2026-02-02&date_to=2026-02-01",
        headers=_headers(manager_client),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "date_from must not be after date_to"}


def test_list_date_boundaries_and_pagination(manager_client):
    headers = _headers(manager_client)
    first = manager_client.post(
        "/api/incident-manager/incidents", json=_payload(), headers=headers
    ).json()
    second = manager_client.post(
        "/api/incident-manager/incidents", json=_payload(title="Second incident"), headers=headers
    ).json()
    today = datetime.now(timezone.utc).date()

    same_day = manager_client.get(
        f"/api/incident-manager/incidents?date_from={today}&date_to={today}&limit=1&offset=0",
        headers=headers,
    )
    next_day = today + timedelta(days=1)
    outside_range = manager_client.get(
        f"/api/incident-manager/incidents?date_from={next_day}&date_to={next_day}",
        headers=headers,
    )
    next_page = manager_client.get(
        "/api/incident-manager/incidents?limit=1&offset=1", headers=headers
    )

    assert same_day.status_code == 200
    assert len(same_day.json()) == 1
    assert outside_range.json() == []
    assert [row["id"] for row in next_page.json()] == [first["id"]]
    assert next_page.json()[0]["id"] != second["id"]


def test_both_discard_transitions_are_allowed_and_final(manager_client):
    headers = _headers(manager_client)
    open_incident = manager_client.post(
        "/api/incident-manager/incidents", json=_payload(), headers=headers
    ).json()
    open_discard = manager_client.patch(
        f"/api/incident-manager/incidents/{open_incident['id']}/status",
        json={"status": "discarded"},
        headers=headers,
    )
    assert open_discard.status_code == 200
    assert open_discard.json()["status"] == "discarded"
    assert manager_client.patch(
        f"/api/incident-manager/incidents/{open_incident['id']}/status",
        json={"status": "in_progress"},
        headers=headers,
    ).status_code == 409

    active_incident = manager_client.post(
        "/api/incident-manager/incidents", json=_payload(), headers=headers
    ).json()
    active_path = f"/api/incident-manager/incidents/{active_incident['id']}/status"
    assert manager_client.patch(active_path, json={"status": "in_progress"}, headers=headers).status_code == 200
    discarded = manager_client.patch(active_path, json={"status": "discarded"}, headers=headers)
    assert discarded.status_code == 200
    assert discarded.json()["status"] == "discarded"
    assert manager_client.patch(
        active_path,
        json={"status": "resolved", "corrective_action": "Synthetic action."},
        headers=headers,
    ).status_code == 409


def test_legacy_import_maps_expected_totals_and_is_idempotent(manager_client, incident_engine, tmp_path):
    from routes.seed_incidents import seed_incidents

    csv_path = tmp_path / "synthetic-incidents.csv"
    csv_path.write_text(_synthetic_legacy_csv(), encoding="utf-8")
    secret_key = "test-secret-that-is-only-used-for-import-digests-123456"

    with Session(incident_engine) as session:
        first = seed_incidents(session, csv_path, secret_key)
        second = seed_incidents(session, csv_path, secret_key)

    assert first["inserted"] == 94
    assert first["invalid"] == 6
    assert first["invalid_by_rule"] == {
        "invalid_clinic_id": 1,
        "country_mismatch": 1,
        "invalid_category": 1,
        "empty_description": 1,
        "missing_patient_id": 1,
        "closed_without_score": 1,
    }
    assert second["inserted"] == 0
    assert second["duplicates"] == 94
    assert second["invalid"] == 6
    with Session(incident_engine) as session:
        source_keys = session.exec(select(ManagedIncident.source_key)).all()
    assert len(source_keys) == 94
    assert all(len(key) == 64 and key != "HC-000001" for key in source_keys)

    summary = manager_client.get(
        "/api/incident-manager/summary", headers=_headers(manager_client)
    ).json()
    assert summary["total"] == 94
    assert summary["by_status"] == {"open": 28, "in_progress": 0, "resolved": 52, "discarded": 14}
    assert summary["by_category"] == {
        "clinical_equipment": 0,
        "it_system": 0,
        "billing_error": 20,
        "compliance_breach": 0,
        "patient_experience": 61,
        "staff_issue": 0,
        "facility_issue": 0,
        "referral_issue": 0,
        "other": 13,
    }
    assert summary["by_branch"] == {
        "central": 7,
        "austin_north": 9,
        "dallas_uptown": 0,
        "houston_med_center": 4,
        "san_antonio_west": 0,
        "miami_brickell": 8,
        "miami_doral": 0,
        "orlando_east": 4,
        "tampa_bay": 7,
        "atlanta_midtown": 12,
        "savannah": 10,
        "london_city": 9,
        "london_west": 9,
        "manchester_central": 15,
    }


def test_legacy_import_rejects_distribution_mismatch_before_writing(manager_client, incident_engine, tmp_path):
    from routes.seed_incidents import seed_incidents

    csv_path = tmp_path / "mismatched-incidents.csv"
    csv_path.write_text(_synthetic_legacy_csv().replace("APPOINTMENT", "BILLING", 1), encoding="utf-8")

    with Session(incident_engine) as session:
        with pytest.raises(ValueError, match="does not match the HealthCore sample distribution"):
            seed_incidents(session, csv_path, "test-import-key-that-is-at-least-thirty-two-characters")
        count = session.exec(select(func.count()).select_from(ManagedIncident)).one()

    assert count == 0