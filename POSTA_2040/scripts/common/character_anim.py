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

Finger helpers (rigs built since the MakeHuman rebuild carry 15 finger bones per hand, children of hand.L/R:
thumb/index/middle/ring/pinky + .01/.02/.03 + .L/.R, local +X rotation = flexion; all helpers silently do nothing
on rigs without finger bones, so older assets keep working):
  curl_fingers(arm, side, amount, frame=None, thumb=None, spread=0.0, fingers=None)   0 = rest, 1 = fist
  set_finger(arm, side, finger, a1, a2, a3, frame=None, spread=0.0)                    explicit joint angles (deg)
  make_two_hand_phone_pose(arm, frame, width=0.168, chest_drop=0.22, forward=0.30, tilt=38)   both hands on a landscape phone
  two_hand_phone_matrix(arm)                       4x4 (armature space) where the phone sits in that pose
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
    for sd in ('L', 'R'):                     # relaxed, slightly curled hands while walking
        for f in (int(start_frame), int(end_frame)):
            curl_fingers(arm, sd, 0.22, frame=f, thumb=0.15)
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


FINGERS = ('thumb', 'index', 'middle', 'ring', 'pinky')
_CURL_MAX = {'thumb': (22.0, 38.0, 60.0), 'index': (82.0, 100.0, 68.0), 'middle': (85.0, 102.0, 70.0),
             'ring': (88.0, 104.0, 70.0), 'pinky': (90.0, 104.0, 70.0)}


def has_fingers(arm, side='R'):
    return ('index.01.%s' % side.upper()) in arm.pose.bones


def set_finger(arm, side, finger, a1=0.0, a2=0.0, a3=0.0, frame=None, spread=0.0):
    """Flex the three joints of one finger (degrees about the bone's local X = toward the palm);
    spread (deg) fans the first joint sideways about its local Z."""
    for i, a in enumerate((a1, a2, a3), 1):
        pb = arm.pose.bones.get('%s.0%d.%s' % (finger, i, side.upper()))
        if pb is None:
            return False
        pb.rotation_mode = 'QUATERNION'
        q = Quaternion((1, 0, 0), math.radians(a))
        if i == 1 and abs(spread) > 1e-6:
            q = Quaternion((0, 0, 1), math.radians(spread)) @ q
        pb.rotation_quaternion = q
        if frame is not None:
            pb.keyframe_insert('rotation_quaternion', frame=frame)
    return True


def curl_fingers(arm, side, amount, frame=None, thumb=None, spread=0.0, fingers=None):
    """Curl the fingers of one hand: amount 0 = relaxed rest pose, 1 = closed fist.  'thumb' (default = amount)
    curls the thumb separately; 'fingers' restricts the call to some of thumb/index/middle/ring/pinky.
    Does nothing (returns False) on rigs without finger bones."""
    if not has_fingers(arm, side):
        return False
    for k, fn in enumerate(FINGERS):
        if fingers is not None and fn not in fingers:
            continue
        a = (amount if thumb is None else thumb) if fn == 'thumb' else amount
        m = _CURL_MAX[fn]
        sp = 0.0 if fn == 'thumb' else spread * (1.5 - k) * 0.5
        set_finger(arm, side, fn, m[0] * a, m[1] * a, m[2] * a, frame=frame, spread=sp)
    return True


def _update():
    bpy.context.view_layer.update()


def _palm(arm, side):
    """Palm centre (armature space) of the posed hand: 45 % along the hand bone."""
    pb = arm.pose.bones['hand.%s' % side]
    return pb.head + (pb.tail - pb.head) * 0.45


_PHONE_GRIP = (0.010, 0.032, -0.016)   # palm centre relative to the phone's short-edge midpoint: along X (outward), Y (behind the back), Z


def _palm_normal(arm, side):
    """Unit palm normal of the posed hand (armature space)."""
    sg = -1.0 if side == 'L' else 1.0
    hd = arm.pose.bones['hand.%s' % side]
    ib = arm.pose.bones.get('index.01.%s' % side)
    if ib is not None:
        n = ib.bone.matrix_local.to_3x3() @ Vector((0, 0, 1))             # rest palm normal (finger roll axis)
    else:
        n = Vector((-sg, 0, 0))
    n = hd.matrix.to_3x3() @ (hd.bone.matrix_local.to_3x3().inverted() @ n)
    d = (hd.tail - hd.head).normalized()
    return (n - d * n.dot(d)).normalized()


def two_hand_phone_matrix(arm):
    """Where a landscape phone sits between the hands after make_two_hand_phone_pose, as a 4x4 in ARMATURE space
    (multiply by rig.matrix_world for world space):
      origin   = phone centre: midpoint of the two palm centres (45 % along hand.L / hand.R) moved 32 mm toward
                 the holder (the palms lie on the phone's back) and 16 mm up,
      +X       = from the left hand to the right hand  -> the phone's long side (168 mm),
      +Z       = up along the phone's short side (79 mm),
      +Y       = out of the BACK of the phone, away from the holder; the screen faces -Y, toward the face."""
    from mathutils import Matrix
    _update()
    pl, pr = _palm(arm, 'L'), _palm(arm, 'R')
    x = (pr - pl).normalized()
    n = _palm_normal(arm, 'L') + _palm_normal(arm, 'R')                   # palms press on the back -> they face -Y
    y = -(n - x * n.dot(x)).normalized()
    z = x.cross(y).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = (pl + pr) * 0.5 - y * _PHONE_GRIP[1] - z * _PHONE_GRIP[2]
    return m


