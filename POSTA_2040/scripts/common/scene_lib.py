"""Scene-level helpers shared by scripts/scenes/*.py"""
import bpy, os, sys, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import posta_lib as P
from mathutils import Vector
import numpy as np

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
    brick.inputs['Scale'].default_value = 0.5; brick.inputs['Mortar Size'].default_value = 0.06; brick.inputs['Brick Width'].default_value = 1.6; brick.inputs['Row Height'].default_value = 1.0; brick.offset = 0.0
    brick.inputs['Color1'].default_value = (0.05, 0.08, 0.11, 1); brick.inputs['Color2'].default_value = (0.09, 0.13, 0.17, 1); brick.inputs['Mortar'].default_value = (0.55, 0.58, 0.6, 1)
    nt.links.new(tc.outputs['Object'], brick.inputs['Vector']); nt.links.new(brick.outputs['Color'], b.inputs['Base Color'])
    # windows (dark bricks) are glossy; panels rougher
    ramp = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(brick.outputs['Fac'], ramp.inputs[0])
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'MULTIPLY_ADD'; inv.inputs[1].default_value = 0.25; inv.inputs[2].default_value = 0.06
    nt.links.new(brick.outputs['Fac'], inv.inputs[0]); nt.links.new(inv.outputs[0], b.inputs['Roughness'])
    # random warm lit windows
    noise = nt.nodes.new('ShaderNodeTexWhiteNoise'); noise.noise_dimensions = '3D'
    snap = nt.nodes.new('ShaderNodeVectorMath'); snap.operation = 'SNAP'; snap.inputs[1].default_value = (2.2 / 0.35 * 0.5, 2.2 / 0.35 * 0.5, 1.0 / 0.35)
    nt.links.new(tc.outputs['Object'], snap.inputs[0]); nt.links.new(snap.outputs[0], noise.inputs['Vector'])
    gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.85
    nt.links.new(noise.outputs['Value'], gt.inputs[0])
    isw = nt.nodes.new('ShaderNodeMath'); isw.operation = 'LESS_THAN'; isw.inputs[1].default_value = 0.5; nt.links.new(brick.outputs['Fac'], isw.inputs[0])
    both = nt.nodes.new('ShaderNodeMath'); both.operation = 'MULTIPLY'; nt.links.new(gt.outputs[0], both.inputs[0]); nt.links.new(isw.outputs[0], both.inputs[1])
    es = nt.nodes.new('ShaderNodeMath'); es.operation = 'MULTIPLY'; es.inputs[1].default_value = 0.6; nt.links.new(both.outputs[0], es.inputs[0])
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
        glare.inputs['Threshold'].default_value = 1.2; glare.inputs['Strength'].default_value = 0.25
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
