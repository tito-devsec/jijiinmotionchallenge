"""SCENE 09b — pull back from the HOT 70 screen (still showing Posta 2040) through the helicopter cabin: the poster hero,
headset on, films the blue-hour skyline through the open door (helicopter_cabin_filming.webp)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S
from mathutils import Vector

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('future', future=True); S.ocean_material_upgrade(dusk=True); S.apply_bluehour_city(objs); S.terrain_urban_material()
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=400, depth=3000, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    heli, seat = S.hover_helicopter(F); rig, phone = S.cabin_passenger(seat, F)
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.6, flip=True, offset=168)
    bpy.context.view_layer.update()
    A = S.seat_cams(seat, rig, phone); inv = seat.matrix_world.inverted()
    to_seat = lambda v: inv @ (phone.matrix_world @ Vector(v))
    tgt = P.make_empty('CAM_TARGET', (0, 0, 0)); tgt.parent = seat
    cam = P.add_camera(loc=(0, 0, 0), target=tgt, lens=40, dof_target=tgt, fstop=4.0); cam.parent = seat; cam.data.clip_start = 0.005
    keys = [(1, to_seat((0, 0, 0.16)), A['phone']),                                   # the screen fills the frame
            (int(F * 0.45), A['phone'] + (A['shoulder'] - A['phone']) * 0.45, A['phone']),
            (F, A['shoulder'], A['out'])]                                          # beside the passenger: phone, door, skyline
    for f, c, t in keys:
        cam.location = c; cam.keyframe_insert('location', frame=f); tgt.location = t; tgt.keyframe_insert('location', frame=f)
    P.ease_all(cam); P.ease_all(tgt)
    for f, l in ((1, 40), (F, 20)):
        cam.data.lens = l; cam.data.keyframe_insert('lens', frame=f)
    S.add_air_traffic(F)
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
