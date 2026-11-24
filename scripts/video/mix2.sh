#!/bin/bash
# bash mix2.sh <naam> : out/<naam>.silent.mp4 + vo + bed + sfx -> out/<naam>.mp4 (1080x1920, -14 LUFS, piek onder -1,5 dBTP)
N=$1
ffmpeg -y -v error -i vo/$N.mp3 -i out/$N.bed.wav -i out/$N.sfx.wav -filter_complex \
"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,highpass=f=70,asplit=2[v1][v2];[1:a]aformat=sample_rates=44100:channel_layouts=stereo[bd];[bd][v2]sidechaincompress=threshold=0.015:ratio=7:attack=15:release=350[bdd];[2:a]aformat=sample_rates=44100:channel_layouts=stereo[fx];[v1][bdd][fx]amix=inputs=3:normalize=0:duration=longest[a]" -map "[a]" out/$N.raw.wav
M=$(ffmpeg -hide_banner -nostats -i out/$N.raw.wav -af loudnorm=I=-14:TP=-2:LRA=7:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
g() { echo "$M" | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
ffmpeg -y -v error -i out/$N.silent.mp4 -i out/$N.raw.wav -filter_complex \
"[1:a]loudnorm=I=-14:TP=-2:LRA=7:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,alimiter=limit=0.84:level=0[a];[0:v]scale=1080:1920:flags=lanczos[vv]" \
-map "[vv]" -map "[a]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest out/$N.mp4
ffmpeg -hide_banner -nostats -i out/$N.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|LRA:|Peak:)" | tr '\n' ' '; echo
