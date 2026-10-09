"""TinyDB persistence and SQLModel session configuration for inventory."""

from functools import lru_cache
import os
from pathlib import Path
from threading import RLock
from typing import Any

from dotenv import load_dotenv
from sqlmodel import Session, create_engine
from tinydb import Query, TinyDB

DATA_DIR = Path(__file__).resolve().parent / "data"
DATABASE_PATH = DATA_DIR / "suppliers.json"
SUPPLIERS_TABLE = "suppliers"
USERS_TABLE = "users"
PROFILES_TABLE = "profiles"
PASSWORD_RESET_TOKENS_TABLE = "password_reset_tokens"
_PASSWORD_RESET_LOCK = RLock()
_USER_UUID_LOCK = RLock()


def _local_user_uuid(record: dict[str, Any], user_id: int, table: Any) -> dict[str, Any]:
    """Return a user with a stable UUID, lazily migrating legacy TinyDB records."""
    from uuid import UUID, uuid4

    with _USER_UUID_LOCK:
        stored_uuid = record.get("user_uuid")
        try:
            user_uuid = str(UUID(str(stored_uuid))) if stored_uuid else str(uuid4())
        except (ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(f"TinyDB user {user_id} has an invalid user_uuid") from exc
        if stored_uuid != user_uuid:
            table.update({"user_uuid": user_uuid}, doc_ids=[user_id])
        return {**record, "user_uuid": user_uuid, "id": user_id}


@lru_cache(maxsize=4)
def _inventory_engine(database_url: str):
    """Create a lazy SQLModel engine for the explicitly configured inventory DB."""
    return create_engine(database_url, pool_pre_ping=True)


def get_inventory_engine():
    """Get the configured inventory engine without connecting until first use."""
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL must be configured before using the inventory database; "
            "use an isolated local/test PostgreSQL database."
        )
    return _inventory_engine(database_url)


def get_db():
    """Yield a request-scoped SQLModel session for inventory operations."""
    with Session(get_inventory_engine()) as session:
        yield session


