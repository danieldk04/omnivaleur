#!/bin/bash
# bash chk.sh <naam> <dir> <idx:offset,...>  -> stills op woordtijden + contactsheet
cd ~/omnivaleur-videos/week-2026-48
TS=$(python3 -c "
import json
w=json.load(open('vo/$1.words.json'))
print(','.join('%.2f'%(w[int(a)]['s']+float(b)) for a,b in [x.split(':') for x in '$3'.split(',')]))")
rm -rf stills/$2; PAGE=motion3d.html V=$1 node render2.mjs stills $TS stills/$2 2>&1 | grep -i "error\|fail" ; python3 sheet.py stills/$2
