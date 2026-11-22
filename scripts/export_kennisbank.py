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

# Geheugen van Daniels andere mappen (o.a. Downloads: daar schrijft de nachtelijke
# Dreaming-taak naartoe). Dezelfde regel: wat alleen op één account staat, bestaat voor
# de ander niet. Eigen bestand, zodat de omnivaleur-kennisbank leesbaar blijft.
OUT2 = pathlib.Path(__file__).resolve().parent.parent / "docs/kennisbank-overig.md"
PROJ = pathlib.Path.home() / ".claude/projects"
SKIP = {"-Users-Danie-Documents-omnivaleur"}
SECRET = re.compile(r"sk-[A-Za-z0-9]{10,}|sb_secret_\w{6,}|eyJ[A-Za-z0-9]{20,}|AIza[\w-]{20,}|whsec_|rk_live|sk_live")

def overig() -> None:
    parts = ["# Kennisbank overig: geheugen uit Daniels andere mappen\n\nAutomatisch gemaakt door `scripts/export_kennisbank.py`. Per kopje staat de map waaruit de les komt. Bevat Downloads (hier schrijft de nachtelijke Dreaming-taak), Documents, crosslist-eu en de andere projecten.\n\n---\n"]
    n = 0
    for d in sorted(PROJ.glob("*/memory")):
        proj = d.parent.name
        if proj in SKIP or "scratch" in proj or "worktrees" in proj:
            continue
        fs = [f for f in glob.glob(str(d / "*.md")) if not f.endswith("MEMORY.md")]
        fs.sort(key=os.path.getmtime, reverse=True)
        for f in fs:
            txt = open(f).read()
            if SECRET.search(txt):
                continue
            date = datetime.date.fromtimestamp(os.path.getmtime(f)).strftime("%d-%m-%Y")
            parts.append(f"## {proj} / {os.path.basename(f)[:-3]}\n\n*{date}*\n\n{re.sub(r'^---\n.*?\n---\n', '', txt, count=1, flags=re.S).strip()}\n\n---\n")
            n += 1
    OUT2.write_text("\n".join(parts))
    print(f"{n} overige lessen naar {OUT2}")

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
    overig()

if __name__ == "__main__":
    main()
