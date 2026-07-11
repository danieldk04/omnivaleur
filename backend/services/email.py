"""
Best-effort e-mailmeldingen voor de content-pijplijn. Non-blocking by design: een
publicatie mag nooit wachten op of mislukken door een e-mailprobleem, dus elke
fout hier wordt gelogd en verder genegeerd i.p.v. gepropageerd.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from backend.config import settings

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password and settings.smtp_from_email)


def send_email(subject: str, body: str, to: str | None = None) -> bool:
    if not _is_configured():
        logger.info(f"SMTP niet geconfigureerd — melding overgeslagen: {subject}")
        return False

    recipient = to or settings.owner_email
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = recipient

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [recipient], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"E-mailmelding mislukt ({subject}): {e}")
        return False


def notify_published(keyword: str, url_path: str, action: str, schema_warnings: list[str] | None = None) -> None:
    site_url = "https://crosslisteu.com"
    lines = [
        f"Nieuw artikel {action}: {keyword}",
        f"{site_url}{url_path}",
    ]
    if schema_warnings:
        lines.append("")
        lines.append("Let op — structured-data waarschuwingen (controleer handmatig):")
        lines.extend(f"- {w}" for w in schema_warnings)
    send_email(subject=f"[ListHub blog] {action}: {keyword}", body="\n".join(lines))
