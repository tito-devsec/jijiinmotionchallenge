"""bmesh asset-kit helpers shared by scripts/assets/build_*.py (Blender 4.5)."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if c.name not in p.children: p.children.link(c)
    return c

def empty(name, col, loc=(0, 0, 0), parent=None, size=0.5):
    e = bpy.data.objects.new(name, None); e.empty_display_size = size; e.empty_display_type = 'PLAIN_AXES'
    e.location = loc; col.objects.link(e); e.parent = parent
    return e

def obj_from_bm(name, bm, col, mats=(), loc=(0, 0, 0), parent=None, rot=None):
    me = bpy.data.meshes.new(name)
    bm.normal_update(); bm.to_mesh(me); bm.free(); me.update()
    for m in mats: me.materials.append(m)
    o = bpy.data.objects.new(name, me); o.location = loc
    if rot is not None: o.rotation_euler = rot
    col.objects.link(o); o.parent = parent
    return o

def _tag(verts, mat, smooth=None):
    faces = {f for v in verts for f in v.link_faces}
    for f in faces:
        f.material_index = mat
        if smooth is not None: f.smooth = smooth if len(f.verts) == 4 else False
    return faces

def _M(loc, rot, scale):
    return Matrix.Translation(Vector(loc)) @ (rot if rot is not None else Matrix.Identity(4)) @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))

def bm_box(bm, half, loc=(0, 0, 0), rot=None, mat=0):
    """Box with half-extents `half` centred at loc."""
    r = bmesh.ops.create_cube(bm, size=1.0); vs = r['verts']
    bmesh.ops.transform(bm, matrix=_M(loc, rot, (2 * half[0], 2 * half[1], 2 * half[2])), verts=vs)
    _tag(vs, mat, smooth=False); return vs

def bm_cyl(bm, r1, r2, depth, loc=(0, 0, 0), rot=None, seg=16, mat=0, caps=True, smooth=True):
    r = bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r1, radius2=max(r2, 1e-5), depth=depth); vs = r['verts']
    bmesh.ops.transform(bm, matrix=_M(loc, rot, (1, 1, 1)), verts=vs)
    _tag(vs, mat, smooth=smooth); return vs

def bm_sphere(bm, r, loc=(0, 0, 0), subdiv=2, mat=0, scale=(1, 1, 1), smooth=True):
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r); vs = res['verts']
    bmesh.ops.transform(bm, matrix=_M(loc, None, scale), verts=vs)
    for f in _tag(vs, mat): f.smooth = smooth
    return vs

def rot_to(p1, p2):
    d = Vector(p2) - Vector(p1)
    return d.to_track_quat('Z', 'Y').to_matrix().to_4x4()

def bm_bar(bm, p1, p2, r, mat=0, shape='box', seg=8, ry=None, ext=0.0):
    """Structural member from p1 to p2; square (half-width r, ry) box or round tube."""
    p1, p2 = Vector(p1), Vector(p2); d = p2 - p1; L = d.length + 2 * ext
    if L < 1e-6: return []
    mid = (p1 + p2) / 2; rot = rot_to(p1, p2)
    if shape == 'box': return bm_box(bm, (r, ry if ry is not None else r, L / 2), mid, rot, mat)
    return bm_cyl(bm, r, r, L, mid, rot, seg=seg, mat=mat)

def bm_profile_extrude(bm, profile_xz, length, mat=0, axis='Y'):
    """Extrude a closed 2D profile (list of (x,z)) along axis for `length`, centred on 0."""
    verts = [bm.verts.new((x, -length / 2, z) if axis == 'Y' else (-length / 2, x, z)) for x, z in profile_xz]
    f = bm.faces.new(verts)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    ext = [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]
    vec = (0, length, 0) if axis == 'Y' else (length, 0, 0)
    bmesh.ops.translate(bm, vec=vec, verts=ext)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for face in bm.faces: face.material_index = mat
    return verts + ext

def rx(a): return Matrix.Rotation(math.radians(a), 4, 'X')
def ry(a): return Matrix.Rotation(math.radians(a), 4, 'Y')
def rz(a): return Matrix.Rotation(math.radians(a), 4, 'Z')

def tri_count(objs=None):
    n = 0
    for o in (objs or bpy.data.objects):
        if o.type == 'MESH':
            n += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return n

def collection_tris(col):
    return tri_count(col.all_objects)

def set_parent_keep(child, parent):
    child.parent = parent; child.matrix_parent_inverse = parent.matrix_world.inverted()

def ground(name='GROUND', size=400, mat=None, z=0.0):
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    o = obj_from_bm(name, bm, bpy.context.scene.collection, [mat] if mat else [], loc=(0, 0, z))
    return o
