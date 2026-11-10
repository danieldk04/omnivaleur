#!/bin/bash
# bash mix.sh <werkmap> <uitvoer.mp4>  : silent.mp4 + stem + bed, loudnorm -14 LUFS, 1080x1920
W=$1
ffmpeg -y -v error -i $W/silent.mp4 -i $W/audio/vo_pad.wav -i $W/audio/bed.wav -filter_complex "[1:a]volume=1.0[v];[2:a]volume=0.8[b];[v][b]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=7,volume=2dB,alimiter=limit=0.84[a];[0:v]scale=1080:1920:flags=lanczos[vv]" -map "[vv]" -map "[a]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest $2
