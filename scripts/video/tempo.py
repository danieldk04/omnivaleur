#!/usr/bin/env python3
"""python tempo.py <naam> <factor>: versnelt vo/<naam>.mp3 (toonhoogte blijft) en schaalt de woordtijden. Bewaart het origineel als .raw.mp3 / .raw.words.json en gaat altijd daarvan uit."""
import sys, json, shutil, subprocess, os
n, f = sys.argv[1], float(sys.argv[2])
if not os.path.exists(f'vo/{n}.raw.mp3'):
    shutil.copy(f'vo/{n}.mp3', f'vo/{n}.raw.mp3'); shutil.copy(f'vo/{n}.words.json', f'vo/{n}.raw.words.json')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', f'vo/{n}.raw.mp3', '-filter:a', f'atempo={f}', '-b:a', '64k', f'vo/{n}.mp3'], check=True)
w = json.load(open(f'vo/{n}.raw.words.json'))
for x in w: x['s'] /= f; x['e'] /= f
json.dump(w, open(f'vo/{n}.words.json', 'w')); print(n, 'tempo', f, 'einde', round(w[-1]['e'], 2))
