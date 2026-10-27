"""Authenticated HealthCore incident register and aggregate reporting."""

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

import database
from auth.dependencies import get_current_user
from models import IncidentAuditEvent, ManagedIncident, utc_now
from schemas import (
    IncidentAuditResponse,
    IncidentCategory,
    IncidentBranch,
    IncidentOrigin,
    IncidentStatus,
    IncidentStatusUpdate,
    IncidentSummaryResponse,
    ManagedIncidentCreate,
    ManagedIncidentResponse,
)

router = APIRouter(
    prefix="/api/incident-manager",
    tags=["incident manager"],
    dependencies=[Depends(get_current_user)],
)

VALID_TRANSITIONS = {
    "open": {"in_progress", "discarded"},
    "in_progress": {"resolved", "discarded"},
}
BRANCH_COUNTRIES = {
    "central": "US",
    "austin_north": "US",
    "dallas_uptown": "US",
    "houston_med_center": "US",
    "san_antonio_west": "US",
    "miami_brickell": "US",
    "miami_doral": "US",
    "orlando_east": "US",
    "tampa_bay": "US",
    "atlanta_midtown": "US",
    "savannah": "US",
    "london_city": "UK",
    "london_west": "UK",
    "manchester_central": "UK",
}
CATEGORIES: tuple[IncidentCategory, ...] = (
    "clinical_equipment",
    "it_system",
    "billing_error",
    "compliance_breach",
    "patient_experience",
    "staff_issue",
    "facility_issue",
    "referral_issue",
    "other",
)
STATUSES: tuple[IncidentStatus, ...] = ("open", "in_progress", "resolved", "discarded")
BRANCHES: tuple[IncidentBranch, ...] = tuple(BRANCH_COUNTRIES)


def _event_response(event: IncidentAuditEvent) -> IncidentAuditResponse:
    return IncidentAuditResponse.model_validate(event)


def _incident_response(
    incident: ManagedIncident,
    events: list[IncidentAuditEvent],
) -> ManagedIncidentResponse:
    payload = incident.model_dump(exclude={"source_key"})
    payload["audit_events"] = [_event_response(event) for event in events]
    return ManagedIncidentResponse.model_validate(payload)


