"""Procedural realistic tree kit for POSTA 2040 (Blender 4.5, headless).
Recursive branching skeletons -> bmesh skinned tubes; foliage as crossed leaf cards with
procedural alpha textures (assets/textures/, made by make_leaf_textures.py).
Output: blender/assets/trees.blend with collections TREE_<NAME>, root empty TREE_<NAME>_ROOT at trunk base,
Z up, metres, 10 m nominal height.
Run: /opt/blender/blender -b --python build_trees.py [-- --preview]
"""
import bpy, bmesh, math, os, sys, random, time
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
import posta_lib as P  # noqa: E402
import kit_lib as K    # noqa: E402

TEX = os.path.join(ROOT, 'assets', 'textures')
OUT_BLEND = os.path.join(ROOT, 'blender', 'assets', 'trees.blend')
PREVIEWS = os.path.join(ROOT, 'previews')
NOMINAL_H = 10.0
SPECIES = ['BROADLEAF_A', 'BROADLEAF_B', 'MANGO', 'MANGO_SPREAD', 'UMBRELLA', 'CONIFER', 'PALM']

# ----------------------------------------------------------------------------- materials
def img(name):
    path = os.path.join(TEX, name)
    im = bpy.data.images.get(name)
    if im is None:
        im = bpy.data.images.load(path); im.name = name
    im.alpha_mode = 'STRAIGHT'
    return im

