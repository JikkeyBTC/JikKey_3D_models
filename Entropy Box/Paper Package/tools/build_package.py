"""One vector model, synchronized native Illustrator data and PDF preview.

The supplied Illustrator container/setup is reused; original artwork is replaced
in both representations. No Adobe application is installed for an opening test.
"""
from pathlib import Path
import io, json, math, re, struct, subprocess, zlib, hashlib
from functools import lru_cache
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DictionaryObject, NameObject, NumberObject,
                           TextStringObject, DecodedStreamObject)

OUT=Path(__file__).resolve().parent.parent
OUT.mkdir(parents=True,exist_ok=True)
SRC=OUT/'Reference_Source/template_06.ai'
if not SRC.is_file():SRC=OUT.parents[1]/'tmp/dicebox-paper-package-source/template_06.ai'
PT=72/25.4
T=.35
IW,IH,ID=59.,59.,17.
W,H,D=IW+2*T,IH+3*T,ID+2*T
G=10.;TAB=8.;BLEED=2.5
X=[G,G+W,G+W+D,G+2*W+D,G+2*(W+D)]
Y=D+TAB;YT=Y+H
NW=X[-1];NH=H+2*(D+TAB)
OX,OY=12.,23.
PW,PH=NW+24,NH+44
LAYERS=['01_ARTWORK_PRINT','02_CUT_DO_NOT_PRINT','03_CREASE_DO_NOT_PRINT',
        '04_BLEED_SAFE_DO_NOT_PRINT','05_DIMENSIONS_DO_NOT_PRINT']
BLACK=(0,0,0,1);ORANGE=(0,.48,.72,.22);GREY=(0,0,0,.55)
CUT=(0,1,0,0);CREASE=(1,0,1,0);PALE=(0,0,0,.22)
shapes=[]

def shape(cmd,layer=0,fill=None,stroke=None,width=.25,dash=(),tag=''):
    item=dict(cmd=cmd,layer=layer,fill=fill,stroke=stroke,width=width,dash=dash,tag=tag)
    shapes.append(item);return item

def polygon(points,layer=0,fill=None,stroke=None,width=.25,tag=''):
    return shape([('M',points[0])]+[('L',p) for p in points[1:]]+[('Z',[])],
                 layer,fill,stroke,width,tag=tag)

def line(x1,y1,x2,y2,layer=4,color=GREY,width=.25,dash=(),tag=''):
    return shape([('M',[x1,y1]),('L',[x2,y2])],layer,stroke=color,width=width,dash=dash,tag=tag)

def circle(x,y,r,fill=BLACK,layer=0,tag=''):
    k=.5522847498*r
    return shape([('M',[x+r,y]),('C',[x+r,y+k,x+k,y+r,x,y+r]),
        ('C',[x-k,y+r,x-r,y+k,x-r,y]),('C',[x-r,y-k,x-k,y-r,x,y-r]),
        ('C',[x+k,y-r,x+r,y-k,x+r,y]),('Z',[])],layer,fill=fill,tag=tag)

# Read simple TrueType glyph contours using the bundled ReportLab font parser.
# English lettering/numerals are converted to curves, eliminating font links.
faces={}
for bold,name in [(False,'arial.ttf'),(True,'arialbd.ttf')]:
    face=TTFont('ArialB' if bold else 'ArialR',str(Path('C:/Windows/Fonts')/name)).face
    faces[bold]=(face,face.get_table('glyf'))
face=TTFont('Malgun',str(Path('C:/Windows/Fonts/malgun.ttf'))).face
assert face.unitsPerEm==faces[False][0].unitsPerEm
faces['ko']=(face,face.get_table('glyf'))

