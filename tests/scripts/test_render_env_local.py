"""Tests for scripts/render_env_local.py, the dev VM's .env.local renderer."""

import json

import pytest

from scripts.render_env_local import main, render

REQUIRED_SECRETS = {
    "ENV_SECRET_KEY": "secret",
    "ENV_ENCRYPTION_KEY": "fernet-key=",
    "ENV_POSTGRES_PASSWORD": "pg-password",
    "ENV_DATABASE_URL": "postgresql://sparkth:pg-password@db:5432/sparkth",
    "ENV_ANALYTICS_DATABASE_URL": "postgresql://sparkth:pg-password@db:5432/sparkth_analytics",
    "ENV_REDIS_URL": "redis://redis:6379",
}


def test_render_writes_only_prefixed_entries_with_the_prefix_stripped() -> None:
    secrets = {**REQUIRED_SECRETS, "github_token": "ghs_x", "CLAUDE_CODE_OAUTH_TOKEN": "oauth"}
    variables = {"ENV_TRUSTED_PROXY_HOPS": "1", "DEV_DEPLOY_DIR": "/app/sparkth"}

    lines = render(secrets, variables).splitlines()

    assert lines == [
        "ANALYTICS_DATABASE_URL='postgresql://sparkth:pg-password@db:5432/sparkth_analytics'",
        "DATABASE_URL='postgresql://sparkth:pg-password@db:5432/sparkth'",
        "ENCRYPTION_KEY='fernet-key='",
        "POSTGRES_PASSWORD='pg-password'",
        "REDIS_URL='redis://redis:6379'",
        "SECRET_KEY='secret'",
        "TRUSTED_PROXY_HOPS='1'",
    ]


def test_render_rejects_a_missing_required_entry() -> None:
    secrets = {name: value for name, value in REQUIRED_SECRETS.items() if name != "ENV_ENCRYPTION_KEY"}

    with pytest.raises(ValueError) as excinfo:
        render(secrets, {})

    assert "ENCRYPTION_KEY" in str(excinfo.value)


def test_render_rejects_a_name_set_as_both_secret_and_variable() -> None:
    with pytest.raises(ValueError) as excinfo:
        render(REQUIRED_SECRETS, {"ENV_REDIS_URL": "redis://elsewhere:6379"})

    assert "REDIS_URL" in str(excinfo.value)


@pytest.mark.parametrize("value", ["it's", "line one\nline two"])
def test_render_rejects_a_value_it_cannot_quote_without_echoing_it(value: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        render({**REQUIRED_SECRETS, "ENV_SLACK_CLIENT_SECRET": value}, {})

    assert "SLACK_CLIENT_SECRET" in str(excinfo.value)
    assert value not in str(excinfo.value)


def test_main_prints_the_rendered_file(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("SECRETS_JSON", json.dumps(REQUIRED_SECRETS))
    monkeypatch.setenv("VARS_JSON", json.dumps({}))

    main()

    assert capsys.readouterr().out == render(REQUIRED_SECRETS, {})


def test_main_exits_non_zero_on_an_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETS_JSON", json.dumps({}))
    monkeypatch.setenv("VARS_JSON", json.dumps({}))

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code != 0
