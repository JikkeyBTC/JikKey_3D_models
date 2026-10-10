from pathlib import Path
import sys,json
sys.path.append(r'C:/Program Files/FreeCAD 1.0/Mod')
import FreeCAD as A
import Part,MeshPart
root=Path(__file__).resolve().parent.parent
P=json.loads((root/'Dimensions.json').read_text(encoding='utf-8'))
base=Part.read(str(root/'Entropy_Box_V3_Deep_Base.step'))
dice=Part.read(str(root/'Dice_25_REFERENCE.step'))
keep=Part.makeBox(100,100,40,A.Vector(-50,-17.6,0))
for name,shape in [('Base_Section_REFERENCE',base),('Dice_Section_REFERENCE',dice)]:
    s=shape.common(keep)
    assert s.isValid()
    MeshPart.meshFromShape(Shape=s,LinearDeflection=.025,AngularDeflection=.09,Relative=False).write(str(root/(name+'.stl')))
print('Actual CAD section meshes exported for preview only.')
