"""KIT 1 - Construction asset kit for POSTA 2040 (Blender 4.5, headless).
Run: /opt/blender/blender -b --python scripts/assets/build_construction.py [-- --norender]
Builds every asset in its own collection (root empty at ground-centre, real metres, Z up),
the 'GN_BuildUp' geometry-nodes group, saves blender/assets/construction.blend and renders previews.
"""
import bpy, bmesh, sys, os, math, random
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'common'))
import posta_lib as P
import kit_lib as K
from kit_lib import bm_box, bm_cyl, bm_bar, bm_sphere, rx, ry, rz

ROOT = P.ROOT
OUT_BLEND = os.path.join(ROOT, 'blender', 'assets', 'construction.blend')
PREVIEWS = os.path.join(ROOT, 'previews')
NORENDER = '--norender' in sys.argv
QUICK = '--quick' in sys.argv
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 1.0

# ----------------------------------------------------------------- materials
def paint(name, color, rough=0.32, var=0.18, metal=0.0):
    """Painted steel with noise-driven roughness variation and subtle colour wear."""
    m = P.new_mat(name, color, rough, metal); nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 6.0; noise.inputs['Detail'].default_value = 4.0; noise.inputs['Roughness'].default_value = 0.7
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.35; mr.inputs['From Max'].default_value = 0.65
    mr.inputs['To Min'].default_value = max(0.05, rough - var); mr.inputs['To Max'].default_value = min(1.0, rough + var)
    nt.links.new(noise.outputs['Fac'], mr.inputs['Value']); nt.links.new(mr.outputs['Result'], b.inputs['Roughness'])
    # subtle darkening in crevices / wear
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 0.35
    mix.inputs[6].default_value = color
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.3; ramp.color_ramp.elements[0].color = (0.55, 0.5, 0.45, 1); ramp.color_ramp.elements[1].position = 0.7
    nt.links.new(noise.outputs['Fac'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], mix.inputs[7]); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08; bump.inputs['Distance'].default_value = 0.02
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs[0], b.inputs['Normal'])
    return m

M_YEL = paint('MAT_PaintYellow', P.PAL['yellow'])
M_ORA = paint('MAT_PaintOrange', P.PAL['orange'])
M_WHITE = paint('MAT_PaintWhite', (0.85, 0.85, 0.82, 1), 0.3, 0.1)
M_STEEL = paint('MAT_SteelDark', (0.08, 0.08, 0.085, 1), 0.45, 0.15, 0.85)
M_GALV = paint('MAT_Galvanised', (0.55, 0.57, 0.58, 1), 0.38, 0.2, 0.9)
M_RUBBER = P.new_mat('MAT_Rubber', (0.02, 0.02, 0.02, 1), 0.85)
M_GLASS = P.new_mat('MAT_CabGlass', (0.6, 0.75, 0.8, 1), 0.05, 0.0, transmission=1.0, ior=1.45, alpha=1.0)
M_GLASS.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.55, 0.6, 1)
M_CONC = paint('MAT_Concrete', (0.42, 0.41, 0.38, 1), 0.9, 0.08)
M_WOOD = paint('MAT_Plank', (0.45, 0.3, 0.16, 1), 0.7, 0.15)
M_RUST = paint('MAT_Rebar', (0.2, 0.08, 0.04, 1), 0.75, 0.15, 0.3)
M_BAG = paint('MAT_CementBag', (0.7, 0.65, 0.55, 1), 0.8, 0.1)
M_BRICK = paint('MAT_Brick', (0.45, 0.15, 0.09, 1), 0.85, 0.1)
M_TYRE = M_RUBBER

