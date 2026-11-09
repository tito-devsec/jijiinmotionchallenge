"""Scene-level helpers shared by scripts/scenes/*.py"""
import bpy, os, sys, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import posta_lib as P
from mathutils import Vector
import numpy as np
from mathutils import Vector

def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def crop_city(objs, center, radius, keep=('CITY_WATER', 'CITY_TERRAIN', 'OCEAN_FAR')):
    """Delete geometry farther than radius from center (XY) on heavy class meshes to speed up street-level scenes."""
    cx, cy = center
    for n, o in objs.items():
        if n in keep or o.type != 'MESH': continue
        me = o.data; nv = len(me.vertices)
        if nv == 0: continue
        co = np.empty(nv * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        far = (np.hypot(co[:, 0] - cx, co[:, 1] - cy) > radius)
        if not far.any(): continue
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(far)[0]], context='VERTS')
        bm.to_mesh(me); bm.free(); me.update()

def load_city(style='real', crop=None, future=False, real_trees=False):
    """future=True loads the 2040 skyscraper version (same footprints and roads) from city_future.blend."""
    blend = os.path.join(P.ROOT, 'blender', 'city_future.blend' if future else 'city_base.blend')
    names = ('CITY_BUILDING', 'CITY_ROAD', 'CITY_WATER', 'CITY_TERRAIN', 'CITY_TREE', 'CITY_PAVING', 'CITY_FURNITURE', 'CITY_RAIL') + (('CITY_CROWNS', 'CITY_SPIRES') if future else ())
    objs = P.link_city(blend, names)
    if 'OCEAN_FAR' not in objs and bpy.data.objects.get('OCEAN_FAR'): objs['OCEAN_FAR'] = bpy.data.objects['OCEAN_FAR']
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n == 'OCEAN_FAR']
    for o in dst.objects:
        if o: bpy.data.collections['CITY'].objects.link(o); objs['OCEAN_FAR'] = o
    if crop: crop_city(objs, *crop)
    P.city_materials(objs, style)
    if real_trees:
        import tree_lib
        tree_lib.load_real_trees(hide_lowpoly=True); tree_lib.set_tree_lod()
        if crop:
            (cx, cy), rad = crop[0], crop[1]
            for e in list(tree_lib.tree_instances()):
                if math.hypot(e.location.x - cx, e.location.y - cy) > rad: bpy.data.objects.remove(e)
    if 'OCEAN_FAR' in objs: objs['OCEAN_FAR'].data.materials.append(bpy.data.materials['MAT_Ocean'])
    return objs

def ocean_material_upgrade(dusk=False):
    """Make MAT_Ocean a proper water surface: dark tinted glossy with procedural normal ripples."""
    m = bpy.data.materials['MAT_Ocean']; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.01, 0.06, 0.09, 1) if not dusk else (0.005, 0.02, 0.04, 1)
    b.inputs['Roughness'].default_value = 0.05; b.inputs['Metallic'].default_value = 0.0; b.inputs['Coat Weight'].default_value = 0.0
    b.inputs['Specular IOR Level'].default_value = 0.6
    tex = nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 0.06; tex.inputs['Detail'].default_value = 6; tex.inputs['Roughness'].default_value = 0.7
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.12; bump.inputs['Distance'].default_value = 0.5
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs[0], b.inputs['Normal'])

def world_dusk(strength=0.03, sun_elev=6, sun_az=262, sun_energy=1.2):
    sun = P.setup_world(sun_elev=sun_elev, sun_az=sun_az, sun_energy=sun_energy, sky_strength=strength, sun_color=(1.0, 0.75, 0.55))
    sun.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az + 180)); return sun

def world_day(strength=0.06, sun_elev=38, sun_az=250, sun_energy=3.0):
    sun = P.setup_world(sun_elev=sun_elev, sun_az=sun_az, sun_energy=sun_energy, sky_strength=strength)
    sun.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az + 180)); return sun

def world_golden(strength=0.05, sun_elev=14, sun_az=258, sun_energy=2.2):
    sun = P.setup_world(sun_elev=sun_elev, sun_az=sun_az, sun_energy=sun_energy, sky_strength=strength, sun_color=(1.0, 0.82, 0.62))
    sun.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az + 180)); return sun

def add_fog(density=0.00035, size=6000, height=400, color=(0.6, 0.7, 0.85, 1), anisotropy=0.4):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, height / 2)); c = bpy.context.object; c.name = 'FOG'
    c.scale = (size, size, height)
    m = bpy.data.materials.new('MAT_Fog'); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); v = nt.nodes.new('ShaderNodeVolumePrincipled')
    v.inputs['Density'].default_value = density; v.inputs['Color'].default_value = color; v.inputs['Anisotropy'].default_value = anisotropy
    nt.links.new(v.outputs[0], out.inputs['Volume']); c.data.materials.append(m)
    c.display_type = 'WIRE'; c.visible_shadow = False
    return c

