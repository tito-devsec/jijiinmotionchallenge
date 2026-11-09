"""Procedural rigged humanoid characters for POSTA_2040.
Run:  /opt/blender/blender -b --python scripts/assets/build_characters.py [-- --norender]
Builds HERO, CIVILIAN_A, CIVILIAN_B, WORKER, PASSENGER, DIVER into blender/assets/characters.blend
(one collection per variant, root empty '<NAME>_root' at feet centre, facing +Y, armature 'RIG_<NAME>')
and renders previews/asset_characters_lineup.png and previews/asset_hero_walk.png.
"""
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
import posta_lib as P
import character_anim as A

OUT_BLEND = os.path.join(ROOT, 'blender', 'assets', 'characters.blend')
PREV = os.path.join(ROOT, 'previews')
NORENDER = '--norender' in sys.argv
QUICK = '--quick' in sys.argv

# ----------------------------------------------------------------------------- scene reset
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'

def override(obj, extra=None):
    objs = [obj] + (extra or [])
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return bpy.context.temp_override(object=obj, active_object=obj, selected_objects=objs,
                                     selected_editable_objects=objs, view_layer=bpy.context.view_layer)

def link(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj

# ----------------------------------------------------------------------------- geometry helpers
class Shape:
    """Accumulates verts/faces of closed lofts and ellipsoids, then makes one mesh object."""
    def __init__(self):
        self.v = []; self.f = []

    def loft(self, path, segs=28, vhint=(0, 1, 0), caps=True):
        """path: list of (center(3), ru, rv[, (du, dv) offset of ring centre in the ring plane]).
        Frame: direction d along path, v ~ vhint, u = d x v. Closed tube with end caps."""
        n = len(path); base = len(self.v)
        pts = [Vector(p[0]) for p in path]
        for i, p in enumerate(path):
            c = pts[i]
            d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            vh = Vector(vhint)
            if abs(d.dot(vh)) > 0.95: vh = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((0, 1, 0))
            u = d.cross(vh).normalized(); v = u.cross(d).normalized()
            ru, rv = p[1], p[2]
            off = p[3] if len(p) > 3 else (0, 0)
            c = c + u * off[0] + v * off[1]
            for k in range(segs):
                a = 2 * math.pi * k / segs
                self.v.append(tuple(c + u * (ru * math.cos(a)) + v * (rv * math.sin(a))))
        for i in range(n - 1):
            for k in range(segs):
                a = base + i * segs + k; b = base + i * segs + (k + 1) % segs
                self.f.append((a, b, b + segs, a + segs))
        if caps:
            self.f.append(tuple(base + k for k in range(segs))[::-1])
            self.f.append(tuple(base + (n - 1) * segs + k for k in range(segs)))
        return self

    def ellipsoid(self, c, r, segs=20, rings=12, rot=None):
        base = len(self.v)
        R = Matrix.Rotation(rot[1], 3, rot[0]) if rot else Matrix.Identity(3)
        for j in range(1, rings):
            th = math.pi * j / rings
            for k in range(segs):
                a = 2 * math.pi * k / segs
                p = Vector((r[0] * math.sin(th) * math.cos(a), r[1] * math.sin(th) * math.sin(a), r[2] * math.cos(th)))
                self.v.append(tuple(Vector(c) + R @ p))
        top = len(self.v); self.v.append(tuple(Vector(c) + R @ Vector((0, 0, r[2]))))
        bot = len(self.v); self.v.append(tuple(Vector(c) + R @ Vector((0, 0, -r[2]))))
        for j in range(rings - 2):
            for k in range(segs):
                a = base + j * segs + k; b = base + j * segs + (k + 1) % segs
                self.f.append((a, a + segs, b + segs, b))
        for k in range(segs):
            self.f.append((top, base + k, base + (k + 1) % segs))
            j = rings - 2
            self.f.append((bot, base + j * segs + (k + 1) % segs, base + j * segs + k))
        return self

    def capsule(self, a, b, ra, rb=None, segs=20):
        rb = ra if rb is None else rb
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized(); L = (b - a).length
        path = []
        for t in (0.0, 0.5, 1.0):
            r = ra + (rb - ra) * t
            path.append((tuple(a + d * (L * t)), r, r))
        self.loft(path, segs=segs)
        self.ellipsoid(tuple(a), (ra, ra, ra), segs=segs)
        self.ellipsoid(tuple(b), (rb, rb, rb), segs=segs)
        return self

    def to_object(self, name, col):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.validate(); me.update()
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); col.objects.link(ob)
        return ob


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data; ob.data = me; ob.modifiers.clear()
    bpy.data.meshes.remove(old)
    return ob


def remesh_smooth(ob, voxel=0.01, smooth_iter=3, lam=0.6, max_tris=60000):
    rm = ob.modifiers.new('Remesh', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = voxel; rm.use_smooth_shade = True
    ls = ob.modifiers.new('LapSmooth', 'LAPLACIANSMOOTH'); ls.iterations = smooth_iter; ls.lambda_factor = lam
    ls.lambda_border = 0.0; ls.use_volume_preserve = True; ls.use_normalized = True
    apply_modifiers(ob)
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if tris > max_tris:
        dm = ob.modifiers.new('Decimate', 'DECIMATE'); dm.ratio = max_tris / tris * 0.95
        apply_modifiers(ob)
    shade_smooth(ob)
    recalc_normals(ob)
    return ob


def shade_smooth(ob):
    me = ob.data
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.update()


def recalc_normals(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data); bm.free(); ob.data.update()


def displace_gaussian(ob, center, sigma, depth, normal_dir=None):
    """Push verts near 'center' along -normal (depth>0 = indent) with anisotropic gaussian sigma=(sx,sy,sz)."""
    me = ob.data; n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    nm = np.empty(n * 3); me.vertices.foreach_get('normal', nm); nm = nm.reshape(n, 3)
    d = (co - np.array(center)) / np.array(sigma)
    w = np.exp(-0.5 * (d ** 2).sum(1))
    dirv = nm if normal_dir is None else np.tile(np.array(normal_dir, dtype=float), (n, 1))
    co = co - dirv * (w * depth)[:, None]
    me.vertices.foreach_set('co', co.ravel()); me.update()


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)

# ----------------------------------------------------------------------------- materials
def skin_material(name, base=(0.18, 0.09, 0.05, 1)):
    m = P.new_mat(name, base, rough=0.45)
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Subsurface Weight'].default_value = 0.25
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.3, 0.12)
    b.inputs['Subsurface Scale'].default_value = 0.012
    b.inputs['Specular IOR Level'].default_value = 0.4
    b.inputs['Coat Weight'].default_value = 0.08; b.inputs['Coat Roughness'].default_value = 0.35
    return m

def cloth_material(name, color, rough=0.85, sheen=0.6):
    m = P.new_mat(name, color, rough=rough)
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Sheen Weight'].default_value = sheen; b.inputs['Sheen Roughness'].default_value = 0.5
    # subtle woven bump
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 900.0; tex.inputs['Detail'].default_value = 1.0
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08; bump.inputs['Distance'].default_value = 0.002
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def tint(col, f):
    return (col[0] * f, col[1] * f, col[2] * f, 1.0)