def stripe_mat(name, c1, c2, period=0.5, axis='Y'):
    m = P.new_mat(name, c1, 0.6); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    div = nt.nodes.new('ShaderNodeMath'); div.operation = 'DIVIDE'; div.inputs[1].default_value = period
    nt.links.new(sep.outputs[axis], div.inputs[0])
    fl = nt.nodes.new('ShaderNodeMath'); fl.operation = 'FLOOR'; nt.links.new(div.outputs[0], fl.inputs[0])
    md = nt.nodes.new('ShaderNodeMath'); md.operation = 'MODULO'; md.inputs[1].default_value = 2.0; nt.links.new(fl.outputs[0], md.inputs[0])
    ab = nt.nodes.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; nt.links.new(md.outputs[0], ab.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs[6].default_value = c1; mix.inputs[7].default_value = c2
    nt.links.new(ab.outputs[0], mix.inputs['Factor']); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    return m

M_BARRIER = stripe_mat('MAT_BarrierStripe', (0.75, 0.04, 0.02, 1), (0.85, 0.85, 0.82, 1), 0.5, 'Y')
M_DRUM = stripe_mat('MAT_DrumStripe', P.PAL['orange'], (0.85, 0.85, 0.82, 1), 0.6, 'Z')

def cone_mat():
    m = P.new_mat('MAT_Cone', P.PAL['orange'], 0.45); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); cr = ramp.color_ramp; cr.interpolation = 'CONSTANT'
    cr.elements[0].color = P.PAL['orange']; cr.elements[1].position = 0.38; cr.elements[1].color = (0.9, 0.9, 0.88, 1)
    e = cr.elements.new(0.52); e.color = P.PAL['orange']
    nt.links.new(sep.outputs['Z'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    return m
M_CONE = cone_mat()

def chainlink_mat(cell=0.06, wire=0.14):
    m = P.new_mat('MAT_ChainLink', (0.6, 0.62, 0.63, 1), 0.35, 0.9); m.surface_render_method = 'DITHERED'
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    lines = []
    for sign in (1, -1):
        s = nt.nodes.new('ShaderNodeMath'); s.operation = 'MULTIPLY_ADD'; nt.links.new(sep.outputs['X'], s.inputs[0]); s.inputs[1].default_value = sign; nt.links.new(sep.outputs['Z'], s.inputs[2])
        d = nt.nodes.new('ShaderNodeMath'); d.operation = 'DIVIDE'; d.inputs[1].default_value = cell; nt.links.new(s.outputs[0], d.inputs[0])
        fr = nt.nodes.new('ShaderNodeMath'); fr.operation = 'FRACT'; nt.links.new(d.outputs[0], fr.inputs[0])
        lt = nt.nodes.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = wire; nt.links.new(fr.outputs[0], lt.inputs[0])
        lines.append(lt)
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'; nt.links.new(lines[0].outputs[0], mx.inputs[0]); nt.links.new(lines[1].outputs[0], mx.inputs[1])
    nt.links.new(mx.outputs[0], b.inputs['Alpha'])
    return m
M_CHAIN = chainlink_mat()
M_LAMP = P.new_mat('MAT_LampPanel', (1, 1, 1, 1), 0.3, emission=(1.0, 0.97, 0.9, 1), estrength=40.0)
M_PLASTIC_DK = P.new_mat('MAT_PlasticDark', (0.03, 0.03, 0.035, 1), 0.5)

# ----------------------------------------------------------------- builders
def truss_box(bm, origin, w, seg_len, n, chord_r=0.08, brace_r=0.045, mat=0, axis='Z'):
    """Square lattice mast: 4 chords + horizontal rungs + alternating diagonals, built along +Z then rotated."""
    o = Vector(origin)
    corners = [Vector((sx * w, sy * w, 0)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    L = seg_len * n
    rot = Matrix.Identity(4) if axis == 'Z' else rot_axis(axis)
    def T(v): return o + (rot @ Vector(v).to_4d()).to_3d()
    for c in corners: bm_bar(bm, T(c), T(c + Vector((0, 0, L))), chord_r, mat)
    for k in range(n + 1):
        z = k * seg_len
        for i in range(4):
            a, b = corners[i] + Vector((0, 0, z)), corners[(i + 1) % 4] + Vector((0, 0, z))
            bm_bar(bm, T(a), T(b), brace_r, mat)
            if k < n:
                flip = (k + i) % 2 == 0
                d1 = a if flip else b; d2 = (b if flip else a) + Vector((0, 0, seg_len))
                bm_bar(bm, T(d1), T(d2), brace_r * 0.85, mat)

def rot_axis(axis):
    return {'X': ry(90), '-X': ry(-90), 'Y': rx(-90), '-Y': rx(90)}[axis]

def truss_tri(bm, x0, x1, y_half, z_bot, z_top, seg, chord_r=0.07, brace_r=0.04, mat=0, taper=1.0):
    """Triangular jib truss along X (two bottom chords, one top chord)."""
    n = max(1, int(round((x1 - x0) / seg))); seg = (x1 - x0) / n
    def pts(x):
        f = 1 - (1 - taper) * (x - x0) / max(1e-6, (x1 - x0))
        return (Vector((x, y_half * f, z_bot)), Vector((x, -y_half * f, z_bot)), Vector((x, 0, z_bot + (z_top - z_bot) * f)))
    for i in range(3): bm_bar(bm, pts(x0)[i], pts(x1)[i], chord_r, mat)
    for k in range(n + 1):
        a, b, t = pts(x0 + k * seg)
        bm_bar(bm, a, b, brace_r, mat)
        if k < n:
            a2, b2, t2 = pts(x0 + (k + 1) * seg)
            if k % 2 == 0: bm_bar(bm, a, t2, brace_r, mat); bm_bar(bm, b, t2, brace_r, mat); bm_bar(bm, a, b2, brace_r * 0.8, mat)
            else: bm_bar(bm, t, a2, brace_r, mat); bm_bar(bm, t, b2, brace_r, mat); bm_bar(bm, b, a2, brace_r * 0.8, mat)

def build_crane():
    col = K.coll('CRANE_TOWER'); root = K.empty('CRANE_TOWER', col, size=2)
    H, SEG, W = 45.0, 3.0, 1.0
    bm = bmesh.new()
    bm_box(bm, (3.0, 3.0, 0.4), (0, 0, 0.4), mat=1)                    # concrete foundation block
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)): bm_bar(bm, (0, 0, 0.9), (sx * 2.6, sy * 2.6, 0.8), 0.1, 0)  # base cross feet
    truss_box(bm, (0, 0, 0.8), W, SEG, int((H - 0.8) // SEG), mat=0)
    # ladder on one face
    for z in range(1, int(H), 1): bm_bar(bm, (-W - 0.25, -0.2, z), (-W - 0.25, 0.2, z), 0.015, 0, 'cyl', seg=6)
    bm_bar(bm, (-W - 0.25, -0.2, 1), (-W - 0.25, -0.2, H), 0.02, 0, 'cyl', seg=6); bm_bar(bm, (-W - 0.25, 0.2, 1), (-W - 0.25, 0.2, H), 0.02, 0, 'cyl', seg=6)
    K.obj_from_bm('CRANE_MAST', bm, col, [M_YEL, M_CONC], parent=root)

    # slewing unit + jib assembly (origin on mast axis at top of mast)
    bm = bmesh.new()
    bm_cyl(bm, 1.4, 1.4, 0.5, (0, 0, 0.25), seg=24, mat=2)             # slew ring
    bm_box(bm, (1.2, 1.2, 0.35), (0, 0, 0.85), mat=0)                  # turntable deck
    # operator cab (hangs off the side at the jib root)
    bm_box(bm, (0.9, 0.75, 0.1), (1.6, -1.9, 1.3), mat=0)
    bm_box(bm, (0.9, 0.75, 0.1), (1.6, -1.9, 3.1), mat=0)
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)): bm_bar(bm, (1.6 + sx * 0.85, -1.9 + sy * 0.7, 1.3), (1.6 + sx * 0.85, -1.9 + sy * 0.7, 3.1), 0.05, 0)
    bm_box(bm, (0.82, 0.68, 0.8), (1.6, -1.9, 2.2), mat=4)             # glass
    # tower top (apex pyramid)
    apex = Vector((0, 0, 9.0))
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        base = Vector((sx * W, sy * W, 1.2)); bm_bar(bm, base, apex, 0.07, 0)
        bm_bar(bm, base, Vector(((-sy) * W, sx * W, 1.2)), 0.05, 0)
    for k in range(1, 4):
        f = k / 4.0; z = 1.2 + f * 7.8; w = W * (1 - f) + 0.15
        for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)): bm_bar(bm, (sx * w, sy * w, z), ((-sy) * w, sx * w, z), 0.04, 0)
    # main jib 35 m, triangular truss, bottom chords at z=1.2
    truss_tri(bm, 1.3, 36.3, 0.7, 1.2, 2.6, 2.5, mat=0, taper=0.7)
    bm_box(bm, (0.15, 0.6, 0.5), (36.4, 0, 1.7), mat=1)               # jib tip plate
    # counter-jib 11 m
    truss_tri(bm, -1.3, -12.3, 1.0, 1.2, 2.2, 2.75, chord_r=0.08, brace_r=0.045, mat=0)
    bm_box(bm, (5.5, 1.1, 0.03), (-6.8, 0, 1.25), mat=2)              # walkway deck
    for i in range(4): bm_box(bm, (0.3, 1.0, 1.0), (-8.8 - i * 0.75, 0, 0.35), mat=3)   # concrete counterweights
    bm_box(bm, (1.0, 0.9, 0.7), (-4.0, 0, 1.95), mat=1)               # hoist winch housing
    bm_cyl(bm, 0.45, 0.45, 1.2, (-4.0, 0, 2.3), rx(90), seg=16, mat=2)  # winch drum
    # pendant tie bars
    for tip, r in (((20.0, 0, 2.6 - 0.56), 0.035), ((35.5, 0, 2.6 - 0.98), 0.035), ((-11.5, 0, 2.2), 0.04)):
        for sy in (-0.25, 0.25): bm_bar(bm, (0, sy, 9.0), (tip[0], sy, tip[2]), r, 2, 'cyl', seg=6)
    # trolley rails under the jib bottom chords
    for sy in (-0.7, 0.7): bm_bar(bm, (1.5, sy, 1.05), (35.8, sy * 0.72, 1.05), 0.04, 2)
    slew = K.obj_from_bm('CRANE_SLEW', bm, col, [M_YEL, M_ORA, M_STEEL, M_CONC, M_GLASS], loc=(0, 0, H), parent=root)

    bm = bmesh.new()
    bm_box(bm, (0.7, 0.85, 0.25), (0, 0, -0.3), mat=0)
    for sy in (-0.65, 0.65):
        for sx in (-0.5, 0.5): bm_cyl(bm, 0.12, 0.12, 0.1, (sx, sy, 0.0), rx(90), seg=12, mat=1)
    trolley = K.obj_from_bm('CRANE_TROLLEY', bm, col, [M_ORA, M_STEEL], loc=(20.0, 0, 1.05), parent=slew)

    bm = bmesh.new(); L = 22.0
    for sy in (-0.12, 0.12): bm_bar(bm, (0, sy, -0.55), (0, sy, -L), 0.015, 1, 'cyl', seg=6)
    bm_box(bm, (0.3, 0.3, 0.45), (0, 0, -L - 0.4), mat=0)             # hook block
    bm_cyl(bm, 0.35, 0.35, 0.25, (0, 0, -L - 0.4), rx(90), seg=20, mat=1)  # sheave
    bm_bar(bm, (0, 0, -L - 0.85), (0, 0, -L - 1.4), 0.06, 1, 'cyl', seg=8)
    # hook curve: half-ring of short tube segments, open end pointing up
    c = Vector((0.0, 0.0, -L - 1.75)); R = 0.3
    for i in range(8):
        a0, a1 = math.pi * (0.1 + 1.3 * i / 8.0), math.pi * (0.1 + 1.3 * (i + 1) / 8.0)
        p0 = c + Vector((R * math.cos(a0), 0, -R * math.sin(a0))); p1 = c + Vector((R * math.cos(a1), 0, -R * math.sin(a1)))
        bm_bar(bm, p0 - Vector((R, 0, 0)), p1 - Vector((R, 0, 0)), 0.06, 1, 'cyl', seg=8, ext=0.02)
    K.obj_from_bm('CRANE_HOOK', bm, col, [M_ORA, M_STEEL], loc=(0, 0, 0), parent=trolley)
    return root

