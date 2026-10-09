import json, math, pathlib, struct, sys, time
import FreeCAD as App
import Part
import numpy as np

# All paths resolve from this model directory, independently of the checkout.
ROOT = pathlib.Path(__file__).resolve().parents[1]
STL_DIR = ROOT / 'STL'
STEP_DIR = ROOT / 'STEP'
OPTIONAL_DIR = ROOT / 'Optional_Tests'
NATIVE_DIR = ROOT / 'Native_CAD'
REFERENCE_DIR = ROOT / 'Reference'
VERIFICATION_DIR = ROOT / 'Verification'
WORK = VERIFICATION_DIR / '_build'
for p in (STL_DIR, STEP_DIR, OPTIONAL_DIR, NATIVE_DIR, REFERENCE_DIR,
          VERIFICATION_DIR, WORK / 'assembled'):
    p.mkdir(parents=True, exist_ok=True)

P = dict(body_length=110.0, body_width=82.0, body_height=47.0,
         nominal_gap=150.0, min_gap=145.0, max_gap=215.0,
         screw_pitch=6.0, screw_length=95.0, male_root_radius=10.0,
         male_crest_radius=12.0, female_radial_clearance=0.35,
         pad_thickness=3.0, guide_length=115.0, guide_width=8.0,
         guide_height=10.0, guide_clearance=0.35,
         camera_plate_diameter=82.0, camera_plate_thickness=4.0,
         camera_hole_diameter=4.3, camera_bolt_circle=45.03333,
         camera_hole_count=9, camera_hole_start_angle=10.0)
PARAM = VERIFICATION_DIR / 'Dimensions.json'
PARAM.write_text(json.dumps(P, ensure_ascii=False, indent=2), encoding='utf-8')

def V(x=0,y=0,z=0): return App.Vector(x,y,z)
def box(l,w,h,x=0,y=0,z=0): return Part.makeBox(l,w,h,V(x,y,z))
def cyl(r,h,x=0,y=0,z=0,axis=None):
    return Part.makeCylinder(r,h,V(x,y,z),axis or V(0,0,1))
def polygon(points): return Part.makePolygon([V(*p) for p in points+[points[0]]])
def hex_prism(radius,height,z=0):
    pts=[(radius*math.cos(math.radians(30+60*i)),radius*math.sin(math.radians(30+60*i)),z) for i in range(6)]
    return Part.Face(polygon(pts)).extrude(V(0,0,height))
def axial(shape, x=0, y=0, z=28, angle=0):
    s=shape.copy()
    if angle: s.rotate(V(),V(0,0,1),angle)
    s.rotate(V(),V(0,1,0),90)
    s.translate(V(x,y,z)); return s
def tidy(s):
    cleaned=s.removeSplitter()
    return cleaned if cleaned.isValid() else s
def teardrop(radius,depth,x,y,z):
    c=cyl(radius,depth,x,y,z)
    a=radius/math.sqrt(2)
    tri=Part.Face(polygon([(x+a,y-a,z),(x+radius*math.sqrt(2),y,z),(x+a,y+a,z)])).extrude(V(0,0,depth))
    return c.fuse(tri)

def rib(pitch, length, root, crest, base_width, crest_width, z=0):
    helix=Part.makeHelix(pitch,length,root)
    pts=[(root-0.12,0,-base_width/2),(crest,0,-crest_width/2),
         (crest,0,crest_width/2),(root-0.12,0,base_width/2)]
    profile=polygon(pts)
    thread=Part.Wire(helix.Edges).makePipeShell([profile],True,True)
    thread.translate(V(0,0,z))
    return thread

