#!/usr/bin/env python3
"""De lijst "Omnivaleur te bouwen" in Google Sheets lezen en bijwerken.

  lijst                                   toont alle regels
  voeg WAT STATUS PRIO KEER WIE OPMERKING nieuwe regel onderaan
  wijzig DEEL_VAN_WAT KOLOM WAARDE        KOLOM: status, prio, keer, wie, opmerking

Sleutel: ~/.omnivaleur/sheets-sleutel.json (of GOOGLE_SHEETS_SLEUTEL)."""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from leadgen_sheets import Sheets  # noqa: E402

BESTAND = "1tsuITAh4E5WQbb-OoEsiH7tBmU2Mno8Hm0utM5buXXQ"
TAB = "Te bouwen"
KOLOMMEN = {"wat": "A", "status": "B", "prio": "C", "keer": "D", "wie": "E", "opmerking": "F"}


def sheets() -> Sheets:
    pad = Path.home() / ".omnivaleur" / "sheets-sleutel.json"
    ruw = os.environ.get("GOOGLE_SHEETS_SLEUTEL") or (pad.read_text() if pad.exists() else "")
    return Sheets(ruw)


def main(a: list[str]) -> int:
    s = sheets()
    rijen = s.lees(BESTAND, f"{TAB}!A1:F500")
    if not a or a[0] == "lijst":
        for i, r in enumerate(rijen, 1):
            print(i, " | ".join(str(x)[:60] for x in r))
    elif a[0] == "voeg" and len(a) == 7:
        s.voeg_toe(BESTAND, TAB, [a[1:]])
        print("toegevoegd")
    elif a[0] == "wijzig" and len(a) == 4 and a[2] in KOLOMMEN:
        hits = [i for i, r in enumerate(rijen, 1) if i > 1 and r and a[1].lower() in str(r[0]).lower()]
        if len(hits) != 1:
            print(f"{len(hits)} regels gevonden voor '{a[1]}', maak het specifieker"); return 1
        k = KOLOMMEN[a[2]]
        s.schrijf(BESTAND, [{"range": f"{TAB}!{k}{hits[0]}", "values": [[a[3]]]}])
        print(f"regel {hits[0]}: {a[2]} = {a[3]}")
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