def build_excavator():
    col = K.coll('EXCAVATOR'); root = K.empty('EXCAVATOR', col, size=2)
    bm = bmesh.new()
    for sy in (-1.3, 1.3):
        bm_box(bm, (2.1, 0.36, 0.42), (0, sy, 0.5), mat=0)                                 # track body
        for sx in (-2.1, 2.1): bm_cyl(bm, 0.42, 0.42, 0.72, (sx, sy, 0.5), rx(90), seg=20, mat=0)
        for sx in (-1.4, -0.7, 0.0, 0.7, 1.4): bm_cyl(bm, 0.22, 0.22, 0.5, (sx, sy, 0.3), rx(90), seg=12, mat=1)  # rollers
        for i in range(26):                                                               # track pads
            x = -2.0 + i * 0.16; bm_box(bm, (0.06, 0.4, 0.03), (x, sy, 0.06), mat=0); bm_box(bm, (0.06, 0.4, 0.03), (x, sy, 0.94), mat=0)
    bm_box(bm, (1.5, 1.0, 0.3), (0, 0, 0.75), mat=2)                                      # track frame
    bm_cyl(bm, 1.0, 1.0, 0.25, (0, 0, 1.15), seg=24, mat=1)                                # slew ring
    K.obj_from_bm('EXC_TRACKS', bm, col, [M_RUBBER, M_STEEL, M_YEL], parent=root)

    bm = bmesh.new()
    bm_box(bm, (1.3, 1.35, 0.1), (-0.6, 0, 0.1), mat=0)                                   # deck
    bm_box(bm, (1.6, 1.3, 0.55), (-1.1, 0.0, 0.75), mat=0)                                # engine house
    bm_box(bm, (0.45, 1.35, 0.7), (-2.95, 0, 0.75), mat=1)                                # counterweight
    bm_cyl(bm, 0.07, 0.07, 0.8, (-1.4, 0.7, 1.6), seg=8, mat=1)                           # exhaust
    bm_box(bm, (0.9, 0.3, 0.3), (0.2, -0.95, 0.35), mat=0)                                # cab base
    bm_box(bm, (0.95, 0.68, 0.06), (0.25, -0.95, 2.05), mat=0)                            # cab roof
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)): bm_bar(bm, (0.25 + sx * 0.88, -0.95 + sy * 0.6, 0.65), (0.25 + sx * 0.88, -0.95 + sy * 0.6, 2.0), 0.05, 0)
    bm_box(bm, (0.86, 0.6, 0.68), (0.25, -0.95, 1.33), mat=2)                              # cab glass
    bm_box(bm, (0.5, 0.25, 0.35), (0.5, 0.55, 0.35), mat=0)                               # boom foot bracket
    house = K.obj_from_bm('EXC_HOUSE', bm, col, [M_YEL, M_STEEL, M_GLASS], loc=(0, 0, 1.25), parent=root)

    bm = bmesh.new()
    elbow = Vector((2.4, 0, 2.9)); tip = Vector((5.3, 0, 1.9))
    bm_bar(bm, (0, 0, 0), elbow, 0.26, 0, ry=0.32); bm_bar(bm, elbow, tip, 0.2, 0, ry=0.26, ext=0.2)
    bm_cyl(bm, 0.3, 0.3, 0.75, elbow, rx(90), seg=16, mat=0)
    bm_cyl(bm, 0.14, 0.14, 1.0, (0, 0, 0), rx(90), seg=16, mat=1)                          # boom pivot pin
    for sy in (-0.42, 0.42):                                                              # boom lift cylinders
        bm_bar(bm, (0.6, sy, -0.55), (1.9, sy, 1.9), 0.09, 1, 'cyl', seg=10); bm_bar(bm, (1.3, sy, 0.7), (1.9, sy, 1.9), 0.055, 2, 'cyl', seg=8)
    bm_bar(bm, (2.9, 0, 3.05), (4.8, 0, 2.5), 0.08, 1, 'cyl', seg=10)                      # stick cylinder
    bm_bar(bm, (4.5, 0, 2.6), (5.1, 0, 2.45), 0.05, 2, 'cyl', seg=8)
    boom = K.obj_from_bm('EXC_BOOM', bm, col, [M_YEL, M_STEEL, M_GALV], loc=(0.5, 0.55, 0.55), parent=house)

    bm = bmesh.new(); stick_tip = Vector((1.1, 0, -2.9))
    bm_bar(bm, (0.2, 0, 0.5), stick_tip, 0.17, 0, ry=0.22, ext=0.2)
    bm_cyl(bm, 0.24, 0.24, 0.6, (0, 0, 0), rx(90), seg=16, mat=0)
    bm_cyl(bm, 0.12, 0.12, 0.8, (0, 0, 0), rx(90), seg=12, mat=1)
    bm_bar(bm, (0.3, 0, 0.55), (0.1, 0, 0.9), 0.1, 1, 'cyl', seg=8)                        # stick cylinder rod end
    bm_bar(bm, (0.15, 0, 0.1), (1.4, 0, -1.6), 0.075, 1, 'cyl', seg=10)                    # bucket cylinder
    bm_bar(bm, (1.4, 0, -1.6), (1.75, 0, -2.3), 0.045, 2, 'cyl', seg=8)
    stick = K.obj_from_bm('EXC_STICK', bm, col, [M_YEL, M_STEEL, M_GALV], loc=tuple(tip), parent=boom)

    bm = bmesh.new()
    bm_box(bm, (0.55, 0.72, 0.5), (0.35, 0, -0.55), mat=0)                                 # bucket body
    bm_cyl(bm, 0.6, 0.6, 1.4, (0.1, 0, -0.6), rx(90), seg=14, mat=0)                       # rounded back
    bm_box(bm, (0.35, 0.7, 0.04), (0.6, 0, -1.05), mat=0)                                 # lip
    for sy in (-0.56, -0.28, 0, 0.28, 0.56): bm_bar(bm, (0.9, sy, -1.0), (1.3, sy, -1.1), 0.05, 0, ry=0.035)   # teeth
    bm_bar(bm, (0, 0, 0), (0.25, 0, -0.5), 0.08, 1, ry=0.3)                                 # linkage
    bm_cyl(bm, 0.1, 0.1, 0.7, (0, 0, 0), rx(90), seg=12, mat=1)
    K.obj_from_bm('EXC_BUCKET', bm, col, [M_STEEL, M_GALV], loc=tuple(stick_tip), parent=stick)
    return root