@lru_cache(None)
def glyph(ch,bold):
    face,table=faces['ko' if ord(ch)>127 else bold];gid=face.charToGlyph[ord(ch)]
    a,b=face.glyphPos[gid:gid+2]
    if a==b:return [],face.hmetrics[gid][0]
    data=table[a:b];n=struct.unpack_from('>h',data)[0]
    assert n>=0,('composite glyph unsupported',ch)
    ends=struct.unpack_from('>'+str(n)+'H',data,10);p=10+2*n
    ins=struct.unpack_from('>H',data,p)[0];p+=2+ins
    count=ends[-1]+1;flags=[]
    while len(flags)<count:
        f=data[p];p+=1;flags.append(f)
        if f&8:
            repeat=data[p];p+=1;flags.extend([f]*repeat)
    values=[]
    for short,same in [(2,16),(4,32)]:
        v=[];total=0
        for f in flags:
            if f&short:
                delta=data[p];p+=1
                if not f&same:delta=-delta
            elif f&same:delta=0
            else:delta=struct.unpack_from('>h',data,p)[0];p+=2
            total+=delta;v.append(total)
        values.append(v)
    pts=[(values[0][i],values[1][i],bool(flags[i]&1)) for i in range(count)]
    contours=[];start=0
    for end in ends:
        q=pts[start:end+1];start=end+1
        if q[0][2]:begin=q[0][:2];seq=q[1:]
        elif q[-1][2]:begin=q[-1][:2];seq=q[:-1]
        else:begin=((q[0][0]+q[-1][0])/2,(q[0][1]+q[-1][1])/2);seq=q
        seq=seq+[(begin[0],begin[1],True)]
        cmds=[('M',list(begin))];cur=begin;i=0
        while i<len(seq):
            x,y,on=seq[i]
            if on:cmds.append(('L',[x,y]));cur=(x,y);i+=1
            else:
                nx,ny,non=seq[i+1]
                dest=(nx,ny) if non else ((x+nx)/2,(y+ny)/2)
                c1=(cur[0]+2*(x-cur[0])/3,cur[1]+2*(y-cur[1])/3)
                c2=(dest[0]+2*(x-dest[0])/3,dest[1]+2*(y-dest[1])/3)
                cmds.append(('C',[*c1,*c2,*dest]));cur=dest;i+=2 if non else 1
        cmds.append(('Z',[]));contours.extend(cmds)
    return contours,face.hmetrics[gid][0]

def text(value,x,y,points=8,bold=False,color=BLACK,layer=0,align='left',angle=0,tracking=0,tag=''):
    face,_=faces[bold];scale=points/PT/face.unitsPerEm
    widths=[glyph(c,bold)[1]*scale for c in value]
    total=sum(widths)+tracking*max(0,len(value)-1)
    shift=0 if align=='left' else (-total/2 if align=='center' else -total)
    c=math.cos(math.radians(angle));s=math.sin(math.radians(angle));cmd=[];offset=shift
    for ch,advance in zip(value,widths):
        g,_=glyph(ch,bold)
        for op,coords in g:
            points_out=[]
            for i in range(0,len(coords),2):
                px=coords[i]*scale+offset;py=coords[i+1]*scale
                points_out.extend([x+c*px-s*py,y+s*px+c*py])
            cmd.append((op,points_out))
        offset+=advance+tracking
    return shape(cmd,layer,fill=color,tag=tag or 'outlined_text:'+value)

# Counterclockwise outside contour: reverse-tuck carton, finger notches and dust flaps.
cmd=[]
def m(x,y):cmd.append(('M',[x+OX,y+OY]))
def l(x,y):cmd.append(('L',[x+OX,y+OY]))
def c(*v):cmd.append(('C',[n+(OX if i%2==0 else OY) for i,n in enumerate(v)]))
def thumb(cx,y,sign):
    r=2.;k=.5522847498*r
    l(cx-r,y)
    c(cx-r,y+sign*k,cx-k,y+sign*r,cx,y+sign*r)
    c(cx+k,y+sign*r,cx+r,y+sign*k,cx+r,y)
def dust_top(a,b):
    l(a+.8,YT-.5);l(a+.8,YT+.5);l(a+2,YT+14)
    l(b-2,YT+14);l(b-.8,YT+.5);l(b-.8,YT-.5);l(b,YT)
def dust_bottom_reverse(a,b):
    l(b-.8,Y+.5);l(b-.8,Y-.5);l(b-2,Y-14)
    l(a+2,Y-14);l(a+.8,Y-.5);l(a+.8,Y+.5);l(a,Y)
def main_top(a,b):
    y=YT+D;r=2.;k=.5522847498*r
    l(a+.35,YT);l(a+.35,y);l(a+2.2,y);l(a+2.2,y+TAB-r)
    c(a+2.2,y+TAB-r+k,a+2.2+r-k,y+TAB,a+2.2+r,y+TAB)
    l(b-2.2-r,y+TAB)
    c(b-2.2-r+k,y+TAB,b-2.2,y+TAB-r+k,b-2.2,y+TAB-r)
    l(b-2.2,y);l(b-.35,y);l(b-.35,YT);l(b,YT)
