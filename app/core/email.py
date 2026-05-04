from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings
from app.core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def send_email(*, to: str, subject: str, html_body: str, text_body: str) -> None:
    """Send a multipart (text + HTML) email via SMTP.

    Raises RuntimeError if SMTP is not configured. Logs and re-raises
    aiosmtplib.SMTPException on send failure.
    """
    if not settings.SMTP_HOST:
        raise RuntimeError("SMTP not configured: set SMTP_HOST")

    message = EmailMessage()
    message["From"] = f'"{settings.SMTP_FROM_NAME}" <{settings.SMTP_FROM_EMAIL}>'
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_USE_TLS,
        )
    except aiosmtplib.SMTPException:
        logger.exception("Failed to send email to %s (subject=%s)", to, subject)
        raise
