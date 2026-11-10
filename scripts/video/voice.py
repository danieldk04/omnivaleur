#!/usr/bin/env python3
"""Voice-over for one video: python voice.py <werkmap> <lines.json>
Kokoro am_michael, snelheid 1.05, 0.22 s tussen regels. Schrijft audio/vo.wav, audio/lines.json en (via words.py) audio/vo.words.json.
Draai met ~/claude-animation-skills/kit/.venv/bin/python."""
import json, os, sys, subprocess, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
KIT = os.path.expanduser('~/claude-animation-skills/kit')
work, lines = sys.argv[1], json.load(open(sys.argv[2]))
os.makedirs(f'{work}/audio', exist_ok=True)
k = Kokoro(f'{KIT}/models/kokoro-v1.0.onnx', f'{KIT}/models/voices-v1.0.bin')
sr = 24000; out = []; info = []; t = 0.0
for i, s in enumerate(lines):
    y, sr = k.create(s, voice='am_michael', speed=1.05, lang='en-us')
    info.append({'i': i, 'text': s, 'start': round(t, 3), 'dur': round(len(y) / sr, 3)})
    out.append(y); gap = np.zeros(int(0.22 * sr), dtype=y.dtype); out.append(gap); t += len(y) / sr + 0.22
sf.write(f'{work}/audio/vo.wav', np.concatenate(out), sr)
json.dump(info, open(f'{work}/audio/lines.json', 'w'), indent=1)
subprocess.run([f'{KIT}/.venv/bin/python', f'{KIT}/words.py', f'{work}/audio/vo.wav', '/dev/stdin'], input=json.dumps(lines).encode(), check=False)
print(json.dumps(info))