def _date_filters(
    statement,
    date_from: date | None,
    date_to: date | None,
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    if date_from is not None:
        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        statement = statement.where(ManagedIncident.created_at >= start)
    if date_to is not None:
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        statement = statement.where(ManagedIncident.created_at < end)
    return statement


@router.post("/incidents", response_model=ManagedIncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: ManagedIncidentCreate,
    session: Session = Depends(database.get_db),
    current_user: dict = Depends(get_current_user),
) -> ManagedIncidentResponse:
    actor_uuid = str(current_user["user_uuid"])
    now = utc_now()
    with session.begin():
        incident = ManagedIncident(
            **payload.model_dump(),
            status="open",
            created_at=now,
            updated_at=now,
            created_by_uuid=actor_uuid,
            updated_by_uuid=actor_uuid,
        )
        session.add(incident)
        session.flush()
        event = IncidentAuditEvent(
            incident_id=int(incident.id),
            action="created",
            to_status="open",
            actor_uuid=actor_uuid,
            created_at=now,
        )
        session.add(event)
        session.flush()
    session.refresh(incident)
    session.refresh(event)
    return _incident_response(incident, [event])


@router.get("/incidents", response_model=list[ManagedIncidentResponse])
def list_incidents(
    category: IncidentCategory | None = None,
    branch: IncidentBranch | None = None,
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(database.get_db),
    _current_user: dict = Depends(get_current_user),
) -> list[ManagedIncidentResponse]:
    statement = select(ManagedIncident)
    if category is not None:
        statement = statement.where(ManagedIncident.category == category)
    if branch is not None:
        statement = statement.where(ManagedIncident.branch == branch)
    if incident_status is not None:
        statement = statement.where(ManagedIncident.status == incident_status)
    statement = _date_filters(statement, date_from, date_to)
    incidents = session.exec(
        statement.order_by(ManagedIncident.created_at.desc(), ManagedIncident.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    if not incidents:
        return []
    incident_ids = [int(incident.id) for incident in incidents]
    events = session.exec(
        select(IncidentAuditEvent)
        .where(IncidentAuditEvent.incident_id.in_(incident_ids))
        .order_by(IncidentAuditEvent.created_at, IncidentAuditEvent.id)
    ).all()
    events_by_incident: dict[int, list[IncidentAuditEvent]] = {incident_id: [] for incident_id in incident_ids}
    for event in events:
        events_by_incident[event.incident_id].append(event)
    return [
        _incident_response(incident, events_by_incident[int(incident.id)])
        for incident in incidents
    ]


@router.get("/incidents/{incident_id}", response_model=ManagedIncidentResponse)
def get_incident(
    incident_id: int,
    session: Session = Depends(database.get_db),
    _current_user: dict = Depends(get_current_user),
) -> ManagedIncidentResponse:
    incident = session.get(ManagedIncident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    events = session.exec(
        select(IncidentAuditEvent)
        .where(IncidentAuditEvent.incident_id == incident_id)
        .order_by(IncidentAuditEvent.created_at, IncidentAuditEvent.id)
    ).all()
    return _incident_response(incident, events)


@router.patch("/incidents/{incident_id}/status", response_model=ManagedIncidentResponse)
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    session: Session = Depends(database.get_db),
    current_user: dict = Depends(get_current_user),
) -> ManagedIncidentResponse:
    actor_uuid = str(current_user["user_uuid"])
    now = utc_now()
    with session.begin():
        incident = session.get(ManagedIncident, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        if payload.status not in VALID_TRANSITIONS.get(incident.status, set()):
            raise HTTPException(status_code=409, detail="The requested incident status transition is not allowed")
        if payload.status == "resolved" and not (payload.corrective_action or "").strip():
            raise HTTPException(status_code=422, detail="Corrective action is required to resolve an incident")
        if payload.corrective_action is not None and payload.status != "resolved":
            raise HTTPException(status_code=422, detail="Corrective action can only be recorded when resolving")
        previous_status = incident.status
        incident.status = payload.status
        incident.updated_at = now
        incident.updated_by_uuid = actor_uuid
        if payload.status == "resolved":
            incident.corrective_action = payload.corrective_action.strip()
        event = IncidentAuditEvent(
            incident_id=incident_id,
            action="status_transition",
            from_status=previous_status,
            to_status=payload.status,
            actor_uuid=actor_uuid,
            created_at=now,
        )
        session.add(incident)
        session.add(event)
        session.flush()
    session.refresh(incident)
    events = session.exec(
        select(IncidentAuditEvent)
        .where(IncidentAuditEvent.incident_id == incident_id)
        .order_by(IncidentAuditEvent.created_at, IncidentAuditEvent.id)
    ).all()
    return _incident_response(incident, events)


@router.get("/summary", response_model=IncidentSummaryResponse)
def incident_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    session: Session = Depends(database.get_db),
    _current_user: dict = Depends(get_current_user),
) -> IncidentSummaryResponse:
    base = _date_filters(select(ManagedIncident), date_from, date_to)
    count_statement = select(func.count()).select_from(ManagedIncident)
    count_statement = _date_filters(count_statement, date_from, date_to)
    total = int(session.exec(count_statement).one())

    by_status = {key: 0 for key in STATUSES}
    for key, count in session.exec(
        select(ManagedIncident.status, func.count()).select_from(ManagedIncident)
        .where(ManagedIncident.id.in_(base.with_only_columns(ManagedIncident.id)))
        .group_by(ManagedIncident.status)
    ).all():
        by_status[key] = int(count)

    by_category = {key: 0 for key in CATEGORIES}
    for key, count in session.exec(
        select(ManagedIncident.category, func.count()).select_from(ManagedIncident)
        .where(ManagedIncident.id.in_(base.with_only_columns(ManagedIncident.id)))
        .group_by(ManagedIncident.category)
    ).all():
        by_category[key] = int(count)

    by_branch = {key: 0 for key in BRANCHES}
    for key, count in session.exec(
        select(ManagedIncident.branch, func.count()).select_from(ManagedIncident)
        .where(ManagedIncident.id.in_(base.with_only_columns(ManagedIncident.id)))
        .group_by(ManagedIncident.branch)
    ).all():
        by_branch[key] = int(count)

    critical_open_by_country = {"US": 0, "UK": 0}
    critical_statement = base.where(
        ManagedIncident.status == "open",
        ManagedIncident.is_critical.is_(True),
    )
    for branch in session.exec(critical_statement.with_only_columns(ManagedIncident.branch)).all():
        critical_open_by_country[BRANCH_COUNTRIES[branch]] += 1

    return IncidentSummaryResponse(
        total=total,
        by_status=by_status,
        by_category=by_category,
        by_branch=by_branch,
        critical_open_by_country=critical_open_by_country,
    )