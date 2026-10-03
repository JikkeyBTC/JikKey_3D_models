"""Eight concealed PLA latches with deeper engagement and reinforced leaves.
58x58x15.6 mm. No external latch windows, print pause, screws or glue.
"""
from pathlib import Path
import json
import sys
sys.path.append(r'C:/Program Files/FreeCAD 1.0/Mod')
import FreeCAD as A
import Part
import MeshPart
import Import

OUT=Path(__file__).resolve().parent.parent
OUT.mkdir(parents=True,exist_ok=True)
P=dict(outer=58.0,height_closed=15.6,corner_radius=4.0,floor=1.4,
       throat=6.0,throat_top=2.0,mouth=8.0,funnel_top=3.0,pitch=8.8,
       chamber=44.0,panel=50.0,panel_thickness=2.0,panel_recess=50.6,
       panel_seat=12.0,base_top=14.2,seam=5.8,male=53.0,male_radius=1.5,
       female=53.1,female_radius=1.55,roof=1.4,tab_width=8.0,
       slot_width=.6,tab_thickness=1.0,tab_root_z=14.4,tab_tip_z=6.2,
       latch_projection=.55,latch_bottom=6.2,latch_low_peak=6.8,
       latch_high_peak=7.2,latch_top=7.2,groove_bottom=6.15,
       groove_top=7.25,groove_depth=.65,groove_width=8.5,
       tab_back_clearance=.6,tab_root_fillet=.3,entry_chamfer=.3,
       guide_rib_projection=.10,guide_rib_width=1.2,guide_rib_position=20.0,tab_position=11.0,
       guide_rib_bottom=8.0,guide_rib_bottom_full=8.3,
       guide_rib_top_full=12.5,guide_rib_top=12.8)
doc=A.newDocument('DiceBox_StrongLockV2_Lid_50x50x2')
report=dict(parameters_mm=P,files={},checks={},
            limitations='Unstrained reference geometry. Guide-rib interference is intentional (nominal 0.05 mm at rib tips); it requires local deformation/burnishing. PLA fit, lock force, fracture and zero real-world movement cannot be guaranteed by CAD or slicing. Prototype required.')

def box(size,z,h,cx=0,cy=0):
    return Part.makeBox(size,size,h,A.Vector(cx-size/2,cy-size/2,z))

def rect(w,d,z,h,x,y):
    return Part.makeBox(w,d,h,A.Vector(x,y,z))

def rounded(size,z,h,r):
    s=box(size,z,h)
    es=[e for e in s.Edges if e.BoundBox.ZLength>h-1e-6]
    return s.makeFillet(r,es)

def square(size,z,x,y):
    q=size/2
    return Part.makePolygon([A.Vector(x-q,y-q,z),A.Vector(x+q,y-q,z),
                             A.Vector(x+q,y+q,z),A.Vector(x-q,y+q,z),
                             A.Vector(x-q,y-q,z)])

def rounded_wire(size,z,r):
    sample=rounded(size,z,1,r)
    return next(face.OuterWire for face in sample.Faces
                if abs(face.BoundBox.ZMin-z)<1e-7 and abs(face.BoundBox.ZMax-z)<1e-7)

def world_shape(shape):
    # Bake top-level placement into the geometry. The installed headless STEP
    # exporter otherwise ignores transformed feature shapes in this environment.
    s=shape.copy();matrix=s.Placement.toMatrix();s.Placement=A.Placement()
    return s.transformGeometry(matrix).removeSplitter()

def guide_wire(x,z,depth):
    f=P['female']/2;w=P['guide_rib_width']/2
    points=[A.Vector(x-w,f+.04,z),A.Vector(x+w,f+.04,z),
            A.Vector(x,f-depth,z),A.Vector(x-w,f+.04,z)]
    return Part.makePolygon(points)

def guide_rib(x):
    return Part.makeLoft([
        guide_wire(x,P['guide_rib_bottom'],.001),
        guide_wire(x,P['guide_rib_bottom_full'],P['guide_rib_projection']),
        guide_wire(x,P['guide_rib_top_full'],P['guide_rib_projection']),
        guide_wire(x,P['guide_rib_top'],.001)],True,True)

def pocket(x,y):
    lower=box(P['throat'],P['floor'],P['throat_top']-P['floor']+.001,x,y)
    funnel=Part.makeLoft([square(P['throat'],P['throat_top'],x,y),
                         square(P['mouth'],P['funnel_top'],x,y)],True,True)
    overlap=box(P['mouth'],P['funnel_top']-.001,.051,x,y)
    return lower.fuse(funnel).fuse(overlap).removeSplitter()

