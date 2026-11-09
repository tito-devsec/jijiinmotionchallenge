"""SCENE 09 — through the camera. The realistic 2040 Posta seen from the helicopter's altitude, framed as the phone is recording.
Rendered clean; the camera-interface frame is composited afterwards by scripts/rendering/overlay_ui.py (keeps the UI crisp and readable)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('future', future=True, real_trees=True); S.ocean_material_upgrade(dusk=False); S.apply_future_materials(objs); S.terrain_urban_material()
    S.world_golden(strength=0.05, sun_elev=18, sun_az=262, sun_energy=2.6)
    S.enable_mist(start=300, depth=2600, color=(0.85, 0.76, 0.64, 1), strength=0.3)
    # continuity with scene 07/08: aerial, looking down on Kivukoni from the south-east over the harbour, slow drift
    cam = P.add_camera(loc=(650, -700, 420), target=(-100, 150, 20), lens=40)
    S.cam_path(cam, [(1, (650, -700, 420)), (F, (520, -620, 390))], [(1, (-100, 150, 20)), (F, (-60, 170, 30))])
    # handheld micro-shake
    import random; random.seed(9)
    for f in range(1, F + 1, 6):
        cam.rotation_euler = cam.rotation_euler  # tracked by constraint; add tiny offsets via delta
        cam.delta_rotation_euler = (math.radians(random.uniform(-0.15, 0.15)), math.radians(random.uniform(-0.15, 0.15)), 0)
        cam.keyframe_insert('delta_rotation_euler', frame=f)
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