def leaf_material(name, tex, tint=(1, 1, 1, 1), translucency=0.35, rough=0.55, hue_var=0.06):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(tex); t.interpolation = 'Linear'; t.extension = 'CLIP'
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'; nt.links.new(uv.outputs[0], t.inputs[0])
    # per-card colour variation from the 'leafrand' colour attribute (R channel) -> hue shift and brightness
    attr = nt.nodes.new('ShaderNodeVertexColor'); attr.layer_name = 'leafrand'
    hsv = nt.nodes.new('ShaderNodeHueSaturation')
    hmap = nt.nodes.new('ShaderNodeMapRange'); hmap.inputs['To Min'].default_value = 0.5 - hue_var; hmap.inputs['To Max'].default_value = 0.5 + hue_var
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(attr.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs[0], hmap.inputs[0]); nt.links.new(hmap.outputs[0], hsv.inputs['Hue'])
    vmap = nt.nodes.new('ShaderNodeMapRange'); vmap.inputs['To Min'].default_value = 0.75; vmap.inputs['To Max'].default_value = 1.25
    nt.links.new(sep.outputs[1], vmap.inputs[0]); nt.links.new(vmap.outputs[0], hsv.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0; mul.inputs[2].default_value = tint
    nt.links.new(t.outputs['Color'], mul.inputs[1]); nt.links.new(mul.outputs[0], hsv.inputs['Color'])
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
    nt.links.new(hsv.outputs[0], bsdf.inputs['Base Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); nt.links.new(hsv.outputs[0], tr.inputs['Color'])
    mix1 = nt.nodes.new('ShaderNodeMixShader'); mix1.inputs[0].default_value = translucency
    nt.links.new(bsdf.outputs[0], mix1.inputs[1]); nt.links.new(tr.outputs[0], mix1.inputs[2])
    tp = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix2 = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(t.outputs['Alpha'], mix2.inputs[0])
    nt.links.new(tp.outputs[0], mix2.inputs[1]); nt.links.new(mix1.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], out.inputs[0])
    m.surface_render_method = 'DITHERED'; m.use_backface_culling = False
    if hasattr(m, 'blend_method'): m.blend_method = 'HASHED'
    return m

def bark_material(name, tex, tint=(1, 1, 1, 1), rough=0.85, bump=0.35, scale=(1.0, 1.0)):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = rough; bsdf.inputs['Specular IOR Level'].default_value = 0.2
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale[0], scale[1], 1); nt.links.new(uv.outputs[0], mp.inputs[0])
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(tex); t.extension = 'REPEAT'; nt.links.new(mp.outputs[0], t.inputs[0])
    mul = nt.nodes.new('ShaderNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0; mul.inputs[2].default_value = tint
    nt.links.new(t.outputs['Color'], mul.inputs[1])
    # large-scale colour variation (lichen / moisture) from object-space noise
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 4
    nt.links.new(tc.outputs['Object'], nz.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[0].color = (0.55, 0.6, 0.45, 1)
    ramp.color_ramp.elements[1].position = 0.65; ramp.color_ramp.elements[1].color = (1.1, 1.05, 1.0, 1)
    nt.links.new(nz.outputs['Fac'], ramp.inputs[0])
    mul2 = nt.nodes.new('ShaderNodeMixRGB'); mul2.blend_type = 'MULTIPLY'; mul2.inputs[0].default_value = 0.8
    nt.links.new(mul.outputs[0], mul2.inputs[1]); nt.links.new(ramp.outputs[0], mul2.inputs[2])
    nt.links.new(mul2.outputs[0], bsdf.inputs['Base Color'])
    # bump: texture luminance + fine noise
    nz2 = nt.nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 40; nz2.inputs['Detail'].default_value = 6; nz2.inputs['Roughness'].default_value = 0.7
    nt.links.new(tc.outputs['Object'], nz2.inputs[0])
    add = nt.nodes.new('ShaderNodeMixRGB'); add.blend_type = 'ADD'; add.inputs[0].default_value = 0.5
    nt.links.new(t.outputs['Color'], add.inputs[1]); nt.links.new(nz2.outputs['Fac'], add.inputs[2])
    bmp = nt.nodes.new('ShaderNodeBump'); bmp.inputs['Strength'].default_value = bump; bmp.inputs['Distance'].default_value = 0.05
    nt.links.new(add.outputs[0], bmp.inputs['Height']); nt.links.new(bmp.outputs[0], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m

def fruit_material(name='MAT_TreeFruit'):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = 0.35; b.inputs['Coat Weight'].default_value = 0.3
    attr = nt.nodes.new('ShaderNodeVertexColor'); attr.layer_name = 'leafrand'
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(attr.outputs['Color'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.18, 0.38, 0.08, 1); ramp.color_ramp.elements[1].color = (0.75, 0.28, 0.08, 1)
    e = ramp.color_ramp.elements.new(0.55); e.color = (0.72, 0.52, 0.08, 1)
    nt.links.new(sep.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m

# ----------------------------------------------------------------------------- geometry helpers
class TreeMesh:
    """Accumulates bark tubes, leaf cards and fruit into separate bmeshes."""
    def __init__(self):
        self.bark = bmesh.new(); self.leaf = bmesh.new(); self.fruit = bmesh.new()
        self.uv_b = self.bark.loops.layers.uv.new('UVMap')
        self.uv_l = self.leaf.loops.layers.uv.new('UVMap'); self.col_l = self.leaf.loops.layers.color.new('leafrand')
        self.col_f = self.fruit.loops.layers.color.new('leafrand')

    # -- tube along a polyline with per-point radius; parallel-transport frames; UVs u around, v along
    def tube(self, pts, radii, seg=8, v_scale=1.0, cap=True):
        bm = self.bark; uvl = self.uv_b
        n = len(pts)
        if n < 2: return
        dirs = []
        for i in range(n):
            if i == 0: d = pts[1] - pts[0]
            elif i == n - 1: d = pts[-1] - pts[-2]
            else: d = (pts[i + 1] - pts[i - 1])
            dirs.append(d.normalized() if d.length > 1e-9 else Vector((0, 0, 1)))
        # initial frame
        d0 = dirs[0]; a = Vector((1, 0, 0)) if abs(d0.x) < 0.9 else Vector((0, 1, 0))
        nrm = (a - d0 * a.dot(d0)).normalized()
        rings = []; vlen = 0.0
        for i in range(n):
            if i > 0:
                q = dirs[i - 1].rotation_difference(dirs[i]); nrm = (q @ nrm); nrm = (nrm - dirs[i] * nrm.dot(dirs[i])).normalized()
                vlen += (pts[i] - pts[i - 1]).length
            bn = dirs[i].cross(nrm).normalized()
            ring = []
            for j in range(seg):
                a_ = 2 * math.pi * j / seg
                ring.append(bm.verts.new(pts[i] + (nrm * math.cos(a_) + bn * math.sin(a_)) * radii[i]))
            rings.append((ring, vlen))
        circ = max(2 * math.pi * radii[0], 0.05)
        for i in range(n - 1):
            r0, v0 = rings[i]; r1, v1 = rings[i + 1]
            for j in range(seg):
                j2 = (j + 1) % seg
                f = bm.faces.new((r0[j], r0[j2], r1[j2], r1[j])); f.smooth = True
                us = [j / seg, (j + 1) / seg, (j + 1) / seg, j / seg]; vs = [v0, v0, v1, v1]
                for k, loop in enumerate(f.loops):
                    loop[uvl].uv = (us[k], vs[k] * v_scale / circ)
        if cap:
            r_last, vl = rings[-1]
            tip = bm.verts.new(pts[-1] + dirs[-1] * radii[-1] * 1.5)
            for j in range(seg):
                f = bm.faces.new((r_last[j], r_last[(j + 1) % seg], tip)); f.smooth = True
                for loop in f.loops: loop[uvl].uv = (j / seg, vl * v_scale / circ)

    # -- a single quad card centred at c, with local axes (right, up), size (w, h), uv 0..1
    def card(self, c, right, up, w, h, rnd, uv=(0, 0, 1, 1), anchor=0.5):
        bm = self.leaf
        r = right * (w / 2); u0 = up * (h * anchor); u1 = up * (h * (1 - anchor))
        vs = [bm.verts.new(c - r - u0), bm.verts.new(c + r - u0), bm.verts.new(c + r + u1), bm.verts.new(c - r + u1)]
        f = bm.faces.new(vs); f.smooth = True
        us = [uv[0], uv[2], uv[2], uv[0]]; vvs = [uv[1], uv[1], uv[3], uv[3]]
        for k, loop in enumerate(f.loops):
            loop[self.uv_l].uv = (us[k], vvs[k]); loop[self.col_l] = (rnd[0], rnd[1], rnd[2], 1.0)
        return f

    def crossed_cards(self, c, size, rng, tilt=0.5, facing=None, aspect=1.0):
        """Two perpendicular quads around c. facing: preferred normal direction (outward) or None for random."""
        rnd = (rng.random(), rng.random(), rng.random())
        if facing is not None and facing.length > 1e-6:
            nrm = facing.normalized()
            # mix with random for variety
            nrm = (nrm + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * tilt).normalized()
        else:
            nrm = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-tilt, tilt))).normalized()
        a = Vector((0, 0, 1)) if abs(nrm.z) < 0.8 else Vector((1, 0, 0))
        right = nrm.cross(a).normalized(); up = right.cross(nrm).normalized()
        ang = rng.uniform(0, math.pi)
        q = Quaternion(nrm, ang); right = q @ right; up = q @ up
        self.card(c, right, up, size, size * aspect, rnd)
        q2 = Quaternion(up, math.pi / 2)
        self.card(c, q2 @ right, up, size, size * aspect, rnd)

    def sphere(self, c, r, rnd, scale=(1, 1, 1), subdiv=1):
        bm = self.fruit
        res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
        bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1)), verts=res['verts'])
        for v in res['verts']:
            for f in v.link_faces:
                f.smooth = True
                for loop in f.loops: loop[self.col_f] = (rnd, rnd, rnd, 1)

    def finish(self, name, col, root, bark_mat, leaf_mat, fruit_mat=None):
        objs = []
        for bm, suffix, mat in ((self.bark, 'bark', bark_mat), (self.leaf, 'leaves', leaf_mat), (self.fruit, 'fruit', fruit_mat)):
            if len(bm.verts) == 0: bm.free(); continue
            if suffix == 'bark':
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            me = bpy.data.meshes.new(f'{name}_{suffix}'); bm.to_mesh(me); bm.free(); me.update()
            if mat: me.materials.append(mat)
            o = bpy.data.objects.new(f'{name}_{suffix}', me); col.objects.link(o); o.parent = root
            if suffix == 'leaves': o.visible_shadow = True
            objs.append(o)
        return objs

