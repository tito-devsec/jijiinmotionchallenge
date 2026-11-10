"""SCENE 08 — inside the helicopter: the passenger records Posta on the Infinix HOT 70. The camera starts over the
passenger's shoulder on the live camera screen, slides round the phone's edge to the rear camera island and dives into
the main lens (hand-off to scene 09). The camera and its target are parented to the phone, so the hover never breaks
the macro move."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA
from mathutils import Vector

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('future', future=True); S.ocean_material_upgrade(dusk=True); S.apply_bluehour_city(objs); S.terrain_urban_material()
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=400, depth=3000, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    heli, seat = S.hover_helicopter(F)
    rig, phone = S.cabin_passenger(seat, F)
    # before the lens dive the hero lets go with the right hand (it covers the rear camera) and holds the phone left-handed
    def _key(pb, f):
        pb.keyframe_insert('rotation_quaternion' if pb.rotation_mode == 'QUATERNION' else 'rotation_euler', frame=f)
    right = [pb for pb in rig.pose.bones if pb.name.endswith('.R') and not pb.name.startswith(('thigh', 'shin', 'foot'))]
    fA, fB = int(F * 0.40), int(F * 0.54)
    for pb in right: _key(pb, 1); _key(pb, fA)
    for pb in right:
        if pb.rotation_mode == 'QUATERNION': pb.rotation_quaternion = (1, 0, 0, 0)
        else: pb.rotation_euler = (0, 0, 0)
        _key(pb, fB)
    CA.set_rot(rig, 'upper_arm.R', rx=18, ry=-12, frame=fB); CA.set_rot(rig, 'forearm.R', rx=35, frame=fB)
    bpy.context.scene.frame_set(1)
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.6, flip=True)
    bpy.context.view_layer.update()
    A = S.seat_cams(seat, rig, phone); Y = A['n']
    tgt = P.make_empty('CAM_TARGET', (0, 0, 0)); tgt.parent = seat
    cam = P.add_camera(loc=(0, 0, 0), target=tgt, lens=28, dof_target=tgt, fstop=5.6); cam.parent = seat; cam.data.clip_start = 0.001
    keys = [(1, A['shoulder'], A['out']),                                               # beside the passenger: filming the skyline
            (int(F * 0.35), A['shoulder'] + (A['phone'] - A['shoulder']) * 0.5 + Vector((0, 0, 0.05)), A['phone']),
            (int(F * 0.6), A['lens'] + Y * 0.35 + Vector((0.08, 0, 0.04)), A['lens']),   # outside the door, facing the camera island
            (int(F * 0.85), A['lens'] + Y * 0.03, A['lens']),                          # macro on the main lens
            (F, A['lens'] + Y * 0.0012, A['lens'] - Y * 0.05)]                         # through the glass
    for f, c, t in keys:
        cam.location = c; cam.keyframe_insert('location', frame=f); tgt.location = t; tgt.keyframe_insert('location', frame=f)
    P.ease_all(cam); P.ease_all(tgt)
    for f, l in ((1, 28), (int(F * 0.35), 35), (int(F * 0.6), 50), (F, 60)):
        cam.data.lens = l; cam.data.keyframe_insert('lens', frame=f)
    for f, st in ((1, 4.0), (int(F * 0.6), 8.0), (F, 11.0)):
        cam.data.dof.aperture_fstop = st; cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
    # soft fill on the phone (kept from the cabin rig)
    ld = bpy.data.lights.new('CABIN_FILL', 'AREA'); ld.energy = 25; ld.size = 0.6; ld.color = (1.0, 0.9, 0.8)
    lo = bpy.data.objects.new('CABIN_FILL', ld); bpy.context.scene.collection.objects.link(lo); lo.parent = phone; lo.location = (-0.3, -0.4, 0.5)
    c = lo.constraints.new('TRACK_TO'); c.target = phone; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    S.add_air_traffic(F)
    P.setup_render(samples=32, frame_end=F); S.frame_range(scn)
