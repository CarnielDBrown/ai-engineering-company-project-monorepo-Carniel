from __future__ import annotations

import builtins

import pytest

from incidents_analysis import InvalidFormatError, analyze_file, validate_row


def test_analyze_file_maps_oserror_to_safe_message(monkeypatch):
    def fail_open(*_args, **_kwargs):
        raise OSError("/private/patient/data.csv: permission denied")

    monkeypatch.setattr(builtins, "open", fail_open)

    with pytest.raises(InvalidFormatError, match="^The specified CSV file could not be read\\.$"):
        analyze_file("sensitive-input.csv")


def test_validate_row_reports_rule_keys_without_returning_row_data():
    row = {
        "incident_id": "HC-000001",
        "date": "2026-01-01",
        "clinic_id": "US-TX-01",
        "country": "US",
        "category": "APPOINTMENT",
        "description": "Appointment follow-up issue",
        "status": "OPEN",
        "patient_id": "PAT-123456",
        "satisfaction_score": "",
    }

    assert validate_row(row) == []
    row["category"] = "PATIENT-NAME-MUST-NOT-BE-RETURNED"
    assert validate_row(row) == ["invalid_category"]