# ----------------------------------------------------------------------------- skeleton growth
def ray_ellipsoid_scale(p, d, centre, rx, rz):
    """Largest t such that p + d*t stays inside ellipsoid (centre, rx, rx, rz).
    If p is outside, returns the far intersection (so the branch may grow into the canopy), 0 if it points away, None if no hit."""
    o = Vector(((p.x - centre.x) / rx, (p.y - centre.y) / rx, (p.z - centre.z) / rz)); dd = Vector((d.x / rx, d.y / rx, d.z / rz))
    a = dd.dot(dd); b = 2 * o.dot(dd); c = o.dot(o) - 1
    disc = b * b - 4 * a * c
    if disc < 0 or a < 1e-12: return None if c > 0 else None
    far = (-b + math.sqrt(disc)) / (2 * a)
    return max(far, 0.0)

def grow_branch(rng, base, d, length, r0, r1, segs, jitter, gravity, photo, curve=0.0, bend_axis=None):
    """Polyline from base along d for length; gravity (-droop/+lift in z per step), photo (pull toward +z), jitter random."""
    pts = [Vector(base)]; radii = [r0]; d = Vector(d).normalized()
    step = length / segs
    for i in range(segs):
        t = (i + 1) / segs
        jit = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * jitter
        d = (d + jit + Vector((0, 0, gravity)) + Vector((0, 0, 1)) * photo * (1 - d.z)).normalized()
        if bend_axis is not None and curve:
            d = (Quaternion(bend_axis, curve / segs) @ d).normalized()
        pts.append(pts[-1] + d * step); radii.append(r0 + (r1 - r0) * t)
    return pts, radii

def point_on(pts, radii, t):
    """Point, direction, radius at parametric t (0..1 along polyline, by segment index)."""
    n = len(pts) - 1; f = t * n; i = min(int(f), n - 1); u = f - i
    p = pts[i].lerp(pts[i + 1], u); d = (pts[i + 1] - pts[i]).normalized(); r = radii[i] + (radii[i + 1] - radii[i]) * u
    return p, d, r

def perp_dir(rng, d, angle, roll=None):
    """Direction at `angle` from d, rolled around d by roll (random if None)."""
    a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    n = d.cross(a).normalized()
    roll = rng.uniform(0, 2 * math.pi) if roll is None else roll
    n = Quaternion(d, roll) @ n
    return (d * math.cos(angle) + n * math.sin(angle)).normalized()

