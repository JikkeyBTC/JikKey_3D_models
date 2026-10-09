import json,math,pathlib
import vtk
ROOT=pathlib.Path(__file__).resolve().parents[1]
VERIFICATION_DIR=ROOT/'Verification'
BASE=VERIFICATION_DIR/'_build'
def mesh(name):
    r=vtk.vtkSTLReader();r.SetFileName(str(BASE/'assembled'/(name+'.stl')));r.Update()
    p=vtk.vtkPolyData();p.DeepCopy(r.GetOutput());return p
def implicit(poly):
    x=vtk.vtkImplicitPolyDataDistance();x.SetInput(poly);return x
body=implicit(mesh('01_body'));male=mesh('02_screw')
checks=[]
for gap in (145,150,175,215):
    for bad in (False,True):
        dx=gap-150;angle=math.radians(dx*60+(180 if bad else 0));c=math.cos(angle);s=math.sin(angle)
        tr=vtk.vtkTransform();tr.SetMatrix([1,0,0,dx,0,c,-s,28*s,0,s,c,28*(1-c),0,0,0,1])
        tf=vtk.vtkTransformPolyDataFilter();tf.SetInputData(male);tf.SetTransform(tr);tf.Update()
        screw=implicit(tf.GetOutput());both=0;examples=[]
        xs=[max(78.4,gap-128+2)+i*0.4 for i in range(70)]
        for x in xs:
            if x>106:continue
            for i in range(48):
                a=(i+0.173)*math.pi/24;p=(x,11.1*math.cos(a),28+11.1*math.sin(a))
                if body.EvaluateFunction(p)<-0.08 and screw.EvaluateFunction(p)<-0.08:
                    both+=1
                    if len(examples)<3:examples.append(p)
        checks.append(dict(gap_mm=gap,phase='wrong_180' if bad else 'correct',
                           interior_collision_samples=both,examples=examples))
print(json.dumps(checks,indent=2),flush=True)
assert all(r['interior_collision_samples']==0 for r in checks if r['phase']=='correct')
assert all(r['interior_collision_samples']>20 for r in checks if r['phase']=='wrong_180')
(VERIFICATION_DIR/'Thread_Mesh_Validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
