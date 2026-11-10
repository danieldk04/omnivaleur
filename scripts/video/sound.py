# Code-made music bed + sfx for the Omnivaleur test reel. Pure numpy: warm pad, soft pluck arp, pops on card appearances, whooshes on cuts.
import numpy as np, soundfile as sf
sr = 44100; D = 18.0; n = int(D * sr); t = np.arange(n) / sr
rng = np.random.default_rng(7)
def env(x0, dur, a=0.01, r=0.2):
    e = np.zeros(n); i0 = int(x0 * sr); L = int(dur * sr); k = np.arange(L) / sr
    e[i0:i0 + L] = np.minimum(k / a, 1) * np.exp(-k / r)[:len(k)] if i0 + L <= n else 0
    return e
def put(sig, x0, y):
    i0 = int(x0 * sr); L = min(len(y), n - i0)
    if L > 0: sig[i0:i0 + L] += y[:L]
mix = np.zeros(n)
# pad: Am - F - C - G, 2.2 s each, loops
chords = [[220, 261.63, 329.63], [174.61, 220, 261.63], [130.81, 196, 261.63], [196, 246.94, 293.66]]
for b in range(int(D / 2.2) + 1):
    for f in chords[b % 4]:
        seg = np.zeros(n); i0 = int(b * 2.2 * sr); L = int(2.6 * sr); k = np.arange(L) / sr
        w = (np.sin(2 * np.pi * f * k) + 0.4 * np.sin(2 * np.pi * f * 2.005 * k)) * np.minimum(k / 0.5, 1) * np.minimum((2.6 - k) / 0.8, 1)
        if i0 < n: seg[i0:i0 + min(L, n - i0)] = w[:min(L, n - i0)]
        mix += 0.035 * seg
# pluck arp, 8ths at 104 bpm
beat = 60 / 104 / 2; notes = [440, 523.25, 659.25, 523.25, 349.23, 440, 523.25, 440, 261.63, 392, 523.25, 392, 392, 493.88, 587.33, 493.88]
for i in range(int(D / beat)):
    f = notes[i % 16]; k = np.arange(int(0.5 * sr)) / sr
    y = (np.sin(2 * np.pi * f * k) + 0.3 * np.sin(2 * np.pi * 2 * f * k)) * np.exp(-k / 0.12)
    put(mix, i * beat, 0.05 * y)
# soft kick on every beat after 9.6 s (the "fixes that" lift)
for i in range(int((D - 9.6) / (beat * 2))):
    x = 9.6 + i * beat * 2; k = np.arange(int(0.3 * sr)) / sr
    put(mix, x, 0.22 * np.sin(2 * np.pi * (55 + 90 * np.exp(-k / 0.03)) * k) * np.exp(-k / 0.12))
# ---- soft sfx (separate track, mixed in quietly) ----
from scipy.signal import butter, lfilter
sfx = np.zeros(n)
def lp(x, hz): b_, a_ = butter(2, hz / (sr / 2)); return lfilter(b_, a_, x)
def bloop(x, f=420, g=1.0):   # gentle water-drop style blip, no sharp attack
    k = np.arange(int(0.22 * sr)) / sr
    y = np.sin(2 * np.pi * (f + 120 * np.exp(-k / 0.05)) * k) * (1 - np.exp(-k / 0.004)) * np.exp(-k / 0.07)
    put(sfx, x, 0.5 * g * lp(y, 2200))
def swish(x, dur=0.32):       # soft air swish, low-passed so it never hisses
    L = int(dur * sr); k = np.arange(L) / L; y = lp(rng.standard_normal(L), 1400) * (np.sin(np.pi * k) ** 2)
    put(sfx, x, 0.9 * y / (np.abs(y).max() + 1e-9) * 0.5)
def tick(x):
    k = np.arange(int(0.04 * sr)) / sr; put(sfx, x, 0.35 * lp(np.sin(2 * np.pi * 900 * k) * np.exp(-k / 0.01), 2500))
for x, f in [(1.5, 400), (2.5, 440), (3.65, 480)]: bloop(x, f)
for i in range(5): bloop(4.4 + i * 0.165, 360 + 30 * i, 0.5)        # photo grid: five soft drops, not fifteen
for i in range(4): bloop(5.45 + i * 0.22, 420 + 40 * i, 0.5)
bloop(6.6, 380, 0.6); bloop(7.1, 380, 0.6)
bloop(11.2 + 0.4, 520, 0.9)                                         # the click
for i in range(5): bloop(12.0 + 0.15 + i * 0.09, 400 + 45 * i, 0.55)
bloop(14.25, 520, 0.8)
cuts = [0.8, 1.4, 2.4, 3.3, 4.4, 5.4, 6.4, 7.75, 8.7, 9.6, 10.4, 11.2, 12.0, 12.9, 13.65, 14.6, 16.0]
for x in cuts: swish(x - 0.1)
for i in range(4): tick(7.9 + i * 0.5)                               # clock under the midnight shot
# duck the bed under the voice, then fade out
vo, vsr = sf.read('audio/vo.wav'); vo = vo if vo.ndim == 1 else vo[:, 0]
if vsr != sr:
    import scipy.signal as ss; vo = ss.resample_poly(vo, sr, vsr)
vo = np.pad(vo, (0, max(0, n - len(vo))))[:n]
lvl = np.convolve(np.abs(vo), np.ones(int(0.15 * sr)) / int(0.15 * sr), mode='same'); duck = 1 - 0.55 * np.clip(lvl / 0.08, 0, 1)
mix *= duck; mix *= np.clip((D - t) / 1.2, 0, 1) * np.minimum(t / 0.3, 1)
mix /= max(1e-6, np.abs(mix).max()); mix *= 0.55
sfx *= duck * np.clip((D - t) / 1.0, 0, 1)
mix += sfx * (0.16 / max(1e-6, np.abs(sfx).max()))
mix = np.clip(mix, -0.95, 0.95)
sf.write('audio/bed.wav', mix, sr)
print('ok', mix.shape)
