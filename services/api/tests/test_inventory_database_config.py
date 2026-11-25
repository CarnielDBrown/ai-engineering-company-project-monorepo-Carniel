"""Regression tests for safe PostgreSQL URL and driver configuration."""

from sqlalchemy.engine import make_url

import database


def test_bare_postgresql_url_uses_declared_psycopg2_driver(monkeypatch) -> None:
    captured: list[str] = []
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://test_user:test_password@localhost/test_inventory",
    )
    monkeypatch.setattr(database, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(database, "_inventory_engine", lambda url: captured.append(url) or object())

    database.get_inventory_engine()

    assert make_url(captured[0]).drivername == "postgresql+psycopg2"


def test_explicit_postgresql_driver_is_preserved(monkeypatch) -> None:
    captured: list[str] = []
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://test_user:test_password@localhost/test_inventory",
    )
    monkeypatch.setattr(database, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(database, "_inventory_engine", lambda url: captured.append(url) or object())

    database.get_inventory_engine()

    assert make_url(captured[0]).drivername == "postgresql+psycopg2"


def test_tinydb_path_can_be_configured_for_persistent_local_accounts(monkeypatch, tmp_path) -> None:
    path = tmp_path / "private" / "healthcore.json"
    monkeypatch.setenv("TINYDB_PATH", str(path))

    with database.get_database() as tinydb:
        tinydb.table("users").insert({"synthetic": True})

    assert path.is_file()