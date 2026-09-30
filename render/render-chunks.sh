#!/bin/bash
# Render the video in parallel chunks, join them, then run the flash guard, which adds the song and re-encodes.
# usage: bash render-chunks.sh NAME "start end" "start end" ...   e.g. bash render-chunks.sh full "0 64" "64 129" "129 193" "193 257.56"
# Chunk boundaries must be multiples of 1/30 s so the frames line up (whole seconds are safest). One chunk per core.
# Output: ../renders/NAME.mp4 (CRF 21), then a flash check of the result (flashcheck2.py prints PASS or the failing ranges).
cd "$(dirname "$0")"
FF=${FFMPEG:-ffmpeg}   # needs libx264
NAME=$1; shift; mkdir -p ../renders; i=0; : > ../renders/${NAME}_list.txt
T0=$(echo $1 | cut -d' ' -f1)
for r in "$@"; do set -- $r
  START=$1 END=$2 PRESET=veryfast FFMPEG=$FF node render.mjs ../renders/${NAME}_$i.mp4 30 > ../renders/${NAME}_$i.log 2>&1 &
  echo "file '${NAME}_$i.mp4'" >> ../renders/${NAME}_list.txt; T1=$2; i=$((i+1))
done
wait
$FF -y -loglevel error -f concat -safe 0 -i ../renders/${NAME}_list.txt -c copy ../renders/${NAME}_raw.mp4
FFMPEG=$FF python3 flashguard.py ../renders/${NAME}_raw.mp4 ../renders/${NAME}.mp4 ../audio/take1.flac $(python3 -c "print($T1-$T0)") $T0
echo "wrote ../renders/${NAME}.mp4"
FFMPEG=$FF python3 flashcheck2.py ../renders/${NAME}.mp4
