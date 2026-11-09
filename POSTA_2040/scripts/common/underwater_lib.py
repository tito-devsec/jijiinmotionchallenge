"""Underwater world / volume / caustics helpers for POSTA 2040 (Blender 4.5, Cycles).
    import underwater_lib as U
    U.setup_underwater(scene, depth=12)     # world, WATER_VOLUME, WATER_SURFACE, UW_SUN, UW_CAUSTIC (textured spot)
    U.add_light_shafts(scene)               # noisy shadow-only gobo above the surface -> god rays in the volume
"""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import posta_lib as P

def _mix(a, b, f): return tuple(a[i] * (1 - f) + b[i] * f for i in range(3)) + (1.0,)
DEEP = _mix(P.PAL['blue'], (0.0, 0.01, 0.04, 1), 0.85)        # deep blue-green, almost black
MID = _mix(P.PAL['blue'], P.PAL['turq'], 0.25)                 # mid-water blue
BRIGHT = _mix(MID, (0.5, 0.85, 1.0, 1), 0.45)                    # looking up toward the sun

def _linear_extrap(id_data):
    ad = id_data.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves: fc.extrapolation = 'LINEAR'

def underwater_world(scene):
    w = scene.world or bpy.data.worlds.new('World'); scene.world = w; w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    # Generated coords for the world = view direction; Z = -1 (down) .. 1 (up)
    ramp = nt.nodes.new('ShaderNodeValToRGB'); cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = DEEP
    cr.elements[1].position = 0.55; cr.elements[1].color = MID
    e = cr.elements.new(0.9); e.color = BRIGHT
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -1; mr.inputs['From Max'].default_value = 1
    nt.links.new(sep.outputs['Z'], mr.inputs['Value']); nt.links.new(mr.outputs[0], ramp.inputs[0]); nt.links.new(ramp.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.45
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w

def water_volume_material(density=0.025, anisotropy=0.6, name='MAT_WaterVolume'):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); pv = nt.nodes.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = (0.2, 0.5, 0.9, 1)              # scatter albedo: blue
    pv.inputs['Density'].default_value = density
    pv.inputs['Anisotropy'].default_value = anisotropy
    pv.inputs['Absorption Color'].default_value = (0.05, 0.35, 0.8, 1)  # absorbs red/green first
    nt.links.new(pv.outputs[0], out.inputs['Volume'])
    return m

def water_surface_material(name='MAT_WaterSurface', wave_scale=0.08, amp=0.35):
    m = P.new_mat(name, (1, 1, 1, 1), 0.02, 0.0, transmission=1.0, ior=1.33); nt = m.node_tree
    b = nt.nodes['Principled BSDF']; out = nt.nodes['Material Output']
    m.surface_render_method = 'DITHERED'
    # shadows pass straight through (so the sun / caustic spot reach the seabed)
    lp = nt.nodes.new('ShaderNodeLightPath'); tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Shadow Ray'], mx.inputs[0]); nt.links.new(b.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs['Surface'])
    # displaced wavy surface (two noise octaves, drifting with time)
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.name = 'WaveMapping'
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = wave_scale; n1.inputs['Detail'].default_value = 3.0; n1.inputs['Roughness'].default_value = 0.55
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = wave_scale * 4.5; n2.inputs['Detail'].default_value = 2.0
    nt.links.new(mp.outputs[0], n1.inputs['Vector']); nt.links.new(mp.outputs[0], n2.inputs['Vector'])
    add = nt.nodes.new('ShaderNodeMath'); add.operation = 'MULTIPLY_ADD'; nt.links.new(n2.outputs['Fac'], add.inputs[0]); add.inputs[1].default_value = 0.25; nt.links.new(n1.outputs['Fac'], add.inputs[2])
    disp = nt.nodes.new('ShaderNodeDisplacement'); disp.inputs['Midlevel'].default_value = 0.62; disp.inputs['Scale'].default_value = amp
    nt.links.new(add.outputs[0], disp.inputs['Height']); nt.links.new(disp.outputs[0], out.inputs['Displacement'])
    m.displacement_method = 'BOTH'
    mp.inputs['Location'].default_value = (0, 0, 0); mp.inputs['Location'].keyframe_insert('default_value', frame=1)
    mp.inputs['Location'].default_value = (6.0, 3.0, 0); mp.inputs['Location'].keyframe_insert('default_value', frame=241)
    _linear_extrap(nt)
    return m

