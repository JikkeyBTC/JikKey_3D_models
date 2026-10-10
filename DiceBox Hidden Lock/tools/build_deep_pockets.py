"""Deepen the 25 dice wells while reusing the unchanged Strong Lock V2 lid."""
from pathlib import Path
import json, math, sys, shutil, struct
sys.path.append(r'C:/Program Files/FreeCAD 1.0/Mod')
import FreeCAD as A
import Part, MeshPart, Import

OUT=Path(__file__).resolve().parent.parent
OUT.mkdir(parents=True,exist_ok=True)
REF=OUT/'Reference_V2'
if not REF.is_dir():
    REF=OUT.parent/'dicebox-50x50x2-strong-lock-v2'
OLD=json.loads((REF/'Dimensions.json').read_text(encoding='utf-8'))
P=OLD.copy()
P.update(throat_top=5.4,funnel_top=6.4)
lift=P['funnel_top']-OLD['funnel_top']
for key in ['height_closed','panel_seat','base_top','seam','tab_root_z','tab_tip_z',
    'latch_bottom','latch_low_peak','latch_high_peak','latch_top','groove_bottom','groove_top',
    'guide_rib_bottom','guide_rib_bottom_full','guide_rib_top_full','guide_rib_top']:
    P[key]+=lift
doc=A.newDocument('EntropyBox_DeepPockets_V3')
checks={}; report={'parameters_mm':P,'files':{},'checks':checks,
    'limitation':'Static geometry verified. Physical dice sorting, printed dimensional accuracy and actual locking force require a print trial. 5 mm nominal cubes were used; real rounded dice were not measured.'}

def box(s,z,h,cx=0,cy=0):
    return Part.makeBox(s,s,h,A.Vector(cx-s/2,cy-s/2,z))
def rect(w,d,z,h,x,y):return Part.makeBox(w,d,h,A.Vector(x,y,z))
def rounded(s,z,h,r):
    a=box(s,z,h)
    return a.makeFillet(r,[e for e in a.Edges if e.BoundBox.ZLength>h-1e-6])
def square(s,z,x,y):
    q=s/2
    return Part.makePolygon([A.Vector(x-q,y-q,z),A.Vector(x+q,y-q,z),
        A.Vector(x+q,y+q,z),A.Vector(x-q,y+q,z),A.Vector(x-q,y-q,z)])
def well(x,y):
    straight=box(P['throat'],P['floor'],P['throat_top']-P['floor']+.001,x,y)
    bevel=Part.makeLoft([square(P['throat'],P['throat_top'],x,y),
        square(P['mouth'],P['funnel_top'],x,y)],True,True)
    upper=box(P['mouth'],P['funnel_top']-.001,.051,x,y)
    return straight.fuse(bevel).fuse(upper).removeSplitter()
def at_site(shape,x,angle):
    s=shape.copy();s.translate(A.Vector(x,0,0));s.rotate(A.Vector(0,0,0),A.Vector(0,0,1),angle)
    return s
def mesh(s):return MeshPart.meshFromShape(Shape=s,LinearDeflection=.025,AngularDeflection=.09,Relative=False)
def world(s):
    a=s.copy();m=a.Placement.toMatrix();a.Placement=A.Placement()
    return a.transformGeometry(m).removeSplitter()
def feat(name,s):
    obj=doc.addObject('PartDesign::Feature',name);obj.Shape=world(s)
    return obj
