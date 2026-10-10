from pathlib import Path
import json, zipfile, hashlib

root = Path(__file__).resolve().parent.parent
cad = json.loads((root/'Validation.json').read_text(encoding='utf-8'))
capacity = json.loads((root/'Independent_Capacity_Validation.json').read_text(encoding='utf-8'))
stl = json.loads((root/'Independent_STL_Validation.json').read_text(encoding='utf-8'))
assert capacity['capacity'] == 100 and capacity['pane_size_mm'] == [100,100,2]
assert cad['checks']['pocket_profile_difference_vs_v3_mm3'] < 1e-6
assert all(item['closed_manifold'] and item['connected_components']==1 for item in stl['stl'].values())

files = {'Assembly_Guide_KO.txt':'Assembly_Guide_KO.txt'}
for part in ['Entropy_Box_100_V3_Base','Entropy_Box_100_V3_Lid','Entropy_Box_100_V3_Print_Layout']:
    for ext in ['stl','step']:
        files[f'{part}.{ext}'] = f'{part}.{ext}'
files['Entropy_Box_100_V3.FCStd'] = 'Native_CAD/Entropy_Box_100_V3.FCStd'
for name in ['Dimensions.json','Validation.json','Independent_Capacity_Validation.json','Independent_STL_Validation.json']:
    files[name] = 'Verification/'+name
for name in ['Entropy_Box_100_V3_Assembly_REFERENCE.step',
             'ClearPanel_100x100x2_REFERENCE.stl','ClearPanel_100x100x2_REFERENCE.step',
             'Dice_100_REFERENCE.stl','Dice_100_REFERENCE.step',
             'Lid_Closed_REFERENCE.stl','Base_Section_REFERENCE.stl','Dice_Section_REFERENCE.stl']:
    files[name] = 'Reference/'+name
for name in ['Preview_100_Open.png','Preview_100_Assembled.png','Preview_100_Section.png']:
    files[name] = 'Previews/'+name
for path in (root/'tools').glob('*.py'):
    files['tools/'+path.name] = 'tools/'+path.name
manifest={}
for source,target in files.items():
    path=root/source
    assert path.is_file() and path.stat().st_size > 0, source
    manifest[target]=hashlib.sha256(path.read_bytes()).hexdigest()
(root/'SHA256_Manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
files['SHA256_Manifest.json']='SHA256_Manifest.json'
destination=root/'Entropy_Box_100_V3_100x100x2_STL_STEP.zip'
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for source,target in files.items(): archive.write(root/source,target)
with zipfile.ZipFile(destination) as archive:
    assert archive.testzip() is None
    for name,digest in manifest.items():
        assert hashlib.sha256(archive.read(name)).hexdigest()==digest
print(json.dumps({'zip':str(destination),'files':len(files),'bytes':destination.stat().st_size,
                  'crc_verified':True,'manifest_verified':True},ensure_ascii=False,indent=2))
