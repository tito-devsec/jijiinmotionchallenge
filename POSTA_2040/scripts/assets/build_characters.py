"""Rigged characters for POSTA_2040: MakeHuman (MPFB) humans + procedural gear, diver kit and armoured robot.

Run:  /opt/blender/blender -b --python scripts/assets/build_characters.py [-- options]
  --norender            build + save only
  --only A,B            build only these collections (debug; saved to characters_debug.blend, not the asset file)
  --previews-only       load blender/assets/characters.blend and render the previews
  --shots a,b           subset of previews: lineup,hero,hands,twohand,diver,robot,walk
  --lowsamples          12 samples instead of 32

Needs the MPFB extension (bl_ext.blender_org.mpfb) and its CC0 MakeHuman system assets, both installed locally
(nothing is downloaded).  Output: blender/assets/characters.blend (textures packed) with collections HERO,
CIVILIAN_A, CIVILIAN_B, CIVILIAN_C, WORKER, PASSENGER, DIVER, ROBOT.  Each has a root empty '<NAME>_root' at the
feet centre and an armature 'RIG_<NAME>' (child of the root, facing +Y) with the 17 contract bones
(hips, spine, chest, neck, head, upper_arm/forearm/hand .L/.R, thigh/shin/foot .L/.R) plus 15 finger bones per
hand parented to hand.L/R: thumb/index/middle/ring/pinky .01-.03 + .L/.R (local +X rotation = flexion).

Pipeline per character:
  1. MPFB: base human from macro targets (gender / age / muscle / weight, african), skin, eyes, brows, lashes,
     hair, MakeHuman clothes, MPFB 'default' rig only as the source of skin weights and joint positions,
  2. bake targets + helper/delete masks, turn to +Y, scale to height, merge the 163 MPFB weight groups into the
     contract bones, build OUR armature (A-pose),
  3. recolour clothes to the HOT 70 palette (texture detail kept as luminance), garment / armour shells duplicated
     from the body or clothes surface (exact implicit cuts, offset along normals, relaxed, hemmed) that inherit
     the skin weights,
  4. re-rest into the contract rest pose (arms down, legs vertical), then rigid gear (glasses, hard hat, dive
     kit, armour plates ...) weighted 100 % to single bones, join into a few Armature-deformed objects.
"""
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix, kdtree
from mathutils.bvhtree import BVHTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
import posta_lib as P
import character_anim as A

OUT_BLEND = os.path.join(ROOT, 'blender', 'assets', 'characters.blend')
PREV = os.path.join(ROOT, 'previews')
ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def _opt(name, default=None):
    if name in ARGV:
        i = ARGV.index(name)
        return ARGV[i + 1] if i + 1 < len(ARGV) and not ARGV[i + 1].startswith('--') else True
    return default
NORENDER = bool(_opt('--norender'))
LOWS = bool(_opt('--lowsamples'))
ONLY = _opt('--only'); ONLY = ONLY.split(',') if isinstance(ONLY, str) else None
SHOTS = _opt('--shots'); SHOTS = SHOTS.split(',') if isinstance(SHOTS, str) else None
PREVIEWS_ONLY = bool(_opt('--previews-only'))

ORDER = ['HERO', 'CIVILIAN_A', 'CIVILIAN_B', 'CIVILIAN_C', 'WORKER', 'PASSENGER', 'DIVER', 'ROBOT']
CORE_BONES = ['hips', 'spine', 'chest', 'neck', 'head',
              'upper_arm.L', 'forearm.L', 'hand.L', 'upper_arm.R', 'forearm.R', 'hand.R',
              'thigh.L', 'shin.L', 'foot.L', 'thigh.R', 'shin.R', 'foot.R']
FINGERS = ['thumb', 'index', 'middle', 'ring', 'pinky']
SIDES = ((-1, 'L'), (1, 'R'))          # anatomical left is at -X
V3 = lambda *a: Vector(a)

# ============================================================================= scene utils
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'

def override(obj, extra=None):
    objs = [obj] + (extra or [])
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        if o is not None: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return bpy.context.temp_override(object=obj, active_object=obj, selected_objects=objs,
                                     selected_editable_objects=objs, view_layer=bpy.context.view_layer)

def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data; ob.data = me; ob.modifiers.clear()
    bpy.data.meshes.remove(old)
    return ob

def shade_smooth(ob, on=True):
    me = ob.data
    me.polygons.foreach_set('use_smooth', [on] * len(me.polygons)); me.update()

def recalc_normals(ob):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data); bm.free(); ob.data.update()

def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)

def get_co(ob):
    n = len(ob.data.vertices); co = np.empty(n * 3); ob.data.vertices.foreach_get('co', co); return co.reshape(n, 3)

def set_co(ob, co):
    ob.data.vertices.foreach_set('co', np.ascontiguousarray(co, dtype=np.float64).ravel()); ob.data.update()

def get_normals(ob):
    n = len(ob.data.vertices); nm = np.empty(n * 3); ob.data.vertices.foreach_get('normal', nm); return nm.reshape(n, 3)

def get_edges(ob):
    m = len(ob.data.edges); e = np.empty(m * 2, dtype=np.int64); ob.data.edges.foreach_get('vertices', e); return e.reshape(m, 2)

def boundary_mask(ob):
    """True for vertices on an open boundary."""
    me = ob.data; n = len(me.vertices)
    ne = len(me.edges); cnt = np.zeros(ne, dtype=np.int64)
    nl = len(me.loops); le = np.empty(nl, dtype=np.int64); me.loops.foreach_get('edge_index', le)
    np.add.at(cnt, le, 1)
    e = get_edges(ob); b = np.zeros(n, dtype=bool); be = e[cnt == 1]; b[be.ravel()] = True
    return b, be

def laplace(vals, edges, n, iters=1, lam=0.5, mu=None, mask=None, bmask=None, bedges=None):
    """Uniform Laplacian smoothing of per-vertex values (n,k). mu<0 -> Taubin (no shrink).
    Boundary vertices (bmask) only average along boundary edges so hems stay crisp loops."""
    vals = vals.copy(); k = vals.shape[1]
    deg = np.bincount(edges.ravel(), minlength=n).astype(float); deg[deg == 0] = 1
    if bmask is not None and bedges is not None and len(bedges):
        bdeg = np.bincount(bedges.ravel(), minlength=n).astype(float); bdeg[bdeg == 0] = 1
    def step(v, f):
        acc = np.zeros_like(v)
        for j in range(k):
            acc[:, j] = np.bincount(edges[:, 0], weights=v[edges[:, 1], j], minlength=n) + np.bincount(edges[:, 1], weights=v[edges[:, 0], j], minlength=n)
        avg = acc / deg[:, None]
        if bmask is not None and bedges is not None and len(bedges):
            accb = np.zeros_like(v)
            for j in range(k):
                accb[:, j] = np.bincount(bedges[:, 0], weights=v[bedges[:, 1], j], minlength=n) + np.bincount(bedges[:, 1], weights=v[bedges[:, 0], j], minlength=n)
            avg[bmask] = (accb / bdeg[:, None])[bmask]
        d = (avg - v) * f
        if mask is not None: d *= mask[:, None]
        return v + d
    for _ in range(iters):
        vals = step(vals, lam)
        if mu is not None: vals = step(vals, mu)
    return vals

def smooth_mesh(ob, iters=4, lam=0.5, taubin=True, mask=None, keep_boundary=True):
    co = get_co(ob); e = get_edges(ob); n = len(co)
    bm_, be = boundary_mask(ob) if keep_boundary else (None, None)
    co = laplace(co, e, n, iters, lam, (-lam * 1.04) if taubin else None, mask, bm_, be)
    set_co(ob, co)

def displace_gaussian(ob, center, sigma, depth, direction=None, co=None, nm=None):
    """Move verts near 'center' by -depth * gaussian along the normal (or along 'direction')."""
    own = co is None
    if own: co = get_co(ob); nm = get_normals(ob)
    d = (co - np.array(center)) / np.array(sigma)
    w = np.exp(-0.5 * (d ** 2).sum(1))
    dirv = nm if direction is None else np.tile(np.array(direction, dtype=float), (len(co), 1))
    co -= dirv * (w * depth)[:, None]
    if own: set_co(ob, co)
    return co

def smoothstep(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3 - 2 * x)

def join(target, others):
    others = [o for o in others if o is not None and o is not target]
    if not others: return target
    with override(target, others):
        bpy.ops.object.join()
    return target

# ============================================================================= primitive accumulator
class Shape:
    """Accumulates closed lofts / ellipsoids (each face tagged with a region label), later unioned by voxel remesh."""
    def __init__(self):
        self.v = []; self.f = []; self.fl = []; self.labels = []; self.cur = 0

    def lab(self, name):
        if name not in self.labels: self.labels.append(name)
        self.cur = self.labels.index(name); return self

    def _face(self, f):
        self.f.append(f); self.fl.append(self.cur)

    def loft(self, path, segs=24, vhint=(0, 1, 0), caps=True, sq=2.0):
        """path: list of (centre, ru, rv[, (du, dv)]). Frame: d along path, v ~ vhint, u = d x v.
        sq = superellipse exponent (2 = ellipse, >2 boxier)."""
        n = len(path); base = len(self.v)
        pts = [Vector(p[0]) for p in path]
        for i, p in enumerate(path):
            c = pts[i]
            d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            vh = Vector(vhint)
            if abs(d.dot(vh)) > 0.97: vh = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((0, 1, 0))
            u = d.cross(vh).normalized(); v = u.cross(d).normalized()
            ru, rv = p[1], p[2]
            off = p[3] if len(p) > 3 else (0, 0)
            c = c + u * off[0] + v * off[1]
            for k in range(segs):
                a = 2 * math.pi * k / segs; ca, sa = math.cos(a), math.sin(a)
                if sq != 2.0:
                    ca = math.copysign(abs(ca) ** (2.0 / sq), ca); sa = math.copysign(abs(sa) ** (2.0 / sq), sa)
                self.v.append(tuple(c + u * (ru * ca) + v * (rv * sa)))
        for i in range(n - 1):
            for k in range(segs):
                a = base + i * segs + k; b = base + i * segs + (k + 1) % segs
                self._face((a, b, b + segs, a + segs))
        if caps:
            self._face(tuple(base + k for k in range(segs))[::-1])
            self._face(tuple(base + (n - 1) * segs + k for k in range(segs)))
        return self

    def ellipsoid(self, c, r, segs=16, rings=10, rot=None, basis=None):
        base = len(self.v)
        if basis is not None: R = basis
        elif rot: R = Matrix.Rotation(rot[1], 3, rot[0])
        else: R = Matrix.Identity(3)
        if not hasattr(r, '__len__'): r = (r, r, r)
        c = Vector(c)
        for j in range(1, rings):
            th = math.pi * j / rings
            for k in range(segs):
                a = 2 * math.pi * k / segs
                p = Vector((r[0] * math.sin(th) * math.cos(a), r[1] * math.sin(th) * math.sin(a), r[2] * math.cos(th)))
                self.v.append(tuple(c + R @ p))
        top = len(self.v); self.v.append(tuple(c + R @ Vector((0, 0, r[2]))))
        bot = len(self.v); self.v.append(tuple(c + R @ Vector((0, 0, -r[2]))))
        for j in range(rings - 2):
            for k in range(segs):
                a = base + j * segs + k; b = base + j * segs + (k + 1) % segs
                self._face((a, a + segs, b + segs, b))
        for k in range(segs):
            self._face((top, base + k, base + (k + 1) % segs))
            j = rings - 2
            self._face((bot, base + j * segs + (k + 1) % segs, base + j * segs + k))
        return self

    def capsule(self, a, b, ra, rb=None, segs=12):
        rb = ra if rb is None else rb
        a, b = Vector(a), Vector(b)
        self.loft([(tuple(a), ra, ra), (tuple((a + b) / 2), (ra + rb) / 2, (ra + rb) / 2), (tuple(b), rb, rb)], segs=segs)
        self.ellipsoid(tuple(a), ra, segs=segs, rings=8); self.ellipsoid(tuple(b), rb, segs=segs, rings=8)
        return self

    def box(self, c, half, basis=None, sq=6.0, segs=24):
        """Rounded box: superellipse loft along local Z."""
        R = basis or Matrix.Identity(3); c = Vector(c)
        zs = (-1.0, -0.86, 0.86, 1.0); sc = (0.82, 1.0, 1.0, 0.82)
        base = len(self.v)
        for zz, k in zip(zs, sc):
            for i in range(segs):
                a = 2 * math.pi * i / segs; ca, sa = math.cos(a), math.sin(a)
                ca = math.copysign(abs(ca) ** (2.0 / sq), ca); sa = math.copysign(abs(sa) ** (2.0 / sq), sa)
                self.v.append(tuple(c + R @ Vector((half[0] * k * ca, half[1] * k * sa, half[2] * zz))))
        for j in range(3):
            for i in range(segs):
                a = base + j * segs + i; b = base + j * segs + (i + 1) % segs
                self._face((a, b, b + segs, a + segs))
        self._face(tuple(base + i for i in range(segs))[::-1]); self._face(tuple(base + 3 * segs + i for i in range(segs)))
        return self

    def merge(self, other, M=None):
        base = len(self.v)
        for v in other.v:
            self.v.append(tuple(M @ Vector(v)) if M is not None else v)
        lm = []
        for l in other.labels:
            if l not in self.labels: self.labels.append(l)
            lm.append(self.labels.index(l))
        for f, l in zip(other.f, other.fl):
            self.f.append(tuple(i + base for i in f)); self.fl.append(lm[l])
        return self

    def to_object(self, name, col=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f); me.update()
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); (col or bpy.context.scene.collection).objects.link(ob)
        return ob

    def bvh(self):
        return BVHTree.FromPolygons([Vector(v) for v in self.v], self.f, all_triangles=False)

def solid(S, name, col, voxel=0.004, smooth=3, mat=None, ratio=None):
    """Union a Shape by voxel remesh, relax, optionally decimate -> smooth-shaded object."""
    ob = S.to_object(name, col)
    rm = ob.modifiers.new('Remesh', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = voxel; rm.adaptivity = 0.0
    apply_modifiers(ob)
    if smooth: smooth_mesh(ob, iters=smooth, lam=0.5)
    if ratio:
        dm = ob.modifiers.new('Decimate', 'DECIMATE'); dm.ratio = ratio; apply_modifiers(ob)
    shade_smooth(ob); recalc_normals(ob)
    if mat is not None: ob.data.materials.append(mat)
    return ob

def raw(S, name, col, mat=None, smooth=True):
    """Shape -> object without remesh (clean hard-surface lofts)."""
    ob = S.to_object(name, col)
    if smooth: shade_smooth(ob)
    if mat is not None: ob.data.materials.append(mat)
    return ob

def bevel_shade(ob, angle=35, width=0.0015):
    """Hard-surface finish: small bevel on sharp edges, smooth shading with sharp creases kept."""
    bv = ob.modifiers.new('Bevel', 'BEVEL'); bv.width = width; bv.segments = 2; bv.limit_method = 'ANGLE'; bv.angle_limit = math.radians(angle)
    apply_modifiers(ob); shade_smooth(ob)
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(angle + 10))
    except Exception:
        pass
    return ob