# ----------------------------------------------------------------------------- body landmarks
class Body:
    """Anatomical landmark table scaled to height (metres). 7.5-head canon."""
    def __init__(self, height=1.75, female=False, bulk=1.0, shoulder=1.0, hip=1.0):
        self.s = height / 1.75; self.female = female; self.bulk = bulk
        s = self.s
        self.H = height
        self.z = dict(top=1.75, chin=1.52, jaw=1.555, eye=1.655, nose=1.62, mouth=1.567,
                      neck_base=1.44, shoulder=1.405, nipple=1.27, waist=1.07, navel=1.04,
                      hip=0.90, crotch=0.80, knee=0.47, ankle=0.08, elbow=1.12, wrist=0.845)
        for k in self.z: self.z[k] *= s
        sw = shoulder * (0.93 if female else 1.0)
        hw = hip * (1.08 if female else 1.0)
        self.shoulder_x = 0.175 * s * sw
        self.hip_x = 0.095 * s * hw
        self.elbow = Vector((0.235 * s * sw, -0.015 * s, self.z['elbow']))
        self.wrist = Vector((0.285 * s * sw, 0.0, self.z['wrist']))
        self.hand_end = Vector((0.315 * s * sw, 0.01 * s, self.z['wrist'] - 0.18 * s))
        self.shoulder = Vector((self.shoulder_x, 0.0, self.z['shoulder']))
        self.hip = Vector((self.hip_x, 0.0, self.z['hip']))
        self.knee = Vector((self.hip_x * 0.95, 0.0, self.z['knee']))
        self.ankle = Vector((self.hip_x * 0.95, -0.02 * s, self.z['ankle']))
        self.toe = Vector((self.hip_x * 0.95, 0.20 * s, 0.02 * s))
        self.head_c = Vector((0, 0, (self.z['top'] + self.z['chin']) / 2))
        self.sw = sw; self.hw = hw

    def mirror(self, v, side):
        return Vector((v.x * side, v.y, v.z))


def torso_table(B):
    s, z, bk, fem = B.s, B.z, B.bulk, B.female
    sw, hw = B.sw, B.hw
    return [(z['crotch'] + 0.0 * s, 0.105 * hw, 0.085, -0.01),
            (z['hip'] - 0.03 * s, 0.165 * hw, 0.115, -0.015),
            (z['hip'] + 0.06 * s, 0.168 * hw, 0.11, -0.01),
            (z['waist'], 0.138 * (0.93 if fem else 1.0) * bk, 0.098 * bk, 0.0),
            (z['waist'] + 0.08 * s, 0.15 * bk, 0.105 * bk, 0.0),
            (z['nipple'], 0.162 * sw * bk, 0.112 * bk, 0.0),
            (z['nipple'] + 0.08 * s, 0.172 * sw * bk, 0.108 * bk, 0.0),
            (z['shoulder'], 0.16 * sw * bk, 0.095, 0.0),
            (z['neck_base'] + 0.02 * s, 0.085, 0.07, 0.005)]

def torso_section(B, zz):
    tab = torso_table(B)
    if zz <= tab[0][0]: return tab[0][1:]
    if zz >= tab[-1][0]: return tab[-1][1:]
    for (a, b) in zip(tab, tab[1:]):
        if a[0] <= zz <= b[0]:
            t = (zz - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))

def torso_shell(S, B, off, zb, zt, n=12, deltoids=True, breasts=True, hips_extra=0.0):
    """Closed shell loft following the torso between zb and zt, inflated by off (clothing)."""
    s, z = B.s, B.z
    path = []
    for i in range(n + 1):
        zz = zb + (zt - zb) * i / n
        rx, ry, cy = torso_section(B, zz)
        g = max(0.0, 1 - abs(zz - (z['hip'] - 0.015 * s)) / (0.12 * s))  # glute / hip fullness
        path.append(((0, cy * s - 0.02 * s * g, zz), rx * s + off + hips_extra * g, ry * s + off + 0.045 * s * g))
    S.loft(path, segs=32)
    if deltoids:
        for sd in (-1, 1):
            S.ellipsoid((sd * (B.shoulder_x - 0.005 * s), 0, z['shoulder'] - 0.01 * s), (0.062 * s * B.bulk + off, 0.062 * s * B.bulk + off, 0.075 * s * B.bulk + off))
    if breasts and B.female:
        for sd in (-1, 1):
            S.ellipsoid((sd * 0.078 * s, 0.085 * s, z['nipple'] + 0.005 * s), (0.065 * s + off, 0.055 * s + off, 0.06 * s + off))
    return S

