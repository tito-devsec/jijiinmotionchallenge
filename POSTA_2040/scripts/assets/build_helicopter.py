"""Procedural civilian passenger helicopter (stylised angular navy fuselage). Run: /opt/blender/blender -b --python build_helicopter.py [-- --no-render]
Conventions: nose faces +Y, Z up, metres. HELI_ROOT at ground centre under the main mast.
ROTOR_MAIN spins about its local Z (mast axis). ROTOR_TAIL spins about its local X (axle axis, mounted on the -X side of the tail fin).
Open passenger doorway is on the +X side; HELI_PASSENGER_SEAT empty sits on the bench with local +Y pointing out of the door (+X world).
No weapons (civilian aircraft).
Output: blender/assets/helicopter.blend (collection HELICOPTER), previews/asset_helicopter.png
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asset_common as C
P = C.P

NO_RENDER = '--no-render' in sys.argv
ROOT = C.ROOT
BLEND = os.path.join(ROOT, 'blender', 'assets', 'helicopter.blend')
PREVIEW = os.path.join(ROOT, 'previews', 'asset_helicopter.png')

C.reset_scene()
col = C.get_collection('HELICOPTER')

# ----------------------------------------------------------------- materials
M_HULL = P.new_mat('MAT_HeliHull', (0.012, 0.018, 0.045, 1), rough=0.22, metal=0.35, coat=1.0)
M_HULL.node_tree.nodes['Principled BSDF'].inputs['Coat Roughness'].default_value = 0.05
M_DARK = P.new_mat('MAT_HeliDark', (0.008, 0.008, 0.01, 1), rough=0.5)
M_GLASS = P.new_mat('MAT_HeliGlass', (0.82, 0.86, 0.92, 1), rough=0.10, coat=1.0, transmission=0.55, ior=1.45)
M_INTERIOR = P.new_mat('MAT_HeliInterior', (0.09, 0.09, 0.1, 1), rough=0.6)
M_SEAT = P.new_mat('MAT_SeatUpholstery', (0.95, 0.94, 0.92, 1), rough=0.8)
M_SEAT_PAD = P.new_mat('MAT_SeatPad', (0.92, 0.55, 0.58, 1), rough=0.9)
M_BLADE_W = P.new_mat('MAT_BladeWhite', (0.85, 0.85, 0.85, 1), rough=0.4)
M_BLADE_D = P.new_mat('MAT_BladeDark', (0.02, 0.025, 0.045, 1), rough=0.35, metal=0.3)
M_METAL = P.new_mat('MAT_HeliMetal', (0.25, 0.25, 0.27, 1), rough=0.4, metal=1.0)
M_RUBBER = P.new_mat('MAT_HeliTyre', (0.015, 0.015, 0.015, 1), rough=0.85)
HULL_MATS = [M_HULL, M_GLASS, M_DARK, M_INTERIOR]

root = bpy.data.objects.new('HELI_ROOT', None); root.empty_display_type = 'ARROWS'; root.empty_display_size = 1.0
col.objects.link(root)

# ----------------------------------------------------------------- fuselage + tail boom (angular loft)
# half profile rows (x, z): r0 keel, r1 lower chine, r2 max beam, r3 upper chine, r4 spine.  y: +5.7 nose .. -6.7 tail
STATIONS = [
    # y,     zb,   (x1,z1),      (x2,z2),      (x3,z3),      zt
    ( 5.70, 1.45, (0.10, 1.42), (0.18, 1.58), (0.12, 1.78), 1.85),
    ( 5.10, 1.12, (0.55, 1.10), (0.85, 1.52), (0.68, 2.05), 2.22),
    ( 4.30, 0.82, (0.88, 0.88), (1.12, 1.52), (0.92, 2.40), 2.66),
    ( 3.30, 0.66, (1.00, 0.74), (1.22, 1.52), (1.05, 2.62), 2.92),
    ( 2.20, 0.60, (1.02, 0.70), (1.24, 1.55), (1.08, 2.70), 3.00),
    ( 0.80, 0.60, (1.02, 0.70), (1.24, 1.55), (1.08, 2.70), 3.00),
    (-0.60, 0.62, (1.00, 0.72), (1.22, 1.55), (1.05, 2.70), 3.00),
    (-1.60, 0.85, (0.85, 0.95), (1.05, 1.65), (0.88, 2.62), 2.90),
    (-2.50, 1.35, (0.45, 1.42), (0.55, 1.92), (0.45, 2.48), 2.68),
    (-3.60, 1.70, (0.30, 1.75), (0.38, 2.05), (0.30, 2.40), 2.52),
    (-5.00, 1.90, (0.25, 1.95), (0.32, 2.20), (0.25, 2.48), 2.55),
    (-6.20, 2.00, (0.22, 2.04), (0.30, 2.26), (0.22, 2.44), 2.50),
    (-6.70, 2.10, (0.14, 2.12), (0.18, 2.26), (0.14, 2.40), 2.44),
]
rings = []
for s in STATIONS:
    y, zb, p1, p2, p3, zt = s
    rings.append(C.half_ring(y, [(0, zb), p1, p2, p3, (0, zt)]))

def hull_mat(i, row, j):
    ymid = 0.5 * (STATIONS[i][0] + STATIONS[i + 1][0])
    if row == 3 and 2.2 < ymid < 5.5: return 1          # large white-tinted canopy panel (top-front)
    if row == 2 and 3.3 < ymid < 5.3: return 1          # canopy side windows
    return 0
fus = C.loft('HELI_FUSELAGE', rings, col, HULL_MATS, hull_mat, cap_mat=(0, 0))

# hollow cabin + doorway on +X side (boolean, transfer dark interior material)
cab_in = C.box('cut_cabin', (0.0, 0.85, 1.55), (2.05, 2.5, 1.55), col, M_INTERIOR)
C.apply_bool(fus, cab_in)
door = C.box('cut_door', (1.2, 0.85, 1.65), (0.8, 2.1, 1.3), col, M_INTERIOR)
C.apply_bool(fus, door)
C.bevel(fus, 0.025, 2, 28)
C.smooth(fus, 30)

# canopy centre pillar (dark spine over the glass) and nose chin
C.box('HELI_CANOPY_PILLAR', (0, 3.9, 2.78), (0.22, 3.2, 0.10), col, M_DARK, rot=(math.radians(-14), 0, 0))
for sx in (1, -1):
    C.box(f'HELI_SIDE_FAIRING_{"R" if sx>0 else "L"}', (sx * 1.14, 3.1, 1.45), (0.25, 1.1, 0.45), col, M_HULL, rot=(0, 0, math.radians(sx * 8)))

# cabin floor and bench with two seats on the -X wall facing the +X door
C.box('HELI_CABIN_FLOOR', (0.0, 0.85, 0.80), (2.0, 2.4, 0.06), col, M_INTERIOR)
def seat(name, y):
    base = C.box(name, (-0.50, y, 1.02), (0.62, 0.60, 0.16), col, M_SEAT_PAD)
    back = C.box(name + '_BACK', (-0.78, y, 1.38), (0.14, 0.60, 0.72), col, M_SEAT)
    arm = C.box(name + '_SIDE', (-0.50, y, 1.06), (0.62, 0.07, 0.30), col, M_SEAT)
    arm.location.y = y - 0.30 if 'R' in name else y + 0.30
    for o in (back, arm): C.parent(o, base)
    return base
# facing +X: passenger's left is +Y (forward)
seat_l = seat('HELI_SEAT_L', 1.17)
seat_r = seat('HELI_SEAT_R', 0.53)
pax = bpy.data.objects.new('HELI_PASSENGER_SEAT', None); pax.empty_display_type = 'ARROWS'; pax.empty_display_size = 0.5
col.objects.link(pax); pax.location = (-0.50, 0.85, 1.10); pax.rotation_euler = (0, 0, math.radians(-90))  # local +Y -> world +X (out of the door)

# engine deck housing, exhaust, side intakes, vent panel over the door
eng = C.box('HELI_ENGINE_DECK', (0, 0.0, 3.18), (1.25, 3.4, 0.50), col, M_HULL)
C.bevel(eng, 0.10, 3, 30)
for sx in (1, -1):
    ib = C.box(f'HELI_INTAKE_{"R" if sx>0 else "L"}', (sx * 1.05, 0.9, 2.78), (0.55, 1.3, 0.42), col, M_HULL, rot=(0, math.radians(sx * -20), 0))
    C.bevel(ib, 0.05, 2, 30)
    C.box(f'HELI_INTAKE_MOUTH_{"R" if sx>0 else "L"}', (sx * 1.26, 1.45, 2.78), (0.14, 0.26, 0.26), col, M_DARK, rot=(0, math.radians(sx * -20), 0))
    C.cylinder(f'HELI_EXHAUST_{"R" if sx>0 else "L"}', 0.16, 0.5, (sx * 0.45, -1.9, 3.10), col, M_DARK, axis='Y', segments=16)
for i in range(4):
    C.box(f'HELI_VENT_{i}', (1.19, 1.5 - i * 0.32, 2.42), (0.06, 0.24, 0.22), col, M_DARK, rot=(0, 0, 0))
C.box('HELI_VENT_FRAME', (1.17, 1.02, 2.42), (0.04, 1.45, 0.32), col, M_HULL)

# tail: fin + V/anhedral tail plane (gull wing) built as lofted chord sections
def chord_ring(x, y, z, chord, thick):
    return [Vector((x, y + chord / 2, z)), Vector((x, y + chord * 0.1, z + thick / 2)), Vector((x, y - chord / 2, z)), Vector((x, y + chord * 0.1, z - thick / 2))]
for sx in (1, -1):
    secs = [chord_ring(sx * 0.15, -5.9, 2.25, 1.6, 0.26), chord_ring(sx * 1.5, -6.15, 2.15, 1.2, 0.18), chord_ring(sx * 2.9, -6.6, 1.15, 0.8, 0.10), chord_ring(sx * 3.1, -6.75, 1.0, 0.4, 0.06)]
    tp = C.loft(f'HELI_TAILPLANE_{"R" if sx>0 else "L"}', secs, col, [M_HULL], None, cap_mat=(0, 0))
    C.smooth(tp, 25)
fin = C.loft('HELI_FIN', [chord_ring(0, -6.1, 2.45, 1.3, 0.3), chord_ring(0, -6.45, 2.95, 0.9, 0.18), chord_ring(0, -6.7, 3.2, 0.5, 0.1)], col, [M_HULL], None)
# rotate fin rings so the loft runs upward (chord_ring builds rings in the YZ plane already; fine)
C.smooth(fin, 25)

# main rotor: hub + mast + 2 blades (one white, one dark like the reference)
mast = C.cylinder('HELI_MAST', 0.13, 0.55, (0, 0.2, 3.55), col, M_METAL, axis='Z', segments=16)
rot_main = bpy.data.objects.new('ROTOR_MAIN', bpy.data.meshes.new('ROTOR_MAIN')); col.objects.link(rot_main)
rot_main.location = (0, 0.2, 3.85)
hub = C.cylinder('hub', 0.62, 0.20, (0, 0, 0.0), col, M_HULL, axis='Z', segments=32)
C.bevel(hub, 0.06, 2, 30); C.apply_mods(hub)
cap = C.cylinder('cap', 0.30, 0.16, (0, 0, 0.17), col, M_DARK, axis='Z', segments=24, radius2=0.14)
parts = [hub, cap]
R_ROTOR = 5.5
for i, mat in enumerate((M_BLADE_W, M_BLADE_D)):
    a = i * math.pi
    bl = C.box('blade', (0, 0, 0), (0.42, R_ROTOR - 0.35, 0.06), col, mat)
    bl.location = (math.sin(a) * (R_ROTOR / 2 + 0.2), math.cos(a) * (R_ROTOR / 2 + 0.2), 0.02)
    bl.rotation_euler = (math.radians(4), 0, -a)  # slight pitch
    C.bevel(bl, 0.02, 2, 30)
    C.apply_mods(bl)
    parts.append(bl)
    grip = C.cylinder('grip', 0.09, 0.5, (math.sin(a) * 0.5, math.cos(a) * 0.5, 0.02), col, M_METAL, axis='Y', segments=12)
    grip.rotation_euler = (0, 0, -a)
    parts.append(grip)
for pobj in parts: pobj.parent = rot_main
bpy.context.view_layer.update()
with bpy.context.temp_override(object=rot_main, active_object=rot_main, selected_objects=[rot_main] + parts, selected_editable_objects=[rot_main] + parts):
    bpy.ops.object.join()
rot_main.data.materials.append(M_BLADE_D)
C.smooth(rot_main, 40)

# tail rotor on the -X side of the fin, spins about local X
rot_tail = bpy.data.objects.new('ROTOR_TAIL', bpy.data.meshes.new('ROTOR_TAIL')); col.objects.link(rot_tail)
rot_tail.location = (-0.32, -6.35, 2.85)
th = C.cylinder('thub', 0.14, 0.16, (0, 0, 0), col, M_DARK, axis='X', segments=16)
tparts = [th]
for i in range(2):
    a = i * math.pi
    tb = C.box('tblade', (0, 0, 0), (0.04, 0.16, 0.95), col, M_BLADE_D if i else M_BLADE_W)
    tb.location = (-0.0, math.sin(a) * 0.55, math.cos(a) * 0.55)
    tb.rotation_euler = (a, math.radians(10), 0)
    tparts.append(tb)
for pobj in tparts: pobj.parent = rot_tail
bpy.context.view_layer.update()
with bpy.context.temp_override(object=rot_tail, active_object=rot_tail, selected_objects=[rot_tail] + tparts, selected_editable_objects=[rot_tail] + tparts):
    bpy.ops.object.join()
C.cylinder('HELI_TAIL_AXLE', 0.05, 0.4, (-0.15, -6.35, 2.85), col, M_METAL, axis='X', segments=12)

# landing gear: two nose wheels on struts + small tail skid wheel
def wheel(name, loc, r=0.24, w=0.14):
    t = C.cylinder(name, r, w, loc, col, M_RUBBER, axis='X', segments=24)
    C.bevel(t, 0.05, 2, 30); C.apply_mods(t)
    C.cylinder(name + '_HUB', r * 0.55, w + 0.02, loc, col, M_METAL, axis='X', segments=16)
    return t
for sx in (1, -1):
    tag = 'R' if sx > 0 else 'L'
    wheel(f'HELI_WHEEL_{tag}', (sx * 0.78, 3.9, 0.26))
    strut = C.cylinder(f'HELI_STRUT_{tag}', 0.05, 0.75, (sx * 0.62, 3.9, 0.62), col, M_METAL, axis='Z', segments=10)
    strut.rotation_euler = (0, math.radians(sx * -22), 0)
    brace = C.cylinder(f'HELI_BRACE_{tag}', 0.035, 0.7, (sx * 0.55, 4.25, 0.6), col, M_METAL, axis='Z', segments=8)
    brace.rotation_euler = (math.radians(-35), math.radians(sx * -12), 0)
    C.cylinder(f'HELI_AXLE_{tag}', 0.03, 0.3, (sx * 0.68, 3.9, 0.26), col, M_METAL, axis='X', segments=8)
wheel('HELI_WHEEL_TAIL', (0.0, -0.9, 0.30), r=0.2, w=0.12)
C.cylinder('HELI_STRUT_TAIL', 0.05, 0.45, (0.0, -0.9, 0.5), col, M_METAL, axis='Z', segments=10)
# fin-mounted anti-collision lamp
C.cylinder('HELI_BEACON', 0.06, 0.06, (0, -6.5, 3.25), col, P.new_mat('MAT_Beacon', (1, 0.1, 0.1, 1), rough=0.3, emission=(1, 0.05, 0.05, 1), estrength=6), axis='Z', segments=12)

# parent everything to root
for ob in list(col.objects):
    if ob is root or ob.parent is not None: continue
    C.parent(ob, root)
    if ob.type == 'MESH' and ob not in (fus, rot_main, rot_tail) and not ob.name.startswith('HELI_TAILPLANE') and ob.name != 'HELI_FIN':
        C.smooth(ob, 40)

root['facing'] = '+Y'; root['door_side'] = '+X'; root['rotor_main_axis'] = 'local Z'; root['rotor_tail_axis'] = 'local X'
root['length_m'] = 12.4; root['rotor_diameter_m'] = 2 * R_ROTOR
print('HELICOPTER tris:', C.tri_count(col))
C.save(BLEND)
print('saved', BLEND)

if not NO_RENDER:
    C.studio(size=12.0, cam_loc=(14.0, 9.5, 3.8), target=(0, 0.0, 2.0), lens=50)
    # preview-only fill aimed into the open doorway so the bench reads
    ld = bpy.data.lights.new('DOOR_FILL', 'SPOT'); ld.energy = 2500; ld.spot_size = math.radians(40); ld.spot_blend = 0.5
    dl = bpy.data.objects.new('DOOR_FILL', ld); bpy.data.collections['STUDIO'].objects.link(dl); dl.location = (7.0, 2.5, 3.0)
    tg = P.make_empty('DOOR_TARGET', (-0.5, 0.85, 1.3)); C.link(tg, bpy.data.collections['STUDIO'])
    c = dl.constraints.new('TRACK_TO'); c.target = tg; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    C.render(PREVIEW)
    print('rendered', PREVIEW)