def grow_tree(tm, rng, prm):
    """Generic broadleaf generator. prm keys documented in SPECIES_PARAMS."""
    branches = []  # (pts, radii, level)
    env_c = Vector((0, 0, prm['env'][0])); env_rx, env_rz = prm['env'][1], prm['env'][2]

    def recurse(base, d, length, r0, level, roll0=0.0):
        lv = prm['levels']
        p = prm['level'][level]
        pts, radii = grow_branch(rng, base, d, length, r0, max(r0 * p['taper'], 0.012), p['segs'], p['jitter'], p['gravity'], p['photo'])
        branches.append((pts, radii, level))
        if level + 1 < lv:
            cp = prm['level'][level + 1]
            nch = max(0, int(round(rng.uniform(*p['children']))))
            roll = rng.uniform(0, 2 * math.pi)
            for k in range(nch):
                t = rng.uniform(p['child_start'], 0.97) if k > 0 else rng.uniform(0.88, 0.99)  # first child continues near the tip
                pp, pd, pr = point_on(pts, radii, t)
                ang = math.radians(rng.uniform(*p['child_angle'])) * (0.35 if k == 0 else 1.0)
                roll += math.radians(137.5) + rng.uniform(-0.4, 0.4)
                cd = perp_dir(rng, pd, ang, roll)
                cl = length * rng.uniform(*p['child_len']) * (1.0 - 0.35 * (t - p['child_start']) if k > 0 else 1.0)
                # keep inside canopy envelope
                s = ray_ellipsoid_scale(pp, cd, env_c, env_rx, env_rz)
                if s is not None:
                    if s < 0.3: continue
                    cl = min(cl, s * rng.uniform(0.8, 1.0))
                cr = min(pr * p['child_r'], r0 * 0.9)
                recurse(pp, cd, cl, cr, level + 1, roll)
        # leaves
        if level >= prm['leaf_level']:
            n_cards = max(1, int(length * prm['cards_per_m']))
            for i in range(n_cards):
                t = rng.uniform(0.25, 1.0) ** 0.7
                pp, pd, pr = point_on(pts, radii, t)
                off = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * prm['card_size'] * 0.25
                c = pp + off
                facing = Vector((c.x, c.y, (c.z - env_c.z) * env_rx / env_rz))
                tm.crossed_cards(c, prm['card_size'] * rng.uniform(0.75, 1.25), rng, tilt=prm.get('card_tilt', 0.6), facing=facing)
            # fill: cloud of cards around the tip so the canopy reads as a continuous volume
            tip = pts[-1]
            for i in range(prm.get('tip_cards', 0)):
                off = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.8, 0.6))).normalized() * rng.uniform(0.2, prm.get('tip_r', 0.7))
                c = tip + off
                if ray_ellipsoid_scale(c, Vector((0, 0, 1)), env_c, env_rx, env_rz) in (None, 0.0): continue
                facing = Vector((c.x, c.y, (c.z - env_c.z) * env_rx / env_rz))
                tm.crossed_cards(c, prm['card_size'] * rng.uniform(0.7, 1.1), rng, tilt=prm.get('card_tilt', 0.6), facing=facing)

    # trunk(s)
    for tk in prm.get('trunks', [((0, 0, 0), (0, 0, 1), 1.0)]):
        b, d, scale = tk
        recurse(Vector(b), Vector(d), prm['trunk_len'] * scale, prm['trunk_r'] * scale, 0)
    # skin
    for pts, radii, level in branches:
        seg = prm['level'][level]['ring']
        tm.tube(pts, radii, seg=seg, v_scale=prm.get('bark_v', 1.0))
    # root flare
    if prm.get('flare', True):
        for tk in prm.get('trunks', [((0, 0, 0), (0, 0, 1), 1.0)]):
            b = Vector(tk[0]); r = prm['trunk_r'] * tk[2]
            tm.tube([b - Vector((0, 0, 0.05)), b + Vector((0, 0, 0.25)), b + Vector((0, 0, 0.7))], [r * 1.55, r * 1.18, r * 0.995], seg=prm['level'][0]['ring'], cap=False)
    return branches

# ----------------------------------------------------------------------------- species parameters
def L(segs, ring, taper, jitter, gravity, photo, children, child_start, child_angle, child_len, child_r):
    return dict(segs=segs, ring=ring, taper=taper, jitter=jitter, gravity=gravity, photo=photo, children=children, child_start=child_start, child_angle=child_angle, child_len=child_len, child_r=child_r)

SPECIES_PARAMS = {
    # columnar / oval broadleaf (lineup, 2nd-4th trees): straight trunk, canopy 2.8..10 m, oval
    'BROADLEAF_A': dict(seed=101, trunk_len=4.2, trunk_r=0.2, levels=4, leaf_level=2, env=(6.6, 2.7, 3.7), cards_per_m=14, card_size=0.6, card_tilt=0.7, tip_cards=5, tip_r=0.7,
        leaf_tex='leaves_broad.png', bark_tex='bark_broad.png', bark_tint=(0.75, 0.72, 0.68, 1),
        level=[L(7, 12, 0.55, 0.05, 0.0, 0.3, (9, 12), 0.5, (35, 60), (0.75, 1.05), 0.6),
               L(5, 8, 0.4, 0.14, -0.02, 0.25, (5, 7), 0.3, (30, 55), (0.55, 0.8), 0.6),
               L(4, 5, 0.35, 0.22, -0.05, 0.12, (4, 6), 0.25, (30, 60), (0.5, 0.75), 0.55),
               L(3, 4, 0.3, 0.3, -0.08, 0.0, (0, 0), 0.3, (30, 60), (0.5, 0.7), 0.5)]),
    # rounder spreading broadleaf (lineup 1st / 5th tree): lower fork, broad crown
    'BROADLEAF_B': dict(seed=202, trunk_len=3.2, trunk_r=0.23, levels=4, leaf_level=2, env=(6.4, 3.7, 3.5), cards_per_m=13, card_size=0.65, card_tilt=0.7, tip_cards=5, tip_r=0.75,
        leaf_tex='leaves_broad2.png', bark_tex='bark_broad.png', bark_tint=(0.7, 0.68, 0.66, 1),
        level=[L(6, 12, 0.6, 0.06, 0.0, 0.2, (7, 9), 0.55, (40, 70), (0.9, 1.3), 0.6),
               L(5, 8, 0.42, 0.14, -0.03, 0.3, (5, 7), 0.3, (30, 60), (0.55, 0.85), 0.6),
               L(4, 5, 0.35, 0.22, -0.06, 0.12, (4, 6), 0.25, (30, 65), (0.5, 0.75), 0.55),
               L(3, 4, 0.3, 0.3, -0.08, 0.0, (0, 0), 0.3, (30, 60), (0.5, 0.7), 0.5)]),
    # dense round mango: short thick dark trunk, 4-6 scaffolds, very dense canopy almost to the ground
    'MANGO': dict(seed=303, trunk_len=2.2, trunk_r=0.32, levels=4, leaf_level=2, env=(6.3, 4.4, 3.9), cards_per_m=14, card_size=0.62, card_tilt=0.6, fruit=60, tip_cards=8, tip_r=0.9,
        leaf_tex='leaves_mango.png', bark_tex='bark_mango.png', bark_tint=(0.6, 0.55, 0.55, 1),
        level=[L(4, 14, 0.75, 0.05, 0.0, 0.0, (6, 7), 0.5, (35, 60), (1.6, 2.2), 0.62),
               L(5, 8, 0.45, 0.12, -0.02, 0.2, (5, 7), 0.3, (30, 60), (0.6, 0.9), 0.6),
               L(4, 5, 0.35, 0.2, -0.05, 0.1, (4, 6), 0.25, (30, 65), (0.55, 0.8), 0.55),
               L(3, 4, 0.3, 0.3, -0.1, 0.0, (0, 0), 0.3, (30, 60), (0.5, 0.7), 0.5)]),
    # spreading mango: fork at 1.3 m into 3 leaders, crown wider than tall, hanging fruit
    'MANGO_SPREAD': dict(seed=404, trunk_len=1.3, trunk_r=0.32, levels=4, leaf_level=2, env=(6.4, 5.6, 3.6), cards_per_m=14, card_size=0.62, card_tilt=0.6, fruit=90, fruit_hang=True, tip_cards=7, tip_r=0.85,
        leaf_tex='leaves_mango.png', bark_tex='bark_mango.png', bark_tint=(0.72, 0.68, 0.62, 1),
        level=[L(3, 14, 0.85, 0.03, 0.0, 0.0, (3, 3), 0.9, (30, 45), (2.4, 3.0), 0.7),
               L(6, 8, 0.4, 0.1, -0.03, 0.1, (6, 8), 0.3, (35, 65), (0.55, 0.85), 0.6),
               L(4, 5, 0.35, 0.2, -0.06, 0.1, (4, 6), 0.25, (30, 65), (0.55, 0.8), 0.55),
               L(3, 4, 0.3, 0.3, -0.1, 0.0, (0, 0), 0.3, (30, 60), (0.5, 0.7), 0.5)]),
}