def body_shape(B, offset=0.0, parts=('torso', 'arms', 'legs', 'head', 'hands', 'feet')):
    """Returns a Shape with all limbs overlapping (to be unioned by voxel remesh).
    offset>0 inflates radii (for clothing shells)."""
    s, z, bk = B.s, B.z, B.bulk
    o = offset
    S = Shape()
    fem = B.female
    if 'torso' in parts:
        sw, hw = B.sw, B.hw
        # torso loft: (z, rx, ry, cy)
        tor = torso_table(B)
        path = [((0, cy * s, zz), rx * s + o, ry * s + o) for (zz, rx, ry, cy) in tor]
        S.loft(path, segs=32)
        # deltoids
        for sd in (-1, 1):
            S.ellipsoid((sd * (B.shoulder_x - 0.005 * s), 0, z['shoulder'] - 0.01 * s), (0.062 * s * bk + o, 0.062 * s * bk + o, 0.075 * s * bk + o))
        if fem and offset < 0.02:
            for sd in (-1, 1):
                S.ellipsoid((sd * 0.078 * s, 0.085 * s, z['nipple'] + 0.005 * s), (0.065 * s + o, 0.055 * s + o, 0.06 * s + o))
        # glutes
        for sd in (-1, 1):
            S.ellipsoid((sd * 0.085 * s * hw, -0.075 * s, z['hip'] - 0.015 * s), (0.1 * s + o, 0.085 * s + o, 0.11 * s + o))
        # neck
        S.loft([((0, 0.005 * s, z['neck_base'] - 0.03 * s), 0.065 * s + o, 0.065 * s + o),
                ((0, 0.01 * s, z['neck_base'] + 0.05 * s), 0.056 * s + o, 0.06 * s + o),
                ((0, 0.012 * s, z['chin'] + 0.02 * s), 0.06 * s + o, 0.065 * s + o)], segs=24)
    if 'head' in parts:
        hd = [(z['chin'] - 0.004 * s, 0.03, 0.03, 0.035),
              (z['chin'] + 0.02 * s, 0.056, 0.06, 0.03),
              (z['jaw'] + 0.015 * s, 0.07, 0.085, 0.012),
              (z['nose'], 0.076, 0.096, 0.0),
              (z['eye'], 0.079, 0.1, -0.002),
              (z['eye'] + 0.045 * s, 0.078, 0.098, -0.004),
              (z['top'] - 0.04 * s, 0.068, 0.088, -0.008),
              (z['top'] - 0.012 * s, 0.045, 0.06, -0.012),
              (z['top'], 0.012, 0.016, -0.015)]
        S.loft([((0, cy * s, zz), rx * s + o, ry * s + o) for (zz, rx, ry, cy) in hd], segs=32)
        if offset == 0.0:
            # nose, chin, ears, brow ridge, cheeks
            S.ellipsoid((0, 0.1 * s, z['nose'] - 0.002 * s), (0.015 * s, 0.024 * s, 0.03 * s), rot=('X', math.radians(-12)))
            S.ellipsoid((0, 0.108 * s, z['nose'] - 0.02 * s), (0.017 * s, 0.014 * s, 0.011 * s))
            S.ellipsoid((0, 0.082 * s, z['chin'] + 0.012 * s), (0.032 * s, 0.03 * s, 0.028 * s))
            S.ellipsoid((0, 0.092 * s, z['mouth'] - 0.012 * s), (0.03 * s, 0.018 * s, 0.014 * s))  # lower lip/chin pad
            S.ellipsoid((0, 0.094 * s, z['mouth'] + 0.01 * s), (0.028 * s, 0.014 * s, 0.01 * s))  # upper lip
            for sd in (-1, 1):
                S.ellipsoid((sd * 0.078 * s, -0.005 * s, z['eye'] - 0.01 * s), (0.009 * s, 0.016 * s, 0.026 * s))  # ear
                S.ellipsoid((sd * 0.05 * s, 0.08 * s, z['eye'] - 0.035 * s), (0.03 * s, 0.025 * s, 0.025 * s))  # cheek
                S.ellipsoid((sd * 0.034 * s, 0.092 * s, z['eye'] + 0.022 * s), (0.028 * s, 0.014 * s, 0.009 * s))  # brow ridge
    if 'arms' in parts:
        for sd in (-1, 1):
            sh = B.mirror(B.shoulder, sd); el = B.mirror(B.elbow, sd); wr = B.mirror(B.wrist, sd)
            up = [sh + (el - sh) * t for t in (0.0, 0.3, 0.6, 1.0)]
            ru = [0.055 * bk, 0.052 * bk, 0.045 * bk, 0.038]
            S.loft([(tuple(up[i]), ru[i] * s + o, (ru[i] * 0.95) * s + o) for i in range(4)], segs=20)
            fo = [el + (wr - el) * t for t in (0.0, 0.25, 0.6, 1.0)]
            rf = [0.038, 0.044 * bk, 0.034, 0.027]
            rf2 = [0.038, 0.042 * bk, 0.03, 0.021]
            S.loft([(tuple(fo[i]), rf[i] * s + o, rf2[i] * s + o) for i in range(4)], segs=20)
            S.ellipsoid(tuple(el), (0.04 * s + o,) * 3)
    if 'hands' in parts:
        for sd in (-1, 1):
            wr = B.mirror(B.wrist, sd); he = B.mirror(B.hand_end, sd)
            d = (he - wr).normalized()
            hp = [wr + d * (0.0), wr + d * 0.05 * s, wr + d * 0.1 * s, wr + d * 0.15 * s, he]
            rw = [0.028, 0.038, 0.044, 0.04, 0.03]
            rt = [0.02, 0.017, 0.015, 0.014, 0.012]
            hp[-1] = wr + d * 0.17 * s
            S.loft([(tuple(hp[i]), rw[i] * s + o, rt[i] * s + o) for i in range(5)], segs=20)
            # thumb (points forward, +Y)
            tb = wr + d * 0.04 * s + Vector((0, 0.01 * s, 0))
            te = tb + Vector((-sd * 0.015 * s, 0.055 * s, -0.03 * s))
            S.capsule(tuple(tb), tuple(te), 0.013 * s + o, 0.01 * s + o, segs=12)
    if 'legs' in parts:
        for sd in (-1, 1):
            hp = B.mirror(B.hip, sd); kn = B.mirror(B.knee, sd); an = B.mirror(B.ankle, sd)
            th = [hp + (kn - hp) * t for t in (-0.05, 0.25, 0.55, 0.85, 1.0)]
            rt = [0.092 * B.hw * bk, 0.088 * bk, 0.075 * bk, 0.062, 0.055]
            rt2 = [0.095 * bk, 0.09 * bk, 0.078 * bk, 0.064, 0.058]
            S.loft([(tuple(th[i]), rt[i] * s + o, rt2[i] * s + o) for i in range(5)], segs=24)
            sh = [kn + (an - kn) * t for t in (0.0, 0.25, 0.55, 0.85, 1.0)]
            rs = [0.055, 0.06 * bk, 0.05, 0.038, 0.034]
            rs2 = [0.058, 0.066 * bk, 0.054, 0.04, 0.036]
            cy = [0.0, -0.012, -0.01, -0.004, 0.0]
            S.loft([(tuple(sh[i]), rs[i] * s + o, rs2[i] * s + o, (0, cy[i] * s)) for i in range(5)], segs=24)
            S.ellipsoid(tuple(kn), (0.055 * s + o, 0.058 * s + o, 0.065 * s + o))
    if 'feet' in parts:
        for sd in (-1, 1):
            an = B.mirror(B.ankle, sd); toe = B.mirror(B.toe, sd)
            x = an.x
            fp = [((x, an.y - 0.055 * s, 0.045 * s), 0.038, 0.04), ((x, an.y - 0.02 * s, 0.04 * s), 0.042, 0.04),
                  ((x, an.y + 0.06 * s, 0.035 * s), 0.046, 0.034), ((x, an.y + 0.14 * s, 0.028 * s), 0.05, 0.026),
                  ((x, toe.y, 0.022 * s), 0.045, 0.02), ((x, toe.y + 0.025 * s, 0.018 * s), 0.03, 0.014)]
            S.loft([(c, ru * s + o, rv * s + o) for (c, ru, rv) in fp], segs=20, vhint=(0, 0, 1))
    return S


def sculpt_face(ob, B):
    s, z = B.s, B.z
    for sd in (-1, 1):
        displace_gaussian(ob, (sd * 0.032 * s, 0.095 * s, z['eye']), (0.02 * s, 0.03 * s, 0.013 * s), 0.011 * s, normal_dir=(0, 1, 0))
    displace_gaussian(ob, (0, 0.098 * s, z['mouth']), (0.022 * s, 0.03 * s, 0.004 * s), 0.006 * s, normal_dir=(0, 1, 0))
    # temples slightly in, philtrum
    for sd in (-1, 1):
        displace_gaussian(ob, (sd * 0.08 * s, 0.045 * s, z['eye'] + 0.02 * s), (0.02 * s, 0.03 * s, 0.03 * s), 0.004 * s)
    recalc_normals(ob)