print('Building coarse self-supporting screw',flush=True)
pitch=P['screw_pitch']; sl=P['screw_length']
male_rib=rib(pitch,sl-2,10,12,4.6,0.6,z=1)
print('rib valid',male_rib.isValid(),flush=True)
screw=cyl(10,sl).fuse(male_rib)
print('fused shaft valid',screw.isValid(),flush=True)
screw=screw.common(cyl(12.01,sl))
print('trimmed shaft valid',screw.isValid(),flush=True)
# A flat first layer and a 45-degree transition support the entire screw.
screw=screw.fuse(cyl(10,0.7))
screw=screw.fuse(Part.makeCone(12,18,6,V(0,0,sl)))
screw=screw.fuse(hex_prism(18,6,z=sl+6))
screw=screw.fuse(cyl(6.5,6,z=sl+12))
screw=screw.fuse(cyl(4.75,3,z=sl+18))
screw=screw.fuse(Part.makeCone(4.75,6.5,1.75,V(0,0,sl+21)))
screw=screw.fuse(cyl(6.5,2.25,z=sl+22.75))
print('full screw before cleanup valid',screw.isValid(),flush=True)
# Do not unify helical seams: OCC removeSplitter changes this valid thread topology.
print('full screw export topology valid',screw.isValid(),flush=True)

print('Building body and female thread',flush=True)
body=box(110,82,47,0,-41,0)
# Cavities are open at the upper end of the upright print; there are no large roofs.
for yc in (-28.5,28.5):
    body=body.cut(box(103,17,18,8,yc-8.5,25))
for yc in (-28,28):
    body=body.cut(box(103,8.7,10.7,8,yc-4.35,10.65))
    # Small slots accept two M3 stop screw heads, accessible through the side cavities.
    body=body.cut(box(79,6.4,26.2,29,yc-3.2,20.9))
# M4 heat-set insert pockets: nominal OD6 x length5mm hardware.
for xc in (23,87):
    body=body.cut(teardrop(2.8,5.5,xc,0,0))
# Construct the threaded section at the helix origin, with the cylindrical seam
# opposite the profile. This avoids OCC's C0 seam classification failure.
rear=body.common(box(76,82,47,0,-41,0))
rear=rear.cut(cyl(12.65,69,8,0,28,V(1,0,0)))
nut_section=body.common(box(34,82,47,76,-41,0))
nut_section.rotate(V(),V(0,1,0),-90);nut_section.translate(V(28,0,-76))
female_core=cyl(10.35,34);female_core.rotate(V(),V(0,0,1),180)
female_rib=rib(pitch,34,10.35,12.35,5.0,1.0)
nut_section=nut_section.cut(female_core).cut(female_rib)
nut_section=nut_section.cut(Part.makeCone(12.65,10.35,2.3,V(0,0,0)))
nut_section=nut_section.cut(Part.makeCone(10.35,12.7,2.35,V(0,0,31.65)))
body=rear.fuse(axial(nut_section,x=76,z=28))
print('body thread curved surfaces',[type(f.Surface).__name__ for f in body.Faces if type(f.Surface).__name__ not in ('Plane','Cylinder','Cone')],flush=True)

print('Building guided moving foot',flush=True)
# Screw coordinates: shaft0..95, knob101..107, capture groove113..116.
foot=box(14.7,82,47,107.3,-41,0)
for yc in (-28,28):
    foot=foot.fuse(box(115,8,10,-7.7,yc-4,11))
    # Pilot holes for M3x10 self-tapping travel-stop screws.
    foot=foot.cut(cyl(1.35,9,17.3,yc,13))
# Open bearing/counterbore with a 45-degree transition, face-first print.
foot=foot.cut(cyl(6.8,4,107.2,0,28,V(1,0,0)))
foot=foot.cut(Part.makeCone(6.8,10,3.2,V(111,0,28),V(1,0,0)))
foot=foot.cut(cyl(10,5.8,114.2,0,28,V(1,0,0)))
# Closed 2mm thrust seat carries pressure at the screw tip. This open-back/top
# access slot accepts the clip and never creates a roof in the face-first print.
foot=foot.cut(box(9.8,20,20,107.2,-10,28))
foot=tidy(foot)

