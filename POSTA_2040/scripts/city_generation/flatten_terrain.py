"""The Terrarium DEM over dense Posta is inflated by buildings (Kivukoni reads ~15 m, reality ~4 m).
Subtract a fraction of local terrain height from every vertex of every class mesh so bases follow a flatter ground while
building heights are preserved. Also clamps the coastal band."""
import bpy, os, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FRAC = 0.6; SEA = 0.4
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_base.blend'))
ter = bpy.data.objects['CITY_TERRAIN']; me = ter.data
verts = [v.co.copy() for v in me.vertices]; polys = [list(p.vertices) for p in me.polygons]
bvh = BVHTree.FromPolygons(verts, polys)
def h(x, y):
    hit = bvh.ray_cast(Vector((x, y, 500)), Vector((0, 0, -1)), 1000)
    return hit[0].z if hit[0] is not None else 0.0
names = ['CITY_TERRAIN', 'CITY_BUILDING', 'CITY_ROAD', 'CITY_PAVING', 'CITY_FURNITURE', 'CITY_TREE', 'CITY_RAIL']
cache = {}
for n in names:
    o = bpy.data.objects.get(n)
    if not o: continue
    co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    # sample ground on a 2 m grid cache to keep it fast
    keys = np.round(co[:, :2] / 2.0).astype(int)
    hz = np.empty(len(co))
    for i, (kx, ky) in enumerate(map(tuple, keys)):
        v = cache.get((kx, ky))
        if v is None: v = h(kx * 2.0, ky * 2.0); cache[(kx, ky)] = v
        hz[i] = v
    hz = np.maximum(hz, 0.0)
    co[:, 2] -= FRAC * hz
    o.data.vertices.foreach_set('co', co.ravel()); o.data.update()
    print(n, 'lowered; z range now', co[:, 2].min().round(1), co[:, 2].max().round(1))
bpy.data.objects['CITY_WATER'].location.z = 0
bpy.ops.wm.save_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_base.blend')); print('saved')