# ----------------------------------------------------------------------------- special species
def build_umbrella(tm, rng):
    """Acacia-like: thick trunk, heavy outward scaffolds, each ending in a flat umbrella-shaped foliage disc."""
    branches = []
    trunk_pts, trunk_r = grow_branch(rng, (0, 0, 0), (0.03, 0.0, 1), 4.0, 0.55, 0.4, 5, 0.03, 0.0, 0.0)
    tm.tube(trunk_pts, trunk_r, seg=16, v_scale=1.0)
    tm.tube([Vector((0, 0, -0.05)), Vector((0, 0, 0.35)), Vector((0, 0, 0.9))], [0.9, 0.68, 0.56], seg=16, cap=False)
    # buttress ridges
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.2, 0.2); d = Vector((math.cos(a), math.sin(a), 0))
        tm.tube([d * 0.95 + Vector((0, 0, -0.02)), d * 0.68 + Vector((0, 0, 0.35)), d * 0.45 + Vector((0, 0, 1.0))], [0.1, 0.15, 0.11], seg=6)
    n_sc = 7; roll = rng.uniform(0, 6.28)
    tops = []
    for k in range(n_sc):
        roll += math.radians(137.5) + rng.uniform(-0.3, 0.3)
        t = rng.uniform(0.55, 1.0); pp, pd, pr = point_on(trunk_pts, trunk_r, t)
        elev = math.radians(rng.uniform(20, 45)) if k < n_sc - 1 else math.radians(75)  # last one is the central leader
        d = Vector((math.cos(roll) * math.cos(elev), math.sin(roll) * math.cos(elev), math.sin(elev)))
        length = rng.uniform(4.2, 5.8) if k < n_sc - 1 else 3.8
        pts, radii = grow_branch(rng, pp, d, length, pr * 0.55, 0.08, 6, 0.06, 0.03, 0.08)  # lifts upward at the end
        tm.tube(pts, radii, seg=8)
        # secondary scaffolds splitting from the primary
        for j in range(rng.randint(2, 3)):
            tt = rng.uniform(0.45, 0.85); qp, qd, qr = point_on(pts, radii, tt)
            cd = perp_dir(rng, qd, math.radians(rng.uniform(25, 45)))
            cd = Vector((cd.x, cd.y, abs(cd.z) * 0.6 + 0.1)).normalized()
            cpts, cr = grow_branch(rng, qp, cd, length * rng.uniform(0.35, 0.55), qr * 0.65, 0.05, 4, 0.08, 0.02, 0.1)
            tm.tube(cpts, cr, seg=6)
            tops.append((cpts[-1], 1.6))
        tops.append((pts[-1], 2.4 if k < n_sc - 1 else 2.0))
    # umbrella discs: fan of thin twigs + flattened cluster of horizontal-ish cards
    for c, R in tops:
        c = Vector(c)
        for j in range(10):
            a = 2 * math.pi * j / 10 + rng.uniform(-0.2, 0.2); d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.05, 0.15))).normalized()
            tpts, tr = grow_branch(rng, c, d, R * rng.uniform(0.6, 0.95), 0.035, 0.012, 3, 0.1, 0.0, 0.0)
            tm.tube(tpts, tr, seg=4)
        n = int(R * R * 70)
        for j in range(n):
            u = rng.random() ** 0.5; a = rng.uniform(0, 2 * math.pi)
            p = c + Vector((math.cos(a) * u * R, math.sin(a) * u * R, rng.uniform(-0.2, 0.6) * (1 - 0.5 * u) + 0.1))
            tm.crossed_cards(p, rng.uniform(0.45, 0.65), rng, tilt=0.5, facing=Vector((0, 0, 1)), aspect=0.8)
    return branches