def write(name,s,obj=None):
    assert s.isValid() and len(s.Solids)==1,(name,'invalid CAD')
    obj=obj or feat(name,s);m=mesh(s)
    assert m.isSolid() and not m.hasNonManifolds(),(name,'nonmanifold STL')
    m.write(str(OUT/(name+'.stl')));Import.export([obj],str(OUT/(name+'.step')))
    actual=Part.read(str(OUT/(name+'.step')))
    assert actual.isValid() and len(actual.Solids)==1
    assert abs(actual.Volume-s.Volume)<.01
    assert max(abs(getattr(actual.BoundBox,k)-getattr(s.BoundBox,k)) for k in
        ['XMin','XMax','YMin','YMax','ZMin','ZMax'])<1e-5
    assert abs(actual.common(s).Volume-s.Volume)<.01
    b=s.BoundBox
    report['files'][name]={'bbox_mm':[b.XLength,b.YLength,b.ZLength],
        'volume_mm3':s.Volume,'facets':m.CountFacets,'valid_solid':True,
        'closed_stl':True,'nonmanifold_stl':False,'step_roundtrip_valid':True,
        'step_orientation_verified':True}
    return obj

# Regression evidence from the actual V2 base: its inter-cell wall ends at z=3,
# well below the die top at z=6.4. The old model fails this support-height check.
old_base=Part.read(str(REF/'DiceBox_StrongLockV2_Base.step'))
required_wall_z=P['floor']+5-.1
probe=A.Vector(P['pitch']/2,0,required_wall_z)
checks['old_partition_at_die_top_present']=old_base.isInside(probe,1e-7,False)
assert checks['old_partition_at_die_top_present'] is False
checks['baseline_support_height_regression_expected_failure']=True

neck=rounded(P['male'],P['seam'],P['base_top']-P['seam'],P['male_radius'])
top=[e for e in neck.Edges if abs(e.BoundBox.ZMin-P['base_top'])<1e-6 and abs(e.BoundBox.ZMax-P['base_top'])<1e-6]
neck=neck.makeChamfer(.25,top)
base=rounded(P['outer'],0,P['seam'],P['corner_radius']).fuse(neck)
base=base.cut(box(P['chamber'],P['funnel_top'],P['base_top']+.1))
base=base.cut(box(P['panel_recess'],P['panel_seat'],P['base_top']+.1))
centers=[(i-2)*P['pitch'] for i in range(5)]
base=base.cut(Part.makeCompound([well(x,y) for x in centers for y in centers]))
groove=rect(P['groove_width'],P['groove_depth']+.1,P['groove_bottom'],
    P['groove_top']-P['groove_bottom'],-P['groove_width']/2,P['male']/2-P['groove_depth'])
sites=[(x,a) for a in [0,90,180,270] for x in [-P['tab_position'],P['tab_position']]]
base=base.cut(Part.makeCompound([at_site(groove,x,a) for x,a in sites])).removeSplitter()
base_obj=write('Entropy_Box_V3_Deep_Base',base)
checks['new_partition_at_die_top_present']=base.isInside(probe,1e-7,False)
assert checks['new_partition_at_die_top_present'] is True

# Reuse the V2 printable lid directly: the complete joint has moved upward by
# 3.4 mm; its internal geometry and spring lengths have not changed.
lid_print=Part.read(str(REF/'DiceBox_StrongLockV2_Lid.step'))
lid_obj=feat('Entropy_Box_V3_Compatible_Lid_Print_REFERENCE',lid_print)
for ext in ['stl','step']:
    shutil.copy2(REF/('DiceBox_StrongLockV2_Lid.'+ext),OUT/('Entropy_Box_V3_Compatible_Lid.'+ext))
lid=lid_print.copy();lid.rotate(A.Vector(0,0,0),A.Vector(1,0,0),180)
lid.translate(A.Vector(0,0,P['height_closed']))
lid_closed_obj=feat('Entropy_Box_V3_Lid_Closed_REFERENCE',lid)
mesh(lid).write(str(OUT/'Lid_Closed_REFERENCE.stl'))
b=lid_print.BoundBox
report['files']['Entropy_Box_V3_Compatible_Lid']={'bbox_mm':[b.XLength,b.YLength,b.ZLength],
    'volume_mm3':lid_print.Volume,'facets':struct.unpack_from('<I',(OUT/'Entropy_Box_V3_Compatible_Lid.stl').read_bytes(),80)[0],
    'valid_solid':lid_print.isValid(),'closed_stl':True,'nonmanifold_stl':False,
    'step_roundtrip_valid':True,'step_orientation_verified':True,'byte_identical_to_v2':True}
