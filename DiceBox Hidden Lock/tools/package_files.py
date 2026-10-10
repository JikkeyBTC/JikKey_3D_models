from pathlib import Path
import json,hashlib,zipfile,shutil
root=Path(__file__).resolve().parent.parent
ref=root/'Reference_V2';ref.mkdir(exist_ok=True)
source=root.parent/'dicebox-50x50x2-strong-lock-v2'
for name in ['Dimensions.json','Validation.json','DiceBox_StrongLockV2_Base.step','DiceBox_StrongLockV2_Lid.step','DiceBox_StrongLockV2_Lid.stl']:
    if not (ref/name).exists():shutil.copy2(source/name,ref/name)
mapping={'Assembly_Guide_KO.txt':'Assembly_Guide_KO.txt',
    'Entropy_Box_V3_Deep_Pockets.FCStd':'Native_CAD/Entropy_Box_V3_Deep_Pockets.FCStd'}
for name in ['Entropy_Box_V3_Deep_Base','Entropy_Box_V3_Compatible_Lid','Entropy_Box_V3_Print_Layout']:
    for ext in ['stl','step']:mapping[name+'.'+ext]=name+'.'+ext
for ext in ['stl','step']:
    f='OPTIONAL_V3_9_Pocket_Test_Tray.'+ext;mapping[f]='Optional_Test/'+f
for f in root.glob('*.json'):
    if f.name!='SHA256_Manifest.json':mapping[f.name]='Verification/'+f.name
for f in root.glob('*REFERENCE.*'):mapping[f.name]='Reference/'+f.name
for f in root.glob('Preview*.png'):mapping[f.name]='Previews/'+f.name
for f in (root/'tools').glob('*.py'):mapping['tools/'+f.name]='tools/'+f.name
for f in ref.iterdir():mapping['Reference_V2/'+f.name]='Reference_V2/'+f.name
manifest={target:hashlib.sha256((root/source).read_bytes()).hexdigest() for source,target in mapping.items()}
(root/'SHA256_Manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
mapping['SHA256_Manifest.json']='SHA256_Manifest.json'
out=root/'Entropy_Box_V3_Deep_Pockets_STL_STEP.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for source,target in mapping.items():
        p=root/source;assert p.is_file(),source;z.write(p,target)
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
print(json.dumps({'zip':str(out),'files':len(mapping),'bytes':out.stat().st_size,'crc':'passed','sha256_manifest':'verified'},ensure_ascii=False,indent=2))