def build_mixer():
    col = K.coll('MIXER_TRUCK'); root = K.empty('MIXER_TRUCK', col, size=2)
    bm = bmesh.new()
    bm_box(bm, (3.9, 0.5, 0.12), (-0.3, 0, 0.9), mat=1)                                    # chassis rails
    bm_box(bm, (1.2, 1.25, 0.75), (2.6, 0, 1.85), mat=0)                                  # cab
    bm_box(bm, (1.0, 1.15, 0.5), (2.65, 0, 2.95), mat=2)                                  # glass band
    bm_box(bm, (1.1, 1.2, 0.08), (2.6, 0, 3.5), mat=0)                                    # cab roof
    bm_box(bm, (0.5, 1.2, 0.45), (3.5, 0, 1.4), mat=0)                                    # bumper/grille
    bm_box(bm, (0.3, 1.3, 0.1), (3.7, 0, 0.8), mat=1)
    bm_box(bm, (0.9, 1.2, 0.6), (0.6, 0, 1.6), mat=3)                                     # water tank / hydraulics box
    for sx in (2.5, -1.2, -2.5):
        for sy in (-1.15, 1.15):
            bm_cyl(bm, 0.52, 0.52, 0.38, (sx, sy, 0.52), rx(90), seg=20, mat=4)
            bm_cyl(bm, 0.3, 0.3, 0.4, (sx, sy, 0.52), rx(90), seg=12, mat=1)
    # drum: barrel + conical rear, tilted 14 degrees nose-up toward the rear
    drot = ry(-76)   # drum axis: mostly along -X, nose up 14 deg toward the rear
    c = Vector((-0.9, 0, 2.55))
    bm_cyl(bm, 1.1, 0.95, 2.6, c, drot, seg=28, mat=5)
    bm_cyl(bm, 0.95, 0.45, 1.6, c + (drot @ Vector((0, 0, 2.1, 0))).to_3d(), drot, seg=28, mat=5)
    bm_cyl(bm, 1.1, 0.4, 0.9, c - (drot @ Vector((0, 0, 1.75, 0))).to_3d(), drot, seg=28, mat=5)
    bm_box(bm, (0.35, 0.6, 0.75), (0.75, 0, 1.75), mat=1)                                  # front drum pedestal
    for sy in (-0.7, 0.7): bm_bar(bm, (-3.0, sy, 1.0), (-2.6, sy * 0.9, 3.0), 0.09, 1)   # rear A-frame
    bm_bar(bm, (-2.6, -0.63, 3.0), (-2.6, 0.63, 3.0), 0.09, 1)
    bm_cyl(bm, 0.55, 0.55, 0.3, (-2.9, 0, 3.35), drot, seg=20, mat=1)                      # drum roller ring
    bm_box(bm, (0.9, 0.3, 0.05), (-3.6, 0.4, 3.0), rz(25) @ rx(-30), mat=1)                # chute
    bm_box(bm, (0.5, 0.25, 0.3), (-3.9, 0, 1.3), mat=1)                                   # hopper/ladder box
    K.obj_from_bm('MIXER_BODY', bm, col, [M_WHITE, M_STEEL, M_GLASS, M_ORA, M_RUBBER, M_DRUM], parent=root)
    return root

