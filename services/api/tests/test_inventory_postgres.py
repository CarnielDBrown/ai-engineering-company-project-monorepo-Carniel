"""Opt-in PostgreSQL integration coverage for inventory row locking.

Set INVENTORY_TEST_DATABASE_URL to a dedicated local PostgreSQL database whose
name begins with ``test_``. Tests create a uniquely named temporary schema and
drop only that schema; they never create or drop tables in the database's public
schema. Shared/remote database URLs are rejected.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine, select

from models import MedicalSupply, SupplyConsumption, SupplyDelivery
from routes.inventory import create_outbound_order
from schemas import OutboundOrderCreate


def _integration_database_url() -> str:
    import os

    configured_url = os.getenv("INVENTORY_TEST_DATABASE_URL", "").strip()
    if not configured_url:
        pytest.skip("Set INVENTORY_TEST_DATABASE_URL to run local PostgreSQL integration tests")

    url = make_url(configured_url)
    host = (url.host or "").strip("[]").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("PostgreSQL integration tests are restricted to a local database host")
    if not (url.database or "").startswith("test_"):
        pytest.fail("PostgreSQL integration tests require a dedicated database named with the test_ prefix")
    if url.get_backend_name() != "postgresql":
        pytest.fail("INVENTORY_TEST_DATABASE_URL must use PostgreSQL")
    return configured_url


@pytest.fixture
def postgres_inventory_engine():
    base_engine = create_engine(_integration_database_url(), pool_pre_ping=True)
    schema_name = f"inventory_it_{uuid4().hex}"
    try:
        with base_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

        isolated_engine = base_engine.execution_options(schema_translate_map={None: schema_name})
        SQLModel.metadata.create_all(isolated_engine)
        yield isolated_engine
    finally:
        try:
            with base_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        finally:
            base_engine.dispose()


def test_concurrent_consumptions_cannot_overspend_postgres(postgres_inventory_engine) -> None:
    with Session(postgres_inventory_engine) as session:
        supply = MedicalSupply(
            name="Concurrency test supply",
            sku=f"IT-{uuid4().hex}",
            category="ppe",
            unit="box",
            country="US",
        )
        session.add(supply)
        session.flush()
        session.add(
            SupplyDelivery(
                supply_id=int(supply.id),
                quantity=10,
                vendor_name="Integration test vendor",
                clinic_id=1,
                user_uuid="f871e9a9-71b5-451a-aec1-0f43bb70f338",
            )
        )
        session.commit()
        supply_id = int(supply.id)

    start_together = Barrier(2)

    def consume_seven_units() -> str:
        with Session(postgres_inventory_engine) as session:
            start_together.wait(timeout=10)
            try:
                create_outbound_order(
                    OutboundOrderCreate(
                        supply_id=supply_id,
                        quantity=7,
                        consumption_type="clinical_use",
                        clinic_id=1,
                    ),
                    session,
                    {"user_uuid": "f871e9a9-71b5-451a-aec1-0f43bb70f338"},
                )
                return "created"
            except Exception as exc:
                if isinstance(exc, HTTPException) and exc.status_code == 400:
                    return "rejected"
                raise

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: consume_seven_units(), range(2)))

    assert sorted(outcomes) == ["created", "rejected"]
    with Session(postgres_inventory_engine) as session:
        consumptions = session.exec(
            select(SupplyConsumption).where(SupplyConsumption.supply_id == supply_id)
        ).all()
        assert len(consumptions) == 1
        assert sum(order.quantity for order in consumptions) == 7
