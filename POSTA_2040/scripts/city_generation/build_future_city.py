"""Futurise Posta: every building keeps its real footprint but grows into a 2040 tower.
Per building (obj_id island): vertical scale k driven by distance to the CBD, footprint area and a seeded random;
tall towers get a tapered crown, a spire and a beacon. Roads, water, terrain are untouched. Output: blender/city_future.blend
with CITY_BUILDING replaced by the 2040 version (plus CITY_CROWNS and CITY_SPIRES meshes)."""
import bpy, os, sys, numpy as np, bmesh, math, random
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common')); import posta_lib as P
CBD = (-180.0, 230.0); R_CBD = 520.0; MAXH = 330.0
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_base.blend'))
o = bpy.data.objects['CITY_BUILDING']; me = o.data
n = len(me.vertices); co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
ids = np.empty(n, dtype=np.int32); me.attributes['obj_id'].data.foreach_get('value', ids)
rnd_all = np.empty(n); me.attributes['obj_rand'].data.foreach_get('value', rnd_all)
uniq = np.unique(ids); print('buildings', len(uniq))
crowns = []; spires = []
rng = np.random.default_rng(2040)
for b in uniq:
    m = ids == b; pts = co[m]
    zmin, zmax = pts[:, 2].min(), pts[:, 2].max(); h = zmax - zmin
    if h < 2.5: continue
    cx, cy = pts[:, 0].mean(), pts[:, 1].mean(); r = rnd_all[m][0]
    area = (pts[:, 0].max() - pts[:, 0].min()) * (pts[:, 1].max() - pts[:, 1].min())
    d = math.hypot(cx - CBD[0], cy - CBD[1]); cbd = max(0.0, 1.0 - d / R_CBD)
    k = 1.15 + 0.9 * r + cbd * (1.5 + 3.5 * r) * (1.0 if area > 150 else 0.4)
    if area > 900 and cbd > 0.3: k *= 1.3
    H = min(h * k, MAXH); k = H / h
    co[m, 2] = zmin + (pts[:, 2] - zmin) * k
    if H > 70 and area > 200:
        bx0, bx1, by0, by1 = pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()
        crowns.append((cx, cy, zmin + H, (bx1 - bx0) * 0.6, (by1 - by0) * 0.6, H * (0.08 + 0.08 * r), r))
        if r > 0.35: spires.append((cx, cy, zmin + H + H * (0.08 + 0.08 * r), H * (0.12 + 0.12 * r), r))
me.vertices.foreach_set('co', co.ravel()); me.update()
print('crowns', len(crowns), 'spires', len(spires), 'max z', co[:, 2].max().round(1))
# crowns: tapered boxes (glass), spires: thin tapered cylinders with beacon spheres
def make_mesh(name, build):
    bm = bmesh.new(); build(bm); mesh = bpy.data.meshes.new(name); bm.to_mesh(mesh); bm.free(); ob = bpy.data.objects.new(name, mesh); bpy.data.collections['CITY'].objects.link(ob); return ob
def build_crowns(bm):
    for cx, cy, z, sx, sy, hz, r in crowns:
        verts = bmesh.ops.create_cube(bm, size=1.0)['verts']
        taper = 0.55 + 0.3 * r
        for v in verts:
            s = taper if v.co.z > 0 else 1.0
            v.co = (cx + v.co.x * sx * s, cy + v.co.y * sy * s, z + (v.co.z + 0.5) * hz)
def build_spires(bm):
    for cx, cy, z, hz, r in spires:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.9 + r, radius2=0.15, depth=hz, matrix=__import__('mathutils').Matrix.Translation((cx, cy, z + hz / 2)))
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.8, matrix=__import__('mathutils').Matrix.Translation((cx, cy, z + hz + 0.5)))
cr = make_mesh('CITY_CROWNS', build_crowns); sp = make_mesh('CITY_SPIRES', build_spires)
for ob in (cr, sp):
    for p in ob.data.polygons: p.use_smooth = False
cr.data.materials.append(P.new_mat('MAT_Crown', (0.3, 0.5, 0.6, 1), 0.08, 0.9, coat=1.0))
sp.data.materials.append(P.new_mat('MAT_Spire', (0.7, 0.72, 0.75, 1), 0.3, 1.0, emission=P.PAL['turq'], estrength=1.5))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_future.blend'), compress=True); print('saved city_future.blend')
