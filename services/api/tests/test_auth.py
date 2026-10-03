from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import jwt

from auth.security import ALGORITHM
from conftest import auth_headers, login, register


def test_registration_login_and_me_exposes_linked_profile_only(client):
    user = register(client, name="Ada Test", phone="555-0100", address="1 Example Way")
    assert user["role"] == "user"
    assert "hashed_password" not in user

    token = login(client)
    headers = auth_headers(token)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"
    assert me.json()["profile"]["name"] == "Ada Test"
    assert me.json()["profile"]["phone"] == "555-0100"
    assert "hashed_password" not in me.text
    assert client.get("/profiles/me", headers=headers).json()["user_id"] == user["id"]


def test_auth_required_for_business_routes_and_invalid_tokens(client):
    for path in (
        "/suppliers",
        "/api/incidents/results/export",
        "/users",
        "/profiles/me",
        "/auth/me",
    ):
        response = client.get(path)
        assert response.status_code == 401, (path, response.text)

    change_payload = {"current_password": "Correct-Horse-42", "new_password": "New-Password-123"}
    assert client.post("/auth/change-password", json=change_payload).status_code == 401
    assert client.put("/profiles/me", json={"name": "Unauthenticated"}).status_code == 401

    register(client)
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        os.environ["SECRET_KEY"],
        algorithm=ALGORITHM,
    )
    for token in ("not-a-jwt", expired):
        response = client.get("/suppliers", headers=auth_headers(token))
        assert response.status_code == 401

    wrong_signature = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "x" * 40, algorithm=ALGORITHM)
    assert client.get("/suppliers", headers=auth_headers(wrong_signature)).status_code == 401


def test_token_configuration_is_required_and_validated(client, monkeypatch):
    from auth.security import create_access_token

    monkeypatch.delenv("SECRET_KEY")
    try:
        create_access_token(1)
    except RuntimeError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("missing signing key must fail closed")

    monkeypatch.setenv("SECRET_KEY", "a-valid-test-secret-with-more-than-thirty-two-bytes")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "0")
    try:
        create_access_token(1)
    except RuntimeError as exc:
        assert "ACCESS_TOKEN_EXPIRE_MINUTES" in str(exc)
    else:
        raise AssertionError("non-positive expiration must fail closed")


def test_registration_rejects_duplicates_privilege_fields_and_invalid_roles(client):
    register(client)
    duplicate = client.post(
        "/users",
        json={"email": "USER@example.com", "password": "Correct-Horse-42", "name": "Other"},
    )
    assert duplicate.status_code == 409
    assert client.post(
        "/users",
        json={"email": "elevated@example.com", "password": "Correct-Horse-42", "name": "Elevated", "role": "admin"},
    ).status_code == 422


def test_registration_allows_missing_optional_profile_fields(client):
    response = client.post("/users", json={"email": "no-profile@example.com", "password": "Correct-Horse-42"})
    assert response.status_code == 201, response.text
    token = client.post("/auth/login", json={"email": "no-profile@example.com", "password": "Correct-Horse-42"}).json()["access_token"]
    headers = auth_headers(token)
    assert client.get("/auth/me", headers=headers).json()["profile"] is None
    assert client.get("/profiles/me", headers=headers).status_code == 404


def test_auth_me_rejects_missing_expired_wrong_signature_and_unknown_user_tokens(client):
    register(client)
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        os.environ["SECRET_KEY"],
        algorithm=ALGORITHM,
    )
    wrong_signature = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "x" * 40,
        algorithm=ALGORITHM,
    )
    unknown_user = jwt.encode(
        {"sub": "999", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        os.environ["SECRET_KEY"],
        algorithm=ALGORITHM,
    )

    assert client.get("/auth/me").status_code == 401
    for token in ("not-a-jwt", expired, wrong_signature, unknown_user):
        assert client.get("/auth/me", headers=auth_headers(token)).status_code == 401


def test_auth_me_accepts_identity_without_linked_profile(client):
    client.post("/users", json={"email": "no-profile@example.com", "password": "Correct-Horse-42"})
    token = login(client, "no-profile@example.com")

    response = client.get("/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["profile"] is None


def test_inactive_user_cannot_login_or_use_existing_access_token(client):
    from auth.security import create_access_token
    import database

    user = register(client)
    database.update_user(user["id"], {"is_active": False})

    response = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "Correct-Horse-42"}
    )
    assert response.status_code == 401
    token = create_access_token(user["id"])
    assert client.get("/auth/me", headers=auth_headers(token)).status_code == 401


