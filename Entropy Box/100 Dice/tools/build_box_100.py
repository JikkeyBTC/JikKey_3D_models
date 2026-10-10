"""Entropy Box V3 expanded to 100 5 mm dice and a 100x100x2 mm pane.
108x108x19 mm. V3 pocket, floor, hook and joint cross-sections retained.
"""
from pathlib import Path
import json, math, sys
sys.path.append(r'C:/Program Files/FreeCAD 1.0/Mod')
import FreeCAD as A
import Part, MeshPart, Import
OUT = Path(__file__).resolve().parent.parent
OUT.mkdir(parents=True, exist_ok=True)
P = {'outer': 108.0, 'height_closed': 19.0, 'corner_radius': 4.0, 'floor': 1.4, 'throat': 6.0, 'throat_top': 5.4, 'mouth': 8.0, 'funnel_top': 6.4, 'pitch': 8.8, 'chamber': 88.0, 'panel': 100.0, 'panel_thickness': 2.0, 'panel_recess': 100.6, 'panel_seat': 15.4, 'base_top': 17.6, 'seam': 9.2, 'male': 103.0, 'male_radius': 1.5, 'female': 103.1, 'female_radius': 1.55, 'roof': 1.4, 'tab_width': 8.0, 'slot_width': 0.6, 'tab_thickness': 1.0, 'tab_root_z': 17.8, 'tab_tip_z': 9.600000000000001, 'latch_projection': 0.55, 'latch_bottom': 9.600000000000001, 'latch_low_peak': 10.2, 'latch_high_peak': 10.600000000000001, 'latch_top': 10.600000000000001, 'groove_bottom': 9.55, 'groove_top': 10.65, 'groove_depth': 0.65, 'groove_width': 8.5, 'tab_back_clearance': 0.6, 'tab_root_fillet': 0.3, 'entry_chamfer': 0.3, 'guide_rib_projection': 0.1, 'guide_rib_width': 1.2, 'guide_rib_position': 45.0, 'tab_position': 11.0, 'guide_rib_bottom': 11.4, 'guide_rib_bottom_full': 11.700000000000001, 'guide_rib_top_full': 15.9, 'guide_rib_top': 16.200000000000003}
GRID = 10
LATCH_POS = [-36.0, -14.0, 14.0, 36.0]
GUIDE_POS = [-45.0, -25.0, 0.0, 25.0, 45.0]
doc = A.newDocument('EntropyBox_100_V3')
report = dict(parameters_mm=P, files={}, checks={},
              limitations='Static geometry verified. Physical 100-dice sorting, PLA warping, printed fit and latch force require a print trial. Reference dice are nominal 5 mm cubes.')
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

snap_sites=[(x,a) for a in [0,90,180,270] for x in LATCH_POS]

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

# Lower shoulder and a reduced upper neck maintain a flush 108 mm exterior.
neck=rounded(P['male'],P['seam'],P['base_top']-P['seam'],P['male_radius'])
top_edges=[e for e in neck.Edges if abs(e.BoundBox.ZMin-P['base_top'])<1e-6
           and abs(e.BoundBox.ZMax-P['base_top'])<1e-6]
neck=neck.makeChamfer(.25,top_edges)
base=rounded(P['outer'],0,P['seam'],P['corner_radius']).fuse(neck)
base=base.cut(box(P['chamber'],P['funnel_top'],P['base_top']+.1))
base=base.cut(box(P['panel_recess'],P['panel_seat'],P['base_top']+.1))
centers=[(i-4.5)*P['pitch'] for i in range(GRID)]
base=base.cut(Part.makeCompound([pocket(x,y) for x in centers for y in centers]))
# Recesses are below the pane pocket, where the neck wall is thick.
groove=rect(P['groove_width'],P['groove_depth']+.1,P['groove_bottom'],
            P['groove_top']-P['groove_bottom'],-P['groove_width']/2,
            P['male']/2-P['groove_depth'])
