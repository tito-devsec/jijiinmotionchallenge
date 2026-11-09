"""Pose / animation helpers for the procedural POSTA_2040 humanoid rigs (RIG_<name>).

Bone names: hips, spine, chest, neck, head, upper_arm.L/R, forearm.L/R, hand.L/R, thigh.L/R, shin.L/R, foot.L/R.
Characters face +Y, Z up; anatomical left (.L) is at -X, right (.R) at +X.

All rotation helpers take degrees about the WORLD axes of the rest pose (X = sideways, Y = forward, Z = up),
converted into the bone's local frame, so callers never need to think about bone rolls:
  +rx on a leg/arm  -> swings the limb FORWARD (+Y);  -rx -> backward
  +rx on head/spine -> tilts forward (looking down)
  +ry on a right (+X) limb -> brings it inward (toward the body); on a left limb -> outward
  +rz -> turns toward the character's left (counter-clockwise seen from above)

API:
  set_rot(arm, bone, rx, ry, rz, frame=None)     rest-frame world-axis rotation (deg), optionally keyed
  set_loc(arm, bone, (x,y,z), frame=None)         offset in metres (world/armature axes), optionally keyed
  clear_pose(arm)                                  reset every bone (no keyframes removed)
  clear_animation(arm)                             drop the action
  make_walk_cycle(arm, start, end, stride_frames=24, travel=0.0, amp=1.0)
  make_idle(arm, start, end, period=72)
  make_hold_phone_pose(arm, frame, side='R')
  make_swim_pose_cycle(arm, start, end, kick_frames=36)
  make_seated_pose(arm, frame, seat_height=0.45)
  make_cyclic(arm)                                 add Cycles F-modifiers to every f-curve
"""
import math
import bpy
from mathutils import Vector, Quaternion

ROT_BONES = ('hips', 'spine', 'chest', 'neck', 'head',
             'upper_arm.L', 'upper_arm.R', 'forearm.L', 'forearm.R', 'hand.L', 'hand.R',
             'thigh.L', 'thigh.R', 'shin.L', 'shin.R', 'foot.L', 'foot.R')


def _rest(pb):
    return pb.bone.matrix_local.to_3x3()


def _q_world(pb, axis, deg):
    """Quaternion (bone-local) that rotates the bone about a rest-pose world axis."""
    if abs(deg) < 1e-9:
        return Quaternion()
    a = _rest(pb).inverted() @ Vector(axis)
    return Quaternion(a.normalized(), math.radians(deg))


def set_rot(arm, bone, rx=0.0, ry=0.0, rz=0.0, frame=None):
    pb = arm.pose.bones[bone]
    pb.rotation_mode = 'QUATERNION'
    q = _q_world(pb, (0, 0, 1), rz) @ _q_world(pb, (0, 1, 0), ry) @ _q_world(pb, (1, 0, 0), rx)
    pb.rotation_quaternion = q
    if frame is not None:
        pb.keyframe_insert('rotation_quaternion', frame=frame)
    return pb


def set_loc(arm, bone, offset, frame=None):
    pb = arm.pose.bones[bone]
    pb.location = _rest(pb).inverted() @ Vector(offset)
    if frame is not None:
        pb.keyframe_insert('location', frame=frame)
    return pb


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion()
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def clear_animation(arm):
    if arm.animation_data:
        arm.animation_data_clear()
    clear_pose(arm)


def make_cyclic(arm):
    ad = arm.animation_data
    if not ad or not ad.action:
        return
    for fc in ad.action.fcurves:
        if not any(m.type == 'CYCLES' for m in fc.modifiers):
            fc.modifiers.new('CYCLES')


def _pos(x):
    return max(0.0, x)


