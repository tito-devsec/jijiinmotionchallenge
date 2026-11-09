#!/bin/bash
# Render one full-quality still per scene for quality control; logs per-frame render time.
cd "$(dirname "$0")/../.."
for spec in "$@"; do
  sid=${spec%%:*}; f=${spec##*:}
  /opt/blender/blender -b --python "$PWD/scripts/rendering/render_scene.py" -- $sid still $f 2>&1 | grep -E "\[$sid\] (frame|done)|Traceback|Error:" | tail -2
done
echo QC_DONE