def caustic_light(scene, name='UW_CAUSTIC', height=30.0, energy=250000.0, scale=22.0, speed=1.0):
    """Wide spot light from above with a node-tree Voronoi caustic net (animated mapping). Needs Cycles."""
    ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, 'SPOT')
    ld.type = 'SPOT'; ld.energy = energy; ld.color = (0.85, 0.95, 1.0); ld.spot_size = math.radians(140); ld.spot_blend = 0.4
    ld.shadow_soft_size = 0.6; ld.use_nodes = True
    nt = ld.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputLight'); em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (0.85, 0.95, 1.0, 1)
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.name = 'CausticMapping'
    nt.links.new(tc.outputs['Normal'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (scale, scale, scale)
    layers = []
    for i, (vs, w) in enumerate(((1.0, 0.09), (1.9, 0.06))):
        vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = vs; vor.inputs['Randomness'].default_value = 1.0
        nt.links.new(mp.outputs[0], vor.inputs['Vector'])
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.0; mr.inputs['From Max'].default_value = w; mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.0
        nt.links.new(vor.outputs['Distance'], mr.inputs['Value'])
        pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 3.0; nt.links.new(mr.outputs[0], pw.inputs[0])
        layers.append(pw)
    sm = nt.nodes.new('ShaderNodeMath'); sm.operation = 'MULTIPLY_ADD'; nt.links.new(layers[1].outputs[0], sm.inputs[0]); sm.inputs[1].default_value = 0.6; nt.links.new(layers[0].outputs[0], sm.inputs[2])
    fin = nt.nodes.new('ShaderNodeMath'); fin.operation = 'MULTIPLY_ADD'; nt.links.new(sm.outputs[0], fin.inputs[0]); fin.inputs[1].default_value = 2.2; fin.inputs[2].default_value = 0.12
    nt.links.new(fin.outputs[0], em.inputs['Strength']); nt.links.new(em.outputs[0], out.inputs[0])
    # animate the pattern (drift + slow rotation) with linear extrapolation
    mp.inputs['Location'].default_value = (0, 0, 0); mp.inputs['Location'].keyframe_insert('default_value', frame=1)
    mp.inputs['Location'].default_value = (0.8 * speed, 0.5 * speed, 0); mp.inputs['Location'].keyframe_insert('default_value', frame=241)
    mp.inputs['Rotation'].default_value = (0, 0, 0); mp.inputs['Rotation'].keyframe_insert('default_value', frame=1)
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(25 * speed)); mp.inputs['Rotation'].keyframe_insert('default_value', frame=241)
    _linear_extrap(nt)
    lo = bpy.data.objects.get(name) or bpy.data.objects.new(name, ld)
    if lo.name not in scene.collection.objects: scene.collection.objects.link(lo)
    lo.location = (0, 0, height); lo.rotation_euler = (0, 0, 0)   # points -Z
    return lo

def setup_underwater(scene, depth=12.0, size=200.0, density=0.014, anisotropy=0.6, sun_energy=3.5, sun_tilt=22.0, caustic_energy=250000.0):
    """Deep blue-green world, WATER_VOLUME cube, WATER_SURFACE plane at z=0 (wavy glass), UW_SUN and UW_CAUSTIC lights.
    The seabed is expected at z=-depth. Returns dict of created objects."""
    underwater_world(scene)
    col = scene.collection
    # volume cube: top face at the water surface
    me = bpy.data.meshes.new('WATER_VOLUME'); import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
    vol = bpy.data.objects.new('WATER_VOLUME', me); col.objects.link(vol)
    vol.scale = (size, size, size); vol.location = (0, 0, -size / 2 + 0.01)
    me.materials.append(water_volume_material(density, anisotropy))
    vol.display_type = 'WIRE'; vol.visible_shadow = False
    # water surface
    me = bpy.data.meshes.new('WATER_SURFACE'); bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=140, y_segments=140, size=size / 2)
    for f in bm.faces: f.smooth = True
    bm.to_mesh(me); bm.free()
    surf = bpy.data.objects.new('WATER_SURFACE', me); col.objects.link(surf); surf.location = (0, 0, 0)
    me.materials.append(water_surface_material())
    # lights
    ld = bpy.data.lights.new('UW_SUN', 'SUN'); ld.energy = sun_energy; ld.color = (0.8, 0.93, 1.0); ld.angle = math.radians(3)
    sun = bpy.data.objects.new('UW_SUN', ld); col.objects.link(sun); sun.rotation_euler = (math.radians(sun_tilt), 0, math.radians(35)); sun.location = (0, 0, 20)
    caus = caustic_light(scene, height=depth * 1.5 + 2, energy=caustic_energy)
    # render settings for volumes
    if scene.render.engine == 'CYCLES' or True:
        c = scene.cycles; c.volume_bounces = 1; c.volume_step_rate = 1.0; c.volume_max_steps = 256; c.volume_preview_step_rate = 2.0
        c.transparent_max_bounces = 12; c.transmission_bounces = 8; c.max_bounces = 8
    return {'volume': vol, 'surface': surf, 'sun': sun, 'caustic': caus}

