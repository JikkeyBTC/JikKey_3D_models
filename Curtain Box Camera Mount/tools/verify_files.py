"""Verify exported CAD/meshes/packages, and write model-relative public reports."""
from pathlib import Path
import hashlib,json,re,zipfile,xml.etree.ElementTree as ET
from urllib.parse import unquote,urlsplit
import FreeCAD as App
import Part
import numpy as np
from package_3mf import read_stl

ROOT=Path(__file__).resolve().parents[1]
VERIFY=ROOT/'Verification'
NS={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
BUNDLE='CurtainBox_CameraMount_145-215mm_STL_STEP_3MF.zip'

def relative(path):return Path(path).resolve().relative_to(ROOT).as_posix()
def sanitize(value):
    if isinstance(value,dict):return {k:sanitize(v) for k,v in value.items()}
    if isinstance(value,list):return [sanitize(v) for v in value]
    if isinstance(value,str) and value.startswith(str(ROOT)):
        return relative(value)
    return value
def write(name,data):
    (VERIFY/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def bounds(shape):
    vertices,_=shape.tessellate(0.10)
    pts=np.array([[v.x,v.y,v.z] for v in vertices]);return np.array([pts.min(axis=0),pts.max(axis=0)])

steps=[];stls=[]
for folder in ('STL','Optional_Tests'):
    for p in sorted((ROOT/folder).glob('*.stl')):
        mesh=read_stl(p);r=mesh.report
        assert all(r[k]==0 for k in ('boundary_edges','nonmanifold_edges','inconsistent_shared_edges'))
        assert r['signed_volume_mm3']>0 and abs(r['bounds_min_mm'][2])<0.002
        stls.append({**sanitize(r),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        step=(ROOT/'STEP'/p.with_suffix('.step').name) if folder=='STL' else p.with_suffix('.step')
        s=Part.read(str(step));assert len(s.Solids)==1 and s.isValid()
        vb=np.array([r['bounds_min_mm'],r['bounds_max_mm']]);sb=bounds(s)
        delta=float(np.max(np.abs(vb-sb)));assert delta<0.05,(step,delta)
        volume_error=abs(s.Volume-r['signed_volume_mm3'])/s.Volume
        assert volume_error<0.005,(step,volume_error)
        steps.append({'file':relative(step),'valid':True,'solids':1,'volume_mm3':s.Volume,
                      'bounds_mm':sb.tolist(),'max_STL_bounds_difference_mm':delta,
                      'STL_volume_relative_difference':volume_error})
assert len(stls)==8 and len(steps)==8
assembly_path=ROOT/'Reference'/'CurtainBox_Mount_Assembly_REFERENCE.step'
assembly=Part.read(str(assembly_path));assert len(assembly.Solids)==7 and all(s.isValid() for s in assembly.Solids)
native=App.openDocument(str(ROOT/'Native_CAD'/'CurtainBox_CameraMount.FCStd'))
native_shapes=[o.Shape for o in native.Objects if hasattr(o,'Shape')]
assert len(native_shapes)==7 and all(s.isValid() for s in native_shapes)
App.closeDocument(native.Name)
write('STEP_Validation.json',{'parts':steps,'assembly':{'file':relative(assembly_path),'valid_solids':7},
                             'native_CAD_valid_solids':7})

packages=[]
specs=[('3MF/CurtainBox_Mount_Print_PETG.3mf',5,True),
       ('3MF/CurtainBox_Mount_Print_TPU.3mf',2,True),
       ('Reference/CurtainBox_Mount_Assembly_REFERENCE.3mf',7,False),
       ('Optional_Tests/Thread_Fit_Test.3mf',2,True)]
for name,count,is_print in specs:
    p=ROOT/name
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        model=ET.fromstring(z.read('3D/3dmodel.model'))
    assert model.get('unit')=='millimeter'
    objects=model.findall('m:resources/m:object',NS);items=model.findall('m:build/m:item',NS)
    assert len(objects)==len(items)==count
    records=[];boxes=[]
    for obj,item in zip(objects,items):
        pts=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in obj.findall('m:mesh/m:vertices/m:vertex',NS)])
        triangles=obj.findall('m:mesh/m:triangles/m:triangle',NS)
        assert all(all(0<=int(t.get(k))<len(pts) for k in ('v1','v2','v3')) for t in triangles)
        tr=np.array([float(n) for n in item.get('transform','1 0 0 0 1 0 0 0 1 0 0 0').split()])
        placed=pts@tr[:9].reshape(3,3)+tr[9:]
        lo=placed.min(axis=0);hi=placed.max(axis=0)
        if is_print:assert abs(lo[2])<0.002
        boxes.append((lo,hi))
        records.append({'name':obj.get('name'),'triangles':len(triangles),'bounds_mm':[lo.tolist(),hi.tolist()]})
    if is_print:
        for i,(lo,hi) in enumerate(boxes):
            for other_lo,other_hi in boxes[i+1:]:
                assert not(np.all(np.minimum(hi[:2],other_hi[:2])>np.maximum(lo[:2],other_lo[:2])+0.001))
    packages.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                     'objects':records,'units':'millimeter','zip_xml_valid':True,
                     'print_bed_contact_verified':is_print,'print_XY_overlap_verified':is_print,
                     'support_free_verified':False})
write('STL_3MF_Validation.json',{'STLs':stls,'packages':packages,'physical_print_verified':False})

# Keep fresh packaging evidence, without the originating user's checkout paths.
for name in ('3MF_Print_Validation.json','3MF_Assembly_Validation.json','3MF_Fit_Validation.json'):
    write(name,sanitize(json.loads((VERIFY/name).read_text(encoding='utf-8'))))

links=[];missing=[]
for doc in [ROOT/'README.md',ROOT/'Assembly_Guide_KO.md',ROOT/'tools'/'README.md']:
    for href in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
        raw=href.strip('<>');url=urlsplit(raw)
        if url.scheme or raw.startswith('#'):continue
        target=(doc.parent/unquote(url.path)).resolve()
        if target.name==BUNDLE:
            links.append({'document':relative(doc),'link':raw,'bundle_built_separately':True});continue
        if not target.exists():missing.append((relative(doc),raw))
        else:links.append({'document':relative(doc),'link':raw,'exists':True})
assert not missing,missing
write('File_Validation.json',{'STL_count':len(stls),'individual_STEP_count':len(steps),
                             '3MF_count':len(packages),'local_links':links,
                             'physical_print_verified':False,'support_free_verified':False})
print('Verified8 STLs/8 individualSTEPs/7 assembledsolids/4 core3MFs anddocument links.',flush=True)