def head_accessories(B, col, prefix, mats, hair='short', female=False):
    """Eyes, eyebrows, hair cap -> list of (object, bone)."""
    s, z = B.s, B.z
    out = []
    for sd, nm in ((-1, 'L'), (1, 'R')):
        S = Shape(); S.ellipsoid((sd * 0.032 * s, 0.085 * s, z['eye']), (0.0125 * s,) * 3, segs=16, rings=10)
        eye = S.to_object(f'{prefix}_eye.{nm}', col); shade_smooth(eye); eye.data.materials.append(mats['eye'])
        S = Shape(); S.ellipsoid((sd * 0.032 * s, 0.0955 * s, z['eye']), (0.0065 * s, 0.003 * s, 0.0065 * s), segs=16, rings=8)
        iris = S.to_object(f'{prefix}_iris.{nm}', col); shade_smooth(iris); iris.data.materials.append(mats['iris'])
        S = Shape(); S.ellipsoid((sd * 0.034 * s, 0.1 * s, z['eye'] + 0.025 * s), (0.024 * s, 0.006 * s, 0.005 * s), rot=('Y', math.radians(10 * sd)), segs=12, rings=6)
        brow = S.to_object(f'{prefix}_brow.{nm}', col); shade_smooth(brow); brow.data.materials.append(mats['hair'])
        out += [(eye, 'head'), (iris, 'head'), (brow, 'head')]
    # hair cap: loft following the cranium, slightly inflated, hairline pulled back
    hd = [(z['eye'] + 0.005 * s, 0.084, 0.104, -0.022), (z['eye'] + 0.03 * s, 0.085, 0.106, -0.018),
          (z['eye'] + 0.055 * s, 0.083, 0.104, -0.012), (z['top'] - 0.035 * s, 0.073, 0.094, -0.01),
          (z['top'] - 0.005 * s, 0.045, 0.06, -0.014), (z['top'] + 0.012 * s, 0.012, 0.016, -0.016)]
    S = Shape(); S.loft([((0, cy * s, zz), rx * s, ry * s) for (zz, rx, ry, cy) in hd], segs=32)
    S.ellipsoid((0, -0.045 * s, z['eye'] - 0.01 * s), (0.078 * s, 0.062 * s, 0.045 * s))  # occiput / nape coverage
    if hair == 'bun':
        S.ellipsoid((0, -0.085 * s, z['top'] - 0.02 * s), (0.04 * s, 0.035 * s, 0.035 * s))
    if hair == 'long':
        S.loft([((0, -0.07 * s, z['eye'] + 0.02 * s), 0.07 * s, 0.045 * s), ((0, -0.075 * s, z['chin']), 0.075 * s, 0.04 * s),
                ((0, -0.08 * s, z['neck_base'] - 0.02 * s), 0.07 * s, 0.035 * s)], segs=20)
    hr = S.to_object(f'{prefix}_hair', col)
    rm = hr.modifiers.new('Remesh', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.008; apply_modifiers(hr)
    ls = hr.modifiers.new('S', 'LAPLACIANSMOOTH'); ls.iterations = 2; ls.lambda_factor = 0.5; ls.use_volume_preserve = True; apply_modifiers(hr)
    shade_smooth(hr); hr.data.materials.append(mats['hair'])
    out.append((hr, 'head'))
    return out

# ----------------------------------------------------------------------------- armature
BONES = [  # name, parent, head attr, tail attr, connect
    ('hips', None), ('spine', 'hips'), ('chest', 'spine'), ('neck', 'chest'), ('head', 'neck'),
    ('upper_arm.L', 'chest'), ('forearm.L', 'upper_arm.L'), ('hand.L', 'forearm.L'),
    ('upper_arm.R', 'chest'), ('forearm.R', 'upper_arm.R'), ('hand.R', 'forearm.R'),
    ('thigh.L', 'hips'), ('shin.L', 'thigh.L'), ('foot.L', 'shin.L'),
    ('thigh.R', 'hips'), ('shin.R', 'thigh.R'), ('foot.R', 'shin.R')]

def bone_positions(B):
    s, z = B.s, B.z
    pos = {'hips': ((0, 0, z['hip'] + 0.02 * s), (0, 0, z['waist'] - 0.01 * s)),
           'spine': ((0, 0, z['waist'] - 0.01 * s), (0, 0.01 * s, z['nipple'] - 0.06 * s)),
           'chest': ((0, 0.01 * s, z['nipple'] - 0.06 * s), (0, 0.005 * s, z['neck_base'])),
           'neck': ((0, 0.005 * s, z['neck_base']), (0, 0.012 * s, z['chin'] + 0.02 * s)),
           'head': ((0, 0.012 * s, z['chin'] + 0.02 * s), (0, 0.0, z['top']))}
    for sd, nm in ((-1, 'L'), (1, 'R')):
        sh, el, wr, he = (B.mirror(v, sd) for v in (B.shoulder, B.elbow, B.wrist, B.hand_end))
        hp, kn, an, toe = (B.mirror(v, sd) for v in (B.hip, B.knee, B.ankle, B.toe))
        pos[f'upper_arm.{nm}'] = (tuple(sh), tuple(el)); pos[f'forearm.{nm}'] = (tuple(el), tuple(wr)); pos[f'hand.{nm}'] = (tuple(wr), tuple(he))
        pos[f'thigh.{nm}'] = (tuple(hp), tuple(kn)); pos[f'shin.{nm}'] = (tuple(kn), tuple(an)); pos[f'foot.{nm}'] = (tuple(an), tuple(toe))
    return pos

def make_armature(name, B, col):
    ad = bpy.data.armatures.new(name); arm = bpy.data.objects.new(name, ad); col.objects.link(arm)
    ad.display_type = 'OCTAHEDRAL'
    pos = bone_positions(B)
    with override(arm):
        bpy.ops.object.mode_set(mode='EDIT')
        eb = {}
        for nm, par in BONES:
            b = ad.edit_bones.new(nm); b.head, b.tail = pos[nm]; eb[nm] = b
            if par:
                b.parent = eb[par]
                b.use_connect = (Vector(b.head) - Vector(eb[par].tail)).length < 1e-4
        bpy.ops.object.mode_set(mode='OBJECT')
    return arm

def auto_weights(arm, meshes):
    """Try bone-heat automatic weights; fall back to numpy proximity weights per mesh."""
    ok = False
    try:
        for m in meshes:
            m.parent = None; m.matrix_world = Matrix.Identity(4)
        with override(arm, meshes):
            bpy.ops.object.parent_set(type='ARMATURE_AUTO', keep_transform=False)
        ok = True
        for m in meshes:
            n = len(m.data.vertices)
            if n == 0: continue
            w = np.zeros(n)
            for vg in m.vertex_groups:
                for v in m.data.vertices:
                    pass
            # check coverage via per-vertex groups
            covered = sum(1 for v in m.data.vertices if any(g.weight > 1e-4 for g in v.groups))
            if covered < 0.98 * n:
                print(f'[weights] {m.name}: bone heat covered {covered}/{n} -> numpy fallback'); ok = False
    except Exception as e:
        print('[weights] ARMATURE_AUTO failed:', e); ok = False
    if not ok:
        for m in meshes:
            proximity_weights(arm, m)
    return ok

def proximity_weights(arm, m, soft=0.06):
    m.vertex_groups.clear()
    for md in list(m.modifiers):
        if md.type == 'ARMATURE': m.modifiers.remove(md)
    n = len(m.data.vertices); co = np.empty(n * 3); m.data.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    co = (np.array(m.matrix_world) @ np.c_[co, np.ones(n)].T).T[:, :3]
    names = [b.name for b in arm.data.bones]; D = np.empty((n, len(names)))
    for j, b in enumerate(arm.data.bones):
        a = np.array(arm.matrix_world @ b.head_local); c = np.array(arm.matrix_world @ b.tail_local)
        ab = c - a; t = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1); p = a + t[:, None] * ab
        D[:, j] = np.linalg.norm(co - p, axis=1)
    W = np.exp(-(D / soft) ** 2); idx = np.argsort(D, axis=1)[:, :2]
    Wm = np.zeros_like(W); rows = np.arange(n)[:, None]; Wm[rows, idx] = W[rows, idx] + 1e-6
    Wm /= Wm.sum(1, keepdims=True)
    for j, nm in enumerate(names):
        vg = m.vertex_groups.new(name=nm)
        for i in np.nonzero(Wm[:, j] > 1e-3)[0]:
            vg.add([int(i)], float(Wm[i, j]), 'REPLACE')
    md = m.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    m.parent = arm

def bind_to_bone(ob, arm, bone):
    """Single-bone rigid attach via armature modifier + full-weight group (keeps meshes link-friendly)."""
    vg = ob.vertex_groups.new(name=bone); vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    ob.parent = arm

def bind_soft(ob, arm, bones):
    """Weights by proximity restricted to a bone subset (clothing/accessories)."""
    n = len(ob.data.vertices); co = np.empty(n * 3); ob.data.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    D = np.empty((n, len(bones)))
    for j, bn in enumerate(bones):
        b = arm.data.bones[bn]; a = np.array(b.head_local); c = np.array(b.tail_local)
        ab = c - a; t = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1); p = a + t[:, None] * ab
        D[:, j] = np.linalg.norm(co - p, axis=1)
    W = np.exp(-(D / 0.07) ** 2) + 1e-6; W /= W.sum(1, keepdims=True)
    for j, bn in enumerate(bones):
        vg = ob.vertex_groups.new(name=bn)
        for i in np.nonzero(W[:, j] > 1e-3)[0]: vg.add([int(i)], float(W[i, j]), 'REPLACE')
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    ob.parent = arm

