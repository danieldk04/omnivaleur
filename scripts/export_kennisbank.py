#!/usr/bin/env python3
"""Bundelt de losse geheugenbestanden tot docs/kennisbank.md.

De geheugenmap hangt aan één Claude-account. Een tweede ontwikkelaar ziet die
niet. Dit script maakt er één bestand van dat wél in de repo staat.
"""
import os, re, glob, datetime, pathlib

MEM = pathlib.Path.home() / ".claude/projects/-Users-Danie-Documents-omnivaleur/memory"
OUT = pathlib.Path(__file__).resolve().parent.parent / "docs/kennisbank.md"

HEADER = """# Kennisbank — wat eerdere sessies hebben geleerd

Dit bestand staat in de repo en reist dus mee naar elk account en elke machine.
De losse geheugenbestanden onder `~/.claude/projects/.../memory/` zijn **per
account** en voor een tweede ontwikkelaar onzichtbaar; dit is de overdraagbare
kopie daarvan.

Lees dit samen met [team-notes.md](team-notes.md): team-notes is het dagboek
(wat er wanneer gebeurde), deze kennisbank is de les (wat je voortaan moet weten
om dezelfde fout niet nog eens te maken).

Nieuwste bovenaan. De datum is wanneer de les is vastgelegd of bijgewerkt.
Verwijzingen tussen lessen staan als "zie: naam-van-de-les" — zoek op die naam
in dit bestand.

Bijwerken: `python3 scripts/export_kennisbank.py` en het resultaat committen.

---
"""

def main() -> None:
    files = [f for f in glob.glob(str(MEM / "*.md")) if not f.endswith("MEMORY.md")]
    files.sort(key=os.path.getmtime, reverse=True)
    parts = [HEADER]
    for f in files:
        txt = open(f).read()
        body, desc = txt, ""
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", txt, re.S)
        if m:
            body = m.group(2)
            d = re.search(r"^description:\s*(.*)$", m.group(1), re.M)
            if d:
                desc = d.group(1).strip()
        body = re.sub(r"\[\[([^\]]+)\]\]", r'"\1"', body)
        name = os.path.basename(f)[:-3]
        date = datetime.date.fromtimestamp(os.path.getmtime(f)).strftime("%d-%m-%Y")
        parts.append(f"## {name}\n\n*{date} — {desc}*\n\n{body.strip()}\n\n---\n")
    OUT.write_text("\n".join(parts))
    print(f"{len(files)} lessen geschreven naar {OUT}")

if __name__ == "__main__":
    main()