def test_user_cannot_change_password_through_generic_update(client):
    user = register(client)
    headers = auth_headers(login(client))
    response = client.put(f"/users/{user['id']}", headers=headers, json={"password": "New-Correct-Horse-99"})
    assert response.status_code == 403


def test_multibyte_password_over_bcrypt_limit_is_rejected(client):
    response = client.post(
        "/users",
        json={"email": "long-password@example.com", "password": "é" * 37},
    )
    assert response.status_code == 422


def test_user_ownership_and_role_permissions(client, admin_headers):
    first = register(client, "first@example.com")
    first_headers = auth_headers(login(client, "first@example.com"))
    second = register(client, "second@example.com")

    assert client.get(f"/users/{second['id']}", headers=first_headers).status_code == 403
    assert client.put(
        f"/users/{first['id']}", headers=first_headers, json={"role": "admin"}
    ).status_code == 403
    assert client.put(
        "/profiles/me", headers=first_headers, json={"name": "Updated", "phone": None, "address": None}
    ).status_code == 200

    assert client.get(f"/users/{second['id']}", headers=admin_headers).status_code == 200
    assert client.put(
        f"/users/{second['id']}", headers=admin_headers, json={"role": "manager"}
    ).status_code == 200
    assert client.get(f"/users/{second['id']}", headers=first_headers).status_code == 403


def test_user_collection_and_resource_authorization_and_missing_users(client, admin_headers):
    user = register(client)
    user_headers = auth_headers(login(client))

    assert client.get("/users").status_code == 401
    assert client.get("/users", headers=user_headers).status_code == 403
    listed = client.get("/users", headers=admin_headers)
    assert listed.status_code == 200
    assert all("hashed_password" not in item for item in listed.json())

    assert client.get("/users/999", headers=admin_headers).status_code == 404
    assert client.put("/users/999", headers=admin_headers, json={"email": "new@example.com"}).status_code == 404
    assert client.delete("/users/999", headers=admin_headers).status_code == 404
    assert client.get(f"/users/{user['id']}").status_code == 401
    assert client.put(f"/users/{user['id']}", json={"email": "new@example.com"}).status_code == 401
    assert client.delete(f"/users/{user['id']}").status_code == 401


def test_non_admin_cannot_read_or_modify_another_users_resource(client):
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")
    headers = auth_headers(login(client, "first@example.com"))

    assert client.get(f"/users/{second['id']}", headers=headers).status_code == 403
    assert client.put(
        f"/users/{second['id']}", headers=headers, json={"email": "changed@example.com"}
    ).status_code == 403
    assert client.delete(f"/users/{second['id']}", headers=headers).status_code == 403
    assert client.get(f"/users/{first['id']}", headers=headers).status_code == 200


def test_user_update_rejects_empty_duplicate_and_invalid_updates(client):
    first = register(client, "first@example.com")
    register(client, "second@example.com")
    headers = auth_headers(login(client, "first@example.com"))

    assert client.put(f"/users/{first['id']}", headers=headers, json={}).status_code == 422
    duplicate = client.put(
        f"/users/{first['id']}", headers=headers, json={"email": "second@example.com"}
    )
    assert duplicate.status_code == 409
    assert client.put(f"/users/{first['id']}", headers=headers, json={"email": None}).status_code == 422
    assert client.put(f"/users/{first['id']}", headers=headers, json={"unknown": "value"}).status_code == 422


def test_deleting_user_cascades_profile(client):
    user = register(client)
    headers = auth_headers(login(client))
    response = client.delete(f"/users/{user['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/profiles/me", headers=headers).status_code == 401


def test_profile_routes_require_auth_and_validate_updates(client):
    register(client)
    headers = auth_headers(login(client))

    assert client.get("/profiles/me").status_code == 401
    assert client.put("/profiles/me", json={"name": "New Name"}).status_code == 401
    updated = client.put("/profiles/me", headers=headers, json={"name": "Updated", "phone": None})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated"
    assert client.put("/profiles/me", headers=headers, json={}).status_code == 422
    assert client.put("/profiles/me", headers=headers, json={"name": ""}).status_code == 422
    assert client.put("/profiles/me", headers=headers, json={"name": "Updated", "extra": True}).status_code == 422


def test_invalid_login_and_malformed_stored_hash_fail_closed(client):
    assert client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "Correct-Horse-42"}
    ).status_code == 401
    register(client)
    import database

    user = database.get_user_by_email("user@example.com")
    database.update_user(user["id"], {"hashed_password": "broken-hash"})
    assert client.post(
        "/auth/login", json={"email": "user@example.com", "password": "Correct-Horse-42"}
    ).status_code == 401
