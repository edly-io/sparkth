from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import get_password_hash
from app.models.user import User


def test_create_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test User",
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "id" in data
    assert "hashed_password" not in data


def test_create_user_existing_username(client: TestClient, session: Session) -> None:
    hashed_password = get_password_hash("testpassword")
    user = User(
        name="Test User",
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
    )
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Another User",
            "username": "testuser",
            "email": "another@example.com",
            "password": "testpassword",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}


def test_create_user_existing_email(client: TestClient, session: Session) -> None:
    hashed_password = get_password_hash("testpassword")
    user = User(
        name="Test User",
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
    )
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Another User",
            "username": "anotheruser",
            "email": "test@example.com",
            "password": "testpassword",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}


def test_login(client: TestClient, session: Session) -> None:
    password = "testpassword"
    hashed_password = get_password_hash(password)
    user = User(
        name="Test User",
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
    )
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, session: Session) -> None:
    password = "testpassword"
    hashed_password = get_password_hash(password)
    user = User(
        name="Test User",
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
    )
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}


def test_login_non_existent_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "testpassword"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
