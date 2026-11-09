"""SCENE 12 — the diver discovers the phone. A diver with a torch glides in over the sand, spots the glow of the screen,
picks the phone up and turns it over; the screen lights up with the futuristic Posta footage; the diver pauses, amazed."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
spec = importlib.util.spec_from_file_location('s11', os.path.join(os.path.dirname(os.path.abspath(__file__)), 's11.py')); s11 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s11)

def build(scn, quality):
    F = scn['frames']; floor, reef = s11.open_reef(); sc = bpy.context.scene
    S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    rest = (reef.x + 2.2, reef.y - 3.0, floor + 0.05)
    phone.location = rest; phone.rotation_euler = (math.radians(180), 0, 0.4)
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=3.0)
    col, rig = S.add_character('DIVER', loc=(rest[0] - 9.0, rest[1] - 1.0, floor + 0.2), heading=math.radians(-90))
    fp = int(F * 0.45)  # pick-up frame
    CA.make_swim_pose_cycle(rig, 1, fp, kick_frames=36)
    P.key(rig, 1, loc=(rest[0] - 9.0, rest[1] - 1.0, floor + 0.3)); P.key(rig, fp, loc=(rest[0] - 1.35, rest[1] - 0.2, floor + 0.05))
    # after pick-up: rise to upright hover, hold the phone in front of the mask
    CA.set_rot(rig, 'hips', rx=-20, frame=fp + 30); CA.make_hold_phone_pose(rig, fp + 40)
    CA.set_rot(rig, 'head', rx=18, frame=fp + 40); CA.set_rot(rig, 'head', rx=10, ry=0, rz=8, frame=F)
    P.key(rig, fp + 40, loc=(rest[0] - 1.2, rest[1] - 0.2, floor + 0.6)); P.key(rig, F, loc=(rest[0] - 1.1, rest[1] - 0.25, floor + 0.7))
    hand = rig.pose.bones.get('hand.R')
    c = phone.constraints.new('CHILD_OF'); c.target = rig; c.subtarget = 'hand.R'; c.influence = 0.0
    c.keyframe_insert('influence', frame=fp - 1); c.influence = 1.0; c.keyframe_insert('influence', frame=fp)
    bpy.context.view_layer.update(); sc.frame_set(fp); c.set_inverse_pending = True if hasattr(c, 'set_inverse_pending') else None
    # turn the phone screen-up in the hand
    phone.keyframe_insert('rotation_euler', frame=fp); phone.rotation_euler = (math.radians(0), 0, 0.4); phone.keyframe_insert('rotation_euler', frame=fp + 36)
    mat = bpy.data.materials.get('MAT_PhoneScreen')
    if mat:
        b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); s = b.inputs['Emission Strength']
        s.default_value = 0.6; s.keyframe_insert('default_value', frame=1); s.default_value = 3.0; s.keyframe_insert('default_value', frame=fp + 40)
    cam = P.add_camera(loc=(rest[0] - 5, rest[1] - 4.5, floor + 1.6), target=phone, lens=30, dof_target=phone, fstop=2.4)
    S.cam_path(cam, [(1, (rest[0] - 5, rest[1] - 4.5, floor + 1.6)), (fp, (rest[0] - 2.5, rest[1] - 3.0, floor + 1.2)), (F, (rest[0] + 0.4, rest[1] - 1.7, floor + 1.0))])
    P.setup_render(samples=24, frame_end=F, volumes=True)
    cy = sc.cycles; cy.volume_bounces = 1; cy.volume_step_rate = 4.0; cy.volume_max_steps = 48; cy.transparent_max_bounces = 12
    sc.view_settings.exposure = -0.4; S.frame_range(scn)
