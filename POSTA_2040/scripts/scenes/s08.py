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
    S.screen_sequence(seq_dir=os.path.join(P.ROOT, 'renders', 's09_ui'), strength=2.6)
    lens = Vector((0.0217, 0.0673, -0.0065))     # main lens centre, phone-local (back face is -Z)
    tgt = P.make_empty('CAM_TARGET', (0, 0, 0)); tgt.parent = phone
    cam = P.add_camera(loc=(0, 0, 0), target=tgt, lens=32, dof_target=tgt, fstop=5.6)
    cam.parent = phone; cam.data.clip_start = 0.001; cam.data.sensor_width = 36
    keys = [(1, Vector((-0.06, -0.32, 0.42)), Vector((0, 0, 0))),             # over the shoulder on the live screen
            (int(F * 0.33), Vector((0.0, -0.02, 0.17)), Vector((0, 0.0, 0))),  # screen fills the frame
            (int(F * 0.52), Vector((0.16, 0.06, 0.0)), Vector((0.02, 0.06, 0))),  # sweep round the long edge
            (int(F * 0.72), lens + Vector((0.05, 0.03, -0.11)), lens),          # rear camera island
            (int(F * 0.9), lens + Vector((0, 0, -0.028)), lens),               # macro on the main lens
            (F, lens + Vector((0, 0, -0.0012)), lens + Vector((0, 0, 0.03)))]   # through the glass
    for f, c, t in keys:
        cam.location = c; cam.keyframe_insert('location', frame=f); tgt.location = t; tgt.keyframe_insert('location', frame=f)
    P.ease_all(cam); P.ease_all(tgt)
    for f, l in ((1, 32), (int(F * 0.33), 35), (int(F * 0.72), 50), (F, 60)):
        cam.data.lens = l; cam.data.keyframe_insert('lens', frame=f)
    for f, s in ((1, 5.6), (int(F * 0.72), 8.0), (F, 11.0)):
        cam.data.dof.aperture_fstop = s; cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
    # soft fill on the phone
    ld = bpy.data.lights.new('CABIN_FILL', 'AREA'); ld.energy = 25; ld.size = 0.6; ld.color = (1.0, 0.9, 0.8)
    lo = bpy.data.objects.new('CABIN_FILL', ld); bpy.context.scene.collection.objects.link(lo); lo.parent = phone; lo.location = (-0.3, -0.4, 0.5)
    c = lo.constraints.new('TRACK_TO'); c.target = phone; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    P.setup_render(samples=32, frame_end=F); S.frame_range(scn)