print('Building retaining clip and camera platform',flush=True)
clip=cyl(9,2.2).cut(cyl(4.95,2.4,z=-0.1))
clip=clip.cut(box(9.0,12,3,-4.5,0,-0.4))
clip=tidy(clip)
camera=cyl(41,4)
# Two separate mounting bosses keep the original camera holes unobstructed.
for xc in (-32,32): camera=camera.fuse(cyl(6,8,xc,0,4))
camera=camera.fuse(cyl(20,2,z=4))
for i in range(9):
    a=math.radians(10+40*i);r=P['camera_bolt_circle']/2
    camera=camera.cut(cyl(2.15,13,r*math.cos(a),r*math.sin(a),-0.5))
for xc in (-32,32):
    camera=camera.cut(cyl(2.25,13,xc,0,-0.5))
    camera=camera.cut(Part.makeCone(4.5,2.25,2.25,V(xc,0,0)))
camera=tidy(camera)

pad=box(82,47,2.4)
for y in range(3,45,6): pad=pad.fuse(box(78,2,0.6,2,y,2.4))
pad=tidy(pad)

# Compact fit coupons use the exact same thread geometry as the final parts.
test_nut=cyl(17,18).cut(female_core).cut(female_rib)
test_screw=screw.common(cyl(12.01,20))
test_screw=test_screw.fuse(Part.makeCone(12,18,6,V(0,0,20)))
test_screw=test_screw.fuse(hex_prism(18,5,z=26))

def pose(s,translation=None,rotation=None):
    q=s.copy()
    if rotation: q.rotate(V(),V(*rotation[0]),rotation[1])
    if translation: q.translate(V(*translation))
    return q
def to_bed(s,rotation=None):
    q=pose(s,rotation=rotation)
    vertices,_=q.tessellate(0.10)
    mins=np.min([[v.x,v.y,v.z] for v in vertices],axis=0)
    q.translate(V(*(-mins)));return q
def stl(shape,path):
    verts,faces=shape.tessellate(0.10)
    vs=np.array([[v.x,v.y,v.z] for v in verts],dtype=np.float64)
    fs=np.asarray(faces,dtype=np.int64)
    tris=vs[fs];normals=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0])
    lens=np.linalg.norm(normals,axis=1);normals/=np.maximum(lens,1e-20)[:,None]
    with open(path,'wb') as f:
        f.write(b'Curtainbox pressure mount | millimetres'.ljust(80,b' '));f.write(struct.pack('<I',len(fs)))
        for n,t in zip(normals,tris): f.write(struct.pack('<12fH',*(n.tolist()+t.ravel().tolist()),0))
    return dict(triangles=len(fs),bounds=[vs.min(axis=0).tolist(),vs.max(axis=0).tolist()])

parts={'01_body':body,'02_screw':screw,'03_moving_foot':foot,
       '04_retaining_clip':clip,'05_camera_plate':camera,'06_TPU_pad':pad}
orients={'01_body':((0,1,0),-90),'02_screw':None,
         '03_moving_foot':((0,1,0),90),'04_retaining_clip':None,
         '05_camera_plate':None,'06_TPU_pad':None}
info={}; print_parts={}
for name,shape in parts.items():
    print(name,'valid',shape.isValid(),'solids',len(shape.Solids),flush=True)
    if not shape.isValid() or len(shape.Solids)!=1: raise RuntimeError('Invalid printable part: '+name)
    q=to_bed(shape,orients[name]);print_parts[name]=q
    info[name]=stl(q,STL_DIR/(name+'.stl'))
    info[name].update(volume_mm3=shape.Volume,valid=shape.isValid(),solids=len(shape.Solids))

fit_print_parts={}
for name,shape in {'fit_nut':test_nut,'fit_screw':test_screw}.items():
    if not shape.isValid() or len(shape.Solids)!=1: raise RuntimeError('Invalid fit coupon '+name)
    printable=to_bed(shape)
    fit_print_parts[name]=printable
    stl(printable,OPTIONAL_DIR/(name+'.stl'))

