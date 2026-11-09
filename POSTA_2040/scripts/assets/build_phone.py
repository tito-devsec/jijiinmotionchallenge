"""Procedural Infinix HOT 70 smartphone (Blender 4.5, headless).

Run:  /opt/blender/blender -b --python scripts/assets/build_phone.py [-- --no-render]

Builds collection 'PHONE' (all parts parented to empty 'PHONE_ROOT' at origin), phone lying flat,
screen facing +Z, long axis along Y, metres. Saves blender/assets/phone.blend, then renders two
studio previews (previews/asset_phone_front.png / asset_phone_back.png).

Extra objects: 'PHONE_LENS_MAIN' (main rear lens glass disc), 'PHONE_SCREEN_CENTER' (empty at screen centre).
Screen material 'MAT_PhoneScreen' has an Image Texture node 'ScreenImage' left unconnected so a wallpaper
image can be plugged into the emission later (placeholder procedural wallpaper drives emission meanwhile).
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
import posta_lib as P

OUT_BLEND = os.path.join(ROOT, 'blender', 'assets', 'phone.blend')
OUT_PREV = os.path.join(ROOT, 'previews')
RENDER = '--no-render' not in sys.argv

# ------------------------------------------------------------------ dimensions (metres)
W, L, T = 0.076, 0.165, 0.0076           # width (X), length (Y), thickness (Z)
R_CORNER = 0.0085                        # body corner radius
HT = T / 2                               # half thickness; screen at +HT, back at -HT

# ------------------------------------------------------------------ scene reset
def reset_scene():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.lights, bpy.data.cameras, bpy.data.collections, bpy.data.images):
        for d in list(coll):
            if d.users == 0 or True:
                try: coll.remove(d)
                except Exception: pass
    bpy.context.scene.unit_settings.system = 'METRIC'; bpy.context.scene.unit_settings.scale_length = 1.0

reset_scene()
COL = bpy.data.collections.new('PHONE'); bpy.context.scene.collection.children.link(COL)
ROOT_E = bpy.data.objects.new('PHONE_ROOT', None); ROOT_E.empty_display_size = 0.05; ROOT_E.empty_display_type = 'ARROWS'; COL.objects.link(ROOT_E)

# ------------------------------------------------------------------ materials
def mat_frame():
    m = P.new_mat('MAT_PhoneFrame', (0.40, 0.48, 0.34, 1), rough=0.32, metal=0.85)
    return m

def mat_dark(): return P.new_mat('MAT_PhoneDark', (0.012, 0.012, 0.013, 1), rough=0.55)

def mat_back():
    """Sage green back with low-contrast anisotropic feather / brush-stroke streaks (procedural)."""
    m = P.new_mat('MAT_PhoneBack', (0.40, 0.50, 0.32, 1), rough=0.22, metal=0.0, coat=0.6)
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # streak field A: fine diagonal streaks (brush strokes)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (0, 0, math.radians(-62)); mp.inputs['Scale'].default_value = (1, 1, 1)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    dist = nt.nodes.new('ShaderNodeTexNoise'); dist.inputs['Scale'].default_value = 28.0; dist.inputs['Detail'].default_value = 2.0; dist.inputs['Roughness'].default_value = 0.5
    nt.links.new(mp.outputs[0], dist.inputs['Vector'])
    wave = nt.nodes.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'Y'; wave.wave_profile = 'SIN'
    wave.inputs['Scale'].default_value = 520.0; wave.inputs['Distortion'].default_value = 9.0; wave.inputs['Detail'].default_value = 3.0; wave.inputs['Detail Scale'].default_value = 2.0
    nt.links.new(mp.outputs[0], wave.inputs['Vector'])
    # streak field B: large feather plumes (low frequency bands bent by noise)
    mp2 = nt.nodes.new('ShaderNodeMapping'); mp2.inputs['Rotation'].default_value = (0, 0, math.radians(-40))
    nt.links.new(tc.outputs['Object'], mp2.inputs['Vector'])
    wave2 = nt.nodes.new('ShaderNodeTexWave'); wave2.wave_type = 'BANDS'; wave2.bands_direction = 'Y'; wave2.wave_profile = 'SIN'
    wave2.inputs['Scale'].default_value = 170.0; wave2.inputs['Distortion'].default_value = 6.0; wave2.inputs['Detail'].default_value = 2.0; wave2.inputs['Detail Scale'].default_value = 1.5
    nt.links.new(mp2.outputs[0], wave2.inputs['Vector'])
    # plume mask: only in some regions (noise) so the streaks look like scattered feathers
    mask = nt.nodes.new('ShaderNodeTexNoise'); mask.inputs['Scale'].default_value = 14.0; mask.inputs['Detail'].default_value = 1.0
    nt.links.new(tc.outputs['Object'], mask.inputs['Vector'])
    maskr = nt.nodes.new('ShaderNodeMapRange'); maskr.inputs['From Min'].default_value = 0.50; maskr.inputs['From Max'].default_value = 0.68
    nt.links.new(mask.outputs['Fac'], maskr.inputs['Value'])
    # streaks = mask * (0.7*plume + 0.5*fine) + 0.08*fine  (faint brushed look everywhere, plumes only in masked regions)
    fine = nt.nodes.new('ShaderNodeMath'); fine.operation = 'MULTIPLY'; fine.inputs[1].default_value = 0.5
    nt.links.new(wave.outputs['Fac'], fine.inputs[0])
    plume = nt.nodes.new('ShaderNodeMath'); plume.operation = 'MULTIPLY_ADD'; plume.inputs[1].default_value = 0.7
    nt.links.new(wave2.outputs['Fac'], plume.inputs[0]); nt.links.new(fine.outputs[0], plume.inputs[2])
    faint = nt.nodes.new('ShaderNodeMath'); faint.operation = 'MULTIPLY'; faint.inputs[1].default_value = 0.16
    nt.links.new(wave.outputs['Fac'], faint.inputs[0])
    comb = nt.nodes.new('ShaderNodeMath'); comb.operation = 'MULTIPLY_ADD'
    nt.links.new(plume.outputs[0], comb.inputs[0]); nt.links.new(maskr.outputs[0], comb.inputs[1]); nt.links.new(faint.outputs[0], comb.inputs[2])
    # colour mix: base sage -> lighter sage/cream along streaks
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'
    mix.inputs['A'].default_value = (0.36, 0.46, 0.27, 1); mix.inputs['B'].default_value = (0.62, 0.72, 0.48, 1)
    fac = nt.nodes.new('ShaderNodeMapRange'); fac.inputs['From Min'].default_value = 0.0; fac.inputs['From Max'].default_value = 1.2; fac.inputs['To Max'].default_value = 0.85
    nt.links.new(comb.outputs[0], fac.inputs['Value']); nt.links.new(fac.outputs[0], mix.inputs['Factor'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    # roughness variation along streaks (anisotropic-ish sheen)
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['From Max'].default_value = 1.2; rr.inputs['To Min'].default_value = 0.30; rr.inputs['To Max'].default_value = 0.12
    nt.links.new(comb.outputs[0], rr.inputs['Value']); nt.links.new(rr.outputs[0], b.inputs['Roughness'])
    b.inputs['Coat Roughness'].default_value = 0.08
    return m

def mat_screen():
    m = P.new_mat('MAT_PhoneScreen', (0.004, 0.004, 0.005, 1), rough=0.04, metal=0.0, coat=1.0)
    nt = m.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Coat Roughness'].default_value = 0.02; b.inputs['Specular IOR Level'].default_value = 0.6
    img = nt.nodes.new('ShaderNodeTexImage'); img.name = 'ScreenImage'; img.label = 'ScreenImage (plug a wallpaper here -> Emission Color)'
    img.location = (-700, 400)
    # placeholder procedural wallpaper: dark green field with two glowing rounded rings (HOT 70 style)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1100, 0)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-900, 0)
    mp.inputs['Scale'].default_value = (1 / 0.034, 1 / 0.034, 1)  # normalise half-width to 1
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    def ring(cy, rad, width, col):
        sub = nt.nodes.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = (0, cy, 0)
        nt.links.new(mp.outputs[0], sub.inputs[0])
        sc = nt.nodes.new('ShaderNodeVectorMath'); sc.operation = 'MULTIPLY'; sc.inputs[1].default_value = (1.0, 0.78, 1.0)
        nt.links.new(sub.outputs[0], sc.inputs[0])
        ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; nt.links.new(sc.outputs[0], ln.inputs[0])
        d = nt.nodes.new('ShaderNodeMath'); d.operation = 'SUBTRACT'; d.inputs[1].default_value = rad; nt.links.new(ln.outputs['Value'], d.inputs[0])
        a = nt.nodes.new('ShaderNodeMath'); a.operation = 'ABSOLUTE'; nt.links.new(d.outputs[0], a.inputs[0])
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = width; mr.inputs['From Max'].default_value = 0.0; mr.interpolation_type = 'SMOOTHSTEP'
        nt.links.new(a.outputs[0], mr.inputs['Value'])
        cm = nt.nodes.new('ShaderNodeMix'); cm.data_type = 'RGBA'; cm.inputs['A'].default_value = (0, 0, 0, 1); cm.inputs['B'].default_value = col
        nt.links.new(mr.outputs[0], cm.inputs['Factor'])
        return cm.outputs['Result']
    r1 = ring(0.75, 0.62, 0.30, (0.05, 0.75, 0.45, 1)); r2 = ring(-0.55, 0.70, 0.34, (0.03, 0.55, 0.40, 1))
    add = nt.nodes.new('ShaderNodeMix'); add.data_type = 'RGBA'; add.blend_type = 'ADD'; add.inputs['Factor'].default_value = 1.0
    nt.links.new(r1, add.inputs['A']); nt.links.new(r2, add.inputs['B'])
    # dark green base glow + vertical gradient
    base = nt.nodes.new('ShaderNodeMix'); base.data_type = 'RGBA'; base.blend_type = 'ADD'; base.inputs['Factor'].default_value = 1.0
    base.inputs['B'].default_value = (0.004, 0.03, 0.02, 1)
    nt.links.new(add.outputs['Result'], base.inputs['A'])
    nt.links.new(base.outputs['Result'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 1.2
    return m

MAT_FRAME = mat_frame(); MAT_DARK = mat_dark(); MAT_BACK = mat_back(); MAT_SCREEN = mat_screen()
MAT_GLASS_BLACK = P.new_mat('MAT_PhoneGlassBlack', (0.01, 0.01, 0.012, 1), rough=0.03, coat=1.0)
MAT_ISLAND = P.new_mat('MAT_PhoneIsland', (0.46, 0.54, 0.44, 1), rough=0.25, metal=0.9)
MAT_RING = P.new_mat('MAT_PhoneLensRing', (0.58, 0.60, 0.66, 1), rough=0.18, metal=1.0)
MAT_LENS_GLASS = P.new_mat('MAT_PhoneLensGlass', (0.75, 0.85, 0.9, 1), rough=0.02, transmission=1.0, ior=1.5)
MAT_LENS = P.new_mat('MAT_PhoneLensElement', (0.01, 0.012, 0.02, 1), rough=0.08, coat=0.8)
MAT_LENS_IRIS = P.new_mat('MAT_PhoneLensIris', (0.08, 0.04, 0.14, 1), rough=0.15, metal=0.4)
MAT_ACCENT = P.new_mat('MAT_PhoneAccent', (0.85, 0.22, 0.04, 1), rough=0.35)
MAT_FLASH = P.new_mat('MAT_PhoneFlash', (0.95, 0.88, 0.62, 1), rough=0.1, emission=(1.0, 0.9, 0.6, 1), estrength=0.4)
MAT_LOGO = P.new_mat('MAT_PhoneLogo', (0.75, 0.80, 0.72, 1), rough=0.25, metal=0.6)

# ------------------------------------------------------------------ geometry helpers
def rr_points(w, h, r, segs=10, cx=0.0, cy=0.0):
    """Rounded rectangle outline (CCW) in a local 2D (u,v) plane."""
    r = max(1e-6, min(r, w / 2, h / 2)); pts = []
    corners = [(cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90), (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)]
    for x, y, a0 in corners:
        for i in range(segs + 1):
            a = math.radians(a0 + i * 90 / segs); pts.append((x + r * math.cos(a), y + r * math.sin(a)))
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > 1e-7 or abs(p[1] - out[-1][1]) > 1e-7): out.append(p)
    if abs(out[0][0] - out[-1][0]) < 1e-7 and abs(out[0][1] - out[-1][1]) < 1e-7: out.pop()
    return out

def circle_points(r, segs=48, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs)) for i in range(segs)]

M_XY = Matrix.Identity(4)                                   # (u,v,w) -> (x,y,z)
M_XZ = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # (u,v,w) -> (x=u, y=w, z=v)   bottom/top edge features
M_YZ = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # (u,v,w) -> (x=w, y=u, z=v)   side features

def prism(bm, pts, w0, w1, M=M_XY, offset=(0, 0, 0), mat=0):
    """Extrude closed 2D outline from w0 to w1 along local w, mapped through M then offset. Returns faces."""
    off = Vector(offset)
    vb = [bm.verts.new((M @ Vector((u, v, w0, 1))).to_3d() + off) for u, v in pts]
    vt = [bm.verts.new((M @ Vector((u, v, w1, 1))).to_3d() + off) for u, v in pts]
    faces = [bm.faces.new(vb[::-1]), bm.faces.new(vt)]
    n = len(pts)
    for i in range(n):
        faces.append(bm.faces.new((vb[i], vb[(i + 1) % n], vt[(i + 1) % n], vt[i])))
    for f in faces: f.material_index = mat
    return faces

def dome_disc(bm, R, z0, height, segs=48, rings=5, offset=(0, 0, 0), flip=False, mat=0):
    """Slightly domed disc (lens glass), facing +Z (or -Z when flip)."""
    off = Vector(offset); s = -1 if flip else 1
    centre = bm.verts.new(Vector((0, 0, z0 + s * height)) + off); loops = []
    for k in range(1, rings + 1):
        r = R * k / rings; z = z0 + s * height * (1 - (k / rings) ** 2)
        loops.append([bm.verts.new(Vector((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z)) + off) for i in range(segs)])
    faces = []
    for i in range(segs):
        faces.append(bm.faces.new((centre, loops[0][i], loops[0][(i + 1) % segs])))
    for k in range(rings - 1):
        a, b_ = loops[k], loops[k + 1]
        for i in range(segs): faces.append(bm.faces.new((a[i], b_[i], b_[(i + 1) % segs], a[(i + 1) % segs])))
    for f in faces: f.material_index = mat
    return faces

def finish(bm, name, mats, smooth=True, parent=True, col=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    if smooth: me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me); (col or COL).objects.link(ob)
    if parent: ob.parent = ROOT_E
    return ob

def bevel(ob, width, segs=4, angle=30, harden=True):
    md = ob.modifiers.new('Bevel', 'BEVEL'); md.width = width; md.segments = segs; md.limit_method = 'ANGLE'; md.angle_limit = math.radians(angle)
    md.harden_normals = harden; md.miter_outer = 'MITER_ARC'; md.use_clamp_overlap = True
    return md

def boolean(ob, cutter, op='DIFFERENCE', name='Cut'):
    md = ob.modifiers.new(name, 'BOOLEAN'); md.operation = op; md.solver = 'EXACT'; md.object = cutter; md.material_mode = 'TRANSFER'
    cutter.hide_render = True; cutter.hide_viewport = True; cutter.display_type = 'WIRE'
    return md

# ------------------------------------------------------------------ BODY (frame + back)
bm = bmesh.new()
prism(bm, rr_points(W, L, R_CORNER, segs=14), -HT, HT)
BODY = finish(bm, 'PHONE_Body', [MAT_FRAME, MAT_BACK, MAT_DARK])
for p in BODY.data.polygons:   # caps: back = green, top (under glass) = dark; sides = frame metal
    p.material_index = (1 if p.center.z < 0 else 2) if len(p.vertices) > 4 else 0
bevel(BODY, 0.0014, segs=7, angle=30)

# cutter geometry for body: side buttons, SIM slot, bottom edge features
cb = bmesh.new()
BTN = {  # name: (y centre, length along Y, height along Z, protrusion)
    'vol': (+0.0083, 0.0135, 0.0024, 0.0007),
    'pwr': (-0.0248, 0.0100, 0.0024, 0.0007),
}
for k, (yc, ln, hz, pr) in BTN.items():
    prism(cb, rr_points(ln + 0.0004, hz + 0.0004, 0.0008, 6, cy=0), W / 2 - 0.0012, W / 2 + 0.002, M_YZ, offset=(0, yc, 0))
# SIM tray outline (shallow recess) on the right side above the volume rocker
prism(cb, rr_points(0.0115, 0.0022, 0.0009, 6), W / 2 - 0.00015, W / 2 + 0.002, M_YZ, offset=(0, +0.0289, 0))
prism(cb, circle_points(0.00035, 16), W / 2 - 0.0012, W / 2 + 0.002, M_YZ, offset=(0, +0.0289 + 0.0042, 0))
# bottom edge (y = -L/2): USB-C centred, speaker slot (+X side), mic hole (-X side)
prism(cb, rr_points(0.0088, 0.0030, 0.0014, 8), -L / 2 - 0.002, -L / 2 + 0.0065, M_XZ, offset=(0, 0, 0))
prism(cb, rr_points(0.0145, 0.0016, 0.0008, 6), -L / 2 - 0.002, -L / 2 + 0.003, M_XZ, offset=(+0.0190, 0, 0))
prism(cb, circle_points(0.0006, 16), -L / 2 - 0.002, -L / 2 + 0.003, M_XZ, offset=(-0.0170, 0, 0))
# top edge: secondary mic hole
prism(cb, circle_points(0.0006, 16), L / 2 - 0.003, L / 2 + 0.002, M_XZ, offset=(-0.012, 0, 0))
CUT_BODY = finish(cb, 'PHONE_CUT_Body', [MAT_DARK], smooth=False)
boolean(BODY, CUT_BODY)

# USB-C tongue inside the port
bm = bmesh.new(); prism(bm, rr_points(0.0066, 0.0007, 0.0003, 4), -L / 2 + 0.0012, -L / 2 + 0.0062, M_XZ)
finish(bm, 'PHONE_UsbTongue', [MAT_DARK])

# buttons
for k, (yc, ln, hz, pr) in BTN.items():
    bm = bmesh.new(); prism(bm, rr_points(ln, hz, 0.0008, 6), W / 2 - 0.0012, W / 2 + pr, M_YZ, offset=(0, yc, 0))
    ob = finish(bm, 'PHONE_Btn_' + ('Volume' if k == 'vol' else 'Power'), [MAT_ACCENT if k == 'pwr' else MAT_FRAME])
    bevel(ob, 0.0004, 3, 40)
# SIM tray face (sits flush in its recess)
bm = bmesh.new(); prism(bm, rr_points(0.0109, 0.0017, 0.0008, 6), W / 2 - 0.0010, W / 2 - 0.00004, M_YZ, offset=(0, +0.0289, 0))
finish(bm, 'PHONE_SimTray', [MAT_FRAME])

# ------------------------------------------------------------------ SCREEN (glass + display + punch hole)
Z_GLASS = HT + 0.00006; Z_DISP = HT + 0.00016
bm = bmesh.new(); prism(bm, rr_points(W - 0.0024, L - 0.0024, R_CORNER - 0.0012, 14), HT - 0.0002, Z_GLASS)
GLASS = finish(bm, 'PHONE_ScreenGlass', [MAT_GLASS_BLACK])
bm = bmesh.new(); prism(bm, rr_points(W - 0.0068, L - 0.0078, R_CORNER - 0.0034, 14, cy=-0.0004), Z_GLASS, Z_DISP)
DISP = finish(bm, 'PHONE_Display', [MAT_SCREEN])
# punch-hole camera: black disc + tiny lens
PH_Y = L / 2 - 0.0062
bm = bmesh.new(); prism(bm, circle_points(0.0017, 40), Z_DISP, Z_DISP + 0.00004, offset=(0, PH_Y, 0))
finish(bm, 'PHONE_PunchHole', [MAT_DARK])
bm = bmesh.new(); dome_disc(bm, 0.0009, Z_DISP + 0.00004, 0.00003, 32, 3, offset=(0, PH_Y, 0))
finish(bm, 'PHONE_FrontLens', [MAT_LENS])
# earpiece slit at the very top of the frame/glass seam
bm = bmesh.new(); prism(bm, rr_points(0.012, 0.0006, 0.0003, 4, cy=L / 2 - 0.0009), Z_GLASS, Z_GLASS + 0.00004)
finish(bm, 'PHONE_Earpiece', [MAT_DARK])

SC = bpy.data.objects.new('PHONE_SCREEN_CENTER', None); SC.empty_display_size = 0.01; SC.location = (0, -0.0004, Z_DISP); COL.objects.link(SC); SC.parent = ROOT_E

# ------------------------------------------------------------------ CAMERA ISLAND (back, top-left when viewed from the back => +X, +Y)
ISL_W, ISL_L = 0.0152, 0.0480
ISL_X = W / 2 - 0.0163; ISL_Y = L / 2 - 0.0298
ISL_H = 0.0017                                   # protrusion from back plane
Z_BACK = -HT; Z_ISL = Z_BACK - ISL_H             # island top face
bm = bmesh.new(); prism(bm, rr_points(ISL_W, ISL_L, ISL_W / 2, 16), Z_BACK + 0.0003, Z_ISL, offset=(ISL_X, ISL_Y, 0))
ISLAND = finish(bm, 'PHONE_CameraIsland', [MAT_ISLAND])
bevel(ISLAND, 0.0009, 5, 30)
# module layout (centres along Y). Top two: squircle glass modules, bottom: thick squircle ring
LENS_Y = [L / 2 - 0.0152, L / 2 - 0.0280, L / 2 - 0.0432]
MOD = 0.0118                                      # module squircle size
# recess cutter in the island for the three modules
cb = bmesh.new()
for y in LENS_Y: prism(cb, rr_points(MOD + 0.0006, MOD + 0.0006, 0.0038, 10), Z_ISL - 0.001, Z_ISL + 0.0005, offset=(ISL_X, y, 0))
CUT_ISL = finish(cb, 'PHONE_CUT_Island', [MAT_DARK], smooth=False)
boolean(ISLAND, CUT_ISL)

for i, y in enumerate(LENS_Y):
    off = (ISL_X, y, 0)
    if i < 2:
        # metal squircle frame
        bm = bmesh.new(); prism(bm, rr_points(MOD, MOD, 0.0036, 10), Z_ISL + 0.0005, Z_ISL - 0.0007, offset=off)
        ring = finish(bm, f'PHONE_LensFrame_{i+1}', [MAT_RING]); bevel(ring, 0.00025, 3, 40)
        # dark squircle glass insert
        bm = bmesh.new(); prism(bm, rr_points(MOD - 0.0018, MOD - 0.0018, 0.0030, 10), Z_ISL - 0.0004, Z_ISL - 0.00072, offset=off)
        finish(bm, f'PHONE_LensInsert_{i+1}', [MAT_GLASS_BLACK])
        # lens element + iris + glass dome
        bm = bmesh.new(); prism(bm, circle_points(0.0034, 48), Z_ISL - 0.00072, Z_ISL - 0.00076, offset=off); finish(bm, f'PHONE_LensRim_{i+1}', [MAT_LENS_IRIS])
        bm = bmesh.new(); prism(bm, circle_points(0.0024, 48), Z_ISL - 0.00076, Z_ISL - 0.00080, offset=off); finish(bm, f'PHONE_LensElement_{i+1}', [MAT_LENS])
        bm = bmesh.new(); dome_disc(bm, 0.0036, Z_ISL - 0.00080, 0.00030, 48, 5, offset=off, flip=True)
        g = finish(bm, 'PHONE_LENS_MAIN' if i == 0 else f'PHONE_LensGlass_{i+1}', [MAT_LENS_GLASS])
    else:
        # thick squircle ring with a round dark lens (annulus: outer squircle, inner circle, bridged caps)
        bm = bmesh.new()
        outer = rr_points(MOD, MOD, 0.0040, 12); inner = circle_points(0.0036, len(outer))
        zt, zb = Z_ISL - 0.0009, Z_ISL + 0.0005
        vo_b = [bm.verts.new((u + ISL_X, v + y, zb)) for u, v in outer]; vo_t = [bm.verts.new((u + ISL_X, v + y, zt)) for u, v in outer]
        vi_b = [bm.verts.new((u + ISL_X, v + y, zb)) for u, v in inner]; vi_t = [bm.verts.new((u + ISL_X, v + y, zt)) for u, v in inner]
        n = len(outer)
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((vo_b[k], vo_b[k2], vo_t[k2], vo_t[k]))      # outer wall
            bm.faces.new((vi_b[k], vi_b[k2], vi_t[k2], vi_t[k]))      # inner wall
            bm.faces.new((vo_t[k], vo_t[k2], vi_t[k2], vi_t[k]))      # top annulus
            bm.faces.new((vo_b[k], vo_b[k2], vi_b[k2], vi_b[k]))      # bottom annulus
        ring = finish(bm, 'PHONE_LensFrame_3', [MAT_RING]); bevel(ring, 0.00025, 3, 40)
        bm = bmesh.new(); prism(bm, circle_points(0.0037, 48), Z_ISL - 0.0002, Z_ISL - 0.00070, offset=off); finish(bm, 'PHONE_LensInsert_3', [MAT_GLASS_BLACK])
        bm = bmesh.new(); prism(bm, circle_points(0.0022, 48), Z_ISL - 0.00070, Z_ISL - 0.00074, offset=off); finish(bm, 'PHONE_LensElement_3', [MAT_LENS])
        bm = bmesh.new(); dome_disc(bm, 0.0036, Z_ISL - 0.00074, 0.00022, 48, 5, offset=off, flip=True); finish(bm, 'PHONE_LensGlass_3', [MAT_LENS_GLASS])

# LED flash: small rounded square to the right of the island (towards the centre => -X), near the top
bm = bmesh.new(); prism(bm, rr_points(0.0030, 0.0030, 0.0008, 6), Z_BACK + 0.0002, Z_BACK - 0.00025, offset=(ISL_X - 0.0145, L / 2 - 0.0133, 0))
FLASH = finish(bm, 'PHONE_Flash', [MAT_FLASH]); bevel(FLASH, 0.0002, 2, 40)
bm = bmesh.new(); prism(bm, rr_points(0.0036, 0.0036, 0.0010, 6), Z_BACK + 0.0002, Z_BACK - 0.00012, offset=(ISL_X - 0.0145, L / 2 - 0.0133, 0))
finish(bm, 'PHONE_FlashRing', [MAT_RING])

# ------------------------------------------------------------------ WORDMARK "Infinix" (vertical, bottom-left of back)
font_path = P.find_font(['/usr/share/fonts/truetype/inter/InterDisplay-Medium.ttf', P.FONT_SANS, '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
cu = bpy.data.curves.new('PHONE_Wordmark', 'FONT'); cu.body = 'Infinix'; cu.size = 0.0074; cu.extrude = 0.00005; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
cu.space_character = 0.98
if font_path: cu.font = bpy.data.fonts.load(font_path)
LOGO = bpy.data.objects.new('PHONE_Wordmark', cu); COL.objects.link(LOGO)
# reading direction +Y, letter-up +X, facing -Z  ==> Euler XYZ (180deg, 0, 90deg)
LOGO.rotation_euler = (math.pi, 0, math.pi / 2); LOGO.location = (W / 2 - 0.0085, -L / 2 + 0.0275, Z_BACK - 0.00005)
bpy.context.view_layer.objects.active = LOGO; LOGO.select_set(True); bpy.ops.object.convert(target='MESH'); LOGO.select_set(False)
LOGO.data.materials.append(MAT_LOGO); LOGO.parent = ROOT_E

# ------------------------------------------------------------------ housekeeping
for ob in COL.objects:
    if ob.type == 'MESH': ob.data.use_auto_texspace = True
tri_count = 0
dg = bpy.context.evaluated_depsgraph_get()
for ob in COL.objects:
    if ob.type == 'MESH' and not ob.hide_render:
        me = ob.evaluated_get(dg).to_mesh(); me.calc_loop_triangles(); tri_count += len(me.loop_triangles); ob.evaluated_get(dg).to_mesh_clear()
print(f'[phone] render triangles: {tri_count}')

ROOT_E.location = (0, 0, 0)
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
print('[phone] saved', OUT_BLEND)

# ------------------------------------------------------------------ PREVIEW RENDERS (not saved into the asset file)
if RENDER:
    os.makedirs(OUT_PREV, exist_ok=True)
    PREV = bpy.data.collections.new('PHONE_PREVIEW'); bpy.context.scene.collection.children.link(PREV)
    def area(name, loc, power, size, color=(1, 1, 1), target=(0, 0, 0)):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.size = size; ld.color = color; ld.shape = 'RECTANGLE'; ld.size_y = size * 0.6
        ob = bpy.data.objects.new(name, ld); PREV.objects.link(ob); ob.location = loc
        tgt = bpy.data.objects.new(name + '_tgt', None); PREV.objects.link(tgt); tgt.location = target
        c = ob.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        return ob
    area('KEY', (0.30, -0.28, 0.40), 3.2, 0.60, (1.0, 0.97, 0.92))
    area('FILL', (-0.40, -0.20, 0.22), 1.4, 0.80, (0.9, 0.95, 1.0))
    area('RIM', (-0.10, 0.32, 0.28), 3.5, 0.50, (1.0, 1.0, 1.0))
    # long soft strip light to draw a highlight line along the frame / glossy surfaces
    area('STRIP', (0.02, 0.02, 0.55), 1.3, 1.0, (1, 1, 1)).data.size_y = 0.16
    # world: dark vertical gradient
    sc = bpy.context.scene; w = sc.world or bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True; nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground'); tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.010, 0.012, 0.018, 1); ramp.color_ramp.elements[1].color = (0.075, 0.085, 0.105, 1)
    lp = nt.nodes.new('ShaderNodeLightPath'); mixc = nt.nodes.new('ShaderNodeMix'); mixc.data_type = 'RGBA'
    mixc.inputs['A'].default_value = (0.10, 0.11, 0.13, 1)   # what the phone reflects (soft grey studio)
    nt.links.new(tc.outputs['Window'], sep.inputs[0]); nt.links.new(sep.outputs['Y'], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], mixc.inputs['B']); nt.links.new(lp.outputs['Is Camera Ray'], mixc.inputs['Factor'])
    nt.links.new(mixc.outputs['Result'], bg.inputs[0]); bg.inputs[1].default_value = 1.0; nt.links.new(bg.outputs[0], out.inputs[0])

    P.setup_render(res=(1280, 720), samples=48, denoise=True, exposure=0.0)
    sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.max_bounces = 8; sc.cycles.transmission_bounces = 8; sc.cycles.glossy_bounces = 4
    tgt = bpy.data.objects.new('CAM_TARGET', None); PREV.objects.link(tgt); tgt.location = (0, 0, 0)
    cam = P.add_camera('CAM_PREVIEW', loc=(0.185, -0.060, 0.200), target=tgt, lens=55)
    PREV.objects.link(cam); bpy.context.scene.collection.objects.unlink(cam)

    def render(path):
        sc.render.filepath = path; bpy.ops.render.render(write_still=True); print('[phone] rendered', path)

    render(os.path.join(OUT_PREV, 'asset_phone_front.png'))
    # back view: flip the phone over (rotate 180deg about Y) so the back faces the camera
    ROOT_E.rotation_euler = (0, math.pi, 0)
    render(os.path.join(OUT_PREV, 'asset_phone_back.png'))
    ROOT_E.rotation_euler = (0, 0, 0)