# ============================================================================= materials
def _bsdf(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')

def cloth_material(name, color, rough=0.85, sheen=0.5, weave=900.0, bump=0.08):
    m = P.new_mat(name, color, rough=rough)
    b = _bsdf(m)
    b.inputs['Sheen Weight'].default_value = sheen; b.inputs['Sheen Roughness'].default_value = 0.5
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = weave; tex.inputs['Detail'].default_value = 1.0
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.002
    nt.links.new(tex.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def pattern_material(name='MAT_hero_pattern'):
    """Bold black & white organic (leaf / wave) print, procedural, object space."""
    m = P.new_mat(name, (1, 1, 1, 1), 0.8)
    nt = m.node_tree; b = _bsdf(m)
    b.inputs['Sheen Weight'].default_value = 0.4
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, 1.5)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 5.0; n1.inputs['Detail'].default_value = 1.5; n1.inputs['Roughness'].default_value = 0.4; n1.inputs['Distortion'].default_value = 1.6
    nt.links.new(mp.outputs[0], n1.inputs['Vector'])
    vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = 3.4
    nt.links.new(n1.outputs['Color'], vor.inputs['Vector'])
    r1 = nt.nodes.new('ShaderNodeValToRGB'); r1.color_ramp.interpolation = 'CONSTANT'
    white, black = (0.82, 0.84, 0.86, 1), (0.010, 0.010, 0.012, 1)
    r1.color_ramp.elements[0].position = 0.0; r1.color_ramp.elements[0].color = white
    r1.color_ramp.elements[1].position = 0.05; r1.color_ramp.elements[1].color = black
    e = r1.color_ramp.elements.new(0.15); e.color = white
    e2 = r1.color_ramp.elements.new(0.33); e2.color = black
    nt.links.new(vor.outputs['Distance'], r1.inputs['Fac'])
    nt.links.new(r1.outputs['Color'], b.inputs['Base Color'])
    return m

def shade(col, f):
    return (col[0] * f, col[1] * f, col[2] * f, 1.0)

H70 = P.HOT70
SILVER, NIGHT, THERMO, THERMO_D, VIOLET, GREEN, DIVE = (H70[k] for k in ('silver', 'night', 'thermo', 'thermo_deep', 'violet', 'green', 'dive'))

# ============================================================================= MPFB (MakeHuman) base humans
_MP = {}
def mpfb():
    if not _MP:
        bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.mpfb')
        from bl_ext.blender_org.mpfb.services.humanservice import HumanService
        from bl_ext.blender_org.mpfb.services.targetservice import TargetService
        _MP['HS'] = HumanService; _MP['TS'] = TargetService
        cands = [os.path.join(bpy.utils.user_resource('EXTENSIONS'), '.user', 'blender_org', 'mpfb', 'data'),
                 '/root/.config/blender/4.5/extensions/.user/blender_org/mpfb/data']
        _MP['data'] = next((c for c in cands if os.path.isdir(os.path.join(c, 'skins'))), None)
        if not _MP['data']: raise RuntimeError('MPFB system assets not found (skins/hair/clothes)')
    return _MP

BONE_NAMES = list(CORE_BONES) + [f'{fn}.0{i}.{s}' for s in 'LR' for fn in FINGERS for i in (1, 2, 3)]
BI = {n: i for i, n in enumerate(BONE_NAMES)}
NB = len(BONE_NAMES)

def mh_bone_map(parents):
    """MPFB 'default' rig bone -> [(contract bone, share)] (unlisted bones inherit from their nearest listed ancestor)."""
    ex = {'root': 'hips', 'spine05': 'hips', 'spine04': 'spine', 'spine03': 'spine', 'spine02': 'chest', 'spine01': 'chest',
          'neck01': 'neck', 'neck03': 'head', 'head': 'head'}
    for S in 'LR':
        ex.update({f'pelvis.{S}': 'hips', f'clavicle.{S}': 'chest', f'upperarm01.{S}': f'upper_arm.{S}',
                   f'lowerarm01.{S}': f'forearm.{S}', f'wrist.{S}': f'hand.{S}', f'upperleg01.{S}': f'thigh.{S}',
                   f'lowerleg01.{S}': f'shin.{S}', f'foot.{S}': f'foot.{S}'})
        for i, fn in enumerate(FINGERS, 1):
            for k in (1, 2, 3): ex[f'finger{i}-{k}.{S}'] = f'{fn}.0{k}.{S}'
    out = {}
    for b in parents:
        a = b
        while a is not None and a not in ex: a = parents[a]
        out[b] = [(ex[a], 1.0)] if a else [('hips', 1.0)]
    for S in 'LR':   # scapular bone: share between chest and upper arm so the shoulder cap follows the arm halfway
        out[f'shoulder01.{S}'] = [('chest', 0.55), (f'upper_arm.{S}', 0.45)]
    return out

def read_W(ob):
    """Contract-bone weights of an object as (n, NB) array."""
    n = len(ob.data.vertices); W = np.zeros((n, NB))
    gi = {g.index: BI[g.name] for g in ob.vertex_groups if g.name in BI}
    for v in ob.data.vertices:
        for g in v.groups:
            j = gi.get(g.group)
            if j is not None: W[v.index, j] = g.weight
    return W

def write_W(ob, W, arm=None, keep=()):
    for g in list(ob.vertex_groups):
        if g.name not in keep: ob.vertex_groups.remove(g)
    s = W.sum(1); s[s < 1e-8] = 1.0; W = W / s[:, None]
    for j, nm in enumerate(BONE_NAMES):
        idx = np.nonzero(W[:, j] > 2e-3)[0]
        if not len(idx): continue
        vg = ob.vertex_groups.new(name=nm)
        col = W[:, j]
        for i in idx: vg.add((int(i),), float(col[i]), 'REPLACE')
    if arm is not None: bind(ob, arm)

def bind(ob, arm):
    for m in list(ob.modifiers):
        if m.type == 'ARMATURE': ob.modifiers.remove(m)
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    ob.parent = arm; ob.matrix_parent_inverse.identity()

def rigid(ob, arm, bone):
    """100 % one bone (hard-surface pieces never stretch)."""
    ob.vertex_groups.clear()
    vg = ob.vertex_groups.new(name=bone); vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
    bind(ob, arm); return ob

def soft(ob, arm, bones, J, sigma=0.06):
    """Proximity weights restricted to a bone subset (straps, hoses, chains)."""
    co = get_co(ob); n = len(co); D = np.empty((n, len(bones)))
    for j, bn in enumerate(bones):
        a, c = (np.array(x) for x in J[bn]); ab = c - a
        t = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1); D[:, j] = np.linalg.norm(co - (a + t[:, None] * ab), axis=1)
    Wl = np.exp(-(D / sigma) ** 2) + 1e-9; Wl /= Wl.sum(1, keepdims=True)
    W = np.zeros((n, NB))
    for j, bn in enumerate(bones): W[:, BI[bn]] = Wl[:, j]
    write_W(ob, W, arm); return ob

def weights_from(ob, src, arm, k=3):
    """Copy weights from the nearest vertices of an already weighted object."""
    Ws = read_W(src); cs = get_co(src); kd = kdtree.KDTree(len(cs))
    for i, c in enumerate(cs): kd.insert(c, i)
    kd.balance()
    co = get_co(ob); W = np.zeros((len(co), NB))
    for i, c in enumerate(co):
        for (_, j, d) in kd.find_n(c, k): W[i] += Ws[j] / (d + 1e-4)
    write_W(ob, W, arm); return ob

class Reg:
    """Vectorised region helpers for implicit cut functions: bone weights and position along bones."""
    GROUPS = {}
    def __init__(self, co, W, J, extra=None):
        self.co, self.W, self.J = co, W, J; self.extra = extra or {}
        self.x, self.y, self.z = co[:, 0], co[:, 1], co[:, 2]
    def w(self, *names):
        out = np.zeros(len(self.co))
        for nm in names:
            if nm in BI: out += self.W[:, BI[nm]]
            else:
                for b in Reg.GROUPS[nm]: out += self.W[:, BI[b]]
        return out
    def g(self, name):
        return self.extra.get(name, np.zeros(len(self.co)))
    def t(self, bone):
        a, c = (np.array(v) for v in self.J[bone]); d = c - a
        return ((self.co - a) @ d) / (d @ d)
    def along(self, bone):
        a, c = (np.array(v) for v in self.J[bone]); d = c - a; L = np.linalg.norm(d)
        return ((self.co - a) @ d) / L
    def radial(self, bone):
        a, c = (np.array(v) for v in self.J[bone]); d = (c - a) / np.linalg.norm(c - a)
        r = self.co - a; r = r - np.outer(r @ d, d)
        return r
for _s in 'LR':
    Reg.GROUPS['arm.' + _s] = [f'upper_arm.{_s}', f'forearm.{_s}', f'hand.{_s}'] + [f'{fn}.0{i}.{_s}' for fn in FINGERS for i in (1, 2, 3)]
    Reg.GROUPS['hand.' + _s + '+'] = [f'hand.{_s}'] + [f'{fn}.0{i}.{_s}' for fn in FINGERS for i in (1, 2, 3)]
    Reg.GROUPS['leg.' + _s] = [f'thigh.{_s}', f'shin.{_s}', f'foot.{_s}']
Reg.GROUPS['arms'] = Reg.GROUPS['arm.L'] + Reg.GROUPS['arm.R']
Reg.GROUPS['legs'] = Reg.GROUPS['leg.L'] + Reg.GROUPS['leg.R']
Reg.GROUPS['hands'] = Reg.GROUPS['hand.L+'] + Reg.GROUPS['hand.R+']
Reg.GROUPS['torso'] = ['hips', 'spine', 'chest']
Reg.GROUPS['headneck'] = ['neck', 'head']

# ----------------------------------------------------------------------------- exact implicit cuts
def bm_W(bm, ob, extra=None):
    """Bone weights (n, NB) of a bmesh; non-bone vertex groups (scalp, lips ...) are collected into 'extra'."""
    dl = bm.verts.layers.deform.active; n = len(bm.verts); W = np.zeros((n, NB))
    if dl is None: return W
    gi = {g.index: BI[g.name] for g in ob.vertex_groups if g.name in BI}
    go = {g.index: g.name for g in ob.vertex_groups if g.name not in BI}
    if extra is not None:
        for nm in go.values(): extra[nm] = np.zeros(n)
    for i, v in enumerate(bm.verts):
        for g, w in v[dl].items():
            j = gi.get(g)
            if j is not None: W[i, j] = w
            elif extra is not None and g in go: extra[go[g]][i] = w
    return W

def bm_reg(bm, ob, J):
    bm.verts.ensure_lookup_table()
    co = np.array([v.co[:] for v in bm.verts]).reshape(-1, 3); ex = {}
    W = bm_W(bm, ob, ex)
    return Reg(co, W, J, ex)

def cut_implicit(bm, lay, eps=0.12):
    """Split every edge where the per-vertex float layer changes sign, then connect the new vertices, so the
    zero level set becomes a clean edge loop (used for hems, material borders, armour plate outlines)."""
    for e in bm.edges:
        a, b = e.verts; fa, fb = a[lay], b[lay]
        if fa * fb < 0:
            t = fa / (fa - fb)
            if t < eps: a[lay] = 0.0
            elif t > 1 - eps: b[lay] = 0.0
    newv = []
    for e in list(bm.edges):
        a, b = e.verts; fa, fb = a[lay], b[lay]
        if fa * fb < 0:
            t = fa / (fa - fb)
            _, nv = bmesh.utils.edge_split(e, a, t)
            nv[lay] = 0.0; newv.append(nv)
    zero = [v for v in bm.verts if v[lay] == 0.0]
    if zero:
        try: bmesh.ops.connect_verts(bm, verts=zero, check_degenerate=True)
        except Exception as ex: print('connect_verts:', ex)
    return newv

def face_side(f, lay):
    return sum(v[lay] for v in f.verts) / len(f.verts)

def paint_region(ob, fn, mat, J, cut=True):
    """Assign 'mat' to the faces where fn(co, Reg) > 0 (boundary cut exactly). Returns the slot index."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    R = bm_reg(bm, ob, J); f = fn(R.co, R)
    lay = bm.verts.layers.float.new('f')
    for v, val in zip(bm.verts, f): v[lay] = float(val)
    if cut: cut_implicit(bm, lay)
    if mat.name not in [m.name for m in ob.data.materials]: ob.data.materials.append(mat)
    slot = [m.name for m in ob.data.materials].index(mat.name)
    for fc in bm.faces:
        if face_side(fc, lay) > 0: fc.material_index = slot
    bm.verts.layers.float.remove(lay)
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    return slot

def delete_region(ob, fn, J, cut=True):
    """Delete the faces where fn > 0."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    R = bm_reg(bm, ob, J); f = fn(R.co, R)
    lay = bm.verts.layers.float.new('f')
    for v, val in zip(bm.verts, f): v[lay] = float(val)
    if cut: cut_implicit(bm, lay)
    bmesh.ops.delete(bm, geom=[fc for fc in bm.faces if face_side(fc, lay) > 0], context='FACES')
    bm.verts.layers.float.remove(lay)
    bm.to_mesh(ob.data); bm.free(); ob.data.update()

def add_hem(ob, depth=0.004):
    """Fold every open border inwards so single-layer shells read as thick cloth / plate."""
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.normal_update()
    be = [e for e in bm.edges if e.is_boundary]
    if be:
        nrm = {v: v.normal.copy() for v in bm.verts}
        r = bmesh.ops.extrude_edge_only(bm, edges=be)
        nv = [g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)]; ns = set(nv)
        for v in nv:
            for e in v.link_edges:
                o = e.other_vert(v)
                if o not in ns and o in nrm:
                    v.co = o.co - nrm[o] * depth; break
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data); bm.free(); ob.data.update()

def shell_from(C, src, fn, name, mat, offset=0.006, smooth=3, hem=0.004, subdiv=0, slot=None, offset_fn=None,
               solidify=0.0, bone=None, bevel=False):
    """Duplicate the faces of 'src' where fn(co, Reg) > 0 into a new object: cut exactly on fn = 0, optionally
    subdivide, push out along the normals, relax, hem (or solidify for armour plates).  The shell keeps the skin
    weights of the surface it came from, or is bound rigidly to 'bone'."""
    arm, J = C['arm'], C['J']
    bm = bmesh.new(); bm.from_mesh(src.data)
    if slot is not None:
        slots = slot if isinstance(slot, (list, tuple, set)) else (slot,)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in slots], context='FACES')
    R = bm_reg(bm, src, J); f = fn(R.co, R)
    lay = bm.verts.layers.float.new('f')
    for v, val in zip(bm.verts, f): v[lay] = float(val)
    cut_implicit(bm, lay)
    bmesh.ops.delete(bm, geom=[fc for fc in bm.faces if face_side(fc, lay) <= 0], context='FACES')
    bm.verts.layers.float.remove(lay)
    for fc in bm.faces: fc.material_index = 0; fc.smooth = True
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); C['col'].objects.link(ob)
    for g in src.vertex_groups: ob.vertex_groups.new(name=g.name)
    me.materials.append(mat)
    if not len(me.polygons):
        print(f'[warn] shell {name} is empty'); return ob
    if subdiv:
        sd = ob.modifiers.new('S', 'SUBSURF'); sd.levels = subdiv; sd.boundary_smooth = 'PRESERVE_CORNERS'; apply_modifiers(ob)
    co = get_co(ob); nm = get_normals(ob)
    off = np.full(len(co), offset) if offset_fn is None else offset_fn(co, Reg(co, read_W(ob), J))
    set_co(ob, co + nm * off[:, None])
    if smooth: smooth_mesh(ob, iters=smooth, lam=0.5, taubin=True)
    if solidify:
        so = ob.modifiers.new('Sol', 'SOLIDIFY'); so.thickness = solidify; so.offset = 1.0; so.use_even_offset = True; so.use_rim = True
        apply_modifiers(ob)
        if bevel: bevel_shade(ob, angle=40, width=min(0.002, solidify * 0.3))
    elif hem:
        add_hem(ob, hem)
    shade_smooth(ob)
    if bone: rigid(ob, arm, bone)
    else:
        W = read_W(ob); write_W(ob, W, arm)
    return ob

def refine_skin(ob, keep=('head', 'neck'), smooth=1.0):
    """Spend triangles where the camera looks: subdivide (smooth) only the faces weighted to the head / neck and
    the hands; neighbouring faces receive the new edge vertices, so the mesh stays watertight."""
    W = read_W(ob); k = np.zeros(len(W))
    for b in list(keep) + Reg.GROUPS['hands']: k += W[:, BI[b]]
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    faces = [f for f in bm.faces if all(k[v.index] > 0.5 for v in f.verts)]
    edges = list({e for f in faces for e in f.edges})
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, smooth=smooth, use_grid_fill=True)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng: bmesh.ops.triangulate(bm, faces=ng)
    for f in bm.faces: f.smooth = True
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    return ob

# ----------------------------------------------------------------------------- MakeHuman clothes -> palette colours
def uv_islands(bm):
    uv = bm.loops.layers.uv.active; isl = {}; out = []
    for f0 in bm.faces:
        if f0 in isl: continue
        k = len(out); comp = [f0]; isl[f0] = k; st = [f0]
        while st:
            f = st.pop()
            for l in f.loops:
                for l2 in l.edge.link_loops:
                    g = l2.face
                    if g is f or g in isl: continue
                    a0, a1 = l[uv].uv, l.link_loop_next[uv].uv; b0, b1 = l2[uv].uv, l2.link_loop_next[uv].uv
                    if ((a0 - b1).length < 1e-5 and (a1 - b0).length < 1e-5) or ((a0 - b0).length < 1e-5 and (a1 - b1).length < 1e-5):
                        isl[g] = k; comp.append(g); st.append(g)
        out.append(comp)
    return out