def make_walk_cycle(armature, start_frame, end_frame, stride_frames=24, travel=0.0, amp=1.0):
    """Keyframes a believable walk cycle on every frame from start to end.
    stride_frames = frames for a full cycle (two steps). travel = metres moved forward (+Y) per cycle
    (0 = walk in place). amp scales the limb swing (1 = normal walk)."""
    arm = armature
    for f in range(int(start_frame), int(end_frame) + 1):
        t = (f - start_frame) / float(stride_frames)
        ph = 2 * math.pi * t
        s, c = math.sin(ph), math.cos(ph)
        # legs -----------------------------------------------------------
        thL, thR = 28 * amp * s, -28 * amp * s
        kneeL = 10 + 42 * amp * _pos(c) ** 1.4 + 6 * _pos(-s)
        kneeR = 10 + 42 * amp * _pos(-c) ** 1.4 + 6 * _pos(s)
        set_rot(arm, 'thigh.L', rx=thL, frame=f)
        set_rot(arm, 'thigh.R', rx=thR, frame=f)
        set_rot(arm, 'shin.L', rx=-kneeL, frame=f)
        set_rot(arm, 'shin.R', rx=-kneeR, frame=f)
        # feet: keep roughly flat, toe-down at push-off, heel up at strike
        set_rot(arm, 'foot.L', rx=-(thL - kneeL) * 0.55 - 8 * _pos(-s), frame=f)
        set_rot(arm, 'foot.R', rx=-(thR - kneeR) * 0.55 - 8 * _pos(s), frame=f)
        # arms (counter-swing) --------------------------------------------
        aL, aR = -24 * amp * s, 24 * amp * s
        set_rot(arm, 'upper_arm.L', rx=aL, ry=-4, frame=f)       # slight abduction
        set_rot(arm, 'upper_arm.R', rx=aR, ry=4, frame=f)
        set_rot(arm, 'forearm.L', rx=18 + 16 * _pos(-s), frame=f)
        set_rot(arm, 'forearm.R', rx=18 + 16 * _pos(s), frame=f)
        set_rot(arm, 'hand.L', rx=5, frame=f)
        set_rot(arm, 'hand.R', rx=5, frame=f)
        # torso / hips ---------------------------------------------------
        bob = 0.018 * (math.cos(2 * ph) - 1.0) * 0.5 * amp         # 0 .. -0.018
        sway = 0.012 * s
        set_loc(arm, 'hips', (sway, travel * t, bob), frame=f)
        set_rot(arm, 'hips', rx=2, ry=3 * s, rz=6 * s, frame=f)
        set_rot(arm, 'spine', rx=1, rz=-3 * s, frame=f)
        set_rot(arm, 'chest', rx=2, rz=-5 * s, frame=f)
        set_rot(arm, 'neck', rx=-2, frame=f)
        set_rot(arm, 'head', rx=-3, rz=2 * s, ry=-1.5 * s, frame=f)
    return arm


def make_idle(armature, start, end, period=72):
    """Subtle breathing / weight-shift idle."""
    arm = armature
    for f in range(int(start), int(end) + 1, 2):
        ph = 2 * math.pi * (f - start) / float(period)
        b = math.sin(ph)
        set_rot(arm, 'chest', rx=1.5 * b, frame=f)
        set_rot(arm, 'spine', rx=0.5 * b, rz=1.0 * math.sin(ph * 0.5), frame=f)
        set_rot(arm, 'neck', rx=-1.0 * b, frame=f)
        set_rot(arm, 'head', rz=3.0 * math.sin(ph * 0.5 + 1.0), ry=1.5 * math.sin(ph * 0.37), frame=f)
        set_rot(arm, 'upper_arm.L', ry=-3 - 1.5 * b, rx=2, frame=f)
        set_rot(arm, 'upper_arm.R', ry=3 + 1.5 * b, rx=2, frame=f)
        set_rot(arm, 'forearm.L', rx=10, frame=f)
        set_rot(arm, 'forearm.R', rx=10, frame=f)
        set_loc(arm, 'hips', (0.006 * math.sin(ph * 0.5), 0, -0.004 - 0.003 * b), frame=f)
        set_rot(arm, 'hips', rz=1.5 * math.sin(ph * 0.5), frame=f)
        set_rot(arm, 'thigh.L', rz=-1.5 * math.sin(ph * 0.5), frame=f)
        set_rot(arm, 'thigh.R', rz=-1.5 * math.sin(ph * 0.5), frame=f)
    return arm