def key_progress(md, keys, name='Progress'):
    for f, v in keys: P.key_mod(md, name, f, v)
    for fc in md.id_data.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.easing = 'EASE_IN_OUT'

def drive_flow(md, fps=24, speed=1.0):
    ident = P.mod_input_id(md, 'Flow'); md[ident] = 0.0
    fc = md.id_data.driver_add(f'modifiers["{md.name}"]["{ident}"]'); fc.driver.expression = f'frame/{fps}*{speed}'

def cam_path(cam, keys, target_keys=None, interp='BEZIER'):
    """keys: list of (frame, (x,y,z)); target_keys: list of (frame,(x,y,z)) for the look-at empty."""
    for f, loc in keys: P.key(cam, f, loc=loc, interp=interp)
    if target_keys:
        tgt = bpy.data.objects[cam['target']]
        for f, loc in target_keys: P.key(tgt, f, loc=loc, interp=interp)
    P.ease_all(cam); 
    if target_keys: P.ease_all(bpy.data.objects[cam['target']])

def frame_range(scn):
    sc = bpy.context.scene; sc.frame_start = 1; sc.frame_end = scn['frames']

def text_object(name, body, size=1.0, font=None, extrude=0.0, align='CENTER', mat=None):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size; cu.extrude = extrude; cu.align_x = align; cu.align_y = 'CENTER'
    fp = font or P.find_font([P.FONT_SANS])
    if fp: cu.font = bpy.data.fonts.load(fp)
    ob = bpy.data.objects.new(name, cu); bpy.context.scene.collection.objects.link(ob)
    if mat: ob.data.materials.append(mat)
    return ob

def link_asset(blend, collection, name=None):
    path = os.path.join(P.ROOT, 'blender', 'assets', blend)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [collection]
    col = dst.collections[0]
    if col is None: raise RuntimeError(f'{collection} not in {blend}')
    if name: col.name = name
    bpy.context.scene.collection.children.link(col)
    return col

def collection_root(col, root_name_contains='ROOT'):
    for o in col.all_objects:
        if o.type == 'EMPTY' and root_name_contains in o.name and o.parent is None: return o
    for o in col.all_objects:
        if o.parent is None: return o

