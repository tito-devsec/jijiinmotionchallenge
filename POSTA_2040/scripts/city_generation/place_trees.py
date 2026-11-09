"""Instance the realistic tree kit (blender/assets/trees.blend) at the real tree positions of the Posta map.
Reads assets/city/original_map/Instances/Tile_X*_Y0.trees.json -> blender/city_trees.blend with collection CITY_TREES_REAL
(collection-instance empties, one per tree, scaled so the tree height matches json 'height', random Z rotation) plus the
appended TREE_* kit collections (kept under the excluded 'TREE_SOURCES' collection).

Axis verification (see verify in __main__ output): json (x, y, z) == Blender (x east, y north, z up) of CITY_TREE in city_base.blend
(median XY distance to the nearest low-poly tree vertex 3.5 mm). json 'z' is the canopy centre (terrain + ~0.74*height), so the
instance base is taken from the terrain (P.ground_z), falling back to z - 0.74*height.
Run: /opt/blender/blender -b --python place_trees.py [-- --preview]
"""
import bpy, json, os, sys, math, random, time
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
import posta_lib as P   # noqa: E402
import tree_lib as T    # noqa: E402

INST = os.path.join(ROOT, 'assets', 'city', 'original_map', 'Instances')
TILES = ['Tile_X0_Y0.trees.json', 'Tile_X1_Y0.trees.json']
OUT = os.path.join(ROOT, 'blender', 'city_trees.blend')
NOMINAL_H = T.NOMINAL_H
MIN_H = 4.0

BROADLEAF_MIX = [('BROADLEAF_A', 0.28), ('BROADLEAF_B', 0.24), ('MANGO', 0.2), ('MANGO_SPREAD', 0.14), ('UMBRELLA', 0.14)]
POPLAR_MIX = [('BROADLEAF_A', 0.6), ('CONIFER', 0.15), ('PALM', 0.25)]   # 'poplar' in OSM here is mostly tall street trees; in Dar they are palms/columnar
BUSH_MIX = [('MANGO_SPREAD', 0.5), ('BROADLEAF_B', 0.5)]

def pick(rng, mix):
    r = rng.random() * sum(w for _, w in mix)
    for name, w in mix:
        r -= w
        if r <= 0: return name
    return mix[-1][0]

def is_coastal(x, y, ground):
    return (y < 80 and x > -100) or ground < 3.5   # low ground near the harbour; ~25% of the map trees

def choose_species(rng, t, ground):
    sp = t.get('species', 'broadleaf')
    if is_coastal(t['x'], t['y'], ground) and rng.random() < 0.4:
        return 'PALM'
    if sp == 'conifer': return pick(rng, [('CONIFER', 0.15), ('MANGO', 0.3), ('BROADLEAF_A', 0.2), ('UMBRELLA', 0.15), ('PALM', 0.2)])  # OSM mis-tags most Dar trees as conifer
    if sp == 'palm': return 'PALM'
    if sp == 'poplar': return pick(rng, POPLAR_MIX)
    if sp == 'bush': return pick(rng, BUSH_MIX)
    return pick(rng, BROADLEAF_MIX)

def verify_axes():
    """Compare json positions with CITY_TREE vertices (both should be x east / y north / z up)."""
    with bpy.data.libraries.load(os.path.join(ROOT, 'blender', 'city_base.blend'), link=False) as (src, dst):
        dst.objects = ['CITY_TREE']
    o = dst.objects[0]; me = o.data
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    trees = load_trees()
    Pm = np.array([[t['x'], t['y'], t['z']] for t in trees])
    def score(Q):
        return float(np.median([np.hypot(co[:, 0] - q[0], co[:, 1] - q[1]).min() for q in Q[::25]]))
    res = {'(x,y)': score(Pm), '(x,-y)': score(Pm * [1, -1, 1]), '(-x,y)': score(Pm * [-1, 1, 1]), '(y,x)': score(Pm[:, [1, 0, 2]]), '(x,z)': score(Pm[:, [0, 2, 1]])}
    print('AXIS CHECK median XY distance json->CITY_TREE verts (m):', res)
    for t in trees[:3]:
        d = np.hypot(co[:, 0] - t['x'], co[:, 1] - t['y']); i = d.argmin()
        print('  json', (t['x'], t['y'], t['z']), 'nearest low-poly vert', tuple(round(float(v), 2) for v in co[i]), 'dxy', round(float(d[i]), 3))
    bpy.data.objects.remove(o)
    best = min(res, key=res.get)
    assert best == '(x,y)', f'unexpected axis mapping {best}'
    return res

