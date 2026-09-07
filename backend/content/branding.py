"""Merk- en kanaalgegevens, los van de weblaag.

Waarom een apart bestandje: de content-pijplijn (`backend/content/pipeline.py`,
gedraaid door de dagelijkse GitHub Actions-cron met alleen `requirements-content.txt`)
heeft deze lijst nodig voor het `sameAs`-veld in de JSON-LD. Stond hij in
`backend/api/content.py`, dan sleepte één import de hele FastAPI-stack mee — die
in de cron niet geïnstalleerd is. Sinds 30-08-2026 liet dat de blogpijplijn elke
dag stil crashen op de laatste stap (opslaan). `backend/api/content.py`
her-exporteert deze namen, dus voor de rest van de codebase verandert er niets.
"""

# ── De vaste links per kanaal ─────────────────────────────────────────────
# Eén plek waar staat welke link waar hoort. Waarom dit niet "gewoon even zelf
# in elkaar zetten" is: zodra dezelfde TikTok-link een keer `tiktok` en een
# keer `TikTok` of `tik-tok` als bron krijgt, telt Google Analytics dat als
# twee kanalen en klopt geen enkel totaal meer. Vandaar drie afspraken:
#
#   utm_source    het kanaal, kleine letters:  tiktok / instagram / youtube /
#                 pinterest / threads / koude-mail
#   utm_medium    alleen `social` of `email`. Dit zijn de woorden die Analytics
#                 zelf herkent; iets anders (`cold_email`) belandt in de bak
#                 "niet toegewezen" en is dan onvindbaar in de rapporten.
#   utm_campaign  waar de link staat: bio-en / bio-nl / marktplaats-nl.
#                 Nederlands en Engels hebben dezelfde bron (instagram), dus
#                 dit veld is wat de twee accounts uit elkaar houdt.
#
# utm_content blijft vrij voor losse posts — daar is de linkbouwer onderaan het
# dashboard voor. Deze tabel gaat alleen over de vaste links in de profielen.
KANAAL_LINKS: list[dict] = [
    {"kanaal": "TikTok", "taal": "EN", "profiel": "https://www.tiktok.com/@omnivaleur",
     "pad": "/", "source": "tiktok", "medium": "social", "campagne": "bio-en",
     "kort": "tt"},
    {"kanaal": "Instagram", "taal": "EN", "profiel": "https://www.instagram.com/omnivaleur/",
     "pad": "/", "source": "instagram", "medium": "social", "campagne": "bio-en",
     "kort": "ig"},
    {"kanaal": "YouTube", "taal": "EN", "profiel": "https://www.youtube.com/@Omnivaleur",
     "pad": "/", "source": "youtube", "medium": "social", "campagne": "bio-en",
     "kort": "yt"},
    {"kanaal": "Pinterest", "taal": "EN", "profiel": "https://nl.pinterest.com/Omnivaleur/",
     "pad": "/", "source": "pinterest", "medium": "social", "campagne": "bio-en",
     "kort": "pin"},
    {"kanaal": "Threads", "taal": "EN", "profiel": "https://www.threads.com/@omnivaleur",
     "pad": "/", "source": "threads", "medium": "social", "campagne": "bio-en",
     "kort": "th"},
    {"kanaal": "Instagram", "taal": "NL", "profiel": "https://www.instagram.com/omnivaleurnl/",
     "pad": "/", "source": "instagram", "medium": "social", "campagne": "bio-nl",
     "kort": "ig-nl"},
    {"kanaal": "TikTok", "taal": "NL", "profiel": "https://www.tiktok.com/@omni.valeur",
     "pad": "/", "source": "tiktok", "medium": "social", "campagne": "bio-nl",
     "kort": "tt-nl"},
    {"kanaal": "YouTube", "taal": "NL", "profiel": "https://www.youtube.com/@OmnivaleurNL",
     "pad": "/", "source": "youtube", "medium": "social", "campagne": "bio-nl",
     "kort": "yt-nl"},
]

# ── Merkkoppeling: welke profielen zijn aantoonbaar hetzelfde merk ────────
# Google leidde "Omnivaleur" niet af als merknaam — hij stelde "omnivore" voor en
# corrigeerde de zoekopdracht zelfs stilzwijgend — terwijl de socials en de Web
# Store-vermelding wél bovenaan stonden. Oorzaak: de site en die profielen stonden
# volledig los van elkaar. Er was geen enkele machineleesbare uitspraak dat ze bij
# hetzelfde bedrijf horen, en de homepage linkte er ook nergens naartoe.
#
# sameAs is precies die uitspraak, en het is de manier waarop een zoekmachine een
# merkentiteit opbouwt. Deze lijst is afgeleid van KANAAL_LINKS (waar de profielen
# toch al staan) zodat een kanaal erbij automatisch meeloopt; hij mag daar dus
# nooit los van gaan leven. Een test bewaakt dat de statische homepage dezelfde
# verzameling draagt.
WEBSTORE_URL = (
    "https://chromewebstore.google.com/detail/omnivaleur/"
    "gfaogapbhaacfbpdppdcmnkjndlphleh"
)


def merk_profielen() -> list[str]:
    """Alle openbare profielen van het merk, ontdubbeld en in vaste volgorde.
    Vaste volgorde omdat een wisselende sameAs bij elke deploy een gewijzigde
    pagina lijkt zonder dat er iets veranderd is."""
    uniek: list[str] = []
    for kanaal in KANAAL_LINKS:
        profiel = kanaal.get("profiel")
        if profiel and profiel not in uniek:
            uniek.append(profiel)
    if WEBSTORE_URL not in uniek:
        uniek.append(WEBSTORE_URL)
    return uniek
