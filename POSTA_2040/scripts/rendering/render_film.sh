#!/bin/bash
# Full production render queue (sequential: each Blender process uses all CPU cores). Resumable: existing frames are skipped.
# Usage: scripts/rendering/render_film.sh [STEP]   (STEP=2 renders every 2nd frame; the edit interpolates back to 24 fps)
cd "$(dirname "$0")/../.."
STEP=${1:-2}; B=/opt/blender/blender; RS="$PWD/scripts/rendering/render_scene.py"
log(){ echo "$(date +%H:%M:%S) $*"; }
# s09 first: its frames feed the phone screens in s08, s12, s13, s14
for sid in s09; do log start $sid; $B -b --python $RS -- $sid final $STEP 2>&1 | grep -E "\[$sid\] (frame|done)|Error:" ; done
python3 scripts/rendering/overlay_ui.py camera renders/s09 renders/s09_ui && log s09_ui done
for sid in s01 s02 s03 s04 s05 s06 s07 s08 s10 s11 s12 s13 s14; do
  log start $sid; $B -b --python $RS -- $sid final $STEP 2>&1 | grep -E "\[$sid\] (frame|done)|Error:"
done
python3 scripts/rendering/overlay_ui.py social renders/s13 renders/s13_ui && log s13_ui done
python3 scripts/rendering/overlay_ui.py brand renders/s14 renders/s14_ui && log s14_ui done
python3 scripts/rendering/brand_cards.py
python3 scripts/rendering/edit_film.py && log FILM_DONE
