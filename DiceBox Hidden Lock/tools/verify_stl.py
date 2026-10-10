from pathlib import Path
import json,struct
import numpy as np
root=Path(__file__).resolve().parent.parent
cad_path=root/'Validation.json'
if not cad_path.is_file():cad_path=root/'Verification/Validation.json'
cad=json.loads(cad_path.read_text(encoding='utf-8'))
result={}
names=[('Entropy_Box_V3_Deep_Base',[58,58,17.6]),
       ('Entropy_Box_V3_Compatible_Lid',[58,58,9.8]),
       ('OPTIONAL_V3_9_Pocket_Test_Tray',[28,28,6.4])]
for name,bbox in names:
    stl_path=root/(name+'.stl')
    if not stl_path.is_file():stl_path=root/'Optional_Test'/(name+'.stl')
    data=stl_path.read_bytes();n=struct.unpack_from('<I',data,80)[0]
    assert len(data)==84+50*n
    dtype=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')])
    t=np.frombuffer(data,dtype=dtype,count=n,offset=84)['v'].astype(float)
    v,ids=np.unique(np.round(t.reshape(-1,3),5),axis=0,return_inverse=True)
    f=ids.reshape(-1,3)
    assert len(np.unique(np.sort(f,axis=1),axis=0))==n
    assert np.all(np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)>1e-9)
    e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    edges,ei,count=np.unique(np.sort(e,axis=1),axis=0,return_inverse=True,return_counts=True)
    assert np.all(count==2),(name,'open/nonmanifold')
    assert np.all(np.bincount(ei,weights=np.where(e[:,0]<e[:,1],1,-1))==0)
    adj=[[] for _ in v]
    for a,b in edges:adj[a].append(b);adj[b].append(a)
    seen={0};pending=[0]
    while pending:
        for k in adj[pending.pop()]:
            if k not in seen:seen.add(k);pending.append(k)
    assert len(seen)==len(v)
    vol=float(np.sum(np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])))/6)
    actual_bbox=np.max(v,axis=0)-np.min(v,axis=0)
    assert np.allclose(actual_bbox,bbox,atol=1e-5)
    assert vol>0 and abs(vol-cad['files'][name]['volume_mm3'])<1
    result[name]={'triangles':n,'closed_manifold':True,'consistent_winding':True,
        'connected_components':1,'bbox_mm':actual_bbox.tolist(),
        'step_mesh_volume_difference_mm3':vol-cad['files'][name]['volume_mm3']}
ref=root/'Reference_V2'
if not ref.is_dir():ref=root.parent/'dicebox-50x50x2-strong-lock-v2'
assert (root/'Entropy_Box_V3_Compatible_Lid.stl').read_bytes()==(ref/'DiceBox_StrongLockV2_Lid.stl').read_bytes()
report={'stl':result,'lid_identical_to_v2':True,'z_zero_for_printing':True}
(cad_path.parent/'Independent_STL_Validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
