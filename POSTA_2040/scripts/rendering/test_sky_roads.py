import bpy, sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P
mode = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
objs = P.link_city()
P.city_materials(objs, 'real')
if mode == 'roads':
    r = objs['CITY_ROAD']; r.material_slots[0].material = P.dissolving_material('MAT_RoadDissolve', (0.05, 0.05, 0.055, 1), glow='blue')
    P.apply_binary(r, progress=0.55, density=0.5, size=0.8, noise_scale=0.01, seed=11, flow=3.0, height_bias=0.0, band=0.2)
    P.setup_world(sun_elev=12, sun_az=260, sun_energy=1.0, sky_strength=0.04)
    cam = P.add_camera(loc=(-330, -120, 14), target=(-250, -40, 6), lens=35)
elif mode == 'sky':
    P.setup_world(sun_elev=35, sun_az=250, sun_energy=3.0, sky_strength=float(sys.argv[-2]))
    cam = P.add_camera(loc=(-600, -500, 220), target=(-150, 100, 20), lens=35)
P.setup_render(res=(960, 540), samples=24, out=os.path.join(P.ROOT, 'previews', f'test_{mode}_{sys.argv[-2]}.png'))
bpy.ops.render.render(write_still=True)