def load_trees():
    trees = []
    for tile in TILES:
        p = os.path.join(INST, tile)
        if os.path.exists(p): trees += json.load(open(p))['trees']
    return trees

def place(seed=7):
    rng = random.Random(seed)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.unit_settings.system = 'METRIC'
    # terrain for ground heights
    P.link_city(names=('CITY_TERRAIN', 'CITY_ROAD'))
    kits = T.load_tree_kits()
    src_col = bpy.data.collections.new('TREE_SOURCES'); sc.collection.children.link(src_col)
    for name, col in kits.items():
        if col is None: raise RuntimeError(f'missing kit TREE_{name}; run scripts/assets/build_trees.py first')
        src_col.children.link(col)
    inst_col = bpy.data.collections.new('CITY_TREES_REAL'); sc.collection.children.link(inst_col)
    trees = load_trees(); counts = {}
    for i, t in enumerate(trees):
        g = P.ground_z(t['x'], t['y'], default=None)
        if g is None: g = t['z'] - 0.74 * t['height']
        # guard against json z wildly disagreeing with the terrain (bridge / data glitch): trust json then
        if abs((t['z'] - 0.74 * t['height']) - g) > 6.0: g = t['z'] - 0.74 * t['height']
        name = choose_species(rng, t, g); counts[name] = counts.get(name, 0) + 1
        h = max(float(t.get('height', 10.0)), MIN_H)
        e = bpy.data.objects.new(f'TREE_{i:04d}_{name}', None)
        e.instance_type = 'COLLECTION'; e.instance_collection = kits[name]
        e.empty_display_type = 'PLAIN_AXES'; e.empty_display_size = 0.5
        e.location = (t['x'], t['y'], g - 0.03)
        s = h / NOMINAL_H
        e.scale = (s * rng.uniform(0.92, 1.08), s * rng.uniform(0.92, 1.08), s)
        e.rotation_euler = (0, 0, rng.uniform(0, 2 * math.pi))
        e['species'] = t.get('species', ''); e['shade'] = float(t.get('shade', 0.5)); e['kit'] = name
        inst_col.objects.link(e)
    # source kits must not render by themselves
    src_col.hide_render = True
    vl = sc.view_layers[0]
    def excl(layer_col):
        for lc in layer_col.children:
            if lc.collection is src_col: lc.exclude = True
            excl(lc)
    excl(vl.layer_collection)
    # drop the city geometry again; the blend only holds trees
    for n in ('CITY_TERRAIN', 'CITY_ROAD'):
        o = bpy.data.objects.get(n)
        if o: bpy.data.objects.remove(o)
    city = bpy.data.collections.get('CITY')
    if city: bpy.data.collections.remove(city)
    bpy.ops.outliner.orphans_purge(do_recursive=True) if hasattr(bpy.ops.outliner, 'orphans_purge') else None
    for im in bpy.data.images:
        if not im.packed_file:
            try: im.pack()
            except Exception: pass
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print(f'placed {len(trees)} trees -> {OUT}; species counts {counts}')
    return counts

def preview_city(out=os.path.join(ROOT, 'previews', 'asset_trees_in_city.png'), spot=(-172, 150), samples=48):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    objs = P.link_city(); P.city_materials(objs, 'real')
    T.load_real_trees(hide_lowpoly=True)
    T.remove_lowpoly_trees()
    P.setup_world(sun_rot=(math.radians(55), 0, math.radians(-50)), sun_energy=4.0, sky=True, sky_strength=0.8, turbidity=1.5, sun_elev=50, sun_az=230)
    P.setup_render((1280, 720), samples=samples, out=out)
    T.set_tree_lod(max_bounces=16)
    x, y = spot; gz = P.ground_z(x, y)
    # look from a few metres away toward the tree-rich spot
    trees = T.trees_in_box(x - 60, x + 60, y - 60, y + 60)
    print('trees within 60 m of spot:', len(trees))
    cx, cy = x + 28, y - 34
    cz = P.ground_z(cx, cy) + 1.7
    P.add_camera('CAM_city', loc=(cx, cy, cz), target=(x, y, gz + 5.0), lens=28)
    bpy.ops.render.render(write_still=True); print('rendered', out)

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    t0 = time.time()
    verify_axes()
    place()
    print('placement done in', round(time.time() - t0, 1), 's')
    if '--preview' in argv:
        smp = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 48
        preview_city(samples=smp)