def build_scaffold():
    col = K.coll('SCAFFOLD_MODULE'); root = K.empty('SCAFFOLD_MODULE', col)
    bm = bmesh.new(); r = 0.024; w = 1.0
    cs = [(sx * w, sy * w) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    for x, y in cs:
        bm_bar(bm, (x, y, 0.0), (x, y, 2.0), r, 0, 'cyl', seg=8)
        bm_box(bm, (0.08, 0.08, 0.01), (x, y, 0.01), mat=0)                                # base plate
        for z in (0.5, 1.0, 1.95): bm_cyl(bm, 0.04, 0.04, 0.05, (x, y, z), seg=8, mat=0)  # couplers
    for z in (0.3, 1.1, 1.95):
        for i in range(4):
            a, b = cs[i], cs[(i + 1) % 4]; bm_bar(bm, (a[0], a[1], z), (b[0], b[1], z), r * 0.9, 0, 'cyl', seg=8)
    bm_bar(bm, (-w, -w - 0.04, 0.3), (w, -w - 0.04, 1.95), r * 0.9, 0, 'cyl', seg=8)       # diagonals
    bm_bar(bm, (w + 0.04, -w, 0.3), (w + 0.04, w, 1.95), r * 0.9, 0, 'cyl', seg=8)
    bm_bar(bm, (-w, -w, 1.95), (-w, w, 1.95), r, 0, 'cyl', seg=8)
    for i in range(5):                                                                    # planks
        y = -0.8 + i * 0.4; bm_box(bm, (1.0, 0.19, 0.022), (0, y, 2.0 + 0.022), mat=1)
    bm_box(bm, (1.0, 0.012, 0.075), (0, -1.0, 2.12), mat=1); bm_box(bm, (1.0, 0.012, 0.075), (0, 1.0, 2.12), mat=1)  # toe boards
    bm_bar(bm, (-w, -w - 0.03, 2.5), (w, -w - 0.03, 2.5), r * 0.9, 0, 'cyl', seg=8)         # guardrail (front)
    bm_bar(bm, (-w, -w - 0.03, 3.0), (w, -w - 0.03, 3.0), r * 0.9, 0, 'cyl', seg=8)
    K.obj_from_bm('SCAFFOLD_MESH', bm, col, [M_GALV, M_WOOD], parent=root)
    return root

def ibeam_profile(h, b, tf, tw):
    x, z = b / 2, h
    return [(-x, 0), (x, 0), (x, tf), (tw / 2, tf), (tw / 2, h - tf), (x, h - tf), (x, h), (-x, h), (-x, h - tf), (-tw / 2, h - tf), (-tw / 2, tf), (-x, tf)]

def build_steel():
    col = K.coll('STEEL_COLUMN'); root = K.empty('STEEL_COLUMN', col)
    bm = bmesh.new()
    verts = K.bm_profile_extrude(bm, [(x, z) for x, z in ibeam_profile(0.3, 0.3, 0.02, 0.012)], 4.0, mat=0, axis='Y')
    # profile is drawn in XZ and extruded along Y -> rotate so the member is vertical (Z) with base at z=0
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, 2.0)) @ rx(90) @ Matrix.Translation((0, 0, -0.15)), verts=bm.verts[:])
    bm_box(bm, (0.25, 0.25, 0.015), (0, 0, 0.015), mat=0)
    bm_box(bm, (0.25, 0.25, 0.015), (0, 0, 3.985), mat=0)
    K.obj_from_bm('STEEL_COLUMN_MESH', bm, col, [M_STEEL], parent=root)
    col2 = K.coll('STEEL_BEAM'); root2 = K.empty('STEEL_BEAM', col2)
    bm = bmesh.new()
    K.bm_profile_extrude(bm, ibeam_profile(0.4, 0.18, 0.0135, 0.0086), 6.0, mat=0, axis='X')
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0.0, 0.0)), verts=bm.verts[:])
    for sx in (-2.97, 2.97): bm_box(bm, (0.012, 0.11, 0.2), (sx, 0, 0.2), mat=0)
    K.obj_from_bm('STEEL_BEAM_MESH', bm, col2, [M_STEEL], parent=root2)
    return root, root2

