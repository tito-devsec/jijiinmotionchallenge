"""Shared helpers for procedural vehicle assets (Blender 4.5 bpy, headless).
Lofting, primitives, booleans, studio preview rig. Conventions: +Y forward, Z up, metres.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
import posta_lib as P  # noqa: E402


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 1.0
    return sc


def get_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(col)
    return col


def link(obj, col):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def mesh_obj(name, bm, col, mats=()):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    for m in mats: me.materials.append(m)
    link(ob, col)
    return ob


def half_ring(y, half):
    """half = list of (x, z) from bottom centre (x=0) to top centre (x=0). Returns a closed ring of 3D points."""
    k = len(half)
    right = [Vector((x, y, z)) for x, z in half]
    left = [Vector((-x, y, z)) for x, z in reversed(half[1:-1])]
    return right + left


def seg_row(j, k):
    """Row (profile segment) index for ring edge j -> j+1 given a half profile of k points."""
    n = 2 * k - 2
    return j if j < k - 1 else (n - 1 - j)


def loft(name, rings, col, mats, mat_fn=None, cap_mat=(0, 0), close=True):
    """rings: list of equal-length point rings along the loft. mat_fn(i_station, row_index, j) -> material slot index."""
    bm = bmesh.new()
    verts = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0]); k = n // 2 + 1
    for i in range(len(rings) - 1):
        for j in range(n):
            a, b = verts[i][j], verts[i][(j + 1) % n]
            c, d = verts[i + 1][(j + 1) % n], verts[i + 1][j]
            try:
                f = bm.faces.new((a, b, c, d))
            except ValueError:
                continue
            f.material_index = mat_fn(i, seg_row(j, k), j) if mat_fn else 0
    if close:
        f0 = bm.faces.new(verts[0]); f0.material_index = cap_mat[0]
        f1 = bm.faces.new(list(reversed(verts[-1]))); f1.material_index = cap_mat[1]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, col, mats)


def box(name, center, size, col, mat, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = mesh_obj(name, bm, col, [mat])
    ob.location = center
    if rot: ob.rotation_euler = rot
    return ob


def cylinder(name, radius, depth, loc, col, mat, axis='Z', segments=32, radius2=None, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments, radius1=radius, radius2=radius2 if radius2 is not None else radius, depth=depth)
    if axis == 'X': bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Y'), verts=bm.verts)
    elif axis == 'Y': bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, 'X'), verts=bm.verts)
    ob = mesh_obj(name, bm, col, [mat])
    ob.location = loc
    if rot: ob.rotation_euler = rot
    return ob


def tube(name, r_out, r_in, depth, loc, col, mat, axis='X', segments=32):
    """Ring (annulus) extruded along axis."""
    bm = bmesh.new()
    outer = [bm.verts.new((r_out * math.cos(a), r_out * math.sin(a), -depth / 2)) for a in [i * 2 * math.pi / segments for i in range(segments)]]
    inner = [bm.verts.new((r_in * math.cos(a), r_in * math.sin(a), -depth / 2)) for a in [i * 2 * math.pi / segments for i in range(segments)]]
    outer2 = [bm.verts.new((v.co.x, v.co.y, depth / 2)) for v in outer]
    inner2 = [bm.verts.new((v.co.x, v.co.y, depth / 2)) for v in inner]
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((outer[i], outer[j], outer2[j], outer2[i]))
        bm.faces.new((inner[j], inner[i], inner2[i], inner2[j]))
        bm.faces.new((outer[j], outer[i], inner[i], inner[j]))
        bm.faces.new((outer2[i], outer2[j], inner2[j], inner2[i]))
    if axis == 'X': bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Y'), verts=bm.verts)
    elif axis == 'Y': bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, 'X'), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, col, [mat])
    ob.location = loc
    return ob


def apply_bool(target, cutter, op='DIFFERENCE', transfer_mat=True, remove=True):
    md = target.modifiers.new('bool', 'BOOLEAN'); md.object = cutter; md.operation = op; md.solver = 'EXACT'
    md.material_mode = 'TRANSFER' if transfer_mat else 'INDEX'
    bpy.context.view_layer.update()
    with bpy.context.temp_override(object=target, active_object=target, selected_objects=[target]):
        bpy.ops.object.modifier_apply(modifier=md.name)
    if remove:
        me = cutter.data; bpy.data.objects.remove(cutter); bpy.data.meshes.remove(me)


def apply_mods(ob):
    bpy.context.view_layer.update()
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        for md in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=md.name)


def bevel(ob, width=0.01, segments=2, angle=30):
    md = ob.modifiers.new('Bevel', 'BEVEL'); md.width = width; md.segments = segments
    md.limit_method = 'ANGLE'; md.angle_limit = math.radians(angle); md.harden_normals = False
    return md


def smooth(ob, angle=35):
    me = ob.data
    for p in me.polygons: p.use_smooth = True
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        try: bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
        except Exception: pass


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = par.matrix_world.inverted()


def tri_count(col):
    dg = bpy.context.evaluated_depsgraph_get(); n = 0
    for ob in col.all_objects:
        if ob.type != 'MESH': continue
        me = ob.evaluated_get(dg).to_mesh()
        n += sum(len(p.vertices) - 2 for p in me.polygons)
        ob.evaluated_get(dg).to_mesh_clear()
    return n


def save(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)


# ----------------------------------------------------------------- studio preview
def studio(size=6.0, cam_loc=(7, 8, 2.5), target=(0, 0, 0.6), lens=45, out=None, key_energy=None):
    """Grey cyclorama + 3-point area lights + camera. size ~ subject radius."""
    sc = bpy.context.scene
    col = get_collection('STUDIO')
    grey = P.new_mat('MAT_StudioGrey', (0.22, 0.22, 0.23, 1), rough=0.7)
    # cyclorama profile (y, z) extruded along X
    R = size * 3.0; H = size * 2.5; r = size * 0.8
    prof = [(R * 1.5, 0.0), (-R + r, 0.0)]
    for i in range(1, 9):
        a = math.pi / 2 * i / 8
        prof.append((-R + r - r * math.sin(a), r - r * math.cos(a)))
    prof.append((-R, H))
    bm = bmesh.new()
    W = R * 2.0
    row0 = [bm.verts.new((-W, y, z)) for y, z in prof]; row1 = [bm.verts.new((W, y, z)) for y, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((row0[i], row0[i + 1], row1[i + 1], row1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cyc = mesh_obj('STUDIO_CYC', bm, col, [grey]); smooth(cyc, 60)
    # world: soft gradient grey
    w = sc.world or bpy.data.worlds.new('World'); sc.world = w; w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out_n = nt.nodes.new('ShaderNodeOutputWorld'); bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.12, 0.12, 0.13, 1); ramp.color_ramp.elements[1].color = (0.55, 0.55, 0.58, 1)
    nt.links.new(tc.outputs['Window'], sep.inputs[0]); nt.links.new(sep.outputs['Y'], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.35
    nt.links.new(bg.outputs[0], out_n.inputs[0])
    # lights
    s2 = size * size
    ke = key_energy or 900 * s2 / 36
    def area(name, loc, energy, sz, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = sz; ld.color = color
        ob = bpy.data.objects.new(name, ld); col.objects.link(ob); ob.location = loc
        c = ob.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        return ob
    tgt = P.make_empty('STUDIO_TARGET', target); link(tgt, col)
    area('KEY', (size * 1.2, size * 1.0, size * 1.3), ke, size * 1.2, (1.0, 0.97, 0.93))
    area('FILL', (-size * 1.6, size * 0.9, size * 0.6), ke * 0.35, size * 2.0, (0.9, 0.94, 1.0))
    area('RIM', (-size * 0.6, -size * 1.5, size * 1.2), ke * 0.9, size * 0.8, (1.0, 1.0, 1.0))
    cam = P.add_camera('CAM_PREVIEW', loc=cam_loc, target=tgt, lens=lens)
    link(cam, col)
    P.setup_render(res=(1280, 720), samples=48, out=out, frame_start=1, frame_end=1)
    sc.view_settings.look = 'AgX - Base Contrast'
    return cam


def render(out):
    sc = bpy.context.scene
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
