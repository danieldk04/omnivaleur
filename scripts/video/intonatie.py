#!/usr/bin/env python3
"""Intonatie van een stem meten: python intonatie.py bestand.wav [...]  (draai met ~/earshot/.venv/bin/python)
Geeft per bestand: toonhoogtebereik (halve tonen, sd en p10-p90), tempo (woorden/s als --woorden N), pauzes, energievariatie.
Vuistregel (eigen, geen norm): levende spreker met emotie sd 3 tot 5 halve tonen, p10-p90 7 tot 12; onder sd 2 klinkt monotoon."""
import sys, numpy as np, librosa
for f in sys.argv[1:]:
    y, sr = librosa.load(f, sr=16000)
    f0, vo, _ = librosa.pyin(y, fmin=70, fmax=400, sr=sr, frame_length=1024)
    v = f0[~np.isnan(f0)]; st = 12 * np.log2(v / np.median(v))
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]; db = 20 * np.log10(rms + 1e-6)
    act = db > db.max() - 35; sil = ~act
    # pauzes: stiltes van minstens 0,18 s
    runs, n = [], 0
    for s in sil:
        if s: n += 1
        else:
            if n * 256 / sr >= 0.18: runs.append(n * 256 / sr)
            n = 0
    # toonhoogtebeweging per seconde (hoe vaak verandert de toon)
    d = np.abs(np.diff(st)); mov = float(np.mean(d))
    print(f"{f.split('/')[-1]:28s} dur {len(y)/sr:5.1f}s  F0 mediaan {np.median(v):5.0f}Hz  sd {st.std():4.1f}  p10-p90 {np.percentile(st,90)-np.percentile(st,10):5.1f} ht  beweging {mov:4.2f}  pauzes {len(runs)} (gem {np.mean(runs) if runs else 0:.2f}s)  dyn {np.percentile(db[act],90)-np.percentile(db[act],10):4.1f} dB")