def add_light_shafts(scene, size=120.0, z=1.5, scale=0.1, coverage=0.5, name='UW_SHAFT_GOBO'):
    """A shadow-only 'gobo' plane above the water surface with noisy holes: the caustic spot and sun shine through
    the gaps and produce volumetric god rays in WATER_VOLUME. Camera rays ignore it."""
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); ob.location = (0, 0, z)
    m = bpy.data.materials.new('MAT_ShaftGobo'); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); tr = nt.nodes.new('ShaderNodeBsdfTransparent'); blk = nt.nodes.new('ShaderNodeBsdfDiffuse'); blk.inputs[0].default_value = (0, 0, 0, 1)
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.name = 'GoboMapping'; nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (1.0, 2.5, 1.0)     # streaky, elongated gaps
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = scale * size; noise.inputs['Detail'].default_value = 3.0; noise.inputs['Roughness'].default_value = 0.6
    nt.links.new(mp.outputs[0], noise.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = coverage - 0.08; ramp.color_ramp.elements[1].position = coverage + 0.08
    nt.links.new(noise.outputs['Fac'], ramp.inputs[0])
    mask = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(ramp.outputs[0], mask.inputs[0]); nt.links.new(blk.outputs[0], mask.inputs[1]); nt.links.new(tr.outputs[0], mask.inputs[2])
    lp = nt.nodes.new('ShaderNodeLightPath'); final = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Shadow Ray'], final.inputs[0]); nt.links.new(tr.outputs[0], final.inputs[1]); nt.links.new(mask.outputs[0], final.inputs[2])
    nt.links.new(final.outputs[0], out.inputs[0])
    m.surface_render_method = 'DITHERED'
    me.materials.append(m)
    ob.visible_camera = False; ob.visible_diffuse = False; ob.visible_glossy = False; ob.visible_transmission = False; ob.visible_volume_scatter = False
    mp.inputs['Location'].default_value = (0, 0, 0); mp.inputs['Location'].keyframe_insert('default_value', frame=1)
    mp.inputs['Location'].default_value = (3.0, 1.5, 0); mp.inputs['Location'].keyframe_insert('default_value', frame=241)
    _linear_extrap(nt)
    return ob
