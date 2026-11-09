"""Scene render driver. Usage:
  blender -b --python scripts/rendering/render_scene.py -- <scene_id> [preview|final] [frame_step] [start] [end]
Loads scripts/scenes/<scene_id>.py which must define build(scene_cfg, quality) -> None (sets up the scene and camera, frame range 1..frames).
Frames are written to renders/<scene_id>/f_####.png. Skips frames that already exist (resumable).
"""
import bpy, sys, os, json, importlib.util, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
args = sys.argv[sys.argv.index('--') + 1:]
sid = args[0]; quality = args[1] if len(args) > 1 else 'preview'; step = int(args[2]) if len(args) > 2 else 1
cfg = json.load(open(os.path.join(ROOT, 'scripts', 'film_config.json')))
scn = next(s for s in cfg['scenes'] if s['id'] == sid)
start = int(args[3]) if len(args) > 3 else 1; end = int(args[4]) if len(args) > 4 else scn['frames']
spec = importlib.util.spec_from_file_location(sid, os.path.join(ROOT, 'scripts', 'scenes', f'{sid}.py'))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
t0 = time.time()
mod.build(scn, quality)
import posta_lib as _P; _P.enforce_palette()
for _o in bpy.data.objects:   # practical/area lights light the scene but are never seen as glowing slabs
    if _o.type == 'LIGHT': _o.visible_camera = False
print(f'[{sid}] built in {time.time()-t0:.1f}s, objects={len(bpy.data.objects)}')
sc = bpy.context.scene
SAMPLE_CAP = int(os.environ.get('POSTA_SAMPLES', '12'))
if quality == 'preview':
    sc.render.resolution_percentage = 50; sc.cycles.samples = min(sc.cycles.samples, 8); sc.cycles.adaptive_threshold = 0.1
else:
    sc.cycles.samples = min(sc.cycles.samples, SAMPLE_CAP); sc.cycles.adaptive_threshold = 0.06
out = os.path.join(ROOT, 'renders', sid + ('_preview' if quality == 'preview' else '')); os.makedirs(out, exist_ok=True)
frames = list(range(start, end + 1, step))
if quality == 'still':  # one representative frame (arg 3 = frame) at full quality
    frames = [int(args[2])] if len(args) > 2 else [(scn['frames'] // 2)]; out = os.path.join(ROOT, 'previews')
for f in frames:
    fp = os.path.join(out, f'f_{f:04d}.png') if quality != 'still' else os.path.join(out, f'{sid}_still_{f:04d}.png')
    if os.path.exists(fp) and quality != 'still': continue
    sc.frame_set(f); sc.render.filepath = fp; t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[{sid}] frame {f} {time.time()-t1:.1f}s')
print(f'[{sid}] done {time.time()-t0:.1f}s')