# ----------------------------------------------------------------------------- clothing
def shirt(B, col, prefix, mat, sleeves='short', hem=None, off=0.014, neck=True):
    s, z = B.s, B.z
    hem = hem if hem is not None else z['hip'] + 0.02 * s
    top = z['neck_base'] + (0.012 * s if neck else -0.015 * s)
    S = torso_shell(Shape(), B, off, hem, top, deltoids=bool(sleeves) or off > 0.02, breasts=True, hips_extra=0.0)
    ob = S.to_object(f'{prefix}_shirt', col)
    # sleeves
    if sleeves:
        SS = Shape()
        for sd in (-1, 1):
            sh = B.mirror(B.shoulder, sd); el = B.mirror(B.elbow, sd); wr = B.mirror(B.wrist, sd)
            if sleeves == 'short':
                pts = [sh + (el - sh) * t for t in (-0.1, 0.2, 0.45, 0.55)]; rr = [0.07, 0.068, 0.062, 0.06]
            elif sleeves == 'cap':
                pts = [sh + (el - sh) * t for t in (-0.1, 0.1, 0.22, 0.26)]; rr = [0.072, 0.07, 0.066, 0.064]
            else:
                pts = [sh + (el - sh) * t for t in (-0.1, 0.3, 0.7, 1.0)] + [el + (wr - el) * t for t in (0.3, 0.7, 1.0)]
                rr = [0.07, 0.066, 0.06, 0.055, 0.052, 0.046, 0.042]
            SS.loft([(tuple(pts[i]), rr[i] * s * B.bulk, rr[i] * 0.96 * s * B.bulk) for i in range(len(pts))], segs=20)
        sl = SS.to_object(f'{prefix}_sleeves', col)
        join(ob, [sl])
    remesh_smooth(ob, voxel=0.011, smooth_iter=2, lam=0.5)
    ob.data.materials.append(mat)
    return ob

def trousers(B, col, prefix, mat, length=1.0, off=0.012, waist=None):
    s, z = B.s, B.z
    S = Shape()
    hw = B.hw
    waist = waist if waist is not None else z['hip'] + 0.09 * s
    tor = [(waist, 0.165 * hw, 0.112, -0.01), (z['hip'] - 0.03 * s, 0.168 * hw, 0.118, -0.015), (z['crotch'] + 0.02 * s, 0.12 * hw, 0.095, -0.01), (z['crotch'] - 0.02 * s, 0.05, 0.05, 0.0)]
    S.loft([((0, cy * s, zz), rx * s + off, ry * s + off) for (zz, rx, ry, cy) in tor], segs=32)
    for sd in (-1, 1):
        S.ellipsoid((sd * 0.085 * s * hw, -0.075 * s, z['hip'] - 0.015 * s), (0.1 * s + off, 0.085 * s + off, 0.11 * s + off))
        hp = B.mirror(B.hip, sd); kn = B.mirror(B.knee, sd); an = B.mirror(B.ankle, sd)
        pts = [hp + (kn - hp) * t for t in (-0.02, 0.3, 0.6, 1.0)]
        rr = [0.092 * hw * B.bulk, 0.086 * B.bulk, 0.074 * B.bulk, 0.062]
        rr2 = [0.095 * B.bulk, 0.09 * B.bulk, 0.078 * B.bulk, 0.064]
        if length > 0.5:
            L = (length - 0.5) / 0.5
            pts += [kn + (an - kn) * t for t in (0.3, 0.65, L)]
            rr += [0.062, 0.058, 0.052]; rr2 += [0.066, 0.06, 0.054]
        S.loft([(tuple(pts[i]), rr[i] * s + off, rr2[i] * s + off) for i in range(len(pts))], segs=24)
    ob = S.to_object(f'{prefix}_trousers', col)
    remesh_smooth(ob, voxel=0.011, smooth_iter=2, lam=0.5)
    ob.data.materials.append(mat)
    return ob

def shoes(B, col, prefix, mat, boot=False, off=0.012):
    s, z = B.s, B.z
    S = Shape()
    for sd in (-1, 1):
        an = B.mirror(B.ankle, sd); toe = B.mirror(B.toe, sd); x = an.x
        fp = [((x, an.y - 0.065 * s, 0.05 * s), 0.04, 0.045), ((x, an.y - 0.02 * s, 0.045 * s), 0.046, 0.045),
              ((x, an.y + 0.06 * s, 0.038 * s), 0.05, 0.038), ((x, an.y + 0.14 * s, 0.032 * s), 0.054, 0.03),
              ((x, toe.y + 0.01 * s, 0.026 * s), 0.048, 0.024), ((x, toe.y + 0.04 * s, 0.02 * s), 0.03, 0.016)]
        S.loft([(c, ru * s + off, rv * s + off) for (c, ru, rv) in fp], segs=20, vhint=(0, 0, 1))
        # sole slab
        S.loft([((x, an.y - 0.07 * s, 0.012 * s), 0.045 * s, 0.012 * s), ((x, an.y + 0.1 * s, 0.012 * s), 0.056 * s, 0.012 * s), ((x, toe.y + 0.045 * s, 0.012 * s), 0.04 * s, 0.012 * s)], segs=16, vhint=(0, 0, 1))
        if boot:
            S.loft([((x, an.y, z['ankle'] - 0.02 * s), 0.052 * s, 0.056 * s), ((x, an.y - 0.005 * s, z['ankle'] + 0.07 * s), 0.052 * s, 0.056 * s), ((x, an.y - 0.01 * s, z['ankle'] + 0.14 * s), 0.055 * s, 0.06 * s)], segs=20)
    ob = S.to_object(f'{prefix}_shoes', col)
    remesh_smooth(ob, voxel=0.008, smooth_iter=1, lam=0.4)
    ob.data.materials.append(mat)
    return ob

def join(target, others):
    with override(target, others):
        bpy.ops.object.join()
    return target

# ----------------------------------------------------------------------------- character assembly
def build_character(name, height=1.75, female=False, bulk=1.0, skin=(0.18, 0.09, 0.05, 1), outfit=None, hair='short', seat=False):
    outfit = outfit or {}
    t0 = time.time()
    col = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(col)
    B = Body(height=height, female=female, bulk=bulk)
    root = bpy.data.objects.new(f'{name}_root', None); root.empty_display_type = 'ARROWS'; root.empty_display_size = 0.3; col.objects.link(root)
    mats = {'skin': skin_material(f'MAT_{name}_skin', skin), 'eye': P.new_mat('MAT_eye_white', (0.8, 0.78, 0.74, 1), 0.25, coat=1.0),
            'iris': P.new_mat('MAT_iris', (0.02, 0.012, 0.008, 1), 0.2, coat=1.0), 'hair': P.new_mat('MAT_hair', (0.012, 0.008, 0.006, 1), 0.8)}
    # --- body
    body = body_shape(B).to_object(f'{name}_body', col)
    remesh_smooth(body, voxel=0.01 if not QUICK else 0.02, smooth_iter=3, lam=0.6)
    sculpt_face(body, B)
    body.data.materials.append(mats['skin'])
    print(f'[{name}] body tris {tri_count(body)}')
    # --- head accessories
    acc = head_accessories(B, col, name, mats, hair=hair, female=female)
    # --- clothing
    cl = []
    if outfit.get('shirt'):
        cl.append(shirt(B, col, name, outfit['shirt'], sleeves=outfit.get('sleeves', 'short'), hem=outfit.get('hem'), neck=outfit.get('neck', True)))
    if outfit.get('trousers'):
        cl.append(trousers(B, col, name, outfit['trousers'], length=outfit.get('length', 1.0), waist=outfit.get('waist')))
    if outfit.get('shoes'):
        cl.append(shoes(B, col, name, outfit['shoes'], boot=outfit.get('boot', False)))
    # --- armature
    arm = make_armature(f'RIG_{name}', B, col)
    arm.parent = root
    ok = auto_weights(arm, [body] + cl)
    print(f'[{name}] auto weights: {"bone heat" if ok else "numpy proximity"}')
    for ob, bone in acc:
        bind_to_bone(ob, arm, bone)
    return dict(name=name, col=col, root=root, arm=arm, body=body, cloth=cl, acc=[a[0] for a in acc], B=B, mats=mats)

