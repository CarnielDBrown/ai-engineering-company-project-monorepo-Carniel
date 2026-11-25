"""Pydantic supplier models and SQLModel inventory tables."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlmodel import Field as SQLField
from sqlmodel import Relationship, SQLModel

SupplierCountry = Literal["USA", "UK"]
SupplierStatus = Literal["active", "suspended"]
ComplianceAgreement = Literal["BAA", "DPA", "both"] | None

VALID_CATEGORIES = (
    "medical_supplies",
    "laboratory_services",
    "pharmaceutical",
    "clinical_software",
    "it_infrastructure",
    "hr_and_payroll_software",
    "cleaning_and_facilities",
    "patient_communication",
    "billing_and_coding_software",
    "training_platforms",
)


class SupplierFields(BaseModel):
    """Fields shared by supplier create and response representations."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    country: SupplierCountry
    categories: list[Literal[
        "medical_supplies",
        "laboratory_services",
        "pharmaceutical",
        "clinical_software",
        "it_infrastructure",
        "hr_and_payroll_software",
        "cleaning_and_facilities",
        "patient_communication",
        "billing_and_coding_software",
        "training_platforms",
    ]] = Field(min_length=1)
    monthly_rate: float = Field(gt=0)
    currency: Literal["USD", "GBP"]
    status: SupplierStatus
    compliance_agreement: ComplianceAgreement = None
    contract_renewal_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    contact_email: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def currency_matches_country(self) -> "SupplierFields":
        expected = "USD" if self.country == "USA" else "GBP"
        if self.currency != expected:
            raise ValueError(f"currency must be {expected} for country {self.country}")
        return self


class SupplierCreate(SupplierFields):
    """Client-supplied fields. updated_at is deliberately not accepted."""


class SupplierRateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monthly_rate: float = Field(gt=0)


class SupplierStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: SupplierStatus


class SupplierResponse(SupplierFields):
    """Stored supplier with system-managed metadata and TinyDB identifier."""

    id: int
    updated_at: datetime


class MedicalSupply(SQLModel, table=True):
    """A catalogue item; stock is derived from deliveries and consumptions."""

    __tablename__ = "medical_supplies"

    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    sku: str = SQLField(index=True, unique=True)
    category: str
    unit: str
    country: str
    deliveries: list["SupplyDelivery"] = Relationship(back_populates="supply")
    consumptions: list["SupplyConsumption"] = Relationship(back_populates="supply")


class SupplyDelivery(SQLModel, table=True):
    """Inbound stock movement from a vendor to one clinic."""

    __tablename__ = "supply_deliveries"

    id: int | None = SQLField(default=None, primary_key=True)
    supply_id: int = SQLField(foreign_key="medical_supplies.id", index=True)
    quantity: int
    vendor_name: str
    clinic_id: int
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(timezone.utc), index=True)
    user_uuid: str
    supply: "MedicalSupply" = Relationship(back_populates="deliveries")


class SupplyConsumption(SQLModel, table=True):
    """Outbound stock movement recorded by clinic staff."""

    __tablename__ = "supply_consumptions"

    id: int | None = SQLField(default=None, primary_key=True)
    supply_id: int = SQLField(foreign_key="medical_supplies.id", index=True)
    quantity: int
    consumption_type: str
    clinic_id: int
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(timezone.utc), index=True)
    user_uuid: str
    supply: "MedicalSupply" = Relationship(back_populates="consumptions")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for system-managed updates."""
    return datetime.now(timezone.utc)