def rot(s,angle):
    a=s.copy();a.rotate(A.Vector(0,0,0),A.Vector(0,0,1),angle)
    return a

def at_site(shape,x,angle):
    s=shape.copy();s.translate(A.Vector(x,0,0));return rot(s,angle)

snap_sites=[(x,a) for a in [0,90,180,270] for x in [-P['tab_position'],P['tab_position']]]

def mesh(shape):
    return MeshPart.meshFromShape(Shape=shape,LinearDeflection=.025,
                                 AngularDeflection=.09,Relative=False)

def feat(name,shape,color=(.13,.16,.19)):
    o=doc.addObject('PartDesign::Feature',name);o.Shape=world_shape(shape)
    if o.ViewObject: o.ViewObject.ShapeColor=color
    return o

def write_part(name,shape,obj=None):
    assert shape.isValid() and len(shape.Solids)==1,(name,'invalid solid')
    obj=obj or feat(name,shape)
    m=mesh(shape)
    assert m.isSolid() and not m.hasNonManifolds(),(name,'mesh invalid')
    m.write(str(OUT/(name+'.stl')))
    Import.export([obj],str(OUT/(name+'.step')))
    reread=Part.read(str(OUT/(name+'.step')))
    assert reread.isValid() and len(reread.Solids)==1
    assert abs(reread.Volume-shape.Volume)<.01
    expected=shape.BoundBox;actual=reread.BoundBox
    assert max(abs(getattr(actual,k)-getattr(expected,k))
               for k in ['XMin','XMax','YMin','YMax','ZMin','ZMax'])<1e-5
    assert abs(reread.common(shape).Volume-shape.Volume)<.01
    b=shape.BoundBox
    report['files'][name]=dict(bbox_mm=[b.XLength,b.YLength,b.ZLength],
        volume_mm3=shape.Volume,solid_count=1,valid_solid=True,closed_stl=True,
        nonmanifold_stl=False,step_roundtrip_valid=True,
        step_world_orientation_and_position_verified=True,facets=m.CountFacets)
    return obj

# Lower shoulder and a reduced upper neck maintain a flush 58 mm exterior.
neck=rounded(P['male'],P['seam'],P['base_top']-P['seam'],P['male_radius'])
top_edges=[e for e in neck.Edges if abs(e.BoundBox.ZMin-P['base_top'])<1e-6
           and abs(e.BoundBox.ZMax-P['base_top'])<1e-6]
neck=neck.makeChamfer(.25,top_edges)
base=rounded(P['outer'],0,P['seam'],P['corner_radius']).fuse(neck)
base=base.cut(box(P['chamber'],P['funnel_top'],P['base_top']+.1))
base=base.cut(box(P['panel_recess'],P['panel_seat'],P['base_top']+.1))
centers=[(i-2)*P['pitch'] for i in range(5)]
base=base.cut(Part.makeCompound([pocket(x,y) for x in centers for y in centers]))
# Recesses are below the pane pocket, where the neck wall is thick.
groove=rect(P['groove_width'],P['groove_depth']+.1,P['groove_bottom'],
            P['groove_top']-P['groove_bottom'],-P['groove_width']/2,
            P['male']/2-P['groove_depth'])
base=base.cut(Part.makeCompound([at_site(groove,x,a) for x,a in snap_sites])).removeSplitter()
base_obj=write_part('DiceBox_StrongLockV2_Base',base)

# Open-bottom lid in closed-assembly coordinates. It is inverted for printing.
lid=rounded(P['outer'],P['seam'],P['height_closed']-P['seam'],P['corner_radius'])
cavity=rounded(P['female'],P['seam']-.1,P['base_top']-P['seam']+.1,P['female_radius'])
lid=lid.cut(cavity).cut(box(P['chamber'],P['base_top']-.001,P['roof']+.101))
entry=Part.makeLoft([
    rounded_wire(P['female']+2*P['entry_chamfer'],P['seam']-.001,
                 P['female_radius']+P['entry_chamfer']),
    rounded_wire(P['female'],P['seam']+P['entry_chamfer'],P['female_radius'])],True,True)
