"""KIT 2 - Underwater / tropical reef asset kit for POSTA 2040 (Blender 4.5, headless, Cycles).
Run: /opt/blender/blender -b --python scripts/assets/build_underwater.py [-- --norender] [-- --quick] [-- --fishonly]
Builds REEF_FLOOR, CORAL_KIT (9 coral types), REEF_HEAD (+GN_CoralScatter), FISH_KIT (3 fish), GN_FishSchool
(FISH_SCHOOL_A/B), GN_Bubbles (BUBBLE_EMITTER), the underwater world/volume/caustics (underwater_lib),
saves blender/assets/underwater.blend and renders previews/asset_reef.png + previews/asset_fish_kit.png.
"""
import bpy, bmesh, sys, os, math, random
from mathutils import Vector, Matrix, Quaternion, noise
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'common'))
import posta_lib as P
import kit_lib as K
import underwater_lib as U
from kit_lib import bm_box, bm_cyl, bm_bar, bm_sphere, rot_to, rx, ry, rz

ROOT = P.ROOT
OUT_BLEND = os.path.join(ROOT, 'blender', 'assets', 'underwater.blend')
PREVIEWS = os.path.join(ROOT, 'previews')
NORENDER = '--norender' in sys.argv; QUICK = '--quick' in sys.argv; FISHONLY = '--fishonly' in sys.argv
DEPTH = 12.0
random.seed(11); noise.seed_set(11)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ----------------------------------------------------------------- materials
def coral_mat(name, base, tip=None, sss=0.35, rough=0.45, radius=(0.3, 0.12, 0.08), tip_power=2.0, bump=0.3):
    """Saturated coral material: subsurface, translucent/pale tips driven by vertex attribute 'tip' (0 base .. 1 tip)."""
    m = P.new_mat(name, base, rough); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Subsurface Weight'].default_value = sss; b.inputs['Subsurface Radius'].default_value = radius; b.inputs['Subsurface Scale'].default_value = 0.15
    b.inputs['Coat Weight'].default_value = 0.15; b.inputs['Coat Roughness'].default_value = 0.3
    tipc = tip or tuple(min(1.0, base[i] * 0.6 + 0.4) for i in range(3)) + (1.0,)
    attr = nt.nodes.new('ShaderNodeAttribute'); attr.attribute_name = 'tip'
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = tip_power * 1.6; nt.links.new(attr.outputs['Fac'], pw.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs[6].default_value = base; mix.inputs[7].default_value = tipc
    nt.links.new(pw.outputs[0], mix.inputs['Factor']); nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    nt.links.new(mix.outputs[2], b.inputs['Subsurface Radius']) if False else None
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 40.0; nz.inputs['Detail'].default_value = 4.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.01
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    # translucent tips: a little emission so they read bright against the blue
    nt.links.new(mix.outputs[2], b.inputs['Emission Color']);
    em = nt.nodes.new('ShaderNodeMath'); em.operation = 'MULTIPLY'; em.inputs[1].default_value = 0.12; nt.links.new(pw.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], b.inputs['Emission Strength'])
    return m

PINK = (0.95, 0.12, 0.45, 1); HOTPINK = (1.0, 0.2, 0.6, 1); ORANGE = (1.0, 0.32, 0.05, 1); PURPLE = (0.42, 0.1, 0.75, 1)
YELLOW = (1.0, 0.75, 0.1, 1); RED = (0.85, 0.06, 0.08, 1); LILAC = (0.75, 0.55, 0.95, 1); TAN = (0.8, 0.55, 0.3, 1); GREENISH = (0.55, 0.7, 0.25, 1)
M_STAG = coral_mat('MAT_CoralStaghorn', LILAC, (0.95, 0.9, 1.0, 1), 0.4, tip_power=1.5)
M_TABLE = coral_mat('MAT_CoralTable', (0.8, 0.42, 0.15, 1), (0.95, 0.7, 0.4, 1), 0.3, 0.6, tip_power=3.0)
M_BRAIN = coral_mat('MAT_CoralBrain', (0.7, 0.55, 0.1, 1), (0.85, 0.8, 0.35, 1), 0.25, 0.55, tip_power=4.0, bump=0.6)
M_FAN = coral_mat('MAT_SeaFan', RED, (1.0, 0.4, 0.3, 1), 0.3, 0.5, tip_power=2.5)
M_SPONGE_P = coral_mat('MAT_SpongePurple', PURPLE, (0.8, 0.6, 1.0, 1), 0.3, 0.6, tip_power=3.0, bump=0.8)
M_SPONGE_Y = coral_mat('MAT_SpongeYellow', YELLOW, (1.0, 0.95, 0.6, 1), 0.3, 0.6, tip_power=3.0, bump=0.8)
M_SOFT_PINK = coral_mat('MAT_SoftCoralPink', HOTPINK, (1.0, 0.85, 0.95, 1), 0.6, 0.4, (0.5, 0.2, 0.3), tip_power=2.0, bump=0.5)
M_SOFT_ORANGE = coral_mat('MAT_SoftCoralOrange', ORANGE, (1.0, 0.9, 0.7, 1), 0.6, 0.4, (0.5, 0.25, 0.1), tip_power=2.0, bump=0.5)
M_ANEM = coral_mat('MAT_Anemone', (0.6, 0.25, 0.7, 1), (1.0, 0.55, 0.85, 1), 0.5, 0.35, tip_power=1.5)
M_ANEM_BASE = coral_mat('MAT_AnemoneBase', (0.55, 0.3, 0.15, 1), (0.6, 0.4, 0.2, 1), 0.3, 0.6)

