"""Tests for ``send_password_reset_email``: the link, its expiry, escaping and SMTP failures."""

from unittest.mock import AsyncMock, MagicMock

import aiosmtplib
import pytest

from sparkth.services.account import ResetEmail
from sparkth.services.account import password_reset as svc


@pytest.fixture
def send_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    monkeypatch.setattr(svc.settings, "FRONTEND_BASE_URL", "https://app.test")
    mock = AsyncMock()
    monkeypatch.setattr(svc, "send_email", mock)
    return mock


async def test_sends_the_reset_link_and_its_expiry(send_mock: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc.settings, "PASSWORD_RESET_TOKEN_TTL_MINUTES", 45)

    await svc.send_password_reset_email(ResetEmail(to="alice@example.com", name="Alice", raw_token="abc123"))

    assert send_mock.await_args is not None
    kwargs = send_mock.await_args.kwargs
    assert kwargs["to"] == "alice@example.com"
    assert "Alice" in kwargs["text_body"]
    # Trailing slash matches the statically exported frontend, which would otherwise
    # redirect and drop the query string.
    assert "https://app.test/reset-password/?token=abc123" in kwargs["text_body"]
    assert "https://app.test/reset-password/?token=abc123" in kwargs["html_body"]
    assert "45" in kwargs["text_body"]


async def test_strips_a_trailing_slash_from_the_frontend_url(
    send_mock: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(svc.settings, "FRONTEND_BASE_URL", "https://app.test/")

    await svc.send_password_reset_email(ResetEmail(to="a@b.com", name="A", raw_token="t"))

    assert send_mock.await_args is not None
    assert "https://app.test/reset-password/?token=t" in send_mock.await_args.kwargs["text_body"]


async def test_escapes_the_name_in_the_html_body(send_mock: AsyncMock) -> None:
    await svc.send_password_reset_email(ResetEmail(to="e@example.com", name="<script>x</script>", raw_token="t"))

    assert send_mock.await_args is not None
    html_body = send_mock.await_args.kwargs["html_body"]
    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body


@pytest.mark.parametrize("error", [RuntimeError("SMTP not configured"), aiosmtplib.SMTPException("refused")])
async def test_logs_and_absorbs_send_failures(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    monkeypatch.setattr(svc, "send_email", AsyncMock(side_effect=error))
    log_mock = MagicMock()
    monkeypatch.setattr(svc, "logger", log_mock)

    await svc.send_password_reset_email(ResetEmail(to="x@example.com", name="X", raw_token="t"))

    log_mock.exception.assert_called_once()
    assert "x@example.com" in log_mock.exception.call_args.args