base=base.cut(Part.makeCompound([at_site(groove,x,a) for x,a in snap_sites])).removeSplitter()
base_obj=write_part('Entropy_Box_100_V3_Base',base)

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
assert len(root_edges)==16,('hidden root edge count',len(root_edges))
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
            for x in GUIDE_POS]
guide_ribs=Part.makeCompound(rib_shapes)
lid=lid.fuse(guide_ribs).removeSplitter()
assert lid.isValid() and len(lid.Solids)==1
lid_assembled_obj=feat('Lid_Closed_REFERENCE',lid,(.24,.3,.34))
lid_print=lid.copy()
lid_print.rotate(A.Vector(0,0,0),A.Vector(1,0,0),180)
lid_print.translate(A.Vector(0,0,P['height_closed']))
lid_print_obj=write_part('Entropy_Box_100_V3_Lid',lid_print)
if lid_print_obj.ViewObject:lid_print_obj.ViewObject.Visibility=False

panel=box(P['panel'],P['panel_seat'],P['panel_thickness'])
panel_obj=write_part('ClearPanel_100x100x2_REFERENCE',panel,
                     feat('ClearPanel_100x100x2_REFERENCE',panel,(.72,.91,.96)))
if panel_obj.ViewObject:panel_obj.ViewObject.Transparency=80
dice_shapes=[box(5,P['floor'],5,x,y) for y in centers for x in centers]
dice=Part.makeCompound(dice_shapes)
dice_obj=feat('Dice_100_REFERENCE',dice,(.88,.87,.79))
mesh(dice).write(str(OUT/'Dice_100_REFERENCE.stl'))
Import.export([dice_obj],str(OUT/'Dice_100_REFERENCE.step'))
assembly_path=OUT/'Entropy_Box_100_V3_Assembly_REFERENCE.step'
Import.export([base_obj,lid_assembled_obj,panel_obj,dice_obj],str(assembly_path))
assembly_reread=Part.read(str(assembly_path))
assert assembly_reread.isValid() and len(assembly_reread.Solids)==103
assert abs(assembly_reread.Volume-(base.Volume+lid.Volume+panel.Volume+dice.Volume))<.01
mesh(lid).write(str(OUT/'Lid_Closed_REFERENCE.stl'))

# Both actual print orientations in a single optional layout.
layout_doc=A.newDocument('EntropyBox100_Print_Layout')
layout_base=layout_doc.addObject('PartDesign::Feature','Base');layout_base.Shape=world_shape(base)
shifted_lid=lid_print.copy();shifted_lid.translate(A.Vector(118,0,0))
layout_lid=layout_doc.addObject('PartDesign::Feature','Lid');layout_lid.Shape=world_shape(shifted_lid)
layout_path=OUT/'Entropy_Box_100_V3_Print_Layout.step'
Import.export([layout_base,layout_lid],str(layout_path))
layout_reread=Part.read(str(layout_path))
assert layout_reread.isValid() and len(layout_reread.Solids)==2
assert abs(layout_reread.Volume-(base.Volume+lid_print.Volume))<.01
assert abs(layout_reread.BoundBox.XLength-226)<1e-5
assert abs(layout_reread.BoundBox.ZMin)<1e-5
assert abs(layout_reread.common(Part.makeCompound([base,shifted_lid])).Volume-layout_reread.Volume)<.01
mesh(Part.makeCompound([base,shifted_lid])).write(str(OUT/'Entropy_Box_100_V3_Print_Layout.stl'))

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
checks['guide_rib_count']=20
checks['latch_count']=16
checks['pocket_count']=100
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

checks['closed_size_mm'] = [108,108,19]
checks['array_columns'] = GRID
checks['array_rows'] = GRID
checks['pane_size_mm'] = [100,100,2]
checks['pocket_depth_mm'] = P['funnel_top'] - P['floor']
checks['straight_side_support_height_mm'] = P['throat_top'] - P['floor']
checks['funnel_height_mm'] = P['funnel_top'] - P['throat_top']
checks['latch_positions_per_side_mm'] = LATCH_POS
checks['guide_positions_per_side_mm'] = GUIDE_POS
# Same spring geometry as V3; the outer wall remains solid at all 16 leaves.
hidden_cover = Part.makeCompound([at_site(rect(tab_w+2*gap,.65,P['seam'],
    P['tab_root_z']-P['seam'],-tab_w/2-gap,P['outer']/2-.75),x,a)
    for x,a in snap_sites])
