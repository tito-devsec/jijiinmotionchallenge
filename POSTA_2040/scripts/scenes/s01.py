"""SCENE 01 — the city begins with construction. Ground level in Posta at golden hour: excavation, crane, workers, materials.
A worker signals, the camera rises while the buildings of the block assemble themselves floor by floor (GN_BuildUp on the
real OSM footprints), glowing orange at the construction front; existing surrounding buildings stay as they are."""
import bpy, os, sys, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA

SITE = (-150.0, 185.0)

_BVH = None
def _inside_building(x, y):
    global _BVH
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    if _BVH is None:
        verts, polys, off = [], [], 0
        for n in ('CITY_BUILDING', 'CITY_BUILD_NEW'):
            o = bpy.data.objects.get(n)
            if not o: continue
            verts += [v.co.copy() for v in o.data.vertices]; polys += [[i + off for i in p.vertices] for p in o.data.polygons]; off += len(o.data.vertices)
        _BVH = BVHTree.FromPolygons(verts, polys)
    hit = _BVH.ray_cast(Vector((x, y, 600.0)), Vector((0, 0, -1)), 1200.0)
    return hit[0] is not None and hit[0].z > P.ground_z(x, y) + 1.0

def kit(name, loc, rot=0.0, scale=1.0, push=None, clearance=4.0):
    """Instance a kit asset; if its spot (or a ring of `clearance` m around it) falls inside a building footprint,
    slide it along `push` (unit XY, toward the street) until clear."""
    x, y, _ = loc
    if push:
        for _ in range(40):
            ring = [(x, y)] + [(x + clearance * math.cos(a), y + clearance * math.sin(a)) for a in (0, 1.57, 3.14, 4.71)]
            if not any(_inside_building(a, b) for a, b in ring): break
            x += push[0]; y += push[1]
    return S.instance_collection(bpy.data.collections[name], name + '_I', loc=(x, y, P.ground_z(x, y)), rot=(0, 0, rot), scale=scale)

def kit_free(loc, push, clearance=1.0):
    x, y, _ = loc
    for _ in range(40):
        if not _inside_building(x, y): break
        x += push[0]; y += push[1]
    return (x, y, P.ground_z(x, y))

