"""SCENE 07 — the camera rises from the realistic 2040 waterfront into the sky; a helicopter approaches over the harbour
and the camera closes on its open door where the passenger sits (hand-off into scene 08)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def heli_path(F):
    """Helicopter flies in from the south-east over the harbour toward Kivukoni, slowing to a hover near (250, -200, 260)."""
    col = S.link_asset('helicopter.blend', 'HELICOPTER'); root = bpy.data.objects['HELI_ROOT']
    pts = [(1, (1400, -1500, 420)), (int(F * 0.55), (600, -700, 330)), (F, (260, -210, 262))]
    for f, loc in pts: P.key(root, f, loc=loc)
    # heading: face along travel direction (+Y nose) with slight nose-down pitch and bank
    for f, loc in pts:
        nxt = pts[min(pts.index((f, loc)) + 1, len(pts) - 1)][1]; prv = pts[max(pts.index((f, loc)) - 1, 0)][1]
        dx, dy = nxt[0] - prv[0], nxt[1] - prv[1]; yaw = math.atan2(dy, dx) - math.pi / 2
        pitch = math.radians(-6 if f < F else -1); roll = math.radians(4 if f < F else 0)
        P.key(root, f, rot=(pitch, roll, yaw))
    P.ease_all(root)
    rot = bpy.data.objects['ROTOR_MAIN']; rot.rotation_euler = (0, 0, 0); rot.keyframe_insert('rotation_euler', frame=1)
    rot.rotation_euler = (0, 0, math.radians(360 * 6 * F / 24)); rot.keyframe_insert('rotation_euler', frame=F)
    tail = bpy.data.objects['ROTOR_TAIL']; tail.rotation_euler = (0, 0, 0); tail.keyframe_insert('rotation_euler', frame=1)
    tail.rotation_euler = (math.radians(360 * 30 * F / 24), 0, 0); tail.keyframe_insert('rotation_euler', frame=F)
    for o in (rot, tail):
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    S.cabin_passenger(bpy.data.objects['HELI_PASSENGER_SEAT'], F)
    return root

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('future', future=True, real_trees=True); S.ocean_material_upgrade(dusk=True); S.apply_bluehour_city(objs); S.terrain_urban_material()
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=400, depth=3000, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    heli = heli_path(F)
    # camera: from Kivukoni Front at 25 m straight up and back over the harbour, then swings to track the helicopter
    cam = P.add_camera(loc=(120, -40, 25), target=(-60, 120, 20), lens=32)
    S.cam_path(cam, [(1, (120, -40, 25)), (int(F * 0.45), (260, -250, 190)), (int(F * 0.8), (330, -330, 262)), (F, (300, -250, 265))],
               [(1, (-60, 120, 20)), (int(F * 0.45), (-20, 100, 60)), (int(F * 0.6), (420, -480, 300)), (F, (262, -214, 263))])
    P.setup_render(samples=28, frame_end=F, motion_blur=False); S.frame_range(scn)