lid=lid.cut(entry)
f=P['female']/2
outer=P['outer']/2
slot_h=P['tab_root_z']-P['seam']
tab_w=P['tab_width'];gap=P['slot_width']
hidden_outer=f+P['tab_thickness']+P['tab_back_clearance']
cut_depth=hidden_outer-(f-.05)
side_cutters=[rect(gap,cut_depth,P['seam']-.05,slot_h+.05,-tab_w/2-gap,f-.05),
              rect(gap,cut_depth,P['seam']-.05,slot_h+.05,tab_w/2,f-.05),
              rect(tab_w,cut_depth,P['seam']-.05,P['tab_tip_z']-P['seam']+.05,-tab_w/2,f-.05),
              rect(tab_w,P['tab_back_clearance'],P['tab_tip_z'],
                   P['tab_root_z']-P['tab_tip_z'],-tab_w/2,f+P['tab_thickness'])]
cuts=[at_site(c,x,a) for x,a in snap_sites for c in side_cutters]
lid=lid.cut(Part.makeCompound(cuts)).removeSplitter()
# Radius the rear roots of the hidden leaf springs to reduce stress concentration.
root_edges=[e for e in lid.Edges
    if abs(e.BoundBox.ZMin-P['tab_root_z'])<1e-6 and abs(e.BoundBox.ZMax-P['tab_root_z'])<1e-6
    and ((abs(e.BoundBox.XLength-tab_w)<1e-6 and abs(abs(e.CenterOfMass.y)-(f+P['tab_thickness']))<1e-6)
         or (abs(e.BoundBox.YLength-tab_w)<1e-6 and abs(abs(e.CenterOfMass.x)-(f+P['tab_thickness']))<1e-6))]
assert len(root_edges)==8,('hidden root edge count',len(root_edges))
lid=lid.makeFillet(P['tab_root_fillet'],root_edges).removeSplitter()
# Sloped insertion face and a horizontal retaining shoulder. The deeper lip
# requires toolpath verification; actual overhang quality needs a PLA test print.
profile=[(f+.05,P['latch_bottom']),
         (f,P['latch_bottom']),
         (f-P['latch_projection'],P['latch_low_peak']),
         (f-P['latch_projection'],P['latch_high_peak']),
         (f,P['latch_top']),
         (f+.05,P['latch_top'])]
points=[A.Vector(-tab_w/2,y,z) for y,z in profile]
points.append(points[0])
barb=Part.Face(Part.makePolygon(points)).extrude(A.Vector(tab_w,0,0))
lid=lid.fuse(Part.makeCompound([at_site(barb,x,a) for x,a in snap_sites])).removeSplitter()
structural_lid=lid.copy()
rib_shapes=[rot(guide_rib(x),a) for a in [0,90,180,270]
            for x in [-P['guide_rib_position'],0,P['guide_rib_position']]]
guide_ribs=Part.makeCompound(rib_shapes)
lid=lid.fuse(guide_ribs).removeSplitter()
assert lid.isValid() and len(lid.Solids)==1
lid_assembled_obj=feat('Lid_Closed_REFERENCE',lid,(.24,.3,.34))
lid_print=lid.copy()
lid_print.rotate(A.Vector(0,0,0),A.Vector(1,0,0),180)
lid_print.translate(A.Vector(0,0,P['height_closed']))
lid_print_obj=write_part('DiceBox_StrongLockV2_Lid',lid_print)
if lid_print_obj.ViewObject:lid_print_obj.ViewObject.Visibility=False

panel=box(P['panel'],P['panel_seat'],P['panel_thickness'])
panel_obj=write_part('ClearPanel_50x50x2_REFERENCE',panel,
                     feat('ClearPanel_50x50x2_REFERENCE',panel,(.72,.91,.96)))
if panel_obj.ViewObject:panel_obj.ViewObject.Transparency=80
dice_shapes=[box(5,P['floor'],5,x,y) for y in centers for x in centers]
dice=Part.makeCompound(dice_shapes)
dice_obj=feat('Dice_25_REFERENCE',dice,(.88,.87,.79))
mesh(dice).write(str(OUT/'Dice_25_REFERENCE.stl'))
Import.export([dice_obj],str(OUT/'Dice_25_REFERENCE.step'))
assembly_path=OUT/'DiceBox_StrongLockV2_Assembly_REFERENCE.step'
Import.export([base_obj,lid_assembled_obj,panel_obj,dice_obj],str(assembly_path))
assembly_reread=Part.read(str(assembly_path))
assert assembly_reread.isValid() and len(assembly_reread.Solids)==28
assert abs(assembly_reread.Volume-(base.Volume+lid.Volume+panel.Volume+dice.Volume))<.01
mesh(lid).write(str(OUT/'Lid_Closed_REFERENCE.stl'))

