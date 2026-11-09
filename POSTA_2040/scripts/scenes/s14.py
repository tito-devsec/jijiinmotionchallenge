"""SCENE 14 — brand reveal. Premium product shot of the Infinix HOT 70 standing on a dark reflective surface, slow turn,
Posta 2040 skyline glowing behind; title and tagline rise in."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    # city far behind as a skyline (future style), seen from the harbour at dusk
    objs = S.load_city('future', future=True); S.ocean_material_upgrade(dusk=True); S.apply_bluehour_city(objs)
    S.world_bluehour(sun_energy=0.3, strength=0.55)
    S.enable_mist(start=200, depth=1800, color=(0.1, 0.1, 0.2, 1), strength=0.35)
    # product stage floating over the harbour water at (300,-250): a dark glossy disc
    stage = (300, -250, 1.5)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=0.04, location=stage); st = bpy.context.object; st.name = 'STAGE'
    st.data.materials.append(P.new_mat('MAT_Stage', (0.02, 0.02, 0.025, 1), 0.08, 0.2, coat=1.0))
    S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    phone.location = (stage[0], stage[1], stage[2] + 0.02 + 0.0825); phone.rotation_euler = (math.radians(90), 0, math.radians(215))
    phone.keyframe_insert('rotation_euler', frame=1); phone.rotation_euler = (math.radians(90), 0, math.radians(165)); phone.keyframe_insert('rotation_euler', frame=F)
    for fc in phone.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.easing = 'EASE_IN_OUT'
    # screen shows the city it captured (frame from scene 09 UI if present)
    mat = bpy.data.materials.get('MAT_PhoneScreen'); img_path = os.path.join(P.ROOT, 'renders', 's09_ui', 'f_0100.png')
    if mat and os.path.exists(img_path):
        nt = mat.node_tree; tex = nt.nodes.get('ScreenImage'); tex.image = bpy.data.images.load(img_path)
        b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'); nt.links.new(tex.outputs[0], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 3.0
    # studio lights
    for nm, loc, e, sz, col in (('KEY', (299.2, -250.9, 2.3), 60, 0.8, (1, 0.95, 0.9)), ('RIM', (300.8, -249.2, 2.2), 90, 0.5, P.PAL['turq'][:3]), ('FILL', (300.9, -251.0, 1.9), 25, 1.2, (0.8, 0.85, 1.0))):
        ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.size = sz; ld.color = col; lo = bpy.data.objects.new(nm, ld); bpy.context.scene.collection.objects.link(lo); lo.location = loc
        c = lo.constraints.new('TRACK_TO'); c.target = phone; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    # titles are set in post (overlay_ui.py brand) for crisp, always-legible typography
    # phone on the right third; title space on the left; slow push-in with an 85 mm lens
    aim = P.make_empty('AIM', (stage[0] - 0.09, stage[1], stage[2] + 0.11))
    cam = P.add_camera(loc=(stage[0] - 0.05, stage[1] - 1.25, stage[2] + 0.2), target=aim, lens=85, dof_target=phone, fstop=4.0)
    S.cam_path(cam, [(1, (stage[0] + 0.1, stage[1] - 1.35, stage[2] + 0.24)), (F, (stage[0] - 0.06, stage[1] - 1.15, stage[2] + 0.18))])
    P.setup_render(samples=36, frame_end=F); S.frame_range(scn)
