"""Shared production library for JIJI IN MOTION (Blender 4.5 bpy).
Palette, materials, binary-transformation Geometry Nodes system, render settings, camera helpers.
"""
import bpy, math, os, random
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FONT_MONO = '/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf'
FONT_SANS = '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'

def hex2rgb(h, a=1.0):
    h = h.lstrip('#'); r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    # sRGB -> linear
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b), a)

PAL = {
    'space': hex2rgb('#090D16'), 'blue': hex2rgb('#0755C9'), 'turq': hex2rgb('#00C6A8'),
    'orange': hex2rgb('#FF650D'), 'yellow': hex2rgb('#F6C928'), 'white': hex2rgb('#F3F0E8'),
}

def find_font(candidates):
    for c in candidates:
        if os.path.exists(c): return c
    import glob
    for pat in ('/usr/share/fonts/**/*JetBrainsMono*Bold*.ttf', '/usr/share/fonts/**/InterDisplay-Bold.otf', '/usr/share/fonts/**/Inter-Bold.otf', '/usr/share/fonts/**/DejaVuSans-Bold.ttf'):
        g = glob.glob(pat, recursive=True)
        if g: return g[0]
    return None

# ----------------------------------------------------------------- materials
def new_mat(name, color=(0.8, 0.8, 0.8, 1), rough=0.5, metal=0.0, emission=None, estrength=0.0, alpha=1.0, transmission=0.0, ior=1.45, coat=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs['Base Color'].default_value = color; b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal; b.inputs['Alpha'].default_value = alpha
    b.inputs['Transmission Weight'].default_value = transmission; b.inputs['IOR'].default_value = ior
    b.inputs['Coat Weight'].default_value = coat
    if emission is not None:
        b.inputs['Emission Color'].default_value = emission; b.inputs['Emission Strength'].default_value = estrength
    if alpha < 1 or transmission > 0:
        m.surface_render_method = 'BLENDED' if hasattr(m, 'surface_render_method') else None
    return m

def glyph_material(name='MAT_BinaryGlyph', c1='turq', c2='blue', strength=6.0):
    """Emissive glyph material; colour picked per instance from Object Info > Random (works for GN instances in Cycles);
    pulse = 0.5+0.5*sin(time*4 + random*2pi) with 'time' driven by the frame."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
    ramp.color_ramp.elements[0].color = PAL[c1]; ramp.color_ramp.elements[1].position = 0.5; ramp.color_ramp.elements[1].color = PAL[c2]
    e2 = ramp.color_ramp.elements.new(0.8); e2.color = PAL['white']
    e3 = ramp.color_ramp.elements.new(0.94); e3.color = PAL['orange']
    nt.links.new(oi.outputs['Random'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], em.inputs[0])
    tval = nt.nodes.new('ShaderNodeValue'); tval.name = 'time'; tval.label = 'time'
    fc = tval.outputs[0].driver_add('default_value'); fc.driver.expression = 'frame/24.0'
    ph = nt.nodes.new('ShaderNodeMath'); ph.operation = 'MULTIPLY_ADD'; ph.inputs[1].default_value = 6.283
    nt.links.new(oi.outputs['Random'], ph.inputs[0])
    t4 = nt.nodes.new('ShaderNodeMath'); t4.operation = 'MULTIPLY'; t4.inputs[1].default_value = 4.0; nt.links.new(tval.outputs[0], t4.inputs[0])
    nt.links.new(t4.outputs[0], ph.inputs[2])
    sn = nt.nodes.new('ShaderNodeMath'); sn.operation = 'SINE'; nt.links.new(ph.outputs[0], sn.inputs[0])
    pulse = nt.nodes.new('ShaderNodeMath'); pulse.operation = 'MULTIPLY_ADD'; pulse.inputs[1].default_value = strength * 0.4; pulse.inputs[2].default_value = strength * 0.8
    nt.links.new(sn.outputs[0], pulse.inputs[0]); nt.links.new(pulse.outputs[0], em.inputs[1])
    nt.links.new(em.outputs[0], out.inputs[0])
    return m

def dissolving_material(name, base_color, rough=0.6, metal=0.0, glow='turq', glow_strength=2.5):
    """Surface material whose faces glow at the dissolve front: reads face attribute 'front' (0..1)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = base_color; b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    attr = nt.nodes.new('ShaderNodeAttribute'); attr.attribute_name = 'front'
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = glow_strength
    b.inputs['Emission Color'].default_value = PAL[glow]
    nt.links.new(attr.outputs['Fac'], mul.inputs[0]); nt.links.new(mul.outputs[0], b.inputs['Emission Strength'])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m

# ----------------------------------------------------------------- glyphs
def make_glyph_collection(name='GLYPHS', size=1.0, depth=0.12):
    """Two extruded text meshes '0' and '1' (JetBrains Mono) in a collection, origin centred."""
    if name in bpy.data.collections: return bpy.data.collections[name]
    col = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(col)
    font_path = find_font([FONT_MONO])
    font = bpy.data.fonts.load(font_path) if font_path else None
    mat = glyph_material()
    for ch in ('0', '1'):
        cu = bpy.data.curves.new(f'glyph_{ch}', 'FONT'); cu.body = ch; cu.size = size; cu.extrude = depth / 2; cu.resolution_u = 2; cu.fill_mode = 'FRONT'
        cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
        if font: cu.font = font
        ob = bpy.data.objects.new(f'glyph_{ch}', cu); col.objects.link(ob)
        bpy.context.view_layer.objects.active = ob; ob.select_set(True)
        bpy.ops.object.convert(target='MESH'); ob.select_set(False)
        ob.data.materials.append(mat)
        ob.hide_render = True; ob.hide_viewport = True
    col.hide_render = True
    return col

# ----------------------------------------------------------------- geometry nodes helpers
class GN:
    def __init__(self, tree): self.t = tree; self.x = 0
    def n(self, typ, **kw):
        node = self.t.nodes.new(typ); node.location = (self.x, 0); self.x += 200
        for k, v in kw.items():
            if k == 'op': node.operation = v
            elif k == 'dtype': node.data_type = v
            elif k == 'domain': node.domain = v
            elif k == 'mode': node.mode = v
            elif k == 'name_': node.name = v
            else:
                sock = node.inputs[k] if isinstance(k, int) or k in node.inputs else None
                if sock is None: raise KeyError(f'{typ} has no input {k}')
                if hasattr(v, 'bl_idname') or (isinstance(v, tuple) and hasattr(v[0], 'bl_idname')):
                    self.t.links.new(v if hasattr(v, 'bl_idname') else v[0].outputs[v[1]], sock)
                else: sock.default_value = v
        return node
    def link(self, a, b): self.t.links.new(a, b)

def binary_transform_group(name='GN_BinaryTransform'):
    """Reusable node group. Inputs: Geometry, Progress, Density, Glyph Size, Noise Scale, Seed, Flow, Glyphs (collection), Height Bias, Edge Glow.
    Real surface dissolves into glyph instances as Progress 0->1. Drive Progress backwards for binary->real."""
    if name in bpy.data.node_groups: return bpy.data.node_groups[name]
    t = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    it = t.interface
    it.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for nm, dv, mn, mx in (('Progress', 0.0, 0.0, 1.0), ('Density', 0.8, 0.0, 1000.0), ('Glyph Size', 0.9, 0.0, 100.0), ('Noise Scale', 0.02, 0.0, 100.0), ('Seed', 0.0, 0.0, 10000.0), ('Flow', 0.0, -1e6, 1e6), ('Height Bias', 0.5, 0.0, 1.0), ('Edge Glow', 1.0, 0.0, 1.0), ('Band', 0.12, 0.001, 1.0)):
        s = it.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = dv; s.min_value = mn; s.max_value = mx
    it.new_socket('Glyphs', in_out='INPUT', socket_type='NodeSocketCollection')
    it.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    g = GN(t)
    gi = g.n('NodeGroupInput'); go = g.n('NodeGroupOutput'); go.location = (4200, 0)
    I = lambda s: gi.outputs[s]
    pos = g.n('GeometryNodeInputPosition')
    # --- threshold field t(x) = noise*(1-hb) + normalized height*hb  (per face / per point)
    noise = g.n('ShaderNodeTexNoise'); noise.noise_dimensions = '4D'
    g.link(pos.outputs[0], noise.inputs['Vector']); g.link(I('Noise Scale'), noise.inputs['Scale']); g.link(I('Seed'), noise.inputs['W'])
    noise.inputs['Detail'].default_value = 3.0; noise.inputs['Roughness'].default_value = 0.6
    # height normalised by bounding box of the input geometry
    bbox = g.n('GeometryNodeBoundBox'); g.link(I('Geometry'), bbox.inputs[0])
    sepmin = g.n('ShaderNodeSeparateXYZ'); g.link(bbox.outputs['Min'], sepmin.inputs[0])
    sepmax = g.n('ShaderNodeSeparateXYZ'); g.link(bbox.outputs['Max'], sepmax.inputs[0])
    sepp = g.n('ShaderNodeSeparateXYZ'); g.link(pos.outputs[0], sepp.inputs[0])
    hrange = g.n('ShaderNodeMath', op='SUBTRACT'); g.link(sepmax.outputs['Z'], hrange.inputs[0]); g.link(sepmin.outputs['Z'], hrange.inputs[1])
    hmax = g.n('ShaderNodeMath', op='MAXIMUM'); g.link(hrange.outputs[0], hmax.inputs[0]); hmax.inputs[1].default_value = 1.0
    hz = g.n('ShaderNodeMath', op='SUBTRACT'); g.link(sepp.outputs['Z'], hz.inputs[0]); g.link(sepmin.outputs['Z'], hz.inputs[1])
    hn = g.n('ShaderNodeMath', op='DIVIDE'); g.link(hz.outputs[0], hn.inputs[0]); g.link(hmax.outputs[0], hn.inputs[1])
    # mix: t = noise*(1-hb) + hn*hb   -> rescale to 0.05..0.95
    one_minus = g.n('ShaderNodeMath', op='SUBTRACT'); one_minus.inputs[0].default_value = 1.0; g.link(I('Height Bias'), one_minus.inputs[1])
    a = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(noise.outputs['Fac'], a.inputs[0]); g.link(one_minus.outputs[0], a.inputs[1])
    b = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(hn.outputs[0], b.inputs[0]); g.link(I('Height Bias'), b.inputs[1])
    tsum = g.n('ShaderNodeMath', op='ADD'); g.link(a.outputs[0], tsum.inputs[0]); g.link(b.outputs[0], tsum.inputs[1])
    tmap = g.n('ShaderNodeMapRange'); g.link(tsum.outputs[0], tmap.inputs['Value']); tmap.inputs['From Min'].default_value = 0.2; tmap.inputs['From Max'].default_value = 0.8; tmap.inputs['To Min'].default_value = 0.0; tmap.inputs['To Max'].default_value = 1.0
    T = tmap.outputs['Result']
    # --- store t on faces, compute front glow = 1 - clamp((t - progress)/band)
    diff = g.n('ShaderNodeMath', op='SUBTRACT'); g.link(T, diff.inputs[0]); g.link(I('Progress'), diff.inputs[1])
    fr = g.n('ShaderNodeMath', op='DIVIDE'); g.link(diff.outputs[0], fr.inputs[0]); g.link(I('Band'), fr.inputs[1])
    frc = g.n('ShaderNodeClamp'); g.link(fr.outputs[0], frc.inputs[0])
    front = g.n('ShaderNodeMath', op='SUBTRACT'); front.inputs[0].default_value = 1.0; g.link(frc.outputs[0], front.inputs[1])
    frontg = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(front.outputs[0], frontg.inputs[0]); g.link(I('Edge Glow'), frontg.inputs[1])
    store_front = g.n('GeometryNodeStoreNamedAttribute', dtype='FLOAT', domain='FACE'); store_front.inputs['Name'].default_value = 'front'
    g.link(I('Geometry'), store_front.inputs['Geometry']); g.link(frontg.outputs[0], store_front.inputs['Value'])
    # dissolve faces where t < progress  (surface breaks into digits)
    less = g.n('FunctionNodeCompare', dtype='FLOAT', op='LESS_THAN'); g.link(T, less.inputs[0]); g.link(I('Progress'), less.inputs[1])
    delf = g.n('GeometryNodeDeleteGeometry', domain='FACE'); g.link(store_front.outputs[0], delf.inputs['Geometry']); g.link(less.outputs[0], delf.inputs['Selection'])
    # --- glyph points on the ORIGINAL surface, visible where t < progress + band (digits appear just ahead of the dissolve)
    dist = g.n('GeometryNodeDistributePointsOnFaces'); dist.distribute_method = 'RANDOM'
    g.link(I('Geometry'), dist.inputs['Mesh']); g.link(I('Density'), dist.inputs['Density']); g.link(I('Seed'), dist.inputs['Seed'])
    pb = g.n('ShaderNodeMath', op='ADD'); g.link(I('Progress'), pb.inputs[0]); g.link(I('Band'), pb.inputs[1])
    vis = g.n('FunctionNodeCompare', dtype='FLOAT', op='LESS_THAN'); g.link(T, vis.inputs[0]); g.link(pb.outputs[0], vis.inputs[1])
    # fade-in factor per point: clamp((progress + band - t)/band)
    fin = g.n('ShaderNodeMath', op='SUBTRACT'); g.link(pb.outputs[0], fin.inputs[0]); g.link(T, fin.inputs[1])
    fin2 = g.n('ShaderNodeMath', op='DIVIDE'); g.link(fin.outputs[0], fin2.inputs[0]); g.link(I('Band'), fin2.inputs[1])
    finc = g.n('ShaderNodeClamp'); g.link(fin2.outputs[0], finc.inputs[0])
    # random per point
    rnd = g.n('FunctionNodeRandomValue', dtype='FLOAT'); idx = g.n('GeometryNodeInputIndex'); g.link(idx.outputs[0], rnd.inputs['ID'])
    seedi = g.n('ShaderNodeMath', op='ADD'); g.link(I('Seed'), seedi.inputs[0]); seedi.inputs[1].default_value = 7.0
    g.link(seedi.outputs[0], rnd.inputs['Seed'])
    # bit flips over time: idx = floor(flow*3 + rnd*20) mod 2
    fl = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(I('Flow'), fl.inputs[0]); fl.inputs[1].default_value = 3.0
    r20 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(rnd.outputs[1], r20.inputs[0]); r20.inputs[1].default_value = 20.0
    g.link(r20.outputs[0], fl.inputs[2])
    flo = g.n('ShaderNodeMath', op='FLOOR'); g.link(fl.outputs[0], flo.inputs[0])
    md = g.n('ShaderNodeMath', op='MODULO'); g.link(flo.outputs[0], md.inputs[0]); md.inputs[1].default_value = 2.0
    # pulse = 0.5+0.5*sin(flow*4 + rnd*6.28 + z*0.3)
    ph = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(rnd.outputs[1], ph.inputs[0]); ph.inputs[1].default_value = 6.283
    fl4 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(I('Flow'), fl4.inputs[0]); fl4.inputs[1].default_value = 4.0
    g.link(fl4.outputs[0], ph.inputs[2])
    sn = g.n('ShaderNodeMath', op='SINE'); g.link(ph.outputs[0], sn.inputs[0])
    pulse = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(sn.outputs[0], pulse.inputs[0]); pulse.inputs[1].default_value = 0.5; pulse.inputs[2].default_value = 0.5
    # drift along normal: normal * sin(flow*2 + rnd*6.28) * 0.25 * glyphsize * progress
    drift_s = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(I('Flow'), drift_s.inputs[0]); drift_s.inputs[1].default_value = 2.0; g.link(ph.outputs[0], drift_s.inputs[2])
    drift_sin = g.n('ShaderNodeMath', op='SINE'); g.link(drift_s.outputs[0], drift_sin.inputs[0])
    drift_amp = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(drift_sin.outputs[0], drift_amp.inputs[0]); g.link(I('Glyph Size'), drift_amp.inputs[1])
    drift_amp2 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(drift_amp.outputs[0], drift_amp2.inputs[0]); g.link(I('Progress'), drift_amp2.inputs[1])
    nrm_scale = g.n('ShaderNodeVectorMath', op='SCALE'); g.link(dist.outputs['Normal'], nrm_scale.inputs[0]); g.link(drift_amp2.outputs[0], nrm_scale.inputs['Scale'])
    # push glyphs slightly off the surface (0.3*size) so they sit on the facade
    off = g.n('ShaderNodeVectorMath', op='SCALE'); g.link(dist.outputs['Normal'], off.inputs[0])
    off_amt = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(I('Glyph Size'), off_amt.inputs[0]); off_amt.inputs[1].default_value = 0.35
    g.link(off_amt.outputs[0], off.inputs['Scale'])
    total_off = g.n('ShaderNodeVectorMath', op='ADD'); g.link(nrm_scale.outputs[0], total_off.inputs[0]); g.link(off.outputs[0], total_off.inputs[1])
    setpos = g.n('GeometryNodeSetPosition'); g.link(dist.outputs['Points'], setpos.inputs['Geometry']); g.link(total_off.outputs[0], setpos.inputs['Offset'])
    # select visible, store attrs on points (carried to instances)
    delp = g.n('GeometryNodeDeleteGeometry', domain='POINT'); g.link(setpos.outputs[0], delp.inputs['Geometry'])
    notvis = g.n('FunctionNodeBooleanMath', op='NOT'); g.link(vis.outputs[0], notvis.inputs[0]); g.link(notvis.outputs[0], delp.inputs['Selection'])
    st1 = g.n('GeometryNodeStoreNamedAttribute', dtype='FLOAT', domain='POINT'); st1.inputs['Name'].default_value = 'bit_rand'
    g.link(delp.outputs[0], st1.inputs['Geometry']); g.link(rnd.outputs[1], st1.inputs['Value'])
    st2 = g.n('GeometryNodeStoreNamedAttribute', dtype='FLOAT', domain='POINT'); st2.inputs['Name'].default_value = 'pulse'
    g.link(st1.outputs[0], st2.inputs['Geometry']); g.link(pulse.outputs[0], st2.inputs['Value'])
    # instance
    cinfo = g.n('GeometryNodeCollectionInfo'); cinfo.transform_space = 'ORIGINAL'; g.link(I('Glyphs'), cinfo.inputs['Collection']); cinfo.inputs['Separate Children'].default_value = True; cinfo.inputs['Reset Children'].default_value = True
    inst = g.n('GeometryNodeInstanceOnPoints'); g.link(st2.outputs[0], inst.inputs['Points']); g.link(cinfo.outputs[0], inst.inputs['Instance'])
    inst.inputs['Pick Instance'].default_value = True; g.link(md.outputs[0], inst.inputs['Instance Index'])
    # rotation: align glyph +Z (text faces +Z after conversion) to the normal
    rot = g.n('FunctionNodeAlignEulerToVector'); rot.axis = 'Z'; g.link(dist.outputs['Normal'], rot.inputs['Vector'])
    # spin around normal randomly a little + keep upright for walls: second align with Y to world Z
    rot2 = g.n('FunctionNodeAlignEulerToVector'); rot2.axis = 'Y'; rot2.pivot_axis = 'Z'; g.link(rot.outputs[0], rot2.inputs['Rotation']); rot2.inputs['Vector'].default_value = (0, 0, 1)
    g.link(rot2.outputs[0], inst.inputs['Rotation'])
    sc = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(I('Glyph Size'), sc.inputs[0]); g.link(finc.outputs[0], sc.inputs[1])
    scv = g.n('ShaderNodeCombineXYZ'); g.link(sc.outputs[0], scv.inputs[0]); g.link(sc.outputs[0], scv.inputs[1]); g.link(sc.outputs[0], scv.inputs[2])
    g.link(scv.outputs[0], inst.inputs['Scale'])
    # --- glowing structural edges: wireframe of original mesh, appears with progress
    m2c = g.n('GeometryNodeMeshToCurve'); g.link(I('Geometry'), m2c.inputs['Mesh'])
    circ = g.n('GeometryNodeCurvePrimitiveCircle'); circ.inputs['Resolution'].default_value = 4
    er = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(I('Glyph Size'), er.inputs[0]); er.inputs[1].default_value = 0.06
    er2 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(er.outputs[0], er2.inputs[0]); g.link(I('Progress'), er2.inputs[1])
    g.link(er2.outputs[0], circ.inputs['Radius'])
    c2m = g.n('GeometryNodeCurveToMesh'); g.link(m2c.outputs[0], c2m.inputs['Curve']); g.link(circ.outputs[0], c2m.inputs['Profile Curve'])
    setmat = g.n('GeometryNodeSetMaterial'); g.link(c2m.outputs[0], setmat.inputs['Geometry']); setmat.inputs['Material'].default_value = glyph_material('MAT_BinaryEdge', 'blue', 'turq', 3.0)
    # only show edges where t < progress
    # (apply via delete on the curve mesh using t sampled at position — positions preserved so field evaluates)
    dele = g.n('GeometryNodeDeleteGeometry', domain='POINT'); g.link(setmat.outputs[0], dele.inputs['Geometry'])
    gte = g.n('FunctionNodeCompare', dtype='FLOAT', op='GREATER_THAN'); g.link(T, gte.inputs[0]); g.link(I('Progress'), gte.inputs[1]); g.link(gte.outputs[0], dele.inputs['Selection'])
    join = g.n('GeometryNodeJoinGeometry')
    g.link(delf.outputs[0], join.inputs[0]); g.link(inst.outputs[0], join.inputs[0]); g.link(dele.outputs[0], join.inputs[0])
    g.link(join.outputs[0], go.inputs[0])
    return t

def apply_binary(obj, progress=0.0, density=0.8, size=0.9, noise_scale=0.02, seed=0.0, flow=0.0, height_bias=0.5, band=0.12, glyphs=None, name='Binary'):
    glyphs = glyphs or make_glyph_collection()
    grp = binary_transform_group()
    md = obj.modifiers.new(name, 'NODES'); md.node_group = grp
    vals = {'Progress': progress, 'Density': density, 'Glyph Size': size, 'Noise Scale': noise_scale, 'Seed': seed, 'Flow': flow, 'Height Bias': height_bias, 'Band': band}
    for s in grp.interface.items_tree:
        if s.item_type == 'SOCKET' and s.in_out == 'INPUT':
            if s.name in vals: md[s.identifier] = float(vals[s.name])
            elif s.name == 'Glyphs': md[s.identifier] = glyphs
    return md

def mod_input_id(md, name):
    for s in md.node_group.interface.items_tree:
        if s.item_type == 'SOCKET' and s.in_out == 'INPUT' and s.name == name: return s.identifier

def key_mod(md, name, frame, value):
    ident = mod_input_id(md, name); md[ident] = float(value); md.keyframe_insert(f'["{ident}"]', frame=frame)

# ----------------------------------------------------------------- world / render / camera
def setup_world(sun_rot=(math.radians(50), 0, math.radians(-120)), sun_energy=3.0, sun_color=(1, 0.95, 0.88), sky=True, sky_strength=0.6, turbidity=3.0, sun_elev=35, sun_az=240, horizon=None):
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
    if sky:
        sk = nt.nodes.new('ShaderNodeTexSky'); sk.sky_type = 'NISHITA'; sk.sun_elevation = math.radians(sun_elev); sk.sun_rotation = math.radians(sun_az)
        sk.sun_intensity = 0.4; sk.sun_size = math.radians(1.5); sk.air_density = 1.1; sk.dust_density = turbidity * 0.5; sk.ozone_density = 1.2
        nt.links.new(sk.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = sky_strength
    else:
        bg.inputs[0].default_value = horizon or PAL['space']; bg.inputs[1].default_value = sky_strength
    nt.links.new(bg.outputs[0], out.inputs[0])
    sun = bpy.data.objects.get('SUN')
    if sun is None:
        ld = bpy.data.lights.new('SUN', 'SUN'); sun = bpy.data.objects.new('SUN', ld); sc.collection.objects.link(sun)
    sun.data.energy = sun_energy; sun.data.color = sun_color; sun.data.angle = math.radians(1.5)
    sun.rotation_euler = sun_rot
    return sun

def setup_render(res=(1280, 720), samples=48, fps=24, engine='CYCLES', motion_blur=False, exposure=0.0, denoise=True, volumes=False, out=None, frame_start=1, frame_end=48, film_transparent=False):
    sc = bpy.context.scene
    sc.render.engine = engine; sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.fps = fps; sc.frame_start = frame_start; sc.frame_end = frame_end
    sc.render.film_transparent = film_transparent
    if engine == 'CYCLES':
        c = sc.cycles; c.device = 'CPU'; c.samples = samples; c.use_denoising = denoise
        c.denoiser = 'OPENIMAGEDENOISE'; c.denoising_use_gpu = False; c.use_adaptive_sampling = True; c.adaptive_threshold = 0.05
        c.max_bounces = 6; c.diffuse_bounces = 2; c.glossy_bounces = 3; c.transmission_bounces = 6; c.volume_bounces = 0; c.transparent_max_bounces = 8
        c.caustics_reflective = False; c.caustics_refractive = False; c.blur_glossy = 1.0
        c.volume_step_rate = 2.0 if volumes else 1.0; c.volume_max_steps = 64
        sc.render.use_motion_blur = motion_blur; sc.render.motion_blur_shutter = 0.5
        c.use_light_tree = True
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = exposure
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '8'; sc.render.image_settings.compression = 50
    sc.render.use_persistent_data = True
    if out: sc.render.filepath = out
    return sc

def add_camera(name='CAM', loc=(0, -50, 20), target=None, lens=35, dof_target=None, fstop=2.8, sensor=36):
    cd = bpy.data.cameras.new(name); cam = bpy.data.objects.new(name, cd); bpy.context.scene.collection.objects.link(cam)
    cam.location = loc; cd.lens = lens; cd.sensor_width = sensor; cd.clip_end = 20000
    if target is not None:
        tgt = target if isinstance(target, bpy.types.Object) else make_empty(name + '_target', target)
        c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        cam['target'] = tgt.name
    if dof_target is not None:
        cd.dof.use_dof = True; cd.dof.focus_object = dof_target if isinstance(dof_target, bpy.types.Object) else None
        if not isinstance(dof_target, bpy.types.Object): cd.dof.focus_distance = float(dof_target)
        cd.dof.aperture_fstop = fstop
    bpy.context.scene.camera = cam
    return cam

def make_empty(name, loc):
    e = bpy.data.objects.new(name, None); e.empty_display_size = 1; e.location = loc; bpy.context.scene.collection.objects.link(e); return e

def key(obj, frame, loc=None, rot=None, scale=None, interp='BEZIER'):
    if loc is not None: obj.location = loc; obj.keyframe_insert('location', frame=frame)
    if rot is not None: obj.rotation_euler = rot; obj.keyframe_insert('rotation_euler', frame=frame)
    if scale is not None: obj.scale = scale; obj.keyframe_insert('scale', frame=frame)
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = interp

def ease_all(obj, mode='EASE_IN_OUT'):
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.easing = mode

def link_city(blend=None, names=('CITY_BUILDING', 'CITY_ROAD', 'CITY_WATER', 'CITY_TERRAIN', 'CITY_TREE', 'CITY_PAVING', 'CITY_FURNITURE', 'CITY_RAIL')):
    blend = blend or os.path.join(ROOT, 'blender', 'city_base.blend')
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in names]
    col = bpy.data.collections.get('CITY') or bpy.data.collections.new('CITY')
    if col.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(col)
    objs = {}
    for o in dst.objects:
        if o is None: continue
        col.objects.link(o); objs[o.name] = o
    return objs

def city_materials(objs, style='real'):
    """Assign materials per class. style 'real' = present-day Posta, 'future' = 2040 realistic, 'binary' = dissolving base."""
    pal = PAL
    if style in ('real', 'future'):
        wall = new_mat('MAT_Wall', (0.62, 0.58, 0.52, 1), 0.7) if style == 'real' else new_mat('MAT_Wall2040', (0.55, 0.6, 0.66, 1), 0.25, 0.6, coat=0.6)
        roof = new_mat('MAT_Roof', (0.28, 0.26, 0.25, 1), 0.8) if style == 'real' else new_mat('MAT_Roof2040', (0.12, 0.14, 0.18, 1), 0.3, 0.8)
        road = new_mat('MAT_Road', (0.05, 0.05, 0.055, 1), 0.85) if style == 'real' else new_mat('MAT_Road2040', (0.04, 0.045, 0.06, 1), 0.35, 0.2)
    else:
        wall = dissolving_material('MAT_WallDissolve', (0.62, 0.58, 0.52, 1)); roof = dissolving_material('MAT_RoofDissolve', (0.28, 0.26, 0.25, 1))
        road = dissolving_material('MAT_RoadDissolve', (0.05, 0.05, 0.055, 1), glow='blue')
    water = new_mat('MAT_Ocean', (0.02, 0.12, 0.16, 1), 0.08, 0.0, transmission=0.0, coat=1.0)
    terrain = new_mat('MAT_Terrain', (0.22, 0.2, 0.15, 1), 0.95)
    leaves = new_mat('MAT_Leaves', (0.08, 0.22, 0.06, 1), 0.7); trunk = new_mat('MAT_Trunk', (0.2, 0.13, 0.08, 1), 0.9)
    paving = new_mat('MAT_Paving', (0.35, 0.34, 0.32, 1), 0.8); furn = new_mat('MAT_Furniture', (0.3, 0.3, 0.32, 1), 0.5, 0.5)
    mapping = {'CITY_BUILDING': (wall, roof), 'CITY_ROAD': (road,), 'CITY_WATER': (water,), 'CITY_TERRAIN': (terrain,), 'CITY_TREE': (trunk, leaves), 'CITY_PAVING': (paving,), 'CITY_FURNITURE': (furn,), 'CITY_RAIL': (furn,)}
    for n, o in objs.items():
        mats = mapping.get(n)
        if not mats: continue
        for i, slot in enumerate(o.material_slots):
            nm = slot.material.name if slot.material else ''
            if n == 'CITY_BUILDING': slot.material = roof if 'Roof' in nm else wall
            elif n == 'CITY_TREE': slot.material = leaves if 'Leaves' in nm else trunk
            else: slot.material = mats[0]
    return objs

# ----------------------------------------------------------------- ground query
_BVH = None
def ground_z(x, y, default=12.0):
    """Terrain height at (x, y) using a BVH over CITY_TERRAIN (and CITY_ROAD if present)."""
    global _BVH
    from mathutils.bvhtree import BVHTree
    if _BVH is None:
        objs = [o for n in ('CITY_TERRAIN', 'CITY_ROAD') if (o := bpy.data.objects.get(n))]
        verts, polys, off = [], [], 0
        for o in objs:
            me = o.data
            verts += [o.matrix_world @ v.co for v in me.vertices]
            polys += [[i + off for i in p.vertices] for p in me.polygons]; off += len(me.vertices)
        _BVH = BVHTree.FromPolygons(verts, polys)
    hit = _BVH.ray_cast(Vector((x, y, 500.0)), Vector((0, 0, -1)), 1000.0)
    return hit[0].z if hit[0] is not None else default

def nearest_building_top(x, y, radius=60):
    """Return (position, height) of the tallest building vertex within radius (for framing)."""
    import numpy as np
    o = bpy.data.objects['CITY_BUILDING']; co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    m = (np.abs(co[:, 0] - x) < radius) & (np.abs(co[:, 1] - y) < radius)
    if not m.any(): return None
    sub = co[m]; i = sub[:, 2].argmax(); return Vector(sub[i]), float(sub[i, 2])

def best_street_spot(center, radius=300, building_r=35, tree_r=18, samples=400, seed=1):
    """Pick a road point near center with many building vertices around and no trees close by. Returns (x, y, z)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    def verts(name):
        o = bpy.data.objects[name]; co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); return co.reshape(-1, 3)
    road, bld, tree = verts('CITY_ROAD'), verts('CITY_BUILDING'), verts('CITY_TREE')
    cx, cy = center
    cand = road[np.hypot(road[:, 0] - cx, road[:, 1] - cy) < radius]
    cand = cand[rng.choice(len(cand), min(samples, len(cand)), replace=False)]
    best, bs = None, -1
    for p in cand:
        db = np.hypot(bld[:, 0] - p[0], bld[:, 1] - p[1]); dt = np.hypot(tree[:, 0] - p[0], tree[:, 1] - p[1])
        if (dt < tree_r).any() or (db < 6).any(): continue
        score = int((db < building_r).sum()) + 0.5 * int(((db >= building_r) & (db < 80)).sum())
        if score > bs: bs, best = score, p
    return (float(best[0]), float(best[1]), float(best[2])) if best is not None else (cx, cy, ground_z(cx, cy))

def clear_trees_near(path_points, r=25):
    import numpy as np, bmesh
    o = bpy.data.objects.get('CITY_TREE')
    if not o: return
    me = o.data; co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    near = np.zeros(len(co), bool)
    for p in path_points: near |= np.hypot(co[:, 0] - p[0], co[:, 1] - p[1]) < r
    if near.any():
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(near)[0]], context='VERTS'); bm.to_mesh(me); bm.free()