# Optional matching rim for checking the same lid before printing the complete tray.
test_z=P['seam']-2.0
test_base=base.common(rect(100,100,test_z,P['base_top']-test_z,-50,-50))
test_base=test_base.cut(box(P['chamber'],test_z-.1,P['base_top']-test_z+.2)).removeSplitter()
test_base.translate(A.Vector(0,0,-test_z))
test_obj=write_part('OPTIONAL_StrongLockV2_Base_Rim_Test',test_base)
if test_obj.ViewObject:test_obj.ViewObject.Visibility=False

# A small exact crop of one hidden latch. The outer cover stays intact.
# This test checks a single PLA latch, not full-ring printer dimensional error.
coupon_x=P['tab_position']-7
coupon_crop=rect(14,6,test_z,P['height_closed']-test_z+.1,coupon_x,23)
coupon_base=base.common(coupon_crop).removeSplitter()
coupon_base.translate(A.Vector(-coupon_x,-23,-test_z))
coupon_lid=lid.common(coupon_crop).removeSplitter()
coupon_lid.rotate(A.Vector(0,0,0),A.Vector(1,0,0),180)
coupon_lid.translate(A.Vector(-coupon_x,29,P['height_closed']))
coupon_base_obj=write_part('OPTIONAL_StrongLockV2_Joint_Base_Test',coupon_base)
coupon_lid_obj=write_part('OPTIONAL_StrongLockV2_Joint_Lid_Test',coupon_lid)
for obj in [coupon_base_obj,coupon_lid_obj]:
    if obj.ViewObject:obj.ViewObject.Visibility=False

# Both actual print orientations in a single optional layout.
layout_doc=A.newDocument('StrongLockV2_Print_Layout')
layout_base=layout_doc.addObject('PartDesign::Feature','Base');layout_base.Shape=world_shape(base)
shifted_lid=lid_print.copy();shifted_lid.translate(A.Vector(68,0,0))
layout_lid=layout_doc.addObject('PartDesign::Feature','Lid');layout_lid.Shape=world_shape(shifted_lid)
layout_path=OUT/'DiceBox_StrongLockV2_Print_Layout.step'
Import.export([layout_base,layout_lid],str(layout_path))
layout_reread=Part.read(str(layout_path))
assert layout_reread.isValid() and len(layout_reread.Solids)==2
assert abs(layout_reread.Volume-(base.Volume+lid_print.Volume))<.01
assert abs(layout_reread.BoundBox.XLength-126)<1e-5
assert abs(layout_reread.BoundBox.ZMin)<1e-5
assert abs(layout_reread.common(Part.makeCompound([base,shifted_lid])).Volume-layout_reread.Volume)<.01
mesh(Part.makeCompound([base,shifted_lid])).write(str(OUT/'DiceBox_StrongLockV2_Print_Layout.stl'))

checks=report['checks']
checks['base_structural_lid_closed_intersection_mm3']=base.common(structural_lid).Volume
checks['intentional_guide_rib_contact_volume_mm3']=base.common(guide_ribs).Volume
checks['total_base_lid_reference_overlap_volume_mm3']=base.common(lid).Volume
assert 0<checks['intentional_guide_rib_contact_volume_mm3']<2
assert abs(checks['intentional_guide_rib_contact_volume_mm3']-
           checks['total_base_lid_reference_overlap_volume_mm3'])<1e-6
checks['panel_base_intersection_mm3']=base.common(panel).Volume
checks['panel_lid_intersection_mm3']=lid.common(panel).Volume
checks['dice_base_intersection_mm3']=base.common(dice).Volume
checks['dice_lid_intersection_mm3']=lid.common(dice).Volume
checks['vertical_panel_insertion_intersection_mm3']=base.common(
    box(P['panel'],P['panel_seat']+.001,30)).Volume
checks['offset_panel_insertion_max_intersection_mm3']=max(base.common(
    box(P['panel'],P['panel_seat']+.001,30,dx,dy)).Volume
    for dx in [-.29,0,.29] for dy in [-.29,0,.29])
checks['individual_dice_base_intersections_mm3']=[base.common(d).Volume for d in dice_shapes]
envelope=Part.makeCompound([Part.makeSphere(5*(3**.5)/2,
                A.Vector(x,y,(P['funnel_top']+P['panel_seat'])/2))
                for x in centers for y in centers])