def recolor(C, ob, parts, classify, verbose=False):
    """Split a textured MakeHuman garment into palette-coloured parts.
    parts: {key: dict(color=, rough=, contrast=)}; classify(info) -> key per UV island, where info has
    zmean/zmin/zmax as fractions of the body height, xabs and n (faces).  The original diffuse map is kept only as
    a luminance detail layer (seams, folds, buttons) multiplied onto the flat HOT 70 colour; normal/AO maps stay."""
    name = C['name']; H = C['height']
    src = ob.data.materials[0]
    tex = src.node_tree.nodes.get('diffuseTexture')
    px = None
    if tex and tex.image:
        im = tex.image; w, h = im.size
        px = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(px); px = px.reshape(h, w, 4)
    bm = bmesh.new(); bm.from_mesh(ob.data); uv = bm.loops.layers.uv.active
    keys = list(parts.keys()); lum = {k: [] for k in keys}
    for comp in uv_islands(bm):
        zs = [v.co.z for f in comp for v in f.verts]; xs = [abs(v.co.x) for f in comp for v in f.verts]
        info = dict(zmean=sum(zs) / len(zs) / H, zmin=min(zs) / H, zmax=max(zs) / H, xabs=sum(xs) / len(xs), n=len(comp))
        k = classify(info)
        if verbose: print(f'   island n={info["n"]:5d} z {info["zmin"]:.2f}-{info["zmax"]:.2f} mean {info["zmean"]:.2f} x {info["xabs"]:.2f} -> {k}')
        si = keys.index(k)
        for f in comp:
            f.material_index = si
            if px is not None:
                c = sum((l[uv].uv for l in f.loops), Vector((0, 0))) / len(f.loops)
                p = px[int(c.y % 1.0 * (px.shape[0] - 1)), int(c.x % 1.0 * (px.shape[1] - 1))]
                lum[k].append(0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2])
    bm.to_mesh(ob.data); bm.free()
    mi = np.empty(len(ob.data.polygons), dtype=np.int32); ob.data.polygons.foreach_get('material_index', mi)
    ob.data.materials.clear()
    for k in keys:
        spec = parts[k]
        m = src.copy(); m.name = f'MAT_{name}_{k}'
        nt = m.node_tree; b = _bsdf(m); t = nt.nodes.get('diffuseTexture')
        target = None
        for l in nt.links:
            if l.from_node.name == 'diffuseIntensity': target = l.to_socket
        if target is None: target = b.inputs['Base Color']
        mean = float(np.median(lum[k])) if lum[k] else 0.5
        gain = 1.0 / max(mean, 0.03); cst = spec.get('contrast', 0.7)
        mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1.0
        mix.inputs[1].default_value = spec['color']
        if t is not None and t.image is not None:
            bw = nt.nodes.new('ShaderNodeRGBToBW'); nt.links.new(t.outputs['Color'], bw.inputs[0])
            m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY_ADD'; m1.inputs[1].default_value = gain * cst; m1.inputs[2].default_value = 1.0 - cst
            nt.links.new(bw.outputs[0], m1.inputs[0])
            m2 = nt.nodes.new('ShaderNodeClamp'); m2.inputs['Min'].default_value = 0.25; m2.inputs['Max'].default_value = 1.5
            nt.links.new(m1.outputs[0], m2.inputs['Value']); nt.links.new(m2.outputs[0], mix.inputs[2])
        else:
            mix.inputs[2].default_value = (1, 1, 1, 1)
        nt.links.new(mix.outputs[0], target)
        b.inputs['Roughness'].default_value = spec.get('rough', 0.8)
        if 'Sheen Weight' in b.inputs: b.inputs['Sheen Weight'].default_value = spec.get('sheen', 0.3)
        if not spec.get('alpha', False):
            for l in list(nt.links):
                if l.to_socket == b.inputs['Alpha']: nt.links.remove(l)
            b.inputs['Alpha'].default_value = 1.0
        ob.data.materials.append(m)
    ob.data.polygons.foreach_set('material_index', mi); ob.data.update()
    return {k: i for i, k in enumerate(keys)}

# ----------------------------------------------------------------------------- character from MPFB
def mh_character(name, height=1.75, gender=1.0, age=0.5, muscle=0.5, weight=0.5, proportions=0.5, cupsize=0.5,
                 skin='young_african_male', skin_value=1.0, hair=None, brows='eyebrow001', lashes='eyelashes01',
                 clothes=(), eyes='high-poly', keep_head=True):
    """MPFB human -> contract-space meshes with merged weights and our armature (still in the MakeHuman A-pose)."""
    mp = mpfb(); HS, TS, D = mp['HS'], mp['TS'], mp['data']
    t0 = time.time()
    col = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(col)
    md = TS.get_default_macro_info_dict()
    md.update(gender=gender, age=age, muscle=muscle, weight=weight, proportions=proportions, cupsize=cupsize, firmness=0.6)
    md['race'] = dict(african=1.0, asian=0.0, caucasian=0.0)
    h = HS.create_human(macro_detail_dict=md)
    HS.add_builtin_rig(h, 'default'); rig = h.parent
    HS.set_character_skin(os.path.join(D, 'skins', skin, skin + '.mhmat'), h, skin_type='ENHANCED_SSS', material_instances=True)
    parts = {'body': h}; used = [f'skins/{skin}']
    assets = []
    if keep_head:
        assets += [('Eyes', f'eyes/{eyes}/{eyes}.mhclo', 'eyes')]
        if brows: assets.append(('Eyebrows', f'eyebrows/{brows}/{brows}.mhclo', 'brows'))
        if lashes: assets.append(('Eyelashes', f'eyelashes/{lashes}/{lashes}.mhclo', 'lashes'))
        if hair: assets.append(('Hair', f'hair/{hair}/{hair}.mhclo', 'hair'))
    for c in clothes: assets.append(('Clothes', f'clothes/{c}/{c}.mhclo', c))
    for typ, rel, key in assets:
        o = HS.add_mhclo_asset(os.path.join(D, rel), h, asset_type=typ, subdiv_levels=0, material_type='MAKESKIN')
        parts[key] = o; used.append(rel.rsplit('/', 1)[0])
    # --- joints + hierarchy of the MPFB rig, then drop it
    mj = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in rig.data.bones}
    parents = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
    bmap = mh_bone_map(parents)
    for o in parts.values():
        if o.data.shape_keys: TS.bake_targets(o)
        for m in list(o.modifiers):
            if m.type in ('ARMATURE', 'SUBSURF'): o.modifiers.remove(m)
        if len(o.modifiers): apply_modifiers(o)          # helper mask + 'Delete.<garment>' masks become real deletions
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
        for c in list(o.users_collection): c.objects.unlink(o)
        col.objects.link(o)
    bpy.data.objects.remove(rig)
    # --- contract frame: face +Y, requested height, feet on z = 0
    co = get_co(h); k = height / co[:, 2].max(); z0 = 0.0
    def T(p): return Vector((-p[0] * k, -p[1] * k, (p[2] - z0) * k))
    for o in parts.values():
        c = get_co(o); c = np.c_[-c[:, 0] * k, -c[:, 1] * k, (c[:, 2] - z0) * k]; set_co(o, c)
        o.matrix_world = Matrix.Identity(4)
    mj = {b: (T(a), T(c)) for b, (a, c) in mj.items()}
    # --- merge MPFB weight groups into contract bones
    for key, o in parts.items():
        n = len(o.data.vertices); W = np.zeros((n, NB))
        gm = {g.index: bmap[g.name] for g in o.vertex_groups if g.name in bmap}
        lm = {}
        if key == 'body':
            for g in o.vertex_groups:
                if g.name in ('ears', 'lips', 'scalp', 'fingernails', 'toenails'): lm[g.index] = g.name
        marks = {v: [] for v in lm.values()}
        for v in o.data.vertices:
            for g in v.groups:
                if g.group in gm:
                    for bn, sh in gm[g.group]: W[v.index, BI[bn]] += g.weight * sh
                if g.group in lm and g.weight > 0.5: marks[lm[g.group]].append(v.index)
        zero = W.sum(1) < 1e-6
        if zero.any(): W[zero, BI['head' if key in ('eyes', 'brows', 'lashes', 'hair') else 'hips']] = 1.0
        write_W(o, W, keep=('scalp', 'lips', 'ears', 'fingernails') if key == 'body' else ())
        if key == 'body': body_marks = marks
    # --- contract joints
    J = {}
    top = get_co(h)[:, 2].max()
    nb = mj['spine01'][0].lerp(mj['spine01'][1], 0.72)
    J['hips'] = (mj['spine05'][0], mj['spine05'][1]); J['spine'] = (mj['spine04'][0], mj['spine02'][0])
    J['chest'] = (mj['spine02'][0], nb); J['neck'] = (nb, mj['neck03'][0])
    J['head'] = (mj['neck03'][0], Vector((mj['neck03'][0].x, mj['neck03'][0].y - 0.01, top)))
    for S in 'LR':
        wr = mj[f'wrist.{S}'][0]; tip = mj[f'finger3-3.{S}'][1]
        J[f'upper_arm.{S}'] = (mj[f'upperarm01.{S}'][0], mj[f'lowerarm01.{S}'][0])
        J[f'forearm.{S}'] = (mj[f'lowerarm01.{S}'][0], wr)
        J[f'hand.{S}'] = (wr, wr + (mj[f'finger3-1.{S}'][0] - wr).normalized() * ((tip - wr).length * 0.97))
        J[f'thigh.{S}'] = (mj[f'upperleg01.{S}'][0], mj[f'lowerleg01.{S}'][0])
        J[f'shin.{S}'] = (mj[f'lowerleg01.{S}'][0], mj[f'foot.{S}'][0])
        t = mj[f'toe2-3.{S}'][1]
        J[f'foot.{S}'] = (mj[f'foot.{S}'][0], Vector((t.x, t.y, 0.02)))
        for i, fn in enumerate(FINGERS, 1):
            for kk in (1, 2, 3): J[f'{fn}.0{kk}.{S}'] = mj[f'finger{i}-{kk}.{S}']
    C = dict(name=name, col=col, body=h, parts=parts, J=J, mj=mj, height=height, used=used, gear=[], cloth=[], female=gender < 0.5)
    C['root'] = bpy.data.objects.new(f'{name}_root', None); C['root'].empty_display_type = 'ARROWS'; C['root'].empty_display_size = 0.3; col.objects.link(C['root'])
    C['arm'] = make_armature(C)
    for o in parts.values(): bind(o, C['arm'])
    # --- landmarks for gear
    cb = get_co(h); L = {}
    for S, sg in (('L', -1), ('R', 1)):
        e = cb[[i for i in body_marks['ears'] if cb[i, 0] * sg > 0]]
        L['ear.' + S] = Vector(e.mean(0)); L['ear_top.' + S] = Vector(e[e[:, 2].argmax()]); L['ear_out.' + S] = Vector(e[(e[:, 0] * sg).argmax()])
        L['eye.' + S] = mj[f'eye.{S}'][0].copy()
    lips = cb[body_marks['lips']]; L['mouth'] = Vector(lips.mean(0)); L['mouth_front'] = float(lips[:, 1].max())
    hw = read_W(h)[:, BI['head']] > 0.5
    hc = cb[hw]; mid = hc[np.abs(hc[:, 0]) < 0.006]
    L['top'] = float(hc[:, 2].max()); L['nose'] = Vector(mid[mid[:, 1].argmax()]); L['back'] = float(hc[:, 1].min())
    front = mid[mid[:, 1] > L['mouth'].y - 0.02]; L['chin'] = Vector(front[front[:, 2].argmin()])
    L['head_w'] = float(np.abs(hc[hc[:, 2] > L['eye.L'].z + 0.02][:, 0]).max())
    brow_band = mid[(mid[:, 2] > L['eye.L'].z + 0.008) & (mid[:, 2] < L['eye.L'].z + 0.03)]
    L['brow_y'] = float(brow_band[:, 1].max()) if len(brow_band) else L['nose'].y - 0.02
    C['L'] = L
    rename_materials(C, skin_value)
    print(f'[{name}] MPFB human {time.time() - t0:.1f}s, height {height:.2f}, body verts {len(h.data.vertices)}')
    return C

def rename_materials(C, skin_value=1.0):
    """Palette-safe names: skin/lip/eye/brow/lash/hair stay natural in enforce_palette()."""
    name = C['name']; seen = {}
    roles = {'body': 'skin', 'eyes': 'eye', 'brows': 'brow', 'lashes': 'lash', 'hair': 'hair'}
    for key, o in C['parts'].items():
        role = roles.get(key)
        if role is None: continue
        for i, m in enumerate(o.data.materials):
            if m is None or m.name in seen: continue
            tag = m.name.split('.')[-1] if key == 'body' else ''
            nn = f'MAT_{name}_skin' + ('' if tag == 'body' else '_' + ('lip' if tag == 'lips' else tag)) if key == 'body' else f'MAT_{name}_{role}'
            m.name = nn; seen[nn] = 1
            for nd in m.node_tree.nodes:
                if nd.type == 'GROUP' and nd.node_tree and not nd.node_tree.name.startswith('NG_'):
                    nd.node_tree.name = f'NG_{name}_{nd.node_tree.name.split(".")[-1]}_skin'
            if key in ('brows', 'lashes', 'hair', 'eyes'):
                if hasattr(m, 'surface_render_method'): m.surface_render_method = 'DITHERED'
            if key in ('hair', 'brows'):      # natural black hair whatever the source texture colour
                t = m.node_tree.nodes.get('diffuseTexture')
                if t:
                    outs = [l.to_socket for l in t.outputs['Color'].links]
                    hs = m.node_tree.nodes.new('ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = 0.4; hs.inputs['Value'].default_value = C.get('hair_value', 0.22)
                    m.node_tree.links.new(t.outputs['Color'], hs.inputs['Color'])
                    for s in outs: m.node_tree.links.new(hs.outputs['Color'], s)
                _bsdf(m).inputs['Roughness'].default_value = 0.6
    for m in C['body'].data.materials:
        if not m: continue
        for nd in m.node_tree.nodes:
            if nd.type == 'GROUP':
                for k, v in (('SSS radius scale', 0.03), ('SSS strength', 0.16), ('Clearcoat', 0.05), ('colorMixInStrength', 0.0)):
                    if k in nd.inputs: nd.inputs[k].default_value = v
                if 'Roughness' in nd.inputs: nd.inputs['Roughness'].default_value = min(0.6, nd.inputs['Roughness'].default_value + 0.07)
    tone_skin(C, skin_value, 0.95)
    eo = C['parts'].get('eyes')
    if eo:
        for m in eo.data.materials:
            b = _bsdf(m); b.inputs['Roughness'].default_value = 0.12; b.inputs['Coat Weight'].default_value = 0.6
            t = m.node_tree.nodes.get('diffuseTexture')
            if t:
                outs = [l.to_socket for l in t.outputs['Color'].links]
                hs = m.node_tree.nodes.new('ShaderNodeHueSaturation'); hs.inputs['Saturation'].default_value = 0.55; hs.inputs['Value'].default_value = 0.8
                m.node_tree.links.new(t.outputs['Color'], hs.inputs['Color'])
                for s in outs: m.node_tree.links.new(hs.outputs['Color'], s)

def tone_skin(C, value=1.0, sat=1.0):
    """Slight per-character variation of the skin albedo (value / saturation on the diffuse map)."""
    done = set()
    def patch(nt):
        if nt.name in done: return
        done.add(nt.name)
        for nd in list(nt.nodes):
            if nd.type == 'GROUP' and nd.node_tree: patch(nd.node_tree)
            if nd.type == 'TEX_IMAGE' and nd.image and 'diffuse' in nd.image.name.lower():
                outs = [(l.to_socket) for l in nd.outputs['Color'].links]
                if not outs: continue
                hs = nt.nodes.new('ShaderNodeHueSaturation'); hs.inputs['Value'].default_value = value; hs.inputs['Saturation'].default_value = sat
                nt.links.new(nd.outputs['Color'], hs.inputs['Color'])
                for s in outs: nt.links.new(hs.outputs['Color'], s)
    for m in C['body'].data.materials:
        if m and m.use_nodes: patch(m.node_tree)

def make_armature(C):
    name, J = C['name'], C['J']
    ad = bpy.data.armatures.new(f'RIG_{name}'); arm = bpy.data.objects.new(f'RIG_{name}', ad); C['col'].objects.link(arm)
    ad.display_type = 'OCTAHEDRAL'
    par = {'hips': None, 'spine': 'hips', 'chest': 'spine', 'neck': 'chest', 'head': 'neck'}
    for S in 'LR':
        par.update({f'upper_arm.{S}': 'chest', f'forearm.{S}': f'upper_arm.{S}', f'hand.{S}': f'forearm.{S}',
                    f'thigh.{S}': 'hips', f'shin.{S}': f'thigh.{S}', f'foot.{S}': f'shin.{S}'})
        for fn in FINGERS:
            par[f'{fn}.01.{S}'] = f'hand.{S}'; par[f'{fn}.02.{S}'] = f'{fn}.01.{S}'; par[f'{fn}.03.{S}'] = f'{fn}.02.{S}'
    with override(arm):
        bpy.ops.object.mode_set(mode='EDIT')
        eb = {}
        for nm in BONE_NAMES:
            b = ad.edit_bones.new(nm); b.head, b.tail = J[nm]; eb[nm] = b
        for nm in BONE_NAMES:
            if par[nm]:
                eb[nm].parent = eb[par[nm]]
                eb[nm].use_connect = (eb[nm].head - eb[par[nm]].tail).length < 1e-4 and nm in CORE_BONES
        for S in 'LR':   # finger rolls: local +X rotation curls toward the palm
            wr = Vector(J[f'hand.{S}'][0]); ik = Vector(J[f'index.01.{S}'][0]); pk = Vector(J[f'pinky.01.{S}'][0])
            en = (ik - wr).cross(pk - wr).normalized()
            if en.z > 0: en = -en                       # A-pose palms face the floor
            C.setdefault('palm_n', {})[S] = en.copy()
            for fn in FINGERS:
                for i in (1, 2, 3):
                    b = eb[f'{fn}.0{i}.{S}']
                    if fn == 'thumb':
                        zc = (en * 0.75 + (ik - Vector(J[f'thumb.02.{S}'][0])).normalized() * 0.65).normalized()
                    else: zc = en
                    b.align_roll(zc)
        bpy.ops.object.mode_set(mode='OBJECT')
    arm.parent = C['root']
    arm['palm_bones'] = 'thumb,index,middle,ring,pinky'
    return arm

def refresh_joints(C):
    arm = C['arm']
    C['J'] = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in arm.data.bones}
    return C['J']