def main_bottom_reverse(a,b):
    y=Y-D;r=2.;k=.5522847498*r
    l(b-.35,Y);l(b-.35,y);l(b-2.2,y);l(b-2.2,y-TAB+r)
    c(b-2.2,y-TAB+r-k,b-2.2-r+k,y-TAB,b-2.2-r,y-TAB)
    l(a+2.2+r,y-TAB)
    c(a+2.2+r-k,y-TAB,a+2.2,y-TAB+r-k,a+2.2,y-TAB+r)
    l(a+2.2,y);l(a+.35,y);l(a+.35,Y);l(a,Y)

m(0,Y+3);l(0,YT-3);l(G,YT)
thumb((X[0]+X[1])/2,YT,-1);l(X[1],YT)
dust_top(X[1],X[2]);main_top(X[2],X[3]);dust_top(X[3],X[4])
l(X[4],Y);dust_bottom_reverse(X[3],X[4])
# Bottom rear notch is traversed right to left.
r=2.;k=.5522847498*r;cx=(X[2]+X[3])/2
l(cx+r,Y);c(cx+r,Y+k,cx+k,Y+r,cx,Y+r);c(cx-k,Y+r,cx-r,Y+k,cx-r,Y)
l(X[2],Y);dust_bottom_reverse(X[1],X[2]);main_bottom_reverse(X[0],X[1])
l(0,Y+3);cmd.append(('Z',[]))
cut_shape=shape(cmd,1,stroke=CUT,width=.25,tag='single_closed_cut_contour')

for x in X[:-1]:line(x+OX,Y+OY,x+OX,YT+OY,2,CREASE,dash=(1.5,1),tag='body_score')
for a,b,y in [(X[2]+.35,X[3]-.35,YT),(X[0]+.35,X[1]-.35,Y),
              (X[2]+2.2,X[3]-2.2,YT+D),(X[0]+2.2,X[1]-2.2,Y-D)]:
    line(a+OX,y+OY,b+OX,y+OY,2,CREASE,dash=(1.5,1),tag='lid_or_tuck_score')
for a,b in [(X[1],X[2]),(X[3],X[4])]:
    for y in (Y,YT):line(a+.8+OX,y+OY,b-.8+OX,y+OY,2,CREASE,dash=(1.5,1),tag='dust_score')

# Official naming and a vector product illustration, based on the reference page.
front=(X[0]+X[1])/2+OX;back=(X[2]+X[3])/2+OX;body=Y+OY
text('JikKey',front,body+54,7,True,align='center',tracking=.1)
line(front-3,body+51.5,front+3,body+51.5,0,ORANGE,width=.8)
text('Entropy Box',front,body+44.8,20.5,True,align='center',tracking=.03)
text('우연을 모으는 작은 상자.',front,body+39.5,7.3,align='center')
from product_illustration import draw_product
drawn_die_count=draw_product(shape,polygon,circle,front,body+21.8,.42)
text('5 × 5 주사위 배열',front,body+5.5,6.5,align='center')
text('JikKey / 3D Print',back,body+54,6.6,True,align='center',tracking=.06)
text('Entropy Box',back,body+47,15,True,align='center',tracking=.04)
text('우연을 모으는 작은 상자.',back,body+41.5,7.3,align='center')
text('5 mm 주사위 25개 기준 / 5 × 5 배열',back,body+35,6.4,align='center')
line(back-18,body+31,back+18,body+31,0,ORANGE,width=.8)
for dy,value in [(24,'01  흔들기'),(17,'02  정렬하기'),(10,'03  결과 읽기')]:
    text(value,back-15,body+dy,7.2,tracking=.05)
text('jikkey.com',back,body+5,5.5,align='center',tracking=.1)
for a,b in [(X[1],X[2]),(X[3],X[4])]:
    mid=(a+b)/2+OX
    text('Entropy Box',mid+1.7,body+H/2,9,True,angle=90,align='center',tracking=.08)
    line(mid-3.4,body+18,mid-3.4,body+H-18,0,ORANGE,width=.8)