def build_rebar():
    col = K.coll('REBAR_CAGE'); root = K.empty('REBAR_CAGE', col)
    bm = bmesh.new(); a = 0.25; H = 4.0
    pts = [(-a, -a), (0, -a), (a, -a), (a, 0), (a, a), (0, a), (-a, a), (-a, 0)]
    for x, y in pts: bm_bar(bm, (x, y, 0.0), (x, y, H), 0.01, 0, 'cyl', seg=6)
    for k in range(20):
        z = 0.1 + k * 0.2; cs = [(-a - 0.015, -a - 0.015), (a + 0.015, -a - 0.015), (a + 0.015, a + 0.015), (-a - 0.015, a + 0.015)]
        for i in range(4): bm_bar(bm, (cs[i][0], cs[i][1], z), (cs[(i + 1) % 4][0], cs[(i + 1) % 4][1], z), 0.006, 0, 'cyl', seg=6, ext=0.006)
    K.obj_from_bm('REBAR_CAGE_MESH', bm, col, [M_RUST], parent=root)
    return root

def build_pallet():
    col = K.coll('MATERIAL_PALLET'); root = K.empty('MATERIAL_PALLET', col)
    bm = bmesh.new()
    def pallet(cx, cy, mat=0):
        for y in (-0.45, 0, 0.45): bm_box(bm, (0.6, 0.05, 0.045), (cx, cy + y, 0.045), mat=mat)
        for i in range(7): bm_box(bm, (0.6, 0.06, 0.011), (cx, cy - 0.44 + i * 0.147, 0.1), mat=mat)
    pallet(0, 0)
    for layer in range(4):
        for i in range(2):
            for j in range(3):
                rot = rz(90) if layer % 2 else Matrix.Identity(4)
                px, py = (-0.3 + i * 0.6, -0.33 + j * 0.33) if layer % 2 == 0 else (-0.33 + j * 0.33, -0.3 + i * 0.6)
                bm_box(bm, (0.29, 0.155, 0.08), (px + random.uniform(-0.015, 0.015), py + random.uniform(-0.015, 0.015), 0.11 + 0.08 + layer * 0.16), rz(random.uniform(-4, 4)) @ rot, mat=1)
    pallet(1.5, 0)
    for layer in range(5):
        for i in range(5):
            for j in range(4):
                off = 0.115 if layer % 2 else 0.0
                bm_box(bm, (0.11, 0.055, 0.032), (1.5 - 0.46 + i * 0.235 + off * 0.5, -0.33 + j * 0.22 + random.uniform(-0.006, 0.006), 0.11 + 0.032 + layer * 0.068), mat=2)
    K.obj_from_bm('MATERIAL_PALLET_MESH', bm, col, [M_WOOD, M_BAG, M_BRICK], parent=root)
    return root

def build_barrier():
    col = K.coll('BARRIER'); root = K.empty('BARRIER', col)
    bm = bmesh.new()
    prof = [(-0.3, 0), (0.3, 0), (0.3, 0.08), (0.11, 0.33), (0.08, 0.82), (-0.08, 0.82), (-0.11, 0.33), (-0.3, 0.08)]
    K.bm_profile_extrude(bm, prof, 2.0, mat=0, axis='Y')
    K.obj_from_bm('BARRIER_MESH', bm, col, [M_BARRIER], parent=root)
    return root

def build_cone():
    col = K.coll('CONE'); root = K.empty('CONE', col)
    bm = bmesh.new()
    bm_cyl(bm, 0.17, 0.045, 0.7, (0, 0, 0.37), seg=20, mat=0)
    bm_box(bm, (0.2, 0.2, 0.02), (0, 0, 0.02), mat=1)
    K.obj_from_bm('CONE_MESH', bm, col, [M_CONE, M_PLASTIC_DK], parent=root)
    return root

def build_fence():
    col = K.coll('FENCE_PANEL'); root = K.empty('FENCE_PANEL', col)
    bm = bmesh.new(); W, H, r = 1.75, 2.0, 0.021
    for x in (-W, W): bm_bar(bm, (x, 0, 0.1), (x, 0, H), r, 0, 'cyl', seg=10)
    for z in (0.12, H - 0.02): bm_bar(bm, (-W, 0, z), (W, 0, z), r, 0, 'cyl', seg=10)
    bm_bar(bm, (0, 0, 0.12), (0, 0, H - 0.02), r * 0.8, 0, 'cyl', seg=8)
    for x in (-W, W): bm_box(bm, (0.3, 0.12, 0.07), (x, 0, 0.07), mat=2)                   # concrete feet
    # chain-link mesh plane (XZ), material does the alpha pattern
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
    plane = [v for v in bm.verts if abs(v.co.z) < 1e-6 and abs(abs(v.co.x) - 1.0) < 1e-6 and abs(abs(v.co.y) - 1.0) < 1e-6]
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, 0.12 + (H - 0.14) / 2)) @ rx(90) @ Matrix.Diagonal((W - 0.03, (H - 0.14) / 2, 1, 1)), verts=plane)
    for f in bm.faces:
        if len(f.verts) == 4 and all(v in plane for v in f.verts): f.material_index = 1
    K.obj_from_bm('FENCE_PANEL_MESH', bm, col, [M_GALV, M_CHAIN, M_CONC], parent=root)
    return root

