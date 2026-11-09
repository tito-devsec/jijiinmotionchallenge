"""Original-versus-futuristic map comparison: identical top-down orthographic and oblique views of city_base.blend and
city_future.blend. Output previews/map_compare_{topdown,oblique}_{original,2040}.png, combined by compose_comparison()."""
import bpy, os, sys, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'common'))
import posta_lib as P, scene_lib as S
for tag, fut in (('original', False), ('2040', True)):
    for view in ('topdown', 'oblique'):
        S.fresh(); objs = S.load_city('real' if not fut else 'future', future=fut)
        if fut: S.apply_future_materials(objs)
        S.terrain_urban_material(); S.ocean_material_upgrade()
        S.world_day(strength=0.05, sun_elev=40, sun_az=235, sun_energy=3.0)
        if view == 'topdown':
            cam = P.add_camera(loc=(0, 0, 1500), lens=50); cam.rotation_euler = (0, 0, 0); cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2200
            res = (1100, 900)
        else:
            cam = P.add_camera(loc=(700, -1050, 650), target=(-150, 150, 20), lens=32); res = (1280, 720)
        P.setup_render(res=res, samples=12)
        bpy.context.scene.render.filepath = os.path.join(ROOT, 'previews', f'map_compare_{view}_{tag}.png')
        bpy.ops.render.render(write_still=True)
# side-by-side sheets
from PIL import Image, ImageDraw, ImageFont
import glob
fp = (glob.glob('/usr/share/fonts/opentype/inter/Inter-Bold.otf') + glob.glob('/usr/share/fonts/**/DejaVuSans-Bold.ttf', recursive=True))[0]
for view in ('topdown', 'oblique'):
    a = Image.open(os.path.join(ROOT, 'previews', f'map_compare_{view}_original.png')); b = Image.open(os.path.join(ROOT, 'previews', f'map_compare_{view}_2040.png'))
    W, H = a.size; sheet = Image.new('RGB', (W * 2 + 20, H + 70), (9, 13, 22)); sheet.paste(a, (0, 70)); sheet.paste(b, (W + 20, 70))
    d = ImageDraw.Draw(sheet); f = ImageFont.truetype(fp, 30)
    d.text((16, 18), 'POSTA TODAY  (OpenStreetMap, untouched)', font=f, fill=(243, 240, 232)); d.text((W + 36, 18), 'POSTA 2040  (same footprints, roads, coastline)', font=f, fill=(0, 198, 168))
    sheet.save(os.path.join(ROOT, 'documentation', f'map_comparison_{view}.png'))
print('MAP_COMPARE_DONE')
