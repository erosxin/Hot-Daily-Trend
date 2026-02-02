import logging
import resend
from src.config import settings

logger = logging.getLogger(__name__)


def send_daily_email(subject: str, html_body: str) -> None:
    if not settings.RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY is missing")

    if not settings.SENDER_EMAIL or not settings.RECIPIENT_EMAIL:
        raise ValueError("SENDER_EMAIL or RECIPIENT_EMAIL is missing")

    resend.api_key = settings.RESEND_API_KEY

    recipients = [email.strip() for email in settings.RECIPIENT_EMAIL.split(",") if email.strip()]
    if not recipients:
        raise ValueError("RECIPIENT_EMAIL is missing or empty")

    payload = {
        "from": settings.SENDER_EMAIL,
        "to": recipients,
        "subject": subject,
        "html": html_body,
    }

    logger.info("Sending email via Resend...")
    resend.Emails.send(payload)
    logger.info("Email sent.")
