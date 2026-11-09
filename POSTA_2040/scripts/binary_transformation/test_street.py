import bpy, sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P
bpy.ops.wm.read_factory_settings(use_empty=True)
objs = P.link_city(); P.city_materials(objs, 'binary')
b = objs['CITY_BUILDING']; P.apply_binary(b, progress=0.4, density=0.6, size=0.9, noise_scale=0.02, seed=3, flow=2.0, height_bias=0.5)
r = objs['CITY_ROAD']; P.apply_binary(r, progress=0.5, density=0.8, size=0.6, noise_scale=0.01, seed=11, flow=3.0, height_bias=0.0, band=0.2)
P.setup_world(sun_elev=22, sun_az=255, sun_energy=2.5, sky_strength=0.08)
gz = P.ground_z(-170, 150); print('ground z at posta', gz)
top = P.nearest_building_top(-130, 206, 50); print('nearest tall', top)
cam = P.add_camera(loc=(-170, 150, gz + 1.7), target=(-125, 210, gz + 18), lens=24)
P.setup_render(res=(1280, 720), samples=32, out=os.path.join(P.ROOT, 'previews', 'test_street_binary.png'))
bpy.ops.render.render(write_still=True)
