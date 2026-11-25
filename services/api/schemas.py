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