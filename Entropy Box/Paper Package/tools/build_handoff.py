"""Create artwork-only production files and a folded preview from the same paths."""
from pathlib import Path
import ast, copy, json, subprocess, zipfile
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

OUT=Path(__file__).resolve().parent.parent
V=OUT/'Vendor_Files'; V.mkdir(exist_ok=True)
source=OUT/'tools/build_package.py'
# Load definitions without executing the master-file exports.
tree=ast.parse(source.read_text(encoding='utf-8'))
nodes=[]
for node in tree.body:
    if isinstance(node,(ast.FunctionDef,ast.Import,ast.ImportFrom)):
        nodes.append(node)
    elif getattr(node,'lineno',999)<125:
        nodes.append(node)
scope={'__file__':str(source)}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),scope)
geo=json.loads((OUT/'Package_Dimensions.json').read_text(encoding='utf-8'))
original=geo['vector_shapes']; scope['PW'],scope['PH']=geo['artboard_mm']
scope['OX']=scope['OY']=2.5
PT=72/25.4
art=[copy.deepcopy(s) for s in original if s['layer']==0]
die=[copy.deepcopy(s) for s in original if s['layer'] in (1,2)]
# Fully omit all guide paths from the production print file, in PDF and AI alike.
for label,items in [('01_Entropy_Box_PRINT_ONLY',art),('02_Entropy_Box_DIELINE_REFERENCE_DO_NOT_PRINT',die)]:
    scope['shapes']=items
    pdf=V/(label+'.pdf'); ai=V/(label+'.ai')
    scope['draw_pdf'](pdf,True); native=scope['embed_native'](pdf,ai)
    assert b'%AI12_CompressedData' not in native
    assert len(PdfReader(ai).pages)==1
    assert not any(x.get('/Subtype')=='/Image' for x in PdfReader(ai).pages[0]['/Resources'].get('/XObject',{}).values())
    assert abs(float(PdfReader(ai).pages[0].mediabox.width)/PT-169.8)<.001

