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

def load_city(style='real', crop=None):
    objs = P.link_city()
    if 'OCEAN_FAR' not in objs and bpy.data.objects.get('OCEAN_FAR'): objs['OCEAN_FAR'] = bpy.data.objects['OCEAN_FAR']
    with bpy.data.libraries.load(os.path.join(P.ROOT, 'blender', 'city_base.blend'), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n == 'OCEAN_FAR']
    for o in dst.objects:
        if o: bpy.data.collections['CITY'].objects.link(o); objs['OCEAN_FAR'] = o
    if crop: crop_city(objs, *crop)
    P.city_materials(objs, style)
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
    wave.inputs['Scale'].default_value = 0.25; wave.inputs['Distortion'].default_value = 0.0
    nt.links.new(tc.outputs['Object'], wave.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.93; ramp.color_ramp.elements[1].position = 0.97
    nt.links.new(wave.outputs['Fac'], ramp.inputs[0])
    b.inputs['Emission Color'].default_value = P.PAL['turq']
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 2.5
    nt.links.new(ramp.outputs[0], mul.inputs[0]); nt.links.new(mul.outputs[0], b.inputs['Emission Strength'])
    return m

def facade_2040_material():
    """Realistic futuristic facade: glass + metal panel pattern by object-space brick texture, warm interior lights."""
    m = P.new_mat('MAT_Wall2040', (0.5, 0.56, 0.62, 1), 0.2, 0.7, coat=0.5); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.inputs['Scale'].default_value = 0.35; brick.inputs['Mortar Size'].default_value = 0.08; brick.inputs['Brick Width'].default_value = 2.2; brick.inputs['Row Height'].default_value = 1.0
    brick.inputs['Color1'].default_value = (0.08, 0.1, 0.13, 1); brick.inputs['Color2'].default_value = (0.5, 0.56, 0.62, 1); brick.inputs['Mortar'].default_value = (0.3, 0.32, 0.34, 1)
    nt.links.new(tc.outputs['Object'], brick.inputs['Vector']); nt.links.new(brick.outputs['Color'], b.inputs['Base Color'])
    # windows (dark bricks) are glossy; panels rougher
    ramp = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(brick.outputs['Fac'], ramp.inputs[0])
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'MULTIPLY_ADD'; inv.inputs[1].default_value = 0.4; inv.inputs[2].default_value = 0.08
    nt.links.new(brick.outputs['Fac'], inv.inputs[0]); nt.links.new(inv.outputs[0], b.inputs['Roughness'])
    # random warm lit windows
    noise = nt.nodes.new('ShaderNodeTexWhiteNoise'); noise.noise_dimensions = '3D'
    snap = nt.nodes.new('ShaderNodeVectorMath'); snap.operation = 'SNAP'; snap.inputs[1].default_value = (2.2 / 0.35 * 0.5, 2.2 / 0.35 * 0.5, 1.0 / 0.35)
    nt.links.new(tc.outputs['Object'], snap.inputs[0]); nt.links.new(snap.outputs[0], noise.inputs['Vector'])
    gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.72
    nt.links.new(noise.outputs['Value'], gt.inputs[0])
    isw = nt.nodes.new('ShaderNodeMath'); isw.operation = 'LESS_THAN'; isw.inputs[1].default_value = 0.5; nt.links.new(brick.outputs['Fac'], isw.inputs[0])
    both = nt.nodes.new('ShaderNodeMath'); both.operation = 'MULTIPLY'; nt.links.new(gt.outputs[0], both.inputs[0]); nt.links.new(isw.outputs[0], both.inputs[1])
    es = nt.nodes.new('ShaderNodeMath'); es.operation = 'MULTIPLY'; es.inputs[1].default_value = 3.0; nt.links.new(both.outputs[0], es.inputs[0])
    b.inputs['Emission Color'].default_value = (1.0, 0.75, 0.45, 1); nt.links.new(es.outputs[0], b.inputs['Emission Strength'])
    return m

def apply_future_materials(objs):
    wall = facade_2040_material(); roof = P.new_mat('MAT_Roof2040', (0.1, 0.12, 0.15, 1), 0.3, 0.8); road = road_lane_material()
    for i, s in enumerate(objs['CITY_BUILDING'].material_slots):
        s.material = roof if 'Roof' in (s.material.name if s.material else '') else wall
    for s in objs['CITY_ROAD'].material_slots: s.material = road