text('Entropy Box',back,YT+OY+D/2+1.3,8.3,True,align='center',angle=180,tracking=.05)
text('JikKey',front,Y+OY-D/2+1.3,7.5,True,align='center',angle=180,tracking=.1)

# Nonprinting technical guide: working bounds include 2.5 mm on all sides.
polygon([(OX-BLEED,OY-BLEED),(OX+NW+BLEED,OY-BLEED),
         (OX+NW+BLEED,OY+NH+BLEED),(OX-BLEED,OY+NH+BLEED)],3,
        stroke=PALE,width=.25,tag='bleed_working_bounds')
for a,b in [(X[0],X[1]),(X[1],X[2]),(X[2],X[3]),(X[3],X[4])]:
    polygon([(a+OX+3,body+3),(b+OX-3,body+3),(b+OX-3,body+H-3),(a+OX+3,body+H-3)],
            3,stroke=PALE,width=.2,tag='3mm_panel_safe_area')
text('GLUE / NO INK',OX+4,Y+OY+H/2,5.2,color=GREY,layer=4,angle=90,align='center')
text('Entropy Box / PAPER PACKAGE',OX,PH-8,9,True,layer=4)
text('Internal target 59 x 59 x 17 mm  |  MGB 300g  |  Stock assumption 0.35 mm',
     OX,PH-12,6,color=GREY,layer=4)
for a,b,name in [(X[0],X[1],'FRONT'),(X[1],X[2],'SIDE'),(X[2],X[3],'BACK'),(X[3],X[4],'SIDE')]:
    text(name,(a+b)/2+OX,body+(3.4 if name=='BACK' else 1.5),4.8,color=GREY,layer=4,align='center')

def dim(a,b,y,label):
    line(a,y,b,y)
    for x in (a,b):line(x,y-1,x,y+1)
    text(label,(a+b)/2,y-3,5.5,color=GREY,layer=4,align='center')
last=0
for x in X:dim(last+OX,x+OX,18,f'{x-last:.2f}');last=x
line(6,Y+OY,6,YT+OY)
for y in (Y+OY,YT+OY):line(5,y,7,y)
text(f'{H:.2f} mm',4,Y+OY+H/2,5.5,color=GREY,layer=4,angle=90,align='center')
text(f'Unfolded cut bounds {NW:.2f} x {NH:.2f} mm  |  Bleed 2.5 mm  |  Safe area 3 mm',
     OX,9,5.8,color=GREY,layer=4)
text('CUT',OX,4.5,5.5,color=CUT,layer=4)
text('CREASE',OX+17,4.5,5.5,color=CREASE,layer=4)
text('GUIDES DO NOT PRINT',OX+40,4.5,5.5,color=GREY,layer=4)
line(PW-62,4.5,PW-12,4.5,width=1)
line(PW-62,3.5,PW-62,5.5);line(PW-12,3.5,PW-12,5.5)
text('50 mm / PRINT AT 100%',PW-37,6.5,4.8,color=GREY,layer=4,align='center')

def draw_pdf(path,ocg=True):
    buf=io.BytesIO();cv=canvas.Canvas(buf,pagesize=(PW*PT,PH*PT),pageCompression=1)
    cv.setTitle('Entropy Box Paper Package 59 x 59 x 17 mm')
    cv.setAuthor('JikKey');cv.setCreator('Entropy_Box Packaging Vector Builder')
    cv.setSubject('Reverse tuck carton; proposed stock caliper 0.35 mm; manufacturing proof required.')
    for idx in range(5):
        if ocg:cv._code.append(f'/OC /L{idx} BDC')
        for item in (o for o in shapes if o['layer']==idx):
            cv.saveState()
            if item['fill'] is not None:cv.setFillColorCMYK(*item['fill'])
            if item['stroke'] is not None:cv.setStrokeColorCMYK(*item['stroke'])
            cv.setLineWidth(item['width']);cv.setDash([d*PT for d in item['dash']])
            p=cv.beginPath()
            for op,co in item['cmd']:
                v=[n*PT for n in co]
                if op=='M':p.moveTo(*v)
                elif op=='L':p.lineTo(*v)
                elif op=='C':p.curveTo(*v)
                elif op=='Z':p.close()
            cv.drawPath(p,stroke=int(item['stroke'] is not None),fill=int(item['fill'] is not None),fillMode=1)
            cv.restoreState()
        if ocg:cv._code.append('EMC')
    cv.showPage();cv.save();path.write_bytes(buf.getvalue())

