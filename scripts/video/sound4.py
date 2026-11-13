#!/usr/bin/env python3
"""(sound4: omslagtijd is nu een regelpositie, bv 4.0 = begin regel 4) Music bed + soft sfx for a week video: python sound2.py <werkmap> <videoN> <omslagtijd>
Cuts (swish) komen uit de SHOTS-tijden in src/<videoN>.js, blips uit de bijschriften in src/cap.js. Voor de omslagtijd valt het bed 0,25 s weg (stop-down)."""
import re, sys, numpy as np, soundfile as sf, scipy.signal as ss
from scipy.signal import butter, lfilter
work, vid = sys.argv[1], sys.argv[2]
STIJL = sys.argv[4] if len(sys.argv) > 4 else 'warm'
# muziekstijlen, in code gemaakt (geen rechten nodig): akkoorden, tempo, arp-noten, of er een kick onder de draai zit, hoe luid het bed is
STIJLEN = {
  'warm': dict(ch=[[220, 261.63, 329.63], [174.61, 220, 261.63], [130.81, 196, 261.63], [196, 246.94, 293.66]], bpm=104, arp=[440, 523.25, 659.25, 523.25, 349.23, 440, 523.25, 440, 261.63, 392, 523.25, 392, 392, 493.88, 587.33, 493.88], kick=True, vol=0.30, arpv=0.06),
  'lofi': dict(ch=[[196, 246.94, 293.66, 392], [174.61, 220, 261.63, 349.23], [164.81, 207.65, 246.94, 329.63], [146.83, 185, 220, 293.66]], bpm=78, arp=[392, 0, 493.88, 0, 587.33, 0, 493.88, 392], kick=False, vol=0.26, arpv=0.05),
  'spanning': dict(ch=[[110, 130.81, 164.81], [103.83, 123.47, 155.56], [98, 116.54, 146.83], [103.83, 123.47, 155.56]], bpm=120, arp=[220, 220, 246.94, 220, 207.65, 207.65, 220, 164.81], kick=True, vol=0.34, arpv=0.07),
  'speels': dict(ch=[[261.63, 329.63, 392], [293.66, 349.23, 440], [220, 261.63, 329.63], [196, 246.94, 293.66]], bpm=128, arp=[523.25, 659.25, 783.99, 659.25, 587.33, 698.46, 880, 698.46], kick=True, vol=0.30, arpv=0.07),
  'rustig': dict(ch=[[130.81, 196, 261.63], [110, 164.81, 220], [174.61, 220, 261.63], [196, 246.94, 392]], bpm=66, arp=[0], kick=False, vol=0.22, arpv=0.0),
}
ST = STIJLEN[STIJL]
src = open(f'{work}/src/{vid}.js').read(); cap = open(f'{work}/src/cap.js').read()
D = float(re.search(r'DURATION = ([\d.]+)', cap).group(1))
LN = re.search(r'LINES = \[(.*)\];', cap).group(1); LN = [[float(a), float(b)] for a, b in re.findall(r'\[([\d.]+), ([\d.]+)\]', LN)]
def at(p):
    i = min(int(p), len(LN) - 1); return LN[i][0] + (p - i) * (LN[i][1] - LN[i][0])
pos = [float(x) for x in re.findall(r'^\s+\[([\d.]+), (?:kinetic|soldPoof|K|Ll|Mm|Nn|Oo|addItem)', src, re.M)]
cuts = [at(p) for p in pos][1:]; whip = [c for k, c in enumerate(cuts, start=1) if k % 3 != 2]   # montage-variant van sound3: tijden uit de regelposities
caps = []
turn = at(float(sys.argv[3]))
sr = 44100; n = int(D * sr); t = np.arange(n) / sr; rng = np.random.default_rng(7)
def lp(x, hz): b_, a_ = butter(2, hz / (sr / 2)); return lfilter(b_, a_, x)
def put(sig, x0, y):
    i0 = int(x0 * sr); L = min(len(y), n - i0)
    if L > 0 and i0 >= 0: sig[i0:i0 + L] += y[:L]