def build_conifer(tm, rng):
    """Tall narrow spruce: straight trunk, whorls of near-horizontal branches shrinking to the top, needle-spray cards."""
    H = 10.0
    trunk_pts, trunk_r = grow_branch(rng, (0, 0, 0), (0, 0, 1), H, 0.2, 0.01, 12, 0.004, 0.0, 0.0)
    tm.tube(trunk_pts, trunk_r, seg=10, v_scale=1.0)
    tm.tube([Vector((0, 0, -0.03)), Vector((0, 0, 0.2)), Vector((0, 0, 0.5))], [0.3, 0.23, 0.2], seg=10, cap=False)
    z = 1.1; roll = 0.0
    while z < H - 0.35:
        f = (z - 1.3) / (H - 1.3)
        n = rng.randint(7, 9) if f < 0.7 else rng.randint(5, 7)
        Lb = 2.2 * (1 - f) ** 0.85 + 0.3
        for k in range(n):
            roll += 2 * math.pi / n + rng.uniform(-0.25, 0.25)
            pp, pd, pr = point_on(trunk_pts, trunk_r, z / H)
            elev = math.radians(rng.uniform(-12, 2)) if f < 0.75 else math.radians(rng.uniform(5, 25))
            d = Vector((math.cos(roll) * math.cos(elev), math.sin(roll) * math.cos(elev), math.sin(elev)))
            length = Lb * rng.uniform(0.8, 1.15)
            pts, radii = grow_branch(rng, pp, d, length, min(pr * 0.45, 0.06), 0.008, 4, 0.03, -0.03, 0.08)  # droop then tips lift
            tm.tube(pts, radii, seg=5)
            # needle cards along the branch: flat, oriented along the branch; side sprays
            ncard = max(2, int(length / 0.22))
            for i in range(ncard):
                t = (i + 0.5) / ncard
                qp, qd, qr = point_on(pts, radii, t)
                w = 0.38 + 0.3 * (1 - f) * (1 - 0.4 * t); h = w * 1.25
                rnd = (rng.random(), rng.random(), rng.random())
                side = Vector((0, 0, 1)).cross(qd).normalized()
                # main flat card lying along the branch (texture spray points along +up = qd)
                tilt = Quaternion(qd, rng.uniform(-0.3, 0.3))
                up = qd; right = tilt @ side
                drop = Vector((0, 0, -0.25))
                tm.card(qp + Vector((0, 0, 0.02)), right, (up + drop).normalized(), w, h, rnd, anchor=0.25)
                # vertical crossed card for side views
                tm.card(qp, Vector((0, 0, 1)) * 0.6 + side * 0.0, (up + drop).normalized(), w * 0.7, h, rnd, anchor=0.25) if False else None
                q2 = Quaternion((up + drop).normalized(), math.pi / 2)
                tm.card(qp, q2 @ right, (up + drop).normalized(), w * 0.75, h, rnd, anchor=0.25)
        z += 0.3 + 0.2 * f
    # leader tip spray
    tip = trunk_pts[-1]
    for i in range(3):
        rnd = (rng.random(), rng.random(), rng.random()); a = i * 2.1
        right = Vector((math.cos(a), math.sin(a), 0))
        tm.card(tip - Vector((0, 0, 0.1)), right, Vector((0, 0, 1)), 0.45, 0.7, rnd, anchor=0.5)
    return []

