import bpy, sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P
bpy.ops.wm.read_factory_settings(use_empty=True)
objs = P.link_city()
P.city_materials(objs, 'binary')
b = objs['CITY_BUILDING']
md = P.apply_binary(b, progress=float(sys.argv[-1]), density=0.25, size=1.2, noise_scale=0.015, seed=3, flow=2.0, height_bias=0.45)
P.setup_world(sun_elev=28, sun_az=250, sun_energy=2.5)
# camera: looking NE across Posta toward the harbour from above Azikiwe street (approx x=-250,y=-100)
cam = P.add_camera(loc=(-420, -380, 90), target=(-50, 50, 30), lens=32)
P.setup_render(samples=32, out=os.path.join(P.ROOT, 'previews', f'test_binary_{sys.argv[-1]}.png'))
bpy.ops.render.render(write_still=True)
