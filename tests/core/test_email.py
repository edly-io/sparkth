from email.message import EmailMessage
from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest

from app.core import email as email_module
from app.core.email import send_email


@pytest.fixture
def smtp_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_module.settings, "SMTP_HOST", "smtp.test.local")
    monkeypatch.setattr(email_module.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_module.settings, "SMTP_USERNAME", "user")
    monkeypatch.setattr(email_module.settings, "SMTP_PASSWORD", "pass")
    monkeypatch.setattr(email_module.settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(email_module.settings, "SMTP_FROM_EMAIL", "no-reply@test.local")
    monkeypatch.setattr(email_module.settings, "SMTP_FROM_NAME", "Test")


class TestSendEmail:
    async def test_raises_when_smtp_host_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(email_module.settings, "SMTP_HOST", "")
        with pytest.raises(RuntimeError, match="SMTP not configured"):
            await send_email(to="a@b.com", subject="x", html_body="<p>x</p>", text_body="x")

    async def test_sends_message_with_text_and_html_parts(self, smtp_settings: None) -> None:
        with patch("app.core.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(
                to="alice@example.com",
                subject="Hello",
                html_body="<p>Hello</p>",
                text_body="Hello",
            )

        mock_send.assert_called_once()
        message: EmailMessage = mock_send.call_args.args[0]
        assert message["To"] == "alice@example.com"
        assert message["Subject"] == "Hello"
        # Python's email lib normalizes redundant quotes around simple display names
        assert message["From"] == "Test <no-reply@test.local>"
        # Walking the multipart structure: there should be a text/plain and a text/html part
        types = {part.get_content_type() for part in message.walk() if not part.is_multipart()}
        assert "text/plain" in types
        assert "text/html" in types

    async def test_passes_smtp_connection_args(self, smtp_settings: None) -> None:
        with patch("app.core.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            await send_email(to="a@b.com", subject="s", html_body="<p>h</p>", text_body="h")

        kwargs = mock_send.call_args.kwargs
        assert kwargs["hostname"] == "smtp.test.local"
        assert kwargs["port"] == 587
        assert kwargs["username"] == "user"
        assert kwargs["password"] == "pass"
        assert kwargs["start_tls"] is True

    async def test_logs_and_reraises_on_smtp_exception(self, smtp_settings: None) -> None:
        with patch(
            "app.core.email.aiosmtplib.send",
            new_callable=AsyncMock,
            side_effect=aiosmtplib.SMTPException("boom"),
        ):
            with pytest.raises(aiosmtplib.SMTPException, match="boom"):
                await send_email(to="a@b.com", subject="s", html_body="<p>h</p>", text_body="h")
