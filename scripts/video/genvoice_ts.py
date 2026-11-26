import json, sys, urllib.request, os, base64
key = open(os.path.expanduser('~/.omnivaleur/elevenlabs-sleutel.txt')).read().strip()
S = json.load(open(os.environ.get('SCRIPTS','week48-scripts.json')))
for name in sys.argv[1:]:
    v = S[name]; text = ' '.join(v['lines'])
    body = json.dumps({"text": text, "model_id": v.get("model","eleven_multilingual_v2"), "voice_settings": {"stability": v.get("stability",0.38), "similarity_boost": 0.75, "style": 0.4, "use_speaker_boost": True}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{v['voice']}/with-timestamps?output_format=mp3_44100_64", data=body, headers={"xi-api-key": key, "content-type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    except Exception as e:
        print('FAIL', getattr(e, 'code', e), getattr(e, 'read', lambda: b'')()[:200]); sys.exit(1)
    open(f'vo/{name}.mp3', 'wb').write(base64.b64decode(r['audio_base64']))
    a = r['alignment']; ch, st, en = a['characters'], a['character_start_times_seconds'], a['character_end_times_seconds']
    keep = []; depth = 0
    for i, c in enumerate(ch):
        if c == '[': depth += 1; continue
        if c == ']': depth = max(0, depth - 1); continue
        if depth == 0: keep.append(i)
    ch, st, en = [ch[i] for i in keep], [st[i] for i in keep], [en[i] for i in keep]
    words, cur, s0 = [], '', None
    for c, s, e in zip(ch, st, en):
        if c.isspace():
            if cur: words.append({'w': cur, 's': s0, 'e': pe}); cur = ''
            continue
        if not cur: s0 = s
        cur += c; pe = e
    if cur: words.append({'w': cur, 's': s0, 'e': pe})
    json.dump(words, open(f'vo/{name}.words.json', 'w'))
    print(name, 'ok', len(words), 'words, end', round(words[-1]['e'], 2))
