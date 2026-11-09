"""After DEM correction the terrain pokes through road surfaces in places. Lift roads/paving/markings clear of the ground:
each road vertex is raised to max(own z, terrain z + 0.25 m). Applied to city_base.blend and city_future.blend."""
import bpy, os, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for blend in ('city_base.blend', 'city_future.blend'):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'blender', blend))
    ter = bpy.data.objects['CITY_TERRAIN']
    bvh = BVHTree.FromPolygons([v.co.copy() for v in ter.data.vertices], [list(p.vertices) for p in ter.data.polygons])
    for name, clear in (('CITY_ROAD', 0.25), ('CITY_PAVING', 0.2), ('CITY_RAIL', 0.25)):
        o = bpy.data.objects.get(name)
        if not o: continue
        co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        cache = {}; lifted = 0
        for i in range(len(co)):
            k = (round(co[i, 0]), round(co[i, 1]))
            gz = cache.get(k)
            if gz is None:
                hit = bvh.ray_cast(Vector((k[0], k[1], 500.0)), Vector((0, 0, -1)), 1000.0); gz = hit[0].z if hit[0] is not None else -99.0; cache[k] = gz
            if co[i, 2] < gz + clear: co[i, 2] = gz + clear; lifted += 1
        o.data.vertices.foreach_set('co', co.ravel()); o.data.update(); print(blend, name, 'lifted', lifted, 'of', len(co))
    bpy.ops.wm.save_mainfile(); print('saved', blend)