def instance_collection(col, name, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    e = bpy.data.objects.new(name, None); e.instance_type = 'COLLECTION'; e.instance_collection = col
    e.location = loc; e.rotation_euler = rot; e.scale = (scale,) * 3; bpy.context.scene.collection.objects.link(e); return e

def road_lane_material():
    """2040 road: dark asphalt with pulsing turquoise guidance lines along the surface (procedural, noise-based)."""
    m = P.new_mat('MAT_Road2040', (0.03, 0.035, 0.045, 1), 0.3, 0.1); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); wave = nt.nodes.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'DIAGONAL'
    wave.inputs['Scale'].default_value = 0.12; wave.inputs['Distortion'].default_value = 0.0
    nt.links.new(tc.outputs['Object'], wave.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.96; ramp.color_ramp.elements[1].position = 0.985
    nt.links.new(wave.outputs['Fac'], ramp.inputs[0])
    b.inputs['Emission Color'].default_value = P.PAL['turq']
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.9
    nt.links.new(ramp.outputs[0], mul.inputs[0]); nt.links.new(mul.outputs[0], b.inputs['Emission Strength'])
    return m

def facade_2040_material():
    """Realistic futuristic facade: glass + metal panel pattern by object-space brick texture, warm interior lights."""
    m = P.new_mat('MAT_Wall2040', (0.08, 0.12, 0.16, 1), 0.1, 0.9, coat=0.8); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.inputs['Scale'].default_value = 1.15; brick.inputs['Mortar Size'].default_value = 0.1; brick.inputs['Brick Width'].default_value = 1.6; brick.inputs['Row Height'].default_value = 1.0; brick.offset = 0.0
    brick.inputs['Color1'].default_value = (0.05, 0.08, 0.11, 1); brick.inputs['Color2'].default_value = (0.09, 0.13, 0.17, 1); brick.inputs['Mortar'].default_value = (0.55, 0.58, 0.6, 1)
    nt.links.new(tc.outputs['Object'], brick.inputs['Vector']); nt.links.new(brick.outputs['Color'], b.inputs['Base Color'])
    # windows (dark bricks) are glossy; panels rougher
    ramp = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(brick.outputs['Fac'], ramp.inputs[0])
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'MULTIPLY_ADD'; inv.inputs[1].default_value = 0.25; inv.inputs[2].default_value = 0.06
    nt.links.new(brick.outputs['Fac'], inv.inputs[0]); nt.links.new(inv.outputs[0], b.inputs['Roughness'])
    # random warm lit windows
    noise = nt.nodes.new('ShaderNodeTexWhiteNoise'); noise.noise_dimensions = '3D'
    snap = nt.nodes.new('ShaderNodeVectorMath'); snap.operation = 'SNAP'; snap.inputs[1].default_value = (1.6 / 1.15, 1.6 / 1.15, 1.0 / 1.15)
    nt.links.new(tc.outputs['Object'], snap.inputs[0]); nt.links.new(snap.outputs[0], noise.inputs['Vector'])
    gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.94
    nt.links.new(noise.outputs['Value'], gt.inputs[0])
    isw = nt.nodes.new('ShaderNodeMath'); isw.operation = 'LESS_THAN'; isw.inputs[1].default_value = 0.5; nt.links.new(brick.outputs['Fac'], isw.inputs[0])
    both = nt.nodes.new('ShaderNodeMath'); both.operation = 'MULTIPLY'; nt.links.new(gt.outputs[0], both.inputs[0]); nt.links.new(isw.outputs[0], both.inputs[1])
    es = nt.nodes.new('ShaderNodeMath'); es.operation = 'MULTIPLY'; es.inputs[1].default_value = 0.25; nt.links.new(both.outputs[0], es.inputs[0])
    b.inputs['Emission Color'].default_value = (1.0, 0.75, 0.45, 1); nt.links.new(es.outputs[0], b.inputs['Emission Strength'])
    return m

def apply_future_materials(objs):
    wall = facade_2040_material(); roof = P.new_mat('MAT_Roof2040', (0.1, 0.12, 0.15, 1), 0.3, 0.8); road = road_lane_material()
    for i, s in enumerate(objs['CITY_BUILDING'].material_slots):
        s.material = roof if 'Roof' in (s.material.name if s.material else '') else wall
    for s in objs['CITY_ROAD'].material_slots: s.material = road
    if 'CITY_CROWNS' in objs: objs['CITY_CROWNS'].material_slots[0].material = P.new_mat('MAT_Crown', (0.3, 0.5, 0.6, 1), 0.08, 0.9, coat=1.0)

def enable_mist(start=200, depth=1500, color=(0.35, 0.5, 0.8, 1), strength=0.7):
    """Cheap atmospheric perspective: Mist pass mixed toward a haze colour in the compositor (no volumetrics)."""
    sc = bpy.context.scene; vl = sc.view_layers[0]; vl.use_pass_mist = True
    sc.world.mist_settings.start = start; sc.world.mist_settings.depth = depth; sc.world.mist_settings.falloff = 'QUADRATIC'
    sc.use_nodes = True; nt = sc.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    rl = nt.nodes.new('CompositorNodeRLayers'); comp = nt.nodes.new('CompositorNodeComposite')
    mix = nt.nodes.new('CompositorNodeMixRGB'); mix.blend_type = 'MIX'; mix.inputs[2].default_value = color
    mul = nt.nodes.new('CompositorNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = strength
    nt.links.new(rl.outputs['Mist'], mul.inputs[0]); nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs['Image'], mix.inputs[1]); nt.links.new(mix.outputs[0], comp.inputs[0])
    # glow for emissive glyphs
    glare = nt.nodes.new('CompositorNodeGlare'); glare.glare_type = 'BLOOM' if hasattr(glare, 'glare_type') else None
    try:
        glare.inputs['Threshold'].default_value = 2.0; glare.inputs['Strength'].default_value = 0.15
    except Exception:
        glare.threshold = 1.2
    nt.links.new(mix.outputs[0], glare.inputs[0]); nt.links.new(glare.outputs[0], comp.inputs[0])
    add_grade()

def terrain_urban_material():
    """Urban ground: concrete/paving mixed with grass patches by large-scale noise."""
    m = P.new_mat('MAT_Terrain', (0.3, 0.3, 0.28, 1), 0.9); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.012; n1.inputs['Detail'].default_value = 4
    nt.links.new(tc.outputs['Object'], n1.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.42; ramp.color_ramp.elements[0].color = (0.33, 0.32, 0.3, 1)
    ramp.color_ramp.elements[1].position = 0.58; ramp.color_ramp.elements[1].color = (0.07, 0.16, 0.05, 1)
    nt.links.new(n1.outputs['Fac'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    return m

def snap_to_road(x, y):
    import numpy as np
    o = bpy.data.objects['CITY_ROAD']; co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    co = co[co[:, 2] > 2.5]  # keep land roads only (piers excluded)
    i = np.hypot(co[:, 0] - x, co[:, 1] - y).argmin(); return (float(co[i, 0]), float(co[i, 1]), float(co[i, 2]))

def add_ferry(name='FERRY', start=(60, -60), end=(400, -300), F=200, z=0.4, speed_frames=None):
    """Kigamboni-style passenger ferry (procedural): white hull, blue band, two-deck superstructure, wheelhouse, funnel.
    Crosses the harbour from start to end over the scene."""
    import bmesh
    from mathutils import Vector
    bm = bmesh.new()
    # hull: lofted box with pointed bow
    L, Wd, Hh = 42.0, 11.0, 3.2
    hull = bmesh.ops.create_cube(bm, size=1.0)['verts']
    for v in hull:
        v.co = Vector((v.co.x * Wd, v.co.y * L, (v.co.z + 0.5) * Hh))
        if v.co.y > 0: v.co.x *= 0.35; v.co.y += 4.0
    deck = bmesh.ops.create_cube(bm, size=1.0)['verts']
    for v in deck: v.co = Vector((v.co.x * Wd * 0.9, v.co.y * L * 0.7 - 2, Hh + (v.co.z + 0.5) * 3.0))
    deck2 = bmesh.ops.create_cube(bm, size=1.0)['verts']
    for v in deck2: v.co = Vector((v.co.x * Wd * 0.8, v.co.y * L * 0.55 - 3, Hh + 3.0 + (v.co.z + 0.5) * 2.8))
    wh = bmesh.ops.create_cube(bm, size=1.0)['verts']
    for v in wh: v.co = Vector((v.co.x * Wd * 0.5, v.co.y * 6 + 6, Hh + 5.8 + (v.co.z + 0.5) * 2.6))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=1.0, radius2=0.8, depth=4.0, matrix=__import__('mathutils').Matrix.Translation((0, -9, Hh + 5.8 + 2.0)))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    white = P.new_mat('MAT_FerryWhite', (0.85, 0.86, 0.84, 1), 0.4); blue = P.new_mat('MAT_FerryBlue', P.PAL['blue'], 0.4)
    me.materials.append(white); me.materials.append(blue)
    for p in me.polygons:
        c = me.vertices[p.vertices[0]].co.z
        p.material_index = 1 if c < Hh * 0.6 else 0
    ang = math.atan2(end[1] - start[1], end[0] - start[0]) - math.pi / 2
    ob.rotation_euler = (0, 0, ang)
    ob.location = (start[0], start[1], z); ob.keyframe_insert('location', frame=1)
    ob.location = (end[0], end[1], z); ob.keyframe_insert('location', frame=speed_frames or F)
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    # wake: flat white translucent strip trailing the hull
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0)); wk = bpy.context.object; wk.name = name + '_WAKE'
    wk.scale = (Wd * 0.8, L * 1.6, 1); wk.location = (0, -L * 1.0, 0.05); wk.parent = ob
    wk.data.materials.append(P.new_mat('MAT_Wake', (1, 1, 1, 1), 0.6, alpha=0.35))
    return ob

def add_grade(shadows=(0.98, 1.0, 1.05), midtones=(1.0, 1.0, 1.0), highlights=(1.04, 1.01, 0.96)):
    """HOT 70 palette grade in the compositor: cool teal-blue shadows, warm highlights. Inserts a Color Balance before the Composite."""
    sc = bpy.context.scene; sc.use_nodes = True; nt = sc.node_tree
    comp = next(n for n in nt.nodes if n.type == 'COMPOSITE'); src = comp.inputs[0].links[0].from_socket if comp.inputs[0].links else None
    if src is None: return
    cb = nt.nodes.new('CompositorNodeColorBalance'); cb.correction_method = 'LIFT_GAMMA_GAIN'
    cb.lift = tuple(shadows); cb.gamma = tuple(midtones); cb.gain = tuple(highlights)
    nt.links.new(src, cb.inputs['Image']); nt.links.new(cb.outputs[0], comp.inputs[0])

# ----------------------------------------------------------------- shared helpers for character / site scenes
def split_buildings(objs, center, radius, name='CITY_BUILD_NEW'):
    """Move whole buildings (by obj_id) whose centroid lies within radius of center into a new object. Returns it."""
    import bmesh
    o = objs['CITY_BUILDING']; me = o.data; n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    ids = np.empty(n, dtype=np.int32); me.attributes['obj_id'].data.foreach_get('value', ids)
    sel_ids = set()
    for b in np.unique(ids):
        m = ids == b
        if math.hypot(co[m, 0].mean() - center[0], co[m, 1].mean() - center[1]) < radius: sel_ids.add(int(b))
    inside = np.isin(ids, list(sel_ids))
    new = o.copy(); new.data = me.copy(); new.name = name; new.data.name = name
    for c in o.users_collection: c.objects.link(new)
    for ob, drop in ((o, inside), (new, ~inside)):
        bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(drop)[0]], context='VERTS'); bm.to_mesh(ob.data); bm.free()
    objs[name] = new
    print('split buildings:', len(sel_ids), 'moved to', name)
    return new