checks['external_cover_missing_volume_mm3'] = hidden_cover.cut(lid).Volume
checks['all_100_seated_die_floor_z_mm'] = [d.BoundBox.ZMin for d in dice_shapes]
checks['all_100_seated_die_top_z_mm'] = [d.BoundBox.ZMax for d in dice_shapes]
checks['all_100_full_height_side_support'] = all(base.isInside(
    A.Vector(x+dx,y+dy,6.3),1e-7,False)
    for x in centers for y in centers for dx,dy in [(4.1,0),(-4.1,0),(0,4.1),(0,-4.1)])
assert checks['all_100_full_height_side_support']
for k,v in checks.items():
    if 'intersection_mm3' in k: assert v < 1e-6, (k,v)
assert checks['external_cover_missing_volume_mm3'] < 1e-6
assert abs(checks['pocket_depth_mm']-5) < 1e-6
assert abs(checks['minimum_clear_tumble_height_mm']-9) < 1e-6
assert abs(checks['nominal_neck_fit_clearance_per_side_mm']-.05) < 1e-6
assert abs(checks['snap_latch_deflection_required_mm']-.5) < 1e-6
assert abs(checks['nominal_axial_lid_play_mm']-.05) < 1e-6
assert checks['lift_0_06mm_blocking_volume_mm3'] > .005
assert checks['hidden_tab_outer_cover_thickness_mm'] >= .849
assert checks['hidden_tab_air_clearance_after_insertion_deflection_mm'] >= .099
assert abs(checks['guide_rib_nominal_interference_mm']-.05) < 1e-6
assert abs(checks['snap_flexible_tab_length_mm']-8.2) < 1e-6
assert abs(checks['panel_side_clearance_per_side_mm']-.3) < 1e-6
assert abs(checks['panel_top_clearance_mm']-.2) < 1e-6
assert abs(checks['panel_overlap_per_side_mm']-6) < 1e-6
# Check geometric conservation against the supplied V3 pocket cross-section.
reference = OUT.parent/'entropy-box-deep-pockets-v3/Entropy_Box_V3_Deep_Base.step'
if reference.is_file():
    previous = Part.read(str(reference))
    crop = rect(8.8,8.8,0,6.4,-4.4,-4.4)
    old_cell = previous.common(crop)
    new_cell = base.common(rect(8.8,8.8,0,6.4,0,0))
    new_cell.translate(A.Vector(-4.4,-4.4,0))
    difference = new_cell.cut(old_cell).Volume + old_cell.cut(new_cell).Volume
    assert difference < 1e-6, ('V3 pocket profile changed', difference)
    checks['pocket_profile_difference_vs_v3_mm3'] = difference

# Export real section geometry for the preview only.
keep = rect(130,90,0,30,-65,-4.4)
for name,shape in [('Base_Section_REFERENCE',base),('Dice_Section_REFERENCE',dice)]:
    mesh(shape.common(keep)).write(str(OUT/(name+'.stl')))
for key,value in P.items():
    base_obj.addProperty('App::PropertyLength',key,'Reference dimensions')
    setattr(base_obj,key,value)
    base_obj.setEditorMode(key,1)
base_obj.addProperty('App::PropertyInteger','DiceCapacity','Reference dimensions')
base_obj.DiceCapacity = 100
doc.removeObject(lid_print_obj.Name)
doc.recompute()
doc.saveAs(str(OUT/'Entropy_Box_100_V3.FCStd'))
(OUT/'Dimensions.json').write_text(json.dumps(P,indent=2),encoding='utf-8')
(OUT/'Validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
