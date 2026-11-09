"""Post-process city_base.blend: flatten terrain under water (DEM is unreliable over the harbour) and set a true sea level."""
import bpy, os, sys, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
from PIL import Image
SEA = 0.4
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_base.blend'))
splat = np.array(Image.open(os.path.join(ROOT, 'assets/city/original_map/Heightmaps/Splat_water.png')).convert('L'), dtype=np.float32) / 255.0
H, W = splat.shape
def sample(x, y):
    u = np.clip(((x + 1100.0) / 2200.0 * (W - 1)).astype(int), 0, W - 1)
    v = np.clip(((900.0 - y) / 1800.0 * (H - 1)).astype(int), 0, H - 1)
    return splat[v, u]
# soften mask

ter = bpy.data.objects['CITY_TERRAIN']; co = np.empty(len(ter.data.vertices) * 3); ter.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
w = sample(co[:, 0], co[:, 1])
# dilate water mask a little by sampling neighbours
for dx, dy in ((6, 0), (-6, 0), (0, 6), (0, -6)):
    w = np.maximum(w, sample(co[:, 0] + dx, co[:, 1] + dy) * 0.9)
co[:, 2] = np.where(w > 0.5, -1.5, np.where(w > 0.15, np.minimum(co[:, 2], 1.5), np.where(w > 0.02, np.minimum(co[:, 2], 4.0), co[:, 2])))
ter.data.vertices.foreach_set('co', co.ravel()); ter.data.update()
print('terrain verts under water:', int((w > 0.5).sum()))
wat = bpy.data.objects['CITY_WATER']; co = np.empty(len(wat.data.vertices) * 3); wat.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
co[:, 2] = SEA; wat.data.vertices.foreach_set('co', co.ravel()); wat.data.update()
# also a large ocean plane beyond the tile edge
if "OCEAN_FAR" not in bpy.data.objects:
    bpy.ops.mesh.primitive_plane_add(size=12000, location=(0, 0, SEA - 0.05)); oc = bpy.context.object; oc.name = "OCEAN_FAR"
    bpy.data.collections["CITY"].objects.link(oc); bpy.context.scene.collection.objects.unlink(oc)
bpy.ops.wm.save_mainfile(filepath=os.path.join(ROOT, 'blender', 'city_base.blend'))
print('saved')