def get_database() -> TinyDB:
    """Open the local persistent database, creating its directory if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TinyDB(DATABASE_PATH)


def list_suppliers(*, country: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """Return supplier records matching any provided filters."""
    with get_database() as database:
        table = database.table(SUPPLIERS_TABLE)
        records = table.all()
    if country is not None:
        records = [record for record in records if record.get("country") == country]
    if category is not None:
        records = [record for record in records if category in record.get("categories", [])]
    return [{**record, "id": int(record.doc_id)} for record in records]


def get_supplier(supplier_id: int) -> dict[str, Any] | None:
    with get_database() as database:
        table = database.table(SUPPLIERS_TABLE)
        record = table.get(doc_id=supplier_id)
    return {**record, "id": int(record.doc_id)} if record else None


def insert_supplier(data: dict[str, Any]) -> dict[str, Any]:
    with get_database() as database:
        table = database.table(SUPPLIERS_TABLE)
        doc_id = table.insert(data)
    return {**data, "id": int(doc_id)}


def update_supplier(supplier_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with get_database() as database:
        table = database.table(SUPPLIERS_TABLE)
        if table.get(doc_id=supplier_id) is None:
            return None
        table.update(data, doc_ids=[supplier_id])
        record = table.get(doc_id=supplier_id)
    return {**record, "id": int(record.doc_id)} if record else None


def delete_supplier(supplier_id: int) -> bool:
    with get_database() as database:
        table = database.table(SUPPLIERS_TABLE)
        if table.get(doc_id=supplier_id) is None:
            return False
        table.remove(doc_ids=[supplier_id])
    return True


def supplier_exists_by_name(name: str) -> bool:
    with get_database() as database:
        return database.table(SUPPLIERS_TABLE).contains(Query().name == name)


def list_users() -> list[dict[str, Any]]:
    with get_database() as database:
        table = database.table(USERS_TABLE)
        records = table.all()
        return [_local_user_uuid(dict(record), int(record.doc_id), table) for record in records]


def get_user(user_id: int) -> dict[str, Any] | None:
    with get_database() as database:
        table = database.table(USERS_TABLE)
        record = table.get(doc_id=user_id)
        return _local_user_uuid(dict(record), int(record.doc_id), table) if record else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    with get_database() as database:
        table = database.table(USERS_TABLE)
        record = table.get(Query().email == normalized)
        return _local_user_uuid(dict(record), int(record.doc_id), table) if record else None


def create_user(data: dict[str, Any]) -> dict[str, Any]:
    from uuid import uuid4

    with get_database() as database:
        table = database.table(USERS_TABLE)
        if table.contains(Query().email == data["email"]):
            raise ValueError("Email is already registered")
        record = {**data, "user_uuid": str(uuid4())}
        doc_id = table.insert(record)
    return {**record, "id": int(doc_id)}


def update_user(user_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with get_database() as database:
        table = database.table(USERS_TABLE)
        if table.get(doc_id=user_id) is None:
            return None
        table.update(data, doc_ids=[user_id])
        record = table.get(doc_id=user_id)
    return {**record, "id": int(record.doc_id)} if record else None


def change_user_password(user_id: int, hashed_password: str) -> bool:
    """Update a password and invalidate reset tokens without a local reset race."""
    with _PASSWORD_RESET_LOCK:
        with get_database() as database:
            users = database.table(USERS_TABLE)
            if users.get(doc_id=user_id) is None:
                return False
            users.update({"hashed_password": hashed_password}, doc_ids=[user_id])
            database.table(PASSWORD_RESET_TOKENS_TABLE).remove(Query().user_id == user_id)
            return True


def create_password_reset_token(user_id: int, token_hash: str, expires_at: str) -> None:
    """Replace outstanding reset tokens and persist only the token digest."""
    with _PASSWORD_RESET_LOCK:
        with get_database() as database:
            table = database.table(PASSWORD_RESET_TOKENS_TABLE)
            table.remove(Query().user_id == user_id)
            table.insert({"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at})


def reset_password_with_token(token_hash: str, now: str, hashed_password: str) -> bool:
    """Validate, consume, and apply a reset under one process-local lock."""
    with _PASSWORD_RESET_LOCK:
        with get_database() as database:
            tokens = database.table(PASSWORD_RESET_TOKENS_TABLE)
            record = tokens.get(Query().token_hash == token_hash)
            if record is None or record.get("expires_at", "") <= now:
                return False

            user_id = int(record["user_id"])
            users = database.table(USERS_TABLE)
            user = users.get(doc_id=user_id)
            if user is None or not user.get("is_active"):
                tokens.remove(Query().user_id == user_id)
                return False

            users.update({"hashed_password": hashed_password}, doc_ids=[user_id])
            tokens.remove(Query().user_id == user_id)
            return True


def invalidate_password_reset_tokens(user_id: int) -> None:
    with _PASSWORD_RESET_LOCK:
        with get_database() as database:
            database.table(PASSWORD_RESET_TOKENS_TABLE).remove(Query().user_id == user_id)


def delete_user(user_id: int) -> bool:
    with get_database() as database:
        users = database.table(USERS_TABLE)
        if users.get(doc_id=user_id) is None:
            return False
        users.remove(doc_ids=[user_id])
        database.table(PROFILES_TABLE).remove(Query().user_id == user_id)
    return True


def create_profile(data: dict[str, Any]) -> dict[str, Any]:
    with get_database() as database:
        table = database.table(PROFILES_TABLE)
        doc_id = table.insert(data)
    return {**data, "id": int(doc_id)}


def get_profile_by_user_id(user_id: int) -> dict[str, Any] | None:
    with get_database() as database:
        record = database.table(PROFILES_TABLE).get(Query().user_id == user_id)
    return {**record, "id": int(record.doc_id)} if record else None


def update_profile(user_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with get_database() as database:
        table = database.table(PROFILES_TABLE)
        record = table.get(Query().user_id == user_id)
        if record is None:
            return None
        table.update(data, doc_ids=[record.doc_id])
        updated = table.get(doc_id=record.doc_id)
    return {**updated, "id": int(updated.doc_id)} if updated else None