def build(scn, quality):
    global _BVH; _BVH = None
    S.fresh(); F = scn['frames']
    objs = S.load_city('real', crop=(SITE, 420), real_trees=True)
    S.terrain_urban_material()
    (rx, ry, rz), (dx, dy) = S.road_frame(*SITE)
    new = S.split_buildings(objs, (rx, ry), 120)
    new.material_slots[0].material = P.dissolving_material('MAT_NewWall', (0.66, 0.62, 0.55, 1), glow='orange', glow_strength=4.0)
    for sl in new.material_slots[1:]: sl.material = P.dissolving_material('MAT_NewRoof', (0.3, 0.28, 0.26, 1), glow='orange', glow_strength=4.0)
    ng = S.import_node_group('construction.blend', 'GN_BuildUp')
    md = new.modifiers.new('BuildUp', 'NODES'); md.node_group = ng
    ids = {s.name: s.identifier for s in ng.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT'}
    md[ids['Band']] = 2.5; md[ids['Scaffold Band']] = 6.0
    for f, v in ((1, 0.0), (int(F * 0.3), 0.0), (int(F * 0.95), 1.0), (F, 1.0)):
        md[ids['Progress']] = v; md.keyframe_insert(f'["{ids["Progress"]}"]', frame=f)
    P.clear_trees_near([(rx, ry)], 40)
    import tree_lib; tree_lib.clear_real_trees_near([(rx, ry)], 35)
    # construction kit placed around the site, aligned to the street
    with bpy.data.libraries.load(os.path.join(P.ROOT, 'blender', 'assets', 'construction.blend'), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c in ('CRANE_TOWER', 'EXCAVATOR', 'MIXER_TRUCK', 'SCAFFOLD_MODULE', 'MATERIAL_PALLET', 'BARRIER', 'CONE', 'FENCE_PANEL', 'SITE_LIGHT', 'STEEL_BEAM', 'REBAR_CAGE')]
    hold = bpy.data.collections.new('KIT_SOURCES'); bpy.context.scene.collection.children.link(hold)
    for c in dst.collections: hold.children.link(c)
    bpy.context.view_layer.layer_collection.children['KIT_SOURCES'].exclude = True
    head = math.atan2(dy, dx) - math.pi / 2; nx, ny = -dy, dx   # road-normal (site side)
    g = lambda a, b: (rx + dx * a + nx * b, ry + dy * a + ny * b, P.ground_z(rx + dx * a + nx * b, ry + dy * a + ny * b))
    out = (-nx, -ny)  # toward the street
    kit('CRANE_TOWER', g(10, 28), head, push=out, clearance=5.0); kit('EXCAVATOR', g(-6, 14), head + 0.6, push=out, clearance=5.0); kit('MIXER_TRUCK', g(18, 9), head, push=out, clearance=4.5)
    for i in range(6): kit('FENCE_PANEL', g(-14 + i * 3.6, 6.5), head)
    for i in range(5): kit('BARRIER', g(-10 + i * 2.2, 4.8), head)
    for i in range(6): kit('CONE', g(-12 + i * 2.5, 3.4), head)
    kit('MATERIAL_PALLET', g(4, 12), head, push=out, clearance=1.5); kit('MATERIAL_PALLET', g(6, 13), head + 0.3, push=out, clearance=1.5); kit('STEEL_BEAM', g(0, 16), head + 0.1, push=out, clearance=1.5)
    kit('REBAR_CAGE', g(-2, 19), head, push=out, clearance=1.5); kit('SITE_LIGHT', g(-15, 8), head + 0.8, push=out, clearance=1.5); kit('SITE_LIGHT', g(16, 7), head - 0.8, push=out, clearance=1.5)
    sc0 = kit('SCAFFOLD_MODULE', g(22, 22), head, push=out, clearance=3.0); base = sc0.location.copy()
    for i in range(3):
        for j in range(3):
            if i or j: S.instance_collection(bpy.data.collections['SCAFFOLD_MODULE'], 'SCAF', loc=(base.x + dx * 2 * i, base.y + dy * 2 * i, base.z + 2 * j), rot=(0, 0, head))
    # workers: hero worker signals; others idle / walk
    col, rig = S.add_character('WORKER', loc=g(-2, 5.5), heading=head + math.pi / 2 + 0.4)
    CA.make_idle(rig, 1, int(F * 0.22)); CA.set_rot(rig, 'upper_arm.R', rx=150, frame=int(F * 0.26)); CA.set_rot(rig, 'forearm.R', rx=20, frame=int(F * 0.26))
    CA.set_rot(rig, 'upper_arm.R', rx=0, frame=int(F * 0.4))
    random.seed(4)
    for i, (a, b) in enumerate(((8, 11), (-9, 12), (13, 16), (2, 20))):
        w = kit_free(g(a, b), out); S.instance_collection(col, f'WORKER_{i}', loc=w, rot=(0, 0, head + random.uniform(-1.5, 1.5)))
    S.world_golden(strength=0.06, sun_elev=13, sun_az=255, sun_energy=2.6)
    S.enable_mist(start=60, depth=900, color=(0.92, 0.78, 0.6, 1), strength=0.45)
    c0 = g(-30, 1.7); c0 = (c0[0], c0[1], c0[2] + 1.6); c1 = g(-12, 1.0); c1 = (c1[0], c1[1], c1[2] + 2.2)
    c2 = g(-40, -30); c2 = (c2[0], c2[1], c2[2] + 70)
    cam = P.add_camera(loc=c0, target=g(0, 10), lens=28, dof_target=12, fstop=4.0)
    t0 = g(0, 8); t1 = g(-2, 6); t2 = g(10, 40)
    S.cam_path(cam, [(1, c0), (int(F * 0.3), c1), (F, c2)], [(1, (t0[0], t0[1], t0[2] + 2)), (int(F * 0.3), (t1[0], t1[1], t1[2] + 1.6)), (F, (t2[0], t2[1], t2[2] + 15))])
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