def road_frame(x, y, r=14.0):
    """Nearest land-road point to (x,y) and the local road direction (unit XY) via PCA of nearby road vertices."""
    o = bpy.data.objects['CITY_ROAD']; co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    co = co[co[:, 2] > 1.0]
    i = np.hypot(co[:, 0] - x, co[:, 1] - y).argmin(); p = co[i]
    near = co[np.hypot(co[:, 0] - p[0], co[:, 1] - p[1]) < r][:, :2] - p[:2]
    if len(near) < 3: return (float(p[0]), float(p[1]), float(p[2])), (0.0, 1.0)
    w, v = np.linalg.eigh(near.T @ near); d = v[:, -1]
    return (float(p[0]), float(p[1]), float(p[2])), (float(d[0]), float(d[1]))

def add_character(name, loc=(0, 0, 0), heading=0.0):
    """Append a rigged character collection (HERO, WORKER, CIVILIAN_A/B/C, PASSENGER, DIVER); returns (collection, rig)."""
    col = link_asset('characters.blend', name)
    rig = bpy.data.objects.get('RIG_' + name)
    if rig is None: rig = collection_root(col)
    rig.location = loc; rig.rotation_euler = (0, 0, heading)
    return col, rig

def character_meshes(col):
    return [o for o in col.all_objects if o.type == 'MESH']

