"""SCENE 05 — humans transform from binary into real people. In the binary city, a hero made only of 0/1 glyphs and glowing
edges walks along a digital road; binary particles thicken into a silhouette, then the real surface (skin, clothing, face)
resolves from the head down. Background walkers are at different stages of the same transformation."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S, character_anim as CA

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('binary', crop=((-140, 190), 380), future=True)
    S.ocean_material_upgrade(dusk=True)
    for n, dens, size in (('CITY_BUILDING', 0.06, 1.2), ('CITY_CROWNS', 0.06, 1.2), ('CITY_SPIRES', 0.06, 1.0), ('CITY_TREE', 0.08, 0.6)):
        if n in objs:
            m = P.apply_binary(objs[n], progress=1.0, density=dens, size=size, noise_scale=0.025, seed=3, height_bias=0.5, keep_shell=1.0 if n != 'CITY_TREE' else 0.0); S.drive_flow(m, speed=0.8)
    mr = P.apply_binary(objs['CITY_ROAD'], progress=1.0, density=0.25, size=0.22, noise_scale=0.008, seed=11, height_bias=0.0, band=0.25); S.drive_flow(mr, speed=2.0)
    (rx, ry, rz), (dx, dy) = S.road_frame(-150, 185)
    head = math.atan2(dy, dx) - math.pi / 2
    walk = 1.3 / 24.0  # m per frame
    g = lambda a, b=0.0: (rx + dx * a - dy * b, ry + dy * a + dx * b, rz + 0.05)
    # hero
    hcol, hero = S.add_character('HERO', loc=g(-6), heading=head)
    CA.make_walk_cycle(hero, 1, F, stride_frames=26)
    P.key(hero, 1, loc=g(-6)); P.key(hero, F, loc=g(-6 + walk * F), interp='LINEAR')
    hm = S.apply_binary_character(hcol, progress=1.0, density=7000, size=0.018, seed=5, height_bias=0.7)
    for m in hm:
        S.key_progress(m, [(1, 1.0), (int(F * 0.35), 1.0), (int(F * 0.85), 0.0), (F, 0.0)])
        P.key_mod(m, 'Density', 1, 1500); P.key_mod(m, 'Density', int(F * 0.25), 7000)
        P.key_mod(m, 'Scatter', 1, 2.2); P.key_mod(m, 'Scatter', int(F * 0.3), 0.0); P.key_mod(m, 'Scatter', int(F * 0.6), 0.25)
        S.drive_flow(m, speed=1.5); S.binary_off_after(m, int(F * 0.85) + 2)
    # background walkers at other stages
    for i, (nm, a, b, p0, p1, rev) in enumerate((('CIVILIAN_A', 4, 2.5, 1.0, 0.6, False), ('CIVILIAN_B', 10, -2.5, 0.6, 0.0, True), ('CIVILIAN_C', 16, 3.0, 1.0, 1.0, False), ('WORKER', 22, -3.0, 0.3, 0.0, True))):
        col, rig = S.add_character(nm, loc=g(a, b), heading=head + (math.pi if rev else 0))
        CA.make_walk_cycle(rig, 1, F, stride_frames=24 + 2 * i)
        sgn = -1 if rev else 1
        P.key(rig, 1, loc=g(a, b)); P.key(rig, F, loc=g(a + sgn * walk * F * 0.95, b), interp='LINEAR')
        for m in S.apply_binary_character(col, progress=p0, density=1800, size=0.03, seed=20 + i, height_bias=0.7):
            S.key_progress(m, [(1, p0), (F, p1)]); S.drive_flow(m, speed=1.5)
    S.world_bluehour(sun_energy=0.25, strength=0.12)
    S.binary_rain((rx, ry), size=300, top=90, height=90, columns_per_km2=3000, glyph=0.6, look_at=g(-9, 3.2))
    S.enable_mist(start=30, depth=450, color=(0.03, 0.06, 0.14, 1), strength=0.55)
    # camera: low tracking shot beside the hero, then a slow push to a mid close-up as the face resolves
    cam = P.add_camera(loc=g(-9, 3.2), target=hero, lens=35, dof_target=hero, fstop=2.2)
    con = cam.constraints[0]; tgt = S.make_empty('HERO_HEAD', (0, 0, 0)) if hasattr(S, 'make_empty') else P.make_empty('HERO_HEAD', (0, 0, 0))
    tgt.parent = hero; tgt.location = (0, 0, 1.5); con.target = tgt; cam.data.dof.focus_object = tgt
    end = -6 + walk * F
    S.cam_path(cam, [(1, (g(-8, 3.4)[0], g(-8, 3.4)[1], rz + 1.3)), (int(F * 0.5), (g(end * 0.4, 3.0)[0], g(end * 0.4, 3.0)[1], rz + 1.5)), (F, (g(end + 1.6, 1.4)[0], g(end + 1.6, 1.4)[1], rz + 1.6))])
    cam.data.lens = 35; cam.data.keyframe_insert('lens', frame=1); cam.data.lens = 55; cam.data.keyframe_insert('lens', frame=F)
    # soft key + rim light travelling with the hero so the face reads as it resolves
    for nm, off, e, col in (('KEY_HERO', (-1.6, 1.2, 1.9), 120, (1.0, 0.86, 0.72)), ('RIM_HERO', (1.4, -1.5, 2.1), 160, P.PAL['turq'][:3])):
        ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.size = 1.2; ld.color = col
        lo = bpy.data.objects.new(nm, ld); bpy.context.scene.collection.objects.link(lo); lo.parent = hero; lo.location = off
        c = lo.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    P.setup_render(samples=28, frame_end=F); S.frame_range(scn)
