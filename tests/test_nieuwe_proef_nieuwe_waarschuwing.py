"""Wie een tweede proefperiode krijgt, moet ook een tweede waarschuwing krijgen.

WAAROM DIT ER IS (08-09-2026)

`send_trial_reminders` sloeg iedereen over bij wie `trial_reminder_sent_at` al
gevuld was. Dat werkt zolang niemand ooit een tweede proef krijgt. Zodra dat wel
gebeurt — de terughaalcampagne, een handmatige verlenging, een tweede kans na een
mislukte betaling — staat het vinkje nog op de datum van de vórige proef en
krijgt die persoon geen enkele mail meer. Hij wordt op de dag zelf buitengesloten
zonder dat er ooit iets is gezegd.

GEMETEN, NIET AANGENOMEN (08-09-2026, op de echte abonnementen): van de 29
mensen in proef zouden er elf op 13 september zonder één waarschuwingsmail
buitengesloten zijn, acht van hen ook zonder de laatste herinnering. Onder hen
info@steentjesmeester.nl, davethefirst@hotmail.com en info@retrogameking.com.

Een waarschuwing telt daarom alleen nog als hij BIJ DEZE proef hoort: hij valt
altijd binnen de laatste REMINDER_DAYS_BEFORE dagen ervoor. Staat hij verder
terug, dan ging hij over een eerdere ronde.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.billing import (REMINDER_DAYS_BEFORE,  # noqa: E402
                                      _nog_niet_gewaarschuwd)

NU = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def _abo(eindigt_over_dagen, gewaarschuwd_op=None):
    einde = NU + timedelta(days=eindigt_over_dagen)
    return {
        "id": "abo-1",
        "user_id": "u1",
        "trial_ends_at": einde.isoformat(),
        "trial_reminder_sent_at": gewaarschuwd_op.isoformat() if gewaarschuwd_op else None,
    }


def test_wie_nooit_iets_kreeg_krijgt_de_mail():
    assert _nog_niet_gewaarschuwd([_abo(1)], "trial_reminder_sent_at")


def test_waarschuwing_van_een_eerdere_proef_telt_niet_mee():
    """Precies het geval van steentjesmeester: mail op 3 september, proef tot 13 september."""
    oud = _abo(5, gewaarschuwd_op=NU - timedelta(days=5))
    assert _nog_niet_gewaarschuwd([oud], "trial_reminder_sent_at") == [oud]


def test_waarschuwing_van_deze_proef_wordt_niet_herhaald():
    """Ted Conroy: proef tot morgen, mail gisteren. Geen tweede mail."""
    net = _abo(1, gewaarschuwd_op=NU - timedelta(days=1))
    assert _nog_niet_gewaarschuwd([net], "trial_reminder_sent_at") == []


def test_de_grens_ligt_op_reminder_days_before():
    einde = NU + timedelta(days=1)
    net_binnen = {"id": "a", "user_id": "u", "trial_ends_at": einde.isoformat(),
                  "trial_reminder_sent_at": (einde - timedelta(days=REMINDER_DAYS_BEFORE)
                                             + timedelta(hours=1)).isoformat()}
    net_buiten = {"id": "b", "user_id": "u", "trial_ends_at": einde.isoformat(),
                  "trial_reminder_sent_at": (einde - timedelta(days=REMINDER_DAYS_BEFORE)
                                             - timedelta(hours=1)).isoformat()}
    uit = [r["id"] for r in _nog_niet_gewaarschuwd([net_binnen, net_buiten],
                                                   "trial_reminder_sent_at")]
    assert uit == ["b"]


def test_lege_lijst_valt_niet_om():
    assert _nog_niet_gewaarschuwd(None, "trial_reminder_sent_at") == []
