from pathlib import Path
import json,re,zlib,math,hashlib,xml.etree.ElementTree as ET
from pypdf import PdfReader

root=Path(__file__).resolve().parent.parent
g=json.loads((root/'Package_Dimensions.json').read_text());mm=72/25.4
pw,ph=g['artboard_mm'];objects=g['vector_shapes']
ai=root/'Entropy_Box_Paper_Package_59x59x17.ai';reader=PdfReader(ai)
assert len(reader.pages)==1
page=reader.pages[0]
assert abs(float(page.mediabox.width)/mm-pw)<1e-4
assert abs(float(page.mediabox.height)/mm-ph)<1e-4
assert [str(v.get_object()['/Name']) for v in reader.trailer['/Root']['/OCProperties']['/OCGs']]==g['layers']
private=page['/PieceInfo']['/Illustrator'].get_object()['/Private'].get_object()
packed=b''.join(private[f'/AIPrivateData{i}'].get_object().get_data() for i in range(2,int(private['/NumBlock'])+1))
assert packed.startswith(b'%AI12_CompressedData')
native=zlib.decompress(packed[len(b'%AI12_CompressedData'):]).decode('latin1')
assert '(Entropy Box 59x59x17) /UnicodeString (Name)' in native
assert f'{pw*mm:.5f} {-ph*mm:.5f} /RealPointRelToROrigin' in native
body=native.split('%%EndSetup',1)[1]

# Independently parse each native layer's geometry, paint and compound paths.
decoded=[];layer=-1;fill=stroke=None;width=1;dash=[];path=[];compound=None;compound_paint=None;flags=[]
for raw in body.splitlines():
    line=raw.strip()
    if not line or line.startswith('%'):continue
    parts=line.split();op=parts[-1]
    if op=='Lb':
        layer+=1;flags.append(int(parts[3]))
    elif op=='k':fill=list(map(float,parts[:-1]))
    elif op=='K':stroke=list(map(float,parts[:-1]))
    elif ' w ' in ' '+line+' ':
        match=re.search(r'([.\d]+) w',line);width=float(match[1])
    elif op=='d':
        dash=[float(v)/mm for v in re.search(r'\[([^]]*)\]',line)[1].split()]
    elif op in ('m','L','c'):
        values=list(map(float,parts[:-1]));co=[v/mm+(ph if i%2 else 0) for i,v in enumerate(values)]
        path.append(({'m':'M','L':'L','c':'C'}[op],co))
    elif op=='*u':compound=[];compound_paint=None
    elif op=='*U':
        assert compound is not None
        decoded.append(dict(layer=layer,cmd=compound,
                            fill=fill if compound_paint in ('f','b') else None,
                            stroke=stroke if compound_paint in ('s','b') else None,
                            width=width,dash=dash));compound=None
    elif op in ('f','F','s','S','b','B'):
        if op.islower():path.append(('Z',[]))
        if compound is not None:compound.extend(path);compound_paint=op.lower()
        else:decoded.append(dict(layer=layer,cmd=path,fill=fill if op.lower() in ('f','b') else None,
                                  stroke=stroke if op.lower() in ('s','b') else None,width=width,dash=dash))
        path=[]
assert flags==[1,0,0,0,0]
ordered=[o for i in range(5) for o in objects if o['layer']==i]
assert len(decoded)==len(ordered)
for index,(a,b) in enumerate(zip(decoded,ordered)):
    assert a['layer']==b['layer'] and len(a['cmd'])==len(b['cmd']),index
    for (op1,c1),(op2,c2) in zip(a['cmd'],b['cmd']):
        assert op1==op2 and len(c1)==len(c2),index
        assert all(abs(v-w)<5e-6 for v,w in zip(c1,c2)),index
    assert a['fill']==b['fill'] and a['stroke']==b['stroke'],index
    assert abs(a['width']-b['width'])<1e-6 and len(a['dash'])==len(b['dash'])
    assert all(abs(v-w)<5e-6 for v,w in zip(a['dash'],b['dash']))

