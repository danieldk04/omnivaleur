import json, sys, urllib.request, os, subprocess
key = open(os.path.expanduser('~/.omnivaleur/elevenlabs-sleutel.txt')).read().strip()
S = json.load(open('week48-scripts.json'))
only = sys.argv[1:] 
for name, v in S.items():
    if only and name not in only: continue
    text = ' '.join(v['lines'])
    body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.38, "similarity_boost": 0.75, "style": 0.4, "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{v['voice']}?output_format=mp3_44100_64", data=body,
        headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"})
    try:
        d = urllib.request.urlopen(req, timeout=120).read()
        open(f'vo/{name}.mp3', 'wb').write(d); print(name, 'ok', len(d), len(text), 'chars')
    except Exception as e:
        print(name, 'FAIL', getattr(e, 'code', e), getattr(e, 'read', lambda: b'')()[:200])
