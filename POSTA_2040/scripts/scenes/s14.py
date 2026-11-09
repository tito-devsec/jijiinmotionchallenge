"""SCENE 14 — brand reveal. Premium product shot of the Infinix HOT 70 standing on a dark reflective surface, slow turn,
Posta 2040 skyline glowing behind; title and tagline rise in."""
import bpy, os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'common'))
import posta_lib as P, scene_lib as S

def build(scn, quality):
    S.fresh(); F = scn['frames']
    # city far behind as a skyline (future style), seen from the harbour at dusk
    objs = S.load_city('future'); S.ocean_material_upgrade(dusk=True); S.apply_future_materials(objs)
    S.world_dusk(strength=0.05, sun_elev=4, sun_az=262, sun_energy=0.8)
    S.enable_mist(start=200, depth=1800, color=(0.12, 0.16, 0.26, 1), strength=0.6)
    # product stage floating over the harbour water at (300,-250): a dark glossy disc
    stage = (300, -250, 1.5)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=0.04, location=stage); st = bpy.context.object; st.name = 'STAGE'
    st.data.materials.append(P.new_mat('MAT_Stage', (0.02, 0.02, 0.025, 1), 0.08, 0.2, coat=1.0))
    S.link_asset('phone.blend', 'PHONE'); phone = bpy.data.objects['PHONE_ROOT']
    phone.location = (stage[0], stage[1], stage[2] + 0.02 + 0.0825); phone.rotation_euler = (math.radians(90), 0, math.radians(25))
    phone.keyframe_insert('rotation_euler', frame=1); phone.rotation_euler = (math.radians(90), 0, math.radians(25 + 70)); phone.keyframe_insert('rotation_euler', frame=F)
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
    # titles (3D text, emissive warm white) in front of the stage, rising from below
    tmat = P.new_mat('MAT_Title', P.PAL['white'], 0.4, emission=P.PAL['white'], estrength=2.0)
    t1 = S.text_object('TITLE', 'JIJI IN MOTION', size=0.085, mat=tmat, extrude=0.002)
    t2 = S.text_object('TAGLINE', 'THE FUTURE IS WORTH CAPTURING.', size=0.03, mat=tmat, extrude=0.001)
    for ob, z, f0 in ((t1, stage[2] + 0.12, int(F * 0.45)), (t2, stage[2] + 0.07, int(F * 0.55))):
        ob.rotation_euler = (math.radians(90), 0, math.radians(0)); ob.location = (stage[0] - 0.0, stage[1] - 0.55, z - 0.3); ob.keyframe_insert('location', frame=f0)
        ob.location = (stage[0], stage[1] - 0.55, z); ob.keyframe_insert('location', frame=f0 + 30)
        ob.hide_render = True; ob.keyframe_insert('hide_render', frame=1); ob.hide_render = False; ob.keyframe_insert('hide_render', frame=f0)
        P.ease_all(ob)
    cam = P.add_camera(loc=(stage[0] + 0.05, stage[1] - 1.25, stage[2] + 0.22), target=(stage[0], stage[1], stage[2] + 0.1), lens=50, dof_target=phone, fstop=2.8)
    S.cam_path(cam, [(1, (stage[0] + 0.35, stage[1] - 1.1, stage[2] + 0.3)), (F, (stage[0] - 0.05, stage[1] - 1.3, stage[2] + 0.2))])
    P.setup_render(samples=36, frame_end=F); S.frame_range(scn)