mix = np.zeros(n)
chords = ST['ch']
for b in range(int(D / 2.2) + 1):
    for f in chords[b % 4]:
        L = int(2.6 * sr); k = np.arange(L) / sr
        w = (np.sin(2 * np.pi * f * k) + 0.4 * np.sin(2 * np.pi * f * 2.005 * k) + 0.25 * np.sin(2 * np.pi * f * 4 * k)) * np.minimum(k / 0.5, 1) * np.minimum((2.6 - k) / 0.8, 1)
        put(mix, b * 2.2, 0.035 * w)
beat = 60 / ST['bpm'] / 2; notes = ST['arp']
for i in range(int(D / beat)):
    f = notes[i % len(notes)]
    if f == 0 or ST['arpv'] == 0: continue
    k = np.arange(int(0.5 * sr)) / sr
    put(mix, i * beat, ST['arpv'] * (np.sin(2 * np.pi * f * k) + 0.45 * np.sin(2 * np.pi * 2 * f * k) + 0.2 * np.sin(2 * np.pi * 3 * f * k)) * np.exp(-k / 0.12))
for i in range(int((D - turn) / (beat * 2)) if ST['kick'] else 0):
    k = np.arange(int(0.3 * sr)) / sr
    put(mix, turn + i * beat * 2, 0.22 * np.sin(2 * np.pi * (55 + 90 * np.exp(-k / 0.03)) * k) * np.exp(-k / 0.12))
# stop-down: bed silent 0.25 s before the turn, then a bigger hit
mix[int((turn - 0.25) * sr):int(turn * sr)] *= 0.0
k = np.arange(int(0.6 * sr)) / sr; put(mix, turn, 0.45 * np.sin(2 * np.pi * (45 + 120 * np.exp(-k / 0.04)) * k) * np.exp(-k / 0.25))
sfx = np.zeros(n)
def bloop(x, f=420, g=1.0):
    k = np.arange(int(0.22 * sr)) / sr
    put(sfx, x, 0.5 * g * lp(np.sin(2 * np.pi * (f + 120 * np.exp(-k / 0.05)) * k) * (1 - np.exp(-k / 0.004)) * np.exp(-k / 0.07), 2200))
def swish(x, dur=0.3):
    L = int(dur * sr); k = np.arange(L) / L; y = lp(rng.standard_normal(L), 1400) * (np.sin(np.pi * k) ** 2); put(sfx, x, 0.45 * y / (np.abs(y).max() + 1e-9))
for x in whip: swish(x - 0.1)
for i, x in enumerate(caps): bloop(x + 0.02, 380 + 25 * (i % 5), 0.5)
import soundfile as sf2
vo, vsr = sf.read(f'{work}/audio/vo.wav'); vo = vo if vo.ndim == 1 else vo[:, 0]
if vsr != sr: vo = ss.resample_poly(vo, sr, vsr)
vo = np.pad(vo, (0, max(0, n - len(vo))))[:n]
lvl = np.convolve(np.abs(vo), np.ones(int(0.15 * sr)) / int(0.15 * sr), mode='same'); duck = 1 - 0.6 * np.clip(lvl / 0.08, 0, 1)
mix *= duck; mix *= np.clip((D - t) / 1.2, 0, 1) * np.minimum(t / 0.3, 1)
mix /= max(1e-6, np.abs(mix).max()); mix *= ST['vol']
room = lp(rng.standard_normal(n), 900) * 0.004; mix += room   # quiet room tone, so the voice is not in a vacuum
sfx *= duck * np.clip((D - t) / 1.0, 0, 1)
mix += sfx * (0.08 / max(1e-6, np.abs(sfx).max()))
sf.write(f'{work}/audio/bed.wav', np.clip(mix, -0.95, 0.95), sr)
sf.write(f'{work}/audio/vo_pad.wav', vo, sr)
print('ok', D)
