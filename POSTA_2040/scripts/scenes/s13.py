"""SCENE 13 — discovery and sharing. On the boat deck at golden hour, the diver (mask pushed up) reviews the footage;
the camera pushes in until the phone screen fills the frame. The share caption is composited afterwards (overlay_ui social)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA

def build(scn, quality):
    S.fresh(); F = scn['frames']
    S.world_golden(strength=0.08, sun_elev=10, sun_az=258, sun_energy=2.5)
    bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, -1.2)); sea = bpy.context.object; sea.name = 'SEA'
    sea.data.materials.append(P.new_mat('MAT_Ocean', (0.01, 0.06, 0.09, 1), 0.05)); S.ocean_material_upgrade()
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.6)); deck = bpy.context.object; deck.name = 'DECK'; deck.scale = (3.2, 7, 1.2)
    deck.data.materials.append(P.new_mat('MAT_Deck', (0.32, 0.22, 0.14, 1), 0.6))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.6, 0.25)); bench = bpy.context.object; bench.scale = (1.6, 0.5, 0.5)
    bench.data.materials.append(P.new_mat('MAT_Bench', (0.85, 0.86, 0.84, 1), 0.4))
    col, rig = S.add_character('DIVER', loc=(0, 0.6, 0.05), heading=math.pi)
    CA.make_seated_pose(rig, 1, seat_height=0.5); CA.make_hold_phone_pose(rig, 1); CA.set_rot(rig, 'head', rx=25, frame=1)
    CA.make_idle(rig, 1, F)
    S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    c = phone.constraints.new('CHILD_OF'); c.target = rig; c.subtarget = 'hand.R'
    bpy.context.view_layer.update()
    phone.location = (0, 0.08, 0.0); phone.rotation_euler = (math.radians(70), 0, math.radians(180))
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.6)
    # Posta 2040 skyline far away on the horizon: a few tall boxes in silhouette (real city out of frame range)
    for i in range(14):
        h = [60, 120, 90, 200, 150, 80, 260, 110, 170, 70, 140, 230, 95, 60][i]
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-900 + i * 70, 2600, h / 2 - 1)); b = bpy.context.object; b.scale = (40, 40, h)
        b.data.materials.append(P.new_mat('MAT_FarCity', (0.12, 0.14, 0.18, 1), 0.3, 0.6))
    bpy.context.view_layer.update()
    pw = phone.matrix_world.translation
    cam = P.add_camera(loc=(pw.x + 0.9, pw.y - 1.2, pw.z + 0.5), target=phone, lens=40, dof_target=phone, fstop=2.0)
    S.cam_path(cam, [(1, (pw.x + 0.9, pw.y - 1.4, pw.z + 0.55)), (int(F * 0.55), (pw.x + 0.25, pw.y - 0.5, pw.z + 0.35)), (F, (pw.x + 0.05, pw.y - 0.22, pw.z + 0.18))])
    cam.data.clip_start = 0.01
    S.enable_mist(start=200, depth=3000, color=(0.95, 0.8, 0.62, 1), strength=0.4)
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