def build_site_light():
    col = K.coll('SITE_LIGHT'); root = K.empty('SITE_LIGHT', col)
    bm = bmesh.new()
    for i in range(3):
        a = math.radians(90 + i * 120); bm_bar(bm, (0, 0, 1.3), (0.55 * math.cos(a), 0.55 * math.sin(a), 0), 0.015, 0, 'cyl', seg=8)
    bm_bar(bm, (0, 0, 1.2), (0, 0, 2.5), 0.025, 0, 'cyl', seg=10)
    bm_box(bm, (0.1, 0.1, 0.06), (0, 0, 1.3), mat=0)
    head_rot = rx(-25)
    bm_box(bm, (0.33, 0.07, 0.22), (0, 0, 2.7), head_rot, mat=1)                           # lamp housing
    bm_bar(bm, (0, 0, 2.5), (0, 0.06, 2.7), 0.03, 0)
    body = K.obj_from_bm('SITE_LIGHT_MESH', bm, col, [M_STEEL, M_YEL], parent=root)
    bm = bmesh.new()
    bm_box(bm, (0.3, 0.012, 0.19), Vector((0, 0, 2.7)) + (head_rot @ Vector((0, -0.075, 0, 0))).to_3d(), head_rot, mat=0)
    K.obj_from_bm('SITE_LIGHT_PANEL', bm, col, [M_LAMP], parent=root)
    ld = bpy.data.lights.new('SITE_LIGHT_SPOT', 'SPOT'); ld.energy = 3000; ld.color = (1.0, 0.95, 0.85); ld.spot_size = math.radians(100); ld.spot_blend = 0.6; ld.shadow_soft_size = 0.3
    lo = bpy.data.objects.new('SITE_LIGHT_SPOT', ld); col.objects.link(lo); lo.parent = root
    lo.location = (0, -0.12, 2.7); lo.rotation_euler = (math.radians(65), 0, 0)
    return root

# ----------------------------------------------------------------- GN_BuildUp
def build_up_group(name='GN_BuildUp'):
    """Reveals a mesh from the ground up. Inputs: Geometry, Progress (0..1), Band (m), Scaffold Band (m), Offset (m).
    Deletes faces whose centre z > z_min + Progress*height; stores float face attribute 'front' (1 at the cut, fading over Band)
    and boolean face attribute 'scaffold' (faces within Scaffold Band below the cut)."""
    if name in bpy.data.node_groups: return bpy.data.node_groups[name]
    t = bpy.data.node_groups.new(name, 'GeometryNodeTree'); it = t.interface
    it.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for nm, dv, mn, mx in (('Progress', 1.0, 0.0, 1.0), ('Band', 1.5, 0.01, 100.0), ('Scaffold Band', 6.0, 0.0, 100.0), ('Offset', 0.0, -1000.0, 1000.0)):
        s = it.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = dv; s.min_value = mn; s.max_value = mx
    it.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    so = it.new_socket('Cut Height', in_out='OUTPUT', socket_type='NodeSocketFloat')
    g = P.GN(t); gi = g.n('NodeGroupInput'); go = g.n('NodeGroupOutput'); go.location = (3000, 0)
    I = lambda s: gi.outputs[s]
    bbox = g.n('GeometryNodeBoundBox'); g.link(I('Geometry'), bbox.inputs[0])
    smin = g.n('ShaderNodeSeparateXYZ'); g.link(bbox.outputs['Min'], smin.inputs[0])
    smax = g.n('ShaderNodeSeparateXYZ'); g.link(bbox.outputs['Max'], smax.inputs[0])
    h = g.n('ShaderNodeMath', op='SUBTRACT'); g.link(smax.outputs['Z'], h.inputs[0]); g.link(smin.outputs['Z'], h.inputs[1])
    cut = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(I('Progress'), cut.inputs[0]); g.link(h.outputs[0], cut.inputs[1]); g.link(smin.outputs['Z'], cut.inputs[2])
    cut2 = g.n('ShaderNodeMath', op='ADD'); g.link(cut.outputs[0], cut2.inputs[0]); g.link(I('Offset'), cut2.inputs[1])
    pos = g.n('GeometryNodeInputPosition'); sp = g.n('ShaderNodeSeparateXYZ'); g.link(pos.outputs[0], sp.inputs[0])
    # front = 1 - clamp((cut - z)/band)
    d = g.n('ShaderNodeMath', op='SUBTRACT'); g.link(cut2.outputs[0], d.inputs[0]); g.link(sp.outputs['Z'], d.inputs[1])
    dn = g.n('ShaderNodeMath', op='DIVIDE'); g.link(d.outputs[0], dn.inputs[0]); g.link(I('Band'), dn.inputs[1])
    cl = g.n('ShaderNodeClamp'); g.link(dn.outputs[0], cl.inputs[0])
    front = g.n('ShaderNodeMath', op='SUBTRACT'); front.inputs[0].default_value = 1.0; g.link(cl.outputs[0], front.inputs[1])
    st_front = g.n('GeometryNodeStoreNamedAttribute', dtype='FLOAT', domain='FACE'); st_front.inputs['Name'].default_value = 'front'
    g.link(I('Geometry'), st_front.inputs['Geometry']); g.link(front.outputs[0], st_front.inputs['Value'])
    # scaffold = z > cut - scaffold_band  (and z <= cut, enforced by the delete)
    sb = g.n('ShaderNodeMath', op='SUBTRACT'); g.link(cut2.outputs[0], sb.inputs[0]); g.link(I('Scaffold Band'), sb.inputs[1])
    gt = g.n('FunctionNodeCompare', dtype='FLOAT', op='GREATER_THAN'); g.link(sp.outputs['Z'], gt.inputs[0]); g.link(sb.outputs[0], gt.inputs[1])
    st_sc = g.n('GeometryNodeStoreNamedAttribute', dtype='BOOLEAN', domain='FACE'); st_sc.inputs['Name'].default_value = 'scaffold'
    g.link(st_front.outputs[0], st_sc.inputs['Geometry']); g.link(gt.outputs[0], st_sc.inputs['Value'])
    # delete faces above the cut (small epsilon so Progress=1 keeps the roof)
    eps = g.n('ShaderNodeMath', op='ADD'); g.link(cut2.outputs[0], eps.inputs[0]); eps.inputs[1].default_value = 0.001
    above = g.n('FunctionNodeCompare', dtype='FLOAT', op='GREATER_THAN'); g.link(sp.outputs['Z'], above.inputs[0]); g.link(eps.outputs[0], above.inputs[1])
    delf = g.n('GeometryNodeDeleteGeometry', domain='FACE'); g.link(st_sc.outputs[0], delf.inputs['Geometry']); g.link(above.outputs[0], delf.inputs['Selection'])
    g.link(delf.outputs[0], go.inputs[0]); g.link(cut2.outputs[0], go.inputs[1])
    return t

