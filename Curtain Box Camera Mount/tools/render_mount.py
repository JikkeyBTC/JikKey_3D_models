import json,os,pathlib,sys
import vtk
from PIL import Image,ImageDraw,ImageFont
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'images'
WORK=ROOT/'Verification'/'_build'
OUT.mkdir(parents=True,exist_ok=True)
COLORS={'01_body':(0.85,0.87,0.88),'02_screw':(0.50,0.63,0.67),
        '03_moving_foot':(0.85,0.87,0.88),'04_retaining_clip':(0.85,0.47,0.19),
        '05_camera_plate':(0.72,0.78,0.80)}
def render(files,out,camera,focus,parallel_scale=130,ground=False):
    ren=vtk.vtkRenderer();ren.SetBackground(0.955,0.960,0.965)
    for path,offset in files:
        r=vtk.vtkSTLReader();r.SetFileName(str(path));r.Update()
        normal=vtk.vtkPolyDataNormals();normal.SetInputConnection(r.GetOutputPort())
        normal.SetFeatureAngle(45);normal.SplittingOn();normal.ConsistencyOn()
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normal.GetOutputPort())
        actor=vtk.vtkActor();actor.SetMapper(mapper);actor.SetPosition(*offset)
        name=path.stem;col=(0.10,0.115,0.12) if 'TPU' in name else COLORS.get(name,(0.63,0.67,0.70))
        actor.GetProperty().SetColor(*col);actor.GetProperty().SetAmbient(0.28)
        actor.GetProperty().SetDiffuse(0.72);actor.GetProperty().SetSpecular(0.15)
        actor.GetProperty().SetSpecularPower(30);ren.AddActor(actor)
    if ground:
        plane=vtk.vtkPlaneSource();plane.SetOrigin(0,0,-0.5);plane.SetPoint1(220,0,-0.5);plane.SetPoint2(0,180,-0.5)
        mp=vtk.vtkPolyDataMapper();mp.SetInputConnection(plane.GetOutputPort())
        ac=vtk.vtkActor();ac.SetMapper(mp);ac.GetProperty().SetColor(0.80,0.83,0.85);ac.GetProperty().SetOpacity(0.6);ren.AddActor(ac)
    cam=ren.GetActiveCamera();cam.SetPosition(*camera);cam.SetFocalPoint(*focus);cam.SetViewUp(0,0,1)
    cam.ParallelProjectionOn();cam.SetParallelScale(parallel_scale)
    ren.ResetCameraClippingRange()
    win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.AddRenderer(ren);win.SetSize(1500,1050)
    win.SetMultiSamples(8);win.Render()
    cap=vtk.vtkWindowToImageFilter();cap.SetInput(win);cap.SetInputBufferTypeToRGB();cap.ReadFrontBufferOff();cap.Update()
    writer=vtk.vtkPNGWriter();writer.SetFileName(str(out));writer.SetInputConnection(cap.GetOutputPort());writer.Write();win.Finalize()
    return out
def label_font(size):
    candidates=[os.environ.get('CURTAIN_MOUNT_FONT'),
                r'C:\Windows\Fonts\malgun.ttf',
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                '/System/Library/Fonts/AppleSDGothicNeo.ttc']
    for candidate in candidates:
        if not candidate:continue
        try:return ImageFont.truetype(candidate,size)
        except OSError:pass
    # A font override is useful on systems without a Korean-capable font.
    print('No Korean-capable font found; set CURTAIN_MOUNT_FONT for captions.',file=sys.stderr)
    try:return ImageFont.load_default(size=size)
    except TypeError:return ImageFont.load_default()

def label(path,title,subtitle,footer):
    img=Image.open(path).convert('RGB');d=ImageDraw.Draw(img)
    font=label_font(38)
    small=label_font(23)
    d.text((55,32),title,font=font,fill='#20313c')
    d.text((58,91),subtitle,font=small,fill='#536673')
    d.text((58,img.height-60),footer,font=small,fill='#536673')
    img.save(path)

assembly=[(p,(0,0,0)) for p in sorted((WORK/'assembled').glob('*.stl'))]
if not assembly:raise FileNotFoundError('Run tools/build_mount.py first; assembly meshes are missing.')
render(assembly,OUT/'preview_assembly.png',(-255,-440,-220),(76,0,19),96)
label(OUT/'preview_assembly.png','커튼박스 압착 거치대 · 150 mm 시안',
      '조절 범위 145–215 mm  |  카메라 판 Ø82 mm · 원본 3MF의 9개 홀 유지',
      '카메라·체결 볼트는 표시하지 않음  /  실제 커튼박스 폭과 카메라 체결은 출력 전에 확인')

exploded=[]
for p,_ in assembly:
    name=p.stem
    offset=(-55,0,0) if name in ('01_body','06_TPU_pad_fixed') else (0,0,0)
    if name in ('03_moving_foot','07_TPU_pad_moving'):offset=(75,0,0)
    if name=='02_screw':offset=(22,0,0)
    if name=='04_retaining_clip':offset=(22,-38,15)
    if name=='05_camera_plate':offset=(0,0,-37)
    exploded.append((p,offset))
render(exploded,OUT/'preview_exploded.png',(240,-470,245),(87,0,8),157)
label(OUT/'preview_exploded.png','부품 분리 보기',
      '본체 · 굵은 조절 나사 · 가이드가 달린 이동 발 · 고정 클립 · 카메라 판 · 패드 2개',
      '미리보기 색상은 부품을 구분하기 위한 것  /  체결 볼트와 카메라는 별도')

layout={'01_body':(10,10,0),'03_moving_foot':(69,10,0),'02_screw':(128,10,0),
        '05_camera_plate':(128,63,0),'04_retaining_clip':(130,154,0)}
files=[(ROOT/'STL'/(n+'.stl'),p) for n,p in layout.items()]
render(files,OUT/'preview_print_layout.png',(400,-440,480),(105,77,46),142,True)
label(OUT/'preview_print_layout.png','부품별 출력 방향 · PETG 판',
      '본체·이동 발은 끝면으로 세워 출력  |  나사는 수직  |  카메라 판·클립은 평평하게',
      '배치 면적 약 200 × 161 mm  /  TPU 패드 2개는 별도 판에서 출력')
print('Rendered previews',flush=True)