def _aim_bone(arm, name, direction):
    """Rotate a pose bone about its head (shortest arc) so that it points along 'direction' (armature space)."""
    from mathutils import Matrix
    pb = arm.pose.bones[name]
    pb.rotation_mode = 'QUATERNION'
    cur = (pb.tail - pb.head).normalized()
    q = cur.rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()
    pb.matrix = Matrix.Translation(pb.head) @ q @ Matrix.Translation(-pb.head) @ pb.matrix
    pb.location = (0, 0, 0)
    _update()
    return pb


def make_two_hand_phone_pose(armature, frame, width=0.168, chest_drop=0.22, forward=0.30, tilt=38.0):
    """Both hands hold a phone in landscape in front of the chest (client reference two_hands_landscape_phone):
    forearms raised, a hand on each short edge ('width' apart), fingers flat across the back of the phone,
    thumbs wrapped round onto the front bezel.  chest_drop = how far below the shoulders the phone centre sits,
    forward = how far in front of the shoulders (metres), tilt = how far the screen leans back toward the face
    (degrees from vertical).  The arms are solved with a two-bone IK on the rig, so it works for every body
    size; place the phone with two_hand_phone_matrix(rig)."""
    from mathutils import Matrix
    arm = armature
    f = frame
    set_rot(arm, 'chest', rx=3, frame=f)
    set_rot(arm, 'neck', rx=10, frame=f)
    set_rot(arm, 'head', rx=16, frame=f)
    for sd in ('L', 'R'):
        for b in ('upper_arm', 'forearm', 'hand'):
            pb = arm.pose.bones['%s.%s' % (b, sd)]
            pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = Quaternion(); pb.location = (0, 0, 0)
    _update()
    sl, sr = arm.pose.bones['upper_arm.L'].head.copy(), arm.pose.bones['upper_arm.R'].head.copy()
    a = math.radians(tilt)
    x = Vector((1, 0, 0)); y = Vector((0, math.cos(a), -math.sin(a))); z = x.cross(y)
    c = (sl + sr) * 0.5 + Vector((0, forward, -chest_drop))
    for sd, sg, sh in (('L', -1.0, sl), ('R', 1.0, sr)):
        ua, fa, hd = (arm.pose.bones['%s.%s' % (b, sd)] for b in ('upper_arm', 'forearm', 'hand'))
        # fingers lie across the back of the phone pointing inward and a little up; the palm presses on the back,
        # the short edge sits in the crook between thumb and index, the thumb comes round onto the front bezel
        d_hand = (x * (-0.74 * sg) + y * 0.20 + z * 0.56).normalized()
        palm = c + x * sg * (width * 0.5 + _PHONE_GRIP[0]) + y * _PHONE_GRIP[1] + z * _PHONE_GRIP[2]
        wrist = palm - d_hand * (hd.length * 0.45)
        # two-bone IK: elbow below / outside the shoulder-wrist line
        l1, l2 = ua.length, fa.length
        v = wrist - sh; dist = min(v.length, (l1 + l2) * 0.999); vd = v.normalized()
        cos_a = max(-1.0, min(1.0, (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)))
        pole = Vector((0.75 * sg, -0.35, -1.0)); pole = (pole - vd * pole.dot(vd)).normalized()
        elbow = sh + vd * (l1 * cos_a) + pole * (l1 * math.sqrt(max(0.0, 1 - cos_a * cos_a)))
        _aim_bone(arm, 'upper_arm.%s' % sd, elbow - sh)
        _aim_bone(arm, 'forearm.%s' % sd, wrist - fa.head)
        # hand: fingers along d_hand, palm facing the phone edge
        n1 = -y; n1 = (n1 - d_hand * n1.dot(d_hand)).normalized()
        d0 = (hd.tail - hd.head).normalized()
        n0 = _palm_normal(arm, sd)
        f0 = Matrix((d0, n0, d0.cross(n0))).transposed(); f1 = Matrix((d_hand, n1, d_hand.cross(n1))).transposed()
        r = (f1 @ f0.inverted()).to_4x4()
        hd.rotation_mode = 'QUATERNION'
        hd.matrix = Matrix.Translation(hd.head) @ r @ Matrix.Translation(-hd.head) @ hd.matrix
        hd.location = (0, 0, 0)
        _update()
        for pb in (ua, fa, hd):
            pb.keyframe_insert('rotation_quaternion', frame=f)
        # fingers wrap behind the phone, thumb rests on the front bezel
        for fn, (a1, a2, a3) in (('index', (-14, -4, 0)), ('middle', (-12, -2, 0)), ('ring', (-10, 0, 2)), ('pinky', (-8, 2, 4))):
            set_finger(arm, sd, fn, a1, a2, a3, frame=f)
        set_finger(arm, sd, 'thumb', 30, 24, 26, frame=f)
    _update()
    return arm


def make_hold_phone_pose(armature, frame, side='R'):
    """Right (default) hand raised to chest height in front of the body, as if filming with a phone.
    On rigs with finger bones the hand also grips (fingers curled, thumb closing)."""
    arm = armature
    o = side.upper()
    other = 'L' if o == 'R' else 'R'
    inward = 1.0 if o == 'R' else -1.0
    set_rot(arm, f'upper_arm.{o}', rx=28, ry=22 * inward, frame=frame)
    set_rot(arm, f'forearm.{o}', rx=98, ry=12 * inward, frame=frame)
    set_rot(arm, f'hand.{o}', rx=25, rz=-15 * inward, frame=frame)
    curl_fingers(arm, o, 0.42, frame=frame, thumb=0.35)
    curl_fingers(arm, other, 0.08, frame=frame)
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
    for f in (int(start), int(end)):          # right hand grips the torch, left hand relaxed-open
        curl_fingers(arm, 'R', 0.72, frame=f, thumb=0.5)
        curl_fingers(arm, 'L', 0.12, frame=f)
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
