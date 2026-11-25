from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel import select

import database
from conftest import auth_headers, login, register
from main import app
from routes.seed_inventory import seed_inventory
from models import MedicalSupply, SupplyConsumption, SupplyDelivery


@pytest.fixture
def inventory_engine() -> Iterator:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def inventory_client(client: TestClient, inventory_engine) -> Iterator[TestClient]:

    def override_db() -> Iterator[Session]:
        with Session(inventory_engine) as session:
            yield session

    app.dependency_overrides[database.get_db] = override_db
    yield client
    app.dependency_overrides.pop(database.get_db, None)


@pytest.fixture
def inventory_headers(inventory_client: TestClient) -> dict[str, str]:
    register(inventory_client)
    return auth_headers(login(inventory_client))


def test_inventory_routes_require_authentication(inventory_client: TestClient) -> None:
    assert inventory_client.get("/inventory/products").status_code == 401
    assert inventory_client.post(
        "/inventory/products",
        json={"name": "Gloves", "sku": "TEST-001", "category": "ppe", "unit": "box", "country": "US"},
    ).status_code == 401


def test_product_stock_and_orders_are_computed(inventory_client: TestClient, inventory_headers: dict[str, str]) -> None:
    product = inventory_client.post(
        "/inventory/products",
        headers=inventory_headers,
        json={"name": "Nitrile gloves", "sku": "TEST-001", "category": "ppe", "unit": "box", "country": "US"},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    assert product.json()["current_stock"] == 0

    delivery = inventory_client.post(
        "/inventory/orders/inbound",
        headers=inventory_headers,
        json={"supply_id": product_id, "quantity": 15, "vendor_name": "Test Vendor", "clinic_id": 1},
    )
    assert delivery.status_code == 201, delivery.text
    assert delivery.json()["user_uuid"]

    consumption = inventory_client.post(
        "/inventory/orders/outbound",
        headers=inventory_headers,
        json={"supply_id": product_id, "quantity": 4, "consumption_type": "clinical_use", "clinic_id": 1},
    )
    assert consumption.status_code == 201, consumption.text

    listed = inventory_client.get("/inventory/products", headers=inventory_headers)
    assert listed.json()[0]["current_stock"] == 11
    history = inventory_client.get("/inventory/orders", headers=inventory_headers)
    assert len(history.json()) == 2
    assert {order["order_type"] for order in history.json()} == {"inbound", "outbound"}


def test_invalid_consumption_and_overspend_are_rejected_without_persisting(
    inventory_client: TestClient, inventory_headers: dict[str, str]
) -> None:
    product = inventory_client.post(
        "/inventory/products",
        headers=inventory_headers,
        json={"name": "Rapid test", "sku": "TEST-002", "category": "diagnostics", "unit": "unit", "country": "UK"},
    ).json()
    inventory_client.post(
        "/inventory/orders/inbound",
        headers=inventory_headers,
        json={"supply_id": product["id"], "quantity": 5, "vendor_name": "Test Vendor", "clinic_id": 12},
    )
    invalid = inventory_client.post(
        "/inventory/orders/outbound",
        headers=inventory_headers,
        json={"supply_id": product["id"], "quantity": 1, "consumption_type": "other", "clinic_id": 1},
    )
    assert invalid.status_code == 422

    overspend = inventory_client.post(
        "/inventory/orders/outbound",
        headers=inventory_headers,
        json={"supply_id": product["id"], "quantity": 6, "consumption_type": "expiry_waste", "clinic_id": 1},
    )
    assert overspend.status_code == 400
    assert overspend.json()["detail"] == "Insufficient stock for supply 'Rapid test'. Available: 5, requested: 6."
    assert len(inventory_client.get("/inventory/orders", headers=inventory_headers).json()) == 1


def test_inventory_validates_clinic_supply_and_not_found(inventory_client: TestClient, inventory_headers: dict[str, str]) -> None:
    invalid_product = inventory_client.post(
        "/inventory/products",
        headers=inventory_headers,
        json={"name": "Invalid", "sku": "TEST-BAD", "category": "other", "unit": "box", "country": "US"},
    )
    assert invalid_product.status_code == 422
    assert inventory_client.get("/inventory/products/999", headers=inventory_headers).status_code == 404
    invalid_clinic = inventory_client.post(
        "/inventory/orders/inbound",
        headers=inventory_headers,
        json={"supply_id": 999, "quantity": 2, "vendor_name": "Vendor", "clinic_id": 13},
    )
    assert invalid_clinic.status_code == 422
    missing_supply = inventory_client.post(
        "/inventory/orders/inbound",
        headers=inventory_headers,
        json={"supply_id": 999, "quantity": 2, "vendor_name": "Vendor", "clinic_id": 1},
    )
    assert missing_supply.status_code == 404


def test_duplicate_sku_is_rejected(inventory_client: TestClient, inventory_headers: dict[str, str]) -> None:
    payload = {
        "name": "Gloves",
        "sku": "DUPLICATE-001",
        "category": "ppe",
        "unit": "box",
        "country": "US",
    }
    assert inventory_client.post("/inventory/products", headers=inventory_headers, json=payload).status_code == 201
    duplicate = inventory_client.post("/inventory/products", headers=inventory_headers, json=payload)
    assert duplicate.status_code == 409


def test_inventory_foreign_keys_are_enforced(inventory_engine) -> None:
    with Session(inventory_engine) as session:
        session.add(
            SupplyDelivery(
                supply_id=999,
                quantity=1,
                vendor_name="Invalid FK test",
                clinic_id=1,
                user_uuid="f871e9a9-71b5-451a-aec1-0f43bb70f338",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_seeded_stock_is_exposed_through_inventory_api(
    inventory_client: TestClient, inventory_headers: dict[str, str], inventory_engine
) -> None:
    current_user = database.get_user_by_email("user@example.com")
    assert current_user is not None
    with Session(inventory_engine) as session:
        seed_inventory(session, current_user["user_uuid"])

    response = inventory_client.get("/inventory/products", headers=inventory_headers)
    assert response.status_code == 200
    stock_by_sku = {supply["sku"]: supply["current_stock"] for supply in response.json()}
    assert stock_by_sku == {
        "HCR-PPE-001": 125,
        "HCR-PPE-002": 33,
        "HCR-WND-001": 25,
        "HCR-DIAG-001": 0,
        "HCR-DIAG-002": 0,
        "HCR-MED-001": 0,
    }


def test_new_and_legacy_tinydb_users_get_stable_uuids(inventory_client: TestClient) -> None:
    created = register(inventory_client)
    first_lookup = database.get_user(created["id"])
    second_lookup = database.get_user(created["id"])
    assert first_lookup is not None and second_lookup is not None
    assert first_lookup["user_uuid"] == second_lookup["user_uuid"]

    legacy = database.create_user(
        {
            "email": "legacy@example.com",
            "hashed_password": "not-a-real-hash",
            "is_active": True,
            "role": "user",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    with database.get_database() as tinydb:
        tinydb.table(database.USERS_TABLE).update({"user_uuid": None}, doc_ids=[legacy["id"]])
    migrated_once = database.get_user(legacy["id"])
    migrated_twice = database.get_user(legacy["id"])
    assert migrated_once is not None and migrated_twice is not None
    assert migrated_once["user_uuid"] == migrated_twice["user_uuid"]


def test_inventory_seed_is_context_exact_and_idempotent(inventory_engine) -> None:
    actor_uuid = "f871e9a9-71b5-451a-aec1-0f43bb70f338"

    with Session(inventory_engine) as session:
        first = seed_inventory(session, actor_uuid)
        second = seed_inventory(session, actor_uuid)
        assert first == {
            "medical_supplies": 6,
            "supply_deliveries": 4,
            "supply_consumptions": 3,
        }
        assert second == {
            "medical_supplies": 0,
            "supply_deliveries": 0,
            "supply_consumptions": 0,
        }

        supplies = session.exec(select(MedicalSupply)).all()
        assert len(supplies) == 6
        by_sku = {supply.sku: supply for supply in supplies}
        assert by_sku["HCR-PPE-001"].name == "Nitrile gloves (box of 100)"
        assert by_sku["HCR-PPE-002"].country == "UK"

        deliveries = session.exec(select(SupplyDelivery)).all()
        consumptions = session.exec(select(SupplyConsumption)).all()
        assert len(deliveries) == 4
        assert len(consumptions) == 3
        assert {row.user_uuid for row in [*deliveries, *consumptions]} == {actor_uuid}
        assert {row.consumption_type for row in consumptions} == {"clinical_use", "expiry_waste"}

        gloves_id = int(by_sku["HCR-PPE-001"].id)
        received = session.exec(
            select(func.sum(SupplyDelivery.quantity)).where(SupplyDelivery.supply_id == gloves_id)
        ).one()
        consumed = session.exec(
            select(func.sum(SupplyConsumption.quantity)).where(SupplyConsumption.supply_id == gloves_id)
        ).one()
        assert received - consumed == 125