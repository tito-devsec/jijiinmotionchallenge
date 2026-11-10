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
    R = int(F * 0.2)   # the binary city resolves into the real one during the opening wide view only
    b = objs['CITY_BUILDING']; mb = P.apply_binary(b, progress=1.0, density=0.15, size=1.4, noise_scale=0.02, seed=3, height_bias=0.5, band=0.15)
    S.key_progress(mb, [(1, 1.0), (R, 0.0), (F, 0.0)]); S.drive_flow(mb, speed=0.8); S.binary_off_after(mb, R + 2)
    if 'CITY_SPIRES' in objs:
        mx = P.apply_binary(objs['CITY_SPIRES'], progress=1.0, density=0.3, size=1.4, noise_scale=0.02, seed=4, height_bias=0.5, band=0.15); S.key_progress(mx, [(1, 1.0), (R, 0.0), (F, 0.0)]); S.drive_flow(mx, speed=0.8); S.binary_off_after(mx, R + 2)
    r = objs['CITY_ROAD']; mr = P.apply_binary(r, progress=1.0, density=0.3, size=1.0, noise_scale=0.006, seed=11, height_bias=0.0, band=0.25)
    S.key_progress(mr, [(1, 1.0), (int(R * 0.8), 0.0), (F, 0.0)]); S.drive_flow(mr, speed=2.0); S.binary_off_after(mr, int(R * 0.8) + 2)
    add_vehicles(F)
    import character_anim as CA, tree_lib
    (px, py, pz), (dx, dy) = S.road_frame(70, 40); nx, ny = -dy, dx; head = math.atan2(dy, dx) - math.pi / 2
    def g(a, bb=0.0, up=0.05):
        x, y = px + dx * a + nx * bb, py + dy * a + ny * bb; return (x, y, P.ground_z(x, y) + up)
    tree_lib.clear_real_trees_near([g(a, 4) for a in range(-30, 50, 10)], 10)
    f1, f2 = int(F * 0.26), int(F * 0.60)          # street pass window
    # hero roadster on the road, passing close to the camera
    car = S.instance_collection(bpy.data.collections['ROADSTER'], 'CAR_HERO', loc=g(-150, 1.8), rot=(0, 0, head))
    for f, a in ((1, -170), (f1, -70), (int(F * 0.5), 4), (f2, 34), (F, 190)):
        car.location = g(a, 1.8); car.keyframe_insert('location', frame=f)
    for fc in car.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    # robot, hero and a resident walking the pavement toward the camera
    walk = 1.3 / 24.0
    for i, (nm, a0, side) in enumerate((('ROBOT', 2.5, 4.4), ('HERO', 1.0, 5.5), ('CIVILIAN_C', -1.0, 6.4))):
        col, rig = S.add_character(nm, loc=g(a0, side), heading=head)
        CA.make_walk_cycle(rig, 1, F, stride_frames=24 + 2 * i)
        P.key(rig, 1, loc=g(a0, side)); P.key(rig, F, loc=g(a0 + walk * F, side), interp='LINEAR')
    # street lamps so the car and the walkers are clearly lit
    for i, a in enumerate((-6, 4, 14, 24)):
        ld = bpy.data.lights.new(f'LAMP_{i}', 'POINT'); ld.energy = 2600; ld.shadow_soft_size = 0.6; ld.color = P.HOT70['silver'][:3]
        lo = bpy.data.objects.new(f'LAMP_{i}', ld); bpy.context.scene.collection.objects.link(lo); lo.location = g(a, 3.4, up=5.0)
    # flying roadster cruising above the same street for the clear aerial view
    fly = S.instance_collection(bpy.data.collections['ROADSTER'], 'CAR_FLY', rot=(0, 0, head), scale=1.6)
    fkeys = ((1, -260, 34), (f2, -40, 34), (int(F * 0.8), 40, 38), (F, 130, 42))
    for f, a, zz in fkeys:
        fly.location = g(a, 0.5, up=zz); fly.keyframe_insert('location', frame=f)
    for fc in fly.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    bpy.ops.mesh.primitive_plane_add(size=1); gl = bpy.context.object; gl.parent = fly; gl.scale = (1.5, 3.4, 1); gl.location = (0, 0, 0.12); gl.rotation_euler = (math.pi, 0, 0)
    gl.data.materials.append(P.new_mat('MAT_Thruster', P.HOT70['night'], 0.4, emission=(0.35, 0.55, 1.0, 1), estrength=14.0))
    for nm, y, colr in (('H', 2.3, (0.8, 0.88, 1.0, 1)), ('T', -2.4, P.HOT70['thermo'])):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.28, segments=8, ring_count=6); l = bpy.context.object; l.parent = fly; l.location = (0, y, 0.75); l.scale = (3.0, 0.6, 0.6)
        l.data.materials.append(P.new_mat('MAT_FlyLight_' + nm, P.HOT70['night'], 0.4, emission=colr, estrength=25.0))
    kl = bpy.data.lights.new('FLY_KEY', 'AREA'); kl.energy = 9000; kl.size = 6; kl.color = P.HOT70['silver'][:3]
    ko = bpy.data.objects.new('FLY_KEY', kl); bpy.context.scene.collection.objects.link(ko); ko.parent = fly; ko.location = (4, -6, 8)
    kc = ko.constraints.new('TRACK_TO'); kc.target = fly; kc.track_axis = 'TRACK_NEGATIVE_Z'; kc.up_axis = 'UP_Y'
    S.add_air_traffic(F, cars=10, helis=1, center=(px, py), spread=260.0, alts=(60, 90, 130))
    # clear sky so every building colour reads
    S.world_bluehour(sun_energy=1.6, strength=1.5)
    S.enable_mist(start=500, depth=3500, color=(0.1, 0.1, 0.2, 1), strength=0.2)
    # camera: wide low-aerial while the city resolves -> down to the pavement for the pass -> up into the clear aerial view
    w0 = g(60, -40, up=34); w1 = g(22, -3.0, up=1.5); w2 = g(17, 3.3, up=1.35); w3 = g(-60, 85, up=72)
    t0 = g(-20, 30, up=30); t1 = g(4, 3.0, up=1.2); t2 = g(6, 3.2, up=1.2)
    cam = P.add_camera(loc=w0, target=t0, lens=28)
    flyp = lambda f: tuple(next(g(a, 0.5, up=zz) for ff, a, zz in fkeys if ff == f))
    S.cam_path(cam, [(1, w0), (f1, w1), (f2, w2), (int(F * 0.8), g(0, 50, up=46)), (F, w3)],
               [(1, t0), (f1, t1), (f2, t2), (int(F * 0.8), g(40, -30, up=36)), (F, g(110, -90, up=50))])
    cam.data.lens = 28; cam.data.keyframe_insert('lens', frame=f2); cam.data.lens = 24; cam.data.keyframe_insert('lens', frame=F)
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
