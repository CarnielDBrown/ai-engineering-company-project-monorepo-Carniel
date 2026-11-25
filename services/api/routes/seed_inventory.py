"""Idempotently seed the local HealthCore inventory development dataset.

Run explicitly with ``uv run seed-inventory`` after applying the approved local
schema setup. This command never creates tables or seeds during API startup.
"""

from uuid import UUID

from sqlmodel import Session, select

import database
from models import MedicalSupply, SupplyConsumption, SupplyDelivery

INVENTORY_SUPPLIES = (
    {
        "name": "Nitrile gloves (box of 100)",
        "sku": "HCR-PPE-001",
        "category": "ppe",
        "unit": "box",
        "country": "US",
    },
    {
        "name": "Surgical mask (pack of 50)",
        "sku": "HCR-PPE-002",
        "category": "ppe",
        "unit": "pack",
        "country": "UK",
    },
    {
        "name": "Adhesive wound dressing",
        "sku": "HCR-WND-001",
        "category": "wound_care",
        "unit": "box",
        "country": "US",
    },
    {
        "name": "Rapid strep test kit",
        "sku": "HCR-DIAG-001",
        "category": "diagnostics",
        "unit": "unit",
        "country": "US",
    },
    {
        "name": "Blood glucose test strips (50)",
        "sku": "HCR-DIAG-002",
        "category": "diagnostics",
        "unit": "box",
        "country": "UK",
    },
    {
        "name": "0.9% Saline solution 500ml",
        "sku": "HCR-MED-001",
        "category": "medications",
        "unit": "vial",
        "country": "US",
    },
)

# (SKU, quantity, vendor, clinic) — two distinct glove deliveries are required.
INVENTORY_DELIVERIES = (
    ("HCR-PPE-001", 100, "MedLine Industries", 1),
    ("HCR-PPE-001", 50, "Bound Tree Medical", 2),
    ("HCR-PPE-002", 40, "Cardinal Health UK", 10),
    ("HCR-WND-001", 25, "MedLine Industries", 3),
)

# (SKU, quantity, type, clinic) — quantities remain within the seeded deliveries.
INVENTORY_CONSUMPTIONS = (
    ("HCR-PPE-001", 20, "clinical_use", 1),
    ("HCR-PPE-001", 5, "expiry_waste", 2),
    ("HCR-PPE-002", 7, "clinical_use", 10),
)


def seed_inventory(session: Session, user_uuid: str) -> dict[str, int]:
    """Insert missing context seed rows without changing existing inventory.

    Movements are deduplicated by their seed business fields. This avoids adding
    duplicate seed quantities when rerun; existing matching operational rows are
    also treated as satisfying that seed event because the schema has no seed-key
    column and the seeder must not alter the milestone's data model.
    """
    actor_uuid = str(UUID(user_uuid))
    inserted = {"medical_supplies": 0, "supply_deliveries": 0, "supply_consumptions": 0}

    with session.begin():
        supplies_by_sku = {
            supply.sku: supply
            for supply in session.exec(select(MedicalSupply)).all()
        }
        for fields in INVENTORY_SUPPLIES:
            existing = supplies_by_sku.get(fields["sku"])
            if existing is None:
                existing = MedicalSupply(**fields)
                session.add(existing)
                session.flush()
                inserted["medical_supplies"] += 1
            elif any(getattr(existing, field) != value for field, value in fields.items()):
                raise ValueError(f"Existing supply {fields['sku']} conflicts with the HealthCore seed definition")
            supplies_by_sku[fields["sku"]] = existing

        delivery_keys = {
            (row.supply_id, row.quantity, row.vendor_name, row.clinic_id)
            for row in session.exec(select(SupplyDelivery)).all()
        }
        for sku, quantity, vendor_name, clinic_id in INVENTORY_DELIVERIES:
            supply = supplies_by_sku[sku]
            key = (int(supply.id), quantity, vendor_name, clinic_id)
            if key in delivery_keys:
                continue
            session.add(
                SupplyDelivery(
                    supply_id=int(supply.id),
                    quantity=quantity,
                    vendor_name=vendor_name,
                    clinic_id=clinic_id,
                    user_uuid=actor_uuid,
                )
            )
            delivery_keys.add(key)
            inserted["supply_deliveries"] += 1

        consumption_keys = {
            (row.supply_id, row.quantity, row.consumption_type, row.clinic_id)
            for row in session.exec(select(SupplyConsumption)).all()
        }
        for sku, quantity, consumption_type, clinic_id in INVENTORY_CONSUMPTIONS:
            supply = supplies_by_sku[sku]
            key = (int(supply.id), quantity, consumption_type, clinic_id)
            if key in consumption_keys:
                continue
            session.add(
                SupplyConsumption(
                    supply_id=int(supply.id),
                    quantity=quantity,
                    consumption_type=consumption_type,
                    clinic_id=clinic_id,
                    user_uuid=actor_uuid,
                )
            )
            consumption_keys.add(key)
            inserted["supply_consumptions"] += 1

    return inserted


def _seed_actor_uuid() -> str:
    """Use an existing active TinyDB user; never invent a development identity."""
    active_users = [user for user in database.list_users() if user.get("is_active")]
    if not active_users:
        raise RuntimeError(
            "Create an active local TinyDB user before seeding inventory; "
            "seed movement user_uuid values must come from TinyDB."
        )
    try:
        return str(UUID(str(active_users[0]["user_uuid"])))
    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError("The selected TinyDB user has no valid user_uuid") from exc


def main() -> None:
    actor_uuid = _seed_actor_uuid()
    with Session(database.get_inventory_engine()) as session:
        inserted = seed_inventory(session, actor_uuid)
    summary = ", ".join(f"{count} {table}" for table, count in inserted.items())
    print(f"Inventory seed complete: inserted {summary}.")


if __name__ == "__main__":
    main()