REST_DIRS = {'upper_arm': (0.060, -0.015, -0.295), 'forearm': (0.050, 0.015, -0.275), 'hand': (0.030, 0.010, -0.180),
             'thigh': (-0.005, 0.0, -0.43), 'shin': (0.0, -0.02, -0.39)}

def rerest(C):
    """MakeHuman A-pose -> contract rest pose (arms hanging with the old bone directions, legs vertical, feet flat):
    pose our armature, bake the deformation into every bound mesh, apply the pose as the new rest pose."""
    arm = C['arm']; vl = bpy.context.view_layer
    meshes = [o for o in C['col'].all_objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
    vl.update()
    foot0 = {S: arm.pose.bones[f'foot.{S}'].matrix.copy() for S in 'LR'}
    for S, sg in (('L', -1), ('R', 1)):
        for bn in ('upper_arm', 'forearm', 'hand', 'thigh', 'shin'):
            pb = arm.pose.bones[f'{bn}.{S}']; d = REST_DIRS[bn]
            tgt = Vector((d[0] * sg, d[1], d[2])).normalized(); cur = (pb.tail - pb.head).normalized()
            q = cur.rotation_difference(tgt).to_matrix().to_4x4()
            pb.matrix = Matrix.Translation(pb.head) @ q @ Matrix.Translation(-pb.head) @ pb.matrix
            vl.update()
        pb = arm.pose.bones[f'foot.{S}']; M = foot0[S].copy(); M.translation = pb.head; pb.matrix = M; vl.update()
    for o in meshes:
        apply_modifiers(o); bind(o, arm)
    with override(arm):
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.armature_apply(selected=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    # feet back on the ground, centred
    zmin = min(get_co(o)[:, 2].min() for o in meshes)
    for o in meshes:
        c = get_co(o); c[:, 2] -= zmin; set_co(o, c)
    arm.data.transform(Matrix.Translation((0, 0, -zmin)))
    k = C['height'] / (C['L']['top'] - zmin)          # head top (also valid when the head mesh was removed)
    for o in meshes: set_co(o, get_co(o) * k)
    arm.data.transform(Matrix.Scale(k, 4))
    refresh_joints(C)
    L = C['L']
    for key, v in list(L.items()):
        if isinstance(v, Vector): v.z -= zmin; L[key] = v * k
        elif key == 'top': L[key] = (v - zmin) * k
        else: L[key] = v * k
    C['palm_n'] = {}
    for S in 'LR':
        b = arm.data.bones[f'index.01.{S}']; C['palm_n'][S] = (b.matrix_local.to_3x3() @ Vector((0, 0, 1))).normalized()
    return C

# ============================================================================= shared garment / gear helpers
def band(R, bone, t0, t1, ref=None, cosmin=0.0):
    """> 0 inside the band t0..t1 along 'bone' (and inside the angular sector around 'ref'), roughly in metres."""
    a, c = (np.array(v) for v in R.J[bone]); L = np.linalg.norm(c - a)
    t = R.t(bone); f = np.minimum(t - t0, t1 - t) * L
    if ref is not None:
        r = R.radial(bone); rn = np.linalg.norm(r, axis=1) + 1e-9
        f = np.minimum(f, ((r @ np.array(ref)) / rn - cosmin) * rn)
    return f

def bone_dir(C, bone):
    a, c = C['J'][bone]; return (Vector(c) - Vector(a)).normalized()

def arm_outer(C, S):
    """Unit vector on the dorsal / outer side of the arm (works in the A-pose and in the rest pose)."""
    sg = 1 if S == 'R' else -1
    return (bone_dir(C, f'upper_arm.{S}').cross(Vector((0, 1, 0))) * sg).normalized()

def slot_vertex_mask(ob, slot):
    m = np.zeros(len(ob.data.vertices), dtype=bool)
    for p in ob.data.polygons:
        if p.material_index == slot: m[list(p.vertices)] = True
    return m

def loosen_legs(C, ob, slot, top=1.12, bottom=1.38):
    """Slim jeans -> loose cargo cut: scale the trouser legs radially about the hip-ankle axis."""
    co = get_co(ob); W = read_W(ob); R = Reg(co, W, C['J']); vm = slot_vertex_mask(ob, slot)
    for S in 'LR':
        a = np.array(C['J'][f'thigh.{S}'][0]); c = np.array(C['J'][f'shin.{S}'][1]); d = c - a; L = np.linalg.norm(d); d /= L
        t = np.clip(((co - a) @ d) / L, 0, 1.05); r = (co - a) - np.outer((co - a) @ d, d)
        wl = R.w('leg.' + S) * vm
        co += r * ((top + (bottom - top) * t - 1.0) * wl)[:, None]
    set_co(ob, co)

def surface_bvh(objs):
    vs, fs = [], []
    for o in objs:
        base = len(vs); vs += [Vector(c) for c in get_co(o)]
        fs += [tuple(i + base for i in p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(vs, fs)

def tube(S, pts, r, segs=10, rv=None, vhint=(0, 0, 1), caps=True):
    S.loft([(tuple(p), r, rv if rv is not None else r) for p in pts], segs=segs, vhint=vhint, caps=caps); return S

def spline(pts, n=10):
    """Catmull-Rom through the control points."""
    P_ = [Vector(p) for p in pts]; P_ = [P_[0]] + P_ + [P_[-1]]; out = []
    for i in range(1, len(P_) - 2):
        for k in range(n):
            t = k / n; t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * P_[i]) + (-P_[i - 1] + P_[i + 1]) * t + (2 * P_[i - 1] - 5 * P_[i] + 4 * P_[i + 1] - P_[i + 2]) * t2 + (-P_[i - 1] + 3 * P_[i] - 3 * P_[i + 1] + P_[i + 2]) * t3))
    out.append(P_[-2]); return out

def gear(C, ob, bone=None, bones=None, sigma=0.06):
    """Register a gear mesh: rigid to one bone or soft among a few."""
    if bone: rigid(ob, C['arm'], bone)
    else: soft(ob, C['arm'], bones, C['J'], sigma)
    C['gear'].append(ob); return ob

def metal(name, color, rough=0.3, metallic=1.0):
    return P.new_mat(name, color, rough, metal=metallic)

def afro(C, lift=0.034, base=0.006, curl=0.011, mat=None, subdiv=1):
    """Short natural afro: scalp surface pushed out (rounded top, tighter sides) + dense curl displacement that
    fades out toward the hairline."""
    L = C['L']; z0 = L['ear_top.L'].z - 0.01; z1 = L['top']
    def fn(co, R): return R.g('scalp') - 0.5
    def off(co, R):
        t = smoothstep((co[:, 2] - z0) / (z1 - z0) * 1.3)
        return base + lift * (0.25 + 0.75 * t)
    mat = mat or hair_material(f'MAT_{C["name"]}_hair_afro', scale=70.0, strength=1.0, dist=0.012)
    ob = shell_from(C, C['body'], fn, f'{C["name"]}_afro', mat, offset=0.0, offset_fn=lambda co, R: np.full(len(co), 0.001), smooth=0, hem=0.0, subdiv=subdiv)
    arm = C['arm']
    for m in list(ob.modifiers):
        if m.type == 'ARMATURE': ob.modifiers.remove(m)
    # distance-to-hairline weight (0 on the border) drives both the lift and the curl noise
    n = len(ob.data.vertices); bmk, be = boundary_mask(ob); e = get_edges(ob)
    d = np.where(bmk, 0.0, 1.0)[:, None]
    for _ in range(14):
        d = laplace(d, e, n, 1, 0.6); d[bmk] = 0.0
    d = np.clip(d[:, 0] * 1.6, 0, 1)
    co = get_co(ob); nm = get_normals(ob)
    set_co(ob, co + nm * (off(co, None) * d)[:, None])
    smooth_mesh(ob, iters=2)
    vg = ob.vertex_groups.new(name='_curl')
    for i in range(n): vg.add((i,), float(0.15 + 0.85 * d[i]), 'REPLACE')
    for sc, st in ((0.012, curl), (0.005, curl * 0.6)):
        tx = bpy.data.textures.new(f'{C["name"]}_afro_tex', 'CLOUDS'); tx.noise_scale = sc; tx.noise_depth = 2; tx.noise_basis = 'VORONOI_F1'
        dp = ob.modifiers.new('Curl', 'DISPLACE'); dp.texture = tx; dp.strength = st; dp.mid_level = 0.4; dp.texture_coords = 'LOCAL'; dp.vertex_group = '_curl'
    apply_modifiers(ob); shade_smooth(ob)
    rigid(ob, arm, 'head'); C['parts']['afro'] = ob
    return ob

def hair_material(name='MAT_hair', scale=500.0, strength=0.7, dist=0.003):
    m = P.new_mat(name, (0.010, 0.007, 0.005, 1), 0.85)
    nt = m.node_tree; b = _bsdf(m)
    tex = nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = scale; tex.inputs['Detail'].default_value = 5.0; tex.inputs['Roughness'].default_value = 0.75
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength; bump.inputs['Distance'].default_value = dist
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = 0.25
    return m

def sunglasses(C):
    """Dark wayfarer-style sunglasses resting on the nose bridge and ears."""
    name, L = C['name'], C['L']; col = C['col']
    lens_m = P.new_mat(f'MAT_{name}_sunglass_lens', (0.003, 0.003, 0.004, 1), 0.3)
    _bsdf(lens_m).inputs['Specular IOR Level'].default_value = 0.08
    frame_m = P.new_mat(f'MAT_{name}_sunglass_frame', (0.012, 0.012, 0.014, 1), 0.25, coat=0.6)
    ex, ez = abs(L['eye.R'].x), L['eye.R'].z
    yg = max(L['brow_y'] + 0.004, L['eye.R'].y + 0.020)
    SL, SF = Shape(), Shape()
    hw, hh = 0.0265, 0.0185
    for sg in (-1, 1):
        yaw = Matrix.Rotation(-sg * math.radians(9), 3, 'Z')
        basis = yaw @ Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0))).transposed()      # local x -> X, local y -> Z, local z -> Y
        basis = yaw @ Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
        c = Vector((sg * (ex + 0.003), yg - 0.004 * 1, ez - 0.001))
        SL.box(c, (hw, hh, 0.0012), basis=basis, sq=3.0, segs=40)
        SF.box(c - yaw @ Vector((0, 0.0016, 0)), (hw + 0.0018, hh + 0.0018, 0.0018), basis=basis, sq=3.1, segs=40)
        # temple arm: hinge at the outer top corner -> over the ear -> hook
        h0 = c + yaw @ Vector((sg * (hw + 0.001), -0.002, hh * 0.45))
        et = L['ear_top.' + ('R' if sg > 0 else 'L')]
        e1 = Vector((et.x + sg * 0.004, et.y + 0.012, et.z + 0.004)); e2 = Vector((et.x + sg * 0.001, et.y - 0.022, et.z - 0.012))
        tube(SF, spline([h0, h0.lerp(e1, 0.5) + Vector((sg * 0.004, 0, 0)), e1, e2], 6), 0.0019, segs=8, rv=0.0026)
    tube(SF, [Vector((-(ex + 0.003 - hw + 0.001), yg - 0.0045, ez + 0.007)), Vector((0, yg - 0.003, ez + 0.0085)), Vector((ex + 0.003 - hw + 0.001, yg - 0.0045, ez + 0.007))], 0.0022, segs=8)
    lens = raw(SL, f'{name}_sunglass_lenses', col, lens_m); frame = raw(SF, f'{name}_sunglass_frame', col, frame_m)
    gear(C, lens, 'head'); gear(C, frame, 'head')

def necklace(C, drop=0.07, r=0.0016):
    """Thin chain lying on the skin / vest: ring of ray-cast points around the neck base."""
    name, J = C['name'], C['J']; col = C['col']
    srcs = [C['body']] + [o for k, o in C['parts'].items() if k not in ('body', 'eyes', 'brows', 'lashes', 'hair', 'afro')]
    bvh = surface_bvh(srcs)
    nb = Vector(J['neck'][0]); pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48; d = Vector((math.sin(a), math.cos(a), 0))
        front = 0.5 + 0.5 * math.cos(a)                                    # 1 at the front, 0 at the nape
        z = nb.z + 0.078 - drop * front ** 1.6
        o = Vector((0, nb.y, z)) + d * 0.5
        hit = bvh.ray_cast(o, -d)
        if hit[0] is None: continue
        pts.append(hit[0] + d * (r + 0.0012))
    pts.append(pts[0])
    S = Shape(); tube(S, pts, r, segs=6)
    ch = raw(S, f'{name}_chain', col, metal(f'MAT_{name}_chain', SILVER, 0.22))
    gear(C, ch, bones=['chest', 'neck'], sigma=0.05)

def finalize(C):
    """Join into a few Armature-deformed objects: <NAME>_body (skin, eyes, hair), <NAME>_clothes, <NAME>_gear."""
    name, arm = C['name'], C['arm']; out = {}
    bodyk = ('body', 'eyes', 'brows', 'lashes', 'hair', 'afro')
    groups = {'body': [C['parts'][k] for k in bodyk if k in C['parts']],
              'clothes': [o for k, o in C['parts'].items() if k not in bodyk] + C['cloth'],
              'gear': C['gear']}
    for g, objs in groups.items():
        objs = [o for o in objs if o is not None and len(o.data.polygons)]
        if not objs: continue
        print(f'   {g}:', {o.name: tri_count(o) for o in objs})
        for o in objs:
            for uv in o.data.uv_layers: uv.name = 'UVMap'
        tgt = objs[0]; join(tgt, objs[1:]); tgt.name = f'{name}_{g}'; tgt.data.name = f'{name}_{g}'
        bind(tgt, arm); out[g] = tgt
    C['objs'] = out
    tris = {g: tri_count(o) for g, o in out.items()}
    for o in C.get('props', []): tris[o.name] = tri_count(o)
    C['tris'] = sum(tris.values())
    print(f'[{name}] triangles {C["tris"]}  {tris}')
    return C