def make_hold_phone_pose(armature, frame, side='R'):
    """Right (default) hand raised to chest height in front of the body, as if filming with a phone."""
    arm = armature
    o = side.upper()
    other = 'L' if o == 'R' else 'R'
    inward = 1.0 if o == 'R' else -1.0
    set_rot(arm, f'upper_arm.{o}', rx=28, ry=22 * inward, frame=frame)
    set_rot(arm, f'forearm.{o}', rx=98, ry=12 * inward, frame=frame)
    set_rot(arm, f'hand.{o}', rx=25, rz=-15 * inward, frame=frame)
    set_rot(arm, f'upper_arm.{other}', rx=4, ry=-5 * inward, frame=frame)
    set_rot(arm, f'forearm.{other}', rx=12, frame=frame)
    set_rot(arm, 'chest', rx=2, rz=4 * inward, frame=frame)
    set_rot(arm, 'neck', rx=4, frame=frame)
    set_rot(arm, 'head', rx=8, frame=frame)
    set_loc(arm, 'hips', (0, 0, -0.005), frame=frame)
    return arm


def make_swim_pose_cycle(armature, start, end, kick_frames=36):
    """Horizontal swimming (face down, head toward +Y) with alternating flutter kicks.
    The root empty stays at the feet centre; hips are lifted to ~1.0 m so the body floats around z=1."""
    arm = armature
    for f in range(int(start), int(end) + 1):
        ph = 2 * math.pi * (f - start) / float(kick_frames)
        s = math.sin(ph)
        set_loc(arm, 'hips', (0, 0, 0.1 + 0.02 * math.sin(ph * 0.5)), frame=f)
        set_rot(arm, 'hips', rx=-88 + 2 * s, frame=f)
        set_rot(arm, 'spine', rx=-4 + 3 * s, frame=f)
        set_rot(arm, 'chest', rx=-6 - 2 * s, frame=f)
        set_rot(arm, 'neck', rx=-20, frame=f)
        set_rot(arm, 'head', rx=-22, frame=f)
        # arms stretched forward-down, slightly spread
        set_rot(arm, 'upper_arm.L', rx=110, ry=-18, frame=f)
        set_rot(arm, 'upper_arm.R', rx=100, ry=18, frame=f)
        set_rot(arm, 'forearm.L', rx=25 + 4 * s, frame=f)
        set_rot(arm, 'forearm.R', rx=45 - 4 * s, frame=f)
        set_rot(arm, 'hand.L', rx=10, frame=f)
        set_rot(arm, 'hand.R', rx=10, frame=f)
        # flutter kick
        set_rot(arm, 'thigh.L', rx=18 * s - 4, frame=f)
        set_rot(arm, 'thigh.R', rx=-18 * s - 4, frame=f)
        set_rot(arm, 'shin.L', rx=-(12 + 18 * _pos(-s)), frame=f)
        set_rot(arm, 'shin.R', rx=-(12 + 18 * _pos(s)), frame=f)
        set_rot(arm, 'foot.L', rx=-45, frame=f)   # pointed toes / fins
        set_rot(arm, 'foot.R', rx=-45, frame=f)
    return arm




def make_seated_pose(armature, frame, seat_height=0.45):
    """Seated: hips and knees bent 90 deg, hands resting on thighs. Hips drop to seat_height."""
    arm = armature
    hip_z = arm.pose.bones['hips'].bone.head_local.z
    set_loc(arm, 'hips', (0, 0, seat_height - hip_z), frame=frame)
    set_rot(arm, 'hips', rx=-3, frame=frame)
    set_rot(arm, 'spine', rx=4, frame=frame)
    set_rot(arm, 'chest', rx=2, frame=frame)
    set_rot(arm, 'neck', rx=0, frame=frame)
    set_rot(arm, 'head', rx=2, frame=frame)
    for sd, sg in (('L', -1), ('R', 1)):
        set_rot(arm, f'thigh.{sd}', rx=88, ry=-6 * sg, frame=frame)   # knees slightly apart
        set_rot(arm, f'shin.{sd}', rx=-92, frame=frame)
        set_rot(arm, f'foot.{sd}', rx=4, frame=frame)
        set_rot(arm, f'upper_arm.{sd}', rx=22, ry=6 * sg, frame=frame)
        set_rot(arm, f'forearm.{sd}', rx=58, ry=10 * sg, frame=frame)
        set_rot(arm, f'hand.{sd}', rx=-10, frame=frame)
    return arm
