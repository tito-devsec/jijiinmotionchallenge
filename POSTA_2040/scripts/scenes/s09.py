"""SCENE 09 — through the camera. The realistic 2040 Posta seen from the helicopter's altitude, framed as the phone is recording.
Rendered clean; the camera-interface frame is composited afterwards by scripts/rendering/overlay_ui.py (keeps the UI crisp and readable)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('future', future=True, real_trees=True); S.ocean_material_upgrade(dusk=True); S.apply_bluehour_city(objs); S.terrain_urban_material()
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=300, depth=2600, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    # continuity with scene 07/08: aerial, looking down on Kivukoni from the south-east over the harbour, slow drift
    # filmed from the helicopter's hover point (scenes 07/08/10): Posta CBD towers across the harbour, slow handheld drift
    cam = P.add_camera(loc=(262, -212, 262), target=(-170, 230, 90), lens=45)
    S.cam_path(cam, [(1, (262, -212, 262)), (F, (250, -200, 258))], [(1, (-170, 230, 90)), (F, (-120, 250, 85))])
    # handheld micro-shake
    import random; random.seed(9)
    for f in range(1, F + 1, 6):
        cam.rotation_euler = cam.rotation_euler  # tracked by constraint; add tiny offsets via delta
        cam.delta_rotation_euler = (math.radians(random.uniform(-0.15, 0.15)), math.radians(random.uniform(-0.15, 0.15)), 0)
        cam.keyframe_insert('delta_rotation_euler', frame=f)
    S.add_air_traffic(F, cars=16, center=(40.0, 20.0), spread=260.0, alts=(120, 150, 185, 215), scale=1.6)
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