def sand_mat():
    m = P.new_mat('MAT_Sand', (0.6, 0.52, 0.36, 1), 0.9); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.0; nz.inputs['Detail'].default_value = 6.0; nz.inputs['Roughness'].default_value = 0.75
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (0.45, 0.38, 0.25, 1); ramp.color_ramp.elements[1].color = (0.72, 0.64, 0.46, 1)
    nt.links.new(nz.outputs['Fac'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    v = nt.nodes.new('ShaderNodeTexVoronoi'); v.inputs['Scale'].default_value = 120.0; nt.links.new(tc.outputs['Object'], v.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.25; bp.inputs['Distance'].default_value = 0.01
    nt.links.new(v.outputs['Distance'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

def rock_mat():
    m = P.new_mat('MAT_ReefRock', (0.25, 0.2, 0.16, 1), 0.85); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 1.2; n1.inputs['Detail'].default_value = 5.0; nt.links.new(tc.outputs['Object'], n1.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); cr = ramp.color_ramp
    cr.elements[0].position = 0.3; cr.elements[0].color = (0.16, 0.12, 0.1, 1)      # dark rock
    cr.elements[1].position = 0.75; cr.elements[1].color = (0.55, 0.2, 0.45, 1)      # encrusting pink/purple algae
    e = cr.elements.new(0.52); e.color = (0.45, 0.4, 0.22, 1)                        # olive encrusting
    e2 = cr.elements.new(0.62); e2.color = (0.75, 0.45, 0.15, 1)                     # orange sponge patches
    nt.links.new(n1.outputs['Fac'], ramp.inputs[0]); nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 25.0; n2.inputs['Detail'].default_value = 6.0; nt.links.new(tc.outputs['Object'], n2.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6; bp.inputs['Distance'].default_value = 0.05
    nt.links.new(n2.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m

def fish_mat(name, top, belly, metal=0.6, rough=0.22, irid=(0.3, 0.8, 1.0, 1), zrange=0.08):
    m = P.new_mat(name, top, rough, metal); nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -zrange; mr.inputs['From Max'].default_value = zrange * 0.6
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs[6].default_value = belly; mix.inputs[7].default_value = top
    nt.links.new(mr.outputs[0], mix.inputs['Factor'])
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.6
    mix2 = nt.nodes.new('ShaderNodeMix'); mix2.data_type = 'RGBA'; mix2.inputs[7].default_value = irid
    nt.links.new(mix.outputs[2], mix2.inputs[6])
    sc_ = nt.nodes.new('ShaderNodeMath'); sc_.operation = 'MULTIPLY'; sc_.inputs[1].default_value = 0.35; nt.links.new(lw.outputs['Facing'], sc_.inputs[0]); nt.links.new(sc_.outputs[0], mix2.inputs['Factor'])
    nt.links.new(mix2.outputs[2], b.inputs['Base Color'])
    b.inputs['Coat Weight'].default_value = 0.4; b.inputs['Coat Roughness'].default_value = 0.1
    return m

M_SAND = sand_mat(); M_ROCK = rock_mat()
M_FUS = fish_mat('MAT_FishFusilier', (0.25, 0.45, 0.95, 1), (0.85, 0.88, 0.9, 1), 0.7, 0.2, zrange=0.025)
M_FUS_FIN = P.new_mat('MAT_FishFusilierFin', (0.95, 0.75, 0.2, 1), 0.4, 0.3, alpha=0.85)
M_TANG = fish_mat('MAT_FishTang', (0.95, 0.75, 0.05, 1), (0.98, 0.85, 0.2, 1), 0.5, 0.3, (0.2, 0.5, 1.0, 1), zrange=0.1)
M_TANG_FIN = P.new_mat('MAT_FishTangFin', (0.1, 0.25, 0.85, 1), 0.35, 0.4, alpha=0.9)
M_JACK = fish_mat('MAT_FishJack', (0.04, 0.06, 0.16, 1), (0.8, 0.82, 0.85, 1), 0.7, 0.18, (0.4, 0.9, 1.0, 1), zrange=0.09)
M_JACK_FIN = P.new_mat('MAT_FishJackFin', (0.05, 0.05, 0.08, 1), 0.4, 0.5, alpha=0.85)
M_EYE = P.new_mat('MAT_FishEye', (0.01, 0.01, 0.01, 1), 0.08, 0.0, coat=1.0)
M_BUBBLE = P.new_mat('MAT_Bubble', (1, 1, 1, 1), 0.0, 0.0, transmission=1.0, ior=0.75)

def store_tip(obj, mode='z'):
    me = obj.data
    if 'tip' in me.attributes: me.attributes.remove(me.attributes['tip'])
    a = me.attributes.new('tip', 'FLOAT', 'POINT')
    zs = [v.co.z for v in me.vertices]; z0, z1 = min(zs), max(zs)
    for i, v in enumerate(me.vertices):
        a.data[i].value = max(0.0, min(1.0, (v.co.z - z0) / max(1e-6, z1 - z0)))

def smooth_all(obj):
    for p in obj.data.polygons: p.use_smooth = True

# ----------------------------------------------------------------- reef floor
def build_floor(col):
    S, N = 60.0, 110
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=N, y_segments=N, size=S / 2)
    for v in bm.verts:
        p = v.co
        ripple = math.sin(p.x * 2.4 + 2.0 * noise.noise(p * 0.08)) * 0.045 * (0.6 + 0.4 * noise.noise(p * 0.3 + Vector((5, 1, 0))))
        mounds = noise.fractal(p * 0.03 + Vector((1, 7, 3)), 1.0, 2.0, 3) * 0.9
        edge = min(1.0, (p.length / 8.0) ** 2)           # keep the centre (reef head base) flat
        v.co.z = -DEPTH + ripple + mounds * edge + 0.02 * noise.noise(p * 1.5)
    for f in bm.faces: f.smooth = True
    o = K.obj_from_bm('REEF_FLOOR', bm, col, [M_SAND])
    return o

# ----------------------------------------------------------------- corals
def staghorn(name, col):
    bm = bmesh.new()
    def branch(p, d, L, r, lvl):
        q = p + d * L
        bm_cyl(bm, r, r * 0.72, L, (p + q) / 2, rot_to(p, q), seg=7, mat=0)
        bm_sphere(bm, r * 0.74, q, subdiv=1, mat=0)
        if lvl < 3:
            for i in range(random.choice((2, 2, 3))):
                perp = d.orthogonal().normalized(); perp.rotate(Quaternion(d, random.uniform(0, 6.283)))
                nd = d.copy(); nd.rotate(Quaternion(perp, math.radians(random.uniform(25, 50))))
                nd = (nd + Vector((0, 0, 0.3))).normalized()
                branch(q, nd, L * random.uniform(0.65, 0.85), r * 0.68, lvl + 1)
    for i in range(3):
        a = i * 2.1 + random.uniform(-0.3, 0.3)
        d = Vector((math.cos(a) * 0.45, math.sin(a) * 0.45, 1.0)).normalized()
        branch(Vector((math.cos(a) * 0.06, math.sin(a) * 0.06, 0)), d, 0.42, 0.045, 1)
    o = K.obj_from_bm(name, bm, col, [M_STAG]); store_tip(o); return o

def table_coral(name, col):
    bm = bmesh.new()
    bm_cyl(bm, 0.13, 0.1, 0.5, (0, 0, 0.25), seg=12, mat=0)
    vs = bm_sphere(bm, 1.0, (0, 0, 0.6), subdiv=3, mat=0, scale=(0.9, 0.8, 0.1))
    for v in vs:
        if v.co.z > 0.6: v.co.z += 0.05 * noise.noise(v.co * 6) + 0.03 * abs(noise.noise(v.co * 14))
        rr = Vector((v.co.x, v.co.y, 0)).length; v.co.x *= 1 + 0.12 * noise.noise(v.co * 3 + Vector((2, 2, 2))); v.co.y *= 1 + 0.12 * noise.noise(v.co * 3 + Vector((4, 0, 1)))
    o = K.obj_from_bm(name, bm, col, [M_TABLE]); store_tip(o); return o

def brain_coral(name, col):
    bm = bmesh.new(); vs = bm_sphere(bm, 0.7, (0, 0, 0.1), subdiv=4, mat=0, scale=(1, 0.9, 0.7))
    for v in vs:
        n = (v.co - Vector((0, 0, 0.1))).normalized()
        g = noise.noise(v.co * 2.6); ridges = abs(math.sin(g * 9.0 + 0.6 * noise.noise(v.co * 7)))
        v.co += n * (0.05 * ridges + 0.015 * noise.noise(v.co * 10))
    o = K.obj_from_bm(name, bm, col, [M_BRAIN]); store_tip(o); return o

def sea_fan(name, col):
    bm = bmesh.new(); res = bmesh.ops.create_grid(bm, x_segments=44, y_segments=36, size=0.5)
    fan = res['verts']
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, 0.72)) @ rx(90) @ Matrix.Diagonal((1.5, 1.2, 1, 1)), verts=fan)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median(); ex = (c.x / 0.72) ** 2 + ((c.z - 0.72) / 0.6) ** 2
        n = noise.fractal(c * 7.0 + Vector((3, 3, 3)), 1.0, 2.2, 3)
        if ex > 1.0 or (n > 0.18 and ex > 0.05): kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    for v in bm.verts: v.co.y += 0.18 * (v.co.x ** 2) - 0.04 * noise.noise(v.co * 5)
    bm_cyl(bm, 0.04, 0.025, 0.25, (0, 0, 0.12), seg=8, mat=0)
    o = K.obj_from_bm(name, bm, col, [M_FAN]); store_tip(o)
    s = o.modifiers.new('Thick', 'SOLIDIFY'); s.thickness = 0.012; s.offset = 0
    return o

def tube_sponge(name, col, mat):
    bm = bmesh.new()
    for i in range(random.randint(5, 7)):
        a = random.uniform(0, 6.283); rr = random.uniform(0.05, 0.3); h = random.uniform(0.45, 1.1); r = random.uniform(0.07, 0.13)
        base = Vector((math.cos(a) * rr, math.sin(a) * rr, -0.05)); top = base + Vector((random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15), h))
        vs = bm_cyl(bm, r * 1.1, r, h, (base + top) / 2, rot_to(base, top), seg=12, mat=0, caps=False)
        for v in vs: v.co += Vector((noise.noise(v.co * 9), noise.noise(v.co * 9 + Vector((3, 1, 2))), 0)) * 0.012
    o = K.obj_from_bm(name, bm, col, [mat]); store_tip(o)
    s = o.modifiers.new('Wall', 'SOLIDIFY'); s.thickness = 0.03; s.offset = -1
    return o

def soft_tuft(name, col, mat):
    bm = bmesh.new()
    for i in range(10):
        a = i * 0.63 + random.uniform(-0.3, 0.3); rr = random.uniform(0.05, 0.3)
        c = Vector((math.cos(a) * rr, math.sin(a) * rr, random.uniform(0.35, 0.85))); R = random.uniform(0.13, 0.24)
        vs = bm_sphere(bm, R, c, subdiv=2, mat=0, scale=(1, 1, 0.9))
        off = Vector((random.uniform(0, 9), random.uniform(0, 9), random.uniform(0, 9)))
        for v in vs:
            n = (v.co - c).normalized(); v.co = c + n * R * (1 + 0.6 * noise.noise(n * 2.0 + off) + 0.3 * abs(noise.noise(n * 5 + off)))
        bm_cyl(bm, 0.035, 0.02, c.length, c / 2, rot_to(Vector((0, 0, 0)), c), seg=6, mat=0)
    o = K.obj_from_bm(name, bm, col, [mat]); store_tip(o); return o

def anemone(name, col):
    bm = bmesh.new(); bm_sphere(bm, 0.28, (0, 0, 0.0), subdiv=2, mat=1, scale=(1, 1, 0.5))
    for i in range(85):
        n = Vector((random.gauss(0, 1), random.gauss(0, 1), abs(random.gauss(0, 1)) + 0.25)).normalized()
        p0 = Vector((n.x * 0.26, n.y * 0.26, n.z * 0.13)); d = (n + Vector((0, 0, 0.5))).normalized()
        L = random.uniform(0.22, 0.4); mid = p0 + d * L * 0.5; d2 = (d + Vector((random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4), 0.0))).normalized()
        end = mid + d2 * L * 0.5
        bm_cyl(bm, 0.022, 0.014, L * 0.5, (p0 + mid) / 2, rot_to(p0, mid), seg=6, mat=0, caps=False)
        bm_cyl(bm, 0.014, 0.006, L * 0.5, (mid + end) / 2, rot_to(mid, end), seg=6, mat=0, caps=True)
    o = K.obj_from_bm(name, bm, col, [M_ANEM, M_ANEM_BASE]); store_tip(o); return o

def build_coral_kit():
    col = K.coll('CORAL_KIT')
    corals = [staghorn('CORAL_STAGHORN', col), table_coral('CORAL_TABLE', col), brain_coral('CORAL_BRAIN', col), sea_fan('CORAL_SEAFAN', col),
              tube_sponge('CORAL_TUBE_SPONGE', col, M_SPONGE_P), tube_sponge('CORAL_TUBE_SPONGE_YELLOW', col, M_SPONGE_Y),
              soft_tuft('CORAL_SOFT_PINK', col, M_SOFT_PINK), soft_tuft('CORAL_SOFT_ORANGE', col, M_SOFT_ORANGE), anemone('CORAL_ANEMONE', col)]
    for i, o in enumerate(corals):
        smooth_all(o); o.location = (30 + i * 2.2, 25, -DEPTH)       # parked in a row outside the hero area
    # bias the random picker toward the hero soft corals: linked duplicates (same mesh data)
    for src, n in (('CORAL_SOFT_PINK', 2), ('CORAL_SOFT_ORANGE', 2), ('CORAL_SEAFAN', 1)):
        for k in range(n):
            d = bpy.data.objects[src].copy(); d.name = f'{src}_DUP{k+1}'; col.objects.link(d); d.location = (30 + (len(corals) + k) * 2.2, 27 + k, -DEPTH)
    return col, corals

# ----------------------------------------------------------------- reef head + scatter GN
def build_reef_head(col):
    bm = bmesh.new(); R = 3.0; vs = bm_sphere(bm, R, (0, 0, 0), subdiv=5, mat=0)
    for v in vs:
        n = v.co.normalized(); p = v.co / R
        big = noise.noise(p * 0.9 + Vector((3.1, 1.7, 0.4)))
        mid = noise.fractal(p * 2.4 + Vector((0.5, 0.2, 9.0)), 1.0, 2.0, 3)
        ridged = noise.ridged_multi_fractal(p * 1.3 + Vector((2, 5, 1)), 1.0, 2.0, 4, 1.0, 2.0)
        crev = max(0.0, 0.5 - abs(noise.noise(p * 1.7 + Vector((7, 2, 5)))) * 3.5)
        big2 = noise.noise(p * 1.4 + Vector((11.0, 4.0, 2.0)))
        r = 1 + 0.5 * big + 0.25 * big2 + 0.12 * mid + 0.08 * (ridged - 1.0) - 0.28 * crev
        r *= 1 + 0.5 * max(0.0, -n.z) ** 1.5 + 0.15 * max(0.0, n.z) ** 3   # skirt at the base, small cap on top
        v.co = n * R * r
    bmesh.ops.transform(bm, matrix=Matrix.Diagonal((1.35, 0.95, 1.4, 1)), verts=vs)
    zs = [v.co.z for v in vs]; zmin, zmax = min(zs), max(zs)
    for v in vs:
        v.co.z = (v.co.z - zmin) / (zmax - zmin) * 8.2 - 0.8 - DEPTH   # ~7.4 m above the seabed, 0.8 m buried
    for f in bm.faces: f.smooth = True
    o = K.obj_from_bm('REEF_HEAD', bm, col, [M_ROCK])
    return o

def coral_scatter_group(name='GN_CoralScatter'):
    """Inputs: Geometry, Corals (collection), Density, Min Distance, Seed, Min Scale, Max Scale, Up Bias, Max Radius (0 = all).
    Output: rock + coral instances aligned to the surface normal."""
    if name in bpy.data.node_groups: return bpy.data.node_groups[name]
    t = bpy.data.node_groups.new(name, 'GeometryNodeTree'); it = t.interface
    it.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    it.new_socket('Corals', in_out='INPUT', socket_type='NodeSocketCollection')
    for nm, dv, mn, mx in (('Density', 1.6, 0.0, 1000.0), ('Min Distance', 0.55, 0.0, 100.0), ('Min Scale', 0.6, 0.0, 100.0), ('Max Scale', 1.3, 0.0, 100.0), ('Up Bias', 0.35, 0.0, 1.0), ('Max Radius', 0.0, 0.0, 10000.0)):
        s = it.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = dv; s.min_value = mn; s.max_value = mx
    s = it.new_socket('Seed', in_out='INPUT', socket_type='NodeSocketInt'); s.default_value = 0
    it.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    g = P.GN(t); gi = g.n('NodeGroupInput'); go = g.n('NodeGroupOutput'); go.location = (2600, 0); I = lambda s: gi.outputs[s]
    nrm = g.n('GeometryNodeInputNormal'); sepn = g.n('ShaderNodeSeparateXYZ'); g.link(nrm.outputs[0], sepn.inputs[0])
    up_ok = g.n('FunctionNodeCompare', dtype='FLOAT', op='GREATER_THAN'); g.link(sepn.outputs['Z'], up_ok.inputs[0]); up_ok.inputs[1].default_value = -0.25
    pos = g.n('GeometryNodeInputPosition'); dist = g.n('ShaderNodeVectorMath', op='LENGTH'); g.link(pos.outputs[0], dist.inputs[0])
    in_r = g.n('FunctionNodeCompare', dtype='FLOAT', op='LESS_THAN'); g.link(dist.outputs['Value'], in_r.inputs[0]); g.link(I('Max Radius'), in_r.inputs[1])
    no_r = g.n('FunctionNodeCompare', dtype='FLOAT', op='LESS_EQUAL'); g.link(I('Max Radius'), no_r.inputs[0]); no_r.inputs[1].default_value = 0.0
    r_ok = g.n('FunctionNodeBooleanMath', op='OR'); g.link(in_r.outputs[0], r_ok.inputs[0]); g.link(no_r.outputs[0], r_ok.inputs[1])
    sel = g.n('FunctionNodeBooleanMath', op='AND'); g.link(up_ok.outputs[0], sel.inputs[0]); g.link(r_ok.outputs[0], sel.inputs[1])
    dp = g.n('GeometryNodeDistributePointsOnFaces'); dp.distribute_method = 'POISSON'
    g.link(I('Geometry'), dp.inputs['Mesh']); g.link(sel.outputs[0], dp.inputs['Selection']); g.link(I('Min Distance'), dp.inputs['Distance Min'])
    g.link(I('Density'), dp.inputs['Density Max']); dp.inputs['Density Factor'].default_value = 1.0; g.link(I('Seed'), dp.inputs['Seed'])
    idx = g.n('GeometryNodeInputIndex')
    rnd_i = g.n('FunctionNodeRandomValue', dtype='INT'); rnd_i.inputs[4].default_value = 0; rnd_i.inputs[5].default_value = 10000; g.link(idx.outputs[0], rnd_i.inputs['ID']); g.link(I('Seed'), rnd_i.inputs['Seed'])
    rnd_s = g.n('FunctionNodeRandomValue', dtype='FLOAT'); g.link(I('Min Scale'), rnd_s.inputs[2]); g.link(I('Max Scale'), rnd_s.inputs[3]); g.link(idx.outputs[0], rnd_s.inputs['ID'])
    seed2 = g.n('ShaderNodeMath', op='ADD'); g.link(I('Seed'), seed2.inputs[0]); seed2.inputs[1].default_value = 11; g.link(seed2.outputs[0], rnd_s.inputs['Seed'])
    rnd_a = g.n('FunctionNodeRandomValue', dtype='FLOAT'); rnd_a.inputs[2].default_value = 0.0; rnd_a.inputs[3].default_value = 6.283; g.link(idx.outputs[0], rnd_a.inputs['ID'])
    seed3 = g.n('ShaderNodeMath', op='ADD'); g.link(I('Seed'), seed3.inputs[0]); seed3.inputs[1].default_value = 23; g.link(seed3.outputs[0], rnd_a.inputs['Seed'])
    yaw = g.n('ShaderNodeCombineXYZ'); g.link(rnd_a.outputs[1], yaw.inputs['Z'])
    # alignment vector: mix(normal, up, bias)
    mixv = g.n('ShaderNodeMix'); mixv.data_type = 'VECTOR'; g.link(I('Up Bias'), mixv.inputs['Factor']); g.link(dp.outputs['Normal'], mixv.inputs[4]); mixv.inputs[5].default_value = (0, 0, 1)
    ae = g.n('FunctionNodeAlignEulerToVector'); ae.axis = 'Z'; ae.pivot_axis = 'AUTO'; g.link(yaw.outputs[0], ae.inputs['Rotation']); g.link(mixv.outputs[1], ae.inputs['Vector'])
    cinfo = g.n('GeometryNodeCollectionInfo'); cinfo.transform_space = 'ORIGINAL'; g.link(I('Corals'), cinfo.inputs['Collection']); cinfo.inputs['Separate Children'].default_value = True; cinfo.inputs['Reset Children'].default_value = True
    inst = g.n('GeometryNodeInstanceOnPoints'); g.link(dp.outputs['Points'], inst.inputs['Points']); g.link(cinfo.outputs[0], inst.inputs['Instance'])
    inst.inputs['Pick Instance'].default_value = True; g.link(rnd_i.outputs[2], inst.inputs['Instance Index']); g.link(ae.outputs[0], inst.inputs['Rotation'])
    scv = g.n('ShaderNodeCombineXYZ'); [g.link(rnd_s.outputs[1], scv.inputs[i]) for i in range(3)]; g.link(scv.outputs[0], inst.inputs['Scale'])
    join = g.n('GeometryNodeJoinGeometry'); g.link(I('Geometry'), join.inputs[0]); g.link(inst.outputs[0], join.inputs[0]); g.link(join.outputs[0], go.inputs[0])
    return t

def set_inputs(md, vals):
    for s in md.node_group.interface.items_tree:
        if s.item_type == 'SOCKET' and s.in_out == 'INPUT' and s.name in vals:
            v = vals[s.name]; md[s.identifier] = v if isinstance(v, (bpy.types.ID, int)) and not isinstance(v, float) else float(v)
    return md

def drive_time(md, name='Time', expr='frame / 24.0'):
    ident = P.mod_input_id(md, name); md[ident] = 0.0
    fc = md.driver_add(f'["{ident}"]'); fc.driver.type = 'SCRIPTED'; fc.driver.expression = expr
    return fc

# ----------------------------------------------------------------- fish
def make_fish(name, col, L, hw, hh, m_body, m_fin, fork=1.0, dorsal_h=1.2, tall=False, pos=(0, 0, 0)):
    bm = bmesh.new(); a = L * 0.42
    body = bm_sphere(bm, 1.0, (0, 0, 0), subdiv=3, mat=0, scale=(a, hw, hh))
    for v in body:
        t = v.co.x / a
        if t > 0: f = 1 - 0.3 * t ** 2; v.co.z *= (1 - 0.18 * t ** 2)
        else: f = 1 - 0.7 * abs(t) ** 2.0
        v.co.y *= f; v.co.z *= f if t < 0 else 1.0
    def poly(pts, mat):
        f = bm.faces.new([bm.verts.new(Vector(p)) for p in pts]); f.material_index = mat; f.smooth = False; return f
    xb = -a * 0.98; tl = L * 0.2
    if fork > 0.3:   # forked tail
        poly([(xb, 0, hh * 0.25), (xb - tl, 0, hh * (0.6 + 0.7 * fork)), (xb - tl * 0.45, 0, 0.0), (xb - tl, 0, -hh * (0.6 + 0.7 * fork)), (xb, 0, -hh * 0.25)], 1)
    else:            # fan tail
        poly([(xb, 0, hh * 0.3), (xb - tl * 0.9, 0, hh * 0.9), (xb - tl, 0, 0.0), (xb - tl * 0.9, 0, -hh * 0.9), (xb, 0, -hh * 0.3)], 1)
    x0, x1 = -a * 0.55, a * 0.35                                        # dorsal fin
    if tall: poly([(x0, 0, hh * 0.85), (x0 - 0.05 * a, 0, hh * dorsal_h), (x1 * 0.2, 0, hh * (dorsal_h + 0.15)), (x1, 0, hh * dorsal_h * 0.8), (x1, 0, hh * 0.88)], 1)
    else: poly([(x0, 0, hh * 0.7), (x0 + 0.1 * a, 0, hh * dorsal_h), (x1, 0, hh * dorsal_h * 0.55), (x1, 0, hh * 0.9)], 1)
    poly([(x0 + 0.1 * a, 0, -hh * 0.7), (x0 - 0.05 * a, 0, -hh * (0.6 + 0.4 * (dorsal_h - 1))), (x1 * 0.4, 0, -hh * 0.9)], 1)   # anal fin
    for sy in (-1, 1):                                                   # pectoral fins
        poly([(a * 0.3, sy * hw * 0.95, -hh * 0.1), (a * 0.05, sy * hw * 1.9, -hh * 0.5), (a * 0.0, sy * hw * 1.0, -hh * 0.35)], 1)
    for sy in (-1, 1): bm_sphere(bm, hh * 0.17, (a * 0.62, sy * hw * 0.8, hh * 0.22), subdiv=1, mat=2)   # eyes
    o = K.obj_from_bm(name, bm, col, [m_body, m_fin, M_EYE], loc=pos)
    for p in o.data.polygons: p.use_smooth = (len(p.vertices) == 3 and p.material_index != 1)
    return o

def build_fish_kit():
    col = K.coll('FISH_KIT'); base = (30, 18, -DEPTH + 2)
    fus = make_fish('FISH_FUSILIER', col, 0.2, 0.014, 0.026, M_FUS, M_FUS_FIN, fork=1.0, dorsal_h=1.3, pos=(base[0] - 0.5, base[1], base[2] + 0.12))
    jack = make_fish('FISH_JACK', col, 0.5, 0.04, 0.09, M_JACK, M_JACK_FIN, fork=1.2, dorsal_h=1.4, pos=(base[0] + 0.25, base[1], base[2] - 0.1))
    tang = make_fish('FISH_TANG', col, 0.25, 0.02, 0.085, M_TANG, M_TANG_FIN, fork=0.0, dorsal_h=1.55, tall=True, pos=(base[0] - 0.5, base[1], base[2] - 0.2))
    return col, [fus, jack, tang]

def fish_school_group(name='GN_FishSchool'):
    """Inputs: Count, Radius, Time, Speed, Fish (collection), Fish Index (-1 = random), Fish Scale, Seed, Flatten, Spread.
    Points wander in a sphere (rotating about the centre + 4D noise), instances aligned to velocity, with tail-wag yaw."""
    if name in bpy.data.node_groups: return bpy.data.node_groups[name]
    t = bpy.data.node_groups.new(name, 'GeometryNodeTree'); it = t.interface
    it.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    s = it.new_socket('Count', in_out='INPUT', socket_type='NodeSocketInt'); s.default_value = 200; s.min_value = 0
    for nm, dv in (('Radius', 5.0), ('Time', 0.0), ('Speed', 1.0), ('Fish Scale', 1.0), ('Flatten', 0.5), ('Spread', 0.6)):
        s = it.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = dv
    it.new_socket('Fish', in_out='INPUT', socket_type='NodeSocketCollection')
    s = it.new_socket('Fish Index', in_out='INPUT', socket_type='NodeSocketInt'); s.default_value = 0; s.min_value = -1
    s = it.new_socket('Seed', in_out='INPUT', socket_type='NodeSocketInt'); s.default_value = 0
    it.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    g = P.GN(t); gi = g.n('NodeGroupInput'); go = g.n('NodeGroupOutput'); go.location = (4800, 0); I = lambda s: gi.outputs[s]
    pts = g.n('GeometryNodePoints'); g.link(I('Count'), pts.inputs['Count'])
    idx = g.n('GeometryNodeInputIndex')
    rv = g.n('FunctionNodeRandomValue', dtype='FLOAT_VECTOR'); rv.inputs[0].default_value = (-1, -1, -1); rv.inputs[1].default_value = (1, 1, 1); g.link(idx.outputs[0], rv.inputs['ID']); g.link(I('Seed'), rv.inputs['Seed'])
    rp = g.n('FunctionNodeRandomValue', dtype='FLOAT'); rp.inputs[2].default_value = 0.0; rp.inputs[3].default_value = 1.0; g.link(idx.outputs[0], rp.inputs['ID'])
    sd1 = g.n('ShaderNodeMath', op='ADD'); g.link(I('Seed'), sd1.inputs[0]); sd1.inputs[1].default_value = 101; g.link(sd1.outputs[0], rp.inputs['Seed'])
    phase = rp.outputs[1]
    flat = g.n('ShaderNodeCombineXYZ'); flat.inputs['X'].default_value = 1; flat.inputs['Y'].default_value = 1; g.link(I('Flatten'), flat.inputs['Z'])
    base0 = g.n('ShaderNodeVectorMath', op='MULTIPLY'); g.link(rv.outputs[0], base0.inputs[0]); g.link(flat.outputs[0], base0.inputs[1])
    base = g.n('ShaderNodeVectorMath', op='SCALE'); g.link(base0.outputs[0], base.inputs[0]); g.link(I('Radius'), base.inputs['Scale'])
    nvec = g.n('ShaderNodeVectorMath', op='SCALE'); g.link(rv.outputs[0], nvec.inputs[0]); nvec.inputs['Scale'].default_value = 1.3   # noise lookup per fish
    wamp = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(I('Radius'), wamp.inputs[0]); g.link(I('Spread'), wamp.inputs[1])
    def pos_at(T):
        ts = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(T, ts.inputs[0]); g.link(I('Speed'), ts.inputs[1])
        ang = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(ts.outputs[0], ang.inputs[0]); ang.inputs[1].default_value = 0.12; g.link(phase, ang.inputs[2])
        rot = g.n('ShaderNodeVectorRotate'); rot.rotation_type = 'Z_AXIS'; g.link(base.outputs[0], rot.inputs['Vector']); g.link(ang.outputs[0], rot.inputs['Angle'])
        w = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(ts.outputs[0], w.inputs[0]); w.inputs[1].default_value = 0.3
        ph7 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(phase, ph7.inputs[0]); ph7.inputs[1].default_value = 7.0; g.link(ph7.outputs[0], w.inputs[2])
        nz = g.n('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'; nz.inputs['Scale'].default_value = 1.0; nz.inputs['Detail'].default_value = 1.0; nz.inputs['Roughness'].default_value = 0.4
        g.link(nvec.outputs[0], nz.inputs['Vector']); g.link(w.outputs[0], nz.inputs['W'])
        cen = g.n('ShaderNodeVectorMath', op='SUBTRACT'); g.link(nz.outputs['Color'], cen.inputs[0]); cen.inputs[1].default_value = (0.5, 0.5, 0.5)
        wander = g.n('ShaderNodeVectorMath', op='SCALE'); g.link(cen.outputs[0], wander.inputs[0]); g.link(wamp.outputs[0], wander.inputs['Scale'])
        p = g.n('ShaderNodeVectorMath', op='ADD'); g.link(rot.outputs[0], p.inputs[0]); g.link(wander.outputs[0], p.inputs[1])
        return p.outputs[0]
    p1 = pos_at(I('Time'))
    t2 = g.n('ShaderNodeMath', op='ADD'); g.link(I('Time'), t2.inputs[0]); t2.inputs[1].default_value = 0.08
    p2 = pos_at(t2.outputs[0])
    vel = g.n('ShaderNodeVectorMath', op='SUBTRACT'); g.link(p2, vel.inputs[0]); g.link(p1, vel.inputs[1])
    veln = g.n('ShaderNodeVectorMath', op='NORMALIZE'); g.link(vel.outputs[0], veln.inputs[0])
    sp = g.n('GeometryNodeSetPosition'); g.link(pts.outputs[0], sp.inputs['Geometry']); g.link(p1, sp.inputs['Position'])
    ae1 = g.n('FunctionNodeAlignEulerToVector'); ae1.axis = 'X'; ae1.pivot_axis = 'AUTO'; g.link(veln.outputs[0], ae1.inputs['Vector'])
    ae2 = g.n('FunctionNodeAlignEulerToVector'); ae2.axis = 'Z'; ae2.pivot_axis = 'X'; g.link(ae1.outputs[0], ae2.inputs['Rotation']); ae2.inputs['Vector'].default_value = (0, 0, 1)
    # tail wag: yaw = sin(time*speed*9 + phase*2pi) * 0.14
    ts = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(I('Time'), ts.inputs[0]); g.link(I('Speed'), ts.inputs[1])
    wp = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(ts.outputs[0], wp.inputs[0]); wp.inputs[1].default_value = 9.0
    ph2 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(phase, ph2.inputs[0]); ph2.inputs[1].default_value = 6.283; g.link(ph2.outputs[0], wp.inputs[2])
    sn = g.n('ShaderNodeMath', op='SINE'); g.link(wp.outputs[0], sn.inputs[0])
    wag = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(sn.outputs[0], wag.inputs[0]); wag.inputs[1].default_value = 0.14
    wagv = g.n('ShaderNodeCombineXYZ'); g.link(wag.outputs[0], wagv.inputs['Z'])
    re = g.n('FunctionNodeRotateEuler'); re.rotation_type = 'EULER'; re.space = 'LOCAL'; g.link(ae2.outputs[0], re.inputs['Rotation']); g.link(wagv.outputs[0], re.inputs['Rotate By'])
    cinfo = g.n('GeometryNodeCollectionInfo'); cinfo.transform_space = 'ORIGINAL'; g.link(I('Fish'), cinfo.inputs['Collection']); cinfo.inputs['Separate Children'].default_value = True; cinfo.inputs['Reset Children'].default_value = True
    rnd_i = g.n('FunctionNodeRandomValue', dtype='INT'); rnd_i.inputs[4].default_value = 0; rnd_i.inputs[5].default_value = 10000; g.link(idx.outputs[0], rnd_i.inputs['ID']); g.link(I('Seed'), rnd_i.inputs['Seed'])
    neg = g.n('FunctionNodeCompare', dtype='INT', op='LESS_THAN'); g.link(I('Fish Index'), neg.inputs[2]); neg.inputs[3].default_value = 0
    sw = g.n('GeometryNodeSwitch'); sw.input_type = 'INT'; g.link(neg.outputs[0], sw.inputs['Switch']); g.link(I('Fish Index'), sw.inputs['False']); g.link(rnd_i.outputs[2], sw.inputs['True'])
    inst = g.n('GeometryNodeInstanceOnPoints'); g.link(sp.outputs[0], inst.inputs['Points']); g.link(cinfo.outputs[0], inst.inputs['Instance'])
    inst.inputs['Pick Instance'].default_value = True; g.link(sw.outputs[0], inst.inputs['Instance Index']); g.link(re.outputs[0], inst.inputs['Rotation'])
    rs = g.n('FunctionNodeRandomValue', dtype='FLOAT'); rs.inputs[2].default_value = 0.75; rs.inputs[3].default_value = 1.25; g.link(idx.outputs[0], rs.inputs['ID'])
    sd2 = g.n('ShaderNodeMath', op='ADD'); g.link(I('Seed'), sd2.inputs[0]); sd2.inputs[1].default_value = 202; g.link(sd2.outputs[0], rs.inputs['Seed'])
    scl = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(rs.outputs[1], scl.inputs[0]); g.link(I('Fish Scale'), scl.inputs[1])
    scv = g.n('ShaderNodeCombineXYZ'); [g.link(scl.outputs[0], scv.inputs[i]) for i in range(3)]; g.link(scv.outputs[0], inst.inputs['Scale'])
    g.link(inst.outputs[0], go.inputs[0])
    return t

def bubbles_group(name='GN_Bubbles'):
    """Inputs: Geometry (ignored), Time, Count, Height, Radius, Speed, Size, Material. Rising wobbling bubble spheres."""
    if name in bpy.data.node_groups: return bpy.data.node_groups[name]
    t = bpy.data.node_groups.new(name, 'GeometryNodeTree'); it = t.interface
    it.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    s = it.new_socket('Count', in_out='INPUT', socket_type='NodeSocketInt'); s.default_value = 60
    for nm, dv in (('Time', 0.0), ('Height', 10.0), ('Radius', 0.25), ('Speed', 1.2), ('Size', 0.035)):
        s = it.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = dv
    it.new_socket('Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    it.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    g = P.GN(t); gi = g.n('NodeGroupInput'); go = g.n('NodeGroupOutput'); go.location = (3400, 0); I = lambda s: gi.outputs[s]
    pts = g.n('GeometryNodePoints'); g.link(I('Count'), pts.inputs['Count'])
    idx = g.n('GeometryNodeInputIndex')
    r1 = g.n('FunctionNodeRandomValue', dtype='FLOAT'); r1.inputs[2].default_value = 0; r1.inputs[3].default_value = 1; g.link(idx.outputs[0], r1.inputs['ID']); r1.inputs['Seed'].default_value = 1
    r2 = g.n('FunctionNodeRandomValue', dtype='FLOAT'); r2.inputs[2].default_value = 0; r2.inputs[3].default_value = 1; g.link(idx.outputs[0], r2.inputs['ID']); r2.inputs['Seed'].default_value = 2
    r3 = g.n('FunctionNodeRandomValue', dtype='FLOAT'); r3.inputs[2].default_value = 0; r3.inputs[3].default_value = 6.283; g.link(idx.outputs[0], r3.inputs['ID']); r3.inputs['Seed'].default_value = 3
    # z = fract(rand + time*speed*(0.7+0.6*rand2)/height) * height
    sp = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(r2.outputs[1], sp.inputs[0]); sp.inputs[1].default_value = 0.6; sp.inputs[2].default_value = 0.7
    v = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(sp.outputs[0], v.inputs[0]); g.link(I('Speed'), v.inputs[1])
    tv = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(v.outputs[0], tv.inputs[0]); g.link(I('Time'), tv.inputs[1])
    th = g.n('ShaderNodeMath', op='DIVIDE'); g.link(tv.outputs[0], th.inputs[0]); g.link(I('Height'), th.inputs[1])
    ph = g.n('ShaderNodeMath', op='ADD'); g.link(th.outputs[0], ph.inputs[0]); g.link(r1.outputs[1], ph.inputs[1])
    fr = g.n('ShaderNodeMath', op='FRACT'); g.link(ph.outputs[0], fr.inputs[0])
    z = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(fr.outputs[0], z.inputs[0]); g.link(I('Height'), z.inputs[1])
    # xy = radius*rand*dir + wobble(sin(time*3 + angle))*0.08*z/height
    wob = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(I('Time'), wob.inputs[0]); wob.inputs[1].default_value = 3.0; g.link(r3.outputs[1], wob.inputs[2])
    sw = g.n('ShaderNodeMath', op='SINE'); g.link(wob.outputs[0], sw.inputs[0]); cw = g.n('ShaderNodeMath', op='COSINE'); g.link(wob.outputs[0], cw.inputs[0])
    wa = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(fr.outputs[0], wa.inputs[0]); wa.inputs[1].default_value = 0.12
    wx = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(sw.outputs[0], wx.inputs[0]); g.link(wa.outputs[0], wx.inputs[1])
    wy = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(cw.outputs[0], wy.inputs[0]); g.link(wa.outputs[0], wy.inputs[1])
    cx = g.n('ShaderNodeMath', op='COSINE'); g.link(r3.outputs[1], cx.inputs[0]); sy = g.n('ShaderNodeMath', op='SINE'); g.link(r3.outputs[1], sy.inputs[0])
    rr = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(r2.outputs[1], rr.inputs[0]); g.link(I('Radius'), rr.inputs[1])
    px = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(cx.outputs[0], px.inputs[0]); g.link(rr.outputs[0], px.inputs[1]); g.link(wx.outputs[0], px.inputs[2])
    py = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(sy.outputs[0], py.inputs[0]); g.link(rr.outputs[0], py.inputs[1]); g.link(wy.outputs[0], py.inputs[2])
    pos = g.n('ShaderNodeCombineXYZ'); g.link(px.outputs[0], pos.inputs['X']); g.link(py.outputs[0], pos.inputs['Y']); g.link(z.outputs[0], pos.inputs['Z'])
    setp = g.n('GeometryNodeSetPosition'); g.link(pts.outputs[0], setp.inputs['Geometry']); g.link(pos.outputs[0], setp.inputs['Position'])
    ico = g.n('GeometryNodeMeshIcoSphere'); ico.inputs['Subdivisions'].default_value = 2; ico.inputs['Radius'].default_value = 1.0
    shade = g.n('GeometryNodeSetShadeSmooth'); g.link(ico.outputs[0], shade.inputs['Geometry'])
    sm = g.n('GeometryNodeSetMaterial'); g.link(shade.outputs[0], sm.inputs['Geometry']); g.link(I('Material'), sm.inputs['Material'])
    inst = g.n('GeometryNodeInstanceOnPoints'); g.link(setp.outputs[0], inst.inputs['Points']); g.link(sm.outputs[0], inst.inputs['Instance'])
    # size: random 0.6..1.4 * Size, growing a bit as they rise
    ss = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(r1.outputs[1], ss.inputs[0]); ss.inputs[1].default_value = 0.8; ss.inputs[2].default_value = 0.6
    grow = g.n('ShaderNodeMath', op='MULTIPLY_ADD'); g.link(fr.outputs[0], grow.inputs[0]); grow.inputs[1].default_value = 0.5; grow.inputs[2].default_value = 1.0
    s1 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(ss.outputs[0], s1.inputs[0]); g.link(grow.outputs[0], s1.inputs[1])
    s2 = g.n('ShaderNodeMath', op='MULTIPLY'); g.link(s1.outputs[0], s2.inputs[0]); g.link(I('Size'), s2.inputs[1])
    scv = g.n('ShaderNodeCombineXYZ'); [g.link(s2.outputs[0], scv.inputs[i]) for i in range(3)]; g.link(scv.outputs[0], inst.inputs['Scale'])
    g.link(inst.outputs[0], go.inputs[0])
    return t

def empty_mesh_obj(name, col, loc):
    me = bpy.data.meshes.new(name); o = bpy.data.objects.new(name, me); col.objects.link(o); o.location = loc; return o

# ----------------------------------------------------------------- build everything
reef_col = K.coll('REEF')
floor = build_floor(reef_col)
coral_col, corals = build_coral_kit()
head = build_reef_head(reef_col)
gn_scatter = coral_scatter_group()
md = head.modifiers.new('CoralScatter', 'NODES'); md.node_group = gn_scatter
set_inputs(md, {'Corals': coral_col, 'Density': 5.0, 'Min Distance': 0.36, 'Min Scale': 0.4, 'Max Scale': 1.0, 'Up Bias': 0.3, 'Seed': 3})
md2 = floor.modifiers.new('CoralScatter', 'NODES'); md2.node_group = gn_scatter
set_inputs(md2, {'Corals': coral_col, 'Density': 0.12, 'Min Distance': 1.2, 'Min Scale': 0.5, 'Max Scale': 1.0, 'Up Bias': 0.9, 'Max Radius': 14.0, 'Seed': 9})

fish_col, fishes = build_fish_kit()
gn_school = fish_school_group()
school_col = K.coll('FISH_SCHOOLS')
A = empty_mesh_obj('FISH_SCHOOL_A', school_col, (-7, 7, -DEPTH + 7.5))
mA = A.modifiers.new('School', 'NODES'); mA.node_group = gn_school
set_inputs(mA, {'Count': 400, 'Radius': 5.5, 'Speed': 1.0, 'Fish': fish_col, 'Fish Index': 0, 'Fish Scale': 1.0, 'Seed': 1, 'Flatten': 0.45, 'Spread': 0.5}); drive_time(mA)
B = empty_mesh_obj('FISH_SCHOOL_B', school_col, (7, -3, -DEPTH + 5.0))
mB = B.modifiers.new('School', 'NODES'); mB.node_group = gn_school
set_inputs(mB, {'Count': 150, 'Radius': 4.0, 'Speed': 0.8, 'Fish': fish_col, 'Fish Index': 1, 'Fish Scale': 1.0, 'Seed': 7, 'Flatten': 0.5, 'Spread': 0.45}); drive_time(mB)

gn_bub = bubbles_group()
bub = empty_mesh_obj('BUBBLE_EMITTER', reef_col, (2.2, 1.4, -DEPTH + 0.3))
mBub = bub.modifiers.new('Bubbles', 'NODES'); mBub.node_group = gn_bub
set_inputs(mBub, {'Count': 70, 'Height': DEPTH - 0.4, 'Radius': 0.25, 'Speed': 1.2, 'Size': 0.035, 'Material': M_BUBBLE}); drive_time(mBub)

uw = U.setup_underwater(sc, depth=DEPTH)
gobo = U.add_light_shafts(sc, depth=DEPTH, count=28, radius=26.0, sun_tilt=22.0, sun_az=35.0)
sc.frame_set(1)

for n, c in bpy.data.collections.items():
    print(f'[uw] {n:14s} tris={K.collection_tris(c):7d} objects={len(c.all_objects)}')
print('[uw] TOTAL base tris', K.tri_count())
for grp in (gn_scatter, gn_school, gn_bub):
    print(f'[uw] {grp.name} inputs:', [s.name for s in grp.interface.items_tree if s.item_type == 'SOCKET' and s.in_out == 'INPUT'])
dg = bpy.context.evaluated_depsgraph_get()
for o in (head, A, B, bub):
    ev = o.evaluated_get(dg); print(f'[uw] {o.name}: evaluated instances = {len([i for i in dg.object_instances if i.parent and i.parent.original == o])}')
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND); print('[uw] saved', OUT_BLEND)

# ----------------------------------------------------------------- previews
if not NORENDER:
    res = (640, 360) if QUICK else (1280, 720); smp = 16 if QUICK else 48
    # fish kit: small studio shot (water volume off, world only)
    vl = bpy.context.view_layer
    for name in ('REEF', 'CORAL_KIT', 'FISH_SCHOOLS', 'LIGHT_SHAFTS'):
        vl.layer_collection.children[name].exclude = True
    uw['volume'].hide_render = True; uw['surface'].hide_render = True; gobo.hide_render = True; uw['caustic'].hide_render = True
    kl = bpy.data.lights.new('KEY', 'AREA'); kl.energy = 60; kl.size = 1.5; kl.color = (1.0, 0.97, 0.9); ko = bpy.data.objects.new('KEY', kl); sc.collection.objects.link(ko)
    ko.location = (29.6, 17.0, -DEPTH + 3.4); ko.rotation_euler = (math.radians(45), 0, math.radians(-25))
    fl = bpy.data.lights.new('FILL', 'AREA'); fl.energy = 25; fl.size = 3; fl.color = (0.6, 0.8, 1.0); fo = bpy.data.objects.new('FILL', fl); sc.collection.objects.link(fo)
    fo.location = (31.5, 16.5, -DEPTH + 2.6); fo.rotation_euler = (math.radians(70), 0, math.radians(40))
    cam = P.add_camera('CAM_FISH', loc=(30.1, 16.2, -DEPTH + 2.2), target=(30.0, 18.0, -DEPTH + 1.95), lens=50)
    P.setup_render(res=res, samples=smp, exposure=0.0, out=os.path.join(PREVIEWS, 'asset_fish_kit.png'))
    sc.cycles.volume_bounces = 1
    bpy.ops.render.render(write_still=True)
    if not FISHONLY:
        for name in ('REEF', 'FISH_SCHOOLS', 'LIGHT_SHAFTS'): vl.layer_collection.children[name].exclude = False
        for o in (uw['volume'], uw['surface'], gobo, uw['caustic']): o.hide_render = False
        ko.hide_render = True; fo.hide_render = True
        cam2 = P.add_camera('CAM_REEF', loc=(-9.5, -12.5, -DEPTH + 1.9), target=(0.6, 0.3, -DEPTH + 5.2), lens=22)
        sc.camera = cam2; sc.render.filepath = os.path.join(PREVIEWS, 'asset_reef.png')
        sc.view_settings.exposure = -0.4
        bpy.ops.render.render(write_still=True)
    print('[uw] previews done')