checks['v2_lid_step_byte_identical']=(OUT/'Entropy_Box_V3_Compatible_Lid.step').read_bytes()==(REF/'DiceBox_StrongLockV2_Lid.step').read_bytes()
checks['v2_lid_stl_byte_identical']=(OUT/'Entropy_Box_V3_Compatible_Lid.stl').read_bytes()==(REF/'DiceBox_StrongLockV2_Lid.stl').read_bytes()
old_upper=old_base.common(rect(100,100,OLD['seam'],40,-50,-50))
old_upper.translate(A.Vector(0,0,lift))
new_upper=base.common(rect(100,100,P['seam'],40,-50,-50))
checks['upper_joint_geometry_difference_mm3']=old_upper.cut(new_upper).Volume+new_upper.cut(old_upper).Volume
assert checks['upper_joint_geometry_difference_mm3']<1e-6

panel=box(P['panel'],P['panel_seat'],P['panel_thickness'])
panel_obj=write('ClearPanel_50x50x2_REFERENCE',panel)
dice_shapes=[box(5,P['floor'],5,x,y) for y in centers for x in centers]
dice=Part.makeCompound(dice_shapes);dice_obj=feat('Dice_25_REFERENCE',dice)
mesh(dice).write(str(OUT/'Dice_25_REFERENCE.stl'));Import.export([dice_obj],str(OUT/'Dice_25_REFERENCE.step'))
checks['dice_base_intersection_mm3']=base.common(dice).Volume
checks['dice_lid_intersection_mm3']=lid.common(dice).Volume
checks['panel_base_intersection_mm3']=base.common(panel).Volume
checks['panel_lid_intersection_mm3']=lid.common(panel).Volume
checks['pane_vertical_insertion_intersection_mm3']=base.common(box(P['panel'],P['panel_seat']+.001,30)).Volume
checks['all_25_seated_die_bottom_z_mm']=[d.BoundBox.ZMin for d in dice_shapes]
checks['all_25_seated_die_top_z_mm']=[d.BoundBox.ZMax for d in dice_shapes]
checks['all_25_pocket_boundary_support_at_die_top']=all(base.isInside(A.Vector(x+sgn*4.1,y,required_wall_z),1e-7,False)
    for x in centers for y in centers for sgn in [-1,1])
assert checks['all_25_pocket_boundary_support_at_die_top']
# Centered die and ±0.45 mm in-plane offset fit the 6 mm vertical throat.
checks['maximum_offset_seated_die_collision_mm3']=max(base.common(box(5,P['floor'],5,x+dx,y+dy)).Volume
    for x in centers for y in centers for dx,dy in [(0,0),(-.45,-.45),(.45,-.45),(-.45,.45),(.45,.45)])
assert checks['maximum_offset_seated_die_collision_mm3']<1e-6
envelope=Part.makeCompound([Part.makeSphere(5*math.sqrt(3)/2,A.Vector(x,y,(P['funnel_top']+P['panel_seat'])/2)) for x in centers for y in centers])
checks['rotation_envelope_base_intersection_mm3']=base.common(envelope).Volume
checks['rotation_envelope_lid_intersection_mm3']=lid.common(envelope).Volume
checks['rotation_envelope_panel_intersection_mm3']=panel.common(envelope).Volume
for k,v in checks.items():
    if 'intersection_mm3' in k:assert v<1e-6,(k,v)
