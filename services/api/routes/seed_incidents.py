"""Explicit, idempotent import for the anonymized HealthCore incident CSV."""

import argparse
import csv
import hashlib
import hmac
import io
import os
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
import sys

from sqlmodel import Session, select

import database
from models import IncidentAuditEvent, ManagedIncident

REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_PACKAGE = REPO_ROOT / "packages" / "incidents-analysis"
if str(ANALYSIS_PACKAGE) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_PACKAGE))

from incidents_analysis import EmptyFileError, InvalidFormatError, analyze_bytes, validate_row  # noqa: E402

STATUS_MAPPING = {"OPEN": "open", "CLOSED": "resolved", "DISCARDED": "discarded"}
CATEGORY_MAPPING = {
    "APPOINTMENT": "patient_experience",
    "BILLING": "billing_error",
    "CLINICAL_CARE": "patient_experience",
    "ACCESSIBILITY": "patient_experience",
    "ADMINISTRATIVE": "other",
}
BRANCH_MAPPING = {
    "US-TX-01": "central",
    "US-TX-02": "austin_north",
    "US-TX-03": "houston_med_center",
    "US-FL-01": "miami_brickell",
    "US-FL-02": "orlando_east",
    "US-FL-03": "tampa_bay",
    "US-GA-01": "atlanta_midtown",
    "US-GA-02": "atlanta_midtown",
    "US-GA-03": "savannah",
    "UK-LON-01": "london_city",
    "UK-LON-02": "london_west",
    "UK-MAN-01": "manchester_central",
}
EXPECTED_STATUS_COUNTS = {"open": 28, "resolved": 52, "discarded": 14}
EXPECTED_CATEGORY_COUNTS = {"patient_experience": 61, "billing_error": 20, "other": 13}
EXPECTED_BRANCH_COUNTS = {
    "manchester_central": 15,
    "atlanta_midtown": 12,
    "savannah": 10,
    "austin_north": 9,
    "london_west": 9,
    "london_city": 9,
    "miami_brickell": 8,
    "tampa_bay": 7,
    "central": 7,
    "houston_med_center": 4,
    "orlando_east": 4,
}
EXPECTED_INVALID_RULES = {
    "invalid_clinic_id": 1,
    "country_mismatch": 1,
    "invalid_category": 1,
    "empty_description": 1,
    "missing_patient_id": 1,
    "closed_without_score": 1,
}


def _source_digest(incident_id: str, import_key: str) -> str:
    return hmac.new(import_key.encode("utf-8"), incident_id.encode("utf-8"), hashlib.sha256).hexdigest()


def seed_incidents(session: Session, csv_path: Path, import_key: str) -> dict[str, int | dict[str, int]]:
    """Import validated rows and return count-only results, never source values."""
    if len(import_key) < 32:
        raise ValueError("INCIDENT_IMPORT_KEY must contain at least 32 characters")
    try:
        payload = csv_path.read_bytes()
        analysis = analyze_bytes(payload, source_name="legacy incident CSV")
        text = payload.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError, EmptyFileError, InvalidFormatError) as exc:
        raise ValueError("The incident CSV could not be validated") from exc

    reader = csv.DictReader(io.StringIO(text))
    invalid_by_rule: Counter[str] = Counter()
    counts = {"inserted": 0, "duplicates": 0, "invalid": 0}
    status_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    branch_counts: Counter[str] = Counter()
    prepared_rows: list[dict] = []

    for row in reader:
        broken_rules = validate_row(row)
        description = row.get("description") or ""
        title = description[:120].strip()
        if not title:
            broken_rules.append("empty_title")
        if broken_rules:
            counts["invalid"] += 1
            invalid_by_rule.update(broken_rules)
            continue

        incident_id = (row.get("incident_id") or "").strip()
        digest = _source_digest(incident_id, import_key)
        incident_date = date.fromisoformat((row.get("date") or "").strip())
        timestamp = datetime.combine(incident_date, time.min, tzinfo=timezone.utc)
        status_value = STATUS_MAPPING[(row.get("status") or "").strip()]
        category_value = CATEGORY_MAPPING[(row.get("category") or "").strip()]
        branch_value = BRANCH_MAPPING.get((row.get("clinic_id") or "").strip(), "central")
        status_counts[status_value] += 1
        category_counts[category_value] += 1
        branch_counts[branch_value] += 1
        prepared_rows.append(
            {
                "title": title,
                "description": description,
                "category": category_value,
                "branch": branch_value,
                "status": status_value,
                "origin": "customer",
                "is_critical": False,
                "created_at": timestamp,
                "updated_at": timestamp,
                "source_key": digest,
            }
        )

    if (
        analysis.total_records != 100
        or analysis.valid_records != 94
        or analysis.invalid_records != 6
        or dict(invalid_by_rule) != EXPECTED_INVALID_RULES
        or dict(status_counts) != EXPECTED_STATUS_COUNTS
        or dict(category_counts) != EXPECTED_CATEGORY_COUNTS
        or dict(branch_counts) != EXPECTED_BRANCH_COUNTS
        or analysis.by_country != {"US": 61, "UK": 33}
    ):
        raise ValueError("The CSV does not match the HealthCore sample distribution; no rows were imported")

    with session.begin():
        existing_digests = set(
            session.exec(
                select(ManagedIncident.source_key).where(ManagedIncident.source_key.is_not(None))
            ).all()
        )
        for fields in prepared_rows:
            digest = fields["source_key"]
            if digest in existing_digests:
                counts["duplicates"] += 1
                continue

            incident = ManagedIncident(**fields)
            session.add(incident)
            session.flush()
            session.add(
                IncidentAuditEvent(
                    incident_id=int(incident.id),
                    action="legacy_import",
                    to_status=fields["status"],
                    created_at=fields["created_at"],
                )
            )
            existing_digests.add(digest)
            counts["inserted"] += 1

    return {**counts, "invalid_by_rule": dict(invalid_by_rule)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an anonymized HealthCore incident CSV.")
    parser.add_argument("csv_path", type=Path, help="Path to the anonymized incident CSV")
    args = parser.parse_args()
    import_key = os.getenv("INCIDENT_IMPORT_KEY", "")
    try:
        with Session(database.get_inventory_engine()) as session:
            result = seed_incidents(session, args.csv_path, import_key)
    except (RuntimeError, ValueError):
        print("Incident import failed validation or database configuration.", file=sys.stderr)
        raise SystemExit(1)

    print(
        "Incident import complete: "
        f"inserted={result['inserted']}, duplicates={result['duplicates']}, invalid={result['invalid']}."
    )
    invalid_by_rule = result["invalid_by_rule"]
    if isinstance(invalid_by_rule, dict):
        for rule, count in sorted(invalid_by_rule.items()):
            print(f"Invalid rule {rule}: {count}")


if __name__ == "__main__":
    main()