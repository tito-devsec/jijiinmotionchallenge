"""Build original_map.blend (untouched) and city_base.blend (classified) from the gen-map GLB tiles.
Run: blender -b --python build_city_base.py
glTF is Y-up; Blender import converts to Z-up, so Blender X = east, Y = north, Z = up (metres).
"""
import bpy, os, sys, re, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MAP = os.path.join(ROOT, 'assets', 'city', 'original_map', 'Meshes_DCC')
OUT = os.path.join(ROOT, 'blender'); os.makedirs(OUT, exist_ok=True)

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def import_tiles():
    for t in ('Tile_X0_Y0.glb', 'Tile_X1_Y0.glb'):
        bpy.ops.import_scene.gltf(filepath=os.path.join(MAP, t), merge_vertices=False)
        print('imported', t, len(bpy.data.objects))

def mat_class(obj):
    names = [m.name for m in obj.data.materials if m] if obj.type == 'MESH' else []
    s = ' '.join(names)
    if 'Building' in s: return 'BUILDING'
    if 'OSM_Road' in s or 'OSM_Marking' in s or 'OSM_Curb' in s or 'OSM_Bridge' in s or 'OSM_Tunnel' in s: return 'ROAD'
    if 'OSM_Path' in s or 'OSM_Plaza' in s or 'OSM_Parking' in s or 'OSM_Platform' in s: return 'PAVING'
    if 'OSM_Water' in s: return 'WATER'
    if 'OSM_Terrain' in s or 'OSM_Sand' in s or 'OSM_Golf' in s or 'OSM_Pitch' in s or 'OSM_Playground' in s: return 'TERRAIN'
    if 'Tree' in s: return 'TREE'
    if 'OSM_Rail' in s: return 'RAIL'
    return 'FURNITURE'

t0 = time.time()
clear(); import_tiles()
# ---- 1. save untouched original ----
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'original_map.blend'), compress=True)
print('saved original_map.blend', time.time()-t0)

# ---- 2. classify, tag and join per class ----
classes = {}
bid = 0
for o in list(bpy.data.objects):
    if o.type != 'MESH':
        continue
    c = mat_class(o)
    classes.setdefault(c, []).append(o)
    me = o.data
    a = me.attributes.new('obj_id', 'INT', 'POINT')
    if c == 'BUILDING':
        bid += 1
        val = bid
    else:
        val = 0
    a.data.foreach_set('value', [val] * len(me.vertices))
    # per-object random for staggered transformations
    r = me.attributes.new('obj_rand', 'FLOAT', 'POINT')
    import random; random.seed(hash(o.name) & 0xffff)
    r.data.foreach_set('value', [random.random()] * len(me.vertices))
print('buildings tagged:', bid)
for o in bpy.data.objects:
    if o.type == 'EMPTY':
        pass

for c, objs in classes.items():
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(objs) > 1:
        bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    j.name = f'CITY_{c}'
    j.data.name = f'CITY_{c}'
    print(c, 'tris', sum(len(p.vertices) - 2 for p in j.data.polygons), 'verts', len(j.data.vertices))

# remove leftover empties
for o in list(bpy.data.objects):
    if o.type == 'EMPTY':
        bpy.data.objects.remove(o)
# collections
col = bpy.data.collections.new('CITY'); bpy.context.scene.collection.children.link(col)
for o in list(bpy.data.objects):
    for c in o.users_collection: c.objects.unlink(o)
    col.objects.link(o)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'city_base.blend'), compress=True)
print('saved city_base.blend', time.time()-t0)