checks['rotation_envelope_base_intersection_mm3']=base.common(envelope).Volume
checks['rotation_envelope_lid_intersection_mm3']=lid.common(envelope).Volume
checks['rotation_envelope_panel_intersection_mm3']=panel.common(envelope).Volume
checks['nominal_neck_fit_clearance_per_side_mm']=(P['female']-P['male'])/2
checks['panel_side_clearance_per_side_mm']=(P['panel_recess']-P['panel'])/2
checks['panel_top_clearance_mm']=P['base_top']-P['panel_seat']-P['panel_thickness']
checks['panel_overlap_per_side_mm']=(P['panel']-P['chamber'])/2
checks['snap_latch_deflection_required_mm']=P['latch_projection']-(P['female']-P['male'])/2
checks['snap_groove_radial_clearance_mm']=P['groove_depth']-checks['snap_latch_deflection_required_mm']
checks['hidden_tab_outward_air_clearance_mm']=P['tab_back_clearance']
checks['hidden_tab_air_clearance_after_insertion_deflection_mm']=P['tab_back_clearance']-checks['snap_latch_deflection_required_mm']
checks['hidden_tab_outer_cover_thickness_mm']=outer-hidden_outer
checks['guide_rib_nominal_interference_mm']=P['guide_rib_projection']-checks['nominal_neck_fit_clearance_per_side_mm']
checks['nominal_axial_lid_play_mm']=P['groove_top']-P['latch_top']
checks['latch_retaining_face_angle_from_horizontal_deg']=0.0
checks['guide_rib_count']=12
checks['latch_count']=8
checks['pocket_count']=25
checks['minimum_clear_tumble_height_mm']=P['panel_seat']-P['funnel_top']
checks['cube_5mm_space_diagonal_mm']=5*(3**.5)
checks['rotation_vertical_extra_clearance_mm']=checks['minimum_clear_tumble_height_mm']-5*(3**.5)
checks['snap_flexible_tab_length_mm']=P['tab_root_z']-P['tab_tip_z']
checks['total_closed_height_mm']=P['height_closed']
checks['height_change_vs_selected_slim_mm']=P['height_closed']-15.6
checks['assembly_step_valid_solid_count']=len(assembly_reread.Solids)
checks['print_layout_step_valid_solid_count']=len(layout_reread.Solids)
checks['lid_print_min_z_mm']=lid_print.BoundBox.ZMin
checks['base_print_min_z_mm']=base.BoundBox.ZMin

def shifted_intersection(base_shape,lid_shape,dx=0,dy=0,dz=0):
    moved=lid_shape.copy();moved.translate(A.Vector(dx,dy,dz))
    return base_shape.common(moved).Volume

checks['lift_0_04mm_structural_intersection_mm3']=shifted_intersection(base,structural_lid,dz=.04)
checks['lift_0_06mm_blocking_volume_mm3']=shifted_intersection(base,structural_lid,dz=.06)
checks['lateral_offset_0_04mm_max_structural_intersection_mm3']=max(
    shifted_intersection(base,structural_lid,dx=dx,dy=dy)
    for dx,dy in [(.04,0),(-.04,0),(0,.04),(0,-.04)])
# Prior hidden-lock V1 readback uses its verified printable STEP orientation.
previous_dir=OUT.parent/'dicebox-50x50x2-hidden-lock-pla'
if not (previous_dir/'DiceBox_HiddenLock_Base.step').is_file():
    previous_dir=OUT/'Baseline_HiddenLock'
previous_base=Part.read(str(previous_dir/'DiceBox_HiddenLock_Base.step'))
previous_lid=Part.read(str(previous_dir/'DiceBox_HiddenLock_Lid.step'))
previous_lid.rotate(A.Vector(0,0,0),A.Vector(1,0,0),180)
previous_lid.translate(A.Vector(0,0,15.6))
checks['previous_lift_0_04mm_reference_overlap_mm3']=shifted_intersection(previous_base,previous_lid,dz=.04)
checks['previous_lift_0_06mm_additional_blocking_volume_mm3']=shifted_intersection(previous_base,previous_lid,dz=.06)-checks['previous_lift_0_04mm_reference_overlap_mm3']
# The continuous cover is outside the hidden spring pockets, including all eight sites.
cover_probe=Part.makeCompound([at_site(rect(tab_w+2*gap+.1,.65,P['seam'],
    P['tab_root_z']-P['seam'],-tab_w/2-gap-.05,28.25),x,a) for x,a in snap_sites])
