#!/bin/bash
# Production render queue. Sequential (each Blender process uses all cores), resumable (existing frames are skipped).
# Usage: scripts/rendering/render_film.sh preview|final
# After each scene a small review clip is encoded to renders/clips and pushed, so progress survives a container restart.
cd "$(dirname "$0")/../.."
MODE=${1:-preview}; B=/opt/blender/blender; RS="$PWD/scripts/rendering/render_scene.py"
if [ "$MODE" = preview ]; then SUF=_preview; else SUF=""; fi
declare -A STEP=( [s01]=2 [s02]=2 [s03]=3 [s04]=3 [s05]=2 [s06]=3 [s07]=3 [s08]=2 [s09]=3 [s09b]=2 [s10]=2 [s11]=3 [s12]=2 [s13]=2 [s14]=2 )
[ "$MODE" = preview ] && for k in "${!STEP[@]}"; do STEP[$k]=3; done
log(){ echo "$(date +%H:%M:%S) $*"; }
clip(){ mkdir -p renders/clips; d=renders/$1; [ -d renders/$1_ui ] && d=renders/$1_ui
  ffmpeg -y -loglevel error -framerate $((24 / $2)) -pattern_type glob -i "$d/f_*.png" -vf "scale=960:-2,format=yuv420p" -c:v libx264 -crf 26 renders/clips/$1.mp4
  (cd .. && git add POSTA_2040/renders/clips/$1.mp4 && git -c user.name="tito-devsec" -c user.email="237325373+tito-devsec@users.noreply.github.com" commit -q -m "Render progress: $1" && git push -q origin claude/keen-fermat-83k5lr) >/dev/null 2>&1
  log clip $1; }
scene(){ log start $1; $B -b --python $RS -- $1 $MODE ${STEP[$1]} 2>&1 | grep -E "\[$1\] done|Error:|Traceback"; }
export POSTA_SCREEN_DIR="$PWD/renders/s09${SUF}_ui"
scene s09; python3 scripts/rendering/overlay_ui.py camera renders/s09$SUF renders/s09${SUF}_ui >/dev/null && clip s09$SUF 1
for sid in s01 s02 s03 s04 s05 s06 s07 s08 s09b s10 s11 s12 s13 s14; do
  scene $sid
  case $sid in
    s13) python3 scripts/rendering/overlay_ui.py social renders/s13$SUF renders/s13${SUF}_ui >/dev/null; clip s13$SUF 1 ;;
    s14) python3 scripts/rendering/overlay_ui.py brand renders/s14$SUF renders/s14${SUF}_ui >/dev/null; clip s14$SUF 1 ;;
    *) clip $sid$SUF ${STEP[$sid]} ;;
  esac
done
python3 scripts/rendering/brand_cards.py >/dev/null
python3 scripts/rendering/edit_film.py --suffix "$SUF" 2>&1 | tail -2 && log FILM_DONE $MODE