def split_suit(C, key, parts, thr=0.56, verbose=False):
    """Recolour a MakeHuman suit: islands above thr*height -> first part ('top'), below -> second ('bottom')."""
    keys = list(parts.keys())
    return recolor(C, C['parts'][key], parts, lambda i: keys[0] if i['zmean'] > thr else keys[1], verbose=verbose)

def one_color(C, key, pname, color, rough=0.6, contrast=0.8):
    return recolor(C, C['parts'][key], {pname: dict(color=color, rough=rough, contrast=contrast, alpha=True)}, lambda i: pname)

# ============================================================================= characters
def build_hero():
    C = mh_character('HERO', height=1.78, gender=1.0, age=0.42, muscle=0.62, weight=0.38, skin='young_african_male', skin_value=0.62,
                     hair=None, brows='eyebrow001', clothes=('male_casualsuit06', 'shoes05'))
    name, J = C['name'], C['J']; suit = C['parts']['male_casualsuit06']
    sl = split_suit(C, 'male_casualsuit06', {'vest': dict(color=shade(SILVER, 1.0), rough=0.8, contrast=0.35),
                                              'cargo': dict(color=(0.115, 0.125, 0.14, 1), rough=0.9, contrast=0.85)}, verbose=True)
    one_color(C, 'shoes05', 'sneakers', shade(SILVER, 1.0), rough=0.45, contrast=0.75)
    refine_skin(C['body'])
    afro(C, subdiv=1)
    # loose cargo trousers with thigh pockets
    loosen_legs(C, suit, sl['cargo'], top=1.10, bottom=1.42)
    cargo_m = suit.data.materials[sl['cargo']]
    for S, sg in (('L', -1), ('R', 1)):
        ref = (sg, 0.15, 0)
        def pocket(co, R, t0=0.40, t1=0.74, cm=0.62, S=S, ref=ref):
            return np.where(R.w('leg.' + S) > 0.5, band(R, f'thigh.{S}', t0, t1, ref, cm), -1.0)
        pk = shell_from(C, suit, pocket, f'{name}_pocket.{S}', cargo_m, offset=0.012, smooth=1, hem=0.011, slot=sl['cargo'], subdiv=2)
        fl = shell_from(C, pk, lambda co, R, S=S: (0.52 - R.t(f'thigh.{S}')) * 0.4, f'{name}_flap.{S}', cargo_m, offset=0.005, smooth=0, hem=0.004)
        C['cloth'] += [pk, fl]
    # open short-sleeve shirt with the bold black & white print, derived from the T-shirt surface
    tz = get_co(suit)[slot_vertex_mask(suit, sl['vest'])]; hem_z, neck_z = tz[:, 2].min(), J['neck'][0].z
    def shirt_fn(co, R):
        t = np.clip((co[:, 2] - hem_z) / (neck_z - hem_z), 0, 1)
        w = 0.030 + 0.050 * t ** 1.6
        return np.where(co[:, 1] > J['spine'][0].y, np.abs(co[:, 0]) - w, 0.05)
    def shirt_off(co, R):
        t = np.clip((co[:, 2] - hem_z) / (neck_z - hem_z), 0, 1)
        return 0.011 + 0.020 * (1 - t) ** 2 + 0.006 * R.w('arms')
    shirt = shell_from(C, suit, shirt_fn, f'{name}_shirt', pattern_material(f'MAT_{name}_shirt_pattern'), offset_fn=shirt_off, smooth=3, hem=0.004, subdiv=1, slot=sl['vest'])
    C['cloth'].append(shirt)
    rerest(C)
    sunglasses(C); necklace(C)
    return finalize(C)

def build_civilian_a():
    C = mh_character('CIVILIAN_A', height=1.81, gender=1.0, age=0.55, muscle=0.55, weight=0.62, skin='middleage_african_male', skin_value=0.72,
                     hair='short02', brows='eyebrow003', clothes=('male_casualsuit04', 'shoes04'))
    split_suit(C, 'male_casualsuit04', {'tee': dict(color=THERMO, rough=0.85, contrast=0.5), 'trousers': dict(color=shade(NIGHT, 2.2), rough=0.85, contrast=0.6)})
    one_color(C, 'shoes04', 'shoes', shade(SILVER, 0.55), rough=0.5)
    refine_skin(C['body']); rerest(C)
    return finalize(C)

def build_civilian_b():
    C = mh_character('CIVILIAN_B', height=1.64, gender=0.0, age=0.5, muscle=0.4, weight=0.66, cupsize=0.6, skin='young_african_female', skin_value=0.85,
                     hair='braid01', brows='eyebrow006', clothes=('female_elegantsuit01', 'shoes02'))
    split_suit(C, 'female_elegantsuit01', {'blouse': dict(color=DIVE, rough=0.7, contrast=0.5), 'skirt': dict(color=shade(SILVER, 0.9), rough=0.8, contrast=0.5)}, thr=0.60)
    one_color(C, 'shoes02', 'shoes', shade(NIGHT, 1.5), rough=0.5)
    refine_skin(C['body']); rerest(C)
    return finalize(C)

def build_civilian_c():
    C = mh_character('CIVILIAN_C', height=1.72, gender=0.0, age=0.42, muscle=0.72, weight=0.42, cupsize=0.5, skin='young_african_female', skin_value=0.66,
                     hair='ponytail01', brows='eyebrow005', clothes=('female_sportsuit01', 'shoes04'))
    split_suit(C, 'female_sportsuit01', {'top': dict(color=VIOLET, rough=0.6, contrast=0.4), 'leggings': dict(color=shade(NIGHT, 1.6), rough=0.55, contrast=0.4)}, thr=0.62)
    one_color(C, 'shoes04', 'trainers', shade(SILVER, 0.9), rough=0.5)
    refine_skin(C['body']); rerest(C)
    return finalize(C)

def build_passenger():
    C = mh_character('PASSENGER', height=1.74, gender=1.0, age=0.68, muscle=0.45, weight=0.62, skin='middleage_african_male', skin_value=0.82,
                     hair='short03', brows='eyebrow002', clothes=('male_casualsuit03', 'shoes03'))
    split_suit(C, 'male_casualsuit03', {'shirt': dict(color=shade(SILVER, 0.95), rough=0.8, contrast=0.6), 'trousers': dict(color=DIVE, rough=0.85, contrast=0.6)})
    one_color(C, 'shoes03', 'shoes', shade(NIGHT, 1.3), rough=0.4)
    refine_skin(C['body']); rerest(C)
    finalize(C)
    # seat prop + seated pose (kept from the previous asset for compatibility)
    S = Shape(); k = C['height'] / 1.75
    S.box((0, -0.03, 0.42 * k), (0.24, 0.20, 0.02)); S.box((0, -0.25, 0.62 * k), (0.24, 0.02, 0.2))
    for sx in (-0.2, 0.2):
        for sy in (-0.2, 0.14): S.box((sx, sy, 0.2 * k), (0.018, 0.018, 0.2 * k))
    seat = raw(S, 'PASSENGER_seat', C['col'], P.new_mat('MAT_PASSENGER_seat', shade(NIGHT, 3.0), 0.6), smooth=False)
    seat.parent = C['root']; C['props'] = [seat]
    A.make_seated_pose(C['arm'], frame=1)
    return C

def build_worker():
    C = mh_character('WORKER', height=1.78, gender=1.0, age=0.6, muscle=0.7, weight=0.62, skin='middleage_african_male', skin_value=0.66,
                     hair='short04', brows='eyebrow004', clothes=('male_worksuit01', 'shoes01'))
    name, J = C['name'], C['J']; suit = C['parts']['male_worksuit01']
    split_suit(C, 'male_worksuit01', {'shirt': dict(color=GREEN, rough=0.85, contrast=0.5), 'workwear': dict(color=shade(NIGHT, 2.6), rough=0.9, contrast=0.6)}, thr=0.60, verbose=True)
    one_color(C, 'shoes01', 'boots', shade(THERMO_D, 0.22), rough=0.55)
    # hi-vis vest: shell over the suit torso, zip gap at the front, reflective bands derived from the vest
    z0 = J['spine'][0].z - 0.02; z1 = J['neck'][0].z + 0.01; ym = J['chest'][0].y
    def vest_fn(co, R):
        f = np.minimum(co[:, 2] - z0, (0.30 - R.w('arms')) * 0.2)
        f = np.minimum(f, np.hypot(co[:, 0], (co[:, 1] - J['neck'][0].y) * 0.9) - 0.075 + (z1 - co[:, 2]) * 0.6)
        t = np.clip((co[:, 2] - J['chest'][0].z) / (z1 - J['chest'][0].z), 0, 1)
        return np.where(co[:, 1] > ym, np.minimum(f, np.abs(co[:, 0]) - (0.006 + 0.05 * t ** 2)), f)
    vest = shell_from(C, suit, vest_fn, f'{name}_hivis', cloth_material(f'MAT_{name}_hivis', THERMO, rough=0.6, sheen=0.3, weave=1400), offset=0.011, smooth=3, hem=0.004, subdiv=1)
    refl = P.new_mat(f'MAT_{name}_reflective', shade(SILVER, 1.0), 0.18, metal=0.7, coat=0.6)
    zw = J['spine'][0].z
    def strip_fn(co, R):
        h1 = 0.022 - np.abs(co[:, 2] - (zw + 0.035)); h2 = 0.022 - np.abs(co[:, 2] - (zw + 0.125))
        v = np.minimum(0.019 - np.abs(np.abs(co[:, 0]) - 0.085), co[:, 2] - (zw + 0.125))
        return np.maximum(np.maximum(h1, h2), v)
    strips = shell_from(C, vest, strip_fn, f'{name}_reflective', refl, offset=0.0025, smooth=0, hem=0.0025)
    # work gloves
    glove_m = cloth_material(f'MAT_{name}_glove', shade(THERMO_D, 0.9), rough=0.8, sheen=0.2)
    def glove_fn(co, R):
        f = np.full(len(co), -1.0)
        for S in 'LR':
            f = np.where(R.w('arm.' + S) > 0.5, (R.t(f'forearm.{S}') - 0.84) * 0.25, f)
        return f
    gloves = shell_from(C, C['body'], glove_fn, f'{name}_gloves', glove_m, offset=0.0035, smooth=1, hem=0.004)
    delete_region(C['body'], lambda co, R: glove_fn(co, R) - 0.012, J)
    C['cloth'] += [vest, strips, gloves]
    refine_skin(C['body'])
    rerest(C)
    # hard hat
    L = C['L']; hw = L['head_w'] + 0.014; cy = (L['brow_y'] + L['back']) / 2; hd = (L['brow_y'] - L['back']) / 2 + 0.016
    zb = L['eye.R'].z + 0.040; zt = L['top']
    S = Shape()
    S.loft([((0, cy + dy, z), hw * k, hd * k) for z, k, dy in ((zb, 1.0, 0), (zb + 0.03, 1.0, 0), (zt - 0.03, 0.93, -0.003), (zt + 0.004, 0.72, -0.006), (zt + 0.024, 0.42, -0.008), (zt + 0.032, 0.12, -0.008))], segs=40, sq=2.15)
    S.loft([((0, cy + 0.022, zb - 0.004), hw * 1.07, hd * 1.20), ((0, cy + 0.022, zb + 0.004), hw * 1.06, hd * 1.18)], segs=40, sq=2.1)   # brim / peak
    for x in (-0.03, 0.0, 0.03):   # ribs
        tube(S, [Vector((x, cy + hd * (0.86 if x else 0.9) * math.cos(a), zb + 0.02 + (zt + 0.03 - zb) * math.sin(a) * (0.97 if x else 1.0))) for a in np.linspace(0.25, math.pi - 0.25, 12)], 0.007, segs=8)
    hat = solid(S, f'{name}_hardhat', C['col'], voxel=0.004, smooth=3, mat=P.new_mat(f'MAT_{name}_hardhat', THERMO_D, 0.3, coat=0.6), ratio=0.3)
    gear(C, hat, 'head')
    return finalize(C)

# ============================================================================= DIVER
def hand_frame(C, S):
    """Rest-pose hand frame: wrist, finger direction d, palm normal en, thumb-side direction et."""
    J = C['J']; W = Vector(J[f'hand.{S}'][0]); d = (Vector(J[f'hand.{S}'][1]) - W).normalized()
    en = C['palm_n'][S].copy(); en = (en - d * en.dot(d)).normalized()
    thumb = (Vector(J[f'thumb.02.{S}'][0]) - W)
    et = d.cross(en)
    if et.dot(thumb) < 0: et = -et
    return W, d, en, et

def bone_parent(ob, arm, bone):
    """Rigid prop parented to a bone, keeping its world placement (mesh data stays in rest-pose world space)."""
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = arm; ob.parent_type = 'BONE'; ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = mw
    return ob