def build_palm(tm, rng, fronds=14, H=8.2):
    """Coconut palm: curved ringed trunk, arching fronds built from a rib and many leaflet quads, coconuts."""
    lean = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized()
    pts = []; radii = []; n = 14
    for i in range(n + 1):
        t = i / n
        p = Vector((0, 0, t * H)) + lean * (t ** 2.2) * 1.6
        pts.append(p); radii.append(0.27 - 0.1 * t)
    tm.tube(pts, radii, seg=12, v_scale=1.6)
    tm.tube([pts[0] - Vector((0, 0, 0.05)), pts[0] + Vector((0, 0, 0.3)), pts[0] + Vector((0, 0, 0.8))], [0.42, 0.33, 0.28], seg=12, cap=False)
    top = pts[-1]; axis = (pts[-1] - pts[-2]).normalized()
    crown_c = top + axis * 0.15
    # crown bulb (frond bases)
    tm.sphere(crown_c, 0.33, 0.1, scale=(1, 1, 1.2), subdiv=2)
    roll = rng.uniform(0, 6.28)
    for k in range(fronds):
        roll += 2 * math.pi / fronds * rng.uniform(0.75, 1.25)
        # age: young fronds point up, old droop
        age = k / fronds
        elev0 = math.radians(rng.uniform(55, 80) - 85 * (age ** 1.3))
        d = Vector((math.cos(roll) * math.cos(elev0), math.sin(roll) * math.cos(elev0), math.sin(elev0)))
        Lf = rng.uniform(5.0, 6.0)
        rib, rr = grow_branch(rng, crown_c, d, Lf, 0.07, 0.015, 8, 0.01, -0.16 if age < 0.85 else -0.22, 0.0)
        tm.tube(rib, rr, seg=5)
        # leaflets
        nl = 40
        for i in range(nl):
            t = 0.22 + 0.78 * (i / nl)
            qp, qd, qr = point_on(rib, rr, t)
            llen = (1.25 * math.sin(math.pi * min(1, (t - 0.15) / 0.9)) ** 0.5 + 0.2) * (1 - 0.45 * max(0, t - 0.75) / 0.25)
            for side in (-1, 1):
                sidev = qd.cross(Vector((0, 0, 1))).normalized() * side
                # leaflet dir: forward along rib, outward to the side, drooping
                ld = (qd * 0.55 + sidev * 0.8 + Vector((0, 0, -0.55 - 0.5 * t))).normalized()
                right = ld.cross(sidev).normalized()  # blade plane roughly vertical-ish (hanging)
                right = (right * 0.6 + sidev * 0.4 * side).normalized()
                rnd = (rng.random(), rng.random() * 0.5 + 0.3, 0.5)
                c = qp + ld * llen * 0.5 + sidev * 0.02
                # quad: along ld (u = 0..1 along blade), width across
                w = 0.11 + 0.04 * (1 - t)
                bm = tm.leaf
                a0 = qp + sidev * 0.02; a1 = a0 + ld * llen
                perp = ld.cross(right).normalized() * (w / 2)
                vs = [bm.verts.new(a0 - perp), bm.verts.new(a1 - perp * 0.6), bm.verts.new(a1 + perp * 0.6), bm.verts.new(a0 + perp)]
                f = bm.faces.new(vs); f.smooth = True
                uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
                for j, loop in enumerate(f.loops):
                    loop[tm.uv_l].uv = uvs[j]; loop[tm.col_l] = (rnd[0], rnd[1], rnd[2], 1)
    # a few dead hanging fronds (brown) as narrow cards hanging from the crown
    for k in range(4):
        a = rng.uniform(0, 6.28); d = Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, -1)).normalized()
        rib, rr = grow_branch(rng, crown_c - axis * 0.1, d, 2.6, 0.05, 0.01, 4, 0.02, -0.05, 0.0)
        tm.tube(rib, rr, seg=4)
        for i in range(10):
            t = 0.2 + 0.08 * i; qp, qd, qr = point_on(rib, rr, t)
            for side in (-1, 1):
                sidev = qd.cross(Vector((0, 0, 1)))
                if sidev.length < 1e-3: sidev = Vector((1, 0, 0))
                sidev = sidev.normalized() * side
                ld = (qd * 0.5 + sidev * 0.6 + Vector((0, 0, -0.3))).normalized()
                a0 = qp; a1 = a0 + ld * 0.55; perp = ld.cross(Vector((0, 0, 1))).normalized() * 0.035
                bm = tm.leaf
                vs = [bm.verts.new(a0 - perp), bm.verts.new(a1 - perp), bm.verts.new(a1 + perp), bm.verts.new(a0 + perp)]
                f = bm.faces.new(vs)
                for j, loop in enumerate(f.loops):
                    loop[tm.uv_l].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][j]; loop[tm.col_l] = (0.95, 0.05, 0.0, 1)  # dead = high R, low G -> brown via ramp
    # coconuts
    for k in range(rng.randint(7, 11)):
        a = rng.uniform(0, 6.28); r = rng.uniform(0.2, 0.42)
        c = crown_c + Vector((math.cos(a) * r, math.sin(a) * r, rng.uniform(-0.35, -0.05)))
        tm.sphere(c, 0.13, rng.uniform(0.0, 0.6), scale=(1, 1, 1.25), subdiv=1)
    return []

def add_fruit(tm, rng, branches, n, hang=False):
    tips = [(pts, radii) for pts, radii, lv in branches if lv >= 2]
    for i in range(n):
        pts, radii = tips[rng.randrange(len(tips))]
        p, d, r = point_on(pts, radii, rng.uniform(0.3, 1.0))
        drop = rng.uniform(0.25, 0.8) if hang else rng.uniform(0.08, 0.2)
        c = p + Vector((0, 0, -drop))
        if hang: tm.tube([p, c + Vector((0, 0, 0.06))], [0.012, 0.01], seg=3, cap=False)
        tm.sphere(c, 0.075, rng.random(), scale=(0.85, 0.85, 1.2), subdiv=1)

def palm_leaf_material():
    m = leaf_material('MAT_PalmLeaflet', 'palm_leaflet.png', tint=(0.5, 0.66, 0.38, 1), translucency=0.3, rough=0.4, hue_var=0.04)
    # dead fronds: leafrand R ~0.95 & G ~0.05 -> brown. Patch the hue node: use G channel as saturation driver
    nt = m.node_tree
    hsv = next(n for n in nt.nodes if n.type == 'HUE_SAT'); sep = next(n for n in nt.nodes if n.type == 'SEPARATE_COLOR')
    smap = nt.nodes.new('ShaderNodeMapRange'); smap.inputs['From Min'].default_value = 0.0; smap.inputs['From Max'].default_value = 0.3
    smap.inputs['To Min'].default_value = 0.15; smap.inputs['To Max'].default_value = 1.0
    nt.links.new(sep.outputs[1], smap.inputs[0]); nt.links.new(smap.outputs[0], hsv.inputs['Saturation'])
    # brown tint for dead: mix base colour with brown by (1 - G*3 clamp)
    return m