# ----------------------------------------------------------------------------- extras per variant
def worker_extras(C):
    B, col, arm, name = C['B'], C['col'], C['arm'], C['name']; s, z = B.s, B.z
    yellow = P.new_mat('MAT_hardhat', P.PAL['yellow'], 0.35, coat=0.5)
    S = Shape()
    S.loft([((0, -0.005 * s, z['eye'] + 0.03 * s), 0.1 * s, 0.12 * s), ((0, -0.005 * s, z['eye'] + 0.055 * s), 0.1 * s, 0.12 * s),
            ((0, -0.005 * s, z['top'] + 0.0 * s), 0.09 * s, 0.11 * s), ((0, -0.005 * s, z['top'] + 0.035 * s), 0.06 * s, 0.075 * s), ((0, -0.005 * s, z['top'] + 0.05 * s), 0.015 * s, 0.02 * s)], segs=32)
    S.loft([((0, 0.01 * s, z['eye'] + 0.028 * s), 0.11 * s, 0.15 * s), ((0, 0.01 * s, z['eye'] + 0.04 * s), 0.11 * s, 0.15 * s)], segs=32)  # brim
    hat = S.to_object(f'{name}_hardhat', col); remesh_smooth(hat, voxel=0.006, smooth_iter=1, lam=0.3); hat.data.materials.append(yellow)
    bind_to_bone(hat, arm, 'head')
    # hi-vis vest with reflective strips: a torso shell shortened, plus two horizontal bands + two shoulder straps
    orange = cloth_material('MAT_hivis', P.PAL['orange'], rough=0.7, sheen=0.3)
    refl = P.new_mat('MAT_reflective', (0.75, 0.75, 0.72, 1), 0.15, metal=0.6, coat=0.8)
    vest = shirt(B, col, name + '_vest', orange, sleeves=None, hem=z['waist'] - 0.03 * s, off=0.034, neck=False)
    vest.name = f'{name}_vest'
    bind_soft(vest, arm, ['hips', 'spine', 'chest'])
    S = Shape()
    for zz in (z['waist'] + 0.02 * s, z['waist'] + 0.1 * s):
        S.loft([((0, 0, zz - 0.022 * s), 0.158 * s + 0.038, 0.108 * s + 0.038), ((0, 0, zz + 0.022 * s), 0.158 * s + 0.038, 0.108 * s + 0.038)], segs=32)
    for sd in (-1, 1):
        S.loft([((sd * 0.07 * s, 0.11 * s + 0.03, z['nipple'] + 0.02 * s), 0.025 * s, 0.006), ((sd * 0.075 * s, 0.045 * s + 0.03, z['shoulder'] + 0.035 * s), 0.025 * s, 0.006), ((sd * 0.07 * s, -0.06 * s - 0.03, z['nipple'] + 0.02 * s), 0.025 * s, 0.006)], segs=12, vhint=(0, 0, 1))
    strips = S.to_object(f'{name}_reflective', col); shade_smooth(strips); strips.data.materials.append(refl)
    bind_soft(strips, arm, ['hips', 'spine', 'chest'])
    C['acc'] += [hat, vest, strips]

