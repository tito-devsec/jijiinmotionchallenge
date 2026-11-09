"""Realistic tree instances for POSTA 2040 scenes.
load_real_trees(): append CITY_TREES_REAL (collection instances of the TREE_* kits) from blender/city_trees.blend.
clear_real_trees_near(points, radius): drop instances near a camera path / set piece.
Build the data with scripts/assets/build_trees.py then scripts/city_generation/place_trees.py.
"""
import bpy, os, math
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CITY_TREES_BLEND = os.path.join(ROOT, 'blender', 'city_trees.blend')
TREES_BLEND = os.path.join(ROOT, 'blender', 'assets', 'trees.blend')
SPECIES = ['BROADLEAF_A', 'BROADLEAF_B', 'MANGO', 'MANGO_SPREAD', 'UMBRELLA', 'CONIFER', 'PALM']
NOMINAL_H = 10.0

def load_tree_kits(blend=TREES_BLEND, link=False):
    """Append the TREE_<name> source collections (not linked into the scene). Returns {name: collection}."""
    missing = [n for n in SPECIES if f'TREE_{n}' not in bpy.data.collections]
    if missing:
        with bpy.data.libraries.load(blend, link=link) as (src, dst):
            dst.collections = [f'TREE_{n}' for n in missing if f'TREE_{n}' in src.collections]
    return {n: bpy.data.collections.get(f'TREE_{n}') for n in SPECIES}

def load_real_trees(hide_lowpoly=True, blend=CITY_TREES_BLEND, collection='CITY_TREES_REAL', link=False):
    """Append the placed tree instances into the current scene. Hides (or removes) the old low-poly CITY_TREE mesh."""
    col = bpy.data.collections.get(collection)
    if col is None:
        with bpy.data.libraries.load(blend, link=link) as (src, dst):
            dst.collections = [collection]
        col = dst.collections[0]
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    # make sure source kit collections are not rendered on their own
    src = bpy.data.collections.get('TREE_SOURCES')
    if src is not None and src.name in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.unlink(src)
    if hide_lowpoly:
        old = bpy.data.objects.get('CITY_TREE')
        if old is not None:
            old.hide_render = True; old.hide_viewport = True; old.hide_set(True) if old.name in bpy.context.view_layer.objects else None
    return col

def remove_lowpoly_trees():
    old = bpy.data.objects.get('CITY_TREE')
    if old is not None: bpy.data.objects.remove(old)

def tree_instances(collection='CITY_TREES_REAL'):
    col = bpy.data.collections.get(collection)
    return [o for o in col.objects if o.instance_type == 'COLLECTION'] if col else []

def clear_real_trees_near(points, radius=12.0, collection='CITY_TREES_REAL'):
    """Remove tree instances whose base is within `radius` (XY) of any of `points` (sequence of (x, y[, z]))."""
    pts = [Vector((p[0], p[1])) for p in points]
    removed = 0
    for o in tree_instances(collection):
        xy = Vector((o.matrix_world.translation.x, o.matrix_world.translation.y))
        if any((xy - p).length < radius for p in pts):
            bpy.data.objects.remove(o); removed += 1
    return removed

def trees_in_box(xmin, xmax, ymin, ymax, collection='CITY_TREES_REAL'):
    return [o for o in tree_instances(collection) if xmin <= o.location.x <= xmax and ymin <= o.location.y <= ymax]

def set_tree_lod(samples=None, max_bounces=None):
    """Cycles settings that leaf-card foliage needs: enough transparent bounces so overlapping cards do not go black."""
    sc = bpy.context.scene
    if sc.render.engine == 'CYCLES':
        sc.cycles.transparent_max_bounces = max(sc.cycles.transparent_max_bounces, max_bounces or 16)
        if samples: sc.cycles.samples = samples
