#!/usr/bin/env python3
"""Welk format, hooktype en welke stem werkt het best? Leest docs/social-video-metingen.csv.
    python3 scripts/video/format_scores.py [csv] [--aantal 4]
Een rij is één plaatsing (video op één platform). Cijfers worden per platform vergeleken met de mediaan van dat platform,
dan gewogen: betalend en aanmeldingen het zwaarst, dan gedeeld en bewaard per 1000 weergaven, dan percentage bekeken, 3 seconden behoud,
kijktijd, reacties en volgers. Minder dan 3 plaatsingen = 'onzeker'. Geeft ook het advies voor de volgende week (60% winnaars, 40% proberen)."""
import csv, statistics, sys, collections
WEG = {'betalend': 5, 'aanmeldingen': 4, 'gedeeld_p1000': 3, 'bewaard_p1000': 3, 'pct_bekeken': 2, 'drie_sec_behoud_pct': 2, 'gem_kijktijd_s': 1, 'reacties_p1000': 1, 'volgers_p1000': 1}
FORMATS = ['STORY', 'DEMO', 'SKIT', 'ANALOGIE', 'UITLEG', 'DIRECT', 'MYTHE', 'POV', 'LIJST', 'VOORNA', 'ECHT']
def num(x):
    try: return float(str(x).replace(',', '.'))
    except ValueError: return None
def lees(pad):
    out = []
    for r in csv.DictReader(open(pad, encoding='utf-8')):
        if not r.get('platform') or num(r.get('weergaven')) in (None, 0): continue   # alleen echt geplaatst en gemeten
        v = num(r['weergaven']); m = {'betalend': num(r['betalend']), 'aanmeldingen': num(r['aanmeldingen']), 'pct_bekeken': num(r['pct_bekeken']), 'drie_sec_behoud_pct': num(r['drie_sec_behoud_pct']), 'gem_kijktijd_s': num(r['gem_kijktijd_s'])}
        for k, src in [('gedeeld_p1000', 'gedeeld'), ('bewaard_p1000', 'bewaard'), ('reacties_p1000', 'reacties'), ('volgers_p1000', 'volgers_erbij')]:
            x = num(r[src]); m[k] = None if x is None else x / v * 1000
        out.append((r, m))
    return out
def scores(rows):
    med = collections.defaultdict(dict)
    for k in WEG:
        for p in {r['platform'] for r, _ in rows}:
            xs = [m[k] for r, m in rows if r['platform'] == p and m[k] is not None]
            med[p][k] = statistics.median(xs) if xs else None
    res = []
    for r, m in rows:
        s = w = 0
        for k, wt in WEG.items():
            x, md = m[k], med[r['platform']][k]
            if x is None or md is None: continue
            rel = min(3.0, x / md) if md > 0 else (1.0 if x == 0 else 3.0)
            s += wt * rel; w += wt
        if w: res.append((r, s / w))
    return res
def groep(res, key):
    g = collections.defaultdict(list)
    for r, s in res: g[r[key]].append(s)
    return sorted(((k, statistics.mean(v), len(v)) for k, v in g.items()), key=lambda t: -t[1])
def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; pad = a[0] if a else 'docs/social-video-metingen.csv'
    n = int(sys.argv[sys.argv.index('--aantal') + 1]) if '--aantal' in sys.argv else 4
    rows = lees(pad); res = scores(rows)
    print(f'{len(rows)} gemeten plaatsingen in {pad}')
    if not res: print('Nog geen gemeten plaatsingen: verdeel de eerste weken gelijk over de formats (alles is proberen).'); winners = []
    for key in ('format', 'hook_type', 'voice'):
        if res: print(f'\nPer {key}:')
        for k, s, c in groep(res, key): print(f'  {k:22s} score {s:4.2f}  n={c} {"(onzeker, minder dan 3)" if c < 3 else ""}')
    winners = [k for k, s, c in groep(res, 'format') if c >= 3][:2] if res else []
    seen = collections.Counter(r['format'] for r, _ in res)
    nieuw = sorted(FORMATS, key=lambda f: (seen[f], FORMATS.index(f)))
    ex = round(n * 0.6) if winners else 0
    plan = [winners[i % len(winners)] + ' (winnaar, andere hook of stem)' for i in range(ex)] if winners else []
    for f in nieuw:
        if len(plan) >= n: break
        plan.append(f + ' (proberen, ' + str(seen[f]) + ' metingen)')
    print(f'\nAdvies voor volgende week ({n} video\'s):'); [print('  -', p) for p in plan]
if __name__ == '__main__': main()