pdfmetrics.registerFont(TTFont('Ko', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KoB','C:/Windows/Fonts/malgunbd.ttf'))
preview=OUT/'_assembled_preview.pdf'
cv=canvas.Canvas(str(preview),pagesize=(300*PT,180*PT),pageCompression=1)
cv.setTitle('Entropy Box folded paper carton preview')
cv.scale(PT,PT)
cv.setFillColorRGB(.963,.961,.95);cv.rect(0,0,300,180,stroke=0,fill=1)
def label(txt,x,y,size=10,bold=False,color=(.15,.16,.17)):
    cv.setFillColorRGB(*color);cv.setFont('KoB' if bold else 'Ko',size/PT);cv.drawString(x,y,txt)
label('JikKey  /  Entropy Box',18,161,22,True)
label('종이 패키지 조립 미리보기',18,151,11,color=(.4,.42,.44))

def path(item):
    p=cv.beginPath()
    for op,co in item['cmd']:
        if op=='M':p.moveTo(*co)
        elif op=='L':p.lineTo(*co)
        elif op=='C':p.curveTo(*co)
        else:p.close()
    return p
def plane(poly,gray):
    cv.setFillColorRGB(gray,gray,gray);cv.setStrokeColorRGB(.68,.68,.66)
    p=cv.beginPath();p.moveTo(*poly[0])
    for point in poly[1:]:p.lineTo(*point)
    p.close();cv.setLineWidth(.13);cv.drawPath(p,fill=1,stroke=1)
def mapped_art(x0,y0,w,h,matrix):
    cv.saveState();cv.transform(*matrix)
    p=cv.beginPath();p.rect(x0,y0,w,h);cv.clipPath(p,stroke=0,fill=0)
    for item in art:
        cv.setLineWidth(item['width']/PT)
        if item['fill'] is not None:cv.setFillColorCMYK(*item['fill'])
        if item['stroke'] is not None:cv.setStrokeColorCMYK(*item['stroke'])
        cv.drawPath(path(item),fill=int(item['fill'] is not None),stroke=int(item['stroke'] is not None),fillMode=1)
    cv.restoreState()
def folded(bx,by,back=False):
    w,h,d=59.7,60.05,17.7;s=1.45
    # Orthographic affine projection of each actual scored panel.
    ux,uy=s,-.11*s;vx,vy=0,s;zx,zy=.74*s,.43*s
    A=(bx,by);B=(bx+ux*w,by+uy*w);C=(B[0],B[1]+vy*h);E=(bx,by+vy*h)
    F=(B[0]+zx*d,B[1]+zy*d);G=(C[0]+zx*d,C[1]+zy*d);J=(E[0]+zx*d,E[1]+zy*d)
    plane([A,B,C,E],1);plane([B,F,G,C],.89);plane([E,C,G,J],.97)
    frontx=89.9 if back else 12.5; fronty=28.2
    mapped_art(frontx,fronty,w,h,(ux,uy,vx,vy,bx-ux*frontx-vx*fronty,by-uy*frontx-vy*fronty))
    side=149.6 if back else 72.2
    mapped_art(side,fronty,d,h,(zx,zy,vx,vy,B[0]-zx*side-vx*fronty,B[1]-zy*side-vy*fronty))
    # The upper closure belongs to the BACK panel on the unfolded die.
    tx,ty=89.9,88.25
    if not back:
        mapped_art(tx,ty,w,d,(-ux,-uy,-zx,-zy,G[0]+ux*tx+zx*ty,G[1]+uy*tx+zy*ty))
    else:
        mapped_art(tx,ty,w,d,(ux,uy,zx,zy,E[0]-ux*tx-zx*ty,E[1]-uy*tx-zy*ty))
    label('뒷면' if back else '앞면',bx,by-14,10,True)

folded(29,43);folded(165,43,True)
label('목표 내부 공간 59 × 59 × 17 mm',18,19,10,True)
label('MGB 300g · 종이 두께 0.35 mm 가정 · 실제 접기·수납 확인 전의 외형 참고입니다.',18,11,8,color=(.42,.44,.45))
cv.showPage();cv.save()
exe=Path('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
subprocess.run([str(exe),'-png','-r','200','-singlefile',str(preview),str(OUT/'Entropy_Box_Assembled_Preview')],check=True)

request='''Entropy Box 맞춤 종이 패키지 / 제작 요청

주문 수량: 완성 패키지 기준 총 50개 / 디자인 1종
제품 크기: 58×58×15.6 mm
목표 최소 유효 내부 공간: 59×59×17 mm
용지: MGB 300g / 단면 CMYK 4도 / 추가 코팅 없음
구조: 양쪽 끼움 덮개(역방향), 접착 날개 10 mm
칼선 외곽: 164.80×111.45 mm
첨부 단일 도면 작업 대지: 169.80×116.45 mm (사방 2.5 mm)
압선 간 큰 면: 59.70×60.05 mm / 옆면 폭: 17.70 mm

파일 구분:
01_Entropy_Box_PRINT_ONLY.ai: 실제 인쇄용. 칼선·압선·치수·안전선은 데이터에서 제거했습니다.
02_Entropy_Box_DIELINE_REFERENCE_DO_NOT_PRINT.ai: 동일 좌표계의 재단·압선 가공 도면입니다. 색 선은 종이에 인쇄하지 마십시오.
03_Entropy_Box_Dimension_Guide.png: 치수 및 패널 위치 확인용이며 인쇄판이 아닙니다.
04_Entropy_Box_Assembled_Preview.png: 접은 외형 참고용이며 인쇄판이 아닙니다.
PDF는 각 AI의 내용 확인용 보조 파일입니다.

중요 제작 조건:
인쇄 50장이 아닌, 재단·압선 처리된 패키지 전개도 50개를 요청합니다.
웹 옵션 비규격(540×352 이하)은 접수 단위의 최대 크기이며 실제 상자 크기가 아닙니다.
제품 크기나 단일 도면 크기를 웹 옵션의 최대 크기에 맞춰 확대하지 마십시오. 100% 원크기를 유지하십시오.
최종 배치는 제작처의 장비 조건에 맞춰 진행하되 결과 수량은 50개로 맞춰 주십시오.
자유 칼선 재단과 압선이 포함되는지, 접착 가공 포함/별도인지 접수 때 확인 부탁드립니다.
평접착 또는 펼친 상태 납품이 가능한지 명시하고, 추가 칼선비·가공비가 필요하면 작업 전 견적을 안내해 주십시오.
MGB 300g 실제 두께가 0.35 mm와 다를 경우 목표 내부 공간이 유지되도록 종이 두께와 압선 보정을 검토해 주십시오.
본격 생산 전 담당자가 AI 열기, 글자 윤곽선, 칼선 분리, 접기 방향과 수납 치수를 확인해 주십시오.
Illustrator 앱 직접 열기와 실물 수납은 아직 검증되지 않았습니다.

수량·도면·가공 조건이 다르거나 추가 비용이 필요한 경우 임의 변경 없이 주문자에게 확인 후 제작을 진행해 주십시오.
'''
(V/'05_제작요청서.txt').write_text(request,encoding='utf-8-sig')
(OUT/'제작처_전달문.txt').write_text(request,encoding='utf-8-sig')
import shutil
shutil.copy2(OUT/'Entropy_Box_Paper_Package_Dimension_Guide.png',V/'03_Entropy_Box_Dimension_Guide.png')
shutil.copy2(OUT/'Entropy_Box_Assembled_Preview.png',V/'04_Entropy_Box_Assembled_Preview.png')
with zipfile.ZipFile(OUT/'Entropy_Box_Wowpress_50_Order_Files.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(V.iterdir()):z.write(f,f.name)
with zipfile.ZipFile(OUT/'Entropy_Box_Wowpress_50_Order_Files.zip') as z:assert z.testzip() is None
preview.unlink()
print(json.dumps({'print_paths':len(art),'dieline_paths':len(die),'artboard_mm':geo['artboard_mm'],'upload_zip':str(OUT/'Entropy_Box_Wowpress_50_Order_Files.zip')},ensure_ascii=False))
