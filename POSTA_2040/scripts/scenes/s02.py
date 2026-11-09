"""SCENE 02 — real buildings transform into binary. Street level at Posta (Azikiwe / Samora), dolly forward and tilt up."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('binary', crop=((-140, 190), 520), real_trees=True)
    S.ocean_material_upgrade(dusk=True)
    b = objs['CITY_BUILDING']
    md = P.apply_binary(b, progress=0.0, density=0.7, size=0.85, noise_scale=0.025, seed=3, height_bias=0.55, band=0.1, keep_shell=1.0)
    S.key_progress(md, [(1, 0.0), (int(F * 0.12), 0.02), (int(F * 0.85), 1.0), (F, 1.0)]); S.drive_flow(md, speed=1.0)
    # roads start real here; small shimmer only at the end
    r = objs['CITY_ROAD']; mr = P.apply_binary(r, progress=0.0, density=0.5, size=0.6, noise_scale=0.012, seed=11, height_bias=0.0, band=0.2)
    S.key_progress(mr, [(int(F * 0.8), 0.0), (F, 0.08)]); S.drive_flow(mr, speed=1.5)
    S.world_bluehour(sun_energy=0.35, strength=0.35)
    sx, sy, sz = P.best_street_spot((-130, 200), radius=260); print('street spot', sx, sy, sz)
    top = P.nearest_building_top(sx, sy, 60); tx, ty, th = (top[0].x, top[0].y, top[1]) if top else (sx + 30, sy + 30, sz + 30)
    print('hero building', tx, ty, th)
    import math as _m
    ang = _m.atan2(ty - sy, tx - sx); d0 = 70.0
    c0 = (tx - _m.cos(ang) * d0, ty - _m.sin(ang) * d0, sz + 1.7); c1 = (tx - _m.cos(ang) * (d0 - 18), ty - _m.sin(ang) * (d0 - 18), sz + 4.0)
    P.clear_trees_near([c0, c1, (sx, sy), (tx, ty)], 160)
    import tree_lib; tree_lib.clear_real_trees_near([c0, c1, (tx, ty)], 45)
    cam = P.add_camera(loc=c0, target=(tx, ty, sz + 8), lens=22, dof_target=45, fstop=5.6)
    S.cam_path(cam, [(1, c0), (F, c1)], [(1, (tx, ty, sz + 10)), (F, (tx, ty, th * 0.75))])
    rain = S.binary_rain((tx, ty), size=420, top=th + 60, height=th + 60, columns_per_km2=2600, glyph=0.9, look_at=c0)
    rain.hide_render = True; rain.keyframe_insert('hide_render', frame=1); rain.hide_render = False; rain.keyframe_insert('hide_render', frame=int(F * 0.35))
    S.enable_mist(start=60, depth=900, color=(0.03, 0.06, 0.14, 1), strength=0.5)
    P.setup_render(samples=28, motion_blur=False, frame_end=F)
    S.frame_range(scn)