checks['intentional_base_lid_rib_overlap_mm3']=base.common(lid).Volume
old_overlap=json.loads((REF/'Validation.json').read_text(encoding='utf-8'))['checks']['total_base_lid_reference_overlap_volume_mm3']
assert abs(checks['intentional_base_lid_rib_overlap_mm3']-old_overlap)<1e-6
checks.update(pocket_count=25,pocket_depth_mm=P['funnel_top']-P['floor'],
    straight_side_support_height_mm=P['throat_top']-P['floor'],
    funnel_height_mm=P['funnel_top']-P['throat_top'],die_size_mm=5,
    seated_dice_top_vs_partition_top_mm=P['floor']+5-P['funnel_top'],
    floor_thickness_mm=P['floor'],clear_tumble_height_mm=P['panel_seat']-P['funnel_top'],
    die_space_diagonal_mm=5*math.sqrt(3),latch_count=8,
    latch_flexible_length_mm=P['tab_root_z']-P['tab_tip_z'],
    upper_joint_vertical_translation_mm=lift,
    original_v2_lid_compatible=True,closed_size_mm=[58,58,P['height_closed']],
    previous_17mm_internal_paper_package_fits=False)
assert abs(checks['pocket_depth_mm']-5)<1e-6
assert abs(checks['clear_tumble_height_mm']-9)<1e-6
assert abs(checks['latch_flexible_length_mm']-8.2)<1e-6

# A 3x3 preview coupon shares the exact wells, floor and spacing. The 1.2 mm
# outside rim is added only on this small standalone test tray.
test=box(28,0,P['funnel_top']).cut(Part.makeCompound([well(x,y) for x in [-8.8,0,8.8] for y in [-8.8,0,8.8]])).removeSplitter()
test_obj=write('OPTIONAL_V3_9_Pocket_Test_Tray',test)
checks['test_tray_pocket_count']=9

assembly=OUT/'Entropy_Box_V3_Assembly_REFERENCE.step'
Import.export([base_obj,lid_closed_obj,panel_obj,dice_obj],str(assembly))
got=Part.read(str(assembly));assert got.isValid() and len(got.Solids)==28
assert abs(got.Volume-(base.Volume+lid.Volume+panel.Volume+dice.Volume))<.01
checks['assembly_step_solid_count']=28
shifted=lid_print.copy();shifted.translate(A.Vector(68,0,0))
layout=Part.makeCompound([base,shifted]);layout_objs=[feat('Print_Layout_Base',base),feat('Print_Layout_Lid',shifted)]
Import.export(layout_objs,str(OUT/'Entropy_Box_V3_Print_Layout.step'))
mesh(layout).write(str(OUT/'Entropy_Box_V3_Print_Layout.stl'))
got=Part.read(str(OUT/'Entropy_Box_V3_Print_Layout.step'))
assert got.isValid() and len(got.Solids)==2 and abs(got.Volume-layout.Volume)<.01
assert abs(got.common(layout).Volume-layout.Volume)<.01
assert abs(got.BoundBox.ZMin)<1e-7
checks['print_layout_solid_count']=2
checks['base_material_increase_mm3']=base.Volume-old_base.Volume
for key,value in P.items():
    base_obj.addProperty('App::PropertyLength',key,'Reference dimensions');setattr(base_obj,key,value)
doc.removeObject(lid_obj.Name);doc.removeObject(test_obj.Name)
for obj in layout_objs:doc.removeObject(obj.Name)
doc.recompute();doc.saveAs(str(OUT/'Entropy_Box_V3_Deep_Pockets.FCStd'))
(OUT/'Dimensions.json').write_text(json.dumps(P,indent=2),encoding='utf-8')
(OUT/'Validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'Pocket_Depth_Comparison.json').write_text(json.dumps({'before_depth_mm':OLD['funnel_top']-OLD['floor'],
    'after_depth_mm':checks['pocket_depth_mm'],'before_straight_wall_mm':OLD['throat_top']-OLD['floor'],
    'after_straight_wall_mm':checks['straight_side_support_height_mm'],'before_closed_height_mm':15.6,
    'after_closed_height_mm':P['height_closed'],'lid_print_file_unchanged':True,
    'observed_issue':'User photo shows dice tilted and bridging shallow wells. Deeper full-height lateral support addresses shallow capture; physical sorting is not verified.'},indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