def n(v):return f'{v:.5f}'.rstrip('0').rstrip('.') or '0'

def native_body():
    result=[]
    for idx,name in enumerate(LAYERS):
        color=[(255,79,79),(255,79,255),(79,255,79),(160,160,160),(79,128,255)][idx]
        printable=int(idx==0)
        result.extend(['%AI5_BeginLayer',f'1 1 1 {printable} 0 0 1 {idx} {color[0]} {color[1]} {color[2]} 0 50 0 Lb',
                       f'({name}) Ln','0 A','0 Xw','0 Ap','0 O','0 R','0 XR'])
        for item in (o for o in shapes if o['layer']==idx):
            if item['fill'] is not None:result.append(' '.join(n(v) for v in item['fill'])+' k')
            if item['stroke'] is not None:result.append(' '.join(n(v) for v in item['stroke'])+' K')
            result.extend(['0 J 0 j '+n(item['width'])+' w 10 M',
                           '['+' '.join(n(v*PT) for v in item['dash'])+'] 0 d'])
            contours=[];current=[]
            for op,co in item['cmd']:
                if op=='M' and current:contours.append(current);current=[]
                current.append((op,co))
            if current:contours.append(current)
            if len(contours)>1:result.append('*u')
            for co in contours:
                closed=False
                # The native D operator must agree with each contour's winding,
                # including counters in the outlined B/O/D lettering.
                points=[];cur=None
                for op,v in co:
                    if op in ('M','L'):
                        cur=(v[0],v[1]);points.append(cur)
                    elif op=='C':
                        start=cur
                        for step in range(1,13):
                            t=step/12;u=1-t
                            points.append((u**3*start[0]+3*u*u*t*v[0]+3*u*t*t*v[2]+t**3*v[4],
                                           u**3*start[1]+3*u*u*t*v[1]+3*u*t*t*v[3]+t**3*v[5]))
                        cur=(v[4],v[5])
                signed=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
                result.append(('1' if signed>0 else '0')+' D')
                for op,v in co:
                    if op=='Z':closed=True;continue
                    vals=[q*PT-(PH*PT if i%2 else 0) for i,q in enumerate(v)]
                    result.append(' '.join(n(q) for q in vals)+' '+{'M':'m','L':'L','C':'c'}[op])
                fill=item['fill'] is not None;stroke=item['stroke'] is not None
                operator=('b' if closed else 'B') if fill and stroke else (('f' if closed else 'F') if fill else ('s' if closed else 'S'))
                result.append(operator)
            if len(contours)>1:result.append('*U')
        result.extend(['LB','%AI5_EndLayer--'])
    result+=['%%PageTrailer','gsave annotatepage grestore showpage','%%Trailer','%%EOF']
    return '\n'.join(result)+'\n'