def apply_build_up(obj, progress=0.5, band=1.5, scaffold_band=6.0, name='BuildUp'):
    grp = build_up_group(); md = obj.modifiers.new(name, 'NODES'); md.node_group = grp
    for s in grp.interface.items_tree:
        if s.item_type == 'SOCKET' and s.in_out == 'INPUT' and s.name in ('Progress', 'Band', 'Scaffold Band'):
            md[s.identifier] = float({'Progress': progress, 'Band': band, 'Scaffold Band': scaffold_band}[s.name])
    return md

def buildup_demo_material():
    return P.dissolving_material('MAT_BuildUpDemo', (0.6, 0.58, 0.55, 1), glow='orange', glow_strength=6.0)

# ----------------------------------------------------------------- build everything
roots = {}
roots['CRANE_TOWER'] = build_crane()
roots['EXCAVATOR'] = build_excavator()
roots['MIXER_TRUCK'] = build_mixer()
roots['SCAFFOLD_MODULE'] = build_scaffold()
roots['STEEL_COLUMN'], roots['STEEL_BEAM'] = build_steel()
roots['REBAR_CAGE'] = build_rebar()
roots['MATERIAL_PALLET'] = build_pallet()
roots['BARRIER'] = build_barrier()
roots['CONE'] = build_cone()
roots['FENCE_PANEL'] = build_fence()
roots['SITE_LIGHT'] = build_site_light()
gn = build_up_group()

# demo building that uses GN_BuildUp (kept in its own collection; also validates the group)
dcol = K.coll('BUILDUP_DEMO'); droot = K.empty('BUILDUP_DEMO', dcol)
bm = bmesh.new(); bm_box(bm, (3, 3, 5), (0, 0, 5), mat=0)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=11, use_grid_fill=True)
demo = K.obj_from_bm('BUILDUP_DEMO_MESH', bm, dcol, [buildup_demo_material()], parent=droot)
apply_build_up(demo, progress=0.55, band=1.0)

for n, c in bpy.data.collections.items():
    print(f'[kit] {n:18s} tris={K.collection_tris(c):7d} objects={len(c.all_objects)}')
print('[kit] TOTAL tris', K.tri_count())
print('[kit] GN_BuildUp inputs:', [s.name for s in gn.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT'])

os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print('[kit] saved', OUT_BLEND)

# ----------------------------------------------------------------- previews
if not NORENDER:
    M_GROUND = paint('MAT_SiteGround', (0.3, 0.26, 0.21, 1), 0.95, 0.05)
    K.ground('GROUND', 600, M_GROUND)
    layout = {'CRANE_TOWER': (6, 14, 0), 'EXCAVATOR': (-16, -2, 0), 'MIXER_TRUCK': (-4, 4, 0), 'SCAFFOLD_MODULE': (12, -4, 0),
              'STEEL_COLUMN': (18, 0, 0), 'STEEL_BEAM': (13, -11, 0), 'REBAR_CAGE': (20, -5, 0), 'MATERIAL_PALLET': (4, -8, 0),
              'BARRIER': (-6, -10, 0), 'CONE': (-3, -9, 0), 'FENCE_PANEL': (-8, -14, 0), 'SITE_LIGHT': (0, -4, 0), 'BUILDUP_DEMO': (-14, 18, 0)}
    for n, loc in layout.items():
        r = bpy.data.objects[n]; r.location = loc
    bpy.data.objects['MIXER_TRUCK'].rotation_euler.z = math.radians(-35)
    bpy.data.objects['EXCAVATOR'].rotation_euler.z = math.radians(-60)
    bpy.data.objects['CRANE_SLEW'].rotation_euler.z = math.radians(-150)
    bpy.data.objects['FENCE_PANEL'].rotation_euler.z = math.radians(-25)
    bpy.data.objects['STEEL_BEAM'].rotation_euler.z = math.radians(15)
    # extra arrayed scaffold tower to show the module tiles
    sm = bpy.data.objects['SCAFFOLD_MESH']; tower = sm.copy(); tower.name = 'SCAFFOLD_TOWER_PREVIEW'; sc.collection.objects.link(tower); tower.parent = None
    tower.location = (11, 2, 0); a1 = tower.modifiers.new('ArrZ', 'ARRAY'); a1.count = 3; a1.relative_offset_displace = (0, 0, 1.0)
    a2 = tower.modifiers.new('ArrX', 'ARRAY'); a2.count = 3; a2.relative_offset_displace = (1.0, 0, 0)
    # extra cones + barriers
    for i in range(4):
        c = bpy.data.objects['CONE_MESH'].copy(); c.parent = None; c.location = (-10 + i * 2.2, -13, 0); sc.collection.objects.link(c)
    for i in range(2):
        b = bpy.data.objects['BARRIER_MESH'].copy(); b.parent = None; b.location = (-6, -8 + i * 2.05, 0); sc.collection.objects.link(b)
    P.setup_world(sun_elev=42, sun_az=215, sun_energy=4.0, sky_strength=0.5)
    sky = next(n for n in sc.world.node_tree.nodes if n.type == 'TEX_SKY'); sky.sun_disc = False   # sun comes from the SUN lamp only
    cam = P.add_camera('CAM_KIT', loc=(-27, -40, 15), target=(1.5, -2, 4.5), lens=33)
    res = (640, 360) if QUICK else (1280, 720)
    P.setup_render(res=res, samples=16 if QUICK else 48, exposure=-2.6, out=os.path.join(PREVIEWS, 'asset_construction_kit.png'))
    bpy.ops.render.render(write_still=True)
    cam2 = P.add_camera('CAM_CRANE', loc=(6 + 30, 14 - 30, 40), target=(6 + 4, 14 - 1, 45), lens=35)
    sc.camera = cam2; sc.render.filepath = os.path.join(PREVIEWS, 'asset_crane_closeup.png')
    bpy.ops.render.render(write_still=True)
    print('[kit] previews done')
