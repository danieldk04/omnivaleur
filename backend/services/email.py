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


def send_email(subject: str, body: str, to: str | None = None, reply_to: str | None = None) -> bool:
    if not _is_configured():
        logger.info(f"SMTP niet geconfigureerd — melding overgeslagen: {subject}")
        return False

    recipient = to or settings.owner_email
    # utf-8: zonder deze charset weigert Python elke tekst met een euroteken erin.
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = recipient
    if reply_to:
        # De mail vertrekt vanaf de mailbox die toevallig is ingesteld; antwoorden
        # moeten bij het adres in de handtekening uitkomen.
        msg["Reply-To"] = reply_to

    try:
        # Poort 465 is versleuteld vanaf de eerste byte (o.a. Hostinger); 587
        # begint onversleuteld en schakelt over met STARTTLS (o.a. Gmail). Op de
        # verkeerde manier verbinden loopt vast op een time-out i.p.v. een
        # duidelijke fout, dus wordt hier op de poort gekozen.
        if int(settings.smtp_port) == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            server.starttls()
        with server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [recipient], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"E-mailmelding mislukt ({subject}): {e}")
        return False


def notify_content_evaluation(summary: dict, results: list[dict]) -> None:
    """Wekelijkse samenvatting van de blog-evaluator: wat is herschreven en wat staat
    er in de rij. Zelfde best-effort-contract als de rest van deze module."""
    site_url = "https://omnivaleur.com"
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    lines = [
        f"{summary['evaluated']} gepubliceerde pagina's beoordeeld op Search Console-data.",
        "",
        "Verdeling: " + (", ".join(f"{v}: {n}" for v, n in sorted(counts.items())) or "geen"),
        "",
    ]

    if summary["refreshed"]:
        lines.append("HERSCHREVEN deze ronde:")
        lines += [f"- {site_url}{r['url_path']} — {r['reason']}" for r in summary["refreshed"]]
    else:
        lines.append("Deze ronde is er niets herschreven.")

    queue = [c for c in summary["candidates"] if c["intent_key"] not in {r["intent_key"] for r in summary["refreshed"]}]
    if queue:
        lines += ["", "In de wachtrij (hoogste prioriteit eerst):"]
        lines += [
            f"- {c['url_path']} — positie {c['position']:.1f}, {c['impressions']} impressies ({c['verdict']})"
            for c in queue[:10]
        ]

    send_email(subject="[Omnivaleur blog] Wekelijkse content-evaluatie", body="\n".join(lines))


def notify_published(keyword: str, url_path: str, action: str, schema_warnings: list[str] | None = None) -> None:
    site_url = "https://omnivaleur.com"
    lines = [
        f"Nieuw artikel {action}: {keyword}",
        f"{site_url}{url_path}",
    ]
    if schema_warnings:
        lines.append("")
        lines.append("Let op — structured-data waarschuwingen (controleer handmatig):")
        lines.extend(f"- {w}" for w in schema_warnings)
    send_email(subject=f"[Omnivaleur blog] {action}: {keyword}", body="\n".join(lines))
