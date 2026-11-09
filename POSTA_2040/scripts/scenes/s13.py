"""SCENE 13 — discovery and sharing. On the boat deck at golden hour, the diver (mask pushed up) reviews the footage;
the camera pushes in until the phone screen fills the frame. The share caption is composited afterwards (overlay_ui social)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA
from mathutils import Vector

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
    from mathutils import Matrix, Euler
    sc = bpy.context.scene
    for f in range(1, F + 1, 4):   # bake phone into the right hand (screen toward the face)
        sc.frame_set(f); bpy.context.view_layer.update()
        pb = rig.pose.bones['hand.R']; M = rig.matrix_world @ pb.matrix
        phone.matrix_world = M @ Matrix.Translation((0, pb.length * 0.9, 0.02)) @ Euler((math.radians(-90), 0, math.radians(90)), 'XYZ').to_matrix().to_4x4()
        phone.keyframe_insert('location', frame=f); phone.keyframe_insert('rotation_euler', frame=f)
    sc.frame_set(1)
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.6)
    # Posta 2040 skyline far away on the horizon: a few tall boxes in silhouette (real city out of frame range)
    for i in range(14):
        h = [60, 120, 90, 200, 150, 80, 260, 110, 170, 70, 140, 230, 95, 60][i]
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-900 + i * 70, 2600, h / 2 - 1)); b = bpy.context.object; b.scale = (40, 40, h)
        b.data.materials.append(P.new_mat('MAT_FarCity', (0.12, 0.14, 0.18, 1), 0.3, 0.6))
    bpy.context.view_layer.update()
    pw = phone.matrix_world.translation.copy(); head = rig.matrix_world @ rig.pose.bones['head'].head
    # over the diver's right shoulder: start wide on diver + phone + far skyline, push in until the screen fills the frame
    sh = head + (head - pw).normalized() * 0.0
    back = Vector((head.x - pw.x, head.y - pw.y, 0)).normalized()
    c0 = head + back * 0.9 + Vector((0.45, 0, 0.35)); c1 = head + back * 0.15 + Vector((0.18, 0, 0.08)); c2 = pw + (head - pw).normalized() * 0.2
    cam = P.add_camera(loc=c0, target=phone, lens=35, dof_target=phone, fstop=2.8)
    S.cam_path(cam, [(1, tuple(c0)), (int(F * 0.45), tuple(c1)), (F, tuple(c2))])
    cam.data.clip_start = 0.01
    S.enable_mist(start=200, depth=3000, color=(0.95, 0.8, 0.62, 1), strength=0.4)
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
