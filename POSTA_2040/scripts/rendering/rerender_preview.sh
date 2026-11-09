#!/bin/bash
# Re-render selected preview scenes after fixes, then re-cut the preview film.
cd "$(dirname "$0")/../.."
B=/opt/blender/blender; RS="$PWD/scripts/rendering/render_scene.py"; export POSTA_SCREEN_DIR="$PWD/renders/s09_preview_ui"
log(){ echo "$(date +%H:%M:%S) $*"; }
for sid in "$@"; do
  rm -rf renders/${sid}_preview renders/${sid}_preview_ui
  log start $sid; $B -b --python $RS -- $sid preview 3 2>&1 | grep -E "\[$sid\] done|Error:|Traceback"
  [ "$sid" = s13 ] && python3 scripts/rendering/overlay_ui.py social renders/s13_preview renders/s13_preview_ui >/dev/null
  log clip $sid
done
python3 scripts/rendering/edit_film.py --suffix _preview 2>&1 | tail -1 && log FILM_DONE rerender
