"""Authenticated medical-supply inventory endpoints."""

from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

import database
from auth.dependencies import get_current_user
from models import MedicalSupply, SupplyConsumption, SupplyDelivery
from schemas import (
    InboundOrderCreate,
    InventoryOrderResponse,
    MedicalSupplyCreate,
    MedicalSupplyResponse,
    OutboundOrderCreate,
    SupplyConsumptionResponse,
    SupplyDeliveryResponse,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])


def _stock_by_supply(session: Session, supply_ids: Iterable[int] | None = None) -> dict[int, int]:
    """Aggregate movements in two queries rather than loading movement rows."""
    delivery_query = select(SupplyDelivery.supply_id, func.sum(SupplyDelivery.quantity)).group_by(
        SupplyDelivery.supply_id
    )
    consumption_query = select(
        SupplyConsumption.supply_id, func.sum(SupplyConsumption.quantity)
    ).group_by(SupplyConsumption.supply_id)
    if supply_ids is not None:
        ids = list(supply_ids)
        if not ids:
            return {}
        delivery_query = delivery_query.where(SupplyDelivery.supply_id.in_(ids))
        consumption_query = consumption_query.where(SupplyConsumption.supply_id.in_(ids))
    deliveries = {int(supply_id): int(total) for supply_id, total in session.exec(delivery_query).all()}
    consumptions = {
        int(supply_id): int(total) for supply_id, total in session.exec(consumption_query).all()
    }
    ids = set(deliveries) | set(consumptions)
    if supply_ids is not None:
        ids.update(supply_ids)
    return {supply_id: deliveries.get(supply_id, 0) - consumptions.get(supply_id, 0) for supply_id in ids}


def _supply_response(supply: MedicalSupply, stock: int) -> MedicalSupplyResponse:
    return MedicalSupplyResponse(
        id=int(supply.id),
        name=supply.name,
        sku=supply.sku,
        category=supply.category,
        unit=supply.unit,
        country=supply.country,
        current_stock=stock,
    )


def _get_supply(session: Session, supply_id: int, *, lock: bool = False) -> MedicalSupply:
    statement = select(MedicalSupply).where(MedicalSupply.id == supply_id)
    if lock:
        statement = statement.with_for_update()
    supply = session.exec(statement).first()
    if supply is None:
        raise HTTPException(status_code=404, detail="Medical supply not found")
    return supply


@router.get("/products", response_model=list[MedicalSupplyResponse])
def list_products(
    session: Session = Depends(database.get_db),
    _current_user: dict = Depends(get_current_user),
) -> list[MedicalSupplyResponse]:
    supplies = session.exec(select(MedicalSupply).order_by(MedicalSupply.id)).all()
    stock = _stock_by_supply(session, (int(supply.id) for supply in supplies))
    return [_supply_response(supply, stock.get(int(supply.id), 0)) for supply in supplies]


@router.post("/products", response_model=MedicalSupplyResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: MedicalSupplyCreate,
    session: Session = Depends(database.get_db),
    _current_user: dict = Depends(get_current_user),
) -> MedicalSupplyResponse:
    with session.begin():
        duplicate = session.exec(select(MedicalSupply).where(MedicalSupply.sku == payload.sku)).first()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="A medical supply with this SKU already exists")
        supply = MedicalSupply(**payload.model_dump())
        session.add(supply)
        session.flush()
        session.refresh(supply)
    return _supply_response(supply, 0)


@router.get("/products/{supply_id}", response_model=MedicalSupplyResponse)
def get_product(
    supply_id: int,
    session: Session = Depends(database.get_db),
    _current_user: dict = Depends(get_current_user),
) -> MedicalSupplyResponse:
    supply = _get_supply(session, supply_id)
    stock = _stock_by_supply(session, [supply_id]).get(supply_id, 0)
    return _supply_response(supply, stock)


@router.post("/orders/inbound", response_model=SupplyDeliveryResponse, status_code=status.HTTP_201_CREATED)
def create_inbound_order(
    payload: InboundOrderCreate,
    session: Session = Depends(database.get_db),
    current_user: dict = Depends(get_current_user),
) -> SupplyDeliveryResponse:
    with session.begin():
        _get_supply(session, payload.supply_id)
        order = SupplyDelivery(**payload.model_dump(), user_uuid=current_user["user_uuid"])
        session.add(order)
        session.flush()
        session.refresh(order)
    return SupplyDeliveryResponse.model_validate(order)


@router.post("/orders/outbound", response_model=SupplyConsumptionResponse, status_code=status.HTTP_201_CREATED)
def create_outbound_order(
    payload: OutboundOrderCreate,
    session: Session = Depends(database.get_db),
    current_user: dict = Depends(get_current_user),
) -> SupplyConsumptionResponse:
    with session.begin():
        # PostgreSQL row lock serializes consumption writers per supply.
        supply = _get_supply(session, payload.supply_id, lock=True)
        available = _stock_by_supply(session, [payload.supply_id]).get(payload.supply_id, 0)
        if payload.quantity > available:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for supply '{supply.name}'. Available: {available}, "
                    f"requested: {payload.quantity}."
                ),
            )
        order = SupplyConsumption(**payload.model_dump(), user_uuid=current_user["user_uuid"])
        session.add(order)
        session.flush()
        session.refresh(order)
    return SupplyConsumptionResponse.model_validate(order)


@router.get("/orders", response_model=list[InventoryOrderResponse])
def list_orders(
    session: Session = Depends(database.get_db),
    _current_user: dict = Depends(get_current_user),
) -> list[InventoryOrderResponse]:
    deliveries = session.exec(select(SupplyDelivery).order_by(SupplyDelivery.created_at.desc())).all()
    consumptions = session.exec(
        select(SupplyConsumption).order_by(SupplyConsumption.created_at.desc())
    ).all()
    supply_ids = {order.supply_id for order in [*deliveries, *consumptions]}
    supplies = {
        int(supply.id): supply
        for supply in session.exec(select(MedicalSupply).where(MedicalSupply.id.in_(supply_ids))).all()
    } if supply_ids else {}
    stock = _stock_by_supply(session, supply_ids)
    result: list[InventoryOrderResponse] = []
    for order in deliveries:
        supply = supplies.get(order.supply_id)
        if supply is not None:
            result.append(
                InventoryOrderResponse(
                    order_type="inbound",
                    order_id=int(order.id),
                    supply=_supply_response(supply, stock.get(order.supply_id, 0)),
                    quantity=order.quantity,
                    clinic_id=order.clinic_id,
                    created_at=order.created_at,
                    user_uuid=order.user_uuid,
                    vendor_name=order.vendor_name,
                )
            )
    for order in consumptions:
        supply = supplies.get(order.supply_id)
        if supply is not None:
            result.append(
                InventoryOrderResponse(
                    order_type="outbound",
                    order_id=int(order.id),
                    supply=_supply_response(supply, stock.get(order.supply_id, 0)),
                    quantity=order.quantity,
                    clinic_id=order.clinic_id,
                    created_at=order.created_at,
                    user_uuid=order.user_uuid,
                    consumption_type=order.consumption_type,
                )
            )
    return sorted(result, key=lambda item: item.created_at, reverse=True)