def apply_binary_character(col, progress=1.0, density=2500.0, size=0.028, seed=1.0, height_bias=0.6, band=0.18):
    """Binary system on every mesh of a rigged character (modifier runs after the Armature, so glyphs follow the motion)."""
    mods = []
    for i, m in enumerate(character_meshes(col)):
        mods.append(P.apply_binary(m, progress=progress, density=density, size=size, noise_scale=2.5, seed=seed + i, height_bias=height_bias, band=band))
    return mods

def import_node_group(blend, name):
    if name in bpy.data.node_groups: return bpy.data.node_groups[name]
    with bpy.data.libraries.load(os.path.join(P.ROOT, 'blender', 'assets', blend), link=False) as (src, dst): dst.node_groups = [name]
    return bpy.data.node_groups[name]

def screen_sequence(mat_name='MAT_PhoneScreen', seq_dir=None, first=1, count=None, offset=0, strength=3.5):
    """Feed an image sequence into the phone screen emission."""
    import glob as _g
    if seq_dir and os.environ.get('POSTA_SCREEN_DIR'): seq_dir = os.environ['POSTA_SCREEN_DIR']
    mat = bpy.data.materials.get(mat_name)
    files = sorted(_g.glob(os.path.join(seq_dir, 'f_*.png'))) if seq_dir else []
    if not mat or not files: print('screen sequence skipped', seq_dir); return False
    nt = mat.node_tree; tex = nt.nodes.get('ScreenImage'); img = bpy.data.images.load(files[0]); img.source = 'SEQUENCE'
    tex.image = img; tex.image_user.frame_duration = count or len(files); tex.image_user.frame_start = first; tex.image_user.frame_offset = offset
    tex.image_user.use_auto_refresh = True; tex.image_user.use_cyclic = True
    if offset: tex.image_user.frame_offset = offset
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'); nt.links.new(tex.outputs[0], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = strength
    return True


def binary_off_after(md, frame):
    """Stop evaluating a binary modifier once its transformation is finished (saves most of the render cost)."""
    md.show_render = True; md.keyframe_insert('show_render', frame=frame - 1)
    md.show_render = False; md.keyframe_insert('show_render', frame=frame)
    md.show_viewport = True; md.keyframe_insert('show_viewport', frame=frame - 1)
    md.show_viewport = False; md.keyframe_insert('show_viewport', frame=frame)

