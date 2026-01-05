from collections.abc import Generator
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, pool

from app.api.v1.auth import get_current_user
from app.core.db import get_session
from app.main import app
from app.models.plugin import Plugin, UserPlugin
from app.models.user import User
from app.services.plugin import PluginService, get_plugin_service

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module", name="engine")
def engine_fixture() -> Generator[Engine, None, None]:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine: Engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def get_session_override() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def setup_plugins_and_user(session: Session) -> dict[str, Any]:
    user = User(
        name="Test User", username="testuser123", email="test@example.com", hashed_password="fakehashedpassword"
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    plugin_a = Plugin(name="plugin_a", is_core=True, enabled=True)
    plugin_b = Plugin(name="plugin_b", is_core=True, enabled=True)
    configured_plugin_disabled = Plugin(name="configured_plugin_disabled", is_core=True, enabled=True)
    disabled_plugin = Plugin(name="disabled_plugin", is_core=True, enabled=False)

    session.add_all([plugin_a, plugin_b, configured_plugin_disabled, disabled_plugin])
    session.commit()
    session.refresh(plugin_a)
    session.refresh(plugin_b)
    session.refresh(configured_plugin_disabled)
    session.refresh(disabled_plugin)

    user_plugin_b = UserPlugin(
        user_id=cast(int, user.id), plugin_id=cast(int, plugin_b.id), enabled=True, config={"some config": "abc"}
    )
    session.add(user_plugin_b)
    session.commit()

    user_plugin_c = UserPlugin(
        user_id=cast(int, user.id),
        plugin_id=cast(int, configured_plugin_disabled.id),
        enabled=False,
        config={"some config": "abc"},
    )
    session.add(user_plugin_c)
    session.commit()

    return {"user": user, "plugins": [plugin_a, plugin_b, configured_plugin_disabled, disabled_plugin]}


@pytest.fixture
def override_dependencies(client: TestClient, setup_plugins_and_user: Any) -> Generator[TestClient, None, None]:
    app = cast(FastAPI, client.app)

    user: User = setup_plugins_and_user["user"]

    def get_user_override() -> User:
        return user

    def get_plugin_service_override() -> PluginService:
        return PluginService()

    app.dependency_overrides[get_current_user] = get_user_override
    app.dependency_overrides[get_plugin_service] = get_plugin_service_override

    yield client

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_plugin_service, None)


@pytest.fixture
def current_user(client: TestClient) -> Generator[User, None, None]:
    app = cast(FastAPI, client.app)
    user = User(
        id=1,
        name="Test User",
        username="testuser",
        email="test@example.com",
        hashed_password="fakehashedpassword",
    )

    def override_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_user
    yield user
    app.dependency_overrides.pop(get_current_user, None)
