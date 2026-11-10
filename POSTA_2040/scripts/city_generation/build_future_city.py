"""Posta 2040 — the SAME buildings, renovated. Every building keeps its real OSM footprint and position; roads, water and
terrain are untouched. Renovation = added height (more in the CBD), stepped glass tiers on the tall ones that follow the
footprint shape, and slim antenna spires. Look reference: assets/references/city_2040 (dense blue night skylines, fine lit
window grids, glowing tier outlines). No invented caps or canopies.
Per-vertex attributes written for the facade shader: 'hn' (0..1 height within its tier) and 'bh' (building height, m).
Output: blender/city_future.blend"""
import bpy, os, sys, numpy as np, bmesh, math
from mathutils import Matrix
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common')); import posta_lib as P
CBD = (-180.0, 230.0); R_CBD = 520.0; MAXH = 300.0
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_base.blend'))
o = bpy.data.objects['CITY_BUILDING']; me = o.data
bm = bmesh.new(); bm.from_mesh(me)
lid = bm.verts.layers.int['obj_id']; lrnd = bm.verts.layers.float['obj_rand']
lhn = bm.verts.layers.float.new('hn'); lbh = bm.verts.layers.float.new('bh')
groups = {}
for f in bm.faces: groups.setdefault(f.verts[0][lid], []).append(f)
print('buildings', len(groups))
spires = []; tiers = 0
for b, faces in groups.items():
    verts = {v for f in faces for v in f.verts}
    zs = [v.co.z for v in verts]; zmin, zmax = min(zs), max(zs); h = zmax - zmin
    xs = [v.co.x for v in verts]; ys = [v.co.y for v in verts]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys); r = next(iter(verts))[lrnd]
    if h < 2.5:
        for v in verts: v[lhn] = 0.0; v[lbh] = h
        continue
    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    d = math.hypot(cx - CBD[0], cy - CBD[1]); cbd = max(0.0, 1.0 - d / R_CBD)
    k = 1.15 + 0.9 * r + cbd * (1.5 + 3.2 * r) * (1.0 if area > 150 else 0.4)
    if area > 900 and cbd > 0.3: k *= 1.25
    H = min(h * k, MAXH); k = H / h
    for v in verts:
        v.co.z = zmin + (v.co.z - zmin) * k; v[lhn] = (v.co.z - zmin) / H; v[lbh] = H
    top = zmin + H
    # stepped glass tiers that repeat the footprint, smaller each time (renovation add-ons, same plan shape)
    plan = []
    if H > 60 and area > 180: plan.append((0.70, 0.28))
    if H > 120 and area > 250: plan.append((0.46, 0.20))
    if H > 190: plan.append((0.26, 0.14))
    base = top
    for s, frac in plan:
        dup = bmesh.ops.duplicate(bm, geom=faces)['geom']; nv = [e for e in dup if isinstance(e, bmesh.types.BMVert)]
        th = H * frac
        for v in nv:
            t = v[lhn]
            v.co.x = cx + (v.co.x - cx) * s; v.co.y = cy + (v.co.y - cy) * s; v.co.z = base + t * th; v[lhn] = t; v[lbh] = H
        base += th; tiers += 1
    if H > 90 and r > 0.3: spires.append((cx, cy, base, H * (0.10 + 0.14 * r), 0.5 + 0.8 * r))
bm.to_mesh(me); bm.free(); me.update()
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
print('tiers', tiers, 'spires', len(spires), 'max z', co.reshape(-1, 3)[:, 2].max().round(1))
sb = bmesh.new()
for cx, cy, z, hz, rad in spires:
    bmesh.ops.create_cone(sb, cap_ends=True, segments=6, radius1=rad, radius2=0.08, depth=hz, matrix=Matrix.Translation((cx, cy, z + hz / 2)))
sm = bpy.data.meshes.new('CITY_SPIRES'); sb.to_mesh(sm); sb.free()
sp = bpy.data.objects.new('CITY_SPIRES', sm); bpy.data.collections['CITY'].objects.link(sp)
sm.materials.append(P.new_mat('MAT_Spire', P.HOT70['silver'], 0.3, 1.0, emission=P.HOT70['silver'], estrength=2.0))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_future.blend'), compress=True); print('saved city_future.blend')
