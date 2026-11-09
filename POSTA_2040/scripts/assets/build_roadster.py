"""Procedural Tesla-Roadster-style sports car. Run: /opt/blender/blender -b --python build_roadster.py [-- --no-render]
Conventions: car faces +Y, Z up, metres. CAR_ROOT at ground centre. Wheels WHEEL_FL/FR/RL/RR spin about local X (axle axis).
Output: blender/assets/roadster.blend (collection ROADSTER), previews/asset_roadster.png
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asset_common as C
P = C.P

NO_RENDER = '--no-render' in sys.argv
ROOT = C.ROOT
BLEND = os.path.join(ROOT, 'blender', 'assets', 'roadster.blend')
PREVIEW = os.path.join(ROOT, 'previews', 'asset_roadster.png')

C.reset_scene()
col = C.get_collection('ROADSTER')

# ----------------------------------------------------------------- materials
M_BODY = P.new_mat('MAT_CarBody', P.PAL['white'], rough=0.22, metal=0.0, coat=1.0)
M_BODY.node_tree.nodes['Principled BSDF'].inputs['Coat Roughness'].default_value = 0.03
M_BLACK = P.new_mat('MAT_CarTrim', (0.012, 0.012, 0.014, 1), rough=0.45)
M_GLASS = P.new_mat('MAT_CarGlass', (0.006, 0.006, 0.008, 1), rough=0.04, coat=1.0)
M_RED = P.new_mat('MAT_CarTailLight', (0.6, 0.01, 0.01, 1), rough=0.2, emission=(1.0, 0.02, 0.02, 1), estrength=8.0)
M_WHITE_LIGHT = P.new_mat('MAT_CarHeadLight', (0.9, 0.9, 0.9, 1), rough=0.2, emission=(1.0, 0.97, 0.9, 1), estrength=12.0)
M_CHROME = P.new_mat('MAT_CarExhaust', (0.6, 0.6, 0.62, 1), rough=0.3, metal=1.0)
M_RUBBER = P.new_mat('MAT_Tyre', (0.015, 0.015, 0.015, 1), rough=0.85)
M_RIM = P.new_mat('MAT_RimWhite', P.PAL['white'], rough=0.3, coat=0.8)
M_SPOKE = P.new_mat('MAT_Spoke', (0.01, 0.01, 0.011, 1), rough=0.35, metal=0.4)
BODY_MATS = [M_BODY, M_BLACK, M_GLASS]

# ----------------------------------------------------------------- root
root = bpy.data.objects.new('CAR_ROOT', None); root.empty_display_type = 'ARROWS'; root.empty_display_size = 0.5
col.objects.link(root)

# ----------------------------------------------------------------- body (lofted cross-sections)
# half profile rows (x, z): r0 bottom centre, r1 bottom outer, r2 sill top (black/white edge), r3 shoulder crease,
# r4 beltline (canopy base), r5 roof edge, r6 roof centre.  y: +2.3 nose .. -2.3 tail
STATIONS = [
    # y,    wb,  zb,   ws,  zs,   wsh, zsh,  wc,  zc,   wr,  zr,   zt
    ( 2.30, .62, .24,  .72, .34,  .76, .44,  .66, .50,  .40, .53,  .55),
    ( 2.05, .78, .15,  .89, .33,  .94, .50,  .80, .59,  .52, .64,  .66),
    ( 1.70, .85, .13,  .96, .34,  .99, .54,  .85, .65,  .54, .71,  .73),
    ( 1.30, .87, .13,  .97, .34, 1.00, .56,  .87, .69,  .56, .77,  .80),
    ( 0.85, .88, .13,  .98, .34, 1.00, .58,  .89, .72,  .58, .91,  .96),
    ( 0.40, .88, .13,  .98, .34, 1.00, .59,  .90, .74,  .57,1.04, 1.11),
    (-0.10, .88, .13,  .98, .34, 1.00, .60,  .90, .74,  .55,1.09, 1.15),
    (-0.60, .88, .13,  .98, .34, 1.00, .60,  .91, .75,  .56,1.07, 1.13),
    (-1.10, .87, .13,  .98, .35, 1.00, .61,  .93, .77,  .60,1.00, 1.06),
    (-1.60, .86, .13,  .98, .35, 1.00, .62,  .94, .78,  .64, .94, 1.00),
    (-2.00, .84, .15,  .96, .36,  .98, .64,  .93, .80,  .66, .88,  .93),
    (-2.30, .80, .24,  .92, .40,  .95, .66,  .90, .80,  .66, .86,  .89),
]
rings = []
for s in STATIONS:
    y, wb, zb, ws, zs, wsh, zsh, wc, zc, wr, zr, zt = s
    half = [(0, zb), (wb, zb), (ws, zs), (wsh, zsh), (wc, zc), (wr, zr), (0, zt)]
    rings.append(C.half_ring(y, half))

def body_mat(i, row, j):
    y0, y1 = STATIONS[i][0], STATIONS[i + 1][0]
    ymid = 0.5 * (y0 + y1)
    if row <= 1: return 1                      # lower sills / underbody black
    if row >= 4 and -2.1 < ymid < 1.5: return 2  # canopy glass (hood tip & rear deck tip stay white)
    return 0
body = C.loft('CAR_BODY', rings, col, BODY_MATS, body_mat, cap_mat=(0, 0))

# wheel arches (boolean cylinders, transfer black material onto arch interior)
WHEEL_R = 0.36; WB_Y = 1.45; TRACK_X = 0.80
for yy in (WB_Y, -WB_Y):
    for sx in (1, -1):
        cut = C.cylinder('cut', WHEEL_R + 0.075, 0.55, (sx * 1.02, yy, WHEEL_R), col, M_BLACK, axis='X', segments=40)
        cut.data.materials[0] = M_BLACK
        C.apply_bool(body, cut)
# black inner wheel-well boxes so the arch does not read through to the far side
for yy in (WB_Y, -WB_Y):
    for sx in (1, -1):
        C.box(f'CAR_WELL_{"F" if yy>0 else "R"}{"R" if sx>0 else "L"}', (sx * 0.72, yy, 0.38), (0.12, 0.92, 0.52), col, M_BLACK)

C.bevel(body, 0.014, 2, 28)
C.smooth(body, 32)

# ----------------------------------------------------------------- details
# front light bar (thin horizontal strip at the nose crease) + black lower grille/splitter
C.box('CAR_LIGHT_FRONT', (0, 2.265, 0.49), (1.30, 0.06, 0.028), col, M_WHITE_LIGHT)
C.box('CAR_GRILLE_FRONT', (0, 2.22, 0.36), (1.42, 0.22, 0.17), col, M_BLACK)
C.box('CAR_SPLITTER', (0, 2.12, 0.14), (1.80, 0.50, 0.05), col, M_BLACK)
# rear: black band with full-width red light bar
C.box('CAR_REAR_BAND', (0, -2.29, 0.76), (1.86, 0.10, 0.10), col, M_BLACK)
C.box('CAR_LIGHT_REAR', (0, -2.335, 0.765), (1.78, 0.03, 0.028), col, M_RED)
C.box('CAR_PLATE', (0, -2.33, 0.60), (0.34, 0.03, 0.14), col, M_BODY)
# rear diffuser block + quad exhaust
C.box('CAR_DIFFUSER', (0, -2.10, 0.30), (1.72, 0.50, 0.30), col, M_BLACK)
for i, x in enumerate((-0.48, -0.16, 0.16, 0.48)):
    e = C.cylinder(f'CAR_EXHAUST_{i}', 0.05, 0.16, (x, -2.36, 0.36), col, M_CHROME, axis='Y', segments=20)
    C.cylinder(f'CAR_EXHAUST_IN_{i}', 0.036, 0.17, (x, -2.365, 0.36), col, M_BLACK, axis='Y', segments=20)
# side vents (one per side) and sill blade
for sx in (1, -1):
    C.box(f'CAR_VENT_{"R" if sx>0 else "L"}', (sx * 0.985, 0.88, 0.50), (0.05, 0.26, 0.04), col, M_BLACK)
    C.box(f'CAR_SILL_{"R" if sx>0 else "L"}', (sx * 0.93, 0.0, 0.17), (0.14, 2.0, 0.10), col, M_BLACK)
# underbody plate
C.box('CAR_UNDERTRAY', (0, 0, 0.12), (1.70, 4.3, 0.04), col, M_BLACK)
# spoiler lip on the rear deck edge
C.box('CAR_SPOILER', (0, -2.30, 0.905), (1.32, 0.10, 0.03), col, M_BLACK)

# ----------------------------------------------------------------- wheels (5-spoke black, white rim)
def make_wheel(name, loc):
    tyre = C.cylinder(name, WHEEL_R, 0.27, (0, 0, 0), col, M_RUBBER, axis='X', segments=48)
    tyre.data.materials.append(M_RIM); tyre.data.materials.append(M_SPOKE)
    C.bevel(tyre, 0.035, 3, 30)
    C.apply_mods(tyre)
    # hollow the tyre inner (rim seat)
    cut = C.cylinder('cut', 0.29, 0.40, (0, 0, 0), col, M_RUBBER, axis='X', segments=48)
    C.apply_bool(tyre, cut)
    parts = [tyre]
    rim = C.tube('rim', 0.29, 0.245, 0.24, (0, 0, 0), col, M_RIM, axis='X', segments=48); parts.append(rim)
    hub = C.cylinder('hub', 0.075, 0.08, (0.10, 0, 0), col, M_SPOKE, axis='X', segments=24); parts.append(hub)
    for i in range(5):
        a = math.radians(90 + i * 72)
        sp = C.box('spoke', (0.095, 0.0, 0.0), (0.05, 0.065, 0.235), col, M_SPOKE)
        sp.location = (0.095, -0.145 * math.sin(a) * 0 + 0.0, 0.0)
        # offset spoke radially
        sp.location = (0.095, math.cos(a) * 0.14, math.sin(a) * 0.14)
        sp.rotation_euler = (a - math.radians(90), 0, 0)
        parts.append(sp)
    # join
    bpy.context.view_layer.update()
    with bpy.context.temp_override(object=tyre, active_object=tyre, selected_objects=parts, selected_editable_objects=parts):
        bpy.ops.object.join()
    C.smooth(tyre, 40)
    tyre.name = name; tyre.data.name = name
    tyre.location = loc
    C.parent(tyre, root)
    return tyre

wheels = {}
for nm, (sx, sy) in {'FL': (-1, 1), 'FR': (1, 1), 'RL': (-1, -1), 'RR': (1, -1)}.items():
    w = make_wheel('WHEEL_' + nm, (sx * TRACK_X, sy * WB_Y, WHEEL_R))
    if sx < 0: w.rotation_euler = (0, 0, math.pi)  # mirror so spokes face outward
    wheels[nm] = w

# parent everything else to root
for ob in list(col.objects):
    if ob is root or ob.parent is not None: continue
    C.parent(ob, root)
    if ob.type == 'MESH' and ob is not body and not ob.name.startswith('WHEEL'):
        C.smooth(ob, 40)

root['facing'] = '+Y'; root['wheel_spin_axis'] = 'local X'; root['length_m'] = 4.6
print('ROADSTER tris:', C.tri_count(col))
C.save(BLEND)
print('saved', BLEND)

# ----------------------------------------------------------------- preview
if not NO_RENDER:
    C.studio(size=5.0, cam_loc=(5.6, 6.4, 1.9), target=(0, -0.1, 0.5), lens=42)
    C.render(PREVIEW)
    print('rendered', PREVIEW)