def embed_native(base_pdf,ai_path):
    original=PdfReader(SRC)
    old_private=original.pages[0]['/PieceInfo']['/Illustrator'].get_object()['/Private'].get_object()
    packed=b''.join(old_private[f'/AIPrivateData{i}'].get_object().get_data() for i in range(2,int(old_private['/NumBlock'])+1))
    assert packed.startswith(b'%AI12_CompressedData')
    old=zlib.decompress(packed[len(b'%AI12_CompressedData'):]).decode('latin1')
    old=re.sub(r'\r\n?', '\n',old)
    prefix=old[:old.index('%%EndSetup')+len('%%EndSetup')]
    prefix=re.sub(r'%AI11_BeginTextDocument.*?%AI11_EndTextDocument','',prefix,flags=re.S)
    points=[(co[i]*PT,co[i+1]*PT-PH*PT) for item in shapes for op,co in item['cmd'] for i in range(0,len(co),2)]
    bounds=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
    bbox=f'{math.floor(bounds[0])} {math.floor(bounds[1])} {math.ceil(bounds[2])} {math.ceil(bounds[3])}'
    hires=' '.join(f'{v:.5f}' for v in bounds)
    substitutions={r'^%%For:.*$':'%%For: (JikKey) ()',r'^%%Title:.*$':f'%%Title: ({ai_path.name})',
        r'^%%CreationDate:.*$':'%%CreationDate: 2026-10-07',
        r'^%%BoundingBox:.*$':f'%%BoundingBox: {bbox}',
        r'^%%HiResBoundingBox:.*$':f'%%HiResBoundingBox: {hires}',
        r'^%AI3_Cropmarks:.*$':f'%AI3_Cropmarks: 0 {-PH*PT:.5f} {PW*PT:.5f} 0',
        r'^%AI3_TileBox:.*$':f'%AI3_TileBox: 0 {-PH*PT:.5f} {PW*PT:.5f} 0',
        r'^%AI5_NumLayers:.*$':'%AI5_NumLayers: 5',r'^%AI9_OpenToView:.*$':'',
        r'^%%PageOrigin:.*$':'%%PageOrigin:0 0'}
    for pattern,value in substitutions.items():prefix=re.sub(pattern,lambda m:value,prefix,flags=re.M)
    prefix=re.sub(r'%_[-.\d ]+ /RealPointRelToROrigin\s+%_ \(PositionPoint2\)',
                  f'%_{PW*PT:.5f} {-PH*PT:.5f} /RealPointRelToROrigin\n%_ (PositionPoint2)',prefix)
    prefix=re.sub(r'%_[-.\d ]+ /RealPointRelToROrigin\s+%_ \(PositionPoint1\)',
                  '%_0 0 /RealPointRelToROrigin\n%_ (PositionPoint1)',prefix)
    prefix=re.sub(r'%_\([^\n]*\) /UnicodeString \(Name\)',
                  '%_(Entropy Box 59x59x17) /UnicodeString (Name)',prefix)
    native=(prefix+'\n'+native_body()).encode('latin1')
    payload=b'%AI12_CompressedData'+zlib.compress(native,9)
    chunks=[payload[i:i+65536] for i in range(0,len(payload),65536)]
    writer=PdfWriter();writer.clone_document_from_reader(PdfReader(base_pdf))
    refs=[];properties=DictionaryObject()
    for i,name in enumerate(LAYERS):
        ocg=DictionaryObject({NameObject('/Type'):NameObject('/OCG'),NameObject('/Name'):TextStringObject(name),
            NameObject('/Usage'):DictionaryObject({NameObject('/Print'):DictionaryObject({NameObject('/PrintState'):NameObject('/ON' if i==0 else '/OFF')})})})
        ref=writer._add_object(ocg);refs.append(ref);properties[NameObject(f'/L{i}')]=ref
    writer.pages[0]['/Resources'][NameObject('/Properties')]=properties
    writer._root_object[NameObject('/OCProperties')]=DictionaryObject({NameObject('/OCGs'):ArrayObject(refs),
        NameObject('/D'):DictionaryObject({NameObject('/Name'):TextStringObject('Entropy Box layers'),
        NameObject('/ON'):ArrayObject(refs),NameObject('/Order'):ArrayObject(refs),NameObject('/BaseState'):NameObject('/ON')})})
    private=DictionaryObject()
    def stream(data):
        st=DecodedStreamObject();st.set_data(data);return writer._add_object(st.flate_encode())
    header=prefix[:prefix.index('%%EndComments')+len('%%EndComments')].encode('latin1')
    private[NameObject('/AIMetaData')]=stream(header)
    private[NameObject('/AIPrivateData1')]=stream((f'%%BoundingBox: {bbox}\n%%HiResBoundingBox: {hires}\n').encode())
    for i,ch in enumerate(chunks,2):private[NameObject(f'/AIPrivateData{i}')]=stream(ch)
    for key in ('/ContainerVersion','/CreatorVersion','/RoundtripStreamType','/RoundtripVersion'):
        private[NameObject(key)]=NumberObject(int(old_private[key]))
    private[NameObject('/NumBlock')]=NumberObject(len(chunks)+1)
    illustrator=DictionaryObject({NameObject('/LastModified'):TextStringObject('D:20261007000000+09\'00\''),
                                  NameObject('/Private'):writer._add_object(private)})
    writer.pages[0][NameObject('/PieceInfo')]=DictionaryObject({NameObject('/Illustrator'):writer._add_object(illustrator)})
    writer.pdf_header=b'%PDF-1.5'
    with ai_path.open('wb') as f:writer.write(f)
    return native

