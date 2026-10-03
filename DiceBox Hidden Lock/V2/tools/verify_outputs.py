from pathlib import Path
import json,struct
import numpy as np
root=Path(__file__).resolve().parent.parent
cad=json.loads((root/'Validation.json').read_text())
results={}
for name,expected_bbox in [('DiceBox_StrongLockV2_Base',[58,58,14.2]),
                           ('DiceBox_StrongLockV2_Lid',[58,58,9.8]),
                           ('OPTIONAL_StrongLockV2_Base_Rim_Test',[58,58,10.4]),
                           ('OPTIONAL_StrongLockV2_Joint_Base_Test',[14,6,10.4]),
                           ('OPTIONAL_StrongLockV2_Joint_Lid_Test',[14,6,9.8])]:
    data=(root/(name+'.stl')).read_bytes()
    n=struct.unpack_from('<I',data,80)[0]
    assert len(data)==84+50*n
    dtype=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')])
    t=np.frombuffer(data,dtype=dtype,count=n,offset=84)['v'].astype(np.float64)
    v,ids=np.unique(np.round(t.reshape(-1,3),5),axis=0,return_inverse=True)
    f=ids.reshape(-1,3)
    assert len(np.unique(np.sort(f,axis=1),axis=0))==n
    assert np.all(np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)>1e-9)
    e=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    edges,ei,count=np.unique(np.sort(e,axis=1),axis=0,return_inverse=True,return_counts=True)
    assert np.all(count==2),(name,'open/nonmanifold edge')
    direction=np.where(e[:,0]<e[:,1],1,-1)
    assert np.all(np.bincount(ei,weights=direction)==0),(name,'winding')
    adj=[[] for _ in v]
    for a,b in edges:adj[a].append(b);adj[b].append(a)
    seen={0};pending=[0]
    while pending:
        for k in adj[pending.pop()]:
            if k not in seen:seen.add(k);pending.append(k)
    assert len(seen)==len(v),(name,'disconnected components')
    volume=float(np.sum(np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])))/6)
    expected_volume=cad['files'][name]['volume_mm3']
    assert volume>0 and abs(volume-expected_volume)<1,(name,'volume')
    bbox=np.max(v,axis=0)-np.min(v,axis=0)
    assert np.allclose(bbox,expected_bbox,atol=1e-5),(name,'bbox')
    results[name]=dict(triangles=n,vertices=len(v),edges=len(edges),
        euler_characteristic=len(v)-len(edges)+n,closed_manifold=True,
        consistent_winding=True,connected_components=1,bbox_mm=bbox.tolist(),
        signed_volume_mm3=volume,step_mesh_volume_difference_mm3=volume-expected_volume)
(root/'Independent_STL_Validation.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
