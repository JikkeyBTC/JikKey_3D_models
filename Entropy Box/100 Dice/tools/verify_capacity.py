"""Check delivered geometry: 100 seated 5 mm dice, support and fit.

The 25-die source fails the capacity check. No builder helpers are imported.
"""
from pathlib import Path
import sys, json, math
import FreeCAD as A
import Part

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
baseline = '--baseline' in sys.argv
names = ('Entropy_Box_V3_Deep_Base', 'Entropy_Box_V3_Compatible_Lid', 'Dice_25_REFERENCE') if baseline else ('Entropy_Box_100_V3_Base', 'Entropy_Box_100_V3_Lid', 'Dice_100_REFERENCE')
base, lid_print, dice = [Part.read(str(root / (name + '.step'))) for name in names]
assert len(dice.Solids) == 100, f'Capacity requires 100 separate dice; delivered reference contains {len(dice.Solids)}'
assert base.isValid() and len(base.Solids) == 1
assert lid_print.isValid() and len(lid_print.Solids) == 1
assert abs(base.BoundBox.XLength - 108) < 1e-5
assert abs(base.BoundBox.YLength - 108) < 1e-5
assert abs(base.BoundBox.ZLength - 17.6) < 1e-5
assert abs(lid_print.BoundBox.XLength - 108) < 1e-5
assert abs(lid_print.BoundBox.YLength - 108) < 1e-5
assert abs(lid_print.BoundBox.ZLength - 9.8) < 1e-5
assert abs(base.BoundBox.ZMin) < 1e-6 and abs(lid_print.BoundBox.ZMin) < 1e-6

# Literal centrelines checked from a 10 x 10 array at 8.8 mm spacing.
centres = [-39.6, -30.8, -22.0, -13.2, -4.4, 4.4, 13.2, 22.0, 30.8, 39.6]
for x in centres:
    for y in centres:
        assert not base.isInside(A.Vector(x, y, 2.0), 1e-7, False), ('blocked well', x, y)
        assert base.isInside(A.Vector(x, y, 1.3), 1e-7, False), ('missing floor', x, y)
        for dx, dy in [(4.1, 0), (-4.1, 0), (0, 4.1), (0, -4.1)]:
            assert base.isInside(A.Vector(x + dx, y + dy, 6.3), 1e-7, False), ('unsupported die boundary', x, y, dx, dy)
        assert not base.isInside(A.Vector(x + 3.1, y, 6.3), 1e-7, False), ('funnel blocked', x, y)
for die in dice.Solids:
    assert max(abs(getattr(die.BoundBox, key) - 5) for key in ['XLength', 'YLength', 'ZLength']) < 1e-6
    assert abs(die.BoundBox.ZMin - 1.4) < 1e-6
    assert abs(die.BoundBox.ZMax - 6.4) < 1e-6
assert base.common(dice).Volume < 1e-6

lid = lid_print.copy()
lid.rotate(A.Vector(0, 0, 0), A.Vector(1, 0, 0), 180)
lid.translate(A.Vector(0, 0, 19))
panel = Part.read(str(root / 'ClearPanel_100x100x2_REFERENCE.step'))
assert panel.isValid() and len(panel.Solids) == 1
assert abs(panel.BoundBox.XLength - 100) < 1e-6
assert abs(panel.BoundBox.ZMin - 15.4) < 1e-6
assert base.common(panel).Volume < 1e-6
assert lid.common(panel).Volume < 1e-6
assert lid.common(dice).Volume < 1e-6
assert abs(lid.BoundBox.ZMax - 19) < 1e-6

# Closed-state retaining shoulders must block withdrawal after 0.05 mm play.
# Guide ribs account for a small intentional contact volume at zero displacement.
static_overlap = base.common(lid).Volume
lifted = lid.copy(); lifted.translate(A.Vector(0, 0, .06))
assert lifted.common(base).Volume > static_overlap + .005, 'No additional retaining shoulder engagement when lid lifts'
assert 0 < static_overlap < 2, ('excessive or absent guide-rib contact', static_overlap)

assembly = Part.read(str(root / 'Entropy_Box_100_V3_Assembly_REFERENCE.step'))
assert assembly.isValid() and len(assembly.Solids) == 103
assert abs(assembly.BoundBox.XLength - 108) < 1e-5
assert abs(assembly.BoundBox.ZLength - 19) < 1e-5
layout = Part.read(str(root / 'Entropy_Box_100_V3_Print_Layout.step'))
assert layout.isValid() and len(layout.Solids) == 2
assert abs(layout.BoundBox.XLength - 226) < 1e-5
assert abs(layout.BoundBox.ZMin) < 1e-6

result = dict(capacity=100, array=[10, 10], seated_die_size_mm=5,
              closed_size_mm=[108, 108, 19], pocket_depth_mm=5,
              all_wells_have_floor_and_full_height_support=True,
              pane_size_mm=[100, 100, 2], pane_and_dice_collisions_mm3=0,
              lid_withdrawal_shoulder_blocks=True, intentional_rib_contact_mm3=static_overlap,
              assembly_solid_count=103, print_layout_solid_count=2,
              limitations='Static geometry only. Physical sorting, PLA fit/warping and withdrawal force are not measured.')
(root / 'Independent_Capacity_Validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