def build_diver():
    C = mh_character('DIVER', height=1.76, gender=1.0, age=0.5, muscle=0.6, weight=0.5, skin='young_african_male', skin_value=0.7,
                     hair=None, brows='eyebrow001', clothes=())
    name, col = C['name'], C['col']; body = C['body']
    neo = cloth_material(f'MAT_{name}_wetsuit', shade(NIGHT, 1.0), rough=0.5, sheen=0.25, weave=2500, bump=0.04)
    neo2 = cloth_material(f'MAT_{name}_wetsuit_panel', shade(NIGHT, 2.3), rough=0.55, sheen=0.25, weave=2500, bump=0.04)
    hood_m = cloth_material(f'MAT_{name}_hood', DIVE, rough=0.5, sheen=0.3, weave=2500, bump=0.04)
    glove_m = cloth_material(f'MAT_{name}_glove', shade(NIGHT, 1.4), rough=0.65, sheen=0.1, weave=1800, bump=0.06)
    rubber = P.new_mat(f'MAT_{name}_rubber', shade(NIGHT, 0.8), 0.45)
    chrome = metal(f'MAT_{name}_chrome', shade(SILVER, 1.0), 0.18)
    refine_skin(body, keep=('head',))
    rerest(C)
    J, L = C['J'], C['L']
    ez = L['eye.R'].z; chin = L['chin']; zc = (ez + 0.028 + chin.z + 0.012) / 2; hz = (ez + 0.028 - chin.z - 0.012) / 2
    def face_fn(co, R):
        e = (co[:, 0] / 0.064) ** 2 + ((co[:, 2] - zc) / hz) ** 2
        return np.minimum((1.0 - e) * 0.03, co[:, 1] - (L['ear.R'].y + 0.045))
    # --- hood (Dive Blue, as the cap in the client photo): shell over head + neck with a face opening
    collar = J['neck'][0].z + 0.012
    def hood_fn(co, R):
        return np.minimum(np.minimum(-face_fn(co, R), co[:, 2] - collar), (R.w('headneck') - 0.4) * 0.05)
    hood = shell_from(C, body, hood_fn, f'{name}_hood', hood_m, offset=0.006, smooth=4, hem=0.0)
    hc = get_co(hood); lim = L['head_w'] + 0.009            # neoprene presses the ears flat
    hc[:, 0] = np.clip(hc[:, 0], -lim, lim); set_co(hood, hc); smooth_mesh(hood, iters=5); add_hem(hood, 0.005)
    delete_region(body, lambda co, R: np.maximum(R.g('scalp'), R.g('ears')) - 0.5, J, cut=False)
    C['cloth'].append(hood)
    # --- full wetsuit: every remaining body face except the face oval; side panels and gloves as separate materials
    for m in list(body.data.materials)[1:]: pass
    paint_region(body, lambda co, R: -face_fn(co, R), neo, J)
    def panel_fn(co, R):   # lighter side panels torso + outer legs, like a two-tone suit
        side = np.abs(co[:, 0]) - 0.105
        return np.where(R.w('torso') > 0.5, np.minimum(side, J['chest'][1].z - 0.06 - co[:, 2]), -1.0)
    paint_region(body, panel_fn, neo2, J)
    def glove_fn(co, R):
        f = np.full(len(co), -1.0)
        for S in 'LR': f = np.where(R.w('arm.' + S) > 0.5, (R.t(f'forearm.{S}') - 0.93) * 0.25, f)
        return f
    paint_region(body, glove_fn, glove_m, J)
    def boot_fn(co, R):
        f = np.full(len(co), -1.0)
        for S in 'LR': f = np.where(R.w('leg.' + S) > 0.5, (R.t(f'shin.{S}') - 0.86) * 0.4, f)
        return f
    paint_region(body, boot_fn, glove_m, J)
    S = Shape()   # cuff seams
    for sd in 'LR':
        a, c = Vector(J[f'forearm.{sd}'][0]), Vector(J[f'forearm.{sd}'][1]); p = a.lerp(c, 0.93); d = (c - a).normalized()
        S.loft([(tuple(p - d * 0.008), 0.031, 0.036), (tuple(p + d * 0.008), 0.030, 0.035)], segs=20)
    cuffs = raw(S, f'{name}_cuffs', col, neo)
    gear(C, cuffs, bones=['forearm.L', 'forearm.R'], sigma=0.03)
    # --- surfaces for placing gear
    bvh = surface_bvh([body])
    def surf(z, ang, margin=0.0, x0=0.0):
        d = Vector((math.sin(ang), math.cos(ang), 0)); o = Vector((x0, J['chest'][0].y, z)) + d * 0.6
        hit = bvh.ray_cast(o, -d)
        return (hit[0] + d * margin) if hit[0] is not None else o - d * 0.45
    sh_z = J['upper_arm.R'][0].z; waist = J['spine'][0].z; nip = J['chest'][0].z + 0.10
    # --- BCD jacket: shell over the wetsuit torso (shoulder straps, open chest, closed lower front panel)
    bz0 = waist - 0.055; zv = J['chest'][0].z + 0.02; ny = J['neck'][0].y
    def bcd_fn(co, R):
        f = np.minimum(co[:, 2] - bz0, (0.22 - R.w('arms')) * 0.25)
        f = np.minimum(f, np.hypot(co[:, 0], (co[:, 1] - ny)) - 0.082 + np.clip(sh_z + 0.05 - co[:, 2], -0.1, 0.3) * 0.5)
        t = np.clip((co[:, 2] - zv) / 0.16, 0, 1)
        front = np.abs(co[:, 0]) - (0.085 * smoothstep(t) - 0.002)
        return np.where((co[:, 1] > J['chest'][0].y + 0.02) & (co[:, 2] > zv), np.minimum(f, front), f)
    bcd_m = cloth_material(f'MAT_{name}_bcd', shade(NIGHT, 0.9), rough=0.75, sheen=0.3, weave=700, bump=0.15)
    bcd = shell_from(C, body, bcd_fn, f'{name}_bcd', bcd_m, offset=0.020, smooth=5, hem=0.008, subdiv=1)
    panel_m = cloth_material(f'MAT_{name}_bcd_panel', shade(SILVER, 0.33), rough=0.7, sheen=0.3, weave=700, bump=0.15)
    paint_region(bcd, lambda co, R: np.minimum(np.minimum(zv - 0.015 - co[:, 2], co[:, 2] - (bz0 + 0.035)), np.minimum(co[:, 1] - (J['chest'][0].y + 0.05), 0.13 - np.abs(co[:, 0]))), panel_m, J)
    band = shell_from(C, bcd, lambda co, R: 0.032 - np.abs(co[:, 2] - (waist + 0.0)), f'{name}_waistband', rubber, offset=0.004, smooth=0, hem=0.004)
    C['cloth'] += [bcd, band]
    bvh2 = surface_bvh([body, bcd])
    def surf2(z, ang, margin=0.0):
        d = Vector((math.sin(ang), math.cos(ang), 0)); o = Vector((0, J['chest'][0].y, z)) + d * 0.6
        hit = bvh2.ray_cast(o, -d)
        return (hit[0] + d * margin) if hit[0] is not None else o - d * 0.45
    S = Shape()
    S.box(surf2(waist, 0.0, 0.008), (0.028, 0.008, 0.022))                         # waist buckle
    cs_z = zv + 0.085
    pl, pr = surf2(cs_z, math.radians(-38), 0.004), surf2(cs_z, math.radians(38), 0.004)
    tube(S, [pl, (pl + pr) / 2 + Vector((0, 0.012, 0)), pr], 0.003, segs=8, rv=0.011)   # sternum strap
    S.box((pl + pr) / 2 + Vector((0, 0.014, 0)), (0.016, 0.006, 0.014))
    buckles = raw(S, f'{name}_buckles', col, rubber, smooth=False)
    gear(C, buckles, bones=['chest', 'spine'], sigma=0.05)
    # --- tank with boot, bands, valve and first stage
    back0 = surf2(waist + 0.02, math.pi).y; back1 = surf2(sh_z - 0.02, math.pi).y
    tr = 0.088
    p0 = Vector((0, min(back0, back1) - tr - 0.012, waist - 0.07)); p1 = Vector((0, min(back0, back1) - tr - 0.012, sh_z + 0.03))
    S = Shape()
    S.loft([(tuple(p0 + Vector((0, 0, dz))), r, r) for dz, r in ((0.0, tr * 0.6), (0.012, tr * 0.93), (0.05, tr), ((p1 - p0).z - 0.07, tr), ((p1 - p0).z - 0.03, tr * 0.86), ((p1 - p0).z, tr * 0.5), ((p1 - p0).z + 0.02, 0.026), ((p1 - p0).z + 0.045, 0.024))], segs=32)
    tank = raw(S, f'{name}_tank', col, metal(f'MAT_{name}_tank', shade(SILVER, 0.9), 0.32))
    S = Shape()
    S.loft([(tuple(p0 + Vector((0, 0, dz))), r, r) for dz, r in ((-0.006, tr * 0.7), (0.0, tr + 0.004), (0.075, tr + 0.004), (0.08, tr + 0.001))], segs=32)   # boot
    for dz in (0.20, 0.42):   # cam bands
        S.loft([(tuple(p0 + Vector((0, 0, dz - 0.022))), tr + 0.003, tr + 0.003), (tuple(p0 + Vector((0, 0, dz + 0.022))), tr + 0.003, tr + 0.003)], segs=32)
        S.box(p0 + Vector((0, tr * 0.6, dz)), (0.075, 0.035, 0.022))               # backpack pad between tank and BCD
    top = p1 + Vector((0, 0, 0.045))
    S.box(top + Vector((0, 0, 0.012)), (0.022, 0.022, 0.02))                        # valve block
    tube(S, [top + Vector((0.02, 0, 0.012)), top + Vector((0.06, 0, 0.012))], 0.016, segs=14)   # hand wheel
    tankgear = raw(S, f'{name}_tank_fittings', col, rubber, smooth=False); shade_smooth(tankgear)
    FS = top + Vector((0, 0.04, 0.012))
    S = Shape(); tube(S, [top + Vector((0, 0.012, 0.012)), FS + Vector((0, 0.022, 0))], 0.021, segs=16)   # first stage
    S.box(FS, (0.03, 0.016, 0.016))
    first = raw(S, f'{name}_first_stage', col, chrome)
    for o in (tank, tankgear, first): gear(C, o, 'chest')
    # --- dive mask: twin-lens frame, glass, skirt, nose pocket, strap
    ex = abs(L['eye.R'].x); yf = L['eye.R'].y + 0.048
    S = Shape(); SG = Shape()
    for sg in (-1, 1):
        b = Matrix.Rotation(-sg * math.radians(6), 3, 'Z') @ Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
        c = Vector((sg * (ex + 0.002), yf, ez + 0.003))
        S.box(c, (0.0315, 0.0265, 0.0065), basis=b, sq=3.2, segs=36)
        SG.box(c + Vector((0, 0.0012, 0)), (0.0275, 0.0225, 0.0065), basis=b, sq=3.0, segs=36)
    S.box((0, yf - 0.001, ez + 0.012), (0.012, 0.006, 0.012))                       # bridge
    S.ellipsoid((L['nose'].x, L['nose'].y - 0.004, L['nose'].z + 0.004), (0.021, 0.022, 0.026))   # nose pocket
    frame = raw(S, f'{name}_mask_frame', col, rubber)
    glass = raw(SG, f'{name}_mask_glass', col, P.new_mat(f'MAT_{name}_mask_glass', (1, 1, 1, 1), 0.0, transmission=1.0, ior=1.45))
    S = Shape()
    fy = L['brow_y'] - 0.016
    S.loft([((0, yf - 0.004, ez + 0.003), 0.066, 0.030), ((0, (yf + fy) / 2, ez + 0.003), 0.068, 0.034), ((0, fy, ez + 0.004), 0.071, 0.039)], segs=40, vhint=(0, 0, 1), caps=False, sq=2.8)
    hwd = L['head_w'] + 0.010; cy = (L['brow_y'] + L['back']) / 2; hd = (L['brow_y'] - L['back']) / 2 + 0.010
    strap_pts = [Vector((hwd * math.sin(a), cy + hd * math.cos(a) * (1.0 if math.cos(a) < 0 else 0.86), ez + 0.004 + 0.016 * (1 - math.cos(a)) / 2)) for a in np.linspace(math.radians(52), math.radians(308), 30)]
    tube(S, strap_pts, 0.0022, segs=8, rv=0.010)
    skirt = raw(S, f'{name}_mask_skirt', col, rubber)
    # --- snorkel on the left mask strap (Dive Blue tube, black top + mouthpiece)
    S = Shape(); mx = -(hwd + 0.016); mf = L['mouth_front']; mz = L['mouth'].z
    sn = spline([(-0.045, mf + 0.012, mz - 0.012), (-0.075, mf - 0.012, mz - 0.03), (mx + 0.004, L['ear.L'].y + 0.045, mz - 0.012), (mx, L['ear.L'].y + 0.03, ez), (mx, L['ear.L'].y + 0.012, L['top'] + 0.02), (mx + 0.006, L['ear.L'].y - 0.01, L['top'] + 0.13)], 8)
    tube(S, sn, 0.0105, segs=14)
    snorkel = raw(S, f'{name}_snorkel', col, P.new_mat(f'MAT_{name}_snorkel', DIVE, 0.3, coat=0.4))
    S = Shape(); tube(S, [sn[-1] - Vector((0, 0, 0.01)), sn[-1] + Vector((0.002, -0.004, 0.045))], 0.0135, segs=14)
    tube(S, [sn[0] + Vector((0.016, 0.0, 0.004)), sn[0], sn[2]], 0.0125, segs=12)
    S.box(sn[len(sn) // 2 + 2] + Vector((0.008, 0, 0)), (0.007, 0.012, 0.012))        # strap keeper
    sn_fit = raw(S, f'{name}_snorkel_fittings', col, rubber)
    # --- regulator second stage in the mouth
    Rg = Vector((0, mf + 0.034, mz - 0.006))
    S = Shape()
    tube(S, [Rg - Vector((0, 0.017, 0)), Rg + Vector((0, 0.012, 0)), Rg + Vector((0, 0.018, 0))], 0.034, segs=28, vhint=(0, 0, 1))
    S.box((0, mf + 0.008, mz - 0.004), (0.021, 0.012, 0.010))                        # mouthpiece
    S.box(Rg + Vector((0, -0.004, -0.034)), (0.040, 0.012, 0.009))                   # exhaust tee
    tube(S, [Rg + Vector((0.030, 0, 0)), Rg + Vector((0.050, -0.004, 0.0))], 0.010, segs=12)   # hose nut
    reg = raw(S, f'{name}_regulator', col, rubber)
    S = Shape(); tube(S, [Rg + Vector((0, 0.017, 0)), Rg + Vector((0, 0.023, 0))], 0.027, segs=28, vhint=(0, 0, 1))
    tube(S, [Rg + Vector((0, 0.022, 0)), Rg + Vector((0, 0.027, 0))], 0.012, segs=16, vhint=(0, 0, 1))
    regcap = raw(S, f'{name}_regulator_cap', col, chrome)
    for o in (frame, glass, skirt, snorkel, sn_fit, reg, regcap): gear(C, o, 'head')
    # --- hoses
    hose_m = P.new_mat(f'MAT_{name}_hose', shade(NIGHT, 0.7), 0.5)
    rs = J['upper_arm.R'][0]; ls = J['upper_arm.L'][0]
    S = Shape()
    reg_path = spline([FS + Vector((0.03, 0, 0)), Vector((rs.x - 0.07, FS.y + 0.02, sh_z + 0.105)), Vector((rs.x - 0.035, ny + 0.03, sh_z + 0.10)), Vector((rs.x - 0.045, mf - 0.01, mz + 0.01)), Rg + Vector((0.05, -0.004, 0))], 10)
    tube(S, reg_path, 0.0075, segs=10)
    hose_reg = raw(S, f'{name}_hose_regulator', col, hose_m)
    gear(C, hose_reg, bones=['head', 'neck', 'chest'], sigma=0.07)
    S = Shape()
    oc = surf2(waist + 0.15, math.radians(28), 0.03)                                  # octopus parked on the right chest
    tube(S, spline([FS + Vector((0.03, 0, -0.01)), Vector((rs.x - 0.04, FS.y + 0.03, sh_z + 0.07)), surf2(sh_z + 0.02, math.radians(62), 0.03), surf2(nip, math.radians(48), 0.022), oc + Vector((0.035, 0.0, 0.02))], 10), 0.007, segs=10)
    gc = surf2(waist + 0.03, math.radians(-42), 0.03)                                 # gauge console on the left hip
    tube(S, spline([FS + Vector((-0.03, 0, -0.01)), Vector((ls.x + 0.02, FS.y + 0.03, sh_z - 0.06)), surf2(nip - 0.03, math.radians(-105), 0.02), surf2(waist + 0.12, math.radians(-75), 0.025), gc + Vector((0, 0, 0.05))], 10), 0.0065, segs=10)
    infl = [surf2(sh_z + 0.035, math.radians(-30), 0.014), surf2(sh_z - 0.03, math.radians(-33), 0.02), surf2(nip - 0.02, math.radians(-30), 0.022), surf2(nip - 0.10, math.radians(-30), 0.024)]
    ip = spline(infl, 10)
    S.loft([(tuple(p), 0.0105 + 0.002 * (i % 2), 0.0105 + 0.002 * (i % 2)) for i, p in enumerate(ip)], segs=12)   # corrugated inflator hose
    S.box(ip[-1] + Vector((0, 0.004, -0.03)), (0.013, 0.012, 0.032))
    hoses = raw(S, f'{name}_hoses', col, hose_m)
    S = Shape()
    tube(S, [oc + Vector((0, -0.012, 0)), oc + Vector((0, 0.014, 0))], 0.030, segs=24, vhint=(0, 0, 1))
    octo = raw(S, f'{name}_octopus', col, P.new_mat(f'MAT_{name}_octopus', GREEN, 0.4))
    S = Shape(); S.box(gc, (0.026, 0.014, 0.05), sq=3.0)
    console = raw(S, f'{name}_console', col, rubber)
    S = Shape(); tube(S, [gc + Vector((0, 0.012, 0.018)), gc + Vector((0, 0.017, 0.018))], 0.019, segs=20, vhint=(0, 0, 1))
    S.box(gc + Vector((0, 0.013, -0.024)), (0.018, 0.004, 0.014))
    dial = raw(S, f'{name}_console_dial', col, P.new_mat(f'MAT_{name}_console_dial', THERMO, 0.35))
    for o in (hoses, octo, console, dial): gear(C, o, bones=['chest', 'spine', 'hips'], sigma=0.07)
    # --- fins: foot pocket + blade with rails
    S = Shape()
    for sd in 'LR':
        an, toe = Vector(J[f'foot.{sd}'][0]), Vector(J[f'foot.{sd}'][1])
        f = Vector((toe.x - an.x, toe.y - an.y, 0)).normalized(); side = Vector((f.y, -f.x, 0))
        def P_(a, z): return Vector((an.x, an.y, 0)) + f * a + Vector((0, 0, z))
        FSh = Shape()
        FSh.loft([(tuple(P_(-0.075, 0.045)), 0.040, 0.040), (tuple(P_(-0.03, 0.050)), 0.052, 0.050), (tuple(P_(0.07, 0.043)), 0.058, 0.043), (tuple(P_(0.17, 0.034)), 0.062, 0.034), (tuple(P_(0.23, 0.024)), 0.066, 0.022)], segs=20, vhint=(0, 0, 1), sq=2.6)
        FSh.loft([(tuple(P_(0.20, 0.016)), 0.066, 0.010), (tuple(P_(0.34, 0.013)), 0.076, 0.006), (tuple(P_(0.56, 0.011)), 0.090, 0.0045), (tuple(P_(0.66, 0.010)), 0.092, 0.004)], segs=16, vhint=(0, 0, 1), sq=5.0)
        for s_ in (-1, 1):
            FSh.loft([(tuple(P_(0.16, 0.022) + side * s_ * 0.062), 0.007, 0.012), (tuple(P_(0.40, 0.016) + side * s_ * 0.080), 0.006, 0.010), (tuple(P_(0.66, 0.011) + side * s_ * 0.092), 0.004, 0.006)], segs=8, vhint=(0, 0, 1))
        fin = raw(FSh, f'{name}_fin.{sd}', col, P.new_mat(f'MAT_{name}_fin', shade(NIGHT, 0.9), 0.4))
        gear(C, fin, f'foot.{sd}')
    finalize(C)
    # --- torch in the right hand: separate prop DIVER_TORCH (bone-parented) with a spot light child
    W, d, en, et = hand_frame(C, 'R')
    G = W + d * 0.085 + en * 0.026
    S = Shape()
    tube(S, [G - et * 0.075, G + et * 0.05], 0.0165, segs=20)
    S.loft([(tuple(G + et * 0.05), 0.0165, 0.0165), (tuple(G + et * 0.07), 0.027, 0.027), (tuple(G + et * 0.105), 0.028, 0.028)], segs=24)
    tube(S, [G - et * 0.085, G - et * 0.075], 0.012, segs=12)
    torch = raw(S, 'DIVER_TORCH', col, P.new_mat(f'MAT_{name}_torch', THERMO, 0.35, metal=0.2))
    lens = P.new_mat(f'MAT_{name}_torch_lens', (1, 1, 1, 1), 0.1, emission=(1.0, 0.95, 0.8, 1), estrength=20.0)
    torch.data.materials.append(lens)
    tip = G + et * 0.105
    for pg in torch.data.polygons:
        if pg.normal.dot(et) > 0.9 and (Vector(pg.center) - tip).length < 0.03: pg.material_index = 1
    torch.parent = C['arm']; bone_parent(torch, C['arm'], 'hand.R')
    ld = bpy.data.lights.new('DIVER_TORCH_LIGHT', 'SPOT'); ld.energy = 400; ld.spot_size = math.radians(38); ld.spot_blend = 0.4; ld.color = (1.0, 0.95, 0.85); ld.shadow_soft_size = 0.03
    lt = bpy.data.objects.new('DIVER_TORCH_LIGHT', ld); col.objects.link(lt)
    lt.parent = torch
    bpy.context.view_layer.update()
    lt.matrix_world = Matrix.Translation(tip + et * 0.004) @ (Vector((0, 0, -1)).rotation_difference(et)).to_matrix().to_4x4()
    C['props'] = [torch]; C['tris'] += tri_count(torch)
    return C

# ============================================================================= ROBOT (armoured suit)
def build_robot():
    C = mh_character('ROBOT', height=1.86, gender=1.0, age=0.5, muscle=1.0, weight=0.52, skin='young_african_male',
                     hair=None, brows=None, lashes=None, clothes=(), keep_head=False)
    name, col, body, J = C['name'], C['col'], C['body'], C['J']
    L = C['L']
    armor = P.new_mat(f'MAT_{name}_armor', shade(SILVER, 1.15), 0.28, coat=0.5)
    dark = P.new_mat(f'MAT_{name}_armor_dark', shade(NIGHT, 0.9), 0.35, coat=0.3)
    under = cloth_material(f'MAT_{name}_undersuit', shade(NIGHT, 1.3), rough=0.55, sheen=0.15, weave=1600, bump=0.12)
    glove_m = cloth_material(f'MAT_{name}_glove', shade(NIGHT, 0.8), rough=0.6, sheen=0.1, weave=2200, bump=0.1)
    strap_m = cloth_material(f'MAT_{name}_strap', shade(GREEN, 0.55), rough=0.8, sheen=0.2, weave=900, bump=0.2)
    visor_m = P.new_mat(f'MAT_{name}_visor', (0.004, 0.006, 0.012, 1), 0.06, coat=1.0, emission=DIVE, estrength=0.45)
    # --- dark under-suit: the MakeHuman body itself (head removed, it lives inside the helmet)
    delete_region(body, lambda co, R: R.w('head') - 0.5, J, cut=False)
    body.data.materials.clear(); body.data.materials.append(under)
    body.data.polygons.foreach_set('material_index', [0] * len(body.data.polygons))
    def hands_fn(co, R):
        f = np.full(len(co), -1.0)
        for S in 'LR': f = np.where(R.w('arm.' + S) > 0.5, (R.t(f'forearm.{S}') - 0.95) * 0.25, f)
        return f
    paint_region(body, hands_fn, glove_m, J)
    plates = []
    def plate(nm, fn, bone, offset=0.010, thick=0.006, mat=armor, smooth=2, lines=None, subdiv=1):
        ob = shell_from(C, body, fn, f'{name}_{nm}', mat, offset=offset, smooth=smooth, subdiv=subdiv, solidify=thick, bone=bone)
        if lines is not None and len(ob.data.polygons): paint_region(ob, lines, dark, J)
        if len(ob.data.polygons):
            try: ob.data.set_sharp_from_angle(angle=math.radians(48))
            except Exception: pass
            plates.append(ob)
        else: bpy.data.objects.remove(ob)
        return ob
    def torso_mask(R): return np.minimum((0.30 - R.w('arms')) * 0.2, (0.35 - R.w('headneck')) * 0.2)
    ym = J['chest'][0].y; zc0, zc1 = J['chest'][0].z, J['chest'][1].z; zs0 = J['spine'][0].z; zh = J['hips'][0].z
    shx = abs(J['upper_arm.R'][0].x)
    # chest + back
    def chest_fn(co, R):
        return np.minimum.reduce([torso_mask(R), co[:, 1] - (ym + 0.035), co[:, 2] - (zc0 + 0.03), (zc1 + 0.012) - co[:, 2] - 0.42 * np.abs(co[:, 0]), (shx - 0.022) - np.abs(co[:, 0])])
    def chest_lines(co, R):
        a = 0.0065 - np.abs(np.abs(co[:, 0]) - 0.060 - (co[:, 2] - zc0) * 0.22)           # two slanted panel lines
        b = 0.0065 - np.abs(co[:, 2] - (zc0 + 0.105) + 0.12 * np.abs(co[:, 0]))           # chevron across the sternum
        c = np.minimum(0.030 - np.abs(co[:, 0]), 0.018 - np.abs(co[:, 2] - (zc1 - 0.10)))    # centre inlay
        return np.where(co[:, 1] > ym, np.maximum.reduce([a, b, c]), -1.0)
    plate('chest', chest_fn, 'chest', offset=0.016, thick=0.010, lines=chest_lines)
    def back_fn(co, R):
        return np.minimum.reduce([torso_mask(R), (ym - 0.035) - co[:, 1], co[:, 2] - (zc0 + 0.01), (zc1 + 0.0) - co[:, 2] - 0.35 * np.abs(co[:, 0]), (shx - 0.025) - np.abs(co[:, 0])])
    def back_lines(co, R):
        a = 0.006 - np.abs(np.abs(co[:, 0]) - 0.085); b = 0.006 - np.abs(co[:, 2] - (zc0 + 0.06))
        return np.where(co[:, 1] < ym, np.maximum(a, b), -1.0)
    plate('back', back_fn, 'chest', offset=0.016, thick=0.010, lines=back_lines)
    # abdomen segments (spine) and pelvis plates (hips)
    zmid = (zs0 + zc0) / 2
    for i, (za, zb, wd) in enumerate(((zs0 + 0.005, zmid - 0.007, 0.095), (zmid + 0.007, zc0 + 0.022, 0.105))):
        plate(f'abdomen{i + 1}', lambda co, R, za=za, zb=zb, wd=wd: np.minimum.reduce([torso_mask(R), co[:, 1] - (ym + 0.03), co[:, 2] - za, zb - co[:, 2], wd - np.abs(co[:, 0])]),
              'spine', offset=0.010, thick=0.006, lines=lambda co, R: np.where(co[:, 1] > ym, 0.0035 - np.abs(co[:, 0]), -1.0))
        plate(f'lumbar{i + 1}', lambda co, R, za=za, zb=zb: np.minimum.reduce([torso_mask(R), (ym - 0.03) - co[:, 1], co[:, 2] - za, zb - co[:, 2], 0.08 - np.abs(co[:, 0])]),
              'spine', offset=0.010, thick=0.006)
    hipz = J['thigh.R'][0].z
    def pelvis_front(co, R):
        return np.minimum.reduce([(R.w('hips') - 0.45) * 0.1, co[:, 1] - (J['hips'][0].y + 0.035), (zs0 - 0.012) - co[:, 2], co[:, 2] - (hipz - 0.085), 0.075 - np.abs(co[:, 0]) + (co[:, 2] - hipz) * 0.35])
    plate('pelvis', pelvis_front, 'hips', offset=0.011, thick=0.007, lines=lambda co, R: 0.0035 - np.abs(co[:, 2] - (hipz + 0.01)))
    for S, sg in (('L', -1), ('R', 1)):
        plate(f'hip.{S}', lambda co, R, sg=sg: np.minimum.reduce([(R.w('hips') - 0.3) * 0.1, co[:, 0] * sg - 0.105, (zs0 - 0.015) - co[:, 2], co[:, 2] - (hipz - 0.07), 0.085 - np.abs(co[:, 1] - J['hips'][0].y)]),
              'hips', offset=0.012, thick=0.007)
        plate(f'glute.{S}', lambda co, R, sg=sg: np.minimum.reduce([(R.w('hips') - 0.45) * 0.1, (J['hips'][0].y - 0.045) - co[:, 1], (zs0 - 0.02) - co[:, 2], co[:, 2] - (hipz - 0.05), co[:, 0] * sg - 0.012, 0.10 - co[:, 0] * sg]),
              'hips', offset=0.011, thick=0.006)
    # limbs
    for S, sg in (('L', -1), ('R', 1)):
        out = tuple(arm_outer(C, S)); en = C['palm_n'][S]
        A_ = lambda R, S=S: R.w('arm.' + S) > 0.5
        plate(f'pauldron.{S}', lambda co, R, S=S, out=out: np.where((R.w('arm.' + S) + R.w('chest') * 0.6 > 0.5) & (co[:, 0] * (1 if S == 'R' else -1) > shx - 0.06), band(R, f'upper_arm.{S}', -0.36, 0.33, out, -0.15), -1.0),
              f'upper_arm.{S}', offset=0.020, thick=0.010, lines=lambda co, R, S=S: 0.006 - np.abs(R.along(f'upper_arm.{S}') - 0.035))
        plate(f'upper_arm_guard.{S}', lambda co, R, S=S, out=out, A_=A_: np.where(A_(R), band(R, f'upper_arm.{S}', 0.40, 0.86, out, -0.35), -1.0),
              f'upper_arm.{S}', offset=0.009, thick=0.006, lines=lambda co, R, S=S: 0.0045 - np.abs(R.t(f'upper_arm.{S}') - 0.63) * 0.28)
        plate(f'forearm_guard.{S}', lambda co, R, S=S, out=out, A_=A_: np.where(A_(R), band(R, f'forearm.{S}', 0.14, 0.92, out, -0.8), -1.0),
              f'forearm.{S}', offset=0.011, thick=0.008,
              lines=lambda co, R, S=S: np.maximum(0.004 - np.abs(R.t(f'forearm.{S}') - 0.30) * 0.26, 0.004 - np.abs(R.t(f'forearm.{S}') - 0.80) * 0.26))
        dors = tuple(-en)
        plate(f'hand_plate.{S}', lambda co, R, S=S, dors=dors: np.where(R.w(f'hand.{S}') > 0.5, band(R, f'hand.{S}', 0.08, 0.47, dors, 0.25), -1.0),
              f'hand.{S}', offset=0.004, thick=0.004, smooth=1)
        for fn_ in FINGERS:
            for seg in ((1, 2) if fn_ != 'thumb' else (2,)):
                b = f'{fn_}.0{seg}.{S}'
                plate(f'{fn_}{seg}_plate.{S}', lambda co, R, b=b, dors=dors: np.where(R.w(b) > 0.5, band(R, b, 0.14, 0.86, dors, 0.2), -1.0),
                      b, offset=0.0025, thick=0.0028, smooth=0, subdiv=0)
        fr = (sg * 0.55, 0.83, 0.0)
        plate(f'thigh_guard.{S}', lambda co, R, S=S, fr=fr: np.where(R.w('leg.' + S) > 0.5, band(R, f'thigh.{S}', 0.20, 0.86, fr, 0.05), -1.0),
              f'thigh.{S}', offset=0.013, thick=0.009,
              lines=lambda co, R, S=S: np.maximum(0.005 - np.abs(R.t(f'thigh.{S}') - 0.40) * 0.42, 0.005 - np.abs(R.t(f'thigh.{S}') - 0.72) * 0.42))
        plate(f'shin_guard.{S}', lambda co, R, S=S: np.where(R.w('leg.' + S) > 0.5, band(R, f'shin.{S}', 0.15, 0.90, (0, 1, 0), -0.82), -1.0),
              f'shin.{S}', offset=0.012, thick=0.009,
              lines=lambda co, R, S=S: np.maximum(0.005 - np.abs(R.t(f'shin.{S}') - 0.30) * 0.42, 0.005 - np.abs(R.t(f'shin.{S}') - 0.74) * 0.42))
    # harness / belt in Green Texture webbing (olive straps in the reference)
    belt = shell_from(C, body, lambda co, R: np.minimum(torso_mask(R), 0.024 - np.abs(co[:, 2] - (zs0 - 0.012))), f'{name}_belt', strap_m, offset=0.021, smooth=1, hem=0.004, subdiv=1)
    C['cloth'].append(belt)
    for S in 'LR':
        st = shell_from(C, body, lambda co, R, S=S: np.where(R.w('leg.' + S) > 0.5, 0.016 - np.abs(R.along(f'thigh.{S}') - 0.13), -1.0), f'{name}_thigh_strap.{S}', strap_m,
                        offset=0.008, smooth=1, hem=0.003, subdiv=1, bone=f'thigh.{S}')
        C['cloth'].append(st)
    C['gear'] += plates
    rerest(C)
    J, L = C['J'], C['L']
    # sole + toe cap / heel inlays on the boots, knee and elbow pads, built in the rest pose
    S_w, S_d = Shape(), Shape()
    for sd_, sg in (('L', -1), ('R', 1)):
        kn = Vector(J[f'shin.{sd_}'][0]); el = Vector(J[f'forearm.{sd_}'][0])
        K = Shape(); K.ellipsoid(kn + Vector((0, 0.047, -0.005)), (0.050, 0.026, 0.062))
        kp = solid(K, f'{name}_knee.{sd_}', col, voxel=0.005, smooth=2, mat=armor, ratio=0.5); gear(C, kp, f'shin.{sd_}')
        paint_region(kp, lambda co, R, kn=kn: 0.006 - np.abs(co[:, 2] - kn.z + 0.005), dark, J)
        K = Shape(); K.ellipsoid(el + Vector((sg * 0.006, -0.040, -0.004)), (0.034, 0.020, 0.044))
        gear(C, raw(K, f'{name}_elbow.{sd_}', col, dark), f'forearm.{sd_}')
        an, toe = Vector(J[f'foot.{sd_}'][0]), Vector(J[f'foot.{sd_}'][1])
        f = Vector((toe.x - an.x, toe.y - an.y, 0)).normalized()
        Bt = Shape()
        Bt.loft([(tuple(Vector((an.x, an.y, zc_)) + f * a_), w_, h_) for a_, w_, h_, zc_ in ((-0.088, 0.040, 0.046, 0.056), (-0.035, 0.052, 0.060, 0.066), (0.05, 0.057, 0.052, 0.056),
                                                                                   (0.14, 0.060, 0.042, 0.046), (0.205, 0.058, 0.034, 0.038), (0.255, 0.042, 0.024, 0.030))], segs=24, vhint=(0, 0, 1), sq=2.5)
        Bt.loft([((an.x, an.y - 0.006, 0.07), 0.056, 0.062), ((an.x, an.y - 0.004, an.z + 0.05), 0.054, 0.058), ((an.x, an.y, an.z + 0.115), 0.058, 0.062)], segs=24, sq=2.3)
        bt = solid(Bt, f'{name}_boot.{sd_}', col, voxel=0.005, smooth=3, mat=armor, ratio=0.35)
        paint_region(bt, lambda co, R, an=an: np.maximum.reduce([0.022 - co[:, 2], 0.007 - np.abs(co[:, 2] - (an.z + 0.045)), 0.006 - np.abs((co[:, 1] - an.y) * f.y + (co[:, 0] - an.x) * f.x - 0.165)]), dark, J)
        gear(C, bt, f'foot.{sd_}')
    # --- helmet with visor
    hw = L['head_w'] + 0.020; cy = (L['brow_y'] + L['back']) / 2; hd = (L['brow_y'] - L['back']) / 2 + 0.022
    ez, top, chin, mz = L['eye.R'].z, L['top'], L['chin'].z, L['mouth'].z
    H = Shape()
    H.loft([((0, cy + dy, z), hw * kx, hd * ky) for z, kx, ky, dy in ((chin - 0.022, 0.62, 0.70, 0.016), (chin + 0.006, 0.80, 0.86, 0.016), (mz, 0.93, 0.97, 0.010), (ez - 0.01, 1.0, 1.0, 0.004),
                                                                  (ez + 0.04, 1.0, 1.0, 0.0), (top - 0.03, 0.90, 0.93, -0.004), (top + 0.004, 0.68, 0.72, -0.008), (top + 0.02, 0.40, 0.44, -0.010), (top + 0.026, 0.12, 0.14, -0.010))], segs=40, sq=2.25)
    H.box((0, cy + hd * 0.90, mz - 0.006), (0.036, 0.034, 0.030), sq=3.0)                                   # respirator block
    for sg in (-1, 1):
        H.loft([((sg * (hw - 0.012), L['ear.R'].y, L['ear.R'].z + 0.004), 0.036, 0.036), ((sg * (hw + 0.010), L['ear.R'].y, L['ear.R'].z + 0.004), 0.034, 0.034)], segs=24, vhint=(0, 0, 1))   # ear discs
        tube(H, [Vector((sg * 0.036, cy + hd * 0.95 * math.cos(a), ez + 0.03 + (top + 0.020 - ez - 0.03) * math.sin(a))) for a in np.linspace(0.35, math.pi - 0.2, 14)], 0.008, segs=8, rv=0.011)   # crest rails
    H.loft([((0, cy + hd * 0.9, ez + 0.002), 0.070, 0.016), ((0, cy + hd * 1.02, ez + 0.002), 0.064, 0.021)], segs=28, vhint=(0, 0, 1), sq=2.6)   # visor housing
    helmet = solid(H, f'{name}_helmet', col, voxel=0.0035, smooth=4, mat=armor, ratio=0.22)
    fy = cy + hd * 0.42
    paint_region(helmet, lambda co, R: np.minimum.reduce([co[:, 1] - fy - 0.6 * np.abs(co[:, 0]) * 0, (ez + 0.034) - co[:, 2], 0.074 - np.abs(co[:, 0]) + (co[:, 1] - fy) * 0.0]), dark, J)   # face plate
    paint_region(helmet, lambda co, R: np.minimum.reduce([co[:, 1] - (cy + hd * 0.80), 0.0135 - np.abs(co[:, 2] - (ez + 0.002)), 0.058 - np.abs(co[:, 0])]), visor_m, J)   # visor
    paint_region(helmet, lambda co, R: np.minimum(0.007 - np.abs(np.abs(co[:, 0]) - 0.036), co[:, 2] - (ez + 0.045)), dark, J)                 # crest stripes
    paint_region(helmet, lambda co, R: np.minimum(np.abs(co[:, 0]) - (hw + 0.004), 0.020 - np.hypot(co[:, 1] - L['ear.R'].y, co[:, 2] - L['ear.R'].z - 0.004)), dark, J)   # ear disc centres
    gear(C, helmet, 'head')
    # neck guard (ribbed collar) and back unit
    N = Shape(); nb = Vector(J['neck'][0]); nt_ = Vector(J['neck'][1])
    rings = 7
    for i in range(rings):
        t = i / (rings - 1); c = nb.lerp(nt_, t) + Vector((0, -0.004, -0.012 + 0.03 * t)); r = 0.082 - 0.016 * t
        N.loft([(tuple(c - Vector((0, 0, 0.009))), r, r * 1.06), (tuple(c), r + 0.004, (r + 0.004) * 1.06), (tuple(c + Vector((0, 0, 0.009))), r, r * 1.06)], segs=28)
    gear(C, raw(N, f'{name}_neck_guard', col, dark), 'neck')
    bvh = surface_bvh([o for o in C['gear'] if o.name.endswith('_back')] + [body])
    zb = (J['chest'][0].z + J['chest'][1].z) / 2 + 0.01
    hit = bvh.ray_cast(Vector((0, -0.6, zb)), Vector((0, 1, 0)))[0]
    by = hit.y if hit is not None else J['chest'][0].y - 0.13
    Bk = Shape()
    Bk.box((0, by - 0.022, zb), (0.085, 0.030, 0.105), sq=3.4)
    for sg in (-1, 1): Bk.loft([((sg * 0.05, by - 0.045, zb - 0.07), 0.022, 0.022), ((sg * 0.05, by - 0.045, zb + 0.09), 0.022, 0.022), ((sg * 0.05, by - 0.045, zb + 0.105), 0.012, 0.012)], segs=16)
    pack = solid(Bk, f'{name}_backpack', col, voxel=0.004, smooth=2, mat=armor, ratio=0.3)
    paint_region(pack, lambda co, R: np.minimum(0.026 - np.abs(co[:, 0]), 0.05 - np.abs(co[:, 2] - zb)), dark, J)
    gear(C, pack, 'chest')
    # belt pouches + thigh holster
    Pp = Shape(); hz = J['spine'][0].z - 0.012
    bv2 = surface_bvh([C['cloth'][0]])
    for ang in (-62, -38, 38, 62, 150, -150):
        d = Vector((math.sin(math.radians(ang)), math.cos(math.radians(ang)), 0)); hit = bv2.ray_cast(Vector((0, J['hips'][0].y, hz)) + d * 0.6, -d)[0]
        if hit is None: continue
        b = Matrix((Vector((d.y, -d.x, 0)), d, Vector((0, 0, 1)))).transposed()
        Pp.box(hit + d * 0.016 + Vector((0, 0, -0.012)), (0.026, 0.016, 0.034), basis=b, sq=3.2)
    gear(C, raw(Pp, f'{name}_pouches', col, dark, smooth=False), 'hips')
    th = Vector(J['thigh.R'][0]).lerp(Vector(J['thigh.R'][1]), 0.36)
    Hh = Shape(); Hh.box(th + Vector((0.108, 0.0, 0)), (0.016, 0.034, 0.075), sq=3.2); Hh.box(th + Vector((0.118, -0.012, 0.085)), (0.012, 0.016, 0.03), sq=3.0)
    gear(C, raw(Hh, f'{name}_holster', col, dark, smooth=False), 'thigh.R')
    return finalize(C)

# ============================================================================= previews
def studio(size=14):
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs[0].default_value = (0.35, 0.36, 0.38, 1); bg.inputs[1].default_value = 0.6
    nt.links.new(bg.outputs[0], out.inputs[0])
    bm = bmesh.new()
    xs = np.linspace(-size, size, 3)
    prof = [(y, 0.0) for y in (size, -2.0)] + [(-2.0 - 2 * math.sin(a), 2 - 2 * math.cos(a)) for a in np.linspace(0.1, math.pi / 2, 10)] + [(-4.0, 2.0 + size)]
    rows = [[bm.verts.new((x, y, zz)) for x in xs] for (y, zz) in prof]
    for i in range(len(rows) - 1):
        for j in range(len(xs) - 1):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    me = bpy.data.meshes.new('CYC'); bm.to_mesh(me); bm.free()
    cyc = bpy.data.objects.new('STUDIO_CYC', me); sc.collection.objects.link(cyc); shade_smooth(cyc)
    cyc.data.materials.append(P.new_mat('MAT_cyc', (0.42, 0.43, 0.45, 1), 0.9))
    def area(name, loc, target, energy, size_, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size_; ld.color = color
        ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob); ob.location = loc
        tgt = P.make_empty(name + '_tgt', target)
        c = ob.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        return ob
    return cyc, [area('KEY', (4, 5, 4.5), (0, 0, 1.0), 1500, 3.0, (1.0, 0.97, 0.93)),
                 area('FILL', (-5, 5, 2.5), (0, 0, 1.0), 700, 4.0, (0.93, 0.96, 1.0)),
                 area('RIM', (-2, -4, 3.5), (0, 0, 1.2), 900, 2.0)]

def render(path, frame=1, cam=None):
    sc = bpy.context.scene; sc.render.filepath = path
    if cam is not None: sc.camera = cam
    sc.frame_set(frame)
    t = time.time(); bpy.ops.render.render(write_still=True); print(f'rendered {path} in {time.time() - t:.0f}s')

def setup_cycles(samples=32, res=(1280, 720)):
    sc = P.setup_render(res=res, samples=samples, frame_start=1, frame_end=48)
    sc.cycles.transparent_max_bounces = 16; sc.render.use_persistent_data = False
    return sc

# ============================================================================= build all / save / previews
BUILDERS = {'HERO': build_hero, 'CIVILIAN_A': build_civilian_a, 'CIVILIAN_B': build_civilian_b, 'CIVILIAN_C': build_civilian_c,
            'WORKER': build_worker, 'PASSENGER': build_passenger, 'DIVER': build_diver, 'ROBOT': build_robot}

def build_all(names=None):
    reset_scene()
    chars = {}
    for n in (names or ORDER):
        t = time.time(); chars[n] = BUILDERS[n](); print(f'[{n}] built in {time.time() - t:.0f}s, uses {chars[n]["used"]}')
    bpy.context.view_layer.update()
    return chars

def shrink_images(skin_max=2048, other_max=1024):
    """Keep the .blend small (GitHub limit): one image datablock per source file shared by all characters,
    skin maps <= 2048 px, clothes / hair / eye maps <= 1024 px, everything packed."""
    by = {}
    for im in list(bpy.data.images):
        if im.source != 'FILE' or not im.filepath: continue
        key = os.path.normpath(bpy.path.abspath(im.filepath))
        if key in by: im.user_remap(by[key])
        else: by[key] = im
    for im in list(bpy.data.images):
        if im.users == 0: bpy.data.images.remove(im)
    n = 0
    for key, im in by.items():
        if im.name not in bpy.data.images: continue
        lim = skin_max if (os.sep + 'skins' + os.sep) in key else other_max
        w, h = im.size
        if max(w, h) > lim:
            k = lim / max(w, h); im.scale(max(1, int(w * k)), max(1, int(h * k))); n += 1
        if not im.packed_file: im.pack()
    print(f'images: {len(by)} unique files, {n} downscaled')

def save_blend(chars, path=OUT_BLEND):
    for c in chars.values(): c['root'].location = (0, 0, 0)
    bpy.context.scene.frame_set(1)
    shrink_images()
    try: bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception as ex: print('orphans_purge:', ex)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.textures, bpy.data.node_groups, bpy.data.armatures):
        for d in list(blk):
            if d.users == 0: blk.remove(d)
    bpy.ops.file.pack_all()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    size = os.path.getsize(path) / 1e6
    print('saved', path, f'{size:.1f} MB')
    if size > 90: print('[warn] characters.blend is over the 90 MB budget')
    print('TRIANGLES ' + ', '.join(f'{n}={c["tris"]}' for n, c in chars.items()))

def load_chars():
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
    return {n: dict(name=n, root=bpy.data.objects[f'{n}_root'], arm=bpy.data.objects[f'RIG_{n}']) for n in ORDER if f'RIG_{n}' in bpy.data.objects}

def previews(chars):
    os.makedirs(PREV, exist_ok=True)
    shots = SHOTS or ['lineup', 'hero', 'hands', 'twohand', 'diver', 'robot', 'walk']
    names = [n for n in ORDER if n in chars]
    far = lambda: [chars[n]['root'].__setattr__('location', (60 + 3 * i, -60, 0)) for i, n in enumerate(names)]
    studio(); setup_cycles(12 if LOWS else 32)
    def solo(n, clear=True):
        far(); chars[n]['root'].location = (0, 0, 0)
        if clear and n != 'PASSENGER': A.clear_animation(chars[n]['arm'])
        return chars[n]['arm']
    if 'lineup' in shots:
        xs = np.linspace(3.85, -3.85, len(names))
        for n, x in zip(names, xs): chars[n]['root'].location = (x, 0, 0)
        if 'DIVER' in chars: A.curl_fingers(chars['DIVER']['arm'], 'R', 0.72, thumb=0.5)
        cam = P.add_camera('CAM_LINEUP', loc=(0, 11.2, 1.3), target=(0, 0, 0.93), lens=46)
        render(os.path.join(PREV, 'asset_characters_lineup.png'), 1, cam)
    if 'hero' in shots and 'HERO' in chars:
        solo('HERO')
        cam = P.add_camera('CAM_HERO_CU', loc=(0.50, 1.02, 1.66), target=(0.0, 0.04, 1.585), lens=62)
        render(os.path.join(PREV, 'asset_hero_closeup.png'), 1, cam)
    if 'hands' in shots and 'HERO' in chars:
        arm = solo('HERO'); A.make_hold_phone_pose(arm, 1); bpy.context.view_layer.update()
        hp = arm.matrix_world @ arm.pose.bones['hand.R'].head.lerp(arm.pose.bones['hand.R'].tail, 0.5)
        cam = P.add_camera('CAM_HAND', loc=(hp.x + 0.50, hp.y + 0.12, hp.z + 0.08), target=tuple(hp), lens=70)
        render(os.path.join(PREV, 'asset_hands_closeup.png'), 1, cam)
    if 'twohand' in shots and 'HERO' in chars:
        arm = solo('HERO'); A.make_two_hand_phone_pose(arm, 1)
        M = arm.matrix_world @ A.two_hand_phone_matrix(arm)
        objs = []
        for nm_, dims, off, mat in (('PHONE_STANDIN', (0.168, 0.0075, 0.079), 0.0, P.new_mat('MAT_phone_standin', shade(NIGHT, 0.8), 0.45)),
                                    ('PHONE_STANDIN_SCREEN', (0.158, 0.0006, 0.071), -0.0039, P.new_mat('MAT_phone_standin_screen', shade(DIVE, 0.6), 0.2, emission=DIVE, estrength=0.6))):
            bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); me = bpy.data.meshes.new(nm_); bm.to_mesh(me); bm.free()
            box = bpy.data.objects.new(nm_, me); bpy.context.scene.collection.objects.link(box)
            box.matrix_world = M @ Matrix.Translation((0, off, 0)) @ Matrix.Diagonal((dims[0], dims[1], dims[2], 1.0))
            me.materials.append(mat); objs.append(box)
        c = M.translation; print('TWO_HAND_PHONE matrix (rig space):', [tuple(round(v, 4) for v in r) for r in (arm.matrix_world.inverted() @ M)])
        hd = arm.matrix_world @ arm.pose.bones['head'].head
        cam = P.add_camera('CAM_2H', loc=(hd.x + 0.10, hd.y + 0.07, hd.z + 0.13), target=(c.x, c.y, c.z + 0.01), lens=42)
        render(os.path.join(PREV, 'asset_two_hand_phone_pose.png'), 1, cam)
        for o in objs: bpy.data.objects.remove(o)
    if 'walk' in shots and 'HERO' in chars:
        arm = solo('HERO'); A.make_walk_cycle(arm, 1, 48, stride_frames=24)
        cam = P.add_camera('CAM_WALK', loc=(-2.6, 3.7, 1.25), target=(0, 0, 0.93), lens=42)
        render(os.path.join(PREV, 'asset_hero_walk.png'), 7, cam)
    if 'diver' in shots and 'DIVER' in chars:
        arm = solo('DIVER'); A.curl_fingers(arm, 'R', 0.72, thumb=0.5)
        cam = P.add_camera('CAM_DIVER', loc=(1.9, 3.3, 1.35), target=(0, 0.12, 0.98), lens=37)
        render(os.path.join(PREV, 'asset_diver_check.png'), 1, cam)
    if 'robot' in shots and 'ROBOT' in chars:
        solo('ROBOT')
        cam = P.add_camera('CAM_ROBOT', loc=(1.8, 3.4, 1.4), target=(0, 0, 0.96), lens=34)
        render(os.path.join(PREV, 'asset_robot.png'), 1, cam)

if __name__ == '__main__':
    t0 = time.time()
    if PREVIEWS_ONLY:
        chars = load_chars()
    else:
        chars = build_all(ONLY)
        print(f'built all in {time.time() - t0:.0f}s')
        save_blend(chars, OUT_BLEND if not ONLY else os.path.join(os.path.dirname(OUT_BLEND), 'characters_debug.blend'))
    if not NORENDER:
        previews(chars)
    print(f'done in {time.time() - t0:.0f}s')
