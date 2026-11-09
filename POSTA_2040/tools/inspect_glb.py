import sys, json, collections
import trimesh
for p in sys.argv[1:]:
    sc = trimesh.load(p, force='scene')
    print("====", p)
    print("nodes:", len(sc.graph.nodes_geometry), "geometries:", len(sc.geometry))
    b = sc.bounds; print("bounds min", b[0].round(1), "max", b[1].round(1), "extent", (b[1]-b[0]).round(1))
    mats = collections.Counter(); tris=0; verts=0
    for name,g in sc.geometry.items():
        tris += len(g.faces); verts += len(g.vertices)
        m = getattr(g.visual,'material',None)
        mats[(m.name if m is not None else 'none')] += len(g.faces)
    print("total tris", tris, "verts", verts)
    for k,v in mats.most_common(45): print(f"  {k:32s} {v:>9d} tris")