def diver_extras(C):
    B, col, arm, name = C['B'], C['col'], C['arm'], C['name']; s, z = B.s, B.z
    black = cloth_material('MAT_wetsuit', (0.01, 0.01, 0.012, 1), rough=0.45, sheen=0.2)
    rubber = P.new_mat('MAT_rubber', (0.012, 0.012, 0.012, 1), 0.5)
    glass = P.new_mat('MAT_mask_glass', (1, 1, 1, 1), 0.02, transmission=1.0, ior=1.45)
    steel = P.new_mat('MAT_tank', (0.6, 0.62, 0.65, 1), 0.3, metal=1.0)
    yel = P.new_mat('MAT_bcd', (0.05, 0.05, 0.06, 1), 0.7)
    # mask: frame box around eyes with glass plate
    S = Shape()
    S.loft([((0, 0.092 * s, z['eye'] + 0.002 * s), 0.078 * s, 0.03 * s), ((0, 0.112 * s, z['eye'] + 0.002 * s), 0.08 * s, 0.032 * s)], segs=24, vhint=(0, 0, 1))
    frame = S.to_object(f'{name}_mask_frame', col)
    # hollow via inner loft subtract would need boolean; approximate: rim torus
    S = Shape()
    S.loft([((0, 0.113 * s, z['eye'] + 0.002 * s), 0.074 * s, 0.026 * s), ((0, 0.118 * s, z['eye'] + 0.002 * s), 0.074 * s, 0.026 * s)], segs=24, vhint=(0, 0, 1))
    glass_ob = S.to_object(f'{name}_mask_glass', col); shade_smooth(glass_ob); glass_ob.data.materials.append(glass)
    bm = bmesh.new(); bm.from_mesh(frame.data)
    bmesh.ops.inset_region(bm, faces=[f for f in bm.faces if f.normal.y > 0.9], thickness=0.012, depth=0.0)
    inner = [f for f in bm.faces if f.normal.y > 0.9 and f.calc_center_median().y > 0.1 and f.calc_area() > 0.001]
    bmesh.ops.delete(bm, geom=inner, context='FACES')
    bm.to_mesh(frame.data); bm.free()
    sol = frame.modifiers.new('Sol', 'SOLIDIFY'); sol.thickness = 0.008; apply_modifiers(frame); shade_smooth(frame); frame.data.materials.append(rubber)
    # strap
    S = Shape(); S.loft([((0, 0.05 * s, z['eye'] + 0.01 * s), 0.086 * s, 0.012), ((0, -0.03 * s, z['eye'] + 0.02 * s), 0.088 * s, 0.012), ((0, -0.1 * s, z['eye'] + 0.015 * s), 0.07 * s, 0.012)], segs=24, vhint=(0, 0, 1))
    strap = S.to_object(f'{name}_mask_strap', col); shade_smooth(strap); strap.data.materials.append(rubber)
    # regulator at mouth
    S = Shape()
    S.loft([((0, 0.098 * s, z['mouth']), 0.028 * s, 0.028 * s), ((0, 0.125 * s, z['mouth']), 0.032 * s, 0.032 * s), ((0, 0.135 * s, z['mouth']), 0.03 * s, 0.03 * s)], segs=20, vhint=(0, 0, 1))
    reg = S.to_object(f'{name}_regulator', col); shade_smooth(reg); reg.data.materials.append(rubber)
    # tank on back
    S = Shape()
    tz0, tz1 = z['hip'] + 0.02 * s, z['neck_base'] + 0.02 * s
    S.loft([((0, -0.2 * s, tz0), 0.075, 0.075), ((0, -0.2 * s, tz0 + 0.03), 0.085, 0.085), ((0, -0.2 * s, tz1 - 0.05), 0.085, 0.085), ((0, -0.2 * s, tz1), 0.055, 0.055), ((0, -0.2 * s, tz1 + 0.04), 0.022, 0.022), ((0, -0.2 * s, tz1 + 0.08), 0.02, 0.02)], segs=28)
    S.loft([((0, -0.2 * s, tz1 + 0.07), 0.035, 0.035), ((0, -0.2 * s, tz1 + 0.1), 0.035, 0.035)], segs=16)
    tank = S.to_object(f'{name}_tank', col); shade_smooth(tank); tank.data.materials.append(steel)
    # BCD vest (inflated torso shell, open front panels approximated by a thick shell)
    bcd = shirt(B, col, name + '_bcd', yel, sleeves=None, hem=z['waist'] - 0.02 * s, off=0.03, neck=False)
    bcd.name = f'{name}_bcd'
    # add back plate / straps joining tank
    S = Shape(); S.loft([((0, -0.1 * s, z['waist'] + 0.02 * s), 0.14 * s, 0.03), ((0, -0.13 * s, z['waist'] + 0.02 * s), 0.14 * s, 0.03), ((0, -0.13 * s, z['neck_base'] - 0.04 * s), 0.12 * s, 0.03), ((0, -0.1 * s, z['neck_base'] - 0.04 * s), 0.12 * s, 0.03)], segs=16, vhint=(0, 0, 1))
    plate = S.to_object(f'{name}_backplate', col); shade_smooth(plate); plate.data.materials.append(rubber)
    # hose: curve from regulator to tank valve
    cu = bpy.data.curves.new(f'{name}_hose', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.009; cu.bevel_resolution = 4; cu.resolution_u = 12
    sp = cu.splines.new('BEZIER'); pts = [(0.03 * s, 0.13 * s, z['mouth']), (0.14 * s, 0.09 * s, z['mouth'] - 0.06 * s), (0.17 * s, -0.08 * s, z['neck_base'] + 0.02 * s), (0.03 * s, -0.2 * s, tz1 + 0.1)]
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
    hose = bpy.data.objects.new(f'{name}_hose', cu); col.objects.link(hose)
    with override(hose): bpy.ops.object.convert(target='MESH')
    hose = bpy.data.objects[f'{name}_hose']; hose.data.materials.append(rubber); shade_smooth(hose)
    # fins (flat extensions from feet)
    fin_mat = P.new_mat('MAT_fin', (0.02, 0.02, 0.025, 1), 0.4)
    fins = []
    for sd, nm in ((-1, 'L'), (1, 'R')):
        an = B.mirror(B.ankle, sd); toe = B.mirror(B.toe, sd); x = an.x
        S = Shape()
        S.loft([((x, an.y - 0.06 * s, 0.05 * s), 0.045 * s, 0.05 * s), ((x, an.y + 0.1 * s, 0.035 * s), 0.055 * s, 0.035 * s), ((x, toe.y + 0.02 * s, 0.025 * s), 0.06 * s, 0.022 * s),
                ((x, toe.y + 0.15 * s, 0.022 * s), 0.08 * s, 0.009), ((x, toe.y + 0.4 * s, 0.03 * s), 0.1 * s, 0.006), ((x, toe.y + 0.45 * s, 0.032 * s), 0.09 * s, 0.005)], segs=20, vhint=(0, 0, 1))
        fin = S.to_object(f'{name}_fin.{nm}', col); shade_smooth(fin); fin.data.materials.append(fin_mat)
        bind_to_bone(fin, arm, f'foot.{nm}'); fins.append(fin)
    # torch in right hand with spot light
    torch_mat = P.new_mat('MAT_torch', (0.9, 0.8, 0.1, 1), 0.3, metal=0.2)
    wr = B.wrist; he = B.hand_end; d = (he - wr).normalized(); hc = wr + d * 0.09 * s + Vector((0, 0.012 * s, 0))
    S = Shape()
    # torch axis along +Y (forward), through the fist
    S.loft([((hc.x, hc.y - 0.08 * s, hc.z), 0.018 * s, 0.018 * s), ((hc.x, hc.y + 0.05 * s, hc.z), 0.018 * s, 0.018 * s), ((hc.x, hc.y + 0.07 * s, hc.z), 0.03 * s, 0.03 * s), ((hc.x, hc.y + 0.1 * s, hc.z), 0.03 * s, 0.03 * s)], segs=20, vhint=(0, 0, 1))
    torch = S.to_object('DIVER_TORCH', col); shade_smooth(torch); torch.data.materials.append(torch_mat)
    lens = P.new_mat('MAT_torch_lens', (1, 1, 1, 1), 0.1, emission=(1.0, 0.95, 0.8, 1), estrength=20.0)
    torch.data.materials.append(lens)
    for p in torch.data.polygons:
        if p.normal.y > 0.9 and p.center.y > hc.y + 0.09 * s: p.material_index = 1
    bind_to_bone(torch, arm, 'hand.R')
    ld = bpy.data.lights.new('DIVER_TORCH_LIGHT', 'SPOT'); ld.energy = 400; ld.spot_size = math.radians(38); ld.spot_blend = 0.4; ld.color = (1.0, 0.95, 0.85); ld.shadow_soft_size = 0.03
    lt = bpy.data.objects.new('DIVER_TORCH_LIGHT', ld); col.objects.link(lt)
    lt.parent = arm; lt.parent_type = 'BONE'; lt.parent_bone = 'hand.R'
    bpy.context.view_layer.update()
    lt.matrix_world = Matrix.Translation((hc.x, hc.y + 0.1 * s, hc.z)) @ Matrix.Rotation(math.radians(-90), 4, 'X')  # spot -Z -> +Y
    for ob, bone in ((frame, 'head'), (glass_ob, 'head'), (strap, 'head'), (reg, 'head'), (tank, 'chest'), (plate, 'chest')):
        bind_to_bone(ob, arm, bone)
    bind_soft(bcd, arm, ['hips', 'spine', 'chest'])
    bind_soft(hose, arm, ['head', 'neck', 'chest'])
    C['acc'] += [frame, glass_ob, strap, reg, tank, plate, bcd, hose, torch, lt] + fins

def passenger_seat(C):
    B, col, name = C['B'], C['col'], C['name']; s = B.s
    S = Shape()
    S.loft([((0, -0.2 * s, 0.42), 0.24, 0.02), ((0, 0.16 * s, 0.42), 0.24, 0.02)], segs=4, vhint=(0, 0, 1))
    S.loft([((0, -0.23 * s, 0.4), 0.24, 0.02), ((0, -0.25 * s, 0.8), 0.24, 0.02)], segs=4)
    for sd in (-1, 1):
        S.loft([((sd * 0.2, -0.02 * s, 0.0), 0.02, 0.02), ((sd * 0.2, -0.02 * s, 0.42), 0.02, 0.02)], segs=8)
    seat = S.to_object(f'{name}_seat', col)
    seat.data.materials.append(P.new_mat('MAT_seat', (0.12, 0.13, 0.16, 1), 0.6))
    seat.parent = C['root']
    return seat

# ----------------------------------------------------------------------------- build all
def build_all():
    reset_scene()
    turq, white, orange, blue, yellow = P.PAL['turq'], P.PAL['white'], P.PAL['orange'], P.PAL['blue'], P.PAL['yellow']
    chars = {}
    chars['HERO'] = build_character('HERO', height=1.72, female=True, bulk=0.97, skin=(0.18, 0.09, 0.05, 1), hair='bun',
                                    outfit=dict(shirt=cloth_material('MAT_hero_top', turq, 0.7, 0.5), sleeves='cap', hem=None,
                                                trousers=cloth_material('MAT_hero_trousers', tint(white, 0.75), 0.8), length=1.0,
                                                shoes=P.new_mat('MAT_hero_shoes', tint(white, 0.9), 0.35, coat=0.3)))
    chars['CIVILIAN_A'] = build_character('CIVILIAN_A', height=1.80, female=False, bulk=1.06, skin=(0.12, 0.06, 0.035, 1), hair='short',
                                          outfit=dict(shirt=cloth_material('MAT_civA_shirt', orange, 0.85), sleeves='short',
                                                      trousers=cloth_material('MAT_civA_trousers', (0.05, 0.05, 0.06, 1), 0.85), length=1.0,
                                                      shoes=P.new_mat('MAT_civA_shoes', (0.02, 0.02, 0.02, 1), 0.4)))
    chars['CIVILIAN_B'] = build_character('CIVILIAN_B', height=1.64, female=True, bulk=1.1, skin=(0.25, 0.14, 0.08, 1), hair='long',
                                          outfit=dict(shirt=cloth_material('MAT_civB_shirt', blue, 0.85), sleeves='long',
                                                      trousers=cloth_material('MAT_civB_trousers', (0.3, 0.28, 0.25, 1), 0.85), length=0.78,
                                                      shoes=P.new_mat('MAT_civB_shoes', (0.5, 0.45, 0.4, 1), 0.5)))
    chars['WORKER'] = build_character('WORKER', height=1.78, female=False, bulk=1.12, skin=(0.15, 0.075, 0.04, 1), hair='short',
                                      outfit=dict(shirt=cloth_material('MAT_worker_shirt', (0.25, 0.26, 0.3, 1), 0.85), sleeves='long',
                                                  trousers=cloth_material('MAT_worker_trousers', (0.09, 0.07, 0.05, 1), 0.9), length=1.0,
                                                  shoes=P.new_mat('MAT_worker_boots', (0.16, 0.09, 0.04, 1), 0.6), boot=True))
    worker_extras(chars['WORKER'])
    chars['PASSENGER'] = build_character('PASSENGER', height=1.74, female=False, bulk=1.0, skin=(0.2, 0.1, 0.055, 1), hair='short',
                                         outfit=dict(shirt=cloth_material('MAT_pass_shirt', tint(white, 0.95), 0.85), sleeves='short',
                                                     trousers=cloth_material('MAT_pass_trousers', (0.12, 0.14, 0.22, 1), 0.85), length=1.0,
                                                     shoes=P.new_mat('MAT_pass_shoes', (0.03, 0.03, 0.03, 1), 0.4)))
    passenger_seat(chars['PASSENGER'])
    A.make_seated_pose(chars['PASSENGER']['arm'], frame=1)
    chars['DIVER'] = build_character('DIVER', height=1.76, female=False, bulk=1.05, skin=(0.16, 0.08, 0.045, 1), hair='short',
                                     outfit=dict(shirt=cloth_material('MAT_wetsuit', (0.01, 0.01, 0.012, 1), 0.45, 0.2), sleeves='long', hem=0.75, neck=True,
                                                 trousers=cloth_material('MAT_wetsuit', (0.01, 0.01, 0.012, 1), 0.45, 0.2), length=1.0, waist=1.0,
                                                 shoes=P.new_mat('MAT_bootie', (0.015, 0.015, 0.015, 1), 0.5)))
    diver_extras(chars['DIVER'])
    bpy.context.view_layer.update()
    return chars

def save_blend(chars):
    for c in chars.values():
        c['root'].location = (0, 0, 0)
    bpy.context.scene.frame_set(1)
    os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print('saved', OUT_BLEND)

# ----------------------------------------------------------------------------- previews
def studio(size=14):
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs[0].default_value = (0.35, 0.36, 0.38, 1); bg.inputs[1].default_value = 0.5
    nt.links.new(bg.outputs[0], out.inputs[0])
    # cyclorama
    bm = bmesh.new()
    prof = [(-size, -0.0)]
    import numpy as _np
    pts = [(-4, 0)] + [(-4 + 0, 0)]
    verts = []
    xs = _np.linspace(-size, size, 3)
    # floor + curved back wall (quarter circle radius 2 at y=+4)
    prof = [(y, 0.0) for y in (size, -2.0)] + [(-2.0 - 2 * math.sin(a), 2 - 2 * math.cos(a)) for a in _np.linspace(0.1, math.pi / 2, 10)] + [(-4.0, 2.0 + size)]
    rows = []
    for (y, zz) in prof:
        rows.append([bm.verts.new((x, y, zz)) for x in xs])
    for i in range(len(rows) - 1):
        for j in range(len(xs) - 1):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    me = bpy.data.meshes.new('CYC'); bm.to_mesh(me); bm.free()
    cyc = bpy.data.objects.new('STUDIO_CYC', me); sc.collection.objects.link(cyc); shade_smooth(cyc)
    cyc.data.materials.append(P.new_mat('MAT_cyc', (0.42, 0.43, 0.45, 1), 0.9))
    lights = []
    def area(name, loc, target, energy, size_, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size_; ld.color = color
        ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob); ob.location = loc
        tgt = P.make_empty(name + '_tgt', target)
        c = ob.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        lights.append(ob); return ob
    area('KEY', (4, 5, 4.5), (0, 0, 1.0), 1500, 3.0, (1.0, 0.96, 0.9))
    area('FILL', (-5, 5, 2.5), (0, 0, 1.0), 600, 4.0, (0.9, 0.95, 1.0))
    area('RIM', (-2, -4, 3.5), (0, 0, 1.2), 900, 2.0, (1.0, 1.0, 1.0))
    return cyc, lights

def render(path, frame=1):
    sc = bpy.context.scene; sc.render.filepath = path; sc.frame_set(frame)
    t = time.time(); bpy.ops.render.render(write_still=True); print(f'rendered {path} in {time.time()-t:.0f}s')

def previews(chars):
    os.makedirs(PREV, exist_ok=True)
    order = ['HERO', 'CIVILIAN_A', 'CIVILIAN_B', 'WORKER', 'PASSENGER', 'DIVER']
    xs = [-3.25, -1.95, -0.65, 0.65, 1.95, 3.25]
    for n, x in zip(order, xs):
        chars[n]['root'].location = (x, 0, 0)
    studio()
    P.setup_render(res=(1280, 720), samples=16 if QUICK else 48, frame_start=1, frame_end=48)
    cam = P.add_camera('CAM_LINEUP', loc=(0, 8.5, 1.35), target=(0, 0, 0.92), lens=42)
    render(os.path.join(PREV, 'asset_characters_lineup.png'), 1)
    # hero walk
    hero = chars['HERO']
    A.make_walk_cycle(hero['arm'], 1, 48, stride_frames=24)
    for n in order:
        chars[n]['root'].location = (0, 0, 0) if n == 'HERO' else (50, -50, 0)
    cam2 = P.add_camera('CAM_HERO', loc=(-2.4, 3.4, 1.3), target=(0, 0, 0.95), lens=50)
    bpy.context.scene.camera = cam2
    render(os.path.join(PREV, 'asset_hero_walk.png'), 7)
    if '--extra' in sys.argv:
        cam3 = P.add_camera('CAM_FACE', loc=(0.35, 1.0, 1.66), target=(0, 0.05, 1.62), lens=85); bpy.context.scene.camera = cam3
        A.clear_animation(hero['arm'])
        render(os.path.join(PREV, 'asset_hero_face.png'), 1)

if __name__ == '__main__':
    t0 = time.time()
    chars = build_all()
    print(f'built all in {time.time()-t0:.0f}s')
    save_blend(chars)
    if not NORENDER:
        previews(chars)
    print(f'done in {time.time()-t0:.0f}s')
