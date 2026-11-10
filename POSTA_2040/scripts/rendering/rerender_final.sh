#!/bin/bash
# Re-render selected scenes at final quality, optionally re-cut the film.  Usage: rerender_final.sh [--cut] s09 s04 ...
cd "$(dirname "$0")/../.."
B=/opt/blender/blender; RS="$PWD/scripts/rendering/render_scene.py"
export POSTA_RES_PCT=${POSTA_RES_PCT:-75}; export POSTA_SCREEN_DIR="$PWD/renders/s09_ui"
declare -A STEP=( [s01]=2 [s02]=3 [s03]=3 [s04]=3 [s05]=3 [s06]=3 [s07]=2 [s08]=2 [s09]=2 [s09b]=2 [s10]=2 [s11]=3 [s12]=2 [s13]=2 [s14]=2 )
log(){ echo "$(date +%H:%M:%S) $*"; }
CUT=0; [ "$1" = --cut ] && { CUT=1; shift; }
for sid in "$@"; do
  rm -rf renders/$sid renders/${sid}_ui
  log start $sid; $B -b --python $RS -- $sid final ${STEP[$sid]} 2>&1 | grep -E "\[$sid\] done|Error:|Traceback"
  case $sid in
    s09) python3 scripts/rendering/overlay_ui.py camera renders/s09 renders/s09_ui >/dev/null ;;
    s13) python3 scripts/rendering/overlay_ui.py social renders/s13 renders/s13_ui >/dev/null ;;
    s14) python3 scripts/rendering/overlay_ui.py brand renders/s14 renders/s14_ui >/dev/null ;;
  esac
  log clip $sid
done
[ $CUT = 1 ] && python3 scripts/rendering/edit_film.py 2>&1 | tail -1 && log FILM_DONE
log BATCH_DONE