checks['external_cover_missing_volume_mm3']=cover_probe.cut(lid).Volume
# Screening only: ideal straight cantilever, not a fracture or withdrawal-force prediction.
checks['beam_effective_load_length_mm']=P['tab_root_z']-P['latch_top']
checks['ideal_cantilever_outer_fiber_strain']=1.5*P['tab_thickness']*checks['snap_latch_deflection_required_mm']/checks['beam_effective_load_length_mm']**2
checks['nominal_total_retaining_face_area_mm2']=P['tab_width']*checks['snap_latch_deflection_required_mm']*len(snap_sites)
for k,v in checks.items():
    if 'intersection_mm3' in k:
        assert v<1e-6,(k,v)
assert len(base.Solids)==len(lid_print.Solids)==1
assert abs(checks['snap_latch_deflection_required_mm']-.5)<1e-6
assert abs(checks['nominal_neck_fit_clearance_per_side_mm']-.05)<1e-6
assert abs(checks['nominal_axial_lid_play_mm']-.05)<1e-6
assert checks['lift_0_06mm_blocking_volume_mm3']>.001
assert checks['previous_lift_0_06mm_additional_blocking_volume_mm3']>.001
assert checks['external_cover_missing_volume_mm3']<1e-6
assert checks['hidden_tab_outer_cover_thickness_mm']>=.84
assert checks['hidden_tab_air_clearance_after_insertion_deflection_mm']>=.099
assert abs(checks['guide_rib_nominal_interference_mm']-.05)<1e-6
assert checks['minimum_clear_tumble_height_mm']>5*(3**.5)
assert abs(checks['snap_flexible_tab_length_mm']-8.2)<1e-6
assert abs(P['base_top']+P['roof']-P['height_closed'])<1e-6
assert abs(P['floor']/0.2-round(P['floor']/0.2))<1e-6
assert abs(P['roof']/0.2-round(P['roof']/0.2))<1e-6
assert abs(checks['lid_print_min_z_mm'])<1e-6
assert abs(checks['base_print_min_z_mm'])<1e-6

for name,value in P.items():
    base_obj.addProperty('App::PropertyLength',name,'Design dimensions (reference)')
    setattr(base_obj,name,value);base_obj.setEditorMode(name,1)
base_obj.addProperty('App::PropertyString','AssemblyNote','Manufacturing')
base_obj.AssemblyNote='PLA Strong Lock V2. Matched V2 base and lid required. Eight 1.0 mm internal leaves, 0.50 mm engagement, twelve guide ribs with 0.05 mm nominal tip interference. Continuous exterior cover. Higher intended retention; physical force and fracture require a prototype.'
# Save only the closed assembly in the native document.
doc.removeObject(lid_print_obj.Name)
doc.removeObject(test_obj.Name)
doc.removeObject(coupon_base_obj.Name)
doc.removeObject(coupon_lid_obj.Name)
doc.recompute()
doc.saveAs(str(OUT/'DiceBox_StrongLockV2_50x50x2.FCStd'))
(OUT/'Dimensions.json').write_text(json.dumps(P,indent=2),encoding='utf-8')
(OUT/'Validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
comparison=dict(baseline='Hidden Lock V1, user reports very easy separation',
    revised='PLA Strong Lock V2 with eight reinforced hidden leaves',
    lid_per_side_hard_clearance_mm={'before':.10,'after':.05},
    nominal_axial_lid_play_mm={'before':.05,'after':.05},
    latch_insertion_deflection_mm={'before':.30,'after':.50},
    latch_count={'before':4,'after':8},leaf_thickness_mm={'before':.8,'after':1.0},
    leaf_effective_load_length_mm={'before':6.4,'after':7.2},
    nominal_total_retaining_face_area_mm2={'before':9.6,'after':32.0},
    retaining_face_angle_from_horizontal_deg={'before':0,'after':0},
    externally_visible_latch_slots={'before':False,'after':False},
    guide_rib_nominal_interference_mm={'before':.02,'after':.05},
    guide_rib_count={'before':8,'after':12},
    panel_pocket_changed=False,dice_pockets_changed=False,overall_size_changed=False,
    old_and_new_parts_interchangeable=False,
    design_basis='PLA. User can pull V1 lid and base apart with very little force. Physical cause is not proven; deeper engagement, eight leaves and lower lateral clearance address geometric retention sensitivity. Actual printed dimensions, hook condition and pull force were not measured.',
    limitations=report['limitations'])
(OUT/'Fit_Comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
