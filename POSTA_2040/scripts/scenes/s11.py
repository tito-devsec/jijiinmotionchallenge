"""SCENE 11 — underwater. The phone sinks through sun shafts past fish schools and settles on the sand beside the coral head.
Built on the underwater kit scene (water volume, animated caustics, shafts, reef, GN fish schools and bubbles)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S
import numpy as np

def open_reef():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(P.ROOT, 'blender', 'assets', 'underwater.blend'))
    for o in [o for o in bpy.data.objects if o.type == 'CAMERA']: bpy.data.objects.remove(o)
    fl = bpy.data.objects['REEF_FLOOR']; co = np.array([fl.matrix_world @ v.co for v in fl.data.vertices])
    head = bpy.data.objects['REEF_HEAD']
    return float(np.median(co[:, 2])), head.matrix_world.translation.copy()

def build(scn, quality):
    F = scn['frames']; floor, reef = open_reef()
    sc = bpy.context.scene
    S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']; phone.scale = (1, 1, 1)
    rest = (reef.x + 2.2, reef.y - 3.0, floor + 0.05)
    # sinking: decelerating fall with flutter, settles screen-down at 80 % of the scene
    import random; random.seed(3); fs = int(F * 0.8)
    for f in range(1, F + 1):
        t = min(1.0, (f - 1) / (fs - 1)); e = 1 - (1 - t) ** 2.2
        z = -0.5 + (rest[2] + 0.5) * e
        x = rest[0] - 1.2 * (1 - e) + 0.35 * math.sin(f * 0.21) * (1 - e); y = rest[1] + 0.8 * (1 - e) + 0.25 * math.cos(f * 0.17) * (1 - e)
        phone.location = (x, y, z); phone.keyframe_insert('location', frame=f)
        rx = math.radians(180) * e + 0.5 * math.sin(f * 0.13) * (1 - e); rz = 1.5 * (1 - e) + 0.4
        phone.rotation_euler = (rx, 0.3 * math.sin(f * 0.11) * (1 - e), rz); phone.keyframe_insert('rotation_euler', frame=f)
    # a few entry bubbles following the phone
    if 'BUBBLE_EMITTER' in bpy.data.objects:
        be = bpy.data.objects['BUBBLE_EMITTER'].copy(); sc.collection.objects.link(be); be.parent = phone; be.location = (0, 0, 0)
    # chase camera baked from the phone's own curves: ~1.1 m away while it sinks, easing to a low 0.7 m view on the sand
    cam = P.add_camera(loc=(0, 0, 0), target=phone, lens=35, dof_target=phone, fstop=3.2)
    fcs = phone.animation_data.action.fcurves
    ev = lambda f: [next(fc for fc in fcs if fc.data_path == 'location' and fc.array_index == i).evaluate(f) for i in range(3)]
    for f in range(1, F + 1):
        px, py, pz = ev(f); k = min(1.0, f / fs); k = k * k * (3 - 2 * k)
        ang = math.radians(-120 + 50 * k); d = 1.15 - 0.45 * k; h = 0.35 - 0.1 * k
        cam.location = (px + d * math.cos(ang), py + d * math.sin(ang), max(pz + h, rest[2] + 0.25)); cam.keyframe_insert('location', frame=f)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    cam.data.clip_start = 0.01; cam.data.clip_end = 400
    # keep the screen glowing faintly as it sinks (the footage is still playing)
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=1.8)
    P.setup_render(samples=24, frame_end=F, volumes=True)
    c = sc.cycles; c.volume_bounces = 1; c.volume_step_rate = 6.0; c.volume_max_steps = 32; c.transparent_max_bounces = 12
    sc.view_settings.exposure = -0.4
    S.frame_range(scn)
