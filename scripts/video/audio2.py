#!/usr/bin/env python3
"""python audio2.py <naam> [stijl]: bed + effecten uit out/<naam>.cues.json, schrijft out/<naam>.bed.wav en out/<naam>.sfx.wav"""
import sys, json, numpy as np, soundfile as sf
from scipy.signal import butter, lfilter
name = sys.argv[1]; STIJL = sys.argv[2] if len(sys.argv) > 2 else 'warm'
SR = 44100
C = json.load(open(f'out/{name}.cues.json')); D = C['duration'] + 0.3
N = int(D * SR); rng = np.random.default_rng(7)
ST = {
 'warm': dict(ch=[[220, 261.63, 329.63], [174.61, 220, 261.63], [130.81, 196, 261.63], [196, 246.94, 293.66]], bpm=100, arp=[440, 523.25, 659.25, 523.25, 349.23, 440, 523.25, 440], kick=True),
 'lofi': dict(ch=[[196, 246.94, 293.66, 392], [174.61, 220, 261.63, 349.23], [164.81, 207.65, 246.94, 329.63], [146.83, 185, 220, 293.66]], bpm=84, arp=[392, 0, 493.88, 0, 587.33, 0, 493.88, 392], kick=True),
 'speels': dict(ch=[[261.63, 329.63, 392], [293.66, 349.23, 440], [220, 261.63, 329.63], [196, 246.94, 293.66]], bpm=112, arp=[523.25, 659.25, 783.99, 659.25, 587.33, 698.46, 880, 698.46], kick=True),
}[STIJL]
def lp(x, f): b, a = butter(2, f / (SR / 2)); return lfilter(b, a, x)
t = np.arange(N) / SR
beat = 60 / ST['bpm']; bar = beat * 4
bed = np.zeros(N)
for b in range(int(D / bar) + 1):
    s0, s1 = int(b * bar * SR), min(N, int((b + 1) * bar * SR))
    if s0 >= N: break
    n = s1 - s0; tt = np.arange(n) / SR
    env = np.minimum(1, tt / 0.25) * np.minimum(1, (n / SR - tt) / 0.3)
    for f in ST['ch'][b % 4]:
        bed[s0:s1] += (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.004 * tt + 1) + .25 * np.sin(2 * np.pi * f * 2 * tt)) * env * .09
step = beat / 2
for i in range(int(D / step)):
    f = ST['arp'][i % len(ST['arp'])]
    if not f: continue
    s0 = int(i * step * SR); n = int(.35 * SR)
    if s0 + n > N: n = N - s0
    tt = np.arange(n) / SR
    bed[s0:s0 + n] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 9) * .05
if ST['kick']:
    for i in range(int(D / beat)):
        if i % 2: continue
        s0 = int(i * beat * SR); n = int(.3 * SR)
        if s0 + n > N: n = N - s0
        tt = np.arange(n) / SR
        bed[s0:s0 + n] += np.sin(2 * np.pi * (48 + 70 * np.exp(-tt * 22)) * tt) * np.exp(-tt * 9) * .5
bed = lp(bed, 2600)
bed *= min(1, 1.0) * np.minimum(1, t / 0.6) * np.minimum(1, (D - t) / 0.8)
bed *= 0.07 / (np.sqrt(np.mean(bed ** 2)) + 1e-9)
sfx = np.zeros(N)
def add(s, x, g):
    i = int(s * SR)
    if i < 0 or i >= N: return
    x = x[:N - i]; sfx[i:i + len(x)] += x * g
for s, k in C['cues']:
    if k == 'whoosh':
        n = int(.38 * SR); tt = np.arange(n) / SR; x = rng.standard_normal(n)
        x = lp(x, 900) * np.sin(np.pi * tt / .38) ** 2 * .6
        add(s - .12, x, 1.0)
    elif k == 'hit':
        n = int(.35 * SR); tt = np.arange(n) / SR
        x = np.sin(2 * np.pi * (45 + 80 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 10) + lp(rng.standard_normal(n), 1800) * np.exp(-tt * 45) * .6
        add(s, x, .9)
    elif k == 'pop':
        n = int(.12 * SR); tt = np.arange(n) / SR
        add(s, np.sin(2 * np.pi * (420 + 700 * tt / .12) * tt) * np.exp(-tt * 28), .5)
    elif k == 'tick':
        n = int(.06 * SR); tt = np.arange(n) / SR
        add(s, np.sin(2 * np.pi * 1500 * tt) * np.exp(-tt * 70), .35)
    elif k == 'ding':
        n = int(.9 * SR); tt = np.arange(n) / SR
        add(s, (np.sin(2 * np.pi * 988 * tt) + .5 * np.sin(2 * np.pi * 1480 * tt)) * np.exp(-tt * 5), .4)
    elif k == 'buzz':
        n = int(.28 * SR); tt = np.arange(n) / SR
        add(s, lp(np.sign(np.sin(2 * np.pi * 110 * tt)), 600) * np.exp(-tt * 6), .45)
sfx = lp(sfx, 7000); sfx *= 0.35 / (np.abs(sfx).max() + 1e-9)
sf.write(f'out/{name}.bed.wav', bed.astype(np.float32), SR)
sf.write(f'out/{name}.sfx.wav', sfx.astype(np.float32), SR)
print('bed rms', round(float(np.sqrt(np.mean(bed**2))), 3), 'sfx peak', round(float(np.abs(sfx).max()), 3), 'dur', round(D, 1))