# ----------------------------------------------------------------- reference-driven looks (assets/references/style)
def binary_rain(center, size=600.0, top=140.0, height=140.0, columns_per_km2=900, glyph=1.4, per_column=16, speed=6.0, look_at=None, name='BINARY_RAIN'):
    """Matrix-style falling binary columns over the city (binary_building.webp). Geometry Nodes, driven by the frame."""
    glyphs = P.make_glyph_collection()
    t = bpy.data.node_groups.new('GN_BinaryRain', 'GeometryNodeTree'); it = t.interface
    it.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    it.new_socket('Time', in_out='INPUT', socket_type='NodeSocketFloat'); it.new_socket('Glyphs', in_out='INPUT', socket_type='NodeSocketCollection')
    g = P.GN(t); gi = g.n('NodeGroupInput'); go = g.n('NodeGroupOutput')
    grid = g.n('GeometryNodeMeshGrid'); grid.inputs['Size X'].default_value = size; grid.inputs['Size Y'].default_value = size
    grid.inputs['Vertices X'].default_value = 2; grid.inputs['Vertices Y'].default_value = 2
    dist = g.n('GeometryNodeDistributePointsOnFaces'); g.link(grid.outputs[0], dist.inputs['Mesh']); dist.inputs['Density'].default_value = columns_per_km2 / 1e6
    rnd = g.n('FunctionNodeRandomValue', dtype='FLOAT'); idx = g.n('GeometryNodeInputIndex'); g.link(idx.outputs[0], rnd.inputs['ID'])
    st = g.n('GeometryNodeStoreNamedAttribute', dtype='FLOAT', domain='POINT'); st.inputs['Name'].default_value = 'col'
    g.link(dist.outputs['Points'], st.inputs['Geometry']); g.link(rnd.outputs[1], st.inputs['Value'])
    line = g.n('GeometryNodeMeshLine'); line.inputs['Count'].default_value = per_column; line.inputs['Offset'].default_value = (0, 0, -glyph * 1.3)
    inst = g.n('GeometryNodeInstanceOnPoints'); g.link(st.outputs[0], inst.inputs['Points']); g.link(line.outputs[0], inst.inputs['Instance'])
    real = g.n('GeometryNodeRealizeInstances'); g.link(inst.outputs[0], real.inputs[0])
    col = g.n('GeometryNodeInputNamedAttribute', dtype='FLOAT'); col.inputs['Name'].default_value = 'col'
    pos = g.n('GeometryNodeInputPosition'); sep = g.n('ShaderNodeSeparateXYZ'); g.link(pos.outputs[0], sep.inputs[0])
    # z = top - ((top - z0) + time*speed*(0.6+col) + col*height) mod height
    sp = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(col.outputs['Attribute'], sp.inputs[0]); sp.inputs[1].default_value = speed; sp.inputs[2].default_value = speed * 0.6
    tt = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(gi.outputs['Time'], tt.inputs[0]); g.link(sp.outputs[0], tt.inputs[1])
    dz = g.n('ShaderNodeMath', op='MULTIPLY'); dz.inputs[0].default_value = -1.0; g.link(sep.outputs['Z'], dz.inputs[1])
    ch = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(col.outputs['Attribute'], ch.inputs[0]); ch.inputs[1].default_value = height
    a1 = g.n('ShaderNodeMath', op='ADD'); g.link(dz.outputs[0], a1.inputs[0]); g.link(tt.outputs[0], a1.inputs[1])
    a2 = g.n('ShaderNodeMath', op='ADD'); g.link(a1.outputs[0], a2.inputs[0]); g.link(ch.outputs[0], a2.inputs[1])
    md = g.n('ShaderNodeMath', op='FLOORED_MODULO'); g.link(a2.outputs[0], md.inputs[0]); md.inputs[1].default_value = height
    nz = g.n('ShaderNodeMath', op='SUBTRACT'); nz.inputs[0].default_value = top; g.link(md.outputs[0], nz.inputs[1])
    cmb = g.n('ShaderNodeCombineXYZ'); g.link(sep.outputs['X'], cmb.inputs[0]); g.link(sep.outputs['Y'], cmb.inputs[1]); g.link(nz.outputs[0], cmb.inputs[2])
    setp = g.n('GeometryNodeSetPosition'); g.link(real.outputs[0], setp.inputs['Geometry']); g.link(cmb.outputs[0], setp.inputs['Position'])
    m2p = g.n('GeometryNodeMeshToPoints'); g.link(setp.outputs[0], m2p.inputs['Mesh'])
    ci = g.n('GeometryNodeCollectionInfo'); ci.transform_space = 'ORIGINAL'; g.link(gi.outputs['Glyphs'], ci.inputs['Collection']); ci.inputs['Separate Children'].default_value = True; ci.inputs['Reset Children'].default_value = True
    bit = g.n('FunctionNodeRandomValue', dtype='INT'); bit.inputs[4].default_value = 0; bit.inputs[5].default_value = 1
    fl = g.n('ShaderNodeMath', op='FLOOR'); t3 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(gi.outputs['Time'], t3.inputs[0]); t3.inputs[1].default_value = 4.0; g.link(t3.outputs[0], fl.inputs[0])
    g.link(fl.outputs[0], bit.inputs['Seed'])
    ii = g.n('GeometryNodeInstanceOnPoints'); g.link(m2p.outputs[0], ii.inputs['Points']); g.link(ci.outputs[0], ii.inputs['Instance'])
    ii.inputs['Pick Instance'].default_value = True; g.link(bit.outputs[2], ii.inputs['Instance Index'])
    look = look_at or (center[0], center[1] - size, 30.0)
    vec = g.n('ShaderNodeVectorMath', op='SUBTRACT'); vec.inputs[0].default_value = look; g.link(pos.outputs[0], vec.inputs[1])
    rot = g.n('FunctionNodeAlignEulerToVector'); rot.axis = 'Z'; g.link(vec.outputs[0], rot.inputs['Vector'])
    rot2 = g.n('FunctionNodeAlignEulerToVector'); rot2.axis = 'Y'; rot2.pivot_axis = 'Z'; g.link(rot.outputs[0], rot2.inputs['Rotation']); rot2.inputs['Vector'].default_value = (0, 0, 1)
    g.link(rot2.outputs[0], ii.inputs['Rotation']); ii.inputs['Scale'].default_value = (glyph, glyph, glyph)
    g.link(ii.outputs[0], go.inputs[0])
    me = bpy.data.meshes.new(name); ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); ob.location = (center[0], center[1], 0)
    mdf = ob.modifiers.new('Rain', 'NODES'); mdf.node_group = t
    ids = {s.name: s.identifier for s in t.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT'}
    mdf[ids['Glyphs']] = glyphs; mdf[ids['Time']] = 0.0
    fc = ob.driver_add(f'modifiers["Rain"]["{ids["Time"]}"]'); fc.driver.expression = 'frame/24.0'
    return ob

def world_bluehour(sun_energy=0.25, strength=0.6):
    """Blue hour like future_city_bluehour.webp: deep blue zenith, warm orange-violet horizon glow."""
    sc = bpy.context.scene; w = sc.world or bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True; nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground'); tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -0.05; mr.inputs['From Max'].default_value = 0.6
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); el = ramp.color_ramp.elements
    H = P.HOT70   # horizon Thermo Orange glow -> Quiet Violet band -> Dive Blue -> Night Pulse zenith
    el[0].position = 0.0; el[0].color = tuple(c * 0.55 for c in H['thermo'][:3]) + (1,)
    el[1].position = 1.0; el[1].color = tuple(c * 0.6 for c in H['night'][:3]) + (1,)
    e = el.new(0.1); e.color = tuple(c * 0.35 for c in H['violet'][:3]) + (1,)
    e = el.new(0.35); e.color = tuple(c * 0.45 for c in H['dive'][:3]) + (1,)
    nt.links.new(mr.outputs['Result'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bg.inputs['Color']); bg.inputs['Strength'].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs[0])
    sun = bpy.data.objects.get('SUN')
    if sun is None:
        ld = bpy.data.lights.new('SUN', 'SUN'); sun = bpy.data.objects.new('SUN', ld); sc.collection.objects.link(sun)
    sun.data.energy = sun_energy; sun.data.color = (0.55, 0.65, 1.0); sun.rotation_euler = (math.radians(55), 0, math.radians(60))
    return sun

