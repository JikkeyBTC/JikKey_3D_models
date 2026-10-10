"""Render actual exported CAD meshes. Pips are presentation marks only."""
from pathlib import Path
import bpy,math,json
from mathutils import Vector
OUT=Path(__file__).resolve().parent.parent
P=json.loads((OUT/'Dimensions.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(name,col):
    m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=.38
    return m
white=mat('White printed base',(.83,.84,.82));black=mat('Black dice',(.025,.034,.04));pip=mat('White display dots',(.86,.86,.82));gray=mat('Ground',(.2,.24,.25))
def load(filename,m):
    before=set(bpy.data.objects);bpy.ops.wm.stl_import(filepath=str(OUT/filename))
    o=next(o for o in bpy.data.objects if o not in before);o.data.materials.append(m)
    return o
base=load('Entropy_Box_V3_Deep_Base.stl',white);dice=load('Dice_25_REFERENCE.stl',black)
section=load('Base_Section_REFERENCE.stl',white);cutdice=load('Dice_Section_REFERENCE.stl',black)
section.hide_render=cutdice.hide_render=True
coords=[(i-2)*P['pitch'] for i in range(5)]
patterns={1:[(0,0)],2:[(-1,-1),(1,1)],3:[(-1,-1),(0,0),(1,1)],4:[(-1,-1),(-1,1),(1,-1),(1,1)],5:[(-1,-1),(-1,1),(0,0),(1,-1),(1,1)],6:[(-1,-1),(-1,0),(-1,1),(1,-1),(1,0),(1,1)]}
for j,y in enumerate(coords):
    for i,x in enumerate(coords):
        for u,v in patterns[1+(i+3*j)%6]:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=1,location=(x+u*1.1,y+v*1.1,6.405))
            o=bpy.context.object;o.scale=(.28,.28,.035);o.data.materials.append(pip)
bpy.ops.mesh.primitive_plane_add(size=1000,location=(0,0,-.05));bpy.context.object.data.materials.append(gray)
for loc,power,size in [((-70,-90,160),300000,120),((100,0,110),200000,120),((0,120,160),250000,100)]:
    l=bpy.data.lights.new('Softbox','AREA');l.energy=power;l.shape='DISK';l.size=size
    ob=bpy.data.objects.new('Softbox',l);bpy.context.collection.objects.link(ob);ob.location=loc
    ob.rotation_euler=(Vector((0,0,7))-ob.location).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.cameras.new('CAD Camera');camera=bpy.data.objects.new('CAD Camera',cam);bpy.context.collection.objects.link(camera)
camera.location=(70,-100,155);camera.rotation_euler=(Vector((0,0,7))-camera.location).to_track_quat('-Z','Y').to_euler();cam.type='ORTHO';cam.ortho_scale=82;cam.clip_end=2000
scene=bpy.context.scene;scene.camera=camera;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.5
scene.view_settings.view_transform='AgX'
scene.render.filepath=str(OUT/'Preview_V3_Open_25_Dice.png');bpy.ops.render.render(write_still=True)
base.hide_render=dice.hide_render=True;section.hide_render=cutdice.hide_render=False
camera.location=(35,-110,60);camera.rotation_euler=(Vector((0,3,8))-camera.location).to_track_quat('-Z','Y').to_euler();cam.ortho_scale=80
scene.render.filepath=str(OUT/'Preview_V3_Section_5mm_Pockets.png');bpy.ops.render.render(write_still=True)
print('Actual-model open and section previews saved.')
