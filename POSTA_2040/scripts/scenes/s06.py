"""SCENE 06 — Posta 2040 as a realistic futuristic civilisation. Binary architecture resolves into real materials (progress 1->0),
with a street-level pass (roadster, robot, residents) that lifts into an aerial glide along Kivukoni Front."""
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
    # street-level hero pass on the waterfront road: the roadster drives by while the robot and a resident walk the pavement
    import character_anim as CA
    (px, py, pz), (dx, dy) = S.road_frame(70, 40); nx, ny = -dy, dx; head = math.atan2(dy, dx) - math.pi / 2
    g = lambda a, b=0.0: (px + dx * a + nx * b, py + dy * a + ny * b, P.ground_z(px + dx * a + nx * b, py + dy * a + ny * b) + 0.05)
    car = S.instance_collection(bpy.data.collections['ROADSTER'], 'CAR_HERO', loc=g(-90, 1.6), rot=(0, 0, head))
    for f, a in ((1, -90), (int(F * 0.3), -40), (int(F * 0.62), 18), (F, 120)):
        car.location = g(a, 1.6); car.keyframe_insert('location', frame=f)
    for fc in car.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    walk = 1.3 / 24.0
    for i, (nm, a0, side) in enumerate((('ROBOT', 4.0, 5.2), ('CIVILIAN_C', 7.5, 6.0), ('HERO', -3.0, 5.6))):
        try:
            col, rig = S.add_character(nm, loc=g(a0, side), heading=head)
            CA.make_walk_cycle(rig, 1, F, stride_frames=24 + 2 * i)
            P.key(rig, 1, loc=g(a0, side)); P.key(rig, F, loc=g(a0 + walk * F, side), interp='LINEAR')
        except Exception as e: print('character skipped', nm, e)
    import tree_lib; tree_lib.clear_real_trees_near([g(a, 4) for a in range(-20, 40, 10)], 9)
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=350, depth=2600, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    # camera: low beside the road as the city resolves and the roadster passes, then lifts over the waterfront
    c0 = g(22, -4.5); c0 = (c0[0], c0[1], c0[2] + 1.4); c1 = g(30, -7); c1 = (c1[0], c1[1], c1[2] + 3.0)
    t0 = g(-30, 3); t1 = g(10, 3)
    cam = P.add_camera(loc=c0, target=(t0[0], t0[1], t0[2] + 12), lens=28)
    S.cam_path(cam, [(1, c0), (int(F * 0.62), c1), (F, (220, -160, 90))],
               [(1, (t0[0], t0[1], t0[2] + 14)), (int(F * 0.62), (t1[0], t1[1], t1[2] + 1.5)), (F, (-60, 150, 40))])
    S.add_air_traffic(F)
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
