"""SCENE 04 — Posta as a binary civilisation. Aerial rise and slow orbit over Kivukoni, whole peninsula visible."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('binary', future=True); S.ocean_material_upgrade(dusk=True)
    b = objs['CITY_BUILDING']; mb = P.apply_binary(b, progress=1.0, density=0.02, size=2.6, noise_scale=0.02, seed=3, height_bias=0.5, keep_shell=1.0); S.drive_flow(mb, speed=0.8)
    r = objs['CITY_ROAD']; mr = P.apply_binary(r, progress=1.0, density=0.06, size=1.8, noise_scale=0.006, seed=11, height_bias=0.0, band=0.25); S.drive_flow(mr, speed=2.0)
    for extra in ('CITY_CROWNS', 'CITY_SPIRES'):
        if extra in objs:
            mx = P.apply_binary(objs[extra], progress=1.0, density=0.05, size=2.4, noise_scale=0.02, seed=4, height_bias=0.5, keep_shell=1.0); S.drive_flow(mx, speed=0.8)
    tr = objs['CITY_TREE']; mt = P.apply_binary(tr, progress=1.0, density=0.03, size=1.5, noise_scale=0.05, seed=9, height_bias=0.3); S.drive_flow(mt, speed=1.0)
    pv = objs['CITY_PAVING']; mp = P.apply_binary(pv, progress=0.6, density=0.02, size=1.6, noise_scale=0.01, seed=5, height_bias=0.0); S.drive_flow(mp, speed=2.0)
    S.world_bluehour(sun_energy=0.3, strength=0.35)
    S.binary_rain((-150, 150), size=1800, top=380, height=380, columns_per_km2=320, glyph=3.2, per_column=18, speed=14, look_at=(-300, -600, 300))
    S.enable_mist(start=300, depth=2500, color=(0.03, 0.06, 0.14, 1), strength=0.55)
    cam = P.add_camera(loc=(-500, -450, 160), target=(-150, 150, 20), lens=32)
    S.cam_path(cam, [(1, (-500, -450, 160)), (int(F * 0.5), (-250, -650, 420)), (F, (250, -600, 720))], [(1, (-150, 150, 20)), (F, (-200, 200, 0))])
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
