"""SCENE 10 — the phone slips from the passenger's hand and falls from the helicopter into the Indian Ocean.
Rigid-body gravity with tumbling, tracking camera, motion blur; ends with the splash and the camera going under."""
import bpy, os, sys, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']; fps = 24
    objs = S.load_city('future', future=True, real_trees=True); S.ocean_material_upgrade(dusk=True); S.apply_bluehour_city(objs); S.terrain_urban_material()
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=500, depth=3500, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    S.link_asset('helicopter.blend', 'HELICOPTER'); heli = bpy.data.objects['HELI_ROOT']
    H = 262.0; heli.location = (260, -210, H); heli.rotation_euler = (0, 0, math.atan2(490, -340) - math.pi / 2)
    rot = bpy.data.objects['ROTOR_MAIN']; rot.rotation_euler = (0, 0, 0); rot.keyframe_insert('rotation_euler', frame=1)
    rot.rotation_euler = (0, 0, math.radians(360 * 6 * F / 24)); rot.keyframe_insert('rotation_euler', frame=F)
    for fc in rot.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.6, offset=288)
    # analytic fall: starts at the door, hits water at ~72% of the scene (matches the splash in the audio stem)
    t_hit = 0.72 * F / fps; g = 9.81
    x0, y0, z0 = 262.5, -209.0, H - 0.4
    # terminal-velocity-limited fall so the drop time fits the shot: z(t) = z0 - v_eff * t where total drop in t_hit
    vz = (z0 - 0.4) / t_hit
    random.seed(10)
    for f in range(1, F + 1):
        t = (f - 1) / fps
        if t <= t_hit:
            z = z0 - (0.5 * g * t * t if 0.5 * g * t * t < (z0 - 0.4) * (t / t_hit) ** 1.6 else (z0 - 0.4) * (t / t_hit) ** 1.6)
            z = z0 - (z0 - 0.4) * (t / t_hit) ** 1.6
        else:
            z = 0.4 - (t - t_hit) * 3.5  # sinks after entry
        x = x0 + 2.5 * t; y = y0 + 1.5 * t
        phone.location = (x, y, z); phone.keyframe_insert('location', frame=f)
        phone.rotation_euler = (math.radians(70) + 7.5 * t, 4.2 * t, 2.8 * t); phone.keyframe_insert('rotation_euler', frame=f)
    for fc in phone.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    # chase camera baked per frame from the same fall: starts at the door, settles ~1.3 m above/behind the tumbling phone
    # looking down at the harbour, and is held above the waterline for the splash
    cam = P.add_camera(loc=(263.4, -210.2, H - 0.2), target=phone, lens=30, dof_target=phone, fstop=4.0)
    door = (263.4 - x0, -210.2 - y0, (H - 0.2) - z0)
    for f in range(1, F + 1):
        t = (f - 1) / fps
        ph = phone.animation_data.action.fcurves
        px, py, pz = (next(fc for fc in ph if fc.data_path == 'location' and fc.array_index == i).evaluate(f) for i in range(3))
        k = min(1.0, t / 1.2); k = k * k * (3 - 2 * k)
        off = (door[0] * (1 - k) + 0.55 * k, door[1] * (1 - k) - 0.95 * k, door[2] * (1 - k) + 1.05 * k)
        cz = max(pz + off[2], 1.6)
        cam.location = (px + off[0], py + off[1], cz); cam.keyframe_insert('location', frame=f)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    # splash: expanding ring + spray spheres at the impact point (simple procedural, keyed scale)
    hit = (x0 + 2.5 * t_hit, y0 + 1.5 * t_hit, 0.42); fh = int(0.72 * F)
    bpy.ops.mesh.primitive_torus_add(location=hit, major_radius=0.3, minor_radius=0.08); ring = bpy.context.object; ring.name = 'SPLASH_RING'
    ring.data.materials.append(P.new_mat('MAT_Spray', (0.9, 0.95, 1, 1), 0.3, alpha=0.6))
    ring.scale = (0.01, 0.01, 0.01); ring.keyframe_insert('scale', frame=fh); ring.scale = (6, 6, 1.5); ring.keyframe_insert('scale', frame=F)
    ring.hide_render = True; ring.keyframe_insert('hide_render', frame=1); ring.hide_render = False; ring.keyframe_insert('hide_render', frame=fh)
    for i in range(14):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06 + 0.05 * random.random(), location=hit); sp = bpy.context.object; sp.data.materials.append(bpy.data.materials['MAT_Spray'])
        ang = random.uniform(0, 6.28); vx, vy, vz0 = math.cos(ang) * random.uniform(0.5, 2.5), math.sin(ang) * random.uniform(0.5, 2.5), random.uniform(3, 7)
        sp.hide_render = True; sp.keyframe_insert('hide_render', frame=1); sp.hide_render = False; sp.keyframe_insert('hide_render', frame=fh)
        for f in range(fh, F + 1):
            tt = (f - fh) / fps; sp.location = (hit[0] + vx * tt, hit[1] + vy * tt, hit[2] + vz0 * tt - 0.5 * g * tt * tt); sp.keyframe_insert('location', frame=f)
    P.setup_render(samples=28, frame_end=F, motion_blur=True); bpy.context.scene.render.motion_blur_shutter = 0.6; S.frame_range(scn)
