"""SCENE 12 — the diver discovers the phone. A diver with a torch glides in over the sand toward the glow of the screen,
reaches down, lifts the phone and turns it over in front of the mask; the footage of Posta 2040 plays; the diver pauses,
head tilted — amazed. The phone is baked to the hand bone frame by frame after the pick-up (no fragile constraints)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA
from mathutils import Vector, Matrix, Euler
import importlib.util
spec = importlib.util.spec_from_file_location('s11', os.path.join(os.path.dirname(os.path.abspath(__file__)), 's11.py')); s11 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s11)

def build(scn, quality):
    F = scn['frames']; floor, reef = s11.open_reef(); sc = bpy.context.scene
    S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    rest = Vector((reef.x + 2.2, reef.y - 3.0, floor + 0.05))
    phone.location = rest; phone.rotation_euler = (0, 0, 0.4)   # landed screen-up so its glow attracts the diver
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.4)
    col, rig = S.add_character('DIVER', loc=(rest.x - 9.0, rest.y, floor + 0.4), heading=math.radians(-90))
    fp = int(F * 0.42); fh = fp + 44
    CA.make_swim_pose_cycle(rig, 1, fp, kick_frames=36)
    P.key(rig, 1, loc=(rest.x - 9.0, rest.y, floor + 0.4))
    # pick-up: reach the right arm down/forward
    CA.set_rot(rig, 'upper_arm.R', rx=60, frame=fp); CA.set_rot(rig, 'forearm.R', rx=10, frame=fp)
    # solve rig position so the right hand touches the phone at the pick-up frame
    P.key(rig, fp, loc=(rest.x - 1.4, rest.y, floor + 0.4))
    sc.frame_set(fp); bpy.context.view_layer.update()
    hand = rig.matrix_world @ rig.pose.bones['hand.R'].tail
    rig.location += Vector((rest.x - hand.x, rest.y - hand.y, rest.z + 0.02 - hand.z)); rig.keyframe_insert('location', frame=fp)
    # rise to an upright hover and hold the phone in front of the mask; then a slow amazed head tilt
    CA.set_rot(rig, 'hips', rx=-25, frame=fh); CA.make_hold_phone_pose(rig, fh)
    CA.set_rot(rig, 'head', rx=20, frame=fh); CA.set_rot(rig, 'head', rx=14, rz=10, frame=F)
    CA.set_rot(rig, 'upper_arm.L', rx=30, ry=-10, frame=F)
    P.key(rig, fh, loc=(rig.location.x + 0.3, rig.location.y, floor + 0.2)); P.key(rig, F, loc=(rig.location.x + 0.35, rig.location.y, floor + 0.25))
    # bake the phone into the hand after pick-up: palm offset, turning screen toward the diver's face over 36 frames
    phone.keyframe_insert('location', frame=fp - 1); phone.keyframe_insert('rotation_euler', frame=fp - 1)
    for f in range(fp, F + 1):
        sc.frame_set(f); bpy.context.view_layer.update()
        pb = rig.pose.bones['hand.R']; M = rig.matrix_world @ pb.matrix
        k = min(1.0, (f - fp) / 36.0); k = k * k * (3 - 2 * k)
        local = Matrix.Translation((0, pb.length * 0.9, 0.02)) @ Euler((math.radians(-90 * k), 0, math.radians(90)), 'XYZ').to_matrix().to_4x4()
        W = M @ local; phone.matrix_world = W
        phone.keyframe_insert('location', frame=f); phone.keyframe_insert('rotation_euler', frame=f)
    # camera: low tracking beside the diver, settling into an over-the-shoulder two-shot on the phone and the mask
    cam = P.add_camera(loc=(rest.x - 6, rest.y - 3.5, floor + 1.1), target=phone, lens=30, dof_target=phone, fstop=3.2)
    sc.frame_set(F); bpy.context.view_layer.update(); pf = phone.matrix_world.translation.copy()
    S.cam_path(cam, [(1, (rest.x - 6, rest.y - 3.5, floor + 1.1)), (fp, (rest.x - 1.0, rest.y - 2.2, floor + 0.7)), (F, (pf.x + 0.9, pf.y - 1.3, pf.z + 0.35))])
    cam.data.clip_start = 0.01; cam.data.clip_end = 400; sc.frame_set(1)
    P.setup_render(samples=24, frame_end=F, volumes=True)
    cy = sc.cycles; cy.volume_bounces = 1; cy.volume_step_rate = 6.0; cy.volume_max_steps = 32; cy.transparent_max_bounces = 12
    sc.view_settings.exposure = -0.4; S.frame_range(scn)