def apply_bluehour_city(objs):
    """Realistic 2040 city at blue hour (future_city_bluehour.webp): dark glass towers with many warm and cool lit windows,
    gold-lit crowns, glowing spires, sodium-orange street light along the real roads."""
    apply_future_materials(objs)
    w = bpy.data.materials['MAT_Wall2040']; nt = w.node_tree
    for n in nt.nodes:
        if n.type == 'MATH' and n.operation == 'GREATER_THAN' and abs(n.inputs[1].default_value - 0.94) < 1e-3: n.inputs[1].default_value = 0.84
        if n.type == 'MATH' and n.operation == 'MULTIPLY' and abs(n.inputs[1].default_value - 0.25) < 1e-3: n.inputs[1].default_value = 1.8
    b = nt.nodes['Principled BSDF']; b.inputs['Emission Color'].default_value = P.HOT70['thermo']
    crown = P.new_mat('MAT_Crown', tuple(c * 0.5 for c in P.HOT70['dive'][:3]) + (1,), 0.08, 0.9, emission=P.HOT70['thermo'], estrength=0.18, coat=1.0)
    if 'CITY_CROWNS' in objs: objs['CITY_CROWNS'].material_slots[0].material = crown
    if 'CITY_SPIRES' in objs: objs['CITY_SPIRES'].material_slots[0].material = P.new_mat('MAT_Spire', (0.8, 0.8, 0.8, 1), 0.3, 1.0, emission=P.HOT70['silver'], estrength=1.6)
    r = bpy.data.materials['MAT_Road2040']; rb = r.node_tree.nodes['Principled BSDF']; rb.inputs['Emission Color'].default_value = P.HOT70['thermo']
    for n in r.node_tree.nodes:
        if n.type == 'MATH' and n.operation == 'MULTIPLY': n.inputs[1].default_value = 0.9
        if n.type == 'VALTORGB': n.color_ramp.elements[0].position = 0.9; n.color_ramp.elements[1].position = 0.97

