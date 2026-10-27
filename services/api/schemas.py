"""Request and response schemas for medical-supply inventory."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SupplyCategory = Literal["ppe", "wound_care", "diagnostics", "medications", "consumables"]
SupplyCountry = Literal["US", "UK"]
SupplyUnit = Literal["box", "unit", "pack", "vial"]
ConsumptionType = Literal["clinical_use", "expiry_waste"]


class MedicalSupplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    category: SupplyCategory
    unit: SupplyUnit
    country: SupplyCountry


class MedicalSupplyResponse(MedicalSupplyCreate):
    id: int
    current_stock: int


class InboundOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supply_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    vendor_name: str = Field(min_length=1)
    clinic_id: int = Field(ge=1, le=12)


class OutboundOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supply_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    consumption_type: ConsumptionType
    clinic_id: int = Field(ge=1, le=12)


class SupplyDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supply_id: int
    quantity: int
    vendor_name: str
    clinic_id: int
    created_at: datetime
    user_uuid: str


class SupplyConsumptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supply_id: int
    quantity: int
    consumption_type: ConsumptionType
    clinic_id: int
    created_at: datetime
    user_uuid: str


class InventoryOrderResponse(BaseModel):
    order_type: Literal["inbound", "outbound"]
    order_id: int
    supply: MedicalSupplyResponse
    quantity: int
    clinic_id: int
    created_at: datetime
    user_uuid: str
    vendor_name: str | None = None
    consumption_type: ConsumptionType | None = None


IncidentCategory = Literal[
    "clinical_equipment",
    "it_system",
    "billing_error",
    "compliance_breach",
    "patient_experience",
    "staff_issue",
    "facility_issue",
    "referral_issue",
    "other",
]
IncidentStatus = Literal["open", "in_progress", "resolved", "discarded"]
IncidentOrigin = Literal["customer", "branch", "internal"]
IncidentBranch = Literal[
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
]


class ManagedIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    category: IncidentCategory
    branch: IncidentBranch
    origin: IncidentOrigin
    is_critical: bool = False


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IncidentStatus
    corrective_action: str | None = Field(default=None, min_length=1)


class IncidentAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: Literal["created", "legacy_import", "status_transition"]
    from_status: IncidentStatus | None
    to_status: IncidentStatus
    actor_uuid: str | None
    created_at: datetime


class ManagedIncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: IncidentCategory
    branch: IncidentBranch
    status: IncidentStatus
    origin: IncidentOrigin
    is_critical: bool
    corrective_action: str | None
    created_at: datetime
    updated_at: datetime
    created_by_uuid: str | None
    updated_by_uuid: str | None
    audit_events: list[IncidentAuditResponse] = []


class IncidentSummaryResponse(BaseModel):
    total: int
    by_status: dict[IncidentStatus, int]
    by_category: dict[IncidentCategory, int]
    by_branch: dict[IncidentBranch, int]
    critical_open_by_country: dict[Literal["US", "UK"], int]