def coconut_material():
    m = fruit_material('MAT_Coconut')
    ramp = next(n for n in m.node_tree.nodes if n.type == 'VALTORGB').color_ramp
    ramp.elements[0].color = (0.25, 0.3, 0.1, 1); ramp.elements[1].color = (0.32, 0.2, 0.08, 1); ramp.elements[2].color = (0.42, 0.36, 0.12, 1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.6
    return m

# ----------------------------------------------------------------------------- build
def build_species(name, col):
    rng = random.Random(1000 + SPECIES.index(name))
    root = bpy.data.objects.new(f'TREE_{name}_ROOT', None); root.empty_display_type = 'PLAIN_AXES'; root.empty_display_size = 1.0; col.objects.link(root)
    tm = TreeMesh()
    fruit_mat = None
    if name in SPECIES_PARAMS:
        prm = SPECIES_PARAMS[name]; rng = random.Random(prm['seed'])
        if name == 'MANGO_SPREAD':
            # fork: three leaders from a short trunk
            prm = dict(prm); prm['trunks'] = [((0, 0, 0), (0, 0, 1), 1.0)]
        branches = grow_tree(tm, rng, prm)
        if prm.get('fruit'):
            add_fruit(tm, rng, branches, prm['fruit'], hang=prm.get('fruit_hang', False)); fruit_mat = fruit_material()
        bark = bark_material(f'MAT_Bark_{name}', prm['bark_tex'], tint=prm.get('bark_tint', (1, 1, 1, 1)))
        leaf = leaf_material(f'MAT_Leaf_{name}', prm['leaf_tex'], tint=(0.62, 0.72, 0.5, 1), translucency=0.3)
    elif name == 'UMBRELLA':
        rng = random.Random(505); build_umbrella(tm, rng)
        bark = bark_material('MAT_Bark_UMBRELLA', 'bark_broad.png', tint=(0.62, 0.55, 0.48, 1), bump=0.6, scale=(2.0, 1.0))
        leaf = leaf_material('MAT_Leaf_UMBRELLA', 'leaves_umbrella.png', tint=(0.6, 0.7, 0.5, 1), translucency=0.3)
    elif name == 'CONIFER':
        rng = random.Random(606); build_conifer(tm, rng)
        bark = bark_material('MAT_Bark_CONIFER', 'bark_conifer.png', tint=(0.7, 0.62, 0.58, 1))
        leaf = leaf_material('MAT_Needles', 'needles_conifer.png', tint=(0.45, 0.6, 0.5, 1), translucency=0.15, rough=0.65, hue_var=0.03)
    elif name == 'PALM':
        rng = random.Random(707); build_palm(tm, rng)
        bark = bark_material('MAT_Bark_PALM', 'bark_palm.png', tint=(0.8, 0.76, 0.66, 1), bump=0.5, scale=(1.0, 1.0))
        leaf = palm_leaf_material(); fruit_mat = coconut_material()
    objs = tm.finish(f'TREE_{name}', col, root, bark, leaf, fruit_mat)
    zmax = max(v.co.z for o in objs for v in o.data.vertices)
    k = NOMINAL_H / zmax
    for o in objs:
        for v in o.data.vertices: v.co *= k
        for p in o.data.polygons: p.use_smooth = True
        o.data.update()
    return root, objs

def build_all():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.unit_settings.system = 'METRIC'
    report = {}
    for name in SPECIES:
        t0 = time.time()
        col = K.coll(f'TREE_{name}')
        root, objs = build_species(name, col)
        tris = K.collection_tris(col)
        zmax = max((root.matrix_world @ Vector(v)).z for o in objs for v in o.bound_box)
        report[name] = (tris, zmax)
        print(f'{name}: {tris} tris, height {zmax:.2f} m, {time.time() - t0:.1f}s')
    # pack images so the .blend is self-contained
    for im in bpy.data.images:
        try: im.pack()
        except Exception as e: print('pack fail', im.name, e)
    os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print('saved', OUT_BLEND)
    return report

# ----------------------------------------------------------------------------- previews
def preview_lineup(out=os.path.join(PREVIEWS, 'asset_trees_lineup.png'), samples=48):
    sc = bpy.context.scene
    ground = K.ground('GROUND', 4000, P.new_mat('MAT_PreviewGround', (0.55, 0.55, 0.54, 1), 0.9), z=0)
    spacing = 10.5; n = len(SPECIES)
    for i, name in enumerate(SPECIES):
        col = bpy.data.collections[f'TREE_{name}']
        for o in col.objects:
            if o.parent is None: o.location = ((i - (n - 1) / 2) * spacing, 0, 0)
    P.setup_world(sun_rot=(math.radians(52), 0, math.radians(-35)), sun_energy=3.5, sky=True, sky_strength=0.7, turbidity=1.2, sun_elev=48, sun_az=215)
    P.setup_render((1280, 720), samples=samples, out=out)
    sc.cycles.transparent_max_bounces = 16
    P.add_camera('CAM_lineup', loc=(4, -80, 8.5), target=(0, 0, 5.4), lens=35)
    bpy.ops.render.render(write_still=True); print('rendered', out)

def preview_closeup(out=os.path.join(PREVIEWS, 'asset_tree_mango_closeup.png'), samples=48):
    sc = bpy.context.scene
    for i, name in enumerate(SPECIES):
        for o in bpy.data.collections[f'TREE_{name}'].objects:
            if o.parent is None: o.hide_render = name != 'MANGO'
            for c in o.children_recursive: c.hide_render = name != 'MANGO'
    root = bpy.data.objects['TREE_MANGO_ROOT']
    P.setup_world(sun_rot=(math.radians(55), 0, math.radians(-60)), sun_energy=3.5, sky=True, sky_strength=0.7, sun_elev=45, sun_az=200)
    P.setup_render((1280, 720), samples=samples, out=out)
    sc.cycles.transparent_max_bounces = 16
    x = root.location.x
    P.add_camera('CAM_close', loc=(x + 9, -21, 2.2), target=(x, 0, 5.0), lens=40, dof_target=23, fstop=5.6)
    bpy.ops.render.render(write_still=True); print('rendered', out)

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    rep = build_all()
    smp = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 48
    if '--lineup' in argv or '--preview' in argv: preview_lineup(samples=smp)
    if '--closeup' in argv or '--preview' in argv:
        if '--lineup' in argv or '--preview' in argv:
            bpy.data.objects.remove(bpy.data.objects['CAM_lineup'])
        preview_closeup(samples=smp)
    print('REPORT', rep)
