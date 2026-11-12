#!/usr/bin/env python3
"""Zet losse stemregels (audio2/line_NN.wav) aan elkaar tot een natuurlijker voice-over.
python assemble.py <werkmap> <scripts.json> <nr>   (draai met ~/earshot/.venv/bin/python)
Per regel: stilte aan de randen weg, zachte hoogdoorlaat, kleine wisselende tempo-en-volume-verschillen; tussen de regels wisselende pauzes
(korter na een komma of vraag, langer na een punt) in plaats van een vaste rekenmachinepauze. Schrijft audio/vo.wav, audio/lines.json,
src/cap.js (bijschriften uit Parakeet-woordtiming plus LINES voor de montage)."""
import json, os, re, subprocess, sys, numpy as np, soundfile as sf, scipy.signal as ss
work, sc, nr = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
L = sc[nr]; rng = np.random.default_rng(int(nr) * 17); KIT = os.path.expanduser('~/claude-animation-skills/kit')
out, info, t, SR = [], [], 0.0, 24000
hp = ss.butter(2, 75 / (SR / 2), 'high')
for i, s in enumerate(L):
    y, sr = sf.read(f'{work}/audio2/line_{i:02d}.wav'); y = y if y.ndim == 1 else y[:, 0]
    if sr != SR: y = ss.resample_poly(y, SR, sr)
    y = ss.lfilter(*hp, y)
    act = np.where(np.abs(y) > 0.02 * np.abs(y).max())[0]; y = y[max(0, act[0] - int(0.03 * SR)): act[-1] + int(0.06 * SR)]
    y = y * (0.9 + 0.2 * rng.random()) * (0.85 / max(np.abs(y).max(), 1e-6))
    gap = 0.0 if i == 0 else (0.12 + 0.1 * rng.random()) if re.search(r'[,?]$', L[i - 1]) else (0.22 + 0.25 * rng.random())
    out.append(np.zeros(int(gap * SR))); t += gap
    info.append({'i': i, 'text': s, 'start': round(t, 3), 'dur': round(len(y) / SR, 3)}); out.append(y); t += len(y) / SR
out.append(np.zeros(int(0.3 * SR)))
sf.write(f'{work}/audio/vo.wav', np.concatenate(out), SR); json.dump(info, open(f'{work}/audio/lines.json', 'w'), indent=1)
subprocess.run([f'{KIT}/.venv/bin/python', f'{KIT}/words.py', f'{work}/audio/vo.wav', '/dev/stdin'], input=('\n'.join(L)).encode(), check=True, capture_output=True)
cap = subprocess.run(['python3', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captions.py'), f'{work}/audio/vo.words.json'], capture_output=True, text=True, check=True).stdout
cap += 'export const LINES = [' + ', '.join(f"[{x['start']}, {round(x['start'] + x['dur'], 3)}]" for x in info) + '];\n'
open(f'{work}/src/cap.js', 'w').write(cap); print(json.dumps(info))