# Save the annotated 1:1 construction proof, then set the manufacturing artboard
# to the physical cut bounds plus 2.5 mm working allowance on each side.
draw_pdf(OUT/'Entropy_Box_Paper_Package_1to1.pdf',False)
exe=Path('C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
subprocess.run([str(exe),'-png','-r','300','-singlefile',str(OUT/'Entropy_Box_Paper_Package_1to1.pdf'),
                str(OUT/'Entropy_Box_Paper_Package_Dimension_Guide')],check=True)
guide_board=[PW,PH]
dx,dy=OX-BLEED,OY-BLEED
for item in shapes:
    item['cmd']=[(op,[v-(dx if i%2==0 else dy) for i,v in enumerate(coordinates)])
                 for op,coordinates in item['cmd']]
PW,PH=NW+2*BLEED,NH+2*BLEED
OX=OY=BLEED

# Machine-readable source supports verification and future caliper adjustments.
geometry=dict(product_mm=[58,58,15.6],minimum_target_clearance_mm=[IW,IH,ID],
    paper='MGB 300g',assumed_caliper_mm=T,score_panel_mm=[W,H,D],
    compensation={'width':'internal + two calipers including local glue seam','height':'internal + three calipers for dust/closure overlap',
                  'depth':'internal + two calipers including the local inserted tuck flap'},
    outside_envelope_estimate_mm=[W+T,H+T,D+T],glue_mm=G,tuck_mm=TAB,
    bleed_mm=BLEED,safe_mm=3,cut_bounds_mm=[NW,NH],working_bounds_mm=[NW+2*BLEED,NH+2*BLEED],
    artboard_mm=[PW,PH],dimension_guide_artboard_mm=guide_board,coordinate_origin_mm=[OX,OY],layers=LAYERS,vector_shapes=shapes,
    source_template='Provided skin box 60x160mm, reverse tuck closures; unchanged cut/crease geometry from the previous package',
    official_product_name='Entropy Box',official_product_reference='https://jikkey.com/ko/product/4',
    illustration_reference='White lid, dark base and transparent window shown on the official product page. Original vector illustration; conceptual appearance.',
    illustration_die_count=drawn_die_count,
    limitation='300g does not specify paper caliper. Fit and tuck performance require a folded stock sample and converter crease allowance. Illustrator application opening has not been tested on this host.')
(OUT/'Package_Dimensions.json').write_text(json.dumps(geometry,indent=2),encoding='utf-8')
base=OUT/'_vector_preview.pdf';draw_pdf(base,True)
ai=OUT/'Entropy_Box_Paper_Package_59x59x17.ai';native=embed_native(base,ai)
# Companion SVG keeps layers, curves and physical millimetre units accessible.
import xml.etree.ElementTree as ET
svg=ET.Element('svg',xmlns='http://www.w3.org/2000/svg',width=f'{PW}mm',height=f'{PH}mm',viewBox=f'0 0 {PW} {PH}')
def rgb(col):
    if col is None:return 'none'
    return '#'+''.join(f'{round(255*(1-min(1,v+col[3]))):02x}' for v in col[:3])
for i,name in enumerate(LAYERS):
    group=ET.SubElement(svg,'g',id=name,transform=f'translate(0 {PH}) scale(1 -1)')
    for obj in (o for o in shapes if o['layer']==i):
        path=' '.join(op+(' '.join(n(v) for v in co)) for op,co in obj['cmd'])
        a=dict(d=path,fill=rgb(obj['fill']),stroke=rgb(obj['stroke']))
        a['stroke-width']=n(obj['width']/PT)
        if obj['dash']:a['stroke-dasharray']=' '.join(n(v) for v in obj['dash'])
        ET.SubElement(group,'path',a)
ET.ElementTree(svg).write(OUT/'Entropy_Box_Paper_Package_59x59x17.svg',encoding='utf-8',xml_declaration=True)
subprocess.run([str(exe),'-png','-r','300','-singlefile',str(ai),str(OUT/'Entropy_Box_Paper_Package_59x59x17')],check=True)
base.unlink()
print(json.dumps(dict(ai=str(ai),native_bytes=len(native),shapes=len(shapes),cut_bounds_mm=[NW,NH],score_panel_mm=[W,H,D]),indent=2))
