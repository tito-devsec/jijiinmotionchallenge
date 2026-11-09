"""SCENE 03 — roads become digital. Elevated shot above Samora Avenue looking toward the harbour; buildings already binary."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('binary', crop=((-100, 150), 700), real_trees=True); S.ocean_material_upgrade(dusk=True)
    b = objs['CITY_BUILDING']; mb = P.apply_binary(b, progress=1.0, density=0.35, size=0.9, noise_scale=0.025, seed=3, height_bias=0.55); S.drive_flow(mb, speed=1.0)
    r = objs['CITY_ROAD']; mr = P.apply_binary(r, progress=0.0, density=0.9, size=0.55, noise_scale=0.006, seed=11, height_bias=0.0, band=0.25)
    S.key_progress(mr, [(1, 0.0), (int(F * 0.1), 0.0), (int(F * 0.8), 1.0), (F, 1.0)]); S.drive_flow(mr, speed=2.0)
    # street-light pulses: emissive on paving as roads complete
    pv = objs['CITY_PAVING']; mp = P.apply_binary(pv, progress=0.0, density=0.3, size=0.5, noise_scale=0.01, seed=5, height_bias=0.0, band=0.3)
    S.key_progress(mp, [(int(F * 0.4), 0.0), (F, 0.7)]); S.drive_flow(mp, speed=2.0)
    S.world_dusk(strength=0.03, sun_elev=4)
    gz = P.ground_z(-230, 120)
    cam = P.add_camera(loc=(-260, 90, gz + 26), target=(-60, 160, gz + 4), lens=30)
    S.cam_path(cam, [(1, (-260, 90, gz + 26)), (F, (-180, 130, gz + 44))], [(1, (-60, 160, gz + 4)), (F, (40, 120, gz + 2))])
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
