"""
Best-effort e-mailmeldingen voor de content-pijplijn. Non-blocking by design: een
publicatie mag nooit wachten op of mislukken door een e-mailprobleem, dus elke
fout hier wordt gelogd en verder genegeerd i.p.v. gepropageerd.
"""
import logging
import smtplib
import socket
from contextlib import contextmanager
from email.mime.text import MIMEText

from backend.config import settings

logger = logging.getLogger(__name__)


def _send_via_resend(subject: str, body: str, recipient: str, reply_to: str | None,
                     html: str | None = None) -> None:
    """Versturen over https, de enige poort die Railway wél doorlaat."""
    import httpx

    sender = settings.resend_from or settings.smtp_from_email
    # Een kale afzender zonder naam leest als een mailinglijst en helpt Gmail bij
    # het besluit om de mail in Promoties te leggen. Een persoonsnaam ervoor
    # scheelt daar merkbaar in, en klopt ook: deze mails komen van Daniel.
    if sender and "<" not in sender and settings.email_from_name:
        sender = f"{settings.email_from_name} <{sender}>"
    payload = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "text": body,
    }
    # De platte tekst blijft altijd meegaan: mailprogramma's die geen opmaak
    # tonen (of hem uitzetten) vallen daarop terug, en spamfilters rekenen een
    # html-only mail aan.
    if html:
        payload["html"] = html
    if reply_to:
        payload["reply_to"] = reply_to

    # Gmail verwacht sinds 2024 van elke afzender die meer dan een handvol mails
    # stuurt een afmeldmogelijkheid in de kop van het bericht. Ontbreekt die, dan
    # gaat de mail eerder naar spam, ook als hij verder niets fout doet.
    unsubscribe = reply_to or settings.reply_to_email
    if unsubscribe:
        payload["headers"] = {
            "List-Unsubscribe": f"<mailto:{unsubscribe}?subject=unsubscribe>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json=payload,
        timeout=20,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Resend weigerde de mail ({r.status_code}): {r.text[:300]}")


def _is_configured() -> bool:
    return bool(settings.resend_api_key) or bool(settings.smtp_host and settings.smtp_user and settings.smtp_password and settings.smtp_from_email)


def send_email_checked(subject: str, body: str, to: str | None = None, reply_to: str | None = None) -> None:
    """Zelfde als send_email, maar laat de fout staan. Gebruikt door de testknop,
    zodat op het scherm komt te staan wát de mailserver precies weigerde in
    plaats van alleen 'het lukte niet'."""
    recipient_pre = to or settings.owner_email
    if settings.resend_api_key:
        if not (settings.resend_from or settings.smtp_from_email):
            raise RuntimeError("RESEND_FROM ontbreekt op Railway (het afzenderadres)")
        _send_via_resend(subject, body, recipient_pre, reply_to)
        return

    missing = [n for n, v in (
        ("SMTP_HOST", settings.smtp_host),
        ("SMTP_USER", settings.smtp_user),
        ("SMTP_PASSWORD", settings.smtp_password),
        ("SMTP_FROM_EMAIL", settings.smtp_from_email),
    ) if not v]
    if missing:
        raise RuntimeError("Deze instellingen ontbreken op Railway: " + ", ".join(missing))

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

    ports = [int(settings.smtp_port)]
    # Wordt de ingestelde poort niet geaccepteerd, dan is de andere gangbare
    # poort het proberen waard: veel mailservers luisteren op allebei, en welke
    # van de twee het hostingplatform doorlaat is niet te voorspellen.
    for alt in (465, 587):
        if alt not in ports:
            ports.append(alt)

    last_error: Exception | None = None
    for port in ports:
        try:
            _deliver(port, recipient, msg)
            if port != int(settings.smtp_port):
                logger.warning(f"SMTP: poort {settings.smtp_port} werkte niet, verstuurd via {port}")
            return
        except (OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as e:
            # Verbindingsprobleem: andere poort proberen heeft zin.
            last_error = e
            continue
        except Exception:
            # Afgewezen wachtwoord of geweigerde afzender: dan helpt een andere
            # poort niet, en moet de echte melding meteen naar boven.
            raise
    raise last_error  # type: ignore[misc]


def _deliver(port: int, recipient: str, msg) -> None:
    """Eén verzendpoging op één poort.

    Poort 465 is versleuteld vanaf de eerste byte (o.a. Hostinger); 587 begint
    onversleuteld en schakelt over met STARTTLS (o.a. Gmail).

    De verbinding wordt bewust over IPv4 gelegd. Railway-containers hebben wel
    een IPv6-adres maar geen route naar buiten over IPv6; Python koos dat adres
    als eerste en gaf dan "Network is unreachable" — een fout die eruitziet als
    een geblokkeerde poort maar het niet is.
    """
    host = settings.smtp_host
    with _ipv4_only():
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.starttls()
        with server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [recipient], msg.as_string())


@contextmanager
def _ipv4_only():
    """Laat naamopzoekingen tijdelijk alleen IPv4-adressen teruggeven."""
    original = socket.getaddrinfo

    def ipv4(host, port, family=0, *args, **kwargs):
        return original(host, port, socket.AF_INET, *args, **kwargs)

    socket.getaddrinfo = ipv4
    try:
        yield
    finally:
        socket.getaddrinfo = original


def send_email(subject: str, body: str, to: str | None = None, reply_to: str | None = None) -> bool:
    """Best-effort: een mislukte mail mag nooit een publicatie of een geplande
    taak omvergooien, dus hier wordt de fout gelogd en verder genegeerd."""
    try:
        send_email_checked(subject, body, to=to, reply_to=reply_to)
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