def add_headphones(rig, color=(0.03, 0.03, 0.035, 1), accent=None):
    """Aviation headset (helicopter_cabin_filming.webp) bone-parented to the head."""
    import bmesh
    from mathutils import Matrix
    accent = accent or P.PAL['orange']
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.05, radius2=0.05, depth=0.035, matrix=Matrix.Translation((0.085, 0, 0)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.05, radius2=0.05, depth=0.035, matrix=Matrix.Translation((-0.085, 0, 0)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    for i in range(13):
        a = math.radians(-90 + i * 15)
        bmesh.ops.create_cube(bm, size=0.02, matrix=Matrix.Translation((0.095 * math.sin(a), 0, 0.1 * math.cos(a) + 0.0)))
    me = bpy.data.meshes.new('HEADSET'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('HEADSET', me); bpy.context.scene.collection.objects.link(ob)
    me.materials.append(P.new_mat('MAT_Headset', color, 0.35, 0.2)); me.materials.append(P.new_mat('MAT_HeadsetAccent', accent, 0.4))
    for p in me.polygons:
        if abs(me.vertices[p.vertices[0]].co.x) > 0.1: p.material_index = 1
    bpy.context.view_layer.update()
    hb = rig.pose.bones['head']; ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = 'head'
    head_w = rig.matrix_world @ hb.matrix
    ob.matrix_world = Matrix.Translation(head_w @ Vector((0, hb.length * 0.45, 0)) if False else (rig.matrix_world @ (hb.head + (hb.tail - hb.head) * 0.45)))
    return ob


def cabin_passenger(seat, F):
    """The poster hero seated at the open door in a headset, phone raised in the right hand (helicopter_cabin_filming.webp).
    Returns (rig, phone). Phone is parented to the seat at the posed hand."""
    import character_anim as CA
    col = link_asset('characters.blend', 'HERO'); rig = bpy.data.objects['RIG_HERO']
    rig.parent = seat; rig.matrix_parent_inverse.identity(); rig.location = (0, -0.05, -0.5); rig.rotation_euler = (0, 0, 0)
    CA.make_seated_pose(rig, 1, seat_height=0.5); CA.make_hold_phone_pose(rig, 1); CA.set_rot(rig, 'head', rx=10, frame=1)
    CA.set_rot(rig, 'upper_arm.L', rx=55, ry=25, frame=1); CA.set_rot(rig, 'forearm.L', rx=45, frame=1)
    bpy.context.view_layer.update()
    add_headphones(rig)
    hand = rig.matrix_world @ rig.pose.bones['hand.R'].tail
    link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    phone.parent = seat; phone.matrix_parent_inverse.identity(); phone.rotation_euler = (math.radians(-90), math.radians(90), 0)
    bpy.context.view_layer.update()
    phone.location = seat.matrix_world.inverted() @ hand + Vector((0.0, 0.06, 0.04))
    # warm cabin practical so the hero reads against the blue-hour exterior
    ld = bpy.data.lights.new('CABIN_PRACTICAL', 'AREA'); ld.energy = 40; ld.size = 0.8; ld.color = (1.0, 0.82, 0.62)
    lo = bpy.data.objects.new('CABIN_PRACTICAL', ld); bpy.context.scene.collection.objects.link(lo); lo.parent = seat; lo.location = (0.0, -0.8, 1.2)
    c = lo.constraints.new('TRACK_TO'); c.target = rig; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return rig, phone

def hover_helicopter(F, loc=(260, -210, 262)):
    link_asset('helicopter.blend', 'HELICOPTER'); heli = bpy.data.objects['HELI_ROOT']
    heli.location = loc; heli.rotation_euler = (math.radians(-1), 0, math.atan2(-210 - (-700), 260 - 600) - math.pi / 2)
    for f, dz in ((1, 0), (F // 2, 0.5), (F, 0)):
        heli.location.z = loc[2] + dz; heli.keyframe_insert('location', frame=f)
    rot = bpy.data.objects['ROTOR_MAIN']; rot.rotation_euler = (0, 0, 0); rot.keyframe_insert('rotation_euler', frame=1)
    rot.rotation_euler = (0, 0, math.radians(360 * 6 * F / 24)); rot.keyframe_insert('rotation_euler', frame=F)
    for fc in rot.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    return heli, bpy.data.objects['HELI_PASSENGER_SEAT']


def holo_look(lines=1.6, glass=0.55):
    """Per-scene holographic shell intensity: line emission and glass transmission (lower = darker, less stacking glow)."""
    for m in bpy.data.materials:
        if not m.use_nodes: continue
        n = m.node_tree.nodes
        if 'HOLO_LINES' in n: n['HOLO_LINES'].inputs[1].default_value = lines
        if 'HOLO_GLASS' in n: n['HOLO_GLASS'].inputs['Color'].default_value = tuple(glass * (0.4 + 1.2 * c) for c in P.HOT70['dive'][:3]) + (1,)