a=P['nominal_gap']-128
spin=(a+1-76)*360/pitch
assembly={
 '01_body':body,
 '02_screw':axial(screw,x=a,z=28,angle=spin),
 '03_moving_foot':pose(foot,(a,0,0)),
 '04_retaining_clip':axial(clip,x=a+113.4,z=28,angle=-90),
 '05_camera_plate':pose(camera,(55,0,-12)),
 '06_TPU_pad_fixed':pose(pad,(-3,-41,0),((0,1,0),90)),
 '07_TPU_pad_moving':pose(pad,(a+122,-41,0),((0,1,0),90)),
}
# Cyclic axis rotation maps local (width,height,thickness) to world(Y,Z,X).
# The fixed pad is reversed so both textured faces point toward the walls.
fixed=pad.copy();fixed.rotate(V(),V(1,1,1),120);fixed.rotate(V(),V(0,1,0),180)
fixed.translate(V(0,-41,47))
moving=pad.copy();moving.rotate(V(),V(1,1,1),120);moving.translate(V(a+122,-41,0))
assembly['06_TPU_pad_fixed']=fixed
assembly['07_TPU_pad_moving']=moving
for name,s in assembly.items(): stl(s,WORK/'assembled'/(name+'.stl'))

doc=App.newDocument('CurtainboxPressureMount')
meta=doc.addObject('App::FeaturePython','Dimensions')
for k,v in P.items():
    meta.addProperty('App::PropertyFloat',k,'Dimensions');setattr(meta,k,float(v))
objs=[]
for name,s in assembly.items():
    obj=doc.addObject('Part::Feature',name);obj.Label=name;obj.Shape=s;objs.append(obj)
doc.recompute();doc.saveAs(str(NATIVE_DIR/'CurtainBox_CameraMount.FCStd'))
Part.export(objs,str(REFERENCE_DIR/'CurtainBox_Mount_Assembly_REFERENCE.step'))

# Export the exact same oriented, bed-normalized solids used for the STLs.
# A separate temporary document leaves the saved assembly document unchanged.
print_doc=App.newDocument('CurtainboxPrintPartExports')
try:
    for name,shape in print_parts.items():
        feature=print_doc.addObject('Part::Feature',name)
        feature.Label=name;feature.Shape=shape
        print_doc.recompute()
        Part.export([feature],str(STEP_DIR/(name+'.step')))
    for name,shape in fit_print_parts.items():
        feature=print_doc.addObject('Part::Feature',name)
        feature.Label=name;feature.Shape=shape
        print_doc.recompute()
        Part.export([feature],str(OPTIONAL_DIR/(name+'.step')))
finally:
    App.closeDocument(print_doc.Name)

checks=[]
for gap in (145,150,215):
    xa=gap-128;ang=(xa+1-76)*360/pitch
    sc=axial(screw,x=xa,z=28,angle=ang);ft=pose(foot,(xa,0,0))
    checks.append(dict(gap=gap,body_screw_intersection_mm3=body.common(sc).Volume,
                       body_foot_intersection_mm3=body.common(ft).Volume,
                       screw_foot_intersection_mm3=sc.common(ft).Volume,
                       guide_overlap_mm=110-(xa-7.7),
                       screw_thread_engagement_mm=110-max(76,xa+0.7)))
report=dict(parameters=P,parts=info,assembly_clearances=checks,
            reference='(02) camera bracket 3MF; 82mm disk, 9x4.3mm on PCD45.03333',
            physical_fit_verified=False,physical_print_verified=False)
report['wrong_thread_phase_intersection_mm3']=body.common(axial(screw,x=a,z=28,angle=spin+181)).Volume
report['camera_plate_body_intersection_mm3']=body.common(assembly['05_camera_plate']).Volume
report['clip_screw_intersection_mm3']=assembly['02_screw'].common(assembly['04_retaining_clip']).Volume
report['clip_foot_intersection_mm3']=assembly['03_moving_foot'].common(assembly['04_retaining_clip']).Volume
(VERIFICATION_DIR/'CAD_Validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(checks,indent=2),flush=True)
print('Completed CAD exports',flush=True)