def flatten(cmd):
    p=[];cur=None
    for op,v in cmd:
        if op in ('M','L'):cur=(v[0],v[1]);p.append(cur)
        elif op=='C':
            start=cur
            for i in range(1,21):
                t=i/20;u=1-t
                p.append((u**3*start[0]+3*u*u*t*v[0]+3*u*t*t*v[2]+t**3*v[4],
                          u**3*start[1]+3*u*u*t*v[1]+3*u*t*t*v[3]+t**3*v[5]))
            cur=(v[4],v[5])
    result=[]
    for x in p:
        if not result or math.dist(x,result[-1])>1e-8:result.append(x)
    if math.dist(result[0],result[-1])<1e-8:result.pop()
    return result

cut=next(o for o in objects if o['tag']=='single_closed_cut_contour')
assert cut['cmd'][-1][0]=='Z' and sum(op=='M' for op,co in cut['cmd'])==1
poly=flatten(cut['cmd']);edges=list(zip(poly,poly[1:]+poly[:1]))
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
for i,(a,b) in enumerate(edges):
    for j,(c,d) in enumerate(edges[i+1:],i+1):
        if j==i+1 or (i==0 and j==len(edges)-1):continue
        assert not (cross(a,b,c)*cross(a,b,d)<-1e-12 and cross(c,d,a)*cross(c,d,b)<-1e-12),('crossing cut',i,j)
actual=[max(v[k] for v in poly)-min(v[k] for v in poly) for k in (0,1)]
assert all(abs(a-b)<1e-6 for a,b in zip(actual,g['cut_bounds_mm']))
creases=[o for o in objects if o['layer']==2];assert len(creases)==12
assert all(o['width']==.25 and len(o['cmd'])==2 for o in creases)
# Ink is outside the glue tab and all type is vector paths, not live fonts/images.
assert all(min(v[0] for v in flatten(o['cmd']))>=g['coordinate_origin_mm'][0]+g['glue_mm'] for o in objects if o['layer']==0)
ops=page.get_contents().operations
assert not any(op in (b'Tj',b'TJ',b'Do') for args,op in ops)
assert sum(op==b'BDC' for args,op in ops)==5
svg=ET.parse(root/'Entropy_Box_Paper_Package_59x59x17.svg').getroot()
assert len(svg)==5 and sum(len(gr) for gr in svg)==len(objects)

t=g['assumed_caliper_mm'];w,h,d=g['score_panel_mm']
clear=[w-2*t,h-3*t,d-2*t]
assert all(abs(a-b)<1e-6 for a,b in zip(clear,g['minimum_target_clearance_mm']))
assert all(a>b for a,b in zip(clear,g['product_mm']))
previous=root.parent/'dicebox-paper-package/Package_Dimensions.json'
if previous.is_file():
    old=json.loads(previous.read_text())
    for key in ('product_mm','minimum_target_clearance_mm','score_panel_mm','cut_bounds_mm','artboard_mm'):
        assert old[key]==g[key],key
    old_dieline=[o for o in old['vector_shapes'] if o['layer'] in (1,2)]
    new_dieline=[o for o in objects if o['layer'] in (1,2)]
    assert old_dieline==new_dieline
assert g['official_product_name']=='Entropy Box'
assert sum(o['tag']=='product_illustration_die_top' for o in objects)==25
assert not any('DICEBOX' in o['tag'].upper() for o in objects)
report=dict(native_illustrator_stream_present=True,native_pdf_vectors_synchronized=True,
    compared_vector_shapes=len(objects),native_layer_print_flags=flags,pdf_ocg_count=5,
    fonts_outlined=True,external_images=0,closed_cut_contours=1,self_crossing_cut=False,
    crease_count=12,cut_bounds_mm=actual,proposed_minimum_internal_mm=clear,
    artwork_on_glue_tab=False,physical_stock_test=False,illustrator_application_open_test=False,
    official_product_name='Entropy Box',product_illustration_dice=25,
    dieline_unchanged_from_previous=(previous.is_file()),
    limitation='Paper caliper is assumed, not measured. Native stream structure/geometry and embedded PDF checked; no Adobe Illustrator application is installed to test opening or saving. Fold/crease production allowance and actual fit require a stock sample.',
    ai_sha256=hashlib.sha256(ai.read_bytes()).hexdigest())
(root/'Package_Validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
