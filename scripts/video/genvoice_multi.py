#!/usr/bin/env python3
"""python genvoice_multi.py <naam> : dialoog met meerdere stemmen. Leest SCRIPTS (json) {naam:{gap,lines:[{v,t,st?,gap?}]}}, schrijft vo/<naam>.mp3, .words.json en .lines.json (eerste woordindex per regel)."""
import json, sys, os, base64, urllib.request, subprocess, wave
import numpy as np
key = open(os.path.expanduser('~/.omnivaleur/elevenlabs-sleutel.txt')).read().strip()
VOICES = {'liam': 'TX3LPaxmHKxFdv7VOQHJ', 'callum': 'N2lVS1w4EtoT3dr4eOWO', 'charlie': 'IKne3meq5aSn9XLyUdCD', 'daniel': 'onwK4e9ZLuTAKqWW03F9', 'jessica': 'cgSgspJ2msm6clMCkdW9', 'josh': 'TxGEqnHWrfWFTfGW9XjX', 'matilda': 'XrExE9yKIg1WjnnlVkGX'}
S = json.load(open(os.environ.get('SCRIPTS', 'weeknl-new.json')))
SR = 44100
for name in sys.argv[1:]:
    cfg = S[name]; audio = []; words = []; starts = []; t = 0.0; chars = 0
    for i, ln in enumerate(cfg['lines']):
        body = json.dumps({"text": ln['t'], "model_id": "eleven_v3", "voice_settings": {"stability": ln.get('st', .25), "similarity_boost": .7, "style": .5, "use_speaker_boost": True}}).encode()
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICES[ln['v']]}/with-timestamps?output_format=mp3_44100_64", data=body, headers={"xi-api-key": key, "content-type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=120).read()); chars += len(ln['t'])
        open('/tmp/_l.mp3', 'wb').write(base64.b64decode(r['audio_base64']))
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', '/tmp/_l.mp3', '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
        a = np.frombuffer(raw, dtype=np.float32)
        # knip stilte aan begin en eind
        nz = np.where(np.abs(a) > .008)[0]; lo = max(0, nz[0] - int(.03 * SR)); hi = min(len(a), nz[-1] + int(.12 * SR)); trim = lo / SR
        a = a[lo:hi]
        al = r['alignment']; ch, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
        depth = 0; keep = []
        for k, c in enumerate(ch):
            if c == '[': depth += 1; continue
            if c == ']': depth = max(0, depth - 1); continue
            if depth == 0: keep.append(k)
        cur = ''; s0 = 0; pe = 0; first = True
        for k in keep:
            c = ch[k]
            if c.isspace():
                if cur: words.append({'w': cur, 's': t + s0 - trim, 'e': t + pe - trim, 'spk': ln['v']}); cur = ''
                continue
            if not cur: s0 = st[k]
            cur += c; pe = en[k]
        if cur: words.append({'w': cur, 's': t + s0 - trim, 'e': t + pe - trim, 'spk': ln['v']})
        starts.append(next(j for j, w in enumerate(words) if w['s'] >= t - .001 and w['spk'] == ln['v'] and j >= (starts[-1] if starts else 0)))
        audio.append((t, a)); t += len(a) / SR + ln.get('gap', cfg.get('gap', .12))
    out = np.zeros(int((t + .3) * SR), dtype=np.float32)
    for t0, a in audio: out[int(t0 * SR):int(t0 * SR) + len(a)] += a
    np.save('/tmp/_o.npy', out)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-b:a', '64k', f'vo/{name}.mp3'], input=out.tobytes(), check=True)
    json.dump(words, open(f'vo/{name}.words.json', 'w')); json.dump(starts, open(f'vo/{name}.lines.json', 'w'))
    print(name, 'ok', len(words), 'woorden', round(t, 1), 's', chars, 'tekens')
    for k, j in enumerate(starts): print('  regel', k, 'idx', j, words[j]['w'], round(words[j]['s'], 2))
