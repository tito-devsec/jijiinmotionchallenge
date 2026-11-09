"""SCENE 08 — inside the helicopter: the passenger records Posta on the Infinix HOT 70. The camera moves from over the
passenger's shoulder to the phone, swings round to the rear camera island and dives into the main lens (ends on black-glass
refraction, hand-off to scene 09)."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    objs = S.load_city('future', future=True, real_trees=True); S.ocean_material_upgrade(dusk=False); S.apply_future_materials(objs); S.terrain_urban_material()
    S.world_golden(strength=0.06, sun_elev=20, sun_az=262, sun_energy=2.8)
    S.enable_mist(start=400, depth=3000, color=(0.86, 0.78, 0.66, 1), strength=0.3)
    S.link_asset('helicopter.blend', 'HELICOPTER'); heli = bpy.data.objects['HELI_ROOT']
    heli.location = (260, -210, 262); heli.rotation_euler = (math.radians(-1), 0, math.atan2(-210 - (-700), 260 - 600) - math.pi / 2)
    # gentle hover bob
    for f, dz in ((1, 0), (F // 2, 0.6), (F, 0)):
        heli.location.z = 262 + dz; heli.keyframe_insert('location', frame=f)
    rot = bpy.data.objects['ROTOR_MAIN']; rot.rotation_euler = (0, 0, 0); rot.keyframe_insert('rotation_euler', frame=1)
    rot.rotation_euler = (0, 0, math.radians(360 * 6 * F / 24)); rot.keyframe_insert('rotation_euler', frame=F)
    for fc in rot.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    seat = bpy.data.objects['HELI_PASSENGER_SEAT']
    # passenger
    cpath = os.path.join(P.ROOT, 'blender', 'assets', 'characters.blend'); hand = None
    if os.path.exists(cpath):
        try:
            pc = S.link_asset('characters.blend', 'PASSENGER'); proot = S.collection_root(pc)
            proot.parent = seat; proot.matrix_parent_inverse.identity(); proot.location = (0, 0, -0.45)
            hand = next((o for o in pc.all_objects if 'hand' in o.name.lower() and '.R' in o.name), None)
        except Exception as e: print('passenger skipped', e)
    # phone held out of the door, screen facing the passenger (-X local of seat -> world), lens toward the city
    pc2 = S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    phone.parent = seat; phone.matrix_parent_inverse.identity()
    phone.location = (0.0, 0.42, 0.45); phone.rotation_euler = (math.radians(90), 0, math.radians(90))  # upright, landscape, screen toward -Y_seat(back to passenger)
    # phone screen: show the live view -> plug a render of scene 09's first frame if available
    mat = bpy.data.materials.get('MAT_PhoneScreen')
    img_path = os.path.join(P.ROOT, 'renders', 's09_ui', 'f_0001.png')
    if mat and os.path.exists(img_path):
        nt = mat.node_tree; tex = nt.nodes.get('ScreenImage'); tex.image = bpy.data.images.load(img_path)
        b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'); nt.links.new(tex.outputs[0], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 4.0
    lens = bpy.data.objects['PHONE_LENS_MAIN']
    # camera path (in world space): over the shoulder inside the cabin -> phone screen -> orbit to the back -> into the lens
    bpy.context.view_layer.update()
    pm = phone.matrix_world; lw = lens.matrix_world.translation
    def rel(x, y, z): return (pm @ bpy.data.objects['PHONE_ROOT'].matrix_world.inverted() @ pm).translation if False else (pm @ __import__('mathutils').Vector((x, y, z)))
    cam = P.add_camera(loc=tuple(rel(-0.15, -0.9, 0.35)), target=tuple(rel(0, 0, 0)), lens=35, dof_target=lens, fstop=2.0)
    S.cam_path(cam, [(1, tuple(rel(-0.15, -0.9, 0.35))), (int(F * 0.35), tuple(rel(0.0, -0.3, 0.02))), (int(F * 0.6), tuple(rel(0.25, 0.2, -0.22))),
                     (int(F * 0.85), tuple(lw + (lens.matrix_world.to_3x3() @ __import__('mathutils').Vector((0, 0, -0.08))))), (F, tuple(lw))],
               [(1, tuple(rel(0, 0, 0))), (int(F * 0.35), tuple(rel(0, 0.02, 0))), (int(F * 0.6), tuple(lw)), (F, tuple(lw + (lens.matrix_world.to_3x3() @ __import__('mautils'.replace('mautils', 'mathutils')).Vector((0, 0, 0.05)))))])
    cam.data.lens = 35; cam.data.keyframe_insert('lens', frame=int(F * 0.6)); cam.data.lens = 60; cam.data.keyframe_insert('lens', frame=F)
    cam.data.clip_start = 0.002
    P.setup_render(samples=32, frame_end=F); S.frame_range(scn)
