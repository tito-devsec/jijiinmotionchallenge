"""SCENE 10 — the phone slips from the passenger's hand at the open door and falls into the harbour. The screen is still
recording; our helicopter hovers above. Ballistic fall with tumble, per-frame chase camera, motion blur, splash."""
import bpy, os, sys, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA
from mathutils import Vector

def build(scn, quality):
    S.fresh(); F = scn['frames']; fps = 24
    objs = S.load_city('future', future=True, real_trees=True); S.ocean_material_upgrade(dusk=True); S.apply_bluehour_city(objs); S.terrain_urban_material()
    S.add_ferry(start=(380, -300), end=(150, -80), F=F)
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=500, depth=3500, color=(0.1, 0.1, 0.2, 1), strength=0.3)
    heli, seat = S.hover_helicopter(F); rig, phone = S.cabin_passenger(seat, F)
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.6, flip=True)
    # the hand opens and reaches after the phone
    CA.set_rot(rig, 'upper_arm.R', rx=80, frame=8); CA.set_rot(rig, 'upper_arm.R', rx=95, ry=-10, frame=20); CA.set_rot(rig, 'head', rx=35, frame=24)
    bpy.context.view_layer.update()
    M0 = phone.matrix_world.copy(); start = M0.translation.copy(); out = (seat.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
    phone.parent = None; phone.matrix_world = M0
    sea = 0.4; g = 9.81; t_slip = 6 / fps
    drop = start.z - sea; t_hit = t_slip + math.sqrt(2 * drop / g)     # free fall: ~7.3 s from 262 m
    # the shot is F frames; play the fall in slight slow motion so it lands at ~72 % of the scene (matches the audio splash)
    slow = (t_hit) / (0.72 * F / fps)
    random.seed(10); spin = Vector((3.2, 1.8, 1.2))   # slower tumble so the phone reads on screen
    for f in range(1, F + 1):
        t = (f - 1) / fps * slow
        if t < t_slip: p = start + out * (0.4 * t / t_slip); rot = (0, 0, 0)
        else:
            tf = t - t_slip; z = start.z - 0.5 * g * tf * tf
            p = start + out * (0.4 + 2.2 * tf); p.z = max(z, sea - (tf - (t_hit - t_slip)) * 3.5 if z < sea else z)
            rot = (spin.x * tf, spin.y * tf, spin.z * tf)
        phone.location = p; phone.keyframe_insert('location', frame=f)
        e = M0.to_euler(); phone.rotation_euler = (e.x + rot[0], e.y + rot[1], e.z + rot[2]); phone.keyframe_insert('rotation_euler', frame=f)
    for fc in phone.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    # chase camera: starts beside the passenger, swings out and rides ~1.3 m above/behind the phone, held above the water
    A = S.seat_cams(seat, rig, phone); cam_start = seat.matrix_world @ A['shoulder']
    cam = P.add_camera(loc=tuple(cam_start), target=phone, lens=35, dof_target=phone, fstop=5.6)
    fcs = phone.animation_data.action.fcurves
    ev = lambda f: Vector([next(fc for fc in fcs if fc.data_path == 'location' and fc.array_index == i).evaluate(f) for i in range(3)])
    for f in range(1, F + 1):
        p = ev(f); k = min(1.0, (f - 1) / 30.0); k = k * k * (3 - 2 * k)
        follow = p - out * 0.75 + Vector((0, 0, 0.3))   # close behind the phone, the lit Posta skyline beyond it
        c = cam_start.lerp(follow, k); c.z = max(c.z, 1.6)
        cam.location = c; cam.keyframe_insert('location', frame=f)
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    # splash at the impact point
    f_hit = next((f for f in range(1, F + 1) if ev(f).z <= sea + 0.02), int(0.72 * F)); hit = ev(f_hit)
    spray = P.new_mat('MAT_Spray', P.HOT70['silver'], 0.3, alpha=0.6)
    bpy.ops.mesh.primitive_torus_add(location=(hit.x, hit.y, sea + 0.02), major_radius=0.3, minor_radius=0.08); ring = bpy.context.object; ring.data.materials.append(spray)
    ring.scale = (0.01, 0.01, 0.01); ring.keyframe_insert('scale', frame=f_hit); ring.scale = (6, 6, 1.5); ring.keyframe_insert('scale', frame=F)
    ring.hide_render = True; ring.keyframe_insert('hide_render', frame=1); ring.hide_render = False; ring.keyframe_insert('hide_render', frame=f_hit)
    for i in range(16):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05 + 0.05 * random.random(), location=(hit.x, hit.y, sea)); sp = bpy.context.object; sp.data.materials.append(spray)
        a = random.uniform(0, 6.28); vx, vy, vz = math.cos(a) * random.uniform(0.5, 2.5), math.sin(a) * random.uniform(0.5, 2.5), random.uniform(3, 7)
        sp.hide_render = True; sp.keyframe_insert('hide_render', frame=1); sp.hide_render = False; sp.keyframe_insert('hide_render', frame=f_hit)
        for f in range(f_hit, F + 1):
            tt = (f - f_hit) / fps; sp.location = (hit.x + vx * tt, hit.y + vy * tt, sea + vz * tt - 0.5 * g * tt * tt); sp.keyframe_insert('location', frame=f)
    S.add_air_traffic(F)
    P.setup_render(samples=28, frame_end=F, motion_blur=True); bpy.context.scene.render.motion_blur_shutter = 0.25; S.frame_range(scn)
