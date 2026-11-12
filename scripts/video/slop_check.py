#!/usr/bin/env python3
"""Klinkt dit script als AI of reclame? python3 slop_check.py <script.json>   (lijst met voice-overregels, of {"naam": [regels]})
Faalt (exit 1) bij reclamewoorden, uitroeptekens, gedachtestreepjes, drie-delige opsommingen in vast ritme, te lange zinnen of een script zonder één samentrekking."""
import json, re, sys
BAD = ['game-changer', 'game changer', 'revolution', 'unlock', 'seamless', 'effortless', 'elevate', 'supercharge', 'in today', 'cutting-edge', 'leverage', 'streamline', 'empower', 'next level', 'dive in', 'discover', 'journey', 'transform your', 'whether you', 'imagine', 'say goodbye', 'look no further', 'in a world']
def check(name, lines):
    fouten = []; waarsch = []
    tekst = ' '.join(lines).lower()
    for w in BAD:
        if w in tekst: fouten.append(f'reclamewoord: {w}')
    if '!' in ''.join(lines): fouten.append('uitroepteken (praat gewoon)')
    if re.search(r'[—–]| - ', ''.join(lines)): fouten.append('gedachtestreepje')
    for l in lines:
        if len(l.split()) > 16: fouten.append(f'zin te lang ({len(l.split())} woorden): {l[:40]}')
        parts = [p.strip() for p in re.split(r'[.,]', l) if p.strip()]
        if len(parts) == 3 and len({len(p.split()) for p in parts}) == 1 and len(parts[0].split()) <= 2: waarsch.append(f'drie gelijke blokjes in vast ritme (kan bewust, zoals een slogan): {l[:40]}')
    if not re.search(r"\b\w+'(s|ll|ve|re|m|d|t)\b|n't", tekst): fouten.append('geen enkele samentrekking (klinkt voorgelezen)')
    return fouten, waarsch
d = json.load(open(sys.argv[1])); d = d if isinstance(d, dict) else {'script': d}; bad = 0
for n, l in d.items():
    f, w = check(n, l); bad += bool(f); print(('GROEN ' if not f else 'ROOD  ') + n, *['\n   - ' + x for x in f], *['\n   ? ' + x for x in w])
sys.exit(1 if bad else 0)
