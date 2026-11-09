"""SCENE 06 — Posta 2040 as a realistic futuristic civilisation. Binary architecture resolves into real materials (progress 1->0),
then a low aerial glide along Kivukoni Front. Vehicles are added when the roadster asset is present."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def add_vehicles(F):
    path = os.path.join(P.ROOT, 'blender', 'assets', 'roadster.blend')
    if not os.path.exists(path): return
    col = S.link_asset('roadster.blend', 'ROADSTER')
    # cars gliding along Kivukoni Front (approx straight segment from (-60,60) to (260,-20)) and Azikiwe
    routes = [((-20, 95), (180, 30)), ((170, 32), (-30, 97)), ((-135, 210), (-60, 110))]
    routes = [(S.snap_to_road(*a)[:2], S.snap_to_road(*b)[:2]) for a, b in routes]
    for i, (a, b) in enumerate(routes):
        e = S.instance_collection(col, f'CAR_{i}', loc=(a[0], a[1], P.ground_z(*a) + 0.05))
        ang = math.atan2(b[1] - a[1], b[0] - a[0]) - math.pi / 2
        e.rotation_euler = (0, 0, ang)
        for f, (x, y) in ((1, a), (F, b)):
            e.location = (x, y, P.ground_z(x, y) + 0.05); e.keyframe_insert('location', frame=f)
        for fc in e.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('binary', crop=((50, 60), 900), future=True, real_trees=True); S.ocean_material_upgrade(dusk=True)
    S.apply_bluehour_city(objs); S.terrain_urban_material()
    S.add_ferry(start=(120, -40), end=(520, -420), F=F)
    # the dissolving materials are replaced by future ones; binary modifier runs backwards so glyphs resolve into glass and steel
    b = objs['CITY_BUILDING']; mb = P.apply_binary(b, progress=1.0, density=0.15, size=1.4, noise_scale=0.02, seed=3, height_bias=0.5, band=0.15)
    S.key_progress(mb, [(1, 1.0), (int(F * 0.45), 0.0), (F, 0.0)]); S.drive_flow(mb, speed=0.8); S.binary_off_after(mb, int(F * 0.45) + 2)
    for extra in ('CITY_CROWNS', 'CITY_SPIRES'):
        if extra in objs:
            mx = P.apply_binary(objs[extra], progress=1.0, density=0.3, size=1.4, noise_scale=0.02, seed=4, height_bias=0.5, band=0.15); S.key_progress(mx, [(1, 1.0), (int(F * 0.5), 0.0), (F, 0.0)]); S.drive_flow(mx, speed=0.8); S.binary_off_after(mx, int(F * 0.5) + 2)
    r = objs['CITY_ROAD']; mr = P.apply_binary(r, progress=1.0, density=0.3, size=1.0, noise_scale=0.006, seed=11, height_bias=0.0, band=0.25)
    S.key_progress(mr, [(1, 1.0), (int(F * 0.4), 0.0), (F, 0.0)]); S.drive_flow(mr, speed=2.0); S.binary_off_after(mr, int(F * 0.4) + 2)
    add_vehicles(F)
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=350, depth=2600, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    cam = P.add_camera(loc=(-120, -120, 60), target=(-30, 100, 25), lens=35)
    S.cam_path(cam, [(1, (-120, -120, 60)), (F, (220, -160, 90))], [(1, (-30, 100, 25)), (F, (60, 90, 20))])